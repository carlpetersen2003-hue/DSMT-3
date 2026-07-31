#!/usr/bin/env python3
"""Génère un fichier HTML autonome à partir de Suivi_contributions_dsmt.xls."""

import json
import re
import sys
from pathlib import Path

import xlrd

XLS_PATH = Path(__file__).parent / "Suivi_contributions_dsmt.xls"
HTML_PATH = Path(__file__).parent / "contributions_dsmt.html"
CHART_JS_PATH = Path("/tmp/chart.umd.min.js")

CATEGORY_RE = re.compile(r"^(\d+)\s*-\s*(.+)$")
DONT_RE = re.compile(r"^dont\s+", re.I)


def cell_value(cell, wb):
    if cell.ctype == xlrd.XL_CELL_DATE:
        dt = xlrd.xldate_as_datetime(cell.value, wb.datemode)
        return dt.strftime("%d/%m/%Y")
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return ""
    return cell.value


def parse_mandatory(wb):
    sh = wb.sheet_by_name("Contributions obligatoires")
    headers = [cell_value(sh.cell(0, c), wb) for c in range(sh.ncols)]
    items = []
    for r in range(1, sh.nrows):
        name = str(sh.cell_value(r, 0)).strip()
        if not name or name.lower() == "total":
            continue
        row = {"name": name}
        for c in range(1, sh.ncols):
            val = cell_value(sh.cell(r, c), wb)
            row[headers[c]] = val if val != "" else None
        items.append(row)
    return {"headers": headers, "items": items}


def parse_voluntary_sheet(sh, wb, year):
    amount_col = f"{year} (€)"
    items = []
    categories = []
    current_category = None
    current_subtotal = None

    for r in range(1, sh.nrows):
        org = str(sh.cell_value(r, 0)).strip()
        amount = sh.cell_value(r, 1)
        nature = str(sh.cell_value(r, 2)).strip() if sh.ncols > 2 else ""

        if not org:
            continue

        if org.upper().startswith("TOTAL"):
            current_subtotal = {
                "label": org,
                "amount": float(amount) if amount != "" else None,
            }
            continue

        if org == "Contributions Volontaires":
            continue

        m = CATEGORY_RE.match(org)
        if m and not DONT_RE.match(org):
            current_category = {
                "id": int(m.group(1)),
                "name": m.group(2).strip(),
                "amount": float(amount) if amount != "" else None,
            }
            categories.append(current_category)
            continue

        if DONT_RE.match(org):
            parent = categories[-1] if categories else None
            items.append(
                {
                    "organisme": org,
                    "amount": float(amount) if amount != "" else None,
                    "nature": nature,
                    "category": parent["name"] if parent else None,
                    "category_id": parent["id"] if parent else None,
                    "is_breakdown": True,
                    "year": year,
                }
            )
            continue

        items.append(
            {
                "organisme": org,
                "amount": float(amount) if amount != "" else None,
                "nature": nature,
                "category": current_category["name"] if current_category else None,
                "category_id": current_category["id"] if current_category else None,
                "is_breakdown": False,
                "year": year,
            }
        )

    return {
        "year": year,
        "categories": categories,
        "items": items,
        "totals": current_subtotal,
    }


def parse_voluntary(wb):
    years = []
    for sheet_name in wb.sheet_names():
        m = re.match(r"^(\d{4})\s*-\s*DSMT$", sheet_name)
        if not m:
            continue
        year = int(m.group(1))
        sh = wb.sheet_by_name(sheet_name)
        years.append(parse_voluntary_sheet(sh, wb, year))
    return sorted(years, key=lambda y: y["year"])


def build_data():
    wb = xlrd.open_workbook(str(XLS_PATH))
    return {
        "mandatory": parse_mandatory(wb),
        "voluntary": parse_voluntary(wb),
        "generated_from": XLS_PATH.name,
    }


