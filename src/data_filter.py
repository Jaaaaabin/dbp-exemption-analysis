"""
Module for filtering DataFrames based on various criteria.
"""

import pandas as pd
from typing import Any, Callable, Optional


def filter_by_value(
    df: pd.DataFrame,
    column: str,
    value: Any,
    operator: str = '=='
) -> pd.DataFrame:
    """
    Filter DataFrame by a single column value.
    
    Args:
        df: Input DataFrame
        column: Column name to filter on
        value: Value to compare against
        operator: Comparison operator ('==', '!=', '>', '<', '>=', '<=', 'in', 'not in')
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    if operator == '==':
        filtered = df[df[column] == value]
    elif operator == '!=':
        filtered = df[df[column] != value]
    elif operator == '>':
        filtered = df[df[column] > value]
    elif operator == '<':
        filtered = df[df[column] < value]
    elif operator == '>=':
        filtered = df[df[column] >= value]
    elif operator == '<=':
        filtered = df[df[column] <= value]
    elif operator == 'in':
        filtered = df[df[column].isin(value)]
    elif operator == 'not in':
        filtered = df[~df[column].isin(value)]
    else:
        raise ValueError(f"Unsupported operator: {operator}")
    
    print(f"Filtered by {column} {operator} {value}: {len(filtered)} rows")
    return filtered


def filter_by_multiple_conditions(
    df: pd.DataFrame,
    conditions: dict[str, tuple[str, Any]]
) -> pd.DataFrame:
    """
    Filter DataFrame by multiple conditions (AND logic).
    
    Args:
        df: Input DataFrame
        conditions: Dictionary mapping column names to (operator, value) tuples
                   Example: {'age': ('>', 25), 'city': ('==', 'Munich')}
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    filtered = df.copy()
    
    for column, (operator, value) in conditions.items():
        filtered = filter_by_value(filtered, column, value, operator)
    
    print(f"Total rows after all conditions: {len(filtered)}")
    return filtered


def filter_by_date_range(
    df: pd.DataFrame,
    date_column: str,
    start_date: Optional[str | pd.Timestamp] = None,
    end_date: Optional[str | pd.Timestamp] = None
) -> pd.DataFrame:
    """
    Filter DataFrame by date range.
    
    Args:
        df: Input DataFrame
        date_column: Name of the date column
        start_date: Start date (inclusive), None for no lower bound
        end_date: End date (inclusive), None for no upper bound
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    if date_column not in df.columns:
        raise ValueError(f"Column '{date_column}' not found in DataFrame")
    
    # Ensure the column is datetime type
    df_copy = df.copy()
    df_copy[date_column] = pd.to_datetime(df_copy[date_column])
    
    filtered = df_copy
    
    if start_date:
        start_date = pd.to_datetime(start_date)
        filtered = filtered[filtered[date_column] >= start_date]
    
    if end_date:
        end_date = pd.to_datetime(end_date)
        filtered = filtered[filtered[date_column] <= end_date]
    
    print(f"Filtered by date range [{start_date} to {end_date}]: {len(filtered)} rows")
    return filtered


def filter_by_string_pattern(
    df: pd.DataFrame,
    column: str,
    pattern: str,
    case_sensitive: bool = False,
    regex: bool = False
) -> pd.DataFrame:
    """
    Filter DataFrame by string pattern matching.
    
    Args:
        df: Input DataFrame
        column: Column name to search in
        pattern: Pattern to search for
        case_sensitive: Whether matching should be case-sensitive (default: False)
        regex: Whether pattern is a regex (default: False)
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    filtered = df[df[column].astype(str).str.contains(
        pattern,
        case=case_sensitive,
        regex=regex,
        na=False
    )]
    
    print(f"Filtered by pattern '{pattern}' in {column}: {len(filtered)} rows")
    return filtered


def filter_by_numeric_range(
    df: pd.DataFrame,
    column: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    inclusive: str = 'both'
) -> pd.DataFrame:
    """
    Filter DataFrame by numeric range.
    
    Args:
        df: Input DataFrame
        column: Column name to filter on
        min_value: Minimum value (None for no lower bound)
        max_value: Maximum value (None for no upper bound)
        inclusive: Whether bounds are inclusive - 'both', 'neither', 'left', 'right'
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    
    filtered = df.copy()
    
    if min_value is not None and max_value is not None:
        filtered = filtered[filtered[column].between(min_value, max_value, inclusive=inclusive)]
    elif min_value is not None:
        if inclusive in ['both', 'left']:
            filtered = filtered[filtered[column] >= min_value]
        else:
            filtered = filtered[filtered[column] > min_value]
    elif max_value is not None:
        if inclusive in ['both', 'right']:
            filtered = filtered[filtered[column] <= max_value]
        else:
            filtered = filtered[filtered[column] < max_value]
    
    print(f"Filtered by range [{min_value}, {max_value}] ({inclusive}): {len(filtered)} rows")
    return filtered


def filter_by_custom_function(
    df: pd.DataFrame,
    filter_func: Callable[[pd.Series], bool],
    description: str = "custom filter"
) -> pd.DataFrame:
    """
    Filter DataFrame using a custom function.
    
    Args:
        df: Input DataFrame
        filter_func: Function that takes a row (Series) and returns True/False
        description: Description of the filter for logging
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    filtered = df[df.apply(filter_func, axis=1)]
    print(f"Filtered by {description}: {len(filtered)} rows")
    return filtered


def create_filtered_subsets(
    df: pd.DataFrame,
    subset_definitions: dict[str, dict]
) -> dict[str, pd.DataFrame]:
    """
    Create multiple filtered subsets of the DataFrame.
    
    Args:
        df: Input DataFrame
        subset_definitions: Dictionary mapping subset names to filter conditions
                          Example: {
                              'high_value': {'column': 'price', 'operator': '>', 'value': 100},
                              'recent': {'date_column': 'date', 'start_date': '2024-01-01'}
                          }
    
    Returns:
        dict[str, pd.DataFrame]: Dictionary mapping subset names to filtered DataFrames
    """
    subsets = {}
    
    for name, conditions in subset_definitions.items():
        print(f"\nCreating subset: {name}")
        
        # Determine filter type based on conditions keys
        if 'date_column' in conditions:
            filtered = filter_by_date_range(df, **conditions)
        elif 'pattern' in conditions:
            filtered = filter_by_string_pattern(df, **conditions)
        elif 'min_value' in conditions or 'max_value' in conditions:
            filtered = filter_by_numeric_range(df, **conditions)
        elif 'operator' in conditions:
            filtered = filter_by_value(df, **conditions)
        elif 'conditions' in conditions:
            filtered = filter_by_multiple_conditions(df, conditions['conditions'])
        else:
            raise ValueError(f"Unknown filter type for subset '{name}'")
        
        subsets[name] = filtered
    
    return subsets
