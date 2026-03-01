/**
 * casiopy-app — lógica del frontend
 * Único punto de contacto: el gateway (URL cargada desde /config).
 */

// ── Estado global ──────────────────────────────────────────────────────────
let cfg = {
  gateway_url:    'http://127.0.0.1:8800',
  gateway_ws:     'ws://127.0.0.1:8800',
  monitoring_url: 'http://127.0.0.1:8900',
};
let ws       = null;
let mediaRec = null;
let isRec    = false;
let isSending = false;

const USER_ID = 'viewer_' + Math.random().toString(36).slice(2, 7);

// Servicios a gestionar (en orden de inicio).
// El gateway es especial: se inicia llamando directamente a monitoring-service
// (no puede usar el gateway para iniciarse a sí mismo).
const SVCS = [
  { id: 'gateway',         label: 'Gateway',          critical: true,  bootstrap: true  },
  { id: 'memory-postgres', label: 'Memoria DB',       critical: false, bootstrap: false },
  { id: 'memory-api',      label: 'Memoria API',      critical: false, bootstrap: false },
  { id: 'conversation',    label: 'Conversación',     critical: true,  bootstrap: false },
  { id: 'tts-blips',       label: 'TTS Blips',        critical: false, bootstrap: false },
  { id: 'tts-router',      label: 'TTS Router',       critical: false, bootstrap: false },
  { id: 'tts-casiopy',     label: 'TTS Casiopy',      critical: false, bootstrap: false },
  { id: 'face',            label: 'Avatar 2D',        critical: false, bootstrap: false },
  { id: 'stt',             label: 'STT (Voz)',        critical: false, bootstrap: false },
];

// ── Inicialización ─────────────────────────────────────────────────────────
async function init() {
  try {
    const r = await fetch('/config');
    if (r.ok) cfg = await r.json();
  } catch (_) { /* usar defaults */ }

  await refreshStatuses();
  startLogsPolling();

  if (isCoreReady()) {
    showChatView();
  } else {
    setLoadingStatus('Servicios offline. Pulsa "Iniciar servicios" para comenzar.');
  }
}

function isCoreReady() {
  return document.querySelector('#svc-conversation .svc-dot')?.dataset.status === 'online';
}

// ── Carga y estados de servicios ───────────────────────────────────────────
async function refreshStatuses() {
  try {
    const r = await fetch(`/mon/api/services/status`);
    if (!r.ok) return;
    const statuses = await r.json();
    SVCS.forEach(s => {
      const svc  = statuses[s.id] ?? {};
      const st   = svc.status ?? 'offline';
      const rtms = svc.response_time_ms ?? null;
      updateSvcUI(s.id, st, rtms);
    });
    updateProgress();
  } catch (_) {
    setLoadingStatus('No se puede conectar al monitoring-service.');
  }
}

function updateSvcUI(id, status, responseTimeMs = null) {
  // Loading view
  const row = document.getElementById(`svc-${id}`);
  if (row) {
    const dot     = row.querySelector('.svc-dot');
    const text    = row.querySelector('.svc-status-text');
    const rt      = row.querySelector('.svc-response-time');
    const stopBtn = row.querySelector('.svc-stop-btn');
    dot.dataset.status = status;
    text.textContent   = status;
    if (rt)      rt.textContent = responseTimeMs != null ? `${responseTimeMs.toFixed(0)} ms` : '';
    if (stopBtn) stopBtn.classList.toggle('visible', status === 'online');
  }
  // Chat header mini dots
  const mini = document.querySelector(`[data-svc="${id}"]`);
  if (mini) mini.dataset.status = status;
}

function updateProgress() {
  const total   = SVCS.length;
  const online  = SVCS.filter(s =>
    document.querySelector(`#svc-${s.id} .svc-dot`)?.dataset.status === 'online'
  ).length;
  const pct = Math.round((online / total) * 100);
  document.getElementById('progressFill').style.width = pct + '%';
  setLoadingStatus(`${online} de ${total} servicios activos.`);
  document.getElementById('goToChatBtn').disabled = !isCoreReady();
}

