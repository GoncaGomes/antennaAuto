from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from .bundle import RunPaths
from .utils import read_json, text_excerpt, write_json

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.%/-]*", re.IGNORECASE)


def index_run(run_paths: RunPaths) -> dict[str, Any]:
    evidence_items = build_evidence_items(run_paths)
    build_bm25_index(evidence_items, run_paths.bm25_dir)
    build_faiss_index(evidence_items, run_paths.faiss_dir)
    graph = build_graph(run_paths, evidence_items)
    write_json(run_paths.graph_path, graph)

    source_counts = Counter(item["source_type"] for item in evidence_items)
    report = {
        "status": "completed",
        "evidence_item_count": len(evidence_items),
        "source_counts": dict(sorted(source_counts.items())),
        "graph_node_count": len(graph["nodes"]),
        "graph_edge_count": len(graph["edges"]),
        "bm25_dir": str(run_paths.bm25_dir),
        "faiss_dir": str(run_paths.faiss_dir),
        "graph_path": str(run_paths.graph_path),
    }
    write_json(run_paths.index_report_path, report)
    return report


def build_evidence_items(run_paths: RunPaths) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    items.extend(_build_section_items(run_paths.sections_path))
    items.extend(_build_table_items(run_paths.tables_dir))
    items.extend(_build_figure_items(run_paths.figures_dir))
    items.extend(_build_chunk_items(run_paths.fulltext_path))
    items.sort(
        key=lambda item: (
            item["source_type"],
            item["page_number"] if item["page_number"] is not None else 10**9,
            item["source_id"],
        )
    )
    return items


def build_bm25_index(evidence_items: list[dict[str, Any]], output_dir: Path) -> None:
    tokenized_docs = [tokenize_text(item["text"]) for item in evidence_items]
    document_lengths = {item["evidence_id"]: len(tokens) for item, tokens in zip(evidence_items, tokenized_docs)}
    avg_doc_length = (
        sum(document_lengths.values()) / len(document_lengths) if document_lengths else 0.0
    )

    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_docs:
        document_frequency.update(set(tokens))

    total_documents = len(evidence_items)
    idf = {
        token: math.log(1 + (total_documents - freq + 0.5) / (freq + 0.5))
        for token, freq in sorted(document_frequency.items())
    }

    write_json(output_dir / "evidence_items.json", evidence_items)
    write_json(
        output_dir / "bm25_stats.json",
        {
            "backend": "bm25_okapi_v1",
            "k1": 1.5,
            "b": 0.75,
            "avg_doc_length": avg_doc_length,
            "doc_lengths": document_lengths,
            "idf": idf,
        },
    )


def build_faiss_index(evidence_items: list[dict[str, Any]], output_dir: Path) -> None:
    backend = HashEmbeddingBackend()
    vectors = backend.encode_many(item["text"] for item in evidence_items)
    index = faiss.IndexFlatIP(backend.dim)
    if len(vectors) > 0:
        index.add(vectors)

    faiss.write_index(index, str(output_dir / "index.faiss"))
    write_json(output_dir / "evidence_items.json", evidence_items)
    write_json(
        output_dir / "embedding_meta.json",
        {
            "backend": backend.name,
            "dim": backend.dim,
        },
    )


