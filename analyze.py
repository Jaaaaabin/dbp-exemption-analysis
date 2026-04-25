"""
Analysis script. Point JSON_FILE at one of the outputs from extract.py, then run.
Records are enriched via text_parser before analysis, so structured fields
(exemption_primary_type, plan_type, zone_code, …) are available alongside
the original numeric columns.
"""
import json
from pathlib import Path

from src.text_parser import enrich_json
from src.visualize import plot_all
from src.data_analysis import (
    describe_numeric_columns,
    describe_categorical_columns,
    analyze_correlations,
    group_and_aggregate,
    compare_subsets,
    detect_outliers,
)

# ── Select which JSON to analyse ─────────────────────────────────────────────
JSON_FILE = Path("data/cleaned/data_cleaned.json")
# JSON_FILE = Path("data/cleaned/data_out_exemption.json")
# JSON_FILE = Path("data/cleaned/data_out_regulation.json")
# ─────────────────────────────────────────────────────────────────────────────

# Structured fields added by enrich_json (short, categorical, useful to group by):
#   exemption_primary_type, exemption_types, plan_type, plan_name,
#   zone_code, legal_ordinance, document_count_parsed, requirement_count


def main():
    print(f"\nAnalysing: {JSON_FILE}\n")

    # Enrich once; save for inspection and pass to all analysis functions
    records = enrich_json(JSON_FILE)
    enriched_path = JSON_FILE.parent / (JSON_FILE.stem + "_enriched.json")
    with open(enriched_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False, default=str)
    print(f"Saved enriched records to {enriched_path}\n")

    print("=" * 60)
    print("NUMERIC SUMMARY")
    print("=" * 60)
    print(describe_numeric_columns(records))

    print("\n" + "=" * 60)
    print("CORRELATIONS  (|r| >= 0.5)")
    print("=" * 60)
    print(analyze_correlations(records))

    print("\n" + "=" * 60)
    print("DECISIONS BY PERMIT TYPE")
    print("=" * 60)
    print(group_and_aggregate(
        records,
        group_by="permit_type",
        agg_dict={"time_for_decision_months": ["mean", "median", "count"]},
    ))

    print("\n" + "=" * 60)
    print("DECISIONS BY EXEMPTION TYPE")
    print("=" * 60)
    print(group_and_aggregate(
        records,
        group_by="exemption_primary_type",
        agg_dict={"time_for_decision_months": ["mean", "median", "count"],
                  "number_of_exemptions":     ["mean"]},
    ))

    print("\n" + "=" * 60)
    print("DECISIONS BY PLAN TYPE  (Bebauungsplan vs Baustufenplan)")
    print("=" * 60)
    print(group_and_aggregate(
        records,
        group_by="plan_type",
        agg_dict={"time_for_decision_months": ["mean", "median", "count"]},
    ))

    print("\n" + "=" * 60)
    print("DECISIONS BY PLAN REFERENCE TYPE  (development vs construction)")
    print("=" * 60)
    print(group_and_aggregate(
        records,
        group_by="plan_primary_type",
        agg_dict={"time_for_decision_months": ["mean", "median", "count"]},
    ))

    print("\n" + "=" * 60)
    print("DECISIONS BY ISSUING AUTHORITY")
    print("=" * 60)
    print(group_and_aggregate(
        records,
        group_by="issuing_authority",
        agg_dict={"time_for_decision_months": ["mean", "count"]},
    ))

    print("\n" + "=" * 60)
    print("MEAN DECISION TIME ACROSS ALL THREE SUBSETS")
    print("=" * 60)
    print(compare_subsets(
        {
            "complete":            Path("data/cleaned/data_cleaned.json"),
            "missing_exemptions":  Path("data/cleaned/data_out_exemption.json"),
            "missing_regulations": Path("data/cleaned/data_out_regulation.json"),
        },
        metric_column="time_for_decision_months",
        operation="mean",
    ))

    print("\n" + "=" * 60)
    print("OUTLIERS — time_for_decision_months  (IQR)")
    print("=" * 60)
    outliers = detect_outliers(records, column="time_for_decision_months")
    if not outliers.empty:
        print(outliers[["request_id", "permit_type", "exemption_primary_type",
                         "time_for_decision_months"]])

    print("\n" + "=" * 60)
    print("CATEGORICAL COUNTS  (parsed / structured fields only)")
    print("=" * 60)
    structured_cols = [
        "exemption_primary_type", "plan_type", "plan_primary_type",
        "legal_ordinance", "permit_type", "issuing_authority", "type_of_construction",
    ]
    for col, counts in describe_categorical_columns(records, top_n=10).items():
        if col in structured_cols:
            print(f"\n  {col}:")
            print(counts.to_string(index=True))

    print("\n" + "=" * 60)
    print("PLOTS")
    print("=" * 60)
    plot_all(records, output_dir="res/figures")


if __name__ == "__main__":
    main()
