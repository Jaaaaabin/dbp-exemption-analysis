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
│       ├── scope/                   # analyze_scope.py descriptive plots
│       ├── exemption/               # analyze_exemption.py plots
│       ├── decision_basis/          # analyze_decision_basis.py plots
│       ├── both/                    # analyze_both.py cross-branch plots
│       ├── patterns/                # analyze_patterns.py taxonomy-gap plots
│       ├── items/                   # plot.py item-level plots
│       └── manifest.json            # gallery.py figure manifest
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
├── analyze.py                       # deprecated stub — split into parse.py + plot.py
├── analyze_scope.py                 # Step 3a — scope & descriptive stats → res/figures/scope/
├── analyze_exemption.py             # Step 3b — exemption figures → res/figures/exemption/
├── analyze_decision_basis.py        # Step 3c — decision basis figures → res/figures/decision_basis/
├── analyze_both.py                  # Step 3d — combined cross-branch figures → res/figures/both/
├── analyze_patterns.py              # Step 3e — taxonomy-gap diagnostics → res/figures/patterns/
├── plot.py                          # Step 3f — record + item-level plots → res/figures/
├── find_docs.py                     # Step 4 — external document dependencies → data/ext_docs/
├── gallery.py                       # Step 5 — build figure manifest + serve gallery.html
├── gallery.html                     # browser gallery of all generated figures
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
```

`analyze_scope.py` is the exception: it always reads **both** `FILE_ANALYZE_JSON` and `FILE_NONE_EXEMPTION_JSON` so the descriptive statistics cover the full corpus, tagged by cohort.

## Workflow

```bash
uv run python extract.py               # Step 1 — Excel → data/cleaned/*.csv + *.json
uv run python parse.py                 # Step 2 — parse text fields → *_parsed*.json
uv run python analyze_scope.py         # Step 3a — scope & descriptive stats → res/figures/scope/
uv run python analyze_exemption.py     # Step 3b — exemption analysis → res/figures/exemption/
uv run python analyze_decision_basis.py # Step 3c — decision basis → res/figures/decision_basis/
uv run python analyze_both.py          # Step 3d — combined analysis → res/figures/both/
uv run python analyze_patterns.py      # Step 3e — taxonomy-gap diagnostics → res/figures/patterns/
uv run python plot.py                  # Step 3f — record + item plots → res/figures/
uv run python find_docs.py             # Step 4 — external doc deps → data/ext_docs/
uv run python gallery.py --serve       # Step 5 — build manifest + open gallery in browser
```

Steps 3a–3f and Step 4 are all independent and can run in any order after Step 2.

> **Note:** `analyze.py` is a deprecated stub kept only for reference — its functionality was split into `parse.py` (Step 2) and `plot.py` (Step 3f). Don't run it.

### Step 1 outputs (`data/cleaned/`)

| File | Contents |
|---|---|
| `data_analyze` | Rows that **granted ≥1 exemption** |
| `data_none_exemption` | Rows that granted **no exemption** — text missing / `N/A` / `None specified.`, **or** `Number of Exemptions == 0` |

The split is by *content*, not mere column presence. `split_by_missing_columns`
routes a row to `data_none_exemption` when its Granted Exemptions text says so
(the same `grants_no_exemption()` rule the parser uses for `is_empty`) **or** the
source's `Number of Exemptions` count is 0. The count only ever *demotes*
granted→none (e.g. a `§ 34 BauGB` discretion note that grants nothing); a stray
`count > 0` on a text-empty row is ignored as a source artifact, so the text
stays the primary signal. A cell like `Granted Exemptions:\nNone specified.`
therefore lands in `data_none_exemption`, not `data_analyze`.

### Step 2 — enriched record structure

*Flat fields:* `request_id`, `time_for_decision_months`, `permit_type`, `issuing_authority`, `type_of_construction`, `development_plan_implementation_plan`

*Parsed section dicts* (keys in `snake_case`):

| Field | Sub-keys |
|---|---|
| `document_information` | `title`, `creation_date`, `modification_date` |
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

The record-level dict also carries `building_code_subtypes` (a list — see
the building-code sub-taxonomy below; `[]` when no HBauO basis is present).

**`primary_type`** is always the first matched taxonomy label from `types`. When a record matches multiple categories, `types` contains all of them and plots count each separately — there is no `"mixed"` label.

#### Exemption taxonomy

Multi-label, evaluated by `classify_exemption_types(text)` against `_TAXONOMY_RULES`
in `text_parser.py`. Rules are deliberately tied to specific legal/technical terms
so generic prose in (e.g.) a tree or fire-protection condition is not mislabelled.

| Label | Trigger (case-insensitive regex) |
|---|---|
| `planning_law` | `baugb` / `baunvo` / `bplanvo` / `grz` / `grundflächenzahl` / `baugrenze` |
| `tree_environmental` | `baumschutz` / `tree protection` / `schutz des baumbestandes` |
| `building_code` | `hbauo` / `building code` (any HBauO § deviation, not just § 69) |
| `access_road` | `§ 18/19/22/26 HWG` / `wegerecht` / `curb crossing` |
| `access_restriction` | `construction burden` / `baulasten` / `securing sufficient access/width` |
| `nature_protection` | `bnatschg` |
| `no_exemption` | no exemption granted (`is_empty == True`; matched by `_NO_EXEMPTION`) |
| `other` | text present but no recognised pattern |

`no_exemption` replaces the former `none` label. It is excluded from the
**Exemption Type Overview** chart (which answers "of permits that *did* grant an
exemption, what kind"), but retained in the data and elsewhere.

Multi-label records (matching two or more categories) are distributed across all matched categories in the plots. Use `classify_exemption_types(text)` to inspect the full label list for a given text.

#### Building-code sub-taxonomy

`building_code` collapses several distinct HBauO subjects, so
`classify_building_code_subtypes(text)` sub-labels each building-code deviation by
the substantive § it cites (`_BUILDING_CODE_SUBTYPE_BY_PARA`) plus subject
keywords (`_BUILDING_CODE_KEYWORD_RULES`). Returns `[]` when there is no HBauO
basis, or `['unspecified']` when only the generic § 69 deviation clause is cited.

| Subtype | Source (HBauO §) |
|---|---|
| `distance_area` | § 6 — separation distances (Abstandsflächen) |
| `front_garden_structure` | § 9 — structures in front gardens / non-buildable area |
| `play_area` | § 10 — children's play areas |
| `fire_escape_safety` | §§ 29/32/33/37 — staircases, escape routes, fire protection |
| `roof` | § 35 — roofs / dormers / attic exits (keyword: `eaves`) |
| `accessibility` | § 52 — barrier-free access / DIN 18040 |

`plot.py` renders the distribution as `res/figures/building_code_subtypes.png`.

Use `iter_granted_items(ge)` and `iter_sub_items(item)` from `text_parser` to iterate items without hardcoding key names. Use `flatten_to_items(source)` to produce one flat row per item for analysis; each row includes `exemption_primary_type` (first label), `exemption_types` (full list), and `building_code_subtypes`. Note that these three are **record-level** values broadcast to every item of a record — items are not independently re-classified.

### Step 3 figure outputs

| Script | Output dir | Key figures |
|---|---|---|
| `analyze_scope.py` | `res/figures/scope/` | `input_stats_*`: cohort split, permits by issue year, district distribution, HmbTG construction/facility/use breakdowns, combined year × building-use |
| `analyze_exemption.py` | `res/figures/exemption/` | type distribution, legal ref frequency, item-level breakdowns |
| `analyze_decision_basis.py` | `res/figures/decision_basis/` | plan type composition, ordinance context, zone quality |
| `analyze_both.py` | `res/figures/both/` | exemption domain × planning context, zone quality by domain, rationale signals |
| `analyze_patterns.py` | `res/figures/patterns/` | taxonomy-gap breakdown, recurring keywords/bigrams for `type=='other'` items |
| `plot.py` | `res/figures/` | `exemption_overview`, `ordinance_x_exemption`, `exemption_composition_by_authority`, `legal_ref_frequency`, `zone_code_x_exemption`, `building_code_subtypes` |
| `plot.py` | `res/figures/items/` | `item_type_distribution`, `item_authority_x_type`, `item_legal_ref_bar`, `exemption_treemap`, `keywords_*` |

Each analysis script also writes a `metadata.json` alongside its figures, recording the underlying counts and generation timestamp.

### Step 5 — figure gallery

`gallery.py` scans `res/figures/` and writes `manifest.json`; `gallery.html` reads it via `fetch()`, which browsers block on the `file://` protocol, so the gallery must be served over HTTP.

