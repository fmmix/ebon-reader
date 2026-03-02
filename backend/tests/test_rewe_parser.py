"""Unit tests for the REWE eBon PDF parser."""

from datetime import datetime

import pytest

from app.services.parser.rewe_parser import ParsedReceipt, _parse_items, parse_rewe_ebon


GOOD_RECEIPT_TEXT = """REWE Moon Market
Lunar Avenue 42
12345 Crater City
UID Nr. DE123456789
EUR
PAPRIKAPASTE 1,49 B
H-MILCH GVO-FREI 1,90 B
2 Stk x 0,95
PFAND 0,25 EURO 0,25 A *
---
SUMME EUR 3,64
Datum: 27.02.2026
Uhrzeit: 08:40:00 Uhr
Beleg-Nr. 3662
Bon-Nr.: 1124
Markt: 0001 Kasse: 5
TSE-Transaktion: 1236901
Bonus-Aktion(en) 1,40 EUR
Bonus-Coupon(s)
MOON COUPON 2,80 EUR
Aktuelles Bonus-Guthaben: 39,00 EUR
"""


BAD_VARIANT_RECEIPT_TEXT = """REWE Nebula Kiosk
Orbit Ring 7
54321 Starbase
UID Nr. DE987654321
EUR
PAPRIKAPASTE 1,49 B
---
SUMME EUR 1,49
12.11.2025 19:25 Bon-Nr.:5622
Markt: 0099 Kasse: 2
"""


REDEEMED_RECEIPT_TEXT = """REWE Planet Store
Galaxy Lane 9
55555 Solaris
UID Nr. DE123123123
EUR
WASSER 1,00 B
---
SUMME EUR 1,00
Datum: 27.02.2026
Uhrzeit: 09:15:00 Uhr
Bonus-Aktion(en) 1,40 EUR
Bonus-Coupon(s)
MOON COUPON 2,80 EUR
Eingesetztes Bonus-Guthaben: 11,39 EUR
Aktuelles Bonus-Guthaben: 27,61 EUR
"""


@pytest.fixture
def receipt(monkeypatch: pytest.MonkeyPatch) -> ParsedReceipt:
    monkeypatch.setattr(
        "app.services.parser.rewe_parser._extract_text",
        lambda _pdf_path: GOOD_RECEIPT_TEXT,
    )
    return parse_rewe_ebon("dummy.pdf")


@pytest.fixture
def bad_variant_receipt(monkeypatch: pytest.MonkeyPatch) -> ParsedReceipt:
    monkeypatch.setattr(
        "app.services.parser.rewe_parser._extract_text",
        lambda _pdf_path: BAD_VARIANT_RECEIPT_TEXT,
    )
    return parse_rewe_ebon("dummy.pdf")


@pytest.fixture
def redeemed_receipt(monkeypatch: pytest.MonkeyPatch) -> ParsedReceipt:
    monkeypatch.setattr(
        "app.services.parser.rewe_parser._extract_text",
        lambda _pdf_path: REDEEMED_RECEIPT_TEXT,
    )
    return parse_rewe_ebon("dummy.pdf")


class TestStoreInfo:
    def test_store_name(self, receipt: ParsedReceipt) -> None:
        assert receipt.store_name == "REWE Moon Market"

    def test_store_address(self, receipt: ParsedReceipt) -> None:
        assert "Lunar Avenue 42" in receipt.store_address
        assert "Crater City" in receipt.store_address


class TestMetadata:
    def test_purchase_date(self, receipt: ParsedReceipt) -> None:
        assert receipt.purchased_at is not None
        assert receipt.purchased_at.year == 2026
        assert receipt.purchased_at.month == 2
        assert receipt.purchased_at.day == 27

    def test_purchase_time(self, receipt: ParsedReceipt) -> None:
        assert receipt.purchased_at is not None
        assert receipt.purchased_at.hour == 8
        assert receipt.purchased_at.minute == 40
        assert receipt.purchased_at.second == 0

    def test_bon_nr(self, receipt: ParsedReceipt) -> None:
        assert receipt.bon_nr == "1124"

    def test_beleg_nr(self, receipt: ParsedReceipt) -> None:
        assert receipt.beleg_nr == "3662"

    def test_store_id(self, receipt: ParsedReceipt) -> None:
        assert receipt.store_id == "0001"

    def test_register_nr(self, receipt: ParsedReceipt) -> None:
        assert receipt.register_nr == 5

    def test_tse_transaction(self, receipt: ParsedReceipt) -> None:
        assert receipt.tse_transaction == "1236901"

    def test_total_amount(self, receipt: ParsedReceipt) -> None:
        assert receipt.total_amount == pytest.approx(3.64, abs=0.01)

    def test_bad_variant_fallback_purchased_at(
        self, bad_variant_receipt: ParsedReceipt
    ) -> None:
        assert bad_variant_receipt.purchased_at == datetime(2025, 11, 12, 19, 25)

    def test_bad_variant_bon_store_and_register(
        self, bad_variant_receipt: ParsedReceipt
    ) -> None:
        assert bad_variant_receipt.bon_nr == "5622"
        assert bad_variant_receipt.store_id == "0099"
        assert bad_variant_receipt.register_nr == 2


