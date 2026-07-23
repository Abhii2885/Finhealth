# Module 8 — Monitoring & Feedback (Track 3)

Three deliverables: a **bias check across segments** (the architecture
doc's explicit call-out: "are NTC borrowers systematically scored lower
due to missing-dimension penalties?"), **score-drift detection** (PSI),
and **recompute triggers** wired to Module 7's actual event logs.

## Run it

```bash
cd module8_monitoring
pip install pandas numpy
python run_module8.py                     # bias check + drift self-test + recompute triggers
python run_module8.py --with-real-cohort  # also regenerates a genuine second cohort for a real drift comparison (~30-60s)
```

Produces `monitoring_output/`:

| File | Description |
|---|---|
| `bias_check.json` / `archetype_controlled_comparison.csv` | Tier A vs Tier C comparison (raw + archetype-controlled), short-history fairness check |
| `drift_selftest.json` | PSI self-test: control (no real shift) + injected shift |
| `drift_real_cohort.json` | (with `--with-real-cohort`) PSI vs a genuinely regenerated second cohort |
| `recompute_triggers.csv` | Which borrowers need recompute and why, from Module 7's logged events |

## Bias check — current 5C results (400 borrowers)

**Raw (confounded):** Tier A mean 62.5 (n=244) vs Tier C mean 64.6
(n=156) — mixes "less data" with archetype composition; context only.

**Archetype-controlled** (same underlying health, different tier):

| Archetype | Tier A | Tier C |
|---|---|---|
| Healthy | 73.5 | 75.5 |
| Stagnant | 58.6 | 62.7 |
| Distressed | 42.8 | 42.0 |

Tier A trails modestly for healthy/stagnant borrowers and is
essentially level for distressed ones — a small, direction-consistent
gap worth continued monitoring, far short of systematic exclusion.

**Short-history fairness (within Tier A):** healthy full-history 73.7
(n=100) vs short-history 72.3 (n=19) — a gap of **−1.4 points**,
compared with −9.7 before the pre-5C `balance_trend_pct` window-scaling
bug was found and fixed via this module's monitoring (the full
investigation, including the initially wrong diagnosis and its
correction, is preserved in the git history — this module's finding led
to a real Module 3 fix). Under the 5C scorecard, whose submetrics are
predominantly point-in-time or trailing-window ratios rather than
cumulative-window trends, the short-history penalty has largely
dissolved.

**Counterfactual reweighting test: PARKED, disclosed.** The pre-5C
version of this test relied on one dimension (EPFO/operational
stability) being deterministically absent for all of Tier A. Under the
5C structure every gating flag is probabilistic — no C is
deterministically tied to tier — so the old test's premise no longer
exists. It returns an explicit "parked" status with the reason rather
than computing a stale comparison.

## Score drift (PSI)

Standard industry thresholds: <0.10 no significant shift, 0.10–0.25
moderate, >0.25 significant.

**Self-test:** a random 50/50 split of the current cohort gives control
PSI = 0.047 (correctly "no significant shift"); injecting a synthetic
−15-point shift gives PSI = 3.89 (correctly "significant").

**Disclosed small-sample caveat** (documented in `drift.py`'s
docstring): at this population size (400 → ~200 per half → ~20 per
bin), the control PSI is genuinely noisy — across seeds it ranges
roughly 0.05–0.17, straddling the 0.10 threshold on data with *no real
drift*. This is a standard small-sample PSI limitation (industry
guidance assumes far larger populations), verified across 10 seeds
rather than seed-picking a passing run or silently loosening the
threshold.

**Real-cohort comparison** (`--with-real-cohort`): regenerates an
independent second 400-borrower cohort (different seed, full pipeline
re-run) and computes genuine PSI against it — validating the
methodology on a real before/after, not just the synthetic self-test.

## Recompute triggers

Cross-references Module 7's actual consent-refresh log (1 real event
from the demo run, correctly flagged). Staleness-based triggering
(score older than 90 days) is implemented but inert — Module 5 doesn't
yet persist a per-run timestamp — flagged as unwired rather than faked.

## Known limitations

1. **The PSI control test is noisy at this sample size** — see above;
   treat single-run "moderate shift" classifications on this population
   as expected noise, not drift.
2. **The bias check covers tier, archetype, and history length** —
   sector and business-age cuts are unexamined.
3. **Staleness checking is unwired** (no persisted scoring timestamp).
4. **The counterfactual reweighting test is parked** pending a design
   that fits probabilistic gating.

## Files

```
module8_monitoring/
  config.py         - PSI thresholds, staleness threshold
  loader.py         - reads Module 1/4/5/7 outputs
  bias_check.py     - tier/archetype/short-history comparisons (counterfactual parked, documented)
  drift.py          - PSI computation + self-test, with the small-sample disclosure
  cohort_b.py       - regenerates a genuine independent second cohort (--with-real-cohort)
  staleness.py      - recompute-trigger logic
  run_module8.py    - entry point
  monitoring_output/ - output (regenerate by rerunning)
```
