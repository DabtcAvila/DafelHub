"""
Connection Factory
Enterprise database connection factory with automatic database detection and connector instantiation
"""

import re
import asyncio
import urllib.parse
from typing import Dict, Any, Optional, Type, Union, List
from enum import Enum
from dataclasses import dataclass, field

from dafelhub.core.connections import (
    IDataSourceConnector, ConnectionConfig, ConnectionError, 
    ConnectionErrorType
)
from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.database.connectors.postgresql import PostgreSQLConnector, create_postgresql_connector
from dafelhub.database.connectors.mysql_connector import MySQLConnector, create_mysql_connector
from dafelhub.database.connectors.mongodb_connector import MongoDBConnector, create_mongodb_connector


logger = get_logger(__name__)


class DatabaseType(Enum):
    """Supported database types"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"
    ORACLE = "oracle"
    MSSQL = "mssql"
    UNKNOWN = "unknown"


@dataclass
class DatabaseDetectionResult:
    """Result of database type detection"""
    database_type: DatabaseType
    confidence: float
    indicators: List[str] = field(default_factory=list)
    suggested_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorRegistry:
    """Registry of available database connectors"""
    connectors: Dict[DatabaseType, Type[IDataSourceConnector]] = field(default_factory=dict)
    factory_functions: Dict[DatabaseType, callable] = field(default_factory=dict)


class ConnectionStringParser:
    """Parser for various database connection string formats"""
    
    # Connection string patterns for different databases
    PATTERNS = {
        DatabaseType.POSTGRESQL: [
            r'^postgresql://.*',
            r'^postgres://.*',
            r'^host=.*port=.*dbname=.*',
            r'.*postgresql.*'
        ],
        DatabaseType.MYSQL: [
            r'^mysql://.*',
            r'^mysql\+.*://.*',
            r'.*mysql.*',
            r'.*mariadb.*'
        ],
        DatabaseType.MONGODB: [
            r'^mongodb://.*',
            r'^mongodb\+srv://.*',
            r'.*mongodb.*'
        ],
        DatabaseType.SQLITE: [
            r'^sqlite://.*',
            r'.*\.db$',
            r'.*\.sqlite$',
            r'.*\.sqlite3$'
        ],
        DatabaseType.ORACLE: [
            r'^oracle://.*',
            r'.*oracle.*',
            r'.*xe.*',  # Oracle XE
            r'.*orcl.*'  # Oracle service names
        ],
        DatabaseType.MSSQL: [
            r'^mssql://.*',
            r'^sqlserver://.*',
            r'.*sqlserver.*',
            r'.*mssql.*'
        ]
    }
    
    @classmethod
    def parse_connection_string(cls, connection_string: str) -> DatabaseDetectionResult:
        """Parse connection string to detect database type"""
        connection_string_lower = connection_string.lower()
        
        detection_results = []
        
        for db_type, patterns in cls.PATTERNS.items():
            confidence = 0.0
            indicators = []
            
            for pattern in patterns:
                if re.match(pattern, connection_string_lower):
                    confidence += 0.8
                    indicators.append(f"Pattern match: {pattern}")
                elif re.search(pattern.replace('^', '').replace('$', ''), connection_string_lower):
                    confidence += 0.4
                    indicators.append(f"Substring match: {pattern}")
            
            if confidence > 0:
                detection_results.append(DatabaseDetectionResult(
                    database_type=db_type,
                    confidence=min(confidence, 1.0),
                    indicators=indicators
                ))
        
        if detection_results:
            # Return the highest confidence result
            detection_results.sort(key=lambda x: x.confidence, reverse=True)
            return detection_results[0]
        
        return DatabaseDetectionResult(
            database_type=DatabaseType.UNKNOWN,
            confidence=0.0,
            indicators=["No pattern matched"]
        )
    
    @classmethod
    def parse_to_config(cls, connection_string: str, database_type: DatabaseType = None) -> ConnectionConfig:
        """Parse connection string into ConnectionConfig"""
        if database_type is None:
            detection_result = cls.parse_connection_string(connection_string)
            database_type = detection_result.database_type
        
        if database_type == DatabaseType.POSTGRESQL:
            return cls._parse_postgresql_uri(connection_string)
        elif database_type == DatabaseType.MYSQL:
            return cls._parse_mysql_uri(connection_string)
        elif database_type == DatabaseType.MONGODB:
            return cls._parse_mongodb_uri(connection_string)
        else:
            # Generic URI parsing
            return cls._parse_generic_uri(connection_string, database_type)
    
    @classmethod
    def _parse_postgresql_uri(cls, uri: str) -> ConnectionConfig:
        """Parse PostgreSQL connection URI"""
        parsed = urllib.parse.urlparse(uri)
        
        return ConnectionConfig(
            id=f"postgresql_conn_{hash(uri) % 1000000}",
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/') or 'postgres',
            username=parsed.username or 'postgres',
            password=parsed.password or '',
            ssl=parsed.scheme == 'postgresql+ssl',
            connection_timeout=10000,
            query_timeout=30000,
            pool_size=10,
            configuration={
                'connection_string': uri,
                'database_type': 'postgresql',
                'ssl_mode': 'prefer' if not parsed.query else 
                          dict(urllib.parse.parse_qsl(parsed.query)).get('sslmode', 'prefer')
            }
        )
    
    @classmethod
    def _parse_mysql_uri(cls, uri: str) -> ConnectionConfig:
        """Parse MySQL connection URI"""
        parsed = urllib.parse.urlparse(uri)
        
        return ConnectionConfig(
            id=f"mysql_conn_{hash(uri) % 1000000}",
            host=parsed.hostname or 'localhost',
            port=parsed.port or 3306,
            database=parsed.path.lstrip('/') or 'mysql',
            username=parsed.username or 'root',
            password=parsed.password or '',
            ssl=parsed.scheme.endswith('+ssl'),
            connection_timeout=10000,
            query_timeout=30000,
            pool_size=10,
            configuration={
                'connection_string': uri,
                'database_type': 'mysql',
                'charset': 'utf8mb4'
            }
        )
    
    @classmethod
    def _parse_mongodb_uri(cls, uri: str) -> ConnectionConfig:
        """Parse MongoDB connection URI"""
        parsed = urllib.parse.urlparse(uri)
        
        # MongoDB can have multiple hosts
        hosts = parsed.netloc.split('@')[-1] if '@' in parsed.netloc else parsed.netloc
        primary_host = hosts.split(',')[0].split(':')
        
        return ConnectionConfig(
            id=f"mongodb_conn_{hash(uri) % 1000000}",
            host=primary_host[0] if primary_host else 'localhost',
            port=int(primary_host[1]) if len(primary_host) > 1 and primary_host[1] else 27017,
            database=parsed.path.lstrip('/') or 'admin',
            username=parsed.username or '',
            password=parsed.password or '',
            ssl=parsed.scheme == 'mongodb+srv',
            connection_timeout=10000,
            query_timeout=30000,
            pool_size=10,
            configuration={
                'connection_string': uri,
                'database_type': 'mongodb',
                'hosts': hosts.split(',') if ',' in hosts else [hosts]
            }
        )
    
    @classmethod
    def _parse_generic_uri(cls, uri: str, database_type: DatabaseType) -> ConnectionConfig:
        """Parse generic database URI"""
        parsed = urllib.parse.urlparse(uri)
        
        default_ports = {
            DatabaseType.SQLITE: None,
            DatabaseType.ORACLE: 1521,
            DatabaseType.MSSQL: 1433,
            DatabaseType.UNKNOWN: 5432
        }
        
        return ConnectionConfig(
            id=f"{database_type.value}_conn_{hash(uri) % 1000000}",
            host=parsed.hostname or 'localhost',
            port=parsed.port or default_ports.get(database_type, 5432),
            database=parsed.path.lstrip('/') or database_type.value,
            username=parsed.username or '',
            password=parsed.password or '',
            ssl=parsed.scheme.endswith('+ssl') or parsed.scheme.endswith('s'),
            connection_timeout=10000,
            query_timeout=30000,
            pool_size=10,
            configuration={
                'connection_string': uri,
                'database_type': database_type.value
            }
        )


class DatabasePortScanner:
    """Scanner to detect database services on common ports"""
    
    COMMON_PORTS = {
        5432: DatabaseType.POSTGRESQL,
        3306: DatabaseType.MYSQL,
        27017: DatabaseType.MONGODB,
        1521: DatabaseType.ORACLE,
        1433: DatabaseType.MSSQL,
        3307: DatabaseType.MYSQL,  # Alternative MySQL port
        5433: DatabaseType.POSTGRESQL,  # Alternative PostgreSQL port
        27018: DatabaseType.MONGODB,  # Alternative MongoDB port
        27019: DatabaseType.MONGODB,  # Alternative MongoDB port
    }
    
    @classmethod
    async def scan_host(cls, host: str, timeout: float = 2.0) -> List[DatabaseDetectionResult]:
        """Scan host for database services"""
        results = []
        
        tasks = []
        for port, db_type in cls.COMMON_PORTS.items():
            tasks.append(cls._check_port(host, port, db_type, timeout))
        
        port_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in port_results:
            if isinstance(result, DatabaseDetectionResult) and result.confidence > 0:
                results.append(result)
        
        return results
    
    @classmethod
    async def _check_port(cls, host: str, port: int, db_type: DatabaseType, 
                         timeout: float) -> DatabaseDetectionResult:
        """Check if a port is open and likely running a database service"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            
            writer.close()
            await writer.wait_closed()
            
            return DatabaseDetectionResult(
                database_type=db_type,
                confidence=0.7,  # Port open indicates likely database
                indicators=[f"Port {port} open on {host}"],
                suggested_config={
                    'host': host,
                    'port': port,
                    'database_type': db_type.value
                }
            )
        
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return DatabaseDetectionResult(
                database_type=DatabaseType.UNKNOWN,
                confidence=0.0,
                indicators=[f"Port {port} closed or filtered on {host}"]
            )


