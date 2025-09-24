"""
Unit tests for database connection management.

Comprehensive testing of all database connectors, connection pooling, and health monitoring.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
import pymongo
import mysql.connector
import psycopg2

from dafelhub.database.connection_manager import ConnectionManager
from dafelhub.database.connectors.postgresql import PostgreSQLConnector
from dafelhub.database.connectors.mysql_connector import MySQLConnector
from dafelhub.database.connectors.mongodb_connector import MongoDBConnector
from dafelhub.database.health_monitor import HealthMonitor
from dafelhub.database.backup_system import BackupSystem


class TestConnectionManager:
    """Test cases for ConnectionManager."""
    
    @pytest.fixture
    def connection_manager(self, mock_settings):
        """Create connection manager instance."""
        return ConnectionManager(mock_settings)
    
    @pytest.fixture
    def mock_connection_config(self):
        """Mock connection configuration."""
        return {
            "id": "test-conn-123",
            "name": "Test Connection",
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "testuser",
            "password": "testpass",
            "ssl_mode": "prefer",
            "pool_size": 10,
            "max_overflow": 20
        }
    
    def test_connection_registration(self, connection_manager, mock_connection_config):
        """Test database connection registration."""
        result = connection_manager.register_connection(mock_connection_config)
        
        assert result["success"] is True
        assert result["connection_id"] == "test-conn-123"
        assert "test-conn-123" in connection_manager.connections
    
    def test_connection_testing(self, connection_manager, mock_connection_config):
        """Test database connection testing."""
        with patch.object(connection_manager, '_test_postgresql_connection', return_value=True):
            result = connection_manager.test_connection(mock_connection_config)
            
            assert result["success"] is True
            assert result["connection_time"] > 0
    
    def test_connection_retrieval(self, connection_manager, mock_connection_config):
        """Test database connection retrieval."""
        connection_manager.register_connection(mock_connection_config)
        
        connection = connection_manager.get_connection("test-conn-123")
        
        assert connection is not None
        assert connection.connection_id == "test-conn-123"
    
    def test_connection_pooling(self, connection_manager, mock_connection_config):
        """Test connection pool management."""
        connection_manager.register_connection(mock_connection_config)
        
        with patch('sqlalchemy.create_engine') as mock_engine:
            pool_info = connection_manager.get_pool_info("test-conn-123")
            
            assert pool_info["pool_size"] == 10
            assert pool_info["max_overflow"] == 20
    
    def test_connection_health_check(self, connection_manager, mock_connection_config):
        """Test connection health monitoring."""
        connection_manager.register_connection(mock_connection_config)
        
        with patch.object(connection_manager, '_check_connection_health', return_value={"healthy": True}):
            health = connection_manager.check_connection_health("test-conn-123")
            
            assert health["healthy"] is True
    
    def test_connection_cleanup(self, connection_manager, mock_connection_config):
        """Test connection cleanup and resource management."""
        connection_manager.register_connection(mock_connection_config)
        
        result = connection_manager.close_connection("test-conn-123")
        
        assert result["success"] is True
        assert "test-conn-123" not in connection_manager.active_connections
    
    def test_multiple_connection_types(self, connection_manager):
        """Test managing multiple database types."""
        postgres_config = {
            "id": "postgres-1",
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "testdb"
        }
        
        mysql_config = {
            "id": "mysql-1", 
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "testdb"
        }
        
        mongo_config = {
            "id": "mongo-1",
            "type": "mongodb",
            "host": "localhost",
            "port": 27017,
            "database": "testdb"
        }
        
        for config in [postgres_config, mysql_config, mongo_config]:
            result = connection_manager.register_connection(config)
            assert result["success"] is True
        
        assert len(connection_manager.connections) == 3
    
    def test_connection_failover(self, connection_manager):
        """Test connection failover mechanism."""
        primary_config = {
            "id": "primary-db",
            "type": "postgresql",
            "host": "primary.db.com",
            "failover_hosts": ["backup1.db.com", "backup2.db.com"]
        }
        
        with patch.object(connection_manager, '_test_postgresql_connection', side_effect=[False, True]):
            result = connection_manager.establish_connection_with_failover(primary_config)
            
            assert result["success"] is True
            assert result["active_host"] == "backup1.db.com"
    
    def test_connection_encryption(self, connection_manager):
        """Test encrypted connection handling."""
        encrypted_config = {
            "id": "encrypted-db",
            "type": "postgresql",
            "host": "secure.db.com",
            "ssl_mode": "require",
            "ssl_cert": "/path/to/cert.pem",
            "ssl_key": "/path/to/key.pem",
            "ssl_ca": "/path/to/ca.pem"
        }
        
        with patch('sqlalchemy.create_engine') as mock_engine:
            connection_manager.register_connection(encrypted_config)
            
            # Verify SSL parameters were passed
            mock_engine.assert_called()
            call_args = mock_engine.call_args
            assert 'sslmode=require' in str(call_args)


class TestPostgreSQLConnector:
    """Test cases for PostgreSQL connector."""
    
    @pytest.fixture
    def postgres_connector(self, mock_connection_config):
        """Create PostgreSQL connector instance."""
        return PostgreSQLConnector(mock_connection_config)
    
    def test_connection_establishment(self, postgres_connector):
        """Test PostgreSQL connection establishment."""
        with patch('psycopg2.connect') as mock_connect:
            mock_connect.return_value = Mock()
            
            result = postgres_connector.connect()
            
            assert result["success"] is True
            assert mock_connect.called
    
    def test_connection_failure_handling(self, postgres_connector):
        """Test PostgreSQL connection failure handling."""
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("Connection failed")):
            result = postgres_connector.connect()
            
            assert result["success"] is False
            assert "connection failed" in result["error"].lower()
    
    def test_query_execution(self, postgres_connector):
        """Test PostgreSQL query execution."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("test_value",)]
        mock_cursor.description = [("column1",)]
        
        with patch.object(postgres_connector, 'get_cursor', return_value=mock_cursor):
            result = postgres_connector.execute_query("SELECT 'test_value'")
            
            assert result["success"] is True
            assert len(result["data"]) == 1
            assert result["data"][0]["column1"] == "test_value"
    
    def test_transaction_handling(self, postgres_connector):
        """Test PostgreSQL transaction management."""
        mock_conn = Mock()
        
        with patch.object(postgres_connector, 'connection', mock_conn):
            with postgres_connector.transaction():
                postgres_connector.execute_query("INSERT INTO test VALUES (1)")
            
            assert mock_conn.commit.called
    
    def test_transaction_rollback(self, postgres_connector):
        """Test PostgreSQL transaction rollback on error."""
        mock_conn = Mock()
        
        with patch.object(postgres_connector, 'connection', mock_conn):
            try:
                with postgres_connector.transaction():
                    postgres_connector.execute_query("INSERT INTO test VALUES (1)")
                    raise Exception("Test error")
            except Exception:
                pass
            
            assert mock_conn.rollback.called
    
    def test_prepared_statements(self, postgres_connector):
        """Test PostgreSQL prepared statements."""
        mock_cursor = Mock()
        
        with patch.object(postgres_connector, 'get_cursor', return_value=mock_cursor):
            postgres_connector.execute_prepared(
                "SELECT * FROM users WHERE id = %s AND email = %s",
                (123, "test@example.com")
            )
            
            mock_cursor.execute.assert_called_with(
                "SELECT * FROM users WHERE id = %s AND email = %s",
                (123, "test@example.com")
            )
    
    def test_bulk_operations(self, postgres_connector):
        """Test PostgreSQL bulk operations."""
        mock_cursor = Mock()
        data = [(1, "user1"), (2, "user2"), (3, "user3")]
        
        with patch.object(postgres_connector, 'get_cursor', return_value=mock_cursor):
            result = postgres_connector.bulk_insert("users", ["id", "name"], data)
            
            assert result["success"] is True
            assert mock_cursor.executemany.called


