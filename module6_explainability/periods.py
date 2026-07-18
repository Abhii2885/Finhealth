"""
Computes a human-readable 'as of' / period string per borrower per raw
data source - the scorecard's "Actual value (as of ...)" column header
content. Presentation-layer concern deliberately kept out of Module 3
(feature engineering) - Module 3 already has the raw values, this only
labels WHEN they're from, by reading the same Module 1 lake tables Module
6 already loads for the trend view.

SUBMETRIC_PERIOD_SOURCE maps each of the 22 5C submetrics to the period
key that describes its underlying data window. "_6mo" variants exist
because Module 3's compliance_features.py now computes those specific
ratios over a trailing-6-month window, not the full observed history -
the period label needs to say so, not claim the full window.
"""

import pandas as pd

SUBMETRIC_PERIOD_SOURCE = {
    "dscr": "bank", "interest_coverage_ratio": "bank", "cash_flow_match_ratio": "bank",
    "customer_concentration_pct": "bank", "supplier_concentration_pct": "bank", "cheque_bounce_rate": "bank",
    "current_ratio": "balance_sheet", "leverage_ratio": "balance_sheet", "net_worth_to_assets_ratio": "balance_sheet",
    "revenue_cagr_3yr": "turnover", "projected_revenue_growth_rate": "loan_application",
    "bureau_score": "bureau", "credit_limit_utilization_pct": "bureau",
    "civil_suit_years_since_active": "legal_disputes", "other_legal_dispute_years_since_active": "legal_disputes",
    "owner_time_in_business_years": "owners",
    "covenant_compliance_flag": "loan_facilities",
    "gst_ontime_filing_ratio": "gst_6mo",
    "epfo_ontime_remittance_ratio": "epfo_6mo",
    "utility_payment_timeliness": "bank_6mo", "rent_payment_timeliness": "bank_6mo", "salary_payment_timeliness": "bank_6mo",
    "collateral_quality_score": "collateral",
}


def _fmt_date(d):
    if d is None:
        return None
    ts = pd.to_datetime(d, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%d-%b-%Y")


def build_period_lookup(lake, master_df):
    """Returns {borrower_id: {period_key: display_string}}."""
    lookup = {bid: {} for bid in master_df["borrower_id"]}

    for bid, g in lake["bank"].groupby("borrower_id"):
        g = g.sort_values("txn_date")
        lookup[bid]["bank"] = f"Bank statement, {_fmt_date(g['txn_date'].iloc[0])} to {_fmt_date(g['txn_date'].iloc[-1])}"
        months = sorted(g["txn_date"].dt.to_period("M").unique())[-6:]
        if months:
            lookup[bid]["bank_6mo"] = f"Bank statement, {months[0]} to {months[-1]}"

    for bid, g in lake["gst"].groupby("borrower_id"):
        g = g.sort_values("period")
        lookup[bid]["gst"] = f"GST returns, {g['period'].iloc[0]} to {g['period'].iloc[-1]}"
        last6 = g.tail(6)
        lookup[bid]["gst_6mo"] = f"GST returns, {last6['period'].iloc[0]} to {last6['period'].iloc[-1]}"

    sdt_period = {}
    for bid, g in lake["self_declared"].groupby("borrower_id"):
        g = g.sort_values("period")
        sdt_period[bid] = f"Self-declared turnover, {g['period'].iloc[0]} to {g['period'].iloc[-1]}"

    is_gst_registered = dict(zip(master_df["borrower_id"], master_df["is_gst_registered"]))
    for bid in lookup:
        lookup[bid]["turnover"] = lookup[bid].get("gst") if is_gst_registered.get(bid, True) else sdt_period.get(bid)

    for bid, g in lake["epfo"].groupby("borrower_id"):
        g = g.sort_values("period")
        lookup[bid]["epfo"] = f"EPFO, {g['period'].iloc[0]} to {g['period'].iloc[-1]}"
        last6 = g.tail(6)
        lookup[bid]["epfo_6mo"] = f"EPFO, {last6['period'].iloc[0]} to {last6['period'].iloc[-1]}"

    for _, r in lake["balance_sheet"].iterrows():
        lookup[r["borrower_id"]]["balance_sheet"] = f"Balance sheet as of {_fmt_date(r['as_of_date'])}"

    entity_bureau = lake["bureau"][lake["bureau"]["entity_type"] == "msme_commercial"]
    for _, r in entity_bureau.iterrows():
        lookup[r["borrower_id"]]["bureau"] = f"Bureau report dated {_fmt_date(r['report_date'])}"

    for _, r in lake["collateral"].iterrows():
        lookup[r["borrower_id"]]["collateral"] = f"Valuation dated {_fmt_date(r['valuation_date'])}"

    for _, r in lake["loan_facilities"].iterrows():
        lookup[r["borrower_id"]]["loan_facilities"] = f"Loan originated {_fmt_date(r['origination_date'])}"

    for _, r in lake["loan_application"].iterrows():
        lookup[r["borrower_id"]]["loan_application"] = f"Application submitted {_fmt_date(r['submitted_at'])}"

    for bid, g in lake["legal_disputes"].groupby("borrower_id"):
        lookup[bid]["legal_disputes"] = f"Latest filing {_fmt_date(g['filed_date'].max())}"

    for bid in lookup:
        fallback = lookup[bid].get("loan_application", "As reported")
        lookup[bid].setdefault("legal_disputes", f"No disputes on record ({fallback})")
        lookup[bid]["owners"] = fallback

    return lookup
