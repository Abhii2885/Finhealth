"""
Capacity features - the largest of the 5 Cs (30% composite weight):
liquidity (current_ratio), leverage, debt service coverage, interest
coverage, cash-flow-vs-declared-turnover matching, 3-year revenue CAGR,
projected-revenue growth, and customer/supplier concentration (retained
under Capacity per the user's explicit instruction, not a separate
dimension).

Data sources: bank/UPI (cash flow proxies + counterparty concentration),
balance_sheet (current_ratio, leverage_ratio - NaN when
balance_sheet_available=False), loan_facilities (dscr,
interest_coverage_ratio - NaN when has_existing_loan=False, genuinely
not_applicable with no debt, not a data gap), turnover_unify's unified
GST/self-declared series (cash_flow_match_ratio, revenue_cagr_3yr,
projected_revenue_growth_rate - works for non-GST borrowers too), and
loan_application (projected_revenue_next_year_inr).
"""

import pandas as pd
import numpy as np
from config import CAGR_MIN_MONTHS_PER_YEAR, MIN_CONCENTRATION_TXN_COUNT

OPERATING_CREDIT_CATEGORIES = {"sales_inflow", "upi_transfer_in"}
OPERATING_DEBIT_CATEGORIES = {"vendor_payment", "salary_payment", "utility_payment",
                               "rent_payment", "upi_transfer_out", "cash_withdrawal", "cheque_bounce_fee"}

# Display/storage bounds per user instruction - these are DISPLAY-SANE
# clips on otherwise-unbounded ratios (a raw DSCR or interest-coverage
# ratio can mathematically run into the hundreds for a business with tiny
# debt and large cash flow, which is technically correct but unreadable
# on a scorecard). Clipping does not change Module 5's absolute-band
# scoring thresholds (1.0/1.3/1.5 for DSCR, all well under the 10.0 cap).
DSCR_MAX = 10.0
INTEREST_COVERAGE_MAX = 10.0
CURRENT_RATIO_MAX = 10.0
LEVERAGE_MAX = 10.0
CASH_FLOW_MATCH_RANGE = (0.0, 100.0)
CONCENTRATION_RANGE = (2.0, 90.0)


def _clip(v, lo=None, hi=None):
    if v is None or pd.isna(v):
        return v
    if lo is not None:
        v = max(v, lo)
    if hi is not None:
        v = min(v, hi)
    return v


def _net_operating_cash_flow_annualized(g):
    """Bank-derived operating surplus (excludes loan_emi - that's the debt
    service being measured against in dscr/interest_coverage), annualized
    to a 365-day rate so short-history borrowers are comparable."""
    credit = g.loc[g["category"].isin(OPERATING_CREDIT_CATEGORIES), "amount_inr"].sum()
    debit = g.loc[g["category"].isin(OPERATING_DEBIT_CATEGORIES), "amount_inr"].sum()
    n_days = max(g["txn_date"].nunique(), 1)
    return (credit - debit) / n_days * 365


def _last_12_turnover(turnover_g):
    turnover_g = turnover_g.sort_values("period")
    last12 = turnover_g.tail(12)
    if last12["turnover_inr"].notna().sum() == 0:
        return np.nan
    return last12["turnover_inr"].sum()


def _revenue_cagr_3yr(turnover_g):
    turnover_g = turnover_g.sort_values("period")
    n = len(turnover_g)
    if n < 24:
        return np.nan
    year1 = turnover_g.iloc[:12]["turnover_inr"]
    year3 = turnover_g.iloc[-12:]["turnover_inr"]
    if year1.notna().sum() < CAGR_MIN_MONTHS_PER_YEAR or year3.notna().sum() < CAGR_MIN_MONTHS_PER_YEAR:
        return np.nan
    year1_avg, year3_avg = year1.mean(), year3.mean()
    if year1_avg <= 0:
        return np.nan
    return (year3_avg / year1_avg) ** 0.5 - 1


def _concentration_pct(g, category):
    rows = g[g["category"] == category]
    if len(rows) < MIN_CONCENTRATION_TXN_COUNT:
        return np.nan
    by_counterparty = rows.groupby("counterparty_id")["amount_inr"].sum()
    total = by_counterparty.sum()
    if total <= 0:
        return np.nan
    return round(float(by_counterparty.max() / total * 100), 2)


