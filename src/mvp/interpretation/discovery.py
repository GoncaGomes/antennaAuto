from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..bundle import load_run_paths
from ..retrieval import BundleRetriever
from ..schemas.paper_map import PaperMap
from ..utils import read_json, text_excerpt

TITLE_NOISE_PATTERNS = (
    "paper open access",
    "you may also like",
    "journal of",
    "conference series",
    "published under licence",
)
DESIGN_SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "proposed": re.compile(r"\bproposed\b", re.IGNORECASE),
    "final": re.compile(r"\bfinal\b", re.IGNORECASE),
    "optimized": re.compile(r"\boptim(?:ized|ised)\b", re.IGNORECASE),
    "fabricated": re.compile(r"\bfabricat(?:ed|ion)\b", re.IGNORECASE),
    "measured": re.compile(r"\bmeasur(?:ed|ement|ements)\b", re.IGNORECASE),
    "simulated": re.compile(r"\bsimulat(?:ed|ion|ions)\b", re.IGNORECASE),
}
DESIGN_MENTION_PATTERNS: tuple[tuple[str, int], ...] = (
    ("proposed antenna", 8),
    ("proposed design", 8),
    ("final design", 8),
    ("optimized design", 8),
    ("selected design", 7),
    ("fabricated prototype", 7),
    ("measured results", 6),
    ("configuration", 3),
    ("simulated results", 3),
)
DISCOVERY_QUERY_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "proposal",
        (
            "proposed antenna",
            "proposed design",
            "antenna configuration",
        ),
    ),
    (
        "final",
        (
            "final design",
            "selected design",
            "optimized design",
            "fabricated prototype",
            "measured prototype",
        ),
    ),
    (
        "variants",
        (
            "design steps",
            "design variants",
            "reference antenna",
            "modified design",
        ),
    ),
)
DISCOVERY_TOP_K = 5
DISCOVERY_MAX_TOTAL = 9
DISCOVERY_MAX_PER_BUCKET: dict[str, int] = {
    "proposal": 3,
    "final": 3,
    "variants": 3,
}
TABLE_ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("comparison", "comparison"),
    ("material", "materials"),
    ("substrate", "materials"),
    ("dielectric", "materials"),
    ("result", "results"),
    ("gain", "results"),
    ("bandwidth", "results"),
    ("return loss", "results"),
    ("vswr", "results"),
    ("s11", "results"),
    ("parameter", "parameters"),
    ("dimension", "dimensions"),
    ("geometry", "dimensions"),
)
FIGURE_ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("fabricated", "fabricated"),
    ("prototype", "fabricated"),
    ("photo", "fabricated"),
    ("measurement", "measurement"),
    ("measured", "measurement"),
    ("s11", "measurement"),
    ("return loss", "measurement"),
    ("vswr", "measurement"),
    ("radiation", "radiation"),
    ("pattern", "radiation"),
    ("geometry", "geometry"),
    ("layout", "layout"),
    ("top view", "layout"),
    ("bottom view", "layout"),
)


def build_paper_map(run_dir: str | Path) -> PaperMap:
    """Build a deterministic lightweight paper map from existing bundle/index artifacts."""

    run_paths = load_run_paths(Path(run_dir))
    _validate_phase1_inputs(run_paths)

    metadata = read_json(run_paths.metadata_path)
    sections = read_json(run_paths.sections_path)
    parse_report = read_json(run_paths.parse_report_path) if run_paths.parse_report_path.exists() else {}
    fulltext = run_paths.fulltext_path.read_text(encoding="utf-8")
    evidence_items = read_json(run_paths.bm25_dir / "evidence_items.json")
    retriever = BundleRetriever(run_paths.run_dir)

    payload = {
        "title": _extract_title(metadata, fulltext, evidence_items),
        "abstract": _extract_abstract(fulltext, evidence_items),
        "section_headings_top_level": _extract_top_level_headings(fulltext, sections),
        "key_design_signals": _aggregate_design_signals(fulltext),
        "candidate_design_mentions": _select_candidate_design_mentions(run_paths.run_dir, retriever, evidence_items),
        "key_table_refs": _select_key_table_refs(parse_report),
        "key_figure_refs": _select_key_figure_refs(evidence_items),
    }
    return PaperMap.model_validate(payload)


def _validate_phase1_inputs(run_paths) -> None:
    required_paths = [
        run_paths.metadata_path,
        run_paths.fulltext_path,
        run_paths.sections_path,
        run_paths.bm25_dir / "evidence_items.json",
    ]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError("Run directory is not fully prepared for Phase 1. Missing required files: " + missing)


