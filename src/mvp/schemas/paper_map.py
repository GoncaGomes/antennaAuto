from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


TableRoleGuess = Literal["dimensions", "materials", "parameters", "results", "comparison", "unknown"]
FigureRoleGuess = Literal["geometry", "layout", "fabricated", "measurement", "radiation", "unknown"]


class DesignSignalCounts(StrictModel):
    proposed: int = Field(default=0, ge=0)
    final: int = Field(default=0, ge=0)
    optimized: int = Field(default=0, ge=0)
    fabricated: int = Field(default=0, ge=0)
    measured: int = Field(default=0, ge=0)
    simulated: int = Field(default=0, ge=0)


class EvidenceSnippet(StrictModel):
    text: str
    page_number: int | None = Field(default=None, ge=1)
    evidence_id: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("text must not be empty")
        return cleaned


class TableReference(StrictModel):
    table_id: str
    caption: str
    page_number: int | None = Field(default=None, ge=1)
    table_role_guess: TableRoleGuess = "unknown"


class FigureReference(StrictModel):
    figure_id: str
    caption: str
    page_number: int | None = Field(default=None, ge=1)
    figure_role_guess: FigureRoleGuess = "unknown"


class PaperMap(StrictModel):
    """Deterministic lightweight paper-understanding artifact for Phase 1."""

    title: str
    abstract: str | None = None
    section_headings_top_level: list[str] = Field(default_factory=list)
    key_design_signals: DesignSignalCounts
    candidate_design_mentions: list[EvidenceSnippet] = Field(default_factory=list)
    key_table_refs: list[TableReference] = Field(default_factory=list)
    key_figure_refs: list[FigureReference] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("title must not be empty")
        return cleaned

    @field_validator("section_headings_top_level")
    @classmethod
    def normalize_headings(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for heading in value:
            cleaned = " ".join(heading.split())
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned)
        return normalized

    def to_clean_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def validate_paper_map_payload(payload: dict[str, Any]) -> PaperMap:
    return PaperMap.model_validate(payload)
