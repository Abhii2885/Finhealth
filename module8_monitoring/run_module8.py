"""
Entry point for Module 8: Monitoring & Feedback.

Run:
    python run_module8.py [scoring_dir] [segmentation_dir] [data_lake_dir] [integration_dir]
    python run_module8.py --with-real-cohort   # also generates a genuine second cohort (slower, ~30-60s)

Produces monitoring_output/:
    bias_check.json           - Tier A vs Tier C comparison (raw, archetype-controlled, counterfactual reweighting), short-history fairness check
    drift_selftest.json       - PSI self-test (control + injected shift)
    drift_real_cohort.json    - (only with --with-real-cohort) PSI between this cohort and a genuinely regenerated second cohort
    recompute_triggers.csv    - which borrowers need recompute and why
"""

import sys
import os
import json

from config import DEFAULT_SCORING_DIR, DEFAULT_SEGMENTATION_DIR, DEFAULT_DATA_LAKE_DIR, DEFAULT_INTEGRATION_DIR, OUTPUT_DIR
from loader import load_scores, load_segmentation, load_master, load_ground_truth, load_consent_refresh_log
from bias_check import run_bias_check
from drift import run_drift_selftest, compute_psi, classify_psi
from staleness import check_recompute_needed


def _df_to_jsonable(df):
    return json.loads(df.reset_index().to_json(orient="records"))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    with_real_cohort = "--with-real-cohort" in sys.argv

    scoring_dir = args[0] if len(args) > 0 else DEFAULT_SCORING_DIR
    segmentation_dir = args[1] if len(args) > 1 else DEFAULT_SEGMENTATION_DIR
    data_lake_dir = args[2] if len(args) > 2 else DEFAULT_DATA_LAKE_DIR
    integration_dir = args[3] if len(args) > 3 else DEFAULT_INTEGRATION_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading Module 1/4/5/7 outputs...")
    scores = load_scores(scoring_dir)
    segmentation = load_segmentation(segmentation_dir)
    master = load_master(data_lake_dir)
    ground_truth = load_ground_truth(data_lake_dir)
    consent_events = load_consent_refresh_log(integration_dir)

    print("\n[1/3] Bias check across segments (priority - see README)...")
    bias_results = run_bias_check(scores, segmentation, master, ground_truth)
    print("\nRaw (confounded) Tier A vs Tier C comparison:")
    print(bias_results["raw_tier_comparison"].to_string())
    print("\nArchetype-controlled comparison:")
    print(bias_results["archetype_controlled_comparison"].to_string())
    print("\nCounterfactual reweighting test (Tier A actual vs Tier C recomputed with Tier A's 4-dim weights):")
    print(bias_results["counterfactual_archetype_comparison"].to_string())
    print("\nShort-history fairness check (within Tier A):")
    print(bias_results["short_history_fairness_check"].to_string())

    bias_json = {
        "raw_tier_comparison": _df_to_jsonable(bias_results["raw_tier_comparison"]),
        "counterfactual_archetype_comparison": _df_to_jsonable(bias_results["counterfactual_archetype_comparison"]),
        "short_history_fairness_check": _df_to_jsonable(bias_results["short_history_fairness_check"]),
    }
    with open(os.path.join(OUTPUT_DIR, "bias_check.json"), "w") as f:
        json.dump(bias_json, f, indent=2, default=str)
    bias_results["archetype_controlled_comparison"].to_csv(os.path.join(OUTPUT_DIR, "archetype_controlled_comparison.csv"))
    bias_results["per_borrower_counterfactual"].to_csv(os.path.join(OUTPUT_DIR, "per_borrower_counterfactual.csv"), index=False)

    print("\n[2/3] Drift self-test (PSI control + injected shift)...")
    selftest = run_drift_selftest(scores)
    print(json.dumps(selftest, indent=2))
    with open(os.path.join(OUTPUT_DIR, "drift_selftest.json"), "w") as f:
        json.dump(selftest, f, indent=2)

    if with_real_cohort:
        print("\n  Generating a genuinely independent second cohort (different seed) for a real drift comparison...")
        from cohort_b import generate_cohort_b_scores
        cohort_b_scores, _ = generate_cohort_b_scores(seed=43)
        real_psi = compute_psi(scores["composite_score"], cohort_b_scores["composite_score"])
        real_drift_result = {
            "cohort_a_n": int(scores["composite_score"].notna().sum()),
            "cohort_b_n": int(cohort_b_scores["composite_score"].notna().sum()),
            "cohort_a_mean": round(scores["composite_score"].mean(), 2),
            "cohort_b_mean": round(cohort_b_scores["composite_score"].mean(), 2),
            "psi": real_psi,
            "classification": classify_psi(real_psi),
        }
        print(json.dumps(real_drift_result, indent=2))
        with open(os.path.join(OUTPUT_DIR, "drift_real_cohort.json"), "w") as f:
            json.dump(real_drift_result, f, indent=2)

    print("\n[3/3] Recompute triggers (staleness + pending consent-refresh events)...")
    print(f"  {len(consent_events)} consent-refresh event(s) found in Module 7's demo log")
    triggers = check_recompute_needed(scores["borrower_id"].tolist(), consent_events)
    import pandas as pd
    triggers_df = pd.DataFrame(triggers)
    triggers_df.to_csv(os.path.join(OUTPUT_DIR, "recompute_triggers.csv"), index=False)
    n_flagged = triggers_df["needs_recompute"].sum()
    print(f"  {n_flagged} borrower(s) flagged for recompute:")
    print(triggers_df[triggers_df["needs_recompute"]].to_string(index=False))

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
