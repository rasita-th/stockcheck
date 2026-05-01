const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

const scanTable = $('#scanTable');
const tableBody = $('#scanTable tbody');
const tableHeader = $('#scanHeader');
const mobileCards = $('#mobileCards');
const statusEl = $('#status');
const errorsEl = $('#errors');
const scanBtn = $('#scanBtn');
const refreshBtn = $('#refreshBtn');
const marketClock = $('#market-clock');

const STORAGE_KEYS = {
  screeners: 'stockTimingRadar.screeners.v3',
  active: 'stockTimingRadar.activeSettings.v8.hybridStatic',
  alphaQuota: 'stockTimingRadar.alphaVantage.quota.v1',
  alphaCache: 'stockTimingRadar.alphaVantage.cache.v1'
};

const columnDefs = [
  { key: 'symbol', label: 'Ticker', sortKey: 'symbol', align: 'left', group: 'base', defaultVisible: true },
  { key: 'score', label: 'Score', sortKey: 'score', align: 'right', group: 'base', defaultVisible: true },
  { key: 'signal', label: 'Signal', sortKey: 'signal', align: 'left', group: 'base', defaultVisible: true },
  { key: 'close', label: 'Last Price', sortKey: 'close', align: 'right', group: 'price', defaultVisible: true },
  { key: 'ema5', label: 'EMA5 Price', sortKey: 'ema5', align: 'right', group: 'ema', defaultVisible: true },
  { key: 'pctVsEma5', label: 'vs EMA 5', sortKey: 'pctVsEma5', align: 'right', group: 'gap', defaultVisible: true },
  { key: 'ema20', label: 'EMA20 Price', sortKey: 'ema20', align: 'right', group: 'ema', defaultVisible: true },
  { key: 'pctVsEma20', label: 'vs EMA 20', sortKey: 'pctVsEma20', align: 'right', group: 'gap', defaultVisible: true },
  { key: 'ema89', label: 'EMA89 Price', sortKey: 'ema89', align: 'right', group: 'ema', defaultVisible: true },
  { key: 'pctVsEma89', label: 'vs EMA 89', sortKey: 'pctVsEma89', align: 'right', group: 'gap', defaultVisible: true },
  { key: 'ema200', label: 'EMA200 Price', sortKey: 'ema200', align: 'right', group: 'ema', defaultVisible: true },
  { key: 'pctVsEma200', label: 'vs EMA 200', sortKey: 'pctVsEma200', align: 'right', group: 'gap', defaultVisible: true },
  { key: 'rsi14', label: 'RSI', sortKey: 'rsi14', align: 'right', group: 'indicator', defaultVisible: true },
  { key: 'macd1226', label: 'MACD 12,26', sortKey: 'macd1226', align: 'right', group: 'macd', defaultVisible: true },
  { key: 'macdSignal9', label: 'MACD Signal 9', sortKey: 'macdSignal9', align: 'right', group: 'macd', defaultVisible: false },
  { key: 'macdHist', label: 'MACD Hist', sortKey: 'macdHist', align: 'right', group: 'macd', defaultVisible: false },
  { key: 'volumeRatio20', label: 'Vol/20D', sortKey: 'volumeRatio20', align: 'right', group: 'indicator', defaultVisible: true },
  { key: 'high52w', label: '52 Wks High', sortKey: 'high52w', align: 'right', group: 'range', defaultVisible: true },
  { key: 'low52w', label: '52 Wks Low', sortKey: 'low52w', align: 'right', group: 'range', defaultVisible: true }
];


const fundamentalColumnDefs = [
  { key: 'symbol', label: 'Ticker', sortKey: 'symbol', align: 'left', group: 'base', defaultVisible: true },
  { key: 'fundamentalScore', label: 'Fund. Score', sortKey: 'fundamentalScore', align: 'right', group: 'base', defaultVisible: true },
  { key: 'fundamentalSignal', label: 'Signal', sortKey: 'fundamentalSignal', align: 'left', group: 'base', defaultVisible: true },
  { key: 'latestQuarter', label: 'Latest Quarter', sortKey: 'latestQuarter', align: 'left', group: 'fundamental', defaultVisible: true },
  { key: 'earningsDate', label: 'Period End', sortKey: 'earningsDate', align: 'left', group: 'fundamental', defaultVisible: true },
  { key: 'revenue', label: 'Revenue', sortKey: 'revenue', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'revenuePrevQuarter', label: 'Rev Prev Q', sortKey: 'revenuePrevQuarter', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'revenueYearAgo', label: 'Rev Year Ago', sortKey: 'revenueYearAgo', align: 'right', group: 'fundamental', defaultVisible: false },
  { key: 'priorCompanyGuidanceRevenuePeriod', label: 'Prior Guide Period', sortKey: 'priorCompanyGuidanceRevenuePeriod', align: 'left', group: 'fundamental', defaultVisible: false },
  { key: 'priorCompanyGuidanceRevenue', label: 'Prior Co. Guide Mid', sortKey: 'priorCompanyGuidanceRevenue', align: 'right', group: 'fundamental', defaultVisible: false },
  { key: 'actualVsPriorGuidanceRevenuePct', label: 'Actual vs Prior Guide %', sortKey: 'actualVsPriorGuidanceRevenuePct', align: 'right', group: 'fundamental', defaultVisible: false },
  { key: 'nextCompanyGuidanceRevenue', label: 'Next Co. Guide Mid', sortKey: 'nextCompanyGuidanceRevenue', align: 'right', group: 'fundamental', defaultVisible: false },
  { key: 'nextCompanyGuidanceRevenuePeriod', label: 'Next Guide Period', sortKey: 'nextCompanyGuidanceRevenuePeriod', align: 'left', group: 'fundamental', defaultVisible: false },
  { key: 'revenueQoQ', label: 'Rev QoQ', sortKey: 'revenueQoQ', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'revenueYoY', label: 'Rev YoY', sortKey: 'revenueYoY', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'netIncome', label: 'Net Income', sortKey: 'netIncome', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'netIncomePrevQuarter', label: 'NI Prev Q', sortKey: 'netIncomePrevQuarter', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'netIncomeYearAgo', label: 'NI Year Ago', sortKey: 'netIncomeYearAgo', align: 'right', group: 'fundamental', defaultVisible: false },
  { key: 'profitQoQ', label: 'Profit QoQ', sortKey: 'profitQoQ', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'profitYoY', label: 'Profit YoY', sortKey: 'profitYoY', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'eps', label: 'EPS', sortKey: 'eps', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'epsPrevQuarter', label: 'EPS Prev Q', sortKey: 'epsPrevQuarter', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'epsYearAgo', label: 'EPS Year Ago', sortKey: 'epsYearAgo', align: 'right', group: 'fundamental', defaultVisible: false },
  { key: 'epsQoQ', label: 'EPS QoQ', sortKey: 'epsQoQ', align: 'right', group: 'fundamental', defaultVisible: true },
  { key: 'epsYoY', label: 'EPS YoY', sortKey: 'epsYoY', align: 'right', group: 'fundamental', defaultVisible: true }
];

const defaultFundColumns = Object.fromEntries(fundamentalColumnDefs.map(col => [col.key, col.defaultVisible]));

const defaultColumns = Object.fromEntries(columnDefs.map(col => [col.key, col.defaultVisible]));

const compactColumns = {
  symbol: true,
  score: true,
  signal: true,
  close: true,
  ema5: false,
  pctVsEma5: false,
  ema20: true,
  pctVsEma20: true,
  ema89: false,
  pctVsEma89: false,
  ema200: true,
  pctVsEma200: true,
  rsi14: true,
  macd1226: true,
  macdSignal9: false,
  macdHist: false,
  volumeRatio20: true,
  high52w: true,
  low52w: true
};

const emaFocusColumns = {
  symbol: true,
  score: true,
  signal: false,
  close: true,
  ema5: true,
  pctVsEma5: true,
  ema20: true,
  pctVsEma20: true,
  ema89: true,
  pctVsEma89: true,
  ema200: true,
  pctVsEma200: true,
  rsi14: false,
  macd1226: true,
  macdSignal9: true,
  macdHist: true,
  volumeRatio20: false,
  high52w: false,
  low52w: false
};

const state = {
  rows: [],
  filteredRows: [],
  sortKey: 'score',
  sortDir: 'desc',
  lastSymbols: '',
  columns: { ...defaultColumns },
  fundColumns: { ...defaultFundColumns },
  activeTab: 'technical',
  scannerData: null,
  quotes: {},
  currentDetail: null,
  analystCache: {},
  analystLoading: {},
  alphaKeyFetched: false,
  fundDetailTab: 'earnings'
};

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}


function renderAiReasonItem(text) {
  const raw = String(text ?? '');
  const parts = raw.split(/\s+[—-]\s*ที่มา:\s*/);
  if (parts.length < 2) {
    return `<li>${escapeHtml(raw)}</li>`;
  }
  const main = parts.shift();
  const source = parts.join(' — ที่มา: ').trim();
  return `<li>
    <span class="ai-reason-main">${escapeHtml(main)}</span>
    <details class="ai-source-inline">
      <summary title="เปิดดูที่มาของข้อมูล">ที่มา</summary>
      <div>${escapeHtml(source)}</div>
    </details>
  </li>`;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  const sign = Number(value) > 0 ? '+' : '';
  return `${sign}${formatNumber(value, 2)}%`;
}

function formatDaysToNextQuarter(value) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) return 'N/A';
  const n = Math.round(Number(value));
  if (n < 0) return `Overdue ${Math.abs(n)}d`;
  if (n === 0) return 'Today';
  return `${n}d`;
}

function clsForPct(value) {
  if (value === null || value === undefined) return '';
  if (value > 0) return 'good';
  if (value < 0) return 'bad';
  return '';
}

function clsForRsi(value) {
  if (value === null || value === undefined) return '';
  if (value >= 75) return 'hot';
  if (value >= 65) return 'warn';
  if (value >= 45) return 'good';
  if (value < 35) return 'bad';
  return 'warn';
}

function clsForMacd(value) {
  if (value === null || value === undefined) return '';
  if (value > 0) return 'good';
  if (value < 0) return 'bad';
  return 'warn';
}

function signalClass(signal = '') {
  const text = String(signal || '');
  if (text.includes('Fundamental Beat') || text.includes('Strong')) return 'fund-strong';
  if (text.includes('Solid')) return 'fund-watch';
  if (text.includes('Mixed')) return 'fund-mixed';
  if (text.includes('WEAK') || text.includes('AVOID') || text.includes('Weak')) return 'fund-weak';
  if (text.includes('BUY')) return 'buy';
  if (text.includes('WATCH')) return 'watch';
  if (text.includes('HOT')) return 'hot';
  return 'neutral';
}

function setStatus(text) {
  statusEl.textContent = text;
}

function setScreenerStatus(text) {
  $('#screenerStatus').textContent = text;
}

function parseSymbols() {
  return $('#symbols').value
    .replace(/\n/g, ',')
    .split(',')
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
    .filter((v, i, arr) => arr.indexOf(v) === i);
}

function getActiveColumnDefs() {
  return state.activeTab === 'fundamental' ? fundamentalColumnDefs : columnDefs;
}

