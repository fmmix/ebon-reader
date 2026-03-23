"""Unit tests for the LIDL receipt parser."""

import pytest

import app.services.parser  # noqa: F401 - ensure parser registrations are loaded

from app.services.parser.lidl_parser import (
    is_lidl_json_payload,
    is_lidl_plain_text,
    parse_lidl_payload,
    parse_lidl_plain_text,
    parse_lidl_receipt,
)
from app.services.parser.registry import parse_text_payload


# Sample data matching the LIDL HTML data-attributes structure
SAMPLE_RECEIPT = {
    "transaction_id": "1234560585202603054385",
    "store_address": "Große Mond Str. 99, 12345 Berlin",
    "total_amount": "22,39",
    "payment_method": "Kreditkarte",
    "raw_datetime": "05.03.26 15:10",
    "tse_transaction": "123456",
    "beleg_nr": "1234",
    "items": [
        {
            "description": "Bananen Fairtra",
            "unit_price": "1,69",
            "total_price": "1,23",
            "quantity": "0,728",
            "tax_type": "A",
        },
        {
            "description": "Butterkäse [OGT]",
            "unit_price": "2,45",
            "total_price": "2,45",
            "quantity": None,
            "tax_type": "A",
        },
        {
            "description": "Danone Actimel Clas",
            "unit_price": "3,44",
            "total_price": "3,44",
            "quantity": None,
            "tax_type": "A",
        },
        {
            "description": "Gr. Joghurt Brombeer",
            "unit_price": "1,59",
            "total_price": "1,59",
            "quantity": None,
            "tax_type": "A",
        },
        {
            "description": "Edelsalami geschnitt",
            "unit_price": "1,49",
            "total_price": "1,49",
            "quantity": None,
            "tax_type": "A",
        },
        {
            "description": "H-Milch 3,5%",
            "unit_price": "0,95",
            "total_price": "0,95",
            "quantity": None,
            "tax_type": "A",
        },
        {
            "description": "Schwip Schwap Lem.Ze",
            "unit_price": "0,88",
            "total_price": "5,28",
            "quantity": "6",
            "tax_type": "B",
        },
        {
            "description": "Pfand 0,25 M",
            "unit_price": "0,25",
            "total_price": "1,50",
            "quantity": "6",
            "tax_type": "B",
        },
        {
            "description": "Energy Drink light",
            "unit_price": "0,49",
            "total_price": "0,49",
            "quantity": None,
            "tax_type": "B",
        },
        {
            "description": "Pfand 0,25 EM",
            "unit_price": "0,25",
            "total_price": "0,25",
            "quantity": None,
            "tax_type": "B",
        },
        {
            "description": "Brot Bauernkru.",
            "unit_price": "1,99",
            "total_price": "1,99",
            "quantity": None,
            "tax_type": "A",
        },
        {
            "description": "Croissant Wien.",
            "unit_price": "0,99",
            "total_price": "1,98",
            "quantity": "2",
            "tax_type": "A",
        },
    ],
    "discounts": [
        {
            "description": "Lidl Plus Rabatt",
            "amount": "0,25",
            "promotion_id": "100001000-DE-TEMPLATE-DEAS000112569-2",
        }
    ],
}

SAMPLE_PLAIN_TEXT = """logo
Lidl Plus
Lidl Vertriebs-GmbH
Musterstrasse 10
10115 Berlin
EUR
Schwip Schwap Lem.Ze 0,88 x 6 5,28 B
Pfand 0,25 M 0,25 x 6 1,50 B
Brot Bauernkru. 1,99 A
Lidl Plus Rabatt -0,25
zu zahlen 8,52
Beleg-Nr. 4711
TSE Transaktionsnummer: 99887766
K-U-N-D-E-N-B-E-L-E-G
05.03.2026 15:10
"""


@pytest.fixture
def receipt():
    return parse_lidl_receipt(SAMPLE_RECEIPT)


class TestStoreInfo:
    def test_store_name(self, receipt):
        assert receipt.store_name == "Lidl"

    def test_store_address(self, receipt):
        assert "Große Mond Str. 99" in receipt.store_address
        assert "Berlin" in receipt.store_address


