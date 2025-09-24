# PostgreSQL Connector - Enterprise Edition

A sophisticated, production-ready PostgreSQL connector with enterprise-grade features built for DafelHub. This connector provides advanced capabilities including connection pooling, query streaming, schema discovery, performance monitoring, and comprehensive error handling.

## 🚀 Features

### Core Features
- **Asyncpg-based Connection Pooling** - High-performance async connection management
- **Query Streaming** - Handle large datasets efficiently with streaming support
- **Schema Discovery** - Automatic metadata detection and database introspection
- **Prepared Statement Caching** - Performance optimization with intelligent caching
- **Transaction Management** - ACID compliance with proper rollback handling
- **Comprehensive Error Handling** - PostgreSQL-specific error codes and recovery
- **Performance Monitoring** - Query execution tracking and metrics collection
- **Health Checks** - Automated connection health monitoring
- **Real-time Statistics** - Live performance dashboard and alerting

### Enterprise Features
- **Connection Pool Management** - Dynamic scaling and optimization
- **Query Performance Analysis** - Execution plan analysis and optimization recommendations  
- **Alert System** - Configurable performance and health alerts
- **Metrics Export** - Prometheus-compatible metrics export
- **Background Tasks** - Automated cleanup and maintenance
- **Resource Monitoring** - Connection and query resource tracking

## 📦 Installation

The connector is included with DafelHub and requires the following dependencies:

```bash
pip install asyncpg>=0.28.0 psycopg2-binary>=2.9.0
```

## 🔧 Quick Start

### Basic Connection

```python
import asyncio
from dafelhub.core.connections import ConnectionConfig, ConnectionType
from dafelhub.database.connectors import PostgreSQLConnector

async def main():
    # Configure connection
    config = ConnectionConfig(
        id="my-postgres",
        name="My PostgreSQL Connection",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="mydb",
        username="user",
        password="password",
        pool_size=10
    )
    
    # Create and connect
    connector = PostgreSQLConnector(config)
    await connector.connect()
    
    try:
        # Execute query
        result = await connector.execute_query("SELECT * FROM users LIMIT 10")
        if result.success:
            print(f"Found {len(result.data)} users")
            for user in result.data:
                print(f"  - {user['name']}")
    
    finally:
        await connector.disconnect()

asyncio.run(main())
```

### Advanced Configuration

```python
config = ConnectionConfig(
    id="enterprise-postgres",
    name="Enterprise PostgreSQL",
    type=ConnectionType.POSTGRESQL,
    host="db.company.com",
    port=5432,
    database="production",
    username="app_user",
    password="secure_password",
    ssl=True,
    pool_size=20,
    connection_timeout=30000,
    query_timeout=120000,
    retry_attempts=3,
    retry_delay=2000,
    configuration={
        # Pool settings
        'pool_min_size': 5,
        'pool_max_size': 20,
        'max_inactive_connection_lifetime': 300.0,
        'max_queries_per_connection': 50000,
        
        # Performance settings
        'statement_cache_size': 1000,
        'statement_cache_ttl': 3600,
        'query_history_size': 10000,
        
        # Streaming settings
        'streaming_chunk_size': 1000,
        'streaming_prefetch': 100,
        
        # Monitoring settings
        'health_check_interval': 30,
        'cleanup_interval': 300,
        
        # Connection parameters
        'timezone': 'UTC',
        'connection_params': {
            'application_name': 'DafelHub-Enterprise'
        },
        
        # Server settings
        'server_settings': {
            'jit': 'off',
            'shared_preload_libraries': 'pg_stat_statements'
        }
    }
)
```

## 📊 Query Execution

### Simple Queries

```python
# SELECT query
result = await connector.execute_query(
    "SELECT id, name, email FROM users WHERE age > $1", 
    {'age': 21}
)

if result.success:
    print(f"Execution time: {result.execution_time:.3f}s")
    print(f"Rows returned: {len(result.data)}")
    for row in result.data:
        print(f"User: {row['name']} <{row['email']}>")

# INSERT query
result = await connector.execute_query(
    "INSERT INTO users (name, email, age) VALUES ($1, $2, $3)",
    {'name': 'John Doe', 'email': 'john@example.com', 'age': 30}
)

if result.success:
    print(f"Rows affected: {result.metadata['rows_affected']}")
```

### Prepared Statements

```python
# Prepare statement for repeated use
stmt_name = await connector.prepare_statement(
    "SELECT * FROM orders WHERE user_id = $1 AND status = $2",
    "get_user_orders"
)

# Execute multiple times with different parameters
for user_id in [1, 2, 3, 4, 5]:
    result = await connector.execute_prepared(stmt_name, [user_id, 'active'])
    print(f"User {user_id}: {len(result.data)} active orders")
```

### Transaction Management

