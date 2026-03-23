from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SyntheticStore(StrEnum):
    ALL = "all"
    REWE = "rewe"
    LIDL = "lidl"
    KAUFLAND = "kaufland"


class SyntheticGenerateRequest(BaseModel):
    store: SyntheticStore = SyntheticStore.ALL
    count_per_store: int = Field(default=5, ge=1, le=50)


class SyntheticStoreGenerationResult(BaseModel):
    inserted: int
    skipped: int


class SyntheticGenerateResponse(BaseModel):
    stores: dict[str, SyntheticStoreGenerationResult]
    total_inserted: int
    total_skipped: int


class SyntheticDeleteResponse(BaseModel):
    deleted: dict[str, int]
