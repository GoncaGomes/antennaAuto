from __future__ import annotations

from pathlib import Path

from mvp.extraction.legacy.prompting import (
    DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK,
    build_extraction_messages,
    build_repair_messages,
    prepare_prompt_evidence,
)
from mvp.extraction.prompting import build_canonicalization_input, build_schema_construction_input


def test_prompt_builder_includes_extraction_rules() -> None:
    messages = build_extraction_messages(
        {"run_id": "run_1", "original_filename": "article.pdf", "page_count": 5},
        {"materials": [{"evidence_id": "chunk:chunk_001", "content": "Rogers RT5880 substrate"}]},
        interpretation_note={
            "has_multiple_variants": True,
            "has_final_design_signal": True,
            "open_uncertainties": ["final design selection remains ambiguous"],
        },
    )

    assert len(messages) == 2
    assert "Use only the evidence provided in the prompt" in messages[0]["content"]
    assert "reasoning_scratchpad" in messages[0]["content"]
    assert "Interpretation guidance (advisory, not ground truth)" in messages[1]["content"]
    assert "Retrieved evidence by block" in messages[1]["content"]
    prompt_path = Path(__file__).resolve().parents[1] / "src" / "mvp" / "prompts" / "legacy_direct_system.md"
    assert messages[0]["content"] == prompt_path.read_text(encoding="utf-8").strip()


def test_repair_prompt_includes_validation_errors() -> None:
    messages = build_repair_messages(
        {"run_id": "run_1", "original_filename": "article.pdf", "page_count": 5},
        {"materials": [{"evidence_id": "chunk:chunk_001", "content": "Rogers RT5880 substrate"}]},
        {"schema_name": "bad_payload"},
        [{"loc": ["evidence_used"], "msg": "missing"}],
    )

    assert "Repair the JSON" in messages[1]["content"]
    assert "Validation errors" in messages[1]["content"]


def test_prepare_prompt_evidence_compacts_and_caps_records() -> None:
    compact, budget = prepare_prompt_evidence(
        {"run_id": "run_1", "original_filename": "article.pdf", "page_count": 5},
        {
            "materials": [
                {
                    "evidence_id": "chunk:chunk_001",
                    "source_type": "chunk",
                    "page_number": 2,
                    "score": 0.9,
                    "snippet": "Rogers RT5880 substrate and copper ground are used.",
                    "content": "Rogers RT5880 substrate and copper ground are used.",
                    "source_payload": {"text": "Rogers RT5880 substrate and copper ground are used."},
                },
                {
                    "evidence_id": "chunk:chunk_002",
                    "source_type": "chunk",
                    "page_number": 2,
                    "score": 0.85,
                    "snippet": "Rogers RT5880 substrate and copper ground are used.",
                    "content": "Rogers RT5880 substrate and copper ground are used.",
                    "source_payload": {"text": "Rogers RT5880 substrate and copper ground are used."},
                },
                {
                    "evidence_id": "figure:fig_001",
                    "source_type": "figure",
                    "page_number": 2,
                    "score": 0.7,
                    "snippet": "Figure context snippet",
                    "content": "Figure context snippet",
                    "source_payload": {
                        "figure_id": "fig_001",
                        "caption": "Figure 1. Antenna geometry",
                        "context": "Rogers RT5880 is used as the substrate.",
                    },
                },
            ]
        },
        max_items_per_block=2,
    )

    assert budget["prompt_records_by_block"]["materials"] == 2
    assert compact["materials"][0]["evidence_id"] == "chunk:chunk_001"
    assert "source_payload" not in compact["materials"][0]


def test_canonicalization_input_preserves_structured_table_rows() -> None:
    payload = build_canonicalization_input(
        {"run_id": "run_1", "original_filename": "article.pdf", "page_count": 2},
        {
            "parameters": [
                {
                    "evidence_id": "table:table_001",
                    "source_type": "table",
                    "page_number": 2,
                    "score": 0.91,
                    "snippet": "",
                    "content": "",
                    "source_payload": {
                        "table_id": "table_001",
                        "caption": "Table 1. Dimensions of proposed antenna",
                        "rows": [["Step", "L", "W"], ["Step 1", "5.1", "4.7"], ["Step 4", "5.3", "4.8"]],
                        "structured": True,
                    },
                }
            ]
        },
        phase1_guidance={"has_multiple_variants": True, "search_queries": [{"query_text": "final selected design"}]},
    )

    assert "Phase 1 guidance" in payload["input_text"]
    assert "Step 4" in payload["input_text"]
    assert "rows" in payload["input_text"]
    assert "final selected design" in payload["input_text"]
    prompt_path = Path(__file__).resolve().parents[1] / "src" / "mvp" / "prompts" / "canonicalization_system.md"
    assert payload["instructions"] == prompt_path.read_text(encoding="utf-8").strip()


def test_schema_construction_input_includes_canonical_record_and_linked_evidence() -> None:
    payload = build_schema_construction_input(
        {"run_id": "run_1", "original_filename": "article.pdf", "page_count": 2},
        {
            "selected_design_summary": "Rectangular patch",
            "selected_design_rationale": "Main design chosen from proposed geometry evidence.",
            "has_multiple_variants": False,
            "dominant_evidence_ids": ["table:table_001"],
            "secondary_evidence_ids": [],
            "identified_antennas": ["Rectangular patch with inset feed"],
            "proposed_final_antenna_rationale": "Only one proposed antenna appears in the record.",
            "final_design": {
                "classification": {"primary_family": "microstrip_patch", "topology_tags": ["rectangular_patch"]},
                "patch": None,
                "feed": None,
                "ground": None,
                "slots": [],
                "materials": [],
                "layers": [],
                "performance_targets": [],
                "extra_parameters": [],
            },
            "design_evolution_notes": [],
            "unresolved_conflicts": [],
        },
        [{"evidence_id": "table:table_001", "source_type": "table", "source_payload": {"rows": [["L", "5.3"]]}}],
    )

    assert "canonical_design_record" in payload["input_text"]
    assert "linked_evidence_records" in payload["input_text"]
    assert "table:table_001" in payload["input_text"]
    assert "run_context" in payload["input_text"]
    prompt_path = Path(__file__).resolve().parents[1] / "src" / "mvp" / "prompts" / "schema_construction_system.md"
    assert payload["instructions"] == prompt_path.read_text(encoding="utf-8").strip()


def test_prepare_prompt_evidence_uses_block_specific_caps() -> None:
    compact, budget = prepare_prompt_evidence(
        {"run_id": "run_1", "original_filename": "article.pdf", "page_count": 5},
        {
            "parameters": [
                {
                    "evidence_id": f"table:table_00{index}",
                    "source_type": "table",
                    "page_number": 2,
                    "score": 0.9 - index * 0.01,
                    "snippet": "",
                    "content": "",
                    "source_payload": {
                        "table_id": f"table_00{index}",
                        "caption": "Table 1. Dimensions of proposed antenna",
                        "rows": [["Parameter", "Value(mm)"], [f"P{index}", f"{index}.0"]],
                    },
                }
                for index in range(1, 7)
            ],
        },
    )

    assert budget["max_items_per_block"]["parameters"] == DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK["parameters"]
    assert len(compact["parameters"]) == DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK["parameters"]
