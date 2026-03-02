from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    icon: str = "🏷️"
    color: str = "#6b7280"


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    color: str | None = None
