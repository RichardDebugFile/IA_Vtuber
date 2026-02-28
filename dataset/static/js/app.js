// Dataset Generator - Frontend Application

let ws = null;
let currentPage = 0;
const pageSize = 50;
let isInitialized = false;

// WebSocket connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        document.getElementById('wsStatus').className = 'status-dot online';
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        document.getElementById('wsStatus').className = 'status-dot offline';
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'status':
            updateStatus(message.data);
            break;
        case 'progress':
            updateProgress(message.data);
            break;
        case 'entry_update':
            updateEntry(message.data);
            break;
        case 'service_status':
            updateServiceStatus(message.data);
            break;
        case 'log':
            addLogEntry(message.data);
            break;
        case 'error':
            showError(message.data.message);
            break;
    }
}

// Update status display
function updateStatus(data) {
    if (data.status) {
        const statusText = translateStatus(data.status);
        const statusElement = document.getElementById('currentStatus');

        // Show continuation info if there are completed items
        if (data.completed > 0 && data.status === 'idle') {
            statusElement.textContent = statusText + ` (${data.completed} completados, puede continuar)`;
        } else {
            statusElement.textContent = statusText;
        }

        // Update stats if available
        if (data.total_clips !== undefined) {
            document.getElementById('totalClips').textContent = data.total_clips;
            document.getElementById('completedClips').textContent = data.completed || 0;
            document.getElementById('failedClips').textContent = data.failed || 0;
            document.getElementById('totalDuration').textContent =
                data.total_duration_formatted || '-';

            // Update progress
            if (data.progress_percentage !== undefined) {
                updateProgressBar(data.progress_percentage);
            }

            // Enable/disable buttons based on status
            updateButtonStates(data.status);

            // Update start button text based on progress
            const startBtn = document.getElementById('startBtn');
            const pending = data.total_clips - (data.completed || 0);
            if (data.completed > 0 && pending > 0) {
                startBtn.textContent = `▶ Continuar (${pending} pendientes)`;
            } else {
                startBtn.textContent = '▶ Iniciar';
            }
        }
    }
}

// Update progress bar
function updateProgress(data) {
    const percentage = data.percentage || 0;
    updateProgressBar(percentage);

    document.getElementById('completedClips').textContent = data.completed;
    document.getElementById('failedClips').textContent = data.failed;
}

function updateProgressBar(percentage) {
    document.getElementById('progressFill').style.width = percentage + '%';
    document.getElementById('progressText').textContent = percentage.toFixed(1) + '%';
}

// Update service status indicators
function updateServiceStatus(data) {
    const ttsStatus = document.getElementById('ttsStatus');
    const fishStatus = document.getElementById('fishStatus');

    ttsStatus.className = data.tts_available ? 'status-dot online' : 'status-dot offline';
    fishStatus.className = data.fish_available ? 'status-dot online' : 'status-dot offline';
}

// Track recently updated entries
let recentlyUpdated = new Set();

