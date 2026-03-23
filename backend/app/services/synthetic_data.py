from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import random

from sqlalchemy import or_
from sqlmodel import Session, delete, func, select

from app.models.bonus_entry import BonusEntry
from app.models.parser_template import ParserTemplate
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem

SYNTHETIC_SEED = 20260312
STORE_ORDER = ("rewe", "lidl", "kaufland")
STORE_DISPLAY_NAMES = {
    "rewe": "REWE Markt GmbH",
    "lidl": "Lidl",
    "kaufland": "Kaufland",
}

BASE_DATE_SLOTS = {
    "rewe": [
        datetime(2026, 2, 5, 17, 11),
        datetime(2026, 2, 18, 12, 47),
        datetime(2026, 2, 26, 19, 22),
        datetime(2026, 3, 12, 16, 3),
        datetime(2026, 3, 25, 10, 44),
    ],
    "lidl": [
        datetime(2026, 2, 3, 16, 24),
        datetime(2026, 2, 14, 18, 42),
        datetime(2026, 2, 27, 12, 8),
        datetime(2026, 3, 10, 17, 55),
        datetime(2026, 3, 22, 10, 19),
    ],
    "kaufland": [
        datetime(2026, 2, 9, 11, 34),
        datetime(2026, 2, 21, 19, 6),
        datetime(2026, 3, 3, 15, 41),
        datetime(2026, 3, 16, 13, 27),
        datetime(2026, 3, 29, 9, 58),
    ],
}

PRODUCT_CATALOG = {
    "lidl": [
        "Brot Mehrkorn",
        "H-Milch 1.5%",
        "Naturjoghurt",
        "Spaghetti",
        "Tomaten Dose",
        "Gouda Scheiben",
        "Butter mild",
        "Apfel Gala",
        "Banane",
        "Paprika Mix",
        "Mineralwasser 1.5L",
        "Cola Zero 1L",
        "Haehnchenbrust",
        "Waschmittel Color",
        "Toilettenpapier 8er",
        "Nussmix",
        "TK Pizza Salami",
        "Reis Basmati",
        "Ketchup",
        "Croissant Butter",
    ],
    "kaufland": [
        "Vollkornbrot",
        "Frischmilch 3.5%",
        "Quark Mager",
        "Penne Rigate",
        "Passierte Tomaten",
        "Emmentaler",
        "Sahnejoghurt",
        "Birne Conference",
        "Trauben kernlos",
        "Gurke",
        "Orangensaft",
        "Eistee Pfirsich",
        "Putenbrust Aufschnitt",
        "Spuelmittel Zitrone",
        "Kuechenrolle 4er",
        "Haferkekse",
        "TK Gemuesepfanne",
        "Couscous",
        "Senf mittelscharf",
        "Laugenstange",
    ],
    "rewe": [
        "H-MILCH 1,5%",
        "BANANEN BIO",
        "VOLLKORNBROT",
        "APFEL ELSTAR",
        "EIER FREILAND 10ER",
        "MINERALWASSER STILL 1,5L",
        "BUTTER DEUTSCHE MARKENBUTTER",
        "GOUDA JUNG SCHEIBEN",
        "NATURJOGHURT 3,5%",
        "PENNE RIGATE",
        "PASSIERTE TOMATEN",
        "TOILETTENPAPIER 8ER",
        "SPUELMITTEL ZITRONE",
        "HAFERFLOCKEN ZART",
        "ORANGENSAFT DIREKT",
        "HUMMUS KLASSIK",
        "HACKFLEISCH GEMISCHT",
        "TK-BEEREN MIX",
        "KAFFEE GEMAHLEN",
        "MOZZARELLA",
    ],
}

DEPOSIT_LINES = {
    "default": [
        ("Pfand Einweg", Decimal("0.25"), 1),
        ("Pfand Mehrweg", Decimal("0.15"), 2),
        ("Leergut Pfand", Decimal("0.08"), 3),
    ],
    "rewe": [
        ("PFANDARTIKEL", Decimal("0.25"), 1),
        ("PFAND MEHRWEG", Decimal("0.15"), 2),
        ("LEERGUT PFAND", Decimal("0.08"), 3),
    ],
}