class TestMetadata:
    def test_total_amount(self, receipt):
        assert receipt.total_amount == pytest.approx(22.39, abs=0.01)

    def test_transaction_id(self, receipt):
        assert receipt.tse_transaction == "123456"

    def test_beleg_nr(self, receipt):
        assert receipt.beleg_nr == "1234"

    def test_purchased_at(self, receipt):
        assert receipt.purchased_at is not None
        assert receipt.purchased_at.year == 2026
        assert receipt.purchased_at.month == 3
        assert receipt.purchased_at.day == 5
        assert receipt.purchased_at.hour == 15
        assert receipt.purchased_at.minute == 10

    def test_source_filename(self, receipt):
        assert "lidl_" in receipt.source_filename
        assert "lidl_1234560585202603054385" in receipt.source_filename


class TestItems:
    def test_item_count(self, receipt):
        assert len(receipt.items) == 12

    def test_weight_based_item(self, receipt):
        """Bananas: 0.728 kg × 1.69 EUR/kg = 1.23 EUR — stored as qty=1."""
        bananas = receipt.items[0]
        assert bananas.raw_name == "Bananen Fairtra"
        assert bananas.quantity == 1
        assert bananas.total_price == pytest.approx(1.23, abs=0.01)
        # For weight items, unit_price = total_price
        assert bananas.unit_price == pytest.approx(1.23, abs=0.01)
        assert bananas.vat_class == "A"

    def test_single_item(self, receipt):
        """Butterkäse: single item, no quantity."""
        butter = receipt.items[1]
        assert butter.raw_name == "Butterkäse [OGT]"
        assert butter.quantity == 1
        assert butter.unit_price == pytest.approx(2.45, abs=0.01)
        assert butter.total_price == pytest.approx(2.45, abs=0.01)

    def test_multi_quantity_item(self, receipt):
        """Schwip Schwap: 6 × 0.88 = 5.28."""
        schwip = next(i for i in receipt.items if "Schwip" in i.raw_name)
        assert schwip.quantity == 6
        assert schwip.unit_price == pytest.approx(0.88, abs=0.01)
        assert schwip.total_price == pytest.approx(5.28, abs=0.01)
        assert schwip.vat_class == "B"

    def test_deposit_item(self, receipt):
        """Pfand items should be flagged as deposits."""
        pfand_items = [i for i in receipt.items if "Pfand" in i.raw_name]
        assert len(pfand_items) == 2
        for item in pfand_items:
            assert item.is_deposit is True

    def test_deposit_6x(self, receipt):
        """Pfand 0,25 M: 6 × 0.25 = 1.50."""
        pfand = next(i for i in receipt.items if i.raw_name == "Pfand 0,25 M")
        assert pfand.quantity == 6
        assert pfand.unit_price == pytest.approx(0.25, abs=0.01)
        assert pfand.total_price == pytest.approx(1.50, abs=0.01)

    def test_croissant_2x(self, receipt):
        """Croissant: 2 × 0.99 = 1.98."""
        croissant = next(i for i in receipt.items if "Croissant" in i.raw_name)
        assert croissant.quantity == 2
        assert croissant.unit_price == pytest.approx(0.99, abs=0.01)
        assert croissant.total_price == pytest.approx(1.98, abs=0.01)

    def test_vat_classes(self, receipt):
        for item in receipt.items:
            assert item.vat_class in ("A", "B")


class TestDiscounts:
    def test_discount_count(self, receipt):
        assert len(receipt.bonus_entries) == 1

    def test_lidl_plus_rabatt(self, receipt):
        discount = receipt.bonus_entries[0]
        assert discount.description == "Lidl Plus Rabatt"
        assert discount.amount == pytest.approx(0.25, abs=0.01)
        assert discount.type == "instant_discount"

    def test_instant_discount_uses_positive_magnitude(self, receipt):
        discount = receipt.bonus_entries[0]
        assert discount.type == "instant_discount"
        assert discount.amount > 0
        assert discount.amount == pytest.approx(0.25, abs=0.01)

    def test_total_bonus(self, receipt):
        assert receipt.total_bonus == pytest.approx(0.0, abs=0.01)


