"""Loads Module 2's submetric availability output.

Module 4 stays a "pure policy layer" (per its original scope note) - it
never needs Module 1's master flags directly, because Module 2's
submetric_availability.csv already resolved every gating flag
(balance_sheet_available, has_existing_loan, etc.) into the correct
not_applicable/insufficient_data/available status per submetric."""

import os
import pandas as pd


def load_submetric_availability(quality_dir):
    return pd.read_csv(os.path.join(quality_dir, "submetric_availability.csv"))
