# src/data_clean.py
# Excel ingestion and DataFrame cleaning.
#   read_excel_file      – load an Excel sheet into a DataFrame
#   get_basic_info       – return shape, dtypes, missing-value counts, and memory usage
#   print_basic_info     – print a formatted overview of the DataFrame
#   clean_dataframe      – drop duplicates, drop/fill NAs, strip string whitespace
#   columns_to_json_keys – map column names to JSON-safe snake_case keys
#   save_cleaned_data    – write DataFrame to CSV, Excel, Parquet, or JSON
#   load_and_clean       – convenience: read + clean in one call

import re
import pandas as pd
from pathlib import Path
from typing import Optional, Any

from src.utils.cli_utils import progress_iter, spinner

def get_basic_info(df: pd.DataFrame) -> dict[str, Any]:
    """
    Get basic information about the DataFrame.
    
    Args:
        df: Input DataFrame
    
    Returns:
        dict: Dictionary containing basic statistics
    """
    info = {
        'n_rows': len(df),
        'n_columns': len(df.columns),
        'columns': list(df.columns),
        'dtypes': df.dtypes.to_dict(),
        'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2,
        'missing_values': df.isnull().sum().to_dict(),
        'duplicate_rows': df.duplicated().sum()
    }
    
    return info

def print_basic_info(df: pd.DataFrame, title: str = "DATAFRAME OVERVIEW") -> None:
    """
    Print basic information about the DataFrame in a readable format.

    Args:
        df: Input DataFrame
        title: Header title printed above the overview
    """
    info = get_basic_info(df)

    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Rows: {info['n_rows']:,}")
    print(f"Columns: {info['n_columns']}")
    print(f"Memory Usage: {info['memory_usage_mb']:.2f} MB")
    print(f"Duplicate Rows: {info['duplicate_rows']}")
    
    print("\nCOLUMNS:")
    for col, dtype in info['dtypes'].items():
        missing = info['missing_values'][col]
        missing_pct = (missing / info['n_rows'] * 100) if info['n_rows'] > 0 else 0
        print(f"  {col:30} | {str(dtype):15} | Missing: {missing:6} ({missing_pct:5.1f}%)")
    
    print("=" * 60)

def read_excel_file(
    file_path: str | Path,
    sheet_name: str | int = 0,
    **kwargs
) -> pd.DataFrame:
    """
    Read an Excel file and return as a pandas DataFrame.
    
    Args:
        file_path: Path to the Excel file
        sheet_name: Name or index of the sheet to read (default: 0)
        **kwargs: Additional arguments to pass to pd.read_excel()
    
    Returns:
        pd.DataFrame: The loaded data
    
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file cannot be read
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # calamine is significantly faster than openpyxl for xlsx/xlsm
    suffix = file_path.suffix.lower()
    engine = 'calamine' if suffix in ('.xlsx', '.xlsm') else None

    try:
        with spinner(f"Reading {file_path.name}..."):
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, **kwargs)
        print(f"Loaded {len(df)} rows from {file_path.name}")
        return df
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {e}")

def clean_dataframe(
    df: pd.DataFrame,
    drop_duplicates: bool = True,
    drop_na_columns: Optional[list[str]] = None,
    fill_na_value: Optional[dict] = None,
    strip_strings: bool = True,
    drop_unnamed_columns: bool = True
) -> pd.DataFrame:
    """
    Clean the DataFrame by handling missing values, duplicates, and formatting.
    
    Args:
        df: Input DataFrame
        drop_duplicates: Whether to drop duplicate rows (default: True)
        drop_na_columns: List of columns where NA values should cause row removal
        fill_na_value: Dictionary mapping column names to fill values for NA
        strip_strings: Whether to strip whitespace from string columns (default: True)
    
    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    df_clean = df.copy()

    # Guard against blank header cells in the source Excel: pandas auto-fills them
    # as "Unnamed: N". Only drop them when they are entirely null — if a column
    # carries data despite having no header, keep it so nothing is silently lost.
    if drop_unnamed_columns:
        unnamed = [c for c in df_clean.columns
                   if re.match(r'^Unnamed: \d+$', str(c)) and df_clean[c].isna().all()]
        if unnamed:
            df_clean = df_clean.drop(columns=unnamed)
            print(f"Dropped {len(unnamed)} empty unnamed column(s): {unnamed}")

    # Strip whitespace from string columns
    if strip_strings:
        string_columns = df_clean.select_dtypes(include=['object']).columns.tolist()
        for col in progress_iter(string_columns, desc="Stripping whitespace"):
            df_clean[col] = df_clean[col].str.strip()
    
    # Drop rows with NA in specific columns
    if drop_na_columns:
        df_clean = df_clean.dropna(subset=drop_na_columns)
    
    # Fill NA values
    if fill_na_value:
        df_clean = df_clean.fillna(fill_na_value)
    
    # Drop duplicates
    if drop_duplicates:
        initial_count = len(df_clean)
        df_clean = df_clean.drop_duplicates()
        removed = initial_count - len(df_clean)
        if removed > 0:
            print(f"Removed {removed} duplicate rows")
    
    print(f"Cleaned DataFrame: {len(df_clean)} rows, {len(df_clean.columns)} columns")
    
    return df_clean

