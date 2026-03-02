from fastapi import APIRouter, Depends, Query
from sqlalchemy import case
from sqlmodel import Session, select, func, col

from app.core.database import get_session
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
from app.models.bonus_entry import BonusEntry
from app.models.product_category import ProductCategory
from app.schemas.stats_schemas import (
    OverviewStats,
    CategorySpend,
    MonthlySpend,
    MonthlyBonusStat,
    CategoryMonthlySpend,
    TopItemStat,
    ItemPricePoint,
)

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewStats)
def get_overview(session: Session = Depends(get_session)) -> OverviewStats:
    """Aggregate overview: totals, counts, averages."""
    receipt_agg = session.exec(
        select(
            func.coalesce(func.sum(col(Receipt.total_amount)), 0).label("total_spent"),
            func.count(col(Receipt.id)).label("receipt_count"),
            func.coalesce(func.sum(col(Receipt.total_bonus)), 0).label("total_bonus"),
        )
    ).one()

    total_spent = float(receipt_agg[0])
    receipt_count = int(receipt_agg[1])
    total_bonus = float(receipt_agg[2])

    redeemed_bonus_result = session.exec(
        select(func.coalesce(func.sum(col(BonusEntry.amount)), 0)).where(
            col(BonusEntry.type) == "redeemed"
        )
    ).one()
    redeemed_bonus = float(redeemed_bonus_result)

    item_count_result = session.exec(
        select(func.coalesce(func.sum(col(ReceiptItem.quantity)), 0))
    ).one()
    item_count = int(item_count_result)

    avg_basket = total_spent / receipt_count if receipt_count > 0 else 0.0

    return OverviewStats(
        total_spent=round(total_spent, 2),
        receipt_count=receipt_count,
        item_count=item_count,
        avg_basket=round(avg_basket, 2),
        total_bonus=round(total_bonus, 2),
        redeemed_bonus=round(redeemed_bonus, 2),
    )


@router.get("/category-breakdown", response_model=list[CategorySpend])
def get_category_breakdown(
    include_deposit: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> list[CategorySpend]:
    """Spending grouped by product category."""
    query = select(
        col(ReceiptItem.category_id),
        func.sum(col(ReceiptItem.total_price)).label("total_spent"),
        func.coalesce(func.sum(col(ReceiptItem.quantity)), 0).label("item_count"),
    )

    if not include_deposit:
        query = query.where(col(ReceiptItem.is_deposit) == False)  # noqa: E712

    results = session.exec(
        query.group_by(col(ReceiptItem.category_id)).order_by(
            func.sum(col(ReceiptItem.total_price)).desc()
        )
    ).all()

    breakdown: list[CategorySpend] = []
    for row in results:
        cat_id = row[0]
        total = float(row[1])
        count = int(row[2])

        if cat_id is not None:
            cat = session.get(ProductCategory, cat_id)
            name = cat.name if cat else "Unknown"
            icon = cat.icon if cat else "🏷️"
            color = cat.color if cat else "#6b7280"
        else:
            name = "Uncategorized"
            icon = "❓"
            color = "#6b7280"

        breakdown.append(
            CategorySpend(
                category_id=cat_id,
                category_name=name,
                icon=icon,
                color=color,
                total_spent=round(total, 2),
                item_count=count,
            )
        )

    return breakdown


@router.get("/monthly-trend", response_model=list[MonthlySpend])
def get_monthly_trend(
    session: Session = Depends(get_session),
) -> list[MonthlySpend]:
    """Monthly spending totals, ordered chronologically."""
    # SQLite: use strftime to extract YYYY-MM from purchased_at
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))

    results = session.exec(
        select(
            month_expr.label("month"),
            func.sum(col(Receipt.total_amount)).label("total_spent"),
            func.count(col(Receipt.id)).label("receipt_count"),
        )
        .group_by(month_expr)
        .order_by(month_expr)
    ).all()

    return [
        MonthlySpend(
            month=str(row[0]),
            total_spent=round(float(row[1]), 2),
            receipt_count=int(row[2]),
        )
        for row in results
    ]


@router.get("/monthly-bonus", response_model=list[MonthlyBonusStat])
def get_monthly_bonus(
    session: Session = Depends(get_session),
) -> list[MonthlyBonusStat]:
    """Monthly bonus analytics: earned, redeemed, and bonus rate."""
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))

    receipt_results = session.exec(
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(col(Receipt.total_amount)), 0).label("total_spent"),
            func.coalesce(func.sum(col(Receipt.total_bonus)), 0).label("earned_bonus"),
            func.count(col(Receipt.id)).label("receipt_count"),
        )
        .group_by(month_expr)
        .order_by(month_expr)
    ).all()

    redeemed_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("redeemed_bonus"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "redeemed")
        .group_by(month_expr)
        .order_by(month_expr)
    ).all()

    redeemed_by_month = {str(row[0]): float(row[1]) for row in redeemed_results}

    response: list[MonthlyBonusStat] = []
    for row in receipt_results:
        month = str(row[0])
        total_spent = float(row[1])
        earned_bonus = float(row[2])
        redeemed_bonus = redeemed_by_month.get(month, 0.0)
        receipt_count = int(row[3])
        bonus_rate = (earned_bonus / total_spent * 100) if total_spent > 0 else 0.0

        response.append(
            MonthlyBonusStat(
                month=month,
                total_spent=round(total_spent, 2),
                earned_bonus=round(earned_bonus, 2),
                redeemed_bonus=round(redeemed_bonus, 2),
                bonus_rate=round(bonus_rate, 2),
                receipt_count=receipt_count,
            )
        )

    return response


