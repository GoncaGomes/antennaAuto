from __future__ import annotations

import json
from typing import Any

from ..schemas.paper_map import PaperMap

SYSTEM_PROMPT = """You are an antenna-paper retrieval planner.

You will receive a lightweight paper_map.json.

Your job is only to decide what should be searched next.

You are not summarizing the paper.
You are not extracting the final antenna architecture.
You do NOT execute retrieval.
You do NOT emit tool calls.
You do NOT emit backend-specific commands.

Use only the information in the provided paper_map.json.
Do not invent facts.
If the paper may contain multiple variants, stages, or candidate final designs, preserve that uncertainty.

Search queries must be simple natural-language retrieval queries.
Search queries must be article-targeted.
Search queries must be:
- short
- simple natural-language retrieval queries
- retrieval-friendly
- article-targeted
- phrased with the document's own wording when possible

Prioritize:
1. final / selected / optimized / fabricated design signals
2. variants, stages, or design evolution
3. geometry, feed, or materials only when still unresolved

Discourage generic queries such as fabrication details, simulation results, measured performance, optimization process, or comparison with prior work unless they are directly justified by the paper_map evidence.
"""


def build_interpretation_messages(paper_map: PaperMap | dict[str, Any]) -> list[dict[str, str]]:
    if isinstance(paper_map, PaperMap):
        payload = paper_map.to_clean_dict()
    else:
        payload = dict(paper_map)

    paper_map_json = json.dumps(payload, indent=2, sort_keys=True)
    user_prompt = (
        "You will receive a lightweight paper_map.json for one antenna paper.\n\n"
        "Produce the structured interpretation output required by the SDK schema.\n\n"
        "Focus on:\n\n"
        "whether the paper likely contains multiple variants or stages\n"
        "whether there are signals of a final / optimized / selected / fabricated design and any supporting measured validation\n"
        "a small set of useful search queries for deterministic retrieval\n"
        "unresolved ambiguities that still need evidence\n\n"
        "Important constraints:\n\n"
        "do not extract the final architecture schema\n"
        "do not invent facts\n"
        "do not generate tool calls\n"
        "do not generate backend-specific retrieval syntax\n"
        "keep the output simple and operational\n"
        "prefer 3 to 6 search queries maximum\n\n"
        "search_queries must be short\n"
        "search_queries must be retrieval-friendly\n"
        "search_queries must be article-targeted\n"
        "search_queries must use the paper's own wording when possible\n"
        "search_queries must not be long questions\n"
        "prioritize final selected design first\n"
        "then variants, stages, or design evolution\n"
        "only ask about geometry, feed, or materials if still unresolved\n"
        "avoid generic queries like fabrication details, simulation results, optimization process, or comparison with existing designs unless directly justified by the paper_map\n\n"
        "Here is the paper_map.json:\n\n"
        f"{paper_map_json}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
