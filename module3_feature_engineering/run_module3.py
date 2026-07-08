"""
Entry point for Module 3: Dimension Feature Engineering.

Run:
    python run_module3.py [data_lake_dir] [quality_output_dir]

Reads Module 1's data_lake and Module 2's quality_output (defaults assume
sibling folders), writes features_output/ with:
    borrower_features.csv   - one row per borrower, all dimension features + Module 2 availability status
    feature_validation.csv  - backtest of each feature's direction against the hidden true_archetype
    excluded_dimensions.csv - manifest of dimensions this prototype cannot compute at all
"""

import os
import sys
import pandas as pd

from config import DEFAULT_DATA_LAKE_DIR, DEFAULT_QUALITY_DIR, OUTPUT_DIR, NOT_COMPUTABLE_DIMENSIONS, UNAVAILABLE_SUBFEATURES
from loader import load_data_lake, load_ground_truth, load_quality_outputs
from build_features import build_all_features
from validate import validate_features


def main():
    data_lake_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_LAKE_DIR
    quality_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_QUALITY_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading data lake from {data_lake_dir} ...")
    lake = load_data_lake(data_lake_dir)
    ground_truth = load_ground_truth(data_lake_dir)

    print(f"Loading Module 2 quality outputs from {quality_dir} ...")
    quality = load_quality_outputs(quality_dir)

    print("\nBuilding features per dimension...")
    features = build_all_features(lake, quality)
    features_path = os.path.join(OUTPUT_DIR, "borrower_features.csv")
    features.to_csv(features_path, index=False)
    print(f"  {len(features)} borrowers x {len(features.columns)} columns -> {features_path}")

    null_counts = features.isna().sum()
    print("\nNull counts by column (expected: >0 for EPFO-derived columns on Tier A, "
          "and for bureau/utility/limit sub-features on everyone):")
    print(null_counts[null_counts > 0].to_string())

    print("\nValidating features against hidden true_archetype (backtest only, not used as input)...")
    validation = validate_features(features, ground_truth)
    validation.to_csv(os.path.join(OUTPUT_DIR, "feature_validation.csv"), index=False)
    print(validation.to_string(index=False))
    n_correct = validation["direction_correct"].sum()
    n_checked = validation["direction_correct"].notna().sum()
    print(f"\n{n_correct}/{n_checked} features show the expected healthy > stagnant > distressed "
          f"(or reverse) ordering.")

    excluded_rows = []
    for dim in NOT_COMPUTABLE_DIMENSIONS:
        excluded_rows.append({"dimension_or_subfeature": dim, "reason": "no Module 1 data source exists for this at all"})
    for dim, subfeatures in UNAVAILABLE_SUBFEATURES.items():
        for sf in subfeatures:
            excluded_rows.append({"dimension_or_subfeature": f"{dim}.{sf}", "reason": "no Module 1 data source exists for this sub-feature"})
    excluded_df = pd.DataFrame(excluded_rows)
    excluded_df.to_csv(os.path.join(OUTPUT_DIR, "excluded_dimensions.csv"), index=False)
    print(f"\n{len(excluded_df)} dimensions/sub-features excluded entirely - see excluded_dimensions.csv")

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
