"""Kaufland eBon PDF parser."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.services.parser.base import ParsedBonus, ParsedItem, ParsedReceipt

RE_PRICE_HEADER = re.compile(r"^Preis\s+EUR$", re.IGNORECASE)
RE_SUMME_LINE = re.compile(r"^Summe\s+(\d+,\d{2})$", re.IGNORECASE | re.MULTILINE)
RE_ITEM_SINGLE = re.compile(r"^(.+?)\s+(-?\d+,\d{2})\s+([AB])$")
RE_ITEM_WITH_QTY = re.compile(
    r"^(.+?)\s+(\d+)\s*\*\s*(\d+,\d{2})\s+(-?\d+,\d{2})\s+([AB])$"
)
RE_QTY_LINE = re.compile(r"^(\d+)\s*\*\s*(\d+,\d{2})\s+(-?\d+,\d{2})\s+([AB])$")
RE_XTRA_DISCOUNT = re.compile(
    r"^(K\s*Card\s*XTRA\s*Rabatt|Kaufland\s*Card\s*XTRA\s*Rabatt)\s+(-?\d+,\d{2})$",
    re.IGNORECASE,
)
RE_MENGENRABATT = re.compile(r"^(Mengenrabatt)\s+(-?\d+,\d{2})$", re.IGNORECASE)

RE_DATE = re.compile(r"Datum\s*:?\s*(\d{2}\.\d{2}\.(?:\d{2}|\d{4}))", re.IGNORECASE)
RE_TIME = re.compile(r"(\d{1,2}:\d{2})(?::(\d{2}))?\s*Uhr", re.IGNORECASE)
RE_FILIALE = re.compile(r"Filiale\s*:\s*(\d+)", re.IGNORECASE)
RE_KASSE = re.compile(r"Kasse\s*:\s*(\d+)", re.IGNORECASE)
RE_BON = re.compile(r"\bBon\b\s*:?\s*(\d+)", re.IGNORECASE)
RE_STORE_ADDRESS_STOP = re.compile(
    r"^(K-U-N-D-E-N-B-E-L-E-G|Filiale\b|Kasse\b|Bon\b)", re.IGNORECASE
)
RE_STORE_ADDRESS_PHONE = re.compile(r"\bTel\.", re.IGNORECASE)
RE_STORE_ADDRESS_VAT = re.compile(r"\bDE\d{6,}\b", re.IGNORECASE)

DEPOSIT_UNIT_BASES = (0.25, 0.15, 0.08)


def _parse_german_decimal(value: str) -> float:
    return round(float(value.replace(",", ".")), 2)


def _extract_text(pdf_path: str | Path) -> str:
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def _infer_pack_quantity_from_deposit(
    deposit_total: float, item_total: float
) -> int | None:
    candidates: set[int] = set()
    deposit_cents = int(round(deposit_total * 100))

    for base in DEPOSIT_UNIT_BASES:
        base_cents = int(round(base * 100))
        if base_cents <= 0:
            continue
        qty, remainder = divmod(deposit_cents, base_cents)
        if remainder == 0 and qty >= 2:
            candidates.add(qty)

    if not candidates:
        return None

    def _reconstruction_error(qty: int) -> tuple[float, int]:
        unit_price = round(item_total / qty, 2)
        reconstructed = round(unit_price * qty, 2)
        return abs(item_total - reconstructed), qty

    return min(candidates, key=_reconstruction_error)


def _parse_items_and_discounts(
    lines: list[str],
) -> tuple[list[ParsedItem], list[ParsedBonus]]:
    items: list[ParsedItem] = []
    discounts: list[ParsedBonus] = []
    in_items = False
    pending_name: str | None = None

    for line in lines:
        stripped = line.strip()

        if not in_items:
            if RE_PRICE_HEADER.match(stripped):
                in_items = True
            continue

        total_match = RE_SUMME_LINE.match(stripped)
        if total_match:
            break

        if not stripped:
            continue

        discount_match = RE_XTRA_DISCOUNT.match(stripped)
        if discount_match:
            amount = abs(_parse_german_decimal(discount_match.group(2)))
            if amount > 0:
                discounts.append(
                    ParsedBonus(
                        type="instant_discount",
                        description=discount_match.group(1).strip(),
                        amount=amount,
                    )
                )
            pending_name = None
            continue

        basket_discount_match = RE_MENGENRABATT.match(stripped)
        if basket_discount_match:
            amount = abs(_parse_german_decimal(basket_discount_match.group(2)))
            if amount > 0:
                discounts.append(
                    ParsedBonus(
                        type="basket_discount",
                        description=basket_discount_match.group(1).strip(),
                        amount=amount,
                    )
                )
            pending_name = None
            continue

        item_qty_match = RE_ITEM_WITH_QTY.match(stripped)
        if item_qty_match:
            item = ParsedItem(
                raw_name=item_qty_match.group(1).strip(),
                quantity=int(item_qty_match.group(2)),
                unit_price=_parse_german_decimal(item_qty_match.group(3)),
                total_price=_parse_german_decimal(item_qty_match.group(4)),
                vat_class=item_qty_match.group(5),
                is_deposit="pfand" in item_qty_match.group(1).lower(),
            )
            items.append(item)
            pending_name = None
        else:
            qty_line_match = RE_QTY_LINE.match(stripped)
            if qty_line_match and pending_name:
                item = ParsedItem(
                    raw_name=pending_name,
                    quantity=int(qty_line_match.group(1)),
                    unit_price=_parse_german_decimal(qty_line_match.group(2)),
                    total_price=_parse_german_decimal(qty_line_match.group(3)),
                    vat_class=qty_line_match.group(4),
                    is_deposit="pfand" in pending_name.lower(),
                )
                items.append(item)
                pending_name = None
            else:
                item_match = RE_ITEM_SINGLE.match(stripped)
                if item_match:
                    raw_name = item_match.group(1).strip()
                    item = ParsedItem(
                        raw_name=raw_name,
                        quantity=1,
                        unit_price=_parse_german_decimal(item_match.group(2)),
                        total_price=_parse_german_decimal(item_match.group(2)),
                        vat_class=item_match.group(3),
                        is_deposit="pfand" in raw_name.lower(),
                    )
                    items.append(item)
                    pending_name = None
                else:
                    pending_name = stripped

        if items and items[-1].is_deposit and len(items) >= 2:
            previous_item = items[-2]
            is_default_single_qty = (
                previous_item.quantity == 1
                and previous_item.unit_price == previous_item.total_price
            )
            if not previous_item.is_deposit and is_default_single_qty:
                inferred_qty = _infer_pack_quantity_from_deposit(
                    deposit_total=items[-1].total_price,
                    item_total=previous_item.total_price,
                )
                if inferred_qty is not None:
                    previous_item.quantity = inferred_qty
                    previous_item.unit_price = round(
                        previous_item.total_price / inferred_qty,
                        2,
                    )
                    items[-1].quantity = inferred_qty
                    items[-1].unit_price = round(
                        items[-1].total_price / inferred_qty, 2
                    )

    return items, discounts


def _parse_store_address(lines: list[str]) -> str:
    address_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if RE_PRICE_HEADER.match(stripped):
            break

        if (
            RE_STORE_ADDRESS_STOP.match(stripped)
            or RE_STORE_ADDRESS_PHONE.search(stripped)
            or RE_STORE_ADDRESS_VAT.search(stripped)
        ):
            break

        if "kaufland" in stripped.lower():
            continue

        address_lines.append(stripped)

    return ", ".join(address_lines)


def _parse_metadata(text: str) -> dict:
    metadata: dict = {}

    total_match = RE_SUMME_LINE.search(text)
    if total_match:
        metadata["total_amount"] = _parse_german_decimal(total_match.group(1))

    date_match = RE_DATE.search(text)
    time_match = RE_TIME.search(text)
    if date_match:
        date_str = date_match.group(1)
        time_component = "00:00:00"
        if time_match:
            minute_time = time_match.group(1)
            seconds = time_match.group(2) or "00"
            time_component = f"{minute_time}:{seconds}"

        date_format = (
            "%d.%m.%Y" if len(date_str.rsplit(".", maxsplit=1)[-1]) == 4 else "%d.%m.%y"
        )
        metadata["purchased_at"] = datetime.strptime(
            f"{date_str} {time_component}",
            f"{date_format} %H:%M:%S",
        )

    filiale_match = RE_FILIALE.search(text)
    if filiale_match:
        metadata["store_id"] = filiale_match.group(1)

    kasse_match = RE_KASSE.search(text)
    if kasse_match:
        metadata["register_nr"] = int(kasse_match.group(1))

    bon_match = RE_BON.search(text)
    if bon_match:
        metadata["bon_nr"] = bon_match.group(1)

    return metadata


def parse_kaufland_ebon(pdf_path: str | Path) -> ParsedReceipt:
    text = _extract_text(pdf_path)
    lines = text.split("\n")

    items, bonus_entries = _parse_items_and_discounts(lines)
    metadata = _parse_metadata(text)
    store_address = _parse_store_address(lines)

    return ParsedReceipt(
        store_name="Kaufland",
        store_address=store_address,
        purchased_at=metadata.get("purchased_at"),
        store_id=metadata.get("store_id"),
        register_nr=metadata.get("register_nr"),
        bon_nr=metadata.get("bon_nr"),
        total_amount=metadata.get("total_amount", 0.0),
        items=items,
        bonus_entries=bonus_entries,
        total_bonus=0.0,
        bonus_balance=None,
        source_filename=Path(pdf_path).name,
    )
