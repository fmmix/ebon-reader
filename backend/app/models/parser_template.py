from sqlmodel import Field, SQLModel


class ParserTemplate(SQLModel, table=True):
    __tablename__ = "parser_template"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True, description="e.g. 'rewe', 'edeka'")
    display_name: str = Field(description="e.g. 'REWE eBon'")
    icon: str = Field(default="🧾")
    is_active: bool = Field(default=True)
