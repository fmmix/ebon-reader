from fastapi import APIRouter, Depends, Query
from sqlalchemy import case
from sqlmodel import Session, select, func, col

from app.core.database import get_session
from app.models.parser_template import ParserTemplate
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
from app.models.bonus_entry import BonusEntry
from app.models.product_category import ProductCategory
from app.services.shop_identity import resolve_store_display_name
from app.schemas.stats_schemas import (
    OverviewStats,
    StoreSpend,
    StoreBonusStat,
    CategorySpend,
    MonthlySpend,
    MonthlyBonusStat,
    MonthlyBonusByShopStat,
    CategoryMonthlySpend,
    TopItemStat,
    ItemPricePoint,
)

router = APIRouter(prefix="/api/stats", tags=["stats"])

UNCATEGORIZED_NAMES = {"uncategorized", "unkategorisiert"}


def _get_uncategorized_category(session: Session) -> ProductCategory | None:
    """Find the seeded Uncategorized category."""
    cats = session.exec(select(ProductCategory)).all()
    for cat in cats:
        if cat.name.strip().lower() in UNCATEGORIZED_NAMES:
            return cat
    return None


@router.get("/overview", response_model=OverviewStats)
def get_overview(session: Session = Depends(get_session)) -> OverviewStats:
    """Aggregate overview: totals, counts, averages (basket-value based)."""
    receipt_count_result = session.exec(
        select(func.count(col(Receipt.id)))
    ).one()
    receipt_count = int(receipt_count_result)

    # Basket value = sum of item prices (excluding deposits)
    item_agg = session.exec(
        select(
            func.coalesce(func.sum(col(ReceiptItem.total_price)), 0).label("total_spent"),
            func.coalesce(func.sum(col(ReceiptItem.quantity)), 0).label("item_count"),
        )
    ).one()
    total_spent = float(item_agg[0])
    item_count = int(item_agg[1])

    total_bonus_result = session.exec(
        select(func.coalesce(func.sum(col(Receipt.total_bonus)), 0))
    ).one()
    total_bonus = float(total_bonus_result)

    redeemed_bonus_result = session.exec(
        select(func.coalesce(func.sum(col(BonusEntry.amount)), 0)).where(
            col(BonusEntry.type) == "redeemed"
        )
    ).one()
    redeemed_bonus = float(redeemed_bonus_result)

    instant_discount_result = session.exec(
        select(func.coalesce(func.sum(col(BonusEntry.amount)), 0)).where(
            col(BonusEntry.type) == "instant_discount"
        )
    ).one()
    instant_discount = float(instant_discount_result)

    basket_discount_result = session.exec(
        select(func.coalesce(func.sum(col(BonusEntry.amount)), 0)).where(
            col(BonusEntry.type) == "basket_discount"
        )
    ).one()
    basket_discount = float(basket_discount_result)

    program_savings = total_bonus + instant_discount
    total_deductions = redeemed_bonus + instant_discount + basket_discount

    avg_basket = total_spent / receipt_count if receipt_count > 0 else 0.0

    return OverviewStats(
        total_spent=round(total_spent, 2),
        receipt_count=receipt_count,
        item_count=item_count,
        avg_basket=round(avg_basket, 2),
        total_bonus=round(total_bonus, 2),
        instant_discount=round(instant_discount, 2),
        basket_discount=round(basket_discount, 2),
        program_savings=round(program_savings, 2),
        redeemed_bonus=round(redeemed_bonus, 2),
        total_deductions=round(total_deductions, 2),
    )


