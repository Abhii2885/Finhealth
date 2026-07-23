# Module 3 — 5C Feature Engineering (Track 3)

Turns Module 1's raw data lake into the 22 numeric submetrics of the
**5 Cs of Credit** scorecard (Capacity / Character / Capital /
Compliance / Collateral). This module produces **features only** — the
0–100 scoring happens in Module 5 using Module 4's weights.

## Run it

```bash
cd module3_feature_engineering
pip install pandas numpy
python run_module3.py          # uses sibling module1/module2 output dirs by default
```

Produces `features_output/`:

| File | Description |
|---|---|
| `borrower_features.csv` | One row per borrower: all 22 submetrics + Module 2's per-submetric availability status |
| `feature_validation.csv` | Backtest of each directional feature against the hidden `true_archetype` label |
| `excluded_dimensions.csv` | Empty in the 5C build — every scorecard dimension is now computable |

## Features by dimension

**Capacity** (`capacity_features.py`): `dscr`, `interest_coverage_ratio`
(capped at 10×), `current_ratio`, `leverage_ratio` (debt / net worth,
0–10× real-world scale, capped), `cash_flow_match_ratio` (bank credits
vs declared turnover, 0–100%), `revenue_cagr_3yr` (requires 3 full
annual buckets from the 36-month GST/self-declared series),
`projected_revenue_growth_rate` (from the loan application),
`customer_concentration_pct` / `supplier_concentration_pct` (top
counterparty's share of bank inflows/outflows).

**Character** (`character_features.py`): `bureau_score` (CIBIL-style
300–900), `civil_suit_years_since_active` /
`other_legal_dispute_years_since_active` (0 = dispute active now;
N = years since the most recent resolution; sentinel 100 = never had
one — deliberately a large number, not NaN, because "never had a
dispute" is the *best* case and must score, not be excluded),
`cheque_bounce_rate`, `owner_time_in_business_years`.

**Capital** (`capital_features.py`): `net_worth_to_assets_ratio`.

**Compliance** (`compliance_features.py`): all ratios computed over the
**trailing 6 months only** (recent discipline, not permanent record):
`gst_ontime_filing_ratio`, `epfo_ontime_remittance_ratio`,
`utility_payment_timeliness`, `rent_payment_timeliness`,
`salary_payment_timeliness` (denominators are months observed in the
window — a missed payment counts against timeliness, it doesn't vanish),
plus point-in-time `covenant_compliance_flag`.

**Collateral** (`collateral_features.py`): `collateral_type`,
`construction_status`, `estimated_value_inr` (raw pass-through; the
type × construction lookup score is applied in Module 5).

`turnover_unify.py` merges GST and self-declared turnover into one
series so non-GST-registered borrowers get real revenue features rather
than permanent NaN. Missing-by-construction values (no loan → no DSCR)
are NaN, never zero — Module 4 excludes and renormalises.

## Validation against hidden ground truth

Every directional feature's group means are backtested across the hidden
`true_archetype` label (healthy / stagnant / distressed) — never used as
an input, only to verify the engineering captured real signal:

**20 of 20 directional features pass strict monotonic ordering.**
Representative rows:

| Feature | Healthy | Stagnant | Distressed |
|---|---|---|---|
| current_ratio | 2.40 | 1.67 | 0.90 |
| leverage_ratio | 0.47 | 3.17 | 6.86 |
| dscr | 7.14 | 5.10 | 1.49 |
| bureau_score | 758 | 680 | 578 |
| cheque_bounce_rate | 0.4% | 1.5% | 4.3% |
| net_worth_to_assets_ratio | 0.44 | 0.33 | 0.18 |
| gst_ontime_filing_ratio | 0.92 | 0.68 | 0.39 |
| covenant_compliance_flag | 0.95 | 0.75 | 0.45 |

Full table in `features_output/feature_validation.csv`. Non-directional
features (cash-flow match band, concentration, collateral fields,
owner tenure) are deliberately excluded from the ordering check — they
are not archetype-driven by construction.

## Known limitations

1. **Value caps (10× on DSCR/coverage/current/leverage ratios) are
   display-realism bounds**, applied at generation/feature level per
   user specification — a real deployment would document the winsorising
   policy with the lender.
2. **`projected_revenue_growth_rate` is a self-reported application
   figure** with mild archetype-conditioned optimism bias — treated as a
   lower-trust signal (lower subweight in Module 4) than the audited
   CAGR.
3. **The dispute recency sentinel (100 years) is a modelling convention**
   — any value ≥ the rubric's top tier (10 years) scores identically, so
   the magnitude is inert, but it will look odd in raw-data exports.
4. **Concentration features need a minimum transaction count** — below
   it they are NaN (insufficient data), preventing small-sample
   top-counterparty shares from masquerading as signal.

## Files

```
module3_feature_engineering/
  config.py                - snapshot date, windows, value bounds
  loader.py                - reads Module 1 data_lake + Module 2 quality_output
  capacity_features.py     - 9 Capacity submetrics
  character_features.py    - 5 Character submetrics (incl. years-since-active dispute recency)
  capital_features.py      - net worth / total assets
  compliance_features.py   - 6 Compliance submetrics, trailing-6-month windows
  collateral_features.py   - collateral raw fields
  turnover_unify.py        - GST + self-declared turnover into one series
  liquidity_features.py    - legacy bank-trend features (kept for Module 6's trend view)
  operational_features.py  - legacy EPFO features (kept for completeness checks)
  build_features.py        - orchestrator, merges all builders + availability status
  validate.py              - backtests every directional feature against true_archetype
  run_module3.py           - entry point
  features_output/         - output (regenerate by rerunning)
```
