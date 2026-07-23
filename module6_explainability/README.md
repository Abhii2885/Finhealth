# Module 6 — Explainability & Visualization Dashboard (Track 3)

Builds a **standalone offline HTML dashboard** presenting each
borrower's full 5C scorecard: every submetric's actual value (with
source and as-of date), its model score, the method that produced it,
live score overrides with justification capture, ML advisory signals
from Module 9, and a plain-language financial-health trend. All 400
borrowers' data and Chart.js itself are embedded in the one file — no
server, no CDN, no network dependency of any kind.

## Run it

```bash
cd module6_explainability
pip install pandas
python run_module6.py     # uses sibling module1/3/4/5 dirs (and module9's ml_output if present) by default
```

Produces `explainability_output/`:

| File | Description |
|---|---|
| `dashboard.html` | **Open directly in any browser.** ~3 MB, fully self-contained |
| `top_drivers.csv` | Per borrower, per C: top positive/negative driver submetric |
| `trend.csv` | Per borrower: trend indicator at 4 checkpoints of observed history |
| `trend_validation.json` | Trend backtest against hidden `true_archetype` |

Rerun after Module 9 so the dashboard picks up the ML outputs — it
builds fine without them (the ML card then says "ML layer not run").

## Dashboard features

**Scorecard table per C** — Parameter | Actual value (formatted with
source and period, e.g. "6.10x — Bank statement, 01-Jul-2025 to
30-Jun-2026") | Model score (out of 10) | Override. Dimensions expand
and collapse; RAG (green/amber/red) colouring uses the grade-band cut
points consistently across composite, C scores, and submetrics.

**Methodology (i) button on every row** — discloses the exact scoring
method and thresholds behind that score (tiered band cutoffs, the
direct-ratio rule, the 70–80% cash-flow band, the collateral lookup),
plus a shared explainer for each C's weighted-average roll-up.

**Live overrides with mandatory justification** — overriding any
submetric (or C) score recomputes that C, the composite, the grade, RAG
colours, and the ML divergence readout instantly, client-side, using
the same weighted-average logic as Module 5. Justifications are
required, persisted to localStorage, and exportable as JSON — the
feedback artefact intended for future ML retraining. Overrides never
modify the pipeline's output files.

**ML advisory layer (from Module 9)** — two chips near the composite
score when triggered: "Model divergence — review advised" (challenger
vs champion gap ≥ 25 points) and "Unusual profile (ML)" (Isolation
Forest anomaly), each with a per-borrower plain-language explanation of
*why* — the divergence explainer names the submetrics most responsible
(ranked by weight × shortfall, the composite's own math read in
reverse); the anomaly explainer names the rare feature combination
driving the flag. A collapsed "ML Model Insights" card holds the full
champion/challenger numbers, every value tagged **ML**, under an
explicit "advisory only — does not change the score of record" banner.

**Five chart types** — radar (default), horizontal bar, weighted-
contribution donut (score × weight, "what actually drives the
composite"), semicircular composite gauge, and score waterfall.

**Financial Health Trend** — the borrower's health trajectory across 4
stages of their own observed history (Early records / Midway / Recent /
Today), with an auto-generated plain-language reading ("has been
WEAKENING — from 36.5 to 21 out of 100 (−15.5 points), currently at a
weak level") and an (i) note explaining the calculation in simple
terms. The trend combines 3 robust signals (bank balance, cheque
bounces, GST timeliness), each percentile-ranked within its checkpoint
— deliberately **not** a replay of the full 22-parameter score at each
past date, and labelled as such on the page.

**Auto-generated commentary** — a template-based (not LLM) summary of
each borrower's strongest and weakest areas.

**Theme** — IDBI-style green/white branded portal look; deliberately
not OS-theme-adaptive, as a bank portal keeps brand colours constant.

## Trend validation (backtested against hidden `true_archetype`)

| Checkpoint | Healthy | Stagnant | Distressed |
|---|---|---|---|
| 25% of history | 68.8 | 40.4 | 20.1 |
| 50% | 70.2 | 39.5 | 18.1 |
| 75% | 71.1 | 38.8 | 16.8 |
| 100% | 71.6 | 38.6 | 15.9 |

All three directional checks pass: final ordering correct, distressed
genuinely declines, healthy stable-or-improving — real signal recovered
from raw data, not asserted.

## Known limitations

1. **The trend is a 3-signal proxy**, not the full composite replayed
   historically — stated on the dashboard itself.
2. **Fraction-based checkpoints** mean "Midway" spans different
   calendar lengths for different borrowers; only same-borrower
   trajectories are directly comparable.
3. **Override recomputes are client-side approximations of Module 5**
   (they mirror its weighted-average math exactly, but tiered re-scoring
   of a changed *raw value* is not offered — overrides act on the score).
4. **All 400 borrowers embedded in one file** works at this scale; a
   real portfolio needs the Module 7 API pattern instead.

## Files

```
module6_explainability/
  config.py           - labels, RAG thresholds, methodology text, ML advisory strings
  loader.py           - reads Module 1/3/4/5 outputs + Module 9's ml_output (optional)
  drivers.py          - top-driver identification per C
  trend.py            - fraction-based checkpoint trend computation
  validate.py         - trend backtest against hidden true_archetype
  formatting.py       - actual-value display formatting (INR, ratios, dispute recency labels)
  periods.py          - per-submetric as-of period derivation
  commentary.py       - template-based borrower commentary
  ml_commentary.py    - per-borrower ML divergence + anomaly explanations
  dashboard.py        - builds the standalone HTML dashboard
  vendor/chart.umd.min.js - vendored Chart.js (no CDN dependency)
  run_module6.py      - entry point
  explainability_output/  - output incl. dashboard.html (regenerate by rerunning)
```
