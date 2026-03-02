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
from app.services.parser.rewe_parser import parse_rewe_ebon

router = APIRouter(prefix="/api/import", tags=["import"])


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
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"Failed to extract raw PDF text: {e}"
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.post("/preview", response_model=PreviewResponse)
async def preview_ebon(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> PreviewResponse:
    """Upload a PDF, extract items, auto-categorize, and return a preview."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_path: Path | None = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = Path(temp_file.name)

    try:
        receipt = parse_rewe_ebon(temp_path)
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
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    # Check for duplicates via TSE transaction ID
    is_duplicate = False
    if receipt.tse_transaction:
        existing = session.exec(
            select(Receipt).where(Receipt.tse_transaction == receipt.tse_transaction)
        ).first()
        is_duplicate = existing is not None

    # Auto-categorize items
    categorizer = Categorizer(session)
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
        computed_total=round(sum(item.total_price for item in preview_items), 2),
    )


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_import(
    body: ConfirmRequest,
    session: Session = Depends(get_session),
) -> ConfirmResponse:
    """Persist the reviewed receipt, items, and bonus entries to the database."""

    # Duplicate guard
    if body.tse_transaction:
        existing = session.exec(
            select(Receipt).where(Receipt.tse_transaction == body.tse_transaction)
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Receipt already imported (ID {existing.id})",
            )

    # Parse datetime
    purchased_at = None
    if body.purchased_at:
        try:
            purchased_at = datetime.fromisoformat(body.purchased_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime format")

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
    )
    session.add(receipt)
    session.flush()  # Get the receipt ID

    # Create items
    for item in body.items:
        receipt_item = ReceiptItem(
            receipt_id=receipt.id,
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
            receipt_id=receipt.id,
            type=bonus.type,
            description=bonus.description,
            amount=bonus.amount,
        )
        session.add(entry)

    session.commit()
    session.refresh(receipt)

    return ConfirmResponse(
        id=receipt.id,
        message=f"Receipt imported with {len(body.items)} items",
    )
