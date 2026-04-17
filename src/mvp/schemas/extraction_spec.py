from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from ..semantic_roles import (
    classify_parameter_payload,
    is_high_confidence_structural_binding,
)

FieldStatus = Literal["extracted", "partially_extracted", "missing", "assumed_local_origin"]
BuildReadiness = Literal["ready", "partial", "insufficient"]

INTERNAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
EVIDENCE_ID_PATTERN = re.compile(r"^[a-z_]+:[A-Za-z0-9_]+$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceBoundModel(StrictModel):
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_evidence_ids(cls, value: Any) -> Any:
        return _normalize_evidence_id_values(value)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: list[str]) -> list[str]:
        cleaned = _dedupe_preserve_order([item.strip() for item in value if item and item.strip()])
        for evidence_id in cleaned:
            if not EVIDENCE_ID_PATTERN.match(evidence_id):
                raise ValueError(f"Invalid evidence id: {evidence_id}")
        return cleaned


class DocumentContext(StrictModel):
    run_id: str
    original_filename: str
    page_count: int


class Classification(EvidenceBoundModel):
    primary_family: str | None = None
    topology_tags: list[str] = Field(default_factory=list)
    status: FieldStatus
    confidence: float = Field(ge=0.0, le=1.0)


class UnitField(EvidenceBoundModel):
    status: FieldStatus
    value: str | None = None

    @model_validator(mode="after")
    def require_value_when_present(self) -> "UnitField":
        if self.status != "missing" and not self.value:
            raise ValueError("value is required when status is not missing")
        return self


class Units(StrictModel):
    length: UnitField
    frequency: UnitField
    impedance: UnitField


class ParameterSpec(EvidenceBoundModel):
    param_id: str
    symbol: str | None = None
    semantic_name: str
    status: FieldStatus
    value: str | int | float | None = None
    unit: str | None = None

    @field_validator("param_id")
    @classmethod
    def validate_param_id(cls, value: str) -> str:
        return _validate_internal_id(value)

    @model_validator(mode="after")
    def require_value_when_present(self) -> "ParameterSpec":
        if self.status in {"extracted", "partially_extracted", "assumed_local_origin"} and self.value is None:
            raise ValueError("parameter value is required when status is not missing")
        return self


class MaterialSpec(EvidenceBoundModel):
    material_id: str
    name: str
    name_raw: str | None = None
    category: str
    roles: list[str] = Field(default_factory=list)
    status: FieldStatus

    @field_validator("material_id")
    @classmethod
    def validate_material_id(cls, value: str) -> str:
        return _validate_internal_id(value)


class ScalarValue(EvidenceBoundModel):
    status: FieldStatus
    value: str | int | float | None = None
    unit: str | None = None

    @model_validator(mode="after")
    def require_value_when_present(self) -> "ScalarValue":
        if self.status in {"extracted", "partially_extracted", "assumed_local_origin"} and self.value is None:
            raise ValueError("value is required when status is not missing")
        return self


class LayerSpec(EvidenceBoundModel):
    layer_id: str
    role: str
    material_ref: str
    thickness: ScalarValue
    z_order: int

    @field_validator("layer_id", "material_ref")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _validate_internal_id(value)


class GeometryDimension(EvidenceBoundModel):
    name: str
    status: FieldStatus
    value: str | int | float | None = None
    unit: str | None = None
    param_ref: str | None = None

    @field_validator("param_ref")
    @classmethod
    def validate_param_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_internal_id(value)

    @model_validator(mode="after")
    def require_value_or_param(self) -> "GeometryDimension":
        if self.status in {"extracted", "partially_extracted", "assumed_local_origin"}:
            if self.value is None and self.param_ref is None:
                raise ValueError("geometry dimension requires a value or param_ref when status is not missing")
        return self


class OutlinePoint(StrictModel):
    x: str | int | float
    y: str | int | float


class GeometrySpec(StrictModel):
    shape_mode: str
    dimensions: list[GeometryDimension] = Field(default_factory=list)
    outline_points: list[OutlinePoint] = Field(default_factory=list)


