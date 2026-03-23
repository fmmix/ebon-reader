from pydantic import BaseModel


class ParsedItemResponse(BaseModel):
    raw_name: str
    display_name: str
    unit_price: float
    quantity: int
    total_price: float
    vat_class: str
    is_deposit: bool
    category_id: int | None
    confidence: float
    method: str
    matched_rule_keyword: str | None = None
    matched_rule_match_type: str | None = None
    matched_rule_priority: int | None = None


class BonusEntryResponse(BaseModel):
    type: str
    description: str
    amount: float


class PreviewResponse(BaseModel):
    store_name: str
    store_address: str
    store_id: str | None = None
    register_nr: int | None = None
    bon_nr: str | None = None
    beleg_nr: str | None = None
    purchased_at: str
    total_amount: float
    tse_transaction: str | None
    is_duplicate: bool
    items: list[ParsedItemResponse]
    bonus_entries: list[BonusEntryResponse]
    total_bonus: float
    bonus_balance: float | None
    computed_total: float
    template_id: int | None = None
    template_slug: str = ""
    template_name: str = ""


class DebugTextResponse(BaseModel):
    raw_text: str


# --- Confirm request schemas ---


class ConfirmItem(BaseModel):
    """Item as edited by the user in the preview table."""

    raw_name: str
    display_name: str
    unit_price: float
    quantity: int
    total_price: float
    vat_class: str
    is_deposit: bool
    category_id: int | None
    is_manual_assignment: bool = False


class ConfirmBonus(BaseModel):
    type: str
    description: str
    amount: float


class ConfirmRequest(BaseModel):
    """Sent by the frontend to persist a receipt after user review."""

    store_name: str
    store_address: str
    store_id: str | None = None
    register_nr: int | None = None
    bon_nr: str | None = None
    beleg_nr: str | None = None
    purchased_at: str  # ISO datetime
    total_amount: float
    tse_transaction: str | None = None
    source_filename: str
    items: list[ConfirmItem]
    bonus_entries: list[ConfirmBonus]
    total_bonus: float
    bonus_balance: float | None = None
    template_id: int | None = None


class ConfirmResponse(BaseModel):
    id: int
    message: str
