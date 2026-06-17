"""
Decision basis analysis.

Reads the request-keyed *_parsed_decision_basis.json produced by parse.py
and writes simple exploratory figures to res/figures/decision_basis/.

Run:
    uv run python analyze_decision_basis.py
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE


INPUT_FILE = JSON_FILE.parent / (JSON_FILE.stem + "_parsed_decision_basis.json")
OUTPUT_DIR = Path("res/figures/decision_basis")
UNKNOWN = "unknown"

NORMALIZED_FIELDS = [
    "development_plan",
    "regulations",
    "plan_type",
    "plan_name",
    "zone_code",
    "legal_ordinance",
    "plan_references",
    "plan_primary_type",
]
NORMALIZED_FIELD_SET = set(NORMALIZED_FIELDS)

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.0)


def load_decision_basis(path: Path) -> dict[str, dict]:
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

    raise ValueError(f"Unsupported decision basis JSON shape: {type(data).__name__}")


def zone_prefix(zone_code) -> str:
    if not isinstance(zone_code, str) or not zone_code.strip():
        return UNKNOWN

    match = re.match(r"([A-ZÄÖÜ]{1,4})\b", zone_code.strip())
    return match.group(1) if match else UNKNOWN


def zone_quality(zone_code) -> str:
    if not isinstance(zone_code, str) or not zone_code.strip():
        return "missing"

    text = zone_code.strip()
    if re.match(r"^[A-ZÄÖÜ]{1,4}\b", text):
        return "parsed_prefix"
    if text.lower().startswith(("type:", "front:", "back:")):
        return "source_label"
    if "baugesetzbuch" in text.lower():
        return "legal_text"
    return "unparsed_text"


def has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def build_record_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, basis in source.items():
        plan_refs = basis.get("plan_references") or []
        rows.append({
            "request_id": request_id,
            "plan_primary_type": basis.get("plan_primary_type") or UNKNOWN,
            "plan_type": basis.get("plan_type") or UNKNOWN,
            "plan_name": basis.get("plan_name") or UNKNOWN,
            "zone_code": basis.get("zone_code") or UNKNOWN,
            "zone_prefix": zone_prefix(basis.get("zone_code")),
            "zone_quality": zone_quality(basis.get("zone_code")),
            "legal_ordinance": basis.get("legal_ordinance") or UNKNOWN,
            "n_plan_references": len(plan_refs) if isinstance(plan_refs, list) else 0,
            "n_notes": len(basis.get("_notes") or []),
            "n_keys": len(basis),
            **{
                f"has_{field}": has_value(basis.get(field))
                for field in NORMALIZED_FIELDS
            },
        })
    return rows


def build_key_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, basis in source.items():
        for key, value in basis.items():
            rows.append({
                "request_id": request_id,
                "key": key,
                "is_normalized": key in NORMALIZED_FIELD_SET or key == "_notes",
                "has_value": has_value(value),
            })
    return rows


def build_plan_reference_rows(source: dict[str, dict]) -> list[dict]:
    rows = []
    for request_id, basis in source.items():
        refs = basis.get("plan_references") or []
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            rows.append({
                "request_id": request_id,
                "name": ref.get("name") or UNKNOWN,
                "type": ref.get("type") or UNKNOWN,
                "plan_primary_type": basis.get("plan_primary_type") or UNKNOWN,
            })
    return rows


def to_plain_dict(series: pd.Series) -> dict:
    return {
        str(index): value.item() if hasattr(value, "item") else value
        for index, value in series.items()
    }


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


def plot_plan_primary_type(records: pd.DataFrame, output_dir: Path) -> None:
    counts = records["plan_primary_type"].value_counts().sort_values()
    save_barh(
        counts,
        "Planning-Regulatory Context by Primary Plan Type",
        "Number of requests",
        output_dir / "planning_context_primary_plan_distribution.png",
    )


def plot_plan_type(records: pd.DataFrame, output_dir: Path) -> None:
    counts = records["plan_type"].value_counts().sort_values()
    save_barh(
        counts,
        "Planning-Regulatory Context by Parsed Plan Type",
        "Number of requests",
        output_dir / "planning_context_plan_type_distribution.png",
    )


def plot_legal_ordinance(records: pd.DataFrame, output_dir: Path) -> None:
    counts = records["legal_ordinance"].value_counts().sort_values()
    save_barh(
        counts,
        "Planning-Regulatory Ordinance Frequency",
        "Number of requests",
        output_dir / "planning_context_ordinance_distribution.png",
    )


def plot_zone_prefix(records: pd.DataFrame, output_dir: Path, top_n: int = 20) -> None:
    counts = records["zone_prefix"].value_counts().head(top_n).sort_values()
    n_total = records["zone_prefix"].nunique()
    title = (
        f"Top {top_n} Planning Context Zone Prefixes"
        if n_total > top_n
        else "Planning Context Zone Prefixes"
    )
    save_barh(
        counts,
        title,
        "Number of requests",
        output_dir / "planning_context_zone_prefix_frequency.png",
    )


def plot_plan_reference_types(plan_refs: pd.DataFrame, output_dir: Path) -> None:
    if plan_refs.empty:
        print("Skipped plan reference type figure: no plan references")
        return

    counts = plan_refs["type"].value_counts().sort_values()
    save_barh(
        counts,
        "Planning Context Plan Reference Type Frequency",
        "Number of plan references",
        output_dir / "planning_context_plan_reference_type_frequency.png",
    )


def plot_field_coverage(records: pd.DataFrame, output_dir: Path) -> None:
    fields = [f"has_{field}" for field in NORMALIZED_FIELDS]
    coverage = records[fields].mean().mul(100).sort_values()
    coverage.index = [
        label.replace("has_", "").replace("_", " ")
        for label in coverage.index
    ]
    save_barh(
        coverage,
        "Planning-Regulatory Context Field Coverage",
        "Share of requests (%)",
        output_dir / "planning_context_field_coverage.png",
    )


def plot_zone_quality(records: pd.DataFrame, output_dir: Path) -> None:
    counts = records["zone_quality"].value_counts().sort_values()
    save_barh(
        counts,
        "Planning Context Zone Parse Quality",
        "Number of requests",
        output_dir / "planning_context_zone_parse_quality.png",
    )


def plot_plan_references_per_record(records: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    max_refs = int(records["n_plan_references"].max()) if not records.empty else 0
    bins = range(0, max_refs + 2)
    ax.hist(records["n_plan_references"], bins=bins, align="left", rwidth=0.75)
    ax.set_title("Planning Context Plan References per Request", fontweight="bold")
    ax.set_xlabel("Number of plan references")
    ax.set_ylabel("Number of requests")
    ax.set_xticks(list(bins))
    fig.tight_layout()
    path = output_dir / "planning_context_plan_reference_count.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_key_frequency(keys: pd.DataFrame, output_dir: Path) -> None:
    if keys.empty:
        print("Skipped key frequency figure: no key rows")
        return

    counts = keys["key"].value_counts().head(25).sort_values()
    save_barh(
        counts,
        "Decision Basis Residual Key Frequency",
        "Number of requests containing key",
        output_dir / "decision_basis_residual_key_frequency.png",
    )


def plot_cross_tab(
    records: pd.DataFrame,
    row: str,
    column: str,
    title: str,
    path: Path,
) -> None:
    sub = records[[row, column]].dropna()
    if sub.empty:
        print(f"Skipped empty cross-tab: {path}")
        return

    table = pd.crosstab(sub[row], sub[column])
    if table.empty:
        print(f"Skipped empty cross-tab: {path}")
        return

    # Color by each row's share of its own total so one dominant cell doesn't
    # wash out smaller-but-nonzero cells in other rows; annotations still show
    # the raw counts.
    row_share = table.div(table.sum(axis=1), axis=0)

    fig, ax = plt.subplots(
        figsize=(max(8, len(table.columns) * 1.2), max(4, len(table) * 0.65))
    )
    sns.heatmap(
        row_share,
        annot=table,
        fmt="d",
        cmap="Blues",
        linewidths=0.5,
        cbar_kws={"label": "Share of row total"},
        ax=ax,
    )
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(column.replace("_", " "))
    ax.set_ylabel(row.replace("_", " "))
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def save_metadata(
    output_dir: Path,
    input_file: Path,
    records: pd.DataFrame,
    plan_refs: pd.DataFrame,
    keys: pd.DataFrame,
    generated_figures: list[Path],
) -> None:
    field_coverage = records[[f"has_{field}" for field in NORMALIZED_FIELDS]].mean()

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_file),
        "output_dir": str(output_dir),
        "figures": [path.name for path in generated_figures],
        "record_count": int(len(records)),
        "plan_reference_count": int(len(plan_refs)),
        "planning_context_primary_plan_counts": to_plain_dict(
            records["plan_primary_type"].value_counts().sort_index()
        ),
        "planning_context_plan_type_counts": to_plain_dict(
            records["plan_type"].value_counts().sort_index()
        ),
        "planning_context_ordinance_counts": to_plain_dict(
            records["legal_ordinance"].value_counts().sort_index()
        ),
        "planning_context_zone_prefix_counts": to_plain_dict(
            records["zone_prefix"].value_counts().sort_index()
        ),
        "planning_context_zone_quality_counts": to_plain_dict(
            records["zone_quality"].value_counts().sort_index()
        ),
        "planning_context_plan_reference_type_counts": to_plain_dict(
            plan_refs["type"].value_counts().sort_index()
        ) if not plan_refs.empty else {},
        "key_counts": to_plain_dict(
            keys["key"].value_counts().sort_index()
        ) if not keys.empty else {},
        "ad_hoc_key_counts": to_plain_dict(
            keys.loc[~keys["is_normalized"], "key"].value_counts().sort_index()
        ) if not keys.empty else {},
        "summary": {
            "records_with_notes": int((records["n_notes"] > 0).sum()),
            "records_with_multiple_plan_references": int(
                (records["n_plan_references"] > 1).sum()
            ),
            "max_plan_references_per_record": (
                int(records["n_plan_references"].max()) if not records.empty else 0
            ),
            "avg_plan_references_per_record": (
                float(records["n_plan_references"].mean()) if not records.empty else 0.0
            ),
            "max_decision_basis_keys": int(records["n_keys"].max()) if not records.empty else 0,
            "avg_decision_basis_keys": (
                float(records["n_keys"].mean()) if not records.empty else 0.0
            ),
            "records_with_unparsed_zone_code": int(
                records["zone_quality"].isin(["source_label", "legal_text", "unparsed_text"]).sum()
            ),
            "normalized_key_share": (
                float(keys["is_normalized"].mean()) if not keys.empty else 0.0
            ),
        },
        "planning_context_field_coverage_percent": to_plain_dict(field_coverage.mul(100).round(2)),
    }

    path = output_dir / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


def main() -> None:
    print(f"\nAnalyzing decision basis: {INPUT_FILE}\n")
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    decision_basis = load_decision_basis(INPUT_FILE)
    records = pd.DataFrame(build_record_rows(decision_basis))
    keys = pd.DataFrame(build_key_rows(decision_basis))
    plan_refs = pd.DataFrame(build_plan_reference_rows(decision_basis))

    generated_figures = [
        output_dir / "planning_context_primary_plan_distribution.png",
        output_dir / "planning_context_plan_type_distribution.png",
        output_dir / "planning_context_ordinance_distribution.png",
        output_dir / "planning_context_zone_prefix_frequency.png",
        output_dir / "planning_context_plan_reference_type_frequency.png",
        output_dir / "planning_context_field_coverage.png",
        output_dir / "planning_context_zone_parse_quality.png",
        output_dir / "planning_context_plan_reference_count.png",
        output_dir / "decision_basis_residual_key_frequency.png",
        output_dir / "planning_context_plan_x_ordinance.png",
        output_dir / "planning_context_plan_x_zone_prefix.png",
    ]

    plot_plan_primary_type(records, output_dir)
    plot_plan_type(records, output_dir)
    plot_legal_ordinance(records, output_dir)
    plot_zone_prefix(records, output_dir)
    plot_plan_reference_types(plan_refs, output_dir)
    plot_field_coverage(records, output_dir)
    plot_zone_quality(records, output_dir)
    plot_plan_references_per_record(records, output_dir)
    plot_key_frequency(keys, output_dir)
    plot_cross_tab(
        records,
        "plan_primary_type",
        "legal_ordinance",
        "Planning Context: Primary Plan Type x Legal Ordinance",
        output_dir / "planning_context_plan_x_ordinance.png",
    )
    plot_cross_tab(
        records,
        "plan_primary_type",
        "zone_prefix",
        "Planning Context: Primary Plan Type x Zone Prefix",
        output_dir / "planning_context_plan_x_zone_prefix.png",
    )
    save_metadata(output_dir, INPUT_FILE, records, plan_refs, keys, generated_figures)

    print(f"\nAnalyzed {len(records)} decision basis records.")
    print(f"All decision basis figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