@dataclass
class SyntheticGenerationResult:
    stores: dict[str, dict[str, int]]
    total_inserted: int
    total_skipped: int
    payloads: list[dict]


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _slot_datetime(store_slug: str, index: int) -> datetime:
    base_slots = BASE_DATE_SLOTS[store_slug]
    base_slot = base_slots[index % len(base_slots)]
    cycle = index // len(base_slots)
    day_shift = cycle * 35 + (index % 3)
    hour_shift = (cycle * 2) % 6
    return base_slot + timedelta(days=day_shift, hours=hour_shift)


def _build_receipt_payload(store_slug: str, template_id: int, index: int) -> dict:
    rng = random.Random(f"{SYNTHETIC_SEED}:{store_slug}:{index}")
    purchased_at = _slot_datetime(store_slug, index)

    item_count = rng.randint(10, 15)
    regular_item_count = item_count - 1
    catalog = PRODUCT_CATALOG[store_slug]

    items: list[dict] = []
    for _ in range(regular_item_count):
        name = rng.choice(catalog)
        quantity = 1 if rng.random() < 0.8 else 2
        unit_price = _money(Decimal(str(rng.uniform(0.79, 7.99))))
        total_price = _money(unit_price * Decimal(quantity))
        vat_class = "B" if rng.random() < 0.7 else "A"
        items.append(
            {
                "raw_name": name,
                "display_name": name,
                "quantity": quantity,
                "unit_price": float(unit_price),
                "total_price": float(total_price),
                "vat_class": vat_class,
                "is_deposit": False,
            }
        )

    deposit_catalog = DEPOSIT_LINES.get(store_slug, DEPOSIT_LINES["default"])
    deposit_name, deposit_unit, deposit_quantity = rng.choice(deposit_catalog)
    deposit_total = _money(deposit_unit * Decimal(deposit_quantity))
    items.append(
        {
            "raw_name": deposit_name,
            "display_name": deposit_name,
            "quantity": deposit_quantity,
            "unit_price": float(deposit_unit),
            "total_price": float(deposit_total),
            "vat_class": "B",
            "is_deposit": True,
        }
    )

    item_sum = _money(
        sum((Decimal(str(item["total_price"])) for item in items), Decimal("0.00"))
    )

    instant_discounts: list[dict] = []
    if index % 2 == 0 or rng.random() < 0.65:
        discount_amount = _money(Decimal(str(rng.uniform(0.5, 2.4))))
        instant_discounts.append(
            {
                "type": "instant_discount",
                "description": "Sofortrabatt Aktion",
                "amount": float(discount_amount),
            }
        )

    discount_sum = _money(
        sum(
            (Decimal(str(entry["amount"])) for entry in instant_discounts),
            Decimal("0.00"),
        )
    )
    total_amount = _money(item_sum - discount_sum)
    store_display_name = STORE_DISPLAY_NAMES[store_slug]
    date_key = purchased_at.strftime("%Y%m%d")

    return {
        "store_slug": store_slug,
        "store_name": store_display_name,
        "store_address": f"Synthetic {store_display_name}, Musterstr. {101 + index}, 50667 Koeln",
        "store_id": f"SYN-{store_slug.upper()}-{700 + index}",
        "register_nr": 1 + (index % 4),
        "bon_nr": f"{store_slug[:2].upper()}26{index + 1:04d}",
        "source_filename": f"synthetic_{store_slug}_{date_key}_{index + 1:03d}.json",
        "tse_transaction": f"SYN-{store_slug.upper()}-{date_key}-{index + 1:03d}",
        "purchased_at": purchased_at.isoformat(),
        "template_id": template_id,
        "total_bonus": 0.0,
        "total_amount": float(total_amount),
        "items": items,
        "bonus_entries": instant_discounts,
    }


def resolve_requested_stores(store: str) -> list[str]:
    if store == "all":
        return list(STORE_ORDER)
    if store not in STORE_ORDER:
        raise ValueError(
            "Invalid store. Allowed values are: all, rewe, lidl, kaufland."
        )
    return [store]


