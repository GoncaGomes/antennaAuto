# Retrieval Test Commands And Results

## Context

These commands were run on `2026-04-02` inside this repository to test retrieval against the sample article:

- input PDF: `data/raw/paper_001/article.pdf`
- query expression: `substrate material`
- generated run: `runs/run_20260402T161653164815Z`

## 1. Build Parsed And Indexed Run

### Command

```powershell
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf --index
```

### Result

```text
Run path: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z
Generated files:
  - input PDF: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\input\article.pdf
  - metadata: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\bundle\metadata.json
  - fulltext: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\bundle\fulltext.md
  - sections: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\bundle\sections.json
  - parse report: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\bundle\parse_report.json
  - bm25 index: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\indexes\bm25
  - faiss index: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\indexes\faiss
  - graph: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\indexes\graph.json
  - index report: C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T161653164815Z\indexes\index_report.json
Summary: status=completed, figures=11, tables=2
Index summary: evidence_items=57
```

## 2. Original Retrieval Test Command

### Command

```powershell
@'
from pathlib import Path
from pprint import pprint
from mvp.retrieval import BundleRetriever

run_dir = Path(r"runs/run_20260402T161653164815Z")
query = "substrate material"

retriever = BundleRetriever(run_dir)

print("TEXT")
pprint(retriever.search_text(query, top_k=5))
print("\nTABLES")
pprint(retriever.search_tables(query, top_k=5))
print("\nFIGURES")
pprint(retriever.search_figures(query, top_k=5))
'@ | uv run python -
```

### Result

```text
TEXT
[{'evidence_id': 'chunk:chunk_010',
  'metadata': {'chunk_id': 'chunk_010'},
  'page_number': None,
  'score': 1.0,
  'snippet': 'Figure 1 depicts the proposed 5G microstrip patch antenna '
             'operating at 28 GHz. After choosing 28 GHz as the operating '
             'frequency, materials used for the antenna should be considered '
             'first. Three layers make up the antenna. The ground is the ',
  'source_id': 'chunk_010',
  'source_type': 'chunk'},
 {'evidence_id': 'section:page_004',
  'metadata': {'page_end': 4,
               'page_start': 4,
               'section_id': 'page_004',
               'text_excerpt': 'CONF-SPML-2023 Journal of Physics: Conference '
                               'Series (2023) 012063 '
                               'doi:10.1088/1742-6596/2580/1/012063 2. '
                               'Theoretical Analysis of Microstrip Patch '
                               'Antenna Figure 1 depicts the proposed 5G '
                               'microstrip patch antenna operating at 28 GHz. '
                               'After choosing 28 GHz as the operating '
                               'frequency, materials used for the antenna '
                               'should be considered first. Three layers make '
                               'up the antenna. The ground is the bottom '
                               'layer, the substrate is the middle layer, and '
                               'the patch antenna is the top layer. Typically, '
                               'copper foil is used to make the metallic '
                               'patch. The substrate material maintains the '
                               'necessary distance between its ground plane '
                               'and the patch and supports the radiating '
                               'patch. The most important criterion for '
                               'determining the substrate in commercial '
                               'applications is cost. By using the dielectric '
                               'honeycomb',
               'title': 'CONF-SPML-2023'},
  'page_number': 4,
  'score': 0.820732,
  'snippet': 'CONF-SPML-2023 CONF-SPML-2023 Journal of Physics: Conference '
             'Series (2023) 012063 doi:10.1088/1742-6596/2580/1/012063 2. '
             'Theoretical Analysis of Microstrip Patch Antenna Figure 1 '
             'depicts the proposed 5G microstrip patch antenna operating at',
  'source_id': 'page_004',
  'source_type': 'section'},
 {'evidence_id': 'chunk:chunk_013',
  'metadata': {'chunk_id': 'chunk_013'},
  'page_number': None,
  'score': 0.372729,
  'snippet': Traceback (most recent call last):
  File "<stdin>", line 11, in <module>
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 55, in pprint
    printer.pprint(object)
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 156, in pprint
    self._format(object, self._stream, 0, 0, {}, 0)
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 184, in _format
    p(self, object, stream, indent, allowance, context, level + 1)
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 241, in _pprint_list
    self._format_items(object, stream, indent, allowance + 1,
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 453, in _format_items
    self._format(ent, stream, indent,
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 184, in _format
    p(self, object, stream, indent, allowance, context, level + 1)
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 220, in _pprint_dict
    self._format_dict_items(items, stream, indent, allowance + 1,
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 391, in _format_dict_items
    self._format(ent, stream, indent + len(rep) + 2,
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 184, in _format
    p(self, object, stream, indent, allowance, context, level + 1)
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\pprint.py", line 321, in _pprint_str
    write(rep)
  File "C:\Users\Lenovo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode characters in position 1-4: character maps to <undefined>
```