def _extract_title(metadata: dict[str, Any], fulltext: str, evidence_items: list[dict[str, Any]]) -> str:
    pdf_metadata = metadata.get("pdf_metadata") or {}
    pdf_title = " ".join(str(pdf_metadata.get("title", "")).split())
    if _looks_like_title(pdf_title):
        return pdf_title

    for heading in _markdown_headings(fulltext):
        if _looks_like_title(heading):
            return heading

    for item in evidence_items:
        if item.get("source_type") != "chunk":
            continue
        snippet = _clean_text(str(item.get("snippet", "")))
        if _looks_like_title(snippet):
            return snippet

    return metadata.get("original_filename", "unknown document")


def _extract_abstract(fulltext: str, evidence_items: list[dict[str, Any]]) -> str | None:
    fulltext_clean = fulltext.replace("\r\n", "\n")
    pattern = re.compile(
        r"(?is)\babstract\b[:.\s]*(.{40,1800}?)(?:\n\s*##|\n\s*[1-9][0-9]?[.)]\s+|\n\s*keywords\b|$)"
    )
    match = pattern.search(fulltext_clean)
    if match:
        candidate = _clean_text(match.group(1))
        if len(candidate) >= 40:
            return text_excerpt(candidate, limit=800)

    for item in evidence_items:
        if item.get("source_type") not in {"chunk", "section"}:
            continue
        text = _clean_text(str(item.get("text", "")))
        lowered = text.lower()
        if "abstract" not in lowered:
            continue
        abstract_text = re.sub(r"(?is)^.*?\babstract\b[:.\s]*", "", text).strip()
        if len(abstract_text) >= 40:
            return text_excerpt(abstract_text, limit=800)
    return None


def _extract_top_level_headings(fulltext: str, sections: list[dict[str, Any]]) -> list[str]:
    headings = [heading for heading in _markdown_headings(fulltext) if _is_major_heading(heading)]
    if headings:
        return headings[:10]

    fallback: list[str] = []
    seen: set[str] = set()
    for section in sections:
        title = _clean_text(str(section.get("title", "")))
        if not _is_major_heading(title):
            continue
        lowered = title.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        fallback.append(title)
        if len(fallback) >= 10:
            break
    return fallback


def _aggregate_design_signals(fulltext: str) -> dict[str, int]:
    lowered = fulltext.lower()
    return {
        signal: len(pattern.findall(lowered))
        for signal, pattern in DESIGN_SIGNAL_PATTERNS.items()
    }


