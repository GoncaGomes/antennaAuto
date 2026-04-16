from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .bundle import load_run_paths
from .config import RetrievalConfig, load_index_config
from .index import bm25_scores, faiss_scores, load_bm25_artifacts, load_faiss_artifacts
from .utils import read_json, write_json

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


class BundleRetriever:
    def __init__(self, run_dir: str | Path, config: RetrievalConfig | None = None) -> None:
        self.run_paths = load_run_paths(Path(run_dir))
        if config is not None:
            self.config = config
        elif self.run_paths.index_config_path.exists():
            self.config = load_index_config(self.run_paths.index_config_path)
        else:
            self.config = RetrievalConfig()
        self.evidence_items, self.bm25_stats = load_bm25_artifacts(self.run_paths.bm25_dir)
        faiss_items, self.faiss_index, self.embedding_backend, self.embedding_meta = load_faiss_artifacts(
            self.run_paths.faiss_dir
        )
        self.item_by_id = {item["evidence_id"]: item for item in self.evidence_items}
        self.faiss_items = {item["evidence_id"]: item for item in faiss_items}

    def search_text(
        self,
        query: str,
        top_k: int = 5,
        diagnostics_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        return self._hybrid_search(query, {"section", "chunk"}, top_k, diagnostics_path)

    def search_tables(
        self,
        query: str,
        top_k: int = 5,
        diagnostics_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        return self._hybrid_search(query, {"table"}, top_k, diagnostics_path)

    def search_figures(
        self,
        query: str,
        top_k: int = 5,
        diagnostics_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        return self._hybrid_search(query, {"figure"}, top_k, diagnostics_path)

    def get_section(self, section_id: str) -> dict[str, Any] | None:
        for section in read_json(self.run_paths.sections_path):
            if section["section_id"] == section_id:
                return section
        return None

    def get_table(self, table_id: str) -> dict[str, Any] | None:
        json_path = self.run_paths.tables_dir / f"{table_id}.json"
        if json_path.exists():
            return read_json(json_path)

        artifact_dir = self.run_paths.tables_dir / table_id
        metadata_path = artifact_dir / "table.json"
        if metadata_path.exists():
            payload = read_json(metadata_path)
            payload["caption"] = _read_text_if_exists(artifact_dir / "caption.txt")
            payload["context"] = _read_text_if_exists(artifact_dir / "context.txt")
            return payload
        return None

    def get_figure(self, figure_id: str) -> dict[str, Any] | None:
        artifact_dir = self.run_paths.figures_dir / figure_id
        metadata_path = artifact_dir / "figure.json"
        if not metadata_path.exists():
            return None

        payload = read_json(metadata_path)
        payload["caption"] = _read_text_if_exists(artifact_dir / "caption.txt")
        payload["context"] = _read_text_if_exists(artifact_dir / "context.txt")
        payload["image_path"] = str(artifact_dir / "image.png")
        return payload

    def get_evidence_by_id(self, evidence_id: str) -> dict[str, Any] | None:
        item = self.item_by_id.get(evidence_id)
        if item is None:
            return None

        payload = {
            "evidence_id": item["evidence_id"],
            "source_type": item["source_type"],
            "source_id": item["source_id"],
            "page_number": item["page_number"],
            "text": item["text"],
            "metadata": item["metadata"],
        }

        if item["source_type"] == "section":
            payload["source_payload"] = self.get_section(item["source_id"])
        elif item["source_type"] == "table":
            payload["source_payload"] = self.get_table(item["source_id"])
        elif item["source_type"] == "figure":
            payload["source_payload"] = self.get_figure(item["source_id"])
        else:
            payload["source_payload"] = {"text": item["text"], "metadata": item["metadata"]}

        return payload

    def _hybrid_search(
        self,
        query: str,
        allowed_types: set[str],
        top_k: int,
        diagnostics_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        lexical = bm25_scores(self.evidence_items, self.bm25_stats, query, allowed_types=allowed_types)
        dense = faiss_scores(
            self.evidence_items,
            self.faiss_index,
            self.embedding_backend,
            query,
            allowed_types=allowed_types,
            top_k=top_k,
        )

        bm25_ranks = _rank_map(lexical)
        dense_ranks = _rank_map(dense)
        lexical_normalized = _normalize_scores(lexical)
        dense_normalized = _normalize_scores(dense)
        combined_ids = set(lexical) | set(dense)

        ranked: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
        for evidence_id in combined_ids:
            item = self.item_by_id[evidence_id]
            diagnostics = {
                "bm25_score": round(lexical.get(evidence_id, 0.0), 6),
                "dense_score": round(dense.get(evidence_id, 0.0), 6),
                "bm25_rank": bm25_ranks.get(evidence_id),
                "dense_rank": dense_ranks.get(evidence_id),
                "fusion_strategy": self.config.fusion_strategy,
                "chunking_mode": self.config.chunking_mode,
                "embedding_backend": self.embedding_meta["backend"],
            }

            if self.config.fusion_strategy == "weighted":
                final_score = (
                    self.config.weighted_alpha * lexical_normalized.get(evidence_id, 0.0)
                    + self.config.weighted_beta * dense_normalized.get(evidence_id, 0.0)
                )
                diagnostics["weighted_score"] = round(final_score, 6)
            elif self.config.fusion_strategy == "rrf":
                final_score = _rrf_component(
                    bm25_ranks.get(evidence_id), self.config.rrf_k
                ) + _rrf_component(dense_ranks.get(evidence_id), self.config.rrf_k)
                diagnostics["rrf_score"] = round(final_score, 6)
            else:
                raise ValueError(f"Unsupported fusion strategy: {self.config.fusion_strategy}")

            ranked.append((final_score, item, diagnostics))

        ranked.sort(
            key=lambda entry: (
                entry[0],
                -(entry[1]["page_number"] or 0),
                entry[1]["source_id"],
            ),
            reverse=True,
        )

        results: list[dict[str, Any]] = []
        for final_rank, (score, item, diagnostics) in enumerate(ranked[:top_k], start=1):
            diagnostics["final_rank"] = final_rank
            result = {
                "evidence_id": item["evidence_id"],
                "source_type": item["source_type"],
                "source_id": item["source_id"],
                "page_number": item["page_number"],
                "score": round(score, 6),
                "snippet": _query_snippet(item["text"], query),
                "metadata": item["metadata"],
                **diagnostics,
            }
            results.append(result)

        if diagnostics_path is not None:
            write_json(
                Path(diagnostics_path),
                {
                    "query": query,
                    "allowed_types": sorted(allowed_types),
                    "config": self.config.to_dict(),
                    "results": results,
                },
            )

        return results


def search_text(run_dir: str | Path, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return BundleRetriever(run_dir).search_text(query, top_k=top_k)


def search_tables(run_dir: str | Path, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return BundleRetriever(run_dir).search_tables(query, top_k=top_k)


def search_figures(run_dir: str | Path, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return BundleRetriever(run_dir).search_figures(query, top_k=top_k)


def get_section(run_dir: str | Path, section_id: str) -> dict[str, Any] | None:
    return BundleRetriever(run_dir).get_section(section_id)


def get_table(run_dir: str | Path, table_id: str) -> dict[str, Any] | None:
    return BundleRetriever(run_dir).get_table(table_id)


def get_figure(run_dir: str | Path, figure_id: str) -> dict[str, Any] | None:
    return BundleRetriever(run_dir).get_figure(figure_id)


def get_evidence_by_id(run_dir: str | Path, evidence_id: str) -> dict[str, Any] | None:
    return BundleRetriever(run_dir).get_evidence_by_id(evidence_id)


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    maximum = max(scores.values())
    if maximum <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / maximum for key, value in scores.items()}


def _rank_map(scores: dict[str, float]) -> dict[str, int]:
    ranked_ids = sorted(scores, key=lambda key: (scores[key], key), reverse=True)
    return {evidence_id: rank for rank, evidence_id in enumerate(ranked_ids, start=1)}


def _rrf_component(rank: int | None, rrf_k: int) -> float:
    if rank is None:
        return 0.0
    return 1.0 / (rrf_k + rank)


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _query_snippet(text: str, query: str, limit: int = 280) -> str:
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(text) if sentence.strip()]
    query_tokens = set(query.lower().split())
    if not sentences or not query_tokens:
        return text[:limit]

    matched_indexes = [
        index
        for index, sentence in enumerate(sentences)
        if any(token in sentence.lower() for token in query_tokens)
    ]
    if not matched_indexes:
        return text[:limit]

    selected_indexes = [matched_indexes[0]]
    if matched_indexes[-1] != matched_indexes[0]:
        selected_indexes.append(matched_indexes[-1])

    parts = [sentences[index] for index in selected_indexes]
    snippet = " ... ".join(parts)
    if len(snippet) <= limit:
        return snippet
    return snippet[:limit]
