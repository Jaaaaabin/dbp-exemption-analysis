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
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns

from settings import FILE_NONE_EXEMPTION_JSON, JSON_ANALYZE_READY_FILE as JSON_FILE
from src.visualize import _EXEMPTION_PALETTE, _tokenize, plot_keyword_frequency


INPUT_FILE = JSON_FILE.parent / (JSON_FILE.stem + "_parsed_granted_exemptions.json")
# Permits that granted no exemption at all (0 deviations each). Counted into the
# "deviations per application" distribution so it covers the full corpus.
NONE_EXEMPTION_FILE = FILE_NONE_EXEMPTION_JSON
OUTPUT_DIR = Path("res/figures/patterns")
# Exploratory figures live in a subdir so the stable, production figures above
# are never disturbed while iterating on the analysis.
EXPLORE_DIR = OUTPUT_DIR / "explore"

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


def count_zero_exemption_apps(path: Path) -> int:
    """Number of permits that granted no exemption (0 deviations each).

    The none-exemption cohort (rows missing 'Granted Exemptions') has no parsed
    sidecar, so we just count the cleaned records. Returns 0 if the file is absent.
    """
    if not path.exists():
        print(f"None-exemption file not found, treating as 0 apps: {path}")
        return 0
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return len(data) if isinstance(data, (list, dict)) else 0


