# Module 5 — Scoring & Aggregation Engine (Track 3)

Turns Module 3's features + Module 4's weight policy into one composite
0–100 health score and a letter grade per borrower. Rule-based percentile
ranking, not a trained model — matches the architecture doc's note that
this track doesn't require labeled default outcomes.

## Run it

```bash
cd module5_scoring
pip install pandas
python run_module5.py                                                              # uses sibling module3/module4/module1 dirs by default
python run_module5.py /path/to/features_output /path/to/segmentation_output /path/to/data_lake
```

Produces `scoring_output/`:

| File | Description |
|---|---|
| `borrower_scores.csv` | Per-borrower dimension scores, composite score, grade, segment label |
| `validation_summary.json` | Composite score means by hidden archetype + ordering check |
| `grade_by_archetype.csv` | Crosstab of grade vs hidden archetype |
| `consistency_penalty_audit.json` | Honest cost of Module 2's consistency-flag penalty (who actually gets docked) |

## Methodology

**Step 1 — per-feature percentile rank.** Every Module 3 feature used for
scoring (a deliberate subset — see `config.DIMENSION_SCORING_FEATURES`;
things like `avg_monthly_turnover_inr` are size measures, not health
signals, and are excluded) gets converted to a 0–100 percentile rank
within the 400-borrower population, flipped for risk-increasing features.
**Percentile rank, not min-max scaling** — min-max would let the extreme
outliers we already flagged in Module 1 (bank balances running into the
crores for some borrowers) compress everyone else into a narrow band.
Percentile rank is also directly explainable to a loan officer: "this
borrower's turnover growth is in the 73rd percentile of the portfolio."

**Step 2 — average within dimension.** Features within a dimension are
equal-weighted (no importance weighting) because there are no labeled
default outcomes to fit importance against in this track. This is a
simplification, not a claim that all features matter equally.

**Step 3 — consistency-flag penalty.** Module 2's GST-vs-bank consistency
check has precision ~0.40 / recall ~0.29 (see Module 2's README) — real
signal, but weak alone. Rather than blend it silently into a continuous
feature, it's applied as a small, visible, capped penalty to the revenue
dimension score: -10 for "bank inflow much higher than declared" (possible
under-reporting), -5 for "much lower" (weaker signal, possibly just an
under-banked cash business). See the honest cost of this below.

**Step 4 — weighted composite.** Dimension scores are combined using
Module 4's per-borrower `effective_weight` (already renormalized to
exclude not_applicable/not_computable dimensions). Zero-weight dimensions
are skipped entirely, not treated as a zero score.

**Step 5 — grade band.** Composite 0–100 mapped to A–E (see
`config.GRADE_BANDS`). Assumptions, not calibrated against a real
portfolio.

## Results from this run (400 borrowers)

**Composite score distribution:** mean 49.6, std 19.9, range 3.2–81.5.

**Grade distribution:** C-Fair 119, B-Good 108, E-Poor 98, D-Weak 73,
A-Strong 2.

**Validated against the hidden `true_archetype` label** (never used as an
input — only to check the scoring engine actually ranks the archetypes it
was built to separate):

| Archetype | Mean composite score |
|---|---|
| Healthy | 65.8 |
| Stagnant | 44.7 |
| Distressed | 19.1 |

**Ordering is correct: healthy > stagnant > distressed.** The separation
is clean at the extremes — every single distressed-archetype borrower (86
of 86) landed in E-Poor, and no healthy or stagnant borrower did. Stagnant
borrowers spread across C/D/E as expected for a "middling" group.

**One real calibration finding, not hidden:** only 2 of 400 borrowers hit
A-Strong (80+), even though 108 healthy borrowers scored well into B-Good.
The top grade band is calibrated too aggressively for this population's
actual score distribution — worth loosening the A-band cutoff (or
re-examining what "80" should mean) rather than concluding almost nobody
in a real portfolio would ever be "Strong."

## The honest cost of the consistency-flag penalty

80 of 400 borrowers took a penalty. Of those:

- **27 were healthy-archetype borrowers** penalized despite being fine —
  this is the false-positive cost of a check with ~40% precision, showing
  up as real point deductions for real borrowers who didn't do anything
  wrong.
- **18 were actual GST under-reporters** correctly penalized.
- Average points lost: -7.5.

**Read this plainly:** this penalty catches real signal (distressed and
under-reporting borrowers lose more, on average, than healthy ones —
consistent with the overall ordering holding up), but roughly 1 in 3
penalized borrowers are false positives eating a real, if modest, score
hit. That's the tradeoff of using a weak-but-real signal transparently
instead of either ignoring it (losing the true positives) or hiding it
inside a black-box feature (losing the auditability). If this needs to be
more conservative, lower the penalty magnitude or raise Module 2's
consistency-check thresholds — both are one-line changes in `config.py`.

## Known limitations

1. **Percentile ranks are relative to this specific 400-borrower
   population.** Add or remove borrowers and everyone's percentile shifts
   — this is not a fixed, portable scale. A production version needs
   either a large, stable reference population or fixed calibration bins
   (e.g. pre-defined cutoffs per feature) instead of a moving percentile
   rank recomputed on whatever's in the current batch.
2. **Equal-weighting features within a dimension is a simplification** —
   there's no labeled-outcome basis (by design, in this track) to justify
   different importance weights between e.g. `turnover_growth_rate` and
   `turnover_volatility`.
3. **Grade bands are uncalibrated assumptions** — see the A-Strong finding
   above. Don't present the letter grades as validated cutoffs.
4. **This score has never been checked against a real default outcome.**
   The hidden-archetype validation proves the engine recovers the pattern
   Module 1 was built to encode — it does not prove real-world predictive
   validity. Say this distinction plainly if asked.
5. **The consistency penalty's false-positive cost (above) compounds
   whatever unfairness already exists in Module 2's check** — if that
   check turns out to correlate with sector or borrower size in ways not
   yet tested, this penalty would propagate that bias into the composite
   score. Worth a fairness pass before using this on a real portfolio.

## Files

```
module5_scoring/
  config.py            - scoring feature sets, consistency penalty, grade bands
  loader.py              - reads Module 3 features + Module 4 segmentation + hidden ground truth
  dimension_scores.py    - percentile-rank scoring per feature, averaged per dimension, consistency penalty applied
  aggregate.py            - weighted composite using Module 4's effective weights + grade assignment
  validate.py             - backtest against hidden true_archetype + consistency-penalty cost audit
  run_module5.py           - entry point
  scoring_output/          - output (generated, not checked in by hand — rerun to regenerate)
```
