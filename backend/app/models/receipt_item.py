from sqlmodel import Field, SQLModel


class ReceiptItem(SQLModel, table=True):
    __tablename__ = "receipt_item"

    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key="receipt.id", index=True)

    # Product info
    raw_name: str = Field(description="Original name from eBon, e.g. H-MILCH GVO-FREI")
    display_name: str = Field(
        default="", description="User-friendly name (can be edited)"
    )
    unit_price: float
    quantity: int = Field(default=1)
    total_price: float
    vat_class: str = Field(default="B", description="A=19% or B=7%")
    is_deposit: bool = Field(default=False, description="PFAND item")

    # Categorization
    category_id: int | None = Field(default=None, foreign_key="product_category.id")
    auto_categorized: bool = Field(default=False)
    confidence: float = Field(default=0.0)
    is_manual_assignment: bool = Field(default=False)
