from sqlmodel import Field, SQLModel


class CategorizeRule(SQLModel, table=True):
    __tablename__ = "categorize_rule"

    id: int | None = Field(default=None, primary_key=True)
    keyword: str = Field(index=True)
    match_type: str = Field(default="contains")  # "contains" | "exact"
    category_id: int = Field(foreign_key="product_category.id")
    priority: int = Field(default=0)
