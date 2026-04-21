from __future__ import annotations

from pathlib import Path
from typing import Any

from ..retrieval import BundleRetriever
from ..utils import read_json, text_excerpt

PHASE1_TABLE_QUERY_CUES = (
    "table",
    "parameter",
    "parameters",
    "dimension",
    "dimensions",
    "thickness",
    "material",
)
PHASE1_FIGURE_QUERY_CUES = (
    "figure",
    "fig",
    "diagram",
    "schematic",
    "layout",
    "geometry",
)

RETRIEVAL_PLAN: dict[str, list[tuple[str, str]]] = {
    "classification": [
        ("text", "antenna type"),
        ("text", "proposed design"),
        ("text", "final design"),
        ("text", "configuration"),
    ],
    "materials": [
        ("text", "substrate material"),
        ("text", "dielectric material"),
        ("text", "conductor material"),
        ("tables", "material"),
    ],
    "layers": [
        ("text", "layer stack"),
        ("text", "substrate thickness"),
        ("text", "metal thickness"),
        ("text", "ground plane"),
        ("tables", "thickness"),
    ],
    "parameters": [
        ("tables", "dimensions"),
        ("tables", "design parameters"),
        ("text", "geometrical parameters"),
        ("text", "table of dimensions"),
        ("text", "operating frequency"),
    ],
    "entities": [
        ("text", "antenna geometry"),
        ("text", "radiating element"),
        ("text", "slot geometry"),
        ("text", "ground plane geometry"),
        ("figures", "antenna geometry"),
    ],
    "feeds": [
        ("text", "feeding method"),
        ("text", "feed type"),
        ("text", "feed location"),
        ("text", "input port"),
        ("text", "input impedance"),
    ],
    "quality": [
        ("text", "bandwidth"),
        ("text", "gain"),
        ("text", "return loss"),
        ("text", "reflection coefficient"),
        ("text", "VSWR"),
    ],
}


def gather_retrieval_context(retriever: BundleRetriever, top_k: int = 5) -> dict[str, Any]:
    return gather_retrieval_context_with_phase1(retriever, top_k=top_k, phase1_search_queries=None)


def gather_retrieval_context_with_phase1(
    retriever: BundleRetriever,
    top_k: int = 5,
    phase1_search_queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metadata = read_json(retriever.run_paths.metadata_path)
    run_context = {
        "run_id": retriever.run_paths.run_id,
        "original_filename": metadata["original_filename"],
        "page_count": metadata["page_count"],
    }

    retrieval_queries_used: dict[str, list[dict[str, Any]]] = {}
    evidence_ids_by_block: dict[str, list[str]] = {}
    evidence_by_block: dict[str, list[dict[str, Any]]] = {}
    all_retrieved_evidence_ids: list[str] = []
    normalized_phase1_queries = _normalize_phase1_search_queries(phase1_search_queries)

    for block, queries in RETRIEVAL_PLAN.items():
        retrieval_queries_used[block] = []
        seen_ids: set[str] = set()
        block_records: list[dict[str, Any]] = []

        for query_entry in _block_query_entries(block, queries, normalized_phase1_queries):
            search_type = query_entry["search_type"]
            query = query_entry["query"]
            search_fn = _dispatch_search(retriever, search_type)
            effective_top_k = min(3, top_k) if query_entry["query_source"] == "phase1_interpretation_map" else top_k
            results = search_fn(query, top_k=effective_top_k)
            query_log = {
                "search_type": search_type,
                "query": query,
                "query_source": query_entry["query_source"],
                "result_evidence_ids": [item["evidence_id"] for item in results],
            }
            if query_entry.get("phase1_query_id"):
                query_log["phase1_query_id"] = query_entry["phase1_query_id"]
            if query_entry.get("phase1_priority"):
                query_log["phase1_priority"] = query_entry["phase1_priority"]
            retrieval_queries_used[block].append(query_log)
            for result in results:
                evidence_id = result["evidence_id"]
                if evidence_id in seen_ids:
                    continue
                seen_ids.add(evidence_id)
                evidence = retriever.get_evidence_by_id(evidence_id)
                if evidence is None:
                    continue
                block_records.append(_build_prompt_record(result, evidence))
                all_retrieved_evidence_ids.append(evidence_id)

        evidence_by_block[block] = block_records
        evidence_ids_by_block[block] = [record["evidence_id"] for record in block_records]

    return {
        "run_context": run_context,
        "retrieval_queries_used": retrieval_queries_used,
        "evidence_ids_by_block": evidence_ids_by_block,
        "evidence_by_block": evidence_by_block,
        "all_retrieved_evidence_ids": _dedupe_preserve_order(all_retrieved_evidence_ids),
        "phase1_search_queries_used": normalized_phase1_queries,
        "phase1_guidance_found": bool(normalized_phase1_queries),
    }


def _dispatch_search(retriever: BundleRetriever, search_type: str):
    if search_type == "text":
        return retriever.search_text
    if search_type == "tables":
        return retriever.search_tables
    if search_type == "figures":
        return retriever.search_figures
    raise ValueError(f"Unsupported search type: {search_type}")


def _block_query_entries(
    block: str,
    base_queries: list[tuple[str, str]],
    phase1_queries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for search_type, query in base_queries:
        key = ("base_plan", search_type, query)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "query_source": "base_plan",
                "search_type": search_type,
                "query": query,
            }
        )

    if not phase1_queries:
        return entries

    block_search_types = _dedupe_preserve_order([search_type for search_type, _ in base_queries])
    for phase1_query in phase1_queries:
        query_text = str(phase1_query.get("query_text", "")).strip()
        if not query_text:
            continue
        for search_type in _phase1_search_types_for_block(block_search_types, query_text):
            key = ("phase1_interpretation_map", search_type, query_text)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "query_source": "phase1_interpretation_map",
                    "search_type": search_type,
                    "query": query_text,
                    "phase1_query_id": phase1_query.get("query_id"),
                    "phase1_priority": phase1_query.get("priority"),
                }
            )
    return entries


