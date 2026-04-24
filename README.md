# Data Analysis Project

A Python project for analyzing Excel data using pandas, built with UV for dependency management.

## Project Structure

```
data-analysis-project/
├── data/
│   ├── raw/              # Place your Excel files here
│   └── processed/        # Cleaned and processed data
├── src/
│   └── data_analysis_project/
│       ├── __init__.py
│       ├── data_clean.py     # Data loading and cleaning
│       ├── data_filter.py    # Data filtering functions
│       └── data_analysis.py  # Analysis and reporting
├── example_workflow.py   # Example usage script
├── pyproject.toml        # Project configuration
└── README.md            # This file
```

## Setup

This project uses [UV](https://github.com/astral-sh/uv) for fast Python package management.

### Prerequisites
- UV installed on your system
- Python 3.12+

### Installation

1. The project is already initialized with UV
2. Dependencies are already installed in the virtual environment

### Activate the virtual environment

```bash
# On Linux/Mac
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

Or use UV to run commands directly:
```bash
uv run python example_workflow.py
```

## Workflow

### 1. Data Cleaning (`data_clean.py`)

Load and clean Excel files:

```python
from data_analysis_project import load_and_clean

df = load_and_clean(
    file_path="data/raw/your_file.xlsx",
    output_path="data/processed/cleaned_data.csv",
    drop_duplicates=True,
    strip_strings=True
)
```

### 2. Data Filtering (`data_filter.py`)

Create filtered subsets based on criteria:

```python
from data_analysis_project import filter_by_value, filter_by_numeric_range

# Filter by single value
high_value = filter_by_value(df, column='price', value=100, operator='>')

# Filter by numeric range
medium_range = filter_by_numeric_range(df, column='price', min_value=50, max_value=100)

# Create multiple subsets at once
from data_analysis_project import create_filtered_subsets

subsets = create_filtered_subsets(df, {
    'high_value': {'column': 'price', 'operator': '>', 'value': 100},
    'recent': {'date_column': 'date', 'start_date': '2024-01-01'}
})
```

### 3. Data Analysis (`data_analysis.py`)

Analyze your data:

```python
from data_analysis_project import (
    print_basic_info,
    describe_numeric_columns,
    group_and_aggregate,
    generate_summary_report
)

# Print overview
print_basic_info(df)

# Describe numeric columns
print(describe_numeric_columns(df))

# Group and aggregate
grouped = group_and_aggregate(
    df,
    group_by='category',
    agg_dict={'price': ['mean', 'sum'], 'quantity': 'count'}
)

# Generate full report
generate_summary_report(df, output_path='data/processed/report.txt')
```

## Quick Start

1. Place your Excel file in `data/raw/` directory:
   ```bash
   cp your_file.xlsx data/raw/example_data.xlsx
   ```

2. Run the example workflow:
   ```bash
   uv run python example_workflow.py
   ```

3. Customize the example workflow or create your own analysis scripts

## Dependencies

- **pandas**: Data manipulation and analysis
- **openpyxl**: Excel file reading/writing

All dependencies are managed through UV and specified in `pyproject.toml`.

## Adding New Dependencies

To add new packages:

```bash
uv add package-name
```

For example, to add matplotlib for visualizations:
```bash
uv add matplotlib
```

## Development Tips

- Keep raw data in `data/raw/` (never modify these files)
- Save processed data in `data/processed/`
- Create analysis scripts in the project root
- Import functions from the package: `from data_analysis_project import ...`

## Example Analysis Flow

```python
from data_analysis_project import *

# 1. Load and clean
df = load_and_clean("data/raw/sales.xlsx")

# 2. Create subsets
high_value_customers = filter_by_value(df, 'total_spend', 1000, '>')
recent_sales = filter_by_date_range(df, 'date', start_date='2024-01-01')

# 3. Analyze
print_basic_info(df)
summary = describe_numeric_columns(df)
grouped = group_and_aggregate(df, 'region', {'sales': ['sum', 'mean']})

# 4. Compare subsets
comparison = compare_subsets(
    {'high_value': high_value_customers, 'recent': recent_sales},
    'sales',
    'mean'
)
print(comparison)
```

## License

MIT
