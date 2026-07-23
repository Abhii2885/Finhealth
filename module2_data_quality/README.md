# Module 2 — Data Quality & Submetric Availability (Track 3)

Reads Module 1's `data_lake/` and answers three questions per borrower:
is the data trustworthy (schema/referential checks), is there enough of
it (completeness), and does it agree with itself across sources (GST vs
bank consistency)? Its key output is the **per-submetric availability
matrix** — for each of the 22 scorecard submetrics of the 5C framework,
is it `available`, `insufficient_data`, or `not_applicable` for this
borrower — which drives Module 4's exclude-and-renormalise weighting.
A missing submetric is excluded and its weight redistributed, never
defaulted to a zero score.

## Run it

```bash
cd module2_data_quality
pip install pandas numpy
python run_module2.py ../module1_data_ingestion/data_lake
```

(The no-argument default points at a legacy directory name — pass the
data-lake path explicitly as above.)

Produces `quality_output/`:

| File | Description |
|---|---|
| `schema_issues.csv` | Real schema/referential issues found in the data lake (0 on a clean Module 1 run) |
| `selftest_report.csv` | Proof the validator catches 7 known injected defect types |
| `completeness_report.csv` | Per-borrower per-source coverage + status |
| `consistency_report.csv` | GST-vs-bank ratio + consistency flag per borrower |
| `consistency_backtest.json` | Precision/recall of the consistency flag against hidden ground truth |
| `submetric_availability.csv` | Per-borrower status for each of the 22 `(dimension, submetric)` pairs — the file Module 4 consumes |
| `dimension_availability.csv` | Legacy coarse per-dimension view (superseded by the submetric file) |
| `quality_tier.csv` | Re-derived completeness tier (Full/Partial/Thin) + EPFO reliability flag |

## How availability is decided

`config.SUBMETRIC_SOURCE_MAP` maps each of the 22 submetrics to its
source(s) and, where applicable, a **gating flag** from Module 1's
borrower master:

- `is_gst_registered` gates GST-derived submetrics (non-GST borrowers
  use self-declared turnover for revenue features instead);
- `balance_sheet_available` gates current ratio, leverage, and net-worth
  ratio;
- `has_bureau_record` gates the bureau score;
- `has_existing_loan` gates DSCR, interest coverage, and covenant
  compliance (no loan → genuinely not applicable, not missing);
- `has_collateral` gates collateral quality.

A gated-out submetric is `not_applicable`; one whose source exists but
falls below the completeness threshold is `insufficient_data` (Module 4
includes it at half weight); otherwise `available`.

## Results from this run (400 borrowers)

**Schema validation:** 0 issues on Module 1's actual output.

**Self-test (proves the validator has teeth):** 7/7 injected defect
types caught — duplicate GST period, negative turnover, orphan
borrower_id, future-dated transaction, non-positive amount, non-positive
current liabilities (balance sheet), and outstanding-exceeds-original
(loan facilities). A validator that never catches anything on its own
test data isn't validating, it's decorating.

**Submetric availability** (400 borrowers × 22 submetrics = 8,800
cells): 6,344 `available`, 2,051 `not_applicable` (gating flags — e.g.
195 borrowers have no balance sheet, 249 no collateral), 405
`insufficient_data` (thin-history borrowers).

**Quality tier** (re-derived from actual data, not Module 1's assumed
tier): Full 321, Partial 40, Thin 39.

**Cross-source consistency (GST turnover vs bank sales inflow),
backtested against the hidden `is_gst_underreporter` label:** precision
0.39, recall 0.27 (39 flagged, 55 actual under-reporters, 15 true
positives). **Read this honestly:** a single annual ratio catches barely
1 in 4 of the borrowers actually under-reporting, and 6 in 10 of its
flags are false alarms — meaningfully better than the 13.75% base rate,
but not a fraud detector to act on alone. Module 5 accordingly applies
it only as a small, visible, capped penalty, never a silent feature.

## Known limitations

1. **Completeness thresholds are assumptions**, not derived from any
   real lender's policy. Tune in `config.py`.
2. **The consistency check's precision/recall is specific to this
   synthetic dataset's noise characteristics** — not a general claim
   about production performance.
3. **The EPFO-reliability check is implemented but unexercised** — in
   this synthetic dataset EPFO completeness never degrades independently
   of tier assignment, so the check has nothing real to catch yet.

## Files

```
module2_data_quality/
  config.py           - thresholds + SUBMETRIC_SOURCE_MAP (22 submetrics -> sources + gating flags)
  loader.py           - reads Module 1's data_lake (all 11 sources)
  schema_checks.py    - schema/range/referential-integrity validation
  selftest.py         - injects known defects, proves the validator catches them
  completeness.py     - per-source per-borrower coverage metrics
  consistency.py      - GST-vs-bank ratio check + ground-truth backtest
  tiering.py          - submetric availability matrix + re-derived quality tier
  run_module2.py      - entry point
  quality_output/     - output (regenerate by rerunning)
```
