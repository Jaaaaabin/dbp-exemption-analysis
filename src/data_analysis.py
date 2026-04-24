# src/data_analysis.py
# DataFrame analysis helpers.
#   describe_numeric_columns      – descriptive statistics for numeric columns
#   describe_categorical_columns  – value counts for categorical columns
#   analyze_correlations          – correlation matrix filtered by a minimum threshold
#   group_and_aggregate           – groupby with aggregation and flattened column names
#   compare_subsets               – compare a metric across multiple named DataFrames
#   detect_outliers               – flag outliers via IQR or z-score method

import pandas as pd
from typing import Optional, Any

def describe_numeric_columns(
    df: pd.DataFrame,
    percentiles: Optional[list[float]] = None
) -> pd.DataFrame:
    """
    Get descriptive statistics for numeric columns.
    
    Args:
        df: Input DataFrame
        percentiles: List of percentiles to include (default: [0.25, 0.5, 0.75])
    
    Returns:
        pd.DataFrame: Descriptive statistics
    """
    if percentiles is None:
        percentiles = [0.25, 0.5, 0.75]
    
    return df.describe(percentiles=percentiles)


def describe_categorical_columns(
    df: pd.DataFrame,
    top_n: int = 10
) -> dict[str, pd.Series]:
    """
    Get value counts for categorical columns.
    
    Args:
        df: Input DataFrame
        top_n: Number of top values to show for each column
    
    Returns:
        dict: Dictionary mapping column names to value counts
    """
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    
    result = {}
    for col in categorical_cols:
        result[col] = df[col].value_counts().head(top_n)
    
    return result


def analyze_correlations(
    df: pd.DataFrame,
    method: str = 'pearson',
    min_correlation: float = 0.5
) -> pd.DataFrame:
    """
    Analyze correlations between numeric columns.
    
    Args:
        df: Input DataFrame
        method: Correlation method - 'pearson', 'kendall', 'spearman'
        min_correlation: Minimum absolute correlation to display
    
    Returns:
        pd.DataFrame: Correlation matrix filtered by minimum correlation
    """
    numeric_df = df.select_dtypes(include=['number'])
    
    if numeric_df.empty:
        print("No numeric columns found for correlation analysis")
        return pd.DataFrame()
    
    corr_matrix = numeric_df.corr(method=method)
    
    # Filter by minimum correlation (excluding diagonal)
    mask = (abs(corr_matrix) >= min_correlation) & (corr_matrix != 1.0)
    filtered_corr = corr_matrix.where(mask)
    
    return filtered_corr


def group_and_aggregate(
    df: pd.DataFrame,
    group_by: str | list[str],
    agg_dict: dict[str, str | list[str]]
) -> pd.DataFrame:
    """
    Group data and apply aggregations.
    
    Args:
        df: Input DataFrame
        group_by: Column(s) to group by
        agg_dict: Dictionary mapping column names to aggregation functions
                 Example: {'sales': ['sum', 'mean'], 'quantity': 'count'}
    
    Returns:
        pd.DataFrame: Aggregated results
    """
    result = df.groupby(group_by).agg(agg_dict)
    
    # Flatten column names if multi-level
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = ['_'.join(col).strip() for col in result.columns.values]
    
    return result.reset_index()


def compare_subsets(
    subsets: dict[str, pd.DataFrame],
    metric_column: str,
    operation: str = 'mean'
) -> pd.DataFrame:
    """
    Compare a specific metric across different data subsets.
    
    Args:
        subsets: Dictionary mapping subset names to DataFrames
        metric_column: Column to compare
        operation: Aggregation operation - 'mean', 'sum', 'median', 'count'
    
    Returns:
        pd.DataFrame: Comparison results
    """
    results = {}
    
    for name, df in subsets.items():
        if metric_column not in df.columns:
            print(f"Warning: '{metric_column}' not found in subset '{name}'")
            continue
        
        if operation == 'mean':
            results[name] = df[metric_column].mean()
        elif operation == 'sum':
            results[name] = df[metric_column].sum()
        elif operation == 'median':
            results[name] = df[metric_column].median()
        elif operation == 'count':
            results[name] = df[metric_column].count()
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    
    comparison = pd.DataFrame({
        'subset': results.keys(),
        f'{metric_column}_{operation}': results.values()
    })
    
    return comparison.sort_values(f'{metric_column}_{operation}', ascending=False)


def detect_outliers(
    df: pd.DataFrame,
    column: str,
    method: str = 'iqr',
    threshold: float = 1.5
) -> pd.DataFrame:
    """
    Detect outliers in a numeric column.
    
    Args:
        df: Input DataFrame
        column: Column to check for outliers
        method: Method to use - 'iqr' (interquartile range) or 'zscore'
        threshold: Threshold for outlier detection (1.5 for IQR, 3 for z-score)
    
    Returns:
        pd.DataFrame: DataFrame containing only outlier rows
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    if method == 'iqr':
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
        
    elif method == 'zscore':
        mean = df[column].mean()
        std = df[column].std()
        z_scores = abs((df[column] - mean) / std)
        outliers = df[z_scores > threshold]
        
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    print(f"Detected {len(outliers)} outliers in '{column}' using {method} method")
    return outliers