def _resolve_template_ids(session: Session, stores: list[str]) -> dict[str, int]:
    template_ids: dict[str, int] = {}
    missing: list[str] = []
    for store in stores:
        template = session.exec(
            select(ParserTemplate).where(ParserTemplate.slug == store)
        ).first()
        if template is None or template.id is None:
            missing.append(store)
            continue
        template_ids[store] = template.id

    if missing:
        missing_slugs = ", ".join(missing)
        raise ValueError(f"Parser template(s) missing for slug(s): {missing_slugs}")

    return template_ids


def generate_synthetic_receipts(
    session: Session,
    store: str,
    count_per_store: int,
) -> SyntheticGenerationResult:
    stores = resolve_requested_stores(store)
    template_ids = _resolve_template_ids(session, stores)
    summary = {store_slug: {"inserted": 0, "skipped": 0} for store_slug in stores}
    payloads: list[dict] = []

    for store_slug in stores:
        for index in range(count_per_store):
            payload = _build_receipt_payload(
                store_slug=store_slug,
                template_id=template_ids[store_slug],
                index=index,
            )

            existing = session.exec(
                select(Receipt).where(
                    Receipt.tse_transaction == payload["tse_transaction"]
                )
            ).first()

            if existing is not None:
                summary[store_slug]["skipped"] += 1
                payload["status"] = "skipped_existing_tse"
                payloads.append(payload)
                continue

            receipt = Receipt(
                purchased_at=datetime.fromisoformat(payload["purchased_at"]),
                store_name=payload["store_name"],
                store_address=payload["store_address"],
                store_id=payload["store_id"],
                register_nr=payload["register_nr"],
                bon_nr=payload["bon_nr"],
                tse_transaction=payload["tse_transaction"],
                total_amount=payload["total_amount"],
                currency="EUR",
                total_bonus=0.0,
                source_filename=payload["source_filename"],
                template_id=payload["template_id"],
            )
            session.add(receipt)
            session.flush()

            for item in payload["items"]:
                session.add(
                    ReceiptItem(
                        receipt_id=receipt.id,
                        raw_name=item["raw_name"],
                        display_name=item["display_name"],
                        unit_price=item["unit_price"],
                        quantity=item["quantity"],
                        total_price=item["total_price"],
                        vat_class=item["vat_class"],
                        is_deposit=item["is_deposit"],
                    )
                )

            for bonus in payload["bonus_entries"]:
                session.add(
                    BonusEntry(
                        receipt_id=receipt.id,
                        type=bonus["type"],
                        description=bonus["description"],
                        amount=bonus["amount"],
                    )
                )

            summary[store_slug]["inserted"] += 1
            payload["status"] = "inserted"
            payloads.append(payload)

    session.commit()

    total_inserted = sum(store_data["inserted"] for store_data in summary.values())
    total_skipped = sum(store_data["skipped"] for store_data in summary.values())
    return SyntheticGenerationResult(
        stores=summary,
        total_inserted=total_inserted,
        total_skipped=total_skipped,
        payloads=payloads,
    )


def delete_synthetic_receipts(session: Session) -> dict[str, int]:
    synthetic_receipt_ids = session.exec(
        select(Receipt.id).where(
            or_(
                Receipt.source_filename.like("synthetic_%"),
                Receipt.tse_transaction.like("SYN-%"),
            )
        )
    ).all()

    if not synthetic_receipt_ids:
        return {"receipt_item": 0, "bonus_entry": 0, "receipt": 0}

    deleted_item_count = session.exec(
        select(func.count())
        .select_from(ReceiptItem)
        .where(ReceiptItem.receipt_id.in_(synthetic_receipt_ids))
    ).one()

    deleted_bonus_count = session.exec(
        select(func.count())
        .select_from(BonusEntry)
        .where(BonusEntry.receipt_id.in_(synthetic_receipt_ids))
    ).one()

    deleted_receipt_count = len(synthetic_receipt_ids)

    session.exec(
        delete(ReceiptItem).where(ReceiptItem.receipt_id.in_(synthetic_receipt_ids))
    )
    session.exec(
        delete(BonusEntry).where(BonusEntry.receipt_id.in_(synthetic_receipt_ids))
    )
    session.exec(delete(Receipt).where(Receipt.id.in_(synthetic_receipt_ids)))
    session.commit()

    return {
        "receipt_item": deleted_item_count,
        "bonus_entry": deleted_bonus_count,
        "receipt": deleted_receipt_count,
    }