function getActiveColumnState() {
  return state.activeTab === 'fundamental' ? state.fundColumns : state.columns;
}

function sanitizeColumnState(colState, defs) {
  const allowed = new Set(defs.map(col => col.key));
  return Object.fromEntries(Object.entries(colState || {}).filter(([key]) => allowed.has(key)));
}

function getVisibleColumns() {
  const defs = getActiveColumnDefs();
  const colState = getActiveColumnState();
  const visible = defs.filter(col => colState[col.key]);
  if (!visible.length) return [defs[0]];
  return visible;
}

function classForColumn(col) {
  const classes = [];
  if (col.align === 'right') classes.push('num');
  if (col.group) classes.push(`col-${col.group}`);
  return classes.join(' ');
}

function renderValue(row, col) {
  const value = row[col.key];
  if (value === null || value === undefined || value === '') return 'N/A';
  if (['pctVsEma5', 'pctVsEma20', 'pctVsEma89', 'pctVsEma200', 'revenueSurprisePct', 'revenueQoQ', 'revenueYoY', 'profitSurprisePct', 'profitQoQ', 'profitYoY', 'epsSurprisePct', 'epsQoQ', 'epsYoY', 'guidanceRevenueDeltaPct', 'actualVsPriorGuidanceRevenuePct'].includes(col.key)) return formatPct(value);
  if (col.key === 'rsi14') return formatNumber(value, 1);
  if (col.key === 'volumeRatio20') return `${formatNumber(value, 2)}x`;
  if (['macd1226', 'macdSignal9', 'macdHist', 'eps', 'estimatedEps', 'epsPrevQuarter', 'epsYearAgo'].includes(col.key)) return formatNumber(value, 3);
  if (['revenue', 'revenuePrevQuarter', 'revenueYearAgo', 'estimatedRevenue', 'companyGuidanceRevenue', 'companyGuidanceRevenueLow', 'companyGuidanceRevenueHigh', 'priorCompanyGuidanceRevenue', 'priorCompanyGuidanceRevenueLow', 'priorCompanyGuidanceRevenueHigh', 'nextCompanyGuidanceRevenue', 'nextCompanyGuidanceRevenueLow', 'nextCompanyGuidanceRevenueHigh', 'netIncome', 'netIncomePrevQuarter', 'netIncomeYearAgo'].includes(col.key)) return formatBig(value);
  if (typeof value === 'string') return escapeHtml(value);
  return formatNumber(value);
}

function valueClass(row, col) {
  if (['pctVsEma5', 'pctVsEma20', 'pctVsEma89', 'pctVsEma200', 'revenueSurprisePct', 'revenueQoQ', 'revenueYoY', 'profitSurprisePct', 'profitQoQ', 'profitYoY', 'epsSurprisePct', 'epsQoQ', 'epsYoY', 'guidanceRevenueDeltaPct', 'actualVsPriorGuidanceRevenuePct'].includes(col.key)) return clsForPct(row[col.key]);
  if (col.key === 'rsi14') return clsForRsi(row.rsi14);
  if (['macd1226', 'macdSignal9', 'macdHist'].includes(col.key)) return clsForMacd(row[col.key]);
  return '';
}

function renderTableHeader() {
  const visibleCols = getVisibleColumns();
  const approxColumnWidth = state.activeTab === 'fundamental' ? 132 : 118;
  if (scanTable) {
    scanTable.className = state.activeTab === 'fundamental' ? 'table-fundamental' : 'table-technical';
    scanTable.style.minWidth = `${Math.max(window.innerWidth - 72, visibleCols.length * approxColumnWidth)}px`;
  }
  tableHeader.innerHTML = visibleCols.map(col => {
    const sorted = state.sortKey === (col.sortKey || col.key) ? ` <span class="sort-mark">${state.sortDir === 'asc' ? '▲' : '▼'}</span>` : '';
    return `<th data-sort="${col.sortKey || col.key}" class="${classForColumn(col)}">${escapeHtml(col.label)}${sorted}</th>`;
  }).join('');

  tableHeader.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      else {
        state.sortKey = key;
        state.sortDir = key === 'symbol' || key === 'signal' ? 'asc' : 'desc';
      }
      applyFilters();
      saveActiveSettings();
    });
  });
}

function renderColumnToggles() {
  const defs = getActiveColumnDefs();
  const colState = getActiveColumnState();
  $('#columnToggles').innerHTML = defs.map(col => {
    const visible = Boolean(colState[col.key]);
    return `
      <button class="column-toggle ${visible ? 'active' : 'inactive'}" data-column="${col.key}">
        <span>${escapeHtml(col.label)}</span>
        <strong>${visible ? 'ON' : 'OFF'}</strong>
      </button>`;
  }).join('');

  $('#columnToggles').querySelectorAll('button[data-column]').forEach(button => {
    button.addEventListener('click', () => {
      const key = button.dataset.column;
      if (state.activeTab === 'fundamental') state.fundColumns[key] = !state.fundColumns[key];
      else state.columns[key] = !state.columns[key];
      renderColumnToggles();
      applyFilters();
      saveActiveSettings();
    });
  });
}

function setColumns(nextColumns) {
  if (state.activeTab === 'fundamental') state.fundColumns = { ...defaultFundColumns, ...nextColumns };
  else state.columns = { ...defaultColumns, ...nextColumns };
  renderColumnToggles();
  applyFilters();
  saveActiveSettings();
}

function getSettingsFromUi() {
  return {
    symbolsText: $('#symbols').value,
    range: $('#range').value,
    minScore: $('#minScore').value,
    filters: {
      above200: $('#filterAbove200').checked,
      emaStack: $('#filterEmaStack').checked,
      sweetRsi: $('#filterSweetRsi').checked
    },
    columns: { ...state.columns },
    fundColumns: { ...state.fundColumns },
    activeTab: state.activeTab,
    sortKey: state.sortKey,
    sortDir: state.sortDir
  };
}

function applySettingsToUi(settings = {}) {
  if (settings.symbolsText !== undefined) $('#symbols').value = settings.symbolsText;
  if (settings.range !== undefined) $('#range').value = settings.range;
  if (settings.minScore !== undefined) $('#minScore').value = settings.minScore;
  if (settings.filters) {
    $('#filterAbove200').checked = Boolean(settings.filters.above200);
    $('#filterEmaStack').checked = Boolean(settings.filters.emaStack);
    $('#filterSweetRsi').checked = Boolean(settings.filters.sweetRsi);
  }
  state.columns = { ...defaultColumns, ...sanitizeColumnState(settings.columns || {}, columnDefs) };
  state.fundColumns = { ...defaultFundColumns, ...sanitizeColumnState(settings.fundColumns || {}, fundamentalColumnDefs) };
  state.activeTab = settings.activeTab || 'technical';
  updateTabs();
  state.sortKey = settings.sortKey || (state.activeTab === 'fundamental' ? 'fundamentalScore' : 'score');
  state.sortDir = settings.sortDir || 'desc';
  renderColumnToggles();
  applyFilters();
}

function getScreeners() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.screeners) || '{}') || {};
  } catch (_) {
    return {};
  }
}

function setScreeners(screeners) {
  localStorage.setItem(STORAGE_KEYS.screeners, JSON.stringify(screeners));
}

function updateSavedScreenersDropdown(selectedName = '') {
  const select = $('#savedScreeners');
  const screeners = getScreeners();
  const names = Object.keys(screeners).sort((a, b) => a.localeCompare(b));
  select.innerHTML = names.length
    ? names.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('')
    : '<option value="">ยังไม่มี saved screener</option>';
  if (selectedName && names.includes(selectedName)) select.value = selectedName;
}

function saveActiveSettings() {
  localStorage.setItem(STORAGE_KEYS.active, JSON.stringify(getSettingsFromUi()));
}

function restoreActiveSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.active);
    if (!raw) return false;
    applySettingsToUi(JSON.parse(raw));
    return true;
  } catch (_) {
    return false;
  }
}

function saveNamedScreener() {
  const name = $('#screenerName').value.trim();
  if (!name) {
    setScreenerStatus('ใส่ชื่อ screener ก่อน เช่น AI Infra');
    return;
  }
  const screeners = getScreeners();
  screeners[name] = getSettingsFromUi();
  setScreeners(screeners);
  updateSavedScreenersDropdown(name);
  setScreenerStatus(`Saved: ${name}`);
}

function loadNamedScreener() {
  const name = $('#savedScreeners').value || $('#screenerName').value.trim();
  const screeners = getScreeners();
  if (!name || !screeners[name]) {
    setScreenerStatus('ยังไม่ได้เลือก screener ที่จะโหลด');
    return;
  }
  $('#screenerName').value = name;
  applySettingsToUi(screeners[name]);
  saveActiveSettings();
  setScreenerStatus(`Loaded: ${name}`);
  scan();
}

function deleteNamedScreener() {
  const name = $('#savedScreeners').value || $('#screenerName').value.trim();
  const screeners = getScreeners();
  if (!name || !screeners[name]) {
    setScreenerStatus('ยังไม่ได้เลือก screener ที่จะลบ');
    return;
  }
  delete screeners[name];
  setScreeners(screeners);
  updateSavedScreenersDropdown();
  setScreenerStatus(`Deleted: ${name}`);
}

function quarterSortValue(value) {
  const m = String(value || '').match(/Q([1-4])\s+(\d{4})/i);
  if (!m) return -999999;
  return Number(m[2]) * 4 + Number(m[1]);
}

function dateSortValue(value) {
  const t = Date.parse(String(value || ''));
  return Number.isFinite(t) ? t : -9999999999999;
}

function sortValueForKey(row, key) {
  if (key === 'latestQuarter') return quarterSortValue(row.latestQuarter);
  if (['earningsDate', 'periodEnd', 'latestFilingDate'].includes(key)) return dateSortValue(row[key]);
  return row[key];
}

function applyFilters() {
  const minScore = Number($('#minScore').value || 0);
  const above200 = $('#filterAbove200').checked;
  const emaStack = $('#filterEmaStack').checked;
  const sweetRsi = $('#filterSweetRsi').checked;

  let rows = [...state.rows];
  if (state.activeTab === 'fundamental') {
    rows = rows.filter(row => Number(row.fundamentalScore ?? 0) >= minScore);
  } else {
    rows = rows.filter(row => Number(row.score || 0) >= minScore);
    if (above200) rows = rows.filter(row => Number(row.pctVsEma200) > 0);
    if (emaStack) rows = rows.filter(row => Number(row.ema20) > Number(row.ema89));
    if (sweetRsi) rows = rows.filter(row => Number(row.rsi14) >= 45 && Number(row.rsi14) <= 65);
  }

  rows.sort((a, b) => {
    const key = state.sortKey;
    const va = sortValueForKey(a, key);
    const vb = sortValueForKey(b, key);
    let result;
    if (typeof va === 'string' || typeof vb === 'string') {
      result = String(va || '').localeCompare(String(vb || ''));
    } else {
      result = Number(va ?? -999999) - Number(vb ?? -999999);
    }
    return state.sortDir === 'asc' ? result : -result;
  });

  state.filteredRows = rows;
  renderTableHeader();
  renderTable(rows);
  renderMobileCards(rows);
  renderSummary(rows);
}

