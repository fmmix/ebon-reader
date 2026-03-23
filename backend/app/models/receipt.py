from datetime import datetime

from sqlmodel import Field, SQLModel


class Receipt(SQLModel, table=True):
    __tablename__ = "receipt"

    id: int | None = Field(default=None, primary_key=True)

    # Purchase metadata
    purchased_at: datetime
    store_name: str = Field(default="REWE")
    store_address: str = Field(default="")

    # eBon identification
    store_id: str | None = Field(default=None, description="Markt ID, e.g. 0108")
    register_nr: int | None = Field(default=None, description="Kasse number")
    bon_nr: str | None = Field(default=None, description="Bon-Nr on the receipt")
    beleg_nr: str | None = Field(default=None, description="Beleg-Nr (payment doc)")
    tse_transaction: str | None = Field(
        default=None, unique=True, index=True,
        description="TSE-Transaktion ID — unique fiscal identifier",
    )

    # Financials
    total_amount: float
    currency: str = Field(default="EUR")
    total_bonus: float = Field(default=0.0, description="Sum of all bonus entries")
    bonus_balance: float | None = Field(
        default=None, description="Aktuelles Bonus-Guthaben at time of purchase",
    )

    # Import tracking
    source_filename: str = Field(default="")
    imported_at: datetime = Field(default_factory=datetime.now)

    # Parser template used for this receipt
    template_id: int | None = Field(default=None, foreign_key="parser_template.id")