def load_official_exemption_counts(path: Path) -> dict[str, int]:
    """Map request_id -> the raw `number_of_exemptions` column from a cohort file.

    This is the source's own per-permit deviation count, used as the authoritative
    basis for the 'deviations per application' figure (the parsed numbered-items
    count under-counts when one item bundles several deviations).
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    recs = data if isinstance(data, list) else list(data.values())
    return {
        str(r.get("request_id")): r["number_of_exemptions"]
        for r in recs
        if isinstance(r, dict) and r.get("number_of_exemptions") is not None
    }


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
                # Untapped rationale signal: why the exemption was granted.
                "justification": item.get("justification") or "",
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


# ════════════════════════════════════════════════════════════════════════════
# EXPLORATORY PATTERN ANALYSIS
#
# Quick-and-dirty diagnostics grounded in textbook pattern-recognition / data-
# mining techniques. The aim is *discovery*, not publication: surface candidate
# structure so the taxonomy rules can be iterated. Each block names the classic
# method and its calculation logic in the docstring. Output → res/figures/patterns/explore/.
# ════════════════════════════════════════════════════════════════════════════


def _tfidf_by_group(texts_by_group: dict[str, list[str]]) -> pd.DataFrame:
    """TF-IDF term weighting (Salton & McGill, vector space model).

    Each group's concatenated text is treated as one "document". For a term t
    in group g, over G groups:

        tf(t, g)  = count(t in g) / total_terms(g)     # term frequency
        df(t)     = number of groups containing t       # document frequency
        idf(t)    = log(G / df(t))                       # inverse document freq
        tfidf     = tf(t, g) * idf(t)

    High tf-idf = frequent *inside* a group yet rare *across* groups, i.e. the
    term is **distinctive/characteristic** of that group. A term shared by every
    group gets idf = 0 and drops out — exactly the boilerplate ("justification",
    "deviation") that raw frequency counts over-rank. Returns tidy rows.
    """
    group_counts = {
        g: Counter(tok for txt in texts for tok in _tokenize(txt))
        for g, texts in texts_by_group.items()
    }
    n_groups = len(group_counts)
    doc_freq: Counter = Counter()
    for counts in group_counts.values():
        for term in counts:
            doc_freq[term] += 1

    rows = []
    for g, counts in group_counts.items():
        total = sum(counts.values()) or 1
        for term, c in counts.items():
            tf = c / total
            idf = math.log(n_groups / doc_freq[term]) if doc_freq[term] else 0.0
            rows.append({"group": g, "term": term, "count": c, "tfidf": tf * idf})
    return pd.DataFrame(rows)


def _association_rules(baskets: list[set[str]]) -> pd.DataFrame:
    """Association-rule metrics (Agrawal et al., market-basket analysis).

    Each "basket" is the set of exemption types granted in one permit. For a
    pair of labels A, B over N baskets:

        support(X)        = P(X)        = #baskets containing X / N
        support(A, B)     = P(A ∧ B)
        confidence(A→B)   = P(B | A)    = support(A,B) / support(A)
        lift(A, B)        = P(A ∧ B) / (P(A) · P(B))

    lift > 1 ⇒ A and B co-occur **more** than chance (positive association);
    lift = 1 ⇒ independent; lift < 1 ⇒ they avoid each other. lift is symmetric.
    """
    n = len(baskets) or 1
    labels = sorted({x for b in baskets for x in b})
    support = {x: sum(x in b for b in baskets) / n for x in labels}

    rows = []
    for a in labels:
        for b in labels:
            if a == b:
                continue
            sab = sum(a in bs and b in bs for bs in baskets) / n
            conf = sab / support[a] if support[a] else 0.0
            lift = sab / (support[a] * support[b]) if support[a] and support[b] else 0.0
            rows.append({
                "antecedent": a, "consequent": b,
                "support_ab": sab, "confidence": conf, "lift": lift,
            })
    return pd.DataFrame(rows)


def _cosine_similarity_matrix(texts: list[str]) -> np.ndarray:
    """Bag-of-words vectorisation + cosine similarity (vector space model).

    Each document → a term-count vector over the shared vocabulary. Similarity
    of two docs = cos(θ) = (u · v) / (‖u‖ ‖v‖) ∈ [0, 1] for non-negative counts.
    1 = identical token profile, 0 = no shared tokens. Used here to see whether
    the unclassified ('other') items secretly cluster into latent sub-groups.
    """
    vocab = sorted({tok for t in texts for tok in _tokenize(t)})
    index = {w: i for i, w in enumerate(vocab)}
    mat = np.zeros((len(texts), len(vocab) or 1))
    for r, t in enumerate(texts):
        for tok in _tokenize(t):
            mat[r, index[tok]] += 1
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = mat / norms
    return unit @ unit.T


def _section_number(ref: str | None) -> str | None:
    """Extract the leading § section number from a legal reference string."""
    if not ref:
        return None
    m = re.search(r"§\s*(\d+)", ref)
    return m.group(1) if m else None


# ── Exploratory figures ──────────────────────────────────────────────────────

def plot_tfidf_distinctive_terms(
    items: pd.DataFrame, output_dir: Path, group_col: str = "item_type", top_n: int = 10
) -> dict:
    """Faceted bar of the most *distinctive* terms per group (TF-IDF, not raw count)."""
    import matplotlib.pyplot as plt

    texts_by_group = {
        g: grp["text"].tolist()
        for g, grp in items.groupby(group_col)
        if g != UNKNOWN
    }
    tfidf = _tfidf_by_group(texts_by_group)
    groups = [g for g in texts_by_group if (tfidf["group"] == g).any()]
    if not groups:
        print("Skipped tfidf: no terms")
        return {}

    ncol = 2
    nrow = math.ceil(len(groups) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 3.0 * nrow))
    axes = np.atleast_1d(axes).flatten()

    summary: dict[str, list[str]] = {}
    for ax, g in zip(axes, groups):
        top = tfidf[tfidf["group"] == g].nlargest(top_n, "tfidf").sort_values("tfidf")
        ax.barh(top["term"], top["tfidf"], color=_EXEMPTION_PALETTE.get(g, "#7f7f7f"))
        ax.set_title(f"{g}  (n={len(texts_by_group[g])})", fontsize=10, fontweight="bold")
        ax.tick_params(labelsize=8)
        summary[g] = top["term"].tolist()[::-1]
    for ax in axes[len(groups):]:
        ax.axis("off")

    fig.suptitle("Distinctive terms per exemption type (TF-IDF)", fontweight="bold")
    fig.tight_layout()
    path = output_dir / "explore_tfidf_distinctive_terms.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return summary


def plot_type_cooccurrence_lift(source: dict[str, dict], output_dir: Path) -> list[dict]:
    """Heatmap of exemption-type co-occurrence lift (association-rule mining)."""
    import matplotlib.pyplot as plt

    baskets = [set(ge.get("types") or []) - {"no_exemption"} for ge in source.values()]
    baskets = [b for b in baskets if b]
    rules = _association_rules(baskets)
    if rules.empty:
        print("Skipped lift heatmap: no baskets")
        return []

    matrix = rules.pivot(index="antecedent", columns="consequent", values="lift")
    fig, ax = plt.subplots(figsize=(8.5, 7))
    sns.heatmap(
        matrix, annot=True, fmt=".2f", cmap="vlag", center=1.0,
        linewidths=0.5, cbar_kws={"label": "lift  (>1 = co-occur above chance)"}, ax=ax,
    )
    ax.set_title("Exemption-type co-occurrence (lift)", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    path = output_dir / "explore_type_cooccurrence_lift.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")

    top_pairs = (
        rules[rules["lift"] > 1.0]
        .sort_values("lift", ascending=False)
        .drop_duplicates("lift")  # lift is symmetric; show each pair once
        .head(10)[["antecedent", "consequent", "lift", "support_ab"]]
    )
    return top_pairs.round(3).to_dict("records")


def plot_section_number_coverage(items: pd.DataFrame, output_dir: Path) -> dict:
    """Bar of cited section numbers per legal family — surfaces taxonomy-gap §s.

    Splits each ``legal_family`` by the substantive § it cites so you can see
    which section numbers recur and therefore deserve their own rule (the README's
    'closing the taxonomy_gap section-number gaps' next step). 'other'-typed items
    are flagged, since those are the sections the taxonomy currently misses.
    """
    import matplotlib.pyplot as plt

    known = items[items["legal_family"] != UNKNOWN].copy()
    known["section"] = known["legal_ref"].apply(_section_number)
    known = known[known["section"].notna()]
    if known.empty:
        print("Skipped section coverage: no qualified refs")
        return {}

    known["label"] = known["legal_family"] + " §" + known["section"]
    pivot = (
        known.assign(bucket=np.where(known["item_type"] == "other", "unmatched ('other')", "matched"))
        .groupby(["label", "bucket"]).size().unstack(fill_value=0)
    )
    pivot = pivot.loc[pivot.sum(axis=1).sort_values().index]

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(pivot) * 0.4)))
    bottom = np.zeros(len(pivot))
    for bucket, color in [("matched", "#4c72b0"), ("unmatched ('other')", "#dd8452")]:
        if bucket in pivot:
            ax.barh(pivot.index, pivot[bucket], left=bottom, label=bucket, color=color)
            bottom += pivot[bucket].values
    ax.set_title("Cited section numbers by legal family", fontweight="bold")
    ax.set_xlabel("Items")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = output_dir / "explore_section_number_coverage.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return known["label"].value_counts().to_dict()


def plot_justification_patterns(items: pd.DataFrame, output_dir: Path, top_n: int = 15) -> dict:
    """Two-panel view of the untapped `justification` field.

    Left: frequency of *whole* normalised justification strings — exposes the
    templated rationales (mode-finding / prototype detection). Right: TF-style
    keyword frequency across all justifications.
    """
    import matplotlib.pyplot as plt

    just = items[items["justification"].str.strip().astype(bool)]
    if just.empty:
        print("Skipped justification: none present")
        return {}

    phrases = (
        just["justification"].str.strip().str.lower().value_counts().head(top_n).sort_values()
    )
    keywords = Counter(tok for t in just["justification"] for tok in _tokenize(t))
    kw_top = pd.Series(dict(keywords.most_common(top_n))).sort_values()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, max(5, top_n * 0.4)))
    ax1.barh(range(len(phrases)), phrases.values, color="#55a868")
    ax1.set_yticks(range(len(phrases)))
    ax1.set_yticklabels([p[:70] + ("…" if len(p) > 70 else "") for p in phrases.index], fontsize=8)
    ax1.set_title("Templated justification phrases (verbatim)", fontweight="bold")
    ax1.set_xlabel("Items")

    ax2.barh(kw_top.index, kw_top.values, color="#c44e52")
    ax2.set_title("Justification keywords", fontweight="bold")
    ax2.set_xlabel("Occurrences")
    ax2.tick_params(labelsize=8)

    fig.suptitle(f"Rationale patterns from `justification` (n={len(just)} items)", fontweight="bold")
    fig.tight_layout()
    path = output_dir / "explore_justification_patterns.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return {p: int(c) for p, c in phrases.sort_values(ascending=False).items()}


def plot_other_item_similarity(items: pd.DataFrame, output_dir: Path) -> float | None:
    """Cosine-similarity heatmap among 'other' items — do the unclassified cluster?"""
    import matplotlib.pyplot as plt

    other = items[items["item_type"] == "other"].reset_index(drop=True)
    if len(other) < 2:
        print("Skipped similarity: <2 'other' items")
        return None

    sim = _cosine_similarity_matrix(other["text"].tolist())
    labels = [
        f"{r.request_id}.{r.item_index} [{r.gap_category}]"
        for r in other.itertuples()
    ]
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(sim, xticklabels=labels, yticklabels=labels, cmap="rocket",
                vmin=0, vmax=1, square=True, cbar_kws={"label": "cosine similarity"}, ax=ax)
    ax.set_title("Pairwise similarity of 'other' items (bag-of-words cosine)", fontweight="bold")
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    path = output_dir / "explore_other_item_similarity.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")

    off_diag = sim[~np.eye(len(sim), dtype=bool)]
    return float(off_diag.mean())


def explore(items: pd.DataFrame, source: dict[str, dict], output_dir: Path) -> None:
    """Run all exploratory diagnostics and write an explore_report.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print("\n-- Exploratory pattern analysis --")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_notes": {
            "tfidf": "distinctive terms per type (tf * log(G/df))",
            "lift": "type co-occurrence; lift>1 = above-chance pairing",
            "section_coverage": "cited § numbers per family (matched vs 'other')",
            "justification": "templated rationale frequency + keywords",
            "similarity": "bag-of-words cosine among 'other' items",
        },
        "tfidf_distinctive_terms": plot_tfidf_distinctive_terms(items, output_dir),
        "type_cooccurrence_top_lift": plot_type_cooccurrence_lift(source, output_dir),
        "section_number_counts": plot_section_number_coverage(items, output_dir),
        "justification_top_phrases": plot_justification_patterns(items, output_dir),
        "other_item_mean_similarity": plot_other_item_similarity(items, output_dir),
    }

    path = output_dir / "explore_report.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path}")


