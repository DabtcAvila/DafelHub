"""
Unit tests for core configuration module.

Tests all configuration loading, validation, and environment handling.
"""
import pytest
import os
import tempfile
from unittest.mock import patch, mock_open
from pathlib import Path

from dafelhub.core.config import Settings, load_config, validate_config


class TestSettings:
    """Test cases for Settings class."""
    
    def test_default_settings(self):
        """Test default settings initialization."""
        settings = Settings()
        
        assert settings.app_name == "DafelHub"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.secret_key is not None
        assert len(settings.secret_key) >= 32
    
    def test_settings_from_env(self):
        """Test settings loading from environment variables."""
        with patch.dict(os.environ, {
            'DAFELHUB_DEBUG': 'true',
            'DAFELHUB_LOG_LEVEL': 'DEBUG',
            'DAFELHUB_DATABASE_URL': 'postgresql://test:test@localhost/testdb',
            'DAFELHUB_SECRET_KEY': 'test-secret-key-from-env'
        }):
            settings = Settings()
            
            assert settings.debug is True
            assert settings.log_level == "DEBUG"
            assert settings.database_url == "postgresql://test:test@localhost/testdb"
            assert settings.secret_key == "test-secret-key-from-env"
    
    def test_settings_validation(self):
        """Test settings validation."""
        # Valid settings
        settings = Settings(
            database_url="postgresql://user:pass@localhost/db",
            secret_key="valid-32-character-secret-key-12",
            jwt_secret_key="valid-jwt-secret-key"
        )
        
        assert validate_config(settings) is True
    
    def test_invalid_database_url(self):
        """Test invalid database URL handling."""
        with pytest.raises(ValueError):
            Settings(database_url="invalid-url")
    
    def test_weak_secret_key(self):
        """Test weak secret key validation."""
        with pytest.raises(ValueError):
            Settings(secret_key="weak")
    
    def test_config_file_loading(self, temp_dir):
        """Test configuration loading from file."""
        config_content = """
        [dafelhub]
        app_name = "Test Hub"
        debug = true
        log_level = "DEBUG"
        """
        
        config_file = temp_dir / "config.ini"
        config_file.write_text(config_content)
        
        settings = load_config(str(config_file))
        
        assert settings.app_name == "Test Hub"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
    
    def test_config_file_not_found(self):
        """Test handling of missing config file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.ini")
    
    def test_redis_configuration(self):
        """Test Redis configuration."""
        settings = Settings(
            redis_url="redis://localhost:6379/0"
        )
        
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 0
    
    def test_celery_configuration(self):
        """Test Celery configuration."""
        settings = Settings(
            celery_broker="redis://localhost:6379/1",
            celery_backend="redis://localhost:6379/2"
        )
        
        assert settings.celery_broker == "redis://localhost:6379/1"
        assert settings.celery_backend == "redis://localhost:6379/2"
    
    @patch.dict(os.environ, {'DAFELHUB_ENV': 'production'})
    def test_production_settings(self):
        """Test production environment settings."""
        settings = Settings()
        
        assert settings.debug is False
        assert settings.log_level == "WARNING"
        assert settings.env == "production"
    
    @patch.dict(os.environ, {'DAFELHUB_ENV': 'development'})
    def test_development_settings(self):
        """Test development environment settings."""
        settings = Settings()
        
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.env == "development"
    
    def test_encryption_settings(self):
        """Test encryption configuration."""
        settings = Settings(
            encryption_key="test-encryption-key-32-chars!!",
            use_encryption=True
        )
        
        assert settings.encryption_key == "test-encryption-key-32-chars!!"
        assert settings.use_encryption is True
    
    def test_api_settings(self):
        """Test API configuration."""
        settings = Settings(
            api_host="0.0.0.0",
            api_port=8080,
            api_workers=4,
            cors_origins=["http://localhost:3000", "https://example.com"]
        )
        
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8080
        assert settings.api_workers == 4
        assert "http://localhost:3000" in settings.cors_origins
    
    def test_monitoring_settings(self):
        """Test monitoring configuration."""
        settings = Settings(
            enable_metrics=True,
            metrics_port=9090,
            health_check_interval=30,
            log_retention_days=30
        )
        
        assert settings.enable_metrics is True
        assert settings.metrics_port == 9090
        assert settings.health_check_interval == 30
        assert settings.log_retention_days == 30
    
    def test_security_settings(self):
        """Test security configuration."""
        settings = Settings(
            jwt_expiration=3600,
            password_min_length=8,
            max_login_attempts=5,
            session_timeout=1800,
            enable_mfa=True
        )
        
        assert settings.jwt_expiration == 3600
        assert settings.password_min_length == 8
        assert settings.max_login_attempts == 5
        assert settings.session_timeout == 1800
        assert settings.enable_mfa is True
    
    def test_database_pool_settings(self):
        """Test database connection pool settings."""
        settings = Settings(
            db_pool_size=10,
            db_max_overflow=20,
            db_pool_timeout=30,
            db_pool_recycle=3600
        )
        
        assert settings.db_pool_size == 10
        assert settings.db_max_overflow == 20
        assert settings.db_pool_timeout == 30
        assert settings.db_pool_recycle == 3600


class TestConfigValidation:
    """Test configuration validation functions."""
    
    def test_validate_database_url(self):
        """Test database URL validation."""
        valid_urls = [
            "postgresql://user:pass@localhost/db",
            "mysql://user:pass@host:3306/db",
            "sqlite:///path/to/db.sqlite",
            "mongodb://user:pass@host:27017/db"
        ]
        
        for url in valid_urls:
            settings = Settings(database_url=url)
            assert validate_config(settings) is True
    
    def test_validate_redis_url(self):
        """Test Redis URL validation."""
        valid_urls = [
            "redis://localhost:6379/0",
            "redis://user:pass@host:6379/1",
            "rediss://host:6380/0"
        ]
        
        for url in valid_urls:
            settings = Settings(redis_url=url)
            assert validate_config(settings) is True
    
    def test_validate_encryption_key(self):
        """Test encryption key validation."""
        # Valid key (32 characters)
        valid_key = "12345678901234567890123456789012"
        settings = Settings(encryption_key=valid_key)
        assert validate_config(settings) is True
        
        # Invalid key (too short)
        with pytest.raises(ValueError):
            Settings(encryption_key="short")
    
    def test_validate_cors_origins(self):
        """Test CORS origins validation."""
        valid_origins = [
            "http://localhost:3000",
            "https://example.com",
            "https://subdomain.example.com:8080"
        ]
        
        settings = Settings(cors_origins=valid_origins)
        assert validate_config(settings) is True
    
    def test_validate_log_level(self):
        """Test log level validation."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in valid_levels:
            settings = Settings(log_level=level)
            assert validate_config(settings) is True
        
        with pytest.raises(ValueError):
            Settings(log_level="INVALID")
    
    def test_validate_port_numbers(self):
        """Test port number validation."""
        # Valid ports
        settings = Settings(
            api_port=8080,
            metrics_port=9090,
            redis_port=6379
        )
        assert validate_config(settings) is True
        
        # Invalid ports
        with pytest.raises(ValueError):
            Settings(api_port=99999)
        
        with pytest.raises(ValueError):
            Settings(api_port=-1)


