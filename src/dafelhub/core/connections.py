"""
DafelHub Connections Module
Enterprise connection management adapted from Dafel-Technologies
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
import uuid
import time
import json
from concurrent.futures import ThreadPoolExecutor

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)


class ConnectionType(Enum):
    """Supported connection types"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    REST_API = "rest_api"
    GRAPHQL = "graphql"
    S3 = "s3"
    SQLITE = "sqlite"


class ConnectionStatus(Enum):
    """Connection status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ConnectionErrorType(Enum):
    """Connection error types"""
    AUTHENTICATION_FAILED = "authentication_failed"
    CONNECTION_REFUSED = "connection_refused"
    CONNECTION_TIMEOUT = "connection_timeout"
    INVALID_CONFIGURATION = "invalid_configuration"
    NETWORK_ERROR = "network_error"
    POOL_EXHAUSTED = "pool_exhausted"
    QUERY_TIMEOUT = "query_timeout"
    UNKNOWN = "unknown"


@dataclass
class ConnectionConfig:
    """Connection configuration"""
    id: str
    name: str
    type: ConnectionType
    host: str
    port: int
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl: bool = False
    pool_size: int = 10
    connection_timeout: int = 30000
    query_timeout: int = 60000
    retry_attempts: int = 3
    retry_delay: int = 1000
    configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass 
class ConnectionMetadata:
    """Connection runtime metadata"""
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    total_queries: int = 0
    failed_queries: int = 0
    avg_response_time: float = 0.0
    is_healthy: bool = False
    last_error: Optional[str] = None
    server_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Query execution result"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None


class ConnectionError(Exception):
    """Connection-related errors"""
    
    def __init__(
        self, 
        message: str, 
        error_type: ConnectionErrorType = ConnectionErrorType.UNKNOWN,
        code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.error_type = error_type
        self.code = code
        self.context = context or {}
        self.timestamp = datetime.now()


class IDataSourceConnector(ABC):
    """Base interface for data source connectors"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection health"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Quick health check"""
        pass
    
    @abstractmethod
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute query"""
        pass
    
    @property
    @abstractmethod
    def status(self) -> ConnectionStatus:
        """Current connection status"""
        pass


class ConnectionPool(LoggerMixin):
    """Connection pooling implementation"""
    
    def __init__(self, config: ConnectionConfig, max_size: int = 10, min_size: int = 2):
        self.config = config
        self.max_size = max_size
        self.min_size = min_size
        self._pool: Set[IDataSourceConnector] = set()
        self._active: Set[IDataSourceConnector] = set()
        self._lock = asyncio.Lock()
        self._created_at = datetime.now()
        
    async def acquire(self) -> IDataSourceConnector:
        """Acquire connection from pool"""
        async with self._lock:
            # Try to get from pool
            if self._pool:
                connector = self._pool.pop()
                self._active.add(connector)
                return connector
            
            # Create new if under limit
            if len(self._active) < self.max_size:
                connector = await self._create_connection()
                self._active.add(connector)
                return connector
            
            # Pool exhausted
            raise ConnectionError(
                "Connection pool exhausted",
                ConnectionErrorType.POOL_EXHAUSTED
            )
    
    async def release(self, connector: IDataSourceConnector) -> None:
        """Release connection back to pool"""
        async with self._lock:
            if connector in self._active:
                self._active.remove(connector)
                
                # Add back to pool if under min size
                if len(self._pool) < self.min_size:
                    self._pool.add(connector)
                else:
                    await connector.disconnect()
    
    async def _create_connection(self) -> IDataSourceConnector:
        """Create new connection"""
        # This would use ConnectionFactory
        pass