def _phase1_search_types_for_block(block_search_types: list[str], query_text: str) -> list[str]:
    search_types: list[str] = []
    if "text" in block_search_types:
        search_types.append("text")
    if "tables" in block_search_types and _phase1_query_supports_tables(query_text):
        search_types.append("tables")
    if "figures" in block_search_types and _phase1_query_supports_figures(query_text):
        search_types.append("figures")
    return search_types


def _phase1_query_supports_tables(query_text: str) -> bool:
    normalized = query_text.lower()
    return any(cue in normalized for cue in PHASE1_TABLE_QUERY_CUES)


def _phase1_query_supports_figures(query_text: str) -> bool:
    normalized = query_text.lower()
    return any(cue in normalized for cue in PHASE1_FIGURE_QUERY_CUES)


def _normalize_phase1_search_queries(phase1_search_queries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not phase1_search_queries:
        return []
    normalized: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for query in phase1_search_queries:
        query_text = str(query.get("query_text", "")).strip()
        if not query_text or query_text in seen_texts:
            continue
        seen_texts.add(query_text)
        normalized.append(
            {
                "query_id": str(query.get("query_id", "")).strip() or None,
                "query_text": query_text,
                "priority": str(query.get("priority", "")).strip() or None,
                "why": str(query.get("why", "")).strip() or None,
            }
        )
    return normalized


def _build_prompt_record(result: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    source_payload = evidence.get("source_payload") or {}
    record = {
        "evidence_id": evidence["evidence_id"],
        "source_type": evidence["source_type"],
        "source_id": evidence["source_id"],
        "page_number": evidence["page_number"],
        "score": result["score"],
        "snippet": result["snippet"],
        "content": _summarize_evidence_content(evidence),
        "source_payload": _compact_source_payload(evidence["source_type"], source_payload),
    }
    return record


def _summarize_evidence_content(evidence: dict[str, Any]) -> str:
    return text_excerpt(evidence.get("text", ""), limit=700)


def _compact_source_payload(source_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if source_type == "table":
        rows = payload.get("rows", [])
        compact_rows = rows[:6] if isinstance(rows, list) else []
        return {
            "table_id": payload.get("table_id", ""),
            "caption": payload.get("caption", ""),
            "page_number": payload.get("page_number"),
            "rows": compact_rows,
            "structured": payload.get("structured", True),
        }
    if source_type == "figure":
        return {
            "figure_id": payload.get("figure_id", ""),
            "caption": payload.get("caption", ""),
            "context": text_excerpt(payload.get("context", ""), limit=350),
            "page_number": payload.get("page_number"),
        }
    if source_type == "section":
        return {
            "section_id": payload.get("section_id", ""),
            "title": payload.get("title", ""),
            "page_start": payload.get("page_start"),
            "page_end": payload.get("page_end"),
            "text_excerpt": text_excerpt(payload.get("text_excerpt", ""), limit=500),
        }
    return {
        "text": text_excerpt(payload.get("text", ""), limit=500),
        "metadata": payload.get("metadata", {}),
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
