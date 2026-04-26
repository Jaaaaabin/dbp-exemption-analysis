# DBP Exemption Analysis

A Python project for extracting, cleaning, parsing, and visualising Digital Building Permit (DBP) exemption data from Excel, built with [uv](https://github.com/astral-sh/uv).

## Project Structure

```
dbp/
├── config/
│   └── path.yaml              # raw/cleaned folder paths
├── data/
│   ├── raw/                   # source Excel files
│   └── cleaned/               # pipeline outputs
│       ├── data_analyze.csv / .json
│       ├── data_analyze_parsed.json
│       ├── data_none_exemption.csv / .json
│       └── data_none_regulation.csv / .json
├── res/
│   └── figures/               # generated plot PNGs
├── src/
│   ├── configuration.py       # config loader (path.yaml)
│   ├── data_clean.py          # Excel ingestion, DataFrame cleaning, JSON export
│   ├── data_analysis.py       # ETL split, filtering utilities, statistics & aggregations
│   ├── text_parser.py         # long text field parsing and record enrichment
│   ├── visualize.py           # matplotlib/seaborn plots from enriched records
│   └── utils/
│       ├── cli_utils.py       # spinner, progress bars, coloured output
│       ├── env_utils.py       # system info, directory tree printer
│       └── time_utils.py      # @measure_runtime decorator
├── settings.py                # all output file paths + active dataset switch
├── extract.py                 # Step 1 — Excel → cleaned CSV + JSON
├── parse.py                   # Step 2 — parse text fields → _parsed.json
├── plot.py                    # Step 3 — visualise → res/figures/
├── sys.py                     # environment summary
├── pyproject.toml
└── uv.lock
```

## Setup

```bash
uv sync
```

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

Source file expected at `data/raw/data.xlsx` (path configurable in `config/path.yaml`).

## Dataset switch

All three pipeline scripts read from the same file. To change it, edit one line in [settings.py](settings.py):

```python
JSON_ANALYZE_READY_FILE = FILE_ANALYZE_JSON          # default
# JSON_ANALYZE_READY_FILE = FILE_NONE_EXEMPTION_JSON
# JSON_ANALYZE_READY_FILE = FILE_NONE_REGULATION_JSON
```

## Workflow

```bash
uv run python extract.py   # Step 1 — Excel → data/cleaned/*.csv + *.json
uv run python parse.py     # Step 2 — parse text fields → data_analyze_parsed.json
uv run python plot.py      # Step 3 — plots → res/figures/
```

Steps 2 and 3 are independent and can run in any order.

### Step 1 outputs (`data/cleaned/`)

| File | Contents |
|---|---|
| `data_analyze` | Rows where both key columns are present |
| `data_none_exemption` | Rows missing `Granted Exemptions` |
| `data_none_regulation` | Rows missing `Building regulations and requirements` |

### Step 2 — enriched record structure

*Flat fields:* `request_id`, `time_for_decision_months`, `permit_type`, `issuing_authority`, `type_of_construction`, `development_plan_implementation_plan`

*Parsed section dicts* (keys in `snake_case`):

| Field | Sub-keys |
|---|---|
| `document_information` | `title`, `creation_date` |
| `contact_information` | `issuing_authority`, `department`, `address`, `telephone`, `telefax`, `email`, `contact_person` |
| `permit_information` | `reference_number`, `permit_type`, `date_of_receipt`, `issue_date`, `validity` |
| `property_information` | `location`, `project_description` |
| `statistics_for_hmbtg_implementation` | `type_of_construction`, `type_of_requested_facility`, `type_of_building_by_future_use`, `number_of_full_stories` |
| `building_regulations_and_requirements` | one key per requirement; unparseable lines in `_notes` |
| `decision_basis` | `development_plan`, `regulations`, `_notes` + `plan_type`, `plan_name`, `zone_code`, `legal_ordinance`, `plan_references`, `plan_primary_type` |
| `granted_exemptions` | `items`, `types`, `primary_type`, `is_empty`, `legal_refs`, `subjects` |

### Step 3 outputs (`res/figures/`)

`exemption_overview`, `decision_time_by_authority`, `decision_time_by_exemption_type`, `decision_time_by_plan_type`, `decision_time_by_plan_primary_type`, `decision_time_distribution`, `correlation_heatmap`

---

## Source modules

| Module | Responsibility |
|---|---|
| `data_clean.py` | Excel ingestion, DataFrame cleaning, CSV/JSON export |
| `data_analysis.py` | ETL split, DataFrame filtering, statistics & aggregations |
| `text_parser.py` | Long text field parsing, record enrichment (`enrich_json`, `enrich_and_merge_json`) |
| `visualize.py` | All matplotlib/seaborn plots |
| `configuration.py` | Config loader (`path.yaml`) |

## Dependencies

| Package | Purpose |
|---|---|
| `pandas` | DataFrame manipulation |
| `openpyxl` | Excel write support |
| `python-calamine` | Fast Excel reading |
| `python-dotenv` | `.env` loading |
| `pyyaml` | `config/path.yaml` parsing |
| `rich` | Terminal spinner and progress bars |
| `matplotlib` | Plot rendering |
| `seaborn` | Statistical plot styling |

```bash
uv add <package>
uv sync
```
