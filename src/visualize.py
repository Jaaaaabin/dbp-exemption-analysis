# src/visualize.py
# High-level visualizations for building permit exemption analysis.
# All functions accept enriched records (list[dict] from text_parser.enrich_json).
#
# Record-level plots (one data point per permit):
#   plot_exemption_overview                  – count of permits per exemption type
#   plot_ordinance_x_exemption               – heatmap: legal ordinance × exemption type (count)
#   plot_exemption_composition_by_authority  – stacked bar: exemption mix per authority
#   plot_legal_ref_frequency                 – top-N cited § references, colored by exemption type
#   plot_zone_code_x_exemption               – bubble: zone prefix × exemption type (count)
#   plot_all                                 – save all record-level plots to output_dir
#
# Item-level plots (one data point per exemption item, from flatten_to_items):
#   plot_item_type_distribution  – bar: count of items per exemption type
#   plot_item_authority_x_type   – heatmap: authority × exemption type, raw + row-normalised
#   plot_item_legal_ref_bar      – bar: item count per legal reference
#   plot_exemption_treemap       – treemap: exemption type → legal ref (area = count)
#   plot_keyword_frequency       – faceted bar: top-N words per exemption type for a text column
#   plot_all_items               – save all item-level plots to output_dir

import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
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


# ── Shared helpers ────────────────────────────────────────────────────────────

# Consistent color per exemption taxonomy label across all plots.
_EXEMPTION_PALETTE: dict[str, str] = {
    'planning_law':       '#1f77b4',
    'tree_environmental': '#2ca02c',
    'building_code':      '#d62728',
    'access_road':        '#9467bd',
    'access_restriction': '#8c564b',
    'nature_protection':  '#e377c2',
    'mixed':              '#ff7f0e',
    'none':               '#aec7e8',
    'other':              '#7f7f7f',
}


def _zone_prefix(code) -> str | None:
    """Extract base zone type (e.g. 'WR', 'WA', 'W') from a raw zone_code string."""
    if not isinstance(code, str):
        return None
    m = re.match(r'([A-Z]{1,4})', code.strip())
    return m.group(1) if m else None


# ── Plots ─────────────────────────────────────────────────────────────────────

