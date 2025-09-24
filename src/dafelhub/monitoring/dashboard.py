"""
Real-time Monitoring Dashboard
Live metrics visualization and system monitoring interface
@module dafelhub.monitoring.dashboard
"""

import json
import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import socket
import webbrowser
from collections import defaultdict, deque

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .metrics_collector import MetricsCollector, get_metrics_collector
from .logger import Logger, get_logger


class MetricHistory:
    """Store historical metric data for dashboard charts"""
    
    def __init__(self, max_points: int = 100):
        self.max_points = max_points
        self.data: deque = deque(maxlen=max_points)
    
    def add_point(self, timestamp: float, value: float):
        """Add a data point"""
        self.data.append({"timestamp": timestamp, "value": value})
    
    def get_points(self, duration_minutes: int = 60) -> List[Dict]:
        """Get data points for the last N minutes"""
        cutoff = time.time() - (duration_minutes * 60)
        return [point for point in self.data if point["timestamp"] >= cutoff]
    
    def get_latest(self) -> Optional[Dict]:
        """Get latest data point"""
        return self.data[-1] if self.data else None


class DashboardData:
    """Manage dashboard data and history"""
    
    def __init__(self):
        self.metric_histories: Dict[str, MetricHistory] = defaultdict(lambda: MetricHistory())
        self.system_stats = {}
        self.alert_history: deque = deque(maxlen=50)
        self.last_update = time.time()
    
    def update_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """Update metric history"""
        key = f"{name}_{hash(str(sorted((labels or {}).items())))}"
        self.metric_histories[key].add_point(time.time(), value)
    
    def add_alert(self, alert: Dict[str, Any]):
        """Add alert to history"""
        alert["timestamp"] = time.time()
        self.alert_history.appendleft(alert)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data"""
        return {
            "timestamp": time.time(),
            "system_stats": self.system_stats,
            "metrics": {
                key: history.get_points() 
                for key, history in self.metric_histories.items()
            },
            "alerts": list(self.alert_history)[:10],  # Latest 10 alerts
            "uptime": time.time() - self.last_update
        }


class WebSocketManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSockets"""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


