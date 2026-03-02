from sqlmodel import Field, SQLModel


class ProductCategory(SQLModel, table=True):
    __tablename__ = "product_category"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    icon: str = Field(default="🏷️")
    color: str = Field(default="#6b7280")
    is_default: bool = Field(default=False)
