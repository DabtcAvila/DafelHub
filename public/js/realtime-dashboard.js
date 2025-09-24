/**
 * Real-time Monitoring Dashboard Integration
 * Connects frontend dashboard with Python backend WebSocket server
 * Provides live system metrics, alerts, and performance monitoring
 */

class RealtimeDashboard {
    constructor(options = {}) {
        this.options = {
            wsUrl: options.wsUrl || 'ws://localhost:8081/ws/metrics',
            apiUrl: options.apiUrl || 'http://localhost:8081/api/realtime',
            reconnectInterval: options.reconnectInterval || 5000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            chartHistoryLength: options.chartHistoryLength || 50,
            ...options
        };

        // Connection state
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;

        // Data storage
        this.metricsData = {
            system: new Map(),
            application: new Map(),
            alerts: [],
            events: []
        };

        // Charts and UI components
        this.charts = new Map();
        this.alertContainer = null;
        this.statusIndicator = null;

        // Performance tracking
        this.stats = {
            messagesReceived: 0,
            lastUpdate: null,
            connectionUptime: null,
            dataPoints: 0
        };

        this.init();
    }

    async init() {
        try {
            // Initialize UI components
            this.initializeUI();
            
            // Connect to WebSocket
            await this.connect();
            
            // Start heartbeat monitoring
            this.startHeartbeat();
            
            console.log('🚀 Real-time Dashboard initialized');
        } catch (error) {
            console.error('Dashboard initialization failed:', error);
            this.showConnectionError('Failed to initialize dashboard');
        }
    }

    initializeUI() {
        // Create status indicator
        this.createStatusIndicator();
        
        // Create alerts container
        this.createAlertsContainer();
        
        // Initialize charts
        this.initializeCharts();
        
        // Setup refresh controls
        this.setupControls();
    }

    createStatusIndicator() {
        const statusContainer = document.createElement('div');
        statusContainer.className = 'connection-status';
        statusContainer.innerHTML = `
            <div class="status-indicator">
                <span class="status-dot disconnected"></span>
                <span class="status-text">Connecting...</span>
                <span class="status-details"></span>
            </div>
        `;

        // Add to dashboard header
        const header = document.querySelector('.dashboard-header') || document.body;
        header.appendChild(statusContainer);
        
        this.statusIndicator = statusContainer;
    }

    createAlertsContainer() {
        const alertsSection = document.querySelector('#performance-alerts') || document.createElement('div');
        if (!alertsSection.id) {
            alertsSection.id = 'performance-alerts';
            alertsSection.innerHTML = '<h3>Real-time Alerts</h3><div class="alerts-list"></div>';
            document.body.appendChild(alertsSection);
        }
        
        this.alertContainer = alertsSection.querySelector('.alerts-list');
    }

    initializeCharts() {
        // Real-time system metrics chart
        this.createChart('system-metrics', {
            type: 'line',
            title: 'System Metrics (Real-time)',
            datasets: [
                { label: 'CPU %', color: '#ff6384', data: [] },
                { label: 'Memory %', color: '#36a2eb', data: [] },
                { label: 'Disk %', color: '#ffcd56', data: [] }
            ]
        });

        // Network activity chart
        this.createChart('network-activity', {
            type: 'line',
            title: 'Network Activity',
            datasets: [
                { label: 'Bytes Sent/sec', color: '#4bc0c0', data: [] },
                { label: 'Bytes Recv/sec', color: '#9966ff', data: [] }
            ]
        });

        // Performance scores chart
        this.createChart('performance-scores', {
            type: 'radar',
            title: 'Performance Scores',
            datasets: [
                { label: 'Current Scores', color: '#ff9f40', data: [] }
            ]
        });

        // Active processes chart
        this.createChart('process-metrics', {
            type: 'bar',
            title: 'Process Metrics',
            datasets: [
                { label: 'Process Count', color: '#ff6384', data: [] },
                { label: 'Thread Count', color: '#36a2eb', data: [] }
            ]
        });
    }