function setLoadingStatus(msg) {
  const el = document.getElementById('loadingStatus');
  if (el) el.textContent = msg;
}

// ── Inicio de servicios ────────────────────────────────────────────────────
async function startServices() {
  const btn = document.getElementById('startBtn');
  btn.disabled = true;
  setLoadingStatus('Iniciando servicios…');

  for (const svc of SVCS) {
    const current = document.querySelector(`#svc-${svc.id} .svc-dot`)?.dataset.status;
    if (current === 'online') continue;

    updateSvcUI(svc.id, 'starting');
    setLoadingStatus(`Iniciando ${svc.label}…`);

    // Siempre usamos monitoring-service para arrancar servicios:
    // gateway podría no estar corriendo aún y no puede enrutarse a sí mismo.
    const startUrl = `/mon/api/services/${svc.id}/start`;

    try {
      const r = await fetch(startUrl, { method: 'POST' });
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.status === 'online') {
        updateSvcUI(svc.id, 'online');
      } else {
        const detail = data.detail ?? data.status ?? r.statusText;
        updateSvcUI(svc.id, svc.critical ? 'error' : 'offline');
        if (svc.critical) {
          setLoadingStatus(`Error: no se pudo iniciar ${svc.label}. ${detail}`);
          btn.disabled = false;
          updateProgress();
          return;
        } else {
          toast(`${svc.label}: ${detail}`, 'warning');
        }
      }
    } catch (e) {
      updateSvcUI(svc.id, svc.critical ? 'error' : 'offline');
      if (svc.critical) {
        setLoadingStatus(`Error de red al iniciar ${svc.label}.`);
        btn.disabled = false;
        updateProgress();
        return;
      }
    }
  }

  updateProgress();
  btn.disabled = false;

  if (isCoreReady()) {
    setLoadingStatus('✓ Servicios listos. Accediendo al chat…');
    setTimeout(showChatView, 900);
  }
}

// ── Vistas ─────────────────────────────────────────────────────────────────
function showChatView() {
  document.getElementById('loadingView').classList.add('hidden');
  document.getElementById('chatView').classList.remove('hidden');
  // Reposicionar panel de logs: oculto por defecto en chat (toggle con botón 📋)
  const lp = document.getElementById('logPanel');
  if (lp) { lp.classList.add('chat-mode', 'hidden'); }
  connectWebSocket();
  // Sync mini dots
  SVCS.forEach(s => {
    const st = document.querySelector(`#svc-${s.id} .svc-dot`)?.dataset.status ?? 'offline';
    updateSvcUI(s.id, st);
  });
  document.getElementById('messageInput').focus();
  appendMessage('bot', '¡Hola! Soy Casiopy. ¿En qué puedo ayudarte hoy?', null);
}

// ── WebSocket ──────────────────────────────────────────────────────────────
function connectWebSocket() {
  if (ws) ws.close();
  const url = cfg.gateway_ws.replace(/^http/, 'ws') + '/ws';
  ws = new WebSocket(url);

  ws.onopen = () => {
    setWsStatus(true);
    ws.send(JSON.stringify({ type: 'subscribe', topics: ['utterance', 'emotion', 'service-status'] }));
  };

  ws.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch (_) { return; }

    if (msg.type === 'emotion') {
      const badge = document.getElementById('emotionBadge');
      badge.textContent = msg.data?.emotion ?? '—';
    } else if (msg.type === 'service-status') {
      const { id, action } = msg.data ?? {};
      if (id) {
        const st = action === 'started' ? 'online'
                 : action === 'stopped' ? 'offline'
                 : action === 'starting' || action === 'restarting' ? 'starting'
                 : 'offline';
        updateSvcUI(id, st);
      }
    }
  };

  ws.onclose = () => {
    setWsStatus(false);
    setTimeout(connectWebSocket, 4000);
  };

  ws.onerror = () => setWsStatus(false);
}

function setWsStatus(ok) {
  const el = document.getElementById('wsStatus');
  el.className = ok ? 'connected' : 'disconnected';
  el.title = ok ? 'WebSocket conectado' : 'WebSocket desconectado';
}

