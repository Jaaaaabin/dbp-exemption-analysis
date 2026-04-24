# Quick Reference Guide

## Project Setup Complete! ✓

Your data analysis project is ready to use. Here's what you have:

## File Structure

```
data-analysis-project/
├── data/
│   ├── raw/          → Put your Excel files here
│   └── processed/    → Cleaned data will be saved here
├── src/data_analysis_project/
│   ├── data_clean.py      → Load & clean Excel files
│   ├── data_filter.py     → Filter data by criteria
│   └── data_analysis.py   → Analyze & generate reports
├── example_workflow.py    → Full workflow example
├── test_setup.py         → Verify installation
└── README.md             → Complete documentation
```

## Installed Dependencies

- **pandas** (2.3.3) - Data manipulation
- **openpyxl** (3.1.5) - Excel file support
- **numpy** - Numerical operations (pandas dependency)

## Quick Commands

```bash
# Run test to verify setup
uv run python test_setup.py

# Run example workflow (after adding your data)
uv run python example_workflow.py

# Add new dependencies
uv add package-name

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## Your Data Analysis Workflow

### Step 1: Data Cleaning
```python
from data_analysis_project import load_and_clean

df = load_and_clean(
    "data/raw/your_file.xlsx",
    output_path="data/processed/cleaned.csv"
)
```

### Step 2: Data Filtering
```python
from data_analysis_project import filter_by_value, create_filtered_subsets

# Single filter
filtered = filter_by_value(df, 'column_name', value=100, operator='>')

# Multiple subsets
subsets = create_filtered_subsets(df, {
    'subset1': {'column': 'price', 'operator': '>', 'value': 50},
    'subset2': {'date_column': 'date', 'start_date': '2024-01-01'}
})
```

### Step 3: Data Analysis
```python
from data_analysis_project import (
    print_basic_info,
    describe_numeric_columns,
    group_and_aggregate,
    generate_summary_report
)

# Overview
print_basic_info(df)

# Statistics
stats = describe_numeric_columns(df)

# Grouping
grouped = group_and_aggregate(
    df,
    group_by='category',
    agg_dict={'sales': ['sum', 'mean']}
)

# Full report
generate_summary_report(df, 'data/processed/report.txt')
```

## Available Filter Functions

- `filter_by_value()` - Single column filter
- `filter_by_multiple_conditions()` - Multiple AND conditions
- `filter_by_date_range()` - Date range filter
- `filter_by_string_pattern()` - Text pattern matching
- `filter_by_numeric_range()` - Number range filter
- `filter_by_custom_function()` - Custom logic
- `create_filtered_subsets()` - Create multiple subsets at once

## Available Analysis Functions

- `print_basic_info()` - Data overview
- `describe_numeric_columns()` - Numeric statistics
- `describe_categorical_columns()` - Category counts
- `analyze_correlations()` - Correlation analysis
- `group_and_aggregate()` - Group and aggregate data
- `compare_subsets()` - Compare filtered subsets
- `detect_outliers()` - Find outliers
- `generate_summary_report()` - Full text report

## Next Steps

1. **Add your data**: Place Excel file(s) in `data/raw/`
2. **Customize**: Edit `example_workflow.py` for your needs
3. **Run**: Execute with `uv run python example_workflow.py`
4. **Expand**: Add more analysis scripts as needed

## Adding More Libraries

Common additions for data analysis:

```bash
# Visualization
uv add matplotlib seaborn plotly

# Statistics
uv add scipy statsmodels scikit-learn

# Data validation
uv add great-expectations pandera
```

## Tips

- Never modify files in `data/raw/` - keep originals safe
- Use descriptive names for filtered subsets
- Save intermediate results in `data/processed/`
- Document your analysis steps in your scripts
- Use `print_basic_info()` to understand your data first

## Getting Help

- Check `README.md` for detailed documentation
- Look at `example_workflow.py` for patterns
- Read function docstrings: `help(function_name)`
- View module code in `src/data_analysis_project/`

---
Project created with UV - Fast Python package management
