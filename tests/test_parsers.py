from __future__ import annotations

from pathlib import Path

from mvp import parsers


def test_extract_pdf_to_bundle_writes_markdown_native_outputs(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    figures_dir = bundle_dir / "figures"

    def fake_to_markdown(path: str, **kwargs):
        assert path.endswith("article.pdf")
        assert kwargs["write_images"] is True
        assert kwargs["page_chunks"] is True
        assert kwargs["image_format"] == "png"
        assert kwargs["image_path"] == str(figures_dir)
        figures_dir.mkdir(parents=True, exist_ok=True)
        (figures_dir / "article.pdf-0001-01.png").write_bytes(b"png")
        return [
            {
                "metadata": {"page_number": 1},
                "text": "\n".join(
                    [
                        "# Introduction",
                        "Intro text.",
                        "Table 1. Dimensions of proposed antenna",
                        "| Parameter | Value |",
                        "| --- | --- |",
                        "| L | 5.3 |",
                        "![Figure](C:/tmp/article.pdf-0001-01.png)",
                        "Figure 1. Antenna geometry",
                    ]
                ),
            },
            {
                "metadata": {"page_number": 2},
                "text": "## Results\nMore text.",
            },
        ]

    monkeypatch.setattr(parsers.pymupdf4llm, "to_markdown", fake_to_markdown)

    result = parsers.extract_pdf_to_bundle(tmp_path / "article.pdf", bundle_dir)

    assert (bundle_dir / "fulltext.md").exists()
    assert (bundle_dir / "sections.json").exists()
    assert (bundle_dir / "tables" / "table_001.md").exists()
    assert (bundle_dir / "figures" / "article.pdf-0001-01.png").exists()
    fulltext = (bundle_dir / "fulltext.md").read_text(encoding="utf-8")
    assert "![Figure](figures/article.pdf-0001-01.png)" in fulltext
    table_markdown = (bundle_dir / "tables" / "table_001.md").read_text(encoding="utf-8")
    assert "Table 1. Dimensions of proposed antenna" in table_markdown
    assert "| L | 5.3 |" in table_markdown
    assert result["extracted_table_count"] == 1
    assert result["extracted_image_count"] == 1
    assert result["sections"][0] == {
        "section_id": "section_001",
        "title": "Introduction",
        "text_excerpt": "Intro text. Table 1. Dimensions of proposed antenna | Parameter | Value | | --- | --- | | L | 5.3 | ![Figure](figures/article.pdf-0001-01.png) Figure 1. Antenna geometry",
    }


def test_extract_pdf_to_bundle_adds_front_matter_when_no_headers(monkeypatch, tmp_path: Path) -> None:
    def fake_to_markdown(path: str, **kwargs):
        return [{"metadata": {"page_number": 1}, "text": "Plain text without headers."}]

    monkeypatch.setattr(parsers.pymupdf4llm, "to_markdown", fake_to_markdown)

    result = parsers.extract_pdf_to_bundle(tmp_path / "article.pdf", tmp_path / "bundle")

    assert result["sections"] == [
        {
            "section_id": "section_001",
            "title": "Front Matter",
            "text_excerpt": "Plain text without headers.",
        }
    ]
