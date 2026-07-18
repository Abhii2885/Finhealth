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

3. MECHANICAL/COUNTERFACTUAL test - PARKED as of the 5C restructure (v3),
   not computed. Its entire premise was that Tier A borrowers
   DETERMINISTICALLY lack one whole dimension (operational_stability, no
   EPFO by construction), which made "recompute Tier C with Tier A's
   4-dimension weight scheme" a well-defined counterfactual. Under the 5C
   framework, no single C is deterministically and exclusively missing for
   Tier A - every new gating flag (balance_sheet_available,
   has_bureau_record, has_existing_loan, has_collateral) is TIER-
   CONDITIONED but probabilistic (see module1_data_ingestion/config.py's
   *_PROB_BY_TIER dicts), deliberately chosen that way so this bias check
   would have a genuine signal to find rather than a rigged mechanical
   comparison. Redesigning this test's methodology for the new structure
   is out of scope for the 5C restructure itself - see
   counterfactual_reweighting_test()'s docstring for what a real fix would
   need. Shipping a stale comparison against removed dimension names would
   be worse than flagging it as parked.

A fourth check (UNCHANGED, still fully computed): within Tier A only, do
the short-history (insufficient_data, discounted) borrowers score lower
than full-history Tier A borrowers of the SAME archetype - i.e. is Module
4's discount multiplier itself penalizing thin data beyond what the
borrower's true health would predict?
"""

import pandas as pd


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


def counterfactual_reweighting_test(m):
    """
    PARKED (v3, 5C restructure) - returns a status marker, not a
    computation. See this module's docstring for why the old mechanism
    (deterministic Tier A vs Tier C dimension gap) has no clean analogue
    under the 5C framework.

    What a real fix would need: a NEW attribute that IS deterministically
    tied to tier (the way has_epfo used to be), so a well-defined
    "recompute the other tier as if they had this borrower's missing-C
    pattern" counterfactual exists again. None of the 5C gating flags are
    deterministic by tier today - a deliberate choice (see
    module1_data_ingestion/config.py) so this bias check has a genuine
    signal to find. Retargeting this test to a specific new attribute is a
    product decision for a future pass, not something this restructure
    should silently decide.
    """
    return {
        "status": "parked",
        "reason": "No 5C submetric is deterministically tied to tier the way EPFO/"
                  "operational_stability used to be for Tier A - see bias_check.py's "
                  "module docstring and this function's docstring for the full explanation.",
    }, None


def short_history_fairness_check(m):
    tier_a = m[m["tier"] == "A"]
    grouped = tier_a.groupby(["true_archetype", "has_short_history"])["composite_score"].agg(["mean", "count"]).round(2)
    return grouped.reset_index()


def run_bias_check(scores_df, segmentation_df, master_df, ground_truth_df):
    m = _merge_all(scores_df, segmentation_df, master_df, ground_truth_df)

    raw, controlled = raw_and_controlled_comparison(m)
    counterfactual_status, archetype_comparison = counterfactual_reweighting_test(m)
    short_history_check = short_history_fairness_check(m)

    return {
        "raw_tier_comparison": raw,
        "archetype_controlled_comparison": controlled,
        "counterfactual_archetype_comparison": archetype_comparison,  # None - see counterfactual_status
        "counterfactual_status": counterfactual_status,
        "short_history_fairness_check": short_history_check,
    }
