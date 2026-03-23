import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.import_routes import _build_preview_response, confirm_import
from app.models.bonus_entry import BonusEntry  # noqa: F401
from app.models.parser_template import ParserTemplate
from app.models.product_category import ProductCategory  # noqa: F401
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem  # noqa: F401
from app.schemas.import_schemas import ConfirmRequest
from app.services.parser.base import ParsedItem, ParsedReceipt


class FakeCategorizer:
    def categorize(
        self, _raw_name: str
    ) -> tuple[int | None, float, str, str | None, str | None, int | None]:
        return (None, 0.0, "none", None, None, None)


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


EXISTING_PURCHASED_AT = datetime(2026, 3, 17, 10, 0, 0)


def test_preview_marks_duplicate_by_tse() -> None:
    session = _session_with_template()
    session.add(
        Receipt(
            purchased_at=EXISTING_PURCHASED_AT,
            store_name="Kaufland",
            store_address="Example Str. 1",
            total_amount=9.99,
            tse_transaction="TSE-123",
            source_filename="existing.txt",
        )
    )
    session.commit()

    preview = _build_preview_response(
        ParsedReceipt(
            store_name="Kaufland",
            tse_transaction="TSE-123",
            total_amount=9.99,
            items=[ParsedItem(raw_name="Milk", unit_price=9.99)],
        ),
        "kaufland",
        session,
        FakeCategorizer(),
    )

    assert preview.is_duplicate is True
    session.close()


def test_preview_marks_duplicate_by_fallback_identity() -> None:
    session = _session_with_template()
    session.add(
        Receipt(
            purchased_at=EXISTING_PURCHASED_AT,
            store_name="Kaufland",
            store_address="Example Str. 1",
            store_id="1234",
            register_nr=7,
            bon_nr="42",
            total_amount=9.99,
            source_filename="existing.txt",
        )
    )
    session.commit()

    preview = _build_preview_response(
        ParsedReceipt(
            store_name="Kaufland",
            store_id="1234",
            register_nr=7,
            bon_nr="42",
            total_amount=9.99,
            items=[ParsedItem(raw_name="Milk", unit_price=9.99)],
        ),
        "kaufland",
        session,
        FakeCategorizer(),
    )

    assert preview.is_duplicate is True
    session.close()


def test_confirm_rejects_duplicate_by_fallback_identity() -> None:
    session = _session_with_template()
    session.add(
        Receipt(
            purchased_at=EXISTING_PURCHASED_AT,
            store_name="Kaufland",
            store_address="Example Str. 1",
            store_id="1234",
            register_nr=7,
            bon_nr="42",
            total_amount=9.99,
            source_filename="existing.txt",
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(confirm_import(_receipt(), session=session))

    assert exc_info.value.status_code == 409
    session.close()


def test_confirm_allows_insert_when_fallback_identity_is_incomplete() -> None:
    session = _session_with_template()
    session.add(
        Receipt(
            purchased_at=EXISTING_PURCHASED_AT,
            store_name="Kaufland",
            store_address="Example Str. 1",
            store_id="1234",
            register_nr=7,
            bon_nr="42",
            total_amount=9.99,
            source_filename="existing.txt",
        )
    )
    session.commit()

    response = asyncio.run(
        confirm_import(_receipt(register_nr=None, bon_nr="42"), session=session)
    )

    receipts = session.exec(select(Receipt).order_by(Receipt.id)).all()
    assert response.id == receipts[-1].id
    assert len(receipts) == 2
    session.close()
