// ==========================================================================
// TrackingBot Reports Page Logic & Interactive Deep Analytics Suite
// ==========================================================================

let currentPlatform = localStorage.getItem('trackingbot_platform') || 'living';

// Chart Instances
let trendChartInstance = null;
let eventsChartInstance = null;
let dynamicChartInstances = {};

// Modal Chart Instances & Cached Page Data
let modalCurvesChartInstance = null;
let modalActionsChartInstance = null;
let modalDevicesChartInstance = null;
let currentModalPageData = null;
let currentModalCurveType = 'daily';

document.addEventListener('DOMContentLoaded', () => {
  initPlatformSwitchers();
  Promise.all([initWebsitesFilter(), initUTMsFilter()]).then(() => {
    loadAllReportsData();
  });

  // Filter change handlers
  const platformSelect = document.getElementById('platform-select');
  if (platformSelect) {
    platformSelect.addEventListener('change', (e) => switchPlatform(e.target.value));
  }

  const utmSelect = document.getElementById('utm-select');
  if (utmSelect) {
    utmSelect.addEventListener('change', () => loadAllReportsData());
  }

  document.getElementById('site-select').addEventListener('change', () => loadAllReportsData());
  document.getElementById('days-select').addEventListener('change', () => {
    initUTMsFilter().then(() => loadAllReportsData());
  });
  document.getElementById('btn-refresh-data').addEventListener('click', handleManualRefresh);

  // Granularity Toolbar Buttons (Main Page)
  initGranularityButtons();

  // Direct Page URL Lookup
  initDirectPageLookup();

  // Pages Table Real-time Filter
  initPagesTableFilter();

  // Deep Analytics Modal Events
  initModalEvents();

  // On-page Chart Bot handler
  document.getElementById('btn-generate-chart').addEventListener('click', handleChartBotSubmit);
  document.getElementById('chart-bot-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleChartBotSubmit();
  });
});

// ==========================================================================
// Platform Switching (Acolyte Living vs StartupFlora)
// ==========================================================================
function initPlatformSwitchers() {
  updatePlatformUI(currentPlatform);

  // Filter bar website platform select
  const platformSelect = document.getElementById('platform-select');
  if (platformSelect) {
    platformSelect.value = currentPlatform;
    platformSelect.addEventListener('change', (e) => switchPlatform(e.target.value));
  }

  // Global platform select in navbar
  const globalSelect = document.getElementById('global-platform-select');
  if (globalSelect) {
    globalSelect.value = currentPlatform;
    globalSelect.addEventListener('change', (e) => switchPlatform(e.target.value));
  }

  // Backwards compatibility for any button references
  const navLiving = document.getElementById('btn-platform-living');
  const navFlora = document.getElementById('btn-platform-startupflora');
  if (navLiving) navLiving.addEventListener('click', () => switchPlatform('living'));
  if (navFlora) navFlora.addEventListener('click', () => switchPlatform('startupflora'));
}

function switchPlatform(platform) {
  if (currentPlatform === platform) return;
  currentPlatform = platform;
  localStorage.setItem('trackingbot_platform', platform);
  updatePlatformUI(platform);

  // Reload websites dropdown, UTMs dropdown, and all visuals
  Promise.all([initWebsitesFilter(), initUTMsFilter()]).then(() => {
    loadAllReportsData();
  });

  const pName = platform === 'startupflora' ? 'StartupFlora (MySQL)' : 'Acolyte Living (PostgreSQL)';
  showToast(`Switched tracking database to ${pName}`, 'info');
}

function updatePlatformUI(platform) {
  const isLiving = platform === 'living';

  // Update dropdowns
  const platformSelect = document.getElementById('platform-select');
  if (platformSelect && platformSelect.value !== platform) {
    platformSelect.value = platform;
  }

  const globalSelect = document.getElementById('global-platform-select');
  if (globalSelect && globalSelect.value !== platform) {
    globalSelect.value = platform;
  }

  // Update navbar status pill
  const statusLabel = document.getElementById('db-status-label');
  if (statusLabel) {
    statusLabel.textContent = isLiving ? 'Acolyte Living (PG)' : 'StartupFlora (MySQL)';
  }

  // Update Chart Bot banner label
  const botLabel = document.getElementById('bot-active-platform-name');
  if (botLabel) {
    botLabel.textContent = isLiving ? 'Acolyte Living' : 'StartupFlora';
  }
}

