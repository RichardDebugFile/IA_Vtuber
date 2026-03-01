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
  { id: 'gateway',    label: 'Gateway',        critical: true,  bootstrap: true  },
  { id: 'memory-api', label: 'Memoria API',    critical: false, bootstrap: false },
  { id: 'conversation',label: 'Conversación',  critical: true,  bootstrap: false },
  { id: 'tts-blips',  label: 'TTS Blips',     critical: false, bootstrap: false },
  { id: 'tts-router', label: 'TTS Router',    critical: false, bootstrap: false },
  { id: 'tts-casiopy',label: 'TTS Casiopy',   critical: false, bootstrap: false },
  { id: 'stt',        label: 'STT (Voz)',      critical: false, bootstrap: false },
];

// ── Inicialización ─────────────────────────────────────────────────────────
async function init() {
  try {
    const r = await fetch('/config');
    if (r.ok) cfg = await r.json();
  } catch (_) { /* usar defaults */ }

  await refreshStatuses();
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
    const r = await fetch(`${cfg.gateway_url}/services/status`);
    if (!r.ok) return;
    const statuses = await r.json();
    SVCS.forEach(s => {
      const st = statuses[s.id]?.status ?? 'offline';
      updateSvcUI(s.id, st);
    });
    updateProgress();
  } catch (_) {
    setLoadingStatus('No se puede conectar al gateway.');
  }
}

function updateSvcUI(id, status) {
  // Loading view
  const row = document.getElementById(`svc-${id}`);
  if (row) {
    const dot  = row.querySelector('.svc-dot');
    const text = row.querySelector('.svc-status-text');
    dot.dataset.status   = status;
    text.textContent     = status;
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

    // El gateway se inicia llamando a monitoring-service directamente
    // (no puede enrutar a través de sí mismo si aún no está corriendo)
    const startUrl = svc.bootstrap
      ? `${cfg.monitoring_url}/api/services/${svc.id}/start`
      : `${cfg.gateway_url}/services/${svc.id}/start`;

    try {
      const r = await fetch(startUrl, { method: 'POST' });
      if (r.ok) {
        updateSvcUI(svc.id, 'online');
      } else {
        const detail = (await r.json().catch(() => ({}))).detail ?? r.statusText;
        updateSvcUI(svc.id, svc.critical ? 'error' : 'warning');
        if (svc.critical) {
          setLoadingStatus(`Error: no se pudo iniciar ${svc.label}. ${detail}`);
          btn.disabled = false;
          updateProgress();
          return;
        }
      }
    } catch (e) {
      updateSvcUI(svc.id, svc.critical ? 'error' : 'warning');
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

// ── VRAM Guard ─────────────────────────────────────────────────────────────
let _vramPrevPaused = [];
let _vramPrevLevel  = '';

async function pollVram() {
  try {
    const r = await fetch(`${cfg.monitoring_url}/api/vram/status`);
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

// ── Arranque ───────────────────────────────────────────────────────────────
init();
// VRAM polling: primer chequeo a los 5 s (tras init) y luego cada 30 s
setTimeout(() => { pollVram(); setInterval(pollVram, 30_000); }, 5_000);
