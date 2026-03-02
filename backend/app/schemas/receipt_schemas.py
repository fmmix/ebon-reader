from pydantic import BaseModel


class ReceiptItemResponse(BaseModel):
    id: int
    raw_name: str
    display_name: str
    unit_price: float
    quantity: int
    total_price: float
    vat_class: str
    is_deposit: bool
    is_manual_assignment: bool
    category_id: int | None
    category_name: str | None = None
    category_icon: str | None = None


class BonusEntryResponse(BaseModel):
    id: int
    type: str
    description: str
    amount: float


class ReceiptListItem(BaseModel):
    id: int
    purchased_at: str
    store_name: str
    store_address: str
    total_amount: float
    total_bonus: float
    source_filename: str
    item_count: int


class ReceiptDetail(BaseModel):
    id: int
    purchased_at: str
    store_name: str
    store_address: str
    total_amount: float
    total_bonus: float
    bonus_balance: float | None
    source_filename: str
    tse_transaction: str | None
    bon_nr: str | None
    store_id: str | None
    register_nr: int | None
    imported_at: str
    items: list[ReceiptItemResponse]
    bonus_entries: list[BonusEntryResponse]
