"""
DafelHub Enterprise User Models
User authentication and authorization models
Integrated with SecurityAgent authentication system

Features:
- Enterprise user management
- Role-based access control (RBAC)
- Permission system integration
- Security audit trail
- Password management with vault integration
- Multi-factor authentication support
- Session management
- User profile and preferences

TODO: [DB-016] Implement user authentication models - @DatabaseAgent - 2024-09-24
TODO: [DB-017] Add role-based access control - @DatabaseAgent - 2024-09-24
TODO: [DB-018] Integrate with SecurityAgent auth - @DatabaseAgent - 2024-09-24
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Set, Union
from enum import Enum
import json
import secrets

from sqlalchemy import (
    Column, String, Boolean, Text, Integer, DateTime,
    ForeignKey, Table, UniqueConstraint, Index,
    func, and_, or_
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import (
    EnterpriseBaseModel, EnterpriseRepository,
    RecordStatus, AuditAction, ModelValidationError
)
from dafelhub.core.logging import get_logger
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.security.audit_trail import get_persistent_audit_trail


logger = get_logger(__name__)


class UserStatus(Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    PENDING_VERIFICATION = "pending_verification"
    EXPIRED = "expired"


class UserRole(Enum):
    """User roles in the system"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    USER = "user"
    READONLY = "readonly"
    GUEST = "guest"


class PermissionType(Enum):
    """Permission types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    SUPER = "super"


class AuthenticationMethod(Enum):
    """Authentication methods"""
    PASSWORD = "password"
    MFA_TOTP = "mfa_totp"
    MFA_SMS = "mfa_sms"
    MFA_EMAIL = "mfa_email"
    API_KEY = "api_key"
    OAUTH = "oauth"
    LDAP = "ldap"
    SSO = "sso"


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    EnterpriseBaseModel.metadata,
    Column('id', UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()),
    Column('user_id', UUID(as_uuid=False), ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('role_id', UUID(as_uuid=False), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
    Column('assigned_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column('assigned_by', String(255), nullable=True),
    Column('expires_at', DateTime(timezone=True), nullable=True),
    Column('is_active', Boolean, nullable=False, default=True),
    UniqueConstraint('user_id', 'role_id', name='uq_user_roles_user_role')
)


# Association table for many-to-many relationship between roles and permissions
role_permissions = Table(
    'role_permissions',
    EnterpriseBaseModel.metadata,
    Column('id', UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()),
    Column('role_id', UUID(as_uuid=False), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
    Column('permission_id', UUID(as_uuid=False), ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False),
    Column('granted_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column('granted_by', String(255), nullable=True),
    UniqueConstraint('role_id', 'permission_id', name='uq_role_permissions_role_permission')
)


class Permission(EnterpriseBaseModel):
    """Permission model for fine-grained access control"""
    
    __tablename__ = 'permissions'
    __audit_enabled__ = True
    __searchable_fields__ = ['name', 'description', 'resource']
    
    # Permission details
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    permission_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PermissionType.READ.value
    )
    
    resource: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Permission configuration
    conditions: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions"
    )
    
    @validates('permission_type')
    def validate_permission_type(self, key, value):
        """Validate permission type"""
        if value not in [pt.value for pt in PermissionType]:
            raise ValueError(f"Invalid permission type: {value}")
        return value
    
    def __repr__(self) -> str:
        return f"<Permission(name='{self.name}', resource='{self.resource}')>"
    
    def check_conditions(self, context: Dict[str, Any]) -> bool:
        """Check if permission conditions are met"""
        if not self.conditions:
            return True
        
        # Simple condition checking - can be extended
        for key, expected_value in self.conditions.items():
            if key not in context or context[key] != expected_value:
                return False
        
        return True


class Role(EnterpriseBaseModel):
    """Role model for role-based access control"""
    
    __tablename__ = 'roles'
    __audit_enabled__ = True
    __searchable_fields__ = ['name', 'description']
    
    # Role details
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    role_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UserRole.USER.value
    )
    
    # Role configuration
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100
    )
    
    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles"
    )
    
    permissions: Mapped[List[Permission]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles"
    )
    
    @validates('role_type')
    def validate_role_type(self, key, value):
        """Validate role type"""
        if value not in [rt.value for rt in UserRole]:
            raise ValueError(f"Invalid role type: {value}")
        return value
    
    def __repr__(self) -> str:
        return f"<Role(name='{self.name}', type='{self.role_type}')>"
    
    def has_permission(self, permission_name: str, resource: str = None) -> bool:
        """Check if role has specific permission"""
        for perm in self.permissions:
            if perm.name == permission_name:
                if resource is None or perm.resource == resource:
                    return True
        return False
    
    def get_permissions_for_resource(self, resource: str) -> List[Permission]:
        """Get all permissions for a specific resource"""
        return [perm for perm in self.permissions if perm.resource == resource]


class UserSession(EnterpriseBaseModel):
    """User session model for session management"""
    
    __tablename__ = 'user_sessions'
    __audit_enabled__ = True
    __soft_delete__ = False  # Sessions should be hard deleted
    
    # Session details
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    session_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True
    )
    
    # Session metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 support
        nullable=True
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    device_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Session timing
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Session state
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    
    def __repr__(self) -> str:
        return f"<UserSession(user_id='{self.user_id}', token='{self.session_token[:8]}...')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if session is valid"""
        return self.is_active and not self.is_expired and not self.revoked_at
    
    def extend_session(self, duration: timedelta = timedelta(hours=24)) -> None:
        """Extend session expiration"""
        self.expires_at = datetime.now(timezone.utc) + duration
        self.last_activity_at = datetime.now(timezone.utc)
    
    def revoke(self) -> None:
        """Revoke session"""
        self.is_active = False
        self.revoked_at = datetime.now(timezone.utc)


