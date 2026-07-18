"""
Builds a standalone HTML dashboard organized around the 5 Cs of Credit as
a real scorecard: Parameter | Actual value (as of date/period) | Model
score | Override (with mandatory justification). 5 selectable chart
types, RAG (red/amber/green) coloring, a client-side score-override
capability that actually recomputes the affected submetric/C/composite
scores and re-renders (localStorage + JSON export - this file has no
backend, so that IS the persistence mechanism, not a placeholder for one),
an auto-generated bottom commentary, and an IDBI-style green/white theme.

All 400 borrowers' data is embedded as JSON in the page itself, and
Chart.js is vendored/inlined (see _load_chartjs_source) rather than loaded
from a CDN - fully offline/standalone, no server, no database, no network
dependency of any kind once the file is generated.
"""

import json
import os
import pandas as pd
from config import DIMENSIONS, DIMENSION_LABELS, RAG_GREEN_MIN, RAG_AMBER_MIN, PARAMETER_SCORE_SCALE, GRADE_BANDS, \
    METHODOLOGY_TEXT, DIMENSION_METHODOLOGY_NOTE, ML_ADVISORY_NOTE, \
    ML_CHIP_DIVERGENCE_LABEL, ML_CHIP_DIVERGENCE_TOOLTIP, ML_CHIP_ANOMALY_LABEL, ML_CHIP_ANOMALY_TOOLTIP, \
    ML_ADVISED_TAG_LABEL, ML_ADVISED_TAG_TOOLTIP, ML_DIVERGENCE_FLAG_THRESHOLD, FEATURE_LABELS
from commentary import build_commentary
from ml_commentary import build_ml_explanation
from formatting import format_submetric_value
from periods import SUBMETRIC_PERIOD_SOURCE, build_period_lookup


def pd_isna(v):
    try:
        return v != v  # NaN != NaN is True; works without importing pandas here
    except Exception:
        return v is None


def _clean(v, round_to=None):
    if v is None or pd_isna(v):
        return None
    if round_to is not None:
        return round(float(v), round_to)
    return v


def _to_score10(score_0_100):
    if score_0_100 is None:
        return None
    return round(round(score_0_100 / 10 * 2) / 2, 1)


def _rag(score):
    if score is None:
        return "unscored"
    if score >= RAG_GREEN_MIN:
        return "green"
    if score >= RAG_AMBER_MIN:
        return "amber"
    return "red"


STATUS_NOTES = {
    "not_applicable": "not applicable for this borrower",
    "insufficient_data": "data too thin to trust - discounted",
}


def _build_borrower_records(scores_df, segmentation_df, drivers_df, trend_df, feature_scores_df,
                             features_df, master_df, period_lookup, ml_df=None):
    ml_lookup = ml_df.set_index("borrower_id").to_dict("index") if ml_df is not None else {}
    seg_lookup = segmentation_df.set_index("borrower_id").to_dict("index")
    driver_lookup = drivers_df.set_index("borrower_id").to_dict("index")
    fscore_lookup = feature_scores_df.set_index("borrower_id").to_dict("index")
    feat_lookup = features_df.set_index("borrower_id").to_dict("index")
    master_lookup = master_df.set_index("borrower_id").to_dict("index")

    trend_lookup = {}
    for bid, g in trend_df.groupby("borrower_id"):
        g = g.sort_values("checkpoint_frac")
        trend_lookup[bid] = [
            {"frac": row["checkpoint_frac"], "value": _clean(row["trend_indicator"], 1)}
            for _, row in g.iterrows()
        ]

    # Discover each dimension's submetric keys from the segmentation
    # output's "{dim}__{submetric}_status" columns (single source of
    # truth - Module 4's config, not re-declared here).
    submetrics_by_dim = {}
    for col in segmentation_df.columns:
        for dim in DIMENSIONS:
            prefix = f"{dim}__"
            suffix = "_status"
            if col.startswith(prefix) and col.endswith(suffix):
                submetric = col[len(prefix):-len(suffix)]
                submetrics_by_dim.setdefault(dim, []).append(submetric)

    records = {}
    for _, row in scores_df.iterrows():
        bid = row["borrower_id"]
        seg = seg_lookup.get(bid, {})
        drv = driver_lookup.get(bid, {})
        fsc = fscore_lookup.get(bid, {})
        feat = feat_lookup.get(bid, {})
        master = master_lookup.get(bid, {})
        periods = period_lookup.get(bid, {})

        dims = []
        for d in DIMENSIONS:
            score_col = f"{d}_score"
            weight_col = f"{d}_effective_weight"
            dim_score = _clean(row.get(score_col), 1)
            weight = _clean(seg.get(weight_col), 4)

            submetrics = []
            for sm in submetrics_by_dim.get(d, []):
                status = seg.get(f"{d}__{sm}_status")
                sub_weight = _clean(seg.get(f"{d}__{sm}_effective_subweight"), 4)
                sub_score = _clean(fsc.get(f"featscore__{d}__{sm}"), 1)
                raw_value = _clean(feat.get(sm))
                extra = None
                if sm == "collateral_quality_score":
                    extra = {
                        "collateral_type": _clean(feat.get("collateral_type")),
                        "construction_status": _clean(feat.get("construction_status")),
                        "estimated_value_inr": _clean(feat.get("estimated_value_inr")),
                    }
                display_value = format_submetric_value(sm, raw_value, extra)
                period_key = SUBMETRIC_PERIOD_SOURCE.get(sm)
                period = periods.get(period_key) if period_key else None

                submetrics.append({
                    "key": sm,
                    "label": None,  # filled client-side from FEATURE_LABELS
                    "raw_value": raw_value,
                    "display_value": display_value,
                    "period": period,
                    "score": sub_score,
                    "score_10": _to_score10(sub_score),
                    "weight": sub_weight,
                    "status": status,
                    "note": STATUS_NOTES.get(status, ""),
                    "rag": _rag(sub_score),
                })

            dims.append({
                "key": d,
                "label": DIMENSION_LABELS[d],
                "score": dim_score,
                "score_10": _to_score10(dim_score),
                "weight": weight,
                "rag": _rag(dim_score),
                "top_positive": _clean(drv.get(f"{d}_top_positive")),
                "top_negative": _clean(drv.get(f"{d}_top_negative")),
                "note": _clean(drv.get(f"{d}_driver_note", "")) or "",
                "submetrics": submetrics,
            })

        composite_score = _clean(row.get("composite_score"), 1)

        ml_row = ml_lookup.get(bid)
        if ml_row is not None:
            ml_block = {
                "available": True,
                "challenger_score": _clean(ml_row.get("challenger_score"), 1),
                "anomaly_score": _clean(ml_row.get("anomaly_score"), 1),
                "is_anomaly": bool(ml_row.get("is_anomaly", False)),
                "divergence": _clean(ml_row.get("divergence"), 1),
                "flagged_for_review": bool(ml_row.get("flagged_for_review", False)),
            }
        else:
            ml_block = {"available": False}

        if ml_block.get("available"):
            explanation, advised = build_ml_explanation(dims, ml_block, FEATURE_LABELS)
            ml_block["explanation"] = explanation
            ml_block["advised_submetrics"] = advised
            for d in dims:
                for sm in d["submetrics"]:
                    sm["ml_advised"] = sm["key"] in advised

        record = {
            "borrower_id": bid,
            "composite_score": composite_score,
            "composite_rag": _rag(composite_score),
            "grade": row.get("grade"),
            "segment_label": row.get("segment_label"),
            "dimensions": dims,
            "trend": trend_lookup.get(bid, []),
            "context": {
                "is_gst_registered": bool(master.get("is_gst_registered", True)),
                "balance_sheet_available": bool(master.get("balance_sheet_available", False)),
                "has_bureau_record": bool(master.get("has_bureau_record", False)),
                "has_existing_loan": bool(master.get("has_existing_loan", False)),
                "has_collateral": bool(master.get("has_collateral", False)),
            },
            "ml": ml_block,
        }
        record["commentary"] = build_commentary(record)
        records[bid] = record
    return records


