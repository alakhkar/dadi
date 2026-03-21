"""
dashboard.py — Builds the self-contained admin analytics HTML page.
Called by the /admin/analytics FastAPI route in app.py.
"""

import json


def build_dashboard_html(data: dict) -> str:
    kpi   = (data.get("v_kpi_summary") or [{}])[0]
    dau   = data.get("v_dau", [])
    ratio = data.get("v_user_type_ratio", [])
    rag   = data.get("v_rag_usage", [])
    top_s = data.get("v_top_starters", [])
    funnel= data.get("v_otp_funnel", [{}])[0] if data.get("v_otp_funnel") else {}
    mem   = data.get("v_memory_extractions", [])
    sess  = data.get("v_session_stats", [])

    # DAU chart data
    dau_sorted   = sorted(dau, key=lambda r: r.get("day", ""))
    dau_labels   = [r.get("day", "")[:10] for r in dau_sorted]
    dau_total    = [r.get("unique_users", 0) for r in dau_sorted]
    dau_reg      = [r.get("registered_users", 0) for r in dau_sorted]
    dau_guest    = [r.get("guest_users", 0) for r in dau_sorted]

    # User type doughnut
    ratio_labels = [r.get("user_type", "") for r in ratio]
    ratio_vals   = [r.get("session_count", 0) for r in ratio]

    # RAG chart
    rag_sorted  = sorted(rag, key=lambda r: r.get("day", ""))
    rag_labels  = [r.get("day", "")[:10] for r in rag_sorted]
    rag_total   = [r.get("total_messages", 0) for r in rag_sorted]
    rag_pct     = [float(r.get("rag_pct", 0) or 0) for r in rag_sorted]

    # Top starters
    starters_labels = [r.get("starter_label", "") for r in top_s[:10]]
    starters_vals   = [r.get("uses", 0) for r in top_s[:10]]

    # Memory extraction chart
    mem_days = sorted({r.get("day", "")[:10] for r in mem})
    mem_periodic   = []
    mem_session_end = []
    for day in mem_days:
        p = sum(r.get("total_facts_saved", 0) or 0 for r in mem
                if r.get("day", "")[:10] == day and r.get("trigger") == "periodic")
        s = sum(r.get("total_facts_saved", 0) or 0 for r in mem
                if r.get("day", "")[:10] == day and r.get("trigger") == "session_end")
        mem_periodic.append(p)
        mem_session_end.append(s)

    # Session depth histogram
    buckets = {"1": 0, "2-5": 0, "6-10": 0, "11-20": 0, "20+": 0}
    for r in sess:
        mc = r.get("message_count") or 0
        if mc == 1:       buckets["1"]     += 1
        elif mc <= 5:     buckets["2-5"]   += 1
        elif mc <= 10:    buckets["6-10"]  += 1
        elif mc <= 20:    buckets["11-20"] += 1
        else:             buckets["20+"]   += 1

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dadi AI — Analytics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', sans-serif;
    background: #FDF6F0;
    color: #2d1a10;
    padding: 2rem;
    min-height: 100vh;
  }}
  h1 {{
    font-family: 'Playfair Display', serif;
    color: #8B1A1A;
    font-size: 1.8rem;
    margin-bottom: 0.25rem;
  }}
  .subtitle {{ color: #9e7a5a; font-size: 0.85rem; margin-bottom: 2rem; }}
  /* KPI row */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
  }}
  .kpi-card {{
    background: #fff;
    border: 1px solid #f0d9c8;
    border-radius: 12px;
    padding: 1.25rem 1rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(139,26,26,.06);
  }}
  .kpi-card .val {{
    font-size: 2rem;
    font-weight: 600;
    color: #8B1A1A;
    line-height: 1;
  }}
  .kpi-card .label {{
    font-size: 0.72rem;
    color: #9e7a5a;
    margin-top: 0.35rem;
    text-transform: uppercase;
    letter-spacing: .05em;
  }}
  /* Charts */
  .charts-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 1.5rem;
  }}
  .chart-card {{
    background: #fff;
    border: 1px solid #f0d9c8;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 4px rgba(139,26,26,.06);
  }}
  .chart-card h2 {{
    font-family: 'Playfair Display', serif;
    font-size: 1rem;
    color: #8B1A1A;
    margin-bottom: 1rem;
  }}
  canvas {{ max-height: 280px; }}
  /* OTP funnel cards */
  .funnel-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }}
  .funnel-card {{
    background: #FEF0E7;
    border-radius: 8px;
    padding: 0.9rem;
    text-align: center;
  }}
  .funnel-card .fval {{ font-size: 1.6rem; font-weight: 600; color: #8B1A1A; }}
  .funnel-card .flabel {{ font-size: 0.7rem; color: #9e7a5a; text-transform: uppercase; }}
  .conversion-badge {{
    text-align: center;
    font-size: 0.85rem;
    color: #2e7d32;
    font-weight: 500;
    margin-top: 0.5rem;
  }}
</style>
</head>
<body>
<h1>Dadi AI — Analytics</h1>
<p class="subtitle">Last updated on page load &nbsp;·&nbsp; All data from Supabase</p>

<!-- KPI Row -->
<div class="kpi-grid">
  <div class="kpi-card"><div class="val">{kpi.get('dau') or 0}</div><div class="label">DAU (today)</div></div>
  <div class="kpi-card"><div class="val">{kpi.get('wau') or 0}</div><div class="label">WAU (7 days)</div></div>
  <div class="kpi-card"><div class="val">{kpi.get('mau') or 0}</div><div class="label">MAU (30 days)</div></div>
  <div class="kpi-card"><div class="val">{kpi.get('messages_today') or 0}</div><div class="label">Messages today</div></div>
  <div class="kpi-card"><div class="val">{kpi.get('avg_messages_per_session') or '—'}</div><div class="label">Avg msg/session (7d)</div></div>
  <div class="kpi-card"><div class="val">{kpi.get('avg_session_minutes') or '—'}</div><div class="label">Avg duration min (7d)</div></div>
</div>

<!-- Charts -->
<div class="charts-grid">

  <!-- DAU trend -->
  <div class="chart-card" style="grid-column: 1 / -1;">
    <h2>Daily Active Users — last 30 days</h2>
    <canvas id="dauChart"></canvas>
  </div>

  <!-- User type doughnut -->
  <div class="chart-card">
    <h2>User Type Split (30 days)</h2>
    <canvas id="ratioChart"></canvas>
  </div>

  <!-- Session depth histogram -->
  <div class="chart-card">
    <h2>Session Depth — messages per session (30 days)</h2>
    <canvas id="depthChart"></canvas>
  </div>

  <!-- RAG usage -->
  <div class="chart-card" style="grid-column: 1 / -1;">
    <h2>RAG Usage Rate — last 30 days</h2>
    <canvas id="ragChart"></canvas>
  </div>

  <!-- Top starters -->
  <div class="chart-card" style="grid-column: 1 / -1;">
    <h2>Top Starter Prompts (30 days)</h2>
    <canvas id="startersChart"></canvas>
  </div>

  <!-- OTP funnel -->
  <div class="chart-card">
    <h2>OTP Funnel (30 days)</h2>
    <div class="funnel-grid">
      <div class="funnel-card"><div class="fval">{funnel.get('requested') or 0}</div><div class="flabel">Requested</div></div>
      <div class="funnel-card"><div class="fval">{funnel.get('verified') or 0}</div><div class="flabel">Verified</div></div>
      <div class="funnel-card"><div class="fval">{funnel.get('failed') or 0}</div><div class="flabel">Failed</div></div>
    </div>
    <div class="conversion-badge">Conversion: {funnel.get('conversion_pct') or 0}%</div>
  </div>

  <!-- Memory extractions -->
  <div class="chart-card">
    <h2>Memory Facts Saved per Day (30 days)</h2>
    <canvas id="memChart"></canvas>
  </div>

</div>

<script>
const RED   = '#8B1A1A';
const PEACH = '#FEF0E7';
const AMBER = '#c0610a';
const TEAL  = '#2e7d77';
const GRID  = 'rgba(139,26,26,.08)';

Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.color = '#9e7a5a';

// DAU trend
new Chart(document.getElementById('dauChart'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(dau_labels)},
    datasets: [
      {{ label: 'Total', data: {json.dumps(dau_total)}, borderColor: RED,   backgroundColor: 'rgba(139,26,26,.08)', tension: 0.3, fill: true }},
      {{ label: 'Registered', data: {json.dumps(dau_reg)},   borderColor: AMBER, tension: 0.3, fill: false }},
      {{ label: 'Guest',      data: {json.dumps(dau_guest)}, borderColor: TEAL,  tension: 0.3, fill: false }},
    ]
  }},
  options: {{ plugins: {{ legend: {{ position: 'top' }} }}, scales: {{ y: {{ beginAtZero: true, grid: {{ color: GRID }} }}, x: {{ grid: {{ color: GRID }} }} }} }}
}});