class TestItems:
    def test_infers_multi_pack_from_deposit_line(self) -> None:
        lines = [
            "REWE Testmarkt",
            "EUR",
            "VITA COLA ZUCK.F 7,74 A",
            "PFAND 1,50 EURO 1,50 A *",
            "---",
        ]

        items = _parse_items(lines)

        assert len(items) == 2
        cola, pfand = items

        assert cola.raw_name == "VITA COLA ZUCK.F"
        assert cola.quantity == 6
        assert cola.unit_price == pytest.approx(1.29, abs=0.01)
        assert cola.total_price == pytest.approx(7.74, abs=0.01)

        assert pfand.is_deposit is True
        assert pfand.quantity == 6
        assert pfand.unit_price == pytest.approx(0.25, abs=0.01)
        assert pfand.total_price == pytest.approx(1.50, abs=0.01)

    def test_item_count(self, receipt: ParsedReceipt) -> None:
        assert len(receipt.items) == 3

    def test_first_item(self, receipt: ParsedReceipt) -> None:
        first = receipt.items[0]
        assert "PAPRIKAPASTE" in first.raw_name
        assert first.total_price == pytest.approx(1.49, abs=0.01)
        assert first.vat_class == "B"

    def test_quantity_item(self, receipt: ParsedReceipt) -> None:
        """H-MILCH GVO-FREI: 2 Stk x 0,95 = 1,90."""
        milk = next((i for i in receipt.items if "MILCH" in i.raw_name), None)
        assert milk is not None
        assert milk.quantity == 2
        assert milk.unit_price == pytest.approx(0.95, abs=0.01)
        assert milk.total_price == pytest.approx(1.90, abs=0.01)

    def test_deposit_item(self, receipt: ParsedReceipt) -> None:
        """PFAND items should be flagged as deposits."""
        pfand = next((i for i in receipt.items if "PFAND" in i.raw_name), None)
        assert pfand is not None
        assert pfand.is_deposit is True
        assert pfand.vat_class == "A"

    def test_vat_classes(self, receipt: ParsedReceipt) -> None:
        """Items should have valid VAT classes."""
        for item in receipt.items:
            assert item.vat_class in ("A", "B")

    def test_item_prices_positive(self, receipt: ParsedReceipt) -> None:
        """All prices should be positive."""
        for item in receipt.items:
            assert item.total_price > 0
            assert item.unit_price > 0

    def test_items_sum_approximates_total(self, receipt: ParsedReceipt) -> None:
        """Sum of item prices should approximately match the total."""
        items_sum = sum(item.total_price for item in receipt.items)
        assert items_sum == pytest.approx(receipt.total_amount, abs=1.0)


class TestBonus:
    def test_bonus_action(self, receipt: ParsedReceipt) -> None:
        actions = [b for b in receipt.bonus_entries if b.type == "action"]
        assert len(actions) == 1
        assert actions[0].amount == pytest.approx(1.40, abs=0.01)

    def test_bonus_coupon(self, receipt: ParsedReceipt) -> None:
        coupons = [b for b in receipt.bonus_entries if b.type == "coupon"]
        assert len(coupons) == 1
        assert coupons[0].amount == pytest.approx(2.80, abs=0.01)

    def test_total_bonus(self, receipt: ParsedReceipt) -> None:
        assert receipt.total_bonus == pytest.approx(4.20, abs=0.01)

    def test_bonus_balance(self, receipt: ParsedReceipt) -> None:
        assert receipt.bonus_balance is not None
        assert receipt.bonus_balance == pytest.approx(39.00, abs=0.01)

    def test_redeemed_bonus_entry(self, redeemed_receipt: ParsedReceipt) -> None:
        redeemed = [b for b in redeemed_receipt.bonus_entries if b.type == "redeemed"]
        assert len(redeemed) == 1
        assert redeemed[0].description == "Eingesetztes Bonus-Guthaben"
        assert redeemed[0].amount == pytest.approx(11.39, abs=0.01)

    def test_total_bonus_excludes_redeemed(
        self, redeemed_receipt: ParsedReceipt
    ) -> None:
        assert redeemed_receipt.total_bonus == pytest.approx(4.20, abs=0.01)
