from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEST_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ioAAAAASUVORK5CYII="
)


@dataclass
class FakeBBox:
    l: float
    t: float
    r: float
    b: float


@dataclass
class FakeProv:
    page_no: int
    bbox: FakeBBox


@dataclass
class FakeRef:
    cref: str


@dataclass
class FakePageSize:
    width: float = 595.0
    height: float = 842.0


@dataclass
class FakePage:
    page_no: int
    size: FakePageSize


class FakeBaseItem:
    def __init__(
        self,
        *,
        self_ref: str,
        label: str,
        text: str = "",
        page_no: int = 1,
        bbox: tuple[float, float, float, float] = (40.0, 700.0, 200.0, 680.0),
        captions: list[FakeRef] | None = None,
        children: list[FakeRef] | None = None,
    ) -> None:
        self.self_ref = self_ref
        self.label = label
        self.text = text
        self.prov = [FakeProv(page_no=page_no, bbox=FakeBBox(*bbox))]
        self.captions = captions or []
        self.children = children or []


class FakeTextItem(FakeBaseItem):
    pass


class FakeSectionHeaderItem(FakeBaseItem):
    pass


class FakeListItem(FakeBaseItem):
    pass


class FakeFormulaItem(FakeBaseItem):
    pass


class FakeImage:
    def __init__(self, payload: bytes = TEST_PNG) -> None:
        self.payload = payload

    def save(self, path: str | Path, fmt: str) -> None:
        Path(path).write_bytes(self.payload)


class FakePictureItem(FakeBaseItem):
    def __init__(self, *, image_bytes: bytes = TEST_PNG, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._image_bytes = image_bytes

    def get_image(self, _document) -> FakeImage:
        return FakeImage(self._image_bytes)


@dataclass
class FakeTableCell:
    start_row_offset_idx: int
    end_row_offset_idx: int
    start_col_offset_idx: int
    end_col_offset_idx: int
    text: str


class FakeTableData:
    def __init__(self, table_cells: list[FakeTableCell]) -> None:
        self.table_cells = table_cells


class FakeTableItem(FakeBaseItem):
    def __init__(
        self,
        *,
        markdown: str = "",
        table_cells: list[FakeTableCell] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._markdown = markdown
        self.data = FakeTableData(table_cells or [])

    def export_to_markdown(self, _document) -> str:
        return self._markdown


class FakeDoc:
    def __init__(self, items: list[tuple[Any, int]], page_count: int) -> None:
        self._items = items
        self.pages = {
            page_no: FakePage(page_no=page_no, size=FakePageSize())
            for page_no in range(1, page_count + 1)
        }

    def iterate_items(self):
        for item, level in self._items:
            yield item, level


def install_fake_docling(monkeypatch, parsers_module, document: FakeDoc) -> None:
    monkeypatch.setattr(parsers_module, "_convert_pdf_to_docling_document", lambda _pdf_path: document)
    monkeypatch.setattr(
        parsers_module,
        "_maybe_enrich_with_grobid",
        lambda _pdf_path: {
            "status": "disabled",
            "title": "",
            "authors": [],
            "abstract": "",
            "section_titles": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(parsers_module, "PictureItem", FakePictureItem)
    monkeypatch.setattr(parsers_module, "TableItem", FakeTableItem)
    monkeypatch.setattr(parsers_module, "FormulaItem", FakeFormulaItem)
    monkeypatch.setattr(parsers_module, "ListItem", FakeListItem)
    monkeypatch.setattr(parsers_module, "SectionHeaderItem", FakeSectionHeaderItem)
