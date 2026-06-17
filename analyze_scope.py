"""
Scope & descriptive statistics.

Reads BOTH cleaned datasets (the exemption cohort and the no-exemption
cohort) so the descriptive picture covers the full permit corpus, and
summarizes its temporal and geographic spread:
  - year distributions for the key dates (creation, issue, receipt),
    split by cohort
  - district distribution, split by cohort
  - cohort sizes (exemption vs. no-exemption)

Writes a metadata summary plus simple bar charts to res/figures/scope/.

Run:
    uv run python analyze_scope.py
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from settings import FILE_ANALYZE_JSON, FILE_NONE_EXEMPTION_JSON
from src.text_parser import enrich_and_merge_json

OUTPUT_DIR = Path("res/figures/scope")
UNKNOWN = "unknown"

# Each source file and the cohort label its records get tagged with.
SOURCES = [
    (FILE_ANALYZE_JSON, "exemption"),
    (FILE_NONE_EXEMPTION_JSON, "no_exemption"),
]
COHORT_ORDER = ["exemption", "no_exemption"]
COHORT_LABELS = {
    "exemption": "w exemption decisions",
    "no_exemption": "w/o exemption decisions",
}

# (record field, sub-key, human label) for each date we want a year for.
DATE_FIELDS = [
    ("permit_information", "issue_date", "Issue Date"),
]

# Categorical attributes parsed out of "statistics_for_hmbtg_implementation".
# (canonical sub-key, human label, chart kind: "barh" | "barv" | None=no figure)
HMBTG_FIELDS = [
    ("type_of_construction", "Type of construction", "barh"),
    ("type_of_requested_facility", "Type of requested facility (building class)", "barh"),
    ("type_of_building_by_future_use", "Type of building by future use", "barv"),
    ("number_of_full_stories", "Number of full stories", None),
]

# Some records carry these attributes under German keys; fold them in.
HMBTG_KEY_ALIASES = {
    "art_der_baumanahme": "type_of_construction",
    "art_der_beantragten_anlage": "type_of_requested_facility",
}

# Normalize the few German / mojibake values to their English equivalents so
# the categories collapse cleanly.
HMBTG_VALUE_TRANSLATIONS = {
    "Errichtung": "New Construction",
    "Beseitigung (Abbruch), Errichtung": "Demolition, New Construction",
    "Gebäude, Gebäudeklasse 1": "Building, Building Class 1",
    "Geb�ude, Geb�udeklasse 1": "Building, Building Class 1",
    "Not specified": UNKNOWN,
    # Shorten / merge the future-use categories.
    "Pure Residential Building": "Pure Residential",
    "Residential Building": "Residential",
    "Not purely residential building": "Residential",
    "Mixed-use Building": "Mixed-use",
}

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.0)


def extract_year(value) -> int | None:
    """Pull a 4-digit year (1900-2099) from a free-text date string."""
    if not isinstance(value, str):
        return None
    match = re.search(r"\b(19|20)\d{2}\b", value)
    return int(match.group(0)) if match else None


def normalize_district(value) -> str:
    """Fold the mojibake/umlaut variants so districts collapse cleanly."""
    if not isinstance(value, str) or not value.strip():
        return UNKNOWN
    text = value.strip()
    # The replacement char (�) stands in for a dropped umlaut, e.g. "�jendorf".
    text = text.replace("�", "Ö") if text.startswith("�") else text.replace("�", "")
    folds = {"Ojendorf": "Öjendorf"}
    return folds.get(text, text)


def normalize_hmbtg_value(value) -> str:
    """Map German/mojibake HmbTG values onto their canonical English form."""
    if not isinstance(value, str) or not value.strip():
        return UNKNOWN
    text = value.strip()
    return HMBTG_VALUE_TRANSLATIONS.get(text, text)


def hmbtg_attributes(block) -> dict:
    """Merge German-keyed attributes into their English canonical keys."""
    if not isinstance(block, dict):
        return {}
    merged = {}
    for key, value in block.items():
        canonical = HMBTG_KEY_ALIASES.get(key, key)
        if not merged.get(canonical):  # English value wins if both present
            merged[canonical] = value
    return merged


def build_rows() -> pd.DataFrame:
    rows = []
    for source_file, cohort in SOURCES:
        records = enrich_and_merge_json(source_file)
        print(f"  {cohort}: {len(records)} records from {source_file}")
        for record in records:
            row = {
                "request_id": record.get("request_id"),
                "cohort": cohort,
                "district": normalize_district(record.get("district")),
            }
            for field, sub_key, _ in DATE_FIELDS:
                block = record.get(field)
                raw = block.get(sub_key) if isinstance(block, dict) else None
                row[f"{sub_key}_year"] = extract_year(raw)

            stats = hmbtg_attributes(record.get("statistics_for_hmbtg_implementation"))
            for sub_key, _, _ in HMBTG_FIELDS:
                row[f"hmbtg_{sub_key}"] = normalize_hmbtg_value(stats.get(sub_key))
            rows.append(row)
    return pd.DataFrame(rows)


def _cohort_palette() -> dict[str, str]:
    return {
        "exemption": "#006400",     # dark green
        "no_exemption": "#B8860B",  # dark yellow (darkgoldenrod)
    }


def _draw_year_bar(ax, df: pd.DataFrame, sub_key: str) -> bool:
    """Draw the stacked permits-by-year chart onto a given axis."""
    sub = df[[f"{sub_key}_year", "cohort"]].dropna(subset=[f"{sub_key}_year"]).copy()
    if sub.empty:
        return False
    sub[f"{sub_key}_year"] = sub[f"{sub_key}_year"].astype(int)

    # Stacked counts per year x cohort over a continuous year range.
    pivot = sub.pivot_table(index=f"{sub_key}_year", columns="cohort",
                            aggfunc="size", fill_value=0)
    full_range = range(int(pivot.index.min()), int(pivot.index.max()) + 1)
    pivot = pivot.reindex(full_range, fill_value=0)
    for cohort in COHORT_ORDER:
        if cohort not in pivot.columns:
            pivot[cohort] = 0
    pivot = pivot[COHORT_ORDER]

    palette = _cohort_palette()
    bottom = pd.Series(0, index=pivot.index)
    for cohort in COHORT_ORDER:
        bars = ax.bar(pivot.index.astype(str), pivot[cohort], bottom=bottom,
                      label=COHORT_LABELS[cohort], color=palette[cohort])
        # Per-cohort count inside each stacked segment (zeros hidden).
        ax.bar_label(bars, labels=[int(v) if v else "" for v in pivot[cohort]],
                     label_type="center", color="white", fontsize=15, fontweight="bold")
        bottom += pivot[cohort]
    totals = pivot.sum(axis=1)
    ax.bar_label(ax.containers[-1], labels=[str(int(t)) for t in totals],
                 padding=3, fontsize=16)
    ax.margins(y=0.12)
    ax.set_xlabel("Permits by issue date (year)", fontsize=20)
    ax.set_ylabel("Count", fontsize=20)
    ax.tick_params(axis="both", labelsize=15)
    ax.legend(title="", fontsize=18)
    return True


def save_year_bar(df: pd.DataFrame, sub_key: str, label: str, path: Path) -> bool:
    fig, ax = plt.subplots(figsize=(16, 8))
    if not _draw_year_bar(ax, df, sub_key):
        plt.close(fig)
        print(f"Skipped empty figure: {path}")
        return False
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return True


def save_category_barh(df: pd.DataFrame, column: str, xlabel: str, path: Path,
                       seg_fontsize: int = 9) -> bool:
    """Horizontal stacked bar of a categorical column, split by cohort."""
    if df.empty or column not in df:
        print(f"Skipped empty figure: {path}")
        return False

    pivot = df.pivot_table(index=column, columns="cohort", aggfunc="size", fill_value=0)
    for cohort in COHORT_ORDER:
        if cohort not in pivot.columns:
            pivot[cohort] = 0
    pivot = pivot[COHORT_ORDER]
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=True).index]

    palette = _cohort_palette()
    fig, ax = plt.subplots(figsize=(10, max(3, len(pivot) * 0.55)))
    left = pd.Series(0, index=pivot.index)
    for cohort in COHORT_ORDER:
        bars = ax.barh(pivot.index.astype(str), pivot[cohort], left=left,
                       label=COHORT_LABELS[cohort], color=palette[cohort])
        ax.bar_label(bars, labels=[int(v) if v else "" for v in pivot[cohort]],
                     label_type="center", color="white",
                     fontsize=seg_fontsize, fontweight="bold")
        left += pivot[cohort]
    totals = pivot.sum(axis=1)
    ax.bar_label(ax.containers[-1], labels=[str(int(t)) for t in totals],
                 padding=3, fontsize=seg_fontsize + 1)
    ax.margins(x=0.10)
    ax.set_xlabel(xlabel, fontsize=14)
    ax.set_ylabel("")
    ax.tick_params(axis="both", labelsize=12)
    ax.legend(title="", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return True


def _draw_category_barv(ax, df: pd.DataFrame, column: str, xlabel: str,
                        seg_fontsize: int = 12, rotation: int = 0,
                        title_fontsize: int = 14,
                        legend_fontsize: int = 11,
                        xlabel_pad: float | None = None) -> bool:
    """Draw a vertical stacked categorical chart onto a given axis."""
    if df.empty or column not in df:
        return False

    pivot = df.pivot_table(index=column, columns="cohort", aggfunc="size", fill_value=0)
    for cohort in COHORT_ORDER:
        if cohort not in pivot.columns:
            pivot[cohort] = 0
    pivot = pivot[COHORT_ORDER]
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

    palette = _cohort_palette()
    bottom = pd.Series(0, index=pivot.index)
    for cohort in COHORT_ORDER:
        bars = ax.bar(pivot.index.astype(str), pivot[cohort], bottom=bottom,
                      label=COHORT_LABELS[cohort], color=palette[cohort])
        ax.bar_label(bars, labels=[int(v) if v else "" for v in pivot[cohort]],
                     label_type="center", color="white",
                     fontsize=seg_fontsize, fontweight="bold")
        bottom += pivot[cohort]
    totals = pivot.sum(axis=1)
    ax.bar_label(ax.containers[-1], labels=[str(int(t)) for t in totals],
                 padding=3, fontsize=seg_fontsize + 1)
    # Extra headroom so the tallest bar's total clears the legend.
    ax.set_ylim(0, totals.max() * 1.35)
    ax.set_xlabel(xlabel, fontsize=title_fontsize, labelpad=xlabel_pad)
    ax.set_ylabel("Count", fontsize=title_fontsize)
    ax.tick_params(axis="y", labelsize=12)
    ax.tick_params(axis="x", labelsize=13)
    ha = "right" if rotation not in (0, 90) else "center"
    plt.setp(ax.get_xticklabels(), rotation=rotation, ha=ha)
    ax.legend(title="", fontsize=legend_fontsize, loc="upper right")
    return True


def save_category_barv(df: pd.DataFrame, column: str, xlabel: str, path: Path,
                       figsize=(4, 8), seg_fontsize: int = 12,
                       rotation: int = 0, title_fontsize: int = 14,
                       legend_fontsize: int = 11,
                       xlabel_pad: float | None = None) -> bool:
    """Vertical stacked bar of a categorical column, split by cohort."""
    fig, ax = plt.subplots(figsize=figsize)
    if not _draw_category_barv(ax, df, column, xlabel, seg_fontsize, rotation,
                               title_fontsize, legend_fontsize, xlabel_pad):
        plt.close(fig)
        print(f"Skipped empty figure: {path}")
        return False
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return True


def save_year_and_category(df: pd.DataFrame, year_sub_key: str,
                           use_column: str, use_xlabel: str, path: Path) -> bool:
    """Combine the year chart (left, wide) and a categorical chart (right)."""
    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=(20, 8), gridspec_kw={"width_ratios": [75, 25]})
    ok_left = _draw_year_bar(ax_left, df, year_sub_key)
    ok_right = _draw_category_barv(ax_right, df, use_column, use_xlabel)
    if not (ok_left or ok_right):
        plt.close(fig)
        print(f"Skipped empty figure: {path}")
        return False

    # Unify axis titles across both panels.
    for ax in (ax_left, ax_right):
        ax.xaxis.label.set_size(18)
        ax.yaxis.label.set_size(18)

    # Put the right panel's y-axis (ticks + "Count" label) on its right side.
    ax_right.yaxis.set_label_position("right")
    ax_right.yaxis.tick_right()

    # Re-create both legends from scratch with identical size and spacing
    # (only the corner differs), so they match exactly.
    legend_kw = dict(fontsize=14, labelspacing=0.4, handlelength=1.8,
                     handletextpad=0.6, borderpad=0.5, borderaxespad=0.5)
    ax_left.legend(title="", loc="upper left", **legend_kw)
    ax_right.legend(title="", loc="upper right", **legend_kw)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return True


def save_year_use_and_district(df: pd.DataFrame, year_sub_key: str,
                               use_column: str, use_xlabel: str,
                               district_column: str, district_xlabel: str,
                               path: Path) -> bool:
    """Stack two rows into one figure: the issue-year (left) + future-use
    (right) combo on the upper half, the district distribution on the lower."""
    # Upper row matches the (20, 8) year+use combo; lower row is a (16, 6)-style
    # district strip, so height_ratios mirror those 8 : 6 panel heights.
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(2, 2, height_ratios=[8, 6], width_ratios=[75, 25])
    ax_year = fig.add_subplot(gs[0, 0])
    ax_use = fig.add_subplot(gs[0, 1])
    ax_dist = fig.add_subplot(gs[1, :])

    ok_year = _draw_year_bar(ax_year, df, year_sub_key)
    ok_use = _draw_category_barv(ax_use, df, use_column, use_xlabel)
    ok_dist = _draw_category_barv(ax_dist, df, district_column, district_xlabel,
                                  seg_fontsize=12, rotation=45,
                                  title_fontsize=18, legend_fontsize=14,
                                  xlabel_pad=0)
    if not (ok_year or ok_use or ok_dist):
        plt.close(fig)
        print(f"Skipped empty figure: {path}")
        return False

    # Unify axis-title sizes across the upper-row panels.
    for ax in (ax_year, ax_use):
        ax.xaxis.label.set_size(18)
        ax.yaxis.label.set_size(18)

    # Put the use panel's y-axis (ticks + "Count" label) on its right side.
    ax_use.yaxis.set_label_position("right")
    ax_use.yaxis.tick_right()

    # Re-create the upper-row legends from scratch with identical size/spacing
    # (only the corner differs), so they match exactly.
    legend_kw = dict(fontsize=14, labelspacing=0.4, handlelength=1.8,
                     handletextpad=0.6, borderpad=0.5, borderaxespad=0.5)
    ax_year.legend(title="", loc="upper left", **legend_kw)
    ax_use.legend(title="", loc="upper right", **legend_kw)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return True


def save_cohort_bar(df: pd.DataFrame, path: Path) -> bool:
    counts = df["cohort"].value_counts().reindex(COHORT_ORDER, fill_value=0)
    if counts.sum() == 0:
        print(f"Skipped empty figure: {path}")
        return False

    palette = _cohort_palette()
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar([COHORT_LABELS[c] for c in counts.index], counts.values,
                  color=[palette[c] for c in counts.index])
    ax.bar_label(bars, padding=3)
    ax.margins(y=0.15)
    ax.set_title("Records by cohort", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Records")
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return True


def save_metadata(df: pd.DataFrame, generated_figures: list[str]) -> None:
    def cohort_counts(series: pd.Series) -> dict:
        return {c: int((df["cohort"] == c).loc[series.index].sum())
                for c in COHORT_ORDER} if not series.empty else {}

    year_summary = {}
    for _, sub_key, label in DATE_FIELDS:
        col = f"{sub_key}_year"
        valid = df[df[col].notna()]
        years = valid[col].astype(int)
        year_summary[sub_key] = {
            "label": label,
            "coverage": int(years.shape[0]),
            "missing": int(df.shape[0] - years.shape[0]),
            "min": int(years.min()) if not years.empty else None,
            "max": int(years.max()) if not years.empty else None,
            "counts": {str(y): int(c) for y, c in sorted(years.value_counts().items())},
            "counts_by_cohort": {
                cohort: {str(y): int(c) for y, c in
                         sorted(valid[valid["cohort"] == cohort][col].astype(int)
                                .value_counts().items())}
                for cohort in COHORT_ORDER
            },
        }

    district_total = df["district"].value_counts()
    district_by_cohort = (
        df.pivot_table(index="district", columns="cohort", aggfunc="size", fill_value=0)
        .reindex(columns=COHORT_ORDER, fill_value=0)
    )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_files": [str(f) for f, _ in SOURCES],
        "output_dir": str(OUTPUT_DIR),
        "record_count": int(df.shape[0]),
        "cohort_counts": {c: int((df["cohort"] == c).sum()) for c in COHORT_ORDER},
        "figures": generated_figures,
        "years": year_summary,
        "districts": {
            "unique": int(district_total.shape[0]),
            "missing": int((df["district"] == UNKNOWN).sum()),
            "counts": {str(k): int(v) for k, v in district_total.items()},
            "counts_by_cohort": {
                str(district): {c: int(row[c]) for c in COHORT_ORDER}
                for district, row in district_by_cohort.iterrows()
            },
        },
        "hmbtg_statistics": {
            sub_key: {
                "label": label,
                "missing": int((df[f"hmbtg_{sub_key}"] == UNKNOWN).sum()),
                "counts": {
                    str(k): int(v)
                    for k, v in df[f"hmbtg_{sub_key}"].value_counts().items()
                },
                "counts_by_cohort": {
                    str(value): {c: int(row[c]) for c in COHORT_ORDER}
                    for value, row in (
                        df.pivot_table(index=f"hmbtg_{sub_key}", columns="cohort",
                                       aggfunc="size", fill_value=0)
                        .reindex(columns=COHORT_ORDER, fill_value=0).iterrows()
                    )
                },
            }
            for sub_key, label, _ in HMBTG_FIELDS
        },
    }

    path = OUTPUT_DIR / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


def main() -> None:
    print("\nScope analysis (full corpus: exemption + no-exemption)\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = build_rows()

    prefix = "input_stats_"
    generated = []
    if save_cohort_bar(df, OUTPUT_DIR / f"{prefix}cohort_distribution.png"):
        generated.append(f"{prefix}cohort_distribution.png")
    for _, sub_key, label in DATE_FIELDS:
        path = OUTPUT_DIR / f"{prefix}year_{sub_key}.png"
        if save_year_bar(df, sub_key, label, path):
            generated.append(path.name)
    if save_category_barv(df, "district", "District",
                          OUTPUT_DIR / f"{prefix}district_distribution.png",
                          figsize=(16, 6), seg_fontsize=12, rotation=45,
                          title_fontsize=18, legend_fontsize=14, xlabel_pad=0):
        generated.append(f"{prefix}district_distribution.png")
    for sub_key, label, kind in HMBTG_FIELDS:
        if kind is None:
            continue
        path = OUTPUT_DIR / f"{prefix}hmbtg_{sub_key}.png"
        column = f"hmbtg_{sub_key}"
        if kind == "barv":
            ok = save_category_barv(df, column, label, path)
        else:
            ok = save_category_barh(df, column, label, path, seg_fontsize=12)
        if ok:
            generated.append(path.name)

    # Combined: issue-year (left) + future-use (right) in a single figure.
    combined_path = OUTPUT_DIR / f"{prefix}both_year_buildinguse.png"
    if save_year_and_category(df, "issue_date",
                              "hmbtg_type_of_building_by_future_use",
                              "Type of building by future use", combined_path):
        generated.append(combined_path.name)

    # Stacked: year + future-use combo (upper half) over the district
    # distribution (lower half) in a single figure.
    stacked_path = OUTPUT_DIR / f"{prefix}year_buildinguse_district.png"
    if save_year_use_and_district(df, "issue_date",
                                  "hmbtg_type_of_building_by_future_use",
                                  "Type of building by future use",
                                  "district", "District", stacked_path):
        generated.append(stacked_path.name)

    save_metadata(df, generated)

    cohort = df["cohort"].value_counts().reindex(COHORT_ORDER, fill_value=0)
    iyears = df["issue_date_year"].dropna()
    print(f"\n{df.shape[0]} records "
          f"(exemption={cohort['exemption']}, no_exemption={cohort['no_exemption']}) | "
          f"{df['district'].nunique()} districts | "
          f"issue years {iyears.min():.0f}-{iyears.max():.0f}")


if __name__ == "__main__":
    main()
