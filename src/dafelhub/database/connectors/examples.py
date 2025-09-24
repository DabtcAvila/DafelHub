"""
PostgreSQL Connector Usage Examples
Comprehensive examples demonstrating enterprise features
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from dafelhub.core.connections import ConnectionConfig, ConnectionType
from dafelhub.database.connectors.postgresql import PostgreSQLConnector
from dafelhub.database.connectors.monitoring import (
    get_monitoring_collector, get_monitoring_dashboard, start_monitoring
)


async def basic_connection_example():
    """Basic connection and query example"""
    
    print("=== Basic PostgreSQL Connection Example ===\n")
    
    # Create connection configuration
    config = ConnectionConfig(
        id="example-postgres-1",
        name="Example PostgreSQL Connection",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="example_db",
        username="postgres",
        password="password",
        pool_size=5,
        connection_timeout=30000,
        query_timeout=60000,
        configuration={
            'pool_min_size': 2,
            'pool_max_size': 10,
            'statement_cache_size': 500,
            'health_check_interval': 30,
            'cleanup_interval': 300
        }
    )
    
    # Create and connect
    connector = PostgreSQLConnector(config)
    
    try:
        print("Connecting to PostgreSQL...")
        await connector.connect()
        print(f"✓ Connected successfully (Status: {connector.status.value})")
        
        # Test connection
        test_result = await connector.test_connection()
        print(f"✓ Connection test: {test_result['message']}")
        print(f"  - Response time: {test_result['response_time']:.3f}s")
        if test_result.get('server_info'):
            print(f"  - Server version: {test_result['server_info']['version']}")
            print(f"  - Database: {test_result['server_info']['database']}")
        
        # Execute simple query
        result = await connector.execute_query("SELECT version(), current_database(), current_user")
        if result.success:
            print(f"✓ Query executed successfully:")
            for row in result.data:
                print(f"  - Version: {row.get('version', 'N/A')[:50]}...")
                print(f"  - Database: {row.get('current_database')}")
                print(f"  - User: {row.get('current_user')}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    
    finally:
        await connector.disconnect()
        print("✓ Disconnected")


async def advanced_querying_example():
    """Advanced querying features example"""
    
    print("\n=== Advanced Querying Features Example ===\n")
    
    config = ConnectionConfig(
        id="advanced-postgres",
        name="Advanced PostgreSQL Features",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="example_db",
        username="postgres",
        password="password",
        pool_size=3
    )
    
    connector = PostgreSQLConnector(config)
    
    try:
        await connector.connect()
        print("✓ Connected to PostgreSQL")
        
        # Create test table
        await connector.execute_query("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(200) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                age INTEGER
            )
        """)
        print("✓ Test table created/verified")
        
        # Insert sample data
        insert_queries = [
            "INSERT INTO users (name, email, age) VALUES ('Alice Johnson', 'alice@example.com', 28) ON CONFLICT (email) DO NOTHING",
            "INSERT INTO users (name, email, age) VALUES ('Bob Smith', 'bob@example.com', 34) ON CONFLICT (email) DO NOTHING",
            "INSERT INTO users (name, email, age) VALUES ('Charlie Brown', 'charlie@example.com', 25) ON CONFLICT (email) DO NOTHING",
            "INSERT INTO users (name, email, age) VALUES ('Diana Prince', 'diana@example.com', 31) ON CONFLICT (email) DO NOTHING"
        ]
        
        for query in insert_queries:
            await connector.execute_query(query)
        print("✓ Sample data inserted")
        
        # Demonstrate prepared statements
        print("\n--- Prepared Statements ---")
        stmt_name = await connector.prepare_statement(
            "SELECT * FROM users WHERE age > $1 ORDER BY age",
            "get_users_by_min_age"
        )
        print(f"✓ Prepared statement: {stmt_name}")
        
        result = await connector.execute_prepared(stmt_name, [30])
        if result.success:
            print(f"✓ Found {len(result.data)} users over 30:")
            for user in result.data:
                print(f"  - {user['name']}: {user['age']} years old")
        
        # Demonstrate transaction management
        print("\n--- Transaction Management ---")
        try:
            async with connector.transaction() as tx_conn:
                print("✓ Transaction started")
                
                # These operations will be rolled back if any fails
                await tx_conn.execute("UPDATE users SET age = age + 1 WHERE name = 'Alice Johnson'")
                await tx_conn.execute("UPDATE users SET age = age + 1 WHERE name = 'Bob Smith'")
                
                print("✓ Transaction committed successfully")
                
        except Exception as e:
            print(f"✗ Transaction failed and rolled back: {e}")
        
        # Demonstrate query explanation
        print("\n--- Query Explanation ---")
        explain_result = await connector.explain_query(
            "SELECT * FROM users WHERE age BETWEEN $1 AND $2", 
            [25, 35],
            analyze=False
        )
        
        if explain_result:
            print("✓ Query execution plan:")
            print(f"  - Node Type: {explain_result.get('Plan', {}).get('Node Type', 'Unknown')}")
            print(f"  - Total Cost: {explain_result.get('Plan', {}).get('Total Cost', 'Unknown')}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    
    finally:
        await connector.disconnect()


async def streaming_example():
    """Large dataset streaming example"""
    
    print("\n=== Query Streaming Example ===\n")
    
    config = ConnectionConfig(
        id="streaming-postgres",
        name="Streaming PostgreSQL Connection",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="example_db",
        username="postgres",
        password="password",
        pool_size=2,
        configuration={
            'streaming_chunk_size': 50,
            'streaming_prefetch': 20
        }
    )
    
    connector = PostgreSQLConnector(config)
    
    try:
        await connector.connect()
        print("✓ Connected for streaming")
        
        # Generate test data if needed
        await connector.execute_query("""
            CREATE TABLE IF NOT EXISTS large_dataset AS
            SELECT 
                generate_series(1, 1000) as id,
                'User ' || generate_series(1, 1000) as name,
                random() * 100 as score,
                NOW() - (random() * interval '365 days') as created_at
        """)
        print("✓ Large test dataset created")
        
        # Stream query results
        print("\n--- Streaming Results ---")
        total_rows = 0
        chunk_count = 0
        
        query = "SELECT id, name, score FROM large_dataset ORDER BY id"
        
        async for chunk in connector.stream_query(query, chunk_size=100):
            chunk_count += 1
            total_rows += len(chunk)
            
            print(f"✓ Chunk {chunk_count}: {len(chunk)} rows")
            
            # Process first few rows of first chunk as example
            if chunk_count == 1:
                for i, row in enumerate(chunk[:3]):
                    print(f"  - Row {i+1}: ID={row['id']}, Name='{row['name'][:20]}', Score={row['score']:.2f}")
                if len(chunk) > 3:
                    print(f"  - ... and {len(chunk) - 3} more rows in this chunk")
            
            # Stop after 5 chunks for demo
            if chunk_count >= 5:
                break
        
        print(f"✓ Streamed {total_rows} rows in {chunk_count} chunks")
        
    except Exception as e:
        print(f"✗ Streaming error: {e}")
    
    finally:
        await connector.disconnect()


async def schema_discovery_example():
    """Schema discovery and metadata example"""
    
    print("\n=== Schema Discovery Example ===\n")
    
    config = ConnectionConfig(
        id="schema-postgres",
        name="Schema Discovery PostgreSQL",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="example_db",
        username="postgres",
        password="password",
        pool_size=2
    )
    
    connector = PostgreSQLConnector(config)
    
    try:
        await connector.connect()
        print("✓ Connected for schema discovery")
        
        # Discover schema information
        schema_info = await connector.get_schema_info('public')
        
        print(f"\n--- Schema: {schema_info['schema_name']} ---")
        
        # Display tables
        if schema_info['tables']:
            print(f"\nTables ({len(schema_info['tables'])}):")
            for table in schema_info['tables'][:5]:  # Show first 5 tables
                print(f"  📊 {table['name']} ({table['type']})")
                if table.get('comment'):
                    print(f"     Comment: {table['comment']}")
                if table.get('size'):
                    print(f"     Size: {table['size']}")
                
                # Show columns
                if table['columns']:
                    print(f"     Columns ({len(table['columns'])}):")
                    for col in table['columns'][:5]:  # Show first 5 columns
                        nullable = "NULL" if col['nullable'] else "NOT NULL"
                        print(f"       - {col['name']} {col['type']} {nullable}")
                        if col.get('default'):
                            print(f"         Default: {col['default']}")
                
                # Show indexes
                if table.get('indexes'):
                    print(f"     Indexes ({len(table['indexes'])}):")
                    for idx in table['indexes']:
                        idx_type = []
                        if idx.get('primary'):
                            idx_type.append("PRIMARY KEY")
                        if idx.get('unique'):
                            idx_type.append("UNIQUE")
                        idx_desc = f" ({', '.join(idx_type)})" if idx_type else ""
                        print(f"       - {idx['name']}{idx_desc}")
                
                print()  # Empty line between tables
        
        # Display views
        if schema_info['views']:
            print(f"Views ({len(schema_info['views'])}):")
            for view in schema_info['views'][:3]:
                print(f"  👁️  {view['name']}")
            print()
        
        # Display functions
        if schema_info['functions']:
            print(f"Functions ({len(schema_info['functions'])}):")
            for func in schema_info['functions'][:3]:
                print(f"  ⚙️  {func['name']} -> {func['return_type']}")
            print()
        
    except Exception as e:
        print(f"✗ Schema discovery error: {e}")
    
    finally:
        await connector.disconnect()


async def performance_monitoring_example():
    """Performance monitoring and metrics example"""
    
    print("\n=== Performance Monitoring Example ===\n")
    
    config = ConnectionConfig(
        id="perf-postgres",
        name="Performance Monitoring PostgreSQL",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="example_db",
        username="postgres",
        password="password",
        pool_size=3,
        configuration={
            'health_check_interval': 10,
            'statement_cache_size': 100,
            'query_history_size': 1000
        }
    )
    
    connector = PostgreSQLConnector(config)
    
    try:
        await connector.connect()
        print("✓ Connected with performance monitoring")
        
        # Start monitoring
        collector = await get_monitoring_collector()
        dashboard = await get_monitoring_dashboard()
        
        # Register connector with monitoring
        collector.register_connector(connector)
        await dashboard.start()
        print("✓ Monitoring dashboard started")
        
        # Execute some queries to generate metrics
        print("\n--- Generating Query Load ---")
        
        queries = [
            ("SELECT COUNT(*) FROM information_schema.tables", "Count tables"),
            ("SELECT * FROM pg_stat_activity LIMIT 5", "Show activity"),
            ("SELECT version()", "Get version"),
            ("SELECT current_database(), current_user", "Get context"),
            ("SELECT NOW(), pg_postmaster_start_time()", "Get timestamps")
        ]
        
        for query, description in queries:
            result = await connector.execute_query(query)
            print(f"✓ {description}: {'Success' if result.success else 'Failed'}")
            
            # Small delay to separate queries
            await asyncio.sleep(0.1)
        
        # Get performance metrics
        print("\n--- Performance Metrics ---")
        metrics = connector.get_performance_metrics()
        
        print(f"Connection ID: {metrics['connection_id']}")
        print(f"Status: {metrics['status']}")
        print(f"Uptime: {metrics['uptime_seconds']:.1f} seconds")
        
        pool_info = metrics['pool_metrics']
        print(f"Pool: {pool_info['current_size']}/{pool_info['max_size']} connections")
        print(f"Available: {pool_info['available']} connections")
        
        query_info = metrics['query_metrics']
        print(f"Queries: {query_info['total_queries']} total")
        print(f"Success Rate: {query_info['success_rate']:.1f}%")
        print(f"Average Execution Time: {query_info['avg_execution_time']:.3f}s")
        
        if query_info['query_type_distribution']:
            print("Query Type Distribution:")
            for qtype, stats in query_info['query_type_distribution'].items():
                print(f"  - {qtype}: {stats['count']} queries, avg {stats['avg_time']:.3f}s")
        
        # Collect monitoring data
        await collector.collect_metrics()
        
        # Get dashboard data
        dashboard_data = dashboard.get_realtime_data()
        print(f"\n--- Dashboard Overview ---")
        overview = dashboard_data['overview']
        print(f"Total Connections: {overview['total_connections']}")
        print(f"Active Connections: {overview['active_connections']}")
        print(f"Average Success Rate: {overview['avg_success_rate']:.1f}%")
        print(f"Critical Alerts: {overview['critical_alerts']}")
        
        # Generate performance report
        report = await dashboard.generate_report(connector.id)
        print(f"\n--- Performance Report (Preview) ---")
        print(report[:500] + "..." if len(report) > 500 else report)
        
        # Stop monitoring
        await dashboard.stop()
        print("\n✓ Monitoring dashboard stopped")
        
    except Exception as e:
        print(f"✗ Performance monitoring error: {e}")
    
    finally:
        await connector.disconnect()


async def error_handling_example():
    """Error handling and recovery example"""
    
    print("\n=== Error Handling Example ===\n")
    
    config = ConnectionConfig(
        id="error-postgres",
        name="Error Handling PostgreSQL",
        type=ConnectionType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="example_db",
        username="postgres",
        password="password",
        pool_size=2,
        retry_attempts=3,
        retry_delay=1000
    )
    
    connector = PostgreSQLConnector(config)
    
    try:
        await connector.connect()
        print("✓ Connected for error handling demo")
        
        # Test different types of errors
        print("\n--- Testing Error Scenarios ---")
        
        # 1. Syntax error
        print("\n1. Syntax Error:")
        result = await connector.execute_query("INVALID SQL SYNTAX")
        if not result.success:
            print(f"✓ Caught syntax error: {result.error}")
        
        # 2. Table not found error
        print("\n2. Table Not Found Error:")
        result = await connector.execute_query("SELECT * FROM nonexistent_table")
        if not result.success:
            print(f"✓ Caught table error: {result.error}")
        
        # 3. Data type error
        print("\n3. Data Type Error:")
        result = await connector.execute_query("SELECT 'text' + 123")
        if not result.success:
            print(f"✓ Caught type error: {result.error}")
        
        # 4. Transaction rollback
        print("\n4. Transaction Rollback:")
        try:
            async with connector.transaction() as tx_conn:
                await tx_conn.execute("CREATE TEMPORARY TABLE temp_test (id INT PRIMARY KEY)")
                # This will cause a constraint violation
                await tx_conn.execute("INSERT INTO temp_test VALUES (1)")
                await tx_conn.execute("INSERT INTO temp_test VALUES (1)")  # Duplicate key
                
        except Exception as e:
            print(f"✓ Transaction rolled back due to: {str(e)[:100]}...")
        
        # 5. Test recovery with valid query
        print("\n5. Recovery Test:")
        result = await connector.execute_query("SELECT 'Recovery successful' as message")
        if result.success:
            print(f"✓ Recovery verified: {result.data[0]['message']}")
        
        # Health check after errors
        healthy = await connector.health_check()
        print(f"✓ Connection health after errors: {'Healthy' if healthy else 'Unhealthy'}")
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    
    finally:
        await connector.disconnect()


async def main():
    """Run all examples"""
    
    print("PostgreSQL Connector Enterprise Features Demo")
    print("=" * 50)
    
    examples = [
        ("Basic Connection", basic_connection_example),
        ("Advanced Querying", advanced_querying_example),
        ("Query Streaming", streaming_example),
        ("Schema Discovery", schema_discovery_example),
        ("Performance Monitoring", performance_monitoring_example),
        ("Error Handling", error_handling_example),
    ]
    
    for name, example_func in examples:
        print(f"\n\n🚀 Running {name} Example...")
        print("-" * (len(name) + 20))
        
        try:
            await example_func()
            print(f"✅ {name} example completed successfully")
        
        except Exception as e:
            print(f"❌ {name} example failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Brief pause between examples
        await asyncio.sleep(1)
    
    print("\n\n🎉 All examples completed!")
    print("\nNote: Some examples require a running PostgreSQL instance with:")
    print("- Host: localhost")
    print("- Port: 5432")
    print("- Database: example_db")
    print("- Username: postgres")
    print("- Password: password")
    print("\nYou can modify the connection configurations above to match your setup.")


if __name__ == "__main__":
    asyncio.run(main())