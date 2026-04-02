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
from .config import RetrievalConfig, load_index_config, save_index_config
from .utils import read_json, text_excerpt, utc_timestamp, write_json

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.%/-]*", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def index_run(run_paths: RunPaths, config: RetrievalConfig | None = None) -> dict[str, Any]:
    resolved_config = config or RetrievalConfig()
    save_index_config(run_paths.index_config_path, resolved_config)

    evidence_items = build_evidence_items(run_paths, resolved_config)
    build_bm25_index(evidence_items, run_paths.bm25_dir)
    build_faiss_index(evidence_items, run_paths.faiss_dir, resolved_config)
    graph = build_graph(evidence_items)
    write_json(run_paths.graph_path, graph)

    source_counts = Counter(item["source_type"] for item in evidence_items)
    report = {
        "status": "completed",
        "config": resolved_config.to_dict(),
        "evidence_item_count": len(evidence_items),
        "source_counts": dict(sorted(source_counts.items())),
        "graph_node_count": len(graph["nodes"]),
        "graph_edge_count": len(graph["edges"]),
        "bm25_dir": str(run_paths.bm25_dir),
        "faiss_dir": str(run_paths.faiss_dir),
        "graph_path": str(run_paths.graph_path),
        "index_config_path": str(run_paths.index_config_path),
    }
    write_json(run_paths.index_report_path, report)
    return report


