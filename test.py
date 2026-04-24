"""
Example script demonstrating the data analysis workflow.
"""

from src.data_clean import (
    load_and_clean,
    print_basic_info
)

from src.data_analysis import (
    describe_numeric_columns,
    group_and_aggregate,
    compare_subsets
)   

from src.configuration import get_dbp_data_management_config

def main():
    """
    Example workflow for data analysis.
    """

    # Define paths
    data_cfg = get_dbp_data_management_config()
    raw_file = data_cfg.get('raw') / "data.xlsx"
    cleaned_file = data_cfg.get('cleaned')/ "data_cleaned.csv"
    
    # Load and clean data
    if not raw_file.exists():
        print(f"Error: File not found: {raw_file}")
        return
    df = load_and_clean(
        file_path=raw_file,
        output_path=cleaned_file,
        drop_duplicates=True,
        strip_strings=True
    )
    
    # Basic overview
    print_basic_info(df)

    # # Step 5: Generate summary report
    # print("\nStep 5: Generating summary report...")
    # print("-" * 60)
    # report_path = data_dir / "processed" / "summary_report.txt"
    # generate_summary_report(df, output_path=report_path)

if __name__ == "__main__":
    main()
