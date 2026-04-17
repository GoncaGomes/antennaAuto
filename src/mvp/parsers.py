from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf4llm

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from .utils import ensure_dir, text_excerpt, write_json

TABLE_CAPTION_PATTERN = re.compile(
    r"^\s*table\s+(\d+|[IVXLCDM]+)\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
MARKDOWN_TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
MARKDOWN_HEADER_PATTERN = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")


def parser_versions() -> dict[str, str]:
    pymupdf_version = getattr(pymupdf, "VersionBind", None)
    if pymupdf_version is None:
        version_tuple = getattr(pymupdf, "version", None)
        if isinstance(version_tuple, tuple) and version_tuple:
            pymupdf_version = str(version_tuple[0])
        else:
            pymupdf_version = "unknown"

    return {
        "pymupdf": str(pymupdf_version),
        "pymupdf4llm": getattr(pymupdf4llm, "__version__", "unknown"),
    }


def get_pdf_details(pdf_path: Path) -> dict[str, Any]:
    with pymupdf.open(pdf_path) as document:
        metadata = {key: value for key, value in (document.metadata or {}).items() if value}
        return {
            "page_count": document.page_count,
            "pdf_metadata": metadata,
        }


def extract_pdf_to_bundle(pdf_path: Path, bundle_dir: Path) -> dict[str, Any]:
    bundle_dir = ensure_dir(bundle_dir)
    figures_dir = ensure_dir(bundle_dir / "figures")
    tables_dir = ensure_dir(bundle_dir / "tables")
    fulltext_path = bundle_dir / "fulltext.md"
    sections_path = bundle_dir / "sections.json"

    page_chunks = pymupdf4llm.to_markdown(
        str(pdf_path),
        write_images=True,
        image_path=str(figures_dir),
        image_format="png",
        page_chunks=True,
    )
    if not isinstance(page_chunks, list):
        raise TypeError("Expected pymupdf4llm.to_markdown(..., page_chunks=True) to return a list.")

    normalized_pages = _normalize_page_chunks(page_chunks, figures_dir)
    fulltext = _join_page_markdown(normalized_pages)
    fulltext_path.write_text(fulltext, encoding="utf-8")

    table_blocks = _extract_markdown_tables(normalized_pages)
    table_summaries = _write_table_markdown_files(table_blocks, tables_dir)
    figure_summaries = _extract_figure_summaries(normalized_pages, figures_dir)
    sections = _split_markdown_sections(fulltext)
    write_json(sections_path, sections)

    return {
        "fulltext": fulltext,
        "sections": sections,
        "table_summaries": table_summaries,
        "figure_summaries": figure_summaries,
        "page_summaries": [
            {
                "page_number": page["page_number"],
                "text_excerpt": text_excerpt(page["text"], limit=1200),
            }
            for page in normalized_pages
        ],
        "extracted_table_count": len(table_summaries),
        "extracted_image_count": len(figure_summaries),
        "fulltext_generated": bool(fulltext.strip()),
        "sections_generated": bool(sections),
        "warnings": [],
    }


def _normalize_page_chunks(page_chunks: list[Any], figures_dir: Path) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    figure_dir_name = figures_dir.name.replace("\\", "/")
    for index, chunk in enumerate(page_chunks, start=1):
        metadata = dict(chunk.get("metadata", {})) if isinstance(chunk, dict) else {}
        page_number = metadata.get("page_number")
        if not isinstance(page_number, int):
            page_number = index
        text = str(chunk.get("text", "") if isinstance(chunk, dict) else "").strip()
        text = _normalize_image_paths(text, figures_dir, figure_dir_name)
        normalized.append(
            {
                "page_number": page_number,
                "text": text,
            }
        )
    return normalized


def _normalize_image_paths(markdown: str, figures_dir: Path, figure_dir_name: str) -> str:
    figure_root = figures_dir.as_posix().lower()

    def replace(match: re.Match[str]) -> str:
        image_path = match.group("path").strip()
        normalized = image_path.replace("\\", "/")
        file_name = Path(normalized).name
        if not file_name:
            return match.group(0)
        lowered = normalized.lower()
        if lowered.startswith(figure_root) or Path(normalized).is_absolute():
            return f"![{match.group('alt')}]({figure_dir_name}/{file_name})"
        if lowered.startswith(f"{figure_dir_name.lower()}/"):
            return f"![{match.group('alt')}]({figure_dir_name}/{file_name})"
        return f"![{match.group('alt')}]({figure_dir_name}/{file_name})"

    return MARKDOWN_IMAGE_PATTERN.sub(replace, markdown)


def _join_page_markdown(pages: list[dict[str, Any]]) -> str:
    return "\n\n".join(page["text"].strip() for page in pages if page["text"].strip()).strip()


def _extract_markdown_tables(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for page in pages:
        lines = page["text"].splitlines()
        index = 0
        while index < len(lines) - 1:
            header = lines[index].rstrip()
            separator = lines[index + 1].rstrip()
            if "|" not in header or not MARKDOWN_TABLE_SEPARATOR_PATTERN.match(separator):
                index += 1
                continue

            start = index
            table_lines = [header, separator]
            index += 2
            while index < len(lines):
                line = lines[index].rstrip()
                if "|" not in line:
                    break
                table_lines.append(line)
                index += 1

            caption = _nearest_table_caption(lines, start)
            context = _nearby_context(lines, start, index - 1)
            tables.append(
                {
                    "page_number": page["page_number"],
                    "caption": caption,
                    "context": context,
                    "markdown": "\n".join(table_lines).strip(),
                }
            )
    return tables


def _nearest_table_caption(lines: list[str], start_index: int) -> str:
    for candidate in reversed(lines[max(0, start_index - 4) : start_index]):
        stripped = candidate.strip()
        if stripped and TABLE_CAPTION_PATTERN.match(stripped):
            return stripped
    return ""


def _nearby_context(lines: list[str], start_index: int, end_index: int) -> str:
    window = [
        line.strip()
        for line in lines[max(0, start_index - 2) : min(len(lines), end_index + 3)]
        if line.strip()
    ]
    return text_excerpt("\n".join(window), limit=1200)


def _write_table_markdown_files(table_blocks: list[dict[str, Any]], tables_dir: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for index, block in enumerate(table_blocks, start=1):
        table_id = f"table_{index:03d}"
        path = tables_dir / f"{table_id}.md"
        content_parts = [block["caption"]] if block["caption"] else []
        content_parts.append(block["markdown"])
        path.write_text("\n\n".join(part for part in content_parts if part).strip() + "\n", encoding="utf-8")
        summaries.append(
            {
                "table_id": table_id,
                "page_number": block["page_number"],
                "caption": block["caption"],
                "structured": True,
                "parse_strategy": "pymupdf4llm_markdown_table",
                "parse_score": 100.0,
                "artifact_path": str(path),
            }
        )
    return summaries


def _extract_figure_summaries(pages: list[dict[str, Any]], figures_dir: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for page in pages:
        lines = page["text"].splitlines()
        for index, line in enumerate(lines):
            for match in MARKDOWN_IMAGE_PATTERN.finditer(line):
                relative_path = match.group("path").strip().replace("\\", "/")
                image_name = Path(relative_path).name
                if not image_name:
                    continue
                image_path = figures_dir / image_name
                summaries.append(
                    {
                        "figure_id": image_path.stem,
                        "page_number": page["page_number"],
                        "image_path": str(image_path),
                        "markdown_path": f"{figures_dir.name}/{image_name}",
                        "caption": _nearest_figure_caption(lines, index),
                        "context": _nearby_context(lines, index, index),
                    }
                )
    return summaries


def _nearest_figure_caption(lines: list[str], image_line_index: int) -> str:
    nearby = lines[max(0, image_line_index - 2) : min(len(lines), image_line_index + 3)]
    for candidate in nearby:
        stripped = candidate.strip()
        if not stripped or stripped.startswith("!["):
            continue
        if stripped.lower().startswith(("figure ", "fig. ")):
            return stripped
    return ""


def _split_markdown_sections(markdown: str) -> list[dict[str, Any]]:
    lines = markdown.splitlines()
    sections: list[dict[str, Any]] = []
    current_title = "Front Matter"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        text = "\n".join(current_lines).strip()
        if not text:
            current_lines = []
            return
        section_id = f"section_{len(sections) + 1:03d}"
        sections.append(
            {
                "section_id": section_id,
                "title": current_title,
                "text_excerpt": text_excerpt(text, limit=1200),
            }
        )
        current_lines = []

    for line in lines:
        match = MARKDOWN_HEADER_PATTERN.match(line)
        if match:
            flush()
            current_title = match.group(2).strip()
            continue
        current_lines.append(line)

    flush()
    return sections
