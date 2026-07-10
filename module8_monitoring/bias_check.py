"""
Bias check across segments - the architecture doc explicitly calls this
out: "are NTC borrowers systematically scored lower due to
missing-dimension penalties - check this explicitly, it's a real risk in
this design." This is the priority deliverable of Module 8, not a
checkbox afterthought.

Three separate checks, because "Tier A scores lower than Tier C" could
have three very different causes that need very different responses:

1. RAW comparison (confounded, reported for context only): does Tier A's
   unconditional mean composite score differ from Tier C's? This mixes
   together "borrowers with less data" with "whatever archetype mix
   happened to land in each tier" - not a fair comparison on its own.

2. ARCHETYPE-CONTROLLED comparison: same check, but within each hidden
   true_archetype group separately. This isolates whether Tier A
   borrowers score lower than Tier C borrowers OF THE SAME UNDERLYING
   HEALTH LEVEL - the real fairness question.

3. MECHANICAL/COUNTERFACTUAL test: Tier A borrowers never have
   operational_stability (no EPFO by construction), so Module 4
   redistributes that dimension's weight across their other 4 dimensions.
   To check whether this REWEIGHTING MECHANISM ITSELF is what's driving
   any gap (as opposed to genuinely having one fewer real signal), we
   recompute what Tier C borrowers' composite WOULD be if we dropped
   their operational_stability score and renormalized weights the exact
   same way Module 4 does for Tier A - then compare that counterfactual
   to Tier A's actual scores, archetype-by-archetype. If they land close
   together, the reweighting math is doing its job fairly; a remaining
   gap would need a different explanation.

A fourth check: within Tier A only, do the short-history (insufficient_data,
50%-discounted) borrowers score lower than full-history Tier A borrowers
of the SAME archetype - i.e. is Module 4's discount multiplier itself
penalizing thin data beyond what the borrower's true health would predict?
"""

import pandas as pd

DIMENSION_COLS_4 = [
    "liquidity_cash_flow_score", "repayment_credit_behavior_score",
    "revenue_growth_signal_score", "compliance_discipline_score",
]
WEIGHT_COLS_4 = [
    "liquidity_cash_flow_effective_weight", "repayment_credit_behavior_effective_weight",
    "revenue_growth_signal_effective_weight", "compliance_discipline_effective_weight",
]


def _merge_all(scores_df, segmentation_df, master_df, ground_truth_df):
    m = scores_df.merge(master_df[["borrower_id", "tier"]], on="borrower_id", how="left")
    m = m.merge(ground_truth_df[["borrower_id", "true_archetype", "has_short_history"]], on="borrower_id", how="left")
    m = m.merge(segmentation_df, on="borrower_id", how="left", suffixes=("", "_seg"))
    return m


def raw_and_controlled_comparison(m):
    raw = m.groupby("tier")["composite_score"].agg(["mean", "count"]).round(2)

    controlled = m.groupby(["true_archetype", "tier"])["composite_score"].agg(["mean", "count"]).round(2)
    controlled = controlled.reset_index().pivot(index="true_archetype", columns="tier", values=["mean", "count"])

    return raw, controlled


def _get_tier_a_weight_vector(m):
    """Pull the actual effective-weight vector Module 4 assigned to a
    clean (full-history, no discount) Tier A borrower - this IS the
    counterfactual weighting we want to apply to Tier C, so we reuse it
    rather than re-deriving Module 4's config independently (which would
    risk drifting out of sync with the real policy)."""
    tier_a_clean = m[(m["tier"] == "A") & (~m["has_short_history"])]
    if tier_a_clean.empty:
        return None
    row = tier_a_clean.iloc[0]
    return {col: row[col] for col in WEIGHT_COLS_4}


def counterfactual_reweighting_test(m):
    weight_vector = _get_tier_a_weight_vector(m)
    if weight_vector is None:
        return None, None

    tier_c = m[m["tier"] == "C"].copy()

    def _counterfactual(row):
        num, denom = 0.0, 0.0
        for score_col, weight_col in zip(DIMENSION_COLS_4, WEIGHT_COLS_4):
            score = row.get(score_col)
            w = weight_vector[weight_col]
            if pd.notna(score) and w:
                num += score * w
                denom += w
        return round(num / denom, 2) if denom > 0 else float("nan")

    tier_c["counterfactual_4dim_score"] = tier_c.apply(_counterfactual, axis=1)
    tier_c["actual_vs_counterfactual_delta"] = (tier_c["composite_score"] - tier_c["counterfactual_4dim_score"]).round(2)

    # Now compare Tier C's counterfactual (4-dim, Tier-A-style weighting)
    # against Tier A's ACTUAL scores, archetype by archetype - the fair
    # apples-to-apples comparison.
    tier_a_actual = m[(m["tier"] == "A") & (~m["has_short_history"])].groupby("true_archetype")["composite_score"].mean()
    tier_c_counterfactual = tier_c.groupby("true_archetype")["counterfactual_4dim_score"].mean()
    tier_c_actual = tier_c.groupby("true_archetype")["composite_score"].mean()

    comparison = pd.DataFrame({
        "tier_a_actual_4dim": tier_a_actual,
        "tier_c_counterfactual_4dim": tier_c_counterfactual,
        "tier_c_actual_5dim": tier_c_actual,
    }).round(2)
    comparison["tier_a_vs_tier_c_counterfactual_gap"] = (
        comparison["tier_a_actual_4dim"] - comparison["tier_c_counterfactual_4dim"]
    ).round(2)

    return tier_c[["borrower_id", "composite_score", "counterfactual_4dim_score", "actual_vs_counterfactual_delta"]], comparison


def short_history_fairness_check(m):
    tier_a = m[m["tier"] == "A"]
    grouped = tier_a.groupby(["true_archetype", "has_short_history"])["composite_score"].agg(["mean", "count"]).round(2)
    return grouped.reset_index()


def run_bias_check(scores_df, segmentation_df, master_df, ground_truth_df):
    m = _merge_all(scores_df, segmentation_df, master_df, ground_truth_df)

    raw, controlled = raw_and_controlled_comparison(m)
    per_borrower_counterfactual, archetype_comparison = counterfactual_reweighting_test(m)
    short_history_check = short_history_fairness_check(m)

    return {
        "raw_tier_comparison": raw,
        "archetype_controlled_comparison": controlled,
        "counterfactual_archetype_comparison": archetype_comparison,
        "per_borrower_counterfactual": per_borrower_counterfactual,
        "short_history_fairness_check": short_history_check,
    }
