import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.import_routes import confirm_import
from app.api.receipt_routes import update_item_category
from app.models.bonus_entry import BonusEntry  # noqa: F401
from app.models.parser_template import ParserTemplate
from app.models.product_category import ProductCategory
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
from app.schemas.import_schemas import ConfirmRequest


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _confirm_request(**overrides: object) -> ConfirmRequest:
    values = {
        "store_name": "Kaufland",
        "store_address": "Example Str. 1",
        "store_id": "1234",
        "register_nr": 7,
        "bon_nr": "42",
        "beleg_nr": None,
        "purchased_at": "2026-03-17T12:00:00",
        "total_amount": 9.99,
        "tse_transaction": None,
        "source_filename": "receipt.txt",
        "items": [],
        "bonus_entries": [],
        "total_bonus": 0.0,
        "bonus_balance": None,
        "template_id": None,
    }
    values.update(overrides)
    return ConfirmRequest(**values)


def _confirm_item(**overrides: object) -> dict[str, object]:
    values = {
        "raw_name": "Milk",
        "display_name": "Milk",
        "unit_price": 1.99,
        "quantity": 1,
        "total_price": 1.99,
        "vat_class": "B",
        "is_deposit": False,
        "category_id": None,
        "is_manual_assignment": False,
    }
    values.update(overrides)
    return values


def test_confirm_import_rejects_invalid_template_id() -> None:
    session = _session()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(confirm_import(_confirm_request(template_id=999), session=session))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid template_id"
    session.close()


def test_confirm_import_rejects_invalid_item_category_id() -> None:
    session = _session()
    session.add(ParserTemplate(slug="kaufland", display_name="Kaufland eBon"))
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            confirm_import(
                _confirm_request(items=[_confirm_item(category_id=999)]),
                session=session,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid category_id"
    session.close()


def test_update_item_category_rejects_invalid_category_id() -> None:
    session = _session()
    receipt = Receipt(
        purchased_at=datetime(2026, 3, 17, 12, 0, 0),
        store_name="Kaufland",
        store_address="Example Str. 1",
        total_amount=9.99,
        source_filename="receipt.txt",
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    assert receipt.id is not None

    item = ReceiptItem(
        receipt_id=receipt.id,
        raw_name="Milk",
        display_name="Milk",
        unit_price=1.99,
        quantity=1,
        total_price=1.99,
        vat_class="B",
        is_deposit=False,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.id is not None

    with pytest.raises(HTTPException) as exc_info:
        update_item_category(receipt.id, item.id, {"category_id": 999}, session=session)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid category_id"
    session.close()


def test_update_item_category_accepts_null_category_id() -> None:
    session = _session()
    category = ProductCategory(name="Dairy")
    session.add(category)
    session.commit()
    session.refresh(category)
    assert category.id is not None

    receipt = Receipt(
        purchased_at=datetime(2026, 3, 17, 12, 0, 0),
        store_name="Kaufland",
        store_address="Example Str. 1",
        total_amount=9.99,
        source_filename="receipt.txt",
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    assert receipt.id is not None

    item = ReceiptItem(
        receipt_id=receipt.id,
        raw_name="Milk",
        display_name="Milk",
        unit_price=1.99,
        quantity=1,
        total_price=1.99,
        vat_class="B",
        is_deposit=False,
        category_id=category.id,
        is_manual_assignment=False,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.id is not None

    response = update_item_category(
        receipt.id,
        item.id,
        {"category_id": None},
        session=session,
    )

    assert response["category_id"] is None
    assert response["is_manual_assignment"] is True
    session.refresh(item)
    assert item.category_id is None
    session.close()
