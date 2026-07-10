# Module 8 — Monitoring & Feedback (Track 3)

The architecture doc calls out one thing explicitly: *"are NTC borrowers
systematically scored lower due to missing-dimension penalties - check
this explicitly, it's a real risk in this design."* That's the priority
deliverable here, and it surfaced a real, previously undisclosed finding.
Read that section first.

## Run it

```bash
cd module8_monitoring
pip install pandas numpy
python run_module8.py                                    # bias check + drift self-test + recompute triggers
python run_module8.py --with-real-cohort                  # also regenerates a genuine second cohort for real drift comparison (~30-60s)
```

Produces `monitoring_output/`:

| File | Description |
|---|---|
| `bias_check.json` / `archetype_controlled_comparison.csv` / `per_borrower_counterfactual.csv` | Tier A vs Tier C comparison at 3 levels of rigor, short-history fairness check |
| `drift_selftest.json` | PSI self-test: control (no real shift) + injected shift |
| `drift_real_cohort.json` | (only with `--with-real-cohort`) PSI between this cohort and a genuinely regenerated second cohort |
| `recompute_triggers.csv` | Which borrowers need recompute and why, using Module 7's actual logged events |

## The bias check — headline finding first

**Short-history Tier A borrowers get penalized very unevenly by archetype,
and the healthy ones take the biggest hit.** This was investigated and
partially fixed — see "Update: root cause and fix" below for what changed
and, just as important, what didn't.

**Before the fix:**

| Archetype | Full-history mean | Short-history mean | Gap |
|---|---|---|---|
| Healthy | 67.08 (n=100) | 57.33 (n=19) | **-9.75** |
| Stagnant | 44.18 (n=62) | 41.17 (n=11) | -3.01 |
| Distressed | 17.25 (n=43) | 24.12 (n=9) | **+6.87** |

**After the fix (current):**

| Archetype | Full-history mean | Short-history mean | Gap |
|---|---|---|---|
| Healthy | 67.27 (n=100) | 58.09 (n=19) | **-9.18** |
| Stagnant | 44.11 (n=62) | 41.30 (n=11) | -2.81 |
| Distressed | 16.92 (n=43) | 24.12 (n=9) | **+7.20** |

