"""LIDL receipt parser.

Converts structured JSON data (exported by the browser scraper script)
into ParsedReceipt objects compatible with the existing import pipeline.
"""

from __future__ import annotations

from datetime import datetime
import re

from app.services.parser.base import ParsedBonus, ParsedItem, ParsedReceipt


AMOUNT_PATTERN = r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}"
ITEM_QTY_RE = re.compile(
    rf"^(?P<name>.+?)\s+(?P<unit>{AMOUNT_PATTERN})\s*x\s*(?P<qty>\d+)\s+(?P<total>{AMOUNT_PATTERN})\s+(?P<vat>[AB])$"
)
ITEM_SIMPLE_RE = re.compile(
    rf"^(?P<name>.+?)\s+(?P<total>{AMOUNT_PATTERN})\s+(?P<vat>[AB])$"
)
LIDL_PLUS_DISCOUNT_RE = re.compile(
    rf"Lidl\s+Plus\s+Rabatt.*?(?P<amount>{AMOUNT_PATTERN})",
    re.IGNORECASE,
)
DATETIME_YYYY_RE = re.compile(r"(?P<date>\d{2}\.\d{2}\.\d{4})\s+(?P<time>\d{2}:\d{2})")
DATETIME_YY_RE = re.compile(r"(?P<date>\d{2}\.\d{2}\.\d{2})\s+(?P<time>\d{2}:\d{2})")


def is_lidl_plain_text(text: str) -> bool:
    """Detect Lidl plain-text receipts exported/copied into .txt files."""
    normalized = text.lower()
    has_core_markers = "lidl" in normalized and "zu zahlen" in normalized
    has_footer_marker = (
        "tse transaktionsnummer" in normalized or "k-u-n-d-e-n-b-e-l-e-g" in normalized
    )
    return has_core_markers and has_footer_marker


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r\n", "\n").split("\n")]


def _extract_store_address(lines: list[str]) -> str:
    eur_index = next((i for i, line in enumerate(lines) if line.upper() == "EUR"), -1)
    header_lines = lines[:eur_index] if eur_index > 0 else lines[:8]

    cleaned = []
    for line in header_lines:
        if not line:
            continue
        lower = line.lower()
        if "logo" in lower:
            continue
        if lower == "lidl plus":
            continue
        cleaned.append(line)

    return ", ".join(cleaned)