class TestConfigEnvironments:
    """Test configuration in different environments."""
    
    @patch.dict(os.environ, {
        'DAFELHUB_ENV': 'test',
        'DAFELHUB_DATABASE_URL': 'sqlite:///test.db'
    })
    def test_test_environment(self):
        """Test configuration in test environment."""
        settings = Settings()
        
        assert settings.env == "test"
        assert settings.database_url == "sqlite:///test.db"
        assert settings.debug is True
    
    @patch.dict(os.environ, {
        'DAFELHUB_ENV': 'staging',
        'DAFELHUB_DEBUG': 'false'
    })
    def test_staging_environment(self):
        """Test configuration in staging environment."""
        settings = Settings()
        
        assert settings.env == "staging"
        assert settings.debug is False
        assert settings.log_level == "INFO"
    
    def test_config_override_precedence(self):
        """Test configuration override precedence: env vars > config file > defaults."""
        config_content = """
        [dafelhub]
        debug = true
        log_level = "DEBUG"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            # Environment variable should override config file
            with patch.dict(os.environ, {'DAFELHUB_LOG_LEVEL': 'ERROR'}):
                settings = load_config(f.name)
                
                assert settings.debug is True  # From config file
                assert settings.log_level == "ERROR"  # From env var
        
        os.unlink(f.name)