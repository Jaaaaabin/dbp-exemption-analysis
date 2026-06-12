"""
Pattern-discovery diagnostics.

Cross-references item-level `type == 'other'` results (assigned by
classify_exemption_types, applied per item in src/text_parser.py) against
each item's legal_ref and its record's primary_type, to separate three
kinds of taxonomy gaps:

  - taxonomy_gap_<family> – item already has a legal_ref to a recognised
                            ordinance, but _TAXONOMY_RULES doesn't match its
                            specific section number
  - inherits_<type>       – item has no legal_ref, but its record's
                            primary_type is a real category (likely a
                            descriptive sub-item of that exemption)
  - novel                 – neither; candidate for a new taxonomy category

Surfaces recurring keywords/bigrams in each bucket's raw text as evidence
for new or extended _TAXONOMY_RULES.

Reads the request-keyed *_parsed_granted_exemptions.json produced by
parse.py and writes figures to res/figures/patterns/.

Run:
    uv run python analyze_patterns.py
"""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import seaborn as sns

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE
from src.visualize import _tokenize, plot_keyword_frequency


INPUT_FILE = JSON_FILE.parent / (JSON_FILE.stem + "_parsed_granted_exemptions.json")
OUTPUT_DIR = Path("res/figures/patterns")

META_KEYS = {"header", "types", "primary_type", "is_empty", "legal_refs", "subjects"}
UNKNOWN = "unknown"

# item_type values that a ref-less 'other' item can plausibly inherit from
# its record's primary_type.
_INHERITABLE_TYPES = {
    "planning_law", "tree_environmental", "building_code",
    "access_road", "access_restriction", "nature_protection",
}

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.0)


def load_granted_exemptions(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return {
            str(request_id): value
            for request_id, value in data.items()
            if isinstance(value, dict)
        }

    # Backward-compatible fallback for older list-shaped exports.
    if isinstance(data, list):
        return {
            str(i + 1): value
            for i, value in enumerate(data)
            if isinstance(value, dict)
        }

    raise ValueError(f"Unsupported granted exemptions JSON shape: {type(data).__name__}")


def item_keys(granted_exemption: dict) -> list[str]:
    return [
        key
        for key, value in granted_exemption.items()
        if key not in META_KEYS and isinstance(value, dict)
    ]


def legal_family(ref: str | None, text: str | None = None) -> str:
    haystack = f"{ref or ''} {text or ''}".lower()
    if "hbauo" in haystack:
        return "HBauO"
    if "baunvo" in haystack:
        return "BauNVO"
    if "baugb" in haystack:
        return "BauGB"
    if "bnatschg" in haystack:
        return "BNatSchG"
    if "hwg" in haystack or "hamburg road law" in haystack:
        return "HWG"
    if "baumschutz" in haystack or "tree protection" in haystack:
        return "TreeProtection"
    if "bpvo" in haystack:
        return "BPVO"
    if re.search(r"§\s*\d+", haystack):
        return "UnqualifiedSection"
    return UNKNOWN


def build_item_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, ge in source.items():
        record_primary_type = ge.get("primary_type") or UNKNOWN
        for key in item_keys(ge):
            item = ge[key]
            rows.append({
                "request_id": request_id,
                "item_index": key,
                "record_primary_type": record_primary_type,
                "item_type": item.get("type") or UNKNOWN,
                "legal_ref": item.get("legal_ref"),
                "legal_family": legal_family(item.get("legal_ref"), item.get("text")),
                "text": item.get("text") or "",
            })
    return rows


def classify_gap(row: pd.Series) -> str:
    if row["item_type"] != "other":
        return "classified"
    if row["legal_ref"] and row["legal_family"] != UNKNOWN:
        return f"taxonomy_gap_{row['legal_family']}"
    if row["record_primary_type"] in _INHERITABLE_TYPES:
        return f"inherits_{row['record_primary_type']}"
    return "novel"


def save_barh(series: pd.Series, title: str, xlabel: str, path: Path) -> None:
    import matplotlib.pyplot as plt

    if series.empty:
        print(f"Skipped empty figure: {path}")
        return

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(series) * 0.45)))
    bars = ax.barh(series.index.astype(str), series.values)
    ax.bar_label(bars, padding=3)
    ax.margins(x=0.08)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_gap_breakdown(items: pd.DataFrame, output_dir: Path) -> None:
    other = items[items["item_type"] == "other"]
    counts = other["gap_category"].value_counts().sort_values()
    save_barh(
        counts,
        "Item-Type 'other': Gap Category Breakdown",
        "Number of items",
        output_dir / "pattern_gap_breakdown.png",
    )


