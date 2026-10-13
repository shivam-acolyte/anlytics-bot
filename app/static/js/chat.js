// Dedicated AI Chatbot Console Logic

let chatHistory = [];
let currentPlatform = localStorage.getItem('trackingbot_platform') || 'living';

document.addEventListener('DOMContentLoaded', () => {
  initChatPlatformSwitcher();

  const input = document.getElementById('chat-input');
  const btnSend = document.getElementById('btn-send-chat');

  btnSend.addEventListener('click', sendMessage);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  // Preset chips click handler
  document.querySelectorAll('.preset-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.innerText.trim();
      sendMessage();
    });
  });
});

function initChatPlatformSwitcher() {
  updateChatPlatformUI(currentPlatform);

  // Global platform select in navbar
  const globalSelect = document.getElementById('global-platform-select');
  if (globalSelect) {
    globalSelect.value = currentPlatform;
    globalSelect.addEventListener('change', (e) => switchChatPlatform(e.target.value));
  }

  // Navbar platform buttons (fallback)
  const navLiving = document.getElementById('btn-platform-living');
  const navFlora = document.getElementById('btn-platform-startupflora');
  if (navLiving) navLiving.addEventListener('click', () => switchChatPlatform('living'));
  if (navFlora) navFlora.addEventListener('click', () => switchChatPlatform('startupflora'));

  // Chat sidebar choice buttons
  const choiceLiving = document.getElementById('chat-choice-living');
  const choiceFlora = document.getElementById('chat-choice-startupflora');
  if (choiceLiving) choiceLiving.addEventListener('click', () => switchChatPlatform('living'));
  if (choiceFlora) choiceFlora.addEventListener('click', () => switchChatPlatform('startupflora'));
}

function switchChatPlatform(platform) {
  if (currentPlatform === platform) return;
  currentPlatform = platform;
  localStorage.setItem('trackingbot_platform', platform);
  updateChatPlatformUI(platform);

  chatHistory = []; // Reset chat history for new platform
  const pName = platform === 'startupflora' ? 'StartupFlora (MySQL)' : 'Acolyte Living (PostgreSQL)';
  appendMessage('bot', `Switched AI Analyst context to **${pName}**. You can now ask analytics questions specific to this platform!`);
}

function updateChatPlatformUI(platform) {
  const isLiving = platform === 'living';

  const globalSelect = document.getElementById('global-platform-select');
  if (globalSelect && globalSelect.value !== platform) {
    globalSelect.value = platform;
  }

  const navLiving = document.getElementById('btn-platform-living');
  const navFlora = document.getElementById('btn-platform-startupflora');
  if (navLiving) navLiving.classList.toggle('active', isLiving);
  if (navFlora) navFlora.classList.toggle('active', !isLiving);

  const choiceLiving = document.getElementById('chat-choice-living');
  const choiceFlora = document.getElementById('chat-choice-startupflora');
  if (choiceLiving) choiceLiving.classList.toggle('active', isLiving);
  if (choiceFlora) choiceFlora.classList.toggle('active', !isLiving);

  const statusLabel = document.getElementById('db-status-label');
  if (statusLabel) {
    statusLabel.textContent = isLiving ? 'Acolyte Living (PG)' : 'StartupFlora (MySQL)';
  }

  const desc = document.getElementById('chat-db-context-desc');
  if (desc) {
    desc.innerHTML = isLiving
      ? 'Directly querying PostgreSQL <code>acolye-living-v2</code> (647k+ events).'
      : 'Directly querying MySQL <code>insights_db</code> (391k+ events).';
  }
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  // Append user message
  appendMessage('user', text);
  input.value = '';

  // Show typing indicator
  const typingId = showTypingIndicator();

  try {
    const res = await fetch('/api/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: chatHistory, platform: currentPlatform })
    });
    const data = await res.json();
    removeTypingIndicator(typingId);

    // Save history
    chatHistory.push({ role: 'user', content: text });
    chatHistory.push({ role: 'assistant', content: data.answer });

    appendMessage('bot', data.answer, data.sql, data.chart, data.engine);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendMessage('bot', '⚠️ Error contacting analytics engine. Please check your database connection.');
  }
}

function appendMessage(sender, text, sql = null, chart = null, engine = null) {
  const feed = document.getElementById('chat-feed');
  const msgEl = document.createElement('div');
  msgEl.className = `chat-message ${sender}`;

  const avatar = document.createElement('div');
  avatar.className = `chat-avatar ${sender}`;
  avatar.innerText = sender === 'user' ? '👤' : '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';

  // Format simple markdown into HTML
  let formattedText = formatMarkdown(text);
  bubble.innerHTML = formattedText;

  // Engine tag
  if (engine) {
    const engineTag = document.createElement('div');
    engineTag.style.cssText = 'font-size:0.7rem;color:#818cf8;margin-top:6px;font-weight:600;';
    engineTag.innerText = `Powered by ${engine}`;
    bubble.appendChild(engineTag);
  }

  // Optional Chart embed
  if (chart) {
    const chartId = 'chat_chart_' + Date.now();
    const chartBox = document.createElement('div');
    chartBox.style.cssText = 'margin-top:12px;background:#090d16;padding:12px;border-radius:8px;border:1px solid rgba(255,255,255,0.06);min-height:220px;';
    chartBox.innerHTML = `<h4 style="font-size:0.85rem;color:#fff;margin-bottom:8px;">📊 ${chart.title || 'Visual Summary'}</h4><canvas id="${chartId}"></canvas>`;
    bubble.appendChild(chartBox);

    setTimeout(() => {
      const ctx = document.getElementById(chartId).getContext('2d');
      new Chart(ctx, {
        type: chart.type || 'bar',
        data: {
          labels: chart.labels,
          datasets: chart.datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#f8fafc' } } }
        }
      });
    }, 100);
  }

  // Optional SQL transparency toggle
  if (sql) {
    const sqlToggle = document.createElement('div');
    sqlToggle.className = 'chat-sql-toggle';
    sqlToggle.innerHTML = `
      <details>
        <summary style="cursor:pointer;color:#94a3b8;font-weight:500;">🔍 View Executed SQL Query</summary>
        <pre class="sql-code"><code>${escapeHtml(sql)}</code></pre>
      </details>
    `;
    bubble.appendChild(sqlToggle);
  }

  msgEl.appendChild(avatar);
  msgEl.appendChild(bubble);
  feed.appendChild(msgEl);

  // Auto scroll
  feed.scrollTop = feed.scrollHeight;
}

function showTypingIndicator() {
  const feed = document.getElementById('chat-feed');
  const id = 'typing_' + Date.now();
  const el = document.createElement('div');
  el.id = id;
  el.className = 'chat-message bot';
  el.innerHTML = `
    <div class="chat-avatar bot">🤖</div>
    <div class="chat-bubble" style="color:#94a3b8;font-style:italic;">
      Analyzing database and computing insights...
    </div>
  `;
  feed.appendChild(el);
  feed.scrollTop = feed.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/^### (.*$)/gim, '<h3 style="font-size:1.05rem;color:#fff;margin-bottom:8px;">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 style="font-size:1.15rem;color:#fff;margin-bottom:8px;">$1</h2>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong style="color:#fff;">$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/`(.*?)`/gim, '<code style="background:#090d16;padding:2px 6px;border-radius:4px;color:#38bdf8;font-size:0.85em;">$1</code>')
    .replace(/^\- (.*$)/gim, '<li style="margin-left:16px;margin-bottom:4px;">$1</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