    createChart(chartId, config) {
        const container = document.createElement('div');
        container.className = 'chart-container realtime-chart';
        container.innerHTML = `
            <h3 class="chart-title">${config.title}</h3>
            <div class="canvas-container">
                <canvas id="${chartId}"></canvas>
            </div>
            <div class="chart-stats">
                <span class="data-points">0 points</span>
                <span class="last-update">Never</span>
            </div>
        `;

        // Add to charts section or create one
        let chartsSection = document.querySelector('.realtime-charts');
        if (!chartsSection) {
            chartsSection = document.createElement('section');
            chartsSection.className = 'charts-section realtime-charts';
            chartsSection.innerHTML = '<h2 class="section-title">Real-time Metrics</h2><div class="charts-grid"></div>';
            document.body.appendChild(chartsSection);
        }

        chartsSection.querySelector('.charts-grid').appendChild(container);

        // Initialize Chart.js chart
        const canvas = container.querySelector('canvas');
        const ctx = canvas.getContext('2d');

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: config.type !== 'radar' ? {
                x: {
                    type: 'time',
                    time: {
                        unit: 'second',
                        displayFormats: {
                            second: 'HH:mm:ss'
                        }
                    }
                },
                y: {
                    beginAtZero: true
                }
            } : {}
        };

        const chart = new Chart(ctx, {
            type: config.type,
            data: {
                labels: [],
                datasets: config.datasets.map(dataset => ({
                    label: dataset.label,
                    data: dataset.data,
                    borderColor: dataset.color,
                    backgroundColor: dataset.color + '20',
                    tension: 0.4,
                    pointRadius: 2
                }))
            },
            options: chartOptions
        });

