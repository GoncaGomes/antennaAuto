from __future__ import annotations

import json
import re
from typing import Any

from ..utils import text_excerpt

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

SYSTEM_PROMPT = """You extract an antenna_architecture_spec_mvp_v2 JSON document from retrieved evidence.

Rules:
- Use only the evidence provided in the prompt.
- Prefer evidence describing the proposed antenna over references, comparisons, or cited prior work.
- For classification, prioritize title, abstract, proposed-design, geometry, and direct design-description evidence.
- Use only evidence IDs that appear in the provided evidence records.
- Do not invent geometry, parameters, materials, layers, feeds, ports, placements, or IDs.
- Preserve explicit design parameters and units from the provided evidence when they are directly available.
- Bind explicit physical dimensions to the appropriate object type when the evidence makes the target object clear.
- Do not leave extractable structural dimensions orphaned in the global parameters list when they belong to entity geometry or layer thickness.
- If a physical feed property can only be represented globally under the current schema, keep it evidence-grounded and do not invent unsupported numeric placement fields.
- Strict ID Formatting for Assumed Entities: If the schema requires a referenced entity or material but the specific name is omitted in the evidence, you may instantiate a generic placeholder with status `assumed_local_origin`, but every internal id MUST strictly match `^[a-z][a-z0-9_]*$`. Never use dotted or system-like ids such as `.default_conductor`. Use valid ids like `material_assumed_1`.
- Contextual Anchoring for Ambiguous Dimensions: If a table provides dimensional parameters with generic names (e.g., 'Length', 'Width', 'd', 'r') without explicitly naming the target entity, DO NOT guess based purely on the variable name, and DO NOT ignore them. You MUST use your internal reasoning_scratchpad to cross-reference the provided text chunks, figure captions, or table context to deduce which physical entity (e.g., radiator, slot, ground, feed) is described by those values. Bind the dimension to the correct entity's geometry based on this contextual evidence.
- Generic Shape Inference: If an entity has explicit extracted dimensions but the geometric shape name is omitted, do not leave the geometry object empty. Infer a generic `shape_mode` strictly from the dimensional evidence available. For example, `radius` supports `circular`, while `length` and `width` support `rectangular`. If the shape still cannot be inferred safely, use `unspecified_polygon`.
- Every microstrip feed line or feed structure MUST be represented as an entity with its own geometry if dimensions are provided.
- A ground plane MUST be represented as an entity if its dimensions are provided.
- Implicit Port/Connector Handling: If a port/connector is implicitly required to feed the antenna but omitted in the text, do not leave `port_type` missing. Use status `assumed_local_origin` with a generic value such as `generic_port`.
- Do not copy snippets or evidence text into the final JSON.
- Do not include an evidence_registry object.
- Use evidence_ids on fields and objects, and a flat evidence_used list at top level.
- Mark unknowns with explicit status values instead of guessing.
- Avoid mixing design variants; prefer the final, proposed, optimized, selected, or best-supported design described in the evidence.
- Do not infer raw visual geometry from figures; use only the provided figure caption/context evidence.
- Keep the result solver-agnostic.
- Do not include CST commands, simulation setup, or operations trees.
- Slots and notches must be represented as entities, not boolean operations.
- Return one JSON object only.
"""

CANONICALIZATION_SYSTEM_PROMPT = """You are the semantic canonicalization layer for scientific antenna extraction.

You are NOT building the final schema.

Your task is to read mixed retrieved evidence from one paper and produce a canonical design record for the dominant antenna design described by that paper.

Your goal is not to minimize content. Your goal is to resolve the design identity while preserving all structurally useful facts needed later for schema construction.

You must:
- identify the dominant antenna design target of the paper, if one exists
- distinguish dominant evidence from intermediate design steps, contextual discussion, comparison content, literature comparison, deployment context, and side remarks
- reconcile evidence across prose, tables, figures, and sections
- treat final parameter tables as potentially highly authoritative, but do not apply rigid hard-coded rules
- preserve evidence IDs
- preserve geometrically useful details even when they may later be awkward to map into the final schema
- avoid inventing missing geometry
- avoid copying all evidence blindly
- preserve unresolved ambiguity explicitly instead of guessing

Preserve, whenever supported:
- patch geometry
- slot/notch geometry
- feed geometry
- feed location / coordinates
- ground-plane geometry
- substrate and layer information
- material assignments
- operating targets
- performance metrics
- explicit conflicts between sources

When prose and table content disagree:
- do not resolve the conflict silently
- state which evidence appears more authoritative and why
- preserve the conflict if it is not fully resolved

When multiple design variants exist:
- identify which one is the dominant target of the paper
- mark others as intermediate or secondary
- do not let secondary variants overwrite the dominant design record

Important:
- do not output the final schema
- do not compress away useful structural facts
- do not omit canonical details just because they may be difficult to place later
- separate clearly:
  - resolved design facts
  - unresolved conflicts
  - missing information

Output only the canonical design record in the required structured format."""

