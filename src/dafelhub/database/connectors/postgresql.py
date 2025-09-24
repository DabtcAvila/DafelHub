"""
PostgreSQL Connector
Enterprise-grade PostgreSQL database connector with advanced capabilities
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
import asyncpg
from asyncpg.pool import Pool
from asyncpg import Connection, Record
import re
import sys

from dafelhub.core.connections import (
    IDataSourceConnector, ConnectionConfig, ConnectionMetadata, 
    QueryResult, ConnectionError, ConnectionErrorType, ConnectionStatus
)
from dafelhub.core.logging import get_logger, LoggerMixin


logger = get_logger(__name__)


class QueryType(Enum):
    """SQL Query types for optimization"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DDL = "DDL"
    TRANSACTION = "TRANSACTION"
    UTILITY = "UTILITY"


@dataclass
class QueryMetrics:
    """Query execution metrics"""
    query_id: str
    query_type: QueryType
    sql: str
    parameters: Optional[Dict[str, Any]]
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    rows_affected: int = 0
    rows_returned: int = 0
    plan_time: Optional[float] = None
    execution_plan: Optional[Dict[str, Any]] = None
    cache_hit: bool = False
    connection_id: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds"""
        if self.execution_time is not None:
            return self.execution_time * 1000
        return 0.0


@dataclass
class ConnectionPoolMetrics:
    """Connection pool metrics"""
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
class PreparedStatement:
    """Prepared statement cache entry"""
    statement_id: str
    sql: str
    parameter_types: List[str]
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    
    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        """Check if statement is expired"""
        return (datetime.now() - self.last_used).total_seconds() > ttl_seconds


class QueryStream:
    """Async query streaming implementation"""
    
    def __init__(self, connection: Connection, sql: str, parameters: List[Any], 
                 chunk_size: int = 1000, prefetch: int = 100):
        self.connection = connection
        self.sql = sql
        self.parameters = parameters
        self.chunk_size = chunk_size
        self.prefetch = prefetch
        self._cursor = None
        self._exhausted = False
    
    async def __aenter__(self):
        """Enter async context"""
        self._cursor = self.connection.cursor(self.sql, *self.parameters, prefetch=self.prefetch)
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
            chunk = await self._cursor.fetch(self.chunk_size)
            if not chunk:
                self._exhausted = True
                break
            yield chunk


class PostgreSQLConnector(IDataSourceConnector, LoggerMixin):
    """
    Enterprise PostgreSQL Connector with advanced features:
    - Connection pooling with asyncpg
    - Query streaming for large datasets
    - Schema discovery with metadata detection
    - Prepared statement caching
    - Transaction management
    - Comprehensive error handling
    - Performance monitoring
    - Health checks and server version detection
    """
    
    def __init__(self, config: ConnectionConfig):
        self.id = config.id
        self.config = config
        self._pool: Optional[Pool] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._metadata = ConnectionMetadata()
        self._pool_metrics = ConnectionPoolMetrics()
        self._query_history: List[QueryMetrics] = []
        self._prepared_statements: Dict[str, PreparedStatement] = {}
        self._active_queries: Dict[str, QueryMetrics] = {}
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
        self.streaming_prefetch = config.configuration.get('streaming_prefetch', 100)
        self.health_check_interval = config.configuration.get('health_check_interval', 30)
        self.cleanup_interval = config.configuration.get('cleanup_interval', 300)
        
        self.logger.info(f"PostgreSQL connector initialized: {self.id}")
    
    @property
    def status(self) -> ConnectionStatus:
        """Current connection status"""
        return self._status
    
    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        return self._metadata.is_healthy and self._pool is not None
    
    async def connect(self) -> None:
        """Establish connection pool with enterprise features"""
        if self._pool is not None:
            self.logger.warning(f"Connection pool already exists: {self.id}")
            return
        
        self._status = ConnectionStatus.CONNECTING
        start_time = time.time()
        
        try:
            # Build connection DSN
            dsn = self._build_dsn()
            
            # Create connection pool
            self._pool = await asyncpg.create_pool(
                dsn,
                min_size=self.config.configuration.get('pool_min_size', 2),
                max_size=self.config.configuration.get('pool_max_size', self.config.pool_size),
                max_queries=self.config.configuration.get('max_queries_per_connection', 50000),
                max_inactive_connection_lifetime=self.config.configuration.get(
                    'max_inactive_connection_lifetime', 300.0
                ),
                setup=self._setup_connection,
                init=self._init_connection,
                command_timeout=self.config.query_timeout / 1000,
                server_settings=self.config.configuration.get('server_settings', {}),
            )
            
            # Test connection
            await self._test_pool_connection()
            
            # Initialize pool metrics
            self._pool_metrics = ConnectionPoolMetrics(
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
            self.logger.info(f"PostgreSQL pool connected successfully: {self.id} ({duration:.2f}s)", 
                           extra_data={
                               "pool_size": f"{self._pool_metrics.min_connections}-{self._pool_metrics.max_connections}",
                               "server_version": self._server_info.get('version', 'unknown')
                           })
            
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            duration = time.time() - start_time
            error = self._handle_error(e)
            self.logger.error(f"Failed to connect PostgreSQL pool: {self.id} ({duration:.2f}s)", 
                            extra_data={"error": str(error)})
            raise error
    
    async def disconnect(self) -> None:
        """Close connection pool gracefully"""
        if self._pool is None:
            return
        
        self.logger.info(f"Disconnecting PostgreSQL pool: {self.id}")
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
                    await conn.execute('ROLLBACK')
                    await conn.close()
                except Exception as e:
                    self.logger.warning(f"Error closing transaction connection: {e}")
                finally:
                    del self._transaction_connections[tx_id]
            
            # Close pool
            await self._pool.close()
            self._pool = None
            
            # Update metadata
            self._metadata.is_healthy = False
            self._metadata.last_activity = datetime.now()
            
            self.logger.info(f"PostgreSQL pool disconnected: {self.id}")
            
        except Exception as e:
            error = self._handle_error(e)
            self.logger.error(f"Error disconnecting PostgreSQL pool: {self.id}", 
                            extra_data={"error": str(error)})
            raise error
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection and gather server information"""
        if not self._pool:
            return {
                "success": False,
                "message": "No connection pool available",
                "response_time": 0
            }
        
        start_time = time.time()
        
        try:
            async with self._pool.acquire() as conn:
                # Get server information
                version_result = await conn.fetchrow('SELECT version()')
                current_db = await conn.fetchrow('SELECT current_database()')
                current_user = await conn.fetchrow('SELECT current_user')
                timezone = await conn.fetchrow('SHOW timezone')
                encoding = await conn.fetchrow('SHOW client_encoding')
                
                # Get server statistics
                stats = await conn.fetchrow('''
                    SELECT 
                        current_setting('max_connections') as max_connections,
                        current_setting('shared_buffers') as shared_buffers,
                        current_setting('work_mem') as work_mem
                ''')
                
                response_time = time.time() - start_time
                
                server_info = {
                    'version': version_result['version'],
                    'database': current_db['current_database'],
                    'user': current_user['current_user'],
                    'timezone': timezone['timezone'],
                    'encoding': encoding['client_encoding'],
                    'max_connections': stats['max_connections'],
                    'shared_buffers': stats['shared_buffers'],
                    'work_mem': stats['work_mem']
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
        """Quick health check"""
        if not self._pool:
            return False
        
        try:
            async with asyncio.timeout(5.0):  # 5 second timeout
                async with self._pool.acquire() as conn:
                    await conn.fetchrow('SELECT 1')
                    self._metadata.is_healthy = True
                    self._metadata.last_activity = datetime.now()
                    return True
        
        except Exception as e:
            self._metadata.is_healthy = False
            self._metadata.last_error = str(e)
            self.logger.warning(f"Health check failed: {self.id}", extra_data={"error": str(e)})
            return False
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a query with comprehensive monitoring"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        query_id = str(uuid.uuid4())
        query_type = self._detect_query_type(query)
        parameters = params or {}
        
        # Create query metrics
        metrics = QueryMetrics(
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
                    metrics.connection_id = str(id(conn))
                    
                    start_execution = time.time()
                    
                    # Execute query based on type
                    if query_type in [QueryType.SELECT]:
                        if parameters:
                            result = await conn.fetch(query, *parameters.values())
                        else:
                            result = await conn.fetch(query)
                        
                        data = [dict(record) for record in result]
                        rows_returned = len(data)
                        rows_affected = 0
                    
                    else:  # INSERT, UPDATE, DELETE, DDL
                        if parameters:
                            result = await conn.execute(query, *parameters.values())
                        else:
                            result = await conn.execute(query)
                        
                        data = None
                        rows_returned = 0
                        # Extract affected rows from result
                        if isinstance(result, str) and result.split():
                            try:
                                rows_affected = int(result.split()[-1])
                            except (ValueError, IndexError):
                                rows_affected = 0
                        else:
                            rows_affected = 0
                    
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
                          chunk_size: int = None, prefetch: int = None) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream large query results"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        chunk_size = chunk_size or self.streaming_chunk_size
        prefetch = prefetch or self.streaming_prefetch
        parameters = params or []
        
        self.logger.info(f"Starting query stream: {self.id}", 
                        extra_data={
                            "chunk_size": chunk_size,
                            "prefetch": prefetch,
                            "query_preview": query[:100] + "..." if len(query) > 100 else query
                        })
        
        async with self._pool.acquire() as conn:
            stream = QueryStream(conn, query, parameters, chunk_size, prefetch)
            
            async with stream:
                async for chunk in stream:
                    yield [dict(record) for record in chunk]
    
    async def get_schema_info(self, schema_name: str = 'public') -> Dict[str, Any]:
        """Get comprehensive schema information with metadata"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        schema_info = {
            'schema_name': schema_name,
            'tables': [],
            'views': [],
            'functions': [],
            'sequences': [],
            'indexes': [],
            'constraints': []
        }
        
        async with self._pool.acquire() as conn:
            # Get tables with detailed information
            tables_query = '''
                SELECT 
                    t.table_name,
                    t.table_type,
                    obj_description(pgc.oid) as table_comment,
                    pg_size_pretty(pg_total_relation_size(pgc.oid)) as size
                FROM information_schema.tables t
                LEFT JOIN pg_class pgc ON pgc.relname = t.table_name
                LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace
                WHERE t.table_schema = $1
                ORDER BY t.table_name
            '''
            
            tables = await conn.fetch(tables_query, schema_name)
            
            for table in tables:
                table_info = {
                    'name': table['table_name'],
                    'type': table['table_type'],
                    'comment': table['table_comment'],
                    'size': table['size'],
                    'columns': [],
                    'indexes': [],
                    'constraints': []
                }
                
                # Get columns
                columns_query = '''
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        character_maximum_length,
                        numeric_precision,
                        numeric_scale,
                        col_description(pgc.oid, c.ordinal_position) as column_comment
                    FROM information_schema.columns c
                    LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
                    LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace
                    WHERE c.table_schema = $1 AND c.table_name = $2
                    ORDER BY c.ordinal_position
                '''
                
                columns = await conn.fetch(columns_query, schema_name, table['table_name'])
                
                for column in columns:
                    table_info['columns'].append({
                        'name': column['column_name'],
                        'type': column['data_type'],
                        'nullable': column['is_nullable'] == 'YES',
                        'default': column['column_default'],
                        'max_length': column['character_maximum_length'],
                        'precision': column['numeric_precision'],
                        'scale': column['numeric_scale'],
                        'comment': column['column_comment']
                    })
                
                # Get indexes
                indexes_query = '''
                    SELECT 
                        i.indexname,
                        i.indexdef,
                        idx.indisunique as is_unique,
                        idx.indisprimary as is_primary
                    FROM pg_indexes i
                    JOIN pg_class t ON t.relname = i.tablename
                    JOIN pg_index idx ON idx.indexrelid = (
                        SELECT oid FROM pg_class WHERE relname = i.indexname
                    )
                    WHERE i.schemaname = $1 AND i.tablename = $2
                '''
                
                indexes = await conn.fetch(indexes_query, schema_name, table['table_name'])
                
                for index in indexes:
                    table_info['indexes'].append({
                        'name': index['indexname'],
                        'definition': index['indexdef'],
                        'unique': index['is_unique'],
                        'primary': index['is_primary']
                    })
                
                schema_info['tables'].append(table_info)
            
            # Get views
            views_query = '''
                SELECT 
                    table_name,
                    view_definition
                FROM information_schema.views
                WHERE table_schema = $1
                ORDER BY table_name
            '''
            
            views = await conn.fetch(views_query, schema_name)
            schema_info['views'] = [
                {
                    'name': view['table_name'],
                    'definition': view['view_definition']
                }
                for view in views
            ]
            
            # Get functions
            functions_query = '''
                SELECT 
                    routine_name,
                    routine_type,
                    data_type as return_type,
                    routine_definition
                FROM information_schema.routines
                WHERE routine_schema = $1
                ORDER BY routine_name
            '''
            
            functions = await conn.fetch(functions_query, schema_name)
            schema_info['functions'] = [
                {
                    'name': func['routine_name'],
                    'type': func['routine_type'],
                    'return_type': func['return_type'],
                    'definition': func['routine_definition']
                }
                for func in functions
            ]
        
        return schema_info
    
    @asynccontextmanager
    async def transaction(self, isolation_level: str = 'read_committed'):
        """Advanced transaction context manager"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        tx_id = str(uuid.uuid4())
        conn = await self._pool.acquire()
        
        try:
            # Start transaction with specified isolation level
            if isolation_level == 'serializable':
                await conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
            elif isolation_level == 'repeatable_read':
                await conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ')
            elif isolation_level == 'read_committed':
                await conn.execute('BEGIN ISOLATION LEVEL READ COMMITTED')
            else:
                await conn.execute('BEGIN')
            
            self._transaction_connections[tx_id] = conn
            
            try:
                yield conn
                await conn.execute('COMMIT')
                self.logger.debug(f"Transaction committed: {tx_id}")
            
            except Exception as e:
                await conn.execute('ROLLBACK')
                self.logger.warning(f"Transaction rolled back: {tx_id}", extra_data={"error": str(e)})
                raise
        
        finally:
            self._transaction_connections.pop(tx_id, None)
            await self._pool.release(conn)
    
    async def prepare_statement(self, sql: str, name: Optional[str] = None) -> str:
        """Prepare and cache SQL statement"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available", 
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        # Generate statement name if not provided
        statement_name = name or f"stmt_{hash(sql) % sys.maxsize}"
        
        # Check if already cached
        if statement_name in self._prepared_statements:
            stmt = self._prepared_statements[statement_name]
            stmt.last_used = datetime.now()
            stmt.usage_count += 1
            return statement_name
        
        # Prepare new statement
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(f'PREPARE {statement_name} AS {sql}')
                
                # Cache the statement
                self._prepared_statements[statement_name] = PreparedStatement(
                    statement_id=statement_name,
                    sql=sql,
                    parameter_types=[],  # Would need to parse SQL to determine types
                    created_at=datetime.now(),
                    last_used=datetime.now(),
                    usage_count=1
                )
                
                # Clean cache if too large
                await self._cleanup_prepared_statements()
                
                return statement_name
                
            except Exception as e:
                error = self._handle_error(e)
                self.logger.error(f"Failed to prepare statement: {statement_name}", 
                                extra_data={"error": str(error), "sql": sql})
                raise error
    
    async def execute_prepared(self, statement_name: str, params: Optional[List[Any]] = None) -> QueryResult:
        """Execute prepared statement"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        if statement_name not in self._prepared_statements:
            raise ConnectionError(
                f"Prepared statement not found: {statement_name}",
                ConnectionErrorType.INVALID_CONFIGURATION
            )
        
        stmt = self._prepared_statements[statement_name]
        parameters = params or []
        
        try:
            async with self._pool.acquire() as conn:
                start_time = time.time()
                
                if stmt.sql.strip().upper().startswith('SELECT'):
                    result = await conn.fetch(f'EXECUTE {statement_name}', *parameters)
                    data = [dict(record) for record in result]
                    rows_returned = len(data)
                    rows_affected = 0
                else:
                    result = await conn.execute(f'EXECUTE {statement_name}', *parameters)
                    data = None
                    rows_returned = 0
                    rows_affected = int(result.split()[-1]) if result and result.split() else 0
                
                execution_time = time.time() - start_time
                
                # Update statement usage
                stmt.last_used = datetime.now()
                stmt.usage_count += 1
                
                return QueryResult(
                    success=True,
                    data=data,
                    metadata={
                        'statement_name': statement_name,
                        'execution_time': execution_time,
                        'rows_returned': rows_returned,
                        'rows_affected': rows_affected,
                        'cache_hit': True
                    },
                    execution_time=execution_time
                )
                
        except Exception as e:
            error = self._handle_error(e)
            self.logger.error(f"Failed to execute prepared statement: {statement_name}",
                            extra_data={"error": str(error)})
            
            return QueryResult(
                success=False,
                error=str(error),
                metadata={'statement_name': statement_name, 'cache_hit': True}
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
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
                'current_size': self._pool.get_size() if self._pool else 0,
                'available': self._pool.get_idle_size() if self._pool else 0,
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
    
    async def explain_query(self, query: str, params: Optional[List[Any]] = None, 
                           analyze: bool = False) -> Dict[str, Any]:
        """Get query execution plan"""
        if not self._pool:
            raise ConnectionError(
                "No connection pool available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        explain_query = f"EXPLAIN {'ANALYZE ' if analyze else ''}(FORMAT JSON) {query}"
        parameters = params or []
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchrow(explain_query, *parameters)
                return result[0][0] if result and result[0] else {}
                
        except Exception as e:
            error = self._handle_error(e)
            self.logger.error(f"Failed to explain query", extra_data={"error": str(error)})
            raise error
    
    # Private methods
    
    def _build_dsn(self) -> str:
        """Build PostgreSQL DSN from configuration"""
        dsn_parts = [
            f"postgresql://{self.config.username}:{self.config.password}",
            f"@{self.config.host}:{self.config.port}/{self.config.database}"
        ]
        
        params = []
        if self.config.ssl:
            params.append("sslmode=require")
        
        # Add connection timeout
        if self.config.connection_timeout:
            params.append(f"connect_timeout={self.config.connection_timeout // 1000}")
        
        # Add custom parameters
        for key, value in self.config.configuration.get('connection_params', {}).items():
            params.append(f"{key}={value}")
        
        if params:
            dsn_parts.append("?" + "&".join(params))
        
        return "".join(dsn_parts)
    
    async def _setup_connection(self, conn: Connection) -> None:
        """Setup individual connection"""
        # Set connection-level parameters
        await conn.execute("SET application_name = $1", f"DafelHub-{self.id}")
        
        # Set timezone if specified
        timezone = self.config.configuration.get('timezone')
        if timezone:
            await conn.execute(f"SET timezone = '{timezone}'")
    
    async def _init_connection(self, conn: Connection) -> None:
        """Initialize connection with custom types"""
        # Register custom type adapters if needed
        pass
    
    async def _test_pool_connection(self) -> None:
        """Test pool connection during startup"""
        async with self._pool.acquire() as conn:
            await conn.fetchrow('SELECT 1')
    
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
                        await conn.execute(f'DEALLOCATE {name}')
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
                            await conn.execute(f'DEALLOCATE {name}')
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
    
    def _detect_query_type(self, query: str) -> QueryType:
        """Detect query type from SQL"""
        normalized = query.strip().upper()
        
        if normalized.startswith('SELECT'):
            return QueryType.SELECT
        elif normalized.startswith('INSERT'):
            return QueryType.INSERT
        elif normalized.startswith('UPDATE'):
            return QueryType.UPDATE
        elif normalized.startswith('DELETE'):
            return QueryType.DELETE
        elif normalized.startswith(('CREATE', 'DROP', 'ALTER', 'TRUNCATE')):
            return QueryType.DDL
        elif normalized.startswith(('BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT')):
            return QueryType.TRANSACTION
        else:
            return QueryType.UTILITY
    
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
    
    def _store_query_metrics(self, metrics: QueryMetrics) -> None:
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
        """Handle and classify PostgreSQL errors"""
        error_type = ConnectionErrorType.UNKNOWN
        error_code = "UNKNOWN"
        
        if hasattr(error, 'sqlstate'):
            sqlstate = error.sqlstate
            
            # Authentication and authorization errors
            if sqlstate in ('28000', '28P01'):
                error_type = ConnectionErrorType.AUTHENTICATION_FAILED
                error_code = 'AUTH_FAILED'
            
            # Connection errors
            elif sqlstate in ('08000', '08003', '08006'):
                error_type = ConnectionErrorType.CONNECTION_REFUSED
                error_code = 'CONN_FAILED'
            
            # Syntax and semantic errors
            elif sqlstate.startswith('42'):
                error_type = ConnectionErrorType.INVALID_CONFIGURATION
                error_code = 'QUERY_ERROR'
            
            # Timeout errors
            elif sqlstate == '57014':  # Query cancelled
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
def create_postgresql_connector(config: ConnectionConfig) -> PostgreSQLConnector:
    """Create PostgreSQL connector instance"""
    return PostgreSQLConnector(config)