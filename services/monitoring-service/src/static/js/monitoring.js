// Monitoring Dashboard JavaScript
console.log('✅ Monitoring JavaScript loaded');

let ws = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
const responseTimeData = {};

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/monitoring`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        document.getElementById('wsStatus').textContent = 'Connected';
        document.getElementById('wsStatus').className = 'connection-status connected';
        document.getElementById('refreshIndicator').style.display = 'inline-block';
        reconnectAttempts = 0;
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        document.getElementById('wsStatus').textContent = 'Disconnected';
        document.getElementById('wsStatus').className = 'connection-status disconnected';
        document.getElementById('refreshIndicator').style.display = 'none';

        // Attempt reconnection
        if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            setTimeout(connectWebSocket, 3000);
        }
    };
}

function handleWebSocketMessage(data) {
    if (data.type === 'init' || data.type === 'update') {
        updateDashboard(data);
    }
}

function updateDashboard(data) {
    // Update system health
    if (data.health) {
        const healthEl = document.getElementById('systemHealth');
        healthEl.textContent = data.health.health_status.toUpperCase();
        healthEl.className = `stat-value ${data.health.health_status}`;

        document.getElementById('servicesOnline').textContent =
            `${data.health.online}/${data.health.total_services}`;
        document.getElementById('overallUptime').textContent =
            `${data.health.overall_uptime_percentage}%`;
        document.getElementById('activeAlerts').textContent =
            data.health.unresolved_alerts || 0;
    }

    // Update services list
    if (data.services) {
        updateServicesList(data.services, data.metrics);
        updateActiveServicesList(data.services);
    }

    // Fetch Docker and GPU stats immediately on update
    fetchDockerStats();
}

function updateServicesList(services, metrics) {
    const container = document.getElementById('servicesList');
    container.innerHTML = '';

    console.log('Updating services list:', services);

    // Check if BOTH TTS and Fish services are online and show/hide TTS Testing link
    const ttsTestLink = document.getElementById('ttsTestLink');
    const ttsOnline = services.tts && services.tts.status === 'online';
    const fishOnline = services.fish && services.fish.status === 'online';

    if (ttsOnline && fishOnline) {
        ttsTestLink.style.display = 'inline-block';
        ttsTestLink.style.opacity = '1';
        ttsTestLink.title = 'Ambos servicios TTS y Fish están activos';
    } else {
        ttsTestLink.style.display = 'none';
    }

    // Check if TTS Blips service is online and show/hide Blips Testing link
    const blipsTestLink = document.getElementById('blipsTestLink');
    const blipsOnline = services['tts-blips'] && services['tts-blips'].status === 'online';

    if (blipsOnline) {
        blipsTestLink.style.display = 'inline-block';
        blipsTestLink.style.opacity = '1';
        blipsTestLink.title = 'Servicio TTS Blips está activo';
    } else {
        blipsTestLink.style.display = 'none';
    }

    // Check if Conversation service is online and show/hide Conversation Testing link
    const conversationTestLink = document.getElementById('conversationTestLink');
    const conversationOnline = services.conversation && services.conversation.status === 'online';
    const ollamaOnline = services.ollama && services.ollama.status === 'online';

    if (conversationOnline && ollamaOnline) {
        conversationTestLink.style.display = 'inline-block';
        conversationTestLink.style.opacity = '1';
        conversationTestLink.title = 'Servicios Conversation y Ollama están activos';
    } else {
        conversationTestLink.style.display = 'none';
    }

    // Check if all VTuber Chat services are online (Conversation, Gateway, Face, Blips)
    const vtuberChatLink = document.getElementById('vtuberChatLink');
    const gatewayOnline = services.gateway && services.gateway.status === 'online';
    const faceOnline = services.face && services.face.status === 'online';

    if (conversationOnline && ollamaOnline && gatewayOnline && blipsOnline) {
        vtuberChatLink.style.display = 'inline-block';
        vtuberChatLink.style.opacity = '1';
        vtuberChatLink.title = 'Sistema completo: Conversation, Ollama, Gateway, Face y Blips activos';
    } else {
        vtuberChatLink.style.display = 'none';
        let missing = [];
        if (!conversationOnline) missing.push('Conversation');
        if (!ollamaOnline) missing.push('Ollama');
        if (!gatewayOnline) missing.push('Gateway');
        if (!blipsOnline) missing.push('Blips');
        vtuberChatLink.title = `Falta: ${missing.join(', ')}`;
    }

    for (const [serviceId, service] of Object.entries(services)) {
        console.log(`Processing service: ${serviceId}`, service);
        const metric = metrics ? metrics[serviceId] : null;

        const item = document.createElement('div');
        item.className = `service-item ${service.status}`;
        const canManage = service.manageable || false;

        item.innerHTML = `
            <div class="service-header">
                <span class="service-name">${service.name}</span>
                <span class="service-status ${service.status}">${service.status}</span>
            </div>
            <div class="service-metrics">
                <div class="metric">
                    <span class="metric-label">Port</span>
                    <span class="metric-value">${service.port}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Response Time</span>
                    <span class="metric-value">${service.response_time_ms ? service.response_time_ms + 'ms' : '-'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime</span>
                    <span class="metric-value">${metric ? metric.uptime_percentage.toFixed(1) + '%' : '-'}</span>
                </div>
            </div>
            ${metric ? `
                <div class="progress-bar">
                    <div class="progress-fill ${metric.uptime_percentage < 90 ? 'warning' : ''}"
                         style="width: ${metric.uptime_percentage}%"></div>
                </div>
            ` : ''}
            ${service.managed_by === 'docker' ? `
                <div class="service-controls">
                    <p style="margin: 10px 0 0 0; padding: 8px; background: #e3f2fd; border-radius: 4px; font-size: 13px; color: #1976d2;">
                        <strong>🐳 Controlado por Docker:</strong> Use los botones en la sección "Docker & GPU Stats" arriba.
                    </p>
                </div>
            ` : canManage ? `
                <div class="service-controls">
                    <div class="control-buttons">
                        <button class="btn btn-small btn-start" onclick="controlService('${serviceId}', 'start')">
                            <span>▶</span> Start
                        </button>
                        <button class="btn btn-small btn-stop" onclick="controlService('${serviceId}', 'stop')">
                            <span>⏹</span> Stop
                        </button>
                        <button class="btn btn-small btn-restart" onclick="controlService('${serviceId}', 'restart')">
                            <span>🔄</span> Restart
                        </button>
                    </div>
                </div>
            ` : ''}
        `;
        container.appendChild(item);

        // Track response times for chart
        if (service.status === 'online' && service.response_time_ms) {
            if (!responseTimeData[serviceId]) {
                responseTimeData[serviceId] = [];
            }
            responseTimeData[serviceId].push(service.response_time_ms);
            if (responseTimeData[serviceId].length > 10) {
                responseTimeData[serviceId].shift();
            }
        }
    }

    // Update chart
    updateResponseChart();
}

function updateActiveServicesList(services) {
    const container = document.getElementById('activeServicesList');
    container.innerHTML = '';

    // Filter only online services
    const onlineServices = Object.entries(services).filter(([id, svc]) => svc.status === 'online');

    if (onlineServices.length === 0) {
        container.innerHTML = '<div class="no-data">No active services</div>';
        return;
    }

    onlineServices.forEach(([serviceId, service]) => {
        const item = document.createElement('div');
        item.className = 'active-service-item online';
        item.onclick = () => viewServiceLogs(serviceId, service.name);

        item.innerHTML = `
            <div>
                <span class="service-name">${service.name}</span>
                <span class="service-port">:${service.port}</span>
            </div>
            <span class="view-logs-icon">📋</span>
        `;

        container.appendChild(item);
    });
}

function updateResponseChart() {
    const container = document.getElementById('responseChart');
    if (Object.keys(responseTimeData).length === 0) {
        container.innerHTML = '<div class="no-data">No data yet</div>';
        return;
    }

    // Get average response times across all services
    const avgTimes = [];
    const maxLength = Math.max(...Object.values(responseTimeData).map(arr => arr.length));

    for (let i = 0; i < maxLength; i++) {
        let sum = 0;
        let count = 0;
        for (const times of Object.values(responseTimeData)) {
            if (times[i] !== undefined) {
                sum += times[i];
                count++;
            }
        }
        avgTimes.push(count > 0 ? sum / count : 0);
    }

    const maxTime = Math.max(...avgTimes, 100);

    container.innerHTML = '<div class="chart-container"></div>';
    const chartContainer = container.querySelector('.chart-container');

    avgTimes.forEach(time => {
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        const height = (time / maxTime) * 180;
        bar.style.height = `${height}px`;
        bar.title = `${time.toFixed(2)}ms`;
        chartContainer.appendChild(bar);
    });
}

async function fetchDockerStats() {
    try {
        const [statusRes, statsRes, gpuRes] = await Promise.all([
            fetch('/api/docker/status'),
            fetch('/api/docker/stats'),
            fetch('/api/gpu/stats')
        ]);

        const statusData = await statusRes.json();
        const statsData = await statsRes.json();
        const gpuData = await gpuRes.json();

        // Update Docker status
        document.getElementById('dockerStatus').textContent =
            statusData.running ? 'Running' : 'Stopped';

        // Update Docker stats
        if (statsData.stats && !statsData.stats.error) {
            document.getElementById('dockerCPU').textContent = statsData.stats.cpu_percent || '-';
            document.getElementById('dockerMem').textContent = statsData.stats.memory_usage || '-';
        }

        // Update GPU stats
        if (gpuData.gpu && !gpuData.gpu.error) {
            document.getElementById('gpuUtil').textContent =
                `${gpuData.gpu.gpu_utilization_percent}%`;
            document.getElementById('vramUsage').textContent =
                `${(gpuData.gpu.memory_used_mb / 1024).toFixed(1)}GB / ${(gpuData.gpu.memory_total_mb / 1024).toFixed(1)}GB`;
            document.getElementById('gpuTemp').textContent =
                `${gpuData.gpu.temperature_celsius}°C`;
        }
    } catch (error) {
        console.error('Error fetching Docker/GPU stats:', error);
    }
}

// Control functions
async function controlDocker(action) {
    // Security confirmation for critical operations
    if (action === 'stop') {
        const confirm = window.confirm(
            '⚠️ ¿Detener el contenedor Docker?\n\n' +
            'Esto DETENDRÁ el contenedor Fish Speech sin eliminarlo.\n' +
            'Podrás reiniciarlo después con el botón Start.'
        );
        if (!confirm) return;
    } else if (action === 'restart') {
        const confirm = window.confirm(
            '🔄 ¿Reiniciar el contenedor Docker?\n\n' +
            'Esto detendrá y volverá a iniciar el contenedor Fish Speech.\n' +
            'La operación puede tardar unos segundos.'
        );
        if (!confirm) return;
    }

    const btn = document.getElementById(`docker${action.charAt(0).toUpperCase() + action.slice(1)}Btn`);
    const originalHTML = btn.innerHTML;

    try {
        // Disable button and show loading
        btn.disabled = true;
        btn.innerHTML = `<span class="loading-spinner"></span> ${action}ing...`;

        const response = await fetch(`/api/docker/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.ok) {
            alert(`✅ Docker ${action} exitoso!`);
            // Refresh Docker stats immediately
            await fetchDockerStats();
        } else {
            alert(`❌ Docker ${action} falló: ${data.error || 'Error desconocido'}`);
        }
    } catch (error) {
        console.error(`Error ${action}ing Docker:`, error);
        alert(`❌ Error al ejecutar ${action} en Docker: ${error.message}`);
    } finally {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

async function removeDocker() {
    // Double confirmation for destructive operation
    const confirm1 = window.confirm(
        '⚠️ ADVERTENCIA: Operación Destructiva ⚠️\n\n' +
        '¿Estás seguro de que deseas ELIMINAR el contenedor Docker?\n\n' +
        'Esto ejecutará "docker-compose down" que:\n' +
        '• Detendrá el contenedor\n' +
        '• ELIMINARÁ el contenedor\n' +
        '• Liberará los recursos\n\n' +
        'Tendrás que volver a crearlo con "Start" después.'
    );
    if (!confirm1) return;

    const confirm2 = window.confirm(
        '⚠️ CONFIRMACIÓN FINAL ⚠️\n\n' +
        '¿REALMENTE deseas eliminar el contenedor Fish Speech?\n\n' +
        'Esta acción NO se puede deshacer.'
    );
    if (!confirm2) return;

    const btn = document.getElementById('dockerRemoveBtn');
    const originalHTML = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = `<span class="loading-spinner"></span> Removing...`;

        const response = await fetch('/api/docker/remove?confirm=true', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.ok) {
            alert('✅ Contenedor Docker eliminado exitosamente!');
            await fetchDockerStats();
        } else {
            alert(`❌ Error al eliminar Docker: ${data.error || 'Error desconocido'}`);
        }
    } catch (error) {
        console.error('Error removing Docker:', error);
        alert(`❌ Error al eliminar Docker: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

async function controlService(serviceId, action) {
    // Security confirmation for critical operations
    if (action === 'stop') {
        const confirm = window.confirm(
            `⚠️ ¿Detener el servicio "${serviceId}"?\n\n` +
            'El servicio dejará de estar disponible hasta que lo inicies nuevamente.'
        );
        if (!confirm) return;
    } else if (action === 'restart') {
        const confirm = window.confirm(
            `🔄 ¿Reiniciar el servicio "${serviceId}"?\n\n` +
            'El servicio se detendrá y volverá a iniciarse.\n' +
            'Esto puede causar una interrupción temporal.'
        );
        if (!confirm) return;
    }

    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;

    // Create status message element
    const serviceItem = btn.closest('.service-item');
    let statusMsg = serviceItem.querySelector('.service-status-msg');
    if (!statusMsg) {
        statusMsg = document.createElement('div');
        statusMsg.className = 'service-status-msg';
        statusMsg.style.cssText = 'margin-top: 10px; padding: 8px; background: #fff3cd; border-radius: 4px; font-size: 13px;';
        serviceItem.appendChild(statusMsg);
    }

    try {
        // Disable button and show loading
        btn.disabled = true;
        btn.innerHTML = `<span class="loading-spinner"></span>`;

        if (action === 'start') {
            statusMsg.style.background = '#fff3cd';
            statusMsg.style.color = '#856404';
            statusMsg.innerHTML = '⏳ Iniciando servicio... Esto puede tardar hasta 30 segundos.';
        } else if (action === 'stop') {
            statusMsg.style.background = '#fff3cd';
            statusMsg.style.color = '#856404';
            statusMsg.innerHTML = '⏳ Deteniendo servicio...';
        } else if (action === 'restart') {
            statusMsg.style.background = '#fff3cd';
            statusMsg.style.color = '#856404';
            statusMsg.innerHTML = '⏳ Reiniciando servicio... Esto puede tardar hasta 30 segundos.';
        }

        const response = await fetch(`/api/services/${serviceId}/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.ok) {
            statusMsg.style.background = '#d4edda';
            statusMsg.style.color = '#155724';
            statusMsg.innerHTML = `✅ Servicio ${serviceId} ${action === 'start' ? 'iniciado' : action === 'stop' ? 'detenido' : 'reiniciado'} exitosamente!`;

            // Remove message after 3 seconds
            setTimeout(() => statusMsg.remove(), 3000);

            // Trigger a manual status refresh
            const statusRes = await fetch('/api/services/status');
            const statusData = await statusRes.json();
            const metricsRes = await fetch('/api/monitoring/metrics');
            const metricsData = await metricsRes.json();
            updateServicesList(statusData, metricsData.metrics);
        } else {
            statusMsg.style.background = '#f8d7da';
            statusMsg.style.color = '#721c24';
            statusMsg.innerHTML = `❌ Error: ${data.detail || 'Error desconocido'}`;
            setTimeout(() => statusMsg.remove(), 5000);
        }
    } catch (error) {
        console.error(`Error ${action}ing service:`, error);
        statusMsg.style.background = '#f8d7da';
        statusMsg.style.color = '#721c24';
        statusMsg.innerHTML = `❌ Error: ${error.message}`;
        setTimeout(() => statusMsg.remove(), 5000);
    } finally {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

// Logs Modal Functions
async function viewServiceLogs(serviceId, serviceName) {
    const modal = document.getElementById('logsModal');
    const title = document.getElementById('logsModalTitle');
    const content = document.getElementById('logsModalContent');

    // Show modal
    modal.classList.add('active');
    title.textContent = `Logs: ${serviceName}`;
    content.innerHTML = '<div class="no-data">Loading logs...</div>';

    try {
        const response = await fetch(`/api/logs/service/${serviceId}?limit=50`);
        const data = await response.json();

        if (data.ok && data.logs && data.logs.length > 0) {
            content.innerHTML = '';

            data.logs.forEach(log => {
                const logEntry = document.createElement('div');
                logEntry.className = `log-entry ${log.success ? 'success' : 'error'}`;

                const timestamp = new Date(log.timestamp).toLocaleString();
                const action = log.action || log.event_type || 'Unknown';
                const duration = log.duration_ms ? `${log.duration_ms.toFixed(0)}ms` : '-';
                const status = log.final_status || (log.success ? 'Success' : 'Error');

                logEntry.innerHTML = `
                    <div class="log-entry-header">
                        <span>${action.toUpperCase()}</span>
                        <span class="log-entry-time">${timestamp}</span>
                    </div>
                    <div class="log-entry-body">
                        <strong>Status:</strong> ${status}<br>
                        <strong>Duration:</strong> ${duration}
                        ${log.error ? `<br><strong>Error:</strong> <span style="color: #f44336;">${log.error}</span>` : ''}
                        ${log.port ? `<br><strong>Port:</strong> ${log.port}` : ''}
                    </div>
                `;

                content.appendChild(logEntry);
            });
        } else {
            content.innerHTML = '<div class="no-data">No logs found for this service</div>';
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        content.innerHTML = `<div class="no-data" style="color: #f44336;">Error loading logs: ${error.message}</div>`;
    }
}

function closeLogsModal() {
    document.getElementById('logsModal').classList.remove('active');
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('logsModal');
    if (e.target === modal) {
        closeLogsModal();
    }
});

// Initialize immediately (script is loaded at end of body)
connectWebSocket();
// Fetch Docker stats immediately on load
fetchDockerStats();
// Also fetch Docker stats every 10 seconds
setInterval(fetchDockerStats, 10000);
