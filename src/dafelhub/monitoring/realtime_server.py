"""
Real-time Monitoring WebSocket Server
Streams live system metrics and alerts to dashboard clients
@module dafelhub.monitoring.realtime_server
"""

import asyncio
import json
import time
import threading
import websockets
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
import logging
from collections import defaultdict, deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .metrics_collector import MetricsCollector, get_metrics_collector
from .alerting import AlertManager, get_alert_manager
from .logger import Logger, get_logger, LogContext


class WebSocketConnectionManager:
    """Manage WebSocket connections and broadcasting"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_stats = {}
        self.logger = get_logger()
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept and register new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Track connection stats
        if client_id:
            self.connection_stats[client_id] = {
                'connected_at': time.time(),
                'messages_sent': 0,
                'websocket': websocket
            }
        
        self.logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, client_id: str = None):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if client_id and client_id in self.connection_stats:
            del self.connection_stats[client_id]
        
        self.logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            self.logger.warn(f"Failed to send message to client: {e}")
            self.disconnect(websocket)
            return False
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected WebSockets"""
        if not self.active_connections:
            return 0
        
        disconnected = []
        successful = 0
        
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
                successful += 1
            except Exception as e:
                self.logger.warn(f"Connection failed, removing: {e}")
                disconnected.append(connection)
        
        # Remove failed connections
        for connection in disconnected:
            self.disconnect(connection)
        
        return successful
    
    async def send_to_client(self, client_id: str, message: dict):
        """Send message to specific client by ID"""
        if client_id in self.connection_stats:
            websocket = self.connection_stats[client_id]['websocket']
            success = await self.send_personal_message(message, websocket)
            if success:
                self.connection_stats[client_id]['messages_sent'] += 1
            return success
        return False
    
    def get_connection_stats(self):
        """Get connection statistics"""
        return {
            'total_connections': len(self.active_connections),
            'clients': {
                client_id: {
                    'connected_at': stats['connected_at'],
                    'messages_sent': stats['messages_sent'],
                    'uptime': time.time() - stats['connected_at']
                }
                for client_id, stats in self.connection_stats.items()
            }
        }


