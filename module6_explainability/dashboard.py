"""
Builds a standalone HTML dashboard: borrower selector, radar chart across
the 5 scorable dimensions, composite score + grade, top drivers per
dimension, and the trend view. All 400 borrowers' data is embedded as JSON
in the page itself - it works offline/standalone once loaded, no server,
no database. Only Chart.js is pulled from a CDN.
"""

import json
from config import DIMENSIONS, DIMENSION_LABELS


def _build_borrower_records(scores_df, segmentation_df, drivers_df, trend_df):
    seg_lookup = segmentation_df.set_index("borrower_id").to_dict("index")
    driver_lookup = drivers_df.set_index("borrower_id").to_dict("index")
    trend_lookup = {}
    for bid, g in trend_df.groupby("borrower_id"):
        g = g.sort_values("checkpoint_frac")
        trend_lookup[bid] = [
            {"frac": row["checkpoint_frac"], "value": None if pd_isna(row["trend_indicator"]) else round(row["trend_indicator"], 1)}
            for _, row in g.iterrows()
        ]

    records = {}
    for _, row in scores_df.iterrows():
        bid = row["borrower_id"]
        seg = seg_lookup.get(bid, {})
        drv = driver_lookup.get(bid, {})

        dims = []
        for d in DIMENSIONS:
            score_col = f"{d}_score"
            weight_col = f"{d}_effective_weight"
            status_col = f"{d}_status"
            dims.append({
                "key": d,
                "label": DIMENSION_LABELS[d],
                "score": None if score_col not in row or pd_isna(row.get(score_col)) else round(row[score_col], 1),
                "weight": seg.get(weight_col),
                "status": seg.get(status_col, ""),
                "top_positive": drv.get(f"{d}_top_positive"),
                "top_negative": drv.get(f"{d}_top_negative"),
                "note": drv.get(f"{d}_driver_note", ""),
            })

        records[bid] = {
            "borrower_id": bid,
            "composite_score": None if pd_isna(row.get("composite_score")) else round(row["composite_score"], 1),
            "grade": row.get("grade"),
            "segment_label": row.get("segment_label"),
            "dimensions": dims,
            "trend": trend_lookup.get(bid, []),
        }
    return records


def pd_isna(v):
    try:
        return v != v  # NaN != NaN is True; works without importing pandas here
    except Exception:
        return v is None