```python
# Basic transaction
async with connector.transaction() as tx_conn:
    await tx_conn.execute("UPDATE accounts SET balance = balance - $1 WHERE id = $2", 100, 1)
    await tx_conn.execute("UPDATE accounts SET balance = balance + $1 WHERE id = $2", 100, 2)
    # Automatically commits on success, rolls back on error

# Transaction with custom isolation level
async with connector.transaction(isolation_level='serializable') as tx_conn:
    # Perform serializable operations
    result = await tx_conn.fetch("SELECT * FROM inventory WHERE product_id = $1", product_id)
    if result[0]['quantity'] >= requested_qty:
        await tx_conn.execute("UPDATE inventory SET quantity = quantity - $1 WHERE product_id = $2", 
                             requested_qty, product_id)
```

## 🌊 Streaming Large Datasets

```python
# Stream large result set
query = "SELECT * FROM transactions WHERE date >= $1 ORDER BY date"
parameters = [datetime(2023, 1, 1)]

total_processed = 0
async for chunk in connector.stream_query(query, parameters, chunk_size=1000):
    # Process chunk of 1000 rows
    total_processed += len(chunk)
    
    for transaction in chunk:
        # Process individual transaction
        process_transaction(transaction)
    
    print(f"Processed {total_processed} transactions so far...")

print(f"Finished processing {total_processed} transactions")
```

## 🔍 Schema Discovery

```python
# Discover complete schema information
schema_info = await connector.get_schema_info('public')

print(f"Schema: {schema_info['schema_name']}")
print(f"Tables: {len(schema_info['tables'])}")
print(f"Views: {len(schema_info['views'])}")
print(f"Functions: {len(schema_info['functions'])}")

# Examine specific table
for table in schema_info['tables']:
    if table['name'] == 'users':
        print(f"\nTable: {table['name']}")
        print(f"Type: {table['type']}")
        print(f"Size: {table['size']}")
        print(f"Comment: {table['comment']}")
        
        print("Columns:")
        for col in table['columns']:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col['default'] else ""
            print(f"  - {col['name']} {col['type']} {nullable}{default}")
        
        print("Indexes:")
        for idx in table['indexes']:
            idx_type = "PRIMARY KEY" if idx['primary'] else "UNIQUE" if idx['unique'] else "INDEX"
            print(f"  - {idx['name']} ({idx_type})")
```

## 📈 Performance Monitoring

### Basic Metrics

```python
# Get performance metrics
metrics = connector.get_performance_metrics()

print(f"Connection Status: {metrics['status']}")
print(f"Uptime: {metrics['uptime_seconds']:.0f} seconds")
print(f"Pool Usage: {metrics['pool_metrics']['current_size']}/{metrics['pool_metrics']['max_size']}")
print(f"Query Success Rate: {metrics['query_metrics']['success_rate']:.1f}%")
print(f"Average Response Time: {metrics['query_metrics']['avg_execution_time']:.3f}s")

# Query type breakdown
for query_type, stats in metrics['query_metrics']['query_type_distribution'].items():
    print(f"{query_type}: {stats['count']} queries, avg {stats['avg_time']:.3f}s")
```

### Real-time Monitoring Dashboard

```python
from dafelhub.database.connectors import get_monitoring_dashboard, start_monitoring

# Start monitoring system
await start_monitoring()

# Get monitoring instances
collector = await get_monitoring_collector()
dashboard = await get_monitoring_dashboard()

# Register connector for monitoring
collector.register_connector(connector)

# Get real-time dashboard data
dashboard_data = dashboard.get_realtime_data()
print(f"Active Connections: {dashboard_data['overview']['active_connections']}")
print(f"Critical Alerts: {dashboard_data['overview']['critical_alerts']}")

# Generate performance report
report = await dashboard.generate_report(connector.id)
print(report)
```

### Alert Configuration

```python
# Custom alert rules (configured in MonitoringCollector)
alert_rules = {
    'slow_queries': {
        'metric': 'avg_execution_time',
        'threshold': 2.0,  # 2 seconds
        'level': AlertLevel.WARNING,
        'description': 'Queries are running slowly'
    },
    'connection_saturation': {
        'metric': 'pool_utilization',
        'threshold': 85.0,  # 85% utilization
        'level': AlertLevel.CRITICAL,
        'description': 'Connection pool is nearly saturated'
    }
}
```

## 🔧 Query Analysis and Optimization

```python
# Analyze query execution plan
plan = await connector.explain_query(
    "SELECT u.name, COUNT(o.id) FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.id",
    analyze=True
)

print(f"Query Cost: {plan['Plan']['Total Cost']}")
print(f"Execution Time: {plan['Execution Time']:.3f}ms")
print(f"Node Type: {plan['Plan']['Node Type']}")

# Get performance recommendations
if plan['Plan']['Total Cost'] > 1000:
    print("⚠️  High-cost query detected - consider adding indexes")

if 'Seq Scan' in str(plan):
    print("⚠️  Sequential scan detected - consider adding indexes")
```

## 🚨 Error Handling