class MonitoringDashboard:
    """
    Real-time Monitoring Dashboard
    
    Features:
    - Live metrics visualization with charts
    - System resource monitoring (CPU, Memory, Disk, Network)
    - Alert management and history
    - WebSocket-based real-time updates
    - REST API for metrics data
    - Customizable dashboard layout
    - Historical data analysis
    """
    
    def __init__(self,
                 host: str = "localhost",
                 port: int = 8080,
                 metrics_collector: Optional[MetricsCollector] = None,
                 logger: Optional[Logger] = None,
                 update_interval: float = 5.0):
        
        self.host = host
        self.port = port
        self.update_interval = update_interval
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.logger = logger or get_logger()
        
        if not FASTAPI_AVAILABLE:
            self.logger.error("FastAPI is required for dashboard. Install with: pip install fastapi uvicorn")
            raise ImportError("FastAPI is required for dashboard")
        
        self.dashboard_data = DashboardData()
        self.websocket_manager = WebSocketManager()
        
        # Create FastAPI app
        self.app = FastAPI(title="DafelHub Monitoring Dashboard", version="1.0.0")
        self.setup_routes()
        
        # Background task for data collection
        self.running = False
        self.update_task = None
    
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Dashboard home page"""
            return self.get_dashboard_html()
        
        @self.app.get("/api/metrics")
        async def get_metrics():
            """Get current metrics"""
            return JSONResponse(self.get_metrics_data())
        
        @self.app.get("/api/metrics/prometheus")
        async def get_prometheus_metrics():
            """Get metrics in Prometheus format"""
            return self.metrics_collector.export_prometheus()
        
        @self.app.get("/api/metrics/json")
        async def get_json_metrics():
            """Get metrics in JSON format"""
            return JSONResponse(json.loads(self.metrics_collector.export_json()))
        
        @self.app.get("/api/system")
        async def get_system_stats():
            """Get system statistics"""
            return JSONResponse(self.get_system_stats())
        
        @self.app.get("/api/alerts")
        async def get_alerts():
            """Get alert history"""
            return JSONResponse(list(self.dashboard_data.alert_history))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    # Send periodic updates
                    data = self.dashboard_data.get_dashboard_data()
                    await self.websocket_manager.send_personal_message(
                        json.dumps(data), websocket
                    )
                    await asyncio.sleep(self.update_interval)
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
    
    def get_dashboard_html(self) -> str:
        """Generate dashboard HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>DafelHub Monitoring Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #f5f5f7;
                    color: #1d1d1f;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.07);
                    margin-bottom: 20px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                .stat-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.07);
                }}
                .stat-value {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #007AFF;
                }}
                .stat-label {{
                    color: #8E8E93;
                    margin-top: 5px;
                }}
                .charts-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                .chart-container {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.07);
                    height: 400px;
                }}
                .alerts-container {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.07);
                }}
                .alert-item {{
                    padding: 10px;
                    margin: 5px 0;
                    border-radius: 8px;
                    border-left: 4px solid #FF3B30;
                }}
                .status-indicator {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: #34C759;
                    margin-right: 10px;
                }}
                .metrics-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                .metrics-table th, .metrics-table td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #E5E5E7;
                }}
                .metrics-table th {{
                    background: #F2F2F7;
                    font-weight: 600;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔍 DafelHub Monitoring Dashboard</h1>
                <p><span class="status-indicator"></span>System Status: <span id="status">Online</span></p>
                <p>Last Updated: <span id="last-update">--</span></p>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="cpu-usage">--</div>
                    <div class="stat-label">CPU Usage (%)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="memory-usage">--</div>
                    <div class="stat-label">Memory Usage (%)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="active-connections">--</div>
                    <div class="stat-label">Active Connections</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="requests-per-min">--</div>
                    <div class="stat-label">Requests/min</div>
                </div>
            </div>

            <div class="charts-grid">
                <div class="chart-container">
                    <h3>CPU Usage Over Time</h3>
                    <canvas id="cpu-chart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>Memory Usage Over Time</h3>
                    <canvas id="memory-chart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>HTTP Requests Over Time</h3>
                    <canvas id="requests-chart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>Response Time</h3>
                    <canvas id="response-time-chart"></canvas>
                </div>
            </div>

            <div class="alerts-container">
                <h3>Recent Alerts</h3>
                <div id="alerts-list">
                    <p>No alerts</p>
                </div>
            </div>

            <div class="alerts-container">
                <h3>Current Metrics</h3>
                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                            <th>Labels</th>
                            <th>Last Updated</th>
                        </tr>
                    </thead>
                    <tbody id="metrics-table">
                    </tbody>
                </table>
            </div>

            <script>
                // Chart.js setup
                Chart.defaults.responsive = true;
                Chart.defaults.maintainAspectRatio = false;

                // Initialize charts
                const cpuChart = new Chart(document.getElementById('cpu-chart'), {{
                    type: 'line',
                    data: {{
                        datasets: [{{
                            label: 'CPU %',
                            borderColor: '#007AFF',
                            backgroundColor: 'rgba(0, 122, 255, 0.1)',
                            data: []
                        }}]
                    }},
                    options: {{
                        scales: {{
                            x: {{ type: 'time', time: {{ unit: 'minute' }} }},
                            y: {{ min: 0, max: 100 }}
                        }}
                    }}
                }});

                const memoryChart = new Chart(document.getElementById('memory-chart'), {{
                    type: 'line',
                    data: {{
                        datasets: [{{
                            label: 'Memory %',
                            borderColor: '#34C759',
                            backgroundColor: 'rgba(52, 199, 89, 0.1)',
                            data: []
                        }}]
                    }},
                    options: {{
                        scales: {{
                            x: {{ type: 'time', time: {{ unit: 'minute' }} }},
                            y: {{ min: 0, max: 100 }}
                        }}
                    }}
                }});

                const requestsChart = new Chart(document.getElementById('requests-chart'), {{
                    type: 'line',
                    data: {{
                        datasets: [{{
                            label: 'Requests/min',
                            borderColor: '#FF9500',
                            backgroundColor: 'rgba(255, 149, 0, 0.1)',
                            data: []
                        }}]
                    }},
                    options: {{
                        scales: {{
                            x: {{ type: 'time', time: {{ unit: 'minute' }} }},
                            y: {{ min: 0 }}
                        }}
                    }}
                }});

                const responseTimeChart = new Chart(document.getElementById('response-time-chart'), {{
                    type: 'line',
                    data: {{
                        datasets: [{{
                            label: 'Response Time (ms)',
                            borderColor: '#FF3B30',
                            backgroundColor: 'rgba(255, 59, 48, 0.1)',
                            data: []
                        }}]
                    }},
                    options: {{
                        scales: {{
                            x: {{ type: 'time', time: {{ unit: 'minute' }} }},
                            y: {{ min: 0 }}
                        }}
                    }}
                }});

                // WebSocket connection
                const ws = new WebSocket('ws://{self.host}:{self.port}/ws');
                
                ws.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                }};

                ws.onerror = function(error) {{
                    console.error('WebSocket error:', error);
                    document.getElementById('status').textContent = 'Disconnected';
                }};

                function updateDashboard(data) {{
                    // Update timestamp
                    document.getElementById('last-update').textContent = 
                        new Date(data.timestamp * 1000).toLocaleTimeString();
                    
                    // Update stats
                    if (data.system_stats) {{
                        document.getElementById('cpu-usage').textContent = 
                            Math.round(data.system_stats.cpu || 0);
                        document.getElementById('memory-usage').textContent = 
                            Math.round(data.system_stats.memory || 0);
                    }}
                    
                    // Update charts
                    updateChart(cpuChart, data.metrics['system_cpu_percent_total'] || []);
                    updateChart(memoryChart, data.metrics['system_memory_percent'] || []);
                    
                    // Update alerts
                    updateAlerts(data.alerts || []);
                    
                    // Update metrics table
                    updateMetricsTable(data);
                }}

                function updateChart(chart, dataPoints) {{
                    const chartData = dataPoints.map(point => ({{
                        x: new Date(point.timestamp * 1000),
                        y: point.value
                    }}));
                    
                    chart.data.datasets[0].data = chartData.slice(-50); // Keep last 50 points
                    chart.update('none');
                }}

                function updateAlerts(alerts) {{
                    const alertsList = document.getElementById('alerts-list');
                    if (alerts.length === 0) {{
                        alertsList.innerHTML = '<p>No alerts</p>';
                        return;
                    }}
                    
                    const html = alerts.map(alert => `
                        <div class="alert-item">
                            <strong>${{alert.type}}</strong>: ${{alert.message}}
                            <div style="font-size: 0.9em; color: #8E8E93; margin-top: 5px;">
                                ${{new Date(alert.timestamp * 1000).toLocaleString()}}
                            </div>
                        </div>
                    `).join('');
                    
                    alertsList.innerHTML = html;
                }}

                function updateMetricsTable(data) {{
                    const tbody = document.getElementById('metrics-table');
                    const rows = [];
                    
                    // Simplified metrics display
                    if (data.system_stats) {{
                        Object.entries(data.system_stats).forEach(([key, value]) => {{
                            rows.push(`
                                <tr>
                                    <td>system_${{key}}</td>
                                    <td>${{typeof value === 'number' ? value.toFixed(2) : value}}</td>
                                    <td>-</td>
                                    <td>${{new Date().toLocaleTimeString()}}</td>
                                </tr>
                            `);
                        }});
                    }}
                    
                    tbody.innerHTML = rows.join('');
                }}

                // Periodic data fetch as fallback
                setInterval(() => {{
                    fetch('/api/metrics')
                        .then(response => response.json())
                        .then(data => {{
                            if (ws.readyState !== WebSocket.OPEN) {{
                                updateDashboard(data);
                            }}
                        }})
                        .catch(error => console.error('Error fetching metrics:', error));
                }}, {int(self.update_interval * 1000)});
            </script>
        </body>
        </html>
        """
    
    def get_metrics_data(self) -> Dict[str, Any]:
        """Get current metrics data"""
        samples = self.metrics_collector.get_all_samples()
        
        # Group by metric name
        metrics = defaultdict(list)
        for sample in samples:
            metrics[sample.name].append({
                "value": sample.value,
                "labels": sample.labels,
                "timestamp": sample.timestamp
            })
        
        return {
            "timestamp": time.time(),
            "metrics": dict(metrics),
            "system_stats": self.get_system_stats(),
            "alert_count": len(self.dashboard_data.alert_history)
        }
    
    def get_system_stats(self) -> Dict[str, float]:
        """Get current system statistics"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu": cpu_percent,
                "memory": memory.percent,
                "disk": (disk.used / disk.total) * 100,
                "uptime": time.time() - psutil.boot_time(),
                "processes": len(psutil.pids())
            }
        except ImportError:
            return {"error": "psutil not available"}
    
    async def start_data_collection(self):
        """Start background data collection"""
        self.running = True
        
        while self.running:
            try:
                # Collect current metrics
                samples = self.metrics_collector.get_all_samples()
                current_time = time.time()
                
                # Update metric histories
                for sample in samples:
                    self.dashboard_data.update_metric(
                        sample.name, sample.value, sample.labels
                    )
                
                # Update system stats
                self.dashboard_data.system_stats = self.get_system_stats()
                
                # Broadcast to WebSocket clients
                data = self.dashboard_data.get_dashboard_data()
                await self.websocket_manager.broadcast(json.dumps(data))
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in data collection: {e}")
                await asyncio.sleep(self.update_interval)
    
    def start_server(self, auto_open: bool = True):
        """Start the dashboard server"""
        if auto_open:
            # Open browser after short delay
            def open_browser():
                time.sleep(2)
                webbrowser.open(f"http://{self.host}:{self.port}")
            
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
        
        self.logger.info(f"Starting monitoring dashboard at http://{self.host}:{self.port}")
        
        # Start background data collection
        asyncio.create_task(self.start_data_collection())
        
        # Start server
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning"  # Reduce uvicorn logging
        )
    
    def stop_server(self):
        """Stop the dashboard server"""
        self.running = False
    
    def add_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Add an alert to the dashboard"""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": time.time()
        }
        self.dashboard_data.add_alert(alert)
        self.logger.warn(f"Dashboard alert: {alert_type} - {message}")


# Global dashboard instance
_global_dashboard: Optional[MonitoringDashboard] = None


def get_dashboard(**kwargs) -> MonitoringDashboard:
    """Get global dashboard instance"""
    global _global_dashboard
    if _global_dashboard is None:
        _global_dashboard = MonitoringDashboard(**kwargs)
    return _global_dashboard