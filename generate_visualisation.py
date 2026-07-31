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
<title>Contributions de la France auprès de la Conférence du désarmement | Genève</title>
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
  padding: 1rem 1.35rem;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text2);
  border-bottom: 3px solid transparent;
  margin-bottom: -1px;
  transition: all 0.15s;
  font-family: inherit;
  letter-spacing: 0.01em;
}
nav.tabs button:hover { color: var(--accent); background: rgba(44,95,138,0.04); }
nav.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 600;
  background: var(--surface2);
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
.kpi.vc .kpi-val { color: #E8737A; }
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
.chart-container.evolution-chart { height: 380px; }
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
tbody tr.category-row {
  background: #dceaf7;
  font-weight: 600;
  color: #1e4d72;
  border-top: 1px solid #b8d4eb;
  border-bottom: 1px solid #b8d4eb;
}
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
  padding: 2rem;
  font-size: 0.75rem;
  color: #000;
  font-weight: 700;
  border-top: 1px solid var(--border);
  margin-top: 2rem;
  position: relative;
  background: linear-gradient(rgba(255,255,255,0.6), rgba(255,255,255,0.6)),
    url('https://upload.wikimedia.org/wikipedia/fr/thumb/5/50/Bloc_Marianne.svg/3840px-Bloc_Marianne.svg.png');
  background-size: cover;
  background-position: center;
}
.footer-text {
  background: rgba(255,255,255,0.78);
  padding: 0.35rem 1rem;
  display: inline-block;
  border-radius: 4px;
}
.admin-trigger {
  position: absolute;
  right: 1.5rem;
  bottom: 1.2rem;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.92);
  border: 1px solid var(--border2);
  color: var(--text2);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  padding: 7px 14px;
  border-radius: 6px;
  font-family: inherit;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  transition: all 0.15s;
}
.admin-trigger:hover { color: var(--accent); border-color: var(--accent); background: #fff; }
.admin-overlay {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(26,24,20,0.55);
  backdrop-filter: blur(3px);
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.admin-overlay.open { display: flex; }
.admin-panel {
  background: var(--surface);
  border-radius: 12px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.18);
  width: 100%;
  max-width: 960px;
  max-height: 92vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.admin-header {
  padding: 1.2rem 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.admin-header h2 { font-family: Georgia, serif; font-size: 1.25rem; font-weight: 400; }
.admin-close { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: var(--text2); line-height: 1; padding: 4px; }
.admin-body { overflow-y: auto; padding: 1.5rem; display: flex; flex-direction: column; gap: 1.5rem; }
.admin-login { text-align: center; padding: 2rem 1rem; }
.admin-login input { width: 220px; margin: 0.8rem auto; display: block; text-align: center; padding: 8px; border: 1px solid var(--border2); border-radius: 6px; }
.admin-login button {
  background: var(--accent); color: #fff; border: none; border-radius: 6px;
  padding: 8px 24px; font-family: inherit; font-size: 0.88rem; cursor: pointer;
}
.admin-login .err { color: #E8737A; font-size: 0.82rem; margin-top: 0.5rem; display: none; }
.admin-section h3 { font-size: 0.95rem; font-weight: 500; margin-bottom: 0.8rem; color: var(--text); }
.admin-controls { display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: flex-end; margin-bottom: 1rem; }
.admin-controls label { font-size: 0.78rem; font-weight: 500; color: var(--text2); text-transform: uppercase; letter-spacing: 0.06em; display: flex; flex-direction: column; gap: 4px; }
.admin-table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
.admin-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.admin-table th { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; color: var(--text2); padding: 0.5rem 0.6rem; border-bottom: 2px solid var(--border2); text-align: right; background: var(--surface2); white-space: nowrap; }
.admin-table th:first-child { text-align: left; position: sticky; left: 0; background: var(--surface2); z-index: 1; }
.admin-table td { padding: 3px; border-bottom: 1px solid var(--border); }
.admin-table td:first-child { font-weight: 500; padding-left: 0.6rem; white-space: nowrap; position: sticky; left: 0; background: var(--surface); z-index: 1; }
.admin-table input, .admin-table textarea { width: 100%; min-width: 70px; font-size: 0.78rem; padding: 4px 6px; border: 1px solid transparent; border-radius: 4px; background: transparent; font-family: inherit; }
.admin-table input:focus, .admin-table textarea:focus { border-color: var(--accent); background: var(--bg); outline: none; }
.admin-table input.changed, .admin-table textarea.changed { background: rgba(44,95,138,0.08); border-color: var(--accent); }
.admin-btn {
  background: var(--accent); color: #fff; border: none; border-radius: 6px;
  padding: 7px 16px; font-family: inherit; font-size: 0.83rem; cursor: pointer;
}
.admin-btn.secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border2); }
.admin-btn-row { display: flex; flex-wrap: wrap; gap: 0.6rem; }
.admin-export textarea {
  width: 100%; min-height: 140px; font-family: 'Courier New', monospace; font-size: 0.72rem;
  padding: 0.8rem; border: 1px solid var(--border2); border-radius: 8px; background: var(--bg);
  color: var(--text); resize: vertical; line-height: 1.4;
}
.admin-tutorial { background: var(--surface2); border-radius: 8px; padding: 1.2rem 1.4rem; }
.admin-steps { list-style: none; counter-reset: step; display: flex; flex-direction: column; gap: 0.9rem; }
.admin-steps li { counter-increment: step; padding-left: 2.2rem; position: relative; font-size: 0.85rem; line-height: 1.5; }
.admin-steps li::before {
  content: counter(step); position: absolute; left: 0; top: 0;
  width: 1.6rem; height: 1.6rem; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 0.75rem; font-weight: 500; display: flex; align-items: center; justify-content: center;
}
.admin-steps code { background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 3px; font-size: 0.8rem; }
.admin-badge { display: inline-block; background: var(--accent); color: #fff; font-size: 0.7rem; padding: 2px 8px; border-radius: 10px; margin-left: 0.5rem; vertical-align: middle; }
@media (max-width: 960px) {
  .charts-row { grid-template-columns: 1fr; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  header h1 { font-size: 1.35rem; }
  main, nav.tabs { padding-left: 1rem; padding-right: 1rem; }
  .kpi-row { grid-template-columns: 1fr; }
  .toolbar-panel .kpi-row.compact { margin-left: 0; width: 100%; }
  .chart-container, .chart-container.tall, .chart-container.evolution-chart { height: 260px; }
}
</style>
</head>
<body>
<header>
  <h1>Contributions de la France auprès de la Conférence du désarmement | Genève</h1>
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
        <h2>Principaux bénéficiaires</h2>
        <div class="chart-container tall"><canvas id="chart-vol-benef"></canvas></div>
      </div>
      <div class="chart-box">
        <h2>Évolution des catégories volontaires (€)</h2>
        <div class="chart-container evolution-chart"><canvas id="chart-evol-categories"></canvas></div>
      </div>
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
  <span class="footer-text">Données issues de <strong>__GENERATED_FROM__</strong> — Généré le __GENERATION_DATE__</span>
  <button type="button" class="admin-trigger" onclick="openAdmin()" title="Administration des données">
    <span aria-hidden="true">&#9881;</span> Espace admin
  </button>
</footer>

<div class="admin-overlay" id="adminOverlay">
  <div class="admin-panel">
    <div class="admin-header">
      <h2>Administration des données</h2>
      <button type="button" class="admin-close" onclick="closeAdmin()" aria-label="Fermer">&times;</button>
    </div>
    <div class="admin-body" id="adminBody"></div>
  </div>
</div>

<script>
__CHART_JS__
</script>
<script>
__APP_SCRIPT__
</script>
</body>
</html>"""


APP_SCRIPT_PATH = Path(__file__).parent / "dsmt_app.js"


def generate():
    data = build_data()
    chart_js = load_chart_js()
    app_script = APP_SCRIPT_PATH.read_text(encoding="utf-8")
    if not chart_js:
        print("Attention: Chart.js non trouvé, le fichier nécessitera une connexion.", file=sys.stderr)

    from datetime import datetime

    html = HTML_TEMPLATE
    html = html.replace("__APP_SCRIPT__", app_script.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False)))
    html = html.replace("__CHART_JS__", chart_js)
    html = html.replace("__GENERATED_FROM__", data["generated_from"])
    html = html.replace("__GENERATION_DATE__", datetime.now().strftime("%d/%m/%Y"))

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Fichier généré : {HTML_PATH} ({HTML_PATH.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    generate()
