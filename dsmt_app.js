
// ═══════════════════════════════════════════════════════════════════════════════
// BLOC DE DONNÉES — Remplacez tout ce bloc pour mettre à jour la page
// ═══════════════════════════════════════════════════════════════════════════════
const PAGEBLOCK = __DATA_JSON__;
let DATA;

function deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }
function loadFromPageblock() { DATA = deepClone(PAGEBLOCK); }
loadFromPageblock();

const COLORS = [
  '#4A90D9','#F28482','#5CB87A','#F5A623','#9B6DD7','#50C4C8',
  '#FF8A65','#7E8CE0','#66BB6A','#EF5350','#42A5F5','#AB47BC'
];

Chart.defaults.color = '#6b6458';
Chart.defaults.borderColor = 'rgba(40,35,20,0.12)';
Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";

const fmtEUR = v => v == null ? '—' : new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(v);
const fmtUSD = v => v == null ? '—' : new Intl.NumberFormat('fr-FR',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const shortName = s => s.replace(/^\d+\s*-\s*/,'').split(' - ')[0].trim();

const charts = {};
let allRows = [];

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function getGrandTotalVol(year) {
  const yd = DATA.voluntary.find(v => v.year === year);
  if (!yd) return null;
  return yd.categories.reduce((s,c) => s + (c.amount||0), 0);
}

function mandatoryTotalYear(year) {
  const col = year + ' ($)';
  return DATA.mandatory.items.reduce((s,i) => s + (parseFloat(i[col])||0), 0);
}

function getMandatoryUsdYears() {
  return [...new Set(
    DATA.mandatory.headers.filter(h => /\d{4} \(\$\)/.test(h)).map(h => h.match(/\d{4}/)[0])
  )].sort();
}

function getValueColumns() {
  return DATA.mandatory.headers.filter(h => h !== 'Contributions obligatoires' && !h.includes('Date limite'));
}

function buildLegendPills(containerId, labels, colors, chart) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = labels.map((label, i) =>
    `<button type="button" data-idx="${i}" style="border-color:${colors[i % colors.length]};color:${colors[i % colors.length]}">${label}</button>`
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

function renderOverviewKPIs() {
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
    <div class="kpi vc"><div class="kpi-label">Évolution obligatoires 2024→2026</div><div class="kpi-val">${evolMand >= 0 ? '+' : ''}${evolMand.toFixed(0)}%</div><div class="kpi-sub">${fmtUSD(mand2024)} → ${fmtUSD(mand2026)}</div></div>`;
}

function renderChartsOverview() {
  const years = DATA.voluntary.map(v => v.year);
  const totals = years.map(y => getGrandTotalVol(y));
  destroyChart('chart-totals-vol');
  charts['chart-totals-vol'] = new Chart(document.getElementById('chart-totals-vol'), {
    type: 'bar',
    data: { labels: years, datasets: [{ label: 'Total volontaire (€)', data: totals, backgroundColor: COLORS[0] }] },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtEUR(ctx.raw) } } }, scales: { y: { ticks: { callback: v => fmtEUR(v) } } } }
  });

  destroyChart('chart-compare');
  charts['chart-compare'] = new Chart(document.getElementById('chart-compare'), {
    type: 'bar',
    data: {
      labels: years,
      datasets: [
        { label: 'Volontaire (€)', data: years.map(y => getGrandTotalVol(y)), backgroundColor: COLORS[0] },
        { label: 'Obligatoire (USD)', data: years.map(y => mandatoryTotalYear(y) || null), backgroundColor: COLORS[1] }
      ]
    },
    options: { plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + (ctx.dataset.label.includes('€') ? fmtEUR(ctx.raw) : fmtUSD(ctx.raw)) } } }, scales: { y: { ticks: { callback: v => new Intl.NumberFormat('fr-FR').format(v) } } } }
  });

  const mandYears = getMandatoryUsdYears().map(y => y + ' ($)');
  const labels = mandYears.map(y => y.replace(' ($)',''));
  destroyChart('chart-mandatory-overview');
  charts['chart-mandatory-overview'] = new Chart(document.getElementById('chart-mandatory-overview'), {
    type: 'bar',
    data: {
      labels,
      datasets: DATA.mandatory.items.map((item, i) => ({
        label: shortName(item.name),
        data: mandYears.map(y => parseFloat(item[y]) || null),
        backgroundColor: COLORS[i % COLORS.length],
      }))
    },
    options: { plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtUSD(ctx.raw) } } }, scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: v => fmtUSD(v) } } } }
  });
}

function rebuildMandatoryYearSelect() {
  const sel = document.getElementById('year-mandatory');
  const cur = sel.value || '2026';
  sel.innerHTML = '';
  getMandatoryUsdYears().forEach(y => {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    sel.appendChild(opt);
  });
  if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
  else sel.value = sel.options[sel.options.length - 1]?.value || '2026';
}

function updateMandatoryKPIAndBar(year) {
  const total = mandatoryTotalYear(parseInt(year));
  document.getElementById('kpi-mandatory').innerHTML = `
    <div class="kpi vc"><div class="kpi-label">Total ${year} (USD)</div><div class="kpi-val">${fmtUSD(total)}</div></div>`;
  document.getElementById('mandatory-bar-title').textContent = `Montants ${year} par convention (USD)`;
  const col = year + ' ($)';
  destroyChart('chart-mandatory-year');
  charts['chart-mandatory-year'] = new Chart(document.getElementById('chart-mandatory-year'), {
    type: 'bar',
    data: {
      labels: DATA.mandatory.items.map(i => shortName(i.name)),
      datasets: [{ data: DATA.mandatory.items.map(i => parseFloat(i[col])||0), backgroundColor: COLORS }]
    },
    options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtUSD(ctx.raw) } } }, scales: { x: { ticks: { callback: v => fmtUSD(v) } } } }
  });
}

function renderMandatorySection() {
  rebuildMandatoryYearSelect();
  const mandYears = getMandatoryUsdYears();
  const yearCols = mandYears.map(y => y + ' ($)');
  const convLabels = DATA.mandatory.items.map(i => shortName(i.name));

  destroyChart('chart-mandatory-lines');
  const lineChart = new Chart(document.getElementById('chart-mandatory-lines'), {
    type: 'line',
    data: {
      labels: mandYears,
      datasets: DATA.mandatory.items.map((item,i) => ({
        label: convLabels[i],
        data: yearCols.map(y => parseFloat(item[y]) || null),
        borderColor: COLORS[i % COLORS.length],
        backgroundColor: COLORS[i % COLORS.length],
        tension: 0.3,
        fill: false,
        pointRadius: 4,
        borderWidth: 2.5,
      }))
    },
    options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtUSD(ctx.raw) } } }, scales: { y: { ticks: { callback: v => fmtUSD(v) } } } }
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
  updateMandatoryKPIAndBar(document.getElementById('year-mandatory').value);
}

function rebuildVoluntaryYearSelect() {
  const sel = document.getElementById('year-vol');
  const cur = parseInt(sel.value) || Math.max(...DATA.voluntary.map(v => v.year));
  sel.innerHTML = '';
  DATA.voluntary.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.year; opt.textContent = v.year;
    sel.appendChild(opt);
  });
  if ([...sel.options].some(o => parseInt(o.value) === cur)) sel.value = cur;
  else sel.value = Math.max(...DATA.voluntary.map(v => v.year));
}

function renderVoluntaryYear(year) {
  const yd = DATA.voluntary.find(v => v.year === year);
  if (!yd) return;
  document.getElementById('kpi-voluntary').innerHTML = `
    <div class="kpi accent"><div class="kpi-label">Total ${year}</div><div class="kpi-val">${fmtEUR(getGrandTotalVol(year))}</div></div>`;

  const benef = {};
  yd.items.filter(i => !i.is_breakdown && i.amount).forEach(i => {
    benef[i.organisme] = (benef[i.organisme]||0) + i.amount;
  });
  const sorted = Object.entries(benef).sort((a,b)=>b[1]-a[1]).slice(0,8);
  destroyChart('chart-vol-benef');
  charts['chart-vol-benef'] = new Chart(document.getElementById('chart-vol-benef'), {
    type: 'bar',
    data: { labels: sorted.map(s => s[0]), datasets: [{ data: sorted.map(s => s[1]), backgroundColor: COLORS[0] }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtEUR(ctx.raw) } } }, scales: { x: { ticks: { callback: v => fmtEUR(v) } } } }
  });
}

function renderEvolCategoriesChart() {
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
          const c = yd?.categories.find(c => c.name === cat);
          return c ? c.amount : null;
        }),
        borderColor: COLORS[i % COLORS.length],
        backgroundColor: COLORS[i % COLORS.length],
        tension: 0.35,
        spanGaps: true,
        borderWidth: 2.5,
        pointRadius: 5,
        pointHoverRadius: 7,
        pointStyle: 'circle',
      }))
    },
    options: {
      layout: { padding: { right: 8 } },
      plugins: {
        legend: {
          position: 'right',
          align: 'start',
          labels: {
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 10,
            boxHeight: 10,
            padding: 14,
            font: { size: 11, weight: '500' },
            sort: (a, b) => a.text.localeCompare(b.text, 'fr'),
          }
        },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmtEUR(ctx.raw) } }
      },
      scales: { y: { ticks: { callback: v => fmtEUR(v) } } }
    }
  });
}

function buildDetailRows() {
  const rows = [];
  const valueCols = getValueColumns();
  DATA.mandatory.items.forEach(item => {
    valueCols.forEach(col => {
      const v = item[col];
      if (v == null || v === '') return;
      const year = col.match(/\d{4}/)?.[0];
      if (!year) return;
      rows.push({ type: 'Obligatoire', year, category: shortName(item.name), organisme: item.name, amount: v, currency: col.includes('€') ? 'EUR' : 'USD', nature: '', isBreakdown: false, isCategory: false });
    });
  });
  DATA.voluntary.forEach(yd => {
    yd.categories.forEach(c => {
      if (c.amount != null) rows.push({ type: 'Volontaire', year: yd.year, category: c.name, organisme: '— Total catégorie —', amount: c.amount, currency: 'EUR', nature: '', isBreakdown: false, isCategory: true });
    });
    yd.items.forEach(i => {
      if (i.amount == null) return;
      rows.push({ type: 'Volontaire', year: yd.year, category: i.category || '', organisme: i.organisme, amount: i.amount, currency: 'EUR', nature: i.nature, isBreakdown: i.is_breakdown, isCategory: false });
    });
  });
  return rows;
}

function rebuildFilterYearSelect() {
  const filterYear = document.getElementById('filter-year');
  const cur = filterYear.value;
  filterYear.querySelectorAll('option:not([value="all"])').forEach(o => o.remove());
  DATA.voluntary.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.year; opt.textContent = v.year;
    filterYear.appendChild(opt);
  });
  filterYear.value = cur;
}

function renderDetailsTable() {
  const tbody = document.querySelector('#table-details tbody');
  const yf = document.getElementById('filter-year').value;
  const tf = document.getElementById('filter-type').value;
  const q = document.getElementById('filter-search').value.toLowerCase();
  tbody.innerHTML = allRows.filter(r => {
    if (yf !== 'all' && String(r.year) !== yf) return false;
    if (tf === 'mandatory' && r.type !== 'Obligatoire') return false;
    if (tf === 'voluntary' && r.type !== 'Volontaire') return false;
    if (q && !(r.organisme + r.category + r.nature).toLowerCase().includes(q)) return false;
    return true;
  }).map(r => {
    const cls = [r.isBreakdown ? 'breakdown' : '', r.isCategory ? 'category-row' : ''].filter(Boolean).join(' ');
    const amt = r.currency === 'EUR' ? fmtEUR(r.amount) : fmtUSD(r.amount);
    return `<tr class="${cls}"><td>${r.type}</td><td>${r.year}</td><td>${r.category}</td><td>${r.organisme}</td><td class="amount">${amt}</td><td>${r.nature}</td></tr>`;
  }).join('');
}

function renderAll() {
  renderOverviewKPIs();
  renderChartsOverview();
  renderMandatorySection();
  rebuildVoluntaryYearSelect();
  renderVoluntaryYear(parseInt(document.getElementById('year-vol').value));
  renderEvolCategoriesChart();
  allRows = buildDetailRows();
  rebuildFilterYearSelect();
  renderDetailsTable();
}

document.getElementById('year-mandatory').addEventListener('change', e => updateMandatoryKPIAndBar(e.target.value));
document.getElementById('year-vol').addEventListener('change', e => renderVoluntaryYear(parseInt(e.target.value)));
['filter-year','filter-type','filter-search'].forEach(id => {
  document.getElementById(id).addEventListener('input', renderDetailsTable);
  document.getElementById(id).addEventListener('change', renderDetailsTable);
});
document.getElementById('export-csv').addEventListener('click', () => {
  const yf = document.getElementById('filter-year').value;
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

renderAll();

// ── ADMIN ─────────────────────────────────────────────────────────────────────
const ADMIN_PASSWORD = 'admin2026';
let adminAuthenticated = false;
let adminWorkingData = null;

function openAdmin() {
  document.getElementById('adminOverlay').classList.add('open');
  renderAdminPanel();
}
function closeAdmin() {
  document.getElementById('adminOverlay').classList.remove('open');
}

function renderAdminPanel() {
  const body = document.getElementById('adminBody');
  if (!adminAuthenticated) {
    body.innerHTML = `<div class="admin-login">
      <p style="color:var(--text2);font-size:.88rem;">Accès réservé — saisissez le mot de passe</p>
      <input type="password" id="adminPwd" placeholder="Mot de passe" onkeydown="if(event.key==='Enter')checkAdminPassword()">
      <button type="button" onclick="checkAdminPassword()">Accéder</button>
      <p class="err" id="adminPwdErr">Mot de passe incorrect</p>
    </div>`;
    return;
  }
  if (!adminWorkingData) adminWorkingData = deepClone(PAGEBLOCK);
  if (document.getElementById('adminMandatoryTable')) collectAdminFormData();
  body.innerHTML = buildAdminHTML();
}

function checkAdminPassword() {
  const pwd = document.getElementById('adminPwd').value;
  if (pwd === ADMIN_PASSWORD) {
    adminAuthenticated = true;
    adminWorkingData = deepClone(PAGEBLOCK);
    renderAdminPanel();
  } else {
    document.getElementById('adminPwdErr').style.display = 'block';
  }
}

function esc(s) { return String(s ?? '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

function buildAdminHTML() {
  const wd = adminWorkingData;
  const valueCols = wd.mandatory.headers.filter(h => h !== 'Contributions obligatoires' && !h.includes('Date limite'));
  let mandHtml = `<thead><tr><th>Convention</th>`;
  valueCols.forEach(h => { mandHtml += `<th>${esc(h)}</th>`; });
  mandHtml += `</tr></thead><tbody>`;
  wd.mandatory.items.forEach((item, ri) => {
    mandHtml += `<tr><td>${esc(item.name)}</td>`;
    valueCols.forEach(col => {
      const v = item[col];
      mandHtml += `<td><input type="text" data-mand-row="${ri}" data-mand-col="${esc(col)}" value="${v == null ? '' : v}" onchange="adminMandatoryChange(this)"></td>`;
    });
    mandHtml += `</tr>`;
  });
  mandHtml += `</tbody>`;

  const volYear = parseInt(document.getElementById('adminVolYear')?.value) || wd.voluntary[wd.voluntary.length-1].year;
  const yd = wd.voluntary.find(v => v.year === volYear) || wd.voluntary[0];

  let catHtml = `<thead><tr><th>Catégorie</th><th>Montant (€)</th><th></th></tr></thead><tbody>`;
  (yd.categories || []).forEach((c, ci) => {
    catHtml += `<tr><td><input data-vol-year="${yd.year}" data-cat-idx="${ci}" data-field="name" value="${esc(c.name)}" onchange="adminVolCategoryChange(this)"></td>
      <td><input data-vol-year="${yd.year}" data-cat-idx="${ci}" data-field="amount" value="${c.amount ?? ''}" onchange="adminVolCategoryChange(this)"></td>
      <td><button type="button" class="admin-btn secondary" onclick="adminRemoveCategory(${yd.year},${ci})">×</button></td></tr>`;
  });
  catHtml += `</tbody>`;

  let itemsHtml = `<thead><tr><th>Organisme</th><th>Montant (€)</th><th>Catégorie</th><th>Nature</th><th>Dont</th><th></th></tr></thead><tbody>`;
  (yd.items || []).forEach((it, ii) => {
    itemsHtml += `<tr>
      <td><input data-vol-year="${yd.year}" data-item-idx="${ii}" data-field="organisme" value="${esc(it.organisme)}" onchange="adminVolItemChange(this)"></td>
      <td><input data-vol-year="${yd.year}" data-item-idx="${ii}" data-field="amount" value="${it.amount ?? ''}" onchange="adminVolItemChange(this)"></td>
      <td><input data-vol-year="${yd.year}" data-item-idx="${ii}" data-field="category" value="${esc(it.category||'')}" onchange="adminVolItemChange(this)"></td>
      <td><input data-vol-year="${yd.year}" data-item-idx="${ii}" data-field="nature" value="${esc(it.nature||'')}" onchange="adminVolItemChange(this)"></td>
      <td style="text-align:center"><input type="checkbox" data-vol-year="${yd.year}" data-item-idx="${ii}" data-field="is_breakdown" ${it.is_breakdown?'checked':''} onchange="adminVolItemChange(this)"></td>
      <td><button type="button" class="admin-btn secondary" onclick="adminRemoveItem(${yd.year},${ii})">×</button></td></tr>`;
  });
  itemsHtml += `</tbody>`;

  return `
    <div class="admin-section">
      <h3>Contributions obligatoires <span class="admin-badge">Conventions</span></h3>
      <div class="admin-btn-row" style="margin-bottom:.8rem;">
        <button type="button" class="admin-btn secondary" onclick="adminAddMandatoryColumn()">+ Ajouter une colonne année</button>
        <button type="button" class="admin-btn secondary" onclick="adminAddConvention()">+ Ajouter une convention</button>
      </div>
      <div class="admin-table-wrap"><table class="admin-table" id="adminMandatoryTable">${mandHtml}</table></div>
    </div>
    <div class="admin-section">
      <h3>Contributions volontaires (DSMT)</h3>
      <div class="admin-controls">
        <label>Année
          <select id="adminVolYear" onchange="renderAdminPanel()">
            ${wd.voluntary.map(v => `<option value="${v.year}" ${v.year===volYear?'selected':''}>${v.year}</option>`).join('')}
          </select>
        </label>
        <button type="button" class="admin-btn secondary" onclick="adminAddVoluntaryYear()">+ Ajouter une année</button>
        <button type="button" class="admin-btn secondary" onclick="adminAddCategory()">+ Catégorie</button>
        <button type="button" class="admin-btn secondary" onclick="adminAddItem()">+ Ligne de financement</button>
      </div>
      <h4 style="font-size:.85rem;margin:.5rem 0 .4rem;color:var(--text2);">Catégories</h4>
      <div class="admin-table-wrap"><table class="admin-table" id="adminCatTable">${catHtml}</table></div>
      <h4 style="font-size:.85rem;margin:1rem 0 .4rem;color:var(--text2);">Lignes de financement</h4>
      <div class="admin-table-wrap"><table class="admin-table" id="adminItemsTable">${itemsHtml}</table></div>
    </div>
    <div class="admin-section">
      <h3>Exporter le bloc de données</h3>
      <p style="font-size:.84rem;color:var(--text2);margin-bottom:.8rem;">Générez le nouveau bloc à copier-coller dans le fichier HTML source.</p>
      <div class="admin-btn-row" style="margin-bottom:.8rem;">
        <button type="button" class="admin-btn" onclick="adminGenerateExport()">Générer le bloc</button>
        <button type="button" class="admin-btn secondary" onclick="adminCopyExport()">Copier</button>
        <button type="button" class="admin-btn secondary" onclick="adminDownloadExport()">Télécharger (.txt)</button>
        <button type="button" class="admin-btn secondary" onclick="adminPreview()">Prévisualiser</button>
      </div>
      <textarea id="adminExport" readonly placeholder="Cliquez sur « Générer le bloc »…"></textarea>
    </div>
    <div class="admin-section admin-tutorial">
      <h3>Tutoriel — Mettre à jour la page en 4 étapes</h3>
      <ol class="admin-steps">
        <li><strong>Modifiez les données</strong> dans les tableaux ci-dessus (obligatoires et volontaires), puis cliquez sur <strong>Prévisualiser</strong> pour vérifier le rendu.</li>
        <li>Cliquez sur <strong>Générer le bloc</strong>, puis <strong>Copier</strong> ou <strong>Télécharger (.txt)</strong>.</li>
        <li>Ouvrez le fichier <code>contributions_dsmt.html</code> dans un éditeur de texte. Repérez la section <code>// ═══ BLOC DE DONNÉES</code> en haut du second bloc <code>&lt;script&gt;</code>.</li>
        <li><strong>Remplacez</strong> tout le bloc (de <code>// ═══ BLOC DE DONNÉES</code> jusqu'à <code>loadFromPageblock();</code> inclus) par le contenu exporté. Enregistrez et rouvrez la page dans le navigateur.</li>
      </ol>
      <p style="font-size:.75rem;color:var(--text2);margin-top:1rem;">Astuce : vous pouvez aussi relancer <code>python3 generate_visualisation.py</code> après mise à jour du fichier Excel source.</p>
    </div>`;
}

function adminMandatoryChange(input) {
  const row = parseInt(input.dataset.mandRow);
  const col = input.dataset.mandCol;
  const raw = input.value.trim();
  const val = raw === '' ? null : parseFloat(raw.replace(/\s/g,'').replace(',','.'));
  if (raw !== '' && isNaN(val)) { input.classList.add('changed'); return; }
  adminWorkingData.mandatory.items[row][col] = val;
  input.classList.add('changed');
}

function adminVolCategoryChange(input) {
  const year = parseInt(input.dataset.volYear);
  const idx = parseInt(input.dataset.catIdx);
  const field = input.dataset.field;
  const yd = adminWorkingData.voluntary.find(v => v.year === year);
  if (field === 'amount') {
    const raw = input.value.trim();
    yd.categories[idx].amount = raw === '' ? null : parseFloat(raw.replace(',','.'));
  } else {
    yd.categories[idx].name = input.value;
  }
  input.classList.add('changed');
}

function adminVolItemChange(input) {
  const year = parseInt(input.dataset.volYear);
  const idx = parseInt(input.dataset.itemIdx);
  const field = input.dataset.field;
  const yd = adminWorkingData.voluntary.find(v => v.year === year);
  const it = yd.items[idx];
  if (field === 'amount') {
    const raw = input.value.trim();
    it.amount = raw === '' ? null : parseFloat(raw.replace(',','.'));
  } else if (field === 'is_breakdown') {
    it.is_breakdown = input.checked;
  } else {
    it[field] = input.value;
  }
  input.classList.add('changed');
}

function adminAddMandatoryColumn() {
  const year = prompt('Année (ex. 2027) :');
  if (!year) return;
  const cur = prompt('Devise ($ ou €) :', '$');
  if (!cur) return;
  const col = `${year} (${cur})`;
  if (adminWorkingData.mandatory.headers.includes(col)) { alert('Colonne déjà existante.'); return; }
  const idx = adminWorkingData.mandatory.headers.findIndex(h => h.includes('Reliquats'));
  if (idx >= 0) adminWorkingData.mandatory.headers.splice(idx, 0, col);
  else adminWorkingData.mandatory.headers.push(col);
  adminWorkingData.mandatory.items.forEach(item => { item[col] = null; });
  renderAdminPanel();
}

function adminAddConvention() {
  const name = prompt('Nom de la convention :');
  if (!name) return;
  const item = { name };
  adminWorkingData.mandatory.headers.forEach((h, i) => {
    if (i > 0 && !h.includes('Date limite')) item[h] = null;
  });
  adminWorkingData.mandatory.items.push(item);
  renderAdminPanel();
}

function adminAddVoluntaryYear() {
  const newYear = prompt('Numéro de la nouvelle année :', String((adminWorkingData.voluntary.at(-1)?.year || 2026) + 1));
  if (!newYear) return;
  const y = parseInt(newYear);
  if (isNaN(y) || adminWorkingData.voluntary.some(v => v.year === y)) { alert('Année invalide ou déjà existante.'); return; }
  adminWorkingData.voluntary.push({ year: y, categories: [], items: [], totals: null });
  adminWorkingData.voluntary.sort((a,b) => a.year - b.year);
  renderAdminPanel();
}

function adminAddCategory() {
  const year = parseInt(document.getElementById('adminVolYear')?.value) || adminWorkingData.voluntary.at(-1).year;
  const yd = adminWorkingData.voluntary.find(v => v.year === year);
  const id = (yd.categories.at(-1)?.id || 0) + 1;
  yd.categories.push({ id, name: 'Nouvelle catégorie', amount: 0 });
  renderAdminPanel();
}

function adminAddItem() {
  const year = parseInt(document.getElementById('adminVolYear')?.value) || adminWorkingData.voluntary.at(-1).year;
  const yd = adminWorkingData.voluntary.find(v => v.year === year);
  yd.items.push({ organisme: 'Nouvel organisme', amount: 0, nature: '', category: '', category_id: null, is_breakdown: false, year });
  renderAdminPanel();
}

function adminRemoveCategory(year, idx) {
  const yd = adminWorkingData.voluntary.find(v => v.year === year);
  yd.categories.splice(idx, 1);
  renderAdminPanel();
}

function adminRemoveItem(year, idx) {
  const yd = adminWorkingData.voluntary.find(v => v.year === year);
  yd.items.splice(idx, 1);
  renderAdminPanel();
}

function collectAdminFormData() {
  document.querySelectorAll('#adminMandatoryTable input').forEach(adminMandatoryChange);
  document.querySelectorAll('#adminCatTable input').forEach(adminVolCategoryChange);
  document.querySelectorAll('#adminItemsTable input').forEach(el => {
    if (el.type === 'checkbox') adminVolItemChange(el);
    else adminVolItemChange(el);
  });
}

function formatPagblockExport(wd) {
  return `// ═══════════════════════════════════════════════════════════════════════════════
// BLOC DE DONNÉES — Remplacez tout ce bloc pour mettre à jour la page
// ═══════════════════════════════════════════════════════════════════════════════
const PAGEBLOCK = ${JSON.stringify(wd, null, 2)};
let DATA;
function deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }
function loadFromPageblock() { DATA = deepClone(PAGEBLOCK); }
loadFromPageblock();
`;
}

function adminGenerateExport() {
  collectAdminFormData();
  document.getElementById('adminExport').value = formatPagblockExport(adminWorkingData);
}

function adminPreview() {
  collectAdminFormData();
  Object.assign(PAGEBLOCK, deepClone(adminWorkingData));
  loadFromPageblock();
  renderAll();
  alert('Prévisualisation appliquée. Exportez le bloc pour rendre les changements permanents dans le fichier HTML.');
}

function adminCopyExport() {
  if (!document.getElementById('adminExport').value) adminGenerateExport();
  const ta = document.getElementById('adminExport');
  ta.select();
  navigator.clipboard.writeText(ta.value).then(() => alert('Bloc copié !')).catch(() => {
    document.execCommand('copy');
    alert('Bloc copié !');
  });
}

function adminDownloadExport() {
  if (!document.getElementById('adminExport').value) adminGenerateExport();
  const blob = new Blob([document.getElementById('adminExport').value], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'bloc-donnees-contributions-dsmt.txt';
  a.click();
  URL.revokeObjectURL(a.href);
}

document.getElementById('adminOverlay').addEventListener('click', e => {
  if (e.target.id === 'adminOverlay') closeAdmin();
});
