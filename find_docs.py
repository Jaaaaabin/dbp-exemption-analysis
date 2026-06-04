"""
Extract external document and regulation dependencies.

Reads the focused parsed JSON exports from parse.py and writes a request-keyed
external dependency JSON to data/ext_docs/.

Run:
    uv run python find_docs.py
"""
import csv
import json
import re
from pathlib import Path

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE


DECISION_BASIS_FILE = JSON_FILE.parent / (
    JSON_FILE.stem + "_parsed_decision_basis.json"
)
GRANTED_EXEMPTIONS_FILE = JSON_FILE.parent / (
    JSON_FILE.stem + "_parsed_granted_exemptions.json"
)
OUTPUT_DIR = Path("data/ext_docs")
OUTPUT_FILE = OUTPUT_DIR / (JSON_FILE.stem + "_external_dependencies.json")
OUTPUT_CSV = OUTPUT_DIR / (JSON_FILE.stem + "_external_dependencies.csv")

GE_META_KEYS = {"header", "types", "primary_type", "is_empty", "legal_refs", "subjects"}

ORDINANCE_TERMS = (
    "verordnung",
    "ordinance",
    "baunutzungsverordnung",
    "baupolizeiverordnung",
    "baunvo",
    "bpvo",
)
LANDSCAPE_TERMS = (
    "landscape",
    "landschaftsschutz",
    "conservation",
    "protection of landscape",
    "green space",
    "maintenance ordinance",
    "erhaltungsverordnung",
)
PRELIMINARY_TERMS = ("vorbescheid", "preliminary decision")