        this.charts.set(chartId, { chart, container, config });
    }

    setupControls() {
        const controlsContainer = document.createElement('div');
        controlsContainer.className = 'realtime-controls';
        controlsContainer.innerHTML = `
            <div class="controls-section">
                <h3>Real-time Controls</h3>
                <div class="control-buttons">
                    <button id="toggle-connection" class="btn btn-primary">Disconnect</button>
                    <button id="clear-data" class="btn btn-secondary">Clear Data</button>
                    <button id="export-data" class="btn btn-secondary">Export Data</button>
                    <button id="toggle-alerts" class="btn btn-secondary">Mute Alerts</button>
                </div>
                <div class="connection-info">
                    <div class="info-item">
                        <span class="label">Messages:</span>
                        <span id="message-count">0</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Data Points:</span>
                        <span id="data-points">0</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Uptime:</span>
                        <span id="connection-uptime">0s</span>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(controlsContainer);

        // Setup event listeners
        document.getElementById('toggle-connection').addEventListener('click', () => {
            if (this.isConnected) {
                this.disconnect();
            } else {
                this.connect();
            }
        });

        document.getElementById('clear-data').addEventListener('click', () => {
            this.clearAllData();
        });

        document.getElementById('export-data').addEventListener('click', () => {
            this.exportData();
        });

        document.getElementById('toggle-alerts').addEventListener('click', (e) => {
            this.muteAlerts = !this.muteAlerts;
            e.target.textContent = this.muteAlerts ? 'Unmute Alerts' : 'Mute Alerts';
        });
    }

    async connect() {
        try {
            if (this.websocket) {
                this.websocket.close();
            }

            this.updateStatus('connecting', 'Connecting to real-time server...');
            
            this.websocket = new WebSocket(this.options.wsUrl);
            
            this.websocket.onopen = (event) => {
                this.onConnectionOpen(event);
            };

            this.websocket.onmessage = (event) => {
                this.onMessage(event);
            };

            this.websocket.onclose = (event) => {
                this.onConnectionClose(event);
            };

            this.websocket.onerror = (event) => {
                this.onConnectionError(event);
            };

        } catch (error) {
            console.error('Connection failed:', error);
            this.handleConnectionError();
        }
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close();
        }
        this.updateStatus('disconnected', 'Disconnected');
    }

    onConnectionOpen(event) {
        console.log('✅ Connected to real-time monitoring server');
        
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.stats.connectionUptime = Date.now();
        
        this.updateStatus('connected', 'Connected to real-time server');
        this.updateConnectionButton();
        
        // Send initial ping
        this.sendMessage({ type: 'ping', timestamp: Date.now() });
    }

    onMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this.stats.messagesReceived++;
            this.stats.lastUpdate = Date.now();
            
            this.handleMessage(message);
            this.updateStats();
            
        } catch (error) {
            console.error('Failed to parse message:', error);
        }
    }

    onConnectionClose(event) {
        console.log('🔌 Connection closed:', event.code, event.reason);
        
        this.isConnected = false;
        this.updateStatus('disconnected', `Connection closed (${event.code})`);
        this.updateConnectionButton();
        
        // Attempt reconnection if not intentional
        if (!event.wasClean && this.reconnectAttempts < this.options.maxReconnectAttempts) {
            this.scheduleReconnect();
        }
    }

    onConnectionError(event) {
        console.error('❌ WebSocket error:', event);
        this.handleConnectionError();
    }

    handleConnectionError() {
        this.isConnected = false;
        this.updateStatus('error', 'Connection error');
        this.scheduleReconnect();
    }

    scheduleReconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }

        this.reconnectAttempts++;
        const delay = Math.min(this.options.reconnectInterval * this.reconnectAttempts, 30000);
        
        this.updateStatus('reconnecting', `Reconnecting in ${delay/1000}s... (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`);
        
        this.reconnectTimer = setTimeout(() => {
            if (!this.isConnected) {
                this.connect();
            }
        }, delay);
    }

    handleMessage(message) {
        switch (message.type) {
            case 'connection_established':
                this.handleConnectionEstablished(message);
                break;
            case 'metrics_update':
                this.handleMetricsUpdate(message);
                break;
            case 'system_update':
                this.handleSystemUpdate(message);
                break;
            case 'alerts_update':
                this.handleAlertsUpdate(message);
                break;
            case 'heartbeat':
                this.handleHeartbeat(message);
                break;
            case 'pong':
                // Handle pong response
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    handleConnectionEstablished(message) {
        console.log('🎯 Connection established:', message.client_id);
        
        // Load initial data
        if (message.data) {
            this.loadInitialData(message.data);
        }
    }

    handleMetricsUpdate(message) {
        const data = message.data;
        
        // Update metrics data
        if (data.samples) {
            data.samples.forEach(sample => {
                this.addMetricSample(sample);
            });
        }

        // Update performance dashboard if available
        if (window.dashboard && data.families) {
            this.updatePerformanceDashboard(data);
        }
    }

    handleSystemUpdate(message) {
        const systemData = message.data;
        const timestamp = new Date(message.timestamp * 1000);
        
        // Update system charts
        this.updateSystemCharts(systemData, timestamp);
        
        // Update system stats display
        this.updateSystemStats(systemData);
    }

    handleAlertsUpdate(message) {
        const alertsData = message.data;
        
        // Update alerts display
        if (alertsData.active_alerts) {
            this.updateActiveAlerts(alertsData.active_alerts);
        }
        
        // Show new alerts
        if (alertsData.new_alerts && alertsData.new_alerts.length > 0) {
            alertsData.new_alerts.forEach(alert => {
                this.showAlert(alert);
            });
        }
    }

    handleHeartbeat(message) {
        // Update server stats
        const serverData = message.data;
        this.updateServerStats(serverData);
    }

    updateSystemCharts(systemData, timestamp) {
        const systemChart = this.charts.get('system-metrics');
        if (systemChart) {
            const chart = systemChart.chart;
            
            // Add new data point
            chart.data.labels.push(timestamp);
            chart.data.datasets[0].data.push(systemData.cpu.percent);
            chart.data.datasets[1].data.push(systemData.memory.percent);
            chart.data.datasets[2].data.push(systemData.disk.percent);
            
            // Keep only recent data
            if (chart.data.labels.length > this.options.chartHistoryLength) {
                chart.data.labels.shift();
                chart.data.datasets.forEach(dataset => dataset.data.shift());
            }
            
            chart.update('none');
            this.updateChartStats('system-metrics', chart.data.labels.length);
        }

        // Update network chart
        this.updateNetworkChart(systemData.network, timestamp);
    }

    updateNetworkChart(networkData, timestamp) {
        const networkChart = this.charts.get('network-activity');
        if (networkChart && this.lastNetworkData) {
            const chart = networkChart.chart;
            
            // Calculate rates (bytes per second)
            const timeDiff = (timestamp - this.lastNetworkTimestamp) / 1000; // seconds
            const bytesSentRate = (networkData.bytes_sent - this.lastNetworkData.bytes_sent) / timeDiff;
            const bytesRecvRate = (networkData.bytes_recv - this.lastNetworkData.bytes_recv) / timeDiff;
            
            chart.data.labels.push(timestamp);
            chart.data.datasets[0].data.push(Math.max(0, bytesSentRate));
            chart.data.datasets[1].data.push(Math.max(0, bytesRecvRate));
            
            if (chart.data.labels.length > this.options.chartHistoryLength) {
                chart.data.labels.shift();
                chart.data.datasets.forEach(dataset => dataset.data.shift());
            }
            
            chart.update('none');
        }
        
        this.lastNetworkData = networkData;
        this.lastNetworkTimestamp = timestamp;
    }

    addMetricSample(sample) {
        const key = `${sample.name}_${JSON.stringify(sample.labels)}`;
        
        if (!this.metricsData.system.has(key)) {
            this.metricsData.system.set(key, []);
        }
        
        const samples = this.metricsData.system.get(key);
        samples.push({
            timestamp: sample.timestamp * 1000, // Convert to milliseconds
            value: sample.value
        });
        
        // Keep only recent samples
        if (samples.length > this.options.chartHistoryLength * 2) {
            samples.splice(0, samples.length - this.options.chartHistoryLength * 2);
        }
        
        this.stats.dataPoints++;
    }

    updateActiveAlerts(alerts) {
        if (!this.alertContainer) return;
        
        this.metricsData.alerts = alerts;
        
        if (alerts.length === 0) {
            this.alertContainer.innerHTML = '<div class="no-alerts">✅ No active alerts</div>';
            return;
        }

        const alertsHtml = alerts.map(alert => {
            const severityClass = alert.severity.toLowerCase();
            const timeStr = new Date(alert.firing_time * 1000).toLocaleString();
            
            return `
                <div class="alert alert-${severityClass} realtime-alert" data-alert-id="${alert.id}">
                    <div class="alert-header">
                        <span class="alert-severity">${alert.severity.toUpperCase()}</span>
                        <span class="alert-time">${timeStr}</span>
                    </div>
                    <div class="alert-title">${alert.title}</div>
                    <div class="alert-message">${alert.message}</div>
                    <div class="alert-labels">
                        ${Object.entries(alert.labels).map(([k, v]) => 
                            `<span class="label">${k}: ${v}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }).join('');
        
        this.alertContainer.innerHTML = alertsHtml;
    }

    showAlert(alert) {
        if (this.muteAlerts) return;
        
        // Show browser notification if permitted
        if (Notification.permission === 'granted') {
            new Notification(`DafelHub Alert: ${alert.severity.toUpperCase()}`, {
                body: alert.title,
                icon: '/favicon.ico',
                tag: alert.id
            });
        }
        
        // Show toast notification
        this.showToast(`${alert.severity.toUpperCase()}: ${alert.title}`, alert.severity);
    }

    showToast(message, severity) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${severity.toLowerCase()}`;
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-icon">${this.getAlertIcon(severity)}</span>
                <span class="toast-message">${message}</span>
            </div>
            <button class="toast-close">&times;</button>
        `;
        
        // Add to page
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
        
        // Manual close
        toast.querySelector('.toast-close').addEventListener('click', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }

    getAlertIcon(severity) {
        const icons = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '⚠️',
            'low': 'ℹ️',
            'info': 'ℹ️'
        };
        return icons[severity.toLowerCase()] || 'ℹ️';
    }

    updateStatus(status, message) {
        if (!this.statusIndicator) return;
        
        const dot = this.statusIndicator.querySelector('.status-dot');
        const text = this.statusIndicator.querySelector('.status-text');
        const details = this.statusIndicator.querySelector('.status-details');
        
        dot.className = `status-dot ${status}`;
        text.textContent = this.getStatusText(status);
        details.textContent = message;
    }

    getStatusText(status) {
        const statusTexts = {
            'connected': '🟢 Connected',
            'connecting': '🟡 Connecting',
            'reconnecting': '🟡 Reconnecting',
            'disconnected': '🔴 Disconnected',
            'error': '❌ Error'
        };
        return statusTexts[status] || status;
    }

    updateConnectionButton() {
        const button = document.getElementById('toggle-connection');
        if (button) {
            button.textContent = this.isConnected ? 'Disconnect' : 'Connect';
            button.className = this.isConnected ? 'btn btn-danger' : 'btn btn-success';
        }
    }

    updateStats() {
        // Update message count
        const messageCount = document.getElementById('message-count');
        if (messageCount) {
            messageCount.textContent = this.stats.messagesReceived;
        }
        
        // Update data points
        const dataPoints = document.getElementById('data-points');
        if (dataPoints) {
            dataPoints.textContent = this.stats.dataPoints;
        }
        
        // Update uptime
        const uptime = document.getElementById('connection-uptime');
        if (uptime && this.stats.connectionUptime) {
            const uptimeSeconds = Math.floor((Date.now() - this.stats.connectionUptime) / 1000);
            uptime.textContent = this.formatDuration(uptimeSeconds);
        }
    }

    updateChartStats(chartId, dataPoints) {
        const chartContainer = this.charts.get(chartId)?.container;
        if (chartContainer) {
            const dataPointsSpan = chartContainer.querySelector('.data-points');
            const lastUpdateSpan = chartContainer.querySelector('.last-update');
            
            if (dataPointsSpan) {
                dataPointsSpan.textContent = `${dataPoints} points`;
            }
            if (lastUpdateSpan) {
                lastUpdateSpan.textContent = new Date().toLocaleTimeString();
            }
        }
    }

    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
    }

    sendMessage(message) {
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify(message));
        }
    }

    startHeartbeat() {
        setInterval(() => {
            if (this.isConnected) {
                this.sendMessage({ type: 'ping', timestamp: Date.now() });
            }
        }, 30000); // Every 30 seconds
    }

    clearAllData() {
        // Clear metrics data
        this.metricsData.system.clear();
        this.metricsData.application.clear();
        this.metricsData.alerts = [];
        this.metricsData.events = [];
        
        // Clear charts
        this.charts.forEach((chartData, chartId) => {
            const chart = chartData.chart;
            chart.data.labels = [];
            chart.data.datasets.forEach(dataset => {
                dataset.data = [];
            });
            chart.update();
        });
        
        // Reset stats
        this.stats.dataPoints = 0;
        
        console.log('🧹 All data cleared');
    }

    exportData() {
        const exportData = {
            timestamp: Date.now(),
            stats: this.stats,
            metrics: {
                system: Object.fromEntries(this.metricsData.system),
                application: Object.fromEntries(this.metricsData.application),
                alerts: this.metricsData.alerts,
                events: this.metricsData.events
            }
        };
        
        const dataStr = JSON.stringify(exportData, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `dafelhub-monitoring-${new Date().toISOString().slice(0, 19)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
        
        console.log('📁 Data exported');
    }

    async fetchServerStatus() {
        try {
            const response = await fetch(`${this.options.apiUrl}/status`);
            return await response.json();
        } catch (error) {
            console.error('Failed to fetch server status:', error);
            return null;
        }
    }

    destroy() {
        // Disconnect WebSocket
        if (this.websocket) {
            this.websocket.close();
        }
        
        // Clear timers
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        // Destroy charts
        this.charts.forEach(chartData => {
            chartData.chart.destroy();
        });
        this.charts.clear();
        
        // Clear data
        this.metricsData.system.clear();
        this.metricsData.application.clear();
        
        console.log('🔄 Real-time dashboard destroyed');
    }
}

// Auto-initialize if not disabled
if (typeof window !== 'undefined' && !window.DISABLE_REALTIME_DASHBOARD) {
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Initialize dashboard when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.realtimeDashboard = new RealtimeDashboard();
        });
    } else {
        window.realtimeDashboard = new RealtimeDashboard();
    }
}

// Export for manual initialization
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RealtimeDashboard;
} else if (typeof window !== 'undefined') {
    window.RealtimeDashboard = RealtimeDashboard;
}