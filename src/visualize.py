# src/visualize.py
# High-level visualizations for building permit exemption analysis.
# All functions accept enriched records (list[dict] from text_parser.enrich_json).
#
#   plot_exemption_overview        – count + mean decision time by exemption type
#   plot_decision_time_by_group    – horizontal bar: mean decision time for any column
#   plot_decision_time_distribution – histogram with median line
#   plot_correlation_heatmap       – heatmap of numeric column correlations
#   plot_subset_comparison         – bar: mean decision time across JSON subsets
#   plot_all                       – save all standard plots to output_dir

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

# Consistent style across all plots
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.05)
_FIG_DPI = 300

JsonSource = str | Path | list[dict]


def _to_df(source: JsonSource) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    return pd.DataFrame(source)


def _save(fig: plt.Figure, path: Path | None) -> plt.Figure:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=_FIG_DPI, bbox_inches="tight")
        print(f"Saved: {path}")
    return fig


# ── Individual plots ──────────────────────────────────────────────────────────

def plot_exemption_overview(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Two-panel: exemption type count (left) and mean decision time (right)."""
    df = _to_df(source)

    counts = df["exemption_primary_type"].value_counts().sort_values()
    mean_time = (
        df.groupby("exemption_primary_type")["time_for_decision_months"]
        .mean()
        .reindex(counts.index)
    )

    fig, (ax_count, ax_time) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Exemption Type Overview", fontweight="bold")

    # Left: counts
    bars = ax_count.barh(counts.index, counts.values, color=sns.color_palette("muted"))
    ax_count.set_xlabel("Number of permits")
    ax_count.set_title("Count per exemption type")
    ax_count.bar_label(bars, padding=3)

    # Right: mean decision time
    colors = ["#d9534f" if v > 5 else "#5cb85c" for v in mean_time.values]
    bars2 = ax_time.barh(mean_time.index, mean_time.values, color=colors)
    ax_time.set_xlabel("Mean decision time (months)")
    ax_time.set_title("Mean decision time per exemption type")
    ax_time.bar_label(bars2, fmt="%.1f", padding=3)
    ax_time.axvline(df["time_for_decision_months"].mean(), color="gray",
                    linestyle="--", linewidth=1, label="overall mean")
    ax_time.legend(fontsize=9)

    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_decision_time_by_group(
    source: JsonSource,
    group_col: str = "issuing_authority",
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Horizontal bar: mean decision time grouped by any categorical column."""
    df = _to_df(source)

    stats = (
        df.groupby(group_col)["time_for_decision_months"]
        .agg(mean="mean", count="count")
        .sort_values("mean")
    )

    fig, ax = plt.subplots(figsize=(9, max(3, len(stats) * 0.6)))
    bars = ax.barh(
        stats.index,
        stats["mean"],
        color=sns.color_palette("muted", len(stats)),
    )
    # Annotate with count
    for bar, (_, row) in zip(bars, stats.iterrows()):
        ax.text(
            bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
            f"n={int(row['count'])}  {row['mean']:.1f}m",
            va="center", fontsize=9,
        )
    ax.axvline(df["time_for_decision_months"].mean(), color="gray",
               linestyle="--", linewidth=1, label="overall mean")
    ax.set_xlabel("Mean decision time (months)")
    ax.set_title(f"Mean decision time by {group_col.replace('_', ' ')}")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_decision_time_distribution(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Histogram of time_for_decision_months with median and outlier lines."""
    df = _to_df(source)
    times = df["time_for_decision_months"].dropna()

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(times, bins=15, color=sns.color_palette("muted")[0], edgecolor="white")

    median = times.median()
    mean   = times.mean()
    ax.axvline(median, color="#d9534f", linestyle="--", linewidth=1.5, label=f"median {median:.1f}m")
    ax.axvline(mean,   color="#f0ad4e", linestyle=":",  linewidth=1.5, label=f"mean {mean:.1f}m")

    ax.set_xlabel("Decision time (months)")
    ax.set_ylabel("Number of permits")
    ax.set_title("Distribution of decision time")
    ax.legend()
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_correlation_heatmap(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Heatmap of Pearson correlations among numeric columns."""
    df = _to_df(source)

    # Drop columns that are all-zero or near-constant (uninformative)
    numeric = df.select_dtypes(include="number").dropna(axis=1, how="all")
    numeric = numeric.loc[:, numeric.std() > 0]

    corr = numeric.corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    mask = corr.isna()
    sns.heatmap(
        corr, mask=mask, annot=True, fmt=".2f", center=0,
        cmap="RdBu_r", linewidths=0.5, square=True,
        cbar_kws={"shrink": 0.75}, ax=ax,
    )
    ax.set_title("Correlation heatmap (numeric columns)", fontweight="bold")
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_subset_comparison(
    subsets: dict[str, JsonSource],
    metric_column: str = "time_for_decision_months",
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Bar chart comparing mean metric across multiple named JSON sources."""
    rows = []
    for name, source in subsets.items():
        df = _to_df(source)
        if metric_column in df.columns:
            rows.append({"subset": name, "mean": df[metric_column].mean(),
                         "count": df[metric_column].count()})
    stats = pd.DataFrame(rows).sort_values("mean", ascending=False)

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(
        stats["subset"], stats["mean"],
        color=sns.color_palette("muted", len(stats)), edgecolor="white",
    )
    for bar, (_, row) in zip(bars, stats.iterrows()):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
            f"{row['mean']:.2f}m\n(n={int(row['count'])})",
            ha="center", va="bottom", fontsize=9,
        )
    ax.set_ylabel(f"Mean {metric_column.replace('_', ' ')}")
    ax.set_title(f"Mean {metric_column.replace('_', ' ')} across subsets")
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


# ── Convenience: generate all standard plots ──────────────────────────────────

def plot_all(
    source: JsonSource,
    output_dir: str | Path = "res/figures",
    subsets: dict[str, JsonSource] | None = None,
) -> None:
    """Generate and save all standard plots to output_dir.

    subsets: mapping of label → JsonSource passed to plot_subset_comparison.
             If None, the subset comparison plot is skipped.
    """
    out = Path(output_dir)
    records = _to_df(source).to_dict("records")  # normalise to list[dict] once

    plot_exemption_overview(records,
        output_path=out / "exemption_overview.png")

    plot_decision_time_by_group(records, group_col="issuing_authority",
        output_path=out / "decision_time_by_authority.png")

    plot_decision_time_by_group(records, group_col="exemption_primary_type",
        output_path=out / "decision_time_by_exemption_type.png")

    plot_decision_time_by_group(records, group_col="plan_type",
        output_path=out / "decision_time_by_plan_type.png")

    plot_decision_time_by_group(records, group_col="plan_primary_type",
        output_path=out / "decision_time_by_plan_primary_type.png")

    plot_decision_time_distribution(records,
        output_path=out / "decision_time_distribution.png")

    plot_correlation_heatmap(records,
        output_path=out / "correlation_heatmap.png")

    if subsets:
        plot_subset_comparison(subsets, output_path=out / "subset_comparison.png")

    plt.close("all")
    print(f"\nAll plots saved to {out}/")
