# Module 3 — Dimension Feature Engineering (Track 3)

Turns Module 1's raw data lake into numeric features grouped by Track 3's
scoring dimensions. This module produces **features only** — not the 0–100
per-dimension sub-scores. That aggregation/scoring step is Module 5.

## Run it

```bash
cd module3_feature_engineering
pip install pandas numpy
python run_module3.py                                          # uses sibling module1/module2 output dirs by default
python run_module3.py /path/to/data_lake /path/to/quality_output
```

Produces `features_output/`:

| File | Description |
|---|---|
| `borrower_features.csv` | One row per borrower: all dimension features + Module 2's per-dimension availability status |
| `feature_validation.csv` | Backtest of each feature's direction against the hidden `true_archetype` label |
| `excluded_dimensions.csv` | Manifest of dimensions/sub-features this prototype cannot compute at all |

## Features by dimension

**Liquidity & Cash Flow Health** (bank/UPI): `avg_balance_inr`, `balance_trend_pct`, `monthly_inflow_volatility`, `monthly_outflow_volatility`, `txn_frequency_stability`

**Repayment & Credit Behavior** (bank/UPI): `cheque_bounce_rate`, `cheque_bounce_count_annualized`. `bureau_dpd_history` and `credit_limit_utilization_pct` are always null — see Known Gaps.

**Revenue & Growth Signal** (GST, + Module 2 passthrough): `turnover_growth_rate`, `turnover_volatility`, `avg_monthly_turnover_inr`, `gst_periods_observed`, plus `turnover_bank_ratio` / `gst_bank_consistency_flag` carried forward from Module 2 (not recomputed).

**Operational Stability** (EPFO, Tier C only): `headcount_growth_rate`, `headcount_volatility`, `wage_bill_growth_rate`, `avg_employee_count`, `epfo_periods_observed`. Null (not zero) for Tier A.

**Compliance Discipline** (GST): `gst_ontime_filing_ratio`, `gst_missed_filing_rate`, `gst_avg_filing_delay_days`. `utility_payment_timeliness` is always null — see Known Gaps.

**Concentration Risk / Collateral & Coverage**: no columns at all in this table — not partially computed, not computed. See Known Gaps.

## Validation against hidden ground truth

Backtested each feature's group means across the hidden `true_archetype`
label (healthy / stagnant / distressed) — never used as an input, only to
check the feature engineering captured real signal:

| Feature | Healthy | Stagnant | Distressed | Expected direction correct? |
|---|---|---|---|---|
| balance_trend_pct | 16.8 | 14.9 | 10.2 | Yes |
| monthly_inflow_volatility | 0.122 | 0.114 | 0.175 | **No** — distressed clearly highest (right end), but stagnant < healthy breaks strict ordering |
| monthly_outflow_volatility | 0.102 | 0.112 | 0.166 | Yes |
| txn_frequency_stability | 0.082 | 0.084 | 0.111 | Yes |
| cheque_bounce_rate | 0.004 | 0.015 | 0.047 | Yes |
| cheque_bounce_count_annualized | 11.2 | 28.9 | 64.2 | Yes |
| turnover_growth_rate | 1.198 | 1.053 | 0.721 | Yes |
| turnover_volatility | 0.133 | 0.175 | 0.326 | Yes |
| headcount_growth_rate | 1.123 | 1.015 | 0.840 | Yes |
| headcount_volatility | 0.048 | 0.033 | 0.071 | **No** — same pattern as inflow volatility above |
| wage_bill_growth_rate | 1.128 | 1.015 | 0.832 | Yes |
| gst_ontime_filing_ratio | 0.932 | 0.696 | 0.420 | Yes |
| gst_missed_filing_rate | 0.009 | 0.020 | 0.088 | Yes |
| gst_avg_filing_delay_days | -1.26 | 0.77 | 9.19 | Yes |

**12 of 14 features pass strict monotonic ordering.** The 2 that don't
(`monthly_inflow_volatility`, `headcount_volatility`) both fail the same
way: distressed is clearly the highest-volatility group as expected, but
stagnant comes out lower than healthy instead of between healthy and
distressed. This traces back to Module 1's `ARCHETYPE_PARAMS` noise
settings not tuning the "stagnant" archetype's volatility as a strict
midpoint between the other two — a real, minor calibration gap in Module
1, not a bug in this module's feature logic. Worth a one-line fix in
`msme_data_gen`'s archetype params if this comes up in a pitch, but not
worth blocking Module 3 on.