# ════════════════════════════════════════════════════════════════════════════
# REGULATORY COMPOSITION (descriptive)
#
# Answers the plain descriptive questions, not pattern discovery:
#   Q1  What are the deviations applied for?      -> subjects / building subtypes
#   Q2  Which regulations are affected?           -> cited ordinances per application
#   Q3  Planning/zoning vs building/technical?    -> super-domain split
#   Q4  How many deviations per application?       -> items vs distinct § refs
# Output -> res/figures/patterns/explore/.
# ════════════════════════════════════════════════════════════════════════════

# Collapse the fine-grained exemption taxonomy into the regulatory super-domains
# the user reasons in. A permit can touch several (counted once per domain).
_DOMAIN_BY_TYPE = {
    "planning_law":       "Planning / zoning",
    "building_code":      "Building / technical",
    "tree_environmental": "Environmental / nature",
    "nature_protection":  "Environmental / nature",
    "access_road":        "Access / infrastructure",
    "access_restriction": "Access / infrastructure",
    "other":              "Other / unclassified",
}
_DOMAIN_ORDER = [
    "Planning / zoning", "Building / technical",
    "Environmental / nature", "Access / infrastructure", "Other / unclassified",
]
_DOMAIN_COLOR = {
    "Planning / zoning":       _EXEMPTION_PALETTE["planning_law"],
    "Building / technical":    _EXEMPTION_PALETTE["building_code"],
    "Environmental / nature":  _EXEMPTION_PALETTE["tree_environmental"],
    "Access / infrastructure": _EXEMPTION_PALETTE["access_road"],
    "Other / unclassified":    "#7f7f7f",
}
# Applications that granted nothing have no deviation domain.
_NONE_EXEMPTION_LABEL = "No exemption"
_NONE_EXEMPTION_COLOR = _EXEMPTION_PALETTE["no_exemption"]