def _extract_tse_transaction(text: str) -> str | None:
    match = re.search(
        r"TSE\s+Transaktionsnummer\s*:?\s*(?P<value>[^\n\r]+)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group("value").strip() if match else None


def _extract_beleg_nr(text: str) -> str | None:
    match = re.search(
        r"Beleg-Nr\.?\s*:?\s*(?P<value>[A-Za-z0-9\-/]+)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group("value").strip() if match else None


def _extract_total_amount(lines: list[str]) -> float:
    for line in lines:
        if "zu zahlen" not in line.lower():
            continue
        amounts = re.findall(AMOUNT_PATTERN, line)
        if amounts:
            return abs(_parse_german_decimal(amounts[-1]))
    return 0.0


def _extract_purchased_at(lines: list[str]) -> datetime | None:
    for line in reversed(lines):
        match_yyyy = DATETIME_YYYY_RE.search(line)
        if match_yyyy:
            return datetime.strptime(
                f"{match_yyyy.group('date')} {match_yyyy.group('time')}",
                "%d.%m.%Y %H:%M",
            )

        match_yy = DATETIME_YY_RE.search(line)
        if match_yy:
            return datetime.strptime(
                f"{match_yy.group('date')} {match_yy.group('time')}",
                "%d.%m.%y %H:%M",
            )
    return None


def _extract_bonus_entries(lines: list[str]) -> list[ParsedBonus]:
    bonus_entries: list[ParsedBonus] = []
    for line in lines:
        match = LIDL_PLUS_DISCOUNT_RE.search(line)
        if not match:
            continue

        amount = abs(_parse_german_decimal(match.group("amount")))
        if amount <= 0:
            continue

        description = line.split(match.group("amount"))[0].strip() or "Lidl Plus Rabatt"
        bonus_entries.append(
            ParsedBonus(
                type="instant_discount",
                description=description,
                amount=amount,
            )
        )
    return bonus_entries


def _extract_item_section(lines: list[str]) -> list[str]:
    eur_index = next((i for i, line in enumerate(lines) if line.upper() == "EUR"), -1)
    if eur_index < 0:
        return []

    end_index = next(
        (
            i
            for i, line in enumerate(lines[eur_index + 1 :], start=eur_index + 1)
            if "zu zahlen" in line.lower()
        ),
        len(lines),
    )
    return lines[eur_index + 1 : end_index]


def _parse_lidl_plain_text_items(item_lines: list[str]) -> list[ParsedItem]:
    parsed_items: list[ParsedItem] = []

    for raw_line in item_lines:
        line = raw_line.strip()
        if not line:
            continue
        if "lidl plus rabatt" in line.lower():
            continue

        qty_match = ITEM_QTY_RE.match(line)
        if qty_match:
            name = qty_match.group("name").strip()
            unit_price = _parse_german_decimal(qty_match.group("unit"))
            quantity = int(qty_match.group("qty"))
            total_price = _parse_german_decimal(qty_match.group("total"))
            vat_class = qty_match.group("vat")

            parsed_items.append(
                ParsedItem(
                    raw_name=name,
                    unit_price=unit_price,
                    quantity=quantity,
                    total_price=total_price,
                    vat_class=vat_class,
                    is_deposit="pfand" in name.lower(),
                )
            )
            continue

        simple_match = ITEM_SIMPLE_RE.match(line)
        if simple_match:
            name = simple_match.group("name").strip()
            total_price = _parse_german_decimal(simple_match.group("total"))
            vat_class = simple_match.group("vat")

            parsed_items.append(
                ParsedItem(
                    raw_name=name,
                    unit_price=total_price,
                    quantity=1,
                    total_price=total_price,
                    vat_class=vat_class,
                    is_deposit="pfand" in name.lower(),
                )
            )

    return parsed_items


def parse_lidl_plain_text(
    text: str, source_filename: str = "lidl.txt"
) -> ParsedReceipt:
    """Parse Lidl receipt plain-text content from a .txt upload."""
    lines = _split_lines(text)
    item_lines = _extract_item_section(lines)

    return ParsedReceipt(
        store_name="Lidl",
        store_address=_extract_store_address(lines),
        purchased_at=_extract_purchased_at(lines),
        store_id=None,
        register_nr=None,
        bon_nr=None,
        beleg_nr=_extract_beleg_nr(text),
        tse_transaction=_extract_tse_transaction(text),
        total_amount=_extract_total_amount(lines),
        items=_parse_lidl_plain_text_items(item_lines),
        bonus_entries=_extract_bonus_entries(lines),
        total_bonus=0.0,
        bonus_balance=None,
        source_filename=source_filename,
    )


def parse_lidl_text_payload(text: str, source_filename: str) -> list[ParsedReceipt]:
    """Registry-compatible wrapper for Lidl plain-text payload parsing."""
    return [parse_lidl_plain_text(text, source_filename=source_filename)]


def is_lidl_json_payload(payload: dict) -> bool:
    """Detect whether payload matches Lidl scraper export structure."""
    receipts = payload.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return False

    first = receipts[0]
    if not isinstance(first, dict):
        return False

    required_keys = {"items", "discounts", "total_amount"}
    if not required_keys.issubset(first.keys()):
        return False

    if not isinstance(first.get("items"), list):
        return False
    if not isinstance(first.get("discounts"), list):
        return False

    return True


def _parse_german_decimal(value: str | None) -> float:
    """Convert German decimal format '1,49' to float 1.49."""
    if not value:
        return 0.0
    stripped = value.strip()
    if "," in stripped:
        normalized = stripped.replace(".", "").replace(",", ".")
    else:
        normalized = stripped
    return round(float(normalized), 2)


def _parse_lidl_items(items_data: list[dict]) -> list[ParsedItem]:
    """Parse item entries from the scraper JSON."""
    parsed: list[ParsedItem] = []

    for item in items_data:
        raw_name = item.get("description", "").strip()
        if not raw_name:
            continue

        unit_price_raw = item.get("unit_price", "0")
        total_price_raw = item.get("total_price", "0")
        quantity_raw = item.get("quantity")
        tax_type = item.get("tax_type", "B")
        is_deposit = "pfand" in raw_name.lower()

        unit_price = _parse_german_decimal(str(unit_price_raw))
        total_price = _parse_german_decimal(str(total_price_raw))

        # Determine quantity
        quantity = 1
        if quantity_raw is not None:
            qty_str = str(quantity_raw).replace(",", ".")
            qty_float = float(qty_str)
            if qty_float == int(qty_float) and qty_float >= 1:
                # Integer quantity (e.g. 6x bottles)
                quantity = int(qty_float)
            else:
                # Weight-based (e.g. 0.728 kg) — store as qty=1, total_price as-is
                quantity = 1
                unit_price = total_price

        item_obj = ParsedItem(
            raw_name=raw_name,
            unit_price=unit_price,
            quantity=quantity,
            total_price=total_price,
            vat_class=tax_type,
            is_deposit=is_deposit,
        )
        parsed.append(item_obj)

    return parsed


def _parse_lidl_discounts(discounts_data: list[dict]) -> list[ParsedBonus]:
    """Parse discount/Lidl Plus entries."""
    entries: list[ParsedBonus] = []
    for discount in discounts_data:
        desc = discount.get("description", "Lidl Plus Rabatt")
        amount_raw = discount.get("amount", "0")
        amount = abs(_parse_german_decimal(str(amount_raw)))
        if amount > 0:
            entries.append(
                ParsedBonus(
                    type="instant_discount",
                    description=desc,
                    amount=amount,
                )
            )
    return entries


def _parse_lidl_datetime(receipt_data: dict) -> datetime | None:
    """Extract purchase datetime from receipt data."""
    # Try ISO timestamp first
    ts = receipt_data.get("timestamp")
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None)
        except (ValueError, AttributeError):
            pass

    # Try date + time fields
    date_str = receipt_data.get("date")
    time_str = receipt_data.get("time")
    if date_str:
        try:
            if time_str:
                return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            return datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            pass

    # Try the raw date format "05.03.26 15:10" (YY format) or ISO format
    raw_datetime = receipt_data.get("raw_datetime")
    if raw_datetime:
        # ISO format (e.g. "2026-03-05T14:10:31.000Z")
        if "T" in raw_datetime:
            try:
                dt = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
                return dt.replace(tzinfo=None)
            except (ValueError, AttributeError):
                pass
        # German short format (e.g. "05.03.26 15:10")
        try:
            return datetime.strptime(raw_datetime, "%d.%m.%y %H:%M")
        except ValueError:
            pass

    return None


def parse_lidl_receipt(data: dict) -> ParsedReceipt:
    """Parse a single LIDL receipt from the scraper JSON format.

    Args:
        data: Dictionary with keys like 'items', 'discounts', 'store_address',
              'total_amount', 'transaction_id', 'timestamp', etc.

    Returns:
        ParsedReceipt with items, metadata, and discount information.
    """
    # Items
    items = _parse_lidl_items(data.get("items", []))

    # Discounts as bonus entries
    bonus_entries = _parse_lidl_discounts(data.get("discounts", []))
    total_bonus = 0.0

    # Store info
    store_address = data.get("store_address", "").strip()

    # Total
    total_amount = _parse_german_decimal(str(data.get("total_amount", "0")))

    # DateTime
    purchased_at = _parse_lidl_datetime(data)

    # Transaction ID: use TSE number if available, otherwise URL transaction_id
    tse = data.get("tse_transaction") or data.get("transaction_id", "")
    url_tid = data.get("transaction_id", "")

    return ParsedReceipt(
        store_name="Lidl",
        store_address=store_address,
        purchased_at=purchased_at,
        store_id=None,
        register_nr=None,
        bon_nr=None,
        beleg_nr=data.get("beleg_nr"),
        tse_transaction=tse if tse else None,
        total_amount=total_amount,
        items=items,
        bonus_entries=bonus_entries,
        total_bonus=total_bonus,
        bonus_balance=None,
        source_filename=f"lidl_{url_tid}.json" if url_tid else "lidl.json",
    )


def parse_lidl_payload(payload: dict) -> list[ParsedReceipt]:
    """Parse Lidl scraper export payload to a list of ParsedReceipt."""
    receipts_data = payload.get("receipts")
    if not isinstance(receipts_data, list):
        raise ValueError("Lidl payload must contain a 'receipts' list")

    parsed: list[ParsedReceipt] = []
    for receipt_data in receipts_data:
        if not isinstance(receipt_data, dict):
            continue
        try:
            parsed.append(parse_lidl_receipt(receipt_data))
        except Exception:
            continue

    return parsed
