from sqlmodel import Session, select

from app.models.categorize_rule import CategorizeRule
from app.models.learned_mapping import LearnedMapping


class Categorizer:
    """Cascade categorization engine.

    Layers (first match wins):
      1. Learned mappings (exact item name → category)
      2. User/default keyword rules (contains/exact match)
      3. Fallback → None (uncategorized)

    Designed for ML expansion: add new layers between 2 and 3 later.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._rules: list[CategorizeRule] | None = None
        self._mappings: dict[str, int] | None = None

    def _load_rules(self) -> list[CategorizeRule]:
        if self._rules is None:
            self._rules = list(
                self._session.exec(
                    select(CategorizeRule).order_by(CategorizeRule.priority.desc())  # type: ignore[arg-type]
                )
            )
        return self._rules

    def _load_mappings(self) -> dict[str, int]:
        if self._mappings is None:
            mappings = self._session.exec(select(LearnedMapping))
            self._mappings = {m.item_name.upper(): m.category_id for m in mappings}
        return self._mappings

    def categorize(
        self,
        item_name: str,
    ) -> tuple[int | None, float, str, str | None, str | None, int | None]:
        """Categorize an item by name.

        Returns:
            (
                category_id,
                confidence,
                method,
                matched_rule_keyword,
                matched_rule_match_type,
                matched_rule_priority,
            )
            method is one of: "learned", "rule", or "none"
        """
        name_upper = item_name.strip().upper()

        # Layer 1: Learned mappings (exact match)
        mappings = self._load_mappings()
        if name_upper in mappings:
            return mappings[name_upper], 1.0, "learned", None, None, None

        # Layer 2: Keyword rules
        rules = self._load_rules()
        for rule in rules:
            keyword = rule.keyword.upper()
            if rule.match_type == "exact" and name_upper == keyword:
                return (
                    rule.category_id,
                    0.9,
                    "rule",
                    rule.keyword,
                    rule.match_type,
                    rule.priority,
                )
            if rule.match_type == "contains" and keyword in name_upper:
                return (
                    rule.category_id,
                    0.8,
                    "rule",
                    rule.keyword,
                    rule.match_type,
                    rule.priority,
                )

        # Layer 3 (future): ML classifier
        # Layer 4 (future): Embedding similarity

        return None, 0.0, "none", None, None, None

    def categorize_batch(
        self,
        item_names: list[str],
    ) -> list[tuple[int | None, float, str, str | None, str | None, int | None]]:
        """Categorize multiple items at once."""
        return [self.categorize(name) for name in item_names]