SCHEMA_CONSTRUCTION_SYSTEM_PROMPT = """You are the final schema-construction layer for scientific antenna extraction.

You do NOT need to decide the dominant design from mixed raw evidence.
That decision has already been made upstream and is provided to you as a canonical design record.

Your task is to convert the canonical design record into the final schema: antenna_architecture_spec_mvp_v2.

Your primary goal is faithful transfer of canonical facts into the final schema.
Clean output matters, but fidelity matters more.

You must:
- preserve every canonical fact that the schema can represent
- preserve evidence IDs
- include every nested evidence_id again in the top-level evidence_used list
- use only valid internal ids matching `^[a-z][a-z0-9_]*$`
- never use colons, dots, spaces, or hyphens inside internal ids
- avoid inventing facts
- avoid duplicated parameters
- avoid noisy aliases
- keep unresolved ambiguity explicit rather than silently filling gaps
- represent the antenna architecture faithfully for downstream use

Critical rule:
Do NOT silently drop canonical geometric or feed details.

When a canonical fact maps directly to the schema:
- include it

When a canonical fact does not have a perfect one-to-one schema field:
- place it in the closest schema-compatible location that preserves meaning faithfully
- if it still cannot be represented cleanly, surface that loss explicitly in ambiguity, missing_required_for_build, or another schema-compatible uncertainty field
- never omit it silently just to keep the JSON cleaner

This applies especially to:
- feed coordinates
- feed geometry
- slot dimensions
- patch dimensions
- ground-plane dimensions
- layer thickness
- material assignments
- operating targets
- performance metrics

Only use facts supported by the canonical design record and linked evidence.
Do not semantically reinterpret discarded secondary evidence.
Do not create extra junk fields.
Do not create redundant parameter aliases unless required by the schema.

Important:
- cleanliness is secondary to faithful transfer
- omission is worse than explicit uncertainty
- when in doubt, preserve the fact and mark the uncertainty

Output only the structured schema result."""


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
        block: _compact_block_records(block, records, max_items_per_block=block_caps[block], excerpt_char_limit=excerpt_char_limit)
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


def build_canonicalization_input(
    run_context: dict[str, Any],
    evidence_by_block: dict[str, list[dict[str, Any]]],
    phase1_guidance: dict[str, Any] | None = None,
) -> dict[str, str]:
    payload = {
        "run_context": run_context,
        "phase1_guidance": _compact_phase1_guidance_for_llm2(phase1_guidance),
        "retrieved_evidence_by_block": evidence_by_block,
    }
    input_text = "\n".join(
        [
            "You are given:",
            "- Phase 1 guidance",
            "- retrieved evidence records from text, tables, figures, and sections",
            "- evidence IDs and metadata",
            "",
            "Build a compact canonical design record for the dominant antenna design in the paper.",
            "Do not output the final schema.",
            "Do not output explanations outside the structured result.",
            "",
            _json_pretty_block(payload),
        ]
    )
    return {"instructions": CANONICALIZATION_SYSTEM_PROMPT, "input_text": input_text}


def build_schema_construction_input(
    run_context: dict[str, Any],
    canonical_design_record: dict[str, Any],
    linked_evidence_records: list[dict[str, Any]],
) -> dict[str, str]:
    payload = {
        "run_context": run_context,
        "canonical_design_record": canonical_design_record,
        "linked_evidence_records": linked_evidence_records,
    }
    input_text = "\n".join(
        [
            "You are given:",
            "- a canonical design record for one antenna paper",
            "- linked evidence IDs and minimal supporting evidence context",
            "- the target schema definition antenna_architecture_spec_mvp_v2",
            "",
            "Produce antenna_architecture_spec_mvp_v2.",
            "Output only the structured schema result.",
            "",
            _json_pretty_block(payload),
        ]
    )
    return {"instructions": SCHEMA_CONSTRUCTION_SYSTEM_PROMPT, "input_text": input_text}


def _json_block(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _json_pretty_block(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2)


def _compact_phase1_guidance_for_llm2(phase1_guidance: dict[str, Any] | None) -> dict[str, Any] | None:
    if not phase1_guidance:
        return None
    return {
        "has_multiple_variants": phase1_guidance.get("has_multiple_variants"),
        "has_final_design_signal": phase1_guidance.get("has_final_design_signal"),
        "search_queries": phase1_guidance.get("search_queries", []),
        "open_uncertainties": phase1_guidance.get("open_uncertainties", []),
    }


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
        table_limit = max(excerpt_char_limit, 420 if block == "parameters" else 320 if block in {"layers", "feeds"} else excerpt_char_limit)
        return text_excerpt(" ".join(parts), limit=table_limit)
    if source_type == "figure":
        parts = [text_excerpt(payload.get("caption", ""), limit=140), text_excerpt(payload.get("context", ""), limit=excerpt_char_limit)]
        return text_excerpt(" ".join(part for part in parts if part), limit=excerpt_char_limit)
    if source_type == "section":
        parts = [text_excerpt(payload.get("title", ""), limit=120), text_excerpt(payload.get("text_excerpt", ""), limit=excerpt_char_limit)]
        return text_excerpt(" ".join(part for part in parts if part), limit=excerpt_char_limit)
    for candidate in [record.get("snippet", ""), record.get("content", ""), payload.get("text", "") if isinstance(payload, dict) else ""]:
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
    candidates = [(len(records), records[-1].get("score", 0.0), block) for block, records in evidence_by_block.items() if len(records) > 1]
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
        "retrieved_records_by_block": {block: len(records) for block, records in retrieved_evidence_by_block.items()},
        "prompt_records_by_block": {block: len(records) for block, records in prompt_evidence_by_block.items()},
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
        if any(term in lowered for term in ["abstract", "keywords", "proposed design", "final design", "optimized design", "configuration"]):
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
