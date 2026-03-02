from fastapi import APIRouter, Depends, HTTPException
import json
from datetime import datetime, timezone
from sqlalchemy import desc
from sqlmodel import Session, func, select
from typing import Any, cast

from app.core.database import get_session
from app.models.categorize_rule import CategorizeRule
from app.models.product_category import ProductCategory
from app.models.receipt_item import ReceiptItem
from app.models.taxonomy_backup import TaxonomyBackup
from app.schemas.rule_schemas import (
    ReCategorizeChange,
    ReCategorizePreviewResponse,
    ReCategorizeRequest,
    ReCategorizeResponse,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    TaxonomyBundle,
    TaxonomyBackupInfo,
    TaxonomyCategoryPayload,
    TaxonomyReplaceApplyResponse,
    TaxonomyReplacePreviewResponse,
    TaxonomyRulePayload,
)
from app.services.categorizer import Categorizer

router = APIRouter(prefix="/api/rules", tags=["rules"])

UNCATEGORIZED_NAME = "Uncategorized"
UNCATEGORIZED_ICON = "🏷️"
UNCATEGORIZED_COLOR = "#6b7280"


def _resolve_category_name(
    category_id: int | None, category_names_by_id: dict[int, str]
) -> str:
    if category_id is None:
        return UNCATEGORIZED_NAME
    return category_names_by_id.get(category_id, "Unknown")


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def _normalize_match_type(value: str) -> str:
    candidate = value.strip().lower()
    return candidate if candidate else "contains"


def _build_taxonomy_bundle(session: Session) -> TaxonomyBundle:
    categories = list(session.exec(select(ProductCategory)).all())
    categories.sort(key=lambda category: category.name.lower())
    categories_payload = [
        TaxonomyCategoryPayload(
            name=category.name,
            icon=category.icon,
            color=category.color,
            is_default=category.is_default,
        )
        for category in categories
    ]

    category_names_by_id = {
        category.id: category.name for category in categories if category.id is not None
    }
    rules = session.exec(
        select(CategorizeRule).order_by(
            cast(Any, CategorizeRule.keyword),
            cast(Any, CategorizeRule.match_type),
            desc(cast(Any, CategorizeRule.priority)),
        )
    ).all()
    rules_payload = []
    for rule in rules:
        category_name = category_names_by_id.get(rule.category_id)
        if category_name is None:
            continue
        rules_payload.append(
            TaxonomyRulePayload(
                keyword=rule.keyword,
                match_type=rule.match_type,
                category_name=category_name,
                priority=rule.priority,
            )
        )

    return TaxonomyBundle(
        version=1,
        exported_at=datetime.now(timezone.utc).isoformat(),
        categories=categories_payload,
        rules=rules_payload,
    )


def _normalize_taxonomy_bundle(
    bundle: TaxonomyBundle,
) -> tuple[dict[str, TaxonomyCategoryPayload], list[TaxonomyRulePayload], bool]:
    categories_by_normalized_name: dict[str, TaxonomyCategoryPayload] = {}
    for category in bundle.categories:
        normalized_name = _normalize_name(category.name)
        if not normalized_name or normalized_name in categories_by_normalized_name:
            continue
        categories_by_normalized_name[normalized_name] = TaxonomyCategoryPayload(
            name=" ".join(category.name.strip().split()),
            icon=category.icon,
            color=category.color,
            is_default=category.is_default,
        )

    will_ensure_uncategorized = False
    uncategorized_normalized_name = _normalize_name(UNCATEGORIZED_NAME)
    if uncategorized_normalized_name not in categories_by_normalized_name:
        categories_by_normalized_name[uncategorized_normalized_name] = (
            TaxonomyCategoryPayload(
                name=UNCATEGORIZED_NAME,
                icon=UNCATEGORIZED_ICON,
                color=UNCATEGORIZED_COLOR,
                is_default=True,
            )
        )
        will_ensure_uncategorized = True

    normalized_rules: list[TaxonomyRulePayload] = []
    seen_rule_keys: set[tuple[str, str, str]] = set()
    for rule in bundle.rules:
        keyword = " ".join(rule.keyword.strip().split()).upper()
        category_name = " ".join(rule.category_name.strip().split())
        normalized_category_name = _normalize_name(category_name)
        if not keyword or not normalized_category_name:
            continue
        match_type = _normalize_match_type(rule.match_type)
        dedupe_key = (keyword, match_type, normalized_category_name)
        if dedupe_key in seen_rule_keys:
            continue
        seen_rule_keys.add(dedupe_key)
        normalized_rules.append(
            TaxonomyRulePayload(
                keyword=keyword,
                match_type=match_type,
                category_name=category_name,
                priority=rule.priority,
            )
        )

    return (
        categories_by_normalized_name,
        normalized_rules,
        will_ensure_uncategorized,
    )