# Tokens that appear in a § reference but are not the ordinance name.
_REF_NOISE = {"Abs", "Satz", "Nr", "Halbsatz", "iVm", "und", "der", "des", "in"}


def _regulation_acronym(ref: str | None) -> str | None:
    """Extract the ordinance short-name from a legal reference (last name token)."""
    if not ref:
        return None
    tokens = [t for t in re.findall(r"[A-Za-zÄÖÜäöüß]{2,}", ref) if t not in _REF_NOISE]
    return tokens[-1] if tokens else None


def _granted_records(source: dict[str, dict]) -> list[tuple[str, dict]]:
    """Records that actually granted an exemption (drops is_empty / no_exemption)."""
    return [(rid, ge) for rid, ge in source.items() if not ge.get("is_empty")]


def plot_regulatory_domain(items: pd.DataFrame, source: dict[str, dict], output_dir: Path) -> dict:
    """Q3 — planning/zoning vs building/technical (and the other domains).

    Left: applications touching each domain (record's `types` mapped to a domain,
    counted once per domain, so a permit can appear in several). Right: individual
    deviations (items) per domain (mutually exclusive).
    """
    import matplotlib.pyplot as plt

    granted = _granted_records(source)
    rec = Counter()
    for _, ge in granted:
        for d in {_DOMAIN_BY_TYPE.get(t, "Other / unclassified") for t in (ge.get("types") or [])}:
            rec[d] += 1
    itm = Counter(_DOMAIN_BY_TYPE.get(t, "Other / unclassified") for t in items["item_type"])

    order = _DOMAIN_ORDER
    colors = [_DOMAIN_COLOR[d] for d in order]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))
    for ax, data, title in [
        (ax1, [rec.get(d, 0) for d in order], f"Applications affecting each domain (n={len(granted)}, overlapping)"),
        (ax2, [itm.get(d, 0) for d in order], f"Deviations / items per domain (n={len(items)})"),
    ]:
        bars = ax.barh(order, data, color=colors)
        ax.bar_label(bars, padding=3)
        ax.invert_yaxis()
        ax.margins(x=0.12)
        ax.set_title(title, fontsize=11, fontweight="bold")
    fig.suptitle("Regulatory domain of granted deviations", fontweight="bold")
    fig.tight_layout()
    path = output_dir / "explore_regulatory_domain.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return {
        "applications_total": len(granted),
        "applications_by_domain": {d: rec.get(d, 0) for d in order},
        "deviations_by_domain": {d: itm.get(d, 0) for d in order},
    }