def plot_other_bigrams(items: pd.DataFrame, output_dir: Path, top_n: int = 20) -> None:
    other = items[items["item_type"] == "other"]
    bigrams: Counter = Counter()
    for text in other["text"]:
        tokens = _tokenize(text)
        for a, b in zip(tokens, tokens[1:]):
            bigrams[f"{a} {b}"] += 1

    path = output_dir / "pattern_other_bigrams.png"
    if not bigrams:
        print(f"Skipped empty figure: {path}")
        return
    top = pd.Series(dict(bigrams.most_common(top_n))).sort_values()
    save_barh(top, "Item-Type 'other': Top Bigrams in Raw Text", "Occurrences", path)


def plot_other_keywords_by_gap(items: pd.DataFrame, output_dir: Path) -> None:
    other = items[items["item_type"] == "other"]
    plot_keyword_frequency(
        other.to_dict("records"),
        text_col="text",
        facet_col="gap_category",
        top_n=15,
        output_path=output_dir / "pattern_other_keywords_by_gap.png",
    )


def save_report(
    output_dir: Path,
    input_file: Path,
    items: pd.DataFrame,
    generated_figures: list[Path],
) -> None:
    other = items[items["item_type"] == "other"]
    gap_items = other[other["gap_category"].str.startswith("taxonomy_gap_")]

    taxonomy_gap_refs = {
        family: sorted(group["legal_ref"].dropna().unique().tolist())
        for family, group in gap_items.groupby("legal_family")
    }

    novel = other[other["gap_category"] == "novel"]
    novel_items = [
        {
            "request_id": row["request_id"],
            "item_index": row["item_index"],
            "record_primary_type": row["record_primary_type"],
            "text_snippet": row["text"][:150],
        }
        for _, row in novel.iterrows()
    ]

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_file),
        "output_dir": str(output_dir),
        "figures": [path.name for path in generated_figures],
        "item_count": int(len(items)),
        "item_type_counts": items["item_type"].value_counts().sort_index().to_dict(),
        "other_item_count": int(len(other)),
        "gap_category_counts": other["gap_category"].value_counts().sort_index().to_dict(),
        "taxonomy_gap_legal_refs": taxonomy_gap_refs,
        "novel_items": novel_items,
    }

    path = output_dir / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


def main() -> None:
    print(f"\nAnalyzing pattern gaps: {INPUT_FILE}\n")
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    granted = load_granted_exemptions(INPUT_FILE)
    items = pd.DataFrame(build_item_rows(granted))
    items["gap_category"] = items.apply(classify_gap, axis=1)

    generated_figures = [
        output_dir / "pattern_gap_breakdown.png",
        output_dir / "pattern_other_bigrams.png",
        output_dir / "pattern_other_keywords_by_gap.png",
    ]

    plot_gap_breakdown(items, output_dir)
    plot_other_bigrams(items, output_dir)
    plot_other_keywords_by_gap(items, output_dir)
    save_report(output_dir, INPUT_FILE, items, generated_figures)

    other_count = int((items["item_type"] == "other").sum())
    print(f"\n{other_count} of {len(items)} items are unclassified ('other').")
    print(f"All pattern figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
