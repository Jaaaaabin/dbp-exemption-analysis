"""
Enrichment & parsing step.

Reads data_analyze.json produced by extract.py, parses all long text fields
into structured sub-dicts, and writes the result to
data_analyze_parsed.json.

Run:
    uv run python parse.py
"""
import json

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE
from src.text_parser import enrich_json


def main():
    print(f"\nParsing: {JSON_FILE}\n")

    with open(JSON_FILE, encoding='utf-8') as f:
        original = json.load(f)

    enriched = enrich_json(original)

    enriched_path = JSON_FILE.parent / (JSON_FILE.stem + "_parsed.json")
    with open(enriched_path, 'w', encoding='utf-8') as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False, default=str)

    print(f"Saved {len(enriched)} enriched records → {enriched_path}")


if __name__ == "__main__":
    main()