def load_chart_js():
    if CHART_JS_PATH.exists():
        return CHART_JS_PATH.read_text(encoding="utf-8")
    return ""


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contributions de la France à la Conférence du désarmement</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #f7f5f0;
  --surface: #ffffff;
  --surface2: #f0ede6;
  --border: rgba(40,35,20,0.12);
  --border2: rgba(40,35,20,0.22);
  --text: #1a1814;
  --text2: #6b6458;
  --accent: #2c5f8a;
  --accent2: #1a7a5e;
  --ac-vc: #8a2c2c;
  --gold: #b07d2a;
  --radius: 10px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04);
}
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}
header {
  background:
    linear-gradient(rgba(255,255,255,0.55), rgba(247,245,240,0.82)),
    url('https://www.geneve.ch/sites/default/files/styles/max_1280/public/2023-08/palais-nations-cover-02.jpg.webp?itok=dLlVoecQ') center/cover,
    linear-gradient(135deg, #b8cfe0 0%, #d4e4ef 35%, #e8dfd0 100%);
  color: var(--text);
  padding: 2.5rem 2rem 2rem;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  border-bottom: 1px solid var(--border);
}
header h1 {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.85rem;
  font-weight: 400;
  letter-spacing: -0.3px;
  background: rgba(255,255,255,0.82);
  padding: 0.55rem 1rem;
  width: fit-content;
  max-width: 900px;
  line-height: 1.25;
  box-shadow: var(--shadow);
  border-radius: 6px;
}
nav.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  padding: 0 2rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}
nav.tabs button {
  border: none;
  background: transparent;
  padding: 0.85rem 1.15rem;
  cursor: pointer;
  font-size: 0.83rem;
  font-weight: 400;
  color: var(--text2);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.15s;
  font-family: inherit;
}
nav.tabs button:hover { color: var(--accent); }
nav.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 500;
}
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.75rem 2rem 2.5rem;
}
.panel { display: none; }
.panel.active {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}
.kpi-row.compact {
  grid-template-columns: repeat(auto-fill, minmax(200px, 260px));
  justify-content: start;
}
.kpi {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.1rem 1.3rem;
  box-shadow: var(--shadow);
}
.kpi-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text2);
  font-weight: 500;
  margin-bottom: 0.45rem;
}
.kpi-val {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.65rem;
  font-weight: 400;
  color: var(--text);
  line-height: 1.1;
}
.kpi-sub { font-size: 0.75rem; color: var(--text2); margin-top: 0.3rem; }
.kpi.accent .kpi-val { color: var(--accent); }
.kpi.accent2 .kpi-val { color: var(--accent2); }
.kpi.vc .kpi-val { color: var(--ac-vc); }
.toolbar-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem 1.5rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  box-shadow: var(--shadow);
}
.toolbar-panel label {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.toolbar-panel .kpi-row.compact {
  margin-left: auto;
}
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: stretch;
}
.charts-row > .chart-box { min-width: 0; }
.chart-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.4rem;
  box-shadow: var(--shadow);
}
.chart-box h2 {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.05rem;
  font-weight: 400;
  color: var(--text);
  margin-bottom: 1rem;
}
.chart-box.full { grid-column: 1 / -1; }
.chart-container { position: relative; height: 300px; }
.chart-container.tall { height: 340px; }
.chart-container.pie-tall { height: 300px; }
.legend-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-bottom: 0.85rem;
}
.legend-pills button {
  border: 1.5px solid;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 500;
  cursor: pointer;
  background: var(--surface);
  transition: opacity 0.15s, background 0.15s;
  font-family: inherit;
  color: var(--text);
}
.legend-pills button:hover { background: var(--surface2); }
.legend-pills button.inactive { opacity: 0.35; }
.filters, .toolbar-panel select, .toolbar-panel input, .filters select, .filters input {
  font-family: inherit;
  font-size: 0.88rem;
  padding: 6px 10px;
  border: 1px solid var(--border2);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text);
  outline: none;
}
.filters select:focus, .filters input:focus,
.toolbar-panel select:focus { border-color: var(--accent); }
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.9rem 1.1rem;
  box-shadow: var(--shadow);
}
.filters label {
  font-size: 0.72rem;
  font-weight: 500;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.export-btn {
  margin-left: auto;
  font-family: inherit;
  font-size: 0.83rem;
  font-weight: 500;
  padding: 7px 14px;
  border: 1px solid var(--border2);
  border-radius: 6px;
  background: var(--surface);
  color: var(--accent);
  cursor: pointer;
  transition: all 0.15s;
}
.export-btn:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
thead th {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-weight: 500;
  color: var(--text2);
  padding: 0.65rem 0.8rem;
  text-align: left;
  border-bottom: 2px solid var(--border2);
  background: var(--surface2);
}
tbody tr { border-bottom: 1px solid var(--border); transition: background 0.12s; }
tbody tr:hover { background: var(--bg); }
tbody tr.breakdown { color: var(--text2); font-style: italic; }
tbody tr.category-row { background: var(--surface2); font-weight: 500; }
th, td { padding: 0.65rem 0.8rem; vertical-align: top; }
.amount { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.legend-note {
  font-size: 0.74rem;
  color: var(--text2);
  margin-top: 0.75rem;
  padding: 0.55rem 0.75rem;
  background: var(--surface2);
  border-radius: 6px;
  border-left: 3px solid var(--gold);
}
.table-wrap {
  overflow-x: auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.25rem;
}
.table-wrap h2 {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.05rem;
  font-weight: 400;
  margin-bottom: 1rem;
}
footer {
  text-align: center;
  padding: 1.75rem 2rem;
  font-size: 0.75rem;
  color: var(--text2);
  border-top: 1px solid var(--border);
  margin-top: 1rem;
  background: var(--surface2);
}
@media (max-width: 960px) {
  .charts-row { grid-template-columns: 1fr; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  header h1 { font-size: 1.35rem; }
  main, nav.tabs { padding-left: 1rem; padding-right: 1rem; }
  .kpi-row { grid-template-columns: 1fr; }
  .toolbar-panel .kpi-row.compact { margin-left: 0; width: 100%; }
  .chart-container, .chart-container.tall, .chart-container.pie-tall { height: 260px; }
}
</style>
</head>
<body>
<header>
  <h1>Contributions de la représentation de la France auprès de la Conférence du désarmement</h1>
</header>

<nav class="tabs" role="tablist">
  <button class="active" data-tab="vue-ensemble" role="tab">Vue d'ensemble</button>
  <button data-tab="obligatoires" role="tab">Contributions obligatoires</button>
  <button data-tab="volontaires" role="tab">Contributions volontaires</button>
  <button data-tab="details" role="tab">Tableau détaillé</button>
</nav>

<main>
  <section id="vue-ensemble" class="panel active">
    <div class="kpi-row" id="kpi-cards"></div>
    <div class="charts-row">
      <div class="chart-box">
        <h2>Évolution des totaux volontaires (€)</h2>
        <div class="chart-container"><canvas id="chart-totals-vol"></canvas></div>
      </div>
      <div class="chart-box">
        <h2>Comparaison obligatoire vs volontaire</h2>
        <div class="chart-container"><canvas id="chart-compare"></canvas></div>
        <p class="legend-note">Les contributions obligatoires sont exprimées en USD et les volontaires en EUR — comparaison indicative.</p>
      </div>
    </div>
    <div class="chart-box full">
      <h2>Contributions obligatoires par convention (USD)</h2>
      <div class="chart-container tall"><canvas id="chart-mandatory-overview"></canvas></div>
    </div>
  </section>

  <section id="obligatoires" class="panel">
    <div class="toolbar-panel">
      <label for="year-mandatory">Année
        <select id="year-mandatory"></select>
      </label>
      <div class="kpi-row compact" id="kpi-mandatory"></div>
    </div>
    <div class="charts-row">
      <div class="chart-box">
        <h2>Évolution par convention (USD)</h2>
        <div id="mandatory-legend-pills" class="legend-pills"></div>
        <div class="chart-container tall"><canvas id="chart-mandatory-lines"></canvas></div>
      </div>
      <div class="chart-box">
        <h2 id="mandatory-bar-title">Montants 2026 par convention (USD)</h2>
        <div class="chart-container tall"><canvas id="chart-mandatory-year"></canvas></div>
      </div>
    </div>
    <div class="table-wrap">
      <h2>Tableau des contributions obligatoires</h2>
      <table id="table-mandatory"></table>
    </div>
  </section>

  <section id="volontaires" class="panel">
    <div class="toolbar-panel">
      <label for="year-vol">Année
        <select id="year-vol"></select>
      </label>
      <div class="kpi-row compact" id="kpi-voluntary"></div>
    </div>
    <div class="charts-row">
      <div class="chart-box">
        <h2>Répartition par catégorie</h2>
        <div id="vol-legend-pills" class="legend-pills"></div>
        <div class="chart-container pie-tall"><canvas id="chart-vol-pie"></canvas></div>
      </div>
      <div class="chart-box">
        <h2>Principaux bénéficiaires</h2>
        <div class="chart-container pie-tall"><canvas id="chart-vol-benef"></canvas></div>
      </div>
    </div>
    <div class="chart-box full">
      <h2>Évolution des catégories volontaires (€)</h2>
      <div class="chart-container tall"><canvas id="chart-evol-categories"></canvas></div>
    </div>
  </section>

  <section id="details" class="panel">
    <div class="filters">
      <label for="filter-year">Année :</label>
      <select id="filter-year"><option value="all">Toutes</option></select>
      <label for="filter-type">Type :</label>
      <select id="filter-type">
        <option value="all">Tous</option>
        <option value="mandatory">Obligatoires</option>
        <option value="voluntary">Volontaires</option>
      </select>
      <label for="filter-search">Recherche :</label>
      <input type="search" id="filter-search" placeholder="Organisme, convention…">
      <button type="button" id="export-csv" class="export-btn">Exporter CSV</button>
    </div>
    <div class="table-wrap">
      <table id="table-details">
        <thead>
          <tr>
            <th>Type</th>
            <th>Année</th>
            <th>Catégorie / Convention</th>
            <th>Organisme</th>
            <th class="amount">Montant</th>
            <th>Nature du financement</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </section>
</main>

<footer>
  Données issues de <strong>__GENERATED_FROM__</strong> — Généré le __GENERATION_DATE__
</footer>

<script>
__CHART_JS__
</script>
<script>
const DATA = __DATA_JSON__;

const COLORS = [
  '#2c5f8a','#1a7a5e','#8a2c2c','#b07d2a','#5a7a9a','#3d8b6e',
  '#a05050','#c49a3c','#6b8cae','#2e6b52','#9c7a5a','#4a6d8c'
];

const CHART_DEFAULTS = {
  color: '#6b6458',
  borderColor: 'rgba(40,35,20,0.12)',
  font: { family: "'Segoe UI', system-ui, sans-serif" }
};
Chart.defaults.color = CHART_DEFAULTS.color;
Chart.defaults.borderColor = CHART_DEFAULTS.borderColor;
Chart.defaults.font.family = CHART_DEFAULTS.font.family;

const fmtEUR = v => v == null ? '—' : new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(v);
const fmtUSD = v => v == null ? '—' : new Intl.NumberFormat('fr-FR',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const shortName = s => s.replace(/^\d+\s*-\s*/,'').split(' - ')[0].trim();

const charts = {};

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

// --- Tabs ---
document.querySelectorAll('nav.tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    window.dispatchEvent(new Event('resize'));
  });
});

// --- KPI helpers ---
function getGrandTotalVol(year) {
  const yd = DATA.voluntary.find(v => v.year === year);
  if (!yd) return null;
  return yd.categories.reduce((s,c) => s + (c.amount||0), 0);
}

function mandatoryTotalYear(year) {
  const col = year + ' ($)';
  return DATA.mandatory.items.reduce((s,i) => s + (parseFloat(i[col])||0), 0);
}

const MANDATORY_YEARS = ['2023','2024','2025','2026'];

function buildLegendPills(containerId, labels, colors, chart) {
  const container = document.getElementById(containerId);
  container.innerHTML = labels.map((label, i) =>
    `<button type="button" class="pill" data-idx="${i}" style="border-color:${colors[i % colors.length]};color:${colors[i % colors.length]}">${label}</button>`
  ).join('');
  container.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      const meta = chart.getDatasetMeta(idx);
      meta.hidden = !meta.hidden;
      btn.classList.toggle('inactive', meta.hidden);
      chart.update();
    });
  });
}

