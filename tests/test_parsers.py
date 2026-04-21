from __future__ import annotations

from pathlib import Path

from mvp import parsers
from tests.docling_test_stubs import (
    FakeDoc,
    FakePictureItem,
    FakeRef,
    FakeSectionHeaderItem,
    FakeTableCell,
    FakeTableItem,
    FakeTextItem,
    install_fake_docling,
)


def test_extract_pdf_to_bundle_writes_markdown_native_outputs(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    document = FakeDoc(
        [
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/1",
                    label="section_header",
                    text="Introduction",
                    page_no=1,
                    bbox=(40, 760, 180, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/2",
                    label="text",
                    text="Intro text.",
                    page_no=1,
                    bbox=(40, 720, 280, 700),
                ),
                0,
            ),
            (
                FakeTableItem(
                    self_ref="#/tables/1",
                    label="table",
                    text="",
                    page_no=1,
                    bbox=(40, 660, 300, 560),
                    captions=[FakeRef("#/texts/3")],
                    markdown="Table 1. Dimensions of proposed antenna\n\n| Parameter | Value |\n| --- | --- |\n| L | 5.3 |",
                    table_cells=[
                        FakeTableCell(0, 1, 0, 1, "Parameter"),
                        FakeTableCell(0, 1, 1, 2, "Value"),
                        FakeTableCell(1, 2, 0, 1, "L"),
                        FakeTableCell(1, 2, 1, 2, "5.3"),
                    ],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/3",
                    label="caption",
                    text="Table 1. Dimensions of proposed antenna",
                    page_no=1,
                    bbox=(40, 680, 280, 665),
                ),
                0,
            ),
            (
                FakePictureItem(
                    self_ref="#/pictures/1",
                    label="picture",
                    text="",
                    page_no=1,
                    bbox=(320, 660, 480, 520),
                    captions=[FakeRef("#/texts/4")],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/4",
                    label="caption",
                    text="Figure 1. Antenna geometry",
                    page_no=1,
                    bbox=(320, 500, 520, 485),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/5",
                    label="section_header",
                    text="Results",
                    page_no=2,
                    bbox=(40, 760, 150, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/6",
                    label="text",
                    text="More text.",
                    page_no=2,
                    bbox=(40, 720, 180, 700),
                ),
                0,
            ),
        ],
        page_count=2,
    )
    install_fake_docling(monkeypatch, parsers, document)

    result = parsers.extract_pdf_to_bundle(tmp_path / "article.pdf", bundle_dir)

    assert (bundle_dir / "fulltext.md").exists()
    assert (bundle_dir / "sections.json").exists()
    assert (bundle_dir / "page_objects.json").exists()
    assert (bundle_dir / "tables" / "table_001.md").exists()
    assert (bundle_dir / "figures" / "figure_001.png").exists()
    fulltext = (bundle_dir / "fulltext.md").read_text(encoding="utf-8")
    assert "![Figure](figures/figure_001.png)" in fulltext
    table_markdown = (bundle_dir / "tables" / "table_001.md").read_text(encoding="utf-8")
    assert "Table 1. Dimensions of proposed antenna" in table_markdown
    assert "| L | 5.3 |" in table_markdown
    assert result["extracted_table_count"] == 1
    assert result["extracted_image_count"] == 1
    assert result["sections"][0]["section_id"] == "section_001"
    assert result["sections"][0]["title"] == "Introduction"
    assert "Intro text." in result["sections"][0]["text_excerpt"]
    assert "Table 1. Dimensions of proposed antenna" not in result["sections"][0]["text_excerpt"]
    assert "Figure 1. Antenna geometry" not in result["sections"][0]["text_excerpt"]


def test_extract_pdf_to_bundle_adds_front_matter_when_no_headers(monkeypatch, tmp_path: Path) -> None:
    document = FakeDoc(
        [
            (
                FakeTextItem(
                    self_ref="#/texts/1",
                    label="text",
                    text="Plain text without headers.",
                    page_no=1,
                    bbox=(40, 700, 280, 680),
                ),
                0,
            )
        ],
        page_count=1,
    )
    install_fake_docling(monkeypatch, parsers, document)

    result = parsers.extract_pdf_to_bundle(tmp_path / "article.pdf", tmp_path / "bundle")

    assert result["sections"] == [
        {
            "section_id": "section_001",
            "title": "Front Matter",
            "text_excerpt": "Plain text without headers.",
        }
    ]