def _compute_taxonomy_replace_preview(
    session: Session,
    bundle: TaxonomyBundle,
) -> tuple[
    TaxonomyReplacePreviewResponse,
    dict[str, TaxonomyCategoryPayload],
    list[TaxonomyRulePayload],
]:
    categories_by_normalized_name, normalized_rules, will_ensure_uncategorized = (
        _normalize_taxonomy_bundle(bundle)
    )

    existing_categories = session.exec(select(ProductCategory)).all()
    existing_category_names_by_id = {
        category.id: _normalize_name(category.name)
        for category in existing_categories
        if category.id is not None
    }
    existing_rules_count = session.exec(
        select(func.count(cast(Any, CategorizeRule.id)))
    ).one()
    items = session.exec(select(ReceiptItem)).all()

    remap_matched_items = 0
    fallback_uncategorized_items = 0
    incoming_category_names = set(categories_by_normalized_name.keys())
    for item in items:
        old_normalized_name = (
            existing_category_names_by_id.get(item.category_id)
            if item.category_id is not None
            else None
        )
        if old_normalized_name and old_normalized_name in incoming_category_names:
            remap_matched_items += 1
        else:
            fallback_uncategorized_items += 1

    skipped_rules_missing_category = 0
    for rule in normalized_rules:
        if _normalize_name(rule.category_name) not in categories_by_normalized_name:
            skipped_rules_missing_category += 1

    preview_response = TaxonomyReplacePreviewResponse(
        incoming_categories=len(bundle.categories),
        incoming_rules=len(bundle.rules),
        normalized_categories=len(categories_by_normalized_name),
        normalized_rules=len(normalized_rules),
        existing_categories=len(existing_categories),
        existing_rules=int(existing_rules_count),
        receipt_items_total=len(items),
        remap_matched_items=remap_matched_items,
        fallback_uncategorized_items=fallback_uncategorized_items,
        skipped_rules_missing_category=skipped_rules_missing_category,
        will_ensure_uncategorized=will_ensure_uncategorized,
    )
    return preview_response, categories_by_normalized_name, normalized_rules


def _create_taxonomy_backup(session: Session) -> TaxonomyBackup:
    bundle = _build_taxonomy_bundle(session)
    backup = TaxonomyBackup(
        bundle_json=json.dumps(bundle.model_dump(), ensure_ascii=False),
        categories_count=len(bundle.categories),
        rules_count=len(bundle.rules),
    )
    session.add(backup)
    session.flush()
    return backup


def _run_re_categorize(
    session: Session,
    override_manual: bool,
    apply_changes: bool,
) -> tuple[ReCategorizeResponse, dict[tuple[int | None, int | None], int]]:
    items = session.exec(select(ReceiptItem).order_by(cast(Any, ReceiptItem.id))).all()
    categorizer = Categorizer(session)

    total_items = len(items)
    processed_items = 0
    updated_items = 0
    unchanged_items = 0
    skipped_manual_items = 0
    overridden_manual_items = 0
    categorized_items = 0
    uncategorized_items = 0
    change_counts: dict[tuple[int | None, int | None], int] = {}

    for item in items:
        was_manual = item.is_manual_assignment
        if was_manual and not override_manual:
            skipped_manual_items += 1
            continue

        previous_category_id = item.category_id
        category_id, confidence, method, _, _, _ = categorizer.categorize(item.raw_name)

        if was_manual and override_manual:
            overridden_manual_items += 1

        if previous_category_id != category_id:
            updated_items += 1
            pair = (previous_category_id, category_id)
            change_counts[pair] = change_counts.get(pair, 0) + 1
        else:
            unchanged_items += 1

        if category_id is None:
            uncategorized_items += 1
        else:
            categorized_items += 1

        processed_items += 1

        if apply_changes:
            item.category_id = category_id
            item.confidence = confidence
            item.auto_categorized = method != "none"
            if was_manual and override_manual:
                item.is_manual_assignment = False
            session.add(item)

    if apply_changes:
        session.commit()

    return (
        ReCategorizeResponse(
            total_items=total_items,
            processed_items=processed_items,
            updated_items=updated_items,
            unchanged_items=unchanged_items,
            skipped_manual_items=skipped_manual_items,
            overridden_manual_items=overridden_manual_items,
            categorized_items=categorized_items,
            uncategorized_items=uncategorized_items,
        ),
        change_counts,
    )


