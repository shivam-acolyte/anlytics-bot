// ==========================================================================
// TrackingBot Page Deep Dive Analytics Logic
// ==========================================================================

const urlParams = new URLSearchParams(window.location.search);
let currentPagePlatform = urlParams.get('platform') || localStorage.getItem('trackingbot_platform') || 'living';
let currentPageUrl = urlParams.get('url') || '';
let currentDays = parseInt(urlParams.get('days') || '30', 10);
let currentStartDate = urlParams.get('start_date') || '';
let currentEndDate = urlParams.get('end_date') || '';
let currentUtm = urlParams.get('utm') || 'all';
let currentSite = urlParams.get('site') || 'all';
let currentCurveType = 'daily';
let inspectorViewMode = 'tree';

let pageData = null;
let allTrackedPages = [];
let pageCurvesChart = null;
let pageActionsChart = null;
let pageDevicesChart = null;
let pageDomainClicksChart = null;

document.addEventListener('DOMContentLoaded', () => {
  initPageUI();
  initPagePlatformSwitcher();
  initPageCombobox();
  initDateFilterControls();
  initCurvesToggle();
  initSubTabs();
  initCopyAndVisit();
  initInspectorControls();
  initPayloadModal();

  // Load UTMs, Subdomains, and Page Data
  Promise.all([initPageWebsitesFilter(), initPageUTMsFilter()]).then(() => {
    if (!currentPageUrl) {
      loadDefaultTopPage();
    } else {
      loadPageDetails();
    }
  });

  // Filter change listeners
  document.getElementById('page-platform-select')?.addEventListener('change', (e) => {
    switchPagePlatform(e.target.value);
  });

  document.getElementById('page-utm-select')?.addEventListener('change', (e) => {
    currentUtm = e.target.value;
    updateURLParams();
    loadPageDetails();
  });

  document.getElementById('page-site-select')?.addEventListener('change', (e) => {
    currentSite = e.target.value;
    updateURLParams();
    loadPageDetails();
  });

  document.getElementById('btn-page-refresh')?.addEventListener('click', handlePageRefresh);
});

// ==========================================================================
// Initialization & Navigation
// ==========================================================================
function initPageUI() {
  const pSelect = document.getElementById('page-platform-select');
  if (pSelect) pSelect.value = currentPagePlatform;

  const gSelect = document.getElementById('global-platform-select');
  if (gSelect) gSelect.value = currentPagePlatform;

  updatePlatformBadge(currentPagePlatform);

  // Sync date inputs if URL has custom dates
  if (currentStartDate) {
    const sInput = document.getElementById('page-start-date');
    if (sInput) sInput.value = currentStartDate;
  }
  if (currentEndDate) {
    const eInput = document.getElementById('page-end-date');
    if (eInput) eInput.value = currentEndDate;
  }

  // Sync active preset pill
  if (currentStartDate || currentEndDate) {
    document.querySelectorAll('#page-date-presets .date-preset-pill').forEach(b => b.classList.remove('active'));
  } else {
    document.querySelectorAll('#page-date-presets .date-preset-pill').forEach(b => {
      const d = b.getAttribute('data-days');
      if (d === currentDays.toString() || (d === 'all' && currentDays >= 365)) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });
  }
}

function updatePlatformBadge(platform) {
  const badge = document.getElementById('page-platform-badge');
  if (badge) {
    badge.textContent = platform === 'startupflora' ? '🌸 StartupFlora (MySQL)' : '🏢 Acolyte Living (PostgreSQL)';
  }
}

function initPagePlatformSwitcher() {
  const gSelect = document.getElementById('global-platform-select');
  if (gSelect) {
    gSelect.value = currentPagePlatform;
    gSelect.addEventListener('change', (e) => switchPagePlatform(e.target.value));
  }
}

function switchPagePlatform(platform) {
  if (currentPagePlatform === platform) return;
  currentPagePlatform = platform;
  localStorage.setItem('trackingbot_platform', platform);

  const pSelect = document.getElementById('page-platform-select');
  if (pSelect) pSelect.value = platform;

  const gSelect = document.getElementById('global-platform-select');
  if (gSelect) gSelect.value = platform;

  updatePlatformBadge(platform);
  updateURLParams();

  // Reload websites, UTMs, Combobox pages, and target page
  Promise.all([initPageWebsitesFilter(), initPageUTMsFilter()]).then(() => {
    refreshComboboxPages().then(() => {
      loadDefaultTopPage();
    });
  });

  const pName = platform === 'startupflora' ? 'StartupFlora (MySQL)' : 'Acolyte Living (PostgreSQL)';
  showToast(`Switched tracking database to ${pName}`, 'info');
}

function updateURLParams() {
  const params = new URLSearchParams();
  if (currentPageUrl) params.set('url', currentPageUrl);
  params.set('platform', currentPagePlatform);
  if (currentStartDate) params.set('start_date', currentStartDate);
  if (currentEndDate) params.set('end_date', currentEndDate);
  if (!currentStartDate && !currentEndDate) params.set('days', currentDays.toString());
  if (currentUtm && currentUtm !== 'all') params.set('utm', currentUtm);
  if (currentSite && currentSite !== 'all') params.set('site', currentSite);

  const newUrl = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState({}, '', newUrl);
}