function buildPieLegendPills(containerId, labels, colors, chart) {
  const container = document.getElementById(containerId);
  container.innerHTML = labels.map((label, i) =>
    `<button type="button" class="pill" data-idx="${i}" style="border-color:${colors[i % colors.length]};color:${colors[i % colors.length]}">${label}</button>`
  ).join('');
  container.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      chart.toggleDataVisibility(idx);
      btn.classList.toggle('inactive', !chart.getDataVisibility(idx));
      chart.update();
    });
  });
}

// --- Vue d'ensemble KPIs ---
(function renderOverviewKPIs() {
  const years = DATA.voluntary.map(v => v.year);
  const lastYear = Math.max(...years);
  const firstYear = Math.min(...years);
  const totalVolLast = getGrandTotalVol(lastYear);
  const totalVolFirst = getGrandTotalVol(firstYear);
  const mand2026 = mandatoryTotalYear(2026);
  const evolVol = totalVolFirst ? ((totalVolLast - totalVolFirst) / totalVolFirst * 100) : 0;
  const mand2024 = mandatoryTotalYear(2024);
  const evolMand = mand2024 ? ((mand2026 - mand2024) / mand2024 * 100) : 0;

  document.getElementById('kpi-cards').innerHTML = `
    <div class="kpi accent"><div class="kpi-label">Contributions volontaires ${lastYear}</div><div class="kpi-val">${fmtEUR(totalVolLast)}</div><div class="kpi-sub">Hors lignes « dont »</div></div>
    <div class="kpi vc"><div class="kpi-label">Contributions obligatoires 2026</div><div class="kpi-val">${fmtUSD(mand2026)}</div></div>
    <div class="kpi accent2"><div class="kpi-label">Évolution volontaire ${firstYear}→${lastYear}</div><div class="kpi-val">${evolVol >= 0 ? '+' : ''}${evolVol.toFixed(0)}%</div><div class="kpi-sub">${fmtEUR(totalVolFirst)} → ${fmtEUR(totalVolLast)}</div></div>
    <div class="kpi vc"><div class="kpi-label">Évolution obligatoires 2024→2026</div><div class="kpi-val">${evolMand >= 0 ? '+' : ''}${evolMand.toFixed(0)}%</div><div class="kpi-sub">${fmtUSD(mand2024)} → ${fmtUSD(mand2026)}</div></div>
  `;
})();

