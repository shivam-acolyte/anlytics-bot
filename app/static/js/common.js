// Common UI Utilities

function formatNumber(num) {
  if (num === null || num === undefined) return '0';
  return Number(num).toLocaleString();
}

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  const bg = type === 'success' ? '#10b981' : (type === 'error' ? '#ef4444' : '#6366f1');
  toast.style.cssText = `background:${bg};color:#fff;padding:12px 20px;border-radius:8px;font-size:0.88rem;font-weight:500;box-shadow:0 4px 14px rgba(0,0,0,0.3);animation:fadeIn 0.3s ease;`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

document.addEventListener('DOMContentLoaded', () => {
  const currentPlatform = localStorage.getItem('trackingbot_platform') || 'living';
  const globalSelect = document.getElementById('global-platform-select');
  const dbStatusLabel = document.getElementById('db-status-label');
  
  if (globalSelect) {
    globalSelect.value = currentPlatform;
    globalSelect.addEventListener('change', (e) => {
      const p = e.target.value;
      localStorage.setItem('trackingbot_platform', p);
      if (dbStatusLabel) {
        dbStatusLabel.textContent = p === 'startupflora' ? 'StartupFlora (MySQL)' : 'Acolyte Living (PG)';
      }
      if (typeof switchPlatform === 'function') {
        switchPlatform(p);
      } else if (typeof switchPagePlatform === 'function') {
        switchPagePlatform(p);
      } else if (typeof switchChatPlatform === 'function') {
        switchChatPlatform(p);
      } else if (typeof switchSettingsPlatform === 'function') {
        switchSettingsPlatform(p);
      } else if (typeof switchLeadPlatform === 'function') {
        switchLeadPlatform(p);
      } else {
        window.location.reload();
      }
    });
  }

  if (dbStatusLabel) {
    dbStatusLabel.textContent = currentPlatform === 'startupflora' ? 'StartupFlora (MySQL)' : 'Acolyte Living (PG)';
  }
});
