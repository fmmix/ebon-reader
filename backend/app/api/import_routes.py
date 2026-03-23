import json
import os
import shutil
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.bonus_entry import BonusEntry
from app.models.parser_template import ParserTemplate
from app.models.product_category import ProductCategory
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
from app.schemas.import_schemas import (
    BonusEntryResponse,
    ConfirmRequest,
    ConfirmResponse,
    DebugTextResponse,
    ParsedItemResponse,
    PreviewResponse,
)
from app.services.categorizer import Categorizer
from app.services.parser.base import ParsedReceipt
from app.services.parser.registry import (
    parse_ebon,
    parse_json_payload,
    parse_text_payload,
)

from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/import", tags=["import"])

SCRAPER_PATH = Path(__file__).resolve().parents[3] / "tools" / "lidl_scraper.js"
SUPPORTED_PREVIEW_EXTENSIONS = {".pdf", ".json", ".txt"}


def _decode_text_payload(raw_payload: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw_payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_payload.decode("utf-8", errors="replace")


def _find_duplicate_receipt(
    session: Session,
    *,
    tse_transaction: str | None,
    store_id: str | None,
    register_nr: int | None,
    bon_nr: str | None,
) -> Receipt | None:
    if tse_transaction:
        return session.exec(
            select(Receipt).where(Receipt.tse_transaction == tse_transaction)
        ).first()

    if store_id and register_nr is not None and bon_nr:
        return session.exec(
            select(Receipt).where(
                Receipt.store_id == store_id,
                Receipt.register_nr == register_nr,
                Receipt.bon_nr == bon_nr,
            )
        ).first()

    return None


def _build_preview_response(
    receipt: ParsedReceipt,
    detected_slug: str,
    session: Session,
    categorizer: Categorizer,
) -> PreviewResponse:
    template = session.exec(
        select(ParserTemplate).where(ParserTemplate.slug == detected_slug)
    ).first()

    is_duplicate = (
        _find_duplicate_receipt(
            session,
            tse_transaction=receipt.tse_transaction,
            store_id=receipt.store_id,
            register_nr=receipt.register_nr,
            bon_nr=receipt.bon_nr,
        )
        is not None
    )

    preview_items: list[ParsedItemResponse] = []
    for item in receipt.items:
        (
            cat_id,
            confidence,
            method,
            matched_rule_keyword,
            matched_rule_match_type,
            matched_rule_priority,
        ) = categorizer.categorize(item.raw_name)
        preview_items.append(
            ParsedItemResponse(
                raw_name=item.raw_name,
                display_name=item.raw_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                total_price=item.total_price,
                vat_class=item.vat_class,
                is_deposit=item.is_deposit,
                category_id=cat_id,
                confidence=confidence,
                method=method,
                matched_rule_keyword=matched_rule_keyword,
                matched_rule_match_type=matched_rule_match_type,
                matched_rule_priority=matched_rule_priority,
            )
        )

    bonus_entries = [
        BonusEntryResponse(
            type=b.type,
            description=b.description,
            amount=b.amount,
        )
        for b in receipt.bonus_entries
    ]
    items_total = sum(item.total_price for item in preview_items)
    deduction_total = sum(
        b.amount
        for b in receipt.bonus_entries
        if b.type in {"instant_discount", "basket_discount"}
    )

    return PreviewResponse(
        store_name=receipt.store_name,
        store_address=receipt.store_address,
        store_id=receipt.store_id,
        register_nr=receipt.register_nr,
        bon_nr=receipt.bon_nr,
        beleg_nr=receipt.beleg_nr,
        purchased_at=receipt.purchased_at.isoformat() if receipt.purchased_at else "",
        total_amount=receipt.total_amount,
        tse_transaction=receipt.tse_transaction,
        is_duplicate=is_duplicate,
        items=preview_items,
        bonus_entries=bonus_entries,
        total_bonus=receipt.total_bonus,
        bonus_balance=receipt.bonus_balance,
        computed_total=round(items_total - deduction_total, 2),
        template_id=template.id if template else None,
        template_slug=detected_slug,
        template_name=template.display_name if template else detected_slug,
    )


def _parse_required_purchase_datetime(value: str) -> datetime:
    purchased_at_raw = value.strip()
    if not purchased_at_raw:
        raise HTTPException(
            status_code=400,
            detail="Purchase date/time is required",
        )

    try:
        return datetime.fromisoformat(purchased_at_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")


@router.get("/lidl-scraper", response_class=PlainTextResponse)
async def get_lidl_scraper():
    """Serve the LIDL scraper script for copy-to-clipboard."""
    if not SCRAPER_PATH.exists():
        raise HTTPException(status_code=404, detail="Scraper script not found")
    return PlainTextResponse(SCRAPER_PATH.read_text(encoding="utf-8"))


@router.post("/debug-text", response_model=DebugTextResponse)
async def debug_extract_text(file: UploadFile = File(...)) -> DebugTextResponse:
    """Upload a PDF and return raw extracted text without parser preprocessing."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_path: Path | None = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = Path(temp_file.name)

    try:
        import pdfplumber

        with pdfplumber.open(str(temp_path)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return DebugTextResponse(raw_text="\n".join(pages))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Failed to extract raw PDF text: {e}"
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.post("/preview", response_model=list[PreviewResponse])
async def preview_ebon(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> list[PreviewResponse]:
    """Upload a PDF/JSON/TXT payload, parse receipts, and return previews."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    extension = Path(file.filename).suffix.lower()
    if extension not in SUPPORTED_PREVIEW_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .pdf, .json, and .txt files are supported",
        )

    parsed_receipts: list[ParsedReceipt]
    detected_slug: str

    temp_path: Path | None = None
    try:
        if extension == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                shutil.copyfileobj(file.file, temp_file)
                temp_path = Path(temp_file.name)

            receipt, detected_slug = parse_ebon(temp_path)
            parsed_receipts = [receipt]
        elif extension == ".json":
            raw_payload = await file.read()
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON payload in '{file.filename}': {e}",
                )

            if not isinstance(payload, dict):
                raise HTTPException(
                    status_code=400,
                    detail="JSON payload must be an object",
                )

            parsed_receipts, detected_slug = parse_json_payload(payload)
        else:
            raw_payload = await file.read()
            text_payload = _decode_text_payload(raw_payload)

            parsed_receipts, detected_slug = parse_text_payload(
                text_payload,
                source_filename=file.filename,
            )
    except Exception as e:
        debug_log_path = os.getenv("EBON_DEBUG_LOG")
        if debug_log_path:
            try:
                timestamp = datetime.now().isoformat(timespec="seconds")
                source_name = file.filename or "<unknown>"
                log_entry = (
                    f"[{timestamp}] import preview parse failure\n"
                    f"filename={source_name}\n"
                    f"temp_path={temp_path}\n"
                    f"error={e}\n"
                    f"traceback:\n{traceback.format_exc()}\n"
                )
                debug_log = Path(debug_log_path)
                debug_log.parent.mkdir(parents=True, exist_ok=True)
                with debug_log.open("a", encoding="utf-8") as handle:
                    handle.write(log_entry)
            except Exception:
                pass
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse '{file.filename}': {e}",
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    categorizer = Categorizer(session)
    return [
        _build_preview_response(receipt, detected_slug, session, categorizer)
        for receipt in parsed_receipts
    ]


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_import(
    body: ConfirmRequest,
    session: Session = Depends(get_session),
) -> ConfirmResponse:
    """Persist the reviewed receipt, items, and bonus entries to the database."""

    # Duplicate guard
    existing = _find_duplicate_receipt(
        session,
        tse_transaction=body.tse_transaction,
        store_id=body.store_id,
        register_nr=body.register_nr,
        bon_nr=body.bon_nr,
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Receipt already imported (ID {existing.id})",
        )

    # Parse datetime
    purchased_at = _parse_required_purchase_datetime(body.purchased_at)

    if (
        body.template_id is not None
        and session.get(ParserTemplate, body.template_id) is None
    ):
        raise HTTPException(status_code=400, detail="Invalid template_id")

    # Create receipt
    receipt = Receipt(
        store_name=body.store_name,
        store_address=body.store_address,
        store_id=body.store_id,
        register_nr=body.register_nr,
        bon_nr=body.bon_nr,
        beleg_nr=body.beleg_nr,
        purchased_at=purchased_at,
        total_amount=body.total_amount,
        tse_transaction=body.tse_transaction,
        source_filename=body.source_filename,
        total_bonus=body.total_bonus,
        bonus_balance=body.bonus_balance,
        currency="EUR",
        template_id=body.template_id,
    )
    session.add(receipt)
    session.flush()  # Get the receipt ID
    if receipt.id is None:
        raise HTTPException(status_code=500, detail="Failed to create receipt")
    receipt_id = receipt.id

    # Create items
    for item in body.items:
        if (
            item.category_id is not None
            and session.get(ProductCategory, item.category_id) is None
        ):
            raise HTTPException(status_code=400, detail="Invalid category_id")

        receipt_item = ReceiptItem(
            receipt_id=receipt_id,
            raw_name=item.raw_name,
            display_name=item.display_name,
            unit_price=item.unit_price,
            quantity=item.quantity,
            total_price=item.total_price,
            vat_class=item.vat_class,
            is_deposit=item.is_deposit,
            category_id=item.category_id,
            is_manual_assignment=item.is_manual_assignment,
        )
        session.add(receipt_item)

    # Create bonus entries
    for bonus in body.bonus_entries:
        entry = BonusEntry(
            receipt_id=receipt_id,
            type=bonus.type,
            description=bonus.description,
            amount=bonus.amount,
        )
        session.add(entry)

    session.commit()
    session.refresh(receipt)

    return ConfirmResponse(
        id=receipt_id,
        message=f"Receipt imported with {len(body.items)} items",
    )
