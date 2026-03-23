"""Shared parser dataclasses used by all store-specific parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


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
    store_name: str = ""
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
