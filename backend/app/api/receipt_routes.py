from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func, col

from app.core.database import get_session
from app.models.bonus_entry import BonusEntry
from app.models.product_category import ProductCategory
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
from app.schemas.receipt_schemas import (
    BonusEntryResponse,
    ReceiptDetail,
    ReceiptItemResponse,
    ReceiptListItem,
)

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


@router.get("/", response_model=list[ReceiptListItem])
def list_receipts(session: Session = Depends(get_session)) -> list[ReceiptListItem]:
    """List all receipts with item count, sorted by date descending."""
    item_count_subquery = (
        select(
            col(ReceiptItem.receipt_id).label("receipt_id"),
            func.count(col(ReceiptItem.id)).label("item_count"),
        )
        .group_by(col(ReceiptItem.receipt_id))
        .subquery()
    )

    redeemed_bonus_subquery = (
        select(
            col(BonusEntry.receipt_id).label("receipt_id"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("redeemed_bonus"),
        )
        .where(col(BonusEntry.type) == "redeemed")
        .group_by(col(BonusEntry.receipt_id))
        .subquery()
    )

    rows = session.exec(
        select(
            Receipt,
            func.coalesce(item_count_subquery.c.item_count, 0).label("item_count"),
            func.coalesce(redeemed_bonus_subquery.c.redeemed_bonus, 0).label(
                "redeemed_bonus"
            ),
        )
        .outerjoin(
            item_count_subquery, col(Receipt.id) == item_count_subquery.c.receipt_id
        )
        .outerjoin(
            redeemed_bonus_subquery,
            col(Receipt.id) == redeemed_bonus_subquery.c.receipt_id,
        )
        .order_by(col(Receipt.purchased_at).desc())
    ).all()

    result = []
    for row in rows:
        r = row[0]
        item_count = int(row[1])
        redeemed_bonus = float(row[2])
        result.append(
            ReceiptListItem(
                id=r.id,  # type: ignore
                purchased_at=r.purchased_at.isoformat(),
                store_name=r.store_name,
                store_address=r.store_address,
                total_amount=r.total_amount,
                total_bonus=r.total_bonus,
                redeemed_bonus=redeemed_bonus,
                source_filename=r.source_filename,
                item_count=item_count,
            )
        )
    return result


@router.get("/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(
    receipt_id: int,
    session: Session = Depends(get_session),
) -> ReceiptDetail:
    """Get full receipt detail with items and bonus entries."""
    receipt = session.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Load items with category info
    items = session.exec(
        select(ReceiptItem).where(ReceiptItem.receipt_id == receipt_id)
    ).all()

    item_responses = []
    for item in items:
        cat_name = None
        cat_icon = None
        if item.category_id:
            cat = session.get(ProductCategory, item.category_id)
            if cat:
                cat_name = cat.name
                cat_icon = cat.icon
        item_responses.append(
            ReceiptItemResponse(
                id=item.id,  # type: ignore
                raw_name=item.raw_name,
                display_name=item.display_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                total_price=item.total_price,
                vat_class=item.vat_class,
                is_deposit=item.is_deposit,
                is_manual_assignment=item.is_manual_assignment,
                category_id=item.category_id,
                category_name=cat_name,
                category_icon=cat_icon,
            )
        )

    # Load bonus entries
    bonuses = session.exec(
        select(BonusEntry).where(BonusEntry.receipt_id == receipt_id)
    ).all()

    bonus_responses = [
        BonusEntryResponse(
            id=b.id,  # type: ignore
            type=b.type,
            description=b.description,
            amount=b.amount,
        )
        for b in bonuses
    ]

    return ReceiptDetail(
        id=receipt.id,  # type: ignore
        purchased_at=receipt.purchased_at.isoformat(),
        store_name=receipt.store_name,
        store_address=receipt.store_address,
        total_amount=receipt.total_amount,
        total_bonus=receipt.total_bonus,
        bonus_balance=receipt.bonus_balance,
        source_filename=receipt.source_filename,
        tse_transaction=receipt.tse_transaction,
        bon_nr=receipt.bon_nr,
        store_id=receipt.store_id,
        register_nr=receipt.register_nr,
        imported_at=receipt.imported_at.isoformat(),
        items=item_responses,
        bonus_entries=bonus_responses,
    )


@router.delete("/{receipt_id}", status_code=204)
def delete_receipt(
    receipt_id: int,
    session: Session = Depends(get_session),
) -> None:
    """Delete a receipt and all its items and bonus entries."""
    receipt = session.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Delete items
    items = session.exec(
        select(ReceiptItem).where(ReceiptItem.receipt_id == receipt_id)
    ).all()
    for item in items:
        session.delete(item)

    # Delete bonus entries
    bonuses = session.exec(
        select(BonusEntry).where(BonusEntry.receipt_id == receipt_id)
    ).all()
    for bonus in bonuses:
        session.delete(bonus)

    session.delete(receipt)
    session.commit()


@router.patch("/{receipt_id}/items/{item_id}")
def update_item_category(
    receipt_id: int,
    item_id: int,
    body: dict,
    session: Session = Depends(get_session),
) -> dict:
    """Update an item's category."""
    item = session.get(ReceiptItem, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Item not found")

    if "category_id" in body:
        new_category_id = body["category_id"]
        if (
            new_category_id is not None
            and session.get(ProductCategory, new_category_id) is None
        ):
            raise HTTPException(status_code=400, detail="Invalid category_id")

        if item.category_id != new_category_id:
            item.category_id = new_category_id
            item.is_manual_assignment = True
        session.add(item)
        session.commit()
        session.refresh(item)

    cat_name = None
    cat_icon = None
    if item.category_id:
        cat = session.get(ProductCategory, item.category_id)
        if cat:
            cat_name = cat.name
            cat_icon = cat.icon

    return {
        "id": item.id,
        "category_id": item.category_id,
        "is_manual_assignment": item.is_manual_assignment,
        "category_name": cat_name,
        "category_icon": cat_icon,
    }
