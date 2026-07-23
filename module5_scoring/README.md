# Module 5 — Scoring & Aggregation Engine (Track 3)

Turns Module 3's 22 submetric features and Module 4's per-borrower
weights into one composite 0–100 health score and a letter grade.
Rule-based and fully traceable — every submetric's score comes from a
named, documented method, most of them calibrated to a lender-supplied
Score Band rubric.

## Run it

```bash
cd module5_scoring
pip install pandas numpy
python run_module5.py \
    "$(python3 -c 'import config; print(config.DEFAULT_FEATURES_DIR)')" \
    "$(python3 -c 'import config; print(config.DEFAULT_SEGMENTATION_DIR)')" \
    ../module1_data_ingestion/data_lake
```

(The features/segmentation defaults are correct; the ground-truth
data-lake default points at a legacy directory, hence the explicit third
argument.)

Produces `scoring_output/`:

| File | Description |
|---|---|
| `borrower_scores.csv` | Per-borrower C scores, composite score, grade, segment label |
| `feature_scores.csv` | Per-submetric 0–100 scores (consumed by Modules 6 and 9) |
| `validation_summary.json` | Composite means by hidden archetype + ordering check |
| `grade_by_archetype.csv` | Crosstab of grade vs hidden archetype |
| `consistency_penalty_audit.json` | Honest cost of Module 2's consistency-flag penalty |

## Scoring methods (per submetric — see `config.SCORING_SUBMETRICS`)

**Tiered (lender Score Band rubric)** — 15 submetrics across
Capacity/Character/Capital. The lender's rubric defines 4 tiers per
submetric (scoring 0–3 / 4–6 / 7–9 / 10); implemented as continuous
**piecewise-linear interpolation** between the named cutoffs
(`TIERED_ANCHORS`), so a value near the worse edge of its tier scores
toward that tier's floor and a value near the better edge toward its
ceiling — no arbitrary jumps at boundaries. Examples: DSCR <1.0× →
0–3, ≥1.5× → 10; leverage (debt/net-worth) <1× → 10, ≥7× → toward 0;
bureau score on the CIBIL 300–900 scale; dispute recency 0 years
(active) → 0, >10 years or never → 10. Revenue CAGR and projected
growth floor at exactly 0 for zero/negative growth per the rubric.

**Direct ratio** — all 6 Compliance submetrics score as the ratio
itself × 100: 50% on-time GST filing = 50/100 (5/10 displayed), 80% =
80/100. Absolute and portable — the same ratio scores the same
regardless of the rest of the batch, so a single new applicant can be
scored alone.

**Band distance** — `cash_flow_match_ratio` targets the 70–80% band;
score decays symmetrically with distance in *either* direction (95%
match is not healthier than 75%).

**Lookup table** — collateral quality from type × construction status:
residential constructed 100 … industrial bare plot 20.

**Percentile** — no longer used for any submetric in the current
configuration (retained in the engine for future population-relative
metrics).

**Consistency penalty** — Module 2's GST-vs-bank flag (precision ~0.39)
is applied as a small, visible, capped penalty to the revenue-CAGR
submetric score (−10 / −5), never blended silently into a feature.

**Aggregation** — weighted average within each C using Module 4's
effective subweights, then weighted composite across Cs using effective
dimension weights. NaN submetrics carry zero weight and the average
rescales — missing data is excluded, never scored as zero.

**Grades:** A – Strong (80+), B – Good (65–80), C – Fair (50–65),
D – Weak (35–50), E – Poor (<35).

## Results from this run (400 borrowers)

**Composite distribution:** mean 63.3, std 14.2, range 28.8–90.4.

**Grade distribution:** B-Good 180, C-Fair 99, D-Weak 72, A-Strong 37,
E-Poor 12.

**Backtest against the hidden `true_archetype`** (never an input):

| Archetype | Mean composite |
|---|---|
| Healthy | 74.3 |
| Stagnant | 60.1 |
| Distressed | 42.5 |

**Ordering correct: healthy > stagnant > distressed.** All 37 A-Strong
borrowers are healthy-archetype; no distressed borrower grades above
C-Fair.

**Consistency-penalty audit:** 78 borrowers penalised; 18 are actual
GST under-reporters correctly caught, 20 are healthy-archetype false
positives (the disclosed cost of a ~39%-precision signal used
transparently); average −7.5 points on the affected submetric.

**Spot-check discipline:** tiered scores were verified against
hand-calculated interpolation for DSCR, leverage, and bureau score;
direct-ratio Compliance scores verified against raw ratios exactly.

## Known limitations

1. **Grade bands are assumptions**, not calibrated against real
   portfolio outcomes.
2. **This score has never been checked against a real default outcome**
   — the archetype backtest proves the engine recovers the pattern the
   generator encoded, not real-world predictive validity.
3. **The consistency penalty inherits Module 2's false-positive rate**
   — roughly 1 in 4 penalised borrowers didn't under-report.
4. **Tier anchor values are the lender rubric's, transcribed** — one
   acknowledged ordering typo in the source sheet was corrected per the
   lender's instruction (recorded in the session log).

## Files

```
module5_scoring/
  config.py            - TIERED_ANCHORS (Score Band rubric), scoring-method map, penalty, grade bands
  loader.py            - reads Module 3 features + Module 4 policy + hidden ground truth
  dimension_scores.py  - the five scoring methods + weighted within-C aggregation
  aggregate.py         - weighted composite across Cs + grade assignment
  validate.py          - archetype backtest + consistency-penalty cost audit
  run_module5.py       - entry point
  scoring_output/      - output (regenerate by rerunning)
```
