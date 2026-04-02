from __future__ import annotations

from pathlib import Path
from typing import Any

from .bundle import load_run_paths
from .index import bm25_scores, faiss_scores, load_bm25_artifacts, load_faiss_artifacts
from .utils import read_json


class BundleRetriever:
    def __init__(self, run_dir: str | Path) -> None:
        self.run_paths = load_run_paths(Path(run_dir))
        self.evidence_items, self.bm25_stats = load_bm25_artifacts(self.run_paths.bm25_dir)
        _, self.faiss_index, self.embedding_backend = load_faiss_artifacts(self.run_paths.faiss_dir)
        self.item_by_id = {item["evidence_id"]: item for item in self.evidence_items}

    def search_text(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._hybrid_search(query, {"section", "chunk"}, top_k)

    def search_tables(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._hybrid_search(query, {"table"}, top_k)

    def search_figures(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._hybrid_search(query, {"figure"}, top_k)

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

    def _hybrid_search(
        self, query: str, allowed_types: set[str], top_k: int
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

        lexical_normalized = _normalize_scores(lexical)
        dense_normalized = _normalize_scores(dense)
        combined_ids = set(lexical_normalized) | set(dense_normalized)

        ranked: list[tuple[float, dict[str, Any]]] = []
        for evidence_id in combined_ids:
            item = self.item_by_id[evidence_id]
            score = 0.7 * lexical_normalized.get(evidence_id, 0.0) + 0.3 * dense_normalized.get(
                evidence_id, 0.0
            )
            ranked.append((score, item))

        ranked.sort(
            key=lambda entry: (
                entry[0],
                -(entry[1]["page_number"] or 0),
                entry[1]["source_id"],
            ),
            reverse=True,
        )

        results: list[dict[str, Any]] = []
        for score, item in ranked[:top_k]:
            results.append(
                {
                    "evidence_id": item["evidence_id"],
                    "source_type": item["source_type"],
                    "source_id": item["source_id"],
                    "page_number": item["page_number"],
                    "score": round(score, 6),
                    "snippet": item["snippet"],
                    "metadata": item["metadata"],
                }
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


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    maximum = max(scores.values())
    if maximum <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / maximum for key, value in scores.items()}


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
