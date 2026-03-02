from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_spent: float
    receipt_count: int
    item_count: int
    avg_basket: float
    total_bonus: float
    redeemed_bonus: float


class CategorySpend(BaseModel):
    category_id: int | None
    category_name: str
    icon: str
    color: str
    total_spent: float
    item_count: int


class MonthlySpend(BaseModel):
    month: str  # YYYY-MM
    total_spent: float
    receipt_count: int


class CategoryMonthlySpend(BaseModel):
    month: str  # YYYY-MM
    category_id: int | None
    category_name: str
    icon: str
    color: str
    total_spent: float


class TopItemStat(BaseModel):
    item_name: str
    purchase_count: int
    total_quantity: int
    total_spent: float
    avg_unit_price: float


class ItemPricePoint(BaseModel):
    month: str  # YYYY-MM
    avg_unit_price: float
    min_unit_price: float
    max_unit_price: float
    purchase_count: int


class MonthlyBonusStat(BaseModel):
    month: str  # YYYY-MM
    total_spent: float
    earned_bonus: float
    redeemed_bonus: float
    bonus_rate: float
    receipt_count: int