function renderTable(rows) {
  const visibleCols = getVisibleColumns();
  if (!rows.length) {
    tableBody.innerHTML = `<tr><td colspan="${visibleCols.length}" class="muted">ยังไม่มีหุ้นผ่าน filter</td></tr>`;
    return;
  }

  tableBody.innerHTML = rows.map(row => {
    const cells = visibleCols.map(col => renderCell(row, col)).join('');
    return `<tr data-symbol="${escapeHtml(row.symbol)}">${cells}</tr>`;
  }).join('');

  tableBody.querySelectorAll('tr[data-symbol]').forEach(row => {
    row.addEventListener('click', () => loadSymbol(row.dataset.symbol));
  });
}

function renderCell(row, col) {
  const baseClass = classForColumn(col);
  if (col.key === 'symbol') {
    return `<td class="${baseClass}"><strong>${escapeHtml(row.symbol)}</strong><br><span class="muted">${escapeHtml(row.exchange || '')} ${escapeHtml(row.currency || '')}</span></td>`;
  }
  if (col.key === 'score' || col.key === 'fundamentalScore') {
    return `<td class="${baseClass} score">${row[col.key] ?? 'N/A'}</td>`;
  }
  if (col.key === 'signal' || col.key === 'fundamentalSignal') {
    const sig = row[col.key] || 'Insufficient data';
    return `<td class="${baseClass}"><span class="pill ${signalClass(sig)}">${escapeHtml(sig)}</span></td>`;
  }
  return `<td class="${baseClass} ${valueClass(row, col)}">${renderValue(row, col)}</td>`;
}

function renderMobileCards(rows) {
  if (!mobileCards) return;
  const visibleCols = getVisibleColumns().filter(col => !['symbol', 'score', 'signal', 'fundamentalScore', 'fundamentalSignal'].includes(col.key));
  if (!rows.length) {
    mobileCards.innerHTML = '<div class="mobile-empty muted">ยังไม่มีหุ้นผ่าน filter</div>';
    return;
  }
  mobileCards.innerHTML = rows.map(row => {
    const metricItems = visibleCols.map(col => `
      <div class="mobile-metric ${col.group ? `metric-${col.group}` : ''}">
        <span>${escapeHtml(col.label)}</span>
        <strong class="${valueClass(row, col)}">${renderValue(row, col)}</strong>
      </div>`).join('');
    return `
      <article class="stock-card" data-symbol="${escapeHtml(row.symbol)}">
        <div class="stock-card-top">
          <div>
            <h3>${escapeHtml(row.symbol)}</h3>
            <p>${escapeHtml(row.exchange || '')} ${escapeHtml(row.currency || '')}</p>
          </div>
          <div class="stock-card-score">
            <span>${state.activeTab === 'fundamental' ? 'Fund. Score' : 'Score'}</span>
            <strong>${state.activeTab === 'fundamental' ? (row.fundamentalScore ?? 'N/A') : (row.score ?? '-')}</strong>
          </div>
        </div>
        <div class="stock-card-signal"><span class="pill ${signalClass(state.activeTab === 'fundamental' ? row.fundamentalSignal : row.signal)}">${escapeHtml((state.activeTab === 'fundamental' ? row.fundamentalSignal : row.signal) || '-')}</span></div>
        <div class="mobile-metric-grid">${metricItems}</div>
      </article>`;
  }).join('');

  mobileCards.querySelectorAll('.stock-card[data-symbol]').forEach(card => {
    card.addEventListener('click', () => loadSymbol(card.dataset.symbol));
  });
}

function renderSummary(rows) {
  const best = rows[0];
  if (state.activeTab === 'fundamental') {
    $('#bestSetup').textContent = best ? `${best.symbol} ${best.fundamentalScore ?? 'N/A'}` : '-';
    $('#buyWatchCount').textContent = rows.filter(r => (r.fundamentalSignal || '').includes('Strong') || (r.fundamentalSignal || '').includes('Solid')).length;
    $('#hotCount').textContent = rows.filter(r => (r.fundamentalSignal || '').includes('Weak') || (r.fundamentalSignal || '').includes('Insufficient')).length;
  } else {
    $('#bestSetup').textContent = best ? `${best.symbol} ${best.score}` : '-';
    $('#buyWatchCount').textContent = rows.filter(r => (r.signal || '').includes('BUY') || (r.signal || '').includes('WATCH')).length;
    $('#hotCount').textContent = rows.filter(r => (r.signal || '').includes('HOT') || Number(r.rsi14) >= 75).length;
  }
  $('#lastScan').textContent = new Date().toLocaleTimeString();
}

function renderErrors(errors = []) {
  if (!errors.length) {
    errorsEl.innerHTML = '';
    return;
  }
  errorsEl.innerHTML = `<strong>บางตัวดึงข้อมูลไม่ได้:</strong> ${errors.map(e => `${escapeHtml(e.symbol)}: ${escapeHtml(e.error)}`).join(' | ')}`;
}

function isLocalPythonApi() {
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || window.location.port === '8787';
}

async function fetchJsonOrThrow(url, options = {}) {
  const res = await fetch(url, options);
  const raw = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const first = raw.trim().slice(0, 1);
  if (first === '<') throw new Error('ได้ HTML แทน JSON');
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`JSON ไม่ถูกต้อง: ${err.message || err}`);
  }
}


function mergeHybridStaticData(technicalData = {}, fundamentalData = {}) {
  const fundRows = new Map((fundamentalData.rows || []).map(row => [String(row.symbol || '').toUpperCase(), row]));
  const fundDetails = fundamentalData.fundamentals || fundamentalData.quotes || {};
  const rows = (technicalData.rows || []).map(row => {
    const sym = String(row.symbol || '').toUpperCase();
    const f = fundRows.get(sym) || {};
    return { ...row, ...f, symbol: sym || row.symbol };
  });
  const quotes = {};
  Object.entries(technicalData.quotes || {}).forEach(([symRaw, quote]) => {
    const sym = String(symRaw || quote?.symbol || quote?.latest?.symbol || '').toUpperCase();
    const fDetail = fundDetails[sym] || {};
    const fLatest = fDetail.latest || fundRows.get(sym) || {};
    const fObj = fDetail.fundamental || fLatest || {};
    quotes[sym] = {
      ...(quote || {}),
      latest: { ...((quote || {}).latest || {}), ...fLatest, symbol: sym || ((quote || {}).latest || {}).symbol },
      fundamental: { ...fObj }
    };
  });
  Object.entries(fundDetails).forEach(([symRaw, fDetail]) => {
    const sym = String(symRaw || '').toUpperCase();
    if (!sym || quotes[sym]) return;
    const fLatest = fDetail.latest || fundRows.get(sym) || { symbol: sym };
    quotes[sym] = { symbol: sym, latest: { ...fLatest, symbol: sym }, fundamental: fDetail.fundamental || fLatest, series: [], meta: { source: 'fundamental-only-static' } };
  });
  return {
    ...technicalData,
    rows,
    quotes,
    errors: [...(technicalData.errors || []), ...(fundamentalData.errors || []).map(e => ({ ...e, layer: 'fundamental' }))],
    generatedAt: technicalData.generatedAtTechnical || technicalData.generatedAt || '',
    generatedAtTechnical: technicalData.generatedAtTechnical || technicalData.generatedAt || '',
    generatedAtFundamental: fundamentalData.generatedAtFundamental || fundamentalData.generatedAt || '',
    mode: 'github-pages-hybrid-static',
    dataLayers: { technical: true, fundamental: Boolean((fundamentalData.rows || []).length || Object.keys(fundDetails).length) }
  };
}

async function loadHybridStaticJson(force = false) {
  const stamp = force ? Date.now() : 'static';
  let technicalData;
  try {
    technicalData = await fetchJsonOrThrow(`data/technical.json?v=${stamp}`, { cache: force ? 'reload' : 'no-store' });
  } catch (err) {
    technicalData = await fetchJsonOrThrow(`data/scanner.json?v=${stamp}`, { cache: force ? 'reload' : 'no-store' });
  }
  let fundamentalData = { rows: [], fundamentals: {}, errors: [] };
  try {
    fundamentalData = await fetchJsonOrThrow(`data/fundamental.json?v=${stamp}`, { cache: force ? 'reload' : 'no-store' });
  } catch (_) {
    fundamentalData = { rows: [], fundamentals: {}, errors: [{ symbol: 'FUNDAMENTAL', error: 'fundamental.json not found; run Update static fundamental data workflow.' }] };
  }
  return mergeHybridStaticData(technicalData, fundamentalData);
}
async function loadScannerJson(force = false, symbolsOverride = null) {
  const symbols = symbolsOverride || parseSymbols();
  const range = ($('#range') && $('#range').value) || '1y';
  const key = `${symbols.map(s => String(s).toUpperCase()).sort().join(',')}|${range}`;
  if (state.scannerData && state.scannerKey === key && !force) return state.scannerData;

  // Local Python/IDLE mode: use the live backend instead of static scanner.json.
  // This fixes HTTP 404 when static/data/scanner.json does not exist locally.
  if (isLocalPythonApi()) {
    const params = new URLSearchParams({
      symbols: symbols.join(','),
      range,
      interval: '1d',
      v: force ? String(Date.now()) : 'live'
    });
    const data = await fetchJsonOrThrow(`/api/scan?${params.toString()}`, { cache: 'no-store' });
    data.quotes = data.quotes || {};
    state.scannerData = data;
    state.scannerKey = key;
    state.quotes = data.quotes;
    return data;
  }

  // GitHub Pages/static mode: hybrid layer.
  // technical.json refreshes frequently; fundamental.json is static/daily.
  try {
    const data = await loadHybridStaticJson(force);
    data.quotes = data.quotes || {};
    state.scannerData = data;
    state.scannerKey = key;
    state.quotes = data.quotes;
    return data;
  } catch (err) {
    throw new Error(`โหลด static hybrid data ไม่สำเร็จ: ${err.message || err}`);
  }
}


async function scan(force = false) {
  const symbols = parseSymbols();
  if (!symbols.length) return;
  state.lastSymbols = symbols.join(',');
  scanBtn.disabled = true;
  refreshBtn.disabled = true;
  setStatus(`กำลังโหลดข้อมูล ${isLocalPythonApi() ? 'local API' : 'static'} ${symbols.length} ตัว...`);
  errorsEl.innerHTML = '';
  saveActiveSettings();
  try {
    const data = await loadScannerJson(force, symbols);
    const wanted = new Set(symbols.map(s => s.toUpperCase()));
    state.rows = (data.rows || []).filter(row => wanted.has(String(row.symbol || '').toUpperCase()));
    marketClock.textContent = `${state.rows.length} tickers`;
    applyFilters();
    renderErrors((data.errors || []).filter(e => wanted.has(String(e.symbol || '').toUpperCase())));
    setStatus(`โหลดสำเร็จ ${state.rows.length} ตัว • Technical ${data.generatedAtTechnical || data.generatedAt || ''} • Fundamental ${data.generatedAtFundamental || 'not generated yet'}`);
    if (state.rows[0]) loadSymbol(state.rows[0].symbol, false);
  } catch (err) {
    setStatus('โหลดข้อมูลไม่สำเร็จ');
    errorsEl.textContent = err.message || String(err);
  } finally {
    scanBtn.disabled = false;
    refreshBtn.disabled = false;
  }
}

