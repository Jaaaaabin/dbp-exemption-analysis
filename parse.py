"""
Enrichment & parsing step.

Reads data_analyze.json produced by extract.py, parses all long text fields
into structured sub-dicts, and writes the result to:
  - data_analyze_parsed.json
  - data_analyze_parsed_granted_exemptions.json
  - data_analyze_parsed_decision_basis.json

Run:
    uv run python parse.py
"""
import json

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE
from src.text_parser import enrich_json


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)


def main():
    print(f"\nParsing: {JSON_FILE}\n")

    enriched = enrich_json(JSON_FILE)

    enriched_path = JSON_FILE.parent / (JSON_FILE.stem + "_parsed.json")
    granted_path = JSON_FILE.parent / (
        JSON_FILE.stem + "_parsed_granted_exemptions.json"
    )
    decision_basis_path = JSON_FILE.parent / (
        JSON_FILE.stem + "_parsed_decision_basis.json"
    )

    granted_only = {
        str(record.get("request_id")): record.get("granted_exemptions", {})
        for record in enriched
    }
    decision_basis_only = {
        str(record.get("request_id")): record.get("decision_basis", {})
        for record in enriched
    }

    _write_json(enriched_path, enriched)
    _write_json(granted_path, granted_only)
    _write_json(decision_basis_path, decision_basis_only)

    print(f"Saved {len(enriched)} enriched records -> {enriched_path}")
    print(f"Saved {len(granted_only)} request-keyed granted exemptions -> {granted_path}")
    print(f"Saved {len(decision_basis_only)} request-keyed decision bases -> {decision_basis_path}")


if __name__ == "__main__":
    main()
