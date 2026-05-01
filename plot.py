"""
Visualisation step.

Reads the active JSON file (set in settings.py), enriches records in memory,
and saves plots to res/figures/ (record-level) and res/figures/items/ (item-level).

Run:
    uv run python plot.py
"""
from settings import JSON_ANALYZE_READY_FILE as JSON_FILE
from src.text_parser import enrich_and_merge_json, flatten_to_items
from src.visualize import plot_all, plot_all_items


def main():
    print(f"\nVisualising: {JSON_FILE}\n")
    records = enrich_and_merge_json(JSON_FILE)

    plot_all(records, output_dir="res/figures")

    items = flatten_to_items(records)
    print(f"\n{len(items)} exemption items from {len(records)} records")
    plot_all_items(items, output_dir="res/figures/items")


if __name__ == "__main__":
    main()