@router.get("/store-breakdown", response_model=list[StoreSpend])
def get_store_breakdown(session: Session = Depends(get_session)) -> list[StoreSpend]:
    """Spending grouped by store name."""
    normalized_raw_store_name = func.nullif(func.trim(col(Receipt.store_name)), "")

    results = session.exec(
        select(  # type: ignore[arg-type]
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(Receipt.total_amount)), 0).label("total_spent"),
            func.count(col(Receipt.id)).label("receipt_count"),
        )
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .group_by(col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    if not results:
        return []

    canonical_totals: dict[str, dict[str, float | int]] = {}
    for row in results:
        canonical_name = resolve_store_display_name(
            template_slug=str(row[0]) if row[0] is not None else None,
            raw_store_name=str(row[1]) if row[1] is not None else None,
        )
        total_spent = float(row[2])
        receipt_count = int(row[3])

        if canonical_name not in canonical_totals:
            canonical_totals[canonical_name] = {
                "total_spent": 0.0,
                "receipt_count": 0,
            }

        canonical_totals[canonical_name]["total_spent"] = (
            float(canonical_totals[canonical_name]["total_spent"]) + total_spent
        )
        canonical_totals[canonical_name]["receipt_count"] = (
            int(canonical_totals[canonical_name]["receipt_count"]) + receipt_count
        )

    sorted_results = sorted(
        canonical_totals.items(),
        key=lambda item: float(item[1]["total_spent"]),
        reverse=True,
    )

    total_spent_all = sum(float(entry["total_spent"]) for _, entry in sorted_results)
    if total_spent_all <= 0:
        total_spent_all = 0.0

    response: list[StoreSpend] = []
    for store_name, aggregate in sorted_results:
        total_spent = float(aggregate["total_spent"])
        receipt_count = int(aggregate["receipt_count"])
        avg_basket = total_spent / receipt_count if receipt_count > 0 else 0.0
        share_percent = (
            (total_spent / total_spent_all * 100) if total_spent_all > 0 else 0.0
        )

        response.append(
            StoreSpend(
                store_name=store_name,
                total_spent=round(total_spent, 2),
                receipt_count=receipt_count,
                avg_basket=round(avg_basket, 2),
                share_percent=round(share_percent, 2),
            )
        )

    return response


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
            uncat = _get_uncategorized_category(session)
            name = uncat.name if uncat else "Uncategorized"
            icon = uncat.icon if uncat else "🏷️"
            color = uncat.color if uncat else "#6b7280"

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
    """Monthly spending totals (basket-value based), ordered chronologically."""
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))

    # Basket value per month = sum of all item prices (including deposits)
    item_results = session.exec(
        select(  # type: ignore[arg-type]
            func.strftime("%Y-%m", col(Receipt.purchased_at)).label("month"),
            func.coalesce(func.sum(col(ReceiptItem.total_price)), 0).label("total_spent"),
            func.count(func.distinct(col(Receipt.id))).label("receipt_count"),
        )
        .join(Receipt, col(ReceiptItem.receipt_id) == col(Receipt.id))
        .group_by(func.strftime("%Y-%m", col(Receipt.purchased_at)))
        .order_by(func.strftime("%Y-%m", col(Receipt.purchased_at)))
    ).all()

    redeemed_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("redeemed_bonus"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "redeemed")
        .group_by(month_expr)
    ).all()

    instant_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("instant_discount"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "instant_discount")
        .group_by(month_expr)
    ).all()

    basket_discount_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("basket_discount"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "basket_discount")
        .group_by(month_expr)
    ).all()

    redeemed_by_month = {str(row[0]): float(row[1]) for row in redeemed_results}
    instant_by_month = {str(row[0]): float(row[1]) for row in instant_results}
    basket_discount_by_month = {str(row[0]): float(row[1]) for row in basket_discount_results}

    return [
        MonthlySpend(
            month=str(row[0]),
            total_spent=round(float(row[1]), 2),
            redeemed_bonus=round(redeemed_by_month.get(str(row[0]), 0.0), 2),
            instant_discount=round(instant_by_month.get(str(row[0]), 0.0), 2),
            basket_discount=round(basket_discount_by_month.get(str(row[0]), 0.0), 2),
            receipt_count=int(row[2]),
        )
        for row in item_results
    ]


