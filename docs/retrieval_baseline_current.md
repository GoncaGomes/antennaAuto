# Retrieval Benchmark: baseline_current

## Configuration

```json
{
  "chunk_overlap_pct": 0.15,
  "chunking_mode": "fixed",
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
uv run python -m mvp.benchmark --input data/raw/paper_001/article.pdf --config-name baseline_current
```

Run path: `C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto\runs\run_20260402T222333279500Z`

## Query: `substrate material`

Note: Top-3 text results explicit Rogers RT5880=yes; exact query phrase in text snippets=no; text_results=3, table_results=0, figure_results=2.

### search_text

- `chunk:chunk_010` page=4 score=1.0
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... We use copper as the ground and patch antenna, and Rogers RT5880(lossy) as the substrate for this antenna.
  - diagnostics: bm25_score=7.447943 dense_score=0.278682 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `section:page_004` page=4 score=0.820732
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... The most important criterion for determining the substrate in commercial applications is cost.
  - diagnostics: bm25_score=6.234308 dense_score=0.218112 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.820732 rrf_score=None
- `chunk:chunk_013` page=5 score=0.372729
  - snippet: More extensive tests demonstrate that the cross-polarized to co-polarized ratios vary on substrate thickness, resonance frequencies and feed position. ... Where 𝜀𝑟 is the relative dielectric constant, 𝐿𝑝𝑎𝑡 is the length of patch, ℎ is height of the substrate.
  - diagnostics: bm25_score=3.084745 dense_score=0.076923 bm25_rank=3 dense_rank=7 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.372729 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_004` page=4 score=1.0
  - snippet: After choosing 28 GHz as the operating frequency, materials used for the antenna should be considered first. ... The most important criterion for determining the substrate in commercial applications is cost.
  - diagnostics: bm25_score=5.968048 dense_score=0.281495 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_008` page=8 score=0.153955
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.144458 bm25_rank=None dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.153955 rrf_score=None

## Query: `Rogers RT5880`

Note: Top-3 text results explicit Rogers RT5880=yes; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_010` page=4 score=0.923406
  - snippet: We use copper as the ground and patch antenna, and Rogers RT5880(lossy) as the substrate for this antenna.
  - diagnostics: bm25_score=5.605942 dense_score=0.050669 bm25_rank=1 dense_rank=3 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.923406 rrf_score=None
- `chunk:chunk_002` page=2 score=0.717255
  - snippet: In the design, Rogers RT5880 substrate and copper ground are used.
  - diagnostics: bm25_score=4.787352 dense_score=0.027096 bm25_rank=2 dense_rank=6 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.717255 rrf_score=None
- `chunk:chunk_001` page=1 score=0.3
  - snippet: - An off-center fed patch antenna with overlapping sub-patch for simultaneous crack and temperature sensing Xianzhi Li, Songtao Xue, Liyu Xie et al.

- Wideband terahertz imaging pixel with a small on-chip antenna in 180 nm CMOS Yuri Kanazawa, Sayuri Yokoyama, Shota Hiramatsu et 
  - diagnostics: bm25_score=0.0 dense_score=0.068041 bm25_rank=None dense_rank=1 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_003` page=1 score=0.3
  - snippet: Caption extraction not implemented.
Journal of Physics: Conference Series PAPER • OPEN ACCESS A microstrip patch antenna for 5G mobile communications To cite this article: Yitong Li 2023 J. Phys.: Conf. Ser. 2580 012063 View the article online for updates and enhancements. You ma
  - diagnostics: bm25_score=0.0 dense_score=0.055728 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None
- `figure:fig_002` page=1 score=0.3
  - snippet: Caption extraction not implemented.
Journal of Physics: Conference Series PAPER • OPEN ACCESS A microstrip patch antenna for 5G mobile communications To cite this article: Yitong Li 2023 J. Phys.: Conf. Ser. 2580 012063 View the article online for updates and enhancements. You ma
  - diagnostics: bm25_score=0.0 dense_score=0.055728 bm25_rank=None dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None
- `figure:fig_001` page=1 score=0.3
  - snippet: Caption extraction not implemented.
Journal of Physics: Conference Series PAPER • OPEN ACCESS A microstrip patch antenna for 5G mobile communications To cite this article: Yitong Li 2023 J. Phys.: Conf. Ser. 2580 012063 View the article online for updates and enhancements. You ma
  - diagnostics: bm25_score=0.0 dense_score=0.055728 bm25_rank=None dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None

## Query: `inset feed`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=2.

### search_text

- `chunk:chunk_014` page=9 score=1.0
  - snippet: What should be considered is how to feed the antenna. ... Here we use inset feed as it will be easy to do impedance matching using this feeding method.
  - diagnostics: bm25_score=6.773963 dense_score=0.28043 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_009` page=7 score=0.412867
  - snippet: Then introduce the way of feeding – inset feed, which also includes how to make impedance matching meet the requirement within the operating frequency band.
  - diagnostics: bm25_score=3.62609 dense_score=0.035669 bm25_rank=2 dense_rank=14 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.412867 rrf_score=None
- `section:page_003` page=3 score=0.392029
  - snippet: Journal of Physics: Conference Series
Journal of Physics: Conference Series (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 2 commonly used in microstrip patch antenna: coaxial feed, microstrip line feed, and aperture-coupled feed.
  - diagnostics: bm25_score=2.354998 dense_score=0.138972 bm25_rank=6 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.392029 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_005` page=6 score=0.834119
  - snippet: The schematic diagram of inset feeding
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 5 From equations (7-8), it can be derived that the maximum value can be obtained when R equals r.
  - diagnostics: bm25_score=2.510073 dense_score=0.038749 bm25_rank=1 dense_rank=2 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.834119 rrf_score=None