class PlacementSpec(StrictModel):
    status: FieldStatus
    anchor: str | None = None


class EntitySpec(EvidenceBoundModel):
    entity_id: str
    entity_type: str
    role: str
    layer_ref: str
    material_ref: str | None = None
    geometry: GeometrySpec
    placement: PlacementSpec

    @field_validator("entity_id", "layer_ref", "material_ref")
    @classmethod
    def validate_entity_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_internal_id(value)


class PortTypeSpec(StrictModel):
    status: FieldStatus
    value: str | None = None

    @model_validator(mode="after")
    def require_value_when_present(self) -> "PortTypeSpec":
        if self.status in {"extracted", "partially_extracted", "assumed_local_origin"} and not self.value:
            raise ValueError("port_type value is required when status is not missing")
        return self


class FeedSpec(EvidenceBoundModel):
    feed_id: str
    feed_family: str
    matching_style: str
    driven_entity_ref: str
    reference_impedance: ScalarValue
    port_type: PortTypeSpec

    @field_validator("feed_id", "driven_entity_ref")
    @classmethod
    def validate_feed_ids(cls, value: str) -> str:
        return _validate_internal_id(value)


class InstanceSpec(EvidenceBoundModel):
    instance_id: str
    entity_ref: str
    status: FieldStatus
    count: int | None = None
    pattern: str | None = None

    @field_validator("instance_id", "entity_ref")
    @classmethod
    def validate_instance_ids(cls, value: str) -> str:
        return _validate_internal_id(value)


class QualitySpec(StrictModel):
    build_readiness: BuildReadiness
    missing_required_for_build: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class AntennaArchitectureSpecMvpV2(StrictModel):
    schema_name: Literal["antenna_architecture_spec_mvp_v2"] = "antenna_architecture_spec_mvp_v2"
    schema_version: Literal["2.0"] = "2.0"
    document_context: DocumentContext
    classification: Classification
    units: Units
    parameters: list[ParameterSpec] = Field(default_factory=list)
    materials: list[MaterialSpec] = Field(default_factory=list)
    layers: list[LayerSpec] = Field(default_factory=list)
    entities: list[EntitySpec] = Field(default_factory=list)
    feeds: list[FeedSpec] = Field(default_factory=list)
    instances: list[InstanceSpec] = Field(default_factory=list)
    quality: QualitySpec
    evidence_used: list[str] = Field(default_factory=list)

    @field_validator("evidence_used", mode="before")
    @classmethod
    def normalize_evidence_used(cls, value: Any) -> Any:
        return _normalize_evidence_id_values(value)

    @field_validator("evidence_used")
    @classmethod
    def validate_evidence_used(cls, value: list[str]) -> list[str]:
        cleaned = _dedupe_preserve_order([item.strip() for item in value if item and item.strip()])
        for evidence_id in cleaned:
            if not EVIDENCE_ID_PATTERN.match(evidence_id):
                raise ValueError(f"Invalid evidence_used id: {evidence_id}")
        return cleaned

    @model_validator(mode="after")
    def validate_consistency(self) -> "AntennaArchitectureSpecMvpV2":
        parameter_ids = _ensure_unique_ids("param_id", self.parameters)
        material_ids = _ensure_unique_ids("material_id", self.materials)
        layer_ids = _ensure_unique_ids("layer_id", self.layers)
        entity_ids = _ensure_unique_ids("entity_id", self.entities)
        feed_ids = _ensure_unique_ids("feed_id", self.feeds)
        instance_ids = _ensure_unique_ids("instance_id", self.instances)

        _ = feed_ids
        _ = instance_ids

        for layer in self.layers:
            if layer.material_ref not in material_ids:
                raise ValueError(f"Layer references unknown material_ref: {layer.material_ref}")

        for entity in self.entities:
            if entity.layer_ref not in layer_ids:
                raise ValueError(f"Entity references unknown layer_ref: {entity.layer_ref}")
            if entity.material_ref and entity.material_ref not in material_ids:
                raise ValueError(f"Entity references unknown material_ref: {entity.material_ref}")
            for dimension in entity.geometry.dimensions:
                if dimension.param_ref and dimension.param_ref not in parameter_ids:
                    raise ValueError(f"Geometry dimension references unknown param_ref: {dimension.param_ref}")

        for feed in self.feeds:
            if feed.driven_entity_ref not in entity_ids:
                raise ValueError(f"Feed references unknown driven_entity_ref: {feed.driven_entity_ref}")

        for instance in self.instances:
            if instance.entity_ref not in entity_ids:
                raise ValueError(f"Instance references unknown entity_ref: {instance.entity_ref}")

        nested_evidence_ids = collect_nested_evidence_ids(self)
        missing_evidence = sorted(set(nested_evidence_ids) - set(self.evidence_used))
        if missing_evidence:
            raise ValueError(
                "All nested evidence_ids must also appear in evidence_used. Missing: "
                + ", ".join(missing_evidence)
            )

        return self

    def to_clean_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def validate_spec_payload(payload: dict[str, Any]) -> AntennaArchitectureSpecMvpV2:
    return AntennaArchitectureSpecMvpV2.model_validate(payload)


