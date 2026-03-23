import asyncio

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.import_routes import confirm_import
from app.models.bonus_entry import BonusEntry  # noqa: F401
from app.models.parser_template import ParserTemplate
from app.models.product_category import ProductCategory  # noqa: F401
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem  # noqa: F401
from app.schemas.import_schemas import ConfirmRequest


def _session_with_template() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    session.add(ParserTemplate(slug="kaufland", display_name="Kaufland eBon"))
    session.commit()
    return session


def _receipt(**overrides: object) -> ConfirmRequest:
    values = {
        "purchased_at": overrides.pop("purchased_at", "2026-03-17T12:00:00"),
        "store_name": overrides.pop("store_name", "Kaufland"),
        "store_address": overrides.pop("store_address", "Example Str. 1"),
        "store_id": overrides.pop("store_id", "1234"),
        "register_nr": overrides.pop("register_nr", 7),
        "bon_nr": overrides.pop("bon_nr", "42"),
        "beleg_nr": overrides.pop("beleg_nr", None),
        "total_amount": overrides.pop("total_amount", 9.99),
        "tse_transaction": overrides.pop("tse_transaction", None),
        "source_filename": overrides.pop("source_filename", "receipt.txt"),
        "total_bonus": overrides.pop("total_bonus", 0.0),
        "bonus_balance": overrides.pop("bonus_balance", None),
        "template_id": overrides.pop("template_id", None),
        "items": overrides.pop("items", []),
        "bonus_entries": overrides.pop("bonus_entries", []),
    }
    values.update(overrides)
    return ConfirmRequest(**values)


@pytest.mark.parametrize("purchased_at", ["", "   "])
def test_confirm_requires_purchase_datetime(purchased_at: str) -> None:
    session = _session_with_template()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            confirm_import(_receipt(purchased_at=purchased_at), session=session)
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Purchase date/time is required"
    session.close()


def test_confirm_rejects_invalid_purchase_datetime() -> None:
    session = _session_with_template()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            confirm_import(_receipt(purchased_at="not-a-datetime"), session=session)
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid datetime format"
    session.close()


def test_confirm_accepts_valid_purchase_datetime() -> None:
    session = _session_with_template()

    response = asyncio.run(confirm_import(_receipt(), session=session))
    receipt = session.exec(select(Receipt).where(Receipt.id == response.id)).one()

    assert response.message == "Receipt imported with 0 items"
    assert receipt.purchased_at.isoformat() == "2026-03-17T12:00:00"
    session.close()