// ==========================================================================
// Data Loaders
// ==========================================================================
async function initWebsitesFilter() {
  try {
    const res = await fetch(`/api/analytics/websites?platform=${currentPlatform}`);
    const data = await res.json();
    const select = document.getElementById('site-select');
    select.innerHTML = '<option value="all">🌐 All Websites / Domains</option>';

    if (data.websites && data.websites.length) {
      data.websites.forEach(w => {
        const opt = document.createElement('option');
        opt.value = w.id;
        opt.textContent = `${w.name} (${formatNumber(w.events)} events)`;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.error('Failed to load websites:', err);
  }
}

async function initUTMsFilter() {
  const select = document.getElementById('utm-select');
  if (!select) return;

  try {
    const days = document.getElementById('days-select')?.value || 60;
    const res = await fetch(`/api/analytics/utms?platform=${currentPlatform}&days=${days}`);
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
        srcGroup.appendChild(opt);
      });
      select.appendChild(srcGroup);
    }
  } catch (err) {
    console.error('Failed to load UTMs:', err);
  }
}

async function loadAllReportsData() {
  const site = document.getElementById('site-select').value;
  const days = document.getElementById('days-select').value;
  const utm = document.getElementById('utm-select')?.value || 'all';

  loadKPIs(site, days, utm);
  loadHeatmap(site, days, utm);
  loadDailyTrends(site, days, utm);
  loadEventsBreakdown(site, days, utm);
  loadTopPages(site, days, utm);
  loadGeoAndReferrers(site, days, utm);
}

async function loadKPIs(site, days, utm) {
  try {
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const res = await fetch(`/api/analytics/kpis?platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}${utmParam}`);
    const data = await res.json();

    document.getElementById('kpi-events').innerText = formatNumber(data.total_events);
    document.getElementById('kpi-users').innerText = formatNumber(data.unique_users);
    document.getElementById('kpi-sessions').innerText = formatNumber(data.total_sessions);
    document.getElementById('kpi-lowest-slot').innerText = data.lowest_hour_slot || '08:00 - 09:00 IST';
    document.getElementById('kpi-dead-zone').innerText = data.dead_zone_window || '04:00 AM - 10:00 AM IST';
    document.getElementById('kpi-lowest-day').innerText = `${data.lowest_day || 'Sunday'} (~${formatNumber(data.lowest_day_users)} users)`;
  } catch (err) {
    console.error('Failed to load KPIs:', err);
  }
}

async function loadHeatmap(site, days, utm) {
  try {
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const res = await fetch(`/api/analytics/heatmap?platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}${utmParam}`);
    const data = await res.json();

    const tbody = document.getElementById('heatmap-body');
    tbody.innerHTML = '';

    const maxVal = data.max_users || 1;

    data.days.forEach(day => {
      const tr = document.createElement('tr');
      const tdLabel = document.createElement('td');
      tdLabel.className = 'heatmap-day-label';
      tdLabel.innerText = day;
      tr.appendChild(tdLabel);

      const dayUsers = data.users_matrix[day] || Array(24).fill(0);
      dayUsers.forEach((users, hour) => {
        const td = document.createElement('td');
        td.className = 'heatmap-cell';

        const ratio = users / maxVal;
        let intensity = 0;
        if (users === 0) intensity = 0;
        else if (ratio < 0.15) intensity = 1;
        else if (ratio < 0.35) intensity = 2;
        else if (ratio < 0.55) intensity = 3;
        else if (ratio < 0.75) intensity = 4;
        else if (ratio < 0.90) intensity = 5;
        else intensity = 6;

        if (day === 'Sunday' && (hour >= 6 && hour <= 10)) {
          td.classList.add('heat-trough');
        } else if (users >= maxVal * 0.95 && users > 0) {
          td.classList.add('heat-peak');
        } else {
          td.classList.add(`heat-${intensity}`);
        }

        const events = (data.events_matrix[day] && data.events_matrix[day][hour]) || 0;
        td.title = `${day} ${hour.toString().padStart(2, '0')}:00 IST\nUnique Users: ${formatNumber(users)}\nTotal Events: ${formatNumber(events)}`;
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load Heatmap:', err);
  }
}

async function loadDailyTrends(site, days, utm) {
  try {
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const res = await fetch(`/api/analytics/trends?platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}${utmParam}`);
    const data = await res.json();

    const ctx = document.getElementById('chart-daily-trends').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    const labels = data.trends.map(t => `${t.date.slice(5)} (${t.day})`);
    const users = data.trends.map(t => t.users);
    const events = data.trends.map(t => t.events);

    trendChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Unique Users',
            data: users,
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99, 102, 241, 0.15)',
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            yAxisID: 'y'
          },
          {
            label: 'Total Events',
            data: events,
            borderColor: '#06b6d4',
            backgroundColor: 'transparent',
            borderWidth: 2,
            borderDash: [4, 4],
            tension: 0.35,
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
            ticks: { color: '#94a3b8' },
            title: { display: true, text: 'Unique Users', color: '#6366f1' }
          },
          y1: {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#06b6d4' },
            title: { display: true, text: 'Total Events', color: '#06b6d4' }
          }
        },
        plugins: {
          legend: { labels: { color: '#f8fafc' } }
        }
      }
    });
  } catch (err) {
    console.error('Failed to load Daily Trends chart:', err);
  }
}