// Update individual entry in the list
function updateEntry(entryData) {
    const entryElement = document.getElementById(`entry-${entryData.id}`);

    // Track this entry as recently updated (for highlighting and auto-scroll)
    if (entryData.status === 'completed' || entryData.status === 'error') {
        recentlyUpdated.add(entryData.id);

        // Add visual highlight to completed/error entries
        if (entryElement) {
            setTimeout(() => {
                entryElement.style.backgroundColor = '#e8f5e9';
                setTimeout(() => {
                    entryElement.style.backgroundColor = '';
                }, 3000);
            }, 300);
        }

        // Remove from recently updated after 30 seconds
        setTimeout(() => {
            recentlyUpdated.delete(entryData.id);
        }, 30000);
    }

    if (entryElement) {
        // Update status badge
        const badge = entryElement.querySelector('.status-badge');
        if (badge) {
            badge.className = `status-badge ${entryData.status}`;
            badge.textContent = translateStatus(entryData.status);
        }

        // Update metadata
        const metadata = entryElement.querySelector('.entry-metadata');
        if (metadata) {
            if (entryData.status === 'completed' && entryData.duration_seconds) {
                metadata.innerHTML = `
                    <span>${entryData.duration_seconds.toFixed(2)}s</span>
                    <span>${entryData.file_size_kb}KB</span>
                `;
            } else if (entryData.status === 'generating') {
                metadata.innerHTML = `<span class="text-muted">Generando...</span>`;
            } else if (entryData.status === 'error') {
                metadata.innerHTML = `<span class="text-error">${entryData.error_message || 'Error'}</span>`;
            } else {
                metadata.innerHTML = `<span class="text-muted">Pendiente</span>`;
            }
        }

        // Update action buttons
        const actions = entryElement.querySelector('.entry-actions');
        if (actions) {
            let buttonsHTML = `<span class="status-badge ${entryData.status}">
                ${translateStatus(entryData.status)}
            </span>`;

            // Play button for completed entries
            if (entryData.status === 'completed') {
                buttonsHTML += `
                    <button class="btn-icon" onclick="playAudio('${entryData.filename}')" title="Reproducir">▶</button>
                    <button class="btn-icon" onclick="regenerateEntry(${entryData.id})" title="Regenerar">↻</button>
                `;
            }
            // Regenerate button for error entries
            else if (entryData.status === 'error') {
                buttonsHTML += `
                    <button class="btn-icon" onclick="regenerateEntry(${entryData.id})" title="Regenerar">↻</button>
                `;
            }
            // Generate button for pending entries
            else if (entryData.status === 'pending') {
                buttonsHTML += `
                    <button class="btn-icon" onclick="generateSingleEntry(${entryData.id})" title="Generar ahora">▶</button>
                `;
            }

            actions.innerHTML = buttonsHTML;
        }

        // Add recently-updated class for visual distinction
        if (recentlyUpdated.has(entryData.id)) {
            entryElement.classList.add('recently-updated');
            setTimeout(() => {
                entryElement.classList.remove('recently-updated');
            }, 5000);
        }
    } else {
        // Entry not on current page - show notification badge
        updateOffPageNotification(entryData);
    }
}

// Show notification when entries update off current page
function updateOffPageNotification(entryData) {
    const notificationArea = document.getElementById('offPageNotification');
    if (!notificationArea) return;

    if (entryData.status === 'completed' || entryData.status === 'error') {
        const statusText = entryData.status === 'completed' ? 'completado' : 'falló';
        notificationArea.innerHTML = `
            <div style="padding: 10px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; margin-bottom: 15px;">
                ⚠️ Audio #${entryData.id} ${statusText} en otra página.
                <button class="btn btn-sm" onclick="goToEntryPage(${entryData.id})" style="margin-left: 10px;">
                    Ver ahora
                </button>
                <button class="btn btn-sm" onclick="dismissNotification()" style="margin-left: 5px;">
                    ✕
                </button>
            </div>
        `;

        // Auto-dismiss after 10 seconds
        setTimeout(() => {
            dismissNotification();
        }, 10000);
    }
}

function dismissNotification() {
    const notificationArea = document.getElementById('offPageNotification');
    if (notificationArea) {
        notificationArea.innerHTML = '';
    }
}

function showPriorityNotification(message) {
    const notificationArea = document.getElementById('offPageNotification');
    if (!notificationArea) return;

    notificationArea.innerHTML = `
        <div style="padding: 10px; background: #e3f2fd; border: 1px solid #2196F3; border-radius: 6px; margin-bottom: 15px;">
            ⭐ ${message}
            <button class="btn btn-sm" onclick="dismissNotification()" style="margin-left: 10px;">
                ✕
            </button>
        </div>
    `;

    // Auto-dismiss after 8 seconds
    setTimeout(() => {
        dismissNotification();
    }, 8000);
}

function goToEntryPage(entryId) {
    // Calculate which page contains this entry
    const targetPage = Math.floor((entryId - 1) / pageSize);
    currentPage = targetPage;
    loadEntries();
    dismissNotification();
}