// --- Chart: voluntary totals over time ---
(function() {
  const years = DATA.voluntary.map(v => v.year);
  const totals = years.map(y => getGrandTotalVol(y));
  destroyChart('chart-totals-vol');
  charts['chart-totals-vol'] = new Chart(document.getElementById('chart-totals-vol'), {
    type: 'bar',
    data: {
      labels: years,
      datasets: [{ label: 'Total volontaire (€)', data: totals, backgroundColor: COLORS[0] }]
    },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtEUR(ctx.raw) } } }, scales: { y: { ticks: { callback: v => fmtEUR(v) } } } }
  });
})();

// --- Chart: compare obligatoire vs volontaire (vue d'ensemble) ---
(function() {
  const years = DATA.voluntary.map(v => v.year);
  destroyChart('chart-compare');
  charts['chart-compare'] = new Chart(document.getElementById('chart-compare'), {
    type: 'bar',
    data: {
      labels: years,
      datasets: [
        { label: 'Volontaire (€)', data: years.map(y => getGrandTotalVol(y)), backgroundColor: COLORS[0] },
        { label: 'Obligatoire (USD)', data: years.map(y => mandatoryTotalYear(y) || null), backgroundColor: COLORS[2] }
      ]
    },
    options: {
      plugins: {
        tooltip: {
          callbacks: {
            label: ctx => ctx.dataset.label + ': ' + (ctx.dataset.label.includes('€') ? fmtEUR(ctx.raw) : fmtUSD(ctx.raw))
          }
        }
      },
      scales: { y: { ticks: { callback: v => new Intl.NumberFormat('fr-FR').format(v) } } }
    }
  });
})();