class ConnectionFactory(LoggerMixin):
    """
    Enterprise database connection factory with advanced features:
    - Automatic database type detection
    - Connection string parsing
    - Port scanning for database discovery
    - Connector registry management
    - Connection configuration optimization
    - Credential management integration
    - Health monitoring integration
    """
    
    def __init__(self):
        self._registry = ConnectorRegistry()
        self._connection_cache: Dict[str, IDataSourceConnector] = {}
        self._register_default_connectors()
        
        self.logger.info("Connection factory initialized")
    
    def _register_default_connectors(self) -> None:
        """Register default database connectors"""
        self._registry.connectors[DatabaseType.POSTGRESQL] = PostgreSQLConnector
        self._registry.factory_functions[DatabaseType.POSTGRESQL] = create_postgresql_connector
        
        self._registry.connectors[DatabaseType.MYSQL] = MySQLConnector
        self._registry.factory_functions[DatabaseType.MYSQL] = create_mysql_connector
        
        self._registry.connectors[DatabaseType.MONGODB] = MongoDBConnector
        self._registry.factory_functions[DatabaseType.MONGODB] = create_mongodb_connector
    
    def register_connector(self, database_type: DatabaseType, 
                          connector_class: Type[IDataSourceConnector],
                          factory_function: callable = None) -> None:
        """Register a custom database connector"""
        self._registry.connectors[database_type] = connector_class
        if factory_function:
            self._registry.factory_functions[database_type] = factory_function
        
        self.logger.info(f"Registered connector for {database_type.value}")
    
    def get_supported_databases(self) -> List[DatabaseType]:
        """Get list of supported database types"""
        return list(self._registry.connectors.keys())
    
    def detect_database_type(self, connection_string: str = None, 
                           host: str = None, port: int = None) -> DatabaseDetectionResult:
        """Detect database type from connection string or host/port"""
        if connection_string:
            return ConnectionStringParser.parse_connection_string(connection_string)
        
        elif host and port:
            # Check against known port mappings
            if port in DatabasePortScanner.COMMON_PORTS:
                return DatabaseDetectionResult(
                    database_type=DatabasePortScanner.COMMON_PORTS[port],
                    confidence=0.8,
                    indicators=[f"Port {port} matches known database port"],
                    suggested_config={'host': host, 'port': port}
                )
        
        return DatabaseDetectionResult(
            database_type=DatabaseType.UNKNOWN,
            confidence=0.0,
            indicators=["Insufficient information for detection"]
        )
    
    async def scan_for_databases(self, host: str, timeout: float = 2.0) -> List[DatabaseDetectionResult]:
        """Scan host for available database services"""
        self.logger.info(f"Scanning {host} for database services")
        return await DatabasePortScanner.scan_host(host, timeout)
    
    def create_connector(self, config: ConnectionConfig, 
                        database_type: DatabaseType = None) -> IDataSourceConnector:
        """Create database connector instance"""
        # Auto-detect database type if not provided
        if database_type is None:
            if 'database_type' in config.configuration:
                db_type_str = config.configuration['database_type']
                database_type = DatabaseType(db_type_str)
            else:
                # Try to detect from configuration
                detection_result = self.detect_database_type(
                    host=config.host,
                    port=config.port
                )
                database_type = detection_result.database_type
        
        # Check if connector is registered
        if database_type not in self._registry.connectors:
            raise ConnectionError(
                f"No connector registered for database type: {database_type.value}",
                ConnectionErrorType.INVALID_CONFIGURATION
            )
        
        # Create connector instance
        if database_type in self._registry.factory_functions:
            connector = self._registry.factory_functions[database_type](config)
        else:
            connector_class = self._registry.connectors[database_type]
            connector = connector_class(config)
        
        self.logger.info(f"Created {database_type.value} connector: {config.id}")
        return connector
    
    def create_connector_from_string(self, connection_string: str, 
                                   connector_id: str = None) -> IDataSourceConnector:
        """Create connector from connection string"""
        # Detect database type
        detection_result = ConnectionStringParser.parse_connection_string(connection_string)
        
        if detection_result.database_type == DatabaseType.UNKNOWN:
            raise ConnectionError(
                f"Could not detect database type from connection string: {connection_string}",
                ConnectionErrorType.INVALID_CONFIGURATION
            )
        
        # Parse to configuration
        config = ConnectionStringParser.parse_to_config(
            connection_string, 
            detection_result.database_type
        )
        
        if connector_id:
            config.id = connector_id
        
        # Create connector
        return self.create_connector(config, detection_result.database_type)
    
    async def create_connector_with_discovery(self, host: str, 
                                            database: str = None,
                                            username: str = None,
                                            password: str = None,
                                            connector_id: str = None) -> IDataSourceConnector:
        """Create connector with automatic database discovery"""
        # Scan for database services
        detection_results = await self.scan_for_databases(host)
        
        if not detection_results:
            raise ConnectionError(
                f"No database services found on host: {host}",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        # Use the highest confidence detection result
        detection_results.sort(key=lambda x: x.confidence, reverse=True)
        best_result = detection_results[0]
        
        # Create configuration
        config = ConnectionConfig(
            id=connector_id or f"discovered_{best_result.database_type.value}_{hash(host) % 1000000}",
            host=host,
            port=best_result.suggested_config.get('port', 5432),
            database=database or best_result.database_type.value,
            username=username or '',
            password=password or '',
            ssl=False,
            connection_timeout=10000,
            query_timeout=30000,
            pool_size=10,
            configuration={
                'database_type': best_result.database_type.value,
                'detected': True,
                'confidence': best_result.confidence,
                'indicators': best_result.indicators
            }
        )
        
        return self.create_connector(config, best_result.database_type)
    
    def get_cached_connector(self, connector_id: str) -> Optional[IDataSourceConnector]:
        """Get cached connector instance"""
        return self._connection_cache.get(connector_id)
    
    def cache_connector(self, connector: IDataSourceConnector) -> None:
        """Cache connector instance"""
        self._connection_cache[connector.id] = connector
        self.logger.debug(f"Cached connector: {connector.id}")
    
    def remove_cached_connector(self, connector_id: str) -> None:
        """Remove connector from cache"""
        if connector_id in self._connection_cache:
            del self._connection_cache[connector_id]
            self.logger.debug(f"Removed cached connector: {connector_id}")
    
    async def test_connection_string(self, connection_string: str) -> Dict[str, Any]:
        """Test connection string by attempting to connect"""
        try:
            # Create temporary connector
            connector = self.create_connector_from_string(connection_string)
            
            # Test connection
            await connector.connect()
            test_result = await connector.test_connection()
            await connector.disconnect()
            
            return {
                'success': True,
                'database_type': connector.__class__.__name__.replace('Connector', '').lower(),
                'connection_test': test_result,
                'message': 'Connection test successful'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Connection test failed'
            }
    
    def optimize_configuration(self, config: ConnectionConfig, 
                             database_type: DatabaseType) -> ConnectionConfig:
        """Optimize connection configuration based on database type"""
        optimized_config = config
        
        # Database-specific optimizations
        if database_type == DatabaseType.POSTGRESQL:
            # PostgreSQL optimizations
            optimized_config.configuration.update({
                'statement_cache_size': 1000,
                'statement_cache_ttl': 3600,
                'pool_min_size': 2,
                'pool_max_size': min(config.pool_size, 20),
                'server_settings': {
                    'statement_timeout': '30s',
                    'idle_in_transaction_session_timeout': '60s'
                }
            })
        
        elif database_type == DatabaseType.MYSQL:
            # MySQL optimizations
            optimized_config.configuration.update({
                'charset': 'utf8mb4',
                'sql_mode': 'TRADITIONAL',
                'pool_min_size': 2,
                'pool_max_size': min(config.pool_size, 15),
                'max_idle_time_ms': 300000
            })
        
        elif database_type == DatabaseType.MONGODB:
            # MongoDB optimizations
            optimized_config.configuration.update({
                'retry_writes': True,
                'retry_reads': True,
                'compressors': ['zstd', 'zlib'],
                'server_selection_timeout_ms': 30000,
                'heartbeat_frequency_ms': 10000
            })
        
        self.logger.debug(f"Optimized configuration for {database_type.value}")
        return optimized_config
    
    def get_connection_summary(self) -> Dict[str, Any]:
        """Get summary of factory state and cached connections"""
        return {
            'supported_databases': [db.value for db in self.get_supported_databases()],
            'cached_connections': len(self._connection_cache),
            'cached_connection_ids': list(self._connection_cache.keys()),
            'registered_connectors': {
                db_type.value: connector_class.__name__ 
                for db_type, connector_class in self._registry.connectors.items()
            }
        }


# Global factory instance
connection_factory = ConnectionFactory()


# Convenience functions
def create_connector(config: ConnectionConfig, 
                    database_type: DatabaseType = None) -> IDataSourceConnector:
    """Create database connector using global factory"""
    return connection_factory.create_connector(config, database_type)


def create_connector_from_string(connection_string: str, 
                               connector_id: str = None) -> IDataSourceConnector:
    """Create connector from connection string using global factory"""
    return connection_factory.create_connector_from_string(connection_string, connector_id)


async def discover_and_connect(host: str, database: str = None,
                             username: str = None, password: str = None,
                             connector_id: str = None) -> IDataSourceConnector:
    """Discover database and create connector using global factory"""
    return await connection_factory.create_connector_with_discovery(
        host, database, username, password, connector_id
    )


def detect_database_type(connection_string: str = None, 
                        host: str = None, port: int = None) -> DatabaseDetectionResult:
    """Detect database type using global factory"""
    return connection_factory.detect_database_type(connection_string, host, port)