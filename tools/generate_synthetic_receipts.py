from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_DB_PATH = (BACKEND_ROOT / "ebon_reader.db").resolve()
os.environ.setdefault("EBON_DB_PATH", str(DEFAULT_DB_PATH))

from app.core.database import engine, init_db
from app.services.seeder import seed_defaults
from app.services.synthetic_data import generate_synthetic_receipts

RECEIPTS_PER_STORE = 5


def main() -> None:
    print(f"Using database: {os.environ['EBON_DB_PATH']}")
    init_db()

    with Session(engine) as session:
        seed_defaults(session)
        result = generate_synthetic_receipts(
            session=session,
            store="all",
            count_per_store=RECEIPTS_PER_STORE,
        )

    export_path = (
        PROJECT_ROOT / "docs" / "generated" / "synthetic_receipts_feb_mar_2026.json"
    )
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(
        json.dumps(result.payloads, indent=2),
        encoding="utf-8",
    )

    print("Synthetic receipt generation finished.")
    for store_slug, store_summary in result.stores.items():
        print(
            f"- {store_slug}: inserted={store_summary['inserted']}, "
            f"skipped={store_summary['skipped']}"
        )
    print(f"- payload_export={export_path}")


if __name__ == "__main__":
    main()