def build_capacity_features(bank_df, turnover_df, balance_sheet_df, loan_facilities_df, loan_application_df, consistency_df):
    balance_sheet_lookup = balance_sheet_df.set_index("borrower_id").to_dict("index")
    loan_lookup = loan_facilities_df.set_index("borrower_id").to_dict("index")
    projected_lookup = dict(zip(loan_application_df["borrower_id"], loan_application_df["projected_revenue_next_year_inr"]))
    turnover_groups = {bid: g for bid, g in turnover_df.groupby("borrower_id")}

    rows = []
    for bid, g in bank_df.groupby("borrower_id"):
        bs = balance_sheet_lookup.get(bid)
        loan = loan_lookup.get(bid)
        t_g = turnover_groups.get(bid)

        current_ratio = np.nan
        leverage_ratio = np.nan
        if bs is not None:
            if bs["current_liabilities_inr"] > 0:
                current_ratio = round(_clip(bs["current_assets_inr"] / bs["current_liabilities_inr"], 0, CURRENT_RATIO_MAX), 3)
            if bs["net_worth_inr"] > 0:
                leverage_ratio = round(_clip(bs["total_debt_outstanding_inr"] / bs["net_worth_inr"], 0, LEVERAGE_MAX), 3)

        noc_annualized = _net_operating_cash_flow_annualized(g)

        dscr = np.nan
        interest_coverage_ratio = np.nan
        if loan is not None:
            annual_debt_service = loan["monthly_emi_inr"] * 12
            if annual_debt_service > 0:
                dscr = round(_clip(noc_annualized / annual_debt_service, 0, DSCR_MAX), 3)
            annual_interest = loan["principal_outstanding_inr"] * loan["interest_rate_pct_annual"] / 100
            if annual_interest > 0:
                interest_coverage_ratio = round(_clip(noc_annualized / annual_interest, 0, INTEREST_COVERAGE_MAX), 3)

        cash_flow_match_ratio = np.nan
        revenue_cagr_3yr = np.nan
        projected_revenue_growth_rate = np.nan
        if t_g is not None:
            last12_turnover = _last_12_turnover(t_g)
            bank_sales_inflow = g.loc[g["category"] == "sales_inflow", "amount_inr"].sum()
            if pd.notna(last12_turnover) and last12_turnover > 0:
                cash_flow_match_ratio = round(_clip(bank_sales_inflow / last12_turnover * 100, *CASH_FLOW_MATCH_RANGE), 2)
                projected = projected_lookup.get(bid)
                if projected is not None:
                    projected_revenue_growth_rate = round(projected / last12_turnover - 1, 4)
            revenue_cagr_3yr = _revenue_cagr_3yr(t_g)
            if pd.notna(revenue_cagr_3yr):
                # Signed, any direction (declining businesses show negative)
                # per explicit instruction - snapped to whole percentage
                # points for a clean scorecard display (e.g. 0.15 not 0.1487).
                revenue_cagr_3yr = round(round(revenue_cagr_3yr * 100) / 100, 2)

        customer_concentration_pct = _concentration_pct(g, "sales_inflow")
        supplier_concentration_pct = _concentration_pct(g, "vendor_payment")
        if pd.notna(customer_concentration_pct):
            customer_concentration_pct = round(_clip(customer_concentration_pct, *CONCENTRATION_RANGE), 2)
        if pd.notna(supplier_concentration_pct):
            supplier_concentration_pct = round(_clip(supplier_concentration_pct, *CONCENTRATION_RANGE), 2)

        rows.append({
            "borrower_id": bid,
            "current_ratio": current_ratio,
            "leverage_ratio": leverage_ratio,
            "dscr": dscr,
            "interest_coverage_ratio": interest_coverage_ratio,
            "cash_flow_match_ratio": cash_flow_match_ratio,
            "revenue_cagr_3yr": revenue_cagr_3yr,
            "projected_revenue_growth_rate": projected_revenue_growth_rate,
            "customer_concentration_pct": customer_concentration_pct,
            "supplier_concentration_pct": supplier_concentration_pct,
        })

    features = pd.DataFrame(rows)

    # Carries forward Module 2's consistency_flag as a passthrough - NOT
    # recomputed here, it's Module 2's finding attached to the same
    # borrower row so Module 5 can apply its capped penalty to
    # revenue_cagr_3yr (see config.CONSISTENCY_FLAG_PENALTY). This was
    # accidentally dropped when the old revenue_features.py was replaced
    # by this file during the 5C restructure - restored here.
    passthrough = consistency_df[["borrower_id", "turnover_bank_ratio", "consistency_flag"]].rename(
        columns={"consistency_flag": "gst_bank_consistency_flag"}
    )
    return features.merge(passthrough, on="borrower_id", how="left")