// ==========================================================================
// Searchable Combobox Dropdown for Page URLs
// ==========================================================================
function initPageCombobox() {
  const input = document.getElementById('page-search-input');
  const dropdown = document.getElementById('page-search-dropdown');
  const toggleBtn = document.getElementById('btn-combobox-toggle');
  const clearBtn = document.getElementById('btn-combobox-clear');
  const goBtn = document.getElementById('btn-page-search-go');

  if (!input || !dropdown) return;

  refreshComboboxPages();

  let debounceTimer = null;
  let activeIndex = -1;

  // Toggle dropdown on button click
  toggleBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (dropdown.style.display === 'block') {
      closeCombobox();
    } else {
      openCombobox();
      renderComboboxItems(input.value.trim());
    }
  });

  // Open on input focus
  input.addEventListener('focus', () => {
    openCombobox();
    renderComboboxItems(input.value.trim());
  });

  // Filter on input typing
  input.addEventListener('input', () => {
    const val = input.value.trim();
    if (clearBtn) clearBtn.style.display = val ? 'inline-flex' : 'none';
    openCombobox();

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      renderComboboxItems(val);
      // If no local match and query > 1 chars, search server
      if (val.length >= 2) {
        searchServerPages(val);
      }
    }, 200);
  });

  // Clear button
  clearBtn?.addEventListener('click', () => {
    input.value = '';
    clearBtn.style.display = 'none';
    input.focus();
    renderComboboxItems('');
  });

  // Keyboard Navigation
  input.addEventListener('keydown', (e) => {
    const items = dropdown.querySelectorAll('.page-combobox-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (dropdown.style.display !== 'block') openCombobox();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
      highlightComboboxItem(items, activeIndex);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      highlightComboboxItem(items, activeIndex);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && items[activeIndex]) {
        items[activeIndex].click();
      } else {
        const val = input.value.trim();
        if (val) {
          selectComboboxUrl(val);
        }
      }
    } else if (e.key === 'Escape') {
      closeCombobox();
    }
  });

  // Analyze button
  goBtn?.addEventListener('click', () => {
    const val = input.value.trim();
    if (val) selectComboboxUrl(val);
  });

  // Outside click to close
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#page-combobox-wrapper')) {
      closeCombobox();
    }
  });
}

function openCombobox() {
  const dropdown = document.getElementById('page-search-dropdown');
  if (dropdown) dropdown.style.display = 'block';
  const toggleBtn = document.getElementById('btn-combobox-toggle');
  if (toggleBtn) toggleBtn.textContent = '▲';
}

function closeCombobox() {
  const dropdown = document.getElementById('page-search-dropdown');
  if (dropdown) dropdown.style.display = 'none';
  const toggleBtn = document.getElementById('btn-combobox-toggle');
  if (toggleBtn) toggleBtn.textContent = '▼';
}

function highlightComboboxItem(items, index) {
  items.forEach((item, idx) => {
    if (idx === index) {
      item.classList.add('combobox-item-active');
      item.scrollIntoView({ block: 'nearest' });
    } else {
      item.classList.remove('combobox-item-active');
    }
  });
}

async function refreshComboboxPages() {
  const countBadge = document.getElementById('combobox-page-count');
  if (countBadge) countBadge.textContent = 'Loading...';

  try {
    const dateQuery = currentStartDate && currentEndDate ? `&start_date=${currentStartDate}&end_date=${currentEndDate}` : `&days=${currentDays}`;
    const res = await fetch(`/api/analytics/top-pages?platform=${currentPagePlatform}&limit=60${dateQuery}`);
    const data = await res.json();
    allTrackedPages = data.pages || [];
    if (countBadge) countBadge.textContent = `${allTrackedPages.length} Pages Tracked`;
    renderComboboxItems(document.getElementById('page-search-input')?.value.trim() || '');
  } catch (err) {
    console.error('Failed to load combobox pages:', err);
    if (countBadge) countBadge.textContent = 'Ready';
  }
}

async function searchServerPages(query) {
  try {
    const res = await fetch(`/api/analytics/search-pages?q=${encodeURIComponent(query)}&platform=${currentPagePlatform}&limit=30`);
    const data = await res.json();
    const serverPages = data.pages || [];

    // Merge unique with allTrackedPages
    const existing = new Set(allTrackedPages.map(p => p.url));
    serverPages.forEach(p => {
      if (!existing.has(p.url)) {
        allTrackedPages.push(p);
        existing.add(p.url);
      }
    });

    renderComboboxItems(query);
  } catch (err) {
    console.error('Server page search error:', err);
  }
}

function renderComboboxItems(query) {
  const list = document.getElementById('page-combobox-list');
  if (!list) return;

  const q = (query || '').toLowerCase();
  const filtered = allTrackedPages.filter(p => !q || p.url.toLowerCase().includes(q));

  if (filtered.length === 0) {
    list.innerHTML = `
      <div style="padding:14px;text-align:center;color:#94a3b8;font-size:0.85rem;">
        No pages found matching "<strong>${escapeHtml(query)}</strong>"<br/>
        <span style="font-size:0.75rem;color:#64748b;">Press Enter to analyze this custom URL directly.</span>
      </div>
    `;
    return;
  }

  list.innerHTML = '';
  filtered.forEach((p, idx) => {
    const item = document.createElement('div');
    item.className = `page-combobox-item ${p.url === currentPageUrl ? 'selected-current-page' : ''}`;
    
    // Highlight matching part
    let displayUrl = escapeHtml(p.url);
    if (q) {
      const regex = new RegExp(`(${escapeRegExp(q)})`, 'gi');
      displayUrl = displayUrl.replace(regex, '<mark class="combobox-highlight">$1</mark>');
    }

    item.innerHTML = `
      <div class="combobox-item-main">
        <span class="combobox-item-icon">${p.url === '/' ? '🏠' : (p.url.includes('/blog') ? '📝' : '📄')}</span>
        <span class="combobox-item-url">${displayUrl}</span>
      </div>
      <div class="combobox-item-meta">
        <span class="combobox-pill-views">👁️ ${formatNumber(p.views)}</span>
        <span class="combobox-pill-users">👥 ${formatNumber(p.users)}</span>
      </div>
    `;

    item.addEventListener('click', () => {
      selectComboboxUrl(p.url);
    });

    list.appendChild(item);
  });
}

