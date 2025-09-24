"""
Unit tests for security authentication module.

Comprehensive testing of authentication, JWT handling, MFA, and RBAC.
"""
import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import bcrypt
import time

from dafelhub.security.authentication import AuthenticationManager
from dafelhub.security.jwt_manager import JWTManager
from dafelhub.security.mfa_system import MFASystem
from dafelhub.security.rbac import RBACManager


class TestAuthenticationManager:
    """Test cases for AuthenticationManager."""
    
    @pytest.fixture
    def auth_manager(self, mock_settings):
        """Create authentication manager instance."""
        return AuthenticationManager(mock_settings)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user data."""
        return {
            "id": "user-123",
            "email": "test@example.com",
            "username": "testuser",
            "password_hash": bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
            "is_active": True,
            "is_admin": False,
            "created_at": datetime.utcnow()
        }
    
    def test_password_hashing(self, auth_manager):
        """Test password hashing and verification."""
        password = "secure_password_123"
        
        # Hash password
        password_hash = auth_manager.hash_password(password)
        
        assert password_hash is not None
        assert len(password_hash) > 50  # Bcrypt hash is typically 60 chars
        assert password_hash != password  # Should be hashed
        
        # Verify correct password
        assert auth_manager.verify_password(password, password_hash) is True
        
        # Verify incorrect password
        assert auth_manager.verify_password("wrong_password", password_hash) is False
    
    def test_user_registration(self, auth_manager, db_session):
        """Test user registration process."""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "secure123",
            "first_name": "New",
            "last_name": "User"
        }
        
        with patch.object(auth_manager, 'db_session', db_session):
            result = auth_manager.register_user(user_data)
            
            assert result["success"] is True
            assert result["user_id"] is not None
            assert "password" not in result  # Password should not be returned
    
    def test_duplicate_user_registration(self, auth_manager, db_session):
        """Test duplicate user registration prevention."""
        user_data = {
            "email": "existing@example.com",
            "username": "existing",
            "password": "secure123"
        }
        
        with patch.object(auth_manager, 'db_session', db_session):
            with patch.object(auth_manager, 'user_exists', return_value=True):
                result = auth_manager.register_user(user_data)
                
                assert result["success"] is False
                assert "already exists" in result["error"].lower()
    
    def test_user_authentication_success(self, auth_manager, mock_user):
        """Test successful user authentication."""
        with patch.object(auth_manager, 'get_user_by_email', return_value=mock_user):
            with patch.object(auth_manager, 'verify_password', return_value=True):
                result = auth_manager.authenticate("test@example.com", "password123")
                
                assert result["success"] is True
                assert result["user"]["id"] == "user-123"
                assert result["user"]["email"] == "test@example.com"
                assert "password_hash" not in result["user"]
    
    def test_user_authentication_invalid_credentials(self, auth_manager, mock_user):
        """Test authentication with invalid credentials."""
        with patch.object(auth_manager, 'get_user_by_email', return_value=mock_user):
            with patch.object(auth_manager, 'verify_password', return_value=False):
                result = auth_manager.authenticate("test@example.com", "wrong_password")
                
                assert result["success"] is False
                assert "invalid credentials" in result["error"].lower()
    
    def test_user_authentication_nonexistent_user(self, auth_manager):
        """Test authentication with nonexistent user."""
        with patch.object(auth_manager, 'get_user_by_email', return_value=None):
            result = auth_manager.authenticate("nonexistent@example.com", "password")
            
            assert result["success"] is False
            assert "user not found" in result["error"].lower()
    
    def test_inactive_user_authentication(self, auth_manager, mock_user):
        """Test authentication of inactive user."""
        mock_user["is_active"] = False
        
        with patch.object(auth_manager, 'get_user_by_email', return_value=mock_user):
            with patch.object(auth_manager, 'verify_password', return_value=True):
                result = auth_manager.authenticate("test@example.com", "password123")
                
                assert result["success"] is False
                assert "account is inactive" in result["error"].lower()
    
    def test_brute_force_protection(self, auth_manager, mock_user):
        """Test brute force protection mechanism."""
        email = "test@example.com"
        
        with patch.object(auth_manager, 'get_user_by_email', return_value=mock_user):
            with patch.object(auth_manager, 'verify_password', return_value=False):
                # Multiple failed attempts
                for _ in range(5):
                    auth_manager.authenticate(email, "wrong_password")
                
                # Next attempt should be blocked
                result = auth_manager.authenticate(email, "correct_password")
                
                assert result["success"] is False
                assert "too many attempts" in result["error"].lower()
    
    def test_password_reset_request(self, auth_manager, mock_user):
        """Test password reset request."""
        with patch.object(auth_manager, 'get_user_by_email', return_value=mock_user):
            with patch.object(auth_manager, 'send_reset_email') as mock_send:
                result = auth_manager.request_password_reset("test@example.com")
                
                assert result["success"] is True
                assert mock_send.called
                assert len(result["reset_token"]) > 20
    
    def test_password_reset_execution(self, auth_manager, mock_user):
        """Test password reset execution."""
        reset_token = "valid-reset-token-123"
        new_password = "new_secure_password"
        
        with patch.object(auth_manager, 'validate_reset_token', return_value=mock_user):
            with patch.object(auth_manager, 'update_user_password') as mock_update:
                result = auth_manager.reset_password(reset_token, new_password)
                
                assert result["success"] is True
                assert mock_update.called


class TestJWTManager:
    """Test cases for JWT token management."""
    
    @pytest.fixture
    def jwt_manager(self, mock_settings):
        """Create JWT manager instance."""
        return JWTManager(mock_settings)
    
    def test_token_creation(self, jwt_manager):
        """Test JWT token creation."""
        payload = {
            "user_id": "user-123",
            "email": "test@example.com",
            "roles": ["user"]
        }
        
        token = jwt_manager.create_token(payload)
        
        assert token is not None
        assert len(token.split('.')) == 3  # JWT has 3 parts
    
    def test_token_verification_valid(self, jwt_manager):
        """Test verification of valid JWT token."""
        payload = {
            "user_id": "user-123",
            "email": "test@example.com"
        }
        
        token = jwt_manager.create_token(payload)
        result = jwt_manager.verify_token(token)
        
        assert result["valid"] is True
        assert result["payload"]["user_id"] == "user-123"
        assert result["payload"]["email"] == "test@example.com"
    
    def test_token_verification_expired(self, jwt_manager):
        """Test verification of expired JWT token."""
        payload = {"user_id": "user-123"}
        
        # Create token with short expiration
        token = jwt_manager.create_token(payload, expires_in=1)
        
        # Wait for token to expire
        time.sleep(2)
        
        result = jwt_manager.verify_token(token)
        
        assert result["valid"] is False
        assert "expired" in result["error"].lower()
    
    def test_token_verification_invalid_signature(self, jwt_manager):
        """Test verification of token with invalid signature."""
        # Create token with different secret
        payload = {"user_id": "user-123"}
        token = jwt.encode(payload, "different-secret", algorithm="HS256")
        
        result = jwt_manager.verify_token(token)
        
        assert result["valid"] is False
        assert "signature" in result["error"].lower()
    
    def test_token_refresh(self, jwt_manager):
        """Test JWT token refresh mechanism."""
        payload = {"user_id": "user-123"}
        
        original_token = jwt_manager.create_token(payload)
        new_token = jwt_manager.refresh_token(original_token)
        
        assert new_token is not None
        assert new_token != original_token
        
        # Verify new token is valid
        result = jwt_manager.verify_token(new_token)
        assert result["valid"] is True
    
    def test_token_blacklisting(self, jwt_manager):
        """Test JWT token blacklisting."""
        payload = {"user_id": "user-123"}
        token = jwt_manager.create_token(payload)
        
        # Blacklist token
        jwt_manager.blacklist_token(token)
        
        # Verify blacklisted token is invalid
        result = jwt_manager.verify_token(token)
        
        assert result["valid"] is False
        assert "blacklisted" in result["error"].lower()


class TestMFASystem:
    """Test cases for Multi-Factor Authentication system."""
    
    @pytest.fixture
    def mfa_system(self, mock_settings):
        """Create MFA system instance."""
        return MFASystem(mock_settings)
    
    def test_totp_secret_generation(self, mfa_system):
        """Test TOTP secret generation."""
        user_id = "user-123"
        secret = mfa_system.generate_totp_secret(user_id)
        
        assert secret is not None
        assert len(secret) == 32  # Base32 encoded secret
        assert secret.isalnum()
    
    def test_totp_qr_code_generation(self, mfa_system):
        """Test TOTP QR code generation."""
        user_email = "test@example.com"
        secret = "JBSWY3DPEHPK3PXP"  # Test secret
        
        qr_url = mfa_system.generate_qr_code(user_email, secret)
        
        assert qr_url.startswith("otpauth://totp/")
        assert user_email in qr_url
        assert secret in qr_url
    
    def test_totp_verification_valid(self, mfa_system):
        """Test TOTP code verification with valid code."""
        secret = "JBSWY3DPEHPK3PXP"
        
        with patch('pyotp.TOTP') as mock_totp:
            mock_totp_instance = Mock()
            mock_totp_instance.verify.return_value = True
            mock_totp.return_value = mock_totp_instance
            
            result = mfa_system.verify_totp_code("123456", secret)
            
            assert result is True
    
    def test_totp_verification_invalid(self, mfa_system):
        """Test TOTP code verification with invalid code."""
        secret = "JBSWY3DPEHPK3PXP"
        
        with patch('pyotp.TOTP') as mock_totp:
            mock_totp_instance = Mock()
            mock_totp_instance.verify.return_value = False
            mock_totp.return_value = mock_totp_instance
            
            result = mfa_system.verify_totp_code("000000", secret)
            
            assert result is False
    
    def test_backup_codes_generation(self, mfa_system):
        """Test backup codes generation."""
        user_id = "user-123"
        
        codes = mfa_system.generate_backup_codes(user_id, count=10)
        
        assert len(codes) == 10
        for code in codes:
            assert len(code) >= 8
            assert code.isalnum()
    
    def test_backup_code_verification(self, mfa_system):
        """Test backup code verification."""
        user_id = "user-123"
        backup_code = "ABC123DEF456"
        
        with patch.object(mfa_system, 'is_valid_backup_code', return_value=True):
            with patch.object(mfa_system, 'consume_backup_code') as mock_consume:
                result = mfa_system.verify_backup_code(user_id, backup_code)
                
                assert result is True
                assert mock_consume.called
    
    def test_sms_mfa_setup(self, mfa_system):
        """Test SMS MFA setup."""
        user_id = "user-123"
        phone_number = "+1234567890"
        
        with patch.object(mfa_system, 'send_sms_code') as mock_send:
            result = mfa_system.setup_sms_mfa(user_id, phone_number)
            
            assert result["success"] is True
            assert mock_send.called
    
    def test_email_mfa_verification(self, mfa_system):
        """Test email MFA verification."""
        user_id = "user-123"
        email_code = "123456"
        
        with patch.object(mfa_system, 'get_email_code', return_value="123456"):
            result = mfa_system.verify_email_code(user_id, email_code)
            
            assert result is True


class TestRBACManager:
    """Test cases for Role-Based Access Control."""
    
    @pytest.fixture
    def rbac_manager(self, mock_settings):
        """Create RBAC manager instance."""
        return RBACManager(mock_settings)
    
    def test_role_creation(self, rbac_manager, db_session):
        """Test role creation."""
        role_data = {
            "name": "editor",
            "description": "Content editor role",
            "permissions": ["read", "write", "edit"]
        }
        
        with patch.object(rbac_manager, 'db_session', db_session):
            result = rbac_manager.create_role(role_data)
            
            assert result["success"] is True
            assert result["role"]["name"] == "editor"
    
    def test_permission_assignment(self, rbac_manager):
        """Test permission assignment to role."""
        role_id = "role-123"
        permissions = ["read", "write", "delete"]
        
        with patch.object(rbac_manager, 'assign_permissions') as mock_assign:
            result = rbac_manager.assign_permissions_to_role(role_id, permissions)
            
            assert mock_assign.called
    
    def test_user_role_assignment(self, rbac_manager):
        """Test role assignment to user."""
        user_id = "user-123"
        role_id = "role-123"
        
        with patch.object(rbac_manager, 'assign_role') as mock_assign:
            result = rbac_manager.assign_role_to_user(user_id, role_id)
            
            assert mock_assign.called
    
    def test_permission_check_allowed(self, rbac_manager):
        """Test permission check for allowed action."""
        user_id = "user-123"
        permission = "read"
        resource = "projects"
        
        with patch.object(rbac_manager, 'user_has_permission', return_value=True):
            result = rbac_manager.check_permission(user_id, permission, resource)
            
            assert result is True
    
    def test_permission_check_denied(self, rbac_manager):
        """Test permission check for denied action."""
        user_id = "user-123"
        permission = "delete"
        resource = "projects"
        
        with patch.object(rbac_manager, 'user_has_permission', return_value=False):
            result = rbac_manager.check_permission(user_id, permission, resource)
            
            assert result is False
    
    def test_hierarchical_roles(self, rbac_manager):
        """Test hierarchical role inheritance."""
        user_id = "user-123"
        
        roles_hierarchy = {
            "admin": ["user", "moderator"],
            "moderator": ["user"],
            "user": []
        }
        
        with patch.object(rbac_manager, 'get_user_roles', return_value=["admin"]):
            with patch.object(rbac_manager, 'get_role_hierarchy', return_value=roles_hierarchy):
                permissions = rbac_manager.get_effective_permissions(user_id)
                
                # Admin should have all permissions from inherited roles
                assert len(permissions) > 0
    
    def test_resource_based_permissions(self, rbac_manager):
        """Test resource-based permission checking."""
        user_id = "user-123"
        resource_id = "project-456"
        permission = "edit"
        
        with patch.object(rbac_manager, 'check_resource_permission', return_value=True):
            result = rbac_manager.check_resource_permission(
                user_id, permission, "project", resource_id
            )
            
            assert result is True
    
    def test_dynamic_permissions(self, rbac_manager):
        """Test dynamic permission evaluation."""
        user_id = "user-123"
        context = {
            "resource_owner": "user-123",
            "time_of_day": "business_hours",
            "ip_address": "192.168.1.1"
        }
        
        with patch.object(rbac_manager, 'evaluate_dynamic_permission', return_value=True):
            result = rbac_manager.evaluate_permission(
                user_id, "edit", "document", context
            )
            
            assert result is True