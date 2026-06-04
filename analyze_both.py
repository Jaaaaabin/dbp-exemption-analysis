"""
Combined exemption and decision-basis analysis.

Reads the two focused JSON exports produced by parse.py, links them by
request_id, and writes cross-branch figures plus findings metadata to
res/figures/both/.

Run:
    uv run python analyze_both.py
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from settings import JSON_ANALYZE_READY_FILE as JSON_FILE


EXEMPTION_FILE = JSON_FILE.parent / (
    JSON_FILE.stem + "_parsed_granted_exemptions.json"
)
DECISION_BASIS_FILE = JSON_FILE.parent / (
    JSON_FILE.stem + "_parsed_decision_basis.json"
)
EXEMPTION_METADATA_FILE = Path("res/figures/exemption/metadata.json")
DECISION_BASIS_METADATA_FILE = Path("res/figures/decision_basis/metadata.json")
OUTPUT_DIR = Path("res/figures/both")

META_KEYS = {"header", "types", "primary_type", "is_empty", "legal_refs", "subjects"}
UNKNOWN = "unknown"
RATIONALE_COLUMNS = [
    "has_conditions",
    "has_allowed_actions",
    "has_justification",
    "has_subjects",
]

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.0)


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


def load_json_if_present(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def item_keys(granted_exemption: dict) -> list[str]:
    return [
        key
        for key, value in granted_exemption.items()
        if key not in META_KEYS and isinstance(value, dict)
    ]


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


def legal_domain(ref: str | None, text: str | None = None) -> str:
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


def build_record_rows(
    exemptions: dict[str, dict],
    decision_basis: dict[str, dict],
) -> list[dict]:
    rows = []
    for request_id in sorted(set(exemptions) & set(decision_basis), key=int):
        ge = exemptions[request_id]
        db = decision_basis[request_id]
        keys = item_keys(ge)
        items = [ge[key] for key in keys]
        n_subitems = sum(
            len([sub_key for sub_key in item if "." in sub_key])
            for item in items
        )
        has_conditions = any(bool(item.get("conditions")) for item in items)
        has_actions = any(bool(item.get("allowed_actions")) for item in items)
        has_justification = any(bool(item.get("justification")) for item in items)
        has_subjects = bool(ge.get("subjects")) or any(
            bool(item.get("subjects")) for item in items
        )
        complexity_score = (
            len(keys)
            + n_subitems
            + len(ge.get("types") or [])
            + len(ge.get("legal_refs") or [])
            + int(has_conditions)
            + int(has_actions)
            + int(has_justification)
            + int(has_subjects)
        )
        plan_refs = db.get("plan_references") or []

        rows.append({
            "request_id": request_id,
            "exemption_domain": ge.get("primary_type") or UNKNOWN,
            "is_empty": bool(ge.get("is_empty")),
            "n_exemption_domains": len(ge.get("types") or []),
            "n_legal_refs": len(ge.get("legal_refs") or []),
            "n_exemption_items": len(keys),
            "n_subitems": n_subitems,
            "has_conditions": has_conditions,
            "has_allowed_actions": has_actions,
            "has_justification": has_justification,
            "has_subjects": has_subjects,
            "complexity_score": complexity_score,
            "plan_primary_type": db.get("plan_primary_type") or UNKNOWN,
            "plan_type": db.get("plan_type") or UNKNOWN,
            "legal_ordinance": db.get("legal_ordinance") or UNKNOWN,
            "zone_prefix": zone_prefix(db.get("zone_code")),
            "zone_quality": zone_quality(db.get("zone_code")),
            "n_plan_references": len(plan_refs) if isinstance(plan_refs, list) else 0,
        })
    return rows


def build_item_rows(
    exemptions: dict[str, dict],
    decision_basis: dict[str, dict],
) -> list[dict]:
    rows = []
    for request_id in sorted(set(exemptions) & set(decision_basis), key=int):
        ge = exemptions[request_id]
        db = decision_basis[request_id]
        for key in item_keys(ge):
            item = ge[key]
            rows.append({
                "request_id": request_id,
                "exemption_domain": ge.get("primary_type") or UNKNOWN,
                "item_domain": item.get("type") or UNKNOWN,
                "legal_domain": legal_domain(item.get("legal_ref"), item.get("text")),
                "legal_ref": item.get("legal_ref"),
                "has_conditions": bool(item.get("conditions")),
                "has_allowed_actions": bool(item.get("allowed_actions")),
                "has_justification": bool(item.get("justification")),
                "has_subjects": bool(item.get("subjects")),
                "text_length": len(item.get("text") or ""),
                "plan_primary_type": db.get("plan_primary_type") or UNKNOWN,
                "legal_ordinance": db.get("legal_ordinance") or UNKNOWN,
                "zone_prefix": zone_prefix(db.get("zone_code")),
            })
    return rows


def to_plain_dict(series: pd.Series) -> dict:
    return {
        str(index): value.item() if hasattr(value, "item") else value
        for index, value in series.items()
    }


def save_heatmap(
    table: pd.DataFrame,
    title: str,
    path: Path,
    percent: bool = False,
) -> None:
    if table.empty:
        print(f"Skipped empty heatmap: {path}")
        return

    fig, ax = plt.subplots(
        figsize=(max(8, len(table.columns) * 1.25), max(4, len(table) * 0.65))
    )
    fmt = ".1f" if percent else "d"
    sns.heatmap(table, annot=True, fmt=fmt, cmap="Blues", linewidths=0.5, ax=ax)
    ax.set_title(title, fontweight="bold")
    ax.tick_params(axis="x", rotation=30)
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def cramers_v(table: pd.DataFrame) -> float:
    if table.empty:
        return 0.0

    observed = table.astype(float)
    n = observed.to_numpy().sum()
    if n == 0:
        return 0.0

    row_sums = observed.sum(axis=1).to_numpy()[:, None]
    col_sums = observed.sum(axis=0).to_numpy()[None, :]
    expected = row_sums @ col_sums / n
    mask = expected > 0
    chi2 = (((observed.to_numpy() - expected) ** 2) / expected)[mask].sum()
    r, c = observed.shape
    denom = n * (min(r - 1, c - 1))
    if denom <= 0:
        return 0.0
    return float((chi2 / denom) ** 0.5)


def association_metrics(records: pd.DataFrame, items: pd.DataFrame) -> dict:
    record_pairs = {
        "exemption_domain_x_planning_context": (
            records["exemption_domain"],
            records["plan_primary_type"],
        ),
        "exemption_domain_x_ordinance_context": (
            records["exemption_domain"],
            records["legal_ordinance"],
        ),
        "exemption_domain_x_zone_quality": (
            records["exemption_domain"],
            records["zone_quality"],
        ),
    }
    item_pairs = {
        "legal_domain_x_ordinance_context": (
            items["legal_domain"],
            items["legal_ordinance"],
        ),
    }

    metrics = {}
    for name, (left, right) in {**record_pairs, **item_pairs}.items():
        table = pd.crosstab(left, right)
        metrics[name] = {
            "cramers_v": round(cramers_v(table), 4),
            "n": int(table.to_numpy().sum()),
            "rows": int(table.shape[0]),
            "columns": int(table.shape[1]),
        }
    return metrics


def plot_exemption_domain_x_plan(records: pd.DataFrame, output_dir: Path) -> None:
    table = pd.crosstab(
        records["plan_primary_type"],
        records["exemption_domain"],
        normalize="index",
    ).mul(100)
    counts = pd.crosstab(records["plan_primary_type"], records["exemption_domain"])
    totals = counts.sum(axis=1)

    order = totals.sort_values().index
    table = table.loc[order]

    fig, ax = plt.subplots(figsize=(11, max(4, len(table) * 0.6)))
    table.plot(kind="barh", stacked=True, ax=ax, linewidth=0.4, edgecolor="white")
    for i, (_, total) in enumerate(totals.loc[order].items()):
        ax.text(101, i, f"n={total}", va="center", fontsize=8)
    ax.set_title("Exemption Domain Composition within Planning Contexts", fontweight="bold")
    ax.set_xlabel("Share of requests (%)")
    ax.set_ylabel("")
    ax.set_xlim(0, 112)
    ax.legend(title="Exemption domain", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    path = output_dir / "exemption_domain_x_planning_context.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_exemption_domain_x_ordinance(records: pd.DataFrame, output_dir: Path) -> None:
    table = pd.crosstab(
        records["legal_ordinance"],
        records["exemption_domain"],
        normalize="index",
    ).mul(100)
    counts = pd.crosstab(records["legal_ordinance"], records["exemption_domain"])
    totals = counts.sum(axis=1)
    order = totals.sort_values().index
    table = table.loc[order]

    fig, ax = plt.subplots(figsize=(11, max(3.5, len(table) * 0.7)))
    table.plot(kind="barh", stacked=True, ax=ax, linewidth=0.4, edgecolor="white")
    for i, (_, total) in enumerate(totals.loc[order].items()):
        ax.text(101, i, f"n={total}", va="center", fontsize=8)
    ax.set_title("Exemption Domain Composition within Ordinance Contexts", fontweight="bold")
    ax.set_xlabel("Share of requests (%)")
    ax.set_ylabel("")
    ax.set_xlim(0, 112)
    ax.legend(title="Exemption domain", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    path = output_dir / "exemption_domain_x_ordinance_context.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_legal_domain_x_ordinance(items: pd.DataFrame, output_dir: Path) -> None:
    counts = (
        items.groupby(["legal_domain", "legal_ordinance"])
        .size()
        .reset_index(name="count")
    )
    if counts.empty:
        print("Skipped empty bubble plot: legal_domain_x_ordinance_context.png")
        return

    legal_order = (
        counts.groupby("legal_domain")["count"].sum().sort_values(ascending=False).index
    )
    ordinance_order = (
        counts.groupby("legal_ordinance")["count"].sum().sort_values(ascending=False).index
    )
    x_map = {value: i for i, value in enumerate(ordinance_order)}
    y_map = {value: i for i, value in enumerate(legal_order)}

    fig, ax = plt.subplots(figsize=(9, max(4, len(legal_order) * 0.55)))
    for _, row in counts.iterrows():
        x = x_map[row["legal_ordinance"]]
        y = y_map[row["legal_domain"]]
        size = max(row["count"] * 85, 55)
        ax.scatter(x, y, s=size, alpha=0.72)
        ax.text(x, y, str(row["count"]), ha="center", va="center", fontsize=8)

    ax.set_xticks(range(len(ordinance_order)))
    ax.set_xticklabels(ordinance_order, rotation=25, ha="right")
    ax.set_yticks(range(len(legal_order)))
    ax.set_yticklabels(legal_order)
    ax.set_title("Legal Domain Intensity across Ordinance Contexts", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.grid(True, axis="both", linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    path = output_dir / "legal_domain_x_ordinance_context.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_rationale_signals_by_plan(records: pd.DataFrame, output_dir: Path) -> None:
    rates = (
        records.groupby("plan_primary_type")[RATIONALE_COLUMNS]
        .mean()
        .mul(100)
        .rename(columns=lambda col: col.replace("has_", "").replace("_", " "))
        .reset_index()
    )
    long = rates.melt(
        id_vars="plan_primary_type",
        var_name="rationale_signal",
        value_name="share_percent",
    )
    order = (
        records["plan_primary_type"].value_counts().sort_values(ascending=False).index
    )

    fig, ax = plt.subplots(figsize=(12, 5.5))
    sns.barplot(
        data=long,
        x="share_percent",
        y="plan_primary_type",
        hue="rationale_signal",
        order=order,
        ax=ax,
    )
    ax.set_title("Administrative Rationale Signals by Planning Context", fontweight="bold")
    ax.set_xlabel("Share of requests (%)")
    ax.set_ylabel("")
    ax.legend(title="Rationale signal", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    path = output_dir / "rationale_signals_by_planning_context.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_complexity_by_plan(records: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(
        data=records,
        x="complexity_score",
        y="plan_primary_type",
        orient="h",
        ax=ax,
        color="#d8dde6",
        fliersize=0,
    )
    sns.stripplot(
        data=records,
        x="complexity_score",
        y="plan_primary_type",
        orient="h",
        ax=ax,
        color="#2f5d7c",
        alpha=0.7,
        size=4,
        jitter=0.22,
    )
    ax.set_title("Decision Pattern Complexity by Planning Context", fontweight="bold")
    ax.set_xlabel("Derived complexity score")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "decision_pattern_complexity_by_planning_context.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_zone_quality_by_domain(records: pd.DataFrame, output_dir: Path) -> None:
    table = pd.crosstab(
        records["exemption_domain"],
        records["zone_quality"],
        normalize="index",
    ).mul(100)
    counts = pd.crosstab(records["exemption_domain"], records["zone_quality"])
    totals = counts.sum(axis=1)
    order = totals.sort_values().index
    table = table.loc[order]

    fig, ax = plt.subplots(figsize=(10.5, max(4, len(table) * 0.55)))
    table.plot(kind="barh", stacked=True, ax=ax, linewidth=0.4, edgecolor="white")
    for i, (_, total) in enumerate(totals.loc[order].items()):
        ax.text(101, i, f"n={total}", va="center", fontsize=8)
    ax.set_title("Zone Parse Quality Composition by Exemption Domain", fontweight="bold")
    ax.set_xlabel("Share of requests (%)")
    ax.set_ylabel("")
    ax.set_xlim(0, 112)
    ax.legend(title="Zone parse quality", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    path = output_dir / "zone_quality_by_exemption_domain.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def finding_development_plan_concentration(records: pd.DataFrame) -> dict:
    development = records[records["plan_primary_type"] == "development_plan"]
    top_pairs = (
        records.groupby(["exemption_domain", "plan_primary_type"])
        .size()
        .sort_values(ascending=False)
    )
    dominant_pairs = to_plain_dict(top_pairs.head(5))
    mixed_tree_count = int(
        len(
            development[
                development["exemption_domain"].isin(["mixed", "tree_environmental"])
            ]
        )
    )
    return {
        "finding": "Development-plan contexts dominate the joined decision patterns, and within that context mixed and tree/environmental exemptions form the largest combined block.",
        "evidence": {
            "development_plan_records": int(len(development)),
            "total_records": int(len(records)),
            "mixed_or_tree_environmental_in_development_plan": mixed_tree_count,
            "top_exemption_domain_by_plan_pairs": dominant_pairs,
        },
    }


def finding_rationale_signal_divergence(records: pd.DataFrame) -> dict:
    rates = (
        records.groupby("plan_primary_type")[RATIONALE_COLUMNS]
        .mean()
        .mul(100)
        .round(2)
    )
    construction = (
        rates.loc["construction_plan"].to_dict()
        if "construction_plan" in rates.index
        else {}
    )
    development = (
        rates.loc["development_plan"].to_dict()
        if "development_plan" in rates.index
        else {}
    )
    return {
        "finding": "Rationale-bearing signals vary by planning context; construction-plan records show stronger justification and condition presence than development-plan records in this dataset.",
        "evidence": {
            "construction_plan_signal_rates_percent": construction,
            "development_plan_signal_rates_percent": development,
        },
    }


def finding_legal_domain_context_crossing(items: pd.DataFrame) -> dict:
    table = pd.crosstab(items["legal_domain"], items["legal_ordinance"])
    top_pairs = (
        items.groupby(["legal_domain", "legal_ordinance"])
        .size()
        .sort_values(ascending=False)
    )
    return {
        "finding": "The legal domain of granted exemption items crosses planning-regulatory ordinance contexts rather than mapping one-to-one onto them.",
        "evidence": {
            "top_legal_domain_by_ordinance_pairs": to_plain_dict(top_pairs.head(8)),
            "legal_domain_x_ordinance_table": {
                str(index): to_plain_dict(row)
                for index, row in table.iterrows()
            },
        },
    }


def finding_zone_quality_caveat(records: pd.DataFrame) -> dict:
    noisy = records[
        records["zone_quality"].isin(["source_label", "legal_text", "unparsed_text"])
    ]
    by_domain = pd.crosstab(records["exemption_domain"], records["zone_quality"])
    return {
        "finding": "Zone-code context is useful but unevenly parsed, so zone-based exemption patterns should be interpreted as provisional until zone parsing is hardened.",
        "evidence": {
            "records_with_noisy_zone_context": int(len(noisy)),
            "total_records": int(len(records)),
            "zone_quality_by_exemption_domain": {
                str(index): to_plain_dict(row)
                for index, row in by_domain.iterrows()
            },
        },
    }


def build_findings(records: pd.DataFrame, items: pd.DataFrame) -> list[dict]:
    findings = [
        finding_development_plan_concentration(records),
        finding_rationale_signal_divergence(records),
        finding_legal_domain_context_crossing(items),
        finding_zone_quality_caveat(records),
    ]
    return findings


def save_metadata(
    output_dir: Path,
    records: pd.DataFrame,
    items: pd.DataFrame,
    generated_figures: list[Path],
    findings: list[dict],
) -> None:
    exemption_metadata = load_json_if_present(EXEMPTION_METADATA_FILE)
    decision_basis_metadata = load_json_if_present(DECISION_BASIS_METADATA_FILE)

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_files": {
            "granted_exemptions": str(EXEMPTION_FILE),
            "decision_basis": str(DECISION_BASIS_FILE),
        },
        "metadata_inputs": {
            "granted_exemptions": str(EXEMPTION_METADATA_FILE),
            "decision_basis": str(DECISION_BASIS_METADATA_FILE),
        },
        "source_metadata_hints": {
            "exemption_domain_counts": exemption_metadata.get("primary_type_counts", {}),
            "legal_domain_counts": exemption_metadata.get("legal_domain_counts", {}),
            "planning_context_primary_plan_counts": decision_basis_metadata.get(
                "planning_context_primary_plan_counts", {}
            ),
            "planning_context_ordinance_counts": decision_basis_metadata.get(
                "planning_context_ordinance_counts", {}
            ),
            "planning_context_zone_quality_counts": decision_basis_metadata.get(
                "planning_context_zone_quality_counts", {}
            ),
        },
        "output_dir": str(output_dir),
        "figures": [path.name for path in generated_figures],
        "record_count": int(len(records)),
        "item_count": int(len(items)),
        "exemption_domain_by_planning_context": {
            str(index): to_plain_dict(row)
            for index, row in pd.crosstab(
                records["exemption_domain"], records["plan_primary_type"]
            ).iterrows()
        },
        "exemption_domain_by_ordinance_context": {
            str(index): to_plain_dict(row)
            for index, row in pd.crosstab(
                records["exemption_domain"], records["legal_ordinance"]
            ).iterrows()
        },
        "legal_domain_by_ordinance_context": {
            str(index): to_plain_dict(row)
            for index, row in pd.crosstab(
                items["legal_domain"], items["legal_ordinance"]
            ).iterrows()
        },
        "rationale_signals_by_planning_context_percent": {
            str(index): to_plain_dict(row)
            for index, row in (
                records.groupby("plan_primary_type")[RATIONALE_COLUMNS]
                .mean()
                .mul(100)
                .round(2)
            ).iterrows()
        },
        "association_metrics": association_metrics(records, items),
        "findings": findings,
    }

    path = output_dir / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


def main() -> None:
    print("\nAnalyzing combined exemption and decision-basis patterns\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    exemptions = load_request_dict(EXEMPTION_FILE)
    decision_basis = load_request_dict(DECISION_BASIS_FILE)
    records = pd.DataFrame(build_record_rows(exemptions, decision_basis))
    items = pd.DataFrame(build_item_rows(exemptions, decision_basis))

    generated_figures = [
        OUTPUT_DIR / "exemption_domain_x_planning_context.png",
        OUTPUT_DIR / "exemption_domain_x_ordinance_context.png",
        OUTPUT_DIR / "legal_domain_x_ordinance_context.png",
        OUTPUT_DIR / "rationale_signals_by_planning_context.png",
        OUTPUT_DIR / "decision_pattern_complexity_by_planning_context.png",
        OUTPUT_DIR / "zone_quality_by_exemption_domain.png",
    ]

    plot_exemption_domain_x_plan(records, OUTPUT_DIR)
    plot_exemption_domain_x_ordinance(records, OUTPUT_DIR)
    plot_legal_domain_x_ordinance(items, OUTPUT_DIR)
    plot_rationale_signals_by_plan(records, OUTPUT_DIR)
    plot_complexity_by_plan(records, OUTPUT_DIR)
    plot_zone_quality_by_domain(records, OUTPUT_DIR)

    findings = build_findings(records, items)
    save_metadata(OUTPUT_DIR, records, items, generated_figures, findings)

    print(f"\nAnalyzed {len(records)} joined records and {len(items)} joined items.")
    print(f"Identified {len(findings)} mapped findings.")
    print(f"All combined figures saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
