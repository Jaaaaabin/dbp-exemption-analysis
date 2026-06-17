"""
Granted exemption analysis.

Reads the request-keyed *_parsed_granted_exemptions.json produced by parse.py
and writes simple exploratory figures to res/figures/exemption/.

Run:
    uv run python analyze_exemption.py
"""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE


INPUT_FILE = JSON_FILE.parent / (JSON_FILE.stem + "_parsed_granted_exemptions.json")
OUTPUT_DIR = Path("res/figures/exemption")

META_KEYS = {"header", "types", "primary_type", "is_empty", "legal_refs", "subjects"}
UNKNOWN = "unknown"
FEATURE_COLUMNS = [
    "has_legal_ref",
    "has_subjects",
    "has_conditions",
    "has_allowed_actions",
    "has_justification",
]

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


def build_record_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, ge in source.items():
        keys = item_keys(ge)
        items = [ge[key] for key in keys]
        n_items_with_conditions = sum(bool(item.get("conditions")) for item in items)
        n_items_with_actions = sum(bool(item.get("allowed_actions")) for item in items)
        n_items_with_justification = sum(bool(item.get("justification")) for item in items)
        n_subitems = sum(
            len([sub_key for sub_key in item if "." in sub_key])
            for item in items
        )
        rows.append({
            "request_id": request_id,
            "primary_type": ge.get("primary_type") or UNKNOWN,
            "is_empty": bool(ge.get("is_empty")),
            "n_types": len(ge.get("types") or []),
            "n_legal_refs": len(ge.get("legal_refs") or []),
            "n_subjects": len(ge.get("subjects") or []),
            "n_items": len(keys),
            "n_subitems": n_subitems,
            "n_items_with_conditions": n_items_with_conditions,
            "n_items_with_allowed_actions": n_items_with_actions,
            "n_items_with_justification": n_items_with_justification,
            "complexity_score": (
                len(keys)
                + n_subitems
                + len(ge.get("types") or [])
                + len(ge.get("legal_refs") or [])
                + n_items_with_conditions
                + n_items_with_actions
                + n_items_with_justification
            ),
            "has_header": bool(ge.get("header")),
        })
    return rows


def build_item_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, ge in source.items():
        for key in item_keys(ge):
            item = ge[key]
            subkeys = [sub_key for sub_key in item if "." in sub_key]
            rows.append({
                "request_id": request_id,
                "item_index": key,
                "record_primary_type": ge.get("primary_type") or UNKNOWN,
                "item_type": item.get("type") or UNKNOWN,
                "legal_ref": item.get("legal_ref"),
                "legal_family": legal_family(item.get("legal_ref"), item.get("text")),
                "has_legal_ref": bool(item.get("legal_ref")),
                "has_subjects": bool(item.get("subjects")),
                "has_conditions": bool(item.get("conditions")),
                "has_allowed_actions": bool(item.get("allowed_actions")),
                "has_justification": bool(item.get("justification")),
                "n_subjects": len(item.get("subjects") or []),
                "n_conditions": len(item.get("conditions") or []),
                "n_allowed_actions": len(item.get("allowed_actions") or []),
                "n_subitems": len(subkeys),
                "text_length": len(item.get("text") or ""),
            })
    return rows


def build_type_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, ge in source.items():
        for exemption_type in ge.get("types") or [UNKNOWN]:
            rows.append({
                "request_id": request_id,
                "type": exemption_type or UNKNOWN,
                "primary_type": ge.get("primary_type") or UNKNOWN,
            })
    return rows


def save_barh(series: pd.Series, title: str, xlabel: str, path: Path) -> None:
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


def to_plain_dict(series: pd.Series) -> dict:
    return {
        str(index): value.item() if hasattr(value, "item") else value
        for index, value in series.items()
    }


