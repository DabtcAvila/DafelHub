"""
Comprehensive tests for PostgreSQL Connector
Tests enterprise features including connection pooling, streaming, monitoring, etc.
"""

import asyncio
import pytest
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from dafelhub.core.connections import ConnectionConfig, ConnectionType, ConnectionStatus
from dafelhub.database.connectors.postgresql import (
    PostgreSQLConnector, QueryType, QueryMetrics, create_postgresql_connector
)
from dafelhub.database.connectors.monitoring import (
    MonitoringCollector, MonitoringDashboard, get_monitoring_collector
)


@pytest.fixture
def connection_config():
    """Test connection configuration"""
    return ConnectionConfig(
        id="test-postgres-1",
        name="Test PostgreSQL Connection",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass",
        pool_size=5,
        connection_timeout=30000,
        query_timeout=60000,
        configuration={
            'pool_min_size': 2,
            'pool_max_size': 5,
            'statement_cache_size': 100,
            'streaming_chunk_size': 1000,
            'health_check_interval': 30
        }
    )


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg pool"""
    mock_pool = AsyncMock()
    mock_pool.get_size.return_value = 3
    mock_pool.get_idle_size.return_value = 2
    return mock_pool


@pytest.fixture
def mock_connection():
    """Mock asyncpg connection"""
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock()
    mock_conn.fetch = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.cursor = AsyncMock()
    return mock_conn


class TestPostgreSQLConnector:
    """Test PostgreSQL connector functionality"""
    
    def test_initialization(self, connection_config):
        """Test connector initialization"""
        connector = PostgreSQLConnector(connection_config)
        
        assert connector.id == connection_config.id
        assert connector.config == connection_config
        assert connector.status == ConnectionStatus.DISCONNECTED
        assert connector._pool is None
        assert connector.statement_cache_size == 100
        assert connector.streaming_chunk_size == 1000
    
    def test_factory_function(self, connection_config):
        """Test factory function"""
        connector = create_postgresql_connector(connection_config)
        
        assert isinstance(connector, PostgreSQLConnector)
        assert connector.id == connection_config.id
    
    @pytest.mark.asyncio
    async def test_dsn_building(self, connection_config):
        """Test DSN construction"""
        connector = PostgreSQLConnector(connection_config)
        dsn = connector._build_dsn()
        
        expected = "postgresql://testuser:testpass@localhost:5432/testdb?connect_timeout=30"
        assert dsn == expected
    
    @pytest.mark.asyncio
    @patch('dafelhub.database.connectors.postgresql.asyncpg.create_pool')
    async def test_connection_success(self, mock_create_pool, connection_config, mock_asyncpg_pool, mock_connection):
        """Test successful connection"""
        # Setup mocks
        mock_create_pool.return_value = mock_asyncpg_pool
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        # Mock server info queries
        mock_connection.fetchrow.side_effect = [
            {'version': 'PostgreSQL 15.0'},
            {'current_database': 'testdb'},
            {'current_user': 'testuser'},
            {'timezone': 'UTC'},
            {'client_encoding': 'UTF8'},
            {
                'max_connections': '100',
                'shared_buffers': '128MB',
                'work_mem': '4MB'
            }
        ]
        
        connector = PostgreSQLConnector(connection_config)
        
        await connector.connect()
        
        assert connector.status == ConnectionStatus.CONNECTED
        assert connector._pool is not None
        assert connector._metadata.is_healthy is True
        assert connector._server_info['version'] == 'PostgreSQL 15.0'
        
        # Cleanup
        await connector.disconnect()
    
    @pytest.mark.asyncio
    @patch('dafelhub.database.connectors.postgresql.asyncpg.create_pool')
    async def test_connection_failure(self, mock_create_pool, connection_config):
        """Test connection failure handling"""
        mock_create_pool.side_effect = asyncpg.exceptions.InvalidAuthorizationSpecificationError("auth failed")
        
        connector = PostgreSQLConnector(connection_config)
        
        with pytest.raises(Exception):
            await connector.connect()
        
        assert connector.status == ConnectionStatus.ERROR
        assert connector._pool is None
    
    @pytest.mark.asyncio
    async def test_health_check(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test health check functionality"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        mock_connection.fetchrow.return_value = {'result': 1}
        
        result = await connector.health_check()
        
        assert result is True
        assert connector._metadata.is_healthy is True
        
        # Test health check failure
        mock_connection.fetchrow.side_effect = Exception("Connection lost")
        
        result = await connector.health_check()
        
        assert result is False
        assert connector._metadata.is_healthy is False
    
    @pytest.mark.asyncio
    async def test_query_execution_select(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test SELECT query execution"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        connector._connection_semaphore = asyncio.Semaphore(5)
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        mock_records = [
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'}
        ]
        mock_connection.fetch.return_value = mock_records
        
        result = await connector.execute_query("SELECT * FROM users", {'limit': 10})
        
        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]['name'] == 'Alice'
        assert result.metadata['query_type'] == 'SELECT'
        assert result.metadata['rows_returned'] == 2
    
    @pytest.mark.asyncio
    async def test_query_execution_insert(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test INSERT query execution"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        connector._connection_semaphore = asyncio.Semaphore(5)
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        mock_connection.execute.return_value = "INSERT 0 1"
        
        result = await connector.execute_query("INSERT INTO users (name) VALUES ($1)", {'name': 'Charlie'})
        
        assert result.success is True
        assert result.data is None
        assert result.metadata['rows_affected'] == 1
        assert result.metadata['query_type'] == 'INSERT'
    
    @pytest.mark.asyncio
    async def test_query_execution_error(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test query execution error handling"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        connector._connection_semaphore = asyncio.Semaphore(5)
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        # Mock SQL error
        sql_error = asyncpg.exceptions.UndefinedTableError("table does not exist")
        sql_error.sqlstate = '42P01'
        mock_connection.fetch.side_effect = sql_error
        
        result = await connector.execute_query("SELECT * FROM nonexistent_table")
        
        assert result.success is False
        assert "table does not exist" in result.error
    
    @pytest.mark.asyncio
    async def test_transaction_management(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test transaction management"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value = mock_connection
        mock_asyncpg_pool.release = AsyncMock()
        
        async with connector.transaction() as conn:
            assert conn == mock_connection
            mock_connection.execute.assert_any_call('BEGIN ISOLATION LEVEL READ COMMITTED')
        
        # Verify commit was called
        mock_connection.execute.assert_any_call('COMMIT')
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test transaction rollback on error"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value = mock_connection
        mock_asyncpg_pool.release = AsyncMock()
        
        with pytest.raises(ValueError):
            async with connector.transaction() as conn:
                mock_connection.execute.assert_any_call('BEGIN ISOLATION LEVEL READ COMMITTED')
                raise ValueError("Test error")
        
        # Verify rollback was called
        mock_connection.execute.assert_any_call('ROLLBACK')
    
    @pytest.mark.asyncio
    async def test_prepared_statements(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test prepared statement functionality"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        sql = "SELECT * FROM users WHERE id = $1"
        
        # Prepare statement
        stmt_name = await connector.prepare_statement(sql, "get_user_by_id")
        
        assert stmt_name == "get_user_by_id"
        assert stmt_name in connector._prepared_statements
        mock_connection.execute.assert_called_with('PREPARE get_user_by_id AS SELECT * FROM users WHERE id = $1')
        
        # Execute prepared statement
        mock_connection.fetch.return_value = [{'id': 1, 'name': 'Alice'}]
        
        result = await connector.execute_prepared(stmt_name, [1])
        
        assert result.success is True
        assert len(result.data) == 1
        assert result.metadata['cache_hit'] is True
    
    @pytest.mark.asyncio
    async def test_query_streaming(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test query streaming functionality"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        # Mock cursor
        mock_cursor = AsyncMock()
        mock_connection.cursor.return_value = mock_cursor
        
        # Mock data chunks
        chunk1 = [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
        chunk2 = [{'id': 3, 'name': 'Charlie'}]
        
        async def mock_stream():
            yield chunk1
            yield chunk2
            return
        
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.__aexit__.return_value = None
        mock_cursor.__aiter__ = lambda self: mock_stream()
        
        # Test streaming
        chunks = []
        async for chunk in connector.stream_query("SELECT * FROM users", chunk_size=2):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0][0]['name'] == 'Alice'
        assert chunks[1][0]['name'] == 'Charlie'
    
    @pytest.mark.asyncio
    async def test_schema_discovery(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test schema discovery functionality"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        # Mock schema queries
        mock_connection.fetch.side_effect = [
            # Tables query
            [
                {
                    'table_name': 'users',
                    'table_type': 'BASE TABLE',
                    'table_comment': 'User accounts',
                    'size': '8192 bytes'
                }
            ],
            # Columns query
            [
                {
                    'column_name': 'id',
                    'data_type': 'integer',
                    'is_nullable': 'NO',
                    'column_default': 'nextval(\'users_id_seq\'::regclass)',
                    'character_maximum_length': None,
                    'numeric_precision': 32,
                    'numeric_scale': 0,
                    'column_comment': 'Primary key'
                },
                {
                    'column_name': 'name',
                    'data_type': 'character varying',
                    'is_nullable': 'YES',
                    'column_default': None,
                    'character_maximum_length': 255,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'column_comment': 'User name'
                }
            ],
            # Indexes query
            [
                {
                    'indexname': 'users_pkey',
                    'indexdef': 'CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)',
                    'is_unique': True,
                    'is_primary': True
                }
            ],
            # Views query
            [
                {
                    'table_name': 'user_stats',
                    'view_definition': 'SELECT count(*) FROM users'
                }
            ],
            # Functions query
            [
                {
                    'routine_name': 'get_user_count',
                    'routine_type': 'FUNCTION',
                    'return_type': 'integer',
                    'routine_definition': 'RETURN (SELECT count(*) FROM users);'
                }
            ]
        ]
        
        schema = await connector.get_schema_info('public')
        
        assert schema['schema_name'] == 'public'
        assert len(schema['tables']) == 1
        assert schema['tables'][0]['name'] == 'users'
        assert len(schema['tables'][0]['columns']) == 2
        assert schema['tables'][0]['columns'][0]['name'] == 'id'
        assert len(schema['tables'][0]['indexes']) == 1
        assert schema['tables'][0]['indexes'][0]['primary'] is True
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, connection_config):
        """Test performance metrics collection"""
        connector = PostgreSQLConnector(connection_config)
        
        # Add some mock query history
        connector._query_history = [
            QueryMetrics(
                query_id="q1",
                query_type=QueryType.SELECT,
                sql="SELECT * FROM users",
                parameters=None,
                start_time=datetime.now(),
                end_time=datetime.now(),
                execution_time=0.1,
                rows_returned=10
            ),
            QueryMetrics(
                query_id="q2",
                query_type=QueryType.INSERT,
                sql="INSERT INTO users VALUES ($1, $2)",
                parameters={'name': 'test'},
                start_time=datetime.now(),
                end_time=datetime.now(),
                execution_time=0.05,
                rows_affected=1
            )
        ]
        
        metrics = connector.get_performance_metrics()
        
        assert metrics['connection_id'] == connector.id
        assert metrics['query_metrics']['total_queries'] == 2
        assert metrics['query_metrics']['success_rate'] == 100.0
        assert 'SELECT' in metrics['query_metrics']['query_type_distribution']
        assert 'INSERT' in metrics['query_metrics']['query_type_distribution']
    
    @pytest.mark.asyncio
    async def test_explain_query(self, connection_config, mock_asyncpg_pool, mock_connection):
        """Test query explanation functionality"""
        connector = PostgreSQLConnector(connection_config)
        connector._pool = mock_asyncpg_pool
        
        # Setup mock
        mock_asyncpg_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_asyncpg_pool.acquire.return_value.__aexit__.return_value = None
        
        mock_plan = [{
            'Plan': {
                'Node Type': 'Seq Scan',
                'Relation Name': 'users',
                'Total Cost': 15.00,
                'Rows': 100
            }
        }]
        
        mock_connection.fetchrow.return_value = [mock_plan]
        
        result = await connector.explain_query("SELECT * FROM users")
        
        assert 'Plan' in result
        assert result['Plan']['Node Type'] == 'Seq Scan'
    
    def test_query_type_detection(self, connection_config):
        """Test query type detection"""
        connector = PostgreSQLConnector(connection_config)
        
        assert connector._detect_query_type("SELECT * FROM users") == QueryType.SELECT
        assert connector._detect_query_type("INSERT INTO users VALUES (1, 'test')") == QueryType.INSERT
        assert connector._detect_query_type("UPDATE users SET name = 'test'") == QueryType.UPDATE
        assert connector._detect_query_type("DELETE FROM users WHERE id = 1") == QueryType.DELETE
        assert connector._detect_query_type("CREATE TABLE test (id INT)") == QueryType.DDL
        assert connector._detect_query_type("BEGIN TRANSACTION") == QueryType.TRANSACTION
        assert connector._detect_query_type("VACUUM ANALYZE") == QueryType.UTILITY
    
    def test_error_handling(self, connection_config):
        """Test error classification"""
        connector = PostgreSQLConnector(connection_config)
        
        # Test authentication error
        auth_error = Exception("authentication failed")
        auth_error.sqlstate = '28P01'
        
        conn_error = connector._handle_error(auth_error)
        assert conn_error.error_type.value == 'authentication_failed'
        
        # Test connection error
        conn_refused_error = ConnectionRefusedError("connection refused")
        conn_error = connector._handle_error(conn_refused_error)
        assert conn_error.error_type.value == 'connection_refused'
        
        # Test timeout error
        timeout_error = asyncio.TimeoutError("query timeout")
        conn_error = connector._handle_error(timeout_error)
        assert conn_error.error_type.value == 'connection_timeout'


class TestMonitoringIntegration:
    """Test monitoring system integration"""
    
    @pytest.mark.asyncio
    async def test_monitoring_collector(self, connection_config):
        """Test monitoring collector functionality"""
        collector = MonitoringCollector()
        connector = PostgreSQLConnector(connection_config)
        
        # Register connector
        collector.register_connector(connector)
        
        # Mock connector metrics
        with patch.object(connector, 'get_performance_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'status': 'connected',
                'uptime_seconds': 3600,
                'last_activity': datetime.now().isoformat(),
                'query_metrics': {
                    'success_rate': 98.5,
                    'avg_execution_time': 0.15,
                    'query_type_distribution': {
                        'SELECT': {'count': 100, 'avg_time': 0.1, 'total_time': 10.0}
                    }
                },
                'pool_metrics': {
                    'current_size': 3,
                    'max_size': 5
                }
            }
            
            await collector.collect_metrics()
            
            # Check collected data
            assert connector.id in collector._connection_metrics
            health = collector._connection_metrics[connector.id]
            assert health.status == 'connected'
            assert health.query_success_rate == 98.5
            assert health.pool_utilization == 60.0  # 3/5 * 100
    
    @pytest.mark.asyncio
    async def test_dashboard_data_generation(self, connection_config):
        """Test dashboard data generation"""
        collector = MonitoringCollector()
        connector = PostgreSQLConnector(connection_config)
        
        # Add some test data
        from dafelhub.database.connectors.monitoring import ConnectionHealth, PerformanceAlert, AlertLevel
        
        health = ConnectionHealth(
            connection_id=connector.id,
            status='connected',
            uptime=3600,
            last_activity=datetime.now(),
            query_success_rate=99.0,
            avg_response_time=0.1,
            active_connections=3,
            max_connections=5,
            pool_utilization=60.0
        )
        
        collector._connection_metrics[connector.id] = health
        
        dashboard_data = collector.get_dashboard_data()
        
        assert 'overview' in dashboard_data
        assert 'connections' in dashboard_data
        assert len(dashboard_data['connections']) == 1
        assert dashboard_data['connections'][0]['id'] == connector.id
        assert dashboard_data['overview']['active_connections'] == 1
    
    @pytest.mark.asyncio
    async def test_alert_generation(self, connection_config):
        """Test alert generation"""
        collector = MonitoringCollector()
        connector = PostgreSQLConnector(connection_config)
        
        from dafelhub.database.connectors.monitoring import ConnectionHealth
        
        # Create health data that triggers alerts
        health = ConnectionHealth(
            connection_id=connector.id,
            status='connected',
            uptime=3600,
            last_activity=datetime.now(),
            query_success_rate=85.0,  # Below 95% threshold
            avg_response_time=6.0,    # Above 5s threshold
            active_connections=3,
            max_connections=5,
            pool_utilization=95.0     # Above 90% threshold
        )
        
        await collector._check_alerts(connector.id, health)
        
        # Check that alerts were generated
        active_alerts = [a for a in collector._alerts if not a.resolved]
        assert len(active_alerts) > 0
        
        # Should have alerts for low success rate, high query time, and high pool utilization
        alert_metrics = [a.metric for a in active_alerts]
        assert 'query_success_rate' in alert_metrics
        assert 'avg_execution_time' in alert_metrics
        assert 'pool_utilization' in alert_metrics
    
    @pytest.mark.asyncio
    async def test_monitoring_dashboard(self):
        """Test monitoring dashboard functionality"""
        collector = MonitoringCollector()
        dashboard = MonitoringDashboard(collector, update_interval=0.1)
        
        # Start dashboard
        await dashboard.start()
        assert dashboard._running is True
        
        # Get real-time data
        data = dashboard.get_realtime_data()
        assert 'timestamp' in data
        assert 'overview' in data
        
        # Generate report
        report = await dashboard.generate_report()
        assert 'PostgreSQL System Performance Report' in report
        
        # Stop dashboard
        await dashboard.stop()
        assert dashboard._running is False


@pytest.mark.integration
class TestPostgreSQLConnectorIntegration:
    """Integration tests that require a real PostgreSQL instance"""
    
    @pytest.mark.skipif(not pytest.config.getoption("--integration"), 
                       reason="requires --integration option")
    async def test_real_connection(self):
        """Test with real PostgreSQL instance"""
        config = ConnectionConfig(
            id="integration-test",
            name="Integration Test PostgreSQL",
            type=ConnectionType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="postgres",
            username="postgres",
            password="password",
            pool_size=2
        )
        
        connector = PostgreSQLConnector(config)
        
        try:
            await connector.connect()
            
            # Test basic query
            result = await connector.execute_query("SELECT 1 as test_value")
            assert result.success is True
            assert result.data[0]['test_value'] == 1
            
            # Test health check
            healthy = await connector.health_check()
            assert healthy is True
            
        finally:
            await connector.disconnect()


# Pytest configuration
def pytest_addoption(parser):
    parser.addoption(
        "--integration", action="store_true", default=False,
        help="run integration tests"
    )