// --- Chart: mandatory overview stacked ---
(function() {
  const years = ['2023 ($)','2024 ($)','2025 ($)','2026 ($)'];
  const labels = years.map(y => y.replace(' ($)',''));
  const datasets = DATA.mandatory.items.map((item, i) => ({
    label: shortName(item.name),
    data: years.map(y => parseFloat(item[y]) || null),
    backgroundColor: COLORS[i % COLORS.length],
  }));
  destroyChart('chart-mandatory-overview');
  charts['chart-mandatory-overview'] = new Chart(document.getElementById('chart-mandatory-overview'), {
    type: 'bar',
    data: { labels, datasets },
    options: {
      plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtUSD(ctx.raw) } } },
      scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: v => fmtUSD(v) } } }
    }
  });
})();

// --- Mandatory section ---
const yearMandatorySelect = document.getElementById('year-mandatory');
MANDATORY_YEARS.forEach(y => {
  const opt = document.createElement('option');
  opt.value = y; opt.textContent = y;
  yearMandatorySelect.appendChild(opt);
});
yearMandatorySelect.value = '2026';

function updateMandatoryKPIAndBar(year) {
  const total = mandatoryTotalYear(parseInt(year));
  document.getElementById('kpi-mandatory').innerHTML = `
    <div class="kpi vc"><div class="kpi-label">Total ${year} (USD)</div><div class="kpi-val">${fmtUSD(total)}</div></div>
  `;
  document.getElementById('mandatory-bar-title').textContent = `Montants ${year} par convention (USD)`;

  const col = year + ' ($)';
  destroyChart('chart-mandatory-year');
  charts['chart-mandatory-year'] = new Chart(document.getElementById('chart-mandatory-year'), {
    type: 'bar',
    data: {
      labels: DATA.mandatory.items.map(i => shortName(i.name)),
      datasets: [{ label: year + ' ($)', data: DATA.mandatory.items.map(i => parseFloat(i[col])||0), backgroundColor: COLORS }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtUSD(ctx.raw) } } },
      scales: { x: { ticks: { callback: v => fmtUSD(v) } } }
    }
  });
}