def _select_candidate_design_mentions(
    run_dir: Path,
    retriever: BundleRetriever,
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    retriever = _configure_discovery_retriever(retriever)
    bucket_candidates: dict[str, dict[str, dict[str, Any]]] = {
        bucket: {} for bucket, _ in DISCOVERY_QUERY_BUCKETS
    }

    for bucket, queries in DISCOVERY_QUERY_BUCKETS:
        for query in queries:
            results = retriever.search_text(query, top_k=DISCOVERY_TOP_K)
            for result in results:
                candidate = _candidate_design_mention_from_result(retriever, result, bucket=bucket)
                if candidate is None:
                    continue
                _merge_bucket_candidate(bucket_candidates[bucket], candidate, query=query)

    selected: list[dict[str, Any]] = []
    seen_evidence_ids: set[str] = set()
    seen_signatures: set[str] = set()
    for bucket, _queries in DISCOVERY_QUERY_BUCKETS:
        max_items = DISCOVERY_MAX_PER_BUCKET.get(bucket, 1)
        bucket_selected = _select_bucket_candidates(bucket_candidates[bucket], max_items=max_items)
        for candidate in bucket_selected:
            evidence_id = candidate.get("evidence_id")
            signature = _snippet_signature(str(candidate.get("text", "")))
            if evidence_id in seen_evidence_ids or signature in seen_signatures:
                continue
            if evidence_id:
                seen_evidence_ids.add(evidence_id)
            seen_signatures.add(signature)
            selected.append(candidate)
            if len(selected) >= DISCOVERY_MAX_TOTAL:
                return selected

    if selected:
        return selected

    fallback_candidates = _fallback_candidate_design_mentions(evidence_items)
    for candidate in fallback_candidates:
        evidence_id = candidate.get("evidence_id")
        signature = _snippet_signature(str(candidate.get("text", "")))
        if evidence_id in seen_evidence_ids or signature in seen_signatures:
            continue
        if evidence_id:
            seen_evidence_ids.add(evidence_id)
        seen_signatures.add(signature)
        selected.append(candidate)
        if len(selected) >= DISCOVERY_MAX_TOTAL:
            break
    return selected


def _configure_discovery_retriever(retriever: BundleRetriever) -> BundleRetriever:
    if hasattr(retriever, "config"):
        retriever.config = replace(retriever.config, fusion_strategy="rrf")
    return retriever


def _merge_bucket_candidate(
    bucket_candidates: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
    *,
    query: str,
) -> None:
    evidence_id = str(candidate.get("evidence_id", "")).strip()
    signature = _snippet_signature(str(candidate.get("text", "")))
    if not evidence_id and not signature:
        return

    candidate_key = evidence_id
    if candidate_key and candidate_key in bucket_candidates:
        existing = bucket_candidates[candidate_key]
    else:
        existing = next(
            (item for item in bucket_candidates.values() if item.get("_signature") == signature),
            None,
        )
        if existing is None:
            candidate_key = evidence_id or signature

    page_number = candidate.get("page_number")
    if not isinstance(page_number, int):
        page_number = None
    score = float(candidate.get("score", 0.0))

    if existing is None:
        bucket_candidates[candidate_key] = {
            "text": candidate.get("text", ""),
            "page_number": page_number,
            "evidence_id": evidence_id or None,
            "_score": score,
            "_matched_queries": {query},
            "_signature": signature,
        }
        return

    existing["_score"] = max(float(existing.get("_score", 0.0)), score)
    existing["_matched_queries"].add(query)
    if not existing.get("text") and candidate.get("text"):
        existing["text"] = candidate.get("text", "")
    if existing.get("page_number") is None and page_number is not None:
        existing["page_number"] = page_number
    if not existing.get("evidence_id") and evidence_id:
        existing["evidence_id"] = evidence_id


def _select_bucket_candidates(
    bucket_candidates: dict[str, dict[str, Any]],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        bucket_candidates.values(),
        key=lambda item: (
            -float(item.get("_score", 0.0)),
            str(item.get("evidence_id", "")),
        ),
    )
    return [
        {
            "text": item["text"],
            "page_number": item["page_number"],
            "evidence_id": item["evidence_id"],
        }
        for item in ranked[:max_items]
    ]


def _candidate_design_mention_from_result(
    retriever: BundleRetriever,
    result: dict[str, Any],
    *,
    bucket: str,
) -> dict[str, Any] | None:
    evidence_id = str(result.get("evidence_id", "")).strip()
    if not evidence_id:
        return None
    evidence = retriever.get_evidence_by_id(evidence_id) or {}
    text = _extract_candidate_text(evidence, result)
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if any(term in lowered for term in ("references", "related work", "you may also like")):
        return None
    if _looks_like_reference_snippet(cleaned):
        return None
    return {
        "text": text_excerpt(cleaned, limit=220),
        "page_number": result.get("page_number") if isinstance(result.get("page_number"), int) else None,
        "evidence_id": evidence_id,
        "score": float(result.get("score", 0.0)),
    }


def _fallback_candidate_design_mentions(evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in evidence_items:
        if item.get("source_type") not in {"chunk", "section"}:
            continue
        text = _clean_text(str(item.get("text", "") or item.get("snippet", "")))
        if not text:
            continue
        score = 0.0
        lowered = text.lower()
        for phrase, weight in DESIGN_MENTION_PATTERNS:
            if phrase in lowered:
                score += weight
        if any(term in lowered for term in ("design", "antenna", "prototype", "variant", "configuration")):
            score += 1.0
        if any(term in lowered for term in ("references", "related work", "you may also like")):
            score -= 6.0
        page_number = item.get("page_number")
        if isinstance(page_number, int) and page_number <= 3:
            score += 0.75
        if item.get("source_type") == "chunk":
            score += 0.25
        if score <= 0:
            continue
        candidates.append(
            {
                "score": score,
                "text": text_excerpt(text, limit=220),
                "page_number": page_number if isinstance(page_number, int) else None,
                "evidence_id": item.get("evidence_id"),
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["page_number"] or 9999, item["evidence_id"] or ""))
    return [
        {
            "text": item["text"],
            "page_number": item["page_number"],
            "evidence_id": item["evidence_id"],
        }
        for item in candidates
    ]


def _extract_candidate_text(evidence: dict[str, Any], result: dict[str, Any]) -> str:
    source_type = str(evidence.get("source_type") or result.get("source_type") or "")
    if source_type in {"chunk", "section"}:
        text = str(evidence.get("text", "")).strip()
        if text:
            return text
    return str(result.get("snippet", "")).strip()


def _snippet_signature(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _looks_like_reference_snippet(text: str) -> bool:
    bracketed_refs = len(re.findall(r"\[\d+\]", text))
    year_mentions = len(re.findall(r"\b(?:19|20)\d{2}\b", text))
    lowered = text.lower()
    if bracketed_refs >= 2:
        return True
    if text.lstrip().startswith("- ["):
        return True
    if year_mentions >= 3 and bracketed_refs >= 1:
        return True
    if re.match(r"^\s*\d+\.\s+[A-Z][A-Za-z\-']+", text) and year_mentions >= 1:
        if any(term in lowered for term in ("int. j.", "proc.", "vol.", "pp.", "doi", "technol.")):
            return True
    return False


def _looks_like_organization_snippet(text: str) -> bool:
    lowered = text.lower()
    if "structured as follows" in lowered or "organized as follows" in lowered:
        return True
    if "section 2" in lowered and "section 3" in lowered:
        return True
    return False


def _has_bucket_scope_signal(text: str, bucket: str) -> bool:
    terms = DISCOVERY_BUCKET_TERMS.get(bucket, ())
    if any(term in text for term in terms):
        return True
    return "design" in text and "antenna" in text


def _select_key_table_refs(parse_report: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = list(parse_report.get("table_summaries", []))
    scored: list[dict[str, Any]] = []
    for summary in summaries:
        caption = _clean_text(str(summary.get("caption", "")))
        role = _guess_table_role(caption)
        score = float(summary.get("parse_score", 0.0))
        if role in {"dimensions", "parameters", "materials"}:
            score += 15.0
        elif role == "results":
            score += 8.0
        elif role == "comparison":
            score -= 5.0
        scored.append(
            {
                "score": score,
                "table_id": summary.get("table_id", ""),
                "caption": caption,
                "page_number": summary.get("page_number"),
                "table_role_guess": role,
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["page_number"] or 9999, item["table_id"]))
    return [
        {
            "table_id": item["table_id"],
            "caption": item["caption"],
            "page_number": item["page_number"],
            "table_role_guess": item["table_role_guess"],
        }
        for item in scored[:5]
        if item["table_id"] and item["caption"]
    ]


def _select_key_figure_refs(evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in evidence_items:
        if item.get("source_type") != "figure":
            continue
        metadata = item.get("metadata") or {}
        caption = _clean_text(str(metadata.get("caption", "")).strip())
        context = _clean_text(str(metadata.get("context", "")).strip())
        display_caption = caption if caption and caption.lower() != "caption extraction not implemented." else context
        if not display_caption:
            continue
        role = _guess_figure_role(f"{caption} {context}")
        score = 0.0
        if role != "unknown":
            score += 5.0
        page_number = item.get("page_number")
        if isinstance(page_number, int) and page_number <= 4:
            score += 1.0
        refs.append(
            {
                "score": score,
                "figure_id": item.get("source_id", ""),
                "caption": text_excerpt(display_caption, limit=180),
                "page_number": page_number if isinstance(page_number, int) else None,
                "figure_role_guess": role,
            }
        )

    refs.sort(key=lambda item: (-item["score"], item["page_number"] or 9999, item["figure_id"]))
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in refs:
        if item["figure_id"] in seen_ids:
            continue
        seen_ids.add(item["figure_id"])
        selected.append(
            {
                "figure_id": item["figure_id"],
                "caption": item["caption"],
                "page_number": item["page_number"],
                "figure_role_guess": item["figure_role_guess"],
            }
        )
        if len(selected) >= 5:
            break
    return selected


def _markdown_headings(fulltext: str) -> list[str]:
    headings: list[str] = []
    seen: set[str] = set()
    for raw_line in fulltext.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        cleaned = _clean_text(re.sub(r"^#+\s*", "", line))
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        headings.append(cleaned)
    return headings


def _looks_like_title(value: str) -> bool:
    cleaned = _clean_text(value)
    if len(cleaned) < 12:
        return False
    lowered = cleaned.lower()
    if any(noise in lowered for noise in TITLE_NOISE_PATTERNS):
        return False
    return True


def _is_major_heading(value: str) -> bool:
    cleaned = _clean_text(value)
    if len(cleaned) < 3:
        return False
    lowered = cleaned.lower()
    if any(noise in lowered for noise in TITLE_NOISE_PATTERNS):
        return False
    if lowered in {"abstract", "references", "keywords"}:
        return True
    return len(cleaned.split()) <= 12


def _guess_table_role(caption: str) -> str:
    lowered = caption.lower()
    for term, role in TABLE_ROLE_PATTERNS:
        if term in lowered:
            return role
    return "unknown"


def _guess_figure_role(text: str) -> str:
    lowered = text.lower()
    for term, role in FIGURE_ROLE_PATTERNS:
        if term in lowered:
            return role
    return "unknown"


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"\*+", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