@router.get("/monthly-bonus", response_model=list[MonthlyBonusStat])
def get_monthly_bonus(
    session: Session = Depends(get_session),
) -> list[MonthlyBonusStat]:
    """Monthly bonus analytics: earned, instant, redeemed, and savings rate (basket-value based)."""
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))

    # Basket value per month (including deposits)
    item_results = session.exec(
        select(  # type: ignore[arg-type]
            func.strftime("%Y-%m", col(Receipt.purchased_at)).label("month"),
            func.coalesce(func.sum(col(ReceiptItem.total_price)), 0).label("total_spent"),
            func.count(func.distinct(col(Receipt.id))).label("receipt_count"),
        )
        .join(Receipt, col(ReceiptItem.receipt_id) == col(Receipt.id))
        .group_by(func.strftime("%Y-%m", col(Receipt.purchased_at)))
        .order_by(func.strftime("%Y-%m", col(Receipt.purchased_at)))
    ).all()

    earned_results = session.exec(
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(col(Receipt.total_bonus)), 0).label("earned_bonus"),
        )
        .group_by(month_expr)
    ).all()

    redeemed_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("redeemed_bonus"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "redeemed")
        .group_by(month_expr)
    ).all()

    instant_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label(
                "instant_discount"
            ),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "instant_discount")
        .group_by(month_expr)
    ).all()

    earned_by_month = {str(row[0]): float(row[1]) for row in earned_results}
    redeemed_by_month = {str(row[0]): float(row[1]) for row in redeemed_results}
    instant_by_month = {str(row[0]): float(row[1]) for row in instant_results}

    basket_discount_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("basket_discount"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .where(col(BonusEntry.type) == "basket_discount")
        .group_by(month_expr)
    ).all()
    basket_discount_by_month = {str(row[0]): float(row[1]) for row in basket_discount_results}

    response: list[MonthlyBonusStat] = []
    for row in item_results:
        month = str(row[0])
        total_spent = float(row[1])
        earned_bonus = earned_by_month.get(month, 0.0)
        instant_discount = instant_by_month.get(month, 0.0)
        basket_discount = basket_discount_by_month.get(month, 0.0)
        program_savings = earned_bonus + instant_discount
        redeemed_bonus = redeemed_by_month.get(month, 0.0)
        receipt_count = int(row[2])
        bonus_rate = (program_savings / total_spent * 100) if total_spent > 0 else 0.0

        response.append(
            MonthlyBonusStat(
                month=month,
                total_spent=round(total_spent, 2),
                earned_bonus=round(earned_bonus, 2),
                instant_discount=round(instant_discount, 2),
                basket_discount=round(basket_discount, 2),
                program_savings=round(program_savings, 2),
                redeemed_bonus=round(redeemed_bonus, 2),
                bonus_rate=round(bonus_rate, 2),
                receipt_count=receipt_count,
            )
        )

    return response