```bash
uv run python gallery.py               # just (re)build the manifest
uv run python gallery.py --serve       # build, serve, and open the browser (default port 8000)
uv run python gallery.py --serve --port 8765 --no-open
```

The page auto-refreshes the manifest every few seconds, so re-running `gallery.py` (or any analysis script) makes new figures appear without a reload.

---

## Data flow & module inter-relationships

The six Step-3 figure producers do **not** all consume the data the same way.
There are two parallel access patterns, and knowing which is which matters when
extending the analysis:

**A. Enriched in-memory records** — `enrich_and_merge_json(JSON_FILE)` parses and
merges every section into one record per permit, in memory, at runtime:

| Script | Unit(s) of analysis | Notes |
|---|---|---|
| `analyze_scope.py` | records | reads **both** cohort files (`FILE_ANALYZE_JSON` + `FILE_NONE_EXEMPTION_JSON`) |
| `plot.py` | records **and** items | `plot_all` (record-level) + `flatten_to_items` → `plot_all_items` (item-level) |

**B. parse.py sidecar JSON files** — read pre-computed, request-keyed sidecars
written by `parse.py` (`*_parsed_granted_exemptions.json`,
`*_parsed_decision_basis.json`), and build their own row tables from them:

| Script | Sidecar(s) consumed |
|---|---|
| `analyze_exemption.py` | `*_parsed_granted_exemptions.json` |
| `analyze_decision_basis.py` | `*_parsed_decision_basis.json` |
| `analyze_patterns.py` | `*_parsed_granted_exemptions.json` |
| `analyze_both.py` | **both** sidecars — joins them on `request_id` and builds its own record- **and** item-level rows (`build_record_rows` / `build_item_rows`) |