- `figure:fig_008` page=8 score=0.3
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.086675 bm25_rank=None dense_rank=1 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None

## Query: `VSWR`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_021` page=8 score=0.967506
  - snippet: To some extent, VSWR can also be used to represent the power reflected by the antenna, as the reflection coefficient can calculate it. ... In the whole designed frequency band, VSWR is smaller than 1.8.
  - diagnostics: bm25_score=3.867884 dense_score=0.417554 bm25_rank=2 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.967506 rrf_score=None
- `chunk:chunk_020` page=7 score=0.874683
  - snippet: The amount of reflection can be evaluated by the VSWR. ... For the peak of the reflection coefficient, which is -24 dB, its corresponding VSWR is 1.008.
  - diagnostics: bm25_score=4.05617 dense_score=0.243132 bm25_rank=1 dense_rank=3 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.874683 rrf_score=None
- `section:page_007` page=7 score=0.715947
  - snippet: The amount of reflection can be evaluated by the VSWR. ... At this time, VSWR will be the smallest, which is 1.
  - diagnostics: bm25_score=3.374657 dense_score=0.185896 bm25_rank=3 dense_rank=6 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.715947 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_007` page=7 score=1.0
  - snippet: The amount of reflection can be evaluated by the VSWR. ... At this time, VSWR will be the smallest, which is 1.
  - diagnostics: bm25_score=3.301004 dense_score=0.218844 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_006` page=7 score=1.0
  - snippet: The amount of reflection can be evaluated by the VSWR. ... At this time, VSWR will be the smallest, which is 1.
  - diagnostics: bm25_score=3.301004 dense_score=0.218844 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_008` page=8 score=0.168033
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.122577 bm25_rank=None dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.168033 rrf_score=None

## Query: `input impedance`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_022` page=7 score=1.0
  - snippet: Generally, transmission line’s impedance is 50Ω. ... Therefore, impedance match requires the antenna’s entire input impedance to reach approximately 50Ω at operating frequency.
  - diagnostics: bm25_score=4.344317 dense_score=0.436436 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_017` page=7 score=0.915087
  - snippet: As using edge feed always brings large input impedance, altering the feeding position to the antenna’s center can be better for the current at both ends is generally low but relatively higher towards the center. ... This way, we can effectively decrease the input impedance and ma
  - diagnostics: bm25_score=4.312959 dense_score=0.320256 bm25_rank=3 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.915087 rrf_score=None
- `chunk:chunk_023` page=8 score=0.879394
  - snippet: the real part, the imaginary part, and the whole magnitude of the antenna’s input impedance. ... Impedance matching at such frequency bands guarantees good performance within the operating frequency.
  - diagnostics: bm25_score=4.317885 dense_score=0.267176 bm25_rank=2 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.879394 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_008` page=8 score=1.0
  - snippet: Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’s input im
  - diagnostics: bm25_score=3.159136 dense_score=0.144458 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_007` page=7 score=0.643732
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=2.325059 dense_score=0.061898 bm25_rank=2 dense_rank=3 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.643732 rrf_score=None
- `figure:fig_006` page=7 score=0.643732
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=2.325059 dense_score=0.061898 bm25_rank=3 dense_rank=4 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.643732 rrf_score=None

## Query: `gain`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_025` page=6 score=1.0
  - snippet: The antenna’s gain is another parameter that must be considered when designing. ... The antenna’s gain within the operating frequency band can meet the requirement of a mobile antenna.
  - diagnostics: bm25_score=3.75833 dense_score=0.353189 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `section:page_009` page=9 score=0.707716
  - snippet: CONF-SPML-2023
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 8 As the antenna’s gain is highly related to its radiation pattern. ... By doing this, the main lobe’s direction and its gain can be influence
  - diagnostics: bm25_score=3.021444 dense_score=0.170664 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.707716 rrf_score=None
