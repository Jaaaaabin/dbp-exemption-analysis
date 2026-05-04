# src/data_analysis.py
# Data manipulation, filtering, and analysis utilities.
# All analysis functions accept a JsonSource (path or list[dict]) directly.
#
# ETL split (called by extract.py)
#   split_by_missing_columns     – split DataFrame into has-exemption / missing-exemption
#
# DataFrame filtering
#   filter_by_value              – filter a column by a single value and operator
#   filter_by_range              – filter a numeric column by min/max bounds
#   filter_by_string             – substring or regex filter on a string column
#   filter_by_date_range         – filter by start/end date on a datetime column
#   filter_by_custom             – apply an arbitrary row-level predicate
#
# Statistics & aggregations
#   describe_numeric             – descriptive statistics for numeric columns
#   describe_categorical         – value counts for categorical columns
#   correlations                 – correlation matrix filtered by a minimum |r|
#   group_aggregate              – groupby with multi-stat aggregation
#   compare_subsets              – compare a metric across multiple named JSON sources
#   detect_outliers              – flag outliers via IQR or z-score

import json
import pandas as pd
from pathlib import Path
from typing import Any, Callable

JsonSource = str | Path | list[dict]


# ── Internal loader ───────────────────────────────────────────────────────────

def _load(source: JsonSource) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        with open(source, encoding='utf-8') as f:
            return pd.DataFrame(json.load(f))
    return pd.DataFrame(source)


# ── ETL split ─────────────────────────────────────────────────────────────────

def split_by_missing_columns(
    df: pd.DataFrame,
    col_exemption: str = 'Granted Exemptions',
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split df into (has_exemption, missing_exemption)."""
    if col_exemption not in df.columns:
        raise ValueError(f"Column '{col_exemption}' not found in DataFrame")

    mask_no_exemption = df[col_exemption].isna() | (df[col_exemption].astype(str).str.strip().str.upper() == 'N/A')
    df_has_exemption  = df[~mask_no_exemption].copy()
    df_no_exemption   = df[mask_no_exemption].copy()

    print(f"Split — has exemption: {len(df_has_exemption)} | "
          f"missing exemption: {len(df_no_exemption)}")
    return df_has_exemption, df_no_exemption


# ── DataFrame filtering ───────────────────────────────────────────────────────

_OPS = {
    '==': lambda s, v: s == v,
    '!=': lambda s, v: s != v,
    '>':  lambda s, v: s > v,
    '<':  lambda s, v: s < v,
    '>=': lambda s, v: s >= v,
    '<=': lambda s, v: s <= v,
    'in':     lambda s, v: s.isin(v),
    'not in': lambda s, v: ~s.isin(v),
}


def filter_by_value(
    df: pd.DataFrame,
    column: str,
    value: Any,
    operator: str = '==',
) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    op = _OPS.get(operator)
    if op is None:
        raise ValueError(f"Unsupported operator: '{operator}'. Use: {list(_OPS)}")
    return df[op(df[column], value)]


def filter_by_range(
    df: pd.DataFrame,
    column: str,
    min_value: float | None = None,
    max_value: float | None = None,
    inclusive: str = 'both',
) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if min_value is not None and max_value is not None:
        return df[df[column].between(min_value, max_value, inclusive=inclusive)]
    if min_value is not None:
        return df[df[column] >= min_value] if inclusive in ('both', 'left') else df[df[column] > min_value]
    if max_value is not None:
        return df[df[column] <= max_value] if inclusive in ('both', 'right') else df[df[column] < max_value]
    return df


def filter_by_string(
    df: pd.DataFrame,
    column: str,
    pattern: str,
    case_sensitive: bool = False,
    regex: bool = False,
) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    return df[df[column].astype(str).str.contains(pattern, case=case_sensitive, regex=regex, na=False)]


def filter_by_date_range(
    df: pd.DataFrame,
    date_column: str,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    if date_column not in df.columns:
        raise ValueError(f"Column '{date_column}' not found")
    s = df.copy()
    s[date_column] = pd.to_datetime(s[date_column])
    if start_date:
        s = s[s[date_column] >= pd.to_datetime(start_date)]
    if end_date:
        s = s[s[date_column] <= pd.to_datetime(end_date)]
    return s


def filter_by_custom(
    df: pd.DataFrame,
    predicate: Callable[[pd.Series], bool],
) -> pd.DataFrame:
    return df[df.apply(predicate, axis=1)]


# ── Statistics & aggregations ─────────────────────────────────────────────────

def describe_numeric(
    source: JsonSource,
    percentiles: list[float] | None = None,
) -> pd.DataFrame:
    df = _load(source)
    return df.select_dtypes(include='number').describe(
        percentiles=percentiles or [0.25, 0.5, 0.75]
    )


def describe_categorical(
    source: JsonSource,
    top_n: int = 10,
) -> dict[str, pd.Series]:
    df = _load(source)
    return {
        col: df[col].value_counts().head(top_n)
        for col in df.select_dtypes(include=['object', 'category']).columns
    }


def correlations(
    source: JsonSource,
    method: str = 'pearson',
    min_r: float = 0.5,
) -> pd.DataFrame:
    df = _load(source)
    numeric = df.select_dtypes(include='number')
    if numeric.empty:
        return pd.DataFrame()
    corr = numeric.corr(method=method)
    return corr.where((corr.abs() >= min_r) & (corr != 1.0))


def group_aggregate(
    source: JsonSource,
    group_by: str | list[str],
    agg_dict: dict[str, str | list[str]],
) -> pd.DataFrame:
    df = _load(source)
    result = df.groupby(group_by).agg(agg_dict)
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = ['_'.join(c).strip() for c in result.columns]
    return result.reset_index()


def compare_subsets(
    subsets: dict[str, JsonSource],
    metric_column: str,
    operation: str = 'mean',
) -> pd.DataFrame:
    """Compare metric across multiple named JSON sources using any pandas aggregation."""
    rows = {}
    for name, source in subsets.items():
        df = _load(source)
        if metric_column not in df.columns:
            continue
        fn = getattr(df[metric_column].dropna(), operation, None)
        if fn is None:
            raise ValueError(f"Unsupported operation: '{operation}'")
        rows[name] = fn()
    return (
        pd.DataFrame({'subset': list(rows), f'{metric_column}_{operation}': list(rows.values())})
        .sort_values(f'{metric_column}_{operation}', ascending=False)
        .reset_index(drop=True)
    )


def detect_outliers(
    source: JsonSource,
    column: str,
    method: str = 'iqr',
    threshold: float = 1.5,
) -> pd.DataFrame:
    df = _load(source)
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    if method == 'iqr':
        q1, q3 = df[column].quantile(0.25), df[column].quantile(0.75)
        iqr = q3 - q1
        mask = (df[column] < q1 - threshold * iqr) | (df[column] > q3 + threshold * iqr)
    elif method == 'zscore':
        z = (df[column] - df[column].mean()) / df[column].std()
        mask = z.abs() > threshold
    else:
        raise ValueError(f"Unsupported method: '{method}'")
    return df[mask]
