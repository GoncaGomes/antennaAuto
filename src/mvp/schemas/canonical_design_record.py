from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EVIDENCE_ID_PATTERN = re.compile(r"^[a-z_]+:[A-Za-z0-9_]+$")

ConflictStatus = Literal["resolved", "unresolved", "partially_resolved"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlainModel(StrictModel):
    pass


class EvidenceBoundModel(StrictModel):
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[str]) -> list[str]:
        cleaned = _dedupe_preserve_order([item.strip() for item in value if item and item.strip()])
        for evidence_id in cleaned:
            if not EVIDENCE_ID_PATTERN.match(evidence_id):
                raise ValueError(f"Invalid evidence id: {evidence_id}")
        return cleaned


class CanonicalDimension(PlainModel):
    name: str
    value: str | int | float
    unit: str | None = None


class CanonicalLocation(PlainModel):
    x: str | int | float | None = None
    y: str | int | float | None = None
    unit: str | None = None


class CanonicalComponent(EvidenceBoundModel):
    label: str
    shape_mode: str | None = None
    dimensions: list[CanonicalDimension] = Field(default_factory=list)
    material_name: str | None = None
    layer_role: str | None = None


class CanonicalFeed(EvidenceBoundModel):
    feed_family: str
    matching_style: str
    driven_target: str | None = None
    dimensions: list[CanonicalDimension] = Field(default_factory=list)
    location: CanonicalLocation | None = None


class CanonicalMaterial(EvidenceBoundModel):
    name: str
    category: str
    roles: list[str] = Field(default_factory=list)


class CanonicalLayer(EvidenceBoundModel):
    role: str
    material_name: str | None = None
    thickness_value: str | int | float | None = None
    thickness_unit: str | None = None


class CanonicalMetric(EvidenceBoundModel):
    name: str
    value: str | int | float
    unit: str | None = None


class CanonicalParameter(EvidenceBoundModel):
    semantic_name: str
    symbol: str | None = None
    value: str | int | float
    unit: str | None = None
    target_component: str | None = None


class CanonicalConflict(StrictModel):
    topic: str
    description: str
    preferred_evidence_ids: list[str] = Field(default_factory=list)
    conflicting_evidence_ids: list[str] = Field(default_factory=list)
    status: ConflictStatus

    @field_validator("preferred_evidence_ids", "conflicting_evidence_ids")
    @classmethod
    def validate_conflict_evidence_ids(cls, value: list[str]) -> list[str]:
        cleaned = _dedupe_preserve_order([item.strip() for item in value if item and item.strip()])
        for evidence_id in cleaned:
            if not EVIDENCE_ID_PATTERN.match(evidence_id):
                raise ValueError(f"Invalid evidence id: {evidence_id}")
        return cleaned


class CanonicalClassification(PlainModel):
    primary_family: str
    topology_tags: list[str] = Field(default_factory=list)


class CanonicalFinalDesign(StrictModel):
    classification: CanonicalClassification
    patch: CanonicalComponent | None = None
    feed: CanonicalFeed | None = None
    ground: CanonicalComponent | None = None
    slots: list[CanonicalComponent] = Field(default_factory=list)
    materials: list[CanonicalMaterial] = Field(default_factory=list)
    layers: list[CanonicalLayer] = Field(default_factory=list)
    performance_targets: list[CanonicalMetric] = Field(default_factory=list)
    extra_parameters: list[CanonicalParameter] = Field(default_factory=list)


class DesignEvolutionNote(EvidenceBoundModel):
    label: str
    description: str


class CanonicalDesignRecord(StrictModel):
    selected_design_summary: str
    selected_design_rationale: str
    has_multiple_variants: bool
    dominant_evidence_ids: list[str] = Field(default_factory=list)
    secondary_evidence_ids: list[str] = Field(default_factory=list)
    identified_antennas: list[str] = Field(
        default_factory=list,
        description=(
            "List every distinct antenna, design iteration, reference antenna, comparison variant, or extension "
            "that appears in the retrieved context before selecting the paper's dominant final design."
        ),
    )
    proposed_final_antenna_rationale: str = Field(
        description=(
            "Explain which identified antenna is the main proposed final design of the paper and why competing "
            "variants, intermediate steps, or reference antennas were not selected as the canonical final design."
        )
    )
    final_design: CanonicalFinalDesign = Field(
        description="Canonical representation of the single dominant final/proposed antenna design selected from the paper."
    )
    design_evolution_notes: list[DesignEvolutionNote] = Field(default_factory=list)
    unresolved_conflicts: list[CanonicalConflict] = Field(default_factory=list)

    @field_validator("selected_design_summary", "selected_design_rationale", "proposed_final_antenna_rationale")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("text must not be empty")
        return cleaned

    @field_validator("dominant_evidence_ids", "secondary_evidence_ids")
    @classmethod
    def validate_top_level_evidence_ids(cls, value: list[str]) -> list[str]:
        cleaned = _dedupe_preserve_order([item.strip() for item in value if item and item.strip()])
        for evidence_id in cleaned:
            if not EVIDENCE_ID_PATTERN.match(evidence_id):
                raise ValueError(f"Invalid evidence id: {evidence_id}")
        return cleaned

    def to_clean_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def validate_canonical_design_record_payload(payload: dict[str, Any]) -> CanonicalDesignRecord:
    return CanonicalDesignRecord.model_validate(payload)


def collect_canonical_evidence_ids(value: CanonicalDesignRecord | dict[str, Any]) -> list[str]:
    payload = value.to_clean_dict() if isinstance(value, CanonicalDesignRecord) else value
    collected: list[str] = []
    _collect_evidence_ids(payload, collected)
    return _dedupe_preserve_order(collected)


def _collect_evidence_ids(value: Any, collected: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"evidence_ids", "dominant_evidence_ids", "secondary_evidence_ids", "preferred_evidence_ids", "conflicting_evidence_ids"} and isinstance(nested, list):
                collected.extend(item for item in nested if isinstance(item, str))
            else:
                _collect_evidence_ids(nested, collected)
        return
    if isinstance(value, list):
        for nested in value:
            _collect_evidence_ids(nested, collected)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