// User type doughnut
new Chart(document.getElementById('ratioChart'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps(ratio_labels)},
    datasets: [{{ data: {json.dumps(ratio_vals)}, backgroundColor: [RED, AMBER, TEAL, '#6d4c41'] }}]
  }},
  options: {{ plugins: {{ legend: {{ position: 'bottom' }} }}, cutout: '60%' }}
}});

// Session depth
new Chart(document.getElementById('depthChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(list(buckets.keys()))},
    datasets: [{{ label: 'Sessions', data: {json.dumps(list(buckets.values()))}, backgroundColor: RED, borderRadius: 6 }}]
  }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, grid: {{ color: GRID }} }}, x: {{ grid: {{ color: GRID }} }} }} }}
}});

// RAG usage (dual axis)
new Chart(document.getElementById('ragChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(rag_labels)},
    datasets: [
      {{ type: 'bar',  label: 'Total messages', data: {json.dumps(rag_total)}, backgroundColor: 'rgba(139,26,26,.15)', yAxisID: 'y', borderRadius: 4 }},
      {{ type: 'line', label: 'RAG used %',     data: {json.dumps(rag_pct)},  borderColor: AMBER, tension: 0.3, yAxisID: 'y1', fill: false }},
    ]
  }},
  options: {{
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{
      y:  {{ beginAtZero: true, grid: {{ color: GRID }}, title: {{ display: true, text: 'Messages' }} }},
      y1: {{ beginAtZero: true, position: 'right', max: 100, grid: {{ drawOnChartArea: false }}, title: {{ display: true, text: '% RAG' }} }},
      x:  {{ grid: {{ color: GRID }} }}
    }}
  }}
}});

// Top starters (horizontal bar)
new Chart(document.getElementById('startersChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(starters_labels)},
    datasets: [{{ label: 'Uses', data: {json.dumps(starters_vals)}, backgroundColor: RED, borderRadius: 4 }}]
  }},
  options: {{
    indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true, grid: {{ color: GRID }} }}, y: {{ grid: {{ color: GRID }} }} }}
  }}
}});

// Memory extractions stacked bar
new Chart(document.getElementById('memChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(mem_days)},
    datasets: [
      {{ label: 'Periodic',    data: {json.dumps(mem_periodic)},    backgroundColor: RED,   borderRadius: 4 }},
      {{ label: 'Session end', data: {json.dumps(mem_session_end)}, backgroundColor: AMBER, borderRadius: 4 }},
    ]
  }},
  options: {{
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{ x: {{ stacked: true, grid: {{ color: GRID }} }}, y: {{ stacked: true, beginAtZero: true, grid: {{ color: GRID }} }} }}
  }}
}});
</script>
</body>
</html>"""