def save_metadata(
    output_dir: Path,
    input_file: Path,
    records: pd.DataFrame,
    items: pd.DataFrame,
    type_rows: pd.DataFrame,
    generated_figures: list[Path],
) -> None:
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_file),
        "output_dir": str(output_dir),
        "figures": [path.name for path in generated_figures],
        "record_count": int(len(records)),
        "item_count": int(len(items)),
        "primary_type_counts": to_plain_dict(
            records["primary_type"].value_counts().sort_index()
        ),
        "type_label_counts": to_plain_dict(
            type_rows["type"].value_counts().sort_index()
        ),
        "item_type_counts": to_plain_dict(
            items["item_type"].value_counts().sort_index()
        ) if not items.empty else {},
        "legal_domain_counts": to_plain_dict(
            items["legal_family"].value_counts().sort_index()
        ) if not items.empty else {},
        "top_legal_refs": to_plain_dict(
            items["legal_ref"].dropna().value_counts().head(20)
        ) if not items.empty else {},
        "summary": {
            "empty_record_count": int(records["is_empty"].sum()),
            "records_with_header": int(records["has_header"].sum()),
            "records_with_subjects": int((records["n_subjects"] > 0).sum()),
            "records_with_subitems": int((records["n_subitems"] > 0).sum()),
            "max_items_per_record": int(records["n_items"].max()) if not records.empty else 0,
            "avg_items_per_record": (
                float(records["n_items"].mean()) if not records.empty else 0.0
            ),
            "max_complexity_score": (
                int(records["complexity_score"].max()) if not records.empty else 0
            ),
            "avg_complexity_score": (
                float(records["complexity_score"].mean()) if not records.empty else 0.0
            ),
        },
        "rationale_signal_coverage_percent": {},
        "rationale_signal_by_exemption_domain_percent": {},
    }

    if not items.empty:
        coverage = items[FEATURE_COLUMNS].mean().mul(100).round(2)
        metadata["rationale_signal_coverage_percent"] = to_plain_dict(coverage)
        grouped = (
            items.groupby("record_primary_type")[FEATURE_COLUMNS]
            .mean()
            .mul(100)
            .round(2)
        )
        metadata["rationale_signal_by_exemption_domain_percent"] = {
            str(index): to_plain_dict(row)
            for index, row in grouped.iterrows()
        }

    path = output_dir / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


def plot_primary_type_distribution(records: pd.DataFrame, output_dir: Path) -> None:
    counts = records["primary_type"].value_counts().sort_values()
    save_barh(
        counts,
        "Granted Exemption Domain Distribution",
        "Number of requests",
        output_dir / "exemption_domain_distribution.png",
    )


def plot_type_frequency(type_rows: pd.DataFrame, output_dir: Path) -> None:
    counts = type_rows["type"].value_counts().sort_values()
    save_barh(
        counts,
        "Granted Exemption Domain Label Frequency",
        "Number of domain labels",
        output_dir / "exemption_domain_label_frequency.png",
    )


def plot_top_legal_refs(source: dict[str, dict], output_dir: Path, top_n: int = 20) -> None:
    refs = Counter()
    for ge in source.values():
        refs.update(ref for ref in ge.get("legal_refs", []) if ref)

    counts = pd.Series(dict(refs.most_common(top_n))).sort_values()
    save_barh(
        counts,
        f"Top {top_n} Legal Basis References",
        "Number of requests",
        output_dir / "legal_basis_reference_frequency.png",
    )