class TestEdgeCases:
    def test_empty_receipt(self):
        result = parse_lidl_receipt(
            {
                "transaction_id": "test",
                "total_amount": "0",
                "items": [],
                "discounts": [],
            }
        )
        assert result.store_name == "Lidl"
        assert len(result.items) == 0
        assert result.total_amount == 0.0

    def test_missing_quantity(self):
        """Items without quantity should default to 1."""
        result = parse_lidl_receipt(
            {
                "transaction_id": "test",
                "total_amount": "1,49",
                "items": [
                    {
                        "description": "Test Item",
                        "unit_price": "1,49",
                        "total_price": "1,49",
                        "quantity": None,
                        "tax_type": "A",
                    }
                ],
                "discounts": [],
            }
        )
        assert result.items[0].quantity == 1
        assert result.items[0].unit_price == pytest.approx(1.49, abs=0.01)

    def test_iso_timestamp(self):
        """ISO timestamp format should be parsed correctly."""
        result = parse_lidl_receipt(
            {
                "transaction_id": "test",
                "total_amount": "0",
                "timestamp": "2026-03-05T14:12:54.000Z",
                "items": [],
                "discounts": [],
            }
        )
        assert result.purchased_at is not None
        assert result.purchased_at.year == 2026
        assert result.purchased_at.month == 3
        assert result.purchased_at.day == 5


class TestPayloadDetection:
    def test_detects_valid_lidl_payload(self):
        assert is_lidl_json_payload({"receipts": [SAMPLE_RECEIPT]}) is True

    def test_rejects_non_receipt_shape(self):
        assert is_lidl_json_payload({"receipts": [{"foo": "bar"}]}) is False


class TestBulkPayloadParser:
    def test_parses_receipt_list(self):
        parsed = parse_lidl_payload({"receipts": [SAMPLE_RECEIPT]})
        assert len(parsed) == 1
        assert parsed[0].store_name == "Lidl"

    def test_skips_unparseable_receipts(self):
        parsed = parse_lidl_payload({"receipts": [SAMPLE_RECEIPT, {"items": "bad"}]})
        assert len(parsed) == 1


class TestPlainTextParser:
    def test_detects_lidl_plain_text(self):
        assert is_lidl_plain_text(SAMPLE_PLAIN_TEXT) is True

    def test_parse_plain_text_core_metadata(self):
        receipt = parse_lidl_plain_text(
            SAMPLE_PLAIN_TEXT, source_filename="manual-lidl.txt"
        )

        assert receipt.store_name == "Lidl"
        assert receipt.total_amount == pytest.approx(8.52, abs=0.01)
        assert receipt.tse_transaction == "99887766"
        assert receipt.beleg_nr == "4711"
        assert receipt.purchased_at is not None
        assert receipt.purchased_at.year == 2026
        assert receipt.purchased_at.month == 3
        assert receipt.purchased_at.day == 5
        assert receipt.purchased_at.hour == 15
        assert receipt.purchased_at.minute == 10

    def test_parse_plain_text_items_and_bonus(self):
        receipt = parse_lidl_plain_text(SAMPLE_PLAIN_TEXT)

        schwip = next(i for i in receipt.items if "Schwip" in i.raw_name)
        assert schwip.quantity == 6
        assert schwip.unit_price == pytest.approx(0.88, abs=0.01)
        assert schwip.total_price == pytest.approx(5.28, abs=0.01)

        pfand = next(i for i in receipt.items if "Pfand" in i.raw_name)
        assert pfand.is_deposit is True
        assert pfand.quantity == 6
        assert pfand.total_price == pytest.approx(1.50, abs=0.01)

        assert len(receipt.bonus_entries) == 1
        discount = receipt.bonus_entries[0]
        assert discount.type == "instant_discount"
        assert discount.amount == pytest.approx(0.25, abs=0.01)
        assert discount.amount > 0

    def test_plain_text_totals_math(self):
        receipt = parse_lidl_plain_text(SAMPLE_PLAIN_TEXT)

        items_total = sum(item.total_price for item in receipt.items)
        instant_discount = sum(
            bonus.amount
            for bonus in receipt.bonus_entries
            if bonus.type == "instant_discount"
        )

        assert items_total - instant_discount == pytest.approx(
            receipt.total_amount, abs=0.01
        )


class TestTextPayloadRegistry:
    def test_autodetects_lidl_plain_text_payload(self):
        receipts, slug = parse_text_payload(
            SAMPLE_PLAIN_TEXT,
            source_filename="upload.txt",
        )

        assert slug == "lidl"
        assert len(receipts) == 1
        assert receipts[0].store_name == "Lidl"
        assert receipts[0].source_filename == "upload.txt"
