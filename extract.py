"""
ETL pipeline: Excel → cleaned CSV + JSON outputs.
Output paths are defined in settings.py.
"""

from src.data_clean import load_and_clean, print_basic_info, save_cleaned_data
from src.data_analysis import split_by_missing_columns
from src.configuration import get_dbp_data_management_config
from settings import (
    FILE_ANALYZE_CSV,        FILE_ANALYZE_JSON,
    FILE_NONE_EXEMPTION_CSV, FILE_NONE_EXEMPTION_JSON,
    FILE_NON_REGULATION_CSV, FILE_NON_REGULATION_JSON,
)


def main():
    data_cfg = get_dbp_data_management_config()
    raw_file = data_cfg.get('raw') / "data.xlsx"

    if not raw_file.exists():
        print(f"Error: File not found: {raw_file}")
        return

    df = load_and_clean(file_path=raw_file, drop_duplicates=True, strip_strings=True)
    df_analyze, df_none_exemption, df_non_regulation = split_by_missing_columns(df)

    save_cleaned_data(df_analyze,         FILE_ANALYZE_CSV)
    save_cleaned_data(df_none_exemption,  FILE_NONE_EXEMPTION_CSV)
    save_cleaned_data(df_non_regulation,  FILE_NON_REGULATION_CSV)

    save_cleaned_data(df_analyze,         FILE_ANALYZE_JSON,        format='json')
    save_cleaned_data(df_none_exemption,  FILE_NONE_EXEMPTION_JSON, format='json')
    save_cleaned_data(df_non_regulation,  FILE_NON_REGULATION_JSON, format='json')

    print_basic_info(df_analyze,        title="ANALYZE DATA (both columns present)")
    print_basic_info(df_none_exemption, title="MISSING: Granted Exemptions")
    print_basic_info(df_non_regulation, title="MISSING: Building regulations and requirements")


if __name__ == "__main__":
    main()
