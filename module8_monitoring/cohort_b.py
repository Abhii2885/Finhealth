"""
Generates a genuinely independent second cohort (different random seed,
same generator) by re-running the actual Modules 1-5 scripts in an
isolated temp directory via subprocess - not a simulated/fabricated
"pretend cohort B". This is what makes the drift comparison in
run_module8.py real rather than illustrative.

Requires the sibling module folders (module1_data_ingestion,
module2_data_quality, module3_feature_engineering, module4_segmentation,
module5_scoring) to exist as installed in this project - the same layout
this whole pipeline already assumes.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import pandas as pd

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

# Module 1's folder is named "module1_data_ingestion" in the shipped
# project layout, but "msme_data_gen" in some earlier scratch builds -
# auto-detect rather than hardcode so this doesn't silently break.
_MODULE1_CANDIDATES = ["module1_data_ingestion", "msme_data_gen"]


def _resolve_module1_dir():
    for name in _MODULE1_CANDIDATES:
        if os.path.isdir(os.path.join(REPO_ROOT, name)):
            return name
    raise FileNotFoundError(
        f"Could not find Module 1's folder (tried {_MODULE1_CANDIDATES}) next to module8_monitoring."
    )


def generate_cohort_b_scores(seed=43, keep_temp_dir=False):
    """Returns (scores_df, temp_dir_path_or_None). Runs the full pipeline
    with MSME_SEED={seed} in an isolated temp directory so it never
    touches the real, already-committed cohort's output files."""
    module1_dir = _resolve_module1_dir()
    module_dirs = [module1_dir, "module2_data_quality", "module3_feature_engineering",
                   "module4_segmentation", "module5_scoring"]

    tmp_root = tempfile.mkdtemp(prefix="msme_cohort_b_")
    env = dict(os.environ)
    env["MSME_SEED"] = str(seed)

    for name in module_dirs:
        src = os.path.join(REPO_ROOT, name)
        dst = os.path.join(tmp_root, name)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*_output", "data_lake", "quality_output", "features_output", "scoring_output", "segmentation_output"))

    def _run(module_name, script, args):
        cwd = os.path.join(tmp_root, module_name)
        result = subprocess.run([sys.executable, script] + args, cwd=cwd, env=env,
                                 capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"{module_name}/{script} failed:\n{result.stdout}\n{result.stderr}")

    _run(module1_dir, "run_generate.py", [])
    _run("module2_data_quality", "run_module2.py", [f"../{module1_dir}/data_lake"])
    _run("module3_feature_engineering", "run_module3.py", [f"../{module1_dir}/data_lake", "../module2_data_quality/quality_output"])
    _run("module4_segmentation", "run_module4.py", ["../module2_data_quality/quality_output"])
    _run("module5_scoring", "run_module5.py",
         ["../module3_feature_engineering/features_output", "../module4_segmentation/segmentation_output", f"../{module1_dir}/data_lake"])

    scores_path = os.path.join(tmp_root, "module5_scoring", "scoring_output", "borrower_scores.csv")
    scores_df = pd.read_csv(scores_path)

    if not keep_temp_dir:
        shutil.rmtree(tmp_root, ignore_errors=True)
        return scores_df, None
    return scores_df, tmp_root
