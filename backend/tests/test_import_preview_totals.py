from sqlmodel import Session, SQLModel, create_engine

from app.api.import_routes import _build_preview_response
from app.models.parser_template import ParserTemplate
from app.models.product_category import ProductCategory  # noqa: F401
from app.services.parser.base import ParsedBonus, ParsedItem, ParsedReceipt


class FakeCategorizer:
    def categorize(
        self, _raw_name: str
    ) -> tuple[int | None, float, str, str | None, str | None, int | None]:
        return (None, 0.0, "none", None, None, None)


def _session_with_template(slug: str = "rewe") -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    session.add(ParserTemplate(slug=slug, display_name="REWE eBon"))
    session.commit()
    return session


def test_redeemed_bonus_does_not_reduce_preview_computed_total() -> None:
    session = _session_with_template()
    receipt = ParsedReceipt(
        total_amount=59.76,
        items=[ParsedItem(raw_name="ARTIKEL", unit_price=59.76)],
        bonus_entries=[
            ParsedBonus(
                type="redeemed",
                description="Eingesetztes Bonus-Guthaben",
                amount=39.00,
            )
        ],
    )

    preview = _build_preview_response(receipt, "rewe", session, FakeCategorizer())

    assert preview.total_amount == 59.76
    assert preview.computed_total == 59.76
    session.close()


def test_instant_discount_reduces_preview_computed_total() -> None:
    session = _session_with_template()
    receipt = ParsedReceipt(
        total_amount=57.76,
        items=[ParsedItem(raw_name="ARTIKEL", unit_price=59.76)],
        bonus_entries=[
            ParsedBonus(
                type="instant_discount",
                description="Sofort-Rabatt",
                amount=2.00,
            )
        ],
    )

    preview = _build_preview_response(receipt, "rewe", session, FakeCategorizer())

    assert preview.total_amount == 57.76
    assert preview.computed_total == 57.76
    session.close()


def test_basket_discount_reduces_preview_computed_total() -> None:
    session = _session_with_template()
    receipt = ParsedReceipt(
        total_amount=58.26,
        items=[ParsedItem(raw_name="ARTIKEL", unit_price=59.76)],
        bonus_entries=[
            ParsedBonus(
                type="basket_discount",
                description="Mengenrabatt",
                amount=1.50,
            )
        ],
    )

    preview = _build_preview_response(receipt, "rewe", session, FakeCategorizer())

    assert preview.total_amount == 58.26
    assert preview.computed_total == 58.26
    session.close()