async function loadSymbol(symbol, updateInput = true) {
  if (!symbol) return;
  symbol = symbol.trim().toUpperCase();
  if (updateInput) $('#singleSymbol').value = symbol;
  $('#detailTitle').textContent = `${symbol} detail`;
  $('#detailSub').textContent = isLocalPythonApi()
    ? 'กำลังโหลด chart, indicators และ SEC fundamentals จาก local Python API...'
    : 'กำลังโหลด technical.json + fundamental.json จาก GitHub Pages...';
  try {
    let data = await loadScannerJson(false, state.lastSymbols ? state.lastSymbols.split(',') : parseSymbols());
    let quote = (data.quotes || {})[symbol] || (data.quotes || {})[symbol.toUpperCase()];

    // Local mode can fetch any single ticker on demand even if it was not in the current scan set.
    if (!quote && isLocalPythonApi()) {
      const range = ($('#range') && $('#range').value) || '1y';
      const params = new URLSearchParams({ symbol, range, interval: '1d', v: String(Date.now()) });
      quote = await fetchJsonOrThrow(`/api/quote?${params.toString()}`, { cache: 'no-store' });
      data.quotes = data.quotes || {};
      data.quotes[symbol] = quote;
      state.quotes = data.quotes;
    }

    if (!quote) throw new Error(`${symbol}: ยังไม่มี detail ใน static data — เพิ่มใน watchlist.txt แล้ว Run workflows ใหม่`);
    renderDetail(quote);
  } catch (err) {
    $('#detailSub').textContent = err.message || String(err);
  }
}

function renderDetail(data) {
  state.currentDetail = data;
  const latest = data.latest;
  $('#detailTitle').textContent = `${latest.symbol} — ${latest.close} ${latest.currency || ''}`;
  $('#detailSub').textContent = `Score ${latest.score}/100 • RSI ${formatNumber(latest.rsi14, 1)} • MACD ${formatNumber(latest.macd1226, 3)} • ${latest.exchange || ''} • 52 Wks Low/High ${formatNumber(latest.low52w)} - ${formatNumber(latest.high52w)}`;
  const pill = $('#detailSignal');
  pill.textContent = latest.signal;
  pill.className = `signal-pill ${signalClass(latest.signal)}`;

  renderScoreBars(latest.scoreParts || {});
  $('#reasons').innerHTML = (latest.reasons || []).slice(0, 9).map(r => `<li>${escapeHtml(r)}</li>`).join('');
  drawChart(data.series || [], latest.symbol);
  renderFundamentalDetail(data);
}

function formatBig(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  const n = Number(value);
  if (Math.abs(n) >= 1e12) return `${formatNumber(n / 1e12, 2)}T`;
  if (Math.abs(n) >= 1e9) return `${formatNumber(n / 1e9, 2)}B`;
  if (Math.abs(n) >= 1e6) return `${formatNumber(n / 1e6, 2)}M`;
  return formatNumber(n, 0);
}

function formatMetricValue(value, kind = 'money') {
  if (kind === 'eps') return value === null || value === undefined ? 'N/A' : formatNumber(value, 3);
  if (kind === 'days') return value === null || value === undefined ? 'N/A' : String(value);
  if (kind === 'pct') return value === null || value === undefined ? 'N/A' : formatPct(value);
  return formatBig(value);
}

function metricLine(label, value, kind = 'money', extraClass = '', sublabel = '') {
  return `
    <div class="statement-line ${extraClass}">
      <span>${escapeHtml(label)}</span>
      <div>
        <strong class="${extraClass}">${escapeHtml(formatMetricValue(value, kind))}</strong>
        ${sublabel ? `<small>${escapeHtml(sublabel)}</small>` : ''}
      </div>
    </div>`;
}

function statementCardHtml(title, cfg) {
  const kind = cfg.kind || 'money';
  return `
    <section class="statement-card">
      <div class="statement-card-head">
        <h4>${escapeHtml(title)}</h4>
        <span class="mini-chip">${escapeHtml(cfg.period || 'Latest')}</span>
      </div>
      <div class="statement-main">${escapeHtml(formatMetricValue(cfg.current, kind))}</div>
      <div class="statement-lines">
        ${metricLine('Prev Q', cfg.prev, kind, '', cfg.prevLabel || '')}
        ${metricLine('Year Ago', cfg.yearAgo, kind, '', cfg.yearAgoLabel || '')}
        ${metricLine('Estimate', cfg.estimate, kind, '', cfg.estimateStatus || '')}
        ${metricLine('Surprise', cfg.surprise, 'pct', clsForPct(cfg.surprise), 'vs estimate')}
        ${metricLine('QoQ', cfg.qoq, 'pct', clsForPct(cfg.qoq), cfg.qoqStatus || '')}
        ${metricLine('YoY', cfg.yoy, 'pct', clsForPct(cfg.yoy), cfg.yoyStatus || '')}
      </div>
    </section>`;
}


function analystRatingsSummary(ratings = {}) {
  const items = [
    ['Strong Buy', ratings.AnalystRatingStrongBuy],
    ['Buy', ratings.AnalystRatingBuy],
    ['Hold', ratings.AnalystRatingHold],
    ['Sell', ratings.AnalystRatingSell],
    ['Strong Sell', ratings.AnalystRatingStrongSell],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '');
  if (!items.length) return 'N/A';
  return items.map(([label, value]) => `${label}: ${value}`).join(' • ');
}


function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '' || value === '-') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function analystRatingsBarChartHtml(ratings = {}) {
  const rows = [
    { label: 'Strong Buy', key: 'AnalystRatingStrongBuy', tone: 'strong-buy' },
    { label: 'Buy', key: 'AnalystRatingBuy', tone: 'buy' },
    { label: 'Hold', key: 'AnalystRatingHold', tone: 'hold' },
    { label: 'Sell', key: 'AnalystRatingSell', tone: 'sell' },
    { label: 'Strong Sell', key: 'AnalystRatingStrongSell', tone: 'strong-sell' },
  ].map(row => ({ ...row, value: toFiniteNumber(ratings[row.key]) ?? 0 }));
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  if (!total) {
    return `
      <div class="analyst-chart-card">
        <div class="analyst-chart-head">
          <div>
            <h5>Analyst Rating Distribution</h5>
            <p>Alpha Vantage OVERVIEW ไม่มี rating split สำหรับหุ้นตัวนี้</p>
          </div>
          <span class="mini-chip chip-muted">No split</span>
        </div>
        <div class="target-empty compact-empty">ยังไม่มี Strong Buy / Buy / Hold / Sell split ให้ plot</div>
      </div>`;
  }
  return `
    <div class="analyst-chart-card">
      <div class="analyst-chart-head">
        <div>
          <h5>Analyst Rating Distribution</h5>
          <p>ดูน้ำหนัก consensus ว่าเป็น buy-heavy หรือแค่ hold-heavy</p>
        </div>
        <span class="mini-chip chip-good">${escapeHtml(String(total))} analysts</span>
      </div>
      <div class="rating-bars">
        ${rows.map(row => {
          const pct = total ? (row.value / total) * 100 : 0;
          return `
            <div class="rating-bar-row">
              <div class="rating-bar-label"><span>${escapeHtml(row.label)}</span><strong>${escapeHtml(String(row.value))}</strong></div>
              <div class="rating-bar-track" aria-label="${escapeHtml(row.label)} ${formatNumber(pct, 1)}%">
                <div class="rating-bar-fill rating-${escapeHtml(row.tone)}" style="width:${Math.max(0, Math.min(100, pct)).toFixed(2)}%"></div>
              </div>
              <div class="rating-bar-pct">${formatNumber(pct, 1)}%</div>
            </div>`;
        }).join('')}
      </div>
    </div>`;
}

function markerHtml(kind, label, value, axisMin, axisMax) {
  const n = toFiniteNumber(value);
  if (n === null) return '';
  const raw = ((n - axisMin) / (axisMax - axisMin)) * 100;
  const pct = Math.max(1.5, Math.min(98.5, raw));
  return `
    <div class="av-price-marker av-price-${escapeHtml(kind)}" style="left:${pct.toFixed(2)}%">
      <span class="av-marker-dot"></span>
      <span class="av-marker-label"><strong>${escapeHtml(label)}</strong><small>${formatNumber(n, 2)}</small></span>
    </div>`;
}

function analystPricePositionHtml(analyst = {}, overview = {}, currentPrice) {
  const current = toFiniteNumber(currentPrice);
  const target = toFiniteNumber(analyst.targetMeanPrice);
  const low52 = toFiniteNumber(overview.fiftyTwoWeekLow);
  const high52 = toFiniteNumber(overview.fiftyTwoWeekHigh);
  const values = [current, target, low52, high52].filter(v => v !== null && Number.isFinite(v));
  if (values.length < 2) {
    return `
      <div class="analyst-chart-card">
        <div class="analyst-chart-head">
          <div>
            <h5>Current vs Target Position</h5>
            <p>ต้องมีอย่างน้อย current price + target หรือ 52W range</p>
          </div>
          <span class="mini-chip chip-muted">No range</span>
        </div>
        <div class="target-empty compact-empty">ยังไม่มีข้อมูลพอสำหรับทำ price map</div>
      </div>`;
  }
  let axisMin = Math.min(...values);
  let axisMax = Math.max(...values);
  if (axisMax === axisMin) {
    axisMin = axisMin * 0.95;
    axisMax = axisMax * 1.05;
  }
  const pad = Math.max((axisMax - axisMin) * 0.08, Math.abs(axisMax || 1) * 0.01);
  axisMin = Math.max(0, axisMin - pad);
  axisMax = axisMax + pad;
  const upsideText = analyst.targetUpsidePct !== null && analyst.targetUpsidePct !== undefined ? formatPct(analyst.targetUpsidePct) : 'N/A';
  const targetContext = target !== null && high52 !== null && target > high52
    ? 'target above 52W high'
    : target !== null && low52 !== null && target < low52
      ? 'target below 52W low'
      : 'target inside visible range';
  return `
    <div class="analyst-chart-card price-position-card">
      <div class="analyst-chart-head">
        <div>
          <h5>Current vs Target Position</h5>
          <p>แผนที่ราคา: 52W low/high + ราคาปัจจุบัน + target จาก Alpha Vantage</p>
        </div>
        <span class="mini-chip ${analyst.targetUpsidePct > 0 ? 'chip-good' : analyst.targetUpsidePct < 0 ? 'chip-bad' : 'chip-muted'}">Upside ${escapeHtml(upsideText)}</span>
      </div>
      <div class="av-price-scale"><span>${formatNumber(axisMin, 2)}</span><span>${formatNumber(axisMax, 2)}</span></div>
      <div class="av-price-map">
        <div class="av-price-line"></div>
        ${markerHtml('low52', '52W Low', low52, axisMin, axisMax)}
        ${markerHtml('current', 'Current', current, axisMin, axisMax)}
        ${markerHtml('target', 'Target', target, axisMin, axisMax)}
        ${markerHtml('high52', '52W High', high52, axisMin, axisMax)}
      </div>
      <div class="av-price-note">
        <span>${escapeHtml(targetContext)}</span>
        <span>52W: ${low52 !== null ? formatNumber(low52, 2) : 'N/A'} → ${high52 !== null ? formatNumber(high52, 2) : 'N/A'}</span>
      </div>
    </div>`;
}