yearMandatorySelect.addEventListener('change', () => updateMandatoryKPIAndBar(yearMandatorySelect.value));
updateMandatoryKPIAndBar('2026');

(function() {
  const yearCols = MANDATORY_YEARS.map(y => y + ' ($)');
  const convLabels = DATA.mandatory.items.map(i => shortName(i.name));

  destroyChart('chart-mandatory-lines');
  const lineChart = new Chart(document.getElementById('chart-mandatory-lines'), {
    type: 'line',
    data: {
      labels: MANDATORY_YEARS,
      datasets: DATA.mandatory.items.map((item,i) => ({
        label: convLabels[i],
        data: yearCols.map(y => parseFloat(item[y]) || null),
        borderColor: COLORS[i % COLORS.length],
        backgroundColor: COLORS[i % COLORS.length],
        tension: .3,
        fill: false,
        pointRadius: 4,
        pointHoverRadius: 6,
      }))
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtUSD(ctx.raw) } }
      },
      scales: { y: { ticks: { callback: v => fmtUSD(v) } } }
    }
  });
  charts['chart-mandatory-lines'] = lineChart;
  buildLegendPills('mandatory-legend-pills', convLabels, COLORS, lineChart);

  const headers = DATA.mandatory.headers;
  let html = '<thead><tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr></thead><tbody>';
  DATA.mandatory.items.forEach(item => {
    html += '<tr>' + headers.map(h => {
      const v = item[h];
      if (h.includes('($)') || h.includes('(€)')) return `<td class="amount">${typeof v === 'number' ? (h.includes('€') ? fmtEUR(v) : fmtUSD(v)) : (v||'—')}</td>`;
      return `<td>${v ?? '—'}</td>`;
    }).join('') + '</tr>';
  });
  html += '</tbody>';
  document.getElementById('table-mandatory').innerHTML = html;
})();

