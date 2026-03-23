import io

import pdfplumber
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, delete, func, select

from app.core.database import get_session
from app.models.bonus_entry import BonusEntry
from app.models.categorize_rule import CategorizeRule
from app.models.learned_mapping import LearnedMapping
from app.models.product_category import ProductCategory
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
from app.models.taxonomy_backup import TaxonomyBackup
from app.schemas.settings_schemas import (
    SyntheticDeleteResponse,
    SyntheticGenerateRequest,
    SyntheticGenerateResponse,
)
from app.services.seeder import seed_defaults
from app.services.synthetic_data import (
    delete_synthetic_receipts,
    generate_synthetic_receipts,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _count_rows(session: Session, model: type) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


@router.post("/debug-import-text")
async def debug_import_text(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        pdf_bytes = await file.read()
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        raise HTTPException(status_code=422, detail="Failed to extract text from PDF")

    text = "\n".join(page_texts)
    return {
        "text": text,
        "pages": len(page_texts),
        "characters": len(text),
    }


@router.post("/hard-reset")
def hard_reset_data(session: Session = Depends(get_session)) -> dict:
    deleted_counts = {
        "receipt_item": _count_rows(session, ReceiptItem),
        "bonus_entry": _count_rows(session, BonusEntry),
        "receipt": _count_rows(session, Receipt),
        "learned_mapping": _count_rows(session, LearnedMapping),
        "categorize_rule": _count_rows(session, CategorizeRule),
        "product_category": _count_rows(session, ProductCategory),
        "taxonomy_backup": _count_rows(session, TaxonomyBackup),
    }

    session.exec(delete(ReceiptItem))
    session.exec(delete(BonusEntry))
    session.exec(delete(Receipt))
    session.exec(delete(LearnedMapping))
    session.exec(delete(CategorizeRule))
    session.exec(delete(ProductCategory))
    session.exec(delete(TaxonomyBackup))
    session.commit()

    seed_defaults(session)

    return {
        "message": "Hard reset complete. App data cleared and defaults reseeded.",
        "deleted": deleted_counts,
    }


@router.post("/synthetic/generate", response_model=SyntheticGenerateResponse)
def generate_synthetic_data(
    body: SyntheticGenerateRequest,
    session: Session = Depends(get_session),
) -> SyntheticGenerateResponse:
    try:
        result = generate_synthetic_receipts(
            session=session,
            store=body.store,
            count_per_store=body.count_per_store,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SyntheticGenerateResponse(
        stores=result.stores,
        total_inserted=result.total_inserted,
        total_skipped=result.total_skipped,
    )


@router.delete("/synthetic", response_model=SyntheticDeleteResponse)
def delete_synthetic_data(
    session: Session = Depends(get_session),
) -> SyntheticDeleteResponse:
    return SyntheticDeleteResponse(deleted=delete_synthetic_receipts(session))