@router.get("/", response_model=list[RuleResponse])
def list_rules(
    category_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[RuleResponse]:
    """List all categorization rules, optionally filtered by category."""
    query = select(CategorizeRule)
    if category_id is not None:
        query = query.where(CategorizeRule.category_id == category_id)
    query = query.order_by(
        cast(Any, CategorizeRule.keyword),
        desc(cast(Any, CategorizeRule.priority)),
        cast(Any, CategorizeRule.match_type),
    )

    rules = session.exec(query).all()
    result = []
    for rule in rules:
        cat = session.get(ProductCategory, rule.category_id)
        result.append(
            RuleResponse(
                id=cast(int, rule.id),
                keyword=rule.keyword,
                match_type=rule.match_type,
                category_id=rule.category_id,
                category_name=cat.name if cat else "Unknown",
                priority=rule.priority,
            )
        )
    return result


@router.get("/taxonomy/export", response_model=TaxonomyBundle)
def export_taxonomy(session: Session = Depends(get_session)) -> TaxonomyBundle:
    return _build_taxonomy_bundle(session)


@router.get("/taxonomy/backups", response_model=list[TaxonomyBackupInfo])
def list_taxonomy_backups(
    session: Session = Depends(get_session),
) -> list[TaxonomyBackupInfo]:
    backups = session.exec(
        select(TaxonomyBackup).order_by(desc(cast(Any, TaxonomyBackup.created_at)))
    ).all()
    return [
        TaxonomyBackupInfo(
            id=cast(int, backup.id),
            created_at=backup.created_at.isoformat(),
            categories_count=backup.categories_count,
            rules_count=backup.rules_count,
        )
        for backup in backups
        if backup.id is not None
    ]


@router.get("/taxonomy/backups/{backup_id}", response_model=TaxonomyBundle)
def get_taxonomy_backup_bundle(
    backup_id: int,
    session: Session = Depends(get_session),
) -> TaxonomyBundle:
    backup = session.get(TaxonomyBackup, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Taxonomy backup not found")

    return TaxonomyBundle.model_validate(json.loads(backup.bundle_json))


@router.post(
    "/taxonomy/replace/preview",
    response_model=TaxonomyReplacePreviewResponse,
)
def preview_taxonomy_replace(
    body: TaxonomyBundle,
    session: Session = Depends(get_session),
) -> TaxonomyReplacePreviewResponse:
    preview_response, _, _ = _compute_taxonomy_replace_preview(session, body)
    return preview_response


@router.post(
    "/taxonomy/replace/apply",
    response_model=TaxonomyReplaceApplyResponse,
)
def apply_taxonomy_replace(
    body: TaxonomyBundle,
    session: Session = Depends(get_session),
) -> TaxonomyReplaceApplyResponse:
    preview_response, categories_by_normalized_name, normalized_rules = (
        _compute_taxonomy_replace_preview(session, body)
    )

    backup = _create_taxonomy_backup(session)

    existing_categories = session.exec(select(ProductCategory)).all()
    existing_category_names_by_id = {
        category.id: _normalize_name(category.name)
        for category in existing_categories
        if category.id is not None
    }
    items = session.exec(select(ReceiptItem).order_by(cast(Any, ReceiptItem.id))).all()
    old_item_category_name_by_id = {
        item.id: (
            existing_category_names_by_id.get(item.category_id)
            if item.category_id is not None
            else None
        )
        for item in items
        if item.id is not None
    }

    existing_rules = session.exec(select(CategorizeRule)).all()
    for rule in existing_rules:
        session.delete(rule)

    for item in items:
        item.category_id = None
        session.add(item)

    for category in existing_categories:
        session.delete(category)
    session.flush()

    category_ids_by_normalized_name: dict[str, int] = {}
    ordered_categories = sorted(
        categories_by_normalized_name.items(), key=lambda item: item[1].name.lower()
    )
    for normalized_name, category_payload in ordered_categories:
        category = ProductCategory(
            name=category_payload.name,
            icon=category_payload.icon,
            color=category_payload.color,
            is_default=category_payload.is_default,
        )
        session.add(category)
        session.flush()
        if category.id is not None:
            category_ids_by_normalized_name[normalized_name] = category.id

    uncategorized_id = category_ids_by_normalized_name[
        _normalize_name(UNCATEGORIZED_NAME)
    ]
    for item in items:
        old_category_name = (
            old_item_category_name_by_id.get(item.id) if item.id is not None else None
        )
        mapped_category_id = (
            category_ids_by_normalized_name.get(old_category_name)
            if old_category_name is not None
            else None
        )
        item.category_id = mapped_category_id or uncategorized_id
        session.add(item)

    for rule in normalized_rules:
        normalized_category_name = _normalize_name(rule.category_name)
        category_id = category_ids_by_normalized_name.get(normalized_category_name)
        if category_id is None:
            continue
        session.add(
            CategorizeRule(
                keyword=rule.keyword,
                match_type=rule.match_type,
                category_id=category_id,
                priority=rule.priority,
            )
        )

    session.commit()

    return TaxonomyReplaceApplyResponse(
        **preview_response.model_dump(),
        backup_id=cast(int, backup.id),
    )


@router.post("/", status_code=201, response_model=RuleResponse)
def create_rule(
    body: RuleCreate,
    session: Session = Depends(get_session),
) -> RuleResponse:
    """Create a new categorization rule."""
    # Validate category exists
    cat = session.get(ProductCategory, body.category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check for duplicate keyword + match_type
    existing = session.exec(
        select(CategorizeRule).where(
            CategorizeRule.keyword == body.keyword,
            CategorizeRule.match_type == body.match_type,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Rule for '{body.keyword}' ({body.match_type}) already exists",
        )

    rule = CategorizeRule(
        keyword=body.keyword.upper(),
        match_type=body.match_type,
        category_id=body.category_id,
        priority=body.priority,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)

    return RuleResponse(
        id=cast(int, rule.id),
        keyword=rule.keyword,
        match_type=rule.match_type,
        category_id=rule.category_id,
        category_name=cat.name,
        priority=rule.priority,
    )


@router.delete("/all")
def delete_all_rules(session: Session = Depends(get_session)) -> dict[str, int]:
    """Delete all categorization rules and return deleted count."""
    rules = session.exec(select(CategorizeRule)).all()
    deleted = len(rules)
    for rule in rules:
        session.delete(rule)
    session.commit()
    return {"deleted": deleted}


@router.patch("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: int,
    body: RuleUpdate,
    session: Session = Depends(get_session),
) -> RuleResponse:
    """Update a categorization rule."""
    rule = session.get(CategorizeRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.keyword is not None:
        rule.keyword = body.keyword.upper()
    if body.match_type is not None:
        rule.match_type = body.match_type
    if body.category_id is not None:
        cat = session.get(ProductCategory, body.category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        rule.category_id = body.category_id
    if body.priority is not None:
        rule.priority = body.priority

    session.add(rule)
    session.commit()
    session.refresh(rule)

    cat = session.get(ProductCategory, rule.category_id)
    return RuleResponse(
        id=cast(int, rule.id),
        keyword=rule.keyword,
        match_type=rule.match_type,
        category_id=rule.category_id,
        category_name=cat.name if cat else "Unknown",
        priority=rule.priority,
    )


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    session: Session = Depends(get_session),
) -> None:
    """Delete a categorization rule."""
    rule = session.get(CategorizeRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()


@router.post("/re-categorize", response_model=ReCategorizeResponse)
def re_categorize_items(
    body: ReCategorizeRequest,
    session: Session = Depends(get_session),
) -> ReCategorizeResponse:
    """Re-run categorization for all stored receipt items."""
    response, _ = _run_re_categorize(
        session=session,
        override_manual=body.override_manual,
        apply_changes=True,
    )
    return response


@router.post("/re-categorize/preview", response_model=ReCategorizePreviewResponse)
def preview_re_categorize_items(
    body: ReCategorizeRequest,
    session: Session = Depends(get_session),
) -> ReCategorizePreviewResponse:
    """Dry-run re-categorization and return grouped category changes."""
    response, change_counts = _run_re_categorize(
        session=session,
        override_manual=body.override_manual,
        apply_changes=False,
    )

    categories = session.exec(select(ProductCategory)).all()
    category_names_by_id = {
        category.id: category.name for category in categories if category.id is not None
    }

    changes = [
        ReCategorizeChange(
            from_category_id=from_category_id,
            from_category_name=_resolve_category_name(
                from_category_id, category_names_by_id
            ),
            to_category_id=to_category_id,
            to_category_name=_resolve_category_name(
                to_category_id, category_names_by_id
            ),
            item_count=item_count,
        )
        for (from_category_id, to_category_id), item_count in change_counts.items()
    ]
    changes.sort(
        key=lambda change: (
            -change.item_count,
            change.from_category_name.lower(),
            change.to_category_name.lower(),
        )
    )

    return ReCategorizePreviewResponse(
        **response.model_dump(),
        changes=changes,
    )
