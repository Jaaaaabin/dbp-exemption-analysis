# DBP Exemption Analysis

A Python project for extracting, cleaning, parsing, and visualising Digital Building Permit (DBP) exemption data from Excel, built with [uv](https://github.com/astral-sh/uv).

## Project Structure

```
dbp/
├── config/
│   └── path.yaml                    # raw/cleaned folder paths
├── data/
│   ├── raw/                         # source Excel files
│   ├── cleaned/                     # pipeline outputs (CSV + JSON)
│   └── ext_docs/                    # external document dependencies (find_docs.py)
├── res/
│   └── figures/
│       ├── exemption/               # analyze_exemption.py plots
│       ├── decision_basis/          # analyze_decision_basis.py plots
│       ├── both/                    # analyze_both.py cross-branch plots
│       └── items/                   # plot.py item-level plots
├── src/
│   ├── configuration.py             # config loader (path.yaml)
│   ├── data_clean.py                # Excel ingestion, DataFrame cleaning, JSON export
│   ├── data_analysis.py             # ETL split, filtering utilities, statistics & aggregations
│   ├── text_parser.py               # long text field parsing and record enrichment
│   ├── visualize.py                 # matplotlib/seaborn plots from enriched records
│   └── utils/
│       ├── cli_utils.py             # spinner, progress bars, coloured output
│       ├── env_utils.py             # system info, directory tree printer
│       └── time_utils.py            # @measure_runtime decorator
├── settings.py                      # all output file paths + active dataset switch
├── extract.py                       # Step 1 — Excel → cleaned CSV + JSON
├── parse.py                         # Step 2 — parse text fields → _parsed.json
├── analyze_exemption.py             # Step 3a — exemption figures → res/figures/exemption/
├── analyze_decision_basis.py        # Step 3b — decision basis figures → res/figures/decision_basis/
├── analyze_both.py                  # Step 3c — combined cross-branch figures → res/figures/both/
├── plot.py                          # Step 3d — record + item-level plots → res/figures/
├── find_docs.py                     # Step 4 — external document dependencies → data/ext_docs/
├── sys.py                           # environment summary
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

All pipeline scripts read from the same file. To change it, edit one line in [settings.py](settings.py):

```python
JSON_ANALYZE_READY_FILE = FILE_ANALYZE_JSON          # default
# JSON_ANALYZE_READY_FILE = FILE_NONE_EXEMPTION_JSON
# JSON_ANALYZE_READY_FILE = FILE_NONE_REGULATION_JSON
```

## Workflow

```bash
uv run python extract.py               # Step 1 — Excel → data/cleaned/*.csv + *.json
uv run python parse.py                 # Step 2 — parse text fields → *_parsed*.json
uv run python analyze_exemption.py     # Step 3a — exemption analysis → res/figures/exemption/
uv run python analyze_decision_basis.py # Step 3b — decision basis → res/figures/decision_basis/
uv run python analyze_both.py          # Step 3c — combined analysis → res/figures/both/
uv run python plot.py                  # Step 3d — record + item plots → res/figures/
uv run python find_docs.py             # Step 4 — external doc deps → data/ext_docs/
```

Steps 3a–3d and Step 4 are all independent and can run in any order after Step 2.

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
| `granted_exemptions` | `header`, `types`, `primary_type`, `is_empty`, `legal_refs`, `subjects`, **`"1"`, `"2"`, …** (item dicts keyed by index) |

#### `granted_exemptions` structure

Numbered items appear as direct keys (`"1"`, `"2"`, …) in the dict. Sub-items (`"1.1"`, `"1.2"`, …) are direct keys within their parent item. Unnumbered single-item exemptions are stored under `"1"`.

```json
"granted_exemptions": {
  "header": "Wegerecht – This permit includes:",
  "types": ["planning_law", "tree_environmental"],
  "primary_type": "planning_law",
  "is_empty": false,
  "legal_refs": ["§ 31 paragraph 2", "§ 4"],
  "subjects": ["exceeding the building limit by …"],
  "1": {
    "text": "<full raw body of item 1>",
    "legal_ref": "§ 31 paragraph 2",
    "type": "planning_law",
    "1.1": {
      "text": "For exceeding …",
      "subject": "exceeding …"
    }
  },
  "2": { "text": "…", "legal_ref": "§ 69 HBauO", "type": "building_code" }
}
```

**`primary_type`** is always the first matched taxonomy label from `types`. When a record matches multiple categories, `types` contains all of them and plots count each separately — there is no `"mixed"` label.

#### Exemption taxonomy

| Label | Trigger |
|---|---|
| `planning_law` | `§ 31 BauGB` |
| `tree_environmental` | `Baumschutz` / tree protection |
| `building_code` | `§ 69 HBauO` |
| `access_road` | `§ 18/19/22/26 HWG` / Wegerecht / curb crossing |
| `access_restriction` | construction burden / Baulasten |
| `nature_protection` | `BNatSchG` |
| `none` | no exemption present |
| `other` | text present but no recognised pattern |

Multi-label records (matching two or more categories) are distributed across all matched categories in the plots. Use `classify_exemption_types(text)` to inspect the full label list for a given text.

Use `iter_granted_items(ge)` and `iter_sub_items(item)` from `text_parser` to iterate items without hardcoding key names. Use `flatten_to_items(source)` to produce one flat row per item for analysis; each row includes both `exemption_primary_type` (first label) and `exemption_types` (full list).

### Step 3 figure outputs

| Script | Output dir | Key figures |
|---|---|---|
| `analyze_exemption.py` | `res/figures/exemption/` | type distribution, legal ref frequency, item-level breakdowns |
| `analyze_decision_basis.py` | `res/figures/decision_basis/` | plan type composition, ordinance context, zone quality |
| `analyze_both.py` | `res/figures/both/` | exemption domain × planning context, zone quality by domain, rationale signals |
| `plot.py` | `res/figures/` | `exemption_overview`, `ordinance_x_exemption`, `exemption_composition_by_authority`, `legal_ref_frequency`, `zone_code_x_exemption` |
| `plot.py` | `res/figures/items/` | `item_type_distribution`, `item_authority_x_type`, `item_legal_ref_bar`, `exemption_treemap`, `keywords_*` |

---

## Source modules

| Module | Responsibility |
|---|---|
| `data_clean.py` | Excel ingestion, DataFrame cleaning, CSV/JSON export |
| `data_analysis.py` | ETL split, DataFrame filtering, statistics & aggregations |
| `text_parser.py` | Long text field parsing, record enrichment (`enrich_json`, `enrich_and_merge_json`), item iteration (`iter_granted_items`, `iter_sub_items`), flat item rows (`flatten_to_items`) |
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
| `squarify` | Treemap plots (optional — `uv add squarify`) |

```bash
uv add <package>
uv sync
```
