"""
Entry point for Module 9: ML Layer (Champion-Challenger).

Run:
    python run_module9.py [features_dir] [scoring_dir] [data_lake_dir]

Produces ml_output/:
    anomaly_scores.csv           - Isolation Forest anomaly_score (0-100) + is_anomaly per borrower
    challenger_scores.csv        - Gradient Boosting challenger_score (0-100) per borrower
    challenger_holdout_eval.json - held-out train/test MAE, R2, permutation feature importance
    champion_challenger.csv      - champion vs challenger per borrower, divergence, review flag
    validation_summary.json      - challenger ordering check + anomaly-rate breakdown vs hidden true_archetype
"""

import sys
import os
import json

from config import DEFAULT_FEATURES_DIR, DEFAULT_SCORING_DIR, DEFAULT_DATA_LAKE_DIR, OUTPUT_DIR, \
    ROBUSTNESS_CHECK_FEATURE_COLUMNS
from loader import load_features, load_champion_scores, load_ground_truth
from anomaly_detection import build_anomaly_scores
from challenger_model import evaluate_holdout, build_challenger_scores
from compare import build_comparison, validate_challenger


def main():
    features_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FEATURES_DIR
    scoring_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SCORING_DIR
    data_lake_dir = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_DATA_LAKE_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading Module 3 features from {features_dir} ...")
    features = load_features(features_dir)
    print(f"Loading Module 5 champion scores from {scoring_dir} ...")
    champion = load_champion_scores(scoring_dir)
    print(f"Loading hidden ground truth (repayment-outcome proxy) from {data_lake_dir} ...")
    ground_truth = load_ground_truth(data_lake_dir)

    print("\n[1/4] Isolation Forest anomaly detection...")
    anomaly = build_anomaly_scores(features)
    anomaly.to_csv(os.path.join(OUTPUT_DIR, "anomaly_scores.csv"), index=False)
    print(f"  {int(anomaly['is_anomaly'].sum())} of {len(anomaly)} borrowers flagged as anomalous "
          f"(top {anomaly['is_anomaly'].mean()*100:.1f}%)")

    print("\n[2/4] Gradient Boosting challenger - held-out evaluation (full feature set)...")
    holdout = evaluate_holdout(features, ground_truth)
    print(json.dumps({k: v for k, v in holdout.items() if k != "feature_importance"}, indent=2))
    print("  Top 5 features by permutation importance (held-out test set):")
    for row in holdout["feature_importance"][:5]:
        print(f"    {row['feature']}: {row['importance']}")
    if holdout["test_r2"] >= 0.999:
        print("  NOTE: R2=1.0 here reflects a Module 1 synthetic-data artifact "
              "(projected_revenue_growth_rate has zero overlap between archetype groups), "
              "not an unrealistically perfect model - see config.ROBUSTNESS_CHECK_FEATURE_COLUMNS. "
              "The robustness run below excludes that feature.")
    with open(os.path.join(OUTPUT_DIR, "challenger_holdout_eval.json"), "w") as f:
        json.dump(holdout, f, indent=2)

    print("\n  Robustness check: held-out evaluation EXCLUDING projected_revenue_growth_rate...")
    holdout_robust = evaluate_holdout(features, ground_truth, feature_columns=ROBUSTNESS_CHECK_FEATURE_COLUMNS)
    print(json.dumps({k: v for k, v in holdout_robust.items() if k != "feature_importance"}, indent=2))
    print("  Top 5 features by permutation importance (held-out test set, robustness run):")
    for row in holdout_robust["feature_importance"][:5]:
        print(f"    {row['feature']}: {row['importance']}")
    with open(os.path.join(OUTPUT_DIR, "challenger_holdout_eval_robustness.json"), "w") as f:
        json.dump(holdout_robust, f, indent=2)

    print("\n  Refitting challenger on the full population (all features) for deployment scores...")
    challenger = build_challenger_scores(features, ground_truth)
    challenger.to_csv(os.path.join(OUTPUT_DIR, "challenger_scores.csv"), index=False)

    print("\n[3/4] Champion vs challenger comparison...")
    comparison = build_comparison(champion, challenger, anomaly)
    comparison.to_csv(os.path.join(OUTPUT_DIR, "champion_challenger.csv"), index=False)
    print(f"  {int(comparison['flagged_for_review'].sum())} of {len(comparison)} borrowers flagged for review "
          f"(|divergence| >= threshold)")
    print("  Largest divergences:")
    print(comparison.head(5)[["borrower_id", "champion_score", "challenger_score", "divergence", "is_anomaly"]].to_string(index=False))

    print("\n[4/4] Validating challenger against hidden true_archetype (backtest only)...")
    validation = validate_challenger(comparison, ground_truth)
    print(json.dumps(validation, indent=2))
    with open(os.path.join(OUTPUT_DIR, "validation_summary.json"), "w") as f:
        json.dump(validation, f, indent=2)

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")
    print("Reminder: the champion (Module 5 composite_score) remains the score of record. "
          "This module monitors a challenger in parallel - it does not override anything.")


if __name__ == "__main__":
    main()
