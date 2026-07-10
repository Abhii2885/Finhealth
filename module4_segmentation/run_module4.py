"""
Entry point for Module 4: Segmentation & Scoring-Eligibility Policy.

Run:
    python run_module4.py [quality_output_dir]

Produces segmentation_output/:
    segmentation_policy.csv   - per-borrower dimension statuses, effective weights, scorable flag, segment label
    policy_checks.csv         - internal consistency checks (not a ground-truth backtest)
    segment_distribution.csv  - counts per segment label
"""

import os
import sys

from config import DEFAULT_QUALITY_DIR, OUTPUT_DIR
from loader import load_dimension_availability
from segmentation import build_segmentation
from validate import run_checks


def main():
    quality_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUALITY_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading dimension availability from {quality_dir} ...")
    dim_avail = load_dimension_availability(quality_dir)
    print(f"  {len(dim_avail)} borrowers")

    print("\nBuilding segmentation policy (weights, eligibility, segment labels)...")
    seg = build_segmentation(dim_avail)
    seg_path = os.path.join(OUTPUT_DIR, "segmentation_policy.csv")
    seg.to_csv(seg_path, index=False)
    print(f"  -> {seg_path}")

    print("\nScorable vs not:")
    print(seg["scorable"].value_counts().to_string())

    print("\nSegment distribution:")
    dist = seg["segment_label"].value_counts()
    print(dist.to_string())
    dist.rename("count").reset_index().rename(columns={"index": "segment_label"}).to_csv(
        os.path.join(OUTPUT_DIR, "segment_distribution.csv"), index=False
    )

    print("\nData confidence breakdown (is the insufficient-data discount actually doing anything?):")
    print(seg["data_confidence"].value_counts().to_string())
    n_noop = (seg["data_confidence"] == "discount_is_noop_all_dims_uniformly_thin").sum()
    if n_noop:
        print(f"  -> {n_noop} borrower(s) have every included dimension uniformly flagged "
              f"insufficient_data, so INSUFFICIENT_DATA_WEIGHT_MULTIPLIER has zero effect on "
              f"their relative weights (see segmentation.py's _data_confidence docstring for the math).")

    print("\nInternal consistency checks...")
    checks = run_checks(seg)
    checks.to_csv(os.path.join(OUTPUT_DIR, "policy_checks.csv"), index=False)
    print(checks.to_string(index=False))
    all_pass = checks["pass"].fillna(True).all()
    print(f"\nAll checks passed: {all_pass}")

    print(f"\nDone. Outputs in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
