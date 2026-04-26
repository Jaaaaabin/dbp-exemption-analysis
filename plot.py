"""
Visualisation step.

Reads data_analyze.json produced by extract.py, enriches records in memory,
and saves all standard plots to res/figures/.

Run:
    uv run python plot.py
"""
from settings import JSON_ANALYZE_READY_FILE as JSON_FILE
from src.text_parser import enrich_and_merge_json
from src.visualize import plot_all


def main():
    print(f"\nVisualising: {JSON_FILE}\n")
    records = enrich_and_merge_json(JSON_FILE)
    plot_all(records, output_dir="res/figures")


if __name__ == "__main__":
    main()