`parse.py` (Step 2) is therefore a hard prerequisite for the group-B scripts but
not for `analyze_scope.py` / `plot.py`, which re-enrich from the cleaned JSON
directly via `enrich_and_merge_json`.

**Record-level vs item-level.** A permit can grant several numbered exemptions.
`flatten_to_items` explodes records → one row per granted-exemption item, so
Overview figures answer *"what share of permits…"* while Items figures answer
*"what share of individual granted exemptions…"*. The taxonomy fields
(`exemption_primary_type`, `exemption_types`, `building_code_subtypes`) are
record-level values broadcast to each item; the genuinely per-item signals are
`legal_ref` and the text columns (`conditions_text`, `subjects_text`, …).

**Shared `visualize.py` helpers.** Plotting logic is centralised: every script
imports the palette/keyword helpers from `src/visualize.py`. Notably
`analyze_patterns.py` reuses `_tokenize` and `plot_keyword_frequency`, and the
`_EXEMPTION_PALETTE` (with `building_code` → dark red `#8b0000`) is the single
source of truth for category colours across **all** figures.

```
extract.py ──► data/cleaned/*.json
                   │
     ┌─────────────┴──────────────┐
 parse.py (Step 2)          enrich_and_merge_json (in memory)
     │  *_parsed_*.json           │
     ▼                            ▼
 analyze_exemption          analyze_scope
 analyze_decision_basis     plot.py (records + items)
 analyze_patterns           analyze_both ◄─ also reads both sidecars
     └──────────────┬───────────────┘
                    ▼
            res/figures/**  ──►  gallery.py ──► gallery.html
```

### Digging deeper into exemption patterns

`analyze_patterns.py` is the dedicated entry point for taxonomy-gap discovery.
It buckets every `type == 'other'` item into `taxonomy_gap_<family>` (has a
recognised ordinance ref but no matching rule), `inherits_<type>` (ref-less
sub-item of a real category), or `novel` (candidate for a new category), and
surfaces recurring keywords/bigrams as evidence for new `_TAXONOMY_RULES`. After
the latest taxonomy widening, the ~20 item-level `other` rows decompose into
`inherits_*` descriptive sub-items and `taxonomy_gap_*` items that already cite a
recognised ordinance (HWG, tree protection) — leaving just **one** genuinely
`novel` ref-less item. So the next pattern work is most likely in
**sub-categorising existing labels** (as the building-code sub-taxonomy already
does) or closing the `taxonomy_gap_*` section-number gaps, rather than adding
top-level categories. Start from `res/figures/patterns/` and the `metadata.json`
each script emits.

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
