from pathlib import Path

CLEANED_DIR = Path("data/cleaned")

# ── Dataset file paths ────────────────────────────────────────────────────────
FILE_ANALYZE_CSV         = CLEANED_DIR / "data_analyze.csv"
FILE_ANALYZE_JSON        = CLEANED_DIR / "data_analyze.json"
FILE_NONE_EXEMPTION_CSV  = CLEANED_DIR / "data_none_exemption.csv"
FILE_NONE_EXEMPTION_JSON = CLEANED_DIR / "data_none_exemption.json"

# ── Active dataset for parse.py and plot.py ───────────────────────────────────
# Change this one line to switch the input for both scripts.
JSON_ANALYZE_READY_FILE = FILE_ANALYZE_JSON
# JSON_ANALYZE_READY_FILE = FILE_NONE_EXEMPTION_JSON
