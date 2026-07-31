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
:root {
  --bleu: #000091;
  --rouge: #e1000f;
  --bleu-clair: #e8edff;
  --gris: #f6f6f6;
  --gris-fonce: #3a3a3a;
  --blanc: #ffffff;
  --ombre: 0 2px 8px rgba(0,0,0,.08);
  --rayon: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "Marianne", "Segoe UI", system-ui, sans-serif;
  background: var(--gris);
  color: var(--gris-fonce);
  line-height: 1.5;
}
header {
  background: linear-gradient(135deg, var(--bleu) 70%, var(--rouge));
  color: var(--blanc);
  padding: 2rem 1.5rem 1.5rem;
}
header h1 { font-size: 1.6rem; font-weight: 700; }
.badge { display: none; }
.legend-pills {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  margin-bottom: 1rem;
}
.legend-pills button {
  border: 2px solid;
  padding: .35rem .8rem;
  border-radius: 999px;
  font-size: .78rem;
  font-weight: 600;
  cursor: pointer;
  background: var(--blanc);
  transition: opacity .2s;
}
.legend-pills button.inactive { opacity: .3; }
.chart-box .chart-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: .75rem;
  margin-bottom: 1rem;
  padding-bottom: .5rem;
  border-bottom: 2px solid var(--bleu-clair);
}
.chart-box .chart-header h2 {
  margin: 0;
  padding: 0;
  border: none;
}
.chart-container.tall { height: 400px; }
.chart-container.pie-tall { height: 420px; }
nav.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  padding: 1rem 1.5rem 0;
  background: var(--blanc);
  border-bottom: 2px solid var(--bleu-clair);
  position: sticky;
  top: 0;
  z-index: 10;
}
nav.tabs button {
  border: none;
  background: transparent;
  padding: .6rem 1rem;
  cursor: pointer;
  font-size: .9rem;
  font-weight: 600;
  color: var(--bleu);
  border-bottom: 3px solid transparent;
  border-radius: var(--rayon) var(--rayon) 0 0;
}
nav.tabs button.active {
  background: var(--bleu-clair);
  border-bottom-color: var(--bleu);
}
main { padding: 1.5rem; max-width: 1400px; margin: 0 auto; }
.panel { display: none; }
.panel.active { display: block; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.card {
  background: var(--blanc);
  border-radius: var(--rayon);
  padding: 1.2rem;
  box-shadow: var(--ombre);
  border-left: 4px solid var(--bleu);
}
.card.red { border-left-color: var(--rouge); }
.card h3 { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: #666; }
.card .value { font-size: 1.6rem; font-weight: 700; color: var(--bleu); margin-top: .3rem; }
.card.red .value { color: var(--rouge); }
.card .sub { font-size: .8rem; color: #888; margin-top: .2rem; }
.grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}
.chart-box {
  background: var(--blanc);
  border-radius: var(--rayon);
  padding: 1.2rem;
  box-shadow: var(--ombre);
}
.chart-box h2 {
  font-size: 1rem;
  color: var(--bleu);
  margin-bottom: 1rem;
  padding-bottom: .5rem;
  border-bottom: 2px solid var(--bleu-clair);
}
.chart-container { position: relative; height: 320px; }
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: .75rem;
  margin-bottom: 1rem;
  align-items: center;
}
.filters label { font-size: .85rem; font-weight: 600; }
.filters select, .filters input {
  padding: .45rem .7rem;
  border: 1px solid #ccc;
  border-radius: var(--rayon);
  font-size: .9rem;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: .88rem;
  background: var(--blanc);
  border-radius: var(--rayon);
  overflow: hidden;
  box-shadow: var(--ombre);
}
thead { background: var(--bleu); color: var(--blanc); }
th, td { padding: .65rem .8rem; text-align: left; vertical-align: top; }
tbody tr:nth-child(even) { background: #fafafa; }
tbody tr:hover { background: var(--bleu-clair); }
tbody tr.breakdown { color: #666; font-style: italic; }
tbody tr.category-row { background: #eef1ff; font-weight: 700; }
.amount { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.legend-note {
  font-size: .8rem;
  color: #666;
  margin-top: .75rem;
  padding: .75rem;
  background: var(--bleu-clair);
  border-radius: var(--rayon);
}
footer {
  text-align: center;
  padding: 2rem 1rem;
  font-size: .8rem;
  color: #888;
}
@media (max-width: 600px) {
  header h1 { font-size: 1.25rem; }
  .chart-container { height: 260px; }
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
    <div class="cards" id="kpi-cards"></div>
    <div class="grid-2">
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
    <div class="chart-box">
      <h2>Contributions obligatoires par convention (USD)</h2>
      <div class="chart-container" style="height:380px"><canvas id="chart-mandatory-overview"></canvas></div>
    </div>
  </section>

  <section id="obligatoires" class="panel">
    <div class="filters">
      <label for="year-mandatory">Année :</label>
      <select id="year-mandatory"></select>
    </div>
    <div class="cards" id="kpi-mandatory"></div>
    <div class="chart-box">
      <h2>Évolution par convention (USD)</h2>
      <div id="mandatory-legend-pills" class="legend-pills"></div>
      <div class="chart-container tall"><canvas id="chart-mandatory-lines"></canvas></div>
    </div>
    <div class="chart-box" style="margin-top:1.5rem">
      <h2 id="mandatory-bar-title">Montants 2026 par convention (USD)</h2>
      <div class="chart-container"><canvas id="chart-mandatory-year"></canvas></div>
    </div>
    <div class="chart-box" style="margin-top:1.5rem;overflow-x:auto">
      <h2>Tableau des contributions obligatoires</h2>
      <table id="table-mandatory"></table>
    </div>
  </section>

  <section id="volontaires" class="panel">
    <div class="filters">
      <label for="year-vol">Année :</label>
      <select id="year-vol"></select>
    </div>
    <div class="cards" id="kpi-voluntary"></div>
    <div class="grid-2">
      <div class="chart-box">
        <h2>Répartition par catégorie</h2>
        <div id="vol-legend-pills" class="legend-pills"></div>
        <div class="chart-container pie-tall"><canvas id="chart-vol-pie"></canvas></div>
      </div>
      <div class="chart-box">
        <h2>Principaux bénéficiaires</h2>
        <div class="chart-container"><canvas id="chart-vol-benef"></canvas></div>
      </div>
    </div>
    <div class="chart-box" style="margin-top:1.5rem">
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
      <button type="button" id="export-csv" style="margin-left:auto;padding:.45rem 1rem;background:var(--bleu);color:#fff;border:none;border-radius:var(--rayon);cursor:pointer;font-weight:600">Exporter CSV</button>
    </div>
    <div style="overflow-x:auto">
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
  '#000091','#e1000f','#0063cb','#ff9575','#7ab1e8','#929292',
  '#6a6af4','#ffb7ae','#465f9d','#d64d00','#9c9c9c','#8585f6'
];

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
    <div class="card"><h3>Contributions volontaires ${lastYear}</h3><div class="value">${fmtEUR(totalVolLast)}</div><div class="sub">Hors lignes « dont »</div></div>
    <div class="card red"><h3>Contributions obligatoires 2026</h3><div class="value">${fmtUSD(mand2026)}</div></div>
    <div class="card"><h3>Évolution volontaire ${firstYear}→${lastYear}</h3><div class="value">${evolVol >= 0 ? '+' : ''}${evolVol.toFixed(0)}%</div><div class="sub">${fmtEUR(totalVolFirst)} → ${fmtEUR(totalVolLast)}</div></div>
    <div class="card red"><h3>Évolution contributions obligatoires 2024→2026</h3><div class="value">${evolMand >= 0 ? '+' : ''}${evolMand.toFixed(0)}%</div><div class="sub">${fmtUSD(mand2024)} → ${fmtUSD(mand2026)}</div></div>
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
      datasets: [{ label: 'Total volontaire (€)', data: totals, backgroundColor: '#000091' }]
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
        { label: 'Volontaire (€)', data: years.map(y => getGrandTotalVol(y)), backgroundColor: '#000091' },
        { label: 'Obligatoire (USD)', data: years.map(y => mandatoryTotalYear(y) || null), backgroundColor: '#e1000f' }
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
    <div class="card red"><h3>Total ${year} (USD)</h3><div class="value">${fmtUSD(total)}</div></div>
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
    <div class="card"><h3>Total ${year}</h3><div class="value">${fmtEUR(total)}</div></div>
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
      datasets: [{ data: sorted.map(s => s[1]), backgroundColor: '#000091' }]
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
