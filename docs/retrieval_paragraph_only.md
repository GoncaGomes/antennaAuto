# Retrieval Benchmark: paragraph_only

## Configuration

```json
{
  "chunk_overlap_pct": 0.15,
  "chunking_mode": "paragraph",
  "embedding_backend": "hash",
  "embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2",
  "fusion_strategy": "weighted",
  "paragraph_max_chars": 800,
  "paragraph_min_chars": 120,
  "rrf_k": 60,
  "weighted_alpha": 0.7,
  "weighted_beta": 0.3
}
```

## Command

```powershell
uv run python -m mvp.benchmark --input data/raw/paper_001/article.pdf --config-name paragraph_only
```

Run path: `C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T222342272741Z`

## Query: `substrate material`

Note: Top-3 text results explicit Rogers RT5880=yes; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=2.

### search_text

- `chunk:chunk_027` page=4 score=1.0
  - snippet: The substrate material maintains the necessary distance between its ground plane and the patch and supports the radiating patch. ... We use copper as the ground and patch antenna, and Rogers RT5880(lossy) as the substrate for this antenna.
  - diagnostics: bm25_score=8.556719 dense_score=0.320173 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_026` page=4 score=0.754642
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... The most important criterion for determining the substrate in commercial applications is cost.
  - diagnostics: bm25_score=6.546159 dense_score=0.233854 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.754642 rrf_score=None
- `section:page_004` page=4 score=0.693957
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... The most important criterion for determining the substrate in commercial applications is cost.
  - diagnostics: bm25_score=5.984653 dense_score=0.218112 bm25_rank=3 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.693957 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_004` page=4 score=1.0
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... The most important criterion for determining the substrate in commercial applications is cost.
  - diagnostics: bm25_score=5.650411 dense_score=0.281495 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_008` page=8 score=0.153955
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.144458 bm25_rank=None dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.153955 rrf_score=None

## Query: `Rogers RT5880`

Note: Top-3 text results explicit Rogers RT5880=yes; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_027` page=4 score=0.860021
  - snippet: We use copper as the ground and patch antenna, and Rogers RT5880(lossy) as the substrate for this antenna.
  - diagnostics: bm25_score=6.886568 dense_score=0.091478 bm25_rank=1 dense_rank=2 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.860021 rrf_score=None
- `chunk:chunk_010` page=4 score=0.656629
  - snippet: In the design, Rogers RT5880 substrate and copper ground are used.
  - diagnostics: bm25_score=5.778561 dense_score=0.03959 bm25_rank=2 dense_rank=6 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.656629 rrf_score=None
- `chunk:chunk_006` page=1 score=0.3
  - snippet: **==> picture [521 x 337] intentionally omitted <==**

This content was downloaded from IP address 193.137.169.166 on 16/09/2025 at 11:13
  - diagnostics: bm25_score=0.0 dense_score=0.171499 bm25_rank=None dense_rank=1 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_003` page=1 score=0.3
  - snippet: Caption extraction not implemented.
Journal of Physics: Conference Series PAPER • OPEN ACCESS A microstrip patch antenna for 5G mobile communications To cite this article: Yitong Li 2023 J. Phys.: Conf. Ser. 2580 012063 View the article online for updates and enhancements. You ma
  - diagnostics: bm25_score=0.0 dense_score=0.055728 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None
- `figure:fig_002` page=1 score=0.3
  - snippet: Caption extraction not implemented.
Journal of Physics: Conference Series PAPER • OPEN ACCESS A microstrip patch antenna for 5G mobile communications To cite this article: Yitong Li 2023 J. Phys.: Conf. Ser. 2580 012063 View the article online for updates and enhancements. You ma
  - diagnostics: bm25_score=0.0 dense_score=0.055728 bm25_rank=None dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None
- `figure:fig_001` page=1 score=0.3
  - snippet: Caption extraction not implemented.
Journal of Physics: Conference Series PAPER • OPEN ACCESS A microstrip patch antenna for 5G mobile communications To cite this article: Yitong Li 2023 J. Phys.: Conf. Ser. 2580 012063 View the article online for updates and enhancements. You ma
  - diagnostics: bm25_score=0.0 dense_score=0.055728 bm25_rank=None dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None

## Query: `inset feed`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=2.

### search_text

- `chunk:chunk_038` page=6 score=1.0
  - snippet: Meanwhile, as the feeding line also radiates power towards the outside, interfering with the antenna’s radiation pattern, the microstrip line’s width is limited. ... Here we use inset feed as it will be easy to do impedance matching using this feeding method.
  - diagnostics: bm25_score=7.298157 dense_score=0.310253 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_045` page=7 score=0.605355
  - snippet: **==> picture [143 x 198] intentionally omitted <==**

**Figure 2.** The schematic diagram of inset feeding

As using edge feed always brings large input impedance, altering the feeding position to the antenna’s center can be better for the current at both ends is generally low b
  - diagnostics: bm25_score=4.871189 dense_score=0.142857 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.605355 rrf_score=None