def plot_regulations_affected(source: dict[str, dict], output_dir: Path) -> dict:
    """Q2 — which ordinances are affected (applications citing each regulation)."""
    reg = Counter()
    for _, ge in _granted_records(source):
        acronyms = {a for ref in (ge.get("legal_refs") or []) if (a := _regulation_acronym(ref))}
        for a in acronyms:
            reg[a] += 1
    series = pd.Series(reg).sort_values()
    save_barh(
        series,
        "Regulations affected (applications citing each ordinance)",
        "Applications",
        output_dir / "explore_regulations_affected.png",
    )
    return series.sort_values(ascending=False).to_dict()


def plot_deviation_subjects(source: dict[str, dict], output_dir: Path, top_n: int = 15) -> dict:
    """Q1 — what the deviations are applied for (building subtypes + subject terms)."""
    import matplotlib.pyplot as plt

    subtypes = Counter()
    subject_terms = Counter()
    for _, ge in _granted_records(source):
        for st in (ge.get("building_code_subtypes") or []):
            subtypes[st] += 1
        for subj in (ge.get("subjects") or []):
            subject_terms.update(_tokenize(subj))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, max(5, top_n * 0.4)))
    if subtypes:
        s = pd.Series(subtypes).sort_values()
        ax1.barh(s.index, s.values, color=_EXEMPTION_PALETTE["building_code"])
        ax1.bar_label(ax1.containers[0], padding=3)
    ax1.set_title("Building/technical: what was deviated (HBauO subtypes)", fontsize=11, fontweight="bold")

    if subject_terms:
        s = pd.Series(dict(subject_terms.most_common(top_n))).sort_values()
        ax2.barh(s.index, s.values, color=_EXEMPTION_PALETTE["planning_law"])
    ax2.set_title("Subject keywords across all deviations", fontsize=11, fontweight="bold")
    ax2.tick_params(labelsize=8)

    fig.suptitle("What the deviations are applied for", fontweight="bold")
    fig.tight_layout()
    path = output_dir / "explore_deviation_subjects.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return {
        "building_code_subtypes": pd.Series(subtypes).sort_values(ascending=False).to_dict() if subtypes else {},
        "top_subject_terms": dict(subject_terms.most_common(top_n)),
    }


