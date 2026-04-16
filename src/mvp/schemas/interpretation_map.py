from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SearchPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(description="Short identifier such as Q1 or Q2.")
    query_text: str = Field(description="Simple natural-language retrieval query.")
    priority: SearchPriority = Field(description="Relative importance of the query.")
    why: str = Field(description="Why this query should be executed next.")


class InterpretationMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_multiple_variants: bool = Field(
        description="Whether the paper likely contains multiple variants or stages."
    )
    has_final_design_signal: bool = Field(
        description="Whether the paper likely signals a final, optimized, selected, fabricated, or measured design."
    )
    search_queries: list[SearchQuery] = Field(
        description="Small set of search queries for deterministic retrieval."
    )
    open_uncertainties: list[str] = Field(
        description="Key ambiguities that still need evidence."
    )


def validate_interpretation_map_payload(payload: dict) -> InterpretationMap:
    return InterpretationMap.model_validate(payload)
