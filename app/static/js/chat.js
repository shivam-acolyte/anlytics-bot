// ==============================================================================
// TrackingBot Futuristic AI Assistant Controller
// Focused on Real Analytics Warehouse Chat with Cyberpunk Holographic Styling
// ==============================================================================

let chatHistory = [];
let currentPlatform = localStorage.getItem('trackingbot_platform') || 'living';
let isListening = false;
let speechRecognizer = null;

const dbMetadata = {
  living: {
    name: "PostgreSQL",
    fullName: "Acolyte Living (PostgreSQL)",
    events: "653,093",
    badge: "🏢 Acolyte Living (PG)"
  },
  startupflora: {
    name: "MySQL",
    fullName: "StartupFlora (MySQL)",
    events: "395,831",
    badge: "🌸 StartupFlora (MySQL)"
  }
};

document.addEventListener('DOMContentLoaded', () => {
  initVoiceRecognition();
  initPlatformSwitcher();
  setupEventListeners();
  updatePlatformUI(currentPlatform);
});

// ==============================================================================
// 1. Voice Recognition & Audio Visualizer
// ==============================================================================
function initVoiceRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (SpeechRecognition) {
    speechRecognizer = new SpeechRecognition();
    speechRecognizer.continuous = false;
    speechRecognizer.interimResults = true;
    speechRecognizer.lang = 'en-US';

    speechRecognizer.onstart = () => {
      setListeningState(true);
    };

    speechRecognizer.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      const input = document.getElementById('chat-input');
      if (input) input.value = transcript;
    };

    speechRecognizer.onerror = (event) => {
      console.warn('Speech recognition notice:', event.error);
      setListeningState(false);
      if (event.error === 'not-allowed') {
        showToast('Microphone access blocked. Please enable browser permissions.', 'error');
      }
    };

    speechRecognizer.onend = () => {
      setListeningState(false);
      const input = document.getElementById('chat-input');
      if (input && input.value.trim().length > 2) {
        sendMessage();
      }
    };
  }
}

function toggleVoiceListening() {
  if (isListening) {
    if (speechRecognizer) {
      try { speechRecognizer.stop(); } catch (e) {}
    }
    setListeningState(false);
  } else {
    if (speechRecognizer) {
      try {
        speechRecognizer.start();
      } catch (e) {
        console.error('Speech recognition start failed:', e);
        simulateVoiceListening();
      }
    } else {
      simulateVoiceListening();
    }
  }
}

// Fallback voice simulation for browsers without native Web Speech
function simulateVoiceListening() {
  setListeningState(true);
  const sampleQueries = [
    "When is user traffic lowest?",
    "What are our peak active hours?",
    "What are the top 5 visited pages?",
    "Show multi-website traffic distribution"
  ];
  const query = sampleQueries[Math.floor(Math.random() * sampleQueries.length)];

  const input = document.getElementById('chat-input');
  let charIdx = 0;
  input.value = '';

  const typingInterval = setInterval(() => {
    charIdx += 2;
    input.value = query.substring(0, charIdx);
    if (charIdx >= query.length) {
      clearInterval(typingInterval);
      setTimeout(() => {
        setListeningState(false);
        sendMessage();
      }, 650);
    }
  }, 45);
}

function setListeningState(active) {
  isListening = active;
  const voiceStrip = document.getElementById('ai-voice-strip');
  const indicator = document.getElementById('voice-indicator-text');

  if (active) {
    if (voiceStrip) voiceStrip.classList.add('listening');
    if (indicator) {
      indicator.textContent = 'Listening to your voice... Speak your analytical question';
      indicator.style.color = '#00f0ff';
    }
  } else {
    if (voiceStrip) voiceStrip.classList.remove('listening');
    if (indicator) {
      indicator.textContent = 'Click microphone to speak or type your question below';
      indicator.style.color = 'var(--ai-text-dim)';
    }
  }
}