def validate_semantic_bindings(model: AntennaArchitectureSpecMvpV2) -> AntennaArchitectureSpecMvpV2:
    geometry_representations = _collect_geometry_representations(model)

    for parameter in model.parameters:
        if parameter.status == "missing" or parameter.value is None:
            continue
        classification = classify_parameter_payload(parameter.model_dump(exclude_none=True))
        if not is_high_confidence_structural_binding(classification):
            continue

        if classification.role == "entity_geometry":
            if _entity_geometry_parameter_is_bound(parameter, classification, model, geometry_representations):
                continue
            if _matching_entity_exists(model, classification.target_hint):
                raise ValueError(
                    f"Structural geometry parameter is orphaned and should be bound to entity geometry: {parameter.param_id}"
                )

        if classification.role == "layer_property" and classification.property_hint == "thickness":
            if _layer_property_parameter_is_bound(parameter, classification, model):
                continue
            if _matching_layer_exists(model, classification.target_hint):
                raise ValueError(
                    f"Layer thickness parameter is orphaned and should be bound to a layer thickness field: {parameter.param_id}"
                )

    return model


def collect_nested_evidence_ids(model: AntennaArchitectureSpecMvpV2) -> list[str]:
    payload = model.model_dump(exclude_none=True)
    collected: list[str] = []
    _collect_evidence_ids(payload, collected)
    return _dedupe_preserve_order(collected)


