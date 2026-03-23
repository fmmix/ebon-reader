"""Unit tests for the Kaufland eBon PDF parser."""

from datetime import datetime

import pytest

from app.services.parser.kaufland_parser import ParsedReceipt, parse_kaufland_ebon


KAUFLAND_RECEIPT_TEXT = """KAUFLAND
Musterstrasse 10
12345 Beispielstadt
K-U-N-D-E-N-B-E-L-E-G
Filiale: 6620
Kasse: 35
Bon:24181
Preis EUR
Sucuk 2,49 B
K.H-Milch 2 * 0,95 1,90 B
Croissant Gefluegel
2 * 0,99 1,98 B
Vita Cola o.Zucker 4,74 A
Pfandartikel 1,50 A
K Card XTRA Rabatt -0,32
K Card XTRA Rabatt -0,50
Kaufland Card XTRA Rabatt -0,25
Mengenrabatt -0,58
Summe 10,96
Datum 11.03.26 11:57 Uhr
"""


@pytest.fixture
def receipt(monkeypatch: pytest.MonkeyPatch) -> ParsedReceipt:
    monkeypatch.setattr(
        "app.services.parser.kaufland_parser._extract_text",
        lambda _pdf_path: KAUFLAND_RECEIPT_TEXT,
    )
    return parse_kaufland_ebon("kaufland_sample.pdf")


class TestMetadata:
    def test_store_name_and_filename(self, receipt: ParsedReceipt) -> None:
        assert receipt.store_name == "Kaufland"
        assert receipt.source_filename == "kaufland_sample.pdf"

    def test_store_address_from_header(self, receipt: ParsedReceipt) -> None:
        assert "Musterstrasse 10" in receipt.store_address
        assert "12345 Beispielstadt" in receipt.store_address

    def test_footer_metadata(self, receipt: ParsedReceipt) -> None:
        assert receipt.total_amount == pytest.approx(10.96, abs=0.01)
        assert receipt.store_id == "6620"
        assert receipt.register_nr == 35
        assert receipt.bon_nr == "24181"
        assert receipt.purchased_at == datetime(2026, 3, 11, 11, 57)


class TestItems:
    def test_item_count(self, receipt: ParsedReceipt) -> None:
        assert len(receipt.items) == 5

    def test_single_line_item(self, receipt: ParsedReceipt) -> None:
        sucuk = next(i for i in receipt.items if i.raw_name == "Sucuk")
        assert sucuk.quantity == 1
        assert sucuk.unit_price == pytest.approx(2.49, abs=0.01)
        assert sucuk.total_price == pytest.approx(2.49, abs=0.01)
        assert sucuk.vat_class == "B"

    def test_explicit_quantity_item(self, receipt: ParsedReceipt) -> None:
        milk = next(i for i in receipt.items if i.raw_name == "K.H-Milch")
        assert milk.quantity == 2
        assert milk.unit_price == pytest.approx(0.95, abs=0.01)
        assert milk.total_price == pytest.approx(1.90, abs=0.01)

    def test_multiline_quantity_item(self, receipt: ParsedReceipt) -> None:
        croissant = next(i for i in receipt.items if "Croissant" in i.raw_name)
        assert croissant.raw_name == "Croissant Gefluegel"
        assert croissant.quantity == 2
        assert croissant.unit_price == pytest.approx(0.99, abs=0.01)
        assert croissant.total_price == pytest.approx(1.98, abs=0.01)

    def test_deposit_detection_and_pack_inference(self, receipt: ParsedReceipt) -> None:
        cola = next(i for i in receipt.items if i.raw_name == "Vita Cola o.Zucker")
        pfand = next(i for i in receipt.items if i.raw_name == "Pfandartikel")

        assert pfand.is_deposit is True
        assert cola.is_deposit is False

        assert cola.quantity == 6
        assert cola.unit_price == pytest.approx(0.79, abs=0.01)
        assert cola.total_price == pytest.approx(4.74, abs=0.01)

        assert pfand.quantity == 6
        assert pfand.unit_price == pytest.approx(0.25, abs=0.01)
        assert pfand.total_price == pytest.approx(1.50, abs=0.01)


class TestDiscounts:
    def test_parses_xtra_discounts_as_instant_discounts(
        self, receipt: ParsedReceipt
    ) -> None:
        discounts = [b for b in receipt.bonus_entries if b.type == "instant_discount"]
        assert len(discounts) == 3
        assert all(d.amount > 0 for d in discounts)
        assert sum(d.amount for d in discounts) == pytest.approx(1.07, abs=0.01)

    def test_parses_mengenrabatt_as_basket_discount(
        self, receipt: ParsedReceipt
    ) -> None:
        discounts = [b for b in receipt.bonus_entries if b.type == "basket_discount"]
        assert len(discounts) == 1
        assert discounts[0].description == "Mengenrabatt"
        assert discounts[0].amount == pytest.approx(0.58, abs=0.01)

    def test_total_bonus_stays_zero(self, receipt: ParsedReceipt) -> None:
        assert receipt.total_bonus == pytest.approx(0.0, abs=0.01)

    def test_items_minus_discounts_matches_total(self, receipt: ParsedReceipt) -> None:
        items_sum = sum(item.total_price for item in receipt.items)
        instant_discount_sum = sum(
            b.amount for b in receipt.bonus_entries if b.type == "instant_discount"
        )
        basket_discount_sum = sum(
            b.amount for b in receipt.bonus_entries if b.type == "basket_discount"
        )
        assert (
            items_sum - instant_discount_sum - basket_discount_sum
        ) == pytest.approx(receipt.total_amount, abs=0.01)