// ==============================================================================
// 2. Database Warehouse Switcher
// ==============================================================================
function initPlatformSwitcher() {
  const btnLiving = document.getElementById('btn-db-living');
  const btnFlora = document.getElementById('btn-db-startupflora');

  if (btnLiving) {
    btnLiving.addEventListener('click', () => switchChatPlatform('living'));
  }
  if (btnFlora) {
    btnFlora.addEventListener('click', () => switchChatPlatform('startupflora'));
  }

  // Central floating dock AI orb - toggles voice recognition & focuses chat input
  const dockAi = document.getElementById('btn-dock-ai');
  if (dockAi) {
    dockAi.addEventListener('click', (e) => {
      e.preventDefault();
      toggleVoiceListening();
      const input = document.getElementById('chat-input');
      if (input) {
        input.focus();
        input.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }
}

function switchChatPlatform(platform) {
  if (currentPlatform === platform) return;
  currentPlatform = platform;
  localStorage.setItem('trackingbot_platform', platform);
  updatePlatformUI(platform);

  chatHistory = []; // Reset context for new database
  const info = dbMetadata[platform] || dbMetadata.living;
  
  appendMessage('bot', `Switched AI Analyst warehouse context to **${info.fullName}** (${info.events} events). You can now ask analytics queries specific to this database.`);
  updateHologramSpeech(`Switched to ${info.fullName}. Ready for your analytics queries.`);
  showToast(`Active Warehouse: ${info.fullName}`, 'info');
}

function updatePlatformUI(platform) {
  const isLiving = platform === 'living';
  const info = dbMetadata[platform] || dbMetadata.living;

  // Buttons in sidebar
  const btnLiving = document.getElementById('btn-db-living');
  const btnFlora = document.getElementById('btn-db-startupflora');
  if (btnLiving) btnLiving.classList.toggle('active', isLiving);
  if (btnFlora) btnFlora.classList.toggle('active', !isLiving);

  // Topbar badge & Telemetry
  const topbarBadge = document.getElementById('topbar-platform-badge');
  if (topbarBadge) topbarBadge.textContent = info.badge;

  const telName = document.getElementById('telemetry-db-name');
  if (telName) telName.textContent = info.name;

  const telEvents = document.getElementById('telemetry-events-count');
  if (telEvents) telEvents.textContent = info.events;

  // Global navbar synchronization
  const globalSelect = document.getElementById('global-platform-select');
  if (globalSelect && globalSelect.value !== platform) {
    globalSelect.value = platform;
  }
  const dbStatusLabel = document.getElementById('db-status-label');
  if (dbStatusLabel) {
    dbStatusLabel.textContent = isLiving ? 'Acolyte Living (PG)' : 'StartupFlora (MySQL)';
  }
}

// ==============================================================================
// 3. Setup Listeners (Inputs, Prompts, Action Pills)
// ==============================================================================
function setupEventListeners() {
  const input = document.getElementById('chat-input');
  const btnSend = document.getElementById('btn-send-chat');
  const btnMic = document.getElementById('btn-voice-mic');
  const btnInputMic = document.getElementById('btn-input-mic-trigger');
  const btnClear = document.getElementById('btn-clear-chat');

  if (btnSend) btnSend.addEventListener('click', sendMessage);
  if (btnMic) btnMic.addEventListener('click', toggleVoiceListening);
  if (btnInputMic) btnInputMic.addEventListener('click', toggleVoiceListening);

  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendMessage();
    });
  }

  if (btnClear) {
    btnClear.addEventListener('click', () => {
      chatHistory = [];
      const feed = document.getElementById('chat-feed');
      feed.innerHTML = `
        <div class="ai-msg-row bot">
          <div class="ai-msg-avatar bot">AI</div>
          <div class="ai-msg-bubble">
            <h3 style="font-size:1.05rem;color:#00f0ff;margin:0 0 6px 0;font-family:var(--font-heading);">
              Session Cleared. Ready for new analytics queries!
            </h3>
            <p style="margin:0;color:#e2e8f0;">
              Ask anything about your ${dbMetadata[currentPlatform]?.fullName || 'database'}.
            </p>
          </div>
        </div>
      `;
      updateHologramSpeech("Chat session reset. Ready for your next query.");
      showToast("Chat history cleared", "info");
    });
  }

  // Handle all prompt buttons (sidebar pills, chips, and action pills)
  document.querySelectorAll('[data-prompt]').forEach(el => {
    el.addEventListener('click', () => {
      const prompt = el.dataset.prompt;
      if (prompt) {
        input.value = prompt;
        sendMessage();
      }
    });
  });
}

// ==============================================================================
// 4. Send Message & Chat Processing
// ==============================================================================
async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  // Append user message to feed
  appendMessage('user', text);
  input.value = '';

  // Update topbar speech status
  updateHologramSpeech(`Analyzing "${text.length > 40 ? text.substring(0, 37) + '...' : text}"...`);

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

    // Extract first sentence for topbar speech banner
    let firstSentence = data.answer.split('\n')[0].replace(/[#*`]/g, '').trim();
    if (firstSentence.length > 75) firstSentence = firstSentence.substring(0, 72) + '...';
    updateHologramSpeech(firstSentence || "Analytics computation complete.");

  } catch (err) {
    removeTypingIndicator(typingId);
    appendMessage('bot', '⚠️ Error contacting analytics engine. Please check database connection.');
    updateHologramSpeech("Database connection error encountered.");
  }
}

