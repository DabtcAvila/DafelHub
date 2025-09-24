"""
DafelHub JWT Token Management System
Enterprise-Grade Token Management with Security Headers & Refresh Logic
"""

import os
import jwt
import uuid
import redis
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.core.encryption import get_vault_manager
from dafelhub.database.models import User
from .models import UserSession, UserSecurityProfile, SecurityRole


logger = get_logger(__name__)


class TokenType(str, Enum):
    """JWT token types"""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    VERIFY = "verify"
    API = "api"


class TokenStatus(str, Enum):
    """Token status for blacklist management"""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    BLACKLISTED = "blacklisted"


@dataclass
class TokenClaims:
    """Structured token claims"""
    user_id: str
    username: str
    email: str
    role: str
    session_id: str
    ip_address: str
    user_agent_hash: str
    token_type: str
    permissions: List[str]
    two_factor_verified: bool = False
    device_trusted: bool = False
    risk_score: float = 0.0
    iat: Optional[datetime] = None
    exp: Optional[datetime] = None
    jti: Optional[str] = None


@dataclass
class TokenPair:
    """Access and refresh token pair"""
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    session_id: str


class JWTSecurityError(Exception):
    """JWT security related errors"""
    pass


class TokenBlacklistManager(LoggerMixin):
    """Redis-based token blacklist management"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or redis.from_url(
            os.getenv('REDIS_URL', 'redis://localhost:6379/1')
        )
        self.blacklist_prefix = "jwt_blacklist:"
        self.revoked_prefix = "jwt_revoked:"
        
    def blacklist_token(self, jti: str, expires_at: datetime) -> None:
        """Add token to blacklist"""
        try:
            ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
            if ttl > 0:
                self.redis_client.setex(
                    f"{self.blacklist_prefix}{jti}", 
                    ttl, 
                    TokenStatus.BLACKLISTED
                )
                self.logger.info(f"Token blacklisted: {jti}")
        except Exception as e:
            self.logger.error(f"Failed to blacklist token: {e}")
    
    def is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        try:
            return self.redis_client.exists(f"{self.blacklist_prefix}{jti}") > 0
        except Exception as e:
            self.logger.error(f"Failed to check blacklist: {e}")
            return False
    
    def revoke_user_tokens(self, user_id: str) -> None:
        """Revoke all tokens for a user"""
        try:
            pattern = f"{self.revoked_prefix}user:{user_id}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            # Set user token revocation flag
            self.redis_client.setex(
                f"{self.revoked_prefix}user:{user_id}", 
                86400,  # 24 hours
                TokenStatus.REVOKED
            )
            self.logger.info(f"All tokens revoked for user: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to revoke user tokens: {e}")
    
    def are_user_tokens_revoked(self, user_id: str, token_iat: datetime) -> bool:
        """Check if user tokens were revoked after token creation"""
        try:
            revoked_key = f"{self.revoked_prefix}user:{user_id}"
            if not self.redis_client.exists(revoked_key):
                return False
            
            # Check if token was issued before revocation
            revoked_at = self.redis_client.get(f"{revoked_key}:timestamp")
            if revoked_at:
                revoked_datetime = datetime.fromisoformat(revoked_at.decode())
                return token_iat < revoked_datetime
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to check user token revocation: {e}")
            return False


class JWTManager(LoggerMixin):
    """Enterprise JWT token management system"""
    
    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self.secret_key = os.getenv('JWT_SECRET_KEY') or settings.SECRET_KEY
        self.algorithm = 'HS256'
        
        # Token expiration times
        self.access_token_expire = timedelta(minutes=15)
        self.refresh_token_expire = timedelta(days=7)
        self.reset_token_expire = timedelta(hours=1)
        self.verify_token_expire = timedelta(hours=24)
        self.api_token_expire = timedelta(days=30)
        
        # Security managers
        self.vault = get_vault_manager()
        self.blacklist_manager = TokenBlacklistManager(redis_client)
        
        # Security headers
        self.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Cache-Control': 'no-store, no-cache, must-revalidate, private',
            'Pragma': 'no-cache'
        }
    
    def create_token_pair(
        self,
        user: User,
        session_id: uuid.UUID,
        ip_address: str,
        user_agent: str,
        permissions: List[str] = None,
        additional_claims: Dict[str, Any] = None
    ) -> TokenPair:
        """Create access and refresh token pair"""
        try:
            now = datetime.now(timezone.utc)
            permissions = permissions or []
            
            # Get user security profile
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user.id
            ).first()
            
            # Base token claims
            base_claims = TokenClaims(
                user_id=str(user.id),
                username=user.username,
                email=user.email,
                role=getattr(user, 'role', SecurityRole.VIEWER),
                session_id=str(session_id),
                ip_address=ip_address,
                user_agent_hash=self._hash_user_agent(user_agent),
                permissions=permissions,
                token_type="",  # Will be set per token
                two_factor_verified=security_profile.two_factor_enabled if security_profile else False,
                risk_score=security_profile.risk_score if security_profile else 0.0,
                iat=now
            )
            
            if additional_claims:
                for key, value in additional_claims.items():
                    if hasattr(base_claims, key):
                        setattr(base_claims, key, value)
            
            # Create access token
            access_claims = asdict(base_claims)
            access_claims.update({
                'token_type': TokenType.ACCESS,
                'exp': now + self.access_token_expire,
                'jti': str(uuid.uuid4())
            })
            access_token = jwt.encode(access_claims, self.secret_key, algorithm=self.algorithm)
            
            # Create refresh token
            refresh_claims = asdict(base_claims)
            refresh_claims.update({
                'token_type': TokenType.REFRESH,
                'exp': now + self.refresh_token_expire,
                'jti': str(uuid.uuid4())
            })
            refresh_token = jwt.encode(refresh_claims, self.secret_key, algorithm=self.algorithm)
            
            token_pair = TokenPair(
                access_token=access_token,
                refresh_token=refresh_token,
                access_expires_at=now + self.access_token_expire,
                refresh_expires_at=now + self.refresh_token_expire,
                session_id=str(session_id)
            )
            
            self.logger.info(f"Token pair created for user: {user.username}")
            return token_pair
            
        except Exception as e:
            self.logger.error(f"Failed to create token pair: {e}")
            raise JWTSecurityError(f"Token creation failed: {e}")
    
    def verify_token(
        self, 
        token: str, 
        token_type: TokenType = None,
        verify_blacklist: bool = True
    ) -> TokenClaims:
        """Verify and decode JWT token with security checks"""
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    'verify_exp': True,
                    'verify_iat': True,
                    'require_exp': True,
                    'require_iat': True
                }
            )
            
            # Validate token type
            if token_type and payload.get('token_type') != token_type:
                raise JWTSecurityError(f"Invalid token type: {payload.get('token_type')}")
            
            # Check blacklist
            jti = payload.get('jti')
            if verify_blacklist and jti and self.blacklist_manager.is_token_blacklisted(jti):
                raise JWTSecurityError("Token has been revoked")
            
            # Check user token revocation
            user_id = payload.get('user_id')
            token_iat = datetime.fromtimestamp(payload.get('iat'), timezone.utc)
            if user_id and self.blacklist_manager.are_user_tokens_revoked(user_id, token_iat):
                raise JWTSecurityError("All user tokens have been revoked")
            
            # Convert to TokenClaims
            claims = TokenClaims(
                user_id=payload['user_id'],
                username=payload['username'],
                email=payload['email'],
                role=payload['role'],
                session_id=payload['session_id'],
                ip_address=payload['ip_address'],
                user_agent_hash=payload['user_agent_hash'],
                token_type=payload['token_type'],
                permissions=payload.get('permissions', []),
                two_factor_verified=payload.get('two_factor_verified', False),
                device_trusted=payload.get('device_trusted', False),
                risk_score=payload.get('risk_score', 0.0),
                iat=token_iat,
                exp=datetime.fromtimestamp(payload['exp'], timezone.utc),
                jti=jti
            )
            
            return claims
            
        except jwt.ExpiredSignatureError:
            raise JWTSecurityError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise JWTSecurityError(f"Invalid token: {e}")
        except Exception as e:
            self.logger.error(f"Token verification failed: {e}")
            raise JWTSecurityError(f"Token verification failed: {e}")
    
    def refresh_access_token(
        self, 
        refresh_token: str,
        ip_address: str,
        user_agent: str
    ) -> str:
        """Create new access token from refresh token"""
        try:
            # Verify refresh token
            refresh_claims = self.verify_token(refresh_token, TokenType.REFRESH)
            
            # Security checks
            if refresh_claims.ip_address != ip_address:
                self.logger.warning(f"IP address mismatch during token refresh: {refresh_claims.user_id}")
                raise JWTSecurityError("Token refresh from different IP address")
            
            if refresh_claims.user_agent_hash != self._hash_user_agent(user_agent):
                self.logger.warning(f"User agent mismatch during token refresh: {refresh_claims.user_id}")
                # Allow but log warning - user agents can change slightly
            
            # Get current user data
            user = self.db.query(User).filter(User.id == uuid.UUID(refresh_claims.user_id)).first()
            if not user or not user.is_active:
                raise JWTSecurityError("User not found or inactive")
            
            # Create new access token
            now = datetime.now(timezone.utc)
            new_claims = asdict(refresh_claims)
            new_claims.update({
                'token_type': TokenType.ACCESS,
                'exp': now + self.access_token_expire,
                'iat': now,
                'jti': str(uuid.uuid4())
            })
            
            new_token = jwt.encode(new_claims, self.secret_key, algorithm=self.algorithm)
            
            # Update session activity
            session = self.db.query(UserSession).filter(
                UserSession.id == uuid.UUID(refresh_claims.session_id)
            ).first()
            if session:
                session.last_activity = now
                self.db.commit()
            
            self.logger.info(f"Access token refreshed for user: {refresh_claims.username}")
            return new_token
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            raise JWTSecurityError(f"Token refresh failed: {e}")
    
    def create_reset_token(self, user: User) -> str:
        """Create password reset token"""
        try:
            now = datetime.now(timezone.utc)
            claims = {
                'user_id': str(user.id),
                'username': user.username,
                'email': user.email,
                'token_type': TokenType.RESET,
                'iat': now,
                'exp': now + self.reset_token_expire,
                'jti': str(uuid.uuid4())
            }
            
            token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            self.logger.info(f"Reset token created for user: {user.username}")
            return token
            
        except Exception as e:
            self.logger.error(f"Reset token creation failed: {e}")
            raise JWTSecurityError(f"Reset token creation failed: {e}")
    
    def create_api_token(
        self,
        user: User,
        name: str,
        permissions: List[str],
        expires_in: timedelta = None
    ) -> str:
        """Create long-lived API token"""
        try:
            now = datetime.now(timezone.utc)
            expires_at = now + (expires_in or self.api_token_expire)
            
            claims = {
                'user_id': str(user.id),
                'username': user.username,
                'email': user.email,
                'role': getattr(user, 'role', SecurityRole.VIEWER),
                'token_type': TokenType.API,
                'api_token_name': name,
                'permissions': permissions,
                'iat': now,
                'exp': expires_at,
                'jti': str(uuid.uuid4())
            }
            
            token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            self.logger.info(f"API token created for user: {user.username}, name: {name}")
            return token
            
        except Exception as e:
            self.logger.error(f"API token creation failed: {e}")
            raise JWTSecurityError(f"API token creation failed: {e}")
    
    def revoke_token(self, token: str) -> None:
        """Revoke a specific token"""
        try:
            claims = self.verify_token(token, verify_blacklist=False)
            if claims.jti:
                self.blacklist_manager.blacklist_token(claims.jti, claims.exp)
                self.logger.info(f"Token revoked: {claims.jti}")
        except Exception as e:
            self.logger.error(f"Token revocation failed: {e}")
    
    def revoke_user_tokens(self, user_id: str) -> None:
        """Revoke all tokens for a user"""
        try:
            self.blacklist_manager.revoke_user_tokens(user_id)
            
            # Terminate all user sessions
            sessions = self.db.query(UserSession).filter(
                UserSession.user_id == uuid.UUID(user_id),
                UserSession.is_active == True
            ).all()
            
            for session in sessions:
                session.is_active = False
                session.terminated_at = datetime.now(timezone.utc)
                session.termination_reason = "TOKEN_REVOCATION"
            
            self.db.commit()
            self.logger.info(f"All tokens and sessions revoked for user: {user_id}")
            
        except Exception as e:
            self.logger.error(f"User token revocation failed: {e}")
    
    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers for token responses"""
        return self.security_headers.copy()
    
    def validate_session_context(
        self,
        claims: TokenClaims,
        current_ip: str,
        current_user_agent: str,
        strict_validation: bool = True
    ) -> bool:
        """Validate token session context"""
        try:
            # IP address validation
            if strict_validation and claims.ip_address != current_ip:
                self.logger.warning(f"IP address mismatch: expected {claims.ip_address}, got {current_ip}")
                return False
            
            # User agent validation (less strict)
            current_ua_hash = self._hash_user_agent(current_user_agent)
            if claims.user_agent_hash != current_ua_hash:
                self.logger.warning(f"User agent mismatch for user: {claims.user_id}")
                # Don't fail on user agent mismatch - browsers update frequently
            
            # Session validation
            session = self.db.query(UserSession).filter(
                UserSession.id == uuid.UUID(claims.session_id),
                UserSession.is_active == True
            ).first()
            
            if not session:
                self.logger.warning(f"Invalid or inactive session: {claims.session_id}")
                return False
            
            # Update last activity
            session.last_activity = datetime.now(timezone.utc)
            self.db.commit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Session context validation failed: {e}")
            return False
    
    def _hash_user_agent(self, user_agent: str) -> str:
        """Create consistent hash of user agent"""
        return hashlib.sha256(user_agent.encode('utf-8')).hexdigest()[:32]
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """Get information about a token without full verification"""
        try:
            # Decode without verification for inspection
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            
            return {
                'user_id': payload.get('user_id'),
                'username': payload.get('username'),
                'token_type': payload.get('token_type'),
                'issued_at': datetime.fromtimestamp(payload['iat'], timezone.utc) if payload.get('iat') else None,
                'expires_at': datetime.fromtimestamp(payload['exp'], timezone.utc) if payload.get('exp') else None,
                'jti': payload.get('jti'),
                'is_expired': datetime.now(timezone.utc) > datetime.fromtimestamp(payload['exp'], timezone.utc) if payload.get('exp') else True
            }
            
        except Exception as e:
            self.logger.error(f"Token info extraction failed: {e}")
            return {}