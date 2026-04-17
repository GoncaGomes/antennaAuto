from __future__ import annotations

import json
import re
from typing import Any

from ...prompts import load_prompt_text
from ...utils import text_excerpt

STATUS_VALUES = ["extracted", "partially_extracted", "missing", "assumed_local_origin"]
DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK: dict[str, int] = {
    "classification": 2,
    "materials": 2,
    "quality": 2,
    "entities": 3,
    "feeds": 3,
    "layers": 3,
    "parameters": 4,
}
DEFAULT_PROMPT_EXCERPT_CHARS = 280
DEFAULT_PROMPT_CHAR_BUDGET = 40_000
CITATION_PATTERN = re.compile(r"\[[0-9,\-\s]+\]")

SYSTEM_PROMPT = load_prompt_text("legacy_direct_system.md")


class PromptBudgetError(ValueError):
    def __init__(self, message: str, budget: dict[str, Any]) -> None:
        super().__init__(message)
        self.budget = budget


def prepare_prompt_evidence(
    run_context: dict[str, Any],
    evidence_by_block: dict[str, list[dict[str, Any]]],
    *,
    max_items_per_block: int | dict[str, int] = DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK,
    excerpt_char_limit: int = DEFAULT_PROMPT_EXCERPT_CHARS,
    max_prompt_chars: int = DEFAULT_PROMPT_CHAR_BUDGET,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    block_caps = _resolve_block_caps(evidence_by_block, max_items_per_block)
    compact_blocks = {
        block: _compact_block_records(
            block,
            records,
            max_items_per_block=block_caps[block],
            excerpt_char_limit=excerpt_char_limit,
        )
        for block, records in evidence_by_block.items()
    }
    trimmed_for_budget = 0
    prompt_chars = _estimate_prompt_chars(run_context, compact_blocks)

    while prompt_chars > max_prompt_chars:
        if not _trim_lowest_priority_item(compact_blocks):
            budget = _build_prompt_budget(
                evidence_by_block,
                compact_blocks,
                max_items_per_block=block_caps,
                excerpt_char_limit=excerpt_char_limit,
                max_prompt_chars=max_prompt_chars,
                prompt_chars=prompt_chars,
                trimmed_for_budget=trimmed_for_budget,
                within_budget=False,
            )
            raise PromptBudgetError(
                f"Extraction prompt exceeds budget before model call: {prompt_chars} chars > {max_prompt_chars}",
                budget,
            )
        trimmed_for_budget += 1
        prompt_chars = _estimate_prompt_chars(run_context, compact_blocks)

    budget = _build_prompt_budget(
        evidence_by_block,
        compact_blocks,
        max_items_per_block=block_caps,
        excerpt_char_limit=excerpt_char_limit,
        max_prompt_chars=max_prompt_chars,
        prompt_chars=prompt_chars,
        trimmed_for_budget=trimmed_for_budget,
        within_budget=True,
    )
    return compact_blocks, budget


def build_extraction_messages(
    run_context: dict[str, Any],
    evidence_by_block: dict[str, list[dict[str, Any]]],
    interpretation_note: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    lines = [
        "Build a valid antenna_architecture_spec_mvp_v2 object.",
        "",
        "Required top-level keys:",
        "- schema_name",
        "- schema_version",
        "- document_context",
        "- classification",
        "- units",
        "- parameters",
        "- materials",
        "- layers",
        "- entities",
        "- feeds",
        "- instances",
        "- quality",
        "- evidence_used",
        "",
        "Status values:",
        f"- {', '.join(STATUS_VALUES)}",
        "",
        "Document context:",
        _json_block(run_context),
    ]
    if interpretation_note:
        lines.extend(["", "Interpretation guidance (advisory, not ground truth):", _json_block(interpretation_note)])
    lines.extend(["", "Retrieved evidence by block:", _json_block(evidence_by_block)])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]


def build_repair_messages(
    run_context: dict[str, Any],
    evidence_by_block: dict[str, list[dict[str, Any]]],
    invalid_payload: dict[str, Any],
    validation_errors: list[dict[str, Any]],
) -> list[dict[str, str]]:
    user_prompt = "\n".join(
        [
            "Repair the JSON so it validates as antenna_architecture_spec_mvp_v2.",
            "Do not add unsupported facts.",
            "Use only the provided evidence IDs.",
            "",
            "Document context:",
            _json_block(run_context),
            "",
            "Retrieved evidence by block:",
            _json_block(evidence_by_block),
            "",
            "Previous invalid JSON:",
            _json_block(invalid_payload),
            "",
            "Validation errors:",
            _json_block(validation_errors),
        ]
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _json_block(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _compact_block_records(
    block: str,
    records: list[dict[str, Any]],
    *,
    max_items_per_block: int,
    excerpt_char_limit: int,
) -> list[dict[str, Any]]:
    compact_records: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    for record in sorted(records, key=lambda item: _record_sort_key(block, item)):
        compact = _compact_prompt_record(block, record, excerpt_char_limit=excerpt_char_limit)
        signature = _dedupe_signature(compact)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        compact_records.append(compact)
        if len(compact_records) >= max_items_per_block:
            break
    return compact_records


def _record_sort_key(block: str, record: dict[str, Any]) -> tuple[float, float, int, str]:
    priority = _prompt_priority_score(block, record)
    score = record.get("score")
    page = record.get("page_number")
    return (
        -priority,
        -(float(score) if isinstance(score, (int, float)) else 0.0),
        page if isinstance(page, int) else 10_000,
        record["evidence_id"],
    )


def _compact_prompt_record(block: str, record: dict[str, Any], *, excerpt_char_limit: int) -> dict[str, Any]:
    compact = {
        "evidence_id": record["evidence_id"],
        "block": block,
        "type": record.get("source_type", ""),
        "excerpt": _build_excerpt_for_block(block, record, excerpt_char_limit=excerpt_char_limit),
    }
    if record.get("page_number") is not None:
        compact["page"] = record["page_number"]
    if isinstance(record.get("score"), (int, float)):
        compact["score"] = round(float(record["score"]), 6)
    title = _extract_title(record)
    if title:
        compact["title"] = title
    return compact


def _build_excerpt_for_block(block: str, record: dict[str, Any], *, excerpt_char_limit: int) -> str:
    source_type = record.get("source_type", "")
    payload = record.get("source_payload") or {}
    if source_type == "table":
        parts: list[str] = []
        caption = text_excerpt(payload.get("caption", ""), limit=140)
        if caption:
            parts.append(caption)
        rows = payload.get("rows", [])
        if isinstance(rows, list):
            row_lines = []
            row_limit = 8 if block == "parameters" else 5 if block in {"layers", "feeds"} else 4
            for row in rows[:row_limit]:
                if isinstance(row, list):
                    row_lines.append(" | ".join(str(cell).strip() for cell in row if str(cell).strip()))
            if row_lines:
                parts.append("; ".join(row_lines))
        table_limit = max(
            excerpt_char_limit,
            420 if block == "parameters" else 320 if block in {"layers", "feeds"} else excerpt_char_limit,
        )
        return text_excerpt(" ".join(parts), limit=table_limit)
    if source_type == "figure":
        parts = [
            text_excerpt(payload.get("caption", ""), limit=140),
            text_excerpt(payload.get("context", ""), limit=excerpt_char_limit),
        ]
        return text_excerpt(" ".join(part for part in parts if part), limit=excerpt_char_limit)
    if source_type == "section":
        parts = [
            text_excerpt(payload.get("title", ""), limit=120),
            text_excerpt(payload.get("text_excerpt", ""), limit=excerpt_char_limit),
        ]
        return text_excerpt(" ".join(part for part in parts if part), limit=excerpt_char_limit)
    for candidate in [
        record.get("snippet", ""),
        record.get("content", ""),
        payload.get("text", "") if isinstance(payload, dict) else "",
    ]:
        excerpt = text_excerpt(candidate, limit=excerpt_char_limit)
        if excerpt:
            return excerpt
    return ""


def _extract_title(record: dict[str, Any]) -> str:
    payload = record.get("source_payload") or {}
    for key in ("caption", "title"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return text_excerpt(value, limit=120)
    return ""


def _dedupe_signature(record: dict[str, Any]) -> str:
    title = _normalize_for_dedupe(record.get("title", ""))
    excerpt = _normalize_for_dedupe(record.get("excerpt", ""))
    page = str(record.get("page", ""))
    kind = str(record.get("type", ""))
    return "|".join([kind, page, title[:80], excerpt[:160]])


def _normalize_for_dedupe(value: str) -> str:
    return re.sub(r"\W+", " ", value.lower()).strip()


def _trim_lowest_priority_item(evidence_by_block: dict[str, list[dict[str, Any]]]) -> bool:
    candidates = [
        (len(records), records[-1].get("score", 0.0), block)
        for block, records in evidence_by_block.items()
        if len(records) > 1
    ]
    if not candidates:
        return False
    _, _, block = sorted(candidates, key=lambda item: (-item[0], item[1], item[2]))[0]
    evidence_by_block[block].pop()
    return True


def _estimate_prompt_chars(run_context: dict[str, Any], evidence_by_block: dict[str, list[dict[str, Any]]]) -> int:
    messages = build_extraction_messages(run_context, evidence_by_block)
    return sum(len(message.get("content", "")) for message in messages)


def _build_prompt_budget(
    retrieved_evidence_by_block: dict[str, list[dict[str, Any]]],
    prompt_evidence_by_block: dict[str, list[dict[str, Any]]],
    *,
    max_items_per_block: int | dict[str, int],
    excerpt_char_limit: int,
    max_prompt_chars: int,
    prompt_chars: int,
    trimmed_for_budget: int,
    within_budget: bool,
) -> dict[str, Any]:
    return {
        "retrieved_records": sum(len(records) for records in retrieved_evidence_by_block.values()),
        "prompt_records": sum(len(records) for records in prompt_evidence_by_block.values()),
        "retrieved_records_by_block": {
            block: len(records) for block, records in retrieved_evidence_by_block.items()
        },
        "prompt_records_by_block": {
            block: len(records) for block, records in prompt_evidence_by_block.items()
        },
        "max_items_per_block": max_items_per_block,
        "excerpt_char_limit": excerpt_char_limit,
        "max_prompt_chars": max_prompt_chars,
        "prompt_chars": prompt_chars,
        "trimmed_for_budget": trimmed_for_budget,
        "within_budget": within_budget,
    }


def _resolve_block_caps(
    evidence_by_block: dict[str, list[dict[str, Any]]],
    max_items_per_block: int | dict[str, int],
) -> dict[str, int]:
    if isinstance(max_items_per_block, int):
        return {block: max_items_per_block for block in evidence_by_block}
    caps = dict(DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK)
    caps.update(max_items_per_block)
    return {block: caps.get(block, 2) for block in evidence_by_block}


def _prompt_priority_score(block: str, record: dict[str, Any]) -> float:
    base = float(record.get("score", 0.0))
    text = _record_text(record)
    lowered = text.lower()
    page = record.get("page_number")
    source_type = str(record.get("source_type", ""))
    bonus = 0.0
    if isinstance(page, int) and page <= 2:
        bonus += 0.1
    if block == "classification":
        if any(
            term in lowered
            for term in ["abstract", "keywords", "proposed design", "final design", "optimized design", "configuration"]
        ):
            bonus += 0.45
        if any(term in lowered for term in ["antenna type", "antenna geometry", "radiating element", "design description"]):
            bonus += 0.2
        if any(term in lowered for term in ["title", "keywords", "abstract"]):
            bonus += 0.1
        if source_type in {"section", "figure", "table"}:
            bonus += 0.08
        if any(term in lowered for term in ["references", "crossref", "pubmed", "related work", "comparison table", "literature work"]):
            bonus -= 0.7
        if _citation_density(lowered) >= 3:
            bonus -= 0.45
        if isinstance(page, int) and page >= 5:
            bonus -= 0.08
    if block == "parameters":
        if source_type == "table":
            bonus += 0.55
        if any(term in lowered for term in ["dimension", "dimensions", "parameter", "geometrical", "length", "width", "radius", "diameter", "thickness", "height", "size"]):
            bonus += 0.25
        if any(term in lowered for term in ["comparison table", "literature work", "reference"]):
            bonus -= 0.45
    if block == "layers":
        if source_type == "table":
            bonus += 0.2
        if any(term in lowered for term in ["layer", "stack", "substrate", "dielectric", "conductor", "metal", "ground plane", "thickness"]):
            bonus += 0.25
        if _citation_density(lowered) >= 3:
            bonus -= 0.3
    if block == "feeds":
        if any(term in lowered for term in ["feed", "feeding", "input port", "connector", "port", "input impedance", "impedance", "location"]):
            bonus += 0.3
        if _citation_density(lowered) >= 3:
            bonus -= 0.3
    if block == "entities":
        if any(term in lowered for term in ["geometry", "radiating element", "slot", "ground plane", "element", "structure", "rectangular", "triangular", "circular"]):
            bonus += 0.28
        if source_type == "figure":
            bonus += 0.12
        if _citation_density(lowered) >= 3:
            bonus -= 0.2
    return base + bonus


def _record_text(record: dict[str, Any]) -> str:
    payload = record.get("source_payload") or {}
    parts = [record.get("snippet", ""), record.get("content", "")]
    for key in ("title", "caption", "context", "text", "text_excerpt"):
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
    return " ".join(part for part in parts if part)


def _citation_density(text: str) -> int:
    return len(CITATION_PATTERN.findall(text))
