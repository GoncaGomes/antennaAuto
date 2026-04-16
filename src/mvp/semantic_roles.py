from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

SemanticParameterRole = Literal["entity_geometry", "layer_property", "feed_property", "global_metric", "unknown"]
SemanticConfidence = Literal["high", "medium", "low"]

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_CAMEL_BOUNDARY_PATTERN = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_DIGIT_BOUNDARY_PATTERN = re.compile(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])")

GEOMETRY_TARGET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "slot": ("slot", "slit", "aperture", "notch", "cutout", "cut"),
    "ground": ("ground", "gnd", "groundplane", "plane"),
    "patch": ("patch", "radiator", "radiating", "element", "strip", "stub", "ring", "arm"),
}
LAYER_TARGET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "substrate": ("substrate", "dielectric", "laminate"),
    "ground": ("ground", "gnd", "groundplane"),
    "patch": ("patch", "radiator"),
    "conductor": ("conductor", "metal", "copper", "gold", "aluminum", "cladding"),
}
FEED_KEYWORDS = (
    "feed",
    "feedline",
    "feed_line",
    "microstrip",
    "coax",
    "coaxial",
    "probe",
    "port",
    "inset",
    "edge",
    "apex",
)
FEED_POSITION_KEYWORDS = ("offset", "position", "location", "point", "x", "y", "z")
GLOBAL_METRIC_KEYWORDS = (
    "frequency",
    "bandwidth",
    "gain",
    "efficiency",
    "vswr",
    "return_loss",
    "reflection",
    "coefficient",
    "s11",
    "resonant",
    "directivity",
    "axial_ratio",
    "radiation",
)
LENGTH_UNITS = {"mm", "cm", "m", "um", "μm", "mil"}
FREQUENCY_UNITS = {"hz", "khz", "mhz", "ghz"}
IMPEDANCE_UNITS = {"ohm", "ω", "Ω"}

ENTITY_PROPERTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "length": ("length",),
    "width": ("width",),
    "radius": ("radius",),
    "diameter": ("diameter",),
    "base": ("base",),
    "height": ("height",),
    "depth": ("depth",),
    "x": ("x axis", "x-axis", " x "),
    "y": ("y axis", "y-axis", " y "),
    "z": ("z axis", "z-axis", " z "),
}


@dataclass(frozen=True)
class ParameterRoleClassification:
    role: SemanticParameterRole
    confidence: SemanticConfidence
    target_hint: str | None = None
    property_hint: str | None = None

    @property
    def structural(self) -> bool:
        return self.role in {"entity_geometry", "layer_property", "feed_property"}


def classify_parameter_role(
    semantic_name: str,
    symbol: str | None = None,
    unit: str | None = None,
) -> ParameterRoleClassification:
    combined_text = _normalized_text_parts(semantic_name, symbol)
    unit_text = (unit or "").strip().lower()

    if not combined_text:
        return ParameterRoleClassification(role="unknown", confidence="low")

    if _is_reference_impedance(combined_text, unit_text):
        return ParameterRoleClassification(
            role="feed_property",
            confidence="high",
            target_hint="feed",
            property_hint="reference_impedance",
        )

    if _contains_any(combined_text, GLOBAL_METRIC_KEYWORDS) or unit_text in FREQUENCY_UNITS:
        return ParameterRoleClassification(role="global_metric", confidence="high")

    layer_target = _match_target(combined_text, LAYER_TARGET_KEYWORDS)
    if layer_target and _contains_any(combined_text, ("thickness", "height")):
        return ParameterRoleClassification(
            role="layer_property",
            confidence="high",
            target_hint=layer_target,
            property_hint="thickness",
        )

    if _contains_any(combined_text, FEED_KEYWORDS):
        property_hint = _match_entity_property(combined_text)
        if property_hint is not None or _contains_any(combined_text, FEED_POSITION_KEYWORDS):
            return ParameterRoleClassification(
                role="feed_property",
                confidence="high" if property_hint not in {"x", "y", "z"} else "medium",
                target_hint="feed",
                property_hint=property_hint or "position",
            )

    geometry_target = _match_target(combined_text, GEOMETRY_TARGET_KEYWORDS)
    geometry_property = _match_entity_property(combined_text)
    if geometry_target and geometry_property:
        return ParameterRoleClassification(
            role="entity_geometry",
            confidence="high",
            target_hint=geometry_target,
            property_hint=geometry_property,
        )

    if geometry_target and unit_text in LENGTH_UNITS and _contains_any(combined_text, ("dimension", "size")):
        return ParameterRoleClassification(
            role="entity_geometry",
            confidence="medium",
            target_hint=geometry_target,
            property_hint="dimension",
        )

    if _contains_any(combined_text, ("impedance",)) and unit_text in IMPEDANCE_UNITS:
        return ParameterRoleClassification(role="global_metric", confidence="medium")

    return ParameterRoleClassification(role="unknown", confidence="low")


def classify_parameter_payload(parameter: Mapping[str, Any]) -> ParameterRoleClassification:
    return classify_parameter_role(
        semantic_name=str(parameter.get("semantic_name") or ""),
        symbol=(str(parameter.get("symbol")) if parameter.get("symbol") is not None else None),
        unit=(str(parameter.get("unit")) if parameter.get("unit") is not None else None),
    )


def normalize_parameter_text(semantic_name: str, symbol: str | None = None) -> str:
    return _normalized_text_parts(semantic_name, symbol)


def is_high_confidence_structural_binding(classification: ParameterRoleClassification) -> bool:
    return classification.role in {"entity_geometry", "layer_property"} and classification.confidence == "high"


def _normalized_text_parts(*parts: str | None) -> str:
    normalized_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        text = _CAMEL_BOUNDARY_PATTERN.sub(" ", part)
        text = _DIGIT_BOUNDARY_PATTERN.sub(" ", text)
        text = text.replace("(", " ").replace(")", " ")
        text = _NON_ALNUM_PATTERN.sub(" ", text.lower())
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            normalized_parts.append(f" {text} ")
    return " ".join(normalized_parts).strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(f" {keyword} " in padded for keyword in keywords)


def _match_target(text: str, mapping: dict[str, tuple[str, ...]]) -> str | None:
    for target, keywords in mapping.items():
        if _contains_any(text, keywords):
            return target
    return None


def _match_entity_property(text: str) -> str | None:
    padded = f" {text} "
    for property_name, keywords in ENTITY_PROPERTY_KEYWORDS.items():
        if any(keyword in padded for keyword in keywords):
            return property_name
    return None


def _is_reference_impedance(text: str, unit: str) -> bool:
    if unit not in IMPEDANCE_UNITS:
        return False
    if " reference " in text and " impedance " in text:
        return True
    if " characteristic " in text and " impedance " in text:
        return True
    return " feed " in text and " impedance " in text
