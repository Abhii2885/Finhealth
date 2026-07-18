"""
Synthetic loan-application record - the one field this generator produces
as a stand-in for a real future user input or PDF-extracted value
(projected_revenue_next_year_inr), per the 5C Capacity requirement.

Every borrower gets exactly one row (always known, unlike the gated
sources above - an applicant always states a projection, whether or not
it turns out to be reliable).

Deliberate archetype-conditioned optimism bias: healthy borrowers project
close to their true trend; distressed borrowers project MORE optimistically
than their true trend would suggest (a real, disclosed pattern in this
generator, not a bug) - real applicants tend to over-project, especially
when struggling, so projected_revenue_growth_rate should be treated as a
lower-trust signal than its stated priority order implies. Module 3/5
should not treat this figure as ground truth.

Anchored to the borrower's ACTUAL realized last-12-months turnover (from
the already-generated, already-truncated GST/self-declared series), not
an independent re-derivation of the archetype's growth trend - an earlier
version tried to approximate "current turnover" by compounding
true_monthly_turnover_base_inr forward deterministically, but the real
generator is a NOISY random walk (gst_source.py's growth_shock), and
higher-volatility archetypes (distressed, noise_sd=0.14) drift meaningfully
below what a deterministic compounding formula predicts (variance drag).
Anchoring to the real realized number sidesteps needing to reverse-engineer
that noise process. This is why run_generate.py generates and truncates
GST/self-declared turnover BEFORE calling this module.
"""

import pandas as pd
from config import rng, OBS_END_DATE

# Multiplier applied to the archetype's TRUE annualized growth trend to get
# the borrower's PROJECTED growth - >1.0 means over-optimistic relative to
# their own true trajectory.
OPTIMISM_MULTIPLIER_BY_ARCHETYPE = {"healthy": 1.05, "stagnant": 1.25, "distressed": 2.2}
TRUE_ANNUAL_GROWTH_BY_ARCHETYPE = {"healthy": 0.12, "stagnant": 0.01, "distressed": -0.19}
PROJECTION_NOISE_SD = 0.08


def _last_12_turnover_lookup(gst_df, self_declared_df):
    gst_part = gst_df[["borrower_id", "period", "declared_turnover_inr"]].rename(
        columns={"declared_turnover_inr": "turnover_inr"}
    )
    if len(self_declared_df):
        sdt_part = self_declared_df[["borrower_id", "period", "self_declared_turnover_inr"]].rename(
            columns={"self_declared_turnover_inr": "turnover_inr"}
        )
        unified = pd.concat([gst_part, sdt_part], ignore_index=True)
    else:
        unified = gst_part

    lookup = {}
    for bid, g in unified.groupby("borrower_id"):
        last12 = g.sort_values("period").tail(12)
        lookup[bid] = last12["turnover_inr"].sum()
    return lookup


def generate_loan_applications(internal_borrowers, gst_df, self_declared_df):
    rows = []
    submitted_at = pd.Timestamp(OBS_END_DATE)
    last12_lookup = _last_12_turnover_lookup(gst_df, self_declared_df)

    for _, b in internal_borrowers.iterrows():
        archetype = b["true_archetype"]
        true_growth = TRUE_ANNUAL_GROWTH_BY_ARCHETYPE[archetype]
        optimism = OPTIMISM_MULTIPLIER_BY_ARCHETYPE[archetype]

        # For distressed (negative true growth), an optimism multiplier
        # applied directly would make the projection MORE negative - flip
        # sign handling so "optimistic" always means "better than reality".
        if true_growth >= 0:
            projected_growth = true_growth * optimism
        else:
            projected_growth = true_growth / optimism

        projected_growth *= (1 + rng.normal(0, PROJECTION_NOISE_SD))
        current_annual_turnover = last12_lookup.get(
            b["borrower_id"], b["true_monthly_turnover_base_inr"] * 12
        )
        projected_revenue = round(current_annual_turnover * (1 + projected_growth), 2)

        rows.append({
            "borrower_id": b["borrower_id"],
            "projected_revenue_next_year_inr": max(projected_revenue, 0),
            "submitted_at": submitted_at.isoformat(),
        })

    return pd.DataFrame(rows)