// ── Envío de mensaje ───────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('messageInput');
  const text  = input.value.trim();
  if (!text || isSending) return;

  isSending = true;
  input.value = '';
  input.style.height = '';
  document.getElementById('sendBtn').disabled = true;

  appendMessage('user', text, null);
  const typingId = showTyping();

  const ttsMode = document.getElementById('ttsModeSelect').value;

  try {
    const r = await fetch(`${cfg.gateway_url}/orchestrate/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, user_id: USER_ID, tts_mode: ttsMode }),
    });

    removeTyping(typingId);

    if (!r.ok) {
      const detail = (await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`;
      appendMessage('bot', `[Error: ${detail}]`, null);
      toast(detail, 'error');
    } else {
      const data = await r.json();
      appendMessage('bot', data.reply, data.emotion);
      if (data.audio_b64) await playAudio(data.audio_b64);
    }
  } catch (e) {
    removeTyping(typingId);
    appendMessage('bot', '[Sin conexión al gateway]', null);
    toast('No se puede conectar al gateway', 'error');
  }

  isSending = false;
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('messageInput').focus();
}

function handleInputKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ── Mensajes en el chat ────────────────────────────────────────────────────
function appendMessage(role, text, emotion) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `msg ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = text;
  div.appendChild(bubble);

  if (role === 'bot' && emotion) {
    const meta = document.createElement('div');
    meta.className = 'msg-emotion';
    meta.textContent = emotion;
    div.appendChild(meta);
  }

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function showTyping() {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.id = 'typing-' + Date.now();
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble typing-indicator';
  bubble.innerHTML = '<span></span><span></span><span></span>';
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div.id;
}

function removeTyping(id) {
  document.getElementById(id)?.remove();
}

// ── Audio TTS ──────────────────────────────────────────────────────────────
async function playAudio(b64) {
  try {
    const bytes = atob(b64);
    const buf   = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);
    const blob  = new Blob([buf], { type: 'audio/wav' });
    const url   = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play();
  } catch (e) {
    console.warn('Error reproduciendo audio:', e);
  }
}

// ── STT ────────────────────────────────────────────────────────────────────
async function toggleRecording() {
  if (isRec) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];

    // Elige el formato compatible
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    mediaRec = new MediaRecorder(stream, { mimeType });
    mediaRec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
    mediaRec.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(chunks, { type: mimeType });
      await transcribeAudio(blob);
    };
    mediaRec.start();
    isRec = true;
    updateSttBtn();
  } catch (e) {
    toast('No se puede acceder al micrófono', 'error');
  }
}

function stopRecording() {
  if (mediaRec && mediaRec.state !== 'inactive') mediaRec.stop();
  isRec = false;
  updateSttBtn();
}

function updateSttBtn() {
  const btn = document.getElementById('sttBtn');
  btn.classList.toggle('recording', isRec);
  btn.textContent = isRec ? '⏹' : '🎤';
  btn.title = isRec ? 'Detener grabación' : 'Hablar (STT)';
}

async function transcribeAudio(blob) {
  const fd = new FormData();
  fd.append('audio', blob, 'recording.webm');
  try {
    const r = await fetch(`${cfg.gateway_url}/orchestrate/stt`, {
      method: 'POST',
      body: fd,
    });
    if (r.ok) {
      const data = await r.json();
      const input = document.getElementById('messageInput');
      input.value = data.text;
      autoResize(input);
      input.focus();
    } else {
      toast('Error en transcripción', 'error');
    }
  } catch (_) {
    toast('STT no disponible', 'warning');
  }
}

// ── Toast ──────────────────────────────────────────────────────────────────
let toastTimer = null;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent  = msg;
  el.className    = 'show' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, 3500);
}

// ── Services drawer (chat view) ────────────────────────────────────────────
const SERVICE_PORTS = {
  gateway: 8800, 'memory-postgres': 8821, 'memory-api': 8820,
  conversation: 8801, 'tts-blips': 8805, 'tts-router': 8810,
  'tts-casiopy': 8815, face: 8804, stt: 8803,
};

let _lastStatuses  = {};   // {id: {status, response_time_ms}}
let _drawerOpen    = false;
let _drawerTimer   = null;

function toggleSvcDrawer() {
  _drawerOpen = !_drawerOpen;
  const drawer  = document.getElementById('svcDrawer');
  const overlay = document.getElementById('svcDrawerOverlay');
  if (!drawer) return;
  drawer.classList.remove('hidden');
  drawer.classList.toggle('open', _drawerOpen);
  overlay?.classList.toggle('show', _drawerOpen);
  const btn = document.getElementById('svcDrawerBtn');
  if (btn) btn.style.opacity = _drawerOpen ? '1' : '0.75';
  if (_drawerOpen) {
    _fetchAndRenderDrawer();
    _drawerTimer = setInterval(_fetchAndRenderDrawer, 4000);
  } else {
    clearInterval(_drawerTimer);
  }
}

async function _fetchAndRenderDrawer() {
  try {
    const r = await fetch('/mon/api/services/status');
    if (!r.ok) return;
    _lastStatuses = await r.json();
    _renderDrawer();
    // Sync mini-dots and loading view rows too
    SVCS.forEach(s => {
      const svc = _lastStatuses[s.id] ?? {};
      updateSvcUI(s.id, svc.status ?? 'offline', svc.response_time_ms ?? null);
    });
    updateProgress();
  } catch (_) {}
}

function _renderDrawer() {
  const list = document.getElementById('svcDrawerList');
  if (!list) return;
  list.innerHTML = SVCS.map(s => {
    const svc  = _lastStatuses[s.id] ?? {};
    const st   = svc.status ?? 'offline';
    const rt   = svc.response_time_ms != null ? `${Math.round(svc.response_time_ms)}ms` : '';
    const port = SERVICE_PORTS[s.id] ? `:${SERVICE_PORTS[s.id]}` : '';
    const isOnline = st === 'online';
    const startBtn = !isOnline
      ? `<button class="sd-btn start" onclick="drawerStartSvc('${s.id}')" title="Iniciar">▶</button>` : '';
    const stopBtn  = isOnline
      ? `<button class="sd-btn stop"  onclick="drawerStopSvc('${s.id}')"  title="Detener">⏹</button>` : '';
    return `<div class="sd-row" id="sd-${s.id}">
      <span class="sd-dot" data-status="${st}"></span>
      <span class="sd-label">${s.label}</span>
      <span class="sd-port">${port}</span>
      <span class="sd-rt">${rt}</span>
      ${startBtn}${stopBtn}
    </div>`;
  }).join('');
}

async function drawerStartSvc(id) {
  _patchDrawerRow(id, 'starting');
  try {
    const r = await fetch(`/mon/api/services/${id}/start`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg = d.detail ?? `Error ${r.status} al iniciar ${id}`;
      toast(msg, 'error');
      _patchDrawerRow(id, 'error');
      updateProgress();
      return;
    }
    _patchDrawerRow(id, d.status ?? 'offline', d.response_time_ms);
    updateSvcUI(id, d.status ?? 'offline');
  } catch (_) { _patchDrawerRow(id, 'error'); }
  updateProgress();
}

async function drawerStopSvc(id) {
  _patchDrawerRow(id, 'starting');
  try {
    const r = await fetch(`/mon/api/services/${id}/stop`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    _patchDrawerRow(id, d.status ?? (r.ok ? 'offline' : 'error'));
    updateSvcUI(id, d.status ?? 'offline');
  } catch (_) { _patchDrawerRow(id, 'offline'); }
  updateProgress();
}

function _patchDrawerRow(id, status, rtms) {
  const row = document.getElementById(`sd-${id}`);
  if (!row) return;
  const dot  = row.querySelector('.sd-dot');
  const rt   = row.querySelector('.sd-rt');
  const svc  = SVCS.find(s => s.id === id);
  if (dot)  dot.dataset.status = status;
  if (rt && rtms != null) rt.textContent = `${Math.round(rtms)}ms`;
  // Rebuild buttons
  const isOnline = status === 'online';
  const startBtn = !isOnline ? `<button class="sd-btn start" onclick="drawerStartSvc('${id}')" title="Iniciar">▶</button>` : '';
  const stopBtn  =  isOnline ? `<button class="sd-btn stop"  onclick="drawerStopSvc('${id}')"  title="Detener">⏹</button>` : '';
  const old = row.querySelectorAll('.sd-btn');
  old.forEach(b => b.remove());
  row.insertAdjacentHTML('beforeend', startBtn + stopBtn);
}

// ── Parada de servicios ────────────────────────────────────────────────────
async function stopSvc(id) {
  updateSvcUI(id, 'starting'); // visual feedback "deteniéndose"
  try {
    const r = await fetch(`/mon/api/services/${id}/stop`, { method: 'POST' });
    const data = await r.json().catch(() => ({}));
    updateSvcUI(id, data.status ?? (r.ok ? 'offline' : 'error'));
  } catch (_) {
    updateSvcUI(id, 'offline');
  }
  updateProgress();
}

async function stopAllServices() {
  const btn = document.getElementById('stopAllBtn');
  if (btn) btn.disabled = true;
  setLoadingStatus('Deteniendo servicios…');
  // Parar en orden inverso: dependientes primero, gateway al final
  const toStop = [...SVCS].reverse();
  for (const svc of toStop) {
    const st = document.querySelector(`#svc-${svc.id} .svc-dot`)?.dataset.status;
    if (st !== 'online') continue;
    setLoadingStatus(`Deteniendo ${svc.label}…`);
    await stopSvc(svc.id);
  }
  setLoadingStatus('Servicios detenidos.');
  if (btn) btn.disabled = false;
  updateProgress();
}

