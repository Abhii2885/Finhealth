"""
Entry point for Module 6: Explainability & Visualization Layer.

Run:
    python run_module6.py [data_lake_dir] [features_dir] [scoring_dir] [segmentation_dir]

Produces explainability_output/:
    top_drivers.csv          - per-borrower, per-dimension top positive/negative driver feature
    trend.csv                - per-borrower trend_indicator at 4 checkpoints (25/50/75/100% of observed history)
    trend_validation.json    - trend backtest against hidden true_archetype
    dashboard.html            - standalone interactive radar chart + drivers + trend dashboard (all data embedded)
"""

import os
import sys
import json

from config import DEFAULT_DATA_LAKE_DIR, DEFAULT_FEATURES_DIR, DEFAULT_SCORING_DIR, DEFAULT_SEGMENTATION_DIR, \
    DEFAULT_ML_DIR, OUTPUT_DIR
from loader import load_scores, load_feature_scores, load_segmentation, load_features, load_raw_lake, \
    load_ground_truth, load_ml_outputs
from drivers import build_drivers
from trend import build_trend
from validate import validate_trend
from dashboard import build_dashboard


def main():
    data_lake_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_LAKE_DIR
    features_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_FEATURES_DIR
    scoring_dir = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SCORING_DIR
    segmentation_dir = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_SEGMENTATION_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading Module 5 scores + feature scores...")
    scores = load_scores(scoring_dir)
    feature_scores = load_feature_scores(scoring_dir)
    print("Loading Module 3 raw features (for the scorecard's Actual Value column)...")
    features = load_features(features_dir)
    print("Loading Module 4 segmentation...")
    segmentation = load_segmentation(segmentation_dir)
    print("Loading Module 1 raw data lake (for trend checkpoints + as-of periods)...")
    lake = load_raw_lake(data_lake_dir)
    ground_truth = load_ground_truth(data_lake_dir)
    print("Loading Module 9 ML outputs (optional - dashboard degrades gracefully without them)...")
    ml_df, ml_holdout_eval = load_ml_outputs(DEFAULT_ML_DIR)
    if ml_df is not None:
        print(f"  Found champion-challenger data for {len(ml_df)} borrowers"
              f" ({int(ml_df['flagged_for_review'].sum())} flagged for review, {int(ml_df['is_anomaly'].sum())} anomalous)")
    else:
        print("  Not found - ML card will show 'ML layer not run'")

    print("\nBuilding top-drivers explainability...")
    drivers = build_drivers(feature_scores)
    drivers_path = os.path.join(OUTPUT_DIR, "top_drivers.csv")
    drivers.to_csv(drivers_path, index=False)
    print(f"  -> {drivers_path}")

    print("\nBuilding trend view (25/50/75/100% of observed history, per-borrower)...")
    trend = build_trend(lake)
    trend_path = os.path.join(OUTPUT_DIR, "trend.csv")
    trend.to_csv(trend_path, index=False)
    print(f"  -> {trend_path}")

    print("\nValidating trend against hidden true_archetype...")
    trend_validation = validate_trend(trend, ground_truth)
    print(json.dumps(trend_validation, indent=2, default=str))
    with open(os.path.join(OUTPUT_DIR, "trend_validation.json"), "w") as f:
        json.dump(trend_validation, f, indent=2, default=str)

    print("\nBuilding standalone HTML dashboard (5C scorecard + radar/bar/donut/gauge/waterfall + drivers + trend)...")
    dashboard_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    build_dashboard(scores, segmentation, drivers, trend, feature_scores, features, lake["master"], lake, dashboard_path,
                    ml_df=ml_df, ml_holdout_eval=ml_holdout_eval)
    print(f"  -> {dashboard_path}")

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