class RealtimeMetricsCollector:
    """Real-time metrics collection and streaming"""
    
    def __init__(self, connection_manager: WebSocketConnectionManager, 
                 metrics_collector: MetricsCollector = None,
                 alert_manager: AlertManager = None,
                 logger: Logger = None):
        
        self.connection_manager = connection_manager
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.alert_manager = alert_manager or get_alert_manager()
        self.logger = logger or get_logger()
        
        # Real-time data storage
        self.metrics_history = deque(maxlen=500)  # Last 500 data points
        self.alerts_history = deque(maxlen=100)   # Last 100 alerts
        self.system_events = deque(maxlen=200)    # Last 200 events
        
        # Collection state
        self.is_collecting = False
        self.collection_tasks = []
        
        # Performance tracking
        self.collection_stats = {
            'metrics_collected': 0,
            'alerts_processed': 0,
            'broadcasts_sent': 0,
            'start_time': time.time()
        }
    
    async def start_collection(self, interval: float = 2.0):
        """Start real-time metrics collection"""
        if self.is_collecting:
            return
        
        self.is_collecting = True
        self.collection_stats['start_time'] = time.time()
        
        # Start collection tasks
        self.collection_tasks = [
            asyncio.create_task(self._collect_metrics_loop(interval)),
            asyncio.create_task(self._collect_system_metrics_loop(interval * 2)),
            asyncio.create_task(self._monitor_alerts_loop(interval)),
            asyncio.create_task(self._heartbeat_loop(30.0))  # Every 30 seconds
        ]
        
        self.logger.info("Started real-time metrics collection")
    
    async def stop_collection(self):
        """Stop real-time metrics collection"""
        self.is_collecting = False
        
        # Cancel all tasks
        for task in self.collection_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.collection_tasks, return_exceptions=True)
        self.collection_tasks.clear()
        
        self.logger.info("Stopped real-time metrics collection")
    
    async def _collect_metrics_loop(self, interval: float):
        """Main metrics collection loop"""
        while self.is_collecting:
            try:
                # Get current metrics
                samples = self.metrics_collector.get_all_samples()
                metric_families = self.metrics_collector.get_metric_families()
                
                # Prepare real-time data
                realtime_data = {
                    'timestamp': time.time(),
                    'type': 'metrics_update',
                    'data': {
                        'samples': [
                            {
                                'name': sample.name,
                                'value': sample.value,
                                'labels': sample.labels,
                                'timestamp': sample.timestamp,
                                'type': sample.type.value
                            }
                            for sample in samples[-50:]  # Last 50 samples
                        ],
                        'families': {
                            name: {
                                'name': family['name'],
                                'help': family['help'],
                                'type': family['type'],
                                'sample_count': len(family['samples'])
                            }
                            for name, family in metric_families.items()
                        },
                        'collection_stats': self.collection_stats
                    }
                }
                
                # Store in history
                self.metrics_history.append(realtime_data)
                
                # Broadcast to clients
                sent = await self.connection_manager.broadcast(realtime_data)
                self.collection_stats['broadcasts_sent'] += sent
                self.collection_stats['metrics_collected'] += len(samples)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_system_metrics_loop(self, interval: float):
        """System metrics collection loop"""
        while self.is_collecting:
            try:
                import psutil
                
                # Get system stats
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                
                system_data = {
                    'timestamp': time.time(),
                    'type': 'system_update',
                    'data': {
                        'cpu': {
                            'percent': cpu_percent,
                            'count': psutil.cpu_count(),
                            'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                        },
                        'memory': {
                            'total': memory.total,
                            'available': memory.available,
                            'percent': memory.percent,
                            'used': memory.used,
                            'free': memory.free
                        },
                        'disk': {
                            'total': disk.total,
                            'used': disk.used,
                            'free': disk.free,
                            'percent': (disk.used / disk.total) * 100
                        },
                        'network': {
                            'bytes_sent': network.bytes_sent,
                            'bytes_recv': network.bytes_recv,
                            'packets_sent': network.packets_sent,
                            'packets_recv': network.packets_recv
                        },
                        'processes': len(psutil.pids()),
                        'boot_time': psutil.boot_time()
                    }
                }
                
                # Broadcast system data
                await self.connection_manager.broadcast(system_data)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in system metrics collection: {e}")
                await asyncio.sleep(interval)
    
    async def _monitor_alerts_loop(self, interval: float):
        """Monitor and broadcast alerts"""
        last_alert_check = time.time()
        
        while self.is_collecting:
            try:
                # Get active alerts
                active_alerts = self.alert_manager.get_active_alerts()
                alert_history = self.alert_manager.get_alert_history(20)
                
                # Check for new alerts since last check
                new_alerts = [
                    alert for alert in alert_history
                    if alert.firing_time > last_alert_check
                ]
                
                if new_alerts or active_alerts:
                    alert_data = {
                        'timestamp': time.time(),
                        'type': 'alerts_update',
                        'data': {
                            'active_alerts': [alert.to_dict() for alert in active_alerts],
                            'new_alerts': [alert.to_dict() for alert in new_alerts],
                            'alert_statistics': self.alert_manager.get_statistics()
                        }
                    }
                    
                    # Store in history
                    self.alerts_history.append(alert_data)
                    
                    # Broadcast alerts
                    await self.connection_manager.broadcast(alert_data)
                    self.collection_stats['alerts_processed'] += len(new_alerts)
                
                last_alert_check = time.time()
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in alerts monitoring: {e}")
                await asyncio.sleep(interval)
    
    async def _heartbeat_loop(self, interval: float):
        """Send heartbeat to maintain connection"""
        while self.is_collecting:
            try:
                heartbeat = {
                    'timestamp': time.time(),
                    'type': 'heartbeat',
                    'data': {
                        'server_uptime': time.time() - self.collection_stats['start_time'],
                        'connections': len(self.connection_manager.active_connections),
                        'stats': self.collection_stats,
                        'status': 'healthy'
                    }
                }
                
                await self.connection_manager.broadcast(heartbeat)
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(interval)
    
    def get_latest_data(self) -> dict:
        """Get latest collected data"""
        return {
            'metrics': list(self.metrics_history)[-10:] if self.metrics_history else [],
            'alerts': list(self.alerts_history)[-5:] if self.alerts_history else [],
            'events': list(self.system_events)[-10:] if self.system_events else [],
            'stats': self.collection_stats,
            'connections': self.connection_manager.get_connection_stats()
        }


class RealtimeMonitoringServer:
    """Real-time monitoring server with WebSocket support"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 8081,
                 metrics_collector: MetricsCollector = None,
                 alert_manager: AlertManager = None,
                 logger: Logger = None):
        
        self.host = host
        self.port = port
        self.logger = logger or get_logger()
        
        # Components
        self.connection_manager = WebSocketConnectionManager()
        self.realtime_collector = RealtimeMetricsCollector(
            self.connection_manager, metrics_collector, alert_manager, logger
        )
        
        # FastAPI app
        self.app = FastAPI(title="DafelHub Real-time Monitoring", version="1.0.0")
        self.setup_routes()
        
        # Server state
        self.server_task = None
        self.is_running = False
    
    def setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.websocket("/ws/metrics")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time metrics"""
            client_id = f"client_{int(time.time() * 1000)}"
            await self.connection_manager.connect(websocket, client_id)
            
            try:
                # Send initial data
                initial_data = {
                    'type': 'connection_established',
                    'client_id': client_id,
                    'data': self.realtime_collector.get_latest_data()
                }
                await self.connection_manager.send_personal_message(initial_data, websocket)
                
                # Keep connection alive
                while True:
                    # Wait for messages from client (optional)
                    try:
                        message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                        # Handle client messages if needed
                        client_message = json.loads(message)
                        if client_message.get('type') == 'ping':
                            pong = {'type': 'pong', 'timestamp': time.time()}
                            await self.connection_manager.send_personal_message(pong, websocket)
                    except asyncio.TimeoutError:
                        # Send keepalive
                        keepalive = {'type': 'keepalive', 'timestamp': time.time()}
                        await self.connection_manager.send_personal_message(keepalive, websocket)
                    
            except WebSocketDisconnect:
                self.connection_manager.disconnect(websocket, client_id)
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                self.connection_manager.disconnect(websocket, client_id)
        
        @self.app.get("/api/realtime/status")
        async def get_status():
            """Get server status"""
            return JSONResponse({
                'status': 'running' if self.is_running else 'stopped',
                'uptime': time.time() - self.realtime_collector.collection_stats['start_time'],
                'connections': len(self.connection_manager.active_connections),
                'stats': self.realtime_collector.collection_stats,
                'timestamp': time.time()
            })
        
        @self.app.get("/api/realtime/data")
        async def get_latest_data():
            """Get latest monitoring data"""
            return JSONResponse(self.realtime_collector.get_latest_data())
        
        @self.app.get("/api/realtime/connections")
        async def get_connections():
            """Get connection information"""
            return JSONResponse(self.connection_manager.get_connection_stats())
        
        @self.app.post("/api/realtime/alert")
        async def trigger_alert(request: Request):
            """Manually trigger alert for testing"""
            try:
                data = await request.json()
                alert_data = {
                    'timestamp': time.time(),
                    'type': 'manual_alert',
                    'data': {
                        'message': data.get('message', 'Manual test alert'),
                        'severity': data.get('severity', 'info'),
                        'source': 'api'
                    }
                }
                
                sent = await self.connection_manager.broadcast(alert_data)
                return JSONResponse({
                    'success': True,
                    'sent_to': sent,
                    'alert': alert_data
                })
            except Exception as e:
                return JSONResponse({'success': False, 'error': str(e)}, status_code=500)
    
    async def start(self, collection_interval: float = 2.0):
        """Start the real-time monitoring server"""
        if self.is_running:
            return
        
        self.is_running = True
        self.logger.info(f"Starting real-time monitoring server on {self.host}:{self.port}")
        
        # Start metrics collection
        await self.realtime_collector.start_collection(collection_interval)
        
        # Configure and start Uvicorn server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False
        )
        
        self.server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(self.server.serve())
        
        self.logger.info(f"Real-time monitoring server started at ws://{self.host}:{self.port}/ws/metrics")
    
    async def stop(self):
        """Stop the real-time monitoring server"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info("Stopping real-time monitoring server")
        
        # Stop metrics collection
        await self.realtime_collector.stop_collection()
        
        # Stop server
        if self.server_task and not self.server_task.done():
            self.server.should_exit = True
            await self.server_task
        
        self.logger.info("Real-time monitoring server stopped")


# Global server instance
_global_server: Optional[RealtimeMonitoringServer] = None


def get_realtime_server(**kwargs) -> RealtimeMonitoringServer:
    """Get global real-time server instance"""
    global _global_server
    if _global_server is None:
        _global_server = RealtimeMonitoringServer(**kwargs)
    return _global_server


# Server management functions
async def start_realtime_monitoring(host: str = "localhost", 
                                  port: int = 8081, 
                                  collection_interval: float = 2.0):
    """Start real-time monitoring server"""
    server = get_realtime_server(host=host, port=port)
    await server.start(collection_interval)
    return server


async def stop_realtime_monitoring():
    """Stop real-time monitoring server"""
    global _global_server
    if _global_server and _global_server.is_running:
        await _global_server.stop()


if __name__ == "__main__":
    async def main():
        # Start real-time monitoring server
        server = await start_realtime_monitoring(host="0.0.0.0", port=8081)
        
        try:
            # Keep running
            await server.server_task
        except KeyboardInterrupt:
            print("\nShutting down real-time monitoring server...")
            await stop_realtime_monitoring()
    
    asyncio.run(main())