function selectComboboxUrl(url) {
  currentPageUrl = url;
  const input = document.getElementById('page-search-input');
  if (input) input.value = url;
  closeCombobox();
  updateURLParams();
  loadPageDetails();
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ==========================================================================
// Date Filter Controls (Date-to-Date & Range Presets)
// ==========================================================================
function initDateFilterControls() {
  const pills = document.querySelectorAll('#page-date-presets .date-preset-pill');
  const startInput = document.getElementById('page-start-date');
  const endInput = document.getElementById('page-end-date');
  const applyBtn = document.getElementById('btn-apply-dates');

  // Preset buttons (7D, 30D, 60D, 90D, all)
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      const daysVal = pill.getAttribute('data-days');
      if (daysVal === 'all') {
        currentDays = 365;
      } else {
        currentDays = parseInt(daysVal, 10);
      }

      currentStartDate = '';
      currentEndDate = '';
      if (startInput) startInput.value = '';
      if (endInput) endInput.value = '';

      updateURLParams();
      refreshComboboxPages();
      initPageUTMsFilter().then(() => loadPageDetails());
    });
  });

  // Apply custom dates button
  applyBtn?.addEventListener('click', () => {
    const sVal = startInput?.value;
    const eVal = endInput?.value;

    if (!sVal && !eVal) {
      showToast('Please select at least a start date', 'warning');
      return;
    }

    if (sVal && eVal && sVal > eVal) {
      showToast('Start date cannot be after end date', 'warning');
      return;
    }

    currentStartDate = sVal || '';
    currentEndDate = eVal || '';

    // Deselect preset pills
    pills.forEach(p => p.classList.remove('active'));

    updateURLParams();
    refreshComboboxPages();
    initPageUTMsFilter().then(() => loadPageDetails());
    showToast(`Date filter applied: ${currentStartDate || 'Start'} to ${currentEndDate || 'Latest'}`, 'success');
  });
}

// ==========================================================================
// Default Page Loader
// ==========================================================================
async function loadDefaultTopPage() {
  try {
    const res = await fetch(`/api/analytics/top-pages?platform=${currentPagePlatform}&days=${currentDays}&limit=5`);
    const data = await res.json();
    if (data.pages && data.pages.length > 0) {
      currentPageUrl = data.pages[0].url;
      updateURLParams();
      loadPageDetails();
    } else {
      currentPageUrl = '/';
      updateURLParams();
      loadPageDetails();
    }
  } catch (err) {
    console.error('Failed to load default top page:', err);
    currentPageUrl = '/';
    loadPageDetails();
  }
}

// ==========================================================================
// Subdomain & UTM Filter Initializers
// ==========================================================================
async function initPageWebsitesFilter() {
  try {
    const res = await fetch(`/api/analytics/websites?platform=${currentPagePlatform}`);
    const data = await res.json();
    const select = document.getElementById('page-site-select');
    if (!select) return;

    select.innerHTML = '<option value="all">🌐 All Domains</option>';
    if (data.websites && data.websites.length) {
      data.websites.forEach(w => {
        const opt = document.createElement('option');
        opt.value = w.id;
        opt.textContent = `${w.name} (${formatNumber(w.events)} hits)`;
        if (currentSite === w.id) opt.selected = true;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.error('Failed to load websites filter:', err);
  }
}

async function initPageUTMsFilter() {
  const select = document.getElementById('page-utm-select');
  if (!select) return;

  try {
    const dateQuery = currentStartDate && currentEndDate ? `&start_date=${currentStartDate}&end_date=${currentEndDate}` : `&days=${currentDays}`;
    const res = await fetch(`/api/analytics/utms?platform=${currentPagePlatform}${dateQuery}`);
    const data = await res.json();
    const utms = data.utms || {};

    select.innerHTML = '<option value="all">🎯 All Traffic / Organic</option>';

    const campaigns = utms.campaigns || [];
    const sources = utms.sources || [];

    if (campaigns.length > 0) {
      const campGroup = document.createElement('optgroup');
      campGroup.label = '📢 Campaigns (utm_campaign)';
      campaigns.forEach(c => {
        const opt = document.createElement('option');
        opt.value = `campaign:${c.name}`;
        opt.textContent = `${c.name} (${formatNumber(c.events)} hits)`;
        if (currentUtm === `campaign:${c.name}`) opt.selected = true;
        campGroup.appendChild(opt);
      });
      select.appendChild(campGroup);
    }

    if (sources.length > 0) {
      const srcGroup = document.createElement('optgroup');
      srcGroup.label = '🌐 Sources (utm_source)';
      sources.forEach(s => {
        const opt = document.createElement('option');
        opt.value = `source:${s.name}`;
        opt.textContent = `${s.name} (${formatNumber(s.events)} hits)`;
        if (currentUtm === `source:${s.name}`) opt.selected = true;
        srcGroup.appendChild(opt);
      });
      select.appendChild(srcGroup);
    }

    if (currentUtm && currentUtm !== 'all') {
      select.value = currentUtm;
    }
  } catch (err) {
    console.error('Failed to load UTMs:', err);
  }
}

// ==========================================================================
// Copy and Visit URL Actions
// ==========================================================================
function initCopyAndVisit() {
  const copyBtn = document.getElementById('btn-copy-url');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      if (!currentPageUrl) return;
      navigator.clipboard.writeText(currentPageUrl).then(() => {
        showToast('Page URL copied to clipboard!', 'success');
      }).catch(() => {
        showToast('Failed to copy URL', 'error');
      });
    });
  }
}