@router.get("/store-bonus-breakdown", response_model=list[StoreBonusStat])
def get_store_bonus_breakdown(
    session: Session = Depends(get_session),
) -> list[StoreBonusStat]:
    """Bonus analytics grouped by canonical store identity."""
    normalized_raw_store_name = func.nullif(func.trim(col(Receipt.store_name)), "")

    receipt_results = session.exec(
        select(  # type: ignore[arg-type]
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(Receipt.total_amount)), 0).label("total_spent"),
            func.coalesce(func.sum(col(Receipt.total_bonus)), 0).label("earned_bonus"),
            func.count(col(Receipt.id)).label("receipt_count"),
        )
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .group_by(col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    instant_results = session.exec(
        select(  # type: ignore[arg-type]
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label(
                "instant_discount"
            ),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .where(col(BonusEntry.type) == "instant_discount")
        .group_by(col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    redeemed_results = session.exec(
        select(  # type: ignore[arg-type]
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("redeemed_bonus"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .where(col(BonusEntry.type) == "redeemed")
        .group_by(col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    if not receipt_results:
        return []

    def group_key(
        template_slug: object, raw_store_name: object
    ) -> tuple[str | None, str | None]:
        return (
            str(template_slug) if template_slug is not None else None,
            str(raw_store_name) if raw_store_name is not None else None,
        )

    instant_by_group = {
        group_key(row[0], row[1]): float(row[2]) for row in instant_results
    }
    redeemed_by_group = {
        group_key(row[0], row[1]): float(row[2]) for row in redeemed_results
    }

    basket_discount_results = session.exec(
        select(  # type: ignore[arg-type]
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("basket_discount"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .where(col(BonusEntry.type) == "basket_discount")
        .group_by(col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()
    basket_discount_by_group = {
        group_key(row[0], row[1]): float(row[2]) for row in basket_discount_results
    }

    canonical_totals: dict[str, dict[str, float | int]] = {}
    for row in receipt_results:
        template_slug, raw_store_name = group_key(row[0], row[1])
        canonical_name = resolve_store_display_name(
            template_slug=template_slug,
            raw_store_name=raw_store_name,
        )
        total_spent = float(row[2])
        earned_bonus = float(row[3])
        receipt_count = int(row[4])
        instant_discount = instant_by_group.get((template_slug, raw_store_name), 0.0)
        redeemed_bonus = redeemed_by_group.get((template_slug, raw_store_name), 0.0)
        basket_discount = basket_discount_by_group.get((template_slug, raw_store_name), 0.0)

        if canonical_name not in canonical_totals:
            canonical_totals[canonical_name] = {
                "total_spent": 0.0,
                "earned_bonus": 0.0,
                "instant_discount": 0.0,
                "basket_discount": 0.0,
                "redeemed_bonus": 0.0,
                "receipt_count": 0,
            }

        canonical_totals[canonical_name]["total_spent"] = (
            float(canonical_totals[canonical_name]["total_spent"]) + total_spent
        )
        canonical_totals[canonical_name]["earned_bonus"] = (
            float(canonical_totals[canonical_name]["earned_bonus"]) + earned_bonus
        )
        canonical_totals[canonical_name]["instant_discount"] = (
            float(canonical_totals[canonical_name]["instant_discount"])
            + instant_discount
        )
        canonical_totals[canonical_name]["basket_discount"] = (
            float(canonical_totals[canonical_name]["basket_discount"])
            + basket_discount
        )
        canonical_totals[canonical_name]["redeemed_bonus"] = (
            float(canonical_totals[canonical_name]["redeemed_bonus"]) + redeemed_bonus
        )
        canonical_totals[canonical_name]["receipt_count"] = (
            int(canonical_totals[canonical_name]["receipt_count"]) + receipt_count
        )

    sorted_results = sorted(
        canonical_totals.items(),
        key=lambda item: (
            float(item[1]["earned_bonus"]) + float(item[1]["instant_discount"]),
            float(item[1]["total_spent"]),
        ),
        reverse=True,
    )

    response: list[StoreBonusStat] = []
    for store_name, aggregate in sorted_results:
        total_spent = float(aggregate["total_spent"])
        earned_bonus = float(aggregate["earned_bonus"])
        instant_discount = float(aggregate["instant_discount"])
        basket_discount = float(aggregate["basket_discount"])
        program_savings = earned_bonus + instant_discount
        redeemed_bonus = float(aggregate["redeemed_bonus"])
        receipt_count = int(aggregate["receipt_count"])
        bonus_rate = (program_savings / total_spent * 100) if total_spent > 0 else 0.0

        response.append(
            StoreBonusStat(
                store_name=store_name,
                total_spent=round(total_spent, 2),
                earned_bonus=round(earned_bonus, 2),
                instant_discount=round(instant_discount, 2),
                basket_discount=round(basket_discount, 2),
                program_savings=round(program_savings, 2),
                redeemed_bonus=round(redeemed_bonus, 2),
                bonus_rate=round(bonus_rate, 2),
                receipt_count=receipt_count,
            )
        )

    return response


@router.get("/monthly-bonus-by-shop", response_model=list[MonthlyBonusByShopStat])
def get_monthly_bonus_by_shop(
    session: Session = Depends(get_session),
) -> list[MonthlyBonusByShopStat]:
    """Monthly bonus analytics grouped by canonical store identity."""
    month_expr = func.strftime("%Y-%m", col(Receipt.purchased_at))
    normalized_raw_store_name = func.nullif(func.trim(col(Receipt.store_name)), "")

    receipt_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(Receipt.total_amount)), 0).label("total_spent"),
            func.coalesce(func.sum(col(Receipt.total_bonus)), 0).label("earned_bonus"),
            func.count(col(Receipt.id)).label("receipt_count"),
        )
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .group_by(month_expr, col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    if not receipt_results:
        return []

    instant_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label(
                "instant_discount"
            ),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .where(col(BonusEntry.type) == "instant_discount")
        .group_by(month_expr, col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    redeemed_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("redeemed_bonus"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .where(col(BonusEntry.type) == "redeemed")
        .group_by(month_expr, col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()

    def group_key(
        month: object,
        template_slug: object,
        raw_store_name: object,
    ) -> tuple[str, str | None, str | None]:
        return (
            str(month),
            str(template_slug) if template_slug is not None else None,
            str(raw_store_name) if raw_store_name is not None else None,
        )

    instant_by_group = {
        group_key(row[0], row[1], row[2]): float(row[3]) for row in instant_results
    }
    redeemed_by_group = {
        group_key(row[0], row[1], row[2]): float(row[3]) for row in redeemed_results
    }

    basket_discount_results = session.exec(
        select(  # type: ignore[arg-type]
            month_expr.label("month"),
            col(ParserTemplate.slug).label("template_slug"),
            normalized_raw_store_name.label("raw_store_name"),
            func.coalesce(func.sum(col(BonusEntry.amount)), 0).label("basket_discount"),
        )
        .join(Receipt, col(BonusEntry.receipt_id) == col(Receipt.id))
        .join(
            ParserTemplate,
            col(Receipt.template_id) == col(ParserTemplate.id),
            isouter=True,
        )
        .where(col(BonusEntry.type) == "basket_discount")
        .group_by(month_expr, col(ParserTemplate.slug), normalized_raw_store_name)
    ).all()
    basket_discount_by_group = {
        group_key(row[0], row[1], row[2]): float(row[3]) for row in basket_discount_results
    }

    monthly_store_totals: dict[tuple[str, str], dict[str, float | int]] = {}
    for row in receipt_results:
        month = str(row[0])
        template_slug = str(row[1]) if row[1] is not None else None
        raw_store_name = str(row[2]) if row[2] is not None else None
        canonical_name = resolve_store_display_name(
            template_slug=template_slug,
            raw_store_name=raw_store_name,
        )
        total_spent = float(row[3])
        earned_bonus = float(row[4])
        receipt_count = int(row[5])

        grouped_key = group_key(month, template_slug, raw_store_name)
        instant_discount = instant_by_group.get(grouped_key, 0.0)
        redeemed_bonus = redeemed_by_group.get(grouped_key, 0.0)
        basket_discount = basket_discount_by_group.get(grouped_key, 0.0)

        monthly_store_key = (month, canonical_name)
        if monthly_store_key not in monthly_store_totals:
            monthly_store_totals[monthly_store_key] = {
                "total_spent": 0.0,
                "earned_bonus": 0.0,
                "instant_discount": 0.0,
                "basket_discount": 0.0,
                "redeemed_bonus": 0.0,
                "receipt_count": 0,
            }

        monthly_store_totals[monthly_store_key]["total_spent"] = (
            float(monthly_store_totals[monthly_store_key]["total_spent"]) + total_spent
        )
        monthly_store_totals[monthly_store_key]["earned_bonus"] = (
            float(monthly_store_totals[monthly_store_key]["earned_bonus"])
            + earned_bonus
        )
        monthly_store_totals[monthly_store_key]["instant_discount"] = (
            float(monthly_store_totals[monthly_store_key]["instant_discount"])
            + instant_discount
        )
        monthly_store_totals[monthly_store_key]["basket_discount"] = (
            float(monthly_store_totals[monthly_store_key]["basket_discount"])
            + basket_discount
        )
        monthly_store_totals[monthly_store_key]["redeemed_bonus"] = (
            float(monthly_store_totals[monthly_store_key]["redeemed_bonus"])
            + redeemed_bonus
        )
        monthly_store_totals[monthly_store_key]["receipt_count"] = (
            int(monthly_store_totals[monthly_store_key]["receipt_count"])
            + receipt_count
        )

    rows: list[MonthlyBonusByShopStat] = []
    for (month, store_name), aggregate in monthly_store_totals.items():
        total_spent = float(aggregate["total_spent"])
        earned_bonus = float(aggregate["earned_bonus"])
        instant_discount = float(aggregate["instant_discount"])
        basket_discount = float(aggregate["basket_discount"])
        redeemed_bonus = float(aggregate["redeemed_bonus"])
        receipt_count = int(aggregate["receipt_count"])
        program_savings = earned_bonus + instant_discount
        bonus_rate = (program_savings / total_spent * 100) if total_spent > 0 else 0.0

        rows.append(
            MonthlyBonusByShopStat(
                month=month,
                store_name=store_name,
                total_spent=round(total_spent, 2),
                earned_bonus=round(earned_bonus, 2),
                instant_discount=round(instant_discount, 2),
                basket_discount=round(basket_discount, 2),
                program_savings=round(program_savings, 2),
                redeemed_bonus=round(redeemed_bonus, 2),
                bonus_rate=round(bonus_rate, 2),
                receipt_count=receipt_count,
            )
        )

    return sorted(
        rows, key=lambda row: (row.month, -row.program_savings, row.store_name)
    )


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
        category_name = row[2]
        if not category_name:
            uncat = _get_uncategorized_category(session)
            category_name = uncat.name if uncat else "Uncategorized"
            icon = uncat.icon if uncat else "🏷️"
        else:
            icon = row[3] if row[3] else "🏷️"
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
