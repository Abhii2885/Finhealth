# Module 2 — Data Quality & Completeness Tiering (Track 3)

Reads Module 1's `data_lake/` and answers three questions per borrower:
is the data trustworthy (schema/referential checks), is there enough of it
(completeness), and does it agree with itself across sources
(GST vs bank consistency)? The outputs feed Module 5's dimension weighting
— a missing dimension gets excluded and flagged, never defaulted to zero.

## Run it

```bash
cd module2_data_quality
pip install pandas numpy
python run_module2.py                      # uses ../msme_data_gen/data_lake by default
python run_module2.py /path/to/data_lake   # or point at a specific data lake
```

Produces `quality_output/`:

| File | Description |
|---|---|
| `schema_issues.csv` | Real schema/referential issues found in the data lake (0 on a clean Module 1 run) |
| `selftest_report.csv` | Proof the validator catches 5 known injected defect types |
| `completeness_report.csv` | Per-borrower per-source coverage (GST filing %, bank active-day %, EPFO filing %) + status |
| `consistency_report.csv` | GST-vs-bank ratio + consistency flag per borrower |
| `consistency_backtest.json` | Precision/recall of the consistency flag against hidden ground truth |
| `dimension_availability.csv` | Per-borrower, per-dimension: available / insufficient_data / not_applicable / not_computable_in_prototype |
| `quality_tier.csv` | Re-derived completeness tier (Full/Partial/Thin) + EPFO reliability flag |

## Results from this run (400 borrowers)

**Schema validation:** 0 issues on Module 1's actual output. Don't read
this as "the validator is weak" — the self-test below exists specifically
to prove otherwise.

**Self-test (proves the validator has teeth):** 5/5 injected defect types
caught — duplicate GST period, negative turnover, orphan borrower_id,
future-dated transaction, non-positive amount. See `selftest.py` for
exactly what's injected. Do this check before trusting a "0 issues found"
result on any dataset — a validator that never catches anything on its own
test data isn't validating, it's decorating.

**Completeness:**
- GST: 361 sufficient, 39 insufficient_data
- Bank: 361 sufficient, 39 insufficient_data (same 39 — Tier A borrowers with genuinely short history, built into Module 1 v2)
- EPFO: 156 sufficient (all Tier C), 244 not_applicable (all Tier A — correctly NOT counted as missing/bad)

**Quality tier (re-derived from actual data, not Module 1's assumed tier):**
Full 319, Partial 42, Thin 39. Zero Tier C borrowers had unreliable EPFO
data in this run (156/156 reliable) — in this synthetic dataset, EPFO
completeness doesn't degrade independently of the Tier A/C assignment, so
this check currently has nothing real to catch. It's implemented and would
fire if a future Module 1 version simulated EPFO-specific data gaps for
Tier C borrowers (e.g. contribution disputes, employer non-remittance
independent of overall business health) — flagging this as untested
rather than pretending it's been exercised.

**Cross-source consistency (GST turnover vs bank sales inflow), backtested
against the hidden `is_gst_underreporter` label:**

- Precision: 0.40, Recall: 0.29 (40 borrowers flagged, 55 actual under-reporters, 16 true positives)

**Read this honestly, not optimistically.** A single annual ratio,
flagging the top/bottom decile of the population, catches under 1 in 3 of
the borrowers actually under-reporting, and 6 in 10 of what it does flag
are false alarms. That's not nothing — it's meaningfully better than
random (13.75% base rate vs 40% precision) — but it is not a fraud
detector you'd want to act on alone. In a real build, this signal should
be combined with: GST filing delay pattern, month-by-month ratio
volatility (not just the annual snapshot), sector-adjusted norms instead
of one population-wide band, and ideally bureau data. Presenting this as
"we built a consistency check" is honest; presenting it as "we catch GST
fraud" is not — say the first thing, not the second, if this comes up in
a pitch.

## Dimension availability

Maps to Module 3's planned 6 scoring dimensions:

| Dimension | Source(s) needed | Status in this prototype |
|---|---|---|
| Liquidity & Cash Flow | bank | Computable when bank completeness sufficient |
| Repayment & Credit Behavior | bank (+ bureau) | Partially computable — bureau has no generator in this prototype, so this dimension is always missing one intended input |
| Revenue & Growth Signal | GST | Computable when GST completeness sufficient |
| Operational Stability | EPFO | Computable for Tier C only; `not_applicable` (not penalized) for Tier A |
| Compliance Discipline | GST (+ utility) | Partially computable — utility payment data has no generator in this prototype |
| Concentration Risk | buyer/supplier counterparty data | **Not computable at all** — Module 1's bank/UPI generator has no counterparty/vendor identifiers, only transaction categories. This is a real gap, not a completeness issue: no amount of "more data" from the current generator would fix it. If this dimension matters for the pitch, Module 1 needs a counterparty-ID field added before Module 2/3 can do anything with it. |

## Known limitations

1. **Completeness thresholds (`GST_MIN_FILING_COVERAGE`, `BANK_MIN_ACTIVE_DAY_COVERAGE`, etc.) are assumptions**, not derived from any real lender's policy. Tune in `config.py`.
2. **The consistency check's precision/recall is specific to this synthetic dataset's noise characteristics** — it is not a general claim about how well GST-vs-bank consistency checks work in production. Different real-world noise (seasonal invoicing lags, partial banking of cash sales, multi-bank accounts) would change these numbers in either direction.
3. **Concentration risk cannot be computed in this prototype at all** (see table above) — this should be flagged explicitly in any pitch, not glossed over as "still being tuned."
4. **The bureau and utility-payment sources referenced in the architecture doc have no Module 1 generator**, so "Repayment & Credit Behavior" and "Compliance Discipline" are permanently partial in this prototype, not just for specific borrowers.

## Files

```
module2_data_quality/
  config.py           - all thresholds and the dimension-to-source map
  loader.py           - reads Module 1's data_lake
  schema_checks.py    - schema/range/referential-integrity validation
  selftest.py          - injects known defects, proves the validator catches them
  completeness.py      - per-source per-borrower coverage metrics
  consistency.py       - GST-vs-bank ratio check + ground-truth backtest
  tiering.py            - dimension availability matrix + re-derived quality tier
  run_module2.py        - entry point
  quality_output/       - output (generated, not checked in by hand — rerun to regenerate)
```