class UserPreferences(EnterpriseBaseModel):
    """User preferences and settings"""
    
    __tablename__ = 'user_preferences'
    __audit_enabled__ = True
    
    # User reference
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )
    
    # Preferences data
    theme: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default='light'
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default='en'
    )
    
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default='UTC'
    )
    
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    # Custom preferences
    preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="preferences", uselist=False)
    
    def __repr__(self) -> str:
        return f"<UserPreferences(user_id='{self.user_id}', theme='{self.theme}')>"
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get custom preference value"""
        if not self.preferences:
            return default
        return self.preferences.get(key, default)
    
    def set_preference(self, key: str, value: Any) -> None:
        """Set custom preference value"""
        if not self.preferences:
            self.preferences = {}
        self.preferences[key] = value
    
    def update_preferences(self, data: Dict[str, Any]) -> None:
        """Update multiple preferences"""
        if not self.preferences:
            self.preferences = {}
        self.preferences.update(data)


class User(EnterpriseBaseModel):
    """
    Enterprise User Model
    
    Complete user management with:
    - Authentication and authorization
    - Role-based access control
    - Security audit trail
    - Session management
    - User preferences
    - Multi-factor authentication support
    """
    
    __tablename__ = 'users'
    __audit_enabled__ = True
    __searchable_fields__ = ['username', 'email', 'first_name', 'last_name']
    __serializable_fields__ = [
        'id', 'username', 'email', 'first_name', 'last_name',
        'is_active', 'is_verified', 'last_login_at', 'created_at', 'updated_at'
    ]
    
    # User identification
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )
    
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Personal information
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    display_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    # Authentication
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True  # Nullable for OAuth-only users
    )
    
    password_salt: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # Account status
    user_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION.value,
        index=True
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Security settings
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    mfa_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    mfa_backup_codes: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(20)),
        nullable=True
    )
    
    # Account security
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Activity tracking
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Verification
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True
    )
    
    email_verification_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    password_reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True
    )
    
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    roles: Mapped[List[Role]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin"
    )
    
    sessions: Mapped[List[UserSession]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    preferences: Mapped[Optional[UserPreferences]] = relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index('ix_users_status_active', 'user_status', 'is_active'),
        Index('ix_users_email_verified', 'email', 'is_verified'),
        Index('ix_users_last_login', 'last_login_at'),
    )
    
    def __init__(self, **kwargs):
        # Initialize vault manager for password operations
        self._vault = get_enterprise_vault_manager()
        self._audit = get_persistent_audit_trail()
        
        super().__init__(**kwargs)
        
        # Set display name if not provided
        if not self.display_name and self.first_name and self.last_name:
            self.display_name = f"{self.first_name} {self.last_name}"
    
    def __repr__(self) -> str:
        return f"<User(username='{self.username}', email='{self.email}')>"
    
    # Validation methods
    
    def _validate_custom(self) -> List[ModelValidationError]:
        """Custom validation for user model"""
        errors = []
        
        # Username validation
        if not self.username or len(self.username) < 3:
            errors.append(ModelValidationError(
                field='username',
                message='Username must be at least 3 characters long',
                code='min_length',
                value=self.username
            ))
        
        # Email validation
        if not self.email or '@' not in self.email:
            errors.append(ModelValidationError(
                field='email',
                message='Valid email address is required',
                code='invalid_email',
                value=self.email
            ))
        
        # Status validation
        if self.user_status not in [s.value for s in UserStatus]:
            errors.append(ModelValidationError(
                field='user_status',
                message='Invalid user status',
                code='invalid_status',
                value=self.user_status
            ))
        
        return errors
    
    @validates('username')
    def validate_username(self, key, value):
        """Validate username format"""
        if not value or len(value.strip()) < 3:
            raise ValueError("Username must be at least 3 characters long")
        
        # Check for valid characters
        import re
        if not re.match(r'^[a-zA-Z0-9_.-]+$', value):
            raise ValueError("Username can only contain letters, numbers, dots, dashes, and underscores")
        
        return value.strip().lower()
    
    @validates('email')
    def validate_email(self, key, value):
        """Validate email format"""
        if not value or '@' not in value:
            raise ValueError("Valid email address is required")
        
        return value.strip().lower()
    
    @validates('user_status')
    def validate_user_status(self, key, value):
        """Validate user status"""
        if value not in [s.value for s in UserStatus]:
            raise ValueError(f"Invalid user status: {value}")
        return value
    
    # Password management
    
    async def set_password(self, password: str) -> None:
        """Set user password with secure hashing"""
        try:
            # Validate password strength
            if not self._validate_password_strength(password):
                raise ValueError("Password does not meet strength requirements")
            
            # Generate salt and hash password
            salt = secrets.token_hex(16)
            password_hash = await self._vault.hash_password(password + salt)
            
            self.password_hash = password_hash
            self.password_salt = salt
            self.password_changed_at = datetime.now(timezone.utc)
            
            # Reset failed login attempts
            self.failed_login_attempts = 0
            self.locked_until = None
            
            # Audit password change
            self._audit.add_entry(
                'user_password_changed',
                {
                    'user_id': str(self.id),
                    'username': self.username,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                user_context={'user_id': str(self.id)}
            )
            
        except Exception as e:
            logger.error(f"Failed to set password for user {self.id}: {e}")
            raise
    
    async def verify_password(self, password: str) -> bool:
        """Verify user password"""
        try:
            if not self.password_hash or not self.password_salt:
                return False
            
            # Check if account is locked
            if self.is_locked:
                self._audit.add_entry(
                    'user_login_attempt_locked',
                    {
                        'user_id': str(self.id),
                        'username': self.username,
                        'locked_until': self.locked_until.isoformat() if self.locked_until else None
                    },
                    user_context={'user_id': str(self.id)}
                )
                return False
            
            # Verify password
            is_valid = await self._vault.verify_password(
                password + self.password_salt,
                self.password_hash
            )
            
            if is_valid:
                # Reset failed attempts on successful login
                self.failed_login_attempts = 0
                self.last_login_at = datetime.now(timezone.utc)
                self.last_activity_at = datetime.now(timezone.utc)
                
                # Audit successful login
                self._audit.add_entry(
                    'user_login_success',
                    {
                        'user_id': str(self.id),
                        'username': self.username,
                        'last_login': self.last_login_at.isoformat()
                    },
                    user_context={'user_id': str(self.id)}
                )
            else:
                # Increment failed attempts
                self.failed_login_attempts += 1
                
                # Lock account if too many failures
                if self.failed_login_attempts >= 5:
                    self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                
                # Audit failed login
                self._audit.add_entry(
                    'user_login_failed',
                    {
                        'user_id': str(self.id),
                        'username': self.username,
                        'failed_attempts': self.failed_login_attempts,
                        'locked': self.is_locked
                    },
                    user_context={'user_id': str(self.id)}
                )
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to verify password for user {self.id}: {e}")
            return False
    
    def _validate_password_strength(self, password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            return False
        
        # Check for complexity
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        return sum([has_upper, has_lower, has_digit, has_special]) >= 3
    
    # Account status management
    
    @property
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until
    
    @property
    def status_enum(self) -> UserStatus:
        """Get status as enum"""
        try:
            return UserStatus(self.user_status)
        except ValueError:
            return UserStatus.INACTIVE
    
    def activate(self) -> None:
        """Activate user account"""
        self.is_active = True
        self.user_status = UserStatus.ACTIVE.value
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def deactivate(self) -> None:
        """Deactivate user account"""
        self.is_active = False
        self.user_status = UserStatus.INACTIVE.value
    
    def suspend(self, reason: str = None) -> None:
        """Suspend user account"""
        self.user_status = UserStatus.SUSPENDED.value
        if reason:
            self.set_metadata('suspension_reason', reason)
    
    def verify_email(self) -> None:
        """Verify user email"""
        self.is_verified = True
        self.email_verification_token = None
        self.email_verification_expires = None
        
        if self.user_status == UserStatus.PENDING_VERIFICATION.value:
            self.user_status = UserStatus.ACTIVE.value
    
    # Role and permission management
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role"""
        return any(role.name == role_name for role in self.roles)
    
    def has_role_type(self, role_type: UserRole) -> bool:
        """Check if user has specific role type"""
        return any(role.role_type == role_type.value for role in self.roles)
    
    def has_permission(self, permission_name: str, resource: str = None) -> bool:
        """Check if user has specific permission"""
        # Superuser has all permissions
        if self.is_superuser:
            return True
        
        # Check through roles
        for role in self.roles:
            if role.has_permission(permission_name, resource):
                return True
        
        return False
    
    def get_permissions(self) -> Set[str]:
        """Get all user permissions"""
        permissions = set()
        
        for role in self.roles:
            for perm in role.permissions:
                permissions.add(f"{perm.name}:{perm.resource}")
        
        return permissions
    
    def get_role_names(self) -> List[str]:
        """Get list of role names"""
        return [role.name for role in self.roles]
    
    # Multi-factor authentication
    
    def enable_mfa(self, secret: str = None) -> str:
        """Enable multi-factor authentication"""
        if not secret:
            secret = secrets.token_hex(20)
        
        self.mfa_enabled = True
        self.mfa_secret = secret
        
        # Generate backup codes
        backup_codes = [secrets.token_hex(8) for _ in range(10)]
        self.mfa_backup_codes = backup_codes
        
        # Audit MFA enable
        self._audit.add_entry(
            'user_mfa_enabled',
            {
                'user_id': str(self.id),
                'username': self.username,
                'backup_codes_generated': len(backup_codes)
            },
            user_context={'user_id': str(self.id)}
        )
        
        return secret
    
    def disable_mfa(self) -> None:
        """Disable multi-factor authentication"""
        self.mfa_enabled = False
        self.mfa_secret = None
        self.mfa_backup_codes = None
        
        # Audit MFA disable
        self._audit.add_entry(
            'user_mfa_disabled',
            {
                'user_id': str(self.id),
                'username': self.username
            },
            user_context={'user_id': str(self.id)}
        )
    
    def verify_mfa_code(self, code: str) -> bool:
        """Verify MFA code"""
        if not self.mfa_enabled or not self.mfa_secret:
            return False
        
        # Check backup codes first
        if self.mfa_backup_codes and code in self.mfa_backup_codes:
            # Remove used backup code
            self.mfa_backup_codes.remove(code)
            return True
        
        # Verify TOTP code (simplified - would use actual TOTP library)
        # This is a placeholder implementation
        return len(code) == 6 and code.isdigit()
    
    # Session management
    
    def create_session(
        self,
        ip_address: str = None,
        user_agent: str = None,
        device_id: str = None,
        duration: timedelta = timedelta(days=1)
    ) -> UserSession:
        """Create new user session"""
        
        session_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        session = UserSession(
            user_id=str(self.id),
            session_token=session_token,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            device_id=device_id,
            expires_at=datetime.now(timezone.utc) + duration
        )
        
        return session
    
    def get_active_sessions(self) -> List[UserSession]:
        """Get all active user sessions"""
        return [s for s in self.sessions if s.is_valid]
    
    def revoke_all_sessions(self) -> None:
        """Revoke all user sessions"""
        for session in self.sessions:
            if session.is_active:
                session.revoke()
        
        # Audit session revocation
        self._audit.add_entry(
            'user_sessions_revoked_all',
            {
                'user_id': str(self.id),
                'username': self.username,
                'sessions_revoked': len([s for s in self.sessions if s.revoked_at])
            },
            user_context={'user_id': str(self.id)}
        )
    
    # Token generation
    
    def generate_verification_token(self) -> str:
        """Generate email verification token"""
        token = secrets.token_urlsafe(32)
        self.email_verification_token = token
        self.email_verification_expires = datetime.now(timezone.utc) + timedelta(days=1)
        return token
    
    def generate_password_reset_token(self) -> str:
        """Generate password reset token"""
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        return token
    
    def verify_verification_token(self, token: str) -> bool:
        """Verify email verification token"""
        if not self.email_verification_token or not self.email_verification_expires:
            return False
        
        if datetime.now(timezone.utc) > self.email_verification_expires:
            return False
        
        return self.email_verification_token == token
    
    def verify_password_reset_token(self, token: str) -> bool:
        """Verify password reset token"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        
        if datetime.now(timezone.utc) > self.password_reset_expires:
            return False
        
        return self.password_reset_token == token
    
    # Activity tracking
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity_at = datetime.now(timezone.utc)
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    @hybrid_property
    def is_online(self) -> bool:
        """Check if user is currently online"""
        if not self.last_activity_at:
            return False
        
        # Consider online if activity within last 5 minutes
        return (
            datetime.now(timezone.utc) - self.last_activity_at
        ).total_seconds() < 300


class UserRepository(EnterpriseRepository):
    """Repository for User model with additional authentication methods"""
    
    def __init__(self, pool_id: str = "default"):
        super().__init__(User, pool_id)
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            async with self._get_session() as session:
                result = await session.query(User).filter(
                    and_(
                        User.username == username.lower(),
                        User.is_deleted == False
                    )
                ).first()
                
                if result:
                    result._audit_action(AuditAction.READ, session)
                
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to get user by username {username}: {e}")
            raise
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            async with self._get_session() as session:
                result = await session.query(User).filter(
                    and_(
                        User.email == email.lower(),
                        User.is_deleted == False
                    )
                ).first()
                
                if result:
                    result._audit_action(AuditAction.READ, session)
                
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to get user by email {email}: {e}")
            raise
    
    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user by username/email and password"""
        try:
            # Try to find user by username or email
            user = await self.get_by_username(username)
            if not user:
                user = await self.get_by_email(username)
            
            if not user:
                return None
            
            # Check if user can login
            if not user.is_active or user.status_enum != UserStatus.ACTIVE:
                return None
            
            # Verify password
            if await user.verify_password(password):
                return user
            
            return None
            
        except Exception as e:
            self.logger.error(f"Authentication failed for {username}: {e}")
            return None
    
    async def get_active_users(self, limit: int = 100) -> List[User]:
        """Get active users"""
        return await self.list(
            filters={
                'is_active': True,
                'user_status': UserStatus.ACTIVE.value
            },
            limit=limit
        )
    
    async def search_users(self, query: str, limit: int = 50) -> List[User]:
        """Search users by name, username, or email"""
        try:
            async with self._get_session() as session:
                search_term = f"%{query.lower()}%"
                
                result = await session.query(User).filter(
                    and_(
                        User.is_deleted == False,
                        or_(
                            User.username.ilike(search_term),
                            User.email.ilike(search_term),
                            User.first_name.ilike(search_term),
                            User.last_name.ilike(search_term)
                        )
                    )
                ).limit(limit).all()
                
                return result
                
        except Exception as e:
            self.logger.error(f"User search failed for query '{query}': {e}")
            raise


# Repository factory function
def get_user_repository(pool_id: str = "default") -> UserRepository:
    """Get user repository instance"""
    return UserRepository(pool_id)