// ==========================================================================
// Curves Toggle Group & Subtabs
// ==========================================================================
function initCurvesToggle() {
  const buttons = document.querySelectorAll('#page-curves-btn-group .btn-granularity');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCurveType = btn.getAttribute('data-curve');
      renderPageCurvesChart(currentCurveType);
    });
  });
}

function initSubTabs() {
  const btnRef = document.getElementById('btn-tab-referrers');
  const btnUtm = document.getElementById('btn-tab-utm');
  const boxRef = document.getElementById('container-page-referrers');
  const boxUtm = document.getElementById('container-page-utm');

  if (btnRef && btnUtm) {
    btnRef.addEventListener('click', () => {
      btnRef.classList.add('active');
      btnUtm.classList.remove('active');
      boxRef.style.display = 'block';
      boxUtm.style.display = 'none';
    });

    btnUtm.addEventListener('click', () => {
      btnUtm.classList.add('active');
      btnRef.classList.remove('active');
      boxRef.style.display = 'none';
      boxUtm.style.display = 'block';
    });
  }
}

// ==========================================================================
// Main Page Details Loader
// ==========================================================================
async function loadPageDetails() {
  if (!currentPageUrl) return;

  // Update Page Hero display
  const breadcrumb = document.getElementById('breadcrumb-page-url');
  if (breadcrumb) breadcrumb.textContent = currentPageUrl;
  const heroUrl = document.getElementById('page-hero-url');
  if (heroUrl) heroUrl.textContent = currentPageUrl;
  const searchInput = document.getElementById('page-search-input');
  if (searchInput) searchInput.value = currentPageUrl;

  const visitBtn = document.getElementById('btn-visit-url');
  if (visitBtn) {
    visitBtn.href = currentPageUrl.startsWith('http') ? currentPageUrl : `https://${currentPageUrl.replace(/^\/+/, '')}`;
  }

  // Set loading placeholders on KPI Cards
  document.getElementById('kpi-page-views').textContent = '...';
  document.getElementById('kpi-page-clicks').textContent = '...';
  document.getElementById('kpi-page-ctr').textContent = '...%';
  document.getElementById('kpi-page-actions').textContent = '...';
  document.getElementById('kpi-page-users').textContent = '...';
  document.getElementById('kpi-page-clicking-users').textContent = '...';
  document.getElementById('kpi-page-domains').textContent = '...';
  document.getElementById('kpi-page-peakhour').textContent = '...';
  document.getElementById('kpi-page-lastseen').textContent = 'Activity: ...';

  try {
    const site = document.getElementById('page-site-select')?.value || currentSite || 'all';
    const utm = document.getElementById('page-utm-select')?.value || currentUtm || 'all';
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const siteParam = site && site !== 'all' ? `&site=${encodeURIComponent(site)}` : '';
    const dateParam = currentStartDate && currentEndDate ? `&start_date=${currentStartDate}&end_date=${currentEndDate}` : `&days=${currentDays}`;

    const res = await fetch(`/api/analytics/page-details?url=${encodeURIComponent(currentPageUrl)}&platform=${currentPagePlatform}${dateParam}${siteParam}${utmParam}`);
    const data = await res.json();
    pageData = data;

    // 1. Populate KPI Cards
    const kpis = data.kpis || {};
    document.getElementById('kpi-page-views').textContent = formatNumber(kpis.total_views || 0);
    document.getElementById('kpi-page-clicks').textContent = formatNumber(kpis.total_clicks || 0);
    document.getElementById('kpi-page-ctr').textContent = `${kpis.ctr || 0}%`;
    document.getElementById('kpi-page-actions').textContent = formatNumber(kpis.total_actions || 0);
    document.getElementById('kpi-page-users').textContent = formatNumber(kpis.unique_users || 0);
    document.getElementById('kpi-page-clicking-users').textContent = formatNumber(kpis.clicking_users || 0);
    document.getElementById('kpi-page-domains').textContent = formatNumber(kpis.distinct_domains || 0);
    document.getElementById('kpi-page-peakhour').textContent = kpis.peak_hour || '--';
    document.getElementById('kpi-page-lastseen').textContent = `Activity: ${formatDateTime(kpis.last_seen) || '--'}`;

    // 2. Populate Domain Breakdown for Clicks & Buttons
    renderDomainClicksBreakdown(data.domain_clicks_breakdown || [], kpis.total_clicks || 0);

    // 3. Populate Recursive Actions, Buttons & Things Inspector
    renderRecursiveActionsInspector(data.recursive_actions || {}, data.flat_actions || []);

    // 4. Render Traffic Curves
    renderPageCurvesChart(currentCurveType);

    // 5. Render User Actions & Events Funnel
    renderPageActions(data.events_breakdown || []);

    // 6. Render Referrers & UTMs
    renderPageSources(data.sources_and_utm || {});

    // 7. Render Audience & Technology
    renderPageAudience(data.devices_and_audience || {});

    // 8. Render Live Activity Stream
    renderPageActivity(data.recent_activity || []);

  } catch (err) {
    console.error('Failed to load page deep dive details:', err);
    showToast('Failed to load analytics for this page URL', 'error');
  }
}