// Button state management
function updateButtonStates(status) {
    const initBtn = document.getElementById('initBtn');
    const startBtn = document.getElementById('startBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const resumeBtn = document.getElementById('resumeBtn');
    const stopBtn = document.getElementById('stopBtn');
    const resetFromBtn = document.getElementById('resetFromBtn');
    const forceCheckBtn = document.getElementById('forceCheckBtn');

    // Reset all
    startBtn.disabled = true;
    pauseBtn.disabled = true;
    resumeBtn.disabled = true;
    stopBtn.disabled = true;
    resetFromBtn.disabled = true;
    forceCheckBtn.disabled = true;

    if (isInitialized) {
        initBtn.disabled = true;

        switch (status) {
            case 'idle':
            case 'stopped':
            case 'completed':
                startBtn.disabled = false;
                resetFromBtn.disabled = false;
                break;
            case 'running':
                pauseBtn.disabled = false;
                stopBtn.disabled = false;
                forceCheckBtn.disabled = false;  // Enable force check during generation
                break;
            case 'paused':
                resumeBtn.disabled = false;
                stopBtn.disabled = false;
                resetFromBtn.disabled = false;
                break;
        }
    }
}

// Initialize dataset
async function initializeDataset() {
    try {
        const response = await fetch('/api/initialize', { method: 'POST' });
        const data = await response.json();

        if (data.ok) {
            isInitialized = true;
            alert(`Dataset inicializado con ${data.total_clips} clips`);
            loadStatus();
            loadEntries();
            updateButtonStates('idle');
        } else {
            alert('Error al inicializar dataset: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al inicializar dataset');
    }
}

// Generation controls
async function startGeneration() {
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                parallel_workers: 2,  // Balanced: 2 workers for longer phrases (14+ words avg)
                backend: 'http'
            })
        });

        const data = await response.json();
        if (!data.ok) {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al iniciar generación');
    }
}