The connector provides comprehensive error handling with PostgreSQL-specific error codes:

```python
from dafelhub.core.connections import ConnectionError, ConnectionErrorType

try:
    result = await connector.execute_query("INVALID SQL")
except ConnectionError as e:
    if e.error_type == ConnectionErrorType.INVALID_CONFIGURATION:
        print("SQL syntax error - check your query")
    elif e.error_type == ConnectionErrorType.AUTHENTICATION_FAILED:
        print("Authentication failed - check credentials")
    elif e.error_type == ConnectionErrorType.CONNECTION_TIMEOUT:
        print("Connection timeout - check network connectivity")
    
    print(f"Error code: {e.code}")
    print(f"Original error: {e.context.get('original_error')}")
```

### Common Error Types

| Error Type | Description | Typical Cause |
|------------|-------------|---------------|
| `AUTHENTICATION_FAILED` | Login credentials rejected | Wrong username/password |
| `CONNECTION_REFUSED` | Cannot connect to server | Server down or wrong host/port |
| `CONNECTION_TIMEOUT` | Connection attempt timed out | Network issues or server overload |
| `INVALID_CONFIGURATION` | SQL syntax or semantic error | Invalid SQL query |
| `QUERY_TIMEOUT` | Query execution timed out | Long-running query or lock contention |
| `POOL_EXHAUSTED` | No available connections | High load or connection leaks |

## ⚡ Performance Best Practices

### 1. Connection Pool Optimization

```python
# Optimize pool size based on your workload
config.pool_size = min(50, concurrent_requests * 2)
config.configuration['pool_min_size'] = max(2, config.pool_size // 4)
```

### 2. Prepared Statements for Repeated Queries

```python
# Use prepared statements for queries executed frequently
stmt_name = await connector.prepare_statement(
    "SELECT * FROM products WHERE category_id = $1",
    "get_products_by_category"
)
```

### 3. Streaming for Large Result Sets

```python
# Use streaming for results > 10,000 rows
if estimated_rows > 10000:
    async for chunk in connector.stream_query(query):
        process_chunk(chunk)
else:
    result = await connector.execute_query(query)
```

### 4. Transaction Management

```python
# Keep transactions short and focused
async with connector.transaction() as tx_conn:
    # Do minimal work here
    await tx_conn.execute("UPDATE table SET field = $1 WHERE id = $2", value, id)
    # Commit happens automatically
```

## 📊 Metrics Export

### Prometheus Format

```python
from dafelhub.database.connectors.monitoring import get_monitoring_collector

collector = await get_monitoring_collector()
prometheus_metrics = await collector.export_metrics(format='prometheus')

# Output example:
# postgresql_connection_uptime{connection="my-postgres"} 3600
# postgresql_connection_success_rate{connection="my-postgres"} 99.5
# postgresql_connection_response_time{connection="my-postgres"} 0.045
```

### JSON Export

```python
json_metrics = await collector.export_metrics(format='json')
print(json_metrics)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Unit tests
pytest tests/database/test_postgresql_connector.py -v

# Integration tests (requires PostgreSQL instance)
pytest tests/database/test_postgresql_connector.py --integration -v

# Performance tests
pytest tests/database/test_postgresql_connector.py -k "performance" -v
```

## 🎯 Examples

See comprehensive examples in:
- `examples.py` - Complete usage examples
- `test_postgresql_connector.py` - Unit and integration tests

Run the examples:

```bash
cd src/dafelhub/database/connectors
python examples.py
```

## 🔐 Security Considerations

1. **SSL/TLS**: Always use SSL in production
2. **Connection String**: Never log connection strings containing passwords
3. **Prepared Statements**: Use parameterized queries to prevent SQL injection
4. **Connection Limits**: Set appropriate pool limits to prevent DoS
5. **Monitoring**: Enable monitoring to detect unusual activity

## 📝 Configuration Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pool_size` | int | 10 | Maximum connections in pool |
| `pool_min_size` | int | 2 | Minimum connections to maintain |
| `connection_timeout` | int | 30000 | Connection timeout (ms) |
| `query_timeout` | int | 60000 | Query timeout (ms) |
| `statement_cache_size` | int | 1000 | Max prepared statements to cache |
| `streaming_chunk_size` | int | 1000 | Rows per streaming chunk |
| `health_check_interval` | int | 30 | Health check frequency (seconds) |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This PostgreSQL connector is part of DafelHub and follows the same licensing terms.

## 🆘 Support

For issues and questions:
1. Check the examples and documentation
2. Review error handling patterns
3. Enable debug logging for troubleshooting
4. Report issues with detailed logs and configurations

## 🎖️ Acknowledgments

Built with:
- [asyncpg](https://github.com/MagicStack/asyncpg) - High-performance PostgreSQL adapter
- [psycopg2](https://github.com/psycopg/psycopg2) - PostgreSQL adapter for Python
- Inspired by enterprise database connectivity patterns