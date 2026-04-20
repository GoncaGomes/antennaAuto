from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import FormulaItem, ListItem, PictureItem, SectionHeaderItem, TableItem
from grobid_client.grobid_client import GrobidClient

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from .utils import ensure_dir, load_env_file, text_excerpt, write_json

TABLE_CAPTION_PATTERN = re.compile(
    r"^\s*table\s+(\d+|[IVXLCDM]+)\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
FIGURE_CAPTION_PATTERN = re.compile(
    r"^\s*(?:figure|fig\.)\s*(\d+[A-Za-z]?|[IVXLCDM]+[A-Za-z]?)\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
PAGE_COUNTER_PATTERN = re.compile(r"^(?:page\s+)?\d+\s*(?:of\s+\d+)?$", re.IGNORECASE)
DOI_ONLY_PATTERN = re.compile(r"^(?:doi\s*:?\s*)?10\.\d{4,9}/\S+$", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
SECTION_NUMBER_PATTERN = re.compile(r"^(?:\d+(?:\.\d+)*)\.?\s+\S")
TITLE_CASE_NAME_PATTERN = re.compile(r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z.'-]+){1,6})$")
EDITORIAL_PATTERNS = (
    "paper open access",
    "open access",
    "you may also like",
    "to cite this article",
    "citation:",
    "academic editors:",
    "published:",
    "copyright:",
    "licensee",
    "this content was downloaded",
    "published under licence",
    "proceeding paper",
    "publisher's note",
    "disclaimer/publisher",
    "downloaded from",
    "creative commons",
)
PUBLISHER_PATTERNS = (
    "journal of",
    "conference series",
    "iop publishing",
    "mdpi",
    "eng. proc.",
    "physics conference series",
    "international journal of",
    "issn",
)
FRONT_MATTER_PATTERNS = (
    "correspondence:",
    "department of",
    "university",
    "abstract:",
    "keywords:",
)
ANALYSIS_CANDIDATES: list[tuple[str, tuple[str, ...], float]] = [
    ("radiation pattern", ("radiation pattern", "far-field", "e-plane", "h-plane", "polar plot"), 0.95),
    ("s11 plot", ("s11", "return loss", "reflection coefficient"), 0.95),
    ("gain plot", ("gain", "realized gain"), 0.9),
    ("current distribution", ("current distribution", "surface current"), 0.9),
    ("smith chart", ("smith chart", "smith"), 0.9),
    (
        "antenna layout",
        ("antenna geometry", "geometry", "layout", "top view", "bottom view", "patch", "prototype"),
        0.8,
    ),
]
GROBID_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def parser_versions() -> dict[str, str]:
    pymupdf_version = getattr(pymupdf, "VersionBind", None)
    if pymupdf_version is None:
        version_tuple = getattr(pymupdf, "version", None)
        if isinstance(version_tuple, tuple) and version_tuple:
            pymupdf_version = str(version_tuple[0])
        else:
            pymupdf_version = "unknown"

    return {
        "docling": _safe_package_version("docling"),
        "grobid_client": _safe_package_version("grobid-client-python"),
        "pymupdf": str(pymupdf_version),
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
    page_objects_path = bundle_dir / "page_objects.json"

    warnings: list[str] = []
    document = _convert_pdf_to_docling_document(pdf_path)
    grobid = _maybe_enrich_with_grobid(pdf_path)
    warnings.extend(grobid["warnings"])

    pages, by_ref = _collect_page_objects(document)
    _annotate_heading_noise(pages, grobid)

    table_export = _export_tables(document, pages, by_ref, tables_dir)
    figure_export = _export_figures(document, pages, by_ref, figures_dir)

    warnings.extend(table_export["warnings"])
    warnings.extend(figure_export["warnings"])

    page_objects_payload = _serialize_page_objects(pages)
    write_json(page_objects_path, page_objects_payload)

    fulltext = _render_fulltext(
        pages,
        table_export["content_by_id"],
        figure_export["summaries_by_id"],
        table_export["used_caption_ids"] | figure_export["used_caption_ids"],
    )
    fulltext_path.write_text(fulltext, encoding="utf-8")

    sections = _build_sections(
        pages,
        table_export["content_by_id"],
        figure_export["summaries_by_id"],
        grobid,
    )
    write_json(sections_path, sections)

    page_summaries = _build_page_summaries(
        pages,
        table_export["content_by_id"],
        figure_export["summaries_by_id"],
    )

    object_counts = Counter(
        obj["object_type"]
        for page in pages
        for obj in page["objects"]
    )
    figure_summaries = figure_export["summaries"]
    table_summaries = table_export["summaries"]
    figure_kind_counts = _figure_kind_counts(figure_summaries)

    return {
        "fulltext": fulltext,
        "sections": sections,
        "table_summaries": table_summaries,
        "figure_summaries": figure_summaries,
        "page_summaries": page_summaries,
        "extracted_table_count": len(table_summaries),
        "extracted_image_count": len(figure_summaries),
        "captionless_figure_count": sum(1 for summary in figure_summaries if not summary.get("caption")),
        "figure_kind_counts": figure_kind_counts,
        "table_with_caption_count": sum(1 for summary in table_summaries if summary.get("caption")),
        "table_without_caption_count": sum(1 for summary in table_summaries if not summary.get("caption")),
        "page_object_count": sum(len(page["objects"]) for page in pages),
        "object_counts_by_type": dict(sorted(object_counts.items())),
        "tables_using_structured_export_count": table_export["structured_export_count"],
        "figures_with_explicit_caption_count": sum(
            1 for summary in figure_summaries if summary.get("caption_source") == "explicit_caption_object"
        ),
        "figures_with_group_caption_count": sum(
            1 for summary in figure_summaries if summary.get("caption_source") == "group_caption_object"
        ),
        "figures_with_missing_caption_count": sum(
            1 for summary in figure_summaries if summary.get("caption_source") == "missing"
        ),
        "grobid_status": grobid["status"],
        "fulltext_generated": bool(fulltext.strip()),
        "sections_generated": bool(sections),
        "warnings": warnings,
    }


def _safe_package_version(name: str) -> str:
    try:
        return package_version(name)
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"


@lru_cache(maxsize=1)
def _get_docling_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def _convert_pdf_to_docling_document(pdf_path: Path):
    result = _get_docling_converter().convert(pdf_path)
    return result.document


def _maybe_enrich_with_grobid(pdf_path: Path) -> dict[str, Any]:
    load_env_file()
    server = os.environ.get("MVP_GROBID_URL", "").strip()
    if not server:
        return {
            "status": "disabled",
            "title": "",
            "authors": [],
            "abstract": "",
            "section_titles": [],
            "warnings": [],
        }

    try:
        client = GrobidClient(grobid_server=server, timeout=30, check_server=False, verbose=False)
        _pdf_file, status, tei_xml = client.process_pdf(
            "processFulltextDocument",
            str(pdf_path),
            generateIDs=False,
            consolidate_header=True,
            consolidate_citations=False,
            include_raw_citations=False,
            include_raw_affiliations=False,
            tei_coordinates=False,
            segment_sentences=False,
        )
        if status != 200 or not tei_xml.strip():
            raise RuntimeError(f"GROBID processFulltextDocument returned status {status}")
        enrichment = _parse_grobid_tei(tei_xml)
        enrichment["status"] = "used"
        enrichment["warnings"] = []
        return enrichment
    except Exception as exc:
        return {
            "status": "failed",
            "title": "",
            "authors": [],
            "abstract": "",
            "section_titles": [],
            "warnings": [f"GROBID enrichment failed: {exc}"],
        }


def _parse_grobid_tei(tei_xml: str) -> dict[str, Any]:
    root = ET.fromstring(tei_xml)
    title = _xml_text(root.find(".//tei:titleStmt/tei:title", GROBID_NS))
    abstract_parts = [
        _xml_text(node)
        for node in root.findall(".//tei:profileDesc/tei:abstract//tei:p", GROBID_NS)
    ]
    authors = []
    for author in root.findall(".//tei:titleStmt//tei:author", GROBID_NS):
        name_parts = [
            _xml_text(part)
            for part in author.findall(".//tei:forename", GROBID_NS)
        ] + [
            _xml_text(part)
            for part in author.findall(".//tei:surname", GROBID_NS)
        ]
        author_name = _clean_text(" ".join(part for part in name_parts if part))
        if author_name:
            authors.append(author_name)

    section_titles = []
    for head in root.findall(".//tei:text/tei:body//tei:head", GROBID_NS):
        text = _clean_text(" ".join(head.itertext()))
        if text:
            section_titles.append(text)

    return {
        "title": title,
        "authors": authors,
        "abstract": " ".join(part for part in abstract_parts if part).strip(),
        "section_titles": section_titles,
    }


def _collect_page_objects(document) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    page_heights = {
        int(page_no): float(getattr(page.size, "height", 0.0))
        for page_no, page in document.pages.items()
    }
    pages_by_number: dict[int, dict[str, Any]] = {
        page_number: {
            "page_number": page_number,
            "_page_height": page_heights.get(page_number, 0.0),
            "objects": [],
        }
        for page_number in sorted(page_heights)
    }

    provisional: list[dict[str, Any]] = []
    repeated_text_pages: dict[str, set[int]] = defaultdict(set)

    for order_index, (item, _level) in enumerate(document.iterate_items(), start=1):
        primary_prov = _primary_provenance(item)
        page_number = int(getattr(primary_prov, "page_no", 1) or 1)
        page = pages_by_number.setdefault(
            page_number,
            {"page_number": page_number, "_page_height": page_heights.get(page_number, 0.0), "objects": []},
        )
        text = _extract_item_text(item)
        self_ref = str(getattr(item, "self_ref", f"#/unknown/{order_index}"))
        normalized_type = _normalize_object_type(item)
        bbox = _bbox_to_list(getattr(primary_prov, "bbox", None))
        label = _item_label(item)

        provisional_object = {
            "_item": item,
            "_self_ref": self_ref,
            "_page_height": page["_page_height"],
            "page_number": page_number,
            "object_id": f"obj_{order_index:06d}",
            "object_type": normalized_type,
            "order_index": order_index,
            "text": text,
            "bbox": bbox,
            "source_artifact_id": None,
            "meta": {
                "docling_label": label,
                "caption_object_id": None,
                "group_id": None,
                "is_noise": False,
            },
        }
        provisional.append(provisional_object)

        noise_key = _noise_key(text)
        if noise_key:
            repeated_text_pages[noise_key].add(page_number)

    by_ref: dict[str, dict[str, Any]] = {}
    for obj in provisional:
        if _is_footer_or_header_noise(obj, repeated_text_pages):
            obj["object_type"] = "footer_or_header_noise"
            obj["meta"]["is_noise"] = True
        pages_by_number[obj["page_number"]]["objects"].append(obj)
        by_ref[obj["_self_ref"]] = obj

    pages = [pages_by_number[page_number] for page_number in sorted(pages_by_number)]
    return pages, by_ref


def _primary_provenance(item) -> Any | None:
    provenance = getattr(item, "prov", None)
    if isinstance(provenance, list) and provenance:
        return provenance[0]
    return None


def _bbox_to_list(bbox: Any | None) -> list[float] | None:
    if bbox is None:
        return None
    return [float(getattr(bbox, "l", 0.0)), float(getattr(bbox, "t", 0.0)), float(getattr(bbox, "r", 0.0)), float(getattr(bbox, "b", 0.0))]


def _item_label(item) -> str:
    return str(getattr(item, "label", "") or "")


def _extract_item_text(item) -> str:
    return _clean_text(str(getattr(item, "text", "") or ""))


def _normalize_object_type(item) -> str:
    if isinstance(item, PictureItem):
        return "figure"
    if isinstance(item, TableItem):
        return "table"
    if isinstance(item, FormulaItem) or _item_label(item) == "formula":
        return "formula"
    if isinstance(item, ListItem) or _item_label(item) == "list_item":
        return "list_item"
    if isinstance(item, SectionHeaderItem) or _item_label(item) in {"section_header", "title"}:
        return "heading"
    if _item_label(item) == "caption":
        return "caption"
    return "paragraph"


def _noise_key(text: str) -> str:
    normalized = _clean_text(text).lower()
    if not normalized:
        return ""
    if len(normalized) > 120:
        return ""
    return normalized


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _is_footer_or_header_noise(obj: dict[str, Any], repeated_text_pages: dict[str, set[int]]) -> bool:
    text = _clean_text(obj["text"])
    if not text:
        return False
    lowered = text.lower()
    if _is_running_header_footer_line(text):
        return True
    if any(pattern in lowered for pattern in EDITORIAL_PATTERNS):
        return True
    if any(pattern in lowered for pattern in PUBLISHER_PATTERNS):
        bbox = obj.get("bbox")
        page_height = float(obj.get("_page_height", 0.0))
        if _is_top_or_bottom_furniture(bbox, page_height):
            return True
    repeated_pages = repeated_text_pages.get(_noise_key(text), set())
    if len(repeated_pages) >= 2 and _is_top_or_bottom_furniture(obj.get("bbox"), float(obj.get("_page_height", 0.0))):
        return True
    return False


def _is_running_header_footer_line(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if PAGE_COUNTER_PATTERN.fullmatch(lowered):
        return True
    if DOI_ONLY_PATTERN.fullmatch(cleaned):
        return True
    if "issn" in lowered or "doi:" in lowered:
        return True
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if any(pattern in lowered for pattern in EDITORIAL_PATTERNS):
        return True
    if any(pattern in lowered for pattern in PUBLISHER_PATTERNS):
        return True
    return False


def _is_top_or_bottom_furniture(bbox: list[float] | None, page_height: float) -> bool:
    if bbox is None or page_height <= 0:
        return False
    top = bbox[1]
    bottom = bbox[3]
    return top >= page_height * 0.82 or bottom <= page_height * 0.12


def _annotate_heading_noise(pages: list[dict[str, Any]], grobid: dict[str, Any]) -> None:
    grobid_titles = {
        _normalize_heading(title)
        for title in [grobid.get("title", ""), *grobid.get("section_titles", [])]
        if title
    }

    for page in pages:
        objects = page["objects"]
        for index, obj in enumerate(objects):
            if obj["object_type"] != "heading":
                continue
            following = objects[index + 1 : index + 4]
            obj["meta"]["heading_noise"] = _is_heading_noise(obj["text"], following, grobid_titles)


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _is_heading_noise(title: str, following_objects: list[dict[str, Any]], grobid_titles: set[str]) -> bool:
    cleaned = _clean_text(title)
    lowered = cleaned.lower()
    if not cleaned:
        return True
    if _normalize_heading(cleaned) in grobid_titles:
        return False
    if _is_running_header_footer_line(cleaned):
        return True
    if any(pattern in lowered for pattern in EDITORIAL_PATTERNS):
        return True
    if any(pattern in lowered for pattern in ("author contributions", "funding", "institutional review board", "informed consent")):
        return False
    if SECTION_NUMBER_PATTERN.match(cleaned):
        return False
    if len(cleaned.split()) <= 2 and cleaned.lower() in {"references", "conclusion", "results", "introduction", "abstract"}:
        return False
    following_text = " ".join(
        obj["text"]
        for obj in following_objects
        if obj["object_type"] in {"paragraph", "list_item"} and not obj["meta"].get("is_noise")
    ).lower()
    if EMAIL_PATTERN.search(following_text) or any(token in following_text for token in ("department of", "university", "correspondence")):
        if TITLE_CASE_NAME_PATTERN.fullmatch(cleaned):
            return True
    if cleaned.lower() in {"proceeding paper", "paper open access", "you may also like"}:
        return True
    return False


def _export_tables(
    document,
    pages: list[dict[str, Any]],
    by_ref: dict[str, dict[str, Any]],
    tables_dir: Path,
) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    content_by_id: dict[str, str] = {}
    used_caption_ids: set[str] = set()
    warnings: list[str] = []
    structured_export_count = 0

    table_index = 1
    for page in pages:
        objects = page["objects"]
        for index, obj in enumerate(objects):
            if obj["object_type"] != "table":
                continue

            item = obj["_item"]
            table_id = f"table_{table_index:03d}"
            caption_obj = _resolve_primary_caption_object(item, by_ref, expected="table")
            if caption_obj is None:
                caption_obj = _find_adjacent_caption_object(objects, index, expected="table")

            caption = _clean_table_caption(caption_obj["text"]) if caption_obj is not None else ""
            markdown_body, structured = _render_table_body(item, document)
            if not markdown_body:
                markdown_body = "_Table content unavailable._"
            content = "\n\n".join(part for part in [caption, markdown_body] if part).strip() + "\n"
            table_path = tables_dir / f"{table_id}.md"
            table_path.write_text(content, encoding="utf-8")

            obj["source_artifact_id"] = table_id
            obj["meta"]["caption_object_id"] = caption_obj["object_id"] if caption_obj is not None else None

            if caption_obj is not None:
                used_caption_ids.add(caption_obj["object_id"])

            if structured:
                structured_export_count += 1

            summary = {
                "table_id": table_id,
                "page_number": obj["page_number"],
                "caption": caption,
                "context_before": _context_from_neighbors(objects, index, direction="before", allow_captions=False),
                "context_after": _context_from_neighbors(objects, index, direction="after", allow_captions=False),
                "structured": structured,
                "parse_strategy": "docling_structured_table" if structured else "docling_table_fallback",
                "artifact_path": str(table_path),
            }
            summaries.append(summary)
            content_by_id[table_id] = content.strip()
            table_index += 1

    return {
        "summaries": summaries,
        "summaries_by_id": {summary["table_id"]: summary for summary in summaries},
        "content_by_id": content_by_id,
        "used_caption_ids": used_caption_ids,
        "warnings": warnings,
        "structured_export_count": structured_export_count,
    }


def _resolve_primary_caption_object(item, by_ref: dict[str, dict[str, Any]], *, expected: str) -> dict[str, Any] | None:
    caption_refs = getattr(item, "captions", None) or []
    for ref in caption_refs:
        target = by_ref.get(str(getattr(ref, "cref", "")))
        if target is None:
            continue
        if expected == "table" and _looks_like_table_caption(target["text"]):
            return target
        if expected == "figure" and _looks_like_figure_caption(target["text"]):
            return target
    return None


def _find_adjacent_caption_object(
    page_objects: list[dict[str, Any]],
    anchor_index: int,
    *,
    expected: str,
) -> dict[str, Any] | None:
    for direction in (1, -1):
        index = anchor_index + direction
        steps = 0
        while 0 <= index < len(page_objects) and steps < 3:
            candidate = page_objects[index]
            if candidate["meta"].get("is_noise"):
                index += direction
                continue
            if candidate["object_type"] == "caption":
                text = candidate["text"]
                if expected == "table" and _looks_like_table_caption(text):
                    return candidate
                if expected == "figure" and _looks_like_figure_caption(text) and not _looks_like_table_caption(text):
                    return candidate
                return None
            if candidate["object_type"] in {"paragraph", "heading", "list_item", "figure", "table", "formula"}:
                break
            index += direction
            steps += 1
    return None


def _looks_like_table_caption(text: str) -> bool:
    return bool(TABLE_CAPTION_PATTERN.match(_strip_markdown_decorators(text)))


def _looks_like_figure_caption(text: str) -> bool:
    return bool(FIGURE_CAPTION_PATTERN.match(_strip_markdown_decorators(text)))


def _strip_markdown_decorators(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
    cleaned = cleaned.replace("~~", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" \t\n\r")


def _clean_table_caption(text: str) -> str:
    candidate = _strip_markdown_decorators(text)
    if not candidate:
        return ""
    match = TABLE_CAPTION_PATTERN.match(candidate)
    if match:
        suffix = match.group(2).strip()
        prefix = f"Table {match.group(1)}"
        if candidate.lower().startswith("table ") and candidate[:5].istitle():
            prefix = f"Table {match.group(1)}"
        if suffix:
            return f"{prefix}. {suffix}".replace("..", ".").strip()
        return prefix
    return candidate


def _render_table_body(item, document) -> tuple[str, bool]:
    try:
        exported = _clean_text(str(item.export_to_markdown(document) or ""))
    except Exception:
        exported = ""

    caption_from_export, body_from_export = _split_table_markdown(exported)
    if body_from_export and "|" in body_from_export:
        return body_from_export, True

    markdown_from_cells = _table_markdown_from_cells(getattr(getattr(item, "data", None), "table_cells", None))
    if markdown_from_cells:
        return markdown_from_cells, True

    if body_from_export:
        return body_from_export, False
    if caption_from_export:
        return caption_from_export, False
    return "", False


def _split_table_markdown(markdown: str) -> tuple[str, str]:
    lines = [line.rstrip() for line in markdown.splitlines()]
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return "", ""
    first_line = non_empty[0]
    if _looks_like_table_caption(first_line):
        body = "\n".join(line for line in lines if line.strip() and line.strip() != first_line).strip()
        return _clean_table_caption(first_line), body
    return "", markdown.strip()


def _table_markdown_from_cells(table_cells: Any) -> str:
    if not table_cells:
        return ""
    row_count = max(int(getattr(cell, "end_row_offset_idx", 0)) for cell in table_cells)
    col_count = max(int(getattr(cell, "end_col_offset_idx", 0)) for cell in table_cells)
    if row_count <= 0 or col_count <= 0:
        return ""

    grid = [["" for _ in range(col_count)] for _ in range(row_count)]
    for cell in table_cells:
        row = int(getattr(cell, "start_row_offset_idx", 0))
        col = int(getattr(cell, "start_col_offset_idx", 0))
        if 0 <= row < row_count and 0 <= col < col_count:
            grid[row][col] = _clean_text(str(getattr(cell, "text", "") or ""))

    header = grid[0]
    separator = ["---" for _ in header]
    body_rows = grid[1:] if len(grid) > 1 else []
    markdown_lines = [
        "| " + " | ".join(cell or " " for cell in header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    markdown_lines.extend("| " + " | ".join(cell or " " for cell in row) + " |" for row in body_rows)
    return "\n".join(markdown_lines).strip()


def _export_figures(
    document,
    pages: list[dict[str, Any]],
    by_ref: dict[str, dict[str, Any]],
    figures_dir: Path,
) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    summaries_by_id: dict[str, dict[str, Any]] = {}
    used_caption_ids: set[str] = set()
    warnings: list[str] = []

    figure_index = 1
    group_index = 1

    for page in pages:
        blocks = _group_figure_blocks(page["objects"])
        for block in blocks:
            group_id = f"figure_group_{group_index:03d}" if len(block) > 1 else None
            shared_caption = _shared_block_caption(block, page["objects"], by_ref)
            if shared_caption is not None and group_id is not None:
                used_caption_ids.add(shared_caption["object_id"])

            for obj in block:
                item = obj["_item"]
                figure_id = f"figure_{figure_index:03d}"
                image_path = figures_dir / f"{figure_id}.png"
                try:
                    image = item.get_image(document)
                    if image is None:
                        raise ValueError("Docling figure image is missing")
                    image.save(image_path, "PNG")
                except Exception as exc:
                    warnings.append(f"Figure export failed for {obj['object_id']}: {exc}")
                    figure_index += 1
                    continue

                direct_caption = _resolve_primary_caption_object(item, by_ref, expected="figure")
                caption_obj = direct_caption
                caption_source = "missing"
                if group_id is not None and shared_caption is not None:
                    caption_obj = shared_caption
                    caption_source = "group_caption_object"
                elif direct_caption is not None:
                    caption_source = "explicit_caption_object"
                elif shared_caption is not None:
                    caption_obj = shared_caption
                    caption_source = "explicit_caption_object"

                caption = _clean_figure_caption(caption_obj["text"]) if caption_obj is not None else ""
                if not caption:
                    caption_source = "missing"

                if caption_obj is not None:
                    used_caption_ids.add(caption_obj["object_id"])

                local_text_window = _local_text_window(page["objects"], obj, exclude_caption_ids=used_caption_ids)
                context = _figure_context(page["objects"], obj, exclude_caption_ids=used_caption_ids)
                figure_kind = _classify_figure_kind(
                    page_number=obj["page_number"],
                    caption=caption,
                    local_text_window=local_text_window,
                    context=context,
                    page_objects=page["objects"],
                    anchor_object=obj,
                )
                analysis_score, analysis_reason = _analysis_candidate(local_text_window, context, caption, figure_kind)

                obj["source_artifact_id"] = figure_id
                obj["meta"]["caption_object_id"] = caption_obj["object_id"] if caption_obj is not None else None
                obj["meta"]["group_id"] = group_id
                obj["meta"]["figure_kind"] = figure_kind

                summary = {
                    "figure_id": figure_id,
                    "page_number": obj["page_number"],
                    "image_path": str(image_path),
                    "markdown_path": f"{figures_dir.name}/{image_path.name}",
                    "caption": caption,
                    "caption_source": caption_source,
                    "context": context,
                    "local_text_window": local_text_window,
                    "figure_kind": figure_kind,
                    "analysis_candidate_score": analysis_score,
                    "analysis_candidate_reason": analysis_reason,
                }
                summaries.append(summary)
                summaries_by_id[figure_id] = summary
                figure_index += 1

            if group_id is not None:
                group_index += 1

    return {
        "summaries": summaries,
        "summaries_by_id": summaries_by_id,
        "used_caption_ids": used_caption_ids,
        "warnings": warnings,
    }


def _group_figure_blocks(page_objects: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for obj in page_objects:
        if obj["object_type"] == "figure":
            current.append(obj)
            continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _shared_block_caption(
    block: list[dict[str, Any]],
    page_objects: list[dict[str, Any]],
    by_ref: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    shared_direct: dict[str, dict[str, Any]] = {}
    for obj in block:
        caption_obj = _resolve_primary_caption_object(obj["_item"], by_ref, expected="figure")
        if caption_obj is not None:
            shared_direct[caption_obj["object_id"]] = caption_obj
    if len(shared_direct) == 1 and len(block) > 1:
        return next(iter(shared_direct.values()))

    indexes = {obj["object_id"]: page_objects.index(obj) for obj in block}
    block_start = min(indexes.values())
    block_end = max(indexes.values())
    return _find_block_caption_object(page_objects, block_start, block_end)


def _find_block_caption_object(
    page_objects: list[dict[str, Any]],
    block_start: int,
    block_end: int,
) -> dict[str, Any] | None:
    for direction, anchor in ((1, block_end), (-1, block_start)):
        index = anchor + direction
        steps = 0
        while 0 <= index < len(page_objects) and steps < 3:
            candidate = page_objects[index]
            if candidate["meta"].get("is_noise"):
                index += direction
                continue
            if candidate["object_type"] == "caption":
                if _looks_like_figure_caption(candidate["text"]) and not _looks_like_table_caption(candidate["text"]):
                    return candidate
                break
            if candidate["object_type"] in {"paragraph", "heading", "list_item", "table", "formula"}:
                break
            index += direction
            steps += 1
    return None


def _clean_figure_caption(text: str) -> str:
    candidate = _strip_markdown_decorators(text)
    if not candidate:
        return ""
    if _looks_like_table_caption(candidate):
        return ""

    parts = re.split(r"(?=\b(?:Figure|Fig\.)\s*\d+[A-Za-z]?\b)", candidate, flags=re.IGNORECASE)
    if parts:
        candidate = parts[0].strip() if parts[0].strip() else parts[1].strip() if len(parts) > 1 else candidate

    match = FIGURE_CAPTION_PATTERN.match(candidate)
    if not match:
        return ""
    prefix = f"Figure {match.group(1)}"
    suffix = match.group(2).strip()
    if suffix:
        suffix = re.split(r"\s+(?:Figure|Fig\.)\s*\d+[A-Za-z]?\b", suffix, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    cleaned = f"{prefix}. {suffix}".strip(". ").strip()
    if suffix:
        cleaned = f"{prefix}. {suffix}".strip()
    return cleaned[:400].strip()


def _text_neighbors(
    page_objects: list[dict[str, Any]],
    anchor_index: int,
    *,
    limit: int,
    direction: str,
    allow_captions: bool,
    exclude_caption_ids: set[str],
) -> list[str]:
    collected: list[str] = []
    indexes: list[int]
    if direction == "before":
        indexes = list(range(anchor_index - 1, -1, -1))
    elif direction == "after":
        indexes = list(range(anchor_index + 1, len(page_objects)))
    else:
        indexes = list(range(anchor_index - 1, -1, -1)) + list(range(anchor_index + 1, len(page_objects)))

    for idx in indexes:
        obj = page_objects[idx]
        if obj["meta"].get("is_noise"):
            continue
        if obj["object_type"] == "caption" and (not allow_captions or obj["object_id"] in exclude_caption_ids):
            continue
        if obj["object_type"] not in {"heading", "paragraph", "list_item", "caption"}:
            continue
        text = _clean_text(obj["text"])
        if not text:
            continue
        collected.append(text)
        if len(collected) >= limit:
            break
    if direction == "before":
        collected.reverse()
    return collected


def _local_text_window(
    page_objects: list[dict[str, Any]],
    anchor_object: dict[str, Any],
    *,
    exclude_caption_ids: set[str],
) -> str:
    anchor_index = page_objects.index(anchor_object)
    before = _text_neighbors(
        page_objects,
        anchor_index,
        limit=2,
        direction="before",
        allow_captions=False,
        exclude_caption_ids=exclude_caption_ids,
    )
    after = _text_neighbors(
        page_objects,
        anchor_index,
        limit=2,
        direction="after",
        allow_captions=False,
        exclude_caption_ids=exclude_caption_ids,
    )
    return text_excerpt("\n".join(before + after), limit=800)


def _figure_context(
    page_objects: list[dict[str, Any]],
    anchor_object: dict[str, Any],
    *,
    exclude_caption_ids: set[str],
) -> str:
    anchor_index = page_objects.index(anchor_object)
    before = _text_neighbors(
        page_objects,
        anchor_index,
        limit=1,
        direction="before",
        allow_captions=False,
        exclude_caption_ids=exclude_caption_ids,
    )
    after = _text_neighbors(
        page_objects,
        anchor_index,
        limit=1,
        direction="after",
        allow_captions=False,
        exclude_caption_ids=exclude_caption_ids,
    )
    return text_excerpt("\n".join(before + after), limit=500)


def _context_from_neighbors(
    page_objects: list[dict[str, Any]],
    anchor_index: int,
    *,
    direction: str,
    allow_captions: bool,
) -> str:
    snippets = _text_neighbors(
        page_objects,
        anchor_index,
        limit=2,
        direction=direction,
        allow_captions=allow_captions,
        exclude_caption_ids=set(),
    )
    return text_excerpt("\n".join(snippets), limit=500)


def _classify_figure_kind(
    *,
    page_number: int,
    caption: str,
    local_text_window: str,
    context: str,
    page_objects: list[dict[str, Any]],
    anchor_object: dict[str, Any],
) -> str:
    if caption:
        return "labeled_figure"

    local_lower = f"{local_text_window} {context}".lower()
    if page_number == 1 and any(pattern in local_lower for pattern in EDITORIAL_PATTERNS + PUBLISHER_PATTERNS):
        return "decorative_or_editorial"

    anchor_index = page_objects.index(anchor_object)
    nearby_objects = page_objects[max(0, anchor_index - 2) : anchor_index + 3]
    formula_count = sum(1 for obj in nearby_objects if obj["object_type"] == "formula")
    if formula_count >= 1 and _looks_equation_like(local_text_window):
        return "equation_like"

    return "unknown"


def _looks_equation_like(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    math_symbols = sum(cleaned.count(symbol) for symbol in ("=", "+", "-", "/", "^", "λ", "Ω", "µ", "π"))
    alpha = sum(character.isalpha() for character in cleaned)
    digits = sum(character.isdigit() for character in cleaned)
    return math_symbols >= 3 and digits >= 2 and alpha <= max(24, digits * 4)


def _analysis_candidate(local_text_window: str, context: str, caption: str, figure_kind: str) -> tuple[float, str]:
    if figure_kind == "decorative_or_editorial":
        return 0.05, "editorial figure"

    haystack = " ".join(part for part in [caption, local_text_window, context] if part).lower()
    for reason, patterns, score in ANALYSIS_CANDIDATES:
        if any(pattern in haystack for pattern in patterns):
            return score, reason

    if caption:
        return 0.35, "captioned figure"
    return 0.0, ""


def _figure_kind_counts(figure_summaries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "labeled_figure": 0,
        "equation_like": 0,
        "decorative_or_editorial": 0,
        "unknown": 0,
    }
    for summary in figure_summaries:
        kind = str(summary.get("figure_kind", "unknown"))
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _serialize_page_objects(pages: list[dict[str, Any]]) -> dict[str, Any]:
    payload_pages: list[dict[str, Any]] = []
    for page in pages:
        serialized_objects = []
        for obj in page["objects"]:
            serialized_objects.append(
                {
                    "page_number": obj["page_number"],
                    "object_id": obj["object_id"],
                    "object_type": obj["object_type"],
                    "order_index": obj["order_index"],
                    "text": obj["text"],
                    "bbox": obj["bbox"],
                    "source_artifact_id": obj["source_artifact_id"],
                    "meta": dict(obj["meta"]),
                }
            )
        payload_pages.append({"page_number": page["page_number"], "objects": serialized_objects})
    return {"pages": payload_pages}


def _render_fulltext(
    pages: list[dict[str, Any]],
    table_content_by_id: dict[str, str],
    figure_summaries_by_id: dict[str, dict[str, Any]],
    used_caption_ids: set[str],
) -> str:
    blocks: list[str] = []
    first_heading = True
    rendered_figure_groups: set[str] = set()

    for page in pages:
        objects = page["objects"]
        index = 0
        while index < len(objects):
            obj = objects[index]
            if obj["object_type"] == "footer_or_header_noise":
                index += 1
                continue
            if obj["object_type"] == "caption" and obj["object_id"] in used_caption_ids:
                index += 1
                continue

            if obj["object_type"] == "heading":
                if obj["meta"].get("heading_noise"):
                    if obj["text"]:
                        blocks.append(obj["text"])
                else:
                    prefix = "# " if first_heading else "## "
                    blocks.append(f"{prefix}{obj['text']}".strip())
                    first_heading = False
                index += 1
                continue

            if obj["object_type"] in {"paragraph", "list_item", "caption"}:
                if obj["text"]:
                    blocks.append(obj["text"])
                index += 1
                continue

            if obj["object_type"] == "formula":
                if obj["text"]:
                    blocks.append(obj["text"])
                index += 1
                continue

            if obj["object_type"] == "table":
                artifact_id = str(obj.get("source_artifact_id") or "").strip()
                if artifact_id:
                    table_content = table_content_by_id.get(artifact_id, "").strip()
                    if table_content:
                        blocks.append(table_content)
                index += 1
                continue

            if obj["object_type"] == "figure":
                figure_id = str(obj.get("source_artifact_id") or "").strip()
                if not figure_id:
                    index += 1
                    continue
                summary = figure_summaries_by_id.get(figure_id)
                if summary is None:
                    index += 1
                    continue
                if summary.get("figure_kind") == "decorative_or_editorial" and not summary.get("caption"):
                    index += 1
                    continue

                group_id = str(obj["meta"].get("group_id") or "")
                if group_id:
                    if group_id in rendered_figure_groups:
                        index += 1
                        continue
                    rendered_figure_groups.add(group_id)
                    group_objects = [obj]
                    next_index = index + 1
                    while next_index < len(objects) and objects[next_index]["object_type"] == "figure" and objects[next_index]["meta"].get("group_id") == group_id:
                        group_objects.append(objects[next_index])
                        next_index += 1
                    for group_object in group_objects:
                        group_figure_id = str(group_object.get("source_artifact_id") or "")
                        group_summary = figure_summaries_by_id.get(group_figure_id, {})
                        markdown_path = str(group_summary.get("markdown_path", "")).strip()
                        if markdown_path:
                            blocks.append(f"![Figure]({markdown_path})")
                    if summary.get("caption"):
                        blocks.append(str(summary["caption"]).strip())
                    index = next_index
                    continue

                markdown_path = str(summary.get("markdown_path", "")).strip()
                if markdown_path:
                    blocks.append(f"![Figure]({markdown_path})")
                if summary.get("caption"):
                    blocks.append(str(summary["caption"]).strip())
                index += 1
                continue

            index += 1

    return "\n\n".join(block for block in blocks if block.strip()).strip()


def _build_sections(
    pages: list[dict[str, Any]],
    table_content_by_id: dict[str, str],
    figure_summaries_by_id: dict[str, dict[str, Any]],
    grobid: dict[str, Any],
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_title = "Front Matter"
    current_parts: list[str] = []
    first_heading_seen = False

    def flush() -> None:
        nonlocal current_parts
        text = "\n".join(part for part in current_parts if part).strip()
        if not text:
            current_parts = []
            return
        sections.append(
            {
                "section_id": f"section_{len(sections) + 1:03d}",
                "title": current_title,
                "text_excerpt": text_excerpt(text, limit=1200),
            }
        )
        current_parts = []

    for page in pages:
        for obj in page["objects"]:
            if obj["object_type"] == "footer_or_header_noise":
                continue
            if obj["object_type"] == "heading" and not obj["meta"].get("heading_noise"):
                flush()
                current_title = obj["text"] or grobid.get("title", "") or "Untitled Section"
                first_heading_seen = True
                continue

            rendered = _section_text(obj, table_content_by_id, figure_summaries_by_id)
            if rendered:
                current_parts.append(rendered)

    if not first_heading_seen and grobid.get("abstract"):
        current_parts.insert(0, grobid["abstract"])
    flush()
    return sections


def _section_text(
    obj: dict[str, Any],
    table_content_by_id: dict[str, str],
    figure_summaries_by_id: dict[str, dict[str, Any]],
) -> str:
    if obj["object_type"] in {"paragraph", "list_item", "caption", "formula"}:
        return obj["text"]
    if obj["object_type"] == "heading":
        return obj["text"]
    if obj["object_type"] == "table":
        artifact_id = str(obj.get("source_artifact_id") or "").strip()
        table_content = table_content_by_id.get(artifact_id, "")
        caption, _body = _split_table_markdown(table_content)
        return caption or text_excerpt(table_content.replace("|", " "), limit=240)
    if obj["object_type"] == "figure":
        artifact_id = str(obj.get("source_artifact_id") or "").strip()
        summary = figure_summaries_by_id.get(artifact_id, {})
        if summary.get("figure_kind") == "decorative_or_editorial" and not summary.get("caption"):
            return ""
        return str(summary.get("caption") or summary.get("local_text_window") or summary.get("context") or "").strip()
    return ""


def _build_page_summaries(
    pages: list[dict[str, Any]],
    table_content_by_id: dict[str, str],
    figure_summaries_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for page in pages:
        parts: list[str] = []
        for obj in page["objects"]:
            if obj["object_type"] == "footer_or_header_noise":
                continue
            rendered = _section_text(obj, table_content_by_id, figure_summaries_by_id)
            if rendered:
                parts.append(rendered)
        summaries.append(
            {
                "page_number": page["page_number"],
                "text_excerpt": text_excerpt("\n".join(parts), limit=1200),
            }
        )
    return summaries


def _xml_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return _clean_text(" ".join(node.itertext()))
