# src/data_analysis.py
# DataFrame analysis helpers — all functions accept a JSON source directly.
#   _load                        – internal: JSON file/list-of-dicts → DataFrame
#   describe_numeric_columns     – descriptive statistics for numeric columns
#   describe_categorical_columns – value counts for categorical columns
#   analyze_correlations         – correlation matrix filtered by a minimum threshold
#   group_and_aggregate          – groupby with aggregation and flattened column names
#   compare_subsets              – compare a metric across multiple named JSON sources
#   detect_outliers              – flag outliers via IQR or z-score method

import json
import pandas as pd
from pathlib import Path
from typing import Optional

# A JSON source is either a file path or an already-loaded list of records.
JsonSource = str | Path | list[dict]


def _load(source: JsonSource) -> pd.DataFrame:
    """Load a JSON source into a DataFrame."""
    if isinstance(source, (str, Path)):
        with open(source, encoding='utf-8') as f:
            return pd.DataFrame(json.load(f))
    return pd.DataFrame(source)


def describe_numeric_columns(
    source: JsonSource,
    percentiles: Optional[list[float]] = None
) -> pd.DataFrame:
    df = _load(source)
    if percentiles is None:
        percentiles = [0.25, 0.5, 0.75]
    return df.select_dtypes(include='number').describe(percentiles=percentiles)


def describe_categorical_columns(
    source: JsonSource,
    top_n: int = 10
) -> dict[str, pd.Series]:
    df = _load(source)
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    return {col: df[col].value_counts().head(top_n) for col in categorical_cols}


def analyze_correlations(
    source: JsonSource,
    method: str = 'pearson',
    min_correlation: float = 0.5
) -> pd.DataFrame:
    df = _load(source)
    numeric_df = df.select_dtypes(include='number')
    if numeric_df.empty:
        print("No numeric columns found for correlation analysis")
        return pd.DataFrame()
    corr_matrix = numeric_df.corr(method=method)
    mask = (corr_matrix.abs() >= min_correlation) & (corr_matrix != 1.0)
    return corr_matrix.where(mask)


def group_and_aggregate(
    source: JsonSource,
    group_by: str | list[str],
    agg_dict: dict[str, str | list[str]]
) -> pd.DataFrame:
    df = _load(source)
    result = df.groupby(group_by).agg(agg_dict)
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = ['_'.join(col).strip() for col in result.columns.values]
    return result.reset_index()


def compare_subsets(
    subsets: dict[str, JsonSource],
    metric_column: str,
    operation: str = 'mean'
) -> pd.DataFrame:
    """Compare a metric across multiple named JSON sources.

    operation accepts any pandas Series aggregation method name
    (e.g. 'mean', 'median', 'sum', 'count', 'std', 'min', 'max').
    """
    results = {}
    for name, source in subsets.items():
        df = _load(source)
        if metric_column not in df.columns:
            print(f"Warning: '{metric_column}' not found in subset '{name}'")
            continue
        series = df[metric_column].dropna()
        agg_fn = getattr(series, operation, None)
        if agg_fn is None:
            raise ValueError(f"Unsupported operation: '{operation}'")
        results[name] = agg_fn()

    return (
        pd.DataFrame({
            'subset': list(results.keys()),
            f'{metric_column}_{operation}': list(results.values()),
        })
        .sort_values(f'{metric_column}_{operation}', ascending=False)
        .reset_index(drop=True)
    )


def detect_outliers(
    source: JsonSource,
    column: str,
    method: str = 'iqr',
    threshold: float = 1.5
) -> pd.DataFrame:
    df = _load(source)
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")

    if method == 'iqr':
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        outliers = df[(df[column] < Q1 - threshold * IQR) | (df[column] > Q3 + threshold * IQR)]
    elif method == 'zscore':
        mean = df[column].mean()
        std = df[column].std()
        outliers = df[abs((df[column] - mean) / std) > threshold]
    else:
        raise ValueError(f"Unsupported method: '{method}'")

    print(f"Detected {len(outliers)} outliers in '{column}' using {method} method")
    return outliers