async function pauseGeneration() {
    try {
        const response = await fetch('/api/pause', { method: 'POST' });
        const data = await response.json();
        if (!data.ok) {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function resumeGeneration() {
    try {
        const response = await fetch('/api/resume', { method: 'POST' });
        const data = await response.json();
        if (!data.ok) {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function stopGeneration() {
    if (!confirm('¿Estás seguro de detener la generación?')) {
        return;
    }

    try {
        // Show immediate feedback
        const statusElement = document.getElementById('currentStatus');
        const originalText = statusElement.textContent;
        statusElement.textContent = 'Deteniendo...';

        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();

        if (data.ok) {
            // Success feedback
            statusElement.textContent = 'Detenido';

            // Reload status to update counters and UI
            setTimeout(() => {
                loadStatus();
                loadEntries();
            }, 500);
        } else {
            // Restore original text on error
            statusElement.textContent = originalText;
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al detener la generación');
    }
}

async function forcePriorityCheck() {
    try {
        const response = await fetch('/api/force_priority_check', { method: 'POST' });
        const data = await response.json();

        if (data.ok) {
            showPriorityNotification(
                'Verificación de prioridades forzada. Los audios marcados con "Rehacer" se procesarán en el próximo ciclo.'
            );
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al forzar verificación de prioridades');
    }
}

// Refresh dashboard - reload status and entries
async function refreshDashboard() {
    try {
        console.log('Refrescando dashboard...');

        // Show loading indicator
        const notificationArea = document.getElementById('offPageNotification');
        if (notificationArea) {
            notificationArea.innerHTML = `
                <div style="padding: 10px; background: #e3f2fd; border: 1px solid #2196F3; border-radius: 6px; margin-bottom: 15px;">
                    🔄 Refrescando dashboard...
                </div>
            `;
        }

        // Reload status and entries
        await loadStatus();
        await loadEntries();

        // Show success message
        if (notificationArea) {
            notificationArea.innerHTML = `
                <div style="padding: 10px; background: #e8f5e9; border: 1px solid #4CAF50; border-radius: 6px; margin-bottom: 15px;">
                    ✓ Dashboard refrescado exitosamente
                    <button class="btn btn-sm" onclick="dismissNotification()" style="margin-left: 10px;">
                        ✕
                    </button>
                </div>
            `;

            setTimeout(() => dismissNotification(), 3000);
        }

        console.log('Dashboard refrescado');
    } catch (error) {
        console.error('Error refrescando dashboard:', error);
        alert('Error al refrescar dashboard');
    }
}

// Perform silent sync on first load to fix desync issues
let hasSyncedOnLoad = false;

async function silentSyncOnFirstLoad() {
    if (hasSyncedOnLoad) return;

    try {
        // Only sync if idle/stopped/completed (not during generation)
        const statusResp = await fetch('/api/status');
        const statusData = await statusResp.json();

        if (statusData.ok) {
            const status = statusData.status.status;

            // Only sync when not actively generating
            if (status === 'idle' || status === 'stopped' || status === 'completed') {
                console.log('Performing silent sync to fix potential desynchronization...');

                const syncResp = await fetch('/api/sync_state', { method: 'POST' });
                const syncData = await syncResp.json();

                if (syncData.ok && syncData.synced_entries > 0) {
                    console.log(`Silent sync: ${syncData.synced_entries} entries updated`);
                    // Reload entries to reflect changes
                    loadEntries();
                }
            }
        }

        hasSyncedOnLoad = true;
    } catch (error) {
        console.error('Silent sync failed:', error);
        hasSyncedOnLoad = true; // Don't retry on error
    }
}

// Load status
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (data.ok) {
            updateStatus(data.status);
            if (data.status.total_clips > 0) {
                isInitialized = true;

                // Perform silent sync on first load
                if (!hasSyncedOnLoad) {
                    setTimeout(() => silentSyncOnFirstLoad(), 1000);
                }
            }
        }
    } catch (error) {
        console.error('Error loading status:', error);
    }
}

// Load entries
async function loadEntries() {
    const filter = document.getElementById('statusFilter').value;
    const offset = currentPage * pageSize;

    try {
        const url = `/api/entries?limit=${pageSize}&offset=${offset}` +
                    (filter ? `&status_filter=${filter}` : '');

        const response = await fetch(url);
        const data = await response.json();

        if (data.ok) {
            displayEntries(data.entries);
            updatePagination(data.total);
        }
    } catch (error) {
        console.error('Error loading entries:', error);
    }
}

// Display entries in the list
function displayEntries(entries) {
    const container = document.getElementById('entriesList');

    if (entries.length === 0) {
        container.innerHTML = '<div class="loading">No hay entradas disponibles</div>';
        return;
    }

    container.innerHTML = entries.map(entry => `
        <div class="entry-item" id="entry-${entry.id}">
            <div class="entry-info">
                <div class="entry-filename">${entry.filename}.wav</div>
                <div class="entry-text">${entry.text}</div>
                <div class="entry-metadata">
                    ${entry.status === 'completed' && entry.duration_seconds ?
                        `<span>${entry.duration_seconds.toFixed(2)}s</span>
                         <span>${entry.file_size_kb}KB</span>`
                        : entry.status === 'generating' ?
                        '<span class="text-muted">Generando...</span>'
                        : entry.status === 'error' ?
                        `<span class="text-error">${entry.error_message || 'Error'}</span>`
                        : '<span class="text-muted">Pendiente</span>'}
                </div>
            </div>
            <div class="entry-actions">
                <span class="status-badge ${entry.status}">
                    ${translateStatus(entry.status)}
                </span>
                ${entry.status === 'completed' ?
                    `<button class="btn-icon" onclick="playAudio('${entry.filename}')" title="Reproducir">▶</button>
                     <button class="btn-icon" onclick="regenerateEntry(${entry.id})" title="Regenerar">↻</button>`
                    : ''}
                ${entry.status === 'error' ?
                    `<button class="btn-icon" onclick="regenerateEntry(${entry.id})" title="Regenerar">↻</button>`
                    : ''}
                ${entry.status === 'pending' ?
                    `<button class="btn-icon" onclick="generateSingleEntry(${entry.id})" title="Generar ahora">▶</button>`
                    : ''}
            </div>
        </div>
    `).join('');
}

// Pagination
function updatePagination(total) {
    const totalPages = Math.ceil(total / pageSize);
    document.getElementById('pageInfo').textContent =
        `Página ${currentPage + 1} de ${totalPages}`;

    document.getElementById('prevBtn').disabled = currentPage === 0;
    document.getElementById('nextBtn').disabled = currentPage >= totalPages - 1;
}

function previousPage() {
    if (currentPage > 0) {
        currentPage--;
        loadEntries();
    }
}

function nextPage() {
    currentPage++;
    loadEntries();
}

// Play audio
function playAudio(filename) {
    const modal = document.getElementById('audioModal');
    const player = document.getElementById('audioPlayer');
    const title = document.getElementById('modalTitle');
    const info = document.getElementById('audioInfo');

    // Add .wav extension if not present
    const audioFile = filename.endsWith('.wav') ? filename : `${filename}.wav`;

    player.src = `/api/audio/${audioFile}`;
    title.textContent = audioFile;
    info.textContent = 'Reproduciendo...';

    modal.classList.add('active');
    player.play();
}

function closeAudioModal() {
    const modal = document.getElementById('audioModal');
    const player = document.getElementById('audioPlayer');

    player.pause();
    player.src = '';
    modal.classList.remove('active');
}

// Regenerate entry with emotion selection
async function regenerateEntry(entryId) {
    // Show emotion selector dialog
    const emotions = [
        { value: null, label: 'Auto-detectar (por defecto)' },
        { value: 'neutral', label: 'Neutral' },
        { value: 'happy', label: 'Feliz/Alegre' },
        { value: 'sad', label: 'Triste' },
        { value: 'angry', label: 'Enojado/Molesto' },
        { value: 'surprised', label: 'Sorprendido' },
        { value: 'fearful', label: 'Temeroso' },
        { value: 'disgusted', label: 'Disgustado' }
    ];

    // Create emotion selection dialog
    const emotionOptions = emotions.map(e =>
        `<option value="${e.value || ''}">${e.label}</option>`
    ).join('\n');

    const dialogHTML = `
        <div id="emotionDialog" style="
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            z-index: 10000;
            min-width: 350px;
        ">
            <h3 style="margin-top: 0;">Regenerar Audio #${entryId}</h3>
            <p style="margin-bottom: 15px;">Selecciona la emoción para el audio:</p>
            <select id="emotionSelect" style="
                width: 100%;
                padding: 8px;
                margin-bottom: 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            ">
                ${emotionOptions}
            </select>
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button id="cancelEmotion" style="
                    padding: 8px 16px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                    cursor: pointer;
                ">Cancelar</button>
                <button id="confirmEmotion" style="
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    background: #2196F3;
                    color: white;
                    cursor: pointer;
                ">Regenerar</button>
            </div>
        </div>
        <div id="emotionOverlay" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 9999;
        "></div>
    `;

    // Add dialog to DOM
    const dialogContainer = document.createElement('div');
    dialogContainer.innerHTML = dialogHTML;
    document.body.appendChild(dialogContainer);

    // Handle dialog interaction
    return new Promise((resolve) => {
        document.getElementById('confirmEmotion').addEventListener('click', async () => {
            const emotion = document.getElementById('emotionSelect').value || null;

            // Remove dialog
            dialogContainer.remove();

            try {
                // Update UI immediately to show regenerating status
                const entryElement = document.getElementById(`entry-${entryId}`);
                if (entryElement) {
                    const badge = entryElement.querySelector('.status-badge');
                    if (badge) {
                        badge.className = 'status-badge generating';
                        badge.textContent = 'Regenerando...';
                    }
                }

                const response = await fetch('/api/regenerate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        entry_id: entryId,
                        emotion: emotion
                    })
                });

                const data = await response.json();
                if (data.ok) {
                    // Show success message with priority info
                    const emotionText = emotion ? ` con emoción '${emotion}'` : '';
                    showPriorityNotification(
                        `Audio #${entryId} marcado para regeneración${emotionText}. ` +
                        `Se procesará en los próximos 10 audios (sistema de prioridades).`
                    );
                } else {
                    alert('Error al regenerar: ' + data.error);
                    loadEntries();
                }
                // WebSocket will update the entry status automatically
            } catch (error) {
                console.error('Error:', error);
                alert('Error al regenerar entrada');
                loadEntries();
            }

            resolve();
        });

        document.getElementById('cancelEmotion').addEventListener('click', () => {
            dialogContainer.remove();
            resolve();
        });

        document.getElementById('emotionOverlay').addEventListener('click', () => {
            dialogContainer.remove();
            resolve();
        });
    });
}

// Generate a single pending entry immediately
async function generateSingleEntry(entryId) {
    if (!confirm(`¿Generar el audio #${entryId} ahora?\n\nEsto generará este audio individual de forma inmediata con emoción auto-detectada.`)) {
        return;
    }

    try {
        // Update UI immediately to show generating status
        const entryElement = document.getElementById(`entry-${entryId}`);
        if (entryElement) {
            const badge = entryElement.querySelector('.status-badge');
            if (badge) {
                badge.className = 'status-badge generating';
                badge.textContent = 'Generando...';
            }
        }

        const response = await fetch('/api/regenerate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                entry_id: entryId,
                emotion: null  // Auto-detect emotion
            })
        });

        const data = await response.json();
        if (data.ok) {
            showPriorityNotification(
                `Audio #${entryId} en proceso de generación individual...`
            );
        } else {
            alert('Error al generar: ' + data.error);
            loadEntries();
        }
        // WebSocket will update the entry status automatically
    } catch (error) {
        console.error('Error:', error);
        alert('Error al generar entrada');
        loadEntries();
    }
}

