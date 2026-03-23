from sqlmodel import Field, SQLModel


class BonusEntry(SQLModel, table=True):
    __tablename__ = "bonus_entry"

    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key="receipt.id", index=True)
    type: str = Field(
        description=(
            "'action', 'coupon', 'redeemed', 'instant_discount', or 'basket_discount'"
        )
    )
    description: str = Field(default="", description="e.g. '5% auf einen Einkauf'")
    amount: float