## Bug fix: balance_trend_pct was not comparable across history lengths

Module 8's monitoring found that short-history (thin-file) borrowers were
scored unevenly by archetype — healthy ones penalized hardest. Investigating
that finding here (not in Module 4, where it was originally suspected —
see Module 4's README for why that mechanism turned out to be a math
no-op) traced it to this feature.

**The bug:** the original formula compared the mean balance in the first
10% of observed days to the mean in the last 10%, and reported raw %
change over the whole window. That's a cumulative change over however
much time happens to be observed — a borrower with 24 months of history
has ~7x more time for the same underlying trend to compound than a
borrower with 3.5 months. Before the fix, raw `balance_trend_pct` means
were **593–1868%** for full-history borrowers vs. **9–45%** for
short-history borrowers of the *same archetype* — an order-of-magnitude
gap driven by elapsed time, not by how healthy the business actually is.
Percentile-ranking that number in Module 5 against a population dominated
by full-history borrowers then pushed every short-history borrower
(healthy, stagnant, and distressed alike) into the single-digit
percentiles on this feature.

**The fix:** fit a linear trend (OLS slope of balance vs. day index) using
all available days, expressed as % of average balance per 30 days — a
rate, not a cumulative change, so it's comparable regardless of window
length. New raw means (see updated table above): healthy 16.8, stagnant
14.9, distressed 10.2 — still correctly ordered, now on a believable
scale for both full- and short-history borrowers.

**What this did and didn't fix:** it removed a genuine, provable
mechanical bug in one feature. It did **not** fully close Module 8's
short-history fairness gap — see that module's README for the measured
before/after. Several other growth-rate features (`turnover_growth_rate`,
`headcount_growth_rate`, `wage_bill_growth_rate`, gap #4 below) are
ratio-based rather than cumulative, so they don't have this same scaling
defect, but they are still noisier and closer to a neutral 1.0 on short
windows — that's a genuine information limit (less time observed = less
trend visible), not a formula bug, and wasn't changed.

## Known gaps (things this module structurally cannot do)

1. **Concentration risk and collateral/coverage have zero columns** in
   `borrower_features.csv` — not partial, not null-flagged, just absent.
   Module 1 has no counterparty/vendor-ID field (concentration) and no
   collateral data source at all. Adding either requires a Module 1
   change first, not a Module 3 fix.
2. **Repayment & Credit Behavior is missing bureau DPD history and credit
   limit utilization** for every borrower, not a subset — Module 1 has no
   bureau connector and no sanctioned-limit field to compute utilization
   against. This dimension's feature set is permanently thin in this
   prototype.
3. **Compliance Discipline is missing utility payment timeliness** for
   every borrower — same reason, no generator exists for it.
4. **Growth-rate features (`turnover_growth_rate`, `headcount_growth_rate`,
   `wage_bill_growth_rate`) compare short windows** (first/last 3 months,
   or fewer for short-history borrowers) **against each other, not a full
   regression trend line** — sensitive to a single unusually good or bad
   month at either end. Fine for a prototype; a production version should
   fit a trend line instead of comparing two small windows.
5. **Volatility features use coefficient of variation**, which is scale-
   sensitive for near-zero means — flagged NaN when the mean is exactly 0,
   but very small means can still produce inflated-looking volatility
   numbers. Worth sanity-checking per-borrower outliers before using this
   in Module 5's weighting.

## Files

```
module3_feature_engineering/
  config.py                - dimension-to-feature assumptions, trend windows, excluded-dimension list
  loader.py                 - reads Module 1 data_lake + Module 2 quality_output
  liquidity_features.py     - bank/UPI-derived liquidity features
  repayment_features.py     - bank/UPI-derived repayment features (+ documented gaps)
  revenue_features.py       - GST-derived revenue features + Module 2 consistency passthrough
  operational_features.py   - EPFO-derived features (Tier C only)
  compliance_features.py    - GST-derived compliance features (+ documented gap)
  build_features.py         - orchestrator, merges all dimensions + Module 2 availability status
  validate.py               - backtests every feature against the hidden true_archetype label
  run_module3.py             - entry point
  features_output/           - output (generated, not checked in by hand — rerun to regenerate)
```