class ConnectionManager(LoggerMixin):
    """Enterprise Connection Manager - Singleton"""
    
    _instance: Optional['ConnectionManager'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls) -> 'ConnectionManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._connections: Dict[str, IDataSourceConnector] = {}
        self._pools: Dict[str, ConnectionPool] = {}
        self._metadata: Dict[str, ConnectionMetadata] = {}
        self._health_tasks: Dict[str, asyncio.Task] = {}
        self._is_shutting_down = False
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._initialized = True
        
        self.logger.info("ConnectionManager initialized")
    
    @classmethod
    async def get_instance(cls) -> 'ConnectionManager':
        """Get singleton instance"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def create_connection(self, config: ConnectionConfig) -> IDataSourceConnector:
        """Create new connection"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())
        
        try:
            self.logger.info(f"Creating connection: {config.id}", extra_data={
                "connection_id": config.id,
                "type": config.type.value,
                "correlation_id": correlation_id
            })
            
            # Check limits
            if len(self._connections) >= settings.MAX_CONNECTIONS:
                raise ConnectionError(
                    "Maximum connection limit reached",
                    ConnectionErrorType.POOL_EXHAUSTED
                )
            
            # Create connector (would use factory)
            connector = await self._create_connector(config)
            
            # Connect with retry
            await self._connect_with_retry(connector, config.retry_attempts)
            
            # Register
            self._connections[config.id] = connector
            self._metadata[config.id] = ConnectionMetadata(
                connected_at=datetime.now(),
                is_healthy=True
            )
            
            # Start health monitoring
            await self._start_health_monitoring(config.id)
            
            duration = time.time() - start_time
            self.logger.info(f"Connection created: {config.id} ({duration:.2f}s)")
            
            return connector
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Failed to create connection: {config.id}", extra_data={
                "error": str(e),
                "duration": duration,
                "correlation_id": correlation_id
            })
            raise
    
    async def get_connection(self, connection_id: str) -> Optional[IDataSourceConnector]:
        """Get existing connection"""
        return self._connections.get(connection_id)
    
    async def close_connection(self, connection_id: str) -> None:
        """Close and remove connection"""
        connector = self._connections.get(connection_id)
        if not connector:
            return
            
        try:
            # Stop health monitoring
            if connection_id in self._health_tasks:
                self._health_tasks[connection_id].cancel()
                del self._health_tasks[connection_id]
            
            # Disconnect
            await connector.disconnect()
            
            # Remove from registry
            del self._connections[connection_id]
            if connection_id in self._metadata:
                del self._metadata[connection_id]
            
            # Close pool if exists
            if connection_id in self._pools:
                del self._pools[connection_id]
                
            self.logger.info(f"Connection closed: {connection_id}")
            
        except Exception as e:
            self.logger.error(f"Error closing connection: {connection_id}", extra_data={
                "error": str(e)
            })
            raise
    
    async def health_check(self, connection_id: str) -> bool:
        """Check connection health"""
        connector = self._connections.get(connection_id)
        if not connector:
            return False
            
        try:
            is_healthy = await connector.health_check()
            metadata = self._metadata.get(connection_id)
            if metadata:
                metadata.is_healthy = is_healthy
                metadata.last_activity = datetime.now()
            return is_healthy
        except Exception as e:
            self.logger.error(f"Health check failed: {connection_id}", extra_data={
                "error": str(e)
            })
            return False
    
    async def shutdown(self) -> None:
        """Graceful shutdown"""
        if self._is_shutting_down:
            return
            
        self._is_shutting_down = True
        self.logger.info("ConnectionManager shutting down...")
        
        try:
            # Cancel health tasks
            for task in self._health_tasks.values():
                task.cancel()
            
            # Close all connections
            for connection_id in list(self._connections.keys()):
                await self.close_connection(connection_id)
                
            # Shutdown executor
            self._executor.shutdown(wait=True)
            
            self.logger.info("ConnectionManager shutdown complete")
        except Exception as e:
            self.logger.error("Error during shutdown", extra_data={"error": str(e)})
    
    async def _create_connector(self, config: ConnectionConfig) -> IDataSourceConnector:
        """Create connector based on type"""
        # Factory pattern implementation would go here
        # For now, raise not implemented
        raise NotImplementedError(f"Connector for {config.type} not implemented yet")
    
    async def _connect_with_retry(self, connector: IDataSourceConnector, max_retries: int) -> None:
        """Connect with retry logic"""
        for attempt in range(max_retries + 1):
            try:
                await connector.connect()
                return
            except Exception as e:
                if attempt == max_retries:
                    raise
                self.logger.warn(f"Connection attempt {attempt + 1} failed, retrying...", extra_data={
                    "error": str(e)
                })
                await asyncio.sleep(1.0 * (2 ** attempt))  # Exponential backoff
    
    async def _start_health_monitoring(self, connection_id: str) -> None:
        """Start health monitoring task"""
        async def health_monitor():
            while not self._is_shutting_down and connection_id in self._connections:
                try:
                    await self.health_check(connection_id)
                    await asyncio.sleep(30)  # Check every 30 seconds
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Health monitor error: {connection_id}", extra_data={
                        "error": str(e)
                    })
                    await asyncio.sleep(5)
        
        task = asyncio.create_task(health_monitor())
        self._health_tasks[connection_id] = task


# Singleton instance
connection_manager: Optional[ConnectionManager] = None


async def get_connection_manager() -> ConnectionManager:
    """Get global connection manager instance"""
    global connection_manager
    if connection_manager is None:
        connection_manager = await ConnectionManager.get_instance()
    return connection_manager