## 3. UTF-8 Safe Rerun Of The Same Retrieval Query

The original retrieval command failed because Windows console output used a non-UTF-8 encoding. The query itself worked, but printing Unicode snippets failed. The following rerun used `PYTHONIOENCODING=utf-8`.

### Command

```powershell
$env:PYTHONIOENCODING='utf-8'; @'
from pathlib import Path
from pprint import pprint
from mvp.retrieval import BundleRetriever

run_dir = Path(r"runs/run_20260402T161653164815Z")
query = "substrate material"

retriever = BundleRetriever(run_dir)

print("TEXT")
pprint(retriever.search_text(query, top_k=5))
print("\nTABLES")
pprint(retriever.search_tables(query, top_k=5))
print("\nFIGURES")
pprint(retriever.search_figures(query, top_k=5))
'@ | uv run python -
```

### Result

```text
TEXT
[{'evidence_id': 'chunk:chunk_010',
  'metadata': {'chunk_id': 'chunk_010'},
  'page_number': None,
  'score': 1.0,
  'snippet': 'Figure 1 depicts the proposed 5G microstrip patch antenna '
             'operating at 28 GHz. After choosing 28 GHz as the operating '
             'frequency, materials used for the antenna should be considered '
             'first. Three layers make up the antenna. The ground is the ',
  'source_id': 'chunk_010',
  'source_type': 'chunk'},
 {'evidence_id': 'section:page_004',
  'metadata': {'page_end': 4,
               'page_start': 4,
               'section_id': 'page_004',
               'text_excerpt': 'CONF-SPML-2023 Journal of Physics: Conference '
                               'Series (2023) 012063 '
                               'doi:10.1088/1742-6596/2580/1/012063 2. '
                               'Theoretical Analysis of Microstrip Patch '
                               'Antenna Figure 1 depicts the proposed 5G '
                               'microstrip patch antenna operating at 28 GHz. '
                               'After choosing 28 GHz as the operating '
                               'frequency, materials used for the antenna '
                               'should be considered first. Three layers make '
                               'up the antenna. The ground is the bottom '
                               'layer, the substrate is the middle layer, and '
                               'the patch antenna is the top layer. Typically, '
                               'copper foil is used to make the metallic '
                               'patch. The substrate material maintains the '
                               'necessary distance between its ground plane '
                               'and the patch and supports the radiating '
                               'patch. The most important criterion for '
                               'determining the substrate in commercial '
                               'applications is cost. By using the dielectric '
                               'honeycomb',
               'title': 'CONF-SPML-2023'},
  'page_number': 4,
  'score': 0.820732,
  'snippet': 'CONF-SPML-2023 CONF-SPML-2023 Journal of Physics: Conference '
             'Series (2023) 012063 doi:10.1088/1742-6596/2580/1/012063 2. '
             'Theoretical Analysis of Microstrip Patch Antenna Figure 1 '
             'depicts the proposed 5G microstrip patch antenna operating at',
  'source_id': 'page_004',
  'source_type': 'section'},
 {'evidence_id': 'chunk:chunk_013',
  'metadata': {'chunk_id': 'chunk_013'},
  'page_number': None,
  'score': 0.372729,
  'snippet': '𝑊𝑝𝑎𝑡: 𝐿𝑝𝑎𝑡 affects the cross-polarization level. When 𝑊𝑝𝑎𝑡: 𝐿𝑝𝑎𝑡 '
             '= 1.5: 1, or roughly 21 dB below the co-polarized field, the '
             'cross-polarization is the least when applied to a patch feed at '
             'the edge. More extensive tests demonstrate that th',
  'source_id': 'chunk_013',
  'source_type': 'chunk'},
 {'evidence_id': 'chunk:chunk_030',
  'metadata': {'chunk_id': 'chunk_030'},
  'page_number': None,
  'score': 0.246151,
  'snippet': 'A microstrip patch antenna is now widely used in today’s 5G '
             'technology. Meanwhile, 5G is less of a single technology, like '
             '3G or 4G, but more of a pathway, which can enable many new '
             'technologies like IoT. Therefore, the microstrip patch ant',
  'source_id': 'chunk_030',
  'source_type': 'chunk'},
 {'evidence_id': 'chunk:chunk_002',
  'metadata': {'chunk_id': 'chunk_002'},
  'page_number': None,
  'score': 0.233871,
  'snippet': '**Abstract** . The advantages of microstrip patch antennas '
             'include small size, adaptable surface, ease of fabrication, and '
             'compatibility with integrated circuit technology. Numerous '
             'experiments have been done over the past few decades to en',
  'source_id': 'chunk_002',
  'source_type': 'chunk'}]

TABLES
[]

FIGURES
[{'evidence_id': 'figure:fig_004',
  'metadata': {'artifact_dir': 'C:\\Users\\Lenovo\\SynologyDrive\\PhD\\antennaAuto\\runs\\run_20260402T161653164815Z\\bundle\\figures\\fig_004',
               'caption': 'Figure 1 depicts the proposed 5G microstrip patch '
                          'antenna operating at 28 GHz. After choosing 28 GHz',
               'context': 'CONF-SPML-2023 Journal of Physics: Conference '
                          'Series (2023) 012063 '
                          'doi:10.1088/1742-6596/2580/1/012063 2. Theoretical '
                          'Analysis of Microstrip Patch Antenna Figure 1 '
                          'depicts the proposed 5G microstrip patch antenna '
                          'operating at 28 GHz. After choosing 28 GHz as the '
                          'operating frequency, materials used for the antenna '
                          'should be considered first. Three layers make up '
                          'the antenna. The ground is the bottom layer, the '
                          'substrate is the middle layer, and the patch '
                          'antenna is the top layer. Typically, copper foil is '
                          'used to make the metallic patch. The substrate '
                          'material maintains the necessary distance between '
                          'its ground plane and the patch and supports the '
                          'radiating patch. The most important criterion for '
                          'determining the substrate in commercial '
                          'applications is cost. By using the dielectric '
                          'honeycomb'},
  'page_number': 4,
  'score': 1.0,
  'snippet': 'Figure 1 depicts the proposed 5G microstrip patch antenna '
             'operating at 28 GHz. After choosing 28 GHz CONF-SPML-2023 '
             'Journal of Physics: Conference Series (2023) 012063 '
             'doi:10.1088/1742-6596/2580/1/012063 2. Theoretical Analysis of '
             'Microstri',
  'source_id': 'fig_004',
  'source_type': 'figure'},
 {'evidence_id': 'figure:fig_008',
  'metadata': {'artifact_dir': 'C:\\Users\\Lenovo\\SynologyDrive\\PhD\\antennaAuto\\runs\\run_20260402T161653164815Z\\bundle\\figures\\fig_008',
               'caption': 'Figure 5. Real part, imaginary part, magnitude of '
                          'Z11 on the operating frequency',
               'context': 'CONF-SPML-2023 Journal of Physics: Conference '
                          'Series 2580 (2023) 012063 IOP Publishing '
                          'doi:10.1088/1742-6596/2580/1/012063 7 the real '
                          'part, the imaginary part, and the whole magnitude '
                          'of the antenna’s input impedance. The real part of '
                          'impedance, represented by the blue curve, moves '
                          'around from 27 GHz to 28 GHz and reaches about 33Ω '
                          'at 28 GHz. The overall trend of impedance’s real '
                          'part from 27 GHz to 28 GHz is stable, but then it '
                          'grows over 4 times after 28 GHz and reaches its '
                          'peak of 182 Ω at 28.6 GHz. The imaginary part of '
                          'impedance, represented by the orange curve, '
                          'declines rapidly from 150Ω to 0Ω at the frequency '
                          'range 27 GHz – 28.3 GHz and reaches about 40Ω at 28 '
                          'GHz. Within the frequency range 27GHz - 28.3 GHz, '
                          'the imaginary part of impedance decreases almost '
                          'linearly from 150Ω to 0Ω,'},
  'page_number': 8,
  'score': 0.153955,
  'snippet': 'Figure 5. Real part, imaginary part, magnitude of Z11 on the '
             'operating frequency CONF-SPML-2023 Journal of Physics: '
             'Conference Series 2580 (2023) 012063 IOP Publishing '
             'doi:10.1088/1742-6596/2580/1/012063 7 the real part, the '
             'imaginary part,',
  'source_id': 'fig_008',
  'source_type': 'figure'}]
```

## Short Reading Of The Result

- `search_text("substrate material")` returned relevant text evidence from page 4 and nearby fulltext chunks.
- `search_figures("substrate material")` returned figure evidence whose caption/context mentions the same material discussion.
- `search_tables("substrate material")` returned no results for this expression, which is plausible because the structured tables are dimensions-oriented rather than materials-oriented.
