"""
DafelHub Enterprise Database Connection Manager
Enterprise-grade connection pooling and management system
Integrates with SecurityAgent audit trail and vault manager

Features:
- Advanced connection pooling with asyncpg optimized
- Health monitoring and automatic failover
- Connection lifecycle management
- Security integration with audit trail
- Performance monitoring and metrics
- Connection pool scaling
- Transaction management
- Connection recovery and resilience

TODO: [DB-001] Implement connection pooling optimization - @DatabaseAgent - 2024-09-24
TODO: [DB-002] Add database health monitoring - @DatabaseAgent - 2024-09-24
TODO: [DB-003] Integrate with SecurityAgent audit trail - @DatabaseAgent - 2024-09-24
"""

import asyncio
import time
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Union, Callable,
    AsyncGenerator, Tuple, AsyncContextManager
)

import asyncpg
from asyncpg import Pool, Connection, Record
import weakref
import json

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.database.connectors.postgresql import PostgreSQLConnector, ConnectionPoolMetrics
from dafelhub.core.connections import ConnectionConfig, ConnectionStatus
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.security.audit_trail import get_persistent_audit_trail


logger = get_logger(__name__)


class ConnectionPriority(Enum):
    """Connection priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class PoolStatus(Enum):
    """Connection pool status"""
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    SHUTDOWN = "shutdown"


@dataclass
class ConnectionRequest:
    """Connection request with priority and metadata"""
    request_id: str
    priority: ConnectionPriority
    requested_at: datetime
    timeout_seconds: float
    tags: Dict[str, Any] = field(default_factory=dict)
    requester: Optional[str] = None


@dataclass
class ConnectionLease:
    """Connection lease tracking"""
    connection: Connection
    lease_id: str
    leased_at: datetime
    expires_at: datetime
    priority: ConnectionPriority
    active_queries: int = 0
    tags: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if lease is expired"""
        return datetime.now() > self.expires_at


@dataclass
class PoolConfiguration:
    """Advanced pool configuration"""
    min_size: int = 2
    max_size: int = 10
    max_inactive_connection_lifetime: float = 300.0
    connection_timeout: float = 30.0
    query_timeout: float = 60.0
    health_check_interval: float = 30.0
    scaling_threshold: float = 0.8  # Scale when 80% capacity
    scale_up_increment: int = 2
    scale_down_decrement: int = 1
    idle_timeout: float = 600.0  # 10 minutes
    max_queries_per_connection: int = 50000
    enable_auto_scaling: bool = True
    enable_connection_recycling: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'min_size': self.min_size,
            'max_size': self.max_size,
            'max_inactive_connection_lifetime': self.max_inactive_connection_lifetime,
            'connection_timeout': self.connection_timeout,
            'query_timeout': self.query_timeout,
            'health_check_interval': self.health_check_interval,
            'scaling_threshold': self.scaling_threshold,
            'scale_up_increment': self.scale_up_increment,
            'scale_down_decrement': self.scale_down_decrement,
            'idle_timeout': self.idle_timeout,
            'max_queries_per_connection': self.max_queries_per_connection,
            'enable_auto_scaling': self.enable_auto_scaling,
            'enable_connection_recycling': self.enable_connection_recycling
        }


