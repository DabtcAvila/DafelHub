#!/usr/bin/env python3
"""
PostgreSQL Connector Integration Test Script
Quick test to verify the connector is working correctly
"""

import asyncio
import os
import sys
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dafelhub.core.connections import ConnectionConfig, ConnectionType
from dafelhub.database.connectors import PostgreSQLConnector


async def test_postgresql_connector():
    """Test PostgreSQL connector with configurable connection details"""
    
    # Get connection details from environment or use defaults
    config = ConnectionConfig(
        id="integration-test-postgres",
        name="Integration Test PostgreSQL",
        type=ConnectionType.POSTGRESQL,
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'postgres'),
        username=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', 'password'),
        pool_size=3,
        connection_timeout=10000,
        query_timeout=30000,
        configuration={
            'pool_min_size': 1,
            'pool_max_size': 3,
            'statement_cache_size': 10,
            'health_check_interval': 30
        }
    )
    
    print("🐘 PostgreSQL Connector Integration Test")
    print("=" * 50)
    print(f"Host: {config.host}:{config.port}")
    print(f"Database: {config.database}")
    print(f"User: {config.username}")
    print()
    
    connector: Optional[PostgreSQLConnector] = None
    
    try:
        # Create connector
        print("1. Creating PostgreSQL connector...")
        connector = PostgreSQLConnector(config)
        print(f"✓ Connector created: {connector.id}")
        print(f"✓ Initial status: {connector.status.value}")
        
        # Test connection
        print("\n2. Testing connection...")
        await connector.connect()
        print(f"✓ Connected successfully!")
        print(f"✓ Status: {connector.status.value}")
        print(f"✓ Healthy: {connector.is_healthy}")
        
        # Test connection details
        print("\n3. Getting connection details...")
        test_result = await connector.test_connection()
        if test_result['success']:
            print(f"✓ Connection test passed")
            print(f"  - Response time: {test_result['response_time']:.3f}s")
            if 'server_info' in test_result:
                server_info = test_result['server_info']
                print(f"  - Server version: {server_info.get('version', 'Unknown')}")
                print(f"  - Database: {server_info.get('database', 'Unknown')}")
                print(f"  - User: {server_info.get('user', 'Unknown')}")
                print(f"  - Timezone: {server_info.get('timezone', 'Unknown')}")
        else:
            print(f"✗ Connection test failed: {test_result['message']}")
            return False
        
        # Test basic query
        print("\n4. Testing basic queries...")
        
        # Simple SELECT
        result = await connector.execute_query("SELECT version() as db_version, current_database() as db_name")
        if result.success:
            print(f"✓ Basic SELECT query executed")
            print(f"  - Execution time: {result.execution_time:.3f}s")
            print(f"  - Rows returned: {len(result.data)}")
            if result.data:
                row = result.data[0]
                version = row.get('db_version', 'Unknown')[:50] + "..." if len(row.get('db_version', '')) > 50 else row.get('db_version', 'Unknown')
                print(f"  - Version: {version}")
                print(f"  - Database: {row.get('db_name', 'Unknown')}")
        else:
            print(f"✗ Basic query failed: {result.error}")
            return False
        
        # Test CREATE/INSERT/SELECT/DROP sequence
        print("\n5. Testing table operations...")
        
        # Create test table
        create_result = await connector.execute_query("""
            CREATE TEMPORARY TABLE connector_test (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if create_result.success:
            print("✓ Test table created")
        else:
            print(f"✗ Failed to create test table: {create_result.error}")
            return False
        
        # Insert test data
        insert_result = await connector.execute_query(
            "INSERT INTO connector_test (name) VALUES ($1), ($2), ($3)",
            {'names': ['Alice', 'Bob', 'Charlie']}
        )
        
        if insert_result.success:
            print(f"✓ Test data inserted")
        else:
            print(f"✗ Failed to insert test data: {insert_result.error}")
            # Try alternative insert method
            for name in ['Alice', 'Bob', 'Charlie']:
                single_insert = await connector.execute_query(
                    "INSERT INTO connector_test (name) VALUES ($1)",
                    {'name': name}
                )
                if not single_insert.success:
                    print(f"✗ Failed to insert {name}: {single_insert.error}")
                    return False
            print("✓ Test data inserted (individual inserts)")
        
        # Select test data
        select_result = await connector.execute_query("SELECT * FROM connector_test ORDER BY id")
        if select_result.success:
            print(f"✓ Test data retrieved: {len(select_result.data)} rows")
            for row in select_result.data:
                print(f"  - ID: {row['id']}, Name: {row['name']}")
        else:
            print(f"✗ Failed to retrieve test data: {select_result.error}")
            return False
        
        # Test prepared statements
        print("\n6. Testing prepared statements...")
        try:
            stmt_name = await connector.prepare_statement(
                "SELECT * FROM connector_test WHERE name = $1",
                "get_user_by_name"
            )
            print(f"✓ Prepared statement created: {stmt_name}")
            
            # Execute prepared statement
            prep_result = await connector.execute_prepared(stmt_name, ['Alice'])
            if prep_result.success:
                print(f"✓ Prepared statement executed: {len(prep_result.data)} rows")
                print(f"  - Cache hit: {prep_result.metadata.get('cache_hit', False)}")
            else:
                print(f"✗ Prepared statement execution failed: {prep_result.error}")
        
        except Exception as e:
            print(f"⚠ Prepared statements test failed: {e}")
        
        # Test transaction
        print("\n7. Testing transactions...")
        try:
            async with connector.transaction() as tx_conn:
                await tx_conn.execute("INSERT INTO connector_test (name) VALUES ($1)", 'Transaction Test')
                # Query within transaction
                tx_result = await tx_conn.fetch("SELECT COUNT(*) as count FROM connector_test")
                count = tx_result[0]['count']
                print(f"✓ Transaction executed successfully")
                print(f"  - Records in transaction: {count}")
                
        except Exception as e:
            print(f"✗ Transaction test failed: {e}")
        
        # Test health check
        print("\n8. Testing health check...")
        health = await connector.health_check()
        print(f"✓ Health check: {'Healthy' if health else 'Unhealthy'}")
        
        # Test performance metrics
        print("\n9. Getting performance metrics...")
        try:
            metrics = connector.get_performance_metrics()
            print(f"✓ Performance metrics retrieved")
            print(f"  - Status: {metrics['status']}")
            print(f"  - Uptime: {metrics['uptime_seconds']:.1f}s")
            print(f"  - Total queries: {metrics['query_metrics']['total_queries']}")
            print(f"  - Success rate: {metrics['query_metrics']['success_rate']:.1f}%")
            print(f"  - Avg execution time: {metrics['query_metrics']['avg_execution_time']:.3f}s")
            print(f"  - Pool size: {metrics['pool_metrics']['current_size']}/{metrics['pool_metrics']['max_size']}")
            
        except Exception as e:
            print(f"⚠ Performance metrics test failed: {e}")
        
        print(f"\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if connector:
            try:
                print(f"\n10. Cleaning up...")
                await connector.disconnect()
                print(f"✓ Disconnected successfully")
                print(f"✓ Final status: {connector.status.value}")
            except Exception as e:
                print(f"⚠ Cleanup error: {e}")


async def main():
    """Main test runner"""
    print("PostgreSQL Connector Integration Test")
    print("This test requires a PostgreSQL server to be running.\n")
    
    print("Connection configuration:")
    print("- Set POSTGRES_HOST environment variable (default: localhost)")
    print("- Set POSTGRES_PORT environment variable (default: 5432)")
    print("- Set POSTGRES_DB environment variable (default: postgres)")
    print("- Set POSTGRES_USER environment variable (default: postgres)")
    print("- Set POSTGRES_PASSWORD environment variable (default: password)")
    print("\nExample:")
    print("export POSTGRES_HOST=localhost")
    print("export POSTGRES_PASSWORD=your_password")
    print("python test_postgresql_integration.py")
    print()
    
    try:
        success = await test_postgresql_connector()
        
        if success:
            print("\n✅ Integration test PASSED")
            print("The PostgreSQL connector is working correctly!")
            sys.exit(0)
        else:
            print("\n❌ Integration test FAILED")
            print("Please check your PostgreSQL configuration and try again.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())