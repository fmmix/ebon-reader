from pydantic import BaseModel


class RuleCreate(BaseModel):
    keyword: str
    match_type: str = "contains"
    category_id: int
    priority: int = 0


class RuleUpdate(BaseModel):
    keyword: str | None = None
    match_type: str | None = None
    category_id: int | None = None
    priority: int | None = None


class RuleResponse(BaseModel):
    id: int
    keyword: str
    match_type: str
    category_id: int
    category_name: str
    priority: int


class ReCategorizeRequest(BaseModel):
    override_manual: bool = False


class ReCategorizeResponse(BaseModel):
    total_items: int
    processed_items: int
    updated_items: int
    unchanged_items: int
    skipped_manual_items: int
    overridden_manual_items: int
    categorized_items: int
    uncategorized_items: int


class ReCategorizeChange(BaseModel):
    from_category_id: int | None
    from_category_name: str
    to_category_id: int | None
    to_category_name: str
    item_count: int


class ReCategorizePreviewResponse(ReCategorizeResponse):
    changes: list[ReCategorizeChange]


class TaxonomyCategoryPayload(BaseModel):
    name: str
    icon: str
    color: str
    is_default: bool = False


class TaxonomyRulePayload(BaseModel):
    keyword: str
    match_type: str
    category_name: str
    priority: int = 0


class TaxonomyBundle(BaseModel):
    version: int = 1
    exported_at: str | None = None
    categories: list[TaxonomyCategoryPayload]
    rules: list[TaxonomyRulePayload]


class TaxonomyReplacePreviewResponse(BaseModel):
    incoming_categories: int
    incoming_rules: int
    normalized_categories: int
    normalized_rules: int
    existing_categories: int
    existing_rules: int
    receipt_items_total: int
    remap_matched_items: int
    fallback_uncategorized_items: int
    skipped_rules_missing_category: int
    will_ensure_uncategorized: bool


class TaxonomyBackupInfo(BaseModel):
    id: int
    created_at: str
    categories_count: int
    rules_count: int


class TaxonomyReplaceApplyResponse(TaxonomyReplacePreviewResponse):
    backup_id: int