// --- Voluntary section ---
const yearSelect = document.getElementById('year-vol');
DATA.voluntary.forEach(v => {
  const opt = document.createElement('option');
  opt.value = v.year; opt.textContent = v.year;
  yearSelect.appendChild(opt);
});
yearSelect.value = Math.max(...DATA.voluntary.map(v => v.year));

function renderVoluntaryYear(year) {
  const yd = DATA.voluntary.find(v => v.year === year);
  const total = getGrandTotalVol(year);
  document.getElementById('kpi-voluntary').innerHTML = `
    <div class="kpi accent"><div class="kpi-label">Total ${year}</div><div class="kpi-val">${fmtEUR(total)}</div></div>
  `;

  const catLabels = yd.categories.map(c => c.name);
  const catValues = yd.categories.map(c => c.amount);

  destroyChart('chart-vol-pie');
  const pieChart = new Chart(document.getElementById('chart-vol-pie'), {
    type: 'doughnut',
    data: {
      labels: catLabels,
      datasets: [{ data: catValues, backgroundColor: COLORS }]
    },
    options: {
      layout: { padding: 10 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: items => catLabels[items[0].dataIndex],
            label: ctx => fmtEUR(ctx.raw)
          }
        }
      }
    }
  });
  charts['chart-vol-pie'] = pieChart;
  buildPieLegendPills('vol-legend-pills', catLabels, COLORS, pieChart);

  const benef = {};
  yd.items.filter(i => !i.is_breakdown && i.amount).forEach(i => {
    benef[i.organisme] = (benef[i.organisme]||0) + i.amount;
  });
  const sorted = Object.entries(benef).sort((a,b)=>b[1]-a[1]).slice(0,8);
  destroyChart('chart-vol-benef');
  charts['chart-vol-benef'] = new Chart(document.getElementById('chart-vol-benef'), {
    type: 'bar',
    data: {
      labels: sorted.map(s => s[0]),
      datasets: [{ data: sorted.map(s => s[1]), backgroundColor: COLORS[0] }]
    },
    options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtEUR(ctx.raw) } } }, scales: { x: { ticks: { callback: v => fmtEUR(v) } } } }
  });
}
yearSelect.addEventListener('change', () => renderVoluntaryYear(parseInt(yearSelect.value)));
renderVoluntaryYear(parseInt(yearSelect.value));

// --- Évolution catégories volontaires (onglet volontaires) ---
(function() {
  const years = DATA.voluntary.map(v => v.year);
  const allCats = [...new Set(DATA.voluntary.flatMap(v => v.categories.map(c => c.name)))];
  destroyChart('chart-evol-categories');
  charts['chart-evol-categories'] = new Chart(document.getElementById('chart-evol-categories'), {
    type: 'line',
    data: {
      labels: years,
      datasets: allCats.map((cat, i) => ({
        label: cat,
        data: years.map(y => {
          const yd = DATA.voluntary.find(v => v.year === y);
          const c = yd.categories.find(c => c.name === cat);
          return c ? c.amount : null;
        }),
        borderColor: COLORS[i % COLORS.length],
        tension: .3,
        spanGaps: true,
      }))
    },
    options: {
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtEUR(ctx.raw) } }
      },
      scales: { y: { ticks: { callback: v => fmtEUR(v) } } }
    }
  });
})();

// --- Details table ---
const filterYear = document.getElementById('filter-year');
DATA.voluntary.forEach(v => {
  const opt = document.createElement('option');
  opt.value = v.year; opt.textContent = v.year;
  filterYear.appendChild(opt);
});