function updateHologramSpeech(text) {
  const el = document.getElementById('ai-speech-status');
  if (el) {
    el.style.opacity = '0';
    el.style.transform = 'translateY(2px)';
    el.style.transition = 'all 0.2s';
    setTimeout(() => {
      el.textContent = text;
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    }, 200);
  }
}

function appendMessage(sender, text, sql = null, chart = null, engine = null) {
  const feed = document.getElementById('chat-feed');
  const msgRow = document.createElement('div');
  msgRow.className = `ai-msg-row ${sender}`;

  const avatar = document.createElement('div');
  avatar.className = `ai-msg-avatar ${sender}`;
  avatar.innerText = sender === 'user' ? '👤' : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'ai-msg-bubble';

  // Format markdown into styled HTML
  bubble.innerHTML = formatMarkdown(text);

  // Engine tag
  if (engine) {
    const engineTag = document.createElement('div');
    engineTag.style.cssText = 'font-size:0.7rem;color:#00f0ff;margin-top:8px;font-weight:600;display:flex;align-items:center;gap:4px;';
    engineTag.innerHTML = `<span>⚡</span> Powered by ${engine}`;
    bubble.appendChild(engineTag);
  }

  // Chart embedding
  if (chart) {
    const chartId = 'chat_chart_' + Date.now();
    const chartBox = document.createElement('div');
    chartBox.style.cssText = 'margin-top:12px;background:#090d19;padding:12px;border-radius:12px;border:1px solid rgba(0,240,255,0.25);min-height:220px;';
    chartBox.innerHTML = `<h4 style="font-size:0.85rem;color:#fff;margin-bottom:8px;font-family:var(--font-heading);">📊 ${chart.title || 'Visual Summary'}</h4><canvas id="${chartId}"></canvas>`;
    bubble.appendChild(chartBox);

    setTimeout(() => {
      const ctx = document.getElementById(chartId).getContext('2d');
      new Chart(ctx, {
        type: chart.type || 'bar',
        data: {
          labels: chart.labels,
          datasets: (chart.datasets || []).map(ds => ({
            ...ds,
            backgroundColor: ds.backgroundColor || 'rgba(0, 240, 255, 0.45)',
            borderColor: ds.borderColor || '#00f0ff',
            borderRadius: 6
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#f8fafc' } }
          },
          scales: {
            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
          }
        }
      });
    }, 100);
  }

  // SQL transparency toggle
  if (sql) {
    const sqlToggle = document.createElement('div');
    sqlToggle.style.cssText = 'margin-top:10px;font-size:0.78rem;';
    sqlToggle.innerHTML = `
      <details>
        <summary style="cursor:pointer;color:#38bdf8;font-weight:600;">🔍 View Executed SQL Query</summary>
        <pre style="background:rgba(0,0,0,0.5);padding:8px 10px;border-radius:8px;overflow-x:auto;color:#cbd5e1;margin-top:4px;border:1px solid rgba(56,189,248,0.2);"><code>${escapeHtml(sql)}</code></pre>
      </details>
    `;
    bubble.appendChild(sqlToggle);
  }

  msgRow.appendChild(avatar);
  msgRow.appendChild(bubble);
  feed.appendChild(msgRow);

  // Auto scroll
  feed.scrollTop = feed.scrollHeight;
}

function showTypingIndicator() {
  const feed = document.getElementById('chat-feed');
  const id = 'typing_' + Date.now();
  const el = document.createElement('div');
  el.id = id;
  el.className = 'ai-msg-row bot';
  el.innerHTML = `
    <div class="ai-msg-avatar bot">AI</div>
    <div class="ai-msg-bubble" style="color:#94a3b8;font-style:italic;display:flex;align-items:center;gap:8px;">
      <span style="display:inline-block;animation:spin 1s infinite linear;">⚡</span> Computing analytics query on warehouse...
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
    .replace(/^### (.*$)/gim, '<h3 style="font-size:1.05rem;color:#00f0ff;margin:8px 0 6px 0;font-family:var(--font-heading);">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 style="font-size:1.15rem;color:#fff;margin:10px 0 6px 0;font-family:var(--font-heading);">$1</h2>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong style="color:#fff;">$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/`(.*?)`/gim, '<code style="background:#050813;padding:2px 6px;border-radius:4px;color:#00f0ff;font-size:0.86em;border:1px solid rgba(0,240,255,0.2);">$1</code>')
    .replace(/^\- (.*$)/gim, '<li style="margin-left:16px;margin-bottom:4px;color:#cbd5e1;">$1</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
