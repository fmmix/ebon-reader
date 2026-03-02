from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, init_db
from app.api import (
    import_routes,
    receipt_routes,
    category_routes,
    rule_routes,
    stats_routes,
    settings_routes,
)
from app.services.seeder import seed_defaults

# Import all models so SQLModel registers them
from app.models.product_category import ProductCategory  # noqa: F401
from app.models.categorize_rule import CategorizeRule  # noqa: F401
from app.models.receipt import Receipt  # noqa: F401
from app.models.receipt_item import ReceiptItem  # noqa: F401
from app.models.bonus_entry import BonusEntry  # noqa: F401
from app.models.learned_mapping import LearnedMapping  # noqa: F401
from app.models.taxonomy_backup import TaxonomyBackup  # noqa: F401

from sqlmodel import Session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    init_db()
    with Session(engine) as session:
        seed_defaults(session)
    yield
    # Shutdown (nothing to do)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(import_routes.router)
app.include_router(receipt_routes.router)
app.include_router(category_routes.router)
app.include_router(rule_routes.router)
app.include_router(stats_routes.router)
app.include_router(settings_routes.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