def plot_items_per_request(records: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    max_items = int(records["n_items"].max()) if not records.empty else 0
    bins = range(0, max_items + 2)
    ax.hist(records["n_items"], bins=bins, align="left", rwidth=0.75)
    ax.set_title("Decision Pattern: Exemption Items per Request", fontweight="bold")
    ax.set_xlabel("Number of top-level items")
    ax.set_ylabel("Number of requests")
    ax.set_xticks(list(bins))
    fig.tight_layout()
    path = output_dir / "decision_pattern_item_count.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_item_feature_coverage(items: pd.DataFrame, output_dir: Path) -> None:
    if items.empty:
        print("Skipped item feature coverage: no item rows")
        return

    features = [
        "has_legal_ref",
        "has_subjects",
        "has_conditions",
        "has_allowed_actions",
        "has_justification",
    ]
    coverage = items[features].mean().mul(100).round(1).sort_values()
    coverage.index = [
        label.replace("has_", "").replace("_", " ")
        for label in coverage.index
    ]
    save_barh(
        coverage,
        "Administrative Rationale Signal Coverage",
        "Share of exemption items (%)",
        output_dir / "rationale_signal_coverage.png",
    )


def plot_item_type_x_feature(items: pd.DataFrame, output_dir: Path) -> None:
    if items.empty:
        print("Skipped item type feature heatmap: no item rows")
        return

    heat = (
        items.groupby("item_type")[FEATURE_COLUMNS]
        .mean()
        .mul(100)
        .rename(columns=lambda col: col.replace("has_", "").replace("_", " "))
    )
    if heat.empty:
        print("Skipped item type feature heatmap: no grouped rows")
        return

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(heat) * 0.55)))
    sns.heatmap(
        heat,
        annot=True,
        fmt=".0f",
        cmap="Blues",
        linewidths=0.5,
        cbar_kws={"label": "% of items"},
        ax=ax,
    )
    ax.set_title("Rationale Signal Coverage by Exemption Item Domain", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "rationale_signal_by_item_domain.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_type_cooccurrence(type_rows: pd.DataFrame, output_dir: Path) -> None:
    if type_rows.empty:
        print("Skipped type co-occurrence heatmap: no type rows")
        return

    matrix = (
        type_rows.assign(value=1)
        .pivot_table(
            index="request_id",
            columns="type",
            values="value",
            aggfunc="max",
            fill_value=0,
        )
    )
    cooccurrence = matrix.T.dot(matrix)
    if cooccurrence.empty:
        print("Skipped type co-occurrence heatmap: empty matrix")
        return

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(cooccurrence, annot=True, fmt="d", cmap="Blues", linewidths=0.5, ax=ax)
    ax.set_title("Exemption Domain Co-occurrence", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "exemption_domain_cooccurrence.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_legal_family_frequency(items: pd.DataFrame, output_dir: Path) -> None:
    if items.empty:
        print("Skipped legal family figure: no item rows")
        return

    counts = items["legal_family"].value_counts().sort_values()
    save_barh(
        counts,
        "Legal Domain Frequency by Exemption Item",
        "Number of exemption items",
        output_dir / "legal_domain_frequency.png",
    )


def plot_record_primary_feature_coverage(items: pd.DataFrame, output_dir: Path) -> None:
    if items.empty:
        print("Skipped record primary feature heatmap: no item rows")
        return

    group_sizes = items.groupby("record_primary_type").size()
    heat = (
        items.groupby("record_primary_type")[FEATURE_COLUMNS]
        .mean()
        .mul(100)
        .rename(columns=lambda col: col.replace("has_", "").replace("_", " "))
    )
    if heat.empty:
        print("Skipped record primary feature heatmap: no grouped rows")
        return

    # Annotate small-sample groups so 0%/100% rows aren't read as confident
    # rates when they're based on just one or two records.
    heat.index = [f"{label} (n={group_sizes[label]})" for label in heat.index]

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(heat) * 0.55)))
    sns.heatmap(
        heat,
        annot=True,
        fmt=".0f",
        cmap="Blues",
        linewidths=0.5,
        cbar_kws={"label": "% of items"},
        ax=ax,
    )
    ax.set_title("Rationale Signal Coverage by Exemption Domain", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "rationale_signal_by_exemption_domain.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_complexity_by_primary_type(records: pd.DataFrame, output_dir: Path) -> None:
    if records.empty:
        print("Skipped complexity figure: no record rows")
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(
        data=records,
        x="complexity_score",
        y="primary_type",
        orient="h",
        ax=ax,
    )
    ax.set_title("Decision Pattern Complexity by Exemption Domain", fontweight="bold")
    ax.set_xlabel("Derived complexity score")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "decision_pattern_complexity_by_domain.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_text_length_by_item_type(items: pd.DataFrame, output_dir: Path) -> None:
    if items.empty:
        print("Skipped text length figure: no item rows")
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(
        data=items,
        x="text_length",
        y="item_type",
        orient="h",
        ax=ax,
    )
    ax.set_title("Rationale Text Length by Exemption Item Domain", fontweight="bold")
    ax.set_xlabel("Characters in item text")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "rationale_text_length_by_item_domain.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def main() -> None:
    print(f"\nAnalyzing granted exemptions: {INPUT_FILE}\n")
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    granted = load_granted_exemptions(INPUT_FILE)
    records = pd.DataFrame(build_record_rows(granted))
    items = pd.DataFrame(build_item_rows(granted))
    type_rows = pd.DataFrame(build_type_rows(granted))

    generated_figures = [
        output_dir / "exemption_domain_distribution.png",
        output_dir / "exemption_domain_label_frequency.png",
        output_dir / "legal_basis_reference_frequency.png",
        output_dir / "decision_pattern_item_count.png",
        output_dir / "rationale_signal_coverage.png",
        output_dir / "rationale_signal_by_item_domain.png",
        output_dir / "exemption_domain_cooccurrence.png",
        output_dir / "legal_domain_frequency.png",
        output_dir / "rationale_signal_by_exemption_domain.png",
        output_dir / "decision_pattern_complexity_by_domain.png",
        output_dir / "rationale_text_length_by_item_domain.png",
    ]

    plot_primary_type_distribution(records, output_dir)
    plot_type_frequency(type_rows, output_dir)
    plot_top_legal_refs(granted, output_dir)
    plot_items_per_request(records, output_dir)
    plot_item_feature_coverage(items, output_dir)
    plot_item_type_x_feature(items, output_dir)
    plot_type_cooccurrence(type_rows, output_dir)
    plot_legal_family_frequency(items, output_dir)
    plot_record_primary_feature_coverage(items, output_dir)
    plot_complexity_by_primary_type(records, output_dir)
    plot_text_length_by_item_type(items, output_dir)
    save_metadata(output_dir, INPUT_FILE, records, items, type_rows, generated_figures)

    print(f"\nAnalyzed {len(records)} requests and {len(items)} exemption items.")
    print(f"All exemption figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
