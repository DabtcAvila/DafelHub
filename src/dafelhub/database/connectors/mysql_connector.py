"""
MySQL Connector
Enterprise-grade MySQL database connector with advanced capabilities
"""

import asyncio
import time
import uuid
import json
import weakref
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Union, AsyncGenerator, 
    Callable, Tuple, AsyncIterator
)
import aiomysql
from aiomysql.pool import Pool
from aiomysql import Connection
import re
import sys

from dafelhub.core.connections import (
    IDataSourceConnector, ConnectionConfig, ConnectionMetadata, 
    QueryResult, ConnectionError, ConnectionErrorType, ConnectionStatus
)
from dafelhub.core.logging import get_logger, LoggerMixin


logger = get_logger(__name__)


class MySQLQueryType(Enum):
    """MySQL Query types for optimization"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DDL = "DDL"
    TRANSACTION = "TRANSACTION"
    UTILITY = "UTILITY"


@dataclass
class MySQLQueryMetrics:
    """MySQL query execution metrics"""
    query_id: str
    query_type: MySQLQueryType
    sql: str
    parameters: Optional[Dict[str, Any]]
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    rows_affected: int = 0
    rows_returned: int = 0
    connection_id: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds"""
        if self.execution_time is not None:
            return self.execution_time * 1000
        return 0.0


@dataclass
class MySQLConnectionPoolMetrics:
    """MySQL connection pool metrics"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    max_connections: int = 0
    min_connections: int = 0
    total_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    pool_created_at: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None


@dataclass
class MySQLPreparedStatement:
    """MySQL prepared statement cache entry"""
    statement_id: str
    sql: str
    parameter_types: List[str]
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    
    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        """Check if statement is expired"""
        return (datetime.now() - self.last_used).total_seconds() > ttl_seconds


class MySQLQueryStream:
    """Async MySQL query streaming implementation"""
    
    def __init__(self, connection: Connection, sql: str, parameters: List[Any], 
                 chunk_size: int = 1000):
        self.connection = connection
        self.sql = sql
        self.parameters = parameters
        self.chunk_size = chunk_size
        self._cursor = None
        self._exhausted = False
    
    async def __aenter__(self):
        """Enter async context"""
        self._cursor = await self.connection.cursor()
        await self._cursor.execute(self.sql, self.parameters)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context"""
        if self._cursor:
            await self._cursor.close()
    
    async def __aiter__(self):
        """Async iterator"""
        if not self._cursor:
            raise RuntimeError("Stream must be used within async context manager")
        
        while not self._exhausted:
            chunk = await self._cursor.fetchmany(self.chunk_size)
            if not chunk:
                self._exhausted = True
                break
            yield chunk