def build_dashboard(scores_df, segmentation_df, drivers_df, trend_df, out_path):
    records = _build_borrower_records(scores_df, segmentation_df, drivers_df, trend_df)
    borrower_ids = sorted(records.keys())
    data_json = json.dumps(records)
    ids_json = json.dumps(borrower_ids)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MSME Financial Health Score — Explainability Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1420; --panel: #1a2233; --border: #2a3550; --text: #e8ecf5; --muted: #8b96ad;
    --accent: #5b8def; --good: #3ecf8e; --bad: #ef5b5b; --warn: #e8b84b;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: var(--bg); color: var(--text); }}
  header {{ padding: 20px 28px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  h1 {{ font-size: 18px; margin: 0; font-weight: 600; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
  select, input {{ background: var(--panel); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: 14px; }}
  .layout {{ display: grid; grid-template-columns: 340px 1fr; gap: 20px; padding: 20px 28px; max-width: 1200px; margin: 0 auto; }}
  @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }}
  .composite-badge {{ text-align: center; padding: 20px 0; }}
  .composite-score {{ font-size: 48px; font-weight: 700; }}
  .grade {{ font-size: 16px; color: var(--muted); margin-top: 4px; }}
  .segment {{ font-size: 12px; color: var(--muted); margin-top: 10px; line-height: 1.4; }}
  .dim-row {{ border-top: 1px solid var(--border); padding: 10px 0; }}
  .dim-row:first-child {{ border-top: none; }}
  .dim-name {{ font-size: 13px; font-weight: 600; display: flex; justify-content: space-between; }}
  .dim-score {{ color: var(--accent); }}
  .dim-meta {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
  .drivers {{ font-size: 12px; margin-top: 6px; }}
  .driver-pos {{ color: var(--good); }}
  .driver-neg {{ color: var(--bad); }}
  .note {{ color: var(--warn); font-style: italic; }}
  canvas {{ max-height: 380px; }}
  .footer-note {{ font-size: 11px; color: var(--muted); line-height: 1.6; padding: 16px 28px 28px; max-width: 1200px; margin: 0 auto; }}
  .na-tag {{ font-size: 10px; background: var(--border); color: var(--muted); padding: 1px 6px; border-radius: 4px; margin-left: 6px; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>MSME Financial Health Score — Explainability Dashboard</h1>
    <div class="subtitle">Module 6 · Track 3 · radar view, top drivers, and directional trend per borrower</div>
  </div>
  <div>
    <input list="borrower-list" id="borrower-search" placeholder="Type or pick a borrower ID..." />
    <datalist id="borrower-list"></datalist>
  </div>
</header>

<div class="layout">
  <div class="panel">
    <div class="composite-badge">
      <div class="composite-score" id="composite-score">--</div>
      <div class="grade" id="grade">--</div>
      <div class="segment" id="segment">--</div>
    </div>
    <div id="dim-list"></div>
  </div>

  <div>
    <div class="panel" style="margin-bottom:20px;">
      <canvas id="radar-chart"></canvas>
      <div class="footer-note" style="padding:10px 0 0;">
        Concentration Risk isn't shown — Module 1 has no counterparty-level data, so this dimension is not computable in this prototype (not a borrower-specific gap).
      </div>
    </div>
    <div class="panel">
      <canvas id="trend-chart"></canvas>
      <div class="footer-note" style="padding:10px 0 0;">
        Trend indicator uses only bank balance, cheque bounce rate, and GST on-time filing — a robust proxy, NOT a replay of the full Module 5 composite methodology at each checkpoint. Checkpoints are 25/50/75/100% of each borrower's own observed history (not fixed calendar months), since some borrowers have as little as ~3.5 months of data.
      </div>
    </div>
  </div>
</div>

<div class="footer-note">
  Synthetic data (see Module 1 README). Percentile-based scores are relative to this 400-borrower batch, not a fixed portable scale.
  See module5_scoring/README.md and module6_explainability/README.md for full methodology and known limitations.
</div>

<script>
const DATA = {data_json};
const IDS = {ids_json};

const datalist = document.getElementById('borrower-list');
IDS.forEach(id => {{
  const opt = document.createElement('option');
  opt.value = id;
  datalist.appendChild(opt);
}});

let radarChart, trendChart;

function renderBorrower(id) {{
  const rec = DATA[id];
  if (!rec) return;

  document.getElementById('composite-score').textContent = rec.composite_score !== null ? rec.composite_score : 'N/A';
  document.getElementById('grade').textContent = rec.grade || '--';
  document.getElementById('segment').textContent = rec.segment_label || '';

  const dimList = document.getElementById('dim-list');
  dimList.innerHTML = '';
  rec.dimensions.forEach(d => {{
    const div = document.createElement('div');
    div.className = 'dim-row';
    const naTag = (d.status === 'not_applicable') ? '<span class="na-tag">N/A</span>' :
                  (d.status === 'insufficient_data') ? '<span class="na-tag">thin data</span>' : '';
    const scoreText = d.score !== null ? d.score : '—';
    let driverHtml = '';
    if (d.note) {{
      driverHtml = `<div class="drivers note">${{d.note}}</div>`;
    }} else {{
      if (d.top_positive) driverHtml += `<div class="drivers driver-pos">&#9650; ${{d.top_positive}}</div>`;
      if (d.top_negative) driverHtml += `<div class="drivers driver-neg">&#9660; ${{d.top_negative}}</div>`;
    }}
    div.innerHTML = `
      <div class="dim-name"><span>${{d.label}}${{naTag}}</span><span class="dim-score">${{scoreText}}</span></div>
      <div class="dim-meta">weight: ${{d.weight !== null && d.weight !== undefined ? (d.weight*100).toFixed(0)+'%' : '--'}}</div>
      ${{driverHtml}}
    `;
    dimList.appendChild(div);
  }});

  const radarLabels = rec.dimensions.map(d => d.label.replace(' (not computable - no data source)', ''));
  const radarValues = rec.dimensions.map(d => d.score !== null ? d.score : 0);

  if (radarChart) radarChart.destroy();
  radarChart = new Chart(document.getElementById('radar-chart'), {{
    type: 'radar',
    data: {{
      labels: radarLabels,
      datasets: [{{
        label: id,
        data: radarValues,
        backgroundColor: 'rgba(91,141,239,0.25)',
        borderColor: '#5b8def',
        pointBackgroundColor: '#5b8def',
      }}]
    }},
    options: {{
      scales: {{ r: {{ min: 0, max: 100, ticks: {{ color: '#8b96ad', backdropColor: 'transparent' }}, grid: {{ color: '#2a3550' }}, angleLines: {{ color: '#2a3550' }}, pointLabels: {{ color: '#e8ecf5', font: {{ size: 11 }} }} }} }},
      plugins: {{ legend: {{ display: false }} }}
    }}
  }});

  const trendLabels = rec.trend.map(t => (t.frac*100).toFixed(0) + '%');
  const trendValues = rec.trend.map(t => t.value);

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById('trend-chart'), {{
    type: 'line',
    data: {{
      labels: trendLabels,
      datasets: [{{
        label: 'Trend indicator (0-100)',
        data: trendValues,
        borderColor: '#3ecf8e',
        backgroundColor: 'rgba(62,207,142,0.15)',
        tension: 0.3,
        fill: true,
      }}]
    }},
    options: {{
      scales: {{
        y: {{ min: 0, max: 100, ticks: {{ color: '#8b96ad' }}, grid: {{ color: '#2a3550' }} }},
        x: {{ ticks: {{ color: '#8b96ad' }}, grid: {{ color: '#2a3550' }}, title: {{ display: true, text: '% of observed history', color: '#8b96ad' }} }}
      }},
      plugins: {{ legend: {{ labels: {{ color: '#e8ecf5' }} }} }}
    }}
  }});
}}

document.getElementById('borrower-search').addEventListener('change', (e) => {{
  if (DATA[e.target.value]) renderBorrower(e.target.value);
}});
document.getElementById('borrower-search').addEventListener('input', (e) => {{
  if (DATA[e.target.value]) renderBorrower(e.target.value);
}});

// Initial render
document.getElementById('borrower-search').value = IDS[0];
renderBorrower(IDS[0]);
</script>

</body>
</html>
"""
    with open(out_path, "w") as f:
        f.write(html)