// ==========================================================================
// Domain Breakdown for Clicks & Buttons Renderer
// ==========================================================================
function renderDomainClicksBreakdown(domains, totalClicks) {
  const badge = document.getElementById('badge-total-domain-clicks');
  if (badge) badge.textContent = `${formatNumber(totalClicks)} Total Clicks`;

  const tbody = document.getElementById('table-domain-clicks');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!domains || domains.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748b;padding:24px;">No domain clicks logged on this URL in the selected range</td></tr>';
    if (pageDomainClicksChart) pageDomainClicksChart.destroy();
    return;
  }

  domains.forEach(d => {
    const tr = document.createElement('tr');
    
    // Top buttons chips
    let buttonsHtml = '<span style="color:#64748b;font-size:0.8rem;">None recorded</span>';
    if (d.top_buttons && d.top_buttons.length > 0) {
      buttonsHtml = d.top_buttons.map(b => `
        <span class="btn-tag-chip" title="${escapeHtml(b.button)}: ${b.count} clicks">
          ${escapeHtml(b.button)} <strong style="color:#f472b6;">(${b.count})</strong>
        </span>
      `).join(' ');
    }

    tr.innerHTML = `
      <td>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:1.05rem;">🌐</span>
          <span style="font-weight:600;color:#f8fafc;">${escapeHtml(d.domain)}</span>
        </div>
      </td>
      <td><span class="brand-badge" style="background:rgba(236,72,153,0.15);color:#f472b6;font-weight:700;">${formatNumber(d.clicks)} clicks</span></td>
      <td><span style="color:#38bdf8;font-weight:600;">👥 ${formatNumber(d.users)}</span></td>
      <td>
        <div style="display:flex;align-items:center;gap:8px;">
          <div class="progress-bar-bg" style="width:70px;">
            <div class="progress-bar-fill" style="width:${Math.min(100, d.share_pct)}%;background:#f472b6;"></div>
          </div>
          <span style="font-size:0.82rem;font-weight:600;color:#f472b6;">${d.share_pct}%</span>
        </div>
      </td>
      <td style="max-width:320px;">${buttonsHtml}</td>
    `;
    tbody.appendChild(tr);
  });

  // Render Domain Clicks Doughnut Chart
  const ctx = document.getElementById('chart-domain-clicks')?.getContext('2d');
  if (!ctx) return;
  if (pageDomainClicksChart) pageDomainClicksChart.destroy();

  const chartLabels = domains.slice(0, 6).map(d => d.domain);
  const chartValues = domains.slice(0, 6).map(d => d.clicks);
  const chartColors = ['#f472b6', '#38bdf8', '#a78bfa', '#34d399', '#fbbf24', '#f87171'];

  pageDomainClicksChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: chartLabels,
      datasets: [{
        data: chartValues,
        backgroundColor: chartColors,
        borderWidth: 0,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } }
        }
      },
      cutout: '66%'
    }
  });
}

// ==========================================================================
// Recursive Actions, Buttons & Things Inspector Renderer
// ==========================================================================
let currentFlatActionsData = [];
let currentTreeData = {};

function initInspectorControls() {
  const treeBtn = document.getElementById('btn-view-tree');
  const tableBtn = document.getElementById('btn-view-table');
  const treeContainer = document.getElementById('container-actions-tree');
  const tableContainer = document.getElementById('container-actions-table');
  const searchInput = document.getElementById('inspector-search-input');
  const searchClear = document.getElementById('btn-inspector-search-clear');
  const expandAllBtn = document.getElementById('btn-tree-expand-all');
  const collapseAllBtn = document.getElementById('btn-tree-collapse-all');

  treeBtn?.addEventListener('click', () => {
    treeBtn.classList.add('active');
    tableBtn?.classList.remove('active');
    if (treeContainer) treeContainer.style.display = 'block';
    if (tableContainer) tableContainer.style.display = 'none';
    inspectorViewMode = 'tree';
  });

  tableBtn?.addEventListener('click', () => {
    tableBtn.classList.add('active');
    treeBtn?.classList.remove('active');
    if (treeContainer) treeContainer.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';
    inspectorViewMode = 'table';
  });

  // Live filter inside inspector
  searchInput?.addEventListener('input', () => {
    const val = searchInput.value.trim().toLowerCase();
    if (searchClear) searchClear.style.display = val ? 'inline-flex' : 'none';
    filterInspectorContent(val);
  });

  searchClear?.addEventListener('click', () => {
    searchInput.value = '';
    searchClear.style.display = 'none';
    filterInspectorContent('');
  });

  // Expand All / Collapse All
  expandAllBtn?.addEventListener('click', () => {
    document.querySelectorAll('.tree-collapsible-node').forEach(el => el.classList.add('expanded'));
  });

  collapseAllBtn?.addEventListener('click', () => {
    document.querySelectorAll('.tree-collapsible-node').forEach(el => el.classList.remove('expanded'));
  });
}

function renderRecursiveActionsInspector(tree, flatActions) {
  currentTreeData = tree || {};
  currentFlatActionsData = flatActions || [];

  const badge = document.getElementById('badge-total-actions-count');
  if (badge) badge.textContent = `${currentFlatActionsData.length} Action Clusters`;

  renderTreeDOM(currentTreeData);
  renderFlatTableDOM(currentFlatActionsData);
}