def _collect_evidence_ids(value: Any, collected: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "evidence_ids" and isinstance(nested, list):
                collected.extend(item for item in nested if isinstance(item, str))
            else:
                _collect_evidence_ids(nested, collected)
        return
    if isinstance(value, list):
        for nested in value:
            _collect_evidence_ids(nested, collected)


def _ensure_unique_ids(field_name: str, items: list[BaseModel]) -> set[str]:
    values = [getattr(item, field_name) for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate ids found in {field_name}")
    return set(values)


def _validate_internal_id(value: str) -> str:
    cleaned = value.strip()
    if not INTERNAL_ID_PATTERN.match(cleaned):
        raise ValueError(f"Invalid internal id: {cleaned}")
    return cleaned


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_evidence_id_values(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, list):
        return [_autocorrect_evidence_id(item) for item in value]
    if isinstance(value, tuple):
        return [_autocorrect_evidence_id(item) for item in value]
    return value


def _autocorrect_evidence_id(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    if not cleaned or ":" in cleaned:
        return cleaned
    lowered = cleaned.lower()
    if lowered.startswith("chunk"):
        return f"chunk:{cleaned}"
    if lowered.startswith("page"):
        return f"section:{cleaned}"
    if lowered.startswith("table"):
        return f"table:{cleaned}"
    if lowered.startswith("fig"):
        return f"figure:{cleaned}"
    return cleaned


def _matching_entity_exists(model: AntennaArchitectureSpecMvpV2, target_hint: str | None) -> bool:
    if not target_hint:
        return False
    target_terms = {
        "patch": {"patch", "radiator", "radiating_element"},
        "slot": {"slot", "notch", "aperture"},
        "ground": {"ground", "ground_plane"},
    }.get(target_hint, {target_hint})
    for entity in model.entities:
        role = (entity.role or "").lower()
        entity_type = (entity.entity_type or "").lower()
        if role in target_terms or entity_type in target_terms:
            return True
    return False


def _matching_layer_exists(model: AntennaArchitectureSpecMvpV2, target_hint: str | None) -> bool:
    if not target_hint:
        return False
    target_terms = {
        "substrate": {"substrate"},
        "ground": {"ground"},
        "patch": {"patch", "radiator"},
        "conductor": {"patch", "radiator", "ground"},
    }.get(target_hint, {target_hint})
    for layer in model.layers:
        if (layer.role or "").lower() in target_terms:
            return True
    return False


def _entity_geometry_parameter_is_bound(
    parameter: ParameterSpec,
    classification,
    model: AntennaArchitectureSpecMvpV2,
    geometry_representations: list[dict[str, Any]],
) -> bool:
    if any(
        dimension.param_ref == parameter.param_id
        for entity in model.entities
        for dimension in entity.geometry.dimensions
    ):
        return True

    parameter_value = str(parameter.value)
    parameter_unit = (parameter.unit or "").lower()
    parameter_name = (classification.property_hint or "").lower()
    parameter_evidence = set(parameter.evidence_ids)

    for representation in geometry_representations:
        if classification.target_hint and representation["target_hint"] != classification.target_hint:
            continue
        if parameter_name and representation["name"] != parameter_name:
            continue
        if representation["value"] == parameter_value and representation["unit"] == parameter_unit:
            return True
        if parameter_evidence and parameter_evidence.intersection(representation["evidence_ids"]):
            return True
    return False


def _layer_property_parameter_is_bound(
    parameter: ParameterSpec,
    classification,
    model: AntennaArchitectureSpecMvpV2,
) -> bool:
    parameter_value = str(parameter.value)
    parameter_unit = (parameter.unit or "").lower()
    parameter_evidence = set(parameter.evidence_ids)

    for layer in model.layers:
        if classification.target_hint == "substrate" and layer.role.lower() != "substrate":
            continue
        if classification.target_hint == "ground" and layer.role.lower() != "ground":
            continue
        if classification.target_hint in {"patch", "conductor"} and layer.role.lower() not in {"patch", "radiator", "ground"}:
            continue

        if layer.thickness.status == "missing" or layer.thickness.value is None:
            continue
        if str(layer.thickness.value) == parameter_value and (layer.thickness.unit or "").lower() == parameter_unit:
            return True
        if parameter_evidence and parameter_evidence.intersection(layer.thickness.evidence_ids):
            return True
    return False


def _collect_geometry_representations(model: AntennaArchitectureSpecMvpV2) -> list[dict[str, Any]]:
    representations: list[dict[str, Any]] = []
    for entity in model.entities:
        target_hint = _entity_target_hint(entity)
        for dimension in entity.geometry.dimensions:
            representations.append(
                {
                    "target_hint": target_hint,
                    "name": dimension.name.lower(),
                    "value": (str(dimension.value) if dimension.value is not None else None),
                    "unit": (dimension.unit or "").lower(),
                    "evidence_ids": set(dimension.evidence_ids),
                }
            )
    return representations


def _entity_target_hint(entity: EntitySpec) -> str | None:
    entity_type = (entity.entity_type or "").lower()
    role = (entity.role or "").lower()
    if entity_type in {"slot", "notch", "aperture"} or role in {"slot", "notch"}:
        return "slot"
    if entity_type in {"ground", "ground_plane"} or role == "ground":
        return "ground"
    if entity_type in {"patch", "radiating_element"} or role == "radiator":
        return "patch"
    return None