- `chunk:chunk_023` page=7 score=0.495443
  - snippet: Then introduce the way of feeding – inset feed, which also includes how to make impedance matching meet the requirement within the operating frequency band.
  - diagnostics: bm25_score=4.078349 dense_score=0.107833 bm25_rank=4 dense_rank=8 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.495443 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_005` page=6 score=0.7
  - snippet: The schematic diagram of inset feeding
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 5 From equations (7-8), it can be derived that the maximum value can be obtained when R equals r.
  - diagnostics: bm25_score=2.016284 dense_score=0.0 bm25_rank=1 dense_rank=None final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.7 rrf_score=None
- `figure:fig_008` page=8 score=0.3
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.086675 bm25_rank=None dense_rank=1 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None

## Query: `VSWR`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_054` page=8 score=0.978091
  - snippet: To some extent, VSWR can also be used to represent the power reflected by the antenna, as the reflection coefficient can calculate it. ... In the whole designed frequency band, VSWR is smaller than 1.8.
  - diagnostics: bm25_score=4.133406 dense_score=0.417554 bm25_rank=3 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.978091 rrf_score=None
- `chunk:chunk_052` page=7 score=0.864482
  - snippet: The amount of reflection can be evaluated by the VSWR. ... More specifically, for the reflection coefficient’s threshold of acceptance in the proposed antenna, its corresponding VSWR is 1.22.
  - diagnostics: bm25_score=4.266958 dense_score=0.228934 bm25_rank=1 dense_rank=6 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.864482 rrf_score=None
- `chunk:chunk_053` page=7 score=0.854755
  - snippet: More specifically, for the reflection coefficient’s threshold of acceptance in the proposed antenna, its corresponding VSWR is 1.22. ... For the peak of the reflection coefficient, which is -24 dB, its corresponding VSWR is 1.008.
  - diagnostics: bm25_score=4.224818 dense_score=0.225018 bm25_rank=2 dense_rank=9 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.854755 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_007` page=7 score=1.0
  - snippet: The amount of reflection can be evaluated by the VSWR. ... At this time, VSWR will be the smallest, which is 1.
  - diagnostics: bm25_score=3.350087 dense_score=0.218844 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_006` page=7 score=1.0
  - snippet: The amount of reflection can be evaluated by the VSWR. ... At this time, VSWR will be the smallest, which is 1.
  - diagnostics: bm25_score=3.350087 dense_score=0.218844 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_008` page=8 score=0.168033
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.122577 bm25_rank=None dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.168033 rrf_score=None

## Query: `input impedance`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_056` page=7 score=0.986571
  - snippet: Generally, transmission line’s impedance is 50Ω. ... Therefore, impedance match requires the antenna’s entire input impedance to reach approximately 50Ω at operating frequency.
  - diagnostics: bm25_score=5.492082 dense_score=0.436436 bm25_rank=2 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.986571 rrf_score=None
- `chunk:chunk_060` page=8 score=0.951523
  - snippet: As the operating frequency band is from 27.864 to 28.14, the entire magnitude of input impedance ranges from 51Ω to 55Ω, which shows impedance matching is good in the whole frequency band. ... Impedance matching at such frequency bands guarantees good performance within the opera
  - diagnostics: bm25_score=5.599502 dense_score=0.365911 bm25_rank=1 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.951523 rrf_score=None
- `chunk:chunk_045` page=7 score=0.814049
  - snippet: **==> picture [143 x 198] intentionally omitted <==**

**Figure 2.** The schematic diagram of inset feeding

As using edge feed always brings large input impedance, altering the feeding position to the antenna’s center can be better for the current at both ends is generally low b
  - diagnostics: bm25_score=4.940787 dense_score=0.285714 bm25_rank=3 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.814049 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_008` page=8 score=1.0
  - snippet: Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’s input im
  - diagnostics: bm25_score=3.509195 dense_score=0.144458 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_007` page=7 score=0.475871
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=2.385604 dense_score=0.0 bm25_rank=2 dense_rank=None final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.475871 rrf_score=None
- `figure:fig_006` page=7 score=0.475871
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=2.385604 dense_score=0.0 bm25_rank=3 dense_rank=None final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.475871 rrf_score=None