async function loadEventsBreakdown(site, days, utm) {
  try {
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const res = await fetch(`/api/analytics/events?platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}${utmParam}`);
    const data = await res.json();

    const ctx = document.getElementById('chart-events-breakdown').getContext('2d');
    if (eventsChartInstance) eventsChartInstance.destroy();

    const labels = data.events.map(e => e.event_name);
    const counts = data.events.map(e => e.count);

    eventsChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Total Events',
          data: counts,
          backgroundColor: '#8b5cf6',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        scales: {
          x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
          y: { grid: { display: false }, ticks: { color: '#f8fafc' } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  } catch (err) {
    console.error('Failed to load Events Breakdown chart:', err);
  }
}

let allTopPagesData = [];

async function loadTopPages(site, days, utm) {
  try {
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const res = await fetch(`/api/analytics/top-pages?platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}&limit=15${utmParam}`);
    const data = await res.json();
    allTopPagesData = data.pages || [];
    renderTopPagesTable(allTopPagesData);
  } catch (err) {
    console.error('Failed to load top pages:', err);
  }
}

function renderTopPagesTable(pages) {
  const tbody = document.getElementById('table-top-pages');
  tbody.innerHTML = '';
  const days = document.getElementById('days-select')?.value || 30;
  const utm = document.getElementById('utm-select')?.value || 'all';
  const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';

  if (pages && pages.length) {
    pages.forEach(p => {
      const pageAnalyticsUrl = `/page-analytics?url=${encodeURIComponent(p.url)}&platform=${currentPlatform}&days=${days}${utmParam}`;
      const tr = document.createElement('tr');
      tr.style.cursor = 'pointer';
      tr.title = `Click to view detailed analytics for ${p.url}`;
      tr.innerHTML = `
        <td style="font-family:monospace;color:#38bdf8;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(p.url)}">
          <a href="${pageAnalyticsUrl}" style="color:#38bdf8;text-decoration:none;" onclick="event.stopPropagation();">
            ${escapeHtml(p.url)}
          </a>
        </td>
        <td style="font-weight:600;color:#fff;">${formatNumber(p.views)}</td>
        <td>${formatNumber(p.users)}</td>
        <td style="text-align:right;">
          <a href="${pageAnalyticsUrl}" class="btn-deep-dive" onclick="event.stopPropagation();" title="Open Detailed Info for this Page">
            <span>📊</span> Detailed Info
          </a>
        </td>
      `;

      // Clicking row opens the dedicated detailed info page
      tr.addEventListener('click', () => {
        window.location.href = pageAnalyticsUrl;
      });

      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#64748b;padding:20px;">No matching pages found</td></tr>';
  }
}

async function loadGeoAndReferrers(site, days, utm) {
  try {
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    const res = await fetch(`/api/analytics/geo?platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}${utmParam}`);
    const data = await res.json();

    const tbody = document.getElementById('table-referrers');
    tbody.innerHTML = '';

    if (data.referrers && data.referrers.length) {
      data.referrers.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-weight:500;color:#fff;">${escapeHtml(r.source)}</td>
          <td>${formatNumber(r.count)}</td>
          <td>${formatNumber(r.users)}</td>
        `;
        tbody.appendChild(tr);
      });
    } else {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No referrer data</td></tr>';
    }
  } catch (err) {
    console.error('Failed to load geo/referrers:', err);
  }
}

async function handleManualRefresh() {
  const btn = document.getElementById('btn-refresh-data');
  btn.innerHTML = '⏳ Refreshing Cache...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/analytics/refresh', { method: 'POST' });
    showToast('Daily analytics snapshot refreshed successfully!', 'success');
    await loadAllReportsData();
  } catch (err) {
    showToast('Failed to refresh data', 'error');
  } finally {
    btn.innerHTML = '🔄 Refresh Cache';
    btn.disabled = false;
  }
}

// ==========================================================================
// Granularity Toolbar Logic (Main Dashboard)
// ==========================================================================
function initGranularityButtons() {
  const btnGroup = document.getElementById('granularity-btn-group');
  if (!btnGroup) return;

  const buttons = btnGroup.querySelectorAll('.btn-granularity');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const granularity = btn.getAttribute('data-granularity');
      loadGranularTimeline(granularity);
    });
  });
}

async function loadGranularTimeline(granularity) {
  const site = document.getElementById('site-select').value;
  const days = document.getElementById('days-select').value;
  const badge = document.getElementById('current-granularity-badge');
  const titleElem = document.getElementById('timeline-chart-title');

  if (badge) badge.textContent = `By ${granularity.toUpperCase()}`;

  try {
    const res = await fetch(
      `/api/analytics/granular-timeline?granularity=${granularity}&platform=${currentPlatform}&site=${encodeURIComponent(site)}&days=${days}`
    );
    const data = await res.json();

    if (titleElem) titleElem.textContent = `📈 ${data.title}`;

    // Update Summary Strip
    document.getElementById('gran-peak-slot').textContent = data.peak_slot?.label || '--';
    document.getElementById('gran-peak-users').textContent = formatNumber(data.peak_slot?.users || 0);
    document.getElementById('gran-trough-slot').textContent = data.trough_slot?.label || '--';
    document.getElementById('gran-trough-users').textContent = formatNumber(data.trough_slot?.users || 0);
    document.getElementById('gran-avg-users').textContent = data.avg_users_per_slot || '--';

    // Update Chart
    const ctx = document.getElementById('chart-daily-trends').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    trendChartInstance = new Chart(ctx, {
      type: granularity === 'minute' ? 'bar' : 'line',
      data: {
        labels: data.labels,
        datasets: [
          {
            label: 'Unique Users',
            data: data.users,
            borderColor: '#6366f1',
            backgroundColor: granularity === 'minute' ? '#6366f1' : 'rgba(99, 102, 241, 0.15)',
            borderWidth: 2,
            tension: 0.3,
            fill: granularity !== 'minute',
            yAxisID: 'y'
          },
          {
            label: 'Total Events',
            data: data.events,
            borderColor: '#06b6d4',
            backgroundColor: granularity === 'minute' ? '#06b6d4' : 'transparent',
            borderWidth: 2,
            borderDash: granularity === 'minute' ? [] : [4, 4],
            tension: 0.3,
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
            ticks: { color: '#94a3b8' },
            title: { display: true, text: 'Unique Users', color: '#6366f1' }
          },
          y1: {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#06b6d4' },
            title: { display: true, text: 'Events', color: '#06b6d4' }
          }
        },
        plugins: {
          legend: { labels: { color: '#f8fafc' } }
        }
      }
    });
  } catch (err) {
    console.error('Failed to load granular timeline:', err);
  }
}

// ==========================================================================
// Direct Page Lookup & Table Search Filter
// ==========================================================================
function initDirectPageLookup() {
  const input = document.getElementById('direct-page-url-input');
  const btn = document.getElementById('btn-direct-page-analyze');

  const executeLookup = () => {
    const val = input.value.trim();
    if (!val) {
      showToast('Please enter a page URL to analyze', 'warning');
      return;
    }
    const days = document.getElementById('days-select')?.value || 30;
    const utm = document.getElementById('utm-select')?.value || 'all';
    const utmParam = utm && utm !== 'all' ? `&utm=${encodeURIComponent(utm)}` : '';
    window.location.href = `/page-analytics?url=${encodeURIComponent(val)}&platform=${currentPlatform}&days=${days}${utmParam}`;
  };

  if (btn) btn.addEventListener('click', executeLookup);
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') executeLookup();
    });
  }
}

function initPagesTableFilter() {
  const input = document.getElementById('pages-filter-input');
  if (!input) return;

  let debounceTimer = null;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const q = input.value.trim().toLowerCase();
      if (!q) {
        renderTopPagesTable(allTopPagesData);
        return;
      }

      // First filter currently loaded rows locally
      const localMatches = allTopPagesData.filter(p => p.url.toLowerCase().includes(q));
      if (localMatches.length > 0) {
        renderTopPagesTable(localMatches);
      } else {
        // If no local matches, query backend search endpoint!
        searchBackendPages(q);
      }
    }, 250);
  });
}

async function searchBackendPages(query) {
  try {
    const res = await fetch(`/api/analytics/search-pages?q=${encodeURIComponent(query)}&platform=${currentPlatform}&limit=15`);
    const data = await res.json();
    renderTopPagesTable(data.pages || []);
  } catch (err) {
    console.error('Failed to search pages:', err);
  }
}

// ==========================================================================
// Page Deep-Dive Modal Suite (6 KPIs & 5 Rich Tabs)
// ==========================================================================
function initModalEvents() {
  const modal = document.getElementById('page-deepdive-modal');
  const closeBtn = document.getElementById('modal-close-btn');

  // Close button
  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  // Click on backdrop outside dialog closes modal
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  // Escape key closes modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
      closeModal();
    }
  });

  // Modal navigation tabs
  const tabBtns = document.querySelectorAll('.modal-tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetTabId = btn.getAttribute('data-tab');
      const targetContent = document.getElementById(targetTabId);
      if (targetContent) targetContent.classList.add('active');

      // Trigger redraw of charts on tab switch
      if (targetTabId === 'tab-curves') renderModalCurvesChart(currentModalCurveType);
      if (targetTabId === 'tab-actions') renderModalActionsChart();
      if (targetTabId === 'tab-audience') renderModalDevicesChart();
    });
  });

  // Modal Curves toggle buttons (Tab 1)
  const curveBtns = document.querySelectorAll('#modal-curves-toggle-group .btn-granularity');
  curveBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      curveBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentModalCurveType = btn.getAttribute('data-curve-type');
      renderModalCurvesChart(currentModalCurveType);
    });
  });
}

function closeModal() {
  const modal = document.getElementById('page-deepdive-modal');
  if (modal) modal.style.display = 'none';

  // Destroy modal chart instances to prevent memory leaks
  if (modalCurvesChartInstance) { modalCurvesChartInstance.destroy(); modalCurvesChartInstance = null; }
  if (modalActionsChartInstance) { modalActionsChartInstance.destroy(); modalActionsChartInstance = null; }
  if (modalDevicesChartInstance) { modalDevicesChartInstance.destroy(); modalDevicesChartInstance = null; }
}

async function openPageDeepDive(pageUrl) {
  const modal = document.getElementById('page-deepdive-modal');
  if (!modal) return;

  modal.style.display = 'flex';

  // Set loading placeholders
  document.getElementById('modal-page-url').textContent = pageUrl;
  document.getElementById('modal-page-title').textContent = `Analyzing: ${pageUrl}`;
  document.getElementById('modal-platform-badge').textContent = currentPlatform === 'startupflora' ? '🌸 StartupFlora' : '🏢 Acolyte Living';

  document.getElementById('modal-kpi-views').textContent = '...';
  document.getElementById('modal-kpi-users').textContent = '...';
  document.getElementById('modal-kpi-sessions').textContent = '...';
  document.getElementById('modal-kpi-peakhour').textContent = '...';
  document.getElementById('modal-kpi-conversion').textContent = '...%';
  document.getElementById('modal-kpi-lastseen').textContent = '...';
  document.getElementById('modal-kpi-firstseen').textContent = 'First seen: ...';

  // Switch to Tab 1 by default
  const tabBtns = document.querySelectorAll('.modal-tab-btn');
  tabBtns.forEach((b, i) => b.classList.toggle('active', i === 0));
  document.querySelectorAll('.modal-tab-content').forEach((c, i) => c.classList.toggle('active', i === 0));

  try {
    const days = document.getElementById('days-select')?.value || 30;
    const res = await fetch(`/api/analytics/page-details?url=${encodeURIComponent(pageUrl)}&platform=${currentPlatform}&days=${days}`);
    const data = await res.json();
    currentModalPageData = data;

    // Populate 6 KPI Cards
    const kpis = data.kpis || {};
    document.getElementById('modal-kpi-views').textContent = formatNumber(kpis.total_views || 0);
    document.getElementById('modal-kpi-users').textContent = formatNumber(kpis.unique_users || 0);
    document.getElementById('modal-kpi-sessions').textContent = formatNumber(kpis.total_sessions || 0);
    document.getElementById('modal-kpi-peakhour').textContent = kpis.peak_hour || '--';
    document.getElementById('modal-kpi-conversion').textContent = `${kpis.interaction_rate || 0}%`;
    document.getElementById('modal-kpi-lastseen').textContent = formatDateTime(kpis.last_seen);
    document.getElementById('modal-kpi-firstseen').textContent = `First seen: ${formatDateTime(kpis.first_seen)}`;

    // Populate Tab 1: Curves
    currentModalCurveType = 'daily';
    document.querySelectorAll('#modal-curves-toggle-group .btn-granularity').forEach((b, i) => {
      b.classList.toggle('active', i === 0);
    });
    renderModalCurvesChart('daily');

    // Populate Tab 2: User Actions Table & Donut
    renderModalActionsTable(data.events_breakdown || []);
    renderModalActionsChart();

    // Populate Tab 3: Sources & UTM Tables
    renderModalSourcesTables(data.sources_and_utm || {});

    // Populate Tab 4: Devices & Audience
    renderModalAudienceData(data.devices_and_audience || {});

    // Populate Tab 5: Recent Activity Stream
    renderModalActivityStream(data.recent_activity || []);

  } catch (err) {
    console.error('Failed to load page deep dive:', err);
    showToast('Failed to load deep analytics for this page', 'error');
  }
}

// --------------------------------------------------------------------------
// Modal Tab 1: Traffic Curves Chart
// --------------------------------------------------------------------------
function renderModalCurvesChart(curveType) {
  if (!currentModalPageData || !currentModalPageData.traffic_curves) return;
  const curves = currentModalPageData.traffic_curves;
  const ctx = document.getElementById('modal-chart-curves').getContext('2d');

  if (modalCurvesChartInstance) modalCurvesChartInstance.destroy();

  let labels = [];
  let views = [];
  let users = [];

  if (curveType === 'daily') {
    const daily = curves.daily_trends || [];
    labels = daily.map(d => `${d.date.slice(5)} (${d.day})`);
    views = daily.map(d => d.views);
    users = daily.map(d => d.users);
  } else if (curveType === 'hourly') {
    const hourly = curves.hourly || {};
    labels = hourly.labels || [];
    views = hourly.views || [];
    users = hourly.users || [];
  } else if (curveType === '15min') {
    const min15 = curves.fifteen_min || {};
    labels = min15.labels || [];
    views = min15.views || [];
    users = min15.users || [];
  } else if (curveType === 'dow') {
    const dow = curves.dow || {};
    labels = dow.labels || [];
    views = dow.views || [];
    users = dow.users || [];
  }

  modalCurvesChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Views / Hits',
          data: views,
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.15)',
          borderWidth: 2,
          tension: 0.35,
          fill: true
        },
        {
          label: 'Unique Users',
          data: users,
          borderColor: '#818cf8',
          backgroundColor: 'transparent',
          borderWidth: 2,
          borderDash: [4, 4],
          tension: 0.35
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
        y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
      },
      plugins: {
        legend: { labels: { color: '#f8fafc' } }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Modal Tab 2: Actions Table & Chart
// --------------------------------------------------------------------------
function renderModalActionsTable(events) {
  const tbody = document.getElementById('modal-table-events');
  tbody.innerHTML = '';

  if (events && events.length) {
    events.forEach(e => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight:600;color:#fff;">${escapeHtml(e.name)}</td>
        <td style="color:#38bdf8;">${formatNumber(e.count)}</td>
        <td>${formatNumber(e.users)}</td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No actions recorded</td></tr>';
  }
}

function renderModalActionsChart() {
  if (!currentModalPageData || !currentModalPageData.events_breakdown) return;
  const events = currentModalPageData.events_breakdown;
  const ctx = document.getElementById('modal-chart-actions').getContext('2d');

  if (modalActionsChartInstance) modalActionsChartInstance.destroy();

  const labels = events.map(e => e.name);
  const data = events.map(e => e.count);
  const colors = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6'];

  modalActionsChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 2,
        borderColor: '#0f172a'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#f8fafc', boxWidth: 12 } }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Modal Tab 3: Sources & UTM Tables
// --------------------------------------------------------------------------
function renderModalSourcesTables(sourcesData) {
  // Referrers
  const tbodyRef = document.getElementById('modal-table-referrers');
  tbodyRef.innerHTML = '';
  const referrers = sourcesData.referrers || [];
  if (referrers.length) {
    referrers.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="color:#fff;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(r.source)}">
          ${escapeHtml(r.source)}
        </td>
        <td style="color:#38bdf8;">${formatNumber(r.count)}</td>
        <td>${formatNumber(r.users)}</td>
      `;
      tbodyRef.appendChild(tr);
    });
  } else {
    tbodyRef.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No referrers</td></tr>';
  }

  // UTM Campaigns
  const tbodyUtm = document.getElementById('modal-table-utm');
  tbodyUtm.innerHTML = '';
  const campaigns = sourcesData.campaigns || [];
  if (campaigns.length) {
    campaigns.forEach(c => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="color:#fff;">${escapeHtml(c.campaign)}</td>
        <td style="color:#94a3b8;">${escapeHtml(c.source)} (${escapeHtml(c.medium)})</td>
        <td style="color:#10b981;">${formatNumber(c.count)}</td>
      `;
      tbodyUtm.appendChild(tr);
    });
  } else {
    tbodyUtm.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#64748b;">No campaign data</td></tr>';
  }
}

// --------------------------------------------------------------------------
// Modal Tab 4: Devices & Audience
// --------------------------------------------------------------------------
function renderModalAudienceData(audienceData) {
  // Devices Donut Chart
  renderModalDevicesChart();

  // Browsers Table
  const tbodyBrowser = document.getElementById('modal-table-browsers');
  tbodyBrowser.innerHTML = '';
  const browsers = audienceData.browsers || [];
  if (browsers.length) {
    browsers.forEach(b => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="color:#fff;">${escapeHtml(b.browser)}</td>
        <td style="color:#38bdf8;">${formatNumber(b.count)}</td>
      `;
      tbodyBrowser.appendChild(tr);
    });
  } else {
    tbodyBrowser.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#64748b;">No browser data</td></tr>';
  }

  // Countries Table
  const tbodyCountries = document.getElementById('modal-table-countries');
  tbodyCountries.innerHTML = '';
  const countries = audienceData.countries || [];
  if (countries.length) {
    countries.forEach(c => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="color:#fff;">${escapeHtml(c.name)}</td>
        <td style="color:#10b981;">${formatNumber(c.count)}</td>
      `;
      tbodyCountries.appendChild(tr);
    });
  } else {
    tbodyCountries.innerHTML = '<tr><td colspan="2" style="text-align:center;color:#64748b;">No country data</td></tr>';
  }
}

function renderModalDevicesChart() {
  if (!currentModalPageData || !currentModalPageData.devices_and_audience) return;
  const devices = currentModalPageData.devices_and_audience.device_types || [];
  const ctx = document.getElementById('modal-chart-devices').getContext('2d');

  if (modalDevicesChartInstance) modalDevicesChartInstance.destroy();

  const labels = devices.map(d => d.type);
  const data = devices.map(d => d.count);
  const colors = ['#6366f1', '#06b6d4', '#f59e0b', '#64748b'];

  modalDevicesChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 2,
        borderColor: '#0f172a'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#f8fafc', boxWidth: 12 } }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Modal Tab 5: Recent Activity Stream
// --------------------------------------------------------------------------
function renderModalActivityStream(events) {
  const tbody = document.getElementById('modal-table-recent');
  tbody.innerHTML = '';

  if (events && events.length) {
    events.forEach(e => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-size:0.8rem;color:#94a3b8;white-space:nowrap;">${formatDateTime(e.occurred_at)}</td>
        <td><span class="brand-badge" style="background:rgba(99,102,241,0.15);color:#818cf8;">${escapeHtml(e.event_name)}</span></td>
        <td style="font-family:monospace;font-size:0.78rem;color:#cbd5e1;">${escapeHtml(e.session_id)}</td>
        <td style="font-size:0.82rem;color:#38bdf8;">${escapeHtml(e.device)}</td>
        <td style="font-size:0.82rem;color:#94a3b8;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(e.referrer)}">
          ${escapeHtml(e.referrer)}
        </td>
        <td style="font-size:0.8rem;color:#e2e8f0;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(e.data_summary)}">
          ${escapeHtml(e.data_summary || '--')}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#64748b;">No recent activity</td></tr>';
  }
}

// ==========================================================================
// On-Page Chart Bot Logic
// ==========================================================================
async function handleChartBotSubmit() {
  const input = document.getElementById('chart-bot-input');
  const prompt = input.value.trim();
  if (!prompt) return;

  const btn = document.getElementById('btn-generate-chart');
  btn.innerHTML = '⏳ Generating...';
  btn.disabled = true;

  const site = document.getElementById('site-select').value;
  const days = document.getElementById('days-select').value;

  try {
    const res = await fetch('/api/chartbot/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, site, days: parseInt(days), platform: currentPlatform })
    });
    const chartData = await res.json();

    renderDynamicChart(chartData);
    input.value = '';
    showToast(`Chart generated: ${chartData.title}`, 'success');
  } catch (err) {
    showToast('Failed to generate chart. Please try another query.', 'error');
  } finally {
    btn.innerHTML = '✨ Generate Visual';
    btn.disabled = false;
  }
}

function renderDynamicChart(config) {
  const container = document.getElementById('dynamic-charts-container');
  const chartId = 'dynamic_chart_' + Date.now();

  const card = document.createElement('div');
  card.className = 'card-visual';
  card.style.animation = 'fadeIn 0.4s ease-out';
  card.innerHTML = `
    <div class="card-header">
      <div>
        <h3 class="card-title">🤖 ${escapeHtml(config.title)}</h3>
        <p class="card-description">${escapeHtml(config.description || '')}</p>
      </div>
      <button onclick="this.closest('.card-visual').remove()" style="background:transparent;border:none;color:#94a3b8;font-size:1.2rem;cursor:pointer;">✕</button>
    </div>
    <div class="chart-wrapper">
      <canvas id="${chartId}"></canvas>
    </div>
  `;

  container.prepend(card);

  const ctx = document.getElementById(chartId).getContext('2d');
  new Chart(ctx, {
    type: config.chart_type || 'bar',
    data: {
      labels: config.labels,
      datasets: config.datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: config.chart_type !== 'doughnut' && config.chart_type !== 'pie' ? {
        x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
        y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
      } : {},
      plugins: {
        legend: { labels: { color: '#f8fafc' } }
      }
    }
  });
}

// ==========================================================================
// Helper Utilities
// ==========================================================================
function formatNumber(num) {
  if (num === null || num === undefined) return '0';
  return Number(num).toLocaleString('en-US');
}

function formatDateTime(dtStr) {
  if (!dtStr) return '--';
  try {
    const d = new Date(dtStr);
    return d.toLocaleString('en-IN', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
      hour12: true
    });
  } catch (e) {
    return dtStr;
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

function showToast(msg, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.style.position = 'fixed';
  toast.style.bottom = '24px';
  toast.style.right = '24px';
  toast.style.zIndex = '9999';
  toast.style.padding = '12px 20px';
  toast.style.borderRadius = '10px';
  toast.style.background = type === 'error' ? '#ef4444' : (type === 'success' ? '#10b981' : '#6366f1');
  toast.style.color = '#ffffff';
  toast.style.boxShadow = '0 6px 20px rgba(0,0,0,0.3)';
  toast.style.fontWeight = '500';
  toast.style.fontSize = '0.9rem';
  toast.textContent = msg;

  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}
