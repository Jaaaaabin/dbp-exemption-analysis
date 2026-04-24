"""
Example script demonstrating the data analysis workflow.
"""

from src.data_clean import (
    load_and_clean,
    print_basic_info,
    save_cleaned_data,
)

from src.data_analysis import (
    describe_numeric_columns,
    group_and_aggregate,
    compare_subsets
)

from src.data_filter import split_by_missing_columns

from src.configuration import get_dbp_data_management_config

def main():
    """
    Example workflow for data analysis.
    """

    # Define paths
    data_cfg = get_dbp_data_management_config()
    raw_file = data_cfg.get('raw') / "data.xlsx"
    cleaned_dir = data_cfg.get('cleaned')

    if not raw_file.exists():
        print(f"Error: File not found: {raw_file}")
        return

    df = load_and_clean(file_path=raw_file, drop_duplicates=True, strip_strings=True)

    df_clean, df_exemption, df_regulation = split_by_missing_columns(df)

    save_cleaned_data(df_clean,      cleaned_dir / "data_cleaned.csv")
    save_cleaned_data(df_exemption,  cleaned_dir / "data_out_exemption.csv")
    save_cleaned_data(df_regulation, cleaned_dir / "data_out_regulation.csv")

    print_basic_info(df_clean,      title="CLEANED DATA (both columns present)")
    print_basic_info(df_exemption,  title="MISSING: Granted Exemptions")
    print_basic_info(df_regulation, title="MISSING: Building regulations and requirements")

if __name__ == "__main__":
    main()