// Synchronize state with disk files
async function syncState() {
    if (!confirm('¿Sincronizar el estado con los archivos en disco?\n\nEsto actualizará el estado basándose en los archivos .wav que realmente existen.')) {
        return;
    }

    const syncBtn = document.getElementById('syncBtn');
    const syncInfo = document.getElementById('syncInfo');

    try {
        syncBtn.disabled = true;
        syncInfo.textContent = 'Sincronizando...';
        syncInfo.style.color = '#2196F3';

        const response = await fetch('/api/sync_state', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.ok) {
            // Show detailed sync results
            const foundMsg = `${data.files_found} encontrados`;
            const missingMsg = data.files_missing > 0 ? `, ${data.files_missing} faltantes` : '';
            const syncedMsg = data.synced_entries > 0 ? ` → ${data.synced_entries} actualizados` : '';

            syncInfo.textContent = `✓ ${foundMsg}${missingMsg}${syncedMsg}`;
            syncInfo.style.color = '#4CAF50';

            // Show alert if missing files were found
            if (data.files_missing > 0) {
                alert(
                    `Sincronización completa:\n\n` +
                    `• Archivos encontrados: ${data.files_found}\n` +
                    `• Archivos faltantes: ${data.files_missing}\n` +
                    `• Audios marcados como pendientes: ${data.synced_entries}\n\n` +
                    `Los archivos faltantes fueron marcados como "pendientes" y se pueden generar ahora.`
                );
            }

            // Reload status and entries
            loadStatus();
            loadEntries();

            // Clear the message after 8 seconds
            setTimeout(() => {
                syncInfo.textContent = '';
            }, 8000);
        } else {
            alert('Error al sincronizar: ' + data.error);
            syncInfo.textContent = '✗ Error';
            syncInfo.style.color = '#f44336';
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al sincronizar estado');
        syncInfo.textContent = '✗ Error';
        syncInfo.style.color = '#f44336';
    } finally {
        syncBtn.disabled = false;
    }
}

// Reset generation from specific ID
async function resetFromId() {
    const startFromId = parseInt(document.getElementById('startFromId').value);

    if (!startFromId || startFromId < 1) {
        alert('Por favor, ingresa un número de audio válido (mínimo 1)');
        return;
    }

    if (!confirm(`¿Reiniciar generación desde el audio #${startFromId}?\n\nEsto marcará como "pendiente" todos los audios desde ese número en adelante.\nLos audios anteriores no se tocarán.`)) {
        return;
    }

    try {
        const response = await fetch('/api/reset_from', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_from_id: startFromId })
        });

        const data = await response.json();

        if (data.ok) {
            document.getElementById('resetInfo').textContent =
                `✓ ${data.reset_count} audios marcados como pendientes`;
            document.getElementById('resetInfo').style.color = '#4CAF50';

            // Reload status and entries
            loadStatus();
            loadEntries();

            // Clear the message after 5 seconds
            setTimeout(() => {
                document.getElementById('resetInfo').textContent = '';
            }, 5000);
        } else {
            alert('Error al reiniciar: ' + data.error);
            document.getElementById('resetInfo').textContent = '✗ Error';
            document.getElementById('resetInfo').style.color = '#f44336';
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al reiniciar desde ID específico');
    }
}