function analystVisualsHtml(analyst = {}, overview = {}, currentPrice) {
  return `
    <div class="analyst-visual-grid">
      ${analystRatingsBarChartHtml(analyst.ratings || {})}
      ${analystPricePositionHtml(analyst, overview, currentPrice)}
    </div>`;
}


function utcDayKey() {
  return new Date().toISOString().slice(0, 10);
}

function nextUtcMidnightLocalText() {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0));
  return next.toLocaleString(undefined, { hour12: false });
}

function safeNum(value) {
  if (value === null || value === undefined || value === '' || String(value).toLowerCase() === 'none' || String(value).toLowerCase() === 'nan') return null;
  const n = Number(String(value).replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

function getAlphaQuotaLocal() {
  const today = utcDayKey();
  let raw = null;
  try { raw = JSON.parse(localStorage.getItem(STORAGE_KEYS.alphaQuota) || 'null'); } catch (_) { raw = null; }
  if (!raw || raw.dateUtc !== today) raw = { dateUtc: today, used: 0, calls: [] };
  const used = Number(raw.used || 0);
  return {
    dateUtc: today,
    used,
    limit: 25,
    remaining: Math.max(0, 25 - used),
    resetAtLocal: nextUtcMidnightLocalText(),
    calls: Array.isArray(raw.calls) ? raw.calls : []
  };
}

function saveAlphaQuotaLocal(quota) {
  try { localStorage.setItem(STORAGE_KEYS.alphaQuota, JSON.stringify({ dateUtc: quota.dateUtc, used: quota.used, calls: quota.calls || [] })); } catch (_) {}
}

function incrementAlphaQuotaLocal(symbol) {
  const q = getAlphaQuotaLocal();
  if (q.remaining <= 0) throw new Error('Daily Alpha Vantage limit reached in this browser. Try again after reset.');
  q.used += 1;
  q.remaining = Math.max(0, q.limit - q.used);
  q.calls.push({ symbol, endpoint: 'OVERVIEW', atUtc: new Date().toISOString() });
  saveAlphaQuotaLocal(q);
  return q;
}

function getAlphaCacheLocal(symbol) {
  const today = utcDayKey();
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEYS.alphaCache) || '{}') || {};
    const hit = raw[String(symbol || '').toUpperCase()];
    if (hit && hit.dateUtc === today && hit.payload) return hit.payload;
  } catch (_) {}
  return null;
}

function setAlphaCacheLocal(symbol, payload) {
  const today = utcDayKey();
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEYS.alphaCache) || '{}') || {};
    raw[String(symbol || '').toUpperCase()] = { dateUtc: today, payload };
    localStorage.setItem(STORAGE_KEYS.alphaCache, JSON.stringify(raw));
  } catch (_) {}
}

function parseAlphaOverviewClient(ticker, raw, currentPrice) {
  if (!raw || typeof raw !== 'object') throw new Error('Alpha Vantage returned empty overview data');
  if (raw.Note) throw new Error('Alpha Vantage provider limit reached. Try again after provider reset.');
  if (raw.Information) throw new Error(String(raw.Information));
  if (raw['Error Message']) throw new Error(String(raw['Error Message']));
  if (!raw.Symbol && Object.keys(raw).length <= 2) throw new Error('Alpha Vantage returned no overview data for this ticker');
  const target = safeNum(raw.AnalystTargetPrice);
  const current = safeNum(currentPrice);
  const upside = target !== null && current && current > 0 ? (target / current - 1) * 100 : null;
  const ratingKeys = ['AnalystRatingStrongBuy', 'AnalystRatingBuy', 'AnalystRatingHold', 'AnalystRatingSell', 'AnalystRatingStrongSell'];
  const ratings = Object.fromEntries(ratingKeys.map(k => [k, safeNum(raw[k]) === null ? null : Math.trunc(safeNum(raw[k]))]));
  const analystCount = Object.values(ratings).filter(v => v !== null).reduce((a, b) => a + b, 0) || null;
  let ratingScore = null;
  if (analystCount) {
    const weights = { AnalystRatingStrongBuy: 2, AnalystRatingBuy: 1, AnalystRatingHold: 0, AnalystRatingSell: -1, AnalystRatingStrongSell: -2 };
    ratingScore = ratingKeys.reduce((sum, k) => sum + (ratings[k] || 0) * weights[k], 0) / analystCount;
  }
  return {
    ok: true,
    cached: false,
    ticker: raw.Symbol || String(ticker || '').toUpperCase(),
    name: raw.Name || null,
    source: 'Alpha Vantage OVERVIEW direct BYOK',
    fetchedAtUtc: new Date().toISOString(),
    analyst: {
      targetMeanPrice: target,
      targetUpsidePct: upside,
      targetAnalystCount: analystCount,
      ratings,
      ratingScore,
      status: (target !== null || analystCount) ? 'Loaded' : 'No analyst target fields in OVERVIEW response'
    },
    overview: {
      sector: raw.Sector || null,
      industry: raw.Industry || null,
      latestQuarter: raw.LatestQuarter || null,
      marketCapitalization: safeNum(raw.MarketCapitalization),
      epsTtm: safeNum(raw.EPS),
      revenueTtm: safeNum(raw.RevenueTTM),
      profitMargin: safeNum(raw.ProfitMargin),
      returnOnEquityTtm: safeNum(raw.ReturnOnEquityTTM),
      peRatio: safeNum(raw.PERatio),
      pegRatio: safeNum(raw.PEGRatio),
      beta: safeNum(raw.Beta),
      fiftyTwoWeekHigh: safeNum(raw['52WeekHigh']),
      fiftyTwoWeekLow: safeNum(raw['52WeekLow'])
    }
  };
}

async function fetchAlphaOverviewDirect(symbol, currentPrice, apiKey) {
  const url = 'https://www.alphavantage.co/query?' + new URLSearchParams({ function: 'OVERVIEW', symbol, apikey: apiKey }).toString();
  const raw = await fetchJsonOrThrow(url, { cache: 'no-store' });
  return parseAlphaOverviewClient(symbol, raw, currentPrice);
}

function getStoredAlphaKey() {
  try {
    return String(localStorage.getItem(AV_API_KEY_STORAGE_KEY) || '').trim();
  } catch (_) {
    return '';
  }
}

function setStoredAlphaKey(key) {
  try {
    if (key) localStorage.setItem(AV_API_KEY_STORAGE_KEY, key);
    else localStorage.removeItem(AV_API_KEY_STORAGE_KEY);
  } catch (_) {
    // Ignore browsers/storage modes that block localStorage.
  }
}

function maskApiKey(key) {
  key = String(key || '').trim();
  if (!key) return '';
  if (key.length <= 8) return '****';
  return `${key.slice(0, 4)}…${key.slice(-4)}`;
}

function alphaQuotaText(quota) {
  if (!quota) return 'Quota: unknown';
  return `Alpha Vantage quota: ${quota.used}/${quota.limit} used • ${quota.remaining} left • reset ${quota.resetAtLocal || quota.resetAtUtc || ''}`;
}

async function fetchAlphaKeyStatus() {
  const storedKey = getStoredAlphaKey();
  state.alphaKeyStatus = {
    ok: true,
    hasKey: Boolean(storedKey),
    maskedKey: storedKey ? maskApiKey(storedKey) : null,
    storage: 'browser-localStorage',
    quota: getAlphaQuotaLocal()
  };
  state.alphaKeyFetched = true;
  return state.alphaKeyStatus;
}

async function saveAlphaKeyFromInput() {
  const input = $('#avApiKeyInput');
  const status = $('#avKeyStatus');
  const apiKey = String(input?.value || '').trim();
  if (!apiKey || apiKey.length < 8) {
    if (status) status.textContent = 'ใส่ Alpha Vantage API key ให้ถูกต้องก่อน';
    return;
  }
  setStoredAlphaKey(apiKey);
  state.alphaKeyStatus = {
    ok: true,
    hasKey: true,
    maskedKey: maskApiKey(apiKey),
    storage: 'browser-localStorage',
    quota: state.alphaKeyStatus?.quota || null
  };
  state.alphaKeyFetched = true;
  if (input) input.value = '';
  if (status) status.textContent = `Saved in this browser only (${maskApiKey(apiKey)}).`;
  if (state.currentDetail) renderFundamentalDetail(state.currentDetail);
}

function clearAlphaKey() {
  setStoredAlphaKey('');
  state.alphaKeyStatus = { ok: true, hasKey: false, storage: 'browser-localStorage', quota: state.alphaKeyStatus?.quota || null };
  state.alphaKeyFetched = true;
  state.analystCache = {};
  if (state.currentDetail) renderFundamentalDetail(state.currentDetail);
}

async function loadAnalystConsensus(symbol, currentPrice) {
  symbol = String(symbol || '').trim().toUpperCase();
  if (!symbol) return;
  const apiKey = getStoredAlphaKey();
  const btn = $('#loadAnalystBtn');
  const status = $('#analystV2Status');
  if (!apiKey || apiKey.length < 8) {
    if (status) status.textContent = 'กรอกและ Save Alpha Vantage API key ใน browser นี้ก่อน';
    const input = $('#avApiKeyInput');
    if (input) input.focus();
    return;
  }
  const cached = getAlphaCacheLocal(symbol);
  if (cached) {
    state.analystCache[symbol] = { ...cached, cached: true, quota: getAlphaQuotaLocal() };
    if (status) status.textContent = 'Loaded from same-day browser cache; quota not used again.';
    if (state.currentDetail) renderFundamentalDetail(state.currentDetail);
    return;
  }
  state.analystLoading[symbol] = true;
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Loading...';
  }
  if (status) status.textContent = 'กำลังดึง Alpha Vantage OVERVIEW แบบ on-demand จาก browser...';
  try {
    const quota = incrementAlphaQuotaLocal(symbol);
    let payload = await fetchAlphaOverviewDirect(symbol, currentPrice, apiKey);
    payload = { ...payload, quota };
    setAlphaCacheLocal(symbol, payload);
    state.analystCache[symbol] = payload;
    state.alphaKeyStatus = { ...(state.alphaKeyStatus || {}), quota, hasKey: true, maskedKey: maskApiKey(apiKey), storage: 'browser-localStorage' };
    if (status) status.textContent = 'Loaded from Alpha Vantage direct BYOK.';
  } catch (err) {
    state.analystCache[symbol] = {
      ok: false,
      error: err.message || String(err),
      quota: getAlphaQuotaLocal()
    };
  } finally {
    state.analystLoading[symbol] = false;
    if (state.currentDetail) renderFundamentalDetail(state.currentDetail);
  }
}

