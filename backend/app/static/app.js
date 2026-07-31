const API = "";
const TOKEN_KEY = "aktien_token";
const USERNAME_KEY = "aktien_username";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setSession(token, username) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USERNAME_KEY, username);
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}), Authorization: `Bearer ${token}` };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearSession();
    showLoginScreen();
    throw new Error("Sitzung abgelaufen - bitte erneut anmelden");
  }
  return res;
}

function showApp(username) {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  document.getElementById("current-username").textContent = `angemeldet als ${username}`;
  loadWatchlist();
}

function showLoginScreen() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
}

document.getElementById("tab-login").addEventListener("click", () => {
  document.getElementById("tab-login").classList.add("tab-active");
  document.getElementById("tab-register").classList.remove("tab-active");
  document.getElementById("login-form").classList.remove("hidden");
  document.getElementById("register-form").classList.add("hidden");
});

document.getElementById("tab-register").addEventListener("click", () => {
  document.getElementById("tab-register").classList.add("tab-active");
  document.getElementById("tab-login").classList.remove("tab-active");
  document.getElementById("register-form").classList.remove("hidden");
  document.getElementById("login-form").classList.add("hidden");
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    setSession(data.access_token, data.username);
    showApp(data.username);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("register-username").value.trim();
  const password = document.getElementById("register-password").value;
  const errorEl = document.getElementById("register-error");
  errorEl.textContent = "";

  try {
    const res = await fetch(`${API}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    setSession(data.access_token, data.username);
    showApp(data.username);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  clearSession();
  showLoginScreen();
});

document.getElementById("show-delete-btn").addEventListener("click", () => {
  document.getElementById("delete-account-form").classList.toggle("hidden");
});

document.getElementById("delete-account-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = document.getElementById("delete-password").value;
  const errorEl = document.getElementById("delete-error");
  errorEl.textContent = "";

  if (!confirm("Wirklich endgültig löschen? Das kann nicht rückgängig gemacht werden.")) return;

  try {
    const res = await authFetch(`${API}/auth/delete-account`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok && res.status !== 204) {
      const data = await res.json();
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    clearSession();
    alert("Konto wurde gelöscht.");
    showLoginScreen();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

function badgeClass(recommendation) {
  return `badge badge-${recommendation}`;
}

function getTendencyLabel(recommendation, expectedReturnPct) {
  if (recommendation !== "halten" || expectedReturnPct == null) return "";
  const TENDENCY_THRESHOLD = 1.5;
  if (expectedReturnPct > TENDENCY_THRESHOLD) {
    return '<span class="tendency tendency-buy">Tendenz: Kaufen</span>';
  }
  if (expectedReturnPct < -TENDENCY_THRESHOLD) {
    return '<span class="tendency tendency-sell">Tendenz: Verkaufen</span>';
  }
  return "";
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

function formatDateOnly(isoDate) {
  if (!isoDate) return isoDate;
  const [year, month, day] = isoDate.split("-");
  if (!year || !month || !day) return isoDate;
  return `${day}.${month}.${year}`;
}

let currentWatchlistItems = [];
let activeSectorFilters = new Set();
let watchlistSearchQuery = "";

async function loadWatchlist() {
  const container = document.getElementById("watchlist-container");
  container.innerHTML = '<p class="hint">Lade Watchlist ...</p>';

  try {
    const res = await authFetch(`${API}/watchlist/overview`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    currentWatchlistItems = await res.json();
    renderSectorFilterButtons();
    renderSortedWatchlist();
  } catch (err) {
    container.innerHTML = `<p class="error-text">Fehler beim Laden: ${err.message}</p>`;
  }
}

function renderSectorFilterButtons() {
  const container = document.getElementById("sector-filter-container");
  const sectors = [...new Set(currentWatchlistItems.map((i) => i.sector).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "de")
  );

  if (sectors.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = sectors
    .map((sector) => {
      const active = activeSectorFilters.has(sector) ? "sector-filter-active" : "";
      return `<button type="button" class="sector-filter-btn ${active}" data-sector="${escapeHtml(sector)}">${escapeHtml(translateSector(sector))}</button>`;
    })
    .join("");

  container.querySelectorAll(".sector-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sector = btn.dataset.sector;
      if (activeSectorFilters.has(sector)) {
        activeSectorFilters.delete(sector);
      } else {
        activeSectorFilters.add(sector);
      }
      renderSectorFilterButtons();
      renderSortedWatchlist();
    });
  });
}

const SECTOR_TRANSLATIONS = {
  "Technology": "Technologie",
  "Consumer Cyclical": "Zyklische Konsumgüter",
  "Consumer Defensive": "Defensive Konsumgüter",
  "Energy": "Energie",
  "Financial Services": "Finanzdienstleistungen",
  "Healthcare": "Gesundheitswesen",
  "Industrials": "Industrie",
  "Utilities": "Versorger",
  "Communication Services": "Kommunikationsdienste",
  "Real Estate": "Immobilien",
  "Basic Materials": "Grundstoffe",
};

function translateSector(sector) {
  return SECTOR_TRANSLATIONS[sector] || sector;
}

document.getElementById("watchlist-search").addEventListener("input", (e) => {
  watchlistSearchQuery = e.target.value.trim().toLowerCase();
  renderSortedWatchlist();
});

function filterWatchlistItems(items) {
  return items.filter((item) => {
    if (activeSectorFilters.size > 0 && !activeSectorFilters.has(item.sector)) {
      return false;
    }
    if (watchlistSearchQuery) {
      const haystack = `${item.name || ""} ${item.ticker} ${item.symbol || ""}`.toLowerCase();
      if (!haystack.includes(watchlistSearchQuery)) return false;
    }
    return true;
  });
}

function sortWatchlistItems(items, sortKey) {
  const sorted = [...items];
  const val = (item, field) => (item.latest_score ? item.latest_score[field] : null);
  const cmp = (a, b, field, ascending) => {
    const va = val(a, field);
    const vb = val(b, field);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    return ascending ? va - vb : vb - va;
  };

  switch (sortKey) {
    case "recommendation": {
      const rank = { kaufen: 0, halten: 1, verkaufen: 2 };
      sorted.sort((a, b) => {
        const ra = a.latest_score ? rank[a.latest_score.recommendation] : 3;
        const rb = b.latest_score ? rank[b.latest_score.recommendation] : 3;
        return ra - rb;
      });
      break;
    }
    case "kgv":
      sorted.sort((a, b) => cmp(a, b, "trailing_pe", true));
      break;
    case "rsi":
      sorted.sort((a, b) => cmp(a, b, "rsi", true));
      break;
    case "sma": {
      const smaGap = (item) => {
        const s = item.latest_score;
        if (!s || s.sma50 == null || s.current_price == null || s.sma50 === 0) return null;
        return (s.current_price - s.sma50) / s.sma50;
      };
      sorted.sort((a, b) => {
        const ga = smaGap(a);
        const gb = smaGap(b);
        if (ga == null && gb == null) return 0;
        if (ga == null) return 1;
        if (gb == null) return -1;
        return gb - ga;
      });
      break;
    }
    case "risk_high":
      sorted.sort((a, b) => cmp(a, b, "risk_score", false));
      break;
    case "risk_low":
      sorted.sort((a, b) => cmp(a, b, "risk_score", true));
      break;
    case "return_high":
      sorted.sort((a, b) => cmp(a, b, "expected_return_pct", false));
      break;
    case "return_low":
      sorted.sort((a, b) => cmp(a, b, "expected_return_pct", true));
      break;
    case "name":
    default:
      sorted.sort((a, b) => (a.name || a.ticker).localeCompare(b.name || b.ticker, "de"));
      break;
  }
  return sorted;
}

function renderSortedWatchlist() {
  const container = document.getElementById("watchlist-container");

  if (currentWatchlistItems.length === 0) {
    container.innerHTML = '<p class="hint">Noch keine Aktien auf deiner Watchlist.</p>';
    return;
  }

  const filtered = filterWatchlistItems(currentWatchlistItems);

  if (filtered.length === 0) {
    container.innerHTML = '<p class="hint">Keine Treffer für die aktuelle Filter-/Sucheinstellung.</p>';
    return;
  }

  const sortKey = document.getElementById("sort-select").value;
  const sorted = sortWatchlistItems(filtered, sortKey);

  container.innerHTML = "";
  for (const item of sorted) {
    container.appendChild(renderWatchlistItem(item));
  }
}

document.getElementById("sort-select").addEventListener("change", renderSortedWatchlist);

function renderWatchlistItem(item) {
  const div = document.createElement("div");
  div.className = "watchlist-item";

  let scoreHtml = '<p class="hint">Noch nicht bewertet - "Jetzt scannen" klicken.</p>';
  if (item.latest_score) {
    const s = item.latest_score;
    scoreHtml = `
      <div class="score-line">
        <span class="${badgeClass(s.recommendation)}">${s.recommendation}</span>
        ${getTendencyLabel(s.recommendation, s.expected_return_pct)}
        <span>Erw. Rendite: <strong>${s.expected_return_pct}%</strong></span>
        <span>Risiko: <strong>${s.risk_score}</strong></span>
        <span class="hint">${formatDate(s.created_at)}</span>
      </div>
      <div class="reasoning-text">${escapeHtml(s.reasoning) || ""}</div>
    `;
  }

  const primaryLabel = item.name ? escapeHtml(item.name) : escapeHtml(item.ticker);
  const secondaryLabel = item.name ? `<span class="ticker-code">${escapeHtml(item.ticker)}</span>` : "";

  const metaTags = [];
  if (item.sector) metaTags.push(`<span class="sector-tag">${escapeHtml(translateSector(item.sector))}</span>`);
  if (item.symbol) metaTags.push(`<span class="symbol-tag">${escapeHtml(item.symbol)}${item.exchange ? " · " + escapeHtml(item.exchange) : ""}</span>`);
  if (item.price_target) metaTags.push(`<span class="target-tag">🎯 Ziel: ${item.price_target}</span>`);
  const metaHtml = metaTags.length ? `<div class="watchlist-item-meta">${metaTags.join(" ")}</div>` : "";

  let portfolioHtml = "";
  if (item.gain_loss) {
    const gl = item.gain_loss;
    const glClass = gl.gain_loss_abs >= 0 ? "gain-positive" : "gain-negative";
    portfolioHtml = `
      <div class="portfolio-line">
        <span>Investiert: <strong>${gl.invested}</strong></span>
        <span>Wert: <strong>${gl.current_value}</strong></span>
        <span class="${glClass}">G/V: <strong>${gl.gain_loss_abs} (${gl.gain_loss_pct}%)</strong></span>
      </div>
    `;
  }

  div.innerHTML = `
    <div class="watchlist-item-main">
      <div class="ticker-name ticker-clickable">${primaryLabel} ${secondaryLabel}</div>
      ${metaHtml}
      ${portfolioHtml}
      ${item.notes ? `<div class="ticker-notes">${escapeHtml(item.notes)}</div>` : ""}
      ${scoreHtml}
      <button class="edit-btn" type="button">✏️ Bearbeiten</button>
      <div class="edit-panel hidden">
        <textarea class="edit-notes-input" placeholder="Notizen">${escapeHtml(item.notes || "")}</textarea>
        <div class="edit-row">
          <input type="number" class="edit-purchase-price-input" placeholder="Kaufpreis" step="0.01" min="0" value="${item.purchase_price ?? ""}" />
          <input type="number" class="edit-quantity-input" placeholder="Stückzahl" step="0.0001" min="0" value="${item.quantity ?? ""}" />
          <input type="number" class="edit-price-target-input" placeholder="Kursziel" step="0.01" min="0" value="${item.price_target ?? ""}" />
        </div>
        <button class="save-edit-btn" type="button">Speichern</button>
      </div>
    </div>
    <button class="delete-btn" data-ticker="${escapeHtml(item.ticker)}">Entfernen</button>
  `;

  div.querySelector(".ticker-clickable").addEventListener("click", () => openDetailModal(item.ticker));
  div.querySelector(".delete-btn").addEventListener("click", () => removeTicker(item.ticker));

  const editBtn = div.querySelector(".edit-btn");
  const editPanel = div.querySelector(".edit-panel");
  editBtn.addEventListener("click", () => editPanel.classList.toggle("hidden"));

  div.querySelector(".save-edit-btn").addEventListener("click", async () => {
    const notes = div.querySelector(".edit-notes-input").value.trim();
    const purchasePrice = div.querySelector(".edit-purchase-price-input").value;
    const quantity = div.querySelector(".edit-quantity-input").value;
    const priceTarget = div.querySelector(".edit-price-target-input").value;

    const body = {
      notes: notes || null,
      purchase_price: purchasePrice ? parseFloat(purchasePrice) : null,
      quantity: quantity ? parseFloat(quantity) : null,
      price_target: priceTarget ? parseFloat(priceTarget) : null,
    };

    try {
      const res = await authFetch(`${API}/watchlist/${encodeURIComponent(item.ticker)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadWatchlist();
    } catch (err) {
      alert(`Fehler beim Speichern: ${err.message}`);
    }
  });

  return div;
}

document.getElementById("toggle-bulk-add").addEventListener("click", () => {
  document.getElementById("bulk-add-panel").classList.toggle("hidden");
});

document.getElementById("bulk-add-btn").addEventListener("click", async () => {
  const textarea = document.getElementById("bulk-add-textarea");
  const resultEl = document.getElementById("bulk-add-result");
  const raw = textarea.value.trim();
  if (!raw) return;

  const tickers = raw.split(/[\n,]+/).map((t) => t.trim()).filter(Boolean);
  resultEl.innerHTML = '<p class="hint">Füge hinzu ...</p>';

  try {
    const res = await authFetch(`${API}/watchlist/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    resultEl.innerHTML = data.results.map((r) => {
      const icon = r.status === "hinzugefuegt" ? "✅" : r.status === "bereits_vorhanden" ? "⚠️" : "❌";
      return `<div class="hint">${icon} ${escapeHtml(r.ticker)}: ${escapeHtml(r.status)}${r.detail ? " - " + escapeHtml(r.detail) : ""}</div>`;
    }).join("");

    textarea.value = "";
    await loadWatchlist();
  } catch (err) {
    resultEl.innerHTML = `<p class="error-text">${err.message}</p>`;
  }
});

document.getElementById("export-btn").addEventListener("click", async () => {
  try {
    const res = await authFetch(`${API}/watchlist/export`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "watchlist.csv";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Export fehlgeschlagen: ${err.message}`);
  }
});

let currentDetailTicker = null;

const CHART_PERIODS = ["1d", "5d", "1mo", "6mo", "ytd", "1y", "5y"];
const CHART_PERIOD_LABELS = { "1d": "1D", "5d": "5D", "1mo": "1M", "6mo": "6M", "ytd": "YTD", "1y": "1Y", "5y": "5Y" };

function renderPeriodButtons(activePeriod) {
  return CHART_PERIODS.map((p) => `
    <button class="period-btn ${p === activePeriod ? "period-active" : ""}" data-period="${p}">${CHART_PERIOD_LABELS[p]}</button>
  `).join("");
}

function renderSparklineSvg(history) {
  if (!history || history.length < 2) {
    return '<p class="hint">Kein Kursverlauf verfügbar.</p>';
  }
  const width = 600;
  const height = 180;
  const padding = 34;
  const closes = history.map((h) => h.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;

  const points = history.map((h, i) => {
    const x = padding + (i / (history.length - 1)) * (width - padding - 10);
    const y = 14 + (1 - (h.close - min) / range) * (height - 40);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const first = history[0];
  const last = history[history.length - 1];
  const trendUp = last.close >= first.close;
  const strokeColor = trendUp ? "#3ecf8e" : "#f0654f";

  return `
    <div class="chart-wrapper">
      <svg viewBox="0 0 ${width} ${height}" class="price-chart" preserveAspectRatio="none">
        <text x="4" y="16" class="chart-price-label">${max}</text>
        <text x="4" y="${height - 6}" class="chart-price-label">${min}</text>
        <line class="chart-hover-line hidden" x1="0" y1="0" x2="0" y2="${height}"></line>
        <circle class="chart-hover-dot hidden" r="4"></circle>
        <polyline points="${points}" fill="none" stroke="${strokeColor}" stroke-width="2" />
      </svg>
      <div class="chart-tooltip hidden"></div>
    </div>
    <div class="chart-range">
      <span>${first.date}: ${first.close}</span>
      <span>${last.date}: ${last.close}</span>
    </div>
  `;
}

function attachChartHover(history) {
  const wrapper = document.querySelector("#chart-container .chart-wrapper");
  if (!wrapper || !history || history.length < 2) return;

  const svg = wrapper.querySelector("svg");
  const tooltip = wrapper.querySelector(".chart-tooltip");
  const hoverLine = wrapper.querySelector(".chart-hover-line");
  const hoverDot = wrapper.querySelector(".chart-hover-dot");

  const width = 600;
  const height = 180;
  const padding = 34;
  const closes = history.map((h) => h.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;

  function pointAt(index) {
    const x = padding + (index / (history.length - 1)) * (width - padding - 10);
    const y = 14 + (1 - (history[index].close - min) / range) * (height - 40);
    return { x, y };
  }

  svg.addEventListener("mousemove", (e) => {
    const rect = svg.getBoundingClientRect();
    const relX = ((e.clientX - rect.left) / rect.width) * width;
    const ratio = Math.max(0, Math.min(1, (relX - padding) / (width - padding - 10)));
    const index = Math.round(ratio * (history.length - 1));
    const point = history[index];
    const { x, y } = pointAt(index);

    hoverLine.setAttribute("x1", x);
    hoverLine.setAttribute("x2", x);
    hoverLine.classList.remove("hidden");
    hoverDot.setAttribute("cx", x);
    hoverDot.setAttribute("cy", y);
    hoverDot.classList.remove("hidden");

    tooltip.textContent = `${point.date}: ${point.close}`;
    tooltip.classList.remove("hidden");
    const wrapperRect = wrapper.getBoundingClientRect();
    const pxX = (x / width) * wrapperRect.width;
    tooltip.style.left = `${Math.min(Math.max(pxX, 40), wrapperRect.width - 40)}px`;
  });

  svg.addEventListener("mouseleave", () => {
    hoverLine.classList.add("hidden");
    hoverDot.classList.add("hidden");
    tooltip.classList.add("hidden");
  });
}

async function loadChart(ticker, period) {
  const container = document.getElementById("chart-container");
  container.innerHTML = '<p class="hint">Lade Chart ...</p>';

  document.querySelectorAll(".period-btn").forEach((btn) => {
    btn.classList.toggle("period-active", btn.dataset.period === period);
  });

  try {
    const res = await fetch(`${API}/stocks/${encodeURIComponent(ticker)}/chart?period=${period}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    container.innerHTML = renderSparklineSvg(data.price_history);
    attachChartHover(data.price_history);
  } catch (err) {
    container.innerHTML = `<p class="error-text">${err.message}</p>`;
  }
}

document.getElementById("detail-modal-body").addEventListener("click", (e) => {
  if (e.target.classList.contains("period-btn") && currentDetailTicker) {
    loadChart(currentDetailTicker, e.target.dataset.period);
  }
});

async function openDetailModal(ticker) {
  currentDetailTicker = ticker;
  const overlay = document.getElementById("detail-modal-overlay");
  const title = document.getElementById("detail-modal-title");
  const body = document.getElementById("detail-modal-body");

  title.textContent = ticker;
  body.innerHTML = '<p class="hint">Lade Details ...</p>';
  overlay.classList.remove("hidden");

  try {
    const res = await fetch(`${API}/stocks/${encodeURIComponent(ticker)}/details`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    const symbolInfo = data.symbol ? ` · ${data.symbol}${data.exchange ? " (" + data.exchange + ")" : ""}` : "";
    title.textContent = data.name ? `${data.name} (${data.ticker})${symbolInfo}` : data.ticker;

    const earningsHtml = data.next_earnings
      ? `📅 Quartalszahlen am <strong>${formatDateOnly(data.next_earnings.date)}</strong> (in ${data.next_earnings.days} Tagen)`
      : "Kein bekannter Termin in den nächsten 90 Tagen.";

    const dividendHtml = data.dividend_yield
      ? `Dividendenrendite: <strong>${data.dividend_yield.toFixed(2)}%</strong>${data.ex_dividend_date ? ` · nächster Ex-Dividenden-Tag: <strong>${formatDateOnly(data.ex_dividend_date)}</strong>` : ""}`
      : "Keine Dividendendaten verfügbar.";

    body.innerHTML = `
      <div class="score-line">
        <span class="${badgeClass(data.recommendation)}">${data.recommendation}</span>
        ${getTendencyLabel(data.recommendation, data.expected_return_pct)}
        <span>Erw. Rendite: <strong>${data.expected_return_pct}%</strong></span>
        <span>Risiko: <strong>${data.risk_score}</strong></span>
      </div>

      <h3>Über das Unternehmen</h3>
      <p>${escapeHtml(data.business_summary) || "Keine Beschreibung verfügbar."}</p>

      <h3>Nächster Termin</h3>
      <p>${earningsHtml}</p>
      <p class="hint">News &amp; Termin-Info Stand: ${formatDate(data.as_of)} (aus dem letzten automatischen Scan)</p>

      <h3>Dividende</h3>
      <p>${dividendHtml}</p>

      <h3>Kursverlauf</h3>
      <div class="period-selector">${renderPeriodButtons("6mo")}</div>
      <div id="chart-container">${renderSparklineSvg(data.price_history)}</div>

      <h3>Warum dieser Trend?</h3>
      <p>${escapeHtml(data.trend_explanation)}</p>

      <h3>Warum dieses KGV-Signal?</h3>
      <p>${escapeHtml(data.kgv_explanation)}</p>

      <h3>Warum dieses Risiko?</h3>
      <p>${escapeHtml(data.risk_explanation)}</p>

      <h3>Aktuelle News</h3>
      <p>
        <a href="${escapeHtml(data.yahoo_news_url)}" target="_blank" rel="noopener noreferrer" class="btn-secondary" style="display: inline-block; text-decoration: none;">
          Aktien-News auf Yahoo Finance ansehen ↗
        </a>
      </p>

      <p style="margin-top: 16px;">
        <a href="${escapeHtml(data.yahoo_finance_url)}" target="_blank" rel="noopener noreferrer" class="btn-secondary" style="display: inline-block; text-decoration: none;">
          Auf Yahoo Finance ansehen ↗
        </a>
      </p>
    `;
    attachChartHover(data.price_history);
  } catch (err) {
    body.innerHTML = `<p class="error-text">Fehler: ${err.message}</p>`;
  }
}

document.getElementById("detail-modal-close").addEventListener("click", () => {
  document.getElementById("detail-modal-overlay").classList.add("hidden");
});

document.getElementById("detail-modal-overlay").addEventListener("click", (e) => {
  if (e.target.id === "detail-modal-overlay") {
    document.getElementById("detail-modal-overlay").classList.add("hidden");
  }
});

async function removeTicker(ticker) {
  if (!confirm(`${ticker} von deiner Watchlist entfernen?`)) return;
  try {
    const res = await authFetch(`${API}/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    await loadWatchlist();
  } catch (err) {
    alert(`Fehler beim Entfernen: ${err.message}`);
  }
}

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const ticker = document.getElementById("add-ticker").value.trim();
  const notes = document.getElementById("add-notes").value.trim();
  const purchasePrice = document.getElementById("add-purchase-price").value;
  const quantity = document.getElementById("add-quantity").value;
  const errorEl = document.getElementById("add-error");
  errorEl.textContent = "";

  try {
    const res = await authFetch(`${API}/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker,
        notes: notes || null,
        purchase_price: purchasePrice ? parseFloat(purchasePrice) : null,
        quantity: quantity ? parseFloat(quantity) : null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    document.getElementById("add-ticker").value = "";
    document.getElementById("add-notes").value = "";
    document.getElementById("add-purchase-price").value = "";
    document.getElementById("add-quantity").value = "";
    await loadWatchlist();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("scan-btn").addEventListener("click", async () => {
  const btn = document.getElementById("scan-btn");
  btn.disabled = true;
  btn.textContent = "Scanne ... (kann etwas dauern)";

  try {
    const res = await fetch(`${API}/watchlist/scan`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadWatchlist();
  } catch (err) {
    alert(`Scan fehlgeschlagen: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Jetzt scannen";
  }
});

document.getElementById("eval-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const ticker = document.getElementById("eval-ticker").value.trim();
  const resultEl = document.getElementById("eval-result");
  resultEl.innerHTML = '<p class="hint">Bewerte ...</p>';

  try {
    const res = await fetch(`${API}/stocks/${encodeURIComponent(ticker)}/score`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    resultEl.innerHTML = `
      <div class="result-card">
        <div class="score-line">
          <span class="${badgeClass(data.recommendation)}">${data.recommendation}</span>
          ${getTendencyLabel(data.recommendation, data.expected_return_pct)}
          <strong>${escapeHtml(data.ticker)}</strong>
          ${data.name ? `<span class="company-name">${escapeHtml(data.name)}</span>` : ""}
        </div>
        <div class="metric-row">
          <div class="metric"><span class="metric-label">Erw. Rendite</span>${data.expected_return_pct}%</div>
          <div class="metric"><span class="metric-label">Risiko</span>${data.risk_score}</div>
          <div class="metric"><span class="metric-label">Technisch</span>${data.technical_score}</div>
          <div class="metric"><span class="metric-label">Fundamental</span>${data.fundamental_score}</div>
          <div class="metric"><span class="metric-label">Sentiment</span>${data.sentiment_score ?? "n/a"}</div>
        </div>
        <div class="reasoning-text">${escapeHtml(data.reasoning)}</div>
      </div>
    `;
  } catch (err) {
    resultEl.innerHTML = `<p class="error-text">${err.message}</p>`;
  }
});

document.getElementById("backtest-btn").addEventListener("click", async () => {
  const resultEl = document.getElementById("backtest-result");
  resultEl.innerHTML = '<p class="hint">Lade Backtest ...</p>';

  try {
    const res = await fetch(`${API}/backtest`);
    const data = await res.json();
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    if (data.evaluated_count === 0) {
      resultEl.innerHTML = `<p class="hint">Noch keine ausgewerteten Empfehlungen (Beobachtungsfenster: 14 Tage). ${data.pending_count} warten noch.</p>`;
      return;
    }

    resultEl.innerHTML = `
      <div class="result-card">
        <div class="metric-row">
          <div class="metric"><span class="metric-label">Ausgewertet</span>${data.evaluated_count}</div>
          <div class="metric"><span class="metric-label">Noch offen</span>${data.pending_count}</div>
          <div class="metric"><span class="metric-label">Trefferquote</span>${data.hit_rate_pct ?? "n/a"}%</div>
        </div>
      </div>
    `;
  } catch (err) {
    resultEl.innerHTML = `<p class="error-text">${err.message}</p>`;
  }
});

(function init() {
  const token = getToken();
  const username = localStorage.getItem(USERNAME_KEY);
  if (token && username) {
    showApp(username);
  } else {
    showLoginScreen();
  }
})();
