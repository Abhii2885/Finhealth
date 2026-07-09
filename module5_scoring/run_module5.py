"""
Entry point for Module 5: Scoring & Aggregation Engine.

Run:
    python run_module5.py [features_dir] [segmentation_dir] [data_lake_dir]

Produces scoring_output/:
    borrower_scores.csv        - per-borrower dimension scores + composite + grade
    validation_summary.json    - composite score means by hidden archetype, ordering check
    grade_by_archetype.csv     - crosstab of grade vs hidden archetype
    consistency_penalty_audit.json - honest cost of the Module 2 consistency-flag penalty
"""

import os
import sys
import json

from config import DEFAULT_FEATURES_DIR, DEFAULT_SEGMENTATION_DIR, OUTPUT_DIR
from loader import load_features, load_segmentation, load_ground_truth
from dimension_scores import build_dimension_scores
from aggregate import build_composite
from validate import validate_composite, audit_consistency_penalty


def main():
    features_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FEATURES_DIR
    segmentation_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SEGMENTATION_DIR
    data_lake_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(__file__), "..", "msme_data_gen", "data_lake"
    )
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading features from {features_dir} ...")
    features = load_features(features_dir)
    print(f"Loading segmentation policy from {segmentation_dir} ...")
    segmentation = load_segmentation(segmentation_dir)
    print(f"Loading hidden ground truth from {data_lake_dir} ...")
    ground_truth = load_ground_truth(data_lake_dir)

    print("\nComputing per-dimension percentile-rank scores...")
    dim_scores = build_dimension_scores(features)

    feature_score_cols = [c for cols in dim_scores.attrs["feature_score_cols_by_dim"].values() for c in cols]
    feature_scores_path = os.path.join(OUTPUT_DIR, "feature_scores.csv")
    dim_scores[["borrower_id"] + feature_score_cols].to_csv(feature_scores_path, index=False)
    print(f"  per-feature percentile scores (for Module 6's top-drivers) -> {feature_scores_path}")

    print("Aggregating into composite score + grade using Module 4's weights...")
    result = build_composite(dim_scores, segmentation)

    output_cols = ["borrower_id"] + \
        [c for c in result.columns if c.endswith("_score") or c == "composite_score" or c == "grade"] + \
        ["revenue_growth_signal_consistency_penalty", "scorable", "segment_label"]
    output_cols = [c for c in dict.fromkeys(output_cols) if c in result.columns]
    scores_path = os.path.join(OUTPUT_DIR, "borrower_scores.csv")
    result[output_cols].to_csv(scores_path, index=False)
    print(f"  -> {scores_path}")

    print("\nComposite score distribution:")
    print(result["composite_score"].describe().round(2).to_string())
    print("\nGrade distribution:")
    print(result["grade"].value_counts().to_string())

    print("\nValidating against hidden true_archetype (backtest only)...")
    summary, grade_by_archetype, merged = validate_composite(result, ground_truth)
    print(json.dumps(summary, indent=2))
    grade_by_archetype.to_csv(os.path.join(OUTPUT_DIR, "grade_by_archetype.csv"))
    print("\nGrade vs archetype crosstab:")
    print(grade_by_archetype.to_string())

    with open(os.path.join(OUTPUT_DIR, "validation_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\nAuditing the honest cost of the consistency-flag penalty...")
    penalty_audit = audit_consistency_penalty(merged)
    print(json.dumps(penalty_audit, indent=2))
    with open(os.path.join(OUTPUT_DIR, "consistency_penalty_audit.json"), "w") as f:
        json.dump(penalty_audit, f, indent=2)

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