def plot_exemption_overview(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Horizontal bar: count of permits per exemption type."""
    df = _to_df(source)
    counts = df["exemption_primary_type"].value_counts().sort_values()
    colors = [_EXEMPTION_PALETTE.get(t, '#7f7f7f') for t in counts.index]

    fig, ax = plt.subplots(figsize=(8, max(3, len(counts) * 0.5)))
    fig.suptitle("Exemption Type Overview", fontweight="bold")
    bars = ax.barh(counts.index, counts.values, color=colors)
    ax.set_xlabel("Number of permits")
    ax.bar_label(bars, padding=3)
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_ordinance_x_exemption(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Heatmap: count of permits per legal ordinance × exemption type."""
    df = _to_df(source)
    sub = df[['legal_ordinance', 'exemption_primary_type']].dropna()
    if sub.empty:
        return plt.figure()

    count_piv = pd.crosstab(sub['legal_ordinance'], sub['exemption_primary_type'])

    fig, ax = plt.subplots(figsize=(max(8, len(count_piv.columns) * 1.2), max(3, len(count_piv) * 0.9)))
    sns.heatmap(count_piv, annot=True, fmt='d', cmap='Blues', linewidths=0.5,
                ax=ax, cbar_kws={'shrink': 0.8})
    ax.set_title('Legal ordinance × exemption type (count of permits)', fontweight='bold')
    ax.set_xlabel('Exemption type')
    ax.set_ylabel('Legal ordinance')
    ax.tick_params(axis='x', rotation=30)
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_exemption_composition_by_authority(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Stacked horizontal bar: proportion of each exemption type per issuing authority."""
    df = _to_df(source)
    sub = df[['issuing_authority', 'exemption_primary_type']].dropna()
    if sub.empty:
        return plt.figure()

    ct_norm  = pd.crosstab(sub['issuing_authority'], sub['exemption_primary_type'], normalize='index')
    ct_count = pd.crosstab(sub['issuing_authority'], sub['exemption_primary_type'])
    totals   = ct_count.sum(axis=1)

    fig, ax = plt.subplots(figsize=(11, max(4, len(ct_norm) * 0.7)))
    colors = [_EXEMPTION_PALETTE.get(c, '#7f7f7f') for c in ct_norm.columns]
    ct_norm.plot(kind='barh', stacked=True, ax=ax, color=colors, edgecolor='white', linewidth=0.5)

    for i, (_, total) in enumerate(totals.items()):
        ax.text(1.01, i, f'n={total}', va='center', fontsize=9,
                transform=ax.get_yaxis_transform())

    ax.set_xlabel('Proportion of permits')
    ax.set_title('Exemption type composition per issuing authority')
    ax.legend(title='Exemption type', bbox_to_anchor=(1.12, 1), loc='upper left')
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_legal_ref_frequency(
    source: JsonSource,
    top_n: int = 15,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Horizontal bar: top-N most cited § references, bar color = dominant exemption type."""
    df = _to_df(source)
    if 'exemption_legal_refs' not in df.columns:
        return plt.figure()

    ref_df = (
        df[['exemption_legal_refs', 'exemption_primary_type']]
        .explode('exemption_legal_refs')
        .dropna(subset=['exemption_legal_refs'])
        .rename(columns={'exemption_legal_refs': 'ref'})
    )
    if ref_df.empty:
        return plt.figure()

    top_refs = ref_df['ref'].value_counts().head(top_n)
    dominant = (
        ref_df.groupby('ref')['exemption_primary_type']
        .agg(lambda s: s.value_counts().index[0])
    )

    refs_ordered = top_refs.index.tolist()
    colors = [_EXEMPTION_PALETTE.get(dominant.get(r, 'other'), '#7f7f7f') for r in refs_ordered]

    fig, ax = plt.subplots(figsize=(9, max(4, top_n * 0.45)))
    bars = ax.barh(refs_ordered[::-1], top_refs.values[::-1], color=colors[::-1])
    ax.bar_label(bars, padding=3)
    ax.set_xlabel('Occurrences across all records')
    ax.set_title(f'Top {top_n} most cited legal references\n(bar color = dominant exemption type)')

    used_types = list(dict.fromkeys(dominant.get(r, 'other') for r in refs_ordered))
    legend_handles = [
        Patch(color=_EXEMPTION_PALETTE.get(t, '#7f7f7f'), label=t) for t in used_types
    ]
    ax.legend(handles=legend_handles, title='Dominant exemption type',
              bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_zone_code_x_exemption(
    source: JsonSource,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Bubble chart: zone code prefix × exemption type. Bubble size = count; label = count."""
    df = _to_df(source).copy()
    df['zone_prefix'] = df['zone_code'].apply(_zone_prefix)

    sub = df[['zone_prefix', 'exemption_primary_type']].dropna()
    if sub.empty:
        return plt.figure()

    count_piv = pd.crosstab(sub['zone_prefix'], sub['exemption_primary_type'])
    zones = count_piv.index.tolist()
    types = count_piv.columns.tolist()

    fig, ax = plt.subplots(figsize=(max(7, len(types) * 1.4), max(4, len(zones) * 0.8)))

    for j, etype in enumerate(types):
        for i, zone in enumerate(zones):
            count = count_piv.loc[zone, etype]
            if count == 0:
                continue
            ax.scatter(j, i, s=max(count * 80, 40),
                       color=_EXEMPTION_PALETTE.get(etype, '#7f7f7f'), alpha=0.75)
            ax.text(j, i, str(count), ha='center', va='center', fontsize=7.5,
                    color='white', fontweight='bold')

    ax.set_xticks(range(len(types)))
    ax.set_xticklabels(types, rotation=30, ha='right')
    ax.set_yticks(range(len(zones)))
    ax.set_yticklabels(zones)
    ax.set_xlabel('Exemption type')
    ax.set_ylabel('Zone code prefix')
    ax.set_title('Zone code × exemption type (bubble size = count)')
    ax.set_xlim(-0.5, len(types) - 0.5)
    ax.set_ylim(-0.5, len(zones) - 0.5)
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


# ── Convenience: generate all standard plots ──────────────────────────────────

def plot_all(
    source: JsonSource,
    output_dir: str | Path = "res/figures",
) -> None:
    """Generate and save all standard plots to output_dir."""
    out = Path(output_dir)
    records = _to_df(source).to_dict("records")  # normalise to list[dict] once

    plot_exemption_overview(records,
        output_path=out / "exemption_overview.png")

    plot_ordinance_x_exemption(records,
        output_path=out / "ordinance_x_exemption.png")

    plot_exemption_composition_by_authority(records,
        output_path=out / "exemption_composition_by_authority.png")

    plot_legal_ref_frequency(records,
        output_path=out / "legal_ref_frequency.png")

    plot_zone_code_x_exemption(records,
        output_path=out / "zone_code_x_exemption.png")

    plt.close("all")
    print(f"\nAll plots saved to {out}/")


# ── Item-level helpers ────────────────────────────────────────────────────────

_STOPWORDS: frozenset[str] = frozenset({
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
    'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
    'not', 'no', 'nor', 'so', 'yet', 'both', 'either', 'neither', 'each',
    'few', 'more', 'most', 'other', 'some', 'such', 'than', 'too', 'very',
    'just', 'into', 'during', 'before', 'after', 'above', 'below', 'this',
    'that', 'these', 'those', 'it', 'its', 'they', 'their', 'them', 'which',
    'who', 'whom', 'what', 'where', 'when', 'how', 'all', 'any', 'per',
    'also', 'between', 'out', 'up', 'if', 'only', 'then', 'about', 'one',
})


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alpha characters, drop short tokens and stopwords."""
    return [
        w for w in re.split(r'[^a-zA-Z]+', text.lower())
        if len(w) >= 3 and w not in _STOPWORDS
    ]


# ── Item-level plots ──────────────────────────────────────────────────────────

def plot_item_type_distribution(
    items: list[dict],
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Horizontal bar: count of exemption items per exemption type."""
    df = pd.DataFrame(items)
    counts = df['exemption_primary_type'].value_counts().sort_values()
    colors = [_EXEMPTION_PALETTE.get(t, '#7f7f7f') for t in counts.index]

    fig, ax = plt.subplots(figsize=(8, max(3, len(counts) * 0.5)))
    bars = ax.barh(counts.index, counts.values, color=colors)
    ax.bar_label(bars, padding=3)
    ax.set_xlabel('Number of exemption items')
    ax.set_title('Exemption item count by type', fontweight='bold')
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_item_authority_x_type(
    items: list[dict],
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Two-panel heatmap: authority × exemption type — raw item count (left) and row-normalised % (right)."""
    df = pd.DataFrame(items)
    sub = df[['issuing_authority', 'exemption_primary_type']].dropna()
    if sub.empty:
        return plt.figure()

    ct_raw  = pd.crosstab(sub['issuing_authority'], sub['exemption_primary_type'])
    ct_norm = pd.crosstab(sub['issuing_authority'], sub['exemption_primary_type'],
                          normalize='index').mul(100).round(1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, max(3, len(ct_raw) * 0.8)))
    fig.suptitle('Issuing authority × exemption type (items)', fontweight='bold')

    sns.heatmap(ct_raw, annot=True, fmt='d', cmap='Blues', linewidths=0.5,
                ax=ax1, cbar_kws={'shrink': 0.8})
    ax1.set_title('Raw count')
    ax1.set_xlabel('Exemption type')
    ax1.set_ylabel('Issuing authority')
    ax1.tick_params(axis='x', rotation=30)

    sns.heatmap(ct_norm, annot=True, fmt='.1f', cmap='Blues', linewidths=0.5,
                ax=ax2, cbar_kws={'shrink': 0.8, 'label': '%'})
    ax2.set_title('Row-normalised (%)')
    ax2.set_xlabel('Exemption type')
    ax2.set_ylabel('')
    ax2.tick_params(axis='x', rotation=30)

    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_item_legal_ref_bar(
    items: list[dict],
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Horizontal bar: item count per legal reference, colored by dominant exemption type."""
    df = pd.DataFrame(items)
    sub = df[['legal_ref', 'exemption_primary_type']].dropna(subset=['legal_ref'])
    if sub.empty:
        return plt.figure()

    counts   = sub['legal_ref'].value_counts().sort_values()
    dominant = sub.groupby('legal_ref')['exemption_primary_type'].agg(
        lambda s: s.value_counts().index[0]
    )
    colors = [_EXEMPTION_PALETTE.get(dominant.get(r, 'other'), '#7f7f7f') for r in counts.index]

    fig, ax = plt.subplots(figsize=(9, max(4, len(counts) * 0.5)))
    bars = ax.barh(counts.index, counts.values, color=colors)
    ax.bar_label(bars, padding=3)
    ax.set_xlabel('Number of exemption items')
    ax.set_title('Legal reference frequency (per item)\n(bar color = dominant exemption type)',
                 fontweight='bold')

    used = list(dict.fromkeys(dominant.get(r, 'other') for r in counts.index))
    ax.legend(
        handles=[Patch(color=_EXEMPTION_PALETTE.get(t, '#7f7f7f'), label=t) for t in used],
        title='Dominant type', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8,
    )
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_exemption_treemap(
    items: list[dict],
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Treemap: exemption type → legal reference. Rectangle area = item count.
    Requires squarify (uv add squarify).
    """
    try:
        import squarify
    except ImportError:
        print("squarify not installed; skipping treemap. Run: uv add squarify")
        return plt.figure()

    df = pd.DataFrame(items).copy()
    df['exemption_primary_type'] = df['exemption_primary_type'].fillna('other')
    df['legal_ref']              = df['legal_ref'].fillna('(no ref)')

    counts = (
        df.groupby(['exemption_primary_type', 'legal_ref'])
        .size()
        .reset_index(name='count')
        .sort_values(['exemption_primary_type', 'count'], ascending=[True, False])
    )

    sizes  = counts['count'].tolist()
    labels = (counts['legal_ref'] + '\n(n=' + counts['count'].astype(str) + ')').tolist()
    colors = counts['exemption_primary_type'].map(
        lambda t: _EXEMPTION_PALETTE.get(t, '#7f7f7f')
    ).tolist()

    fig, ax = plt.subplots(figsize=(14, 8))
    squarify.plot(sizes=sizes, label=labels, color=colors, alpha=0.85, ax=ax,
                  text_kwargs={'fontsize': 8, 'color': 'white', 'fontweight': 'bold'})
    ax.axis('off')
    ax.set_title('Exemption items: type → legal reference  (area = count)',
                 fontweight='bold', pad=12)

    used = counts['exemption_primary_type'].unique().tolist()
    ax.legend(
        handles=[Patch(color=_EXEMPTION_PALETTE.get(t, '#7f7f7f'), label=t) for t in used],
        title='Exemption type', loc='lower right', fontsize=9,
    )
    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


def plot_keyword_frequency(
    items: list[dict],
    text_col: str = 'combined_text',
    top_n: int = 20,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Faceted bar chart: top-N keywords per exemption type for a given text column.

    One subplot per exemption type. Useful for subjects_text, allowed_actions_text,
    conditions_text, justification_text, or combined_text.
    """
    df = pd.DataFrame(items)
    if text_col not in df.columns:
        return plt.figure()

    types = sorted(t for t in df['exemption_primary_type'].dropna().unique()
                   if isinstance(t, str))
    if not types:
        return plt.figure()

    n_cols   = min(len(types), 3)
    n_rows   = math.ceil(len(types) / n_cols)
    fig, axes_2d = plt.subplots(
        n_rows, n_cols,
        figsize=(6 * n_cols, 7 * n_rows),
        sharey=False, squeeze=False,
    )
    axes_flat = [ax for row in axes_2d for ax in row]
    for ax in axes_flat[len(types):]:   # hide unused cells in last row
        ax.set_visible(False)

    fig.suptitle(
        f'Top {top_n} keywords · {text_col.replace("_", " ")}',
        fontweight='bold',
    )

    for ax, etype in zip(axes_flat, types):
        mask  = df['exemption_primary_type'] == etype
        texts = df.loc[mask, text_col].fillna('').tolist()
        words = [w for t in texts for w in _tokenize(t)]

        if not words:
            ax.set_title(etype, fontweight='bold')
            ax.axis('off')
            continue

        freq = pd.Series(words).value_counts().head(top_n)
        color = _EXEMPTION_PALETTE.get(etype, '#7f7f7f')
        bars = ax.barh(freq.index[::-1], freq.values[::-1], color=color, alpha=0.85)
        ax.bar_label(bars, padding=2, fontsize=7)
        ax.set_title(etype, color=color, fontweight='bold')
        ax.set_xlabel('Count')
        ax.tick_params(axis='y', labelsize=8)

    fig.tight_layout()
    return _save(fig, Path(output_path) if output_path else None)


# ── Convenience: generate all item-level plots ────────────────────────────────

def plot_all_items(
    items: list[dict],
    output_dir: str | Path = "res/figures/items",
) -> None:
    """Generate and save all item-level plots to output_dir."""
    out = Path(output_dir)

    plot_item_type_distribution(items,
        output_path=out / "item_type_distribution.png")

    plot_item_authority_x_type(items,
        output_path=out / "item_authority_x_type.png")

    plot_item_legal_ref_bar(items,
        output_path=out / "item_legal_ref_bar.png")

    plot_exemption_treemap(items,
        output_path=out / "exemption_treemap.png")

    for col in ('combined_text', 'subjects_text', 'allowed_actions_text',
                'conditions_text', 'justification_text'):
        plot_keyword_frequency(items, text_col=col, top_n=20,
            output_path=out / f"keywords_{col}.png")

    plt.close("all")
    print(f"\nAll item-level plots saved to {out}/")
