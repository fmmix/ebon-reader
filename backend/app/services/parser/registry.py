"""Parser registry: auto-detect store template and dispatch to the correct parser."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.services.parser.base import ParsedReceipt

# Each parser is a callable: (pdf_path) -> ParsedReceipt
ParserFunc = Callable[[str | Path], ParsedReceipt]
JsonParserFunc = Callable[[dict], list[ParsedReceipt]]
TextParserFunc = Callable[[str, str], list[ParsedReceipt]]

_REGISTRY: dict[str, ParserFunc] = {}
_JSON_REGISTRY: dict[str, JsonParserFunc] = {}
_TEXT_REGISTRY: dict[str, TextParserFunc] = {}

# Detection rules: (check_func, slug) — evaluated in registration order
_DETECTORS: list[tuple[Callable[[str], bool], str]] = []
_JSON_DETECTORS: list[tuple[Callable[[dict], bool], str]] = []
_TEXT_DETECTORS: list[tuple[Callable[[str], bool], str]] = []


def register_parser(
    slug: str,
    parser_func: ParserFunc,
    detector: Callable[[str], bool],
) -> None:
    """Register a parser with its slug and text-detection function."""
    _REGISTRY[slug] = parser_func
    _DETECTORS.append((detector, slug))


def register_json_parser(
    slug: str,
    parser_func: JsonParserFunc,
    detector: Callable[[dict], bool],
) -> None:
    """Register a JSON parser with its slug and payload-detection function."""
    _JSON_REGISTRY[slug] = parser_func
    _JSON_DETECTORS.append((detector, slug))


def register_text_parser(
    slug: str,
    parser_func: TextParserFunc,
    detector: Callable[[str], bool],
) -> None:
    """Register a text parser with its slug and payload-detection function."""
    _TEXT_REGISTRY[slug] = parser_func
    _TEXT_DETECTORS.append((detector, slug))


def detect_template(text: str) -> str | None:
    """Sniff extracted PDF text and return the matching template slug, or None."""
    for detector, slug in _DETECTORS:
        if detector(text):
            return slug
    return None


def detect_json_template(payload: dict) -> str | None:
    """Detect the JSON template slug from payload structure."""
    for detector, slug in _JSON_DETECTORS:
        if detector(payload):
            return slug
    return None


def detect_text_template(text: str) -> str | None:
    """Detect the text template slug from payload content."""
    for detector, slug in _TEXT_DETECTORS:
        if detector(text):
            return slug
    return None


def get_parser(slug: str) -> ParserFunc | None:
    """Get a parser function by template slug."""
    return _REGISTRY.get(slug)


def get_json_parser(slug: str) -> JsonParserFunc | None:
    """Get a JSON parser function by template slug."""
    return _JSON_REGISTRY.get(slug)


def get_text_parser(slug: str) -> TextParserFunc | None:
    """Get a text parser function by template slug."""
    return _TEXT_REGISTRY.get(slug)


def list_registered_slugs() -> list[str]:
    """Return all registered template slugs."""
    return list(_REGISTRY.keys())


def list_registered_json_slugs() -> list[str]:
    """Return all registered JSON template slugs."""
    return list(_JSON_REGISTRY.keys())


def list_registered_text_slugs() -> list[str]:
    """Return all registered text template slugs."""
    return list(_TEXT_REGISTRY.keys())


def parse_ebon(
    pdf_path: str | Path,
    template_slug: str | None = None,
) -> tuple[ParsedReceipt, str]:
    """Parse a PDF using the specified or auto-detected template.

    Returns:
        (parsed_receipt, detected_slug)

    Raises:
        ValueError if no template could be detected or the slug is unknown.
    """
    if template_slug is None:
        import pdfplumber

        with pdfplumber.open(str(pdf_path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        template_slug = detect_template(text)
        if template_slug is None:
            registered = ", ".join(list_registered_slugs()) or "(none)"
            raise ValueError(
                "Could not detect store template from PDF content. "
                f"Registered templates: {registered}"
            )

    parser = get_parser(template_slug)
    if parser is None:
        raise ValueError(f"Unknown template '{template_slug}'")

    receipt = parser(pdf_path)
    return receipt, template_slug


def parse_json_payload(
    payload: dict,
    template_slug: str | None = None,
) -> tuple[list[ParsedReceipt], str]:
    """Parse a structured JSON payload using the specified or auto-detected parser."""
    if template_slug is None:
        template_slug = detect_json_template(payload)
        if template_slug is None:
            registered = ", ".join(list_registered_json_slugs()) or "(none)"
            raise ValueError(
                "Could not detect store template from JSON payload. "
                f"Registered JSON templates: {registered}"
            )

    parser = get_json_parser(template_slug)
    if parser is None:
        raise ValueError(f"Unknown JSON template '{template_slug}'")

    receipts = parser(payload)
    if not receipts:
        raise ValueError("JSON payload did not produce any parseable receipts")

    return receipts, template_slug


def parse_text_payload(
    text: str,
    source_filename: str,
    template_slug: str | None = None,
) -> tuple[list[ParsedReceipt], str]:
    """Parse a plain-text payload using the specified or auto-detected parser."""
    if template_slug is None:
        template_slug = detect_text_template(text)
        if template_slug is None:
            registered = ", ".join(list_registered_text_slugs()) or "(none)"
            raise ValueError(
                "Could not detect store template from TXT payload. "
                f"Registered TXT templates: {registered}"
            )

    parser = get_text_parser(template_slug)
    if parser is None:
        raise ValueError(f"Unknown TXT template '{template_slug}'")

    receipts = parser(text, source_filename)
    if not receipts:
        raise ValueError("TXT payload did not produce any parseable receipts")

    return receipts, template_slug