## Query: `gain`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_062` page=6 score=1.0
  - snippet: The antenna’s gain is another parameter that must be considered when designing. ... At 27 GHz, the gain is less than -5 dBi.
  - diagnostics: bm25_score=4.089534 dense_score=0.346128 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_063` page=8 score=0.97003
  - snippet: Figure 6 shows the trend of realized gain and reflection coefficient versus frequency. ... The antenna’s gain within the operating frequency band can meet the requirement of a mobile antenna.
  - diagnostics: bm25_score=4.05913 dense_score=0.317554 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.97003 rrf_score=None
- `chunk:chunk_065` page=9 score=0.802273
  - snippet: **==> picture [341 x 191] intentionally omitted <==**

**Figure 6.** Gain vs. ... By doing this, the main lobe’s direction and its gain can be influenced, side lobes’ gain and direction can also be influenced.
  - diagnostics: bm25_score=3.547628 dense_score=0.225018 bm25_rank=3 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.802273 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_010` page=9 score=1.0
  - snippet: Gain vs. ... By doing this, the main lobe’s direction and its gain can be influenced, side lobes’ gain and direction can also be influenced.
  - diagnostics: bm25_score=3.468989 dense_score=0.224662 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_009` page=9 score=1.0
  - snippet: Gain vs. ... By doing this, the main lobe’s direction and its gain can be influenced, side lobes’ gain and direction can also be influenced.
  - diagnostics: bm25_score=3.468989 dense_score=0.224662 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_008` page=8 score=0.05456
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.040859 bm25_rank=None dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.05456 rrf_score=None

## Query: `reflection coefficient`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_053` page=7 score=1.0
  - snippet: More specifically, for the reflection coefficient’s threshold of acceptance in the proposed antenna, its corresponding VSWR is 1.22. ... For the peak of the reflection coefficient, which is -24 dB, its corresponding VSWR is 1.008.
  - diagnostics: bm25_score=5.781236 dense_score=0.397779 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_047` page=7 score=0.904213
  - snippet: For an antenna, the smaller its reflection coefficient, the better performance it will get. ... The tags within the reflection coefficient’s figure show that the bandwidth’s upper limit is 27.864 GHz, and the lower limit of the bandwidth is 28.14 GHz, giving us a bandwidth of 280
  - diagnostics: bm25_score=5.632643 dense_score=0.294628 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.904213 rrf_score=None
- `chunk:chunk_046` page=7 score=0.851229
  - snippet: In this way, there’re 4 coefficients obtained from VNA. ... For an antenna, the smaller its reflection coefficient, the better performance it will get.
  - diagnostics: bm25_score=5.354257 dense_score=0.269069 bm25_rank=3 dense_rank=4 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.851229 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_007` page=7 score=1.0
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=4.577005 dense_score=0.185695 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_006` page=7 score=1.0
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=4.577005 dense_score=0.185695 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_005` page=6 score=0.173349
  - snippet: Low-frequency signals have wavelengths significantly greater than the transmission line’s length since the relationship between wavelength and frequency is inverse, making it unnecessary to consider signal reflection in this situation.
  - diagnostics: bm25_score=1.133454 dense_score=0.0 bm25_rank=3 dense_rank=None final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.173349 rrf_score=None

## Query: `bandwidth`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=1, figure_results=2.

### search_text

- `chunk:chunk_048` page=7 score=1.0
  - snippet: The tags within the reflection coefficient’s figure show that the bandwidth’s upper limit is 27.864 GHz, and the lower limit of the bandwidth is 28.14 GHz, giving us a bandwidth of 280 MHz.
  - diagnostics: bm25_score=4.845661 dense_score=0.286039 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_021` page=1 score=0.699285
  - snippet: A high-frequency range with a wide bandwidth can be provided using 5G in the millimeter wave band. ... More specifically, There is a great demand for uninterrupted high-stream online education worldwide, especially in developing countries, and this application scenario has high d
  - diagnostics: bm25_score=3.670616 dense_score=0.161165 bm25_rank=3 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.699285 rrf_score=None
- `chunk:chunk_047` page=7 score=0.664427
  - snippet: Generally, the frequency band corresponding to half of the reflection coefficient’s peak can be considered the antenna’s bandwidth. ... The tags within the reflection coefficient’s figure show that the bandwidth’s upper limit is 27.864 GHz, and the lower limit of the bandwidth is
  - diagnostics: bm25_score=3.691879 dense_score=0.125 bm25_rank=2 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.664427 rrf_score=None

### search_tables

- `table:table_002` page=10 score=0.3
  - snippet: Table 2 Spacial Parameter of Antenna array
Parameter | X-axis | Y-axis | Z-axis
Elements in x, y, z | 2 | 2 | 2
Space shift in x, y, z | 6 | 1 | 2
  - diagnostics: bm25_score=0.0 dense_score=0.121268 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None

### search_figures

- `figure:fig_010` page=9 score=0.3
  - snippet: Figure 6. Gain vs. Frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 8 As the antenna’s gain is highly related to its radiation pattern. Radiation patterns need to be carefully designed to meet our
  - diagnostics: bm25_score=0.0 dense_score=0.056166 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None
- `figure:fig_009` page=9 score=0.3
  - snippet: Figure 6. Gain vs. Frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 8 As the antenna’s gain is highly related to its radiation pattern. Radiation patterns need to be carefully designed to meet our
  - diagnostics: bm25_score=0.0 dense_score=0.056166 bm25_rank=None dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=paragraph embedding_backend=hash weighted_score=0.3 rrf_score=None
