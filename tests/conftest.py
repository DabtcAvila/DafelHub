"""
PyTest configuration and shared fixtures for DafelHub testing suite.

This file contains all shared fixtures and configuration for the comprehensive
testing suite with 92%+ coverage target.
"""
import asyncio
import os
import tempfile
import pytest
import shutil
from typing import Generator, Dict, Any
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import DafelHub modules for testing
from dafelhub.database.models.base import Base
from dafelhub.core.config import Settings
from dafelhub.database.connection_manager import ConnectionManager
from dafelhub.security.authentication import AuthenticationManager
from dafelhub.api.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_settings(temp_dir: Path) -> Settings:
    """Create mock settings for testing."""
    return Settings(
        app_name="DafelHub Test",
        debug=True,
        database_url="sqlite:///test.db",
        secret_key="test-secret-key-for-testing-only",
        jwt_secret_key="test-jwt-secret-for-testing-only",
        test_mode=True,
        log_level="DEBUG",
        temp_dir=str(temp_dir)
    )


@pytest.fixture
def test_db():
    """Create a test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(test_db) -> Generator[Session, None, None]:
    """Create a database session for testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_connection_manager(mock_settings):
    """Create a mock connection manager."""
    with patch('dafelhub.database.connection_manager.ConnectionManager') as mock:
        manager = Mock(spec=ConnectionManager)
        manager.test_connection.return_value = {"status": "success", "connection": True}
        manager.get_connection.return_value = Mock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_auth_manager():
    """Create a mock authentication manager."""
    with patch('dafelhub.security.authentication.AuthenticationManager') as mock:
        auth = Mock(spec=AuthenticationManager)
        auth.authenticate.return_value = {"user_id": "test-user", "valid": True}
        auth.create_token.return_value = "test-token"
        auth.verify_token.return_value = {"valid": True, "user_id": "test-user"}
        mock.return_value = auth
        yield auth


@pytest.fixture
async def test_client(mock_settings):
    """Create a test HTTP client."""
    app = create_app(mock_settings)
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": "test-user-123",
        "email": "test@example.com",
        "username": "testuser",
        "is_active": True,
        "is_admin": False,
        "permissions": ["read", "write"]
    }


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "id": "project-123",
        "name": "Test Project",
        "description": "A test project for comprehensive testing",
        "spec_version": "1.0.0",
        "status": "active",
        "owner_id": "test-user-123"
    }


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing."""
    with patch('redis.Redis') as mock_redis:
        redis_instance = Mock()
        redis_instance.ping.return_value = True
        redis_instance.get.return_value = None
        redis_instance.set.return_value = True
        redis_instance.delete.return_value = 1
        mock_redis.return_value = redis_instance
        yield redis_instance


@pytest.fixture
def mock_celery():
    """Mock Celery for testing background tasks."""
    with patch('celery.Celery') as mock_celery:
        celery_instance = Mock()
        celery_instance.send_task.return_value = Mock(id="test-task-id")
        mock_celery.return_value = celery_instance
        yield celery_instance


@pytest.fixture
def performance_test_data():
    """Generate performance test data."""
    return {
        "concurrent_users": [10, 50, 100, 500],
        "test_duration": 60,  # seconds
        "endpoints": [
            "/api/health",
            "/api/auth/login",
            "/api/projects",
            "/api/connections"
        ],
        "expected_response_time": 500,  # ms
        "expected_throughput": 1000  # requests/second
    }


@pytest.fixture
def security_test_payloads():
    """Security testing payloads."""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users --"
        ],
        "xss_payloads": [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ],
        "command_injection": [
            "; cat /etc/passwd",
            "| whoami",
            "& dir",
            "`id`"
        ]
    }


# Test markers for different test categories
pytest.mark.unit = pytest.mark.mark("unit")
pytest.mark.integration = pytest.mark.mark("integration") 
pytest.mark.performance = pytest.mark.mark("performance")
pytest.mark.security = pytest.mark.mark("security")
pytest.mark.e2e = pytest.mark.mark("e2e")


class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_user(**kwargs):
        """Create a test user."""
        default_data = {
            "id": "test-user",
            "email": "test@example.com",
            "username": "testuser",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z"
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_project(**kwargs):
        """Create a test project."""
        default_data = {
            "id": "test-project",
            "name": "Test Project",
            "description": "Test project description",
            "owner_id": "test-user",
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z"
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_connection(**kwargs):
        """Create a test connection."""
        default_data = {
            "id": "test-connection",
            "name": "Test Connection",
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "testuser",
            "encrypted_password": "encrypted-password",
            "owner_id": "test-user"
        }
        default_data.update(kwargs)
        return default_data


@pytest.fixture
def test_factory():
    """Provide access to test data factory."""
    return TestDataFactory