function renderTreeDOM(tree) {
  const container = document.getElementById('container-actions-tree');
  if (!container) return;

  const eventNames = Object.keys(tree);
  if (eventNames.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;color:#64748b;padding:36px;">
        <span style="font-size:2rem;display:block;margin-bottom:8px;">🔍</span>
        No non-pageview actions logged on this page in the selected range.
      </div>
    `;
    return;
  }

  let html = '<div class="actions-tree-root">';

  eventNames.forEach(evName => {
    const evData = tree[evName];
    const buttons = evData.buttons || {};
    const btnNames = Object.keys(buttons);

    html += `
      <div class="tree-node tree-level-event tree-collapsible-node expanded" data-filter-text="${escapeHtml(evName)}">
        <div class="tree-node-header" onclick="toggleTreeNode(this)">
          <span class="tree-caret">▼</span>
          <span class="tree-node-icon">⚡</span>
          <span class="tree-node-title event-title">${escapeHtml(evName)}</span>
          <span class="tree-badge badge-event">${formatNumber(evData.total_count)} hits</span>
          <span class="tree-badge badge-users">👥 ${formatNumber(evData.unique_users)} users</span>
        </div>
        <div class="tree-node-children">
    `;

    btnNames.forEach(btnName => {
      const btnData = buttons[btnName];
      const domains = btnData.domains || {};
      const domNames = Object.keys(domains);

      html += `
        <div class="tree-node tree-level-button tree-collapsible-node expanded" data-filter-text="${escapeHtml(evName)} ${escapeHtml(btnName)}">
          <div class="tree-node-header" onclick="toggleTreeNode(this)">
            <span class="tree-caret">▼</span>
            <span class="tree-node-icon">🖱️</span>
            <span class="tree-node-title button-title">${escapeHtml(btnName)}</span>
            <span class="tree-badge badge-button">${formatNumber(btnData.total_count)} clicks</span>
          </div>
          <div class="tree-node-children">
      `;

      domNames.forEach(domName => {
        const domData = domains[domName];
        const occurrences = domData.occurrences || [];
        const things = domData.sample_things || {};
        const thingsKeys = Object.keys(things);

        let thingsHtml = '';
        thingsKeys.forEach(k => {
          thingsHtml += `
            <span class="tree-thing-chip" title="${escapeHtml(k)}: ${escapeHtml(String(things[k]))}">
              <strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(things[k]))}
            </span>
          `;
        });

        html += `
          <div class="tree-node tree-level-domain tree-collapsible-node expanded" data-filter-text="${escapeHtml(evName)} ${escapeHtml(btnName)} ${escapeHtml(domName)} ${escapeHtml(thingsKeys.join(' '))}">
            <div class="tree-node-header" onclick="toggleTreeNode(this)">
              <span class="tree-caret">▼</span>
              <span class="tree-node-icon">🌐</span>
              <span class="tree-node-title domain-title">${escapeHtml(domName)}</span>
              ${domData.dest_domain && domData.dest_domain !== domName ? `<span class="tree-dest-domain">➔ ${escapeHtml(domData.dest_domain)}</span>` : ''}
              <span class="tree-badge badge-domain">${formatNumber(domData.total_count)} hits</span>
            </div>
            <div class="tree-node-children tree-things-leaf">
              <div class="things-contained-box">
                <div class="things-header">
                  <span>📦 Things & Attributes Contained:</span>
                  <button type="button" class="btn-inspect-payload" onclick="viewOccurrencePayload('${escapeHtml(evName)}', '${escapeHtml(btnName)}', '${escapeHtml(domName)}')">
                    <span>🔍</span> View Full JSON
                  </button>
                </div>
                <div class="things-chips-cloud">
                  ${thingsHtml || '<span style="color:#64748b;font-size:0.8rem;">Standard event parameters</span>'}
                </div>
                <div class="things-recent-info">
                  <span>Recent activity: <strong>${occurrences.length ? occurrences[0].latest_at : '--'}</strong></span>
                </div>
              </div>
            </div>
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
  });

  html += '</div>';
  container.innerHTML = html;
}

window.toggleTreeNode = function(headerEl) {
  const node = headerEl.closest('.tree-collapsible-node');
  if (node) {
    node.classList.toggle('expanded');
    const caret = node.querySelector('.tree-caret');
    if (caret) {
      caret.textContent = node.classList.contains('expanded') ? '▼' : '▶';
    }
  }
};

