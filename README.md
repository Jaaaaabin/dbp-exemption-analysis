# DBP Exemption Analysis

A Python project for loading, cleaning, parsing, and analysing Digital Building Permit (DBP) exemption data from Excel, built with [uv](https://github.com/astral-sh/uv) for dependency management.

## Project Structure

```
dbp/
├── config/
│   └── path.yaml                    # data-folder and analysis-type settings
├── data/
│   ├── raw/                         # source Excel files (not tracked)
│   └── cleaned/                     # pipeline outputs (not tracked)
│       ├── data_cleaned.csv / .json
│       ├── data_cleaned_enriched.json
│       ├── data_out_exemption.csv / .json
│       └── data_out_regulation.csv / .json
├── res/
│   └── figures/                     # generated plot PNGs
├── src/
│   ├── configuration.py             # config loader (path.yaml + env-var substitution)
│   ├── data_clean.py                # Excel ingestion, DataFrame cleaning, JSON key normalisation
│   ├── data_filter.py               # filtering and subset splitting
│   ├── data_analysis.py             # descriptive statistics and aggregations (JSON-based)
│   ├── text_parser.py               # structured parsing of long text fields + record enrichment
│   ├── visualize.py                 # matplotlib/seaborn plots from enriched records
│   └── utils/
│       ├── cli_utils.py             # spinner, progress bars, coloured output
│       ├── env_utils.py             # system info display and directory tree printer
│       └── time_utils.py            # @measure_runtime decorator for function timing
├── extract.py                       # ETL pipeline: Excel → cleaned CSV + JSON outputs
├── analyze.py                       # enrichment + statistics + visualizations
├── warmup.py                        # environment summary (system info, directory tree)
├── pyproject.toml
└── uv.lock
```

## Setup

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed
- Python 3.11+

### Installation

```bash
uv sync
```

### Configuration

Paths are resolved from `config/path.yaml`. The default setup expects:

```
data/raw/data.xlsx     ← source file
data/cleaned/          ← output directory (auto-created)
```

## Workflow

### Step 1 — Extract & clean

Reads the source Excel, cleans the data, splits it into three subsets, and writes both CSV and JSON outputs.

```bash
uv run python extract.py
```

Outputs written to `data/cleaned/`:

| File | Contents |
|---|---|
| `data_cleaned.csv / .json` | Rows where both key columns are present |
| `data_out_exemption.csv / .json` | Rows missing `Granted Exemptions` |
| `data_out_regulation.csv / .json` | Rows missing `Building regulations and requirements` |

JSON files use normalised snake_case keys (e.g. `time_for_decision_months`, `parcel_code_2_plus`). Column name → key conversion is handled by `columns_to_json_keys()` in `src/data_clean.py`.

### Step 2 — Analyse & visualise

Enriches records by parsing long text fields, runs descriptive statistics and aggregations, then generates all standard plots.

```bash
uv run python analyze.py
```

Select the target file by setting `JSON_FILE` at the top of `analyze.py`:

```python
JSON_FILE = Path("data/cleaned/data_cleaned.json")
# JSON_FILE = Path("data/cleaned/data_out_exemption.json")
# JSON_FILE = Path("data/cleaned/data_out_regulation.json")
```

**What it does:**

1. Calls `enrich_json()` from `src/text_parser.py` to parse all structured text fields and writes the result to `data_cleaned_enriched.json`.
2. Runs numeric summaries, correlations, groupby aggregations (by permit type, exemption type, plan type, issuing authority), subset comparisons, and outlier detection via `src/data_analysis.py`.
3. Saves all standard plots to `res/figures/` via `src/visualize.py`.

**Generated figures:**

| File | Contents |
|---|---|
| `exemption_overview.png` | Count + mean decision time per exemption type |
| `decision_time_by_authority.png` | Mean decision time per issuing authority |
| `decision_time_by_exemption_type.png` | Mean decision time per exemption type |
| `decision_time_by_plan_type.png` | Mean decision time by plan type (Bebauungsplan vs Baustufenplan) |
| `decision_time_by_plan_primary_type.png` | Mean decision time by plan reference type |
| `decision_time_distribution.png` | Histogram with median and mean lines |
| `correlation_heatmap.png` | Pearson correlations among numeric columns |
| `subset_comparison.png` | Mean decision time across all three data subsets |

## Source modules

| Module | Purpose |
|---|---|
| `data_clean.py` | Excel ingestion, cleaning, CSV/JSON export |
| `data_filter.py` | Filtering utilities and subset splitting (value, range, pattern, date, custom) |
| `data_analysis.py` | Descriptive statistics and aggregations, JSON-native input |
| `text_parser.py` | Structured parsing of `granted_exemptions`, `decision_basis`, `development_plan`, `included_documents`, `building_regulations_and_requirements`; record enrichment |
| `visualize.py` | matplotlib/seaborn plots from enriched records |
| `configuration.py` | Config loader |

### Enriched fields added by `text_parser`

`enrich_record()` merges the following flat fields onto each record:

| Field | Description |
|---|---|
| `exemption_items` | Hierarchical exemption item list (with sub-items) |
| `exemption_types` | Multi-label taxonomy list (`planning_law`, `tree_environmental`, `building_code`, `access_road`, `access_restriction`, `nature_protection`, `none`, `other`) |
| `exemption_primary_type` | Single label or `mixed` |
| `exemption_is_empty` | `true` when no exemption is granted |
| `exemption_legal_refs` | Deduplicated § references |
| `exemption_subjects` | Flattened subjects across all items |
| `plan_type` | `Bebauungsplan`, `Baustufenplan`, or `other` |
| `plan_name` | Specific plan name |
| `zone_code` | Leading zone designation from the decision basis |
| `legal_ordinance` | `BauNutzungsverordnung` or `Baupolizeiverordnung` |
| `plan_references` | List of `{name, type}` from the plan/implementation column |
| `plan_primary_type` | First primary planning instrument type |
| `documents_list` | Cleaned document name list |
| `requirements_list` | Requirement items |
| `document_count_parsed` | `len(documents_list)` |
| `requirement_count` | `len(requirements_list)` |

## Dependencies

| Package | Purpose |
|---|---|
| `pandas` | DataFrame manipulation |
| `openpyxl` | Excel write support |
| `python-calamine` | Fast Excel reading (5–10× faster than openpyxl) |
| `python-dotenv` | `.env` file loading |
| `pyyaml` | `config/path.yaml` parsing |
| `rich` | Spinner and progress bars in the terminal |
| `matplotlib` | Plot rendering |
| `seaborn` | Statistical plot styling |

Managed via uv:

```bash
uv add <package>
uv sync
```
