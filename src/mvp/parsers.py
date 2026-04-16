from __future__ import annotations

import csv
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

UPPERCASE_TITLE_PREFIX_PATTERN = re.compile(r"^([A-Z][A-Z0-9()/%&,\-]*(?:\s+[A-Z0-9()/%&,\-]+){0,10})\b")

TABLE_CAPTION_PATTERN = re.compile(
    r"^\s*table\s+(\d+|[IVXLCDM]+)\b\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
FIGURE_CAPTION_PATTERN = re.compile(r"^\s*figure\s+\d+\b", re.IGNORECASE)
SECTION_HEADING_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*)\.?\s+[A-Z]", re.IGNORECASE)
AXIS_TOKEN_PATTERN = re.compile(r"\b([XYZ]-axis)\b", re.IGNORECASE)
NUMERIC_TOKEN_PATTERN = re.compile(r"^[<>~]?-?\d+(?:\.\d+)?(?:[a-zA-Z%°]+)?$")
TABLE_STRATEGY_THRESHOLD = 55.0
TABLE_HEADER_KEYWORDS = (
    "parameter",
    "parameters",
    "reference",
    "dielectric",
    "constant",
    "size",
    "frequency",
    "frequencies",
    "bandwidth",
    "gain",
    "output",
    "factor",
    "factors",
    "step",
)
PDFPLUMBER_TABLE_STRATEGIES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "pdfplumber_lines_lines",
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "intersection_tolerance": 3,
            "edge_min_length": 3,
        },
    ),
    (
        "pdfplumber_lines_strict_lines_strict",
        {
            "vertical_strategy": "lines_strict",
            "horizontal_strategy": "lines_strict",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "intersection_tolerance": 3,
            "edge_min_length": 3,
        },
    ),
    (
        "pdfplumber_text_text",
        {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
            "intersection_x_tolerance": 5,
            "intersection_y_tolerance": 5,
        },
    ),
    (
        "pdfplumber_text_lines",
        {
            "vertical_strategy": "text",
            "horizontal_strategy": "lines",
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
            "intersection_tolerance": 5,
        },
    ),
    (
        "pdfplumber_lines_text",
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "text",
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
            "intersection_tolerance": 5,
        },
    ),
)


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
    index = 0
    while index < len(source_lines):
        resolved = _resolve_table_caption_text(source_lines, index)
        if resolved is None:
            index += 1
            continue
        caption, end_index = resolved
        captions.append(caption)
        index = end_index + 1
    return captions


def _normalize_table_identifier(raw_identifier: str) -> str:
    cleaned = raw_identifier.strip().upper()
    if cleaned.isdigit():
        return str(int(cleaned))
    roman_value = _roman_to_int(cleaned)
    if roman_value is not None:
        return str(roman_value)
    return cleaned


def _roman_to_int(value: str) -> int | None:
    numerals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    if not value or any(character not in numerals for character in value):
        return None

    total = 0
    previous = 0
    for character in reversed(value):
        current = numerals[character]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total if total > 0 else None


def validate_table_rows(rows: list[list[str]]) -> bool:
    normalized = _normalize_table_rows(rows)
    scored = _score_table_candidate(normalized, caption="", context="")
    return bool(scored["passes_threshold"])


