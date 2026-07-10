"""
Recompute-trigger logic: which borrowers need their score recomputed?

Two independent reasons, checked separately because they call for
different urgency:
1. STALE: score was computed more than STALENESS_THRESHOLD_DAYS ago.
   (This prototype doesn't track a real per-borrower "last scored" date -
   Module 5 doesn't persist one yet - so this check is currently a no-op
   showing the logic, flagged honestly rather than faked with invented
   timestamps.)
2. PENDING CONSENT REFRESH: Module 7 logged an AA consent-refresh event
   for this borrower (new data landed) that hasn't been acted on -
   this one uses REAL data, Module 7's actual demo_run_log.json.
"""

import datetime
from config import STALENESS_THRESHOLD_DAYS


def check_recompute_needed(borrower_ids, consent_refresh_events, last_scored_dates=None):
    """
    last_scored_dates: optional dict {borrower_id: date}. Not populated by
    any module yet (Module 5 doesn't persist a per-run timestamp) - this
    parameter exists so the staleness check is real code, not a stub, the
    moment that data exists. Documented as not-yet-wired rather than faked.
    """
    pending_by_borrower = {}
    for event in consent_refresh_events:
        bid = event.get("borrower_id")
        pending_by_borrower.setdefault(bid, []).append(event)

    today = datetime.date.today()
    results = []
    for bid in borrower_ids:
        reasons = []

        if bid in pending_by_borrower:
            reasons.append(f"{len(pending_by_borrower[bid])} pending consent-refresh event(s)")

        if last_scored_dates and bid in last_scored_dates:
            age_days = (today - last_scored_dates[bid]).days
            if age_days > STALENESS_THRESHOLD_DAYS:
                reasons.append(f"score is {age_days} days old (threshold: {STALENESS_THRESHOLD_DAYS})")
        # else: staleness check not evaluated - no timestamp tracked yet (see docstring)

        results.append({
            "borrower_id": bid,
            "needs_recompute": len(reasons) > 0,
            "reasons": "; ".join(reasons) if reasons else "none",
        })
    return results