class MySQLConnector(IDataSourceConnector, LoggerMixin):
    """
    Enterprise MySQL Connector with advanced features:
    - Connection pooling with aiomysql
    - Query streaming for large datasets
    - Schema discovery with metadata detection
    - Prepared statement caching
    - Transaction management
    - Comprehensive error handling
    - Performance monitoring
    - Health checks and server version detection
    - Migration tools for PostgreSQL compatibility
    """
    
    def __init__(self, config: ConnectionConfig):
        self.id = config.id
        self.config = config
        self._pool: Optional[Pool] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._metadata = ConnectionMetadata()
        self._pool_metrics = MySQLConnectionPoolMetrics()
        self._query_history: List[MySQLQueryMetrics] = []
        self._prepared_statements: Dict[str, MySQLPreparedStatement] = {}
        self._active_queries: Dict[str, MySQLQueryMetrics] = {}
        self._transaction_connections: Dict[str, Connection] = {}
        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._server_info: Dict[str, Any] = {}
        self._connection_semaphore: Optional[asyncio.Semaphore] = None
        
        # Configuration
        self.statement_cache_size = config.configuration.get('statement_cache_size', 1000)
        self.statement_cache_ttl = config.configuration.get('statement_cache_ttl', 3600)
        self.query_history_size = config.configuration.get('query_history_size', 10000)
        self.streaming_chunk_size = config.configuration.get('streaming_chunk_size', 1000)
        self.health_check_interval = config.configuration.get('health_check_interval', 30)
        self.cleanup_interval = config.configuration.get('cleanup_interval', 300)
        
        self.logger.info(f"MySQL connector initialized: {self.id}")
    
    @property
    def status(self) -> ConnectionStatus:
        """Current connection status"""
        return self._status
    
    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        return self._metadata.is_healthy and self._pool is not None
    
    async def connect(self) -> None:
        """Establish MySQL connection pool with enterprise features"""
        if self._pool is not None:
            self.logger.warning(f"MySQL connection pool already exists: {self.id}")
            return
        
        self._status = ConnectionStatus.CONNECTING
        start_time = time.time()
        
        try:
            # Create connection pool
            self._pool = await aiomysql.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.username,
                password=self.config.password,
                db=self.config.database,
                minsize=self.config.configuration.get('pool_min_size', 2),
                maxsize=self.config.configuration.get('pool_max_size', self.config.pool_size),
                charset=self.config.configuration.get('charset', 'utf8mb4'),
                use_unicode=True,
                sql_mode=self.config.configuration.get('sql_mode', 'TRADITIONAL'),
                autocommit=False,
                connect_timeout=self.config.connection_timeout / 1000 if self.config.connection_timeout else 10,
                echo=self.config.configuration.get('echo', False),
            )
            
            # Test connection
            await self._test_pool_connection()
            
            # Initialize pool metrics
            self._pool_metrics = MySQLConnectionPoolMetrics(
                max_connections=self.config.pool_size,
                min_connections=self.config.configuration.get('pool_min_size', 2),
                pool_created_at=datetime.now()
            )
            
            # Update metadata
            self._metadata.connected_at = datetime.now()
            self._metadata.is_healthy = True
            self._metadata.server_info = self._server_info
            self._status = ConnectionStatus.CONNECTED
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Initialize semaphore for connection limiting
            self._connection_semaphore = asyncio.Semaphore(self.config.pool_size)
            
            duration = time.time() - start_time
            self.logger.info(f"MySQL pool connected successfully: {self.id} ({duration:.2f}s)", 
                           extra_data={
                               "pool_size": f"{self._pool_metrics.min_connections}-{self._pool_metrics.max_connections}",
                               "server_version": self._server_info.get('version', 'unknown')
                           })
            
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            duration = time.time() - start_time
            error = self._handle_error(e)
            self.logger.error(f"Failed to connect MySQL pool: {self.id} ({duration:.2f}s)", 
                            extra_data={"error": str(error)})
            raise error
    
    async def disconnect(self) -> None:
        """Close MySQL connection pool gracefully"""
        if self._pool is None:
            return
        
        self.logger.info(f"Disconnecting MySQL pool: {self.id}")
        self._status = ConnectionStatus.DISCONNECTED
        
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Wait for active queries to complete (with timeout)
            await self._wait_for_active_queries(timeout=30.0)
            
            # Cancel background tasks
            if self._health_task and not self._health_task.done():
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass
            
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close all active transactions
            for tx_id, conn in list(self._transaction_connections.items()):
                try:
                    await conn.rollback()
                    conn.close()
                except Exception as e:
                    self.logger.warning(f"Error closing transaction connection: {e}")
                finally:
                    del self._transaction_connections[tx_id]
            
            # Close pool
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            
            # Update metadata
            self._metadata.is_healthy = False
            self._metadata.last_activity = datetime.now()
            
            self.logger.info(f"MySQL pool disconnected: {self.id}")
            
        except Exception as e:
            error = self._handle_error(e)
            self.logger.error(f"Error disconnecting MySQL pool: {self.id}", 
                            extra_data={"error": str(error)})
            raise error
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test MySQL connection and gather server information"""
        if not self._pool:
            return {
                "success": False,
                "message": "No connection pool available",
                "response_time": 0
            }
        
        start_time = time.time()
        
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Get server information
                    await cursor.execute('SELECT VERSION()')
                    version_result = await cursor.fetchone()
                    
                    await cursor.execute('SELECT DATABASE()')
                    current_db = await cursor.fetchone()
                    
                    await cursor.execute('SELECT USER()')
                    current_user = await cursor.fetchone()
                    
                    await cursor.execute("SHOW VARIABLES LIKE 'time_zone'")
                    timezone = await cursor.fetchone()
                    
                    await cursor.execute("SHOW VARIABLES LIKE 'character_set_server'")
                    charset = await cursor.fetchone()
                    
                    # Get server statistics
                    await cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
                    max_conn = await cursor.fetchone()
                    
                    await cursor.execute("SHOW VARIABLES LIKE 'innodb_buffer_pool_size'")
                    buffer_pool = await cursor.fetchone()
                    
                    response_time = time.time() - start_time
                    
                    server_info = {
                        'version': version_result[0] if version_result else 'unknown',
                        'database': current_db[0] if current_db else 'unknown',
                        'user': current_user[0] if current_user else 'unknown',
                        'timezone': timezone[1] if timezone else 'unknown',
                        'charset': charset[1] if charset else 'unknown',
                        'max_connections': max_conn[1] if max_conn else 'unknown',
                        'innodb_buffer_pool_size': buffer_pool[1] if buffer_pool else 'unknown'
                    }
                    
                    self._server_info = server_info
                    
                    return {
                        "success": True,
                        "message": "Connection successful",
                        "response_time": response_time,
                        "server_info": server_info
                    }
        
        except Exception as e:
            response_time = time.time() - start_time
            error = self._handle_error(e)
            
            return {
                "success": False,
                "message": str(error),
                "response_time": response_time
            }
    
    async def health_check(self) -> bool:
        """Quick MySQL health check"""
        if not self._pool:
            return False
        
        try:
            async with asyncio.timeout(5.0):  # 5 second timeout
                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute('SELECT 1')
                        await cursor.fetchone()
                        self._metadata.is_healthy = True
                        self._metadata.last_activity = datetime.now()
                        return True
        
        except Exception as e:
            self._metadata.is_healthy = False
            self._metadata.last_error = str(e)
            self.logger.warning(f"Health check failed: {self.id}", extra_data={"error": str(e)})
            return False
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a MySQL query with comprehensive monitoring"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        query_id = str(uuid.uuid4())
        query_type = self._detect_query_type(query)
        parameters = params or {}
        
        # Create query metrics
        metrics = MySQLQueryMetrics(
            query_id=query_id,
            query_type=query_type,
            sql=query.strip(),
            parameters=parameters,
            start_time=datetime.now()
        )
        
        self._active_queries[query_id] = metrics
        
        try:
            async with self._connection_semaphore:
                async with self._pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        metrics.connection_id = str(id(conn))
                        
                        start_execution = time.time()
                        
                        # Execute query based on type
                        if query_type in [MySQLQueryType.SELECT]:
                            if parameters:
                                await cursor.execute(query, list(parameters.values()))
                            else:
                                await cursor.execute(query)
                            
                            result = await cursor.fetchall()
                            
                            # Get column names
                            columns = [desc[0] for desc in cursor.description] if cursor.description else []
                            
                            # Convert to dictionaries
                            data = [dict(zip(columns, row)) for row in result] if result else []
                            rows_returned = len(data)
                            rows_affected = 0
                        
                        else:  # INSERT, UPDATE, DELETE, DDL
                            if parameters:
                                await cursor.execute(query, list(parameters.values()))
                            else:
                                await cursor.execute(query)
                            
                            data = None
                            rows_returned = 0
                            rows_affected = cursor.rowcount if cursor.rowcount != -1 else 0
                        
                        execution_time = time.time() - start_execution
                        
                        # Update metrics
                        metrics.end_time = datetime.now()
                        metrics.execution_time = execution_time
                        metrics.rows_returned = rows_returned
                        metrics.rows_affected = rows_affected
                        
                        # Update pool metrics
                        self._update_pool_metrics(True, execution_time)
                        
                        # Store in history
                        self._store_query_metrics(metrics)
                        
                        return QueryResult(
                            success=True,
                            data=data,
                            metadata={
                                'query_id': query_id,
                                'execution_time': execution_time,
                                'rows_returned': rows_returned,
                                'rows_affected': rows_affected,
                                'query_type': query_type.value
                            },
                            execution_time=execution_time
                        )
        
        except Exception as e:
            execution_time = time.time() - metrics.start_time.timestamp()
            metrics.end_time = datetime.now()
            metrics.execution_time = execution_time
            metrics.error = str(e)
            
            # Update pool metrics
            self._update_pool_metrics(False, execution_time)
            
            # Store failed query in history
            self._store_query_metrics(metrics)
            
            error = self._handle_error(e)
            self.logger.error(f"Query execution failed: {query_id}", 
                            extra_data={
                                "error": str(error),
                                "query_type": query_type.value,
                                "execution_time": execution_time
                            })
            
            return QueryResult(
                success=False,
                error=str(error),
                execution_time=execution_time
            )
        
        finally:
            # Remove from active queries
            self._active_queries.pop(query_id, None)
    
    async def stream_query(self, query: str, params: Optional[List[Any]] = None, 
                          chunk_size: int = None) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream large MySQL query results"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        chunk_size = chunk_size or self.streaming_chunk_size
        parameters = params or []
        
        self.logger.info(f"Starting MySQL query stream: {self.id}", 
                        extra_data={
                            "chunk_size": chunk_size,
                            "query_preview": query[:100] + "..." if len(query) > 100 else query
                        })
        
        async with self._pool.acquire() as conn:
            stream = MySQLQueryStream(conn, query, parameters, chunk_size)
            
            async with stream:
                async for chunk in stream:
                    # Get column names
                    columns = [desc[0] for desc in stream._cursor.description] if stream._cursor.description else []
                    # Convert to dictionaries
                    yield [dict(zip(columns, row)) for row in chunk]
    
    async def get_schema_info(self, schema_name: str = None) -> Dict[str, Any]:
        """Get comprehensive MySQL schema information with metadata"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        # Use current database if no schema specified
        if not schema_name:
            schema_name = self.config.database
        
        schema_info = {
            'schema_name': schema_name,
            'tables': [],
            'views': [],
            'functions': [],
            'procedures': [],
            'triggers': []
        }
        
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Get tables with detailed information
                await cursor.execute('''
                    SELECT 
                        table_name,
                        table_type,
                        table_comment,
                        table_rows,
                        data_length,
                        index_length,
                        auto_increment
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    ORDER BY table_name
                ''', (schema_name,))
                
                tables = await cursor.fetchall()
                
                for table in tables:
                    table_info = {
                        'name': table[0],
                        'type': table[1],
                        'comment': table[2],
                        'estimated_rows': table[3],
                        'data_size': table[4],
                        'index_size': table[5],
                        'auto_increment': table[6],
                        'columns': [],
                        'indexes': [],
                        'constraints': []
                    }
                    
                    # Get columns
                    await cursor.execute('''
                        SELECT 
                            column_name,
                            data_type,
                            is_nullable,
                            column_default,
                            character_maximum_length,
                            numeric_precision,
                            numeric_scale,
                            column_comment,
                            column_key
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                    ''', (schema_name, table[0]))
                    
                    columns = await cursor.fetchall()
                    
                    for column in columns:
                        table_info['columns'].append({
                            'name': column[0],
                            'type': column[1],
                            'nullable': column[2] == 'YES',
                            'default': column[3],
                            'max_length': column[4],
                            'precision': column[5],
                            'scale': column[6],
                            'comment': column[7],
                            'key_type': column[8]
                        })
                    
                    # Get indexes
                    await cursor.execute('''
                        SELECT DISTINCT
                            index_name,
                            non_unique,
                            index_type,
                            index_comment
                        FROM information_schema.statistics
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY index_name
                    ''', (schema_name, table[0]))
                    
                    indexes = await cursor.fetchall()
                    
                    for index in indexes:
                        table_info['indexes'].append({
                            'name': index[0],
                            'unique': index[1] == 0,
                            'type': index[2],
                            'comment': index[3]
                        })
                    
                    schema_info['tables'].append(table_info)
                
                # Get views
                await cursor.execute('''
                    SELECT 
                        table_name,
                        view_definition
                    FROM information_schema.views
                    WHERE table_schema = %s
                    ORDER BY table_name
                ''', (schema_name,))
                
                views = await cursor.fetchall()
                schema_info['views'] = [
                    {
                        'name': view[0],
                        'definition': view[1]
                    }
                    for view in views
                ]
                
                # Get stored procedures and functions
                await cursor.execute('''
                    SELECT 
                        routine_name,
                        routine_type,
                        data_type,
                        routine_definition
                    FROM information_schema.routines
                    WHERE routine_schema = %s
                    ORDER BY routine_name
                ''', (schema_name,))
                
                routines = await cursor.fetchall()
                
                for routine in routines:
                    routine_info = {
                        'name': routine[0],
                        'type': routine[1],
                        'return_type': routine[2],
                        'definition': routine[3]
                    }
                    
                    if routine[1] == 'FUNCTION':
                        schema_info['functions'].append(routine_info)
                    else:
                        schema_info['procedures'].append(routine_info)
        
        return schema_info
    
    @asynccontextmanager
    async def transaction(self, isolation_level: str = 'read_committed'):
        """Advanced MySQL transaction context manager"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        tx_id = str(uuid.uuid4())
        conn = await self._pool.acquire()
        
        try:
            # Start transaction with specified isolation level
            isolation_map = {
                'read_uncommitted': 'READ UNCOMMITTED',
                'read_committed': 'READ COMMITTED',
                'repeatable_read': 'REPEATABLE READ',
                'serializable': 'SERIALIZABLE'
            }
            
            isolation_sql = isolation_map.get(isolation_level, 'READ COMMITTED')
            
            await conn.begin()
            async with conn.cursor() as cursor:
                await cursor.execute(f'SET SESSION TRANSACTION ISOLATION LEVEL {isolation_sql}')
            
            self._transaction_connections[tx_id] = conn
            
            try:
                yield conn
                await conn.commit()
                self.logger.debug(f"Transaction committed: {tx_id}")
            
            except Exception as e:
                await conn.rollback()
                self.logger.warning(f"Transaction rolled back: {tx_id}", extra_data={"error": str(e)})
                raise
        
        finally:
            self._transaction_connections.pop(tx_id, None)
            self._pool.release(conn)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive MySQL performance metrics"""
        current_time = datetime.now()
        
        # Calculate query statistics
        total_queries = len(self._query_history)
        failed_queries = sum(1 for q in self._query_history if q.error)
        
        if total_queries > 0:
            avg_execution_time = sum(q.execution_time or 0 for q in self._query_history) / total_queries
            success_rate = (total_queries - failed_queries) / total_queries * 100
        else:
            avg_execution_time = 0
            success_rate = 100
        
        # Query type distribution
        query_type_stats = {}
        for query in self._query_history:
            qt = query.query_type.value
            if qt not in query_type_stats:
                query_type_stats[qt] = {'count': 0, 'avg_time': 0, 'total_time': 0}
            query_type_stats[qt]['count'] += 1
            query_type_stats[qt]['total_time'] += query.execution_time or 0
        
        for qt_stats in query_type_stats.values():
            if qt_stats['count'] > 0:
                qt_stats['avg_time'] = qt_stats['total_time'] / qt_stats['count']
        
        return {
            'connection_id': self.id,
            'status': self._status.value,
            'uptime_seconds': (current_time - self._metadata.connected_at).total_seconds() 
                            if self._metadata.connected_at else 0,
            'pool_metrics': {
                'max_size': self._pool_metrics.max_connections,
                'min_size': self._pool_metrics.min_connections,
                'current_size': self._pool.size if self._pool else 0,
                'available': self._pool.freesize if self._pool else 0,
            },
            'query_metrics': {
                'total_queries': total_queries,
                'failed_queries': failed_queries,
                'success_rate': success_rate,
                'avg_execution_time': avg_execution_time,
                'active_queries': len(self._active_queries),
                'query_type_distribution': query_type_stats
            },
            'prepared_statements': {
                'cached_count': len(self._prepared_statements),
                'cache_hit_rate': self._calculate_cache_hit_rate(),
                'total_usage': sum(stmt.usage_count for stmt in self._prepared_statements.values())
            },
            'server_info': self._server_info,
            'last_activity': self._metadata.last_activity.isoformat() 
                           if self._metadata.last_activity else None
        }
    
    async def migrate_from_postgresql(self, postgres_query: str) -> str:
        """Convert PostgreSQL queries to MySQL-compatible syntax"""
        mysql_query = postgres_query
        
        # Common PostgreSQL to MySQL conversions
        conversions = [
            # Data types
            (r'\bSERIAL\b', 'INT AUTO_INCREMENT'),
            (r'\bBIGSERIAL\b', 'BIGINT AUTO_INCREMENT'),
            (r'\bBOOLEAN\b', 'TINYINT(1)'),
            (r'\bTEXT\b', 'LONGTEXT'),
            (r'\bBYTEA\b', 'LONGBLOB'),
            
            # Functions
            (r'\bCURRENT_TIMESTAMP\b', 'NOW()'),
            (r'\bNOW\(\)', 'NOW()'),
            (r'\bCOALESCE\(', 'IFNULL('),
            
            # String functions
            (r'\bCONCAT\(', 'CONCAT('),
            (r'\|\|', ', '),  # String concatenation
            
            # Limit syntax
            (r'\bLIMIT\s+(\d+)\s+OFFSET\s+(\d+)', r'LIMIT \2, \1'),
            
            # Quote identifiers
            (r'"([^"]+)"', r'`\1`'),
            
            # Schema references
            (r'\bpublic\.', ''),
        ]
        
        for pattern, replacement in conversions:
            mysql_query = re.sub(pattern, replacement, mysql_query, flags=re.IGNORECASE)
        
        return mysql_query
    
    # Private methods
    
    async def _test_pool_connection(self) -> None:
        """Test MySQL pool connection during startup"""
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('SELECT 1')
                await cursor.fetchone()
    
    async def _start_background_tasks(self) -> None:
        """Start background monitoring tasks"""
        # Health check task
        self._health_task = asyncio.create_task(self._health_check_loop())
        
        # Cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        while not self._shutdown_event.is_set():
            try:
                await self.health_check()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check loop error: {self.id}", extra_data={"error": str(e)})
                await asyncio.sleep(5)  # Short sleep on error
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while not self._shutdown_event.is_set():
            try:
                await self._cleanup_prepared_statements()
                await self._cleanup_query_history()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {self.id}", extra_data={"error": str(e)})
                await asyncio.sleep(30)  # Longer sleep on error
    
    async def _cleanup_prepared_statements(self) -> None:
        """Clean up expired prepared statements"""
        if len(self._prepared_statements) <= self.statement_cache_size:
            return
        
        # Remove expired statements
        expired = [
            name for name, stmt in self._prepared_statements.items()
            if stmt.is_expired(self.statement_cache_ttl)
        ]
        
        for name in expired:
            try:
                if self._pool:
                    async with self._pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(f'DEALLOCATE PREPARE {name}')
                del self._prepared_statements[name]
            except Exception as e:
                self.logger.warning(f"Failed to deallocate prepared statement: {name}", 
                                  extra_data={"error": str(e)})
        
        # If still too many, remove least recently used
        if len(self._prepared_statements) > self.statement_cache_size:
            sorted_stmts = sorted(
                self._prepared_statements.items(),
                key=lambda x: x[1].last_used
            )
            
            for name, _ in sorted_stmts[:len(self._prepared_statements) - self.statement_cache_size]:
                try:
                    if self._pool:
                        async with self._pool.acquire() as conn:
                            async with conn.cursor() as cursor:
                                await cursor.execute(f'DEALLOCATE PREPARE {name}')
                    del self._prepared_statements[name]
                except Exception as e:
                    self.logger.warning(f"Failed to deallocate prepared statement: {name}",
                                      extra_data={"error": str(e)})
    
    async def _cleanup_query_history(self) -> None:
        """Clean up old query history"""
        if len(self._query_history) > self.query_history_size:
            # Keep only the most recent queries
            self._query_history = self._query_history[-self.query_history_size:]
    
    async def _wait_for_active_queries(self, timeout: float = 30.0) -> None:
        """Wait for active queries to complete"""
        start_time = time.time()
        
        while self._active_queries and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)
        
        if self._active_queries:
            self.logger.warning(f"Timeout waiting for {len(self._active_queries)} active queries")
    
    def _detect_query_type(self, query: str) -> MySQLQueryType:
        """Detect query type from SQL"""
        normalized = query.strip().upper()
        
        if normalized.startswith('SELECT'):
            return MySQLQueryType.SELECT
        elif normalized.startswith('INSERT'):
            return MySQLQueryType.INSERT
        elif normalized.startswith('UPDATE'):
            return MySQLQueryType.UPDATE
        elif normalized.startswith('DELETE'):
            return MySQLQueryType.DELETE
        elif normalized.startswith(('CREATE', 'DROP', 'ALTER', 'TRUNCATE')):
            return MySQLQueryType.DDL
        elif normalized.startswith(('START', 'BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT')):
            return MySQLQueryType.TRANSACTION
        else:
            return MySQLQueryType.UTILITY
    
    def _update_pool_metrics(self, success: bool, execution_time: float) -> None:
        """Update pool metrics"""
        self._pool_metrics.total_queries += 1
        self._pool_metrics.last_activity = datetime.now()
        
        if not success:
            self._pool_metrics.failed_queries += 1
        
        # Update average query time
        if self._pool_metrics.total_queries == 1:
            self._pool_metrics.avg_query_time = execution_time
        else:
            # Exponential moving average
            alpha = 0.1
            self._pool_metrics.avg_query_time = (
                alpha * execution_time + 
                (1 - alpha) * self._pool_metrics.avg_query_time
            )
    
    def _store_query_metrics(self, metrics: MySQLQueryMetrics) -> None:
        """Store query metrics in history"""
        self._query_history.append(metrics)
        
        # Limit history size
        if len(self._query_history) > self.query_history_size:
            self._query_history.pop(0)
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate prepared statement cache hit rate"""
        total_executions = sum(stmt.usage_count for stmt in self._prepared_statements.values())
        cached_executions = len(self._prepared_statements)
        
        if total_executions == 0:
            return 0.0
        
        return (cached_executions / total_executions) * 100
    
    def _handle_error(self, error: Exception) -> ConnectionError:
        """Handle and classify MySQL errors"""
        error_type = ConnectionErrorType.UNKNOWN
        error_code = "UNKNOWN"
        
        if hasattr(error, 'args') and error.args:
            mysql_errno = error.args[0] if isinstance(error.args[0], int) else None
            
            # Authentication and authorization errors
            if mysql_errno in (1045, 1044, 1142, 1227):
                error_type = ConnectionErrorType.AUTHENTICATION_FAILED
                error_code = 'AUTH_FAILED'
            
            # Connection errors
            elif mysql_errno in (2003, 2013, 2006):
                error_type = ConnectionErrorType.CONNECTION_REFUSED
                error_code = 'CONN_FAILED'
            
            # Syntax and semantic errors
            elif mysql_errno in (1064, 1146, 1054, 1049):
                error_type = ConnectionErrorType.INVALID_CONFIGURATION
                error_code = 'QUERY_ERROR'
            
            # Timeout errors
            elif mysql_errno in (1969, 2013):
                error_type = ConnectionErrorType.QUERY_TIMEOUT
                error_code = 'QUERY_TIMEOUT'
        
        # Handle connection-level errors
        elif isinstance(error, (ConnectionRefusedError, OSError)):
            error_type = ConnectionErrorType.CONNECTION_REFUSED
            error_code = 'CONN_REFUSED'
        
        elif isinstance(error, asyncio.TimeoutError):
            error_type = ConnectionErrorType.CONNECTION_TIMEOUT
            error_code = 'CONN_TIMEOUT'
        
        return ConnectionError(
            str(error),
            error_type,
            error_code,
            context={'original_error': error}
        )


# Factory function for easy instantiation
def create_mysql_connector(config: ConnectionConfig) -> MySQLConnector:
    """Create MySQL connector instance"""
    return MySQLConnector(config)