@router.get("/category-monthly", response_model=list[CategoryMonthlySpend])
def get_category_monthly(
    session: Session = Depends(get_session),
) -> list[CategoryMonthlySpend]:
    """Monthly spend grouped by product category."""
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))

    results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            col(ReceiptItem.category_id),
            col(ProductCategory.name),
            col(ProductCategory.icon),
            col(ProductCategory.color),
            func.sum(col(ReceiptItem.total_price)).label("total_spent"),
        )
        .join(Receipt, col(ReceiptItem.receipt_id) == col(Receipt.id))
        .join(
            ProductCategory,
            col(ReceiptItem.category_id) == col(ProductCategory.id),
            isouter=True,
        )
        .where(col(ReceiptItem.is_deposit) == False)  # noqa: E712
        .group_by(
            month_expr,
            col(ReceiptItem.category_id),
            col(ProductCategory.name),
            col(ProductCategory.icon),
            col(ProductCategory.color),
        )
        .order_by(month_expr, col(ProductCategory.name))
    ).all()

    response: list[CategoryMonthlySpend] = []
    for row in results:
        cat_id = row[1]
        category_name = row[2] if row[2] else "Uncategorized"
        icon = row[3] if row[3] else "❓"
        color = row[4] if row[4] else "#6b7280"

        response.append(
            CategoryMonthlySpend(
                month=str(row[0]),
                category_id=cat_id,
                category_name=category_name,
                icon=icon,
                color=color,
                total_spent=round(float(row[5]), 2),
            )
        )

    return response


@router.get("/top-items", response_model=list[TopItemStat])
def get_top_items(
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[TopItemStat]:
    """Top spend items grouped by effective item name."""
    effective_name = func.coalesce(
        func.nullif(col(ReceiptItem.display_name), ""), col(ReceiptItem.raw_name)
    )
    normalized_effective_name = func.lower(func.coalesce(effective_name, ""))
    effective_unit_price = case(
        (
            col(ReceiptItem.quantity) > 0,
            col(ReceiptItem.total_price) / col(ReceiptItem.quantity),
        ),
        else_=col(ReceiptItem.unit_price),
    )
    purchase_count_expr = func.count(col(ReceiptItem.id))
    total_quantity_expr = func.coalesce(func.sum(col(ReceiptItem.quantity)), 0)
    total_spent_expr = func.coalesce(func.sum(col(ReceiptItem.total_price)), 0)

    results = session.exec(
        select(  # type: ignore[arg-type]
            effective_name.label("item_name"),
            purchase_count_expr.label("purchase_count"),
            total_quantity_expr.label("total_quantity"),
            total_spent_expr.label("total_spent"),
            func.coalesce(func.avg(effective_unit_price), 0).label("avg_unit_price"),
        )
        .where(col(ReceiptItem.is_deposit) == False)  # noqa: E712
        .where(~normalized_effective_name.like("%treuerabatt%"))
        .group_by(effective_name)
        .order_by(
            total_quantity_expr.desc(),
            purchase_count_expr.desc(),
            total_spent_expr.desc(),
        )
        .limit(limit)
    ).all()

    return [
        TopItemStat(
            item_name=str(row[0]),
            purchase_count=int(row[1]),
            total_quantity=int(row[2]),
            total_spent=round(float(row[3]), 2),
            avg_unit_price=round(float(row[4]), 2),
        )
        for row in results
    ]


@router.get("/item-price-trend", response_model=list[ItemPricePoint])
def get_item_price_trend(
    item_name: str = Query(min_length=1),
    session: Session = Depends(get_session),
) -> list[ItemPricePoint]:
    """Monthly price trend for a specific effective item name."""
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))
    effective_name = func.coalesce(
        func.nullif(col(ReceiptItem.display_name), ""), col(ReceiptItem.raw_name)
    )
    normalized_effective_name = func.lower(func.coalesce(effective_name, ""))
    effective_unit_price = case(
        (
            col(ReceiptItem.quantity) > 0,
            col(ReceiptItem.total_price) / col(ReceiptItem.quantity),
        ),
        else_=col(ReceiptItem.unit_price),
    )

    results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.avg(effective_unit_price).label("avg_unit_price"),
            func.min(effective_unit_price).label("min_unit_price"),
            func.max(effective_unit_price).label("max_unit_price"),
            func.coalesce(func.sum(col(ReceiptItem.quantity)), 0).label(
                "purchase_count"
            ),
        )
        .join(Receipt, col(ReceiptItem.receipt_id) == col(Receipt.id))
        .where(col(ReceiptItem.is_deposit) == False)  # noqa: E712
        .where(~normalized_effective_name.like("%treuerabatt%"))
        .where(effective_name == item_name)
        .group_by(month_expr)
        .order_by(month_expr)
    ).all()

    return [
        ItemPricePoint(
            month=str(row[0]),
            avg_unit_price=round(float(row[1]), 2),
            min_unit_price=round(float(row[2]), 2),
            max_unit_price=round(float(row[3]), 2),
            purchase_count=int(row[4]),
        )
        for row in results
    ]