def extract_tables(pdf_path: Path, tables_dir: Path) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    table_summaries: list[dict[str, Any]] = []
    caption_candidates_found = 0
    table_candidates_deduplicated = 0
    tables_saved_as_fallback_only = 0
    tables_rejected_validation = 0
    table_regions_cropped = 0

    with pymupdf.open(pdf_path) as document, pdfplumber.open(str(pdf_path)) as plumber_document:
        table_index = 1
        for page_number in range(1, document.page_count + 1):
            page = document.load_page(page_number - 1)
            plumber_page = plumber_document.pages[page_number - 1]
            page_lines = _page_lines(page)
            raw_candidates, candidates = _detect_table_candidates(page_lines, page_number)
            caption_candidates_found += raw_candidates
            table_candidates_deduplicated += len(candidates)

            for candidate in candidates:
                table_id = f"table_{table_index:03d}"
                candidate_lines = collect_lines_below_caption(page_lines, candidate["line_index"])
                candidate_lines = _expand_table_region_lines(page_lines, candidate["line_index"], candidate_lines)
                context = _table_context(page_lines, candidate["line_index"], candidate_lines)
                region_rect = _table_candidate_rect(page, page_lines, candidate, candidate_lines)
                table_regions_cropped += 1
                parse_result = _choose_best_table_parse(
                    plumber_page=plumber_page,
                    region_rect=region_rect,
                    candidate_lines=candidate_lines,
                    caption=candidate["caption"],
                    context=context,
                )

                if parse_result["rows"] is not None:
                    rows = parse_result["rows"]
                    shape = _table_shape(rows)
                    payload = {
                        "table_id": table_id,
                        "page_number": page_number,
                        "caption": candidate["caption"],
                        "context": context,
                        "structured": True,
                        "bbox": _bbox_to_list(region_rect),
                        "caption_bbox": _bbox_to_list(candidate["bbox"]),
                        "parse_strategy": parse_result["strategy"],
                        "parse_score": parse_result["score"],
                        "parse_quality": parse_result["quality"],
                        "candidate_scores_summary": parse_result["attempts"],
                        "shape": {"rows": shape[0], "cols": shape[1]},
                        "extraction_method": parse_result["strategy"],
                        "rows": rows,
                    }
                    write_json(tables_dir / f"{table_id}.json", payload)
                    _write_table_exports(tables_dir, table_id, rows)
                    tables.append(payload)
                    table_summaries.append(
                        {
                            "table_id": table_id,
                            "page_number": page_number,
                            "caption": candidate["caption"],
                            "structured": True,
                            "parse_strategy": parse_result["strategy"],
                            "parse_score": parse_result["score"],
                            "parse_quality": parse_result["quality"],
                            "shape": {"rows": shape[0], "cols": shape[1]},
                        }
                    )
                else:
                    if parse_result["rejected_validation"]:
                        tables_rejected_validation += 1
                    _save_table_fallback(
                        table_id=table_id,
                        page=page,
                        page_lines=page_lines,
                        caption_candidate=candidate,
                        candidate_lines=candidate_lines,
                        output_dir=ensure_dir(tables_dir / table_id),
                        region_rect=region_rect,
                        parse_result=parse_result,
                        context=context,
                    )
                    tables_saved_as_fallback_only += 1
                    table_summaries.append(
                        {
                            "table_id": table_id,
                            "page_number": page_number,
                            "caption": candidate["caption"],
                            "structured": False,
                            "parse_strategy": parse_result["strategy"],
                            "parse_score": parse_result["score"],
                            "parse_quality": parse_result["quality"],
                            "shape": None,
                            "note": parse_result["note"],
                        }
                    )

                table_index += 1

    return {
        "tables": tables,
        "table_summaries": table_summaries,
        "warnings": warnings,
        "table_caption_candidates_found": caption_candidates_found,
        "table_candidates_deduplicated": table_candidates_deduplicated,
        "table_regions_cropped": table_regions_cropped,
        "tables_extracted_structured": len(tables),
        "tables_saved_as_fallback_only": tables_saved_as_fallback_only,
        "tables_rejected_validation": tables_rejected_validation,
    }