**This is still the single most important result in this module, and the
honest news is the fix only moved it about half a point.** The original
diagnosis in this README ("Module 4's 50% insufficient-data discount
interacting with percentile-rank scoring") was **wrong** — see below. The
real, provable bug (Module 3's `balance_trend_pct` mechanically producing
smaller magnitudes for shorter windows, unrelated to actual health) is
fixed, and it was a genuine order-of-magnitude distortion on that one
feature. But it's one feature out of ~14, inside one dimension worth 20%
of the composite weight, so fixing it alone barely dents a gap that
turns out to be spread thinly across several other window-length-sensitive
features (`turnover_growth_rate`, `headcount_growth_rate`,
`wage_bill_growth_rate` — all ratio-based, all genuinely noisier with less
data, none of them a coding bug). Distressed short-history borrowers still
score noticeably higher than their full-history peers. **This gap is now
believed to be substantially a real information limit** (less time
observed → less trend signal → dimension scores regress toward the
population's center when percentile-ranked) **rather than a fixable
defect**, though it hasn't been proven irreducible — a wider fix would
need to touch multiple Module 3 features and possibly how Module 5
percentile-ranks borrowers with different observation windows, which is
out of scope for this pass. Flagged as unresolved, not swept under the rug.

## Update: root cause and fix

The original version of this README diagnosed the cause as "Module 4's
50% insufficient-data discount interacting with percentile-rank scoring."
That turned out to be wrong, discovered while trying to implement the fix:

**The math:** Module 4 discounts a dimension's weight by 0.5× when its
status is `insufficient_data`, then renormalizes all weights to sum to 1.
Scaling every included dimension's weight by the same constant `c` and
renormalizing gives `(w_i·c) / Σ(w_j·c) = w_i / Σw_j` — identical to not
discounting at all. All 39 short-history borrowers have GST and bank data
truncated together (Module 1 truncates both sources consistently), so
every one of their included dimensions carries the same `insufficient_data`
status — meaning the discount was mathematically inert for 100% of the
borrowers it was blamed for affecting. Verified two ways: rerunning Module
4 confirms 0 borrowers in this dataset ever land in the `discount_applied`
bucket of the new `data_confidence` field (all 39 land in
`discount_is_noop_all_dims_uniformly_thin`), and the composite scores in
this table are unchanged before vs. after Module 4's own README/code
correction — only the Module 3 fix moved them.

**The actual cause:** Module 3's `balance_trend_pct` computed a raw %
change over however much history happened to be available, not
normalized for elapsed time. Short-history borrowers' raw values were
9-45%, full-history borrowers' were 593-1868% — for the *same archetype*
— purely because a 24-month window lets the same trend compound far
longer than a 3.5-month window. Percentile-ranking that in Module 5 then
crushed short-history borrowers of every archetype toward the bottom of
this one feature's distribution. Fixed in Module 3 (see that module's
README) by switching to a time-normalized linear-trend rate.

**Why the composite-level gap barely moved:** `balance_trend_pct` is one
feature inside `liquidity_cash_flow`, which is 20% of the composite
weight. Fixing it removed a real, provable, order-of-magnitude bug, but
several *other* growth-rate features (`turnover_growth_rate`,
`headcount_growth_rate`, `wage_bill_growth_rate`) also shrink toward a
neutral value on short windows — not because of a formula defect (they're
already ratio-based, not cumulative), but because a shorter observation
window genuinely contains less trend signal. That's spread across enough
features and dimensions that no single additional fix closes the gap; it
would take a broader rework of Module 3's growth features and possibly
Module 5's percentile-ranking approach for variable-length windows.
Flagged as a real, unresolved limitation, not claimed as fixed.

## Tier A vs Tier C: three levels of rigor, because the naive comparison would mislead

**1. Raw (confounded):** Tier A mean 49.03 vs Tier C mean 50.45 — a
~1.4-point gap that mixes together "less data" with "whatever archetype
mix happened to land in each tier." Not a fair comparison on its own,
reported only for context.

**2. Archetype-controlled** (same archetype, different tier):

| Archetype | Tier A mean | Tier C mean | Gap |
|---|---|---|---|
| Healthy | 65.80 | 66.36 | -0.56 |
| Stagnant | 43.69 | 46.10 | -2.41 |
| Distressed | 18.16 | 19.59 | -1.43 |

Tier A scores modestly lower than Tier C **even for borrowers of the same
underlying health level**, across all three archetypes. Small (0.7-2.6
points) but consistent in direction — a real, if modest, systematic gap.

**3. Counterfactual reweighting test** (isolates whether the *mechanism*
of dropping operational_stability and reweighting is the cause): recompute
what Tier C borrowers would score using only the same 4 dimensions Tier A
has, with Tier A's exact weight scheme, then compare to Tier A's actual
scores:

| Archetype | Tier A actual (4-dim) | Tier C counterfactual (4-dim) | Gap |
|---|---|---|---|
| Healthy | 67.27 | 67.27 | **0.00** |
| Stagnant | 44.11 | 45.02 | -0.91 |
| Distressed | 16.92 | 19.21 | -2.29 |

**For healthy borrowers, the gap essentially disappears** once you compare
on equal footing (4 dimensions vs 4 dimensions) — Module 4's reweighting
mechanism is NOT the source of bias for healthy borrowers. But a real gap
remains for distressed and stagnant borrowers even in this controlled
comparison, meaning something *other* than the reweighting math is
driving it. The likely candidate, not yet proven: Tier A borrowers skew
younger by construction (`business_age_years` in Module 1), and business
age feeds into both the bank/GST scale parameters and indirectly into
volatility — a genuine follow-up investigation, not something this module
resolves. Flagged as an open question, not a fixed conclusion.

## Score drift (PSI)

**Self-test** (proves the detector has teeth, same pattern as Module 2's
schema validator): a random 50/50 split of the current cohort gives PSI =
0.085 ("no significant shift" — correct, there's no real difference).
Injecting a synthetic -15 point shift into half the data gives PSI = 2.88
(far past the 0.25 "significant" threshold — correctly flagged).

**Real cohort comparison** (`--with-real-cohort`): genuinely regenerates
an independent second 400-borrower cohort (different random seed, same
generator, full Module 1-5 pipeline re-run — not simulated) and computes
real PSI against it: **0.052, "no significant shift."** This is the
expected null result — two cohorts from the same unchanged generator
should look statistically similar, and they do. This validates the PSI
methodology on a real (if synthetic) before/after comparison, not just the
synthetic self-test.

PSI thresholds (< 0.10 / 0.10-0.25 / > 0.25) are a standard industry
heuristic for credit scorecard monitoring, not something derived here.

## Recompute triggers

Cross-references Module 7's actual consent-refresh log: 1 real event
found (MSME-00001, logged during Module 7's demo run), correctly flagged
as needing recompute. Staleness-based triggering (score older than 90
days) is implemented but currently inert — Module 5 doesn't yet persist a
per-run "last scored" timestamp, so there's nothing to check age against.
Flagged as not-yet-wired rather than faked with an invented date.

## Known limitations

1. **The healthy-short-history finding is now partially fixed, not fully
   resolved.** One provable bug (Module 3's `balance_trend_pct` window-
   length scaling) is fixed. The remaining ~9-point gap is believed to be
   a genuine information limit spread across several other growth-rate
   features, not a single fixable defect — see "Update: root cause and
   fix" above. Module 4's discount mechanism was investigated and ruled
   out as a cause (it's a mathematical no-op for every borrower it was
   blamed for affecting — see Module 4's README).
2. **The residual distressed/stagnant Tier A vs Tier C gap in the
   counterfactual test is unexplained** — flagged as an open question
   with a plausible but unproven hypothesis (business age correlation),
   not resolved here.
3. **Staleness checking is unwired** — see above.
4. **PSI's real-cohort test only proves the null case** (no drift when
   nothing changed) — it hasn't been tested against a genuinely different
   generator configuration (e.g. changed archetype mix), which would be a
   more convincing test that PSI catches REAL drift in this specific
   pipeline, not just synthetic shifts on the same data.
5. **The bias check only examines Tier A vs Tier C and short-history vs
   full-history** — sector, business age, and other cuts weren't checked
   and could hide their own biases.

## Files

```
module8_monitoring/
  config.py             - PSI thresholds, staleness threshold
  loader.py               - reads Module 1/4/5/7 outputs
  bias_check.py            - the priority deliverable: 3-level Tier A/C comparison + short-history fairness check
  drift.py                 - PSI computation + self-test (control + injected shift)
  cohort_b.py               - regenerates a genuine independent second cohort via subprocess (for --with-real-cohort)
  staleness.py               - recompute-trigger logic (consent-refresh integration real; staleness-by-age unwired)
  run_module8.py              - entry point
  monitoring_output/           - output (generated, not checked in by hand — rerun to regenerate)
```

Also makes `msme_data_gen/config.py`'s `RANDOM_SEED` overridable via the
`MSME_SEED` environment variable (was hardcoded to 42) - additive change
enabling `cohort_b.py`'s real second-cohort generation, doesn't change
default behavior for any other module.