def _load_chartjs_source():
    """Chart.js is vendored locally (vendor/chart.umd.min.js) and inlined
    directly into the page rather than loaded from a CDN <script src> -
    makes the dashboard genuinely fully offline (no network dependency at
    all, not just 'works offline once Chart.js happens to be cached'), and
    compatible with strict-CSP hosting environments that block external
    script requests entirely."""
    vendor_path = os.path.join(os.path.dirname(__file__), "vendor", "chart.umd.min.js")
    with open(vendor_path, "r") as f:
        return f.read()


def build_dashboard(scores_df, segmentation_df, drivers_df, trend_df, feature_scores_df,
                     features_df, master_df, lake, out_path, ml_df=None, ml_holdout_eval=None):
    period_lookup = build_period_lookup(lake, master_df)
    records = _build_borrower_records(
        scores_df, segmentation_df, drivers_df, trend_df, feature_scores_df, features_df, master_df, period_lookup,
        ml_df=ml_df,
    )
    borrower_ids = sorted(records.keys())
    data_json = json.dumps(records)
    ids_json = json.dumps(borrower_ids)
    dim_order_json = json.dumps(DIMENSIONS)
    feature_labels_json = json.dumps(__import__("config").FEATURE_LABELS)
    dim_labels_json = json.dumps(DIMENSION_LABELS)
    grade_bands_json = json.dumps(GRADE_BANDS)
    methodology_json = json.dumps(METHODOLOGY_TEXT)
    dim_methodology_note_json = json.dumps(DIMENSION_METHODOLOGY_NOTE)

    # Model metadata for the ML card's footer - proof it's a real trained
    # model (held-out metrics), plus the synthetic-proxy caveat.
    ml_meta = None
    if ml_holdout_eval is not None:
        top_feature = (ml_holdout_eval.get("feature_importance") or [{}])[0].get("feature")
        ml_meta = {
            "test_mae": ml_holdout_eval.get("test_mae"),
            "test_r2": ml_holdout_eval.get("test_r2"),
            "top_feature": top_feature,
        }
    ml_meta_json = json.dumps(ml_meta)
    ml_strings_json = json.dumps({
        "advisory_note": ML_ADVISORY_NOTE,
        "chip_divergence_label": ML_CHIP_DIVERGENCE_LABEL,
        "chip_divergence_tooltip": ML_CHIP_DIVERGENCE_TOOLTIP,
        "chip_anomaly_label": ML_CHIP_ANOMALY_LABEL,
        "chip_anomaly_tooltip": ML_CHIP_ANOMALY_TOOLTIP,
        "advised_tag_label": ML_ADVISED_TAG_LABEL,
        "advised_tag_tooltip": ML_ADVISED_TAG_TOOLTIP,
    })
    chartjs_source = _load_chartjs_source()

    html = _HTML_TEMPLATE.format(
        data_json=data_json, ids_json=ids_json, dim_order_json=dim_order_json,
        feature_labels_json=feature_labels_json, dim_labels_json=dim_labels_json,
        grade_bands_json=grade_bands_json, methodology_json=methodology_json,
        dim_methodology_note_json=dim_methodology_note_json,
        ml_meta_json=ml_meta_json, ml_strings_json=ml_strings_json, ml_divergence_threshold=ML_DIVERGENCE_FLAG_THRESHOLD,
        param_scale=PARAMETER_SCORE_SCALE, rag_green=RAG_GREEN_MIN, rag_amber=RAG_AMBER_MIN,
        chartjs_source=chartjs_source,
    )
    with open(out_path, "w") as f:
        f.write(html)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MSME Financial Health Score — 5C Explainability Dashboard</title>