function showLoadingView() {
  document.getElementById('chatView').classList.add('hidden');
  document.getElementById('loadingView').classList.remove('hidden');
  const lp = document.getElementById('logPanel');
  if (lp) { lp.classList.remove('chat-mode', 'hidden'); }
  if (ws) { ws.close(); ws = null; }
  refreshStatuses();
}

async function shutdownFromChat() {
  if (!confirm('¿Detener todos los servicios y volver al panel de inicio?')) return;
  showLoadingView();
  await stopAllServices();
}

// ── VRAM Guard ─────────────────────────────────────────────────────────────
let _vramPrevPaused = [];
let _vramPrevLevel  = '';

async function pollVram() {
  try {
    const r = await fetch(`/mon/api/vram/status`);
    if (!r.ok) return;
    const data = await r.json();
    _applyVramState(data);
  } catch (_) { /* monitoring offline — badge stays as-is */ }
}

function _applyVramState(data) {
  const gpu   = data.gpu   || {};
  const guard = data.guard || {};
  const el    = document.getElementById('vramBadge');
  if (!el) return;

  if (gpu.error || gpu.memory_percent == null) {
    el.textContent  = 'GPU N/D';
    el.dataset.level = '';
    el.title = gpu.error ? `Error: ${gpu.error}` : 'nvidia-smi no disponible';
    return;
  }

  const pct       = gpu.memory_percent;
  const warnPct   = guard.warn_pct     ?? 80;
  const critPct   = guard.critical_pct ?? 90;
  const recPct    = guard.recovery_pct ?? 70;
  const paused    = guard.paused_services ?? [];
  const newPaused = paused.filter(id => !_vramPrevPaused.includes(id));

  // Update badge text + colour
  el.textContent   = `VRAM ${pct.toFixed(0)}%`;
  const usedGib    = (gpu.memory_used_mb  / 1024).toFixed(1);
  const totalGib   = (gpu.memory_total_mb / 1024).toFixed(1);
  el.title = (
    `GPU: ${gpu.gpu_utilization_percent ?? '?'}% | ` +
    `VRAM: ${usedGib}/${totalGib} GiB | ` +
    `Temp: ${gpu.temperature_celsius ?? '?'}°C\n` +
    `Aviso ≥${warnPct}%  Crítico ≥${critPct}%  Recuperación <${recPct}%`
  );

  let level = 'ok';
  if (pct >= critPct)      level = 'critical';
  else if (pct >= warnPct) level = 'warn';
  el.dataset.level = level;

  // Notify user only when level actually changes or services are newly paused
  if (newPaused.length > 0) {
    toast(`VRAM ${pct.toFixed(0)}% — pausados: ${newPaused.join(', ')}`, 'error');
    newPaused.forEach(id => updateSvcUI(id, 'offline'));
  } else if (paused.length === 0 && _vramPrevPaused.length > 0) {
    toast(`VRAM ${pct.toFixed(0)}% — presión reducida. Reinicia TTS/STT si lo necesitas.`, 'success');
  } else if (level !== _vramPrevLevel) {
    if (level === 'critical') toast(`VRAM al ${pct.toFixed(0)}% — servicios no críticos siendo pausados…`, 'error');
    else if (level === 'warn') toast(`VRAM al ${pct.toFixed(0)}% — presión alta en GPU.`, 'warning');
  }

  _vramPrevPaused = paused;
  _vramPrevLevel  = level;
}