function renderFlatTableDOM(actions) {
  const tbody = document.getElementById('table-flat-actions');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!actions || actions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#64748b;padding:24px;">No actions recorded</td></tr>';
    return;
  }

  actions.forEach((act, idx) => {
    const tr = document.createElement('tr');
    tr.setAttribute('data-filter-text', `${act.event_name} ${act.button_name} ${act.domain} ${act.things_summary}`.toLowerCase());

    tr.innerHTML = `
      <td><span class="brand-badge" style="background:rgba(99,102,241,0.2);color:#a5b4fc;">${escapeHtml(act.event_name)}</span></td>
      <td style="font-weight:600;color:#f472b6;">${escapeHtml(act.button_name)}</td>
      <td><span style="color:#38bdf8;">🌐 ${escapeHtml(act.domain)}</span></td>
      <td style="font-weight:700;color:#fff;">${formatNumber(act.count)}</td>
      <td style="color:#94a3b8;">${formatNumber(act.users)}</td>
      <td style="max-width:280px;font-size:0.8rem;color:#cbd5e1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
        ${escapeHtml(act.things_summary)}
      </td>
      <td style="font-family:monospace;font-size:0.8rem;color:#94a3b8;white-space:nowrap;">
        ${act.latest_at ? act.latest_at.slice(0, 19).replace('T', ' ') : '--'}
      </td>
      <td>
        <button type="button" class="btn-inspect-payload" onclick="viewFlatActionPayload(${idx})">
          <span>📦</span> JSON
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterInspectorContent(query) {
  const q = (query || '').toLowerCase().trim();

  // Filter tree nodes
  document.querySelectorAll('.tree-node').forEach(node => {
    const text = (node.getAttribute('data-filter-text') || '').toLowerCase();
    if (!q || text.includes(q)) {
      node.style.display = 'block';
      if (q) node.classList.add('expanded');
    } else {
      // Check if any child matches
      const childMatch = node.querySelector(`.tree-node[data-filter-text*="${q}"]`);
      if (childMatch) {
        node.style.display = 'block';
        node.classList.add('expanded');
      } else {
        node.style.display = 'none';
      }
    }
  });

  // Filter flat table rows
  document.querySelectorAll('#table-flat-actions tr').forEach(row => {
    const text = (row.getAttribute('data-filter-text') || '').toLowerCase();
    if (!q || text.includes(q)) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

// ==========================================================================
// Raw Payload JSON Modal
// ==========================================================================
function initPayloadModal() {
  const modal = document.getElementById('modal-payload-viewer');
  const closeBtn = document.getElementById('btn-close-payload-modal');
  const copyBtn = document.getElementById('btn-copy-payload-json');

  closeBtn?.addEventListener('click', () => {
    if (modal) modal.style.display = 'none';
  });

  modal?.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });

  copyBtn?.addEventListener('click', () => {
    const code = document.getElementById('payload-json-code')?.textContent || '';
    navigator.clipboard.writeText(code).then(() => {
      showToast('Payload JSON copied to clipboard!', 'success');
    }).catch(() => {
      showToast('Failed to copy JSON', 'error');
    });
  });
}

window.viewOccurrencePayload = function(evName, btnName, domName) {
  const evData = currentTreeData[evName];
  if (!evData) return;
  const btnData = evData.buttons?.[btnName];
  if (!btnData) return;
  const domData = btnData.domains?.[domName];
  if (!domData) return;

  const raw = domData.occurrences?.[0]?.raw_payload || domData.sample_things || {};
  openPayloadModal(
    `${evName} ➔ ${btnName}`,
    `Attributed on ${domName}`,
    `Total Occurrences: ${domData.total_count} | Unique Users: ${domData.unique_users}`,
    raw
  );
};

window.viewFlatActionPayload = function(index) {
  const act = currentFlatActionsData[index];
  if (!act) return;

  openPayloadModal(
    `${act.event_name} ➔ ${act.button_name}`,
    `Domain: ${act.domain}`,
    `Count: ${act.count} | Users: ${act.users} | Timestamp: ${act.latest_at}`,
    act.raw_payload || act.things || {}
  );
};

function openPayloadModal(title, subtitle, meta, payload) {
  const modal = document.getElementById('modal-payload-viewer');
  const titleEl = document.getElementById('payload-modal-title');
  const subEl = document.getElementById('payload-modal-subtitle');
  const metaEl = document.getElementById('payload-meta-info');
  const codeEl = document.getElementById('payload-json-code');

  if (titleEl) titleEl.textContent = title;
  if (subEl) subEl.textContent = subtitle;
  if (metaEl) metaEl.textContent = meta;
  if (codeEl) codeEl.textContent = JSON.stringify(payload, null, 2);

  if (modal) modal.style.display = 'flex';
}

// ==========================================================================
// Chart: Traffic Curves
// ==========================================================================
function renderPageCurvesChart(type) {
  if (!pageData || !pageData.traffic_curves) return;
  const curves = pageData.traffic_curves;
  const ctx = document.getElementById('chart-page-curves')?.getContext('2d');
  if (!ctx) return;

  if (pageCurvesChart) pageCurvesChart.destroy();

  let labels = [];
  let views = [];
  let users = [];

  if (type === 'hourly') {
    labels = curves.hourly.labels || [];
    views = curves.hourly.views || [];
    users = curves.hourly.users || [];
  } else if (type === '15min') {
    labels = curves.fifteen_min.labels || [];
    views = curves.fifteen_min.views || [];
    users = curves.fifteen_min.users || [];
  } else if (type === 'dow') {
    labels = curves.dow.labels || [];
    views = curves.dow.views || [];
    users = curves.dow.users || [];
  } else { // daily
    const daily = curves.daily_trends || [];
    labels = daily.map(d => `${d.date.slice(5)} (${d.day})`);
    views = daily.map(d => d.views);
    users = daily.map(d => d.users);
  }

  pageCurvesChart = new Chart(ctx, {
    type: type === 'dow' ? 'bar' : 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Page Views',
          data: views,
          borderColor: '#06b6d4',
          backgroundColor: type === 'dow' ? 'rgba(6, 182, 212, 0.65)' : 'rgba(6, 182, 212, 0.15)',
          borderWidth: 2,
          tension: 0.35,
          fill: true,
          borderRadius: 6,
          yAxisID: 'y'
        },
        {
          label: 'Unique Visitors',
          data: users,
          borderColor: '#6366f1',
          backgroundColor: type === 'dow' ? 'rgba(99, 102, 241, 0.65)' : 'rgba(99, 102, 241, 0.15)',
          borderWidth: 2,
          borderDash: type === 'dow' ? [] : [4, 4],
          tension: 0.35,
          fill: false,
          borderRadius: 6,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
        y: { 
          grid: { color: 'rgba(255, 255, 255, 0.05)' }, 
          ticks: { color: '#06b6d4' },
          title: { display: true, text: 'Pageviews', color: '#06b6d4' }
        },
        y1: {
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { color: '#6366f1' },
          title: { display: true, text: 'Unique Visitors', color: '#6366f1' }
        }
      },
      plugins: {
        legend: { labels: { color: '#f8fafc' } }
      }
    }
  });
}

// ==========================================================================
// User Actions Breakdown
// ==========================================================================
function renderPageActions(events) {
  const tbody = document.getElementById('table-page-events');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (events && events.length) {
    events.forEach(e => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight:600;color:#c084fc;">${escapeHtml(e.name)}</td>
        <td style="font-weight:600;color:#fff;">${formatNumber(e.count)}</td>
        <td>${formatNumber(e.users)}</td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No action events logged</td></tr>';
  }

  // Actions Doughnut Chart
  const ctx = document.getElementById('chart-page-actions')?.getContext('2d');
  if (!ctx) return;
  if (pageActionsChart) pageActionsChart.destroy();

  const labels = events.slice(0, 5).map(e => e.name);
  const data = events.slice(0, 5).map(e => e.count);

  pageActionsChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      cutout: '68%'
    }
  });
}

// ==========================================================================
// Inbound Referrers & UTM Campaigns
// ==========================================================================
function renderPageSources(sourcesData) {
  const tbodyRef = document.getElementById('table-page-referrers');
  if (tbodyRef) {
    tbodyRef.innerHTML = '';
    const referrers = sourcesData.referrers || [];
    if (referrers.length) {
      referrers.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="color:#fff;font-weight:500;">${escapeHtml(r.source)}</td>
          <td style="font-weight:600;color:#38bdf8;">${formatNumber(r.count)}</td>
          <td>${formatNumber(r.users)}</td>
        `;
        tbodyRef.appendChild(tr);
      });
    } else {
      tbodyRef.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No referrer data</td></tr>';
    }
  }

  const tbodyUtm = document.getElementById('table-page-utm');
  if (tbodyUtm) {
    tbodyUtm.innerHTML = '';
    const campaigns = sourcesData.campaigns || [];
    if (campaigns.length) {
      campaigns.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-weight:600;color:#a78bfa;">${escapeHtml(c.campaign)}</td>
          <td style="color:#94a3b8;">${escapeHtml(c.source)}</td>
          <td style="font-weight:600;color:#fff;">${formatNumber(c.count)}</td>
        `;
        tbodyUtm.appendChild(tr);
      });
    } else {
      tbodyUtm.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No UTM campaigns recorded</td></tr>';
    }
  }
}

// ==========================================================================
// Audience & Technology
// ==========================================================================
function renderPageAudience(aud) {
  const ctx = document.getElementById('chart-page-devices')?.getContext('2d');
  if (ctx) {
    if (pageDevicesChart) pageDevicesChart.destroy();
    const devTypes = aud.device_types || [];
    pageDevicesChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: devTypes.map(d => d.type),
        datasets: [{
          data: devTypes.map(d => d.count),
          backgroundColor: ['#6366f1', '#06b6d4', '#f59e0b'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 12 } }
        },
        cutout: '62%'
      }
    });
  }

  const tbodyBrowser = document.getElementById('table-page-browsers');
  if (tbodyBrowser) {
    tbodyBrowser.innerHTML = '';
    const browsers = aud.browsers || [];
    if (browsers.length) {
      browsers.forEach(b => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="color:#fff;font-weight:500;">${escapeHtml(b.browser)}</td>
          <td style="font-weight:600;color:#38bdf8;">${formatNumber(b.count)}</td>
        `;
        tbodyBrowser.appendChild(tr);
      });
    } else {
      tbodyBrowser.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#64748b;">No browser data</td></tr>';
    }
  }

  const tbodyCountries = document.getElementById('table-page-countries');
  if (tbodyCountries) {
    tbodyCountries.innerHTML = '';
    const countries = aud.countries || [];
    if (countries.length) {
      countries.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="color:#fff;font-weight:500;">${escapeHtml(c.name)}</td>
          <td style="font-weight:600;color:#34d399;">${formatNumber(c.count)}</td>
        `;
        tbodyCountries.appendChild(tr);
      });
    } else {
      tbodyCountries.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#64748b;">No country data</td></tr>';
    }
  }
}

// ==========================================================================
// Live Stream Feed
// ==========================================================================
function renderPageActivity(events) {
  const tbody = document.getElementById('table-page-activity');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (events && events.length) {
    events.forEach(ev => {
      const tr = document.createElement('tr');
      const isPageView = ev.event_name === 'page_view';
      const badgeColor = isPageView ? 'rgba(6,182,212,0.15)' : 'rgba(99,102,241,0.2)';
      const textColor = isPageView ? '#22d3ee' : '#a5b4fc';

      tr.innerHTML = `
        <td style="font-family:monospace;font-size:0.8rem;color:#94a3b8;white-space:nowrap;">
          ${formatDateTime(ev.occurred_at)}
        </td>
        <td>
          <span class="brand-badge" style="background:${badgeColor};color:${textColor};border:none;">
            ${escapeHtml(ev.event_name)}
          </span>
        </td>
        <td style="font-family:monospace;font-size:0.8rem;color:#64748b;">${escapeHtml(ev.session_id)}</td>
        <td><span class="device-pill">${escapeHtml(ev.device)}</span></td>
        <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#cbd5e1;">${escapeHtml(ev.referrer)}</td>
        <td style="color:#94a3b8;font-size:0.8rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
          ${escapeHtml(ev.data_summary || '--')}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#64748b;padding:24px;">No live stream events recorded</td></tr>';
  }
}

// ==========================================================================
// Helper Utilities
// ==========================================================================
async function handlePageRefresh() {
  const btn = document.getElementById('btn-page-refresh');
  if (btn) {
    btn.innerHTML = '⏳ Refreshing...';
    btn.disabled = true;
  }

  try {
    await fetch('/api/analytics/refresh', { method: 'POST' });
    showToast('Analytics refreshed!', 'success');
    await refreshComboboxPages();
    await loadPageDetails();
  } catch (err) {
    showToast('Failed to refresh data', 'error');
  } finally {
    if (btn) {
      btn.innerHTML = '<span>🔄</span> Refresh';
      btn.disabled = false;
    }
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatNumber(num) {
  if (num === null || num === undefined) return '0';
  return Number(num).toLocaleString('en-US');
}

function formatDateTime(isoStr) {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  } catch (e) {
    return isoStr;
  }
}