<script>{chartjs_source}</script>
<style>
  :root {{
    --bg: #f5f8f6; --panel: #ffffff; --border: #d7e5dc; --text: #1a2b22; --muted: #5c6f64;
    --accent: #0b6e3d; --accent-dark: #084f2b; --accent-soft: #e4f2e9;
    --green: #1f9254; --amber: #c98a12; --red: #c53434;
    --green-bg: #e4f2e9; --amber-bg: #fbf1de; --red-bg: #fbe6e6;
  }}
  /* Deliberately NOT theme-adaptive (no prefers-color-scheme/data-theme
     dark variant) - this simulates a bank's branded portal (IDBI-style
     green/white), which keeps consistent brand colors regardless of the
     viewer's OS theme, unlike a general content app. */
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: var(--bg); color: var(--text); }}
  header {{ padding: 20px 28px; border-bottom: 2px solid var(--accent); background: var(--panel); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  h1 {{ font-size: 18px; margin: 0; font-weight: 700; color: var(--accent-dark); }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
  select, input, button {{ background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: 14px; }}
  button {{ cursor: pointer; }}
  button.primary {{ background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; }}
  button.primary:disabled {{ background: var(--border); color: var(--muted); cursor: not-allowed; }}
  button.ghost {{ background: transparent; }}
  .layout {{ display: grid; grid-template-columns: 420px 1fr; gap: 20px; padding: 20px 28px; max-width: 1400px; margin: 0 auto; }}
  @media (max-width: 1000px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }}
  .composite-badge {{ text-align: center; padding: 16px 0 20px; border-radius: 10px; }}
  .composite-score {{ font-size: 48px; font-weight: 800; }}
  .grade {{ font-size: 16px; color: var(--muted); margin-top: 4px; }}
  .segment {{ font-size: 12px; color: var(--muted); margin-top: 10px; line-height: 1.4; }}
  .rag-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; flex-shrink: 0; }}
  .rag-green {{ background: var(--green); }} .rag-amber {{ background: var(--amber); }} .rag-red {{ background: var(--red); }} .rag-unscored {{ background: var(--border); }}
  .badge-green {{ background: var(--green-bg); }} .badge-amber {{ background: var(--amber-bg); }} .badge-red {{ background: var(--red-bg); }}
  .dim-card {{ border: 1px solid var(--border); border-radius: 8px; margin-top: 10px; overflow: hidden; }}
  .dim-header {{ padding: 12px 14px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }}
  .dim-title {{ font-size: 13px; font-weight: 700; display: flex; align-items: center; }}
  .dim-score {{ font-size: 15px; font-weight: 700; }}
  .dim-body {{ display: none; padding: 4px 14px 14px; border-top: 1px solid var(--border); overflow-x: auto; }}
  .dim-card.expanded .dim-body {{ display: block; }}
  .dim-caret {{ transition: transform 0.15s; display: inline-block; margin-left: 8px; color: var(--muted); }}
  .dim-card.expanded .dim-caret {{ transform: rotate(90deg); }}
  table.scorecard {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }}
  table.scorecard th {{ text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.03em; color: var(--muted); padding: 6px 8px; border-bottom: 1px solid var(--border); }}
  table.scorecard td {{ padding: 8px; border-bottom: 1px dashed var(--border); vertical-align: top; }}
  table.scorecard tr:last-child td {{ border-bottom: none; }}
  .param-cell {{ display: flex; align-items: flex-start; gap: 6px; min-width: 150px; }}
  .value-cell {{ min-width: 140px; }}
  .value-main {{ font-weight: 600; }}
  .value-period {{ color: var(--muted); font-size: 10.5px; display: block; margin-top: 1px; }}
  .score-cell {{ font-weight: 700; white-space: nowrap; }}
  .score-overridden {{ color: var(--accent); }}
  .override-cell {{ min-width: 120px; }}
  .sub-note {{ color: var(--muted); font-style: italic; font-size: 10.5px; display: block; margin-top: 1px; }}
  .override-link {{ font-size: 10.5px; color: var(--accent); background: none; border: none; padding: 0; text-decoration: underline; cursor: pointer; }}
  .info-btn {{ display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; border-radius: 50%; border: 1px solid var(--accent); color: var(--accent); background: var(--panel); font-size: 10px; font-weight: 700; font-style: italic; line-height: 1; cursor: pointer; flex-shrink: 0; padding: 0; }}
  .info-btn:hover {{ background: var(--accent-soft); }}
  .method-note {{ font-size: 11px; line-height: 1.5; color: var(--text); background: var(--accent-soft); border-left: 3px solid var(--accent); padding: 8px 10px; border-radius: 4px; margin-top: 6px; display: none; min-width: 220px; }}
  .method-note.open {{ display: block; }}
  .override-box {{ margin-top: 6px; padding: 10px; border: 1px dashed var(--accent); border-radius: 6px; background: var(--accent-soft); display: none; min-width: 220px; }}
  .override-box.open {{ display: block; }}
  .override-box textarea {{ width: 100%; min-height: 50px; margin: 6px 0; font-family: inherit; font-size: 12px; padding: 6px; border-radius: 4px; border: 1px solid var(--border); background: var(--panel); color: var(--text); }}
  .override-box .row {{ display: flex; gap: 8px; align-items: center; }}
  .override-box input[type=number] {{ width: 80px; }}
  .overridden-tag {{ font-size: 9.5px; background: var(--accent); color: #fff; padding: 1px 5px; border-radius: 4px; margin-left: 4px; }}
  .drivers {{ font-size: 11.5px; margin-top: 2px; }}
  .driver-pos {{ color: var(--green); }}
  .driver-neg {{ color: var(--red); }}
  .note {{ color: var(--amber); font-style: italic; }}
  canvas {{ max-height: 380px; }}
  .chart-tabs {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }}
  .chart-tab {{ padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border); background: var(--panel); font-size: 12px; cursor: pointer; }}
  .chart-tab.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .footer-note {{ font-size: 11px; color: var(--muted); line-height: 1.6; padding: 16px 28px 28px; max-width: 1400px; margin: 0 auto; }}
  .na-tag {{ font-size: 10px; background: var(--border); color: var(--muted); padding: 1px 6px; border-radius: 4px; margin-left: 6px; }}
  .context-strip {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; justify-content: center; }}
  .context-chip {{ font-size: 10.5px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border); }}
  .context-chip.missing {{ color: var(--red); border-color: var(--red); }}
  .commentary {{ font-size: 13px; line-height: 1.6; padding: 16px; background: var(--accent-soft); border-radius: 8px; margin-top: 16px; border-left: 4px solid var(--accent); }}
  .ml-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; justify-content: center; }}
  .ml-chip {{ font-size: 10.5px; padding: 4px 10px; border-radius: 999px; border: 1px solid; font-weight: 600; cursor: help; }}
  .ml-chip.divergence {{ color: var(--amber); border-color: var(--amber); background: var(--amber-bg); }}
  .ml-chip.anomaly {{ color: #6d4fa3; border-color: #6d4fa3; background: #f0eaf9; }}
  .ml-tag {{ font-size: 8.5px; background: #6d4fa3; color: #fff; padding: 1px 4px; border-radius: 3px; margin-left: 5px; vertical-align: middle; letter-spacing: 0.05em; }}
  .ml-card {{ border: 1px solid #c9bbe4; border-radius: 8px; margin-top: 14px; overflow: hidden; }}
  .ml-card .dim-header {{ background: #f7f4fc; }}
  .ml-advisory {{ font-size: 10.5px; color: #6d4fa3; background: #f0eaf9; border-left: 3px solid #6d4fa3; padding: 7px 10px; border-radius: 4px; margin: 8px 0; line-height: 1.5; }}
  table.ml-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 4px; }}
  table.ml-table td {{ padding: 7px 8px; border-bottom: 1px dashed var(--border); }}
  table.ml-table tr:last-child td {{ border-bottom: none; }}
  table.ml-table td:last-child {{ text-align: right; font-weight: 700; white-space: nowrap; }}
  .ml-meta {{ font-size: 10.5px; color: var(--muted); line-height: 1.6; margin-top: 8px; }}
  .ml-explanation {{ font-size: 12.5px; line-height: 1.6; color: var(--text); background: #f7f4fc; border: 1px solid #c9bbe4; border-radius: 6px; padding: 10px 12px; margin: 8px 0 12px; }}
  .ml-advised-tag {{ font-size: 8.5px; background: #6d4fa3; color: #fff; padding: 1px 5px; border-radius: 3px; margin-left: 5px; vertical-align: middle; letter-spacing: 0.03em; cursor: help; }}
  .export-bar {{ display: flex; justify-content: flex-end; align-items: center; gap: 8px; padding: 8px 28px; max-width: 1400px; margin: 0 auto; }}
  #override-count {{ font-size: 11px; color: var(--muted); }}
</style>
</head>
<body>

<header>
  <div>
    <h1>MSME Financial Health Score — 5C Explainability Dashboard</h1>
    <div class="subtitle">Module 6 · Track 3 · Capacity · Character · Capital · Compliance · Collateral</div>
  </div>
  <div>
    <input list="borrower-list" id="borrower-search" placeholder="Type or pick a borrower ID..." />
    <datalist id="borrower-list"></datalist>
  </div>
</header>

<div class="export-bar">
  <span id="override-count"></span>
  <button class="ghost" id="reset-btn">Reset overrides for this borrower</button>
  <button class="ghost" id="export-btn">Export overrides (JSON)</button>
</div>

<div class="layout">
  <div class="panel">
    <div class="composite-badge" id="composite-badge">
      <div class="composite-score" id="composite-score">--</div>
      <div class="grade" id="grade">--</div>
      <div class="segment" id="segment">--</div>
      <div class="context-strip" id="context-strip"></div>
      <div class="ml-chips" id="ml-chips"></div>
    </div>
    <div id="dim-list"></div>
    <div id="ml-card-container"></div>
    <div class="commentary" id="commentary"></div>
  </div>

  <div>
    <div class="panel" style="margin-bottom:20px;">
      <div class="chart-tabs" id="chart-tabs"></div>
      <canvas id="main-chart"></canvas>
      <div class="footer-note" style="padding:10px 0 0;" id="chart-caption"></div>
    </div>
    <div class="panel">
      <canvas id="trend-chart"></canvas>
      <div class="footer-note" style="padding:10px 0 0;">
        Trend indicator (y-axis, 0-100) averages 3 point-in-time metrics - average bank balance, cheque bounce rate, GST on-time filing - each percentile-ranked within its own checkpoint's cross-section. X-axis is % of THIS borrower's own observed history (not fixed calendar months, since some borrowers have as little as ~3.5 months of data). This is a robust proxy, NOT a replay of the full Module 5 5C composite methodology at each checkpoint.
      </div>
    </div>
  </div>
</div>

<div class="footer-note">
  Synthetic data (see Module 1 README). Percentile-based scores are relative to this 400-borrower batch, not a fixed portable scale.
  Parameter scores are shown out of {param_scale} for readability; weights are used only in the background composite calculation.
  RAG thresholds: green &ge;{rag_green}, amber {rag_amber}-{rag_green}, red &lt;{rag_amber} (applied to both the composite and each C).
  Overriding a score recomputes that C's score, the overall composite, and the ML Model Insights card's divergence/review-flag live in this browser tab - it does not change the underlying pipeline output files, and does not re-run the ML challenger model itself (its score reflects the last Module 9 pipeline run). Override justifications export as JSON feedback for the ML model's future retraining.
  See module5_scoring/README.md, module6_explainability/README.md, and module9_ml_layer/README.md for full methodology and known limitations.
</div>

<script>
const ORIGINAL_DATA = {data_json};
const IDS = {ids_json};
const DIM_ORDER = {dim_order_json};
const FEATURE_LABELS = {feature_labels_json};
const DIM_LABELS = {dim_labels_json};
const GRADE_BANDS = {grade_bands_json};
const METHODOLOGY = {methodology_json};
const DIM_METHODOLOGY_NOTE = {dim_methodology_note_json};
const ML_META = {ml_meta_json};
const ML_STRINGS = {ml_strings_json};
const ML_DIVERGENCE_THRESHOLD = {ml_divergence_threshold};
const RAG_GREEN = {rag_green};
const RAG_AMBER = {rag_amber};

// currentRecords: mutable working copies (overrides applied here), keyed
// by borrower_id, lazily cloned from ORIGINAL_DATA on first visit so a
// borrower's overrides persist as you navigate away and back within the
// same session, without ever mutating the original baseline data.
const currentRecords = {{}};
function getRecord(id) {{
  if (!currentRecords[id]) {{
    currentRecords[id] = JSON.parse(JSON.stringify(ORIGINAL_DATA[id]));
  }}
  return currentRecords[id];
}}

// ---------- Overrides: localStorage + export (client-side only, no backend) ----------
const OVERRIDE_KEY = 'msme_5c_score_overrides_v1';
function loadOverrides() {{
  try {{ return JSON.parse(localStorage.getItem(OVERRIDE_KEY) || '[]'); }} catch (e) {{ return []; }}
}}
function saveOverrideLog(entry) {{
  const all = loadOverrides();
  all.push(entry);
  localStorage.setItem(OVERRIDE_KEY, JSON.stringify(all));
  updateOverrideCount();
}}
function updateOverrideCount() {{
  document.getElementById('override-count').textContent = loadOverrides().length + ' override(s) recorded this session';
}}
document.getElementById('export-btn').addEventListener('click', () => {{
  const blob = new Blob([JSON.stringify(loadOverrides(), null, 2)], {{type: 'application/json'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'score_overrides.json'; a.click();
  URL.revokeObjectURL(url);
}});
document.getElementById('reset-btn').addEventListener('click', () => {{
  if (!currentBorrowerId) return;
  delete currentRecords[currentBorrowerId];
  renderBorrower(currentBorrowerId);
}});

function rag(score) {{
  if (score === null || score === undefined) return 'unscored';
  if (score >= RAG_GREEN) return 'green';
  if (score >= RAG_AMBER) return 'amber';
  return 'red';
}}

function toScore10(s) {{
  if (s === null || s === undefined) return null;
  const x = Math.round(s / 10 * 2) / 2;
  return Math.round(x * 10) / 10;
}}

function gradeFor(score) {{
  if (score === null || score === undefined) return 'Not scored';
  for (const [lo, hi, label] of GRADE_BANDS) {{ if (score >= lo && score <= hi) return label; }}
  return 'Not scored';
}}

// Mirrors Module 5's aggregate.py / dimension_scores.py weighted-average
// logic exactly: skip zero/null-weight or null-score items, rescale over
// whatever weight actually had a usable score.
function weightedScore(items) {{
  let wsum = 0, wtotal = 0;
  items.forEach(it => {{
    if (it.weight && it.weight > 0 && it.score !== null && it.score !== undefined) {{
      wsum += it.score * it.weight;
      wtotal += it.weight;
    }}
  }});
  return wtotal > 0 ? Math.round((wsum / wtotal) * 100) / 100 : null;
}}

// The actual recompute chain: submetric override -> that C's score ->
// composite score -> grade + RAG everywhere affected. This is what makes
// overriding a value actually DO something, not just log it.
function applyOverride(record, dimKey, submetricKey, newScore) {{
  const dim = record.dimensions.find(d => d.key === dimKey);
  if (submetricKey) {{
    const sm = dim.submetrics.find(s => s.key === submetricKey);
    sm.score = newScore;
    sm.score_10 = toScore10(newScore);
    sm.rag = rag(newScore);
    sm.overridden = true;
    const newDimScore = weightedScore(dim.submetrics.map(s => ({{score: s.score, weight: s.weight}})));
    dim.score = newDimScore;
    dim.score_10 = toScore10(newDimScore);
    dim.rag = rag(newDimScore);
  }} else {{
    dim.score = newScore;
    dim.score_10 = toScore10(newScore);
    dim.rag = rag(newScore);
    dim.overridden = true;
  }}
  const newComposite = weightedScore(record.dimensions.map(d => ({{score: d.score, weight: d.weight}})));
  record.composite_score = newComposite;
  record.composite_rag = rag(newComposite);
  record.grade = gradeFor(newComposite);
}}

// ---------- Borrower selector ----------
const datalist = document.getElementById('borrower-list');
IDS.forEach(id => {{
  const opt = document.createElement('option');
  opt.value = id;
  datalist.appendChild(opt);
}});

let mainChart, trendChart;
let currentChartType = 'radar';
let currentBorrowerId = null;

const CHART_TYPES = [
  {{key: 'radar', label: 'Radar'}},
  {{key: 'bar', label: 'Bar (by C)'}},
  {{key: 'donut', label: 'Weighted contribution'}},
  {{key: 'gauge', label: 'Composite gauge'}},
  {{key: 'waterfall', label: 'Score waterfall'}},
];
const CHART_CAPTIONS = {{
  radar: 'Fast shape read of relative strength across all 5 C\\'s at once.',
  bar: 'Exact relative magnitudes per C — easier to compare precisely than the radar.',
  donut: 'Each C\\'s ACTUAL contribution to the 0-100 composite (score \\u00d7 weight), not just its own raw score.',
  gauge: 'Single at-a-glance dial for the overall composite score, RAG-banded.',
  waterfall: 'Builds from 0 up through each C\\'s weighted contribution to the final composite.',
}};

const tabsEl = document.getElementById('chart-tabs');
CHART_TYPES.forEach(ct => {{
  const btn = document.createElement('button');
  btn.className = 'chart-tab' + (ct.key === currentChartType ? ' active' : '');
  btn.textContent = ct.label;
  btn.dataset.key = ct.key;
  btn.addEventListener('click', () => {{
    currentChartType = ct.key;
    document.querySelectorAll('.chart-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderMainChart(getRecord(currentBorrowerId));
  }});
  tabsEl.appendChild(btn);
}});

function fmtScore10(s10) {{ return (s10 === null || s10 === undefined) ? '—' : s10 + '/{param_scale}'; }}

function renderContextStrip(ctx) {{
  const items = [
    ['GST-registered', ctx.is_gst_registered],
    ['Balance sheet', ctx.balance_sheet_available],
    ['Bureau record', ctx.has_bureau_record],
    ['Existing loan', ctx.has_existing_loan],
    ['Collateral', ctx.has_collateral],
  ];
  const el = document.getElementById('context-strip');
  el.innerHTML = '';
  items.forEach(([label, present]) => {{
    const chip = document.createElement('span');
    chip.className = 'context-chip' + (present ? '' : ' missing');
    chip.textContent = label + ': ' + (present ? 'yes' : 'no');
    el.appendChild(chip);
  }});
}}

function openOverrideBox(boxId) {{
  document.querySelectorAll('.override-box.open').forEach(b => {{ if (b.id !== boxId) b.classList.remove('open'); }});
  document.getElementById(boxId).classList.toggle('open');
}}

function buildInfoButton(noteId, text) {{
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'info-btn';
  btn.textContent = 'i';
  btn.title = 'How this is scored';
  btn.addEventListener('click', (e) => {{
    e.stopPropagation();
    document.getElementById(noteId).classList.toggle('open');
  }});
  return btn;
}}

function buildInfoNote(noteId, text) {{
  const div = document.createElement('div');
  div.className = 'method-note';
  div.id = noteId;
  div.textContent = text;
  return div;
}}

function buildOverrideBox(id, dimKey, submetricKey, currentScore, boxId) {{
  const div = document.createElement('div');
  div.className = 'override-box';
  div.id = boxId;
  div.innerHTML = `
    <div class="row">
      <label style="font-size:11px;">Override score (0-100):</label>
      <input type="number" min="0" max="100" step="0.1" value="${{currentScore !== null ? currentScore : ''}}" class="ov-score" />
    </div>
    <textarea class="ov-comment" placeholder="Required: justification for this override (exported as feedback for the ML challenger model's future retraining)"></textarea>
    <button class="primary ov-save" disabled>Save override</button>
  `;
  const textarea = div.querySelector('.ov-comment');
  const saveBtn = div.querySelector('.ov-save');
  textarea.addEventListener('input', () => {{ saveBtn.disabled = textarea.value.trim().length === 0; }});
  saveBtn.addEventListener('click', () => {{
    const scoreInput = div.querySelector('.ov-score');
    const newScore = parseFloat(scoreInput.value);
    if (isNaN(newScore)) return;

    saveOverrideLog({{
      borrower_id: id, scope: submetricKey ? 'submetric' : 'dimension',
      key: submetricKey ? `${{dimKey}}.${{submetricKey}}` : dimKey,
      original_score: currentScore, overridden_score: newScore,
      comment: textarea.value.trim(), timestamp: new Date().toISOString(),
    }});

    const record = getRecord(id);
    applyOverride(record, dimKey, submetricKey, newScore);
    renderBorrower(id);  // full re-render so the recompute is visible everywhere at once
  }});
  return div;
}}

// ---------- ML layer (Module 9) surfacing: chips + collapsed detail ----------
// challenger_score, anomaly_score, is_anomaly, and the explanation/advised-
// submetrics list are STATIC (frozen at the last Module 9 pipeline run -
// a separately trained model that doesn't re-infer per keystroke in this
// page). Champion score, divergence, and the divergence flag ARE live -
// they read getRecord(id) (the override-aware working copy) and recompute
// on every render, so the ML card never shows a champion score that
// contradicts what the rest of the page is showing.
function renderMlSection(id) {{
  const ml = (ORIGINAL_DATA[id] && ORIGINAL_DATA[id].ml) || {{available: false}};
  const rec = getRecord(id);
  const champion = rec ? rec.composite_score : null;

  let liveDivergence = null, liveFlagged = false;
  if (ml.available && champion !== null && champion !== undefined && ml.challenger_score !== null && ml.challenger_score !== undefined) {{
    liveDivergence = Math.round((ml.challenger_score - champion) * 10) / 10;
    liveFlagged = Math.abs(liveDivergence) >= ML_DIVERGENCE_THRESHOLD;
  }}
  const overridden = ml.available && liveFlagged !== ml.flagged_for_review;

  const chipsEl = document.getElementById('ml-chips');
  chipsEl.innerHTML = '';
  if (ml.available && liveFlagged) {{
    const chip = document.createElement('span');
    chip.className = 'ml-chip divergence';
    chip.textContent = ML_STRINGS.chip_divergence_label;
    chip.title = ML_STRINGS.chip_divergence_tooltip;
    chipsEl.appendChild(chip);
  }}
  if (ml.available && ml.is_anomaly) {{
    const chip = document.createElement('span');
    chip.className = 'ml-chip anomaly';
    chip.textContent = ML_STRINGS.chip_anomaly_label;
    chip.title = ML_STRINGS.chip_anomaly_tooltip;
    chipsEl.appendChild(chip);
  }}

  const container = document.getElementById('ml-card-container');
  container.innerHTML = '';
  const card = document.createElement('div');
  card.className = 'dim-card ml-card';  // collapsed by default (no 'expanded')

  const header = document.createElement('div');
  header.className = 'dim-header';
  header.innerHTML = `
    <span class="dim-title">ML Model Insights<span class="ml-tag">ML</span><span class="dim-caret">&#9656;</span></span>
    <span class="dim-score" style="font-size:11px;color:var(--muted);font-weight:400;">champion&ndash;challenger</span>
  `;
  header.addEventListener('click', () => card.classList.toggle('expanded'));
  card.appendChild(header);

  const body = document.createElement('div');
  body.className = 'dim-body';

  if (!ml.available) {{
    body.innerHTML = '<div class="ml-meta" style="padding:8px 0;">ML layer not run \\u2014 execute module9_ml_layer/run_module9.py, then rebuild this dashboard.</div>';
  }} else {{
    const advisory = document.createElement('div');
    advisory.className = 'ml-advisory';
    advisory.textContent = ML_STRINGS.advisory_note;
    body.appendChild(advisory);

    if (ml.explanation) {{
      const expl = document.createElement('div');
      expl.className = 'ml-explanation';
      expl.textContent = ml.explanation;
      body.appendChild(expl);
    }}

    const table = document.createElement('table');
    table.className = 'ml-table';
    const fmt = (v, suffix) => (v === null || v === undefined) ? '\\u2014' : v + (suffix || '');
    const divergenceStr = (liveDivergence === null || liveDivergence === undefined) ? '\\u2014'
      : (liveDivergence > 0 ? '+' : '') + liveDivergence + ' pts';
    table.innerHTML = `
      <tr><td>Champion score <span style="color:var(--muted);font-size:10.5px;">(rule-based 5C scorecard \\u2014 score of record, live)</span></td><td>${{fmt(champion)}}</td></tr>
      <tr><td>Challenger score <span class="ml-tag">ML</span> <span style="color:var(--muted);font-size:10.5px;">(Gradient Boosting, as of last pipeline run)</span></td><td>${{fmt(ml.challenger_score)}}</td></tr>
      <tr><td>Divergence (challenger \\u2212 champion, live)</td><td>${{divergenceStr}}</td></tr>
      <tr><td>Anomaly score <span class="ml-tag">ML</span> <span style="color:var(--muted);font-size:10.5px;">(Isolation Forest, 0-100, higher = more unusual)</span></td><td>${{fmt(ml.anomaly_score)}}</td></tr>
      <tr><td>Flagged for manual review (divergence \\u2265 ${{ML_DIVERGENCE_THRESHOLD}}, live)</td><td>${{liveFlagged ? 'YES' : 'No'}}${{overridden ? ' <span style=\\'color:var(--accent);font-size:10px;\\'>(changed by override)</span>' : ''}}</td></tr>
      <tr><td>Unusual data profile (anomaly detector)</td><td>${{ml.is_anomaly ? 'YES' : 'No'}}</td></tr>
    `;
    body.appendChild(table);

    const meta = document.createElement('div');
    meta.className = 'ml-meta';
    let metaText = '';
    if (ML_META) {{
      metaText += 'Challenger validation (held-out test set, robustness run): MAE ' + ML_META.test_mae +
                  ', R\\u00b2 ' + ML_META.test_r2 +
                  (ML_META.top_feature ? '; top predictive signal: ' + (FEATURE_LABELS[ML_META.top_feature] || ML_META.top_feature) : '') + '. ';
    }}
    metaText += 'Prototype caveat: trained against a synthetic archetype proxy label \\u2014 no real repayment outcomes exist in generated data. See module9_ml_layer/README.md.';
    meta.textContent = metaText;
    body.appendChild(meta);
  }}

  card.appendChild(body);
  container.appendChild(card);
}}

function renderBorrower(id) {{
  const rec = getRecord(id);
  currentBorrowerId = id;

  const badge = document.getElementById('composite-badge');
  badge.className = 'composite-badge badge-' + rec.composite_rag;
  document.getElementById('composite-score').innerHTML =
    '<span class="rag-dot rag-' + rec.composite_rag + '"></span>' + (rec.composite_score !== null ? rec.composite_score : 'N/A');
  document.getElementById('grade').textContent = rec.grade || '--';
  document.getElementById('segment').textContent = rec.segment_label || '';
  renderContextStrip(rec.context);
  document.getElementById('commentary').textContent = rec.commentary || '';

  const dimList = document.getElementById('dim-list');
  dimList.innerHTML = '';
  rec.dimensions.forEach((d, idx) => {{
    const card = document.createElement('div');
    card.className = 'dim-card' + (idx < 2 ? ' expanded' : '');
    const scoreText = d.score !== null ? d.score : '—';

    const header = document.createElement('div');
    header.className = 'dim-header';
    header.innerHTML = `
      <span class="dim-title"><span class="rag-dot rag-${{d.rag}}"></span>${{d.label}}${{d.overridden ? '<span class="overridden-tag">overridden</span>' : ''}}<span class="dim-caret">&#9656;</span></span>
      <span class="dim-score">${{scoreText}}${{scoreText !== '—' ? ' <span style=\\'font-size:10px;color:var(--muted);\\'>(' + d.score_10 + '/{param_scale})</span>' : ''}}</span>
    `;
    header.addEventListener('click', () => card.classList.toggle('expanded'));
    card.appendChild(header);

    const body = document.createElement('div');
    body.className = 'dim-body';

    if (d.note) {{
      const noteDiv = document.createElement('div');
      noteDiv.className = 'drivers note';
      noteDiv.textContent = d.note;
      body.appendChild(noteDiv);
    }} else {{
      const driverDiv = document.createElement('div');
      if (d.top_positive) driverDiv.innerHTML += `<div class="drivers driver-pos">&#9650; ${{d.top_positive}}</div>`;
      if (d.top_negative) driverDiv.innerHTML += `<div class="drivers driver-neg">&#9660; ${{d.top_negative}}</div>`;
      body.appendChild(driverDiv);
    }}

    // Scorecard table: Parameter | Actual value (as of ...) | Model score | Override
    const table = document.createElement('table');
    table.className = 'scorecard';
    table.innerHTML = `<thead><tr><th>Parameter</th><th>Actual value</th><th>Model score</th><th>Override</th></tr></thead>`;
    const tbody = document.createElement('tbody');

    // Overall C row first
    const dimBoxId = `ov-${{id}}-${{d.key}}`;
    const dimInfoId = `info-${{id}}-${{d.key}}`;
    const dimTr = document.createElement('tr');
    dimTr.innerHTML = `
      <td><span class="param-cell"><strong>Overall ${{d.label}} score</strong></span></td>
      <td class="value-cell">—</td>
      <td class="score-cell${{d.overridden ? ' score-overridden' : ''}}">${{fmtScore10(d.score_10)}}</td>
      <td class="override-cell"><button class="override-link" type="button">override</button></td>
    `;
    tbody.appendChild(dimTr);
    dimTr.querySelector('.param-cell').appendChild(buildInfoButton(dimInfoId));
    dimTr.querySelector('.override-link').addEventListener('click', () => openOverrideBox(dimBoxId));
    const dimInfoRow = document.createElement('tr');
    const dimInfoTd = document.createElement('td');
    dimInfoTd.colSpan = 4;
    dimInfoTd.appendChild(buildInfoNote(dimInfoId, DIM_METHODOLOGY_NOTE));
    dimInfoRow.appendChild(dimInfoTd);
    tbody.appendChild(dimInfoRow);
    const dimOverrideRow = document.createElement('tr');
    const dimOverrideTd = document.createElement('td');
    dimOverrideTd.colSpan = 4;
    dimOverrideTd.appendChild(buildOverrideBox(id, d.key, null, d.score, dimBoxId));
    dimOverrideRow.appendChild(dimOverrideTd);
    tbody.appendChild(dimOverrideRow);

    d.submetrics.forEach(sm => {{
      const label = FEATURE_LABELS[sm.key] || sm.key;
      const boxId = `ov-${{id}}-${{d.key}}-${{sm.key}}`;
      const infoId = `info-${{id}}-${{d.key}}-${{sm.key}}`;
      const naTag = sm.status === 'not_applicable' ? '<span class="na-tag">N/A</span>' :
                    sm.status === 'insufficient_data' ? '<span class="na-tag">thin data</span>' : '';
      const mlTag = sm.ml_advised ? `<span class="ml-advised-tag" title="${{ML_STRINGS.advised_tag_tooltip}}">${{ML_STRINGS.advised_tag_label}}</span>` : '';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="param-cell"><span class="rag-dot rag-${{sm.rag}}"></span>${{label}}${{naTag}}${{mlTag}}</span>${{sm.note ? '<span class="sub-note">' + sm.note + '</span>' : ''}}</td>
        <td class="value-cell">${{sm.display_value !== null && sm.display_value !== undefined ? '<span class="value-main">' + sm.display_value + '</span>' : '—'}}${{sm.period ? '<span class="value-period">' + sm.period + '</span>' : ''}}</td>
        <td class="score-cell${{sm.overridden ? ' score-overridden' : ''}}">${{fmtScore10(sm.score_10)}}${{sm.overridden ? '<span class="overridden-tag">override</span>' : ''}}</td>
        <td class="override-cell"><button class="override-link" type="button">override</button></td>
      `;
      tbody.appendChild(tr);
      tr.querySelector('.param-cell').appendChild(buildInfoButton(infoId));
      tr.querySelector('.override-link').addEventListener('click', () => openOverrideBox(boxId));

      const infoRow = document.createElement('tr');
      const infoTd = document.createElement('td');
      infoTd.colSpan = 4;
      infoTd.appendChild(buildInfoNote(infoId, METHODOLOGY[sm.key] || 'Methodology details not available for this submetric.'));
      infoRow.appendChild(infoTd);
      tbody.appendChild(infoRow);

      const overrideRow = document.createElement('tr');
      const overrideTd = document.createElement('td');
      overrideTd.colSpan = 4;
      overrideTd.appendChild(buildOverrideBox(id, d.key, sm.key, sm.score, boxId));
      overrideRow.appendChild(overrideTd);
      tbody.appendChild(overrideRow);
    }});

    table.appendChild(tbody);
    body.appendChild(table);

    card.appendChild(body);
    dimList.appendChild(card);
  }});

  renderMlSection(id);
  renderMainChart(rec);
  renderTrendChart(rec);
}}

function renderMainChart(rec) {{
  if (mainChart) {{ mainChart.destroy(); mainChart = null; }}
  const ctxEl = document.getElementById('main-chart');
  const dims = rec.dimensions;
  const labels = dims.map(d => d.label);
  const scores = dims.map(d => d.score !== null ? d.score : 0);
  const colors = dims.map(d => d.rag === 'green' ? '#1f9254' : d.rag === 'amber' ? '#c98a12' : d.rag === 'red' ? '#c53434' : '#9aa79f');
  document.getElementById('chart-caption').textContent = CHART_CAPTIONS[currentChartType] || '';

  if (currentChartType === 'radar') {{
    mainChart = new Chart(ctxEl, {{
      type: 'radar',
      data: {{ labels, datasets: [{{ label: rec.borrower_id, data: scores, backgroundColor: 'rgba(11,110,61,0.20)', borderColor: '#0b6e3d', pointBackgroundColor: '#0b6e3d' }}] }},
      options: {{ scales: {{ r: {{ min: 0, max: 100, ticks: {{ color: '#5c6f64', backdropColor: 'transparent' }}, grid: {{ color: '#d7e5dc' }}, angleLines: {{ color: '#d7e5dc' }}, pointLabels: {{ color: '#1a2b22', font: {{ size: 11 }} }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
    }});
  }} else if (currentChartType === 'bar') {{
    mainChart = new Chart(ctxEl, {{
      type: 'bar',
      data: {{ labels, datasets: [{{ label: 'Score (0-100)', data: scores, backgroundColor: colors }}] }},
      options: {{ indexAxis: 'y', scales: {{ x: {{ min: 0, max: 100, title: {{ display: true, text: 'Score (0-100)' }}, grid: {{ color: '#d7e5dc' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
    }});
  }} else if (currentChartType === 'donut') {{
    const contributions = dims.map(d => (d.score !== null && d.weight) ? Math.round(d.score * d.weight * 10) / 10 : 0);
    mainChart = new Chart(ctxEl, {{
      type: 'doughnut',
      data: {{ labels, datasets: [{{ data: contributions, backgroundColor: colors }}] }},
      options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#1a2b22' }} }}, tooltip: {{ callbacks: {{ label: (c) => c.label + ': ' + c.raw + ' pts of composite' }} }} }} }}
    }});
  }} else if (currentChartType === 'gauge') {{
    const score = rec.composite_score !== null ? rec.composite_score : 0;
    const gaugeColor = rec.composite_rag === 'green' ? '#1f9254' : rec.composite_rag === 'amber' ? '#c98a12' : '#c53434';
    mainChart = new Chart(ctxEl, {{
      type: 'doughnut',
      data: {{ labels: ['Score', ''], datasets: [{{ data: [score, 100 - score], backgroundColor: [gaugeColor, '#e4f2e9'], borderWidth: 0 }}] }},
      options: {{ circumference: 180, rotation: 270, cutout: '70%', plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }} }},
      plugins: [{{
        id: 'gaugeText',
        afterDraw: (chart) => {{
          const {{ctx, chartArea}} = chart;
          ctx.save();
          ctx.font = 'bold 28px sans-serif';
          ctx.fillStyle = gaugeColor;
          ctx.textAlign = 'center';
          ctx.fillText(score, (chartArea.left + chartArea.right) / 2, chartArea.bottom - 10);
          ctx.restore();
        }}
      }}]
    }});
  }} else if (currentChartType === 'waterfall') {{
    let running = 0;
    const floatData = [];
    const wLabels = [];
    dims.forEach(d => {{
      const contrib = (d.score !== null && d.weight) ? d.score * d.weight : 0;
      floatData.push([running, running + contrib]);
      wLabels.push(d.label);
      running += contrib;
    }});
    wLabels.push('Composite');
    floatData.push([0, running]);
    const wColors = [...colors, '#0b6e3d'];
    mainChart = new Chart(ctxEl, {{
      type: 'bar',
      data: {{ labels: wLabels, datasets: [{{ data: floatData, backgroundColor: wColors }}] }},
      options: {{ scales: {{ y: {{ min: 0, max: 100, title: {{ display: true, text: 'Composite score (0-100)' }}, grid: {{ color: '#d7e5dc' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
    }});
  }}
}}

function renderTrendChart(rec) {{
  const trendLabels = rec.trend.map(t => (t.frac * 100).toFixed(0) + '%');
  const trendValues = rec.trend.map(t => t.value);

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById('trend-chart'), {{
    type: 'line',
    data: {{
      labels: trendLabels,
      datasets: [{{
        label: 'Trend indicator (0-100)',
        data: trendValues,
        borderColor: '#0b6e3d',
        backgroundColor: 'rgba(11,110,61,0.12)',
        tension: 0.3,
        fill: true,
      }}]
    }},
    options: {{
      scales: {{
        y: {{ min: 0, max: 100, title: {{ display: true, text: 'Trend indicator (0-100, higher = healthier)', color: '#1a2b22' }}, ticks: {{ color: '#5c6f64' }}, grid: {{ color: '#d7e5dc' }} }},
        x: {{ ticks: {{ color: '#5c6f64' }}, grid: {{ color: '#d7e5dc' }}, title: {{ display: true, text: '% of this borrower\\'s observed history', color: '#1a2b22' }} }}
      }},
      plugins: {{
        legend: {{ labels: {{ color: '#1a2b22' }} }},
        tooltip: {{ callbacks: {{ label: (c) => 'Trend indicator: ' + c.raw + ' / 100' }} }}
      }}
    }}
  }});
}}

document.getElementById('borrower-search').addEventListener('change', (e) => {{ if (ORIGINAL_DATA[e.target.value]) renderBorrower(e.target.value); }});
document.getElementById('borrower-search').addEventListener('input', (e) => {{ if (ORIGINAL_DATA[e.target.value]) renderBorrower(e.target.value); }});

updateOverrideCount();
document.getElementById('borrower-search').value = IDS[0];
renderBorrower(IDS[0]);
</script>

</body>
</html>
"""