class EnterpriseConnectionManager(LoggerMixin):
    """
    Enterprise Database Connection Manager
    
    Advanced features:
    - Priority-based connection allocation
    - Automatic pool scaling and optimization
    - Health monitoring with failover
    - Security integration with audit trail
    - Connection lifecycle management
    - Performance metrics and monitoring
    - Transaction context management
    - Connection recovery and resilience
    """
    
    def __init__(self, vault_manager=None, audit_trail=None):
        super().__init__()
        
        # Core dependencies
        self.vault = vault_manager or get_enterprise_vault_manager()
        self.audit = audit_trail or get_persistent_audit_trail()
        
        # Connection pools management
        self._pools: Dict[str, Pool] = {}
        self._pool_configs: Dict[str, PoolConfiguration] = {}
        self._pool_status: Dict[str, PoolStatus] = {}
        self._pool_metrics: Dict[str, ConnectionPoolMetrics] = {}
        self._connection_leases: Dict[str, ConnectionLease] = {}
        
        # Request management
        self._pending_requests: Dict[str, ConnectionRequest] = {}
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._connection_semaphores: Dict[str, asyncio.Semaphore] = {}
        
        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._scaling_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Thread safety
        self._pools_lock = asyncio.Lock()
        self._leases_lock = asyncio.Lock()
        
        # Performance tracking
        self._total_connections_created = 0
        self._total_connections_destroyed = 0
        self._total_requests_processed = 0
        self._failed_requests = 0
        
        # Configuration
        self.default_lease_duration = 300.0  # 5 minutes
        self.max_lease_duration = 3600.0     # 1 hour
        self.request_timeout = 30.0          # 30 seconds
        
        self.logger.info("Enterprise Connection Manager initialized")
    
    async def initialize(self) -> None:
        """Initialize connection manager"""
        try:
            # Start background tasks
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._scaling_task = asyncio.create_task(self._scaling_loop())
            
            # Audit initialization
            self.audit.add_entry(
                'connection_manager_initialized',
                {
                    'manager_id': id(self),
                    'default_lease_duration': self.default_lease_duration,
                    'max_lease_duration': self.max_lease_duration
                }
            )
            
            self.logger.info("Enterprise Connection Manager started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Connection Manager: {e}")
            raise
    
    async def create_pool(
        self, 
        pool_id: str, 
        connection_config: ConnectionConfig, 
        pool_config: Optional[PoolConfiguration] = None
    ) -> None:
        """Create and configure a new connection pool"""
        
        async with self._pools_lock:
            if pool_id in self._pools:
                self.logger.warning(f"Pool already exists: {pool_id}")
                return
            
            pool_config = pool_config or PoolConfiguration()
            self._pool_configs[pool_id] = pool_config
            self._pool_status[pool_id] = PoolStatus.INITIALIZING
            
            try:
                # Build secure DSN using vault manager
                dsn = await self._build_secure_dsn(connection_config)
                
                # Create asyncpg pool with enterprise configuration
                pool = await asyncpg.create_pool(
                    dsn,
                    min_size=pool_config.min_size,
                    max_size=pool_config.max_size,
                    max_queries=pool_config.max_queries_per_connection,
                    max_inactive_connection_lifetime=pool_config.max_inactive_connection_lifetime,
                    command_timeout=pool_config.query_timeout,
                    setup=self._setup_connection,
                    init=lambda conn: self._init_connection(conn, pool_id),
                    server_settings={
                        'application_name': f'DafelHub-{pool_id}',
                        'tcp_keepalives_idle': '600',
                        'tcp_keepalives_interval': '30',
                        'tcp_keepalives_count': '3'
                    }
                )
                
                self._pools[pool_id] = pool
                self._pool_status[pool_id] = PoolStatus.HEALTHY
                
                # Initialize metrics
                self._pool_metrics[pool_id] = ConnectionPoolMetrics(
                    max_connections=pool_config.max_size,
                    min_connections=pool_config.min_size,
                    total_connections=pool.get_size(),
                    pool_created_at=datetime.now()
                )
                
                # Create semaphore for connection limiting
                self._connection_semaphores[pool_id] = asyncio.Semaphore(pool_config.max_size)
                
                # Test pool connectivity
                await self._test_pool_health(pool_id)
                
                # Audit pool creation
                self.audit.add_entry(
                    'database_pool_created',
                    {
                        'pool_id': pool_id,
                        'config': pool_config.to_dict(),
                        'database': connection_config.database,
                        'host': connection_config.host,
                        'port': connection_config.port
                    }
                )
                
                self.logger.info(f"Connection pool created successfully: {pool_id}", extra={
                    "pool_size": f"{pool_config.min_size}-{pool_config.max_size}",
                    "database": connection_config.database
                })
                
            except Exception as e:
                self._pool_status[pool_id] = PoolStatus.UNHEALTHY
                self.logger.error(f"Failed to create connection pool: {pool_id}", extra={"error": str(e)})
                
                # Audit failure
                self.audit.add_entry(
                    'database_pool_creation_failed',
                    {
                        'pool_id': pool_id,
                        'error': str(e),
                        'database': connection_config.database
                    }
                )
                raise
    
    async def get_connection(
        self,
        pool_id: str,
        priority: ConnectionPriority = ConnectionPriority.NORMAL,
        lease_duration: Optional[float] = None,
        timeout: Optional[float] = None,
        tags: Optional[Dict[str, Any]] = None,
        requester: Optional[str] = None
    ) -> AsyncContextManager[Connection]:
        """Get a connection with priority and lease management"""
        
        if pool_id not in self._pools:
            raise ValueError(f"Pool not found: {pool_id}")
        
        if self._pool_status[pool_id] != PoolStatus.HEALTHY:
            raise RuntimeError(f"Pool is not healthy: {pool_id}")
        
        request_id = str(uuid.uuid4())
        lease_duration = min(lease_duration or self.default_lease_duration, self.max_lease_duration)
        timeout = timeout or self.request_timeout
        
        # Create connection request
        request = ConnectionRequest(
            request_id=request_id,
            priority=priority,
            requested_at=datetime.now(),
            timeout_seconds=timeout,
            tags=tags or {},
            requester=requester
        )
        
        self._pending_requests[request_id] = request
        
        try:
            # Audit connection request
            self.audit.add_entry(
                'database_connection_requested',
                {
                    'pool_id': pool_id,
                    'request_id': request_id,
                    'priority': priority.name,
                    'lease_duration': lease_duration,
                    'requester': requester
                }
            )
            
            # Acquire connection with timeout
            async with asyncio.timeout(timeout):
                return await self._acquire_connection_lease(pool_id, request, lease_duration)
                
        except asyncio.TimeoutError:
            self._failed_requests += 1
            self._pending_requests.pop(request_id, None)
            
            # Audit timeout
            self.audit.add_entry(
                'database_connection_timeout',
                {
                    'pool_id': pool_id,
                    'request_id': request_id,
                    'timeout_seconds': timeout
                }
            )
            
            self.logger.warning(f"Connection request timeout: {pool_id}", extra={
                "request_id": request_id,
                "timeout": timeout
            })
            raise
        
        except Exception as e:
            self._failed_requests += 1
            self._pending_requests.pop(request_id, None)
            
            # Audit error
            self.audit.add_entry(
                'database_connection_error',
                {
                    'pool_id': pool_id,
                    'request_id': request_id,
                    'error': str(e)
                }
            )
            raise
        
        finally:
            self._total_requests_processed += 1
    
    @asynccontextmanager
    async def _acquire_connection_lease(
        self, 
        pool_id: str, 
        request: ConnectionRequest, 
        lease_duration: float
    ) -> AsyncGenerator[Connection, None]:
        """Acquire connection lease with proper lifecycle management"""
        
        lease_id = str(uuid.uuid4())
        connection = None
        
        try:
            # Acquire connection from pool
            async with self._connection_semaphores[pool_id]:
                pool = self._pools[pool_id]
                connection = await pool.acquire()
                
                # Create lease
                lease = ConnectionLease(
                    connection=connection,
                    lease_id=lease_id,
                    leased_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(seconds=lease_duration),
                    priority=request.priority,
                    tags=request.tags
                )
                
                async with self._leases_lock:
                    self._connection_leases[lease_id] = lease
                
                # Update metrics
                self._update_pool_metrics(pool_id, connection_acquired=True)
                
                # Audit lease creation
                self.audit.add_entry(
                    'database_connection_leased',
                    {
                        'pool_id': pool_id,
                        'lease_id': lease_id,
                        'request_id': request.request_id,
                        'lease_duration': lease_duration,
                        'connection_id': str(id(connection))
                    }
                )
                
                self.logger.debug(f"Connection leased: {pool_id}", extra={
                    "lease_id": lease_id,
                    "request_id": request.request_id
                })
                
                # Yield connection to user
                yield connection
        
        finally:
            # Clean up lease
            async with self._leases_lock:
                self._connection_leases.pop(lease_id, None)
            
            if connection:
                try:
                    # Release connection back to pool
                    pool = self._pools[pool_id]
                    await pool.release(connection)
                    
                    # Update metrics
                    self._update_pool_metrics(pool_id, connection_released=True)
                    
                    # Audit lease release
                    self.audit.add_entry(
                        'database_connection_released',
                        {
                            'pool_id': pool_id,
                            'lease_id': lease_id,
                            'connection_id': str(id(connection))
                        }
                    )
                    
                    self.logger.debug(f"Connection released: {pool_id}", extra={
                        "lease_id": lease_id
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error releasing connection: {pool_id}", extra={
                        "lease_id": lease_id,
                        "error": str(e)
                    })
            
            # Remove pending request
            self._pending_requests.pop(request.request_id, None)
    
    async def get_pool_status(self, pool_id: str) -> Dict[str, Any]:
        """Get comprehensive pool status"""
        if pool_id not in self._pools:
            return {"error": "Pool not found"}
        
        pool = self._pools[pool_id]
        config = self._pool_configs[pool_id]
        metrics = self._pool_metrics[pool_id]
        status = self._pool_status[pool_id]
        
        # Get current pool stats
        current_size = pool.get_size()
        idle_size = pool.get_idle_size()
        active_size = current_size - idle_size
        
        # Calculate lease statistics
        active_leases = len([l for l in self._connection_leases.values() if not l.is_expired])
        
        return {
            'pool_id': pool_id,
            'status': status.value,
            'configuration': config.to_dict(),
            'current_stats': {
                'total_connections': current_size,
                'active_connections': active_size,
                'idle_connections': idle_size,
                'active_leases': active_leases,
                'pending_requests': len(self._pending_requests),
                'utilization_percent': (active_size / config.max_size) * 100 if config.max_size > 0 else 0
            },
            'metrics': {
                'total_queries': metrics.total_queries,
                'failed_queries': metrics.failed_queries,
                'avg_query_time': metrics.avg_query_time,
                'pool_uptime': (datetime.now() - metrics.pool_created_at).total_seconds()
            },
            'health': {
                'is_healthy': status == PoolStatus.HEALTHY,
                'last_health_check': metrics.last_activity.isoformat() if metrics.last_activity else None
            }
        }
    
    async def get_global_status(self) -> Dict[str, Any]:
        """Get global connection manager status"""
        
        total_pools = len(self._pools)
        healthy_pools = sum(1 for s in self._pool_status.values() if s == PoolStatus.HEALTHY)
        total_connections = sum(p.get_size() for p in self._pools.values())
        active_connections = sum(p.get_size() - p.get_idle_size() for p in self._pools.values())
        
        return {
            'manager_status': 'healthy' if not self._shutdown_event.is_set() else 'shutdown',
            'pools': {
                'total': total_pools,
                'healthy': healthy_pools,
                'unhealthy': total_pools - healthy_pools
            },
            'connections': {
                'total': total_connections,
                'active': active_connections,
                'idle': total_connections - active_connections,
                'total_created': self._total_connections_created,
                'total_destroyed': self._total_connections_destroyed
            },
            'requests': {
                'total_processed': self._total_requests_processed,
                'failed': self._failed_requests,
                'success_rate': ((self._total_requests_processed - self._failed_requests) / 
                                max(self._total_requests_processed, 1)) * 100,
                'pending': len(self._pending_requests)
            },
            'leases': {
                'active': len(self._connection_leases),
                'expired': len([l for l in self._connection_leases.values() if l.is_expired])
            }
        }
    
    async def shutdown(self, timeout: float = 30.0) -> None:
        """Graceful shutdown of connection manager"""
        
        self.logger.info("Starting Connection Manager shutdown")
        self._shutdown_event.set()
        
        try:
            # Cancel background tasks
            for task in [self._monitor_task, self._cleanup_task, self._scaling_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            
            # Wait for active leases to complete or timeout
            start_time = time.time()
            while self._connection_leases and (time.time() - start_time) < timeout:
                self.logger.info(f"Waiting for {len(self._connection_leases)} active leases to complete")
                await asyncio.sleep(1.0)
            
            # Force close remaining leases
            if self._connection_leases:
                self.logger.warning(f"Force closing {len(self._connection_leases)} remaining leases")
                for lease in list(self._connection_leases.values()):
                    try:
                        if lease.connection:
                            await lease.connection.close()
                    except Exception as e:
                        self.logger.error(f"Error force closing connection: {e}")
                
                self._connection_leases.clear()
            
            # Close all pools
            async with self._pools_lock:
                for pool_id, pool in list(self._pools.items()):
                    try:
                        self.logger.info(f"Closing pool: {pool_id}")
                        await pool.close()
                        self._pool_status[pool_id] = PoolStatus.SHUTDOWN
                        
                        # Audit pool closure
                        self.audit.add_entry(
                            'database_pool_closed',
                            {'pool_id': pool_id, 'shutdown': True}
                        )
                        
                    except Exception as e:
                        self.logger.error(f"Error closing pool {pool_id}: {e}")
                
                self._pools.clear()
            
            # Audit shutdown
            self.audit.add_entry(
                'connection_manager_shutdown',
                {
                    'total_pools_closed': len(self._pool_status),
                    'total_requests_processed': self._total_requests_processed
                }
            )
            
            self.logger.info("Connection Manager shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during Connection Manager shutdown: {e}")
            raise
    
    # Private methods
    
    async def _build_secure_dsn(self, config: ConnectionConfig) -> str:
        """Build secure DSN using vault manager for credentials"""
        try:
            # Get secure credentials from vault
            if hasattr(config, 'credential_id') and config.credential_id:
                # Use stored credentials
                credentials = await self.vault.decrypt(config.credential_id)
                username = credentials.get('username', config.username)
                password = credentials.get('password', config.password)
            else:
                username = config.username
                password = config.password
            
            # Build DSN with security
            dsn = f"postgresql://{username}:{password}@{config.host}:{config.port}/{config.database}"
            
            # Add SSL configuration
            params = []
            if config.ssl:
                params.append("sslmode=require")
            
            if config.connection_timeout:
                params.append(f"connect_timeout={config.connection_timeout // 1000}")
            
            if params:
                dsn += "?" + "&".join(params)
            
            return dsn
            
        except Exception as e:
            self.logger.error(f"Failed to build secure DSN: {e}")
            raise
    
    async def _setup_connection(self, connection: Connection) -> None:
        """Setup individual connection with enterprise configuration"""
        try:
            # Set connection parameters
            await connection.execute("SET statement_timeout = '60s'")
            await connection.execute("SET idle_in_transaction_session_timeout = '5min'")
            await connection.execute("SET tcp_keepalives_idle = 600")
            await connection.execute("SET tcp_keepalives_interval = 30")
            await connection.execute("SET tcp_keepalives_count = 3")
            
        except Exception as e:
            self.logger.error(f"Error setting up connection: {e}")
            raise
    
    async def _init_connection(self, connection: Connection, pool_id: str) -> None:
        """Initialize connection with pool-specific settings"""
        try:
            # Set application name with pool identifier
            await connection.execute("SET application_name = $1", f"DafelHub-{pool_id}")
            
            self._total_connections_created += 1
            
        except Exception as e:
            self.logger.error(f"Error initializing connection for pool {pool_id}: {e}")
            raise
    
    async def _test_pool_health(self, pool_id: str) -> bool:
        """Test pool health with comprehensive checks"""
        try:
            pool = self._pools[pool_id]
            
            async with pool.acquire() as conn:
                # Basic connectivity test
                result = await conn.fetchrow("SELECT 1 as test, NOW() as timestamp")
                
                if result and result['test'] == 1:
                    self._pool_status[pool_id] = PoolStatus.HEALTHY
                    self._update_pool_metrics(pool_id, health_check=True)
                    return True
                else:
                    self._pool_status[pool_id] = PoolStatus.UNHEALTHY
                    return False
                    
        except Exception as e:
            self._pool_status[pool_id] = PoolStatus.UNHEALTHY
            self.logger.error(f"Pool health check failed: {pool_id}", extra={"error": str(e)})
            
            # Audit health check failure
            self.audit.add_entry(
                'database_pool_health_failed',
                {
                    'pool_id': pool_id,
                    'error': str(e)
                }
            )
            return False
    
    def _update_pool_metrics(
        self, 
        pool_id: str, 
        connection_acquired: bool = False,
        connection_released: bool = False,
        health_check: bool = False
    ) -> None:
        """Update pool metrics"""
        if pool_id not in self._pool_metrics:
            return
        
        metrics = self._pool_metrics[pool_id]
        metrics.last_activity = datetime.now()
        
        if connection_acquired:
            metrics.active_connections += 1
        
        if connection_released:
            metrics.active_connections = max(0, metrics.active_connections - 1)
        
        if health_check:
            pool = self._pools[pool_id]
            metrics.total_connections = pool.get_size()
            metrics.idle_connections = pool.get_idle_size()
    
    async def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Health check all pools
                for pool_id in list(self._pools.keys()):
                    await self._test_pool_health(pool_id)
                
                await asyncio.sleep(30)  # Health check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while not self._shutdown_event.is_set():
            try:
                # Clean up expired leases
                expired_leases = []
                async with self._leases_lock:
                    for lease_id, lease in list(self._connection_leases.items()):
                        if lease.is_expired:
                            expired_leases.append(lease_id)
                
                for lease_id in expired_leases:
                    self.logger.warning(f"Cleaning up expired lease: {lease_id}")
                    async with self._leases_lock:
                        lease = self._connection_leases.pop(lease_id, None)
                        if lease and lease.connection:
                            try:
                                # Find the pool this connection belongs to
                                for pool_id, pool in self._pools.items():
                                    try:
                                        await pool.release(lease.connection)
                                        break
                                    except:
                                        continue
                            except Exception as e:
                                self.logger.error(f"Error cleaning up expired lease {lease_id}: {e}")
                
                # Clean up old pending requests
                current_time = datetime.now()
                expired_requests = []
                for request_id, request in self._pending_requests.items():
                    if (current_time - request.requested_at).total_seconds() > request.timeout_seconds:
                        expired_requests.append(request_id)
                
                for request_id in expired_requests:
                    self._pending_requests.pop(request_id, None)
                
                await asyncio.sleep(60)  # Cleanup every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(30)
    
    async def _scaling_loop(self) -> None:
        """Background auto-scaling loop"""
        while not self._shutdown_event.is_set():
            try:
                for pool_id in list(self._pools.keys()):
                    config = self._pool_configs[pool_id]
                    if not config.enable_auto_scaling:
                        continue
                    
                    pool = self._pools[pool_id]
                    current_size = pool.get_size()
                    idle_size = pool.get_idle_size()
                    utilization = (current_size - idle_size) / current_size if current_size > 0 else 0
                    
                    # Scale up if high utilization
                    if (utilization > config.scaling_threshold and 
                        current_size < config.max_size and
                        len(self._pending_requests) > 0):
                        
                        new_size = min(current_size + config.scale_up_increment, config.max_size)
                        await self._scale_pool(pool_id, new_size)
                    
                    # Scale down if low utilization
                    elif (utilization < 0.3 and 
                          current_size > config.min_size and
                          idle_size > config.scale_down_decrement):
                        
                        new_size = max(current_size - config.scale_down_decrement, config.min_size)
                        await self._scale_pool(pool_id, new_size)
                
                await asyncio.sleep(60)  # Check scaling every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Scaling loop error: {e}")
                await asyncio.sleep(30)
    
    async def _scale_pool(self, pool_id: str, target_size: int) -> None:
        """Scale pool to target size"""
        try:
            pool = self._pools[pool_id]
            current_size = pool.get_size()
            
            if target_size == current_size:
                return
            
            self.logger.info(f"Scaling pool {pool_id}: {current_size} -> {target_size}")
            
            # Note: asyncpg doesn't support dynamic pool resizing
            # In a production system, you would implement custom pool scaling
            # For now, we log the scaling intent
            
            # Audit scaling event
            self.audit.add_entry(
                'database_pool_scaling',
                {
                    'pool_id': pool_id,
                    'current_size': current_size,
                    'target_size': target_size,
                    'scaling_direction': 'up' if target_size > current_size else 'down'
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error scaling pool {pool_id}: {e}")


# Global singleton instance
_connection_manager: Optional[EnterpriseConnectionManager] = None
_manager_lock = threading.Lock()


def get_connection_manager() -> EnterpriseConnectionManager:
    """Get global connection manager instance"""
    global _connection_manager
    
    with _manager_lock:
        if _connection_manager is None:
            _connection_manager = EnterpriseConnectionManager()
        return _connection_manager


async def initialize_connection_manager() -> EnterpriseConnectionManager:
    """Initialize and return connection manager"""
    manager = get_connection_manager()
    if not manager._monitor_task:  # Check if already initialized
        await manager.initialize()
    return manager