def columns_to_json_keys(df: pd.DataFrame) -> dict[str, str]:
    """
    Return a mapping of DataFrame column names to JSON-safe snake_case keys.

    Strategy: lowercase → strip whitespace → replace every run of
    non-alphanumeric characters with a single underscore → strip
    leading/trailing underscores.  Duplicate keys (after sanitisation)
    are disambiguated by appending _2, _3, …
    """
    def _sanitize(col: str) -> str:
        key = col.lower().strip()
        # trailing '+' carries meaning (e.g. "Parcel code 2+" → "parcel_code_2_plus")
        if key.endswith('+'):
            key = key[:-1].rstrip() + '_plus'
        key = re.sub(r'[^a-z0-9]+', '_', key)
        return key.strip('_')

    raw = [_sanitize(col) for col in df.columns]

    seen: dict[str, int] = {}
    keys: list[str] = []
    for key in raw:
        if key not in seen:
            seen[key] = 1
            keys.append(key)
        else:
            seen[key] += 1
            keys.append(f"{key}_{seen[key]}")

    return dict(zip(df.columns, keys))


def save_cleaned_data(
    df: pd.DataFrame,
    output_path: str | Path,
    format: str = 'csv'
) -> None:
    """
    Save the cleaned DataFrame to a file.
    
    Args:
        df: DataFrame to save
        output_path: Path where to save the file
        format: Output format - 'csv', 'excel', or 'parquet' (default: 'csv')
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == 'csv':
        df.to_csv(output_path, index=False)
    elif format == 'excel':
        df.to_excel(output_path, index=False)
    elif format == 'parquet':
        df.to_parquet(output_path, index=False)
    elif format == 'json':
        key_map = columns_to_json_keys(df)
        df.rename(columns=key_map).to_json(
            output_path, orient='records', indent=2, force_ascii=False
        )
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    print(f"Saved cleaned data to {output_path}")

def load_and_clean(
    file_path: str | Path,
    output_path: Optional[str | Path] = None,
    **cleaning_kwargs
) -> pd.DataFrame:
    """
    Convenience function to load and clean data in one step.
    
    Args:
        file_path: Path to the Excel file
        output_path: Optional path to save cleaned data
        **cleaning_kwargs: Arguments to pass to clean_dataframe()
    
    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    df = read_excel_file(file_path)
    df_clean = clean_dataframe(df, **cleaning_kwargs)
    
    if output_path:
        save_cleaned_data(df_clean, output_path)
    
    return df_clean