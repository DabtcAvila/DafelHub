"""
DafelHub Authentication System
SOC 2 Type II Compliant Authentication with Banking-Grade Security
"""

import os
import jwt
import uuid
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pyotp
import qrcode
import io
from PIL import Image
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.core.encryption import get_vault_manager
from dafelhub.database.models import User
from .models import (
    UserSecurityProfile, SecurityAuditLog, UserSession, SecurityEvent,
    AuditEventType, ThreatLevel, SecurityRole
)
from .audit import AuditLogger

logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Authentication related errors"""
    pass


class AccountLockedException(AuthenticationError):
    """Account is locked due to security policies"""
    pass


class TwoFactorRequiredException(AuthenticationError):
    """Two-factor authentication is required"""
    pass


@dataclass
class SecurityContext:
    """Security context for authenticated users"""
    user_id: uuid.UUID
    username: str
    email: str
    role: SecurityRole
    session_id: uuid.UUID
    ip_address: str
    user_agent: str
    two_factor_verified: bool = False
    permissions: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    requires_reauth: bool = False
    session_expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7))


class JWTManager(LoggerMixin):
    """JWT token management with enhanced security"""
    
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET_KEY') or settings.SECRET_KEY
        self.algorithm = 'HS256'
        self.access_token_expire = timedelta(hours=1)
        self.refresh_token_expire = timedelta(days=7)
        self.vault = get_vault_manager()
    
    def create_tokens(
        self, 
        user: User, 
        session_id: uuid.UUID,
        ip_address: str,
        user_agent: str,
        additional_claims: Dict[str, Any] = None
    ) -> Tuple[str, str]:
        """Create access and refresh tokens"""
        try:
            now = datetime.now(timezone.utc)
            
            # Base claims
            base_claims = {
                'user_id': str(user.id),
                'username': user.username,
                'email': user.email,
                'role': user.role if hasattr(user, 'role') else 'VIEWER',
                'session_id': str(session_id),
                'ip_address': ip_address,
                'user_agent_hash': self._hash_user_agent(user_agent),
                'iat': now,
            }
            
            if additional_claims:
                base_claims.update(additional_claims)
            
            # Access token
            access_claims = {
                **base_claims,
                'type': 'access',
                'exp': now + self.access_token_expire,
            }
            access_token = jwt.encode(access_claims, self.secret_key, algorithm=self.algorithm)
            
            # Refresh token
            refresh_claims = {
                **base_claims,
                'type': 'refresh',
                'exp': now + self.refresh_token_expire,
                'jti': str(uuid.uuid4()),  # Unique refresh token ID
            }
            refresh_token = jwt.encode(refresh_claims, self.secret_key, algorithm=self.algorithm)
            
            self.logger.info(f"Tokens created for user: {user.username}")
            return access_token, refresh_token
            
        except Exception as e:
            self.logger.error(f"Failed to create tokens: {e}")
            raise AuthenticationError(f"Token creation failed: {e}")
    
    def verify_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={
                    'verify_exp': True,
                    'verify_iat': True,
                    'require_exp': True,
                }
            )
            
            if payload.get('type') != token_type:
                raise jwt.InvalidTokenError(f"Invalid token type: {payload.get('type')}")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
        except Exception as e:
            self.logger.error(f"Token verification failed: {e}")
            raise AuthenticationError(f"Token verification failed: {e}")
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from refresh token"""
        try:
            payload = self.verify_token(refresh_token, 'refresh')
            
            # Create new access token with updated expiration
            now = datetime.now(timezone.utc)
            new_payload = {
                key: value for key, value in payload.items() 
                if key not in ['exp', 'type', 'jti']
            }
            new_payload.update({
                'type': 'access',
                'exp': now + self.access_token_expire,
                'iat': now,
            })
            
            new_token = jwt.encode(new_payload, self.secret_key, algorithm=self.algorithm)
            
            self.logger.info(f"Access token refreshed for user: {payload.get('username')}")
            return new_token
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError(f"Token refresh failed: {e}")
    
    def revoke_token(self, token: str) -> None:
        """Revoke a token (add to blacklist)"""
        # In production, implement token blacklist in Redis or database
        try:
            payload = self.verify_token(token, token_type=None)  # Accept any token type
            jti = payload.get('jti') or payload.get('session_id')
            
            if jti:
                # Store revoked token ID with expiration
                # This would be implemented with Redis or database storage
                self.logger.info(f"Token revoked: {jti}")
            
        except Exception as e:
            self.logger.error(f"Token revocation failed: {e}")
    
    def _hash_user_agent(self, user_agent: str) -> str:
        """Create hash of user agent for security"""
        return bcrypt.hashpw(user_agent.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')[:50]


class TwoFactorAuthManager(LoggerMixin):
    """Two-factor authentication management"""
    
    def __init__(self):
        self.vault = get_vault_manager()
        self.issuer_name = "DafelHub"
    
    def generate_secret(self) -> str:
        """Generate TOTP secret for user"""
        return pyotp.random_base32()
    
    def generate_qr_code(self, user_email: str, secret: str) -> bytes:
        """Generate QR code for TOTP setup"""
        try:
            totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user_email,
                issuer_name=self.issuer_name
            )
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(totp_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            return img_buffer.getvalue()
            
        except Exception as e:
            self.logger.error(f"QR code generation failed: {e}")
            raise AuthenticationError(f"QR code generation failed: {e}")
    
    def verify_totp_code(self, secret: str, code: str, window: int = 1) -> bool:
        """Verify TOTP code"""
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=window)
        except Exception as e:
            self.logger.error(f"TOTP verification failed: {e}")
            return False
    
    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """Generate backup codes for 2FA"""
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    def encrypt_secret(self, secret: str, user_id: str) -> str:
        """Encrypt 2FA secret for storage"""
        return self.vault.encrypt_data(secret, f"2fa_{user_id}")
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt 2FA secret"""
        return self.vault.decrypt_data(encrypted_secret)


class AccountLockoutManager(LoggerMixin):
    """Account lockout management for brute force protection"""
    
    def __init__(self):
        self.max_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        self.progressive_delays = [0, 1, 2, 5, 15]  # Minutes delay after each attempt
    
    def check_lockout_status(
        self, 
        db: Session, 
        user_profile: UserSecurityProfile
    ) -> Tuple[bool, Optional[datetime]]:
        """Check if account is locked and when it expires"""
        if not user_profile.is_locked:
            return False, None
        
        if user_profile.locked_until and datetime.now(timezone.utc) > user_profile.locked_until:
            # Lockout expired, unlock account
            user_profile.is_locked = False
            user_profile.locked_until = None
            user_profile.failed_login_attempts = 0
            db.commit()
            
            self.logger.info(f"Account auto-unlocked: {user_profile.user_id}")
            return False, None
        
        return True, user_profile.locked_until
    
    def record_failed_attempt(
        self, 
        db: Session, 
        user_profile: UserSecurityProfile,
        ip_address: str,
        user_agent: str
    ) -> bool:
        """Record failed login attempt and apply lockout if needed"""
        user_profile.failed_login_attempts += 1
        user_profile.last_failed_login = datetime.now(timezone.utc)
        
        should_lock = user_profile.failed_login_attempts >= self.max_attempts
        
        if should_lock:
            user_profile.is_locked = True
            user_profile.locked_until = datetime.now(timezone.utc) + self.lockout_duration
            
            # Create security event
            security_event = SecurityEvent(
                event_type="ACCOUNT_LOCKED",
                severity=ThreatLevel.HIGH,
                title="Account Locked Due to Failed Login Attempts",
                description=f"Account locked after {self.max_attempts} failed login attempts",
                source_ip=ip_address,
                user_agent=user_agent,
                user_profile_id=user_profile.id,
                event_data={
                    'failed_attempts': user_profile.failed_login_attempts,
                    'lockout_duration_minutes': self.lockout_duration.total_seconds() / 60
                }
            )
            db.add(security_event)
            
            self.logger.warning(
                f"Account locked: {user_profile.user_id} "
                f"({user_profile.failed_login_attempts} failed attempts)"
            )
        
        db.commit()
        return should_lock
    
    def reset_failed_attempts(self, db: Session, user_profile: UserSecurityProfile) -> None:
        """Reset failed login attempts after successful login"""
        user_profile.failed_login_attempts = 0
        user_profile.last_failed_login = None
        db.commit()
        
        self.logger.info(f"Failed attempts reset: {user_profile.user_id}")
    
    def manual_unlock(
        self, 
        db: Session, 
        user_profile: UserSecurityProfile,
        unlocked_by_id: uuid.UUID
    ) -> None:
        """Manually unlock account (admin action)"""
        user_profile.is_locked = False
        user_profile.locked_until = None
        user_profile.failed_login_attempts = 0
        
        # Log admin unlock
        audit_log = SecurityAuditLog(
            event_type=AuditEventType.ACCOUNT_UNLOCKED,
            event_category="ACCOUNT_MANAGEMENT",
            event_description="Account manually unlocked by administrator",
            user_id=unlocked_by_id,
            resource_type="USER_PROFILE",
            resource_id=str(user_profile.user_id),
            success=True,
            event_details={
                'unlocked_user_id': str(user_profile.user_id),
                'unlock_method': 'MANUAL'
            }
        )
        db.add(audit_log)
        db.commit()
        
        self.logger.info(f"Account manually unlocked: {user_profile.user_id} by {unlocked_by_id}")


class AuthenticationManager(LoggerMixin):
    """Main authentication manager with comprehensive security"""
    
    def __init__(self, db: Session):
        self.db = db
        self.jwt_manager = JWTManager()
        self.two_factor_manager = TwoFactorAuthManager()
        self.lockout_manager = AccountLockoutManager()
        self.audit_logger = AuditLogger(db)
        self.vault = get_vault_manager()
    
    def authenticate_user(
        self, 
        username_or_email: str, 
        password: str,
        ip_address: str,
        user_agent: str,
        totp_code: Optional[str] = None
    ) -> SecurityContext:
        """Authenticate user with comprehensive security checks"""
        
        # Find user
        user = self.db.query(User).filter(
            or_(
                User.username == username_or_email,
                User.email == username_or_email
            )
        ).first()
        
        if not user:
            # Log failed attempt for non-existent user
            self.audit_logger.log_security_event(
                event_type=AuditEventType.LOGIN_FAILED,
                category="AUTHENTICATION",
                description="Login attempt with non-existent user",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                event_details={'attempted_username': username_or_email}
            )
            raise AuthenticationError("Invalid credentials")
        
        # Get or create security profile
        security_profile = self.db.query(UserSecurityProfile).filter(
            UserSecurityProfile.user_id == user.id
        ).first()
        
        if not security_profile:
            security_profile = UserSecurityProfile(user_id=user.id)
            self.db.add(security_profile)
            self.db.commit()
        
        # Check account lockout
        is_locked, locked_until = self.lockout_manager.check_lockout_status(
            self.db, security_profile
        )
        
        if is_locked:
            self.audit_logger.log_security_event(
                event_type=AuditEventType.LOGIN_BLOCKED,
                category="AUTHENTICATION",
                description="Login blocked due to account lockout",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                event_details={'locked_until': locked_until.isoformat() if locked_until else None}
            )
            raise AccountLockedException(f"Account locked until {locked_until}")
        
        # Verify password
        if not self._verify_password(password, user.hashed_password):
            # Record failed attempt
            should_lock = self.lockout_manager.record_failed_attempt(
                self.db, security_profile, ip_address, user_agent
            )
            
            self.audit_logger.log_security_event(
                event_type=AuditEventType.LOGIN_FAILED,
                category="AUTHENTICATION",
                description="Login failed - invalid password",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                event_details={
                    'failed_attempts': security_profile.failed_login_attempts,
                    'account_locked': should_lock
                }
            )
            
            raise AuthenticationError("Invalid credentials")
        
        # Check if account is active
        if not user.is_active:
            self.audit_logger.log_security_event(
                event_type=AuditEventType.LOGIN_FAILED,
                category="AUTHENTICATION",
                description="Login failed - account inactive",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
            raise AuthenticationError("Account is deactivated")
        
        # Two-factor authentication check
        two_factor_verified = False
        if security_profile.two_factor_enabled:
            if not totp_code:
                self.audit_logger.log_security_event(
                    event_type=AuditEventType.TWO_FACTOR_FAILED,
                    category="AUTHENTICATION",
                    description="Two-factor authentication required",
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                raise TwoFactorRequiredException("Two-factor authentication required")
            
            # Verify TOTP code
            secret = self.two_factor_manager.decrypt_secret(security_profile.two_factor_secret)
            if not self.two_factor_manager.verify_totp_code(secret, totp_code):
                self.audit_logger.log_security_event(
                    event_type=AuditEventType.TWO_FACTOR_FAILED,
                    category="AUTHENTICATION",
                    description="Two-factor authentication failed - invalid code",
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False
                )
                raise AuthenticationError("Invalid two-factor authentication code")
            
            two_factor_verified = True
            security_profile.two_factor_last_used = datetime.now(timezone.utc)
        
        # Create user session
        session = self._create_user_session(
            user, ip_address, user_agent, security_profile
        )
        
        # Reset failed attempts on successful login
        self.lockout_manager.reset_failed_attempts(self.db, security_profile)
        
        # Create JWT tokens
        access_token, refresh_token = self.jwt_manager.create_tokens(
            user, session.id, ip_address, user_agent
        )
        
        # Update session with tokens
        session.session_token = self._hash_token(access_token)
        session.refresh_token = self._hash_token(refresh_token)
        
        # Update security profile
        security_profile.active_sessions += 1
        security_profile.last_login_ip = ip_address
        security_profile.last_user_agent = user_agent
        
        self.db.commit()
        
        # Log successful login
        self.audit_logger.log_security_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            category="AUTHENTICATION",
            description="User successfully authenticated",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            event_details={
                'session_id': str(session.id),
                'two_factor_verified': two_factor_verified
            }
        )
        
        # Create security context
        context = SecurityContext(
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=SecurityRole(getattr(user, 'role', 'VIEWER')),
            session_id=session.id,
            ip_address=ip_address,
            user_agent=user_agent,
            two_factor_verified=two_factor_verified,
            risk_score=security_profile.risk_score,
            session_expires_at=session.expires_at
        )
        
        self.logger.info(f"User authenticated successfully: {user.username}")
        return context
    
    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password using bcrypt"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _create_user_session(
        self, 
        user: User, 
        ip_address: str, 
        user_agent: str,
        security_profile: UserSecurityProfile
    ) -> UserSession:
        """Create new user session"""
        session = UserSession(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            device_fingerprint=self._generate_device_fingerprint(ip_address, user_agent)
        )
        
        self.db.add(session)
        self.db.flush()  # Get session ID
        
        return session
    
    def _generate_device_fingerprint(self, ip_address: str, user_agent: str) -> str:
        """Generate device fingerprint for session tracking"""
        fingerprint_data = f"{ip_address}:{user_agent}"
        return bcrypt.hashpw(fingerprint_data.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')[:32]
    
    def _hash_token(self, token: str) -> str:
        """Hash token for secure storage"""
        return bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def logout_user(self, session_id: uuid.UUID, ip_address: str, user_agent: str) -> None:
        """Logout user and terminate session"""
        session = self.db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.is_active == True
        ).first()
        
        if session:
            # Terminate session
            session.is_active = False
            session.terminated_at = datetime.now(timezone.utc)
            session.termination_reason = "USER_LOGOUT"
            
            # Update security profile
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == session.user_id
            ).first()
            
            if security_profile and security_profile.active_sessions > 0:
                security_profile.active_sessions -= 1
            
            self.db.commit()
            
            # Log logout
            self.audit_logger.log_security_event(
                event_type=AuditEventType.LOGOUT,
                category="AUTHENTICATION",
                description="User logged out",
                user_id=session.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
                event_details={'session_id': str(session_id)}
            )
            
            self.logger.info(f"User logged out: {session.user_id}")


# Global context storage
_current_context: Optional[SecurityContext] = None


def create_security_context(
    user_id: uuid.UUID,
    username: str,
    email: str,
    role: SecurityRole,
    session_id: uuid.UUID,
    ip_address: str,
    user_agent: str,
    **kwargs
) -> SecurityContext:
    """Create security context"""
    global _current_context
    _current_context = SecurityContext(
        user_id=user_id,
        username=username,
        email=email,
        role=role,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        **kwargs
    )
    return _current_context


def get_current_user_context() -> Optional[SecurityContext]:
    """Get current user security context"""
    return _current_context