class TestMySQLConnector:
    """Test cases for MySQL connector."""
    
    @pytest.fixture
    def mysql_connector(self):
        """Create MySQL connector instance."""
        config = {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "testdb",
            "username": "testuser",
            "password": "testpass"
        }
        return MySQLConnector(config)
    
    def test_mysql_connection(self, mysql_connector):
        """Test MySQL connection establishment."""
        with patch('mysql.connector.connect') as mock_connect:
            mock_connect.return_value = Mock()
            
            result = mysql_connector.connect()
            
            assert result["success"] is True
            assert mock_connect.called
    
    def test_mysql_query_execution(self, mysql_connector):
        """Test MySQL query execution."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("value1", "value2")]
        mock_cursor.column_names = ["col1", "col2"]
        
        with patch.object(mysql_connector, 'get_cursor', return_value=mock_cursor):
            result = mysql_connector.execute_query("SELECT col1, col2 FROM test")
            
            assert result["success"] is True
            assert len(result["data"]) == 1
    
    def test_mysql_charset_handling(self, mysql_connector):
        """Test MySQL charset and collation handling."""
        with patch('mysql.connector.connect') as mock_connect:
            mysql_connector.connect()
            
            call_args = mock_connect.call_args[1]
            assert "charset" in call_args or "use_unicode" in call_args


class TestMongoDBConnector:
    """Test cases for MongoDB connector."""
    
    @pytest.fixture
    def mongodb_connector(self):
        """Create MongoDB connector instance."""
        config = {
            "type": "mongodb",
            "host": "localhost",
            "port": 27017,
            "database": "testdb",
            "username": "testuser",
            "password": "testpass"
        }
        return MongoDBConnector(config)
    
    def test_mongodb_connection(self, mongodb_connector):
        """Test MongoDB connection establishment."""
        with patch('pymongo.MongoClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            result = mongodb_connector.connect()
            
            assert result["success"] is True
            assert mock_client.called
    
    def test_mongodb_document_insertion(self, mongodb_connector):
        """Test MongoDB document insertion."""
        mock_collection = Mock()
        mock_collection.insert_one.return_value.inserted_id = "doc_id_123"
        
        with patch.object(mongodb_connector, 'get_collection', return_value=mock_collection):
            result = mongodb_connector.insert_document("users", {"name": "test", "email": "test@example.com"})
            
            assert result["success"] is True
            assert result["document_id"] == "doc_id_123"
    
    def test_mongodb_document_querying(self, mongodb_connector):
        """Test MongoDB document querying."""
        mock_collection = Mock()
        mock_collection.find.return_value = [
            {"_id": "1", "name": "user1"},
            {"_id": "2", "name": "user2"}
        ]
        
        with patch.object(mongodb_connector, 'get_collection', return_value=mock_collection):
            result = mongodb_connector.find_documents("users", {"active": True})
            
            assert result["success"] is True
            assert len(result["documents"]) == 2
    
    def test_mongodb_aggregation(self, mongodb_connector):
        """Test MongoDB aggregation pipeline."""
        mock_collection = Mock()
        mock_collection.aggregate.return_value = [
            {"_id": "group1", "count": 5},
            {"_id": "group2", "count": 3}
        ]
        
        pipeline = [
            {"$match": {"active": True}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
        ]
        
        with patch.object(mongodb_connector, 'get_collection', return_value=mock_collection):
            result = mongodb_connector.aggregate("users", pipeline)
            
            assert result["success"] is True
            assert len(result["results"]) == 2
    
    def test_mongodb_indexing(self, mongodb_connector):
        """Test MongoDB index management."""
        mock_collection = Mock()
        mock_collection.create_index.return_value = "index_name"
        
        with patch.object(mongodb_connector, 'get_collection', return_value=mock_collection):
            result = mongodb_connector.create_index("users", [("email", 1)], unique=True)
            
            assert result["success"] is True
            assert mock_collection.create_index.called


class TestHealthMonitor:
    """Test cases for database health monitoring."""
    
    @pytest.fixture
    def health_monitor(self, mock_settings):
        """Create health monitor instance."""
        return HealthMonitor(mock_settings)
    
    def test_connection_health_check(self, health_monitor):
        """Test individual connection health check."""
        connection_config = {
            "id": "test-conn",
            "type": "postgresql",
            "host": "localhost"
        }
        
        with patch.object(health_monitor, '_ping_connection', return_value=True):
            health = health_monitor.check_connection_health(connection_config)
            
            assert health["healthy"] is True
            assert health["response_time"] > 0
    
    def test_multiple_connections_monitoring(self, health_monitor):
        """Test monitoring multiple connections."""
        connections = [
            {"id": "conn1", "type": "postgresql"},
            {"id": "conn2", "type": "mysql"},
            {"id": "conn3", "type": "mongodb"}
        ]
        
        with patch.object(health_monitor, '_ping_connection', return_value=True):
            results = health_monitor.check_all_connections(connections)
            
            assert len(results) == 3
            assert all(result["healthy"] for result in results)
    
    def test_health_alerting(self, health_monitor):
        """Test health monitoring alerting."""
        connection_config = {"id": "test-conn", "type": "postgresql"}
        
        with patch.object(health_monitor, '_ping_connection', return_value=False):
            with patch.object(health_monitor, 'send_alert') as mock_alert:
                health_monitor.monitor_and_alert(connection_config)
                
                assert mock_alert.called
    
    @pytest.mark.asyncio
    async def test_continuous_monitoring(self, health_monitor):
        """Test continuous health monitoring."""
        connections = [{"id": "test-conn", "type": "postgresql"}]
        
        with patch.object(health_monitor, 'check_all_connections', return_value=[{"healthy": True}]):
            # Start monitoring for a short period
            task = asyncio.create_task(health_monitor.start_continuous_monitoring(connections, interval=1))
            await asyncio.sleep(3)  # Monitor for 3 seconds
            task.cancel()
            
            assert health_monitor.monitoring_active is True


class TestBackupSystem:
    """Test cases for database backup system."""
    
    @pytest.fixture
    def backup_system(self, mock_settings):
        """Create backup system instance."""
        return BackupSystem(mock_settings)
    
    def test_postgresql_backup(self, backup_system):
        """Test PostgreSQL database backup."""
        connection_config = {
            "type": "postgresql",
            "host": "localhost",
            "database": "testdb"
        }
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            result = backup_system.create_backup(connection_config)
            
            assert result["success"] is True
            assert "backup_file" in result
            assert mock_subprocess.called
    
    def test_mysql_backup(self, backup_system):
        """Test MySQL database backup."""
        connection_config = {
            "type": "mysql",
            "host": "localhost",
            "database": "testdb"
        }
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            result = backup_system.create_backup(connection_config)
            
            assert result["success"] is True
            assert mock_subprocess.called
    
    def test_mongodb_backup(self, backup_system):
        """Test MongoDB database backup."""
        connection_config = {
            "type": "mongodb",
            "host": "localhost",
            "database": "testdb"
        }
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            result = backup_system.create_backup(connection_config)
            
            assert result["success"] is True
            assert mock_subprocess.called
    
    def test_backup_scheduling(self, backup_system):
        """Test scheduled backup functionality."""
        schedule_config = {
            "frequency": "daily",
            "time": "02:00",
            "retention_days": 30
        }
        
        with patch.object(backup_system, 'schedule_backup') as mock_schedule:
            result = backup_system.setup_scheduled_backup("test-conn", schedule_config)
            
            assert result["success"] is True
            assert mock_schedule.called
    
    def test_backup_restoration(self, backup_system):
        """Test database restoration from backup."""
        backup_file = "/path/to/backup.sql"
        connection_config = {
            "type": "postgresql",
            "host": "localhost",
            "database": "testdb"
        }
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            result = backup_system.restore_from_backup(backup_file, connection_config)
            
            assert result["success"] is True
            assert mock_subprocess.called
    
    def test_backup_compression(self, backup_system):
        """Test backup file compression."""
        backup_file = "/path/to/backup.sql"
        
        with patch('gzip.open') as mock_gzip:
            result = backup_system.compress_backup(backup_file)
            
            assert result["success"] is True
            assert result["compressed_file"].endswith('.gz')
    
    def test_backup_encryption(self, backup_system):
        """Test backup file encryption."""
        backup_file = "/path/to/backup.sql"
        encryption_key = "test-encryption-key"
        
        with patch.object(backup_system, 'encrypt_file') as mock_encrypt:
            result = backup_system.encrypt_backup(backup_file, encryption_key)
            
            assert mock_encrypt.called