// ── Logs / Auditoría ───────────────────────────────────────────────────────
let _logsExpanded = false;

function toggleLogsExpand() {
  _logsExpanded = !_logsExpanded;
  document.getElementById('logEntries')?.classList.toggle('expanded', _logsExpanded);
  const tog = document.getElementById('lpToggle');
  if (tog) tog.textContent = _logsExpanded ? '▾' : '▸';
}

function toggleLogsPanel() {
  const panel = document.getElementById('logPanel');
  if (!panel) return;
  if (panel.classList.contains('hidden')) {
    panel.classList.remove('hidden');
    if (!_logsExpanded) toggleLogsExpand();
  } else {
    panel.classList.add('hidden');
  }
}

async function fetchAndRenderLogs() {
  try {
    const r = await fetch(`/mon/api/logs/recent?limit=50`);
    if (!r.ok) return;
    const data = await r.json();
    renderLogs(data.logs ?? []);
  } catch (_) { /* monitoring offline */ }
}

function renderLogs(logs) {
  // Filter out high-frequency API health checks — show only meaningful events
  const filtered = logs.filter(l => {
    if (l.event_type === 'API_REQUEST') {
      const action = (l.action ?? '').toLowerCase();
      return !action.includes('/health') && !action.includes('/api/services/status');
    }
    return true;
  });

  let okCnt = 0, errCnt = 0;
  const rows = filtered.slice(-40).map(l => {
    const ts     = (l.timestamp ?? '').slice(11, 22);
    const et     = l.event_type ?? '';
    const bdgCls = et === 'SERVICE_CONTROL' ? 'SC' : et.startsWith('TTS') ? 'TTS' : 'OTH';
    const bdgLbl = bdgCls === 'SC' ? 'SVC' : bdgCls;
    const action = l.action ?? '';
    const dur    = l.duration_ms != null ? `${Math.round(l.duration_ms)}ms` : '';
    const suc    = l.success;
    if (suc === true)  okCnt++;
    if (suc === false) errCnt++;
    const ico    = suc == null ? '' : suc
      ? '<span class="log-ico ok">✓</span>'
      : '<span class="log-ico err">✗</span>';
    const rowCls = suc === false ? 'log-row fail' : 'log-row';
    return `<div class="${rowCls}">
      <span class="log-ts">${ts}</span>
      <span class="log-bdg ${bdgCls}">${bdgLbl}</span>
      <span class="log-act" title="${action}">${action}</span>
      <span class="log-dur">${dur}</span>
      ${ico}
    </div>`;
  }).join('');

  const el = document.getElementById('logEntries');
  if (el) { el.innerHTML = rows; el.scrollTop = el.scrollHeight; }

  const stats = document.getElementById('lpStats');
  if (stats) {
    stats.innerHTML =
      `<span class="lp-ok">✓${okCnt}</span> ` +
      `<span class="lp-err">✗${errCnt}</span> ` +
      `<span class="lp-dim">${filtered.length}ev</span>`;
  }
}

function startLogsPolling() {
  fetchAndRenderLogs();
  setInterval(fetchAndRenderLogs, 5000);
}

// ── Arranque ───────────────────────────────────────────────────────────────
init();
// VRAM polling: primer chequeo a los 5 s (tras init) y luego cada 30 s
setTimeout(() => { pollVram(); setInterval(pollVram, 30_000); }, 5_000);