- `chunk:chunk_026` page=9 score=0.580271
  - snippet: As the antenna’s gain is highly related to its radiation pattern. ... By doing this, the main lobe’s direction and its gain can be influenced, side lobes’ gain and direction can also be influenced.
  - diagnostics: bm25_score=2.613575 dense_score=0.110059 bm25_rank=3 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.580271 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_010` page=9 score=1.0
  - snippet: Gain vs. ... By doing this, the main lobe’s direction and its gain can be influenced, side lobes’ gain and direction can also be influenced.
  - diagnostics: bm25_score=3.272904 dense_score=0.224662 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_009` page=9 score=1.0
  - snippet: Gain vs. ... By doing this, the main lobe’s direction and its gain can be influenced, side lobes’ gain and direction can also be influenced.
  - diagnostics: bm25_score=3.272904 dense_score=0.224662 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_008` page=8 score=0.05456
  - snippet: Figure 5. Real part, imaginary part, magnitude of Z11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 7 the real part, the imaginary part, and the whole magnitude of the antenna’
  - diagnostics: bm25_score=0.0 dense_score=0.040859 bm25_rank=None dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.05456 rrf_score=None

## Query: `reflection coefficient`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=0, figure_results=3.

### search_text

- `chunk:chunk_018` page=7 score=1.0
  - snippet: In this way, there’re 4 coefficients obtained from VNA. ... In order to get a better reflection coefficient, we have to make the antenna’s input impedance
  - diagnostics: bm25_score=5.564862 dense_score=0.319599 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `chunk:chunk_020` page=7 score=0.948297
  - snippet: The amount of reflection can be evaluated by the VSWR. ... For the peak of the reflection coefficient, which is -24 dB, its corresponding VSWR is 1.008.
  - diagnostics: bm25_score=5.400577 dense_score=0.286534 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.948297 rrf_score=None
- `section:page_007` page=7 score=0.77402
  - snippet: CONF-SPML-2023
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will greatly influence the reflection coefficient. ... T
  - diagnostics: bm25_score=4.68195 dense_score=0.197172 bm25_rank=3 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.77402 rrf_score=None

### search_tables

No results.

### search_figures

- `figure:fig_007` page=7 score=1.0
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=4.581876 dense_score=0.185695 bm25_rank=1 dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_006` page=7 score=1.0
  - snippet: Block diagram of S-parameter and S11 on the operating frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 6 match the transmission line’s reference impedance at the operating frequency, which will gr
  - diagnostics: bm25_score=4.581876 dense_score=0.185695 bm25_rank=2 dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=1.0 rrf_score=None
- `figure:fig_005` page=6 score=0.251175
  - snippet: Low-frequency signals have wavelengths significantly greater than the transmission line’s length since the relationship between wavelength and frequency is inverse, making it unnecessary to consider signal reflection in this situation.
  - diagnostics: bm25_score=1.234319 dense_score=0.038749 bm25_rank=3 dense_rank=3 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.251175 rrf_score=None

## Query: `bandwidth`

Note: Top-3 text results explicit Rogers RT5880=no; exact query phrase in text snippets=yes; text_results=3, table_results=1, figure_results=2.

### search_text

- `chunk:chunk_018` page=7 score=0.939166
  - snippet: Generally, the frequency band corresponding to half of the reflection coefficient’s peak can be considered the antenna’s bandwidth. ... The tags within the reflection coefficient’s figure show that the bandwidth’s upper limit is 27.864 GHz, and the lower limit of the bandwidth is
  - diagnostics: bm25_score=3.408487 dense_score=0.07533 bm25_rank=1 dense_rank=2 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.939166 rrf_score=None
- `chunk:chunk_008` page=3 score=0.632794
  - snippet: A high-frequency range with a wide bandwidth can be provided using 5G in the millimeter wave band. ... More specifically, There is a great demand for uninterrupted high-stream online education worldwide, especially in developing countries, and this application scenario has high d
  - diagnostics: bm25_score=2.559513 dense_score=0.033748 bm25_rank=2 dense_rank=8 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.632794 rrf_score=None
- `chunk:chunk_029` page=10 score=0.625225
  - snippet: The antenna’s bandwidth is 280 MHz, with a lower operating frequency of 27.864GHz and an upper operating frequency of 28.14 GHz.
  - diagnostics: bm25_score=2.356453 dense_score=0.044499 bm25_rank=3 dense_rank=5 final_rank=3 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.625225 rrf_score=None

### search_tables

- `table:table_002` page=10 score=0.3
  - snippet: Table 2 Spacial Parameter of Antenna array
Parameter | X-axis | Y-axis | Z-axis
Elements in x, y, z | 2 | 2 | 2
Space shift in x, y, z | 6 | 1 | 2
  - diagnostics: bm25_score=0.0 dense_score=0.121268 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None

### search_figures

- `figure:fig_010` page=9 score=0.3
  - snippet: Figure 6. Gain vs. Frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 8 As the antenna’s gain is highly related to its radiation pattern. Radiation patterns need to be carefully designed to meet our
  - diagnostics: bm25_score=0.0 dense_score=0.056166 bm25_rank=None dense_rank=1 final_rank=1 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None
- `figure:fig_009` page=9 score=0.3
  - snippet: Figure 6. Gain vs. Frequency
CONF-SPML-2023 Journal of Physics: Conference Series 2580 (2023) 012063 IOP Publishing doi:10.1088/1742-6596/2580/1/012063 8 As the antenna’s gain is highly related to its radiation pattern. Radiation patterns need to be carefully designed to meet our
  - diagnostics: bm25_score=0.0 dense_score=0.056166 bm25_rank=None dense_rank=2 final_rank=2 fusion_strategy=weighted chunking_mode=fixed embedding_backend=hash weighted_score=0.3 rrf_score=None
