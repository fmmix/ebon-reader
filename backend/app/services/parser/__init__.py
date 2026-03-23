"""Parser package — register all store parsers on import."""

from app.services.parser.lidl_parser import (
    is_lidl_json_payload,
    is_lidl_plain_text,
    parse_lidl_payload,
    parse_lidl_text_payload,
)
from app.services.parser.kaufland_parser import parse_kaufland_ebon
from app.services.parser.registry import (
    register_json_parser,
    register_parser,
    register_text_parser,
)
from app.services.parser.rewe_parser import parse_rewe_ebon


def _detect_rewe(text: str) -> bool:
    """Check if text looks like a REWE eBon."""
    # "REWE" may only appear in the footer ("REWE Markt GmbH", "REWE Bonus")
    return "REWE" in text.upper()


def _detect_kaufland(text: str) -> bool:
    """Check if text looks like a Kaufland eBon."""
    upper = text.upper()
    has_brand = "KAUFLAND" in upper
    has_markers = any(
        marker in upper
        for marker in ("K CARD XTRA", "KAUFLAND CARD XTRA", "K-U-N-D-E-N-B-E-L-E-G")
    )
    return has_brand and has_markers


register_parser("rewe", parse_rewe_ebon, _detect_rewe)
register_parser("kaufland", parse_kaufland_ebon, _detect_kaufland)
register_json_parser("lidl", parse_lidl_payload, is_lidl_json_payload)
register_text_parser("lidl", parse_lidl_text_payload, is_lidl_plain_text)
