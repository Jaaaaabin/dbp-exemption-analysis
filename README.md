# DBP Exemption Analysis

A Python project for loading, cleaning, and analysing Digital Building Permit (DBP) exemption data from Excel, built with [uv](https://github.com/astral-sh/uv) for dependency management.

## Project Structure

```
dbp-exemption-analysis/
├── config/
│   └── path.yaml             # data-folder and analysis-type settings
├── data/
│   ├── raw/                  # source Excel files (not tracked)
│   └── cleaned/              # pipeline outputs (not tracked)
│       ├── data_cleaned.csv
│       ├── data_out_exemption.csv
│       └── data_out_regulation.csv
├── src/
│   ├── configuration.py      # config loader (path.yaml + env-var substitution)
│   ├── data_clean.py         # Excel ingestion and DataFrame cleaning
│   ├── data_filter.py        # filtering and subset splitting
│   ├── data_analysis.py      # descriptive statistics and aggregations
│   └── utils/
│       ├── cli_utils.py      # spinner, progress bars, coloured output
│       ├── env_utils.py      # system info display and directory tree printer
│       └── time_utils.py     # @measure_runtime decorator for function timing
├── test.py                   # main workflow script
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

Run the full pipeline:

```bash
uv run python test.py
```

### What the pipeline does

1. Load and clean `data/raw/data.xlsx` (dedup, strip whitespace)
2. Split into three outputs based on missing key columns:
   - `data_cleaned.csv` — both columns present
   - `data_out_exemption.csv` — `Granted Exemptions` missing
   - `data_out_regulation.csv` — `Building regulations and requirements` missing
3. Print a summary overview for each output

## Dependencies

| Package | Purpose |
|---|---|
| `pandas` | DataFrame manipulation |
| `openpyxl` | Excel write support |
| `python-calamine` | Fast Excel reading (5–10× faster than openpyxl) |
| `python-dotenv` | `.env` file loading |
| `pyyaml` | `config/path.yaml` parsing |
| `rich` | Spinner and progress bars in the terminal |

Managed via uv:

```bash
uv add <package>
uv sync
```
