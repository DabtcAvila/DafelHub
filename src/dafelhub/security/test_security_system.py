"""
DafelHub Security System - Comprehensive Tests
Tests for JWT + 2FA + RBAC integration
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dafelhub.database.models import Base, User
from .models import (
    UserSecurityProfile, SecurityRole, AuditEventType,
    SecurityAuditLog, UserSession, APIToken, TokenBlacklist, MFADevice
)
from .authentication import AuthenticationManager, SecurityContext
from .jwt_manager import JWTManager as EnterpriseJWTManager, TokenType, JWTSecurityError
from .rbac_system import RBACManager, Permission, AccessDeniedError
from .mfa_system import MFASystemManager, MFAType, MFAStatus


# Test database setup
@pytest.fixture(scope="session")
def test_db():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def sample_user(test_db):
    """Create sample user for testing"""
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$dummy_hash_for_testing",  # bcrypt hash of "testpassword"
        is_active=True,
        role=SecurityRole.EDITOR
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture  
def admin_user(test_db):
    """Create admin user for testing"""
    user = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@example.com", 
        hashed_password="$2b$12$dummy_hash_for_testing",
        is_active=True,
        role=SecurityRole.ADMIN
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


class TestAuthenticationSystem:
    """Test authentication functionality"""
    
    def test_authentication_manager_creation(self, test_db):
        """Test authentication manager can be created"""
        auth_manager = AuthenticationManager(test_db)
        assert auth_manager is not None
        assert auth_manager.db == test_db
    
    def test_jwt_manager_creation(self, test_db):
        """Test JWT manager can be created"""
        jwt_manager = EnterpriseJWTManager(test_db)
        assert jwt_manager is not None
        assert jwt_manager.db == test_db
    
    @patch('bcrypt.checkpw')
    def test_password_verification(self, mock_checkpw, test_db, sample_user):
        """Test password verification"""
        mock_checkpw.return_value = True
        
        auth_manager = AuthenticationManager(test_db)
        result = auth_manager._verify_password("testpassword", sample_user.hashed_password)
        
        assert result is True
        mock_checkpw.assert_called_once()
    
    def test_jwt_token_creation(self, test_db, sample_user):
        """Test JWT token creation"""
        jwt_manager = EnterpriseJWTManager(test_db)
        session_id = uuid.uuid4()
        
        token_pair = jwt_manager.create_token_pair(
            sample_user,
            session_id,
            "192.168.1.1",
            "Test User Agent",
            permissions=["data:read", "api:read"]
        )
        
        assert token_pair is not None
        assert token_pair.access_token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.session_id == str(session_id)
        assert isinstance(token_pair.access_expires_at, datetime)
        assert isinstance(token_pair.refresh_expires_at, datetime)
    
    def test_jwt_token_verification(self, test_db, sample_user):
        """Test JWT token verification"""
        jwt_manager = EnterpriseJWTManager(test_db)
        session_id = uuid.uuid4()
        
        # Create token
        token_pair = jwt_manager.create_token_pair(
            sample_user, session_id, "192.168.1.1", "Test User Agent"
        )
        
        # Verify token
        claims = jwt_manager.verify_token(token_pair.access_token, TokenType.ACCESS)
        
        assert claims is not None
        assert claims.user_id == str(sample_user.id)
        assert claims.username == sample_user.username
        assert claims.email == sample_user.email
        assert claims.token_type == TokenType.ACCESS
    
    def test_token_refresh(self, test_db, sample_user):
        """Test token refresh functionality"""
        jwt_manager = EnterpriseJWTManager(test_db)
        session_id = uuid.uuid4()
        
        # Create initial tokens
        token_pair = jwt_manager.create_token_pair(
            sample_user, session_id, "192.168.1.1", "Test User Agent"
        )
        
        # Create user session
        session = UserSession(
            id=session_id,
            user_id=sample_user.id,
            ip_address="192.168.1.1",
            user_agent="Test User Agent",
            session_token="dummy_hash",
            refresh_token="dummy_refresh_hash",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        test_db.add(session)
        test_db.commit()
        
        # Refresh token
        new_access_token = jwt_manager.refresh_access_token(
            token_pair.refresh_token,
            "192.168.1.1",
            "Test User Agent"
        )
        
        assert new_access_token is not None
        assert new_access_token != token_pair.access_token
        
        # Verify new token
        claims = jwt_manager.verify_token(new_access_token, TokenType.ACCESS)
        assert claims.user_id == str(sample_user.id)


class TestRBACSystem:
    """Test Role-Based Access Control"""
    
    def test_rbac_manager_creation(self, test_db):
        """Test RBAC manager creation"""
        rbac = RBACManager(test_db)
        assert rbac is not None
        assert rbac.db == test_db
    
    def test_user_permissions_retrieval(self, test_db, sample_user):
        """Test getting user permissions"""
        rbac = RBACManager(test_db)
        permissions = rbac.get_user_permissions(sample_user.id)
        
        assert isinstance(permissions, set)
        assert len(permissions) > 0
        # Editor should have read/write permissions
        assert Permission.DATA_READ in permissions
        assert Permission.DATA_WRITE in permissions
        assert Permission.API_READ in permissions
    
    def test_admin_permissions(self, test_db, admin_user):
        """Test admin user has all permissions"""
        rbac = RBACManager(test_db)
        permissions = rbac.get_user_permissions(admin_user.id)
        
        # Admin should have all permissions
        assert Permission.USER_CREATE in permissions
        assert Permission.USER_DELETE in permissions
        assert Permission.SYSTEM_CONFIG in permissions
        assert Permission.SECURITY_MANAGE_POLICIES in permissions
    
    def test_permission_check(self, test_db, sample_user):
        """Test permission checking"""
        rbac = RBACManager(test_db)
        
        # Editor should have data read permission
        has_permission = rbac.check_permission(
            sample_user.id, 
            Permission.DATA_READ
        )
        assert has_permission is True
        
        # Editor should NOT have user delete permission
        has_permission = rbac.check_permission(
            sample_user.id,
            Permission.USER_DELETE
        )
        assert has_permission is False
    
    def test_role_assignment(self, test_db, sample_user, admin_user):
        """Test role assignment"""
        rbac = RBACManager(test_db)
        
        success = rbac.assign_role(
            sample_user.id,
            SecurityRole.AUDITOR,
            admin_user.id,
            "Test role assignment"
        )
        
        assert success is True
        
        # Verify role was assigned
        user = test_db.query(User).filter(User.id == sample_user.id).first()
        assert user.role == SecurityRole.AUDITOR
        
        # Verify permissions changed
        permissions = rbac.get_user_permissions(sample_user.id)
        assert Permission.AUDIT_VIEW in permissions
        assert Permission.DATA_WRITE not in permissions  # Lost editor permissions


class TestMFASystem:
    """Test Multi-Factor Authentication"""
    
    def test_mfa_manager_creation(self, test_db):
        """Test MFA manager creation"""
        mfa_manager = MFASystemManager(test_db)
        assert mfa_manager is not None
        assert mfa_manager.db == test_db
    
    @patch('pyotp.random_base32')
    @patch('qrcode.QRCode')
    def test_totp_setup(self, mock_qr, mock_random, test_db, sample_user):
        """Test TOTP setup"""
        mock_random.return_value = "JBSWY3DPEHPK3PXP"
        mock_qr_instance = MagicMock()
        mock_qr.return_value = mock_qr_instance
        mock_img = MagicMock()
        mock_qr_instance.make_image.return_value = mock_img
        
        mfa_manager = MFASystemManager(test_db)
        
        with patch.object(mfa_manager.vault, 'encrypt_data', return_value="encrypted_secret"):
            setup_result = mfa_manager.setup_totp_for_user(sample_user.id)
        
        assert setup_result is not None
        assert setup_result.secret == "JBSWY3DPEHPK3PXP"
        assert len(setup_result.backup_codes) == 10
        assert setup_result.qr_code_base64.startswith("data:image/png;base64,")
    
    @patch('pyotp.TOTP')
    def test_totp_verification(self, mock_totp_class, test_db, sample_user):
        """Test TOTP code verification"""
        # Setup user with 2FA
        security_profile = UserSecurityProfile(
            user_id=sample_user.id,
            two_factor_enabled=True,
            two_factor_secret="encrypted_secret"
        )
        test_db.add(security_profile)
        test_db.commit()
        
        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        
        mfa_manager = MFASystemManager(test_db)
        
        with patch.object(mfa_manager.vault, 'decrypt_data', return_value="JBSWY3DPEHPK3PXP"):
            result = mfa_manager.verify_totp_code(sample_user.id, "123456")
        
        assert result is True
        mock_totp.verify.assert_called_once_with("123456", valid_window=1)
    
    def test_mfa_status(self, test_db, sample_user):
        """Test MFA status retrieval"""
        mfa_manager = MFASystemManager(test_db)
        status = mfa_manager.get_mfa_status(sample_user.id)
        
        assert isinstance(status, dict)
        assert 'enabled' in status
        assert 'status' in status
        assert 'methods' in status
        assert 'backup_codes_available' in status
        
        # User should not have MFA enabled by default
        assert status['enabled'] is False
        assert status['status'] == MFAStatus.DISABLED
    
    def test_backup_code_verification(self, test_db, sample_user):
        """Test backup code verification"""
        # Setup user with backup codes
        security_profile = UserSecurityProfile(
            user_id=sample_user.id,
            backup_codes=["encrypted_code_1", "encrypted_code_2"]
        )
        test_db.add(security_profile)
        test_db.commit()
        
        mfa_manager = MFASystemManager(test_db)
        
        with patch.object(mfa_manager.vault, 'decrypt_data', side_effect=["ABCD-1234", "EFGH-5678"]):
            result = mfa_manager.verify_backup_code(sample_user.id, "ABCD-1234")
        
        assert result is True
        
        # Verify backup code was consumed
        test_db.refresh(security_profile)
        assert len(security_profile.backup_codes) == 1


class TestIntegrationScenarios:
    """Test complete authentication flows"""
    
    @patch('bcrypt.checkpw')
    def test_complete_login_flow(self, mock_checkpw, test_db, sample_user):
        """Test complete login flow without 2FA"""
        mock_checkpw.return_value = True
        
        auth_manager = AuthenticationManager(test_db)
        
        # Simulate login
        context = auth_manager.authenticate_user(
            sample_user.username,
            "testpassword",
            "192.168.1.1",
            "Test User Agent"
        )
        
        assert context is not None
        assert context.user_id == sample_user.id
        assert context.username == sample_user.username
        assert context.email == sample_user.email
        assert context.two_factor_verified is False  # No 2FA enabled
    
    @patch('bcrypt.checkpw')
    @patch('pyotp.TOTP')
    def test_login_flow_with_2fa(self, mock_totp_class, mock_checkpw, test_db, sample_user):
        """Test complete login flow with 2FA"""
        mock_checkpw.return_value = True
        
        # Setup 2FA for user
        security_profile = UserSecurityProfile(
            user_id=sample_user.id,
            two_factor_enabled=True,
            two_factor_secret="encrypted_secret"
        )
        test_db.add(security_profile)
        test_db.commit()
        
        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        
        auth_manager = AuthenticationManager(test_db)
        
        with patch.object(auth_manager.two_factor_manager, 'decrypt_secret', return_value="secret"):
            context = auth_manager.authenticate_user(
                sample_user.username,
                "testpassword", 
                "192.168.1.1",
                "Test User Agent",
                totp_code="123456"
            )
        
        assert context is not None
        assert context.two_factor_verified is True
    
    def test_api_token_workflow(self, test_db, sample_user):
        """Test API token creation and usage"""
        jwt_manager = EnterpriseJWTManager(test_db)
        
        # Create API token
        api_token = jwt_manager.create_api_token(
            sample_user,
            "Test API Token",
            ["api:read", "data:read"],
            expires_in=timedelta(days=30)
        )
        
        assert api_token is not None
        
        # Verify API token
        claims = jwt_manager.verify_token(api_token, TokenType.API)
        assert claims.user_id == str(sample_user.id)
        assert claims.token_type == TokenType.API
        assert "api:read" in claims.permissions
        assert "data:read" in claims.permissions
    
    def test_security_context_creation(self, sample_user):
        """Test security context creation"""
        context = SecurityContext(
            user_id=sample_user.id,
            username=sample_user.username,
            email=sample_user.email,
            role=SecurityRole.EDITOR,
            session_id=uuid.uuid4(),
            ip_address="192.168.1.1",
            user_agent="Test User Agent",
            two_factor_verified=True,
            permissions=["data:read", "data:write"]
        )
        
        assert context.user_id == sample_user.id
        assert context.username == sample_user.username
        assert context.two_factor_verified is True
        assert len(context.permissions) == 2


class TestErrorHandling:
    """Test error conditions and edge cases"""
    
    def test_invalid_jwt_token(self, test_db):
        """Test handling of invalid JWT tokens"""
        jwt_manager = EnterpriseJWTManager(test_db)
        
        with pytest.raises(JWTSecurityError):
            jwt_manager.verify_token("invalid.token.here")
    
    def test_expired_jwt_token(self, test_db, sample_user):
        """Test handling of expired JWT tokens"""
        jwt_manager = EnterpriseJWTManager(test_db)
        
        # Create token with very short expiration
        jwt_manager.access_token_expire = timedelta(seconds=-1)  # Already expired
        
        token_pair = jwt_manager.create_token_pair(
            sample_user, uuid.uuid4(), "192.168.1.1", "Test User Agent"
        )
        
        with pytest.raises(JWTSecurityError, match="Token has expired"):
            jwt_manager.verify_token(token_pair.access_token)
    
    def test_nonexistent_user_login(self, test_db):
        """Test login attempt with nonexistent user"""
        auth_manager = AuthenticationManager(test_db)
        
        with pytest.raises(Exception, match="Invalid credentials"):
            auth_manager.authenticate_user(
                "nonexistent",
                "password",
                "192.168.1.1",
                "Test User Agent"
            )
    
    def test_permission_denied(self, test_db, sample_user):
        """Test permission denial"""
        rbac = RBACManager(test_db)
        
        # Editor should not have user delete permission
        has_permission = rbac.check_permission(sample_user.id, Permission.USER_DELETE)
        assert has_permission is False


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])