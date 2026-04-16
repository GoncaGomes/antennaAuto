from __future__ import annotations

from mvp.schemas.interpretation_map import validate_interpretation_map_payload


def test_interpretation_map_schema_accepts_strict_payload() -> None:
    interpretation_map = validate_interpretation_map_payload(
        {
            "has_multiple_variants": True,
            "has_final_design_signal": True,
            "search_queries": [
                {
                    "query_id": "Q1",
                    "query_text": "final selected antenna design",
                    "priority": "high",
                    "why": "The paper likely contains multiple stages and a measured final design.",
                }
            ],
            "open_uncertainties": ["Whether the reported results mix multiple variants."],
        }
    )

    assert interpretation_map.has_multiple_variants is True
    assert interpretation_map.search_queries[0].query_id == "Q1"