def load_request_dict(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return {
            str(request_id): value
            for request_id, value in data.items()
            if isinstance(value, dict)
        }

    if isinstance(data, list):
        return {
            str(i + 1): value
            for i, value in enumerate(data)
            if isinstance(value, dict)
        }

    raise ValueError(f"Unsupported JSON shape in {path}: {type(data).__name__}")


def normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def contains_any(text: str | None, terms: tuple[str, ...]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(term in lowered for term in terms)


def add_unique(target: list[dict], entry: dict) -> None:
    signature = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    for existing in target:
        if json.dumps(existing, ensure_ascii=False, sort_keys=True) == signature:
            return
    target.append(entry)


def make_entry(source_field: str, value, kind: str | None = None) -> dict | None:
    text = normalize_text(value)
    if not text:
        return None

    entry = {"source_field": source_field, "value": text}
    if kind:
        entry["type"] = kind
    return entry


def item_keys(granted_exemption: dict) -> list[str]:
    return [
        key
        for key, value in granted_exemption.items()
        if key not in GE_META_KEYS and isinstance(value, dict)
    ]


def extract_section_refs(text: str | None) -> list[str]:
    if not text:
        return []
    refs = re.findall(
        r"§\s*\d+[a-zA-Z]?(?:\s+(?:Abs(?:atz)?\.?|paragraph)\s*\d+)?"
        r"(?:\s+[A-ZÄÖÜ]{2,}[a-zA-ZÄÖÜäöü]*)?",
        text,
    )
    return list(dict.fromkeys(re.sub(r"\s+", " ", ref.strip()) for ref in refs))


def extract_planning_instruments(basis: dict) -> list[dict]:
    docs: list[dict] = []

    for field in ("development_plan", "plan_name", "plan_type", "plan_primary_type"):
        entry = make_entry(field, basis.get(field))
        if entry:
            add_unique(docs, entry)

    for field in ("bebauungsplan", "teilbebauungsplan_341", "green_order_plan"):
        entry = make_entry(field, basis.get(field))
        if entry:
            add_unique(docs, entry)

    refs = basis.get("plan_references") or []
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            name = normalize_text(ref.get("name"))
            ref_type = normalize_text(ref.get("type"))
            if name or ref_type:
                add_unique(docs, {
                    "source_field": "plan_references",
                    "name": name,
                    "type": ref_type,
                })

    return docs


def extract_regulatory_ordinances(basis: dict) -> list[dict]:
    docs: list[dict] = []

    for field in ("legal_ordinance", "verordnung", "additional_regulations"):
        entry = make_entry(field, basis.get(field))
        if entry:
            add_unique(docs, entry)

    notes = basis.get("_notes") or []
    if isinstance(notes, list):
        for note in notes:
            if contains_any(str(note), ORDINANCE_TERMS):
                entry = make_entry("_notes", note)
                if entry:
                    add_unique(docs, entry)

    for field in ("regulations", "development_plan", "plan_name"):
        value = normalize_text(basis.get(field))
        if contains_any(value, ORDINANCE_TERMS):
            entry = make_entry(field, value)
            if entry:
                add_unique(docs, entry)

    return docs


def extract_regulation_texts(basis: dict) -> list[dict]:
    docs: list[dict] = []
    for field in ("regulations", "zone_code", "type", "building_depth", "grz", "gfz", "roof_pitch", "building_window", "back"):
        entry = make_entry(field, basis.get(field))
        if entry:
            add_unique(docs, entry)
    return docs


def extract_landscape_conservation_docs(basis: dict) -> list[dict]:
    docs: list[dict] = []

    for field in ("conservation_ordinance", "landscape_protection_ordinance", "green_order_plan"):
        entry = make_entry(field, basis.get(field))
        if entry:
            add_unique(docs, entry)

    refs = basis.get("plan_references") or []
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            ref_type = normalize_text(ref.get("type"))
            name = normalize_text(ref.get("name"))
            combined = f"{name or ''} {ref_type or ''}"
            if contains_any(combined, LANDSCAPE_TERMS):
                add_unique(docs, {
                    "source_field": "plan_references",
                    "name": name,
                    "type": ref_type,
                })

    notes = basis.get("_notes") or []
    if isinstance(notes, list):
        for note in notes:
            if contains_any(str(note), LANDSCAPE_TERMS):
                entry = make_entry("_notes", note)
                if entry:
                    add_unique(docs, entry)

    for field in ("regulations", "zone_code"):
        value = normalize_text(basis.get(field))
        if contains_any(value, LANDSCAPE_TERMS):
            entry = make_entry(field, value)
            if entry:
                add_unique(docs, entry)

    return docs


def extract_preliminary_decision_docs(basis: dict) -> list[dict]:
    docs: list[dict] = []

    for field in ("preliminary_decision", "preliminary_decision_gz", "vorbescheid_gz"):
        entry = make_entry(field, basis.get(field))
        if entry:
            add_unique(docs, entry)

    for field, value in basis.items():
        if field in {"preliminary_decision", "preliminary_decision_gz", "vorbescheid_gz"}:
            continue
        text = normalize_text(value)
        if contains_any(field, PRELIMINARY_TERMS) or contains_any(text, PRELIMINARY_TERMS):
            entry = make_entry(field, text)
            if entry:
                add_unique(docs, entry)

    return docs


def extract_exemption_legal_refs(granted_exemption: dict) -> list[dict]:
    docs: list[dict] = []

    for ref in granted_exemption.get("legal_refs") or []:
        entry = make_entry("granted_exemptions.legal_refs", ref)
        if entry:
            add_unique(docs, entry)

    for item_key in item_keys(granted_exemption):
        item = granted_exemption[item_key]
        entry = make_entry(f"granted_exemptions.{item_key}.legal_ref", item.get("legal_ref"))
        if entry:
            add_unique(docs, entry)

        for ref in extract_section_refs(item.get("text")):
            entry = make_entry(f"granted_exemptions.{item_key}.text", ref)
            if entry:
                add_unique(docs, entry)

        for sub_key, sub_item in item.items():
            if "." not in sub_key or not isinstance(sub_item, dict):
                continue
            for ref in extract_section_refs(sub_item.get("text")):
                entry = make_entry(f"granted_exemptions.{item_key}.{sub_key}.text", ref)
                if entry:
                    add_unique(docs, entry)

    return docs


def extract_dependencies_for_record(basis: dict, granted_exemption: dict) -> dict:
    dependencies = {
        "planning_instruments": extract_planning_instruments(basis),
        "regulatory_ordinances": extract_regulatory_ordinances(basis),
        "regulation_texts": extract_regulation_texts(basis),
        "landscape_conservation_documents": extract_landscape_conservation_docs(basis),
        "preliminary_decision_documents": extract_preliminary_decision_docs(basis),
        "granted_exemption_legal_references": extract_exemption_legal_refs(granted_exemption),
    }
    dependencies["summary"] = {
        "category_counts": {
            category: len(entries)
            for category, entries in dependencies.items()
            if isinstance(entries, list)
        },
        "total_dependencies": sum(
            len(entries)
            for entries in dependencies.values()
            if isinstance(entries, list)
        ),
    }
    return dependencies


def flatten_dependencies(output: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, dependencies in output.items():
        total = dependencies.get("summary", {}).get("total_dependencies", 0)
        for category, entries in dependencies.items():
            if category == "summary" or not isinstance(entries, list):
                continue
            for entry in entries:
                rows.append({
                    "request_id": request_id,
                    "category": category,
                    "source_field": entry.get("source_field"),
                    "value": entry.get("value"),
                    "name": entry.get("name"),
                    "type": entry.get("type"),
                    "total_dependencies_for_request": total,
                })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "request_id",
        "category",
        "source_field",
        "value",
        "name",
        "type",
        "total_dependencies_for_request",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    print("\nExtracting external document dependencies\n")
    decision_basis = load_request_dict(DECISION_BASIS_FILE)
    granted_exemptions = load_request_dict(GRANTED_EXEMPTIONS_FILE)

    output = {}
    for request_id in sorted(set(decision_basis) | set(granted_exemptions), key=int):
        output[request_id] = extract_dependencies_for_record(
            decision_basis.get(request_id, {}),
            granted_exemptions.get(request_id, {}),
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    csv_rows = flatten_dependencies(output)
    write_csv(OUTPUT_CSV, csv_rows)

    print(f"Saved {len(output)} request-keyed records → {OUTPUT_FILE}")
    print(f"Saved {len(csv_rows)} dependency rows → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
