from __future__ import annotations

import json
from typing import Any

from ..prompts import load_prompt_text

CANONICALIZATION_SYSTEM_PROMPT = load_prompt_text("canonicalization_system.md")
SCHEMA_CONSTRUCTION_SYSTEM_PROMPT = load_prompt_text("schema_construction_system.md")


def build_canonicalization_input(
    run_context: dict[str, Any],
    evidence_by_block: dict[str, list[dict[str, Any]]],
    phase1_guidance: dict[str, Any] | None = None,
) -> dict[str, str]:
    payload = {
        "run_context": run_context,
        "phase1_guidance": _compact_phase1_guidance_for_llm2(phase1_guidance),
        "retrieved_evidence_by_block": _compact_evidence_for_llm2(evidence_by_block),
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


def _json_pretty_block(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2)


def _compact_evidence_for_llm2(evidence_by_block: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    compact: dict[str, list[dict[str, Any]]] = {}
    for block, records in evidence_by_block.items():
        compact_records: list[dict[str, Any]] = []
        for record in records:
            compact_records.append(
                {
                    "evidence_id": record.get("evidence_id"),
                    "source_type": record.get("source_type"),
                    "source_id": record.get("source_id"),
                    "page_number": record.get("page_number"),
                    "content": record.get("content", ""),
                    "source_payload": record.get("source_payload", {}),
                }
            )
        compact[block] = compact_records
    return compact


def _compact_phase1_guidance_for_llm2(phase1_guidance: dict[str, Any] | None) -> dict[str, Any] | None:
    if not phase1_guidance:
        return None
    return {
        "has_multiple_variants": phase1_guidance.get("has_multiple_variants"),
        "has_final_design_signal": phase1_guidance.get("has_final_design_signal"),
        "search_queries": phase1_guidance.get("search_queries", []),
        "open_uncertainties": phase1_guidance.get("open_uncertainties", []),
    }