def build_graph(run_paths: RunPaths, evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    section_nodes_by_page: dict[int, str] = {}

    for item in evidence_items:
        source_node_id = f"{item['source_type']}:{item['source_id']}"
        nodes.append(
            {
                "id": source_node_id,
                "type": item["source_type"],
                "source_id": item["source_id"],
                "page_number": item["page_number"],
            }
        )

        if item["source_type"] == "section":
            page_start = item["metadata"]["page_start"]
            page_end = item["metadata"]["page_end"]
            for page_number in range(page_start, page_end + 1):
                section_nodes_by_page[page_number] = source_node_id

        if item["source_type"] == "table":
            caption_node_id = f"{source_node_id}:caption"
            content_node_id = f"{source_node_id}:content"
            nodes.append({"id": caption_node_id, "type": "table_caption"})
            nodes.append({"id": content_node_id, "type": "table_content"})
            edges.append({"source": source_node_id, "target": caption_node_id, "relation": "has_caption"})
            edges.append({"source": source_node_id, "target": content_node_id, "relation": "has_content"})

        if item["source_type"] == "figure":
            caption_node_id = f"{source_node_id}:caption"
            context_node_id = f"{source_node_id}:context"
            nodes.append({"id": caption_node_id, "type": "figure_caption"})
            nodes.append({"id": context_node_id, "type": "figure_context"})
            edges.append({"source": source_node_id, "target": caption_node_id, "relation": "has_caption"})
            edges.append({"source": source_node_id, "target": context_node_id, "relation": "has_context"})

    for item in evidence_items:
        if item["source_type"] not in {"table", "figure"}:
            continue
        page_number = item["page_number"]
        if page_number is None:
            continue
        section_node_id = section_nodes_by_page.get(page_number)
        if section_node_id is None:
            continue
        edges.append(
            {
                "source": section_node_id,
                "target": f"{item['source_type']}:{item['source_id']}",
                "relation": f"has_{item['source_type']}",
            }
        )

    return {"nodes": nodes, "edges": edges}


def load_bm25_artifacts(index_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence_items = read_json(index_dir / "evidence_items.json")
    stats = read_json(index_dir / "bm25_stats.json")
    return evidence_items, stats


def bm25_scores(
    evidence_items: list[dict[str, Any]],
    stats: dict[str, Any],
    query: str,
    allowed_types: set[str] | None = None,
) -> dict[str, float]:
    query_tokens = tokenize_text(query)
    if not query_tokens:
        return {}

    k1 = float(stats["k1"])
    b = float(stats["b"])
    avg_doc_length = float(stats["avg_doc_length"]) or 1.0
    idf = {token: float(value) for token, value in stats["idf"].items()}
    scores: dict[str, float] = {}

    for item in evidence_items:
        if allowed_types is not None and item["source_type"] not in allowed_types:
            continue
        tokens = tokenize_text(item["text"])
        if not tokens:
            continue
        term_frequencies = Counter(tokens)
        doc_length = len(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = term_frequencies.get(token, 0)
            if frequency == 0:
                continue
            numerator = frequency * (k1 + 1.0)
            denominator = frequency + k1 * (1.0 - b + b * doc_length / avg_doc_length)
            score += idf.get(token, 0.0) * numerator / denominator
        if score > 0:
            scores[item["evidence_id"]] = score

    return scores


def load_faiss_artifacts(index_dir: Path) -> tuple[list[dict[str, Any]], faiss.Index, "HashEmbeddingBackend"]:
    evidence_items = read_json(index_dir / "evidence_items.json")
    meta = read_json(index_dir / "embedding_meta.json")
    index = faiss.read_index(str(index_dir / "index.faiss"))
    backend = HashEmbeddingBackend(dim=int(meta["dim"]))
    return evidence_items, index, backend


def faiss_scores(
    evidence_items: list[dict[str, Any]],
    index: faiss.Index,
    backend: "HashEmbeddingBackend",
    query: str,
    allowed_types: set[str] | None = None,
    top_k: int = 10,
) -> dict[str, float]:
    if index.ntotal == 0:
        return {}

    query_vector = backend.encode(query)
    candidate_count = min(index.ntotal, max(top_k * 5, 20))
    scores, indices = index.search(query_vector[np.newaxis, :], candidate_count)
    results: dict[str, float] = {}
    for score, idx in zip(scores[0], indices[0], strict=False):
        if idx < 0:
            continue
        item = evidence_items[int(idx)]
        if allowed_types is not None and item["source_type"] not in allowed_types:
            continue
        if score <= 0:
            continue
        results[item["evidence_id"]] = float(score)
    return results


def tokenize_text(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


class HashEmbeddingBackend:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.name = "hash_embedding_v1"

    def encode_many(self, texts: Any) -> np.ndarray:
        vectors = [self.encode(text) for text in texts]
        if not vectors:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack(vectors).astype(np.float32)

    def encode(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dim, dtype=np.float32)
        for token in tokenize_text(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector


def _build_section_items(sections_path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in read_json(sections_path):
        text = "\n".join(part for part in [section["title"], section["text_excerpt"]] if part)
        items.append(
            _make_evidence_item(
                source_type="section",
                source_id=section["section_id"],
                page_number=section["page_start"],
                text=text,
                metadata=section,
            )
        )
    return items


def _build_table_items(tables_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_table_ids: set[str] = set()

    for path in sorted(tables_dir.glob("table_*.json")):
        table = read_json(path)
        rows = table.get("rows", [])
        row_lines = [" | ".join(row) for row in rows]
        text = "\n".join([table.get("caption", ""), *row_lines]).strip()
        table_id = table["table_id"]
        seen_table_ids.add(table_id)
        items.append(
            _make_evidence_item(
                source_type="table",
                source_id=table_id,
                page_number=table.get("page_number"),
                text=text,
                metadata={
                    "caption": table.get("caption"),
                    "structured": True,
                    "row_count": len(rows),
                    "extraction_method": table.get("extraction_method"),
                },
            )
        )

    for path in sorted(tables_dir.glob("table_*")):
        if not path.is_dir():
            continue
        metadata_path = path / "table.json"
        if not metadata_path.exists():
            continue
        metadata = read_json(metadata_path)
        table_id = metadata["table_id"]
        if table_id in seen_table_ids:
            continue
        caption = _read_text_if_exists(path / "caption.txt")
        context = _read_text_if_exists(path / "context.txt")
        items.append(
            _make_evidence_item(
                source_type="table",
                source_id=table_id,
                page_number=metadata.get("page_number"),
                text="\n".join(part for part in [caption, context] if part),
                metadata={
                    "caption": caption,
                    "structured": False,
                    "artifact_dir": str(path),
                },
            )
        )

    return items


def _build_figure_items(figures_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for figure_dir in sorted(figures_dir.glob("fig_*")):
        if not figure_dir.is_dir():
            continue
        metadata = read_json(figure_dir / "figure.json") if (figure_dir / "figure.json").exists() else {}
        caption = _read_text_if_exists(figure_dir / "caption.txt")
        context = _read_text_if_exists(figure_dir / "context.txt")
        text = "\n".join(part for part in [caption, context] if part).strip()
        items.append(
            _make_evidence_item(
                source_type="figure",
                source_id=metadata.get("figure_id", figure_dir.name),
                page_number=metadata.get("page_number"),
                text=text,
                metadata={
                    "caption": caption,
                    "context": context,
                    "artifact_dir": str(figure_dir),
                },
            )
        )
    return items


def _build_chunk_items(fulltext_path: Path) -> list[dict[str, Any]]:
    markdown = fulltext_path.read_text(encoding="utf-8") if fulltext_path.exists() else ""
    paragraphs = [_clean_paragraph(paragraph) for paragraph in markdown.split("\n\n")]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) >= 80]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        if current and current_length + len(paragraph) > 800:
            chunks.append("\n\n".join(current))
            current = []
            current_length = 0
        current.append(paragraph)
        current_length += len(paragraph)
    if current:
        chunks.append("\n\n".join(current))

    items: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_id = f"chunk_{index:03d}"
        items.append(
            _make_evidence_item(
                source_type="chunk",
                source_id=chunk_id,
                page_number=None,
                text=chunk,
                metadata={"chunk_id": chunk_id},
            )
        )
    return items


def _make_evidence_item(
    source_type: str,
    source_id: str,
    page_number: int | None,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_id": f"{source_type}:{source_id}",
        "source_type": source_type,
        "source_id": source_id,
        "page_number": page_number,
        "text": text,
        "snippet": text_excerpt(text, limit=240),
        "metadata": metadata,
    }


def _clean_paragraph(text: str) -> str:
    return " ".join(text.split())


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
