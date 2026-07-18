"""
Entry point for Module 2: Data Quality & Completeness Tiering.

Run:
    python run_module2.py

Reads Module 1's data_lake/ (default: ../msme_data_gen/data_lake) and
writes quality_output/ with:
    schema_issues.csv          - real schema/referential issues found (should be empty on clean Module 1 output)
    selftest_report.csv        - proof the validator catches injected defects
    completeness_report.csv    - per-borrower per-source coverage + status
    consistency_report.csv     - GST-vs-bank ratio + consistency flag per borrower
    consistency_backtest.json  - precision/recall of the consistency flag against hidden ground truth
    submetric_availability.csv - per-borrower, per (dimension, submetric) computability (5C framework)
    quality_tier.csv           - re-derived completeness tier + EPFO reliability flag
"""

import os
import sys
import json
import pandas as pd

from config import DEFAULT_DATA_LAKE_DIR, OUTPUT_DIR
from loader import load_data_lake, load_ground_truth
from schema_checks import run_all_checks
from selftest import run_selftest
from completeness import build_completeness_report
from consistency import compute_consistency, backtest_against_ground_truth
from tiering import build_submetric_availability, build_quality_tier


def main():
    data_lake_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_LAKE_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading data lake from {data_lake_dir} ...")
    lake = load_data_lake(data_lake_dir)
    ground_truth = load_ground_truth(data_lake_dir)
    print(f"  {len(lake['master'])} borrowers, {len(lake['gst'])} GST rows, "
          f"{len(lake['bank'])} bank rows, {len(lake['epfo'])} EPFO rows")

    print("\n[1/5] Schema validation on the real data lake...")
    issues = run_all_checks(lake)
    issues.to_csv(os.path.join(OUTPUT_DIR, "schema_issues.csv"), index=False)
    print(f"  {len(issues)} issues found on Module 1's actual output")

    print("\n[2/5] Self-test: injecting known defects, confirming the validator catches them...")
    selftest_results, all_caught, _ = run_selftest(lake)
    selftest_results.to_csv(os.path.join(OUTPUT_DIR, "selftest_report.csv"), index=False)
    print(selftest_results.to_string(index=False))
    print(f"  All injected defects caught: {all_caught}")

    print("\n[3/5] Completeness per source per borrower...")
    completeness = build_completeness_report(lake)
    completeness.to_csv(os.path.join(OUTPUT_DIR, "completeness_report.csv"), index=False)
    print("  GST status:\n" + completeness["gst_status"].value_counts().to_string())
    print("  Bank status:\n" + completeness["bank_status"].value_counts().to_string())
    print("  EPFO status:\n" + completeness["epfo_status"].value_counts().to_string())

    print("\n[4/5] Cross-source consistency check (GST vs bank inflow)...")
    consistency = compute_consistency(lake)
    consistency.to_csv(os.path.join(OUTPUT_DIR, "consistency_report.csv"), index=False)
    print("  Flags:\n" + consistency["consistency_flag"].value_counts().to_string())

    backtest = backtest_against_ground_truth(consistency, ground_truth)
    with open(os.path.join(OUTPUT_DIR, "consistency_backtest.json"), "w") as f:
        json.dump(backtest, f, indent=2)
    print(f"  Backtest vs hidden ground truth: precision={backtest['precision']}, "
          f"recall={backtest['recall']} "
          f"(flagged {backtest['n_flagged']} of {backtest['n_actual_underreporters']} actual under-reporters)")

    print("\n[5/5] Submetric availability (5C framework) + quality tiering...")
    submetric_avail = build_submetric_availability(completeness)
    submetric_avail.to_csv(os.path.join(OUTPUT_DIR, "submetric_availability.csv"), index=False)
    status_cols = [c for c in submetric_avail.columns if c.endswith("_status")]
    n_not_applicable = (submetric_avail[status_cols] == "not_applicable").sum().sum()
    n_insufficient = (submetric_avail[status_cols] == "insufficient_data").sum().sum()
    n_available = (submetric_avail[status_cols] == "available").sum().sum()
    print(f"  {len(status_cols)} submetrics x {len(submetric_avail)} borrowers: "
          f"{n_available} available, {n_insufficient} insufficient_data, {n_not_applicable} not_applicable")

    quality_tier = build_quality_tier(completeness)
    quality_tier.to_csv(os.path.join(OUTPUT_DIR, "quality_tier.csv"), index=False)
    print("  Quality tier distribution:\n" + quality_tier["quality_tier"].value_counts().to_string())
    unreliable = (quality_tier["epfo_reliability_flag"] == "unreliable_despite_tier_c").sum()
    tier_c_total = (quality_tier["tier"] == "C").sum()
    print(f"  Tier C borrowers with unreliable EPFO data: {unreliable} / {tier_c_total}")

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
