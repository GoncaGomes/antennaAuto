from __future__ import annotations

from typing import Any

import pytest

from mvp.schemas.extraction_spec import (
    AntennaArchitectureSpecMvpV2,
    validate_semantic_bindings,
    validate_spec_payload,
)
from mvp.semantic_roles import classify_parameter_role


def make_valid_payload() -> dict[str, Any]:
    return {
        "schema_name": "antenna_architecture_spec_mvp_v2",
        "schema_version": "2.0",
        "document_context": {
            "run_id": "run_20260403T000000000000Z",
            "original_filename": "article.pdf",
            "page_count": 10,
        },
        "classification": {
            "primary_family": "microstrip_patch",
            "topology_tags": ["rectangular_patch"],
            "status": "extracted",
            "confidence": 0.88,
            "evidence_ids": ["chunk:chunk_001"],
        },
        "units": {
            "length": {"status": "extracted", "value": "mm", "evidence_ids": ["table:table_001"]},
            "frequency": {"status": "extracted", "value": "GHz", "evidence_ids": ["chunk:chunk_002"]},
            "impedance": {"status": "assumed_local_origin", "value": "ohm", "evidence_ids": ["chunk:chunk_003"]},
        },
        "parameters": [
            {
                "param_id": "param_patch_length",
                "symbol": "L",
                "semantic_name": "patch_length",
                "status": "extracted",
                "value": "5.3",
                "unit": "mm",
                "evidence_ids": ["table:table_001"],
            }
        ],
        "materials": [
            {
                "material_id": "material_substrate",
                "name": "Rogers RT5880",
                "category": "dielectric",
                "roles": ["substrate"],
                "status": "extracted",
                "evidence_ids": ["chunk:chunk_002"],
            },
            {
                "material_id": "material_conductor",
                "name": "copper",
                "category": "conductor",
                "roles": ["patch", "ground"],
                "status": "extracted",
                "evidence_ids": ["chunk:chunk_002"],
            },
        ],
        "layers": [
            {
                "layer_id": "layer_substrate",
                "role": "substrate",
                "material_ref": "material_substrate",
                "thickness": {"status": "missing", "evidence_ids": []},
                "z_order": 1,
                "evidence_ids": ["chunk:chunk_002"],
            },
            {
                "layer_id": "layer_patch",
                "role": "radiator",
                "material_ref": "material_conductor",
                "thickness": {
                    "status": "assumed_local_origin",
                    "value": "standard copper cladding",
                    "evidence_ids": ["chunk:chunk_003"],
                },
                "z_order": 2,
                "evidence_ids": ["chunk:chunk_003"],
            },
        ],
        "entities": [
            {
                "entity_id": "entity_patch",
                "entity_type": "patch",
                "role": "radiator",
                "layer_ref": "layer_patch",
                "geometry": {
                    "shape_mode": "rectangular",
                    "dimensions": [
                        {
                            "name": "length",
                            "status": "extracted",
                            "param_ref": "param_patch_length",
                            "evidence_ids": ["table:table_001"],
                        }
                    ],
                    "outline_points": [],
                },
                "placement": {"status": "missing"},
                "evidence_ids": ["table:table_001"],
            }
        ],
        "feeds": [
            {
                "feed_id": "feed_main",
                "feed_family": "microstrip",
                "matching_style": "inset",
                "driven_entity_ref": "entity_patch",
                "reference_impedance": {
                    "status": "assumed_local_origin",
                    "value": "50",
                    "unit": "ohm",
                    "evidence_ids": ["chunk:chunk_003"],
                },
                "port_type": {"status": "missing"},
                "evidence_ids": ["chunk:chunk_003"],
            }
        ],
        "instances": [],
        "quality": {
            "build_readiness": "partial",
            "missing_required_for_build": ["explicit placement anchor"],
            "ambiguities": ["patch width is not explicitly grounded in the retrieved evidence set"],
            "confidence": 0.66,
        },
        "evidence_used": [
            "chunk:chunk_001",
            "chunk:chunk_002",
            "chunk:chunk_003",
            "table:table_001",
        ],
    }


def test_schema_validation_and_clean_dump() -> None:
    spec = validate_spec_payload(make_valid_payload())

    assert isinstance(spec, AntennaArchitectureSpecMvpV2)
    clean = spec.to_clean_dict()
    assert clean["schema_name"] == "antenna_architecture_spec_mvp_v2"
    assert clean["feeds"][0]["feed_family"] == "microstrip"
    assert not _contains_none(clean)


def test_schema_rejects_bad_internal_reference() -> None:
    payload = make_valid_payload()
    payload["layers"][0]["material_ref"] = "material_unknown"

    with pytest.raises(Exception):
        validate_spec_payload(payload)


def test_schema_rejects_missing_evidence_used_subset() -> None:
    payload = make_valid_payload()
    payload["evidence_used"] = ["chunk:chunk_001"]

    with pytest.raises(Exception):
        validate_spec_payload(payload)


def test_semantic_role_classifier_distinguishes_structural_and_global_parameters() -> None:
    assert classify_parameter_role("patch_length", "Lpat", "mm").role == "entity_geometry"
    assert classify_parameter_role("substrate_thickness", "h", "mm").role == "layer_property"
    assert classify_parameter_role("feed_line_width", "Wf", "mm").role == "feed_property"
    assert classify_parameter_role("resonant_frequency", "f0", "GHz").role == "global_metric"


def test_semantic_binding_validation_rejects_orphan_patch_parameter() -> None:
    payload = make_valid_payload()
    payload["entities"][0]["geometry"]["dimensions"] = []

    spec = validate_spec_payload(payload)

    with pytest.raises(ValueError):
        validate_semantic_bindings(spec)


def _contains_none(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(_contains_none(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_none(item) for item in value)
    return False