function analystTargetSectionHtml(symbol, currentPrice) {
  const payload = state.analystCache[symbol];
  const loading = Boolean(state.analystLoading[symbol]);
  const ok = payload && payload.ok;
  const analyst = ok ? (payload.analyst || {}) : {};
  const overview = ok ? (payload.overview || {}) : {};
  const quota = payload && payload.quota;
  const errorText = payload && !payload.ok ? (payload.error || 'Could not load analyst consensus') : '';
  const sourceText = ok ? `${payload.source || 'Alpha Vantage'}${payload.cached ? ' • cached today' : ''}` : 'ยังไม่ดึงข้อมูล — กดปุ่มด้านล่างเท่านั้น';
  const keyStatus = state.alphaKeyStatus || {};
  const storedKey = getStoredAlphaKey();
  const hasLocalKey = Boolean(storedKey);
  const keyLine = hasLocalKey
    ? `API key saved in this browser only (${maskApiKey(storedKey)})`
    : (state.alphaKeyFetched ? 'ยังไม่ได้ใส่ API key ใน browser นี้' : 'กำลังเช็ก API key ใน browser...');
  const keyActionHtml = `
          <div class="analyst-key-actions">
            <input id="avApiKeyInput" type="password" autocomplete="off" placeholder="Paste Alpha Vantage API key here" />
            <button id="saveAvKeyBtn" type="button">Save locally</button>
            ${hasLocalKey ? '<button id="clearAvKeyBtn" type="button" class="secondary">Clear key</button>' : ''}
          </div>
          <small class="detail-muted">Public-safe BYOK mode: key is stored only in this browser localStorage and sent directly to Alpha Vantage only when you click Load.</small>`;
  return `
      <section class="target-section analyst-v2-section">
        <div class="target-section-head">
          <div>
            <h4>Analyst Consensus — Alpha Vantage V2.8 BYOK Manual Loader</h4>
            <p>ส่วนนี้แยกจากตาราง SEC: scan ปกติไม่เรียก Alpha Vantage, กดดึงทีละหุ้นเท่านั้น, API key เก็บเฉพาะใน browser นี้</p>
          </div>
          <span class="mini-chip ${ok ? 'chip-good' : 'chip-muted'}">${escapeHtml(ok ? 'Loaded' : 'Manual only')}</span>
        </div>
        <div class="analyst-key-box">
          <div>
            <strong>API key status</strong>
            <p id="avKeyStatus" class="detail-muted">${escapeHtml(errorText || keyLine)}</p>
          </div>
          ${keyActionHtml}
        </div>
        <div class="analyst-actions">
          <button id="loadAnalystBtn" type="button" ${loading ? 'disabled' : ''}>${loading ? 'Loading...' : `Load consensus for ${escapeHtml(symbol)}`}</button>
          <span id="analystV2Status" class="detail-muted">${escapeHtml(sourceText)}</span>
        </div>
        <div class="target-summary-grid analyst-only-grid">
          <div class="target-mini-card"><span>Current Price</span><strong>${formatNumber(currentPrice, 2)}</strong><small>from Yahoo chart</small></div>
          <div class="target-mini-card"><span>Analyst Target</span><strong>${formatNumber(analyst.targetMeanPrice, 2)}</strong><small class="${clsForPct(analyst.targetUpsidePct)}">${formatPct(analyst.targetUpsidePct)}</small></div>
          <div class="target-mini-card"><span>Analyst Count</span><strong>${analyst.targetAnalystCount ?? 'N/A'}</strong><small>${escapeHtml(analyst.status || 'not loaded')}</small></div>
          <div class="target-mini-card"><span>Rating Score</span><strong>${formatNumber(analyst.ratingScore, 2)}</strong><small>-2 sell to +2 buy</small></div>
          <div class="target-mini-card"><span>AV Latest Quarter</span><strong>${escapeHtml(overview.latestQuarter || 'N/A')}</strong><small>${escapeHtml(overview.sector || '')}</small></div>
          <div class="target-mini-card"><span>PE / PEG</span><strong>${formatNumber(overview.peRatio, 2)} / ${formatNumber(overview.pegRatio, 2)}</strong><small>Alpha overview fields</small></div>
        </div>
        ${ok ? analystVisualsHtml(analyst, overview, currentPrice) : `
          <div class="analyst-visual-grid">
            <div class="analyst-chart-card">
              <div class="analyst-chart-head"><div><h5>Analyst Rating Distribution</h5><p>กด Load consensus ก่อนเพื่อสร้าง bar chart</p></div><span class="mini-chip chip-muted">Manual</span></div>
              <div class="target-empty compact-empty">ยังไม่เรียก Alpha Vantage</div>
            </div>
            <div class="analyst-chart-card">
              <div class="analyst-chart-head"><div><h5>Current vs Target Position</h5><p>กด Load consensus เพื่อวาง target บน price range</p></div><span class="mini-chip chip-muted">Manual</span></div>
              <div class="target-empty compact-empty">รอข้อมูล target / 52W range</div>
            </div>
          </div>`}
        <p class="detail-muted">${escapeHtml(alphaQuotaText(quota || keyStatus.quota))}</p>
        <p class="detail-muted">${escapeHtml(analystRatingsSummary(analyst.ratings || {}))}</p>
        ${errorText ? `<p class="detail-muted bad">Error: ${escapeHtml(errorText)}</p>` : ''}
      </section>`;
}


function fundDetailTabsHtml(activeTab) {
  const tabs = [
    ['earnings', 'Earnings Snapshot'],
    ['guidance', 'Company Guidance View'],
    ['analyst', 'Analyst Consensus']
  ];
  return `
      <div class="fund-detail-tabs" role="tablist" aria-label="Fundamental detail sections">
        ${tabs.map(([key, label]) => `<button type="button" class="fund-detail-tab ${activeTab === key ? 'active' : ''}" data-fund-detail-tab="${key}">${label}</button>`).join('')}
      </div>`;
}

function setFundDetailTab(tab) {
  if (!['earnings', 'guidance', 'analyst'].includes(tab)) return;
  state.fundDetailTab = tab;
  if (state.currentDetail) renderFundamentalDetail(state.currentDetail);
}