// Check service status
async function checkServices() {
    try {
        const response = await fetch('/api/services');
        const data = await response.json();

        if (data.ok) {
            updateServiceStatus(data.services);
        }
    } catch (error) {
        console.error('Error checking services:', error);
    }
}

// Utility functions
function translateStatus(status) {
    const translations = {
        'idle': 'Inactivo',
        'running': 'Generando',
        'paused': 'Pausado',
        'stopped': 'Detenido',
        'completed': 'Completado',
        'pending': 'Pendiente',
        'generating': 'Generando',
        'error': 'Error'
    };
    return translations[status] || status;
}

function showError(message) {
    console.error('Error:', message);
    // Could show a toast notification here
}

// === LOG MANAGEMENT ===
let autoScroll = true;
const MAX_LOG_ENTRIES = 500; // Maximum log entries to keep in memory

function addLogEntry(logData) {
    const container = document.getElementById('logsContainer');
    if (!container) return;

    // Get current time
    const now = new Date();
    const timeStr = now.toLocaleTimeString('es-ES', { hour12: false });

    // Determine log level/type
    const level = logData.level || 'info';
    const message = logData.message || '';

    // Create log entry element
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${level}`;
    logEntry.innerHTML = `
        <span class="log-time">[${timeStr}]</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;

    // Add to container
    container.appendChild(logEntry);

    // Limit number of log entries
    const entries = container.querySelectorAll('.log-entry');
    if (entries.length > MAX_LOG_ENTRIES) {
        entries[0].remove();
    }

    // Auto-scroll to bottom if enabled
    if (autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function clearLogs() {
    const container = document.getElementById('logsContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="log-entry log-info">
            <span class="log-time">[${new Date().toLocaleTimeString('es-ES', { hour12: false })}]</span>
            <span class="log-message">Logs limpiados. Esperando actividad...</span>
        </div>
    `;
}

function toggleAutoScroll() {
    autoScroll = !autoScroll;
    const btn = document.getElementById('autoScrollBtn');
    if (btn) {
        btn.textContent = `📍 Auto-scroll: ${autoScroll ? 'ON' : 'OFF'}`;
        btn.style.background = autoScroll ? '#4CAF50' : '#666';
    }
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    loadStatus();
    loadEntries();
    checkServices();

    // Check services every 30 seconds
    setInterval(checkServices, 30000);

    // Auto-refresh status every 5 seconds
    setInterval(() => {
        loadStatus();
    }, 5000);

    // Refresh entries list only when filter changes or manually requested
    // WebSocket updates handle individual entry updates in real-time
});