def build_evidence_items(run_paths: RunPaths, config: RetrievalConfig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    items.extend(_build_section_items(run_paths.sections_path))
    items.extend(_build_table_items(run_paths.tables_dir))
    items.extend(_build_figure_items(run_paths.figures_dir))
    items.extend(_build_chunk_items(run_paths.fulltext_path, run_paths.sections_path, config))
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


def build_faiss_index(
    evidence_items: list[dict[str, Any]], output_dir: Path, config: RetrievalConfig
) -> None:
    backend = _make_embedding_backend(config)
    vectors = backend.encode_many(item["text"] for item in evidence_items)
    index = faiss.IndexFlatIP(backend.dim)
    if len(vectors) > 0:
        index.add(vectors)

    faiss.write_index(index, str(output_dir / "index.faiss"))
    write_json(output_dir / "evidence_items.json", evidence_items)
    write_json(
        output_dir / "embedding_meta.json",
        {
            "backend": backend.backend_name,
            "model_name": backend.model_name,
            "dim": backend.dim,
            "index_build_timestamp_utc": utc_timestamp(),
        },
    )


def build_graph(evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
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


def load_faiss_artifacts(index_dir: Path) -> tuple[list[dict[str, Any]], faiss.Index, Any, dict[str, Any]]:
    evidence_items = read_json(index_dir / "evidence_items.json")
    meta = read_json(index_dir / "embedding_meta.json")
    index = faiss.read_index(str(index_dir / "index.faiss"))
    backend = _make_embedding_backend_from_meta(meta)
    return evidence_items, index, backend, meta


def faiss_scores(
    evidence_items: list[dict[str, Any]],
    index: faiss.Index,
    backend: Any,
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
    def __init__(self, dim: int = 256, model_name: str = "hash_embedding_v1") -> None:
        self.dim = dim
        self.backend_name = "hash"
        self.model_name = model_name

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


class SentenceTransformerEmbeddingBackend:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "sentence-transformers is required for embedding_backend='sentence_transformer'"
            ) from exc

        self.model = SentenceTransformer(model_name)
        self.dim = int(self.model.get_sentence_embedding_dimension())
        self.backend_name = "sentence_transformer"
        self.model_name = model_name

    def encode_many(self, texts: Any) -> np.ndarray:
        text_list = list(texts)
        if not text_list:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = self.model.encode(
            text_list,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode(self, text: str) -> np.ndarray:
        vector = self.model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return np.asarray(vector, dtype=np.float32)


def _make_embedding_backend(config: RetrievalConfig) -> Any:
    if config.embedding_backend == "hash":
        return HashEmbeddingBackend()
    if config.embedding_backend == "sentence_transformer":
        return SentenceTransformerEmbeddingBackend(config.embedding_model_name)
    raise ValueError(f"Unsupported embedding backend: {config.embedding_backend}")


def _make_embedding_backend_from_meta(meta: dict[str, Any]) -> Any:
    backend_name = meta["backend"]
    model_name = meta.get("model_name", "")
    if backend_name == "hash":
        return HashEmbeddingBackend(dim=int(meta["dim"]), model_name=model_name or "hash_embedding_v1")
    if backend_name == "sentence_transformer":
        return SentenceTransformerEmbeddingBackend(model_name)
    raise ValueError(f"Unsupported embedding backend in metadata: {backend_name}")


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


def _build_chunk_items(
    fulltext_path: Path, sections_path: Path, config: RetrievalConfig
) -> list[dict[str, Any]]:
    markdown = fulltext_path.read_text(encoding="utf-8") if fulltext_path.exists() else ""
    if not markdown.strip():
        return []

    raw_paragraphs = [_clean_block(paragraph) for paragraph in markdown.split("\n\n")]
    raw_paragraphs = [paragraph for paragraph in raw_paragraphs if paragraph]
    sections = read_json(sections_path) if sections_path.exists() else []

    if config.chunking_mode == "fixed":
        chunk_records = _fixed_chunk_records(raw_paragraphs, config)
    elif config.chunking_mode == "paragraph":
        chunk_records = _paragraph_chunk_records(raw_paragraphs, config)
    else:
        raise ValueError(f"Unsupported chunking mode: {config.chunking_mode}")

    items: list[dict[str, Any]] = []
    for index, record in enumerate(chunk_records, start=1):
        chunk_id = f"chunk_{index:03d}"
        page_number = _recover_page_number(record["text"], sections)
        metadata = {
            "chunk_id": chunk_id,
            "paragraph_id": record.get("paragraph_id"),
            "paragraph_index": record.get("paragraph_index"),
            "chunk_index_within_paragraph": record.get("chunk_index_within_paragraph"),
            "source": "fulltext.md",
            "chunking_mode": config.chunking_mode,
        }
        if record.get("char_start") is not None:
            metadata["char_start"] = record["char_start"]
        if record.get("char_end") is not None:
            metadata["char_end"] = record["char_end"]

        items.append(
            _make_evidence_item(
                source_type="chunk",
                source_id=chunk_id,
                page_number=page_number,
                text=record["text"],
                metadata=metadata,
            )
        )
    return items


def _fixed_chunk_records(
    paragraphs: list[str], config: RetrievalConfig
) -> list[dict[str, Any]]:
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) >= 80]
    if not paragraphs:
        return []

    chunk_records: list[dict[str, Any]] = []
    current_parts: list[str] = []
    current_length = 0
    chunk_index = 1
    for paragraph in paragraphs:
        if current_parts and current_length + len(paragraph) > config.paragraph_max_chars:
            text = "\n\n".join(current_parts)
            chunk_records.append(
                {
                    "text": text,
                    "paragraph_id": f"fixed_{chunk_index:03d}",
                    "paragraph_index": chunk_index,
                    "chunk_index_within_paragraph": 1,
                    "char_start": 0,
                    "char_end": len(text),
                }
            )
            current_parts = []
            current_length = 0
            chunk_index += 1
        current_parts.append(paragraph)
        current_length += len(paragraph)

    if current_parts:
        text = "\n\n".join(current_parts)
        chunk_records.append(
            {
                "text": text,
                "paragraph_id": f"fixed_{chunk_index:03d}",
                "paragraph_index": chunk_index,
                "chunk_index_within_paragraph": 1,
                "char_start": 0,
                "char_end": len(text),
            }
        )
    return chunk_records


def _paragraph_chunk_records(
    paragraphs: list[str], config: RetrievalConfig
) -> list[dict[str, Any]]:
    merged_paragraphs = _merge_short_paragraphs(paragraphs, config.paragraph_min_chars)
    records: list[dict[str, Any]] = []

    for paragraph_index, paragraph in enumerate(merged_paragraphs, start=1):
        paragraph_id = f"paragraph_{paragraph_index:03d}"
        if len(paragraph) <= config.paragraph_max_chars:
            records.append(
                {
                    "text": paragraph,
                    "paragraph_id": paragraph_id,
                    "paragraph_index": paragraph_index,
                    "chunk_index_within_paragraph": 1,
                    "char_start": 0,
                    "char_end": len(paragraph),
                }
            )
            continue

        records.extend(_split_long_paragraph(paragraph, paragraph_id, paragraph_index, config))

    return records


def _merge_short_paragraphs(paragraphs: list[str], min_chars: int) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if not buffer:
            buffer = paragraph
        elif len(buffer) < min_chars:
            buffer = f"{buffer}\n\n{paragraph}"
        else:
            merged.append(buffer)
            buffer = paragraph

    if buffer:
        if merged and len(buffer) < min_chars:
            merged[-1] = f"{merged[-1]}\n\n{buffer}"
        else:
            merged.append(buffer)
    return merged


def _split_long_paragraph(
    paragraph: str,
    paragraph_id: str,
    paragraph_index: int,
    config: RetrievalConfig,
) -> list[dict[str, Any]]:
    spans = _sentence_spans(paragraph)
    if not spans:
        spans = [(0, len(paragraph), paragraph)]

    overlap_chars = max(0, int(config.paragraph_max_chars * config.chunk_overlap_pct))
    chunks: list[dict[str, Any]] = []
    start_index = 0
    chunk_index = 1

    while start_index < len(spans):
        current_texts: list[str] = []
        current_start = spans[start_index][0]
        current_end = spans[start_index][1]
        current_length = 0
        end_index = start_index

        while end_index < len(spans):
            sentence_text = spans[end_index][2]
            prospective_length = current_length + len(sentence_text) + (1 if current_texts else 0)
            if current_texts and prospective_length > config.paragraph_max_chars:
                break
            current_texts.append(sentence_text)
            current_length = prospective_length
            current_end = spans[end_index][1]
            end_index += 1

        text = " ".join(current_texts).strip()
        chunks.append(
            {
                "text": text,
                "paragraph_id": paragraph_id,
                "paragraph_index": paragraph_index,
                "chunk_index_within_paragraph": chunk_index,
                "char_start": current_start,
                "char_end": current_end,
            }
        )

        if end_index >= len(spans):
            break

        overlap_index = end_index
        overlap_size = 0
        while overlap_index > start_index and overlap_size < overlap_chars:
            overlap_index -= 1
            overlap_size = current_end - spans[overlap_index][0]

        if overlap_index == start_index:
            overlap_index = end_index - 1

        start_index = max(overlap_index, start_index + 1)
        chunk_index += 1

    return chunks


def _sentence_spans(paragraph: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in SENTENCE_SPLIT_PATTERN.finditer(paragraph):
        end = match.start()
        sentence = paragraph[start:end].strip()
        if sentence:
            spans.append((start, end, sentence))
        start = match.end()
    tail = paragraph[start:].strip()
    if tail:
        spans.append((start, len(paragraph), tail))
    return spans


def _recover_page_number(text: str, sections: list[dict[str, Any]]) -> int | None:
    text_tokens = set(tokenize_text(text))
    if not text_tokens:
        return None

    best_score = 0
    best_page: int | None = None
    for section in sections:
        section_text = " ".join(
            part for part in [section.get("title", ""), section.get("text_excerpt", "")] if part
        )
        section_tokens = set(tokenize_text(section_text))
        overlap = len(text_tokens & section_tokens)
        if overlap > best_score:
            best_score = overlap
            best_page = section.get("page_start")

    if best_score == 0:
        return None
    return best_page


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


def _clean_block(text: str) -> str:
    return " ".join(text.split())


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
