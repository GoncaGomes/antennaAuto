from __future__ import annotations

from mvp.interpretation.prompting import SYSTEM_PROMPT, build_interpretation_messages
from mvp.schemas.paper_map import PaperMap


def test_interpretation_prompt_is_retrieval_guidance_only() -> None:
    paper_map = PaperMap.model_validate(
        {
            "title": "Example antenna paper",
            "abstract": "A proposed design is optimized and measured.",
            "section_headings_top_level": ["Abstract", "Design", "Results"],
            "key_design_signals": {
                "proposed": 1,
                "final": 1,
                "optimized": 1,
                "fabricated": 1,
                "measured": 1,
                "simulated": 1,
            },
            "candidate_design_mentions": [
                {"text": "The final optimized design is fabricated and measured.", "page_number": 1, "evidence_id": "chunk:chunk_001"}
            ],
            "key_table_refs": [
                {"table_id": "table_001", "caption": "Table 1. Design parameters", "page_number": 2, "table_role_guess": "parameters"}
            ],
            "key_figure_refs": [
                {"figure_id": "fig_001", "caption": "Figure 1. Antenna geometry", "page_number": 1, "figure_role_guess": "geometry"}
            ],
        }
    )

    messages = build_interpretation_messages(paper_map)

    assert len(messages) == 2
    assert "You are an antenna-paper retrieval planner." in SYSTEM_PROMPT
    assert "You do NOT execute retrieval." in SYSTEM_PROMPT
    assert "Search queries must be simple natural-language retrieval queries." in SYSTEM_PROMPT
    assert "Search queries must be article-targeted." in SYSTEM_PROMPT
    assert "Discourage generic queries such as fabrication details" in SYSTEM_PROMPT
    assert "Here is the paper_map.json:" in messages[1]["content"]
    assert "prefer 3 to 6 search queries maximum" in messages[1]["content"]
    assert "search_queries must use the paper's own wording when possible" in messages[1]["content"]
    assert "avoid generic queries like fabrication details" in messages[1]["content"]
    assert "Example antenna paper" in messages[1]["content"]
