# Module 4 — 5C Weighting Engine & Scoring-Eligibility Policy (Track 3)

The policy layer of the 5C scorecard. Consumes Module 2's per-submetric
availability matrix and Module 1's gating flags and produces, per
borrower: an **effective weight for each of the 22 submetrics and each
of the 5 Cs**, a scorability decision, and a human-readable segment
label. Module 5 consumes `segmentation_policy.csv` directly — it never
re-derives availability logic.

## The core mechanism: exclude and renormalise, at two levels

One flat base-weight table per level; no conditional branching anywhere.

**Dimension (C-level) base weights:**

| Dimension | Weight |
|---|---|
| Capacity | 0.30 |
| Character | 0.25 |
| Capital | 0.20 |
| Compliance | 0.15 |
| Collateral | 0.10 |

**Submetric base weights within each C** (each set sums to 1.0 —
see `config.py`; e.g. Capacity is led by DSCR at 0.22 and cash-flow
match at 0.18; Character by bureau score at 0.50).

Per borrower:
- `available` → full base weight;
- `insufficient_data` → base weight × 0.5 (data exists but is below
  Module 2's threshold — discounted, not discarded);
- `not_applicable` → weight zeroed, remainder renormalised.

Renormalisation runs **within each C first** (submetric level), then
**across the 5 Cs** (a C whose submetrics are all excluded contributes
nothing, and its dimension weight redistributes proportionally).

**Why no conditional tables:** renormalising after excluding an item
preserves the relative proportions of what remains. The three
"conditional weighting" behaviours the design called for — Character
redistributing when no bureau record exists, Compliance re-ranking when
no covenant exists (GST becomes the top submetric automatically),
Capacity dropping balance-sheet ratios when no balance sheet exists —
all fall out of this single mechanism. Hand-verified: Character with
bureau excluded renormalises to exactly the specified fallback
proportions; Compliance without a covenant yields
gst > utility > epfo > rent > salary, matching the specified
no-covenant ordering.

**Eligibility:** a borrower needs at least 3 of the 5 Cs carrying
nonzero weight to be `scorable`; below that, Module 5 refuses to emit a
composite rather than dress up a 1–2 C number as a full health score.

## Run it

```bash
cd module4_segmentation
pip install pandas
python run_module4.py       # uses ../module2_data_quality/quality_output by default
```

Produces `segmentation_output/`:

| File | Description |
|---|---|
| `segmentation_policy.csv` | Per borrower: status + effective weight per submetric and per C, `scorable`, `segment_label` |
| `policy_checks.csv` | Internal consistency checks (see below) |
| `segment_distribution.csv` | Counts per segment label |

## Results from this run (400 borrowers)

**All 400 borrowers are scorable.** Segment distribution:

| Segment | Count |
|---|---|
| Full — 5 of 5 Cs available | 88 |
| Reduced — 4 of 5 Cs (capacity, character, capital, compliance) | 117 |
| Reduced — 4 of 5 Cs (capacity, character, compliance, collateral) | 63 |
| Reduced — 3 of 5 Cs (capacity, character, compliance) | 132 |

Capital is in play for 205 borrowers (the rest have no balance sheet);
Collateral for 151 (the rest have none pledged). Capacity, Character,
and Compliance are in play for all 400 — Character and Compliance
because their fallback submetrics (disputes, bounce rate, tenure;
GST/utility/rent/salary timeliness) exist even without a bureau record
or covenant.

**All 7 internal consistency checks pass:** C-level effective weights
sum to 1.0 for every scorable borrower (max deviation ~1e-16), and each
C's submetric weights sum to 1.0 when the C is in play and 0 when
excluded.

These checks catch a *broken* policy, not a *bad* one — whether
0.30/0.25/0.20/0.15/0.10 are the right numbers is a lender's judgment
call, tunable in `config.py`.

## Known limitations

1. **All base weights and the 0.5 insufficient-data discount are
   assumptions**, not calibrated against any real portfolio.
2. **The 3-of-5 eligibility floor never bites in this dataset** (all
   400 scorable) — its real-world bite rate is untested.
3. **The discount treats all `insufficient_data` identically** — 59%
   coverage and 10% coverage get the same 0.5×. A production version
   might scale continuously with actual coverage.

## Files

```
module4_segmentation/
  config.py              - 5C base weights + per-C submetric weights + eligibility threshold
  loader.py              - reads Module 2's submetric_availability + Module 1's master flags
  segmentation.py        - two-level exclude-and-renormalise weighting, segment labels
  validate.py            - internal consistency checks (not a ground-truth backtest)
  run_module4.py         - entry point
  segmentation_output/   - output (regenerate by rerunning)
```
