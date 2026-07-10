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
and the healthy ones take the biggest hit:**

| Archetype | Full-history mean | Short-history mean | Gap |
|---|---|---|---|
| Healthy | 67.08 (n=100) | 57.33 (n=19) | **-9.75** |
| Stagnant | 44.18 (n=62) | 41.17 (n=11) | -3.01 |
| Distressed | 17.25 (n=43) | 24.12 (n=9) | **+6.87** |

**This is the single most important result in this module.** A genuinely
healthy MSME with only 3.5-11 months of track record — exactly the
"credit-invisible but creditworthy" borrower this whole project exists to
serve — scores nearly 10 points lower than an equally healthy business
with a full 24-month history, purely because of Module 4's 50%
insufficient-data discount interacting with percentile-rank scoring.
Meanwhile short-history *distressed* borrowers score **higher**, not
lower, than their full-history peers — the discount doesn't uniformly
push scores down, it compresses everyone's percentile rank toward the
middle of the distribution, which specifically hurts borrowers who would
otherwise rank near the top. This is exactly backwards from what the
brief wants ("expand access to credit-invisible MSMEs") and should be
fixed before this design goes further — likely by using a discount that
widens uncertainty (e.g. a confidence interval or wider grade band)
rather than shrinking the score toward the population median.

## Tier A vs Tier C: three levels of rigor, because the naive comparison would mislead

**1. Raw (confounded):** Tier A mean 48.97 vs Tier C mean 50.54 — a
~1.6-point gap that mixes together "less data" with "whatever archetype
mix happened to land in each tier." Not a fair comparison on its own,
reported only for context.

**2. Archetype-controlled** (same archetype, different tier):

| Archetype | Tier A mean | Tier C mean | Gap |
|---|---|---|---|
| Healthy | 65.52 | 66.21 | -0.69 |
| Stagnant | 43.73 | 46.34 | -2.61 |
| Distressed | 18.44 | 20.02 | -1.58 |

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
| Healthy | 67.08 | 67.09 | **-0.01** |
| Stagnant | 44.18 | 45.32 | -1.14 |
| Distressed | 17.25 | 19.73 | -2.48 |

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
0.084 ("no significant shift" — correct, there's no real difference).
Injecting a synthetic -15 point shift into half the data gives PSI = 2.83
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

1. **The healthy-short-history finding (headline, above) is a design flaw
   to fix, not just a data point to report** — if this project continues,
   Module 4's discount mechanism should be revisited before anything else.
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
