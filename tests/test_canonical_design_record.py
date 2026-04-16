from __future__ import annotations

import pytest

from mvp.schemas.canonical_design_record import collect_canonical_evidence_ids, validate_canonical_design_record_payload


def make_payload() -> dict:
    return {
        "selected_design_summary": "Rectangular microstrip patch antenna with inset feed.",
        "selected_design_rationale": "The paper presents this design as the dominant proposed antenna.",
        "has_multiple_variants": True,
        "dominant_evidence_ids": ["table:table_001", "chunk:chunk_001"],
        "secondary_evidence_ids": ["chunk:chunk_002"],
        "final_design": {
            "classification": {
                "primary_family": "microstrip_patch",
                "topology_tags": ["rectangular_patch", "inset_feed"],
            },
            "patch": {
                "label": "main patch",
                "shape_mode": "rectangular",
                "dimensions": [{"name": "length", "value": "5.3", "unit": "mm"}],
                "evidence_ids": ["table:table_001"],
            },
            "feed": {
                "feed_family": "microstrip",
                "matching_style": "inset",
                "dimensions": [],
                "location": {"x": "1.0", "y": "0.5", "unit": "mm"},
                "evidence_ids": ["chunk:chunk_001"],
            },
            "ground": None,
            "slots": [],
            "materials": [],
            "layers": [],
            "performance_targets": [],
            "extra_parameters": [],
        },
        "design_evolution_notes": [
            {
                "label": "step_1",
                "description": "Initial radiator before inset-feed refinement.",
                "evidence_ids": ["chunk:chunk_002"],
            }
        ],
        "unresolved_conflicts": [
            {
                "topic": "patch length",
                "description": "Table and prose differ slightly.",
                "preferred_evidence_ids": ["table:table_001"],
                "conflicting_evidence_ids": ["chunk:chunk_002"],
                "status": "resolved",
            }
        ],
    }


def test_canonical_design_record_validation_round_trip() -> None:
    record = validate_canonical_design_record_payload(make_payload())
    clean = record.to_clean_dict()

    assert clean["selected_design_summary"].startswith("Rectangular")
    assert clean["final_design"]["patch"]["dimensions"][0]["unit"] == "mm"


def test_collect_canonical_evidence_ids_includes_top_level_and_conflict_lists() -> None:
    record = validate_canonical_design_record_payload(make_payload())
    evidence_ids = collect_canonical_evidence_ids(record)

    assert "table:table_001" in evidence_ids
    assert "chunk:chunk_001" in evidence_ids
    assert "chunk:chunk_002" in evidence_ids


def test_canonical_design_record_rejects_bad_evidence_id() -> None:
    payload = make_payload()
    payload["dominant_evidence_ids"] = ["bad-id"]

    with pytest.raises(Exception):
        validate_canonical_design_record_payload(payload)
