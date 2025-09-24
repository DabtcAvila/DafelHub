"""
DafelHub Database Package
Enterprise database connectivity with advanced security integration

Provides:
- PostgreSQL, MySQL, MongoDB enterprise connectors
- Automatic database detection and connection factory
- Universal query builder supporting multiple databases
- Schema discovery and analysis
- Security integration with authentication and credential management
- Audit logging for all database operations
"""

from .connectors.postgresql import PostgreSQLConnector, create_postgresql_connector
from .connectors.mysql_connector import MySQLConnector, create_mysql_connector
from .connectors.mongodb_connector import MongoDBConnector, create_mongodb_connector
from .connectors.connection_factory import (
    ConnectionFactory, DatabaseType, DatabaseDetectionResult,
    connection_factory, create_connector, create_connector_from_string,
    discover_and_connect, detect_database_type
)
from .query_builder import (
    UniversalQueryBuilder, QueryType, JoinType, OrderDirection, ComparisonOperator,
    query_builder, sql_builder, mysql_builder, mongo_builder
)
from .schema_discovery import (
    UniversalSchemaDiscoverer, DatabaseSchema, TableInfo, ColumnInfo, IndexInfo,
    ConstraintInfo, ColumnType, IndexType, ConstraintType,
    schema_discoverer, discover_schema, compare_schemas
)
from .security_integration import (
    DatabaseSecurityManager, DatabaseCredential, DatabaseAccessPolicy,
    DatabasePermission, AccessLevel, SecureConnectorWrapper,
    database_security_manager, create_secure_database_connection,
    store_database_credential, check_database_permission
)

__all__ = [
    # Connectors
    'PostgreSQLConnector',
    'MySQLConnector', 
    'MongoDBConnector',
    'create_postgresql_connector',
    'create_mysql_connector',
    'create_mongodb_connector',
    
    # Connection Factory
    'ConnectionFactory',
    'DatabaseType',
    'DatabaseDetectionResult',
    'connection_factory',
    'create_connector',
    'create_connector_from_string',
    'discover_and_connect',
    'detect_database_type',
    
    # Query Builder
    'UniversalQueryBuilder',
    'QueryType',
    'JoinType',
    'OrderDirection',
    'ComparisonOperator',
    'query_builder',
    'sql_builder',
    'mysql_builder',
    'mongo_builder',
    
    # Schema Discovery
    'UniversalSchemaDiscoverer',
    'DatabaseSchema',
    'TableInfo',
    'ColumnInfo',
    'IndexInfo',
    'ConstraintInfo',
    'ColumnType',
    'IndexType',
    'ConstraintType',
    'schema_discoverer',
    'discover_schema',
    'compare_schemas',
    
    # Security Integration
    'DatabaseSecurityManager',
    'DatabaseCredential',
    'DatabaseAccessPolicy',
    'DatabasePermission',
    'AccessLevel',
    'SecureConnectorWrapper',
    'database_security_manager',
    'create_secure_database_connection',
    'store_database_credential',
    'check_database_permission'
]