def plot_deviations_per_application(
    source: dict[str, dict],
    output_dir: Path,
    zero_apps: int = 0,
    official_counts: dict[str, int] | None = None,
) -> dict:
    """Q4 — deviations per application, counted by the source `number_of_exemptions`.

    The x-axis uses the official per-permit count (``official_counts``), which
    captures bundled deviations the parsed numbered-items count misses. Bars are
    stacked by the granted permit's primary regulatory domain. The text-based
    cohort split is kept: the ``zero_apps`` none-exemption permits are pinned to 0
    (their stray count=1 values are treated as source artifacts). Parsed-item and
    §-reference counts are still computed and returned for comparison.
    """
    import matplotlib.pyplot as plt

    official_counts = official_counts or {}
    rows = []
    for rid, ge in source.items():
        if ge.get("is_empty"):
            rows.append({"request_id": rid, "deviations": 0, "items": 0,
                         "legal_refs": 0, "domain": _NONE_EXEMPTION_LABEL})
            continue
        rows.append({
            "request_id": rid,
            # Official source count; fall back to parsed items if absent.
            "deviations": official_counts.get(str(rid), len(item_keys(ge))),
            "items": len(item_keys(ge)),
            "legal_refs": len(ge.get("legal_refs") or []),
            "domain": _DOMAIN_BY_TYPE.get(ge.get("primary_type"), "Other / unclassified"),
        })
    # None-exemption cohort: pinned to 0 deviations (text-based split is truth).
    rows.extend(
        {"request_id": None, "deviations": 0, "items": 0, "legal_refs": 0,
         "domain": _NONE_EXEMPTION_LABEL}
        for _ in range(zero_apps)
    )
    df = pd.DataFrame(rows)
    if df.empty:
        print("Skipped deviations-per-application: no records")
        return {}

    stats = {}
    for col in ("deviations", "items", "legal_refs"):
        vals = df[col]
        stats[col] = {
            "mean": round(float(vals.mean()), 2),
            "median": float(vals.median()),
            "max": int(vals.max()),
            "total": int(vals.sum()),
        }

    # Stack each count bar by the application's primary domain (counted once each).
    domain_order = [d for d in _DOMAIN_ORDER if d in set(df["domain"])]
    if _NONE_EXEMPTION_LABEL in set(df["domain"]):
        domain_order.append(_NONE_EXEMPTION_LABEL)
    color_map = {**_DOMAIN_COLOR, _NONE_EXEMPTION_LABEL: _NONE_EXEMPTION_COLOR}

    ct = (
        pd.crosstab(df["deviations"], df["domain"])
        .reindex(range(0, int(df["deviations"].max()) + 1), fill_value=0)
        .reindex(columns=domain_order, fill_value=0)
    )
    x = ct.index.to_numpy()

    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = np.zeros(len(ct))
    for d in domain_order:
        ax.bar(x, ct[d].to_numpy(), bottom=bottom, width=0.85, label=d, color=color_map[d])
        bottom += ct[d].to_numpy()

    totals = ct.sum(axis=1).to_numpy()
    for xi, tot in zip(x, totals):
        if tot:
            ax.text(xi, tot, f" {int(tot)}", ha="center", va="bottom", fontsize=10)

    ax.set_xlabel("Count of deviations per application")
    ax.set_ylabel("Number of applications")
    ax.set_xticks(list(x))
    ax.margins(y=0.10)
    ax.legend(title="Primary regulatory domain", fontsize=8, title_fontsize=9)
    fig.tight_layout()
    path = output_dir / "explore_deviations_per_application.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return {
        "applications_total": int(len(df)),
        "granted_cohort": int((df["domain"] != _NONE_EXEMPTION_LABEL).sum()),
        "none_cohort": int(zero_apps),
        "count_basis": "number_of_exemptions (official); none-cohort pinned to 0",
        "zero_deviation_apps": int((df["deviations"] == 0).sum()),
        **stats,
    }


def describe_composition(items: pd.DataFrame, source: dict[str, dict], output_dir: Path) -> None:
    """Run the descriptive composition figures and write composition_report.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print("\n-- Regulatory composition (descriptive) --")

    zero_apps = count_zero_exemption_apps(NONE_EXEMPTION_FILE)
    official_counts = load_official_exemption_counts(JSON_FILE)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "q1_what_applied_for": plot_deviation_subjects(source, output_dir),
        "q2_regulations_affected": plot_regulations_affected(source, output_dir),
        "q3_regulatory_domain": plot_regulatory_domain(items, source, output_dir),
        "q4_deviations_per_application": plot_deviations_per_application(
            source, output_dir, zero_apps, official_counts),
    }
    path = output_dir / "composition_report.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=int)
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

    # Exploratory, iteration-oriented diagnostics → res/figures/patterns/explore/
    explore(items, granted, EXPLORE_DIR)
    describe_composition(items, granted, EXPLORE_DIR)

    other_count = int((items["item_type"] == "other").sum())
    print(f"\n{other_count} of {len(items)} items are unclassified ('other').")
    print(f"All pattern figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
