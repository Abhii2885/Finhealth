"""
Formats Module 3's raw submetric values for the dashboard's scorecard
"Actual value" column - a presentation concern, deliberately kept out of
Module 3 (which stores the raw numeric value, not a display string).

Per-submetric because the underlying scale differs: some Module 3 features
are already 0-100 (cash_flow_match_ratio, *_concentration_pct,
credit_limit_utilization_pct), others are 0-1 fractions
(gst_ontime_filing_ratio, net_worth_to_assets_ratio, etc.) - a generic
"multiply by 100 if <1" heuristic would silently mis-format a genuinely
small percentage, so each key is explicit.
"""

RATIO_X_KEYS = {"current_ratio", "leverage_ratio", "dscr", "interest_coverage_ratio"}
ALREADY_PCT_KEYS = {"cash_flow_match_ratio", "customer_concentration_pct", "supplier_concentration_pct",
                     "credit_limit_utilization_pct"}
FRACTION_PCT_KEYS = {"gst_ontime_filing_ratio", "epfo_ontime_remittance_ratio", "utility_payment_timeliness",
                      "rent_payment_timeliness", "salary_payment_timeliness", "net_worth_to_assets_ratio",
                      "cheque_bounce_rate"}
SIGNED_FRACTION_PCT_KEYS = {"revenue_cagr_3yr", "projected_revenue_growth_rate"}

DISPUTE_SEVERITY_LABELS = {0.0: "No dispute on record", 0.5: "Resolved dispute (closed)", 1.0: "Ongoing dispute (open)"}
COVENANT_LABELS = {1.0: "Compliant", 0.0: "Breached"}


def fmt_inr(v):
    if v is None:
        return None
    v = float(v)
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:.2f}Cr"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:.2f}L"
    return f"₹{v:,.0f}"


def format_submetric_value(key, raw_value, extra=None):
    """extra: dict of sibling raw columns for keys that need more than one
    field (collateral needs type + construction + value)."""
    if key == "collateral_quality_score":
        if not extra or extra.get("collateral_type") is None:
            return None
        type_label = str(extra["collateral_type"]).capitalize()
        status_label = "Constructed" if extra.get("construction_status") == "constructed" else "Bare plot"
        value_str = fmt_inr(extra.get("estimated_value_inr"))
        return f"{type_label} ({status_label}), est. {value_str}"

    if raw_value is None:
        return None

    if key in ("civil_suit_years_since_active", "other_legal_dispute_years_since_active"):
        return DISPUTE_SEVERITY_LABELS.get(raw_value, str(raw_value))
    if key == "covenant_compliance_flag":
        return COVENANT_LABELS.get(raw_value, str(raw_value))
    if key == "bureau_score":
        return f"{raw_value:.0f} (of 300-900)"
    if key == "owner_time_in_business_years":
        return f"{raw_value:.1f} years"
    if key in RATIO_X_KEYS:
        return f"{raw_value:.2f}x"
    if key in ALREADY_PCT_KEYS:
        return f"{raw_value:.1f}%"
    if key in FRACTION_PCT_KEYS:
        return f"{raw_value * 100:.1f}%"
    if key in SIGNED_FRACTION_PCT_KEYS:
        return f"{raw_value * 100:+.0f}%"
    return str(raw_value)
