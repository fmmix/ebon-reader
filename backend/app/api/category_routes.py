from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func

from app.core.database import get_session
from app.models.categorize_rule import CategorizeRule
from app.models.product_category import ProductCategory
from app.models.receipt_item import ReceiptItem
from app.schemas.category_schemas import CategoryCreate, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])

UNCATEGORIZED_NAMES = {"uncategorized", "unkategorisiert"}


@router.get("/")
def list_categories(session: Session = Depends(get_session)) -> list[dict]:
    """List all categories with item count and total spend."""
    categories = list(session.exec(select(ProductCategory)).all())

    result = []
    for cat in categories:
        # For "Uncategorized", also count items with NULL category_id
        if cat.name.strip().lower() in UNCATEGORIZED_NAMES:
            from sqlalchemy import or_

            condition = or_(
                ReceiptItem.category_id == cat.id,
                ReceiptItem.category_id.is_(None),  # type: ignore
            )
        else:
            condition = ReceiptItem.category_id == cat.id

        item_count = session.exec(
            select(func.count(ReceiptItem.id)).where(condition)
        ).one()
        total_spend = session.exec(
            select(func.coalesce(func.sum(ReceiptItem.total_price), 0.0)).where(
                condition
            )
        ).one()

        result.append(
            {
                "id": cat.id,
                "name": cat.name,
                "icon": cat.icon,
                "color": cat.color,
                "is_default": cat.is_default,
                "item_count": item_count,
                "total_spend": round(float(total_spend), 2),
            }
        )

    return result


@router.post("/", status_code=201)
def create_category(
    body: CategoryCreate,
    session: Session = Depends(get_session),
) -> ProductCategory:
    """Create a new custom product category."""
    # Check for duplicate name
    existing = session.exec(
        select(ProductCategory).where(ProductCategory.name == body.name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Category '{body.name}' already exists"
        )

    category = ProductCategory(
        name=body.name,
        icon=body.icon,
        color=body.color,
        is_default=False,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.patch("/{category_id}")
def update_category(
    category_id: int,
    body: CategoryUpdate,
    session: Session = Depends(get_session),
) -> ProductCategory:
    """Update a category's name, icon, or color."""
    category = session.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if body.name is not None:
        # Check for duplicate name
        existing = session.exec(
            select(ProductCategory).where(
                ProductCategory.name == body.name,
                ProductCategory.id != category_id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Category '{body.name}' already exists"
            )
        category.name = body.name

    if body.icon is not None:
        category.icon = body.icon
    if body.color is not None:
        category.color = body.color

    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    session: Session = Depends(get_session),
) -> None:
    """Delete a category except the system Uncategorized anchor."""
    category = session.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.name.strip().lower() in UNCATEGORIZED_NAMES:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete system category 'Uncategorized'",
        )

    # Unassign items that use this category
    items = session.exec(
        select(ReceiptItem).where(ReceiptItem.category_id == category_id)
    ).all()
    for item in items:
        item.category_id = None
        session.add(item)

    # Delete associated rules
    rules = session.exec(
        select(CategorizeRule).where(CategorizeRule.category_id == category_id)
    ).all()
    for rule in rules:
        session.delete(rule)

    session.delete(category)
    session.commit()
