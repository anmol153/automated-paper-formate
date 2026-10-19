"""Diff engine for comparing two RuleSet versions.

Produces a structured diff that highlights:
- Added, removed, or changed fields at the top-level and nested rule-group level.
- The diff is intended for display in a UI diff viewer (side-by-side or unified).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.models.rules import (
    AnonymisationRule,
    DecisionRule,
    FileTypeRule,
    PageRule,
    ParagraphRule,
    PublisherDetails,
    RuleSet,
    SectionRule,
    TypographyRule,
)
from pydantic import BaseModel

# ──────────────────────────────────────────────────────────────────────────────
# Top-level helpers
# ──────────────────────────────────────────────────────────────────────────────

def _model_diff(a: RuleSet, b: RuleSet) -> Dict[str, Any]:
    """Compute a structural diff between two RuleSet instances.

    Returns a dict with keys:
      - "added": fields present in b but not in a
      - "removed": fields present in a but not in b
      - "changed": dict of {field: (old_value, new_value)}
      - "unchanged": fields present in both with same value
    """
    def _extract(model: RuleSet) -> Dict[str, Any]:
        # Grab all model fields including those with defaults
        return {k: v for k, v in model.model_dump().items() if v is not None or k in type(model).model_fields}

    a_dict = _extract(a)
    b_dict = _extract(b)

    added: Dict[str, Any] = {}
    removed: Dict[str, Any] = {}
    changed: Dict[str, Tuple[Any, Any]] = {}
    unchanged: Dict[str, Any] = {}

    all_keys = set(a_dict.keys()) | set(b_dict.keys())

    for key in all_keys:
        a_val = a_dict.get(key)
        b_val = b_dict.get(key)

        if key not in a_dict:
            added[key] = b_val
        elif key not in b_dict:
            removed[key] = a_val
        elif a_val != b_val:
            # For nested models, recurse
            if isinstance(a_val, BaseModel) and isinstance(b_val, BaseModel):
                nested = _model_diff(a_val, b_val)
                if nested["changed"] or nested["added"] or nested["removed"]:
                    changed[key] = {
                        "old": _simplify(a_val),
                        "new": _simplify(b_val),
                        "details": nested,
                    }
                else:
                    unchanged[key] = _simplify(a_val)
            else:
                changed[key] = (a_val, b_val)
        else:
            unchanged[key] = a_val

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }


def _simplify(model: Any) -> Any:
    """Strip a model to a serialisable dict without deep nesting."""

    if hasattr(model, "model_dump"):
        d = model.model_dump()
        # Drop fields that are empty/default
        return {k: v for k, v in d.items() if v not in (None, {}, [])}
    if isinstance(model, dict):
        return {k: _simplify(v) for k, v in model.items()}
    return model


# ──────────────────────────────────────────────────────────────────────────────
# Group-level diffs (file_type, pages, sections, etc.)
# ──────────────────────────────────────────────────────────────────────────────

def diff_file_type(a: FileTypeRule, b: FileTypeRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_page(a: PageRule, b: PageRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_section(a: SectionRule, b: SectionRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_anonymisation(a: AnonymisationRule, b: AnonymisationRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_typography(a: TypographyRule, b: TypographyRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_paragraph(a: ParagraphRule, b: ParagraphRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_decision(a: DecisionRule, b: DecisionRule) -> Dict[str, Any]:
    return _model_diff(a, b)


def diff_publisher(a: PublisherDetails, b: PublisherDetails) -> Dict[str, Any]:
    return _model_diff(a, b)


# ──────────────────────────────────────────────────────────────────────────────
# High-level diff: two full RuleSets
# ──────────────────────────────────────────────────────────────────────────────

def diff_rulesets(
    old: RuleSet, new: RuleSet,
) -> Dict[str, Dict[str, Any]]:
    """Diff two complete RuleSets, grouped by rule category.

    Returns a dict with keys matching the RuleSet field names:
      file_type, pages, sections, anonymisation, typography, paragraph,
      decision, publisher — each value is a diff sub-dict (as produced by
      the per-group diff functions above).
    """
    result: Dict[str, Dict[str, Any]] = {}

    # Per-group diffs
    result["file_type"] = diff_file_type(old.file_type, new.file_type)
    result["pages"] = diff_page(old.pages, new.pages)
    result["sections"] = diff_section(old.sections, new.sections)
    result["anonymisation"] = diff_anonymisation(old.anonymisation, new.anonymisation)
    result["typography"] = diff_typography(old.typography, new.typography)
    result["paragraph"] = diff_paragraph(old.paragraph, new.paragraph)
    result["decision"] = diff_decision(old.decision, new.decision)
    result["publisher"] = diff_publisher(old.publisher, new.publisher)

    # Top-level meta
    top: Dict[str, Any] = {}
    for key in set(old.model_dump().keys()) | set(new.model_dump().keys()):
        av = getattr(old, key, None)
        bv = getattr(new, key, None)
        if av != bv:
            top[key] = (_simplify(av), _simplify(bv))
    result["_meta"] = top

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Human-readable summary (for UI tooltips / badges)
# ──────────────────────────────────────────────────────────────────────────────

def summary_diff(diff: Dict[str, Dict[str, Any]]) -> str:
    """Produce a one-line human summary of a RuleSet diff."""

    parts: List[str] = []

    # Count changed top-level fields
    meta = diff.get("_meta", {})
    if meta:
        changed_top = sum(1 for v in meta.values() if isinstance(v, tuple) and v[0] != v[1])
        if changed_top:
            parts.append(f"{changed_top} top-level rule changed")

    # Count changed groups
    group_counts: Dict[str, int] = {}
    for group, gdiff in diff.items():
        if group == "_meta":
            continue
        # Count leaf-level changes added+removed+changed
        added = sum(1 for v in gdiff.get("added", {}).values() if not isinstance(v, dict))
        removed = sum(1 for v in gdiff.get("removed", {}).values() if not isinstance(v, dict))
        changed = sum(1 for v in gdiff.get("changed", {}).values()
                      if not isinstance(v, dict) and (not isinstance(v, tuple) or v[0] != v[1]))
        total = added + removed + changed
        if total:
            group_counts[group] = total

    if group_counts:
        top3 = sorted(group_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
        group_str = ", ".join(f"{g}({c})" for g, c in top3)
        parts.append(f"groups: {group_str}")

    if not parts:
        return "No changes"

    return ". ".join(parts) + "."