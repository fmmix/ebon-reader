from __future__ import annotations

from typing import Final

CANONICAL_STORE_BY_TEMPLATE_SLUG: Final[dict[str, str]] = {
    "rewe": "REWE Markt GmbH",
    "lidl": "Lidl",
    "kaufland": "Kaufland",
}


def _normalize_slug(template_slug: str | None) -> str | None:
    if template_slug is None:
        return None
    normalized = template_slug.strip().lower()
    return normalized or None


def _normalize_raw_store_name(raw_store_name: str | None) -> str | None:
    if raw_store_name is None:
        return None
    normalized = raw_store_name.strip()
    return normalized or None


def canonical_store_name_from_raw(raw_store_name: str | None) -> str | None:
    normalized = _normalize_raw_store_name(raw_store_name)
    if normalized is None:
        return None

    lowered = normalized.lower()
    if "rewe" in lowered:
        return "REWE Markt GmbH"
    if "lidl" in lowered:
        return "Lidl"
    if "kaufland" in lowered:
        return "Kaufland"

    return normalized


def resolve_store_display_name(
    template_slug: str | None,
    raw_store_name: str | None,
) -> str:
    normalized_slug = _normalize_slug(template_slug)
    if normalized_slug is not None:
        canonical_from_template = CANONICAL_STORE_BY_TEMPLATE_SLUG.get(normalized_slug)
        if canonical_from_template is not None:
            return canonical_from_template

    canonical_from_raw = canonical_store_name_from_raw(raw_store_name)
    if canonical_from_raw is not None:
        return canonical_from_raw

    return "Unknown"
