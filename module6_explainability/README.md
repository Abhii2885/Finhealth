# Module 6 — Explainability & Visualization Layer (Track 3)

Three deliverables per the architecture doc: a radar/spider chart per
borrower, top drivers per dimension, and a trend view. All three are
built here — but read the trend section before you present it, the scope
was deliberately narrowed and you should know exactly what it does and
doesn't prove.

## Run it

```bash
cd module6_explainability
pip install pandas
python run_module6.py                                                                                    # uses sibling module1/3/4/5 dirs by default
python run_module6.py /path/to/data_lake /path/to/features_output /path/to/scoring_output /path/to/segmentation_output
```

Produces `explainability_output/`:

| File | Description |
|---|---|
| `dashboard.html` | **Open this in a browser.** Standalone, self-contained — all 400 borrowers' data is embedded as JSON in the page. Only Chart.js loads from a CDN; works offline otherwise. Type or pick a borrower ID to see their radar chart, composite score, per-dimension drivers, and trend. |
| `top_drivers.csv` | Per borrower, per dimension: top positive/negative driver feature |
| `trend.csv` | Per borrower: trend_indicator at 4 checkpoints (25/50/75/100% of observed history) |
| `trend_validation.json` | Trend backtest against hidden `true_archetype` |

## Top drivers (explainability)

Reuses Module 5's per-feature percentile scores (now exposed in
`module5_scoring/scoring_output/feature_scores.csv`, added specifically
for this module rather than recomputing scoring logic twice). For each
dimension, the feature with the highest percentile score is the "top
positive" driver, the lowest is "top negative."

**Repayment & Credit Behavior has only one scoring feature** (cheque
bounce rate — see Module 3's documented gap on bureau/limit-utilization
data), so there's nothing to compare against. Every borrower's driver note
says so explicitly rather than fabricating a "top driver" from a single
number.

## Trend view — read this before presenting it

**What it is:** a real, computed trajectory using 3 robust point-in-time
metrics — average bank balance, cheque bounce rate, GST on-time filing
ratio — at 4 cumulative checkpoints per borrower (25%, 50%, 75%, 100% of
*their own* observed history). Each metric is percentile-ranked within its
own checkpoint's cross-section of borrowers, then averaged into one
`trend_indicator` (0–100) per checkpoint.

**What it is NOT:** a replay of Module 5's full composite scoring
methodology at each historical point. Two reasons this was scoped down
rather than built in full:
1. Module 3's growth/volatility features (turnover growth, headcount
   growth, etc.) compare a first-N-months window against a last-N-months
   window — meaningless on a 3-month truncated slice where those windows
   would overlap or be identical.
2. A true historical replay would need to re-derive Module 2's
   completeness tiers and Module 4's weights AS OF each past checkpoint,
   not just apply today's weights retroactively — that's a lot of
   re-plumbing for a secondary view.

**Checkpoints are fraction-based, not calendar-based** (25/50/75/100% of
each borrower's own history, not "3/6/9/12 months") because ~15% of Tier A
borrowers genuinely have as little as 3.5 months of data (Module 1 v2) —
a fixed calendar checkpoint would silently break for them.

### Validation (backtested against hidden `true_archetype`)

| Checkpoint | Healthy | Stagnant | Distressed |
|---|---|---|---|
| 25% of history | 67.6 | 41.6 | 21.3 |
| 50% | 69.6 | 40.2 | 18.7 |
| 75% | 70.6 | 39.6 | 17.1 |
| 100% (full history) | 71.2 | 39.0 | 16.5 |

**This is a genuinely strong result, not a marginal one.** Healthy
borrowers' trend indicator *improves* from 67.6 to 71.2 across their
observed history; distressed borrowers *decline* from 21.3 to 16.5;
stagnant borrowers stay roughly flat, as the label implies. All three
directional checks pass: final-checkpoint ordering is correct
(healthy > stagnant > distressed), distressed genuinely declines over the
window, and healthy is stable-or-improving. This is real signal recovered
from the raw data, not something asserted.

## Radar chart dashboard

Shows the 5 scorable dimensions (Concentration Risk is omitted with an
explicit note — Module 1 has no counterparty data, so it's not computable
for anyone, not a per-borrower gap). Each dimension's panel shows its
score, its effective weight (from Module 4 — 0% means excluded), and its
top driver(s), or a note when there's nothing to compare (single-feature
dimension, or no data at all for that borrower/dimension).

The dashboard is a single ~600KB HTML file. It's meant to be opened
directly in a browser — no server, no build step. Regenerate it any time
Module 5's scores change by rerunning `run_module6.py`.

## Known limitations

1. **The trend view's scope narrowing is a real simplification, not a
   placeholder** — see above. Don't present it as "score 3 months ago"
   without the caveat that it's a 3-metric proxy, not the full composite.
2. **Fraction-based checkpoints mean "50%" represents a different
   calendar span for different borrowers** — comparing two borrowers'
   trend charts side by side compares different absolute time periods,
   only same-borrower trajectories are directly meaningful.
3. **Top drivers are computed from percentile scores relative to this
   400-borrower batch** — same portability caveat as Module 5: add or
   remove borrowers and the "top driver" for a given borrower could shift
   even if their own raw numbers didn't change.
4. **The dashboard embeds all 400 borrowers' data in one file** — fine at
   this scale, but this approach won't scale to a portfolio of tens of
   thousands of borrowers without moving to a real backend/API instead of
   a static embedded-JSON page.

## Files

```
module6_explainability/
  config.py           - dimension/feature labels, trend checkpoint fractions
  loader.py            - reads Module 1/3/4/5 outputs
  drivers.py            - top-driver identification per dimension
  trend.py              - fraction-based checkpoint trend computation
  validate.py            - trend backtest against hidden true_archetype
  dashboard.py           - builds the standalone HTML dashboard
  run_module6.py          - entry point
  explainability_output/  - output incl. dashboard.html (generated, not checked in by hand — rerun to regenerate)
```

Also modifies `module5_scoring/dimension_scores.py` and `run_module5.py`
to expose `feature_scores.csv` (per-feature percentile scores) — additive
only, doesn't change any previously-committed Module 5 output file.
