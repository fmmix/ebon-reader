from sqlmodel import Field, SQLModel


class LearnedMapping(SQLModel, table=True):
    __tablename__ = "learned_mapping"

    id: int | None = Field(default=None, primary_key=True)
    item_name: str = Field(index=True, unique=True, description="Exact product name from eBon")
    category_id: int = Field(foreign_key="product_category.id")
    times_seen: int = Field(default=1)
