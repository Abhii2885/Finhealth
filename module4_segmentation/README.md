# Module 4 — Segmentation & Scoring-Eligibility Policy (Track 3)

## Read this before anything else: scope note

The architecture doc's original Module 4 ("route each borrower to Tier
A/B/C, each tier gets a fixed dimension set") is **already done, at finer
granularity**, by Module 2 (`quality_tier`: Full/Partial/Thin, re-derived
from actual completeness) and Module 3 (per-borrower, per-dimension
availability: `available` / `insufficient_data` / `not_applicable` /
`not_computable_in_prototype`). Rebuilding a coarse 3-bucket router on top
of that data would be a step **backward** in precision — it would throw
away information Module 2/3 already computed per-dimension.

What this module actually adds, which Module 2/3 don't do:

1. **A weight policy** — a base weight per dimension, and an explicit rule
   for what happens to that weight when a dimension is unavailable for a
   given borrower (excluded vs. discounted, and by how much).
2. **A scoring-eligibility check** — is there enough usable data to
   produce a composite score at all, or should Module 5 refuse rather than
   output a number that looks precise but isn't.
3. **A human-readable segment label** per borrower, derived from their
   actual dimension combination — not a static assumption about what
   "Tier A" means.

If you only take one thing from this README: **Module 4 is a policy
layer, not a re-tiering step.** Module 5 should consume this module's
`segmentation_policy.csv` directly for its weights, not re-derive
completeness logic that already lives in Module 2/3.

## Run it

```bash
cd module4_segmentation
pip install pandas
python run_module4.py                              # uses ../module2_data_quality/quality_output by default
python run_module4.py /path/to/quality_output
```

Produces `segmentation_output/`:

| File | Description |
|---|---|
| `segmentation_policy.csv` | Per borrower: status + effective weight per dimension, `n_dimensions_included`, `scorable`, `segment_label` |
| `policy_checks.csv` | Internal consistency checks (weights sum to 1.0, non-scorable borrowers get zero weight everywhere, concentration_risk always excluded) |
| `segment_distribution.csv` | Counts per segment label |

## The policy

**Base weights** (sum to 1.0 across all 6 architecture-doc dimensions):

| Dimension | Base weight |
|---|---|
| Liquidity & Cash Flow | 0.20 |
| Repayment & Credit Behavior | 0.15 |
| Revenue & Growth Signal | 0.20 |
| Operational Stability | 0.15 |
| Compliance Discipline | 0.20 |
| Concentration Risk | 0.10 |

These are assumptions, not derived from any lender's actual risk model —
tune in `config.py`. Concentration risk's weight is included so the policy
is ready the moment Module 1 gains counterparty-level data; until then, it
is always excluded (see results below).

**Per-borrower handling, by Module 3's dimension status:**
- `available` → full base weight
- `insufficient_data` → base weight × 0.5 (there IS data, just below
  Module 2's completeness threshold — discounted, not thrown away).
  0.5 is an assumption, not a calibrated number.
- `not_applicable` (e.g. EPFO for Tier A) → excluded, weight redistributed.
  Not a penalty — the dimension genuinely doesn't apply.
- `not_computable_in_prototype` (concentration risk, always, for
  everyone) → excluded, weight redistributed.

Remaining weights are renormalized to sum to 1.0 over whichever
dimensions actually carry weight for that borrower.

**Eligibility:** a borrower needs at least 3 dimensions carrying nonzero
weight to be `scorable`. Below that, Module 5 should refuse to produce a
composite score rather than build one off 1-2 dimensions.

## Results from this run (400 borrowers)

**All 400 borrowers are scorable.** Even the worst-off group (short-history
Tier A borrowers, all their applicable dimensions flagged
`insufficient_data`) still clears the 3-dimension minimum with 4 discounted
dimensions. This is a property of this specific synthetic dataset — it
does NOT prove the 3-dimension threshold is right, only that nobody in
this run happened to fall below it. A real deployment should watch this
threshold's actual bite rate as new borrower profiles show up.

**Segment distribution:**

| Segment | Count | What it means |
|---|---|---|
| Full — 5 dimensions available | 156 | Tier C borrowers with clean data across GST, bank, and EPFO |
| Reduced — 4 dimensions available (structurally unavailable, not a data gap) | 205 | Tier A borrowers — missing only `operational_stability` because they have no EPFO by construction, not because anything is wrong with their data |
| Partial confidence — 4 dimensions (4 discounted for thin data) | 39 | Short-history Tier A borrowers (Module 1 v2) — every applicable dimension is present but thin, all discounted 50% |

Note there is no segment with fewer than 4 dimensions in this run, and
`concentration_risk` never contributes weight to anyone — it's excluded
for all 400 borrowers, every time, because Module 1 has no counterparty
data. **The composite score Module 5 builds from this policy is
effectively a 5-dimension score (4 for Tier A), not the 6-dimension score
implied by the architecture doc.** Say this plainly if it comes up.

## Internal consistency checks

All 3 checks pass: scorable borrowers' effective weights sum to 1.0
(within 1e-3 rounding tolerance), non-scorable borrowers (none in this
run) would get zero weight everywhere, and concentration_risk's weight is
confirmed zero for all 400 borrowers.

These are NOT a ground-truth backtest — there's no "correct" weight
vector to validate against. They only catch a broken policy, not a bad
one. Whether 0.20/0.15/0.20/0.15/0.20/0.10 or a 0.5 discount multiplier
are the *right* numbers is a business judgment call for your team, not
something this module can prove.

## Known limitations

1. Base weights and the 0.5 discount multiplier are assumptions — see above.
2. The 3-dimension eligibility floor is untested against any real edge
   case in this synthetic dataset (nobody fell below it here).
3. Because `concentration_risk` is always excluded in this prototype, its
   0.10 base weight is currently dead configuration — it does nothing
   until Module 1 gains a counterparty-ID field.
4. This module treats all `insufficient_data` dimensions identically (flat
   0.5 discount) regardless of HOW insufficient — a borrower at 59%
   coverage and one at 10% coverage get the same discount. A production
   version might scale the discount continuously with the actual
   coverage ratio instead of a step function.

## Files

```
module4_segmentation/
  config.py              - base weights, discount multiplier, eligibility threshold
  loader.py              - reads Module 2's dimension_availability
  segmentation.py         - core policy logic: weights, eligibility, segment labels
  validate.py             - internal consistency checks (not a ground-truth backtest)
  run_module4.py          - entry point
  segmentation_output/    - output (generated, not checked in by hand — rerun to regenerate)
```