function renderFundamentalDetail(data) {
  const f = data.fundamental || data.latest || {};
  const latest = data.latest || {};
  const reasons = f.fundamentalReasons || [];
  const highlights = f.fundamentalHighlights || [];
  const detail = $('#fundamentalDetail');
  if (!detail) return;

  const currentPrice = latest.close;
  const activeDetailTab = state.fundDetailTab || 'earnings';

  const earningsPanelHtml = `
      <div class="fund-tab-panel">
        <div class="statement-card-grid">
          ${statementCardHtml('Revenue', {
            kind: 'money',
            period: f.latestQuarter,
            current: f.revenue,
            prev: f.revenuePrevQuarter,
            prevLabel: f.revenuePrevQuarterLabel,
            yearAgo: f.revenueYearAgo,
            yearAgoLabel: f.revenueYearAgoLabel,
            estimate: f.estimatedRevenue,
            estimateStatus: f.estimatedRevenueStatus,
            surprise: f.revenueSurprisePct,
            qoq: f.revenueQoQ,
            yoy: f.revenueYoY,
          })}
          ${statementCardHtml('Net Income', {
            kind: 'money',
            period: f.latestQuarter,
            current: f.netIncome,
            prev: f.netIncomePrevQuarter,
            prevLabel: f.netIncomePrevQuarterLabel,
            yearAgo: f.netIncomeYearAgo,
            yearAgoLabel: f.netIncomeYearAgoLabel,
            estimate: f.estimatedNetIncome,
            estimateStatus: 'Estimate ไม่มีใน source นี้',
            surprise: f.profitSurprisePct,
            qoq: f.profitQoQ,
            qoqStatus: f.profitQoQStatus,
            yoy: f.profitYoY,
            yoyStatus: f.profitYoYStatus,
          })}
          ${statementCardHtml('EPS', {
            kind: 'eps',
            period: f.latestQuarter,
            current: f.eps,
            prev: f.epsPrevQuarter,
            prevLabel: f.epsPrevQuarterLabel,
            yearAgo: f.epsYearAgo,
            yearAgoLabel: f.epsYearAgoLabel,
            estimate: f.estimatedEps,
            estimateStatus: f.estimatedEpsStatus,
            surprise: f.epsSurprisePct,
            qoq: f.epsQoQ,
            qoqStatus: f.epsQoQStatus,
            yoy: f.epsYoY,
            yoyStatus: f.epsYoYStatus,
          })}
        </div>
        <div class="fund-two-col fund-two-col-premium">
          <div class="insight-card">
            <h4>What stood out</h4>
            <ul>${highlights.map(x => `<li>${escapeHtml(x)}</li>`).join('') || '<li>Insufficient data</li>'}</ul>
          </div>
          <div class="insight-card">
            <h4>AI view</h4>
            <ul class="ai-view-list">${reasons.map(renderAiReasonItem).join('') || '<li>ข้อมูลพื้นฐานไม่พอ ยังไม่ควรสรุปเชิงพื้นฐาน</li>'}</ul>
          </div>
        </div>
      </div>`;

  const guidanceStats = f.guidanceParseStats || {};
  const guidanceHistoryRows = Array.isArray(f.guidanceHistory) ? f.guidanceHistory.slice(0, 8) : [];
  const guidanceDebugRows = Array.isArray(f.guidanceDebug) ? f.guidanceDebug.slice(0, 8) : [];
  const guidanceHistoryHtml = guidanceHistoryRows.length ? `
        <div class="insight-card" style="margin-top:16px;">
          <h4>Guidance History — medium/high confidence</h4>
          <div class="mini-table-wrap">
            <table class="mini-table">
              <thead><tr><th>Filed</th><th>Period</th><th>Mid</th><th>Range</th><th>Conf.</th><th>Source</th></tr></thead>
              <tbody>
                ${guidanceHistoryRows.map(g => `<tr>
                  <td>${escapeHtml(g.filedDate || '')}</td>
                  <td>${escapeHtml(g.period || 'N/A')}</td>
                  <td>${formatBig(g.midpoint)}</td>
                  <td>${formatBig(g.low)} - ${formatBig(g.high)}</td>
                  <td>${escapeHtml(g.confidence || 'N/A')}</td>
                  <td>${escapeHtml(g.sourceDocument || '')}</td>
                </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>` : '';
  const guidanceDebugHtml = guidanceDebugRows.length ? `
        <details class="debug-details">
          <summary>Guidance debug snippets (${guidanceStats.revenueMatches || guidanceDebugRows.length} raw revenue candidate${(guidanceStats.revenueMatches || guidanceDebugRows.length) === 1 ? '' : 's'})</summary>
          ${guidanceDebugRows.map(g => `<div class="debug-snippet">
            <div><strong>${escapeHtml(g.confidence || 'low')}</strong> · ${escapeHtml(g.period || 'N/A')} · ${formatBig(g.midpoint)} · ${escapeHtml(g.filedDate || '')} · ${escapeHtml(g.sourceDocument || '')}</div>
            <small>${escapeHtml(g.confidenceReason || '')}</small>
            <p>${escapeHtml((g.textSnippet || '').slice(0, 420))}</p>
          </div>`).join('')}
        </details>` : '';

  const guidancePanelHtml = `
      <section class="target-section fund-tab-panel">
        <div class="target-section-head">
          <div>
            <h4>Company Guidance View</h4>
            <p>ดึงจาก SEC 8-K/6-K / Exhibit 99.1 แบบ conservative parser — ไม่ใช่ analyst consensus</p>
          </div>
          <span class="mini-chip ${f.companyGuidanceConnected ? 'chip-good' : 'chip-muted'}">${escapeHtml(f.companyGuidanceConnected ? 'Guidance parsed' : 'No guidance found')}</span>
        </div>
        <div class="target-summary-grid">
          <div class="target-mini-card"><span>Prior Guide Period</span><strong>${escapeHtml(f.priorCompanyGuidanceRevenuePeriod || 'N/A')}</strong><small>${escapeHtml(f.priorCompanyGuidanceRevenueFiledDate || '')}</small></div>
          <div class="target-mini-card"><span>Prior Rev Guide Mid</span><strong>${formatBig(f.priorCompanyGuidanceRevenue)}</strong><small>${formatBig(f.priorCompanyGuidanceRevenueLow)} - ${formatBig(f.priorCompanyGuidanceRevenueHigh)}</small></div>
          <div class="target-mini-card"><span>Prior Guide Confidence</span><strong>${escapeHtml(f.priorCompanyGuidanceRevenueConfidence || 'N/A')}</strong><small>${escapeHtml(f.priorCompanyGuidanceRevenueConfidenceReason || '')}</small></div>
          <div class="target-mini-card"><span>Actual vs Prior Guide</span><strong class="${clsForPct(f.actualVsPriorGuidanceRevenuePct)}">${formatPct(f.actualVsPriorGuidanceRevenuePct)}</strong><small>${escapeHtml(f.actualVsPriorGuidanceRevenueStatus || 'N/A')}</small></div>
          <div class="target-mini-card"><span>Actual Used</span><strong>${formatBig(f.priorGuidanceRevenueActual)}</strong><small>${escapeHtml(f.priorGuidanceRevenueActualPeriod || 'N/A')}</small></div>
          <div class="target-mini-card"><span>Next Guide Period</span><strong>${escapeHtml(f.nextCompanyGuidanceRevenuePeriod || 'N/A')}</strong><small>${escapeHtml(f.nextCompanyGuidanceRevenueFiledDate || '')}</small></div>
          <div class="target-mini-card"><span>Next Rev Guide Mid</span><strong>${formatBig(f.nextCompanyGuidanceRevenue)}</strong><small>${formatBig(f.nextCompanyGuidanceRevenueLow)} - ${formatBig(f.nextCompanyGuidanceRevenueHigh)}</small></div>
          <div class="target-mini-card"><span>Next Guide Confidence</span><strong>${escapeHtml(f.nextCompanyGuidanceRevenueConfidence || 'N/A')}</strong><small>${escapeHtml(f.nextCompanyGuidanceRevenueConfidenceReason || '')}</small></div>
          <div class="target-mini-card"><span>Next EPS Guide Mid</span><strong>${formatNumber(f.nextCompanyGuidanceEps ?? f.companyGuidanceEps, 3)}</strong><small>${(f.nextCompanyGuidanceEpsLow != null || f.nextCompanyGuidanceEpsHigh != null) ? `${formatNumber(f.nextCompanyGuidanceEpsLow, 3)} - ${formatNumber(f.nextCompanyGuidanceEpsHigh, 3)}` : 'N/A'}</small></div>
        </div>
        <p class="detail-muted">${escapeHtml(f.companyGuidanceStatus || 'No company guidance parsed')}</p>
        <p class="detail-muted">Scanned ${guidanceStats.filingsScanned || 0} SEC 8-K/6-K filing(s), ${guidanceStats.documentsScanned || 0} exhibit/document(s), ${guidanceStats.revenueMatches || 0} raw revenue candidate(s). High/Medium/Low: ${guidanceStats.highConfidence || 0}/${guidanceStats.mediumConfidence || 0}/${guidanceStats.lowConfidence || 0}</p>
        ${f.priorCompanyGuidanceRevenueSourceDocument ? `<p class="detail-muted">Prior guide source: ${escapeHtml(f.priorCompanyGuidanceRevenueSourceDocument)}</p>` : ''}
        ${f.nextCompanyGuidanceRevenueSourceDocument ? `<p class="detail-muted">Next guide source: ${escapeHtml(f.nextCompanyGuidanceRevenueSourceDocument)}</p>` : ''}
        ${guidanceHistoryHtml}
        ${guidanceDebugHtml}
      </section>`;

  const analystPanelHtml = analystTargetSectionHtml(String(latest.symbol || '').toUpperCase(), currentPrice);
  const activePanelHtml = activeDetailTab === 'guidance' ? guidancePanelHtml : (activeDetailTab === 'analyst' ? analystPanelHtml : earningsPanelHtml);

  detail.innerHTML = `
    <div class="fund-card fund-card-premium">
      <div class="fund-head fund-head-premium">
        <div>
          <p class="fund-kicker">Fundamental Dashboard</p>
          <h3>${escapeHtml(latest.symbol || '')} dashboard</h3>
          <p>เลือกมุมมอง: Earnings Snapshot / Company Guidance View / Analyst Consensus</p>
        </div>
        <div class="fund-head-side">
          <span class="pill ${signalClass(f.fundamentalSignal || '')}">${escapeHtml(f.fundamentalSignal || 'Insufficient data')}</span>
          <small>Source: ${escapeHtml(f.fundamentalSource || 'N/A')}</small>
        </div>
      </div>

      <div class="fund-hero-grid">
        <div class="hero-mini-card"><span>Fundamental Score</span><strong>${f.fundamentalScore ?? 'N/A'}</strong><small>/100 rules-based</small></div>
        <div class="hero-mini-card"><span>Latest Quarter</span><strong>${escapeHtml(f.latestQuarter || 'N/A')}</strong><small>actual reported quarter</small></div>
        <div class="hero-mini-card"><span>Period End</span><strong>${escapeHtml(f.earningsDate || 'N/A')}</strong><small>SEC reported accounting period</small></div>
        <div class="hero-mini-card"><span>Active View</span><strong>${activeDetailTab === 'earnings' ? 'Earnings' : activeDetailTab === 'guidance' ? 'Guidance' : 'Analyst'}</strong><small>switch tabs below</small></div>
      </div>

      ${fundDetailTabsHtml(activeDetailTab)}

      <div class="fund-note-strip">
        <div class="note-pill note-info">SEC core fundamental remains the scoring source</div>
        <div class="note-pill note-info">Alpha Vantage only runs in Analyst Consensus tab after clicking Load</div>
      </div>

      ${activePanelHtml}
    </div>`;

  $$('.fund-detail-tab').forEach(btn => {
    btn.addEventListener('click', (event) => {
      event.stopPropagation();
      setFundDetailTab(btn.dataset.fundDetailTab);
    });
  });

  const saveKeyBtn = $('#saveAvKeyBtn');
  if (saveKeyBtn) {
    saveKeyBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      saveAlphaKeyFromInput();
    });
  }
  const clearKeyBtn = $('#clearAvKeyBtn');
  if (clearKeyBtn) {
    clearKeyBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      clearAlphaKey();
    });
  }
  const analystBtn = $('#loadAnalystBtn');
  if (analystBtn) {
    analystBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      loadAnalystConsensus(String(latest.symbol || '').toUpperCase(), currentPrice);
    });
  }
  if (activeDetailTab === 'analyst' && !state.alphaKeyFetched) {
    fetchAlphaKeyStatus().then(() => {
      if (state.currentDetail && (state.fundDetailTab || 'earnings') === 'analyst') {
        renderFundamentalDetail(state.currentDetail);
      }
    });
  }
}

function renderScoreBars(parts) {
  const max = { trend: 40, momentum: 30, rsi: 20, volume: 10 };
  const labels = { trend: 'Trend', momentum: 'Momentum', rsi: 'RSI', volume: 'Volume' };
  $('#scoreBars').innerHTML = Object.keys(max).map(k => {
    const value = Number(parts[k] || 0);
    const width = Math.max(0, Math.min(100, value / max[k] * 100));
    return `
      <div class="bar-row">
        <span>${labels[k]}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
        <strong>${value}/${max[k]}</strong>
      </div>`;
  }).join('');
}

function drawChart(series, symbol) {
  const canvas = $('#priceChart');
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const isMobile = window.innerWidth < 620;
  const w = Math.max(330, rect.width || canvas.clientWidth || 330);

  const points = series.slice(-260);
  if (!points.length) {
    const fallbackH = isMobile ? 880 : 820;
    canvas.width = w * dpr;
    canvas.height = fallbackH * dpr;
    canvas.style.height = `${fallbackH}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, fallbackH);
    return;
  }

  const pricePanel = { x: 54, y: 24, w: w - 76, h: isMobile ? 230 : 260 };
  const rsiPanel = { x: 54, y: pricePanel.y + pricePanel.h + 34, w: w - 76, h: 110 };
  const macdPanel = { x: 54, y: rsiPanel.y + rsiPanel.h + 34, w: w - 76, h: isMobile ? 140 : 150 };
  const volPanel = { x: 54, y: macdPanel.y + macdPanel.h + 34, w: w - 76, h: isMobile ? 125 : 115 };
  const h = volPanel.y + volPanel.h + 42;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.height = `${h}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const dateLabel = (dateText) => {
    if (!dateText) return '';
    const parts = String(dateText).split('-');
    if (parts.length !== 3) return String(dateText);
    return `${parts[2]}/${parts[1]}/${parts[0].slice(2)}`;
  };
  const x = (i) => pricePanel.x + (i / Math.max(1, points.length - 1)) * pricePanel.w;
  const drawPanelBg = (panel, title) => {
    ctx.save();
    ctx.fillStyle = 'rgba(8,15,40,.32)';
    ctx.strokeStyle = 'rgba(255,255,255,.10)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    const rx = panel.x - 42;
    const ry = panel.y - 18;
    const rw = panel.w + 54;
    const rh = panel.h + 28;
    if (typeof ctx.roundRect === 'function') {
      ctx.roundRect(rx, ry, rw, rh, 14);
    } else {
      ctx.rect(rx, ry, rw, rh);
    }
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = 'rgba(248,251,255,.80)';
    ctx.font = 'bold 13px system-ui';
    ctx.fillText(title, panel.x - 36, panel.y - 1);
    ctx.restore();
  };

  const drawHorizontalGrid = (panel, ticks = 4) => {
    ctx.strokeStyle = 'rgba(255,255,255,.10)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= ticks; i++) {
      const yy = panel.y + (i / ticks) * panel.h;
      ctx.beginPath();
      ctx.moveTo(panel.x, yy);
      ctx.lineTo(panel.x + panel.w, yy);
      ctx.stroke();
    }
  };

  const drawDateAxis = () => {
    ctx.fillStyle = 'rgba(248,251,255,.78)';
    ctx.font = isMobile ? '10px system-ui' : '11px system-ui';
    ctx.textAlign = 'center';
    const dateTicks = isMobile ? 3 : 5;
    for (let i = 0; i < dateTicks; i++) {
      const idx = Math.round((i / Math.max(1, dateTicks - 1)) * (points.length - 1));
      const xx = x(idx);
      ctx.fillText(dateLabel(points[idx]?.date), xx, volPanel.y + volPanel.h + 26);
    }
    ctx.textAlign = 'left';
  };

  const line = (panel, key, yScale, color, width = 1.6, dash = []) => {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.setLineDash(dash);
    ctx.beginPath();
    let started = false;
    points.forEach((p, i) => {
      const value = p[key];
      if (value === null || value === undefined || Number.isNaN(Number(value))) return;
      if (!started) {
        ctx.moveTo(x(i), yScale(Number(value)));
        started = true;
      } else {
        ctx.lineTo(x(i), yScale(Number(value)));
      }
    });
    ctx.stroke();
    ctx.restore();
  };

  // PRICE + EMA PANEL
  drawPanelBg(pricePanel, `${symbol} Price / EMA`);
  drawHorizontalGrid(pricePanel, 4);
  const priceKeys = ['close', 'ema5', 'ema20', 'ema89', 'ema200'];
  const priceValues = points.flatMap(p => priceKeys.map(k => p[k]).filter(v => v !== null && v !== undefined));
  if (priceValues.length) {
    const minPrice = Math.min(...priceValues) * 0.98;
    const maxPrice = Math.max(...priceValues) * 1.02;
    const yPrice = (v) => pricePanel.y + (maxPrice - v) / (maxPrice - minPrice || 1) * pricePanel.h;
    ctx.fillStyle = 'rgba(234,240,255,.76)';
    ctx.font = '11px system-ui';
    for (let i = 0; i <= 4; i++) {
      const price = maxPrice - i / 4 * (maxPrice - minPrice);
      const yy = pricePanel.y + i / 4 * pricePanel.h;
      ctx.fillText(formatNumber(price), 8, yy + 4);
    }
    line(pricePanel, 'close', yPrice, '#f8fbff', 2.2);
    line(pricePanel, 'ema5', yPrice, '#22c55e', 1.5);
    line(pricePanel, 'ema20', yPrice, '#38bdf8', 1.5);
    line(pricePanel, 'ema89', yPrice, '#f59e0b', 1.3, [4, 4]);
    line(pricePanel, 'ema200', yPrice, '#f43f5e', 1.3, [6, 5]);

    const legend = [
      ['Close', '#f8fbff'], ['EMA5', '#22c55e'], ['EMA20', '#38bdf8'], ['EMA89', '#f59e0b'], ['EMA200', '#f43f5e']
    ];
    let lx = pricePanel.x;
    legend.forEach(([name, color]) => {
      if (lx > w - 86) return;
      ctx.fillStyle = color;
      ctx.fillRect(lx, pricePanel.y + pricePanel.h + 9, 10, 10);
      ctx.fillStyle = 'rgba(248,251,255,.86)';
      ctx.fillText(name, lx + 14, pricePanel.y + pricePanel.h + 18);
      lx += 72;
    });
  }

  // RSI PANEL
  drawPanelBg(rsiPanel, 'RSI(14)');
  drawHorizontalGrid(rsiPanel, 2);
  const yRsi = (v) => rsiPanel.y + (100 - v) / 100 * rsiPanel.h;
  [70, 50, 30].forEach(level => {
    ctx.strokeStyle = level === 50 ? 'rgba(255,255,255,.18)' : 'rgba(251,191,36,.22)';
    ctx.setLineDash(level === 50 ? [] : [5, 5]);
    ctx.beginPath();
    ctx.moveTo(rsiPanel.x, yRsi(level));
    ctx.lineTo(rsiPanel.x + rsiPanel.w, yRsi(level));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(248,251,255,.65)';
    ctx.font = '10px system-ui';
    ctx.fillText(String(level), 22, yRsi(level) + 3);
  });
  line(rsiPanel, 'rsi14', yRsi, '#0ea5e9', 2.0);
  const latest = points[points.length - 1] || {};
  ctx.fillStyle = '#0ea5e9';
  ctx.font = 'bold 13px system-ui';
  ctx.fillText(`RSI14: ${formatNumber(latest.rsi14, 2)}`, rsiPanel.x + 72, rsiPanel.y - 1);

  // MACD PANEL
  drawPanelBg(macdPanel, 'MACD(12,26,9)');
  drawHorizontalGrid(macdPanel, 2);
  const macdValues = points.flatMap(p => ['macd1226', 'macdSignal9', 'macdHist'].map(k => p[k]).filter(v => v !== null && v !== undefined));
  if (macdValues.length) {
    const absMax = Math.max(0.001, ...macdValues.map(v => Math.abs(Number(v))));
    const yMacd = (v) => macdPanel.y + (absMax - v) / (absMax * 2 || 1) * macdPanel.h;
    const zeroY = yMacd(0);
    ctx.strokeStyle = 'rgba(255,255,255,.24)';
    ctx.beginPath();
    ctx.moveTo(macdPanel.x, zeroY);
    ctx.lineTo(macdPanel.x + macdPanel.w, zeroY);
    ctx.stroke();

    const barW = Math.max(1, Math.min(8, macdPanel.w / points.length * 0.72));
    points.forEach((p, i) => {
      const hist = p.macdHist;
      if (hist === null || hist === undefined || Number.isNaN(Number(hist))) return;
      const xx = x(i) - barW / 2;
      const yy = yMacd(Number(hist));
      ctx.fillStyle = Number(hist) >= 0 ? 'rgba(20,184,166,.95)' : 'rgba(244,63,94,.95)';
      ctx.fillRect(xx, Math.min(yy, zeroY), barW, Math.max(1, Math.abs(zeroY - yy)));
    });

    line(macdPanel, 'macd1226', yMacd, '#0ea5e9', 2.0);
    line(macdPanel, 'macdSignal9', yMacd, '#f97316', 1.8);
    ctx.fillStyle = '#0ea5e9';
    ctx.font = 'bold 13px system-ui';
    ctx.fillText(`MACD: ${formatNumber(latest.macd1226, 3)}`, macdPanel.x + 112, macdPanel.y - 1);
    ctx.fillStyle = '#f97316';
    ctx.fillText(`Signal: ${formatNumber(latest.macdSignal9, 3)}`, macdPanel.x + 224, macdPanel.y - 1);
    ctx.fillStyle = '#d946ef';
    ctx.fillText(`Hist: ${formatNumber(latest.macdHist, 3)}`, macdPanel.x + 350, macdPanel.y - 1);
  }

  // VOLUME PANEL with VMA5/VMA10 calculated client-side
  drawPanelBg(volPanel, 'VOL(5,10)');
  drawHorizontalGrid(volPanel, 2);
  const volumes = points.map(p => Number(p.volume || 0));
  const maxVol = Math.max(1, ...volumes);
  const yVol = (v) => volPanel.y + (maxVol - v) / maxVol * volPanel.h;
  const smaClient = (arr, period) => arr.map((_, i) => {
    const start = Math.max(0, i - period + 1);
    const slice = arr.slice(start, i + 1).filter(v => Number.isFinite(v));
    if (slice.length < period) return null;
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });
  const vma5 = smaClient(volumes, 5);
  const vma10 = smaClient(volumes, 10);
  const barW = Math.max(1, Math.min(8, volPanel.w / points.length * 0.72));
  points.forEach((p, i) => {
    const vol = Number(p.volume || 0);
    const prevClose = i > 0 ? Number(points[i - 1].close || 0) : Number(p.open || p.close || 0);
    const up = Number(p.close || 0) >= prevClose;
    ctx.fillStyle = up ? 'rgba(20,184,166,.95)' : 'rgba(244,63,94,.95)';
    const yy = yVol(vol);
    ctx.fillRect(x(i) - barW / 2, yy, barW, Math.max(1, volPanel.y + volPanel.h - yy));
  });
  const yVolLine = (v) => yVol(v);
  const drawArrayLine = (values, color) => {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    let started = false;
    values.forEach((value, i) => {
      if (value === null || value === undefined) return;
      if (!started) { ctx.moveTo(x(i), yVolLine(value)); started = true; }
      else ctx.lineTo(x(i), yVolLine(value));
    });
    ctx.stroke();
    ctx.restore();
  };
  drawArrayLine(vma5, '#0ea5e9');
  drawArrayLine(vma10, '#f97316');
  ctx.fillStyle = '#0ea5e9';
  ctx.font = 'bold 13px system-ui';
  ctx.fillText(`VMA5: ${formatNumber(vma5[vma5.length - 1], 0)}`, volPanel.x + 82, volPanel.y - 1);
  ctx.fillStyle = '#f97316';
  ctx.fillText(`VMA10: ${formatNumber(vma10[vma10.length - 1], 0)}`, volPanel.x + 218, volPanel.y - 1);

  drawDateAxis();
}

function updateTabs() {
  $$('.tab-button').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === state.activeTab));
  const note = $('#tabNote');
  if (note) note.textContent = state.activeTab === 'fundamental'
    ? 'Fundamental tab ใช้ SEC EDGAR static layer • Technical refresh จาก GitHub Actions ทุก ~15 นาที • Analyst Consensus ใช้ Alpha Vantage BYOK กดดึงทีละหุ้น'
    : 'Technical indicators จาก workflow ล่าสุด';
}

function switchTab(tab) {
  state.activeTab = tab;
  state.sortKey = tab === 'fundamental' ? 'fundamentalScore' : 'score';
  state.sortDir = 'desc';
  updateTabs();
  renderColumnToggles();
  applyFilters();
  saveActiveSettings();
}

function setupEventListeners() {
  $('#scanBtn').addEventListener('click', scan);
  $('#refreshBtn').addEventListener('click', () => scan(true));
  $('#loadSingleBtn').addEventListener('click', () => loadSymbol($('#singleSymbol').value.trim().toUpperCase()));
  $('#singleSymbol').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') loadSymbol($('#singleSymbol').value.trim().toUpperCase());
  });

  ['symbols', 'range', 'minScore', 'filterAbove200', 'filterEmaStack', 'filterSweetRsi'].forEach(id => {
    const el = $(`#${id}`);
    el.addEventListener('input', () => { saveActiveSettings(); if (id !== 'symbols' && id !== 'range') applyFilters(); });
    el.addEventListener('change', () => { saveActiveSettings(); if (id !== 'symbols' && id !== 'range') applyFilters(); });
  });

  $$('.tab-button').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));

  $('#saveScreenerBtn').addEventListener('click', saveNamedScreener);
  $('#loadScreenerBtn').addEventListener('click', loadNamedScreener);
  $('#deleteScreenerBtn').addEventListener('click', deleteNamedScreener);
  $('#savedScreeners').addEventListener('change', () => {
    const selected = $('#savedScreeners').value;
    if (selected) $('#screenerName').value = selected;
  });

  $('#showAllColsBtn').addEventListener('click', () => setColumns(Object.fromEntries(columnDefs.map(c => [c.key, true]))));
  $('#compactColsBtn').addEventListener('click', () => setColumns(compactColumns));
  $('#emaFocusColsBtn').addEventListener('click', () => setColumns(emaFocusColumns));

  window.addEventListener('resize', () => {
    renderMobileCards(state.filteredRows);
    const symbol = $('#singleSymbol').value.trim().toUpperCase();
    if (symbol) drawChart.__resizeTimer = clearTimeout(drawChart.__resizeTimer) || setTimeout(() => loadSymbol(symbol, false), 150);
  });
}

function init() {
  updateSavedScreenersDropdown();
  updateTabs();
  renderColumnToggles();
  renderTableHeader();
  setupEventListeners();
  const restored = restoreActiveSettings();
  if (!restored) {
    renderColumnToggles();
    renderTableHeader();
  }
  scan();
}

init();
