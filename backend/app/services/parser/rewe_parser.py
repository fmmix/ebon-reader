"""REWE eBon PDF parser.

Extracts line items, receipt metadata, and bonus information
from REWE electronic receipts (eBons) in PDF format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ParsedItem:
    raw_name: str
    unit_price: float
    quantity: int = 1
    total_price: float = 0.0
    vat_class: str = "B"  # A=19%, B=7%
    is_deposit: bool = False

    def __post_init__(self) -> None:
        if self.total_price == 0.0:
            self.total_price = self.unit_price * self.quantity


@dataclass
class ParsedBonus:
    type: str  # "action", "coupon", or "redeemed"
    description: str
    amount: float


@dataclass
class ParsedReceipt:
    # Store info
    store_name: str = "REWE"
    store_address: str = ""

    # Purchase metadata
    purchased_at: datetime | None = None
    store_id: str | None = None
    register_nr: int | None = None
    bon_nr: str | None = None
    beleg_nr: str | None = None
    tse_transaction: str | None = None

    # Financials
    total_amount: float = 0.0
    currency: str = "EUR"

    # Items & bonus
    items: list[ParsedItem] = field(default_factory=list)
    bonus_entries: list[ParsedBonus] = field(default_factory=list)
    total_bonus: float = 0.0
    bonus_balance: float | None = None

    # Source
    source_filename: str = ""


# --- Regex patterns ---

# Item line: "PAPRIKAPASTETE 1,49 B" or "PFAND 0,25 EURO 0,75 A *"
RE_ITEM = re.compile(r"^(.+?)\s+(-?\d+,\d{2})\s+([AB])(\s+\*)?$")

# Quantity line: "2 Stk x 0,95"
RE_QUANTITY = re.compile(r"^(\d+)\s+Stk\s+x\s+(\d+,\d{2})$")

# Total: "SUMME EUR 56,70"
RE_TOTAL = re.compile(r"^SUMME\s+EUR\s+(\d+,\d{2})$", re.MULTILINE)

# Metadata
RE_DATE = re.compile(r"Datum:\s*(\d{2}\.\d{2}\.\d{4})")
RE_TIME = re.compile(r"Uhrzeit:\s*(\d{2}:\d{2}:\d{2})\s*Uhr")
RE_BON_LINE_DATETIME = re.compile(
    r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)\s+Bon-Nr\.:\s*\d+"
)
RE_BELEG_NR = re.compile(r"Beleg-Nr\.\s*(\d+)")
RE_BON_NR = re.compile(r"Bon-Nr\.:\s*(\d+)")
RE_MARKT_KASSE = re.compile(r"Markt:\s*(\d+)\s+Kasse:\s*(\d+)")
RE_TSE_TRANSACTION = re.compile(r"TSE-Transaktion:\s*(\d+)")

# Bonus
RE_BONUS_ACTION = re.compile(r"Bonus-Aktion\(en\)\s+(\d+,\d{2})\s+EUR")
RE_BONUS_BALANCE = re.compile(r"Aktuelles Bonus-Guthaben:\s*(\d+,\d{2})\s+EUR")
RE_BONUS_REDEEMED = re.compile(r"Eingesetztes Bonus-Guthaben:\s*(\d+,\d{2})\s+EUR")
RE_PAYMENT_REDEEMED = re.compile(r"Geg\.\s*Bonus-Guthaben\s+EUR\s+(\d+,\d{2})")
# Coupon lines appear between "Bonus-Coupon(s)" and "Aktuelles"
RE_COUPON_LINE = re.compile(r"^(.+?)\s+(\d+,\d{2})\s+EUR$")

DEPOSIT_UNIT_BASES = (0.25, 0.15, 0.08)


def _parse_german_decimal(s: str) -> float:
    """Convert German decimal format '1,49' to float 1.49."""
    return round(float(s.replace(",", ".")), 2)


def _extract_text(pdf_path: str | Path) -> str:
    """Extract full text from all PDF pages."""
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def _infer_pack_quantity_from_deposit(
    deposit_total: float,
    item_total: float,
) -> int | None:
    """Infer pack quantity from deposit total and item total."""
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


def _parse_items(lines: list[str]) -> list[ParsedItem]:
    """Parse line items from the items section of the receipt."""
    items: list[ParsedItem] = []
    in_items = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Start parsing after the "EUR" currency header line
        if stripped == "EUR":
            in_items = True
            continue

        # Stop at the separator line
        if in_items and stripped.startswith("---"):
            break

        # Stop at SUMME
        if in_items and RE_TOTAL.match(stripped):
            break

        if not in_items:
            continue

        # Try to match a quantity line first (updates the previous item)
        qty_match = RE_QUANTITY.match(stripped)
        if qty_match and items:
            qty = int(qty_match.group(1))
            unit_price = _parse_german_decimal(qty_match.group(2))
            items[-1].quantity = qty
            items[-1].unit_price = unit_price
            # total_price stays as parsed from the item line above
            continue

        # Try to match an item line
        item_match = RE_ITEM.match(stripped)
        if item_match:
            raw_name = item_match.group(1).strip()
            total_price = _parse_german_decimal(item_match.group(2))
            vat_class = item_match.group(3)
            is_deposit = item_match.group(4) is not None

            item = ParsedItem(
                raw_name=raw_name,
                unit_price=total_price,  # Updated if quantity line follows
                quantity=1,
                total_price=total_price,
                vat_class=vat_class,
                is_deposit=is_deposit,
            )
            items.append(item)

            if is_deposit and len(items) >= 2:
                previous_item = items[-2]
                is_default_single_qty = (
                    previous_item.quantity == 1
                    and previous_item.unit_price == previous_item.total_price
                )
                if not previous_item.is_deposit and is_default_single_qty:
                    inferred_qty = _infer_pack_quantity_from_deposit(
                        deposit_total=item.total_price,
                        item_total=previous_item.total_price,
                    )
                    if inferred_qty is not None:
                        previous_item.quantity = inferred_qty
                        previous_item.unit_price = round(
                            previous_item.total_price / inferred_qty,
                            2,
                        )
                        item.quantity = inferred_qty
                        item.unit_price = round(item.total_price / inferred_qty, 2)

    return items


def _parse_metadata(text: str) -> dict:
    """Extract receipt metadata fields from the full text."""
    meta: dict = {}

    date_match = RE_DATE.search(text)
    time_match = RE_TIME.search(text)
    if date_match:
        date_str = date_match.group(1)
        time_str = time_match.group(1) if time_match else "00:00:00"
        meta["purchased_at"] = datetime.strptime(
            f"{date_str} {time_str}", "%d.%m.%Y %H:%M:%S"
        )

    if "purchased_at" not in meta:
        bon_line_match = RE_BON_LINE_DATETIME.search(text)
        if bon_line_match:
            date_str, time_str = bon_line_match.groups()
            time_format = "%H:%M:%S" if time_str.count(":") == 2 else "%H:%M"
            meta["purchased_at"] = datetime.strptime(
                f"{date_str} {time_str}", f"%d.%m.%Y {time_format}"
            )

    beleg = RE_BELEG_NR.search(text)
    if beleg:
        meta["beleg_nr"] = beleg.group(1)

    bon = RE_BON_NR.search(text)
    if bon:
        meta["bon_nr"] = bon.group(1)

    mk = RE_MARKT_KASSE.search(text)
    if mk:
        meta["store_id"] = mk.group(1)
        meta["register_nr"] = int(mk.group(2))

    tse = RE_TSE_TRANSACTION.search(text)
    if tse:
        meta["tse_transaction"] = tse.group(1)

    total = RE_TOTAL.search(text)
    if total:
        meta["total_amount"] = _parse_german_decimal(total.group(1))

    return meta


def _parse_store_info(lines: list[str]) -> dict:
    """Extract store name and address from the header."""
    info: dict = {"store_name": "REWE", "store_address": ""}

    # Store name is typically the first line
    if lines and "REWE" in lines[0]:
        info["store_name"] = lines[0].strip()

    # Address lines follow until UID Nr.
    address_parts: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("UID") or stripped == "EUR":
            break
        if stripped:
            address_parts.append(stripped)

    info["store_address"] = ", ".join(address_parts)
    return info


def _parse_bonus(text: str) -> tuple[list[ParsedBonus], float, float | None]:
    """Extract bonus entries from the receipt text.

    Returns:
        (bonus_entries, total_bonus, bonus_balance)
    """
    entries: list[ParsedBonus] = []
    total_bonus = 0.0
    bonus_balance: float | None = None
    redeemed_found = False

    # Bonus-Aktion(en)
    action_match = RE_BONUS_ACTION.search(text)
    if action_match:
        amount = _parse_german_decimal(action_match.group(1))
        entries.append(
            ParsedBonus(
                type="action",
                description="Bonus-Aktion(en)",
                amount=amount,
            )
        )
        total_bonus = round(total_bonus + amount, 2)

    # Bonus-Coupon(s) — parse lines between "Bonus-Coupon(s)" and "Aktuelles"
    lines = text.split("\n")
    in_coupon_section = False
    for line in lines:
        stripped = line.strip()

        if "Bonus-Coupon(s)" in stripped:
            in_coupon_section = True
            continue

        if in_coupon_section:
            if "Aktuelles Bonus-Guthaben" in stripped:
                break

            redeemed_match = RE_BONUS_REDEEMED.search(stripped)
            if redeemed_match:
                amount = _parse_german_decimal(redeemed_match.group(1))
                entries.append(
                    ParsedBonus(
                        type="redeemed",
                        description="Eingesetztes Bonus-Guthaben",
                        amount=amount,
                    )
                )
                redeemed_found = True
                continue

            coupon_match = RE_COUPON_LINE.match(stripped)
            if coupon_match:
                desc = coupon_match.group(1).strip()
                amount = _parse_german_decimal(coupon_match.group(2))
                entries.append(
                    ParsedBonus(
                        type="coupon",
                        description=desc,
                        amount=amount,
                    )
                )
                total_bonus = round(total_bonus + amount, 2)

    if not redeemed_found:
        payment_redeemed_match = RE_PAYMENT_REDEEMED.search(text)
        if payment_redeemed_match:
            amount = _parse_german_decimal(payment_redeemed_match.group(1))
            entries.append(
                ParsedBonus(
                    type="redeemed",
                    description="Eingesetztes Bonus-Guthaben",
                    amount=amount,
                )
            )

    # Bonus balance
    balance_match = RE_BONUS_BALANCE.search(text)
    if balance_match:
        bonus_balance = _parse_german_decimal(balance_match.group(1))

    return entries, total_bonus, bonus_balance


def parse_rewe_ebon(pdf_path: str | Path) -> ParsedReceipt:
    """Parse a REWE eBon PDF and return structured receipt data.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        ParsedReceipt with items, metadata, and bonus information.
    """
    text = _extract_text(pdf_path)
    lines = text.split("\n")

    # Parse all sections
    store_info = _parse_store_info(lines)
    items = _parse_items(lines)
    metadata = _parse_metadata(text)
    bonus_entries, total_bonus, bonus_balance = _parse_bonus(text)

    return ParsedReceipt(
        store_name=store_info["store_name"],
        store_address=store_info["store_address"],
        purchased_at=metadata.get("purchased_at"),
        store_id=metadata.get("store_id"),
        register_nr=metadata.get("register_nr"),
        bon_nr=metadata.get("bon_nr"),
        beleg_nr=metadata.get("beleg_nr"),
        tse_transaction=metadata.get("tse_transaction"),
        total_amount=metadata.get("total_amount", 0.0),
        items=items,
        bonus_entries=bonus_entries,
        total_bonus=total_bonus,
        bonus_balance=bonus_balance,
        source_filename=Path(pdf_path).name,
    )
