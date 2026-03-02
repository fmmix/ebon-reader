from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class TaxonomyBackup(SQLModel, table=True):
    __tablename__ = "taxonomy_backup"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    bundle_json: str
    categories_count: int
    rules_count: int
