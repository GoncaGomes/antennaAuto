from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber
import pymupdf4llm

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from .utils import ensure_dir, text_excerpt, write_json

TABLE_CAPTION_PATTERN = re.compile(r"^\s*table\s+(\d+)\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
FIGURE_CAPTION_PATTERN = re.compile(r"^\s*figure\s+\d+\b", re.IGNORECASE)
SECTION_HEADING_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*)\.?\s+[A-Z]", re.IGNORECASE)
AXIS_TOKEN_PATTERN = re.compile(r"\b([XYZ]-axis)\b", re.IGNORECASE)
NUMERIC_TOKEN_PATTERN = re.compile(r"^[<>~]?-?\d+(?:\.\d+)?(?:[a-zA-Z%°]+)?$")


def parser_versions() -> dict[str, str]:
    pymupdf_version = getattr(pymupdf, "VersionBind", None)
    if pymupdf_version is None:
        version_tuple = getattr(pymupdf, "version", None)
        if isinstance(version_tuple, tuple) and version_tuple:
            pymupdf_version = str(version_tuple[0])
        else:
            pymupdf_version = "unknown"

    return {
        "pdfplumber": getattr(pdfplumber, "__version__", "unknown"),
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


def extract_markdown(pdf_path: Path, output_path: Path) -> str:
    markdown = pymupdf4llm.to_markdown(str(pdf_path))
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def _guess_caption(page_text: str) -> str:
    for line in page_text.splitlines():
        candidate = line.strip()
        lowered = candidate.lower()
        if lowered.startswith("figure") or lowered.startswith("fig."):
            return candidate
    return "Caption extraction not implemented."


def _save_png(document: Any, xref: int, output_path: Path) -> None:
    pixmap = pymupdf.Pixmap(document, xref)
    if pixmap.n - pixmap.alpha > 3:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    pixmap.save(output_path)


def extract_images(pdf_path: Path, figures_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    figures: list[dict[str, Any]] = []
    warnings: list[str] = []

    with pymupdf.open(pdf_path) as document:
        figure_index = 1
        for page_number in range(document.page_count):
            page = document.load_page(page_number)
            page_text = page.get_text("text").strip()

            for image in page.get_images(full=True):
                xref = image[0]
                figure_dir = ensure_dir(figures_dir / f"fig_{figure_index:03d}")
                image_path = figure_dir / "image.png"
                caption_path = figure_dir / "caption.txt"
                context_path = figure_dir / "context.txt"
                metadata_path = figure_dir / "figure.json"

                try:
                    _save_png(document, xref, image_path)
                except Exception as exc:  # pragma: no cover
                    warnings.append(
                        f"Failed to extract image xref={xref} on page {page_number + 1}: {exc}"
                    )
                    figure_dir.rmdir()
                    continue

                caption_path.write_text(_guess_caption(page_text), encoding="utf-8")
                context = text_excerpt(page_text) or "Context extraction not implemented."
                context_path.write_text(context, encoding="utf-8")
                figure_id = f"fig_{figure_index:03d}"
                write_json(
                    metadata_path,
                    {
                        "figure_id": figure_id,
                        "page_number": page_number + 1,
                        "image_path": str(image_path),
                    },
                )

                figures.append(
                    {
                        "figure_id": figure_id,
                        "page_number": page_number + 1,
                        "image_path": str(image_path),
                    }
                )
                figure_index += 1

    return figures, warnings


def detect_table_caption_lines(page_text: str | list[str]) -> list[str]:
    source_lines = page_text.splitlines() if isinstance(page_text, str) else page_text
    captions: list[str] = []
    for raw_line in source_lines:
        line = _normalize_text(raw_line)
        if line and _match_table_caption(line):
            captions.append(line)
    return captions


def validate_table_rows(rows: list[list[str]]) -> bool:
    populated_rows = [_normalize_row(row) for row in rows if any(cell.strip() for cell in row)]
    if len(populated_rows) < 2:
        return False

    column_counts = [len(row) for row in populated_rows]
    if min(column_counts) < 2:
        return False
    if len(set(column_counts)) != 1:
        return False

    data_rows = populated_rows[1:]
    if not data_rows:
        return False

    if not any(any(_cell_has_number(cell) for cell in row[1:]) for row in data_rows):
        return False

    for row in data_rows:
        if any(len(cell) > 80 for cell in row):
            return False
        if sum(len(cell) for cell in row) > 140:
            return False

    return True


def extract_tables(pdf_path: Path, tables_dir: Path) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    caption_candidates_found = 0
    table_candidates_deduplicated = 0
    tables_saved_as_fallback_only = 0
    tables_rejected_validation = 0
    table_regions_cropped = 0

    with pymupdf.open(pdf_path) as document:
        table_index = 1
        for page_number in range(1, document.page_count + 1):
            page = document.load_page(page_number - 1)
            page_lines = _page_lines(page)
            raw_candidates, candidates = _detect_table_candidates(page_lines, page_number)
            caption_candidates_found += raw_candidates
            table_candidates_deduplicated += len(candidates)

            for candidate in candidates:
                table_id = f"table_{table_index:03d}"
                candidate_lines = collect_lines_below_caption(page_lines, candidate["line_index"])
                rows, extraction_method, rejected_validation = _extract_structured_table_from_lines(
                    candidate_lines
                )

                if rows is not None:
                    payload = {
                        "table_id": table_id,
                        "page_number": page_number,
                        "caption": candidate["caption"],
                        "extraction_method": extraction_method,
                        "rows": rows,
                    }
                    write_json(tables_dir / f"{table_id}.json", payload)
                    tables.append(payload)
                else:
                    if rejected_validation:
                        tables_rejected_validation += 1
                    _save_table_fallback(
                        table_id=table_id,
                        page=page,
                        page_lines=page_lines,
                        caption_candidate=candidate,
                        candidate_lines=candidate_lines,
                        output_dir=ensure_dir(tables_dir / table_id),
                    )
                    tables_saved_as_fallback_only += 1
                    table_regions_cropped += 1

                table_index += 1

    return {
        "tables": tables,
        "warnings": warnings,
        "table_caption_candidates_found": caption_candidates_found,
        "table_candidates_deduplicated": table_candidates_deduplicated,
        "table_regions_cropped": table_regions_cropped,
        "tables_extracted_structured": len(tables),
        "tables_saved_as_fallback_only": tables_saved_as_fallback_only,
        "tables_rejected_validation": tables_rejected_validation,
    }


def collect_lines_below_caption(
    page_lines: list[dict[str, Any]], caption_index: int, max_lines: int = 12
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for line in page_lines[caption_index + 1 :]:
        text = line["text"]
        if _starts_new_text_region(text):
            break
        if _looks_like_large_paragraph_line(text):
            break
        if _looks_tabular_line(text):
            collected.append(line)
            if len(collected) >= max_lines:
                break
            continue
        if collected:
            break
        break
    return collected


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _normalize_row(row: list[str]) -> list[str]:
    return [_normalize_text(cell) for cell in row]


def _page_lines(page: Any) -> list[dict[str, Any]]:
    fragments: list[dict[str, Any]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = _normalize_text("".join(span.get("text", "") for span in line.get("spans", [])))
            if text:
                fragments.append({"text": text, "bbox": tuple(float(value) for value in line["bbox"])})

    fragments.sort(key=lambda item: (round(item["bbox"][1], 1), item["bbox"][0]))

    grouped: list[dict[str, Any]] = []
    tolerance = 1.5
    for fragment in fragments:
        if grouped and _same_text_row(grouped[-1]["bbox"], fragment["bbox"], tolerance):
            grouped[-1]["parts"].append(fragment)
            grouped[-1]["bbox"] = _merge_bbox(grouped[-1]["bbox"], fragment["bbox"])
        else:
            grouped.append({"bbox": fragment["bbox"], "parts": [fragment]})

    lines: list[dict[str, Any]] = []
    for group in grouped:
        parts = sorted(group["parts"], key=lambda item: item["bbox"][0])
        text = _normalize_text(" ".join(part["text"] for part in parts))
        if text:
            lines.append({"text": text, "bbox": group["bbox"]})
    return lines


def _same_text_row(
    first_bbox: tuple[float, float, float, float],
    second_bbox: tuple[float, float, float, float],
    tolerance: float,
) -> bool:
    return abs(first_bbox[1] - second_bbox[1]) <= tolerance and abs(first_bbox[3] - second_bbox[3]) <= tolerance


def _merge_bbox(
    first_bbox: tuple[float, float, float, float],
    second_bbox: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (
        min(first_bbox[0], second_bbox[0]),
        min(first_bbox[1], second_bbox[1]),
        max(first_bbox[2], second_bbox[2]),
        max(first_bbox[3], second_bbox[3]),
    )


def _detect_table_candidates(
    page_lines: list[dict[str, Any]], page_number: int
) -> tuple[int, list[dict[str, Any]]]:
    raw_count = 0
    candidates: list[dict[str, Any]] = []
    seen_table_numbers: set[int] = set()

    for index, line in enumerate(page_lines):
        match = _match_table_caption(line["text"])
        if not match:
            continue
        raw_count += 1
        table_number = int(match.group(1))
        if table_number in seen_table_numbers:
            continue
        seen_table_numbers.add(table_number)
        candidates.append(
            {
                "page_number": page_number,
                "table_number": table_number,
                "caption": line["text"],
                "bbox": line["bbox"],
                "line_index": index,
            }
        )

    return raw_count, candidates


def _match_table_caption(line: str) -> re.Match[str] | None:
    match = TABLE_CAPTION_PATTERN.match(line)
    if match is None:
        return None
    if not match.group(2).strip():
        return None
    return match


def _starts_new_text_region(text: str) -> bool:
    lowered = text.lower()
    if _match_table_caption(text):
        return True
    if FIGURE_CAPTION_PATTERN.match(text):
        return True
    if SECTION_HEADING_PATTERN.match(text):
        return True
    return lowered == "references"


def _looks_like_large_paragraph_line(text: str) -> bool:
    return len(text) >= 85 and _numeric_token_count(text.split()) <= 1


def _looks_tabular_line(text: str) -> bool:
    lowered = text.lower()
    if "parameter" in lowered or "value" in lowered:
        return True
    if len(AXIS_TOKEN_PATTERN.findall(text)) >= 2:
        return True

    tokens = text.split()
    numeric_count = _numeric_token_count(tokens)
    if numeric_count == 0:
        return False
    if len(text) > 70:
        return False
    return len(tokens) <= 12


def _numeric_token_count(tokens: list[str]) -> int:
    return sum(1 for token in tokens if _looks_numericish(token))


def _looks_numericish(token: str) -> bool:
    cleaned = token.strip(",;:()[]")
    return bool(NUMERIC_TOKEN_PATTERN.match(cleaned))


def _cell_has_number(cell: str) -> bool:
    return any(character.isdigit() for character in cell)


def _extract_structured_table_from_lines(
    candidate_lines: list[dict[str, Any]],
) -> tuple[list[list[str]] | None, str | None, bool]:
    rejected_validation = False
    line_texts = [line["text"] for line in candidate_lines]

    for method, extractor in (
        ("text_axis_columns", _try_extract_mode_b),
        ("text_parameter_value", _try_extract_mode_a),
    ):
        rows = extractor(line_texts)
        if rows is None:
            continue
        if validate_table_rows(rows):
            return rows, method, False
        rejected_validation = True

    return None, None, rejected_validation


def _try_extract_mode_a(lines: list[str]) -> list[list[str]] | None:
    if not lines:
        return None

    rows: list[list[str]] = []
    start_index = 0
    first_line = lines[0]
    first_line_lower = first_line.lower()

    if first_line_lower.startswith("parameter"):
        remainder = first_line[len("parameter") :].strip(" :-")
        rows.append(["Parameter", remainder or "Value"])
        start_index = 1

    for line in lines[start_index:]:
        parsed = _parse_parameter_value_row(line)
        if parsed is None:
            break
        rows.append(parsed)

    if len(rows) < 3:
        return None

    if start_index == 0:
        rows.insert(0, ["Parameter", "Value"])

    return rows


def _parse_parameter_value_row(line: str) -> list[str] | None:
    tokens = line.split()
    if len(tokens) < 2 or len(line) > 60:
        return None
    value = tokens[-1].strip(",;:")
    if not _looks_numericish(value):
        return None
    label = " ".join(tokens[:-1]).strip(" -:")
    if not label or len(label) > 45:
        return None
    return [label, value]


def _try_extract_mode_b(lines: list[str]) -> list[list[str]] | None:
    if not lines:
        return None

    axis_headers = [match.group(1) for match in AXIS_TOKEN_PATTERN.finditer(lines[0])]
    if len(axis_headers) < 2:
        return None

    header = ["Parameter"] + axis_headers
    rows: list[list[str]] = [header]

    for line in lines[1:]:
        parsed = _parse_axis_row(line, expected_values=len(axis_headers))
        if parsed is None:
            break
        rows.append(parsed)

    if len(rows) < 3:
        return None

    return rows


def _parse_axis_row(line: str, expected_values: int) -> list[str] | None:
    tokens = line.split()
    if len(tokens) <= expected_values or len(line) > 80:
        return None

    values: list[str] = []
    index = len(tokens)
    while index > 0 and len(values) < expected_values:
        token = tokens[index - 1].strip(",;:")
        if not _looks_numericish(token):
            break
        values.append(token)
        index -= 1

    if len(values) != expected_values:
        return None

    label = " ".join(tokens[:index]).strip(" -:,")
    if not label or len(label) > 55:
        return None

    values.reverse()
    return [label] + values


def _save_table_fallback(
    table_id: str,
    page: Any,
    page_lines: list[dict[str, Any]],
    caption_candidate: dict[str, Any],
    candidate_lines: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    caption_path = output_dir / "caption.txt"
    context_path = output_dir / "context.txt"
    crop_path = output_dir / "crop.png"
    metadata_path = output_dir / "table.json"

    crop_rect = _fallback_crop_rect(page, page_lines, caption_candidate, candidate_lines)
    context = _table_context(page_lines, caption_candidate["line_index"], candidate_lines)

    caption_path.write_text(caption_candidate["caption"], encoding="utf-8")
    context_path.write_text(context, encoding="utf-8")
    _save_crop_image(page, crop_rect, crop_path)
    write_json(
        metadata_path,
        {
            "table_id": table_id,
            "page_number": caption_candidate["page_number"],
            "caption": caption_candidate["caption"],
            "structured": False,
            "context_path": str(context_path),
            "crop_path": str(crop_path),
        },
    )


def _fallback_crop_rect(
    page: Any,
    page_lines: list[dict[str, Any]],
    caption_candidate: dict[str, Any],
    candidate_lines: list[dict[str, Any]],
) -> Any:
    page_rect = page.rect
    caption_rect = pymupdf.Rect(caption_candidate["bbox"])
    top = min(page_rect.y1 - 20, caption_rect.y1 + 6)

    if candidate_lines:
        x0 = min(line["bbox"][0] for line in candidate_lines) - 8
        x1 = max(line["bbox"][2] for line in candidate_lines) + 8
        bottom = max(line["bbox"][3] for line in candidate_lines) + 6
    else:
        x0 = caption_rect.x0 - 8
        x1 = min(page_rect.x1 - 24, caption_rect.x1 + 260)
        bottom = top + 48

    stop_y = _next_stop_y(page, page_lines, caption_candidate["line_index"], top)
    if stop_y is not None and stop_y > top:
        bottom = min(bottom, stop_y - 4)

    bottom = min(bottom, top + 160, page_rect.y1 - 18)
    if bottom <= top + 18:
        bottom = min(page_rect.y1 - 18, top + 36)

    x0 = max(page_rect.x0 + 18, x0)
    x1 = min(page_rect.x1 - 18, max(x0 + 40, x1))
    return pymupdf.Rect(x0, top, x1, bottom)


def _next_stop_y(page: Any, page_lines: list[dict[str, Any]], caption_index: int, top: float) -> float | None:
    stop_values: list[float] = []

    for line in page_lines[caption_index + 1 :]:
        y0 = line["bbox"][1]
        if y0 <= top:
            continue
        text = line["text"]
        if _starts_new_text_region(text) or _looks_like_large_paragraph_line(text):
            stop_values.append(y0)
            break

    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") == 1:
            bbox = block.get("bbox")
            if bbox and bbox[1] > top:
                stop_values.append(float(bbox[1]))

    if not stop_values:
        return None
    return min(stop_values)


def _table_context(
    page_lines: list[dict[str, Any]],
    caption_index: int,
    candidate_lines: list[dict[str, Any]],
) -> str:
    end_index = caption_index + len(candidate_lines) + 3
    start_index = max(0, caption_index - 1)
    nearby_text = [line["text"] for line in page_lines[start_index:end_index]]
    return text_excerpt("\n".join(nearby_text)) or "Context extraction not implemented."


def _save_crop_image(page: Any, crop_rect: Any, output_path: Path) -> None:
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=crop_rect, alpha=False)
    pixmap.save(output_path)


def generate_sections(pdf_path: Path, output_path: Path) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

    with pymupdf.open(pdf_path) as document:
        for page_number in range(document.page_count):
            page = document.load_page(page_number)
            page_text = page.get_text("text").strip()
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            title = lines[0] if lines else f"Page {page_number + 1}"
            sections.append(
                {
                    "section_id": f"page_{page_number + 1:03d}",
                    "title": title,
                    "page_start": page_number + 1,
                    "page_end": page_number + 1,
                    "text_excerpt": text_excerpt(page_text),
                }
            )

    write_json(output_path, sections)
    return sections
