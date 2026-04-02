# Default Retrieval Baseline Confirmation

## Default Configuration

```json
{
  "chunk_overlap_pct": 0.15,
  "chunking_mode": "paragraph",
  "embedding_backend": "sentence_transformer",
  "embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2",
  "fusion_strategy": "weighted",
  "paragraph_max_chars": 800,
  "paragraph_min_chars": 120,
  "rrf_k": 60,
  "weighted_alpha": 0.7,
  "weighted_beta": 0.3
}
```

This is the new default retrieval baseline because paragraph chunking produced cleaner evidence units,
weighted fusion surfaced more extraction-ready results than RRF in the benchmark, and the
sentence-transformer backend preserved explicit substrate evidence at the top of the text results.

## Command

```powershell
uv run python -m mvp.benchmark --input data/raw/paper_001/article.pdf --config-name paragraph_real_embedding
```

Run path: `C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T225908512486Z`

## Query: `substrate material`

Note: Top-3 text results explicit Rogers RT5880=yes; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3. The top text result contains explicit Rogers RT5880 evidence.

### Top text result

- `chunk:chunk_027` page=4 score=0.974362
  - snippet: The substrate material maintains the necessary distance between its ground plane and the patch and supports the radiating patch. ... We use copper as the ground and patch antenna, and Rogers RT5880(lossy) as the substrate for this antenna.
  - diagnostics: bm25_score=8.556719 dense_score=0.417279 bm25_rank=1 dense_rank=5 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.974362 rrf_score=None

### Top table result

No results.

### Top figure result

- `figure:fig_004` page=4 score=1.0
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... The most important criterion for determining the substrate in commercial applications is cost.
  - diagnostics: bm25_score=5.650411 dense_score=0.422419 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=1.0 rrf_score=None

## Query: `Rogers RT5880`

Note: Top-3 text results explicit Rogers RT5880=yes; exact query phrase in text snippets=yes; text_results=3, table_results=1, figure_results=1. The top text result contains explicit Rogers RT5880 evidence.

### Top text result

- `chunk:chunk_027` page=4 score=0.901115
  - snippet: We use copper as the ground and patch antenna, and Rogers RT5880(lossy) as the substrate for this antenna.
  - diagnostics: bm25_score=6.886568 dense_score=0.25678 bm25_rank=1 dense_rank=4 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.901115 rrf_score=None

### Top table result

- `table:table_002` page=10 score=0.3
  - snippet: Table 2 Spacial Parameter of Antenna array
Parameter | X-axis | Y-axis | Z-axis
Elements in x, y, z | 2 | 2 | 2
Space shift in x, y, z | 6 | 1 | 2
  - diagnostics: bm25_score=0.0 dense_score=0.196485 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.3 rrf_score=None

### Top figure result

- `figure:fig_008` page=8 score=0.3
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.209425 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.3 rrf_score=None

## Query: `VSWR`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=2. The top text result contains the exact query phrase.

### Top text result

- `chunk:chunk_054` page=8 score=0.978091
  - snippet: To some extent, VSWR can also be used to represent the power reflected by the antenna, as the reflection coefficient can calculate it. ... In the whole designed frequency band, VSWR is smaller than 1.8.
  - diagnostics: bm25_score=4.133406 dense_score=0.387683 bm25_rank=3 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.978091 rrf_score=None

### Top table result

No results.

### Top figure result

- `figure:fig_007` page=7 score=1.0
  - snippet: The amount of reflection can be evaluated by the VSWR. ... At this time, VSWR will be the smallest, which is 1.
  - diagnostics: bm25_score=3.350087 dense_score=0.287877 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=1.0 rrf_score=None

## Query: `input impedance`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3. The top text result contains the exact query phrase.

### Top text result

- `chunk:chunk_060` page=8 score=1.0
  - snippet: As the operating frequency band is from 27.864 to 28.14, the entire magnitude of input impedance ranges from 51Ω to 55Ω, which shows impedance matching is good in the whole frequency band. ... Impedance matching at such frequency bands guarantees good performance within the opera
  - diagnostics: bm25_score=5.599502 dense_score=0.522731 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=1.0 rrf_score=None

### Top table result

No results.

### Top figure result

- `figure:fig_008` page=8 score=1.0
  - snippet: Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’s input im
  - diagnostics: bm25_score=3.509195 dense_score=0.378966 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=1.0 rrf_score=None

## Query: `bandwidth`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=2. The top text result contains the exact query phrase.

### Top text result

- `chunk:chunk_048` page=7 score=0.966683
  - snippet: The tags within the reflection coefficient’s figure show that the bandwidth’s upper limit is 27.864 GHz, and the lower limit of the bandwidth is 28.14 GHz, giving us a bandwidth of 280 MHz.
  - diagnostics: bm25_score=4.845661 dense_score=0.376594 bm25_rank=1 dense_rank=3 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.966683 rrf_score=None

### Top table result

No results.

### Top figure result

- `figure:fig_008` page=8 score=0.3
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.222486 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=sentence_transformer weighted_score=0.3 rrf_score=None