def collect_lines_below_caption(
    page_lines: list[dict[str, Any]], caption_index: int, max_lines: int = 18
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    grace_skips = 0
    last_collected: dict[str, Any] | None = None
    for line in page_lines[caption_index + 1 :]:
        text = line["text"]
        if _starts_new_text_region(text):
            break
        if _looks_like_large_paragraph_line(text) and not collected:
            break
        if _looks_tabular_line(text):
            collected.append(line)
            last_collected = line
            grace_skips = 0
            if len(collected) >= max_lines:
                break
            continue
        if collected and last_collected is not None:
            vertical_gap = float(line["bbox"][1]) - float(last_collected["bbox"][3])
            if grace_skips == 0 and vertical_gap <= 16 and not _looks_like_large_paragraph_line(text):
                grace_skips += 1
                continue
        if collected:
            break
        break
    return collected


def _table_candidate_rect(
    page: Any,
    page_lines: list[dict[str, Any]],
    caption_candidate: dict[str, Any],
    candidate_lines: list[dict[str, Any]],
) -> Any:
    page_rect = page.rect
    caption_rect = pymupdf.Rect(caption_candidate["bbox"])
    top = min(page_rect.y1 - 24, caption_rect.y1 + 6)
    stop_y = _next_stop_y(page, page_lines, caption_candidate["line_index"], top)
    region_lines = _expand_table_region_lines(page_lines, caption_candidate["line_index"], candidate_lines)

    if region_lines:
        x0 = min(line["bbox"][0] for line in region_lines) - 12
        x1 = max(line["bbox"][2] for line in region_lines) + 12
        bottom_hint = max(line["bbox"][3] for line in region_lines) + 10
    else:
        x0 = page_rect.x0 + 18
        x1 = page_rect.x1 - 18
        bottom_hint = top + 120

    x0 = max(page_rect.x0 + 18, min(x0, caption_rect.x0 - 8))
    x1 = min(page_rect.x1 - 18, max(x1, caption_rect.x1 + 24))
    if x1 <= x0 + 40:
        x1 = min(page_rect.x1 - 18, x0 + 120)

    if stop_y is not None and stop_y > top:
        bottom = min(stop_y - 4, max(bottom_hint, top + 40))
    else:
        bottom = max(bottom_hint, top + 60)

    bottom_cap = top + 220
    if region_lines:
        line_span = max(line["bbox"][3] for line in region_lines) - min(line["bbox"][1] for line in region_lines)
        bottom_cap = min(page_rect.y1 - 18, top + max(220, min(340, line_span + 48)))

    bottom = min(bottom, page_rect.y1 - 18, bottom_cap)
    if bottom <= top + 20:
        bottom = min(page_rect.y1 - 18, top + 48)

    return pymupdf.Rect(x0, top, x1, bottom)


def _choose_best_table_parse(
    *,
    plumber_page: Any,
    region_rect: Any,
    candidate_lines: list[dict[str, Any]],
    caption: str,
    context: str,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    region_bbox = (float(region_rect.x0), float(region_rect.y0), float(region_rect.x1), float(region_rect.y1))
    expected_line_count = len(candidate_lines)

    for strategy_name, settings in PDFPLUMBER_TABLE_STRATEGIES:
        try:
            tables = _extract_tables_with_pdfplumber(plumber_page, region_bbox, settings)
        except Exception as exc:
            attempts.append(
                {
                    "strategy": strategy_name,
                    "engine": "pdfplumber",
                    "score": 0.0,
                    "passes_threshold": False,
                    "rows": 0,
                    "cols": 0,
                    "note": f"error: {exc}",
                }
            )
            continue

        if not tables:
            attempts.append(
                {
                    "strategy": strategy_name,
                    "engine": "pdfplumber",
                    "score": 0.0,
                    "passes_threshold": False,
                    "rows": 0,
                    "cols": 0,
                    "note": "no tables detected in region",
                }
            )
            continue

        for candidate_index, rows in enumerate(tables, start=1):
            scored = _score_table_candidate(
                rows,
                caption=caption,
                context=context,
                expected_line_count=expected_line_count,
            )
            attempt = {
                "strategy": strategy_name,
                "engine": "pdfplumber",
                "candidate_index": candidate_index,
                **scored,
            }
            attempts.append(attempt)
            if scored["passes_threshold"] and (best is None or scored["score"] > best["score"]):
                best = {
                    "rows": rows,
                    "strategy": strategy_name,
                    "score": scored["score"],
                    "quality": scored["quality"],
                    "rejected_validation": False,
                }

    line_texts = [line["text"] for line in candidate_lines]
    for strategy_name, extractor in (
        ("text_axis_columns", _try_extract_mode_b),
        ("text_parameter_value", _try_extract_mode_a),
    ):
        rows = extractor(line_texts)
        if rows is None:
            attempts.append(
                {
                    "strategy": strategy_name,
                    "engine": "text",
                    "score": 0.0,
                    "passes_threshold": False,
                    "rows": 0,
                    "cols": 0,
                    "note": "no structured rows recovered from line text",
                }
            )
            continue

        normalized_rows = _normalize_table_rows(rows)
        scored = _score_table_candidate(
            normalized_rows,
            caption=caption,
            context=context,
            expected_line_count=expected_line_count,
        )
        attempt = {
            "strategy": strategy_name,
            "engine": "text",
            **scored,
        }
        attempts.append(attempt)
        if scored["passes_threshold"] and (best is None or scored["score"] > best["score"]):
            best = {
                "rows": normalized_rows,
                "strategy": strategy_name,
                "score": scored["score"],
                "quality": scored["quality"],
                "rejected_validation": False,
            }

    attempts.sort(key=lambda item: (-float(item["score"]), item["strategy"]))
    if best is not None:
        return {
            "rows": best["rows"],
            "strategy": best["strategy"],
            "score": best["score"],
            "quality": best["quality"],
            "attempts": attempts,
            "rejected_validation": False,
            "note": "structured parse selected",
        }

    best_attempt = attempts[0] if attempts else None
    return {
        "rows": None,
        "strategy": best_attempt["strategy"] if best_attempt else None,
        "score": float(best_attempt["score"]) if best_attempt else 0.0,
        "quality": best_attempt.get("quality", "weak") if best_attempt else "weak",
        "attempts": attempts,
        "rejected_validation": bool(best_attempt and best_attempt["rows"] > 0),
        "note": best_attempt["note"] if best_attempt else "no table strategies produced a plausible structure",
    }


def _extract_tables_with_pdfplumber(
    plumber_page: Any,
    region_bbox: tuple[float, float, float, float],
    settings: dict[str, Any],
) -> list[list[list[str]]]:
    cropped_page = plumber_page.crop(region_bbox)
    extracted = cropped_page.extract_tables(table_settings=settings) or []
    tables: list[list[list[str]]] = []
    for table in extracted:
        normalized = _normalize_table_rows(table or [])
        if normalized:
            tables.append(normalized)
    return tables


def _normalize_table_rows(rows: list[list[str | None]]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for row in rows:
        normalized_row = [_normalize_text(str(cell or "")) for cell in row]
        if any(normalized_row):
            cleaned.append(normalized_row)

    if not cleaned:
        return []

    max_cols = max(len(row) for row in cleaned)
    padded = [row + [""] * (max_cols - len(row)) for row in cleaned]

    while padded and padded[0] and all(not row[-1] for row in padded):
        for row in padded:
            row.pop()
    while padded and padded[0] and all(not row[0] for row in padded):
        for row in padded:
            row.pop(0)

    return [_normalize_row(row) for row in padded if row]


def _score_table_candidate(
    rows: list[list[str]],
    *,
    caption: str,
    context: str,
    expected_line_count: int = 0,
) -> dict[str, Any]:
    normalized = _normalize_table_rows(rows)
    if not normalized:
        return {
            "score": 0.0,
            "passes_threshold": False,
            "rows": 0,
            "cols": 0,
            "empty_ratio": 1.0,
            "ragged_ratio": 1.0,
            "header_meaningful": False,
            "caption_consistency": 0.0,
            "completeness_penalty": 0.0,
            "quality": "weak",
            "note": "empty candidate",
        }

    row_count, col_count = _table_shape(normalized)
    total_cells = max(1, row_count * max(1, col_count))
    empty_cells = sum(1 for row in normalized for cell in row if not cell)
    empty_ratio = empty_cells / total_cells
    original_lengths = [sum(1 for cell in row if cell) for row in normalized]
    modal_count = max(set(original_lengths), key=original_lengths.count)
    ragged_ratio = sum(1 for length in original_lengths if length != modal_count) / len(original_lengths)
    header_row = normalized[0]
    header_meaningful = any(any(character.isalpha() for character in cell) for cell in header_row) and not all(
        _cell_has_number(cell) for cell in header_row if cell
    )
    data_rows = normalized[1:]
    has_numeric_data = any(any(_cell_has_number(cell) for cell in row[1:]) for row in data_rows)
    single_column = col_count < 2
    linear_collapse = single_column or any(len(" ".join(row)) > 140 for row in data_rows)
    caption_consistency = _score_caption_consistency(caption, context, normalized)
    expected_data_rows = max(0, expected_line_count - 1)
    missing_data_rows = max(0, expected_data_rows - len(data_rows))
    completeness_penalty = 0.0
    if expected_data_rows >= 5 and missing_data_rows > 0:
        completeness_penalty = min(20.0, (missing_data_rows / expected_data_rows) * 24.0)
    too_noisy = ragged_ratio >= 0.6 or (ragged_ratio >= 0.5 and empty_ratio >= 0.25)

    score = 0.0
    if row_count >= 2 and col_count >= 2:
        score += 24
    if row_count >= 3:
        score += 8
    if col_count >= 3:
        score += 6
    score += max(0.0, (1.0 - empty_ratio)) * 18
    score += max(0.0, (1.0 - ragged_ratio)) * 16
    if header_meaningful:
        score += 12
    if has_numeric_data:
        score += 10
    score += caption_consistency
    if single_column:
        score -= 28
    if ragged_ratio > 0.45:
        score -= 14
    if empty_ratio > 0.45:
        score -= 18
    if linear_collapse:
        score -= 18
    if too_noisy:
        score -= 12
    score -= completeness_penalty

    score = max(0.0, min(100.0, round(score, 3)))
    passes_threshold = (
        score >= TABLE_STRATEGY_THRESHOLD
        and row_count >= 2
        and col_count >= 2
        and not single_column
        and not linear_collapse
        and has_numeric_data
        and not too_noisy
    )

    if too_noisy:
        quality = "noisy"
    elif completeness_penalty >= 8.0:
        quality = "partial"
    else:
        quality = "complete"

    if passes_threshold:
        note = "plausible structured table"
    elif too_noisy:
        note = "ragged/noisy table candidate"
    elif single_column:
        note = "single-column collapse"
    elif not has_numeric_data:
        note = "missing numeric data cells"
    elif completeness_penalty >= 8.0:
        note = "likely incomplete table capture"
    elif ragged_ratio > 0.45:
        note = "ragged row structure"
    elif empty_ratio > 0.45:
        note = "mostly empty cells"
    else:
        note = "score below acceptance threshold"

    return {
        "score": score,
        "passes_threshold": passes_threshold,
        "rows": row_count,
        "cols": col_count,
        "empty_ratio": round(empty_ratio, 3),
        "ragged_ratio": round(ragged_ratio, 3),
        "header_meaningful": header_meaningful,
        "caption_consistency": round(caption_consistency, 3),
        "completeness_penalty": round(completeness_penalty, 3),
        "quality": quality,
        "note": note,
    }


def _score_caption_consistency(caption: str, context: str, rows: list[list[str]]) -> float:
    caption_text = f"{caption} {context}".lower()
    table_text = " ".join(" ".join(row).lower() for row in rows)
    bonus = 0.0
    if any(term in caption_text for term in ("dimension", "parameter", "proposed antenna")) and any(
        term in table_text for term in ("parameter", "value", "length", "width", "thickness")
    ):
        bonus += 8.0
    if "array" in caption_text and len(AXIS_TOKEN_PATTERN.findall(rows[0][0] if rows and rows[0] else "")) == 0:
        if any(axis.lower() in table_text for axis in ("x-axis", "y-axis", "z-axis")):
            bonus += 8.0
    if any(term in caption_text for term in ("material", "substrate", "ground")) and any(
        term in table_text for term in ("substrate", "ground", "copper", "rogers")
    ):
        bonus += 5.0
    return bonus


def _table_shape(rows: list[list[str]]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    return len(rows), max((len(row) for row in rows), default=0)


def _bbox_to_list(bbox: Any) -> list[float]:
    if hasattr(bbox, "x0"):
        return [float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1)]
    return [float(value) for value in bbox]


def _write_table_exports(tables_dir: Path, table_id: str, rows: list[list[str]]) -> None:
    csv_path = tables_dir / f"{table_id}.csv"
    markdown_path = tables_dir / f"{table_id}.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)

    markdown_lines = []
    if rows:
        header = rows[0]
        markdown_lines.append("| " + " | ".join(header) + " |")
        markdown_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        for row in rows[1:]:
            padded = row + [""] * (len(header) - len(row))
            markdown_lines.append("| " + " | ".join(padded[: len(header)]) + " |")
    markdown_path.write_text("\n".join(markdown_lines), encoding="utf-8")


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
    seen_table_numbers: set[str] = set()
    line_texts = [line["text"] for line in page_lines]
    index = 0
    while index < len(page_lines):
        line = page_lines[index]
        match = _match_table_caption(line["text"])
        if not match:
            index += 1
            continue
        raw_count += 1
        table_number = _normalize_table_identifier(match.group(1))
        resolved = _resolve_table_caption_text(line_texts, index)
        if resolved is None:
            index += 1
            continue
        caption, end_index = resolved
        if table_number in seen_table_numbers:
            index = end_index + 1
            continue
        seen_table_numbers.add(table_number)
        bbox = line["bbox"]
        if end_index > index:
            bbox = _merge_bbox(bbox, page_lines[end_index]["bbox"])
        candidates.append(
            {
                "page_number": page_number,
                "table_number": table_number,
                "caption": caption,
                "bbox": bbox,
                "line_index": end_index,
            }
        )
        index = end_index + 1

    return raw_count, candidates


def _match_table_caption(line: str) -> re.Match[str] | None:
    match = TABLE_CAPTION_PATTERN.match(line)
    if match is None:
        return None
    identifier = match.group(1).strip()
    if not identifier.isdigit() and _roman_to_int(identifier.upper()) is None:
        return None
    return match


def _resolve_table_caption_text(lines: list[str], start_index: int) -> tuple[str, int] | None:
    line = _normalize_text(lines[start_index])
    match = _match_table_caption(line)
    if match is None:
        return None

    trailing = match.group(2).strip()
    if trailing:
        return line, start_index

    if start_index + 1 >= len(lines):
        return None

    continuation = _caption_continuation_text(_normalize_text(lines[start_index + 1]))
    if not continuation:
        return None

    return f"{line} {continuation}", start_index + 1


def _caption_continuation_text(line: str) -> str | None:
    if not line or _starts_new_text_region(line):
        return None

    uppercase_match = UPPERCASE_TITLE_PREFIX_PATTERN.match(line)
    if uppercase_match:
        return uppercase_match.group(1).strip()

    if _looks_tabular_line(line):
        return None

    return line if any(character.isalpha() for character in line) else None


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
    if _looks_header_like_table_line(text):
        return True

    tokens = text.split()
    numeric_count = _numeric_token_count(tokens)
    if numeric_count == 0:
        return False
    if numeric_count >= 4 and len(tokens) <= 28:
        return True
    if numeric_count >= 2 and len(tokens) <= 22:
        return True
    if any(marker in text for marker in ("×", "λ", "GHz", "MHz", "mm", "dB", "dBi", "Ω", "ohm")):
        return len(tokens) <= 28
    if len(text) > 120:
        return False
    return len(tokens) <= 18


def _looks_header_like_table_line(text: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in TABLE_HEADER_KEYWORDS):
        return True
    tokens = text.split()
    if 1 <= len(tokens) <= 6 and all(any(character.isalpha() for character in token) for token in tokens):
        if text.isupper() or text.istitle():
            return True
    return False


def _numeric_token_count(tokens: list[str]) -> int:
    return sum(1 for token in tokens if _looks_numericish(token))


def _looks_numericish(token: str) -> bool:
    cleaned = token.strip(",;:()[]")
    if NUMERIC_TOKEN_PATTERN.match(cleaned):
        return True
    return bool(re.match(r"^[<>~]?-?\d+(?:\.\d+)?(?:[:/\-–]\d+(?:\.\d+)?)+$", cleaned))


def _cell_has_number(cell: str) -> bool:
    return any(character.isdigit() for character in cell)


def _expand_table_region_lines(
    page_lines: list[dict[str, Any]],
    caption_index: int,
    candidate_lines: list[dict[str, Any]],
    max_extra_lines: int = 8,
) -> list[dict[str, Any]]:
    if not candidate_lines:
        return []

    expanded = list(candidate_lines)
    last_index = page_lines.index(candidate_lines[-1])
    last_kept = candidate_lines[-1]
    grace_skips = 0

    for line in page_lines[last_index + 1 :]:
        text = line["text"]
        if _starts_new_text_region(text):
            break
        if _looks_tabular_line(text):
            expanded.append(line)
            last_kept = line
            grace_skips = 0
            if len(expanded) >= len(candidate_lines) + max_extra_lines:
                break
            continue
        vertical_gap = float(line["bbox"][1]) - float(last_kept["bbox"][3])
        if grace_skips == 0 and vertical_gap <= 16 and not _looks_like_large_paragraph_line(text):
            grace_skips += 1
            continue
        break

    return expanded


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
    region_rect: Any,
    parse_result: dict[str, Any],
    context: str,
) -> None:
    caption_path = output_dir / "caption.txt"
    context_path = output_dir / "context.txt"
    crop_path = output_dir / "crop.png"
    metadata_path = output_dir / "table.json"

    caption_path.write_text(caption_candidate["caption"], encoding="utf-8")
    context_path.write_text(context, encoding="utf-8")
    _save_crop_image(page, region_rect, crop_path)
    write_json(
        metadata_path,
        {
            "table_id": table_id,
            "page_number": caption_candidate["page_number"],
            "caption": caption_candidate["caption"],
            "structured": False,
            "bbox": _bbox_to_list(region_rect),
            "caption_bbox": _bbox_to_list(caption_candidate["bbox"]),
            "parse_strategy": parse_result["strategy"],
            "parse_score": parse_result["score"],
            "parse_quality": parse_result["quality"],
            "candidate_scores_summary": parse_result["attempts"],
            "note": parse_result["note"],
            "context_path": str(context_path),
            "crop_path": str(crop_path),
        },
    )


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