function buildDetailRows() {
  const rows = [];
  DATA.mandatory.items.forEach(item => {
    ['2023 ($)','2024 (€)','2024 ($)','2025 ($)','2026 ($)'].forEach(col => {
      const v = item[col];
      if (v == null || v === '') return;
      const year = col.match(/\d{4}/)[0];
      rows.push({
        type: 'Obligatoire', year, category: shortName(item.name), organisme: item.name,
        amount: v, currency: col.includes('€') ? 'EUR' : 'USD', nature: '', isBreakdown: false
      });
    });
  });
  DATA.voluntary.forEach(yd => {
    yd.categories.forEach(c => {
      if (c.amount != null) rows.push({
        type: 'Volontaire', year: yd.year, category: c.name, organisme: `— Total catégorie —`,
        amount: c.amount, currency: 'EUR', nature: '', isBreakdown: false, isCategory: true
      });
    });
    yd.items.forEach(i => {
      if (i.amount == null) return;
      rows.push({
        type: 'Volontaire', year: yd.year, category: i.category || '', organisme: i.organisme,
        amount: i.amount, currency: 'EUR', nature: i.nature, isBreakdown: i.is_breakdown
      });
    });
  });
  return rows;
}

const allRows = buildDetailRows();
const tbody = document.querySelector('#table-details tbody');

function renderDetails() {
  const yf = filterYear.value;
  const tf = document.getElementById('filter-type').value;
  const q = document.getElementById('filter-search').value.toLowerCase();
  tbody.innerHTML = allRows.filter(r => {
    if (yf !== 'all' && String(r.year) !== yf) return false;
    if (tf === 'mandatory' && r.type !== 'Obligatoire') return false;
    if (tf === 'voluntary' && r.type !== 'Volontaire') return false;
    if (q && !(r.organisme + r.category + r.nature).toLowerCase().includes(q)) return false;
    return true;
  }).map(r => {
    const cls = [r.isBreakdown ? 'breakdown' : '', r.isCategory ? 'category-row' : ''].join(' ');
    const amt = r.currency === 'EUR' ? fmtEUR(r.amount) : fmtUSD(r.amount);
    return `<tr class="${cls}"><td>${r.type}</td><td>${r.year}</td><td>${r.category}</td><td>${r.organisme}</td><td class="amount">${amt}</td><td>${r.nature}</td></tr>`;
  }).join('');
}

['filter-year','filter-type','filter-search'].forEach(id => {
  document.getElementById(id).addEventListener('input', renderDetails);
  document.getElementById(id).addEventListener('change', renderDetails);
});
renderDetails();

document.getElementById('export-csv').addEventListener('click', () => {
  const yf = filterYear.value;
  const tf = document.getElementById('filter-type').value;
  const q = document.getElementById('filter-search').value.toLowerCase();
  const filtered = allRows.filter(r => {
    if (yf !== 'all' && String(r.year) !== yf) return false;
    if (tf === 'mandatory' && r.type !== 'Obligatoire') return false;
    if (tf === 'voluntary' && r.type !== 'Volontaire') return false;
    if (q && !(r.organisme + r.category + r.nature).toLowerCase().includes(q)) return false;
    return true;
  });
  const header = ['Type','Année','Catégorie','Organisme','Montant','Devise','Nature'];
  const lines = [header.join(';')].concat(filtered.map(r =>
    [r.type,r.year,r.category,r.organisme,r.amount,r.currency,'"' + (r.nature||'').replace(/"/g,'""') + '"'].join(';')
  ));
  const blob = new Blob(['\ufeff' + lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'contributions_dsmt_export.csv';
  a.click();
});
</script>
</body>
</html>"""


def generate():
    data = build_data()
    chart_js = load_chart_js()
    if not chart_js:
        print("Attention: Chart.js non trouvé, le fichier nécessitera une connexion.", file=sys.stderr)

    from datetime import datetime

    html = HTML_TEMPLATE
    html = html.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__CHART_JS__", chart_js)
    html = html.replace("__GENERATED_FROM__", data["generated_from"])
    html = html.replace("__GENERATION_DATE__", datetime.now().strftime("%d/%m/%Y"))

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Fichier généré : {HTML_PATH} ({HTML_PATH.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    generate()
