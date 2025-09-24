"""
DafelHub Role-Based Access Control (RBAC) System
Enterprise-Grade Permission Management with Granular Controls
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from functools import wraps
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.database.models import User
from .models import (
    SecurityRole, UserSecurityProfile, SecurityAuditLog, AuditEventType,
    SecurityPolicy, ThreatLevel
)
from .authentication import SecurityContext


logger = get_logger(__name__)


class Permission(str, Enum):
    """System permissions"""
    # User Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"
    USER_ACTIVATE = "user:activate"
    USER_DEACTIVATE = "user:deactivate"
    
    # Role Management
    ROLE_ASSIGN = "role:assign"
    ROLE_REVOKE = "role:revoke"
    ROLE_VIEW = "role:view"
    
    # Security Management
    SECURITY_VIEW_LOGS = "security:view_logs"
    SECURITY_MANAGE_POLICIES = "security:manage_policies"
    SECURITY_UNLOCK_ACCOUNTS = "security:unlock_accounts"
    SECURITY_RESET_2FA = "security:reset_2fa"
    SECURITY_VIEW_SESSIONS = "security:view_sessions"
    SECURITY_TERMINATE_SESSIONS = "security:terminate_sessions"
    
    # Data Management
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"
    DATA_EXPORT = "data:export"
    DATA_IMPORT = "data:import"
    DATA_BACKUP = "data:backup"
    DATA_RESTORE = "data:restore"
    
    # System Administration
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITORING = "system:monitoring"
    SYSTEM_MAINTENANCE = "system:maintenance"
    
    # Audit & Compliance
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"
    COMPLIANCE_MANAGE = "compliance:manage"
    
    # API Access
    API_READ = "api:read"
    API_WRITE = "api:write"
    API_ADMIN = "api:admin"


class ResourceType(str, Enum):
    """Resource types for permission checks"""
    USER = "user"
    ROLE = "role"
    SECURITY = "security"
    DATA = "data"
    SYSTEM = "system"
    AUDIT = "audit"
    API = "api"
    DASHBOARD = "dashboard"
    REPORT = "report"


@dataclass
class PermissionGrant:
    """Permission grant with context"""
    permission: Permission
    resource_type: Optional[ResourceType] = None
    resource_id: Optional[str] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    granted_by: Optional[uuid.UUID] = None
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RoleDefinition:
    """Complete role definition with permissions and metadata"""
    role: SecurityRole
    display_name: str
    description: str
    permissions: Set[Permission]
    inherits_from: Optional[SecurityRole] = None
    is_system_role: bool = True
    can_be_assigned: bool = True
    max_users: Optional[int] = None


class RolePermissionError(Exception):
    """Role and permission related errors"""
    pass


class AccessDeniedError(Exception):
    """Access denied error"""
    pass


class RBACManager(LoggerMixin):
    """Main RBAC management system"""
    
    def __init__(self, db: Session):
        self.db = db
        self._role_definitions = self._initialize_role_definitions()
        self._permission_cache = {}
        self._cache_ttl = timedelta(minutes=15)
    
    def _initialize_role_definitions(self) -> Dict[SecurityRole, RoleDefinition]:
        """Initialize default role definitions"""
        return {
            SecurityRole.ADMIN: RoleDefinition(
                role=SecurityRole.ADMIN,
                display_name="System Administrator",
                description="Full system access with all permissions",
                permissions={
                    # All permissions
                    Permission.USER_CREATE, Permission.USER_READ, Permission.USER_UPDATE, 
                    Permission.USER_DELETE, Permission.USER_LIST, Permission.USER_ACTIVATE, 
                    Permission.USER_DEACTIVATE,
                    Permission.ROLE_ASSIGN, Permission.ROLE_REVOKE, Permission.ROLE_VIEW,
                    Permission.SECURITY_VIEW_LOGS, Permission.SECURITY_MANAGE_POLICIES,
                    Permission.SECURITY_UNLOCK_ACCOUNTS, Permission.SECURITY_RESET_2FA,
                    Permission.SECURITY_VIEW_SESSIONS, Permission.SECURITY_TERMINATE_SESSIONS,
                    Permission.DATA_READ, Permission.DATA_WRITE, Permission.DATA_DELETE,
                    Permission.DATA_EXPORT, Permission.DATA_IMPORT, Permission.DATA_BACKUP,
                    Permission.DATA_RESTORE,
                    Permission.SYSTEM_CONFIG, Permission.SYSTEM_MONITORING, Permission.SYSTEM_MAINTENANCE,
                    Permission.AUDIT_VIEW, Permission.AUDIT_EXPORT, Permission.COMPLIANCE_MANAGE,
                    Permission.API_READ, Permission.API_WRITE, Permission.API_ADMIN
                }
            ),
            
            SecurityRole.SECURITY_ADMIN: RoleDefinition(
                role=SecurityRole.SECURITY_ADMIN,
                display_name="Security Administrator",
                description="Security-focused administration with audit capabilities",
                permissions={
                    Permission.USER_READ, Permission.USER_LIST, Permission.USER_ACTIVATE,
                    Permission.USER_DEACTIVATE,
                    Permission.ROLE_VIEW,
                    Permission.SECURITY_VIEW_LOGS, Permission.SECURITY_MANAGE_POLICIES,
                    Permission.SECURITY_UNLOCK_ACCOUNTS, Permission.SECURITY_RESET_2FA,
                    Permission.SECURITY_VIEW_SESSIONS, Permission.SECURITY_TERMINATE_SESSIONS,
                    Permission.DATA_READ, Permission.DATA_EXPORT,
                    Permission.SYSTEM_MONITORING,
                    Permission.AUDIT_VIEW, Permission.AUDIT_EXPORT, Permission.COMPLIANCE_MANAGE,
                    Permission.API_READ
                }
            ),
            
            SecurityRole.EDITOR: RoleDefinition(
                role=SecurityRole.EDITOR,
                display_name="Editor",
                description="Content management with read/write access",
                permissions={
                    Permission.USER_READ, Permission.USER_LIST,
                    Permission.ROLE_VIEW,
                    Permission.DATA_READ, Permission.DATA_WRITE, Permission.DATA_EXPORT,
                    Permission.API_READ, Permission.API_WRITE
                }
            ),
            
            SecurityRole.AUDITOR: RoleDefinition(
                role=SecurityRole.AUDITOR,
                display_name="Auditor",
                description="Read-only audit and compliance access",
                permissions={
                    Permission.USER_READ, Permission.USER_LIST,
                    Permission.ROLE_VIEW,
                    Permission.SECURITY_VIEW_LOGS, Permission.SECURITY_VIEW_SESSIONS,
                    Permission.DATA_READ,
                    Permission.SYSTEM_MONITORING,
                    Permission.AUDIT_VIEW, Permission.AUDIT_EXPORT,
                    Permission.API_READ
                }
            ),
            
            SecurityRole.VIEWER: RoleDefinition(
                role=SecurityRole.VIEWER,
                display_name="Viewer",
                description="Basic read-only access",
                permissions={
                    Permission.USER_READ,
                    Permission.DATA_READ,
                    Permission.API_READ
                }
            )
        }
    
    def get_user_permissions(self, user_id: uuid.UUID) -> Set[Permission]:
        """Get all permissions for a user"""
        try:
            # Check cache first
            cache_key = f"permissions:{user_id}"
            cached = self._permission_cache.get(cache_key)
            if cached and cached['expires'] > datetime.now(timezone.utc):
                return cached['permissions']
            
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return set()
            
            # Get role permissions
            user_role = getattr(user, 'role', SecurityRole.VIEWER)
            role_def = self._role_definitions.get(user_role, self._role_definitions[SecurityRole.VIEWER])
            permissions = role_def.permissions.copy()
            
            # Add inherited permissions
            if role_def.inherits_from:
                inherited_def = self._role_definitions.get(role_def.inherits_from)
                if inherited_def:
                    permissions.update(inherited_def.permissions)
            
            # Cache permissions
            self._permission_cache[cache_key] = {
                'permissions': permissions,
                'expires': datetime.now(timezone.utc) + self._cache_ttl
            }
            
            return permissions
            
        except Exception as e:
            self.logger.error(f"Failed to get user permissions: {e}")
            return set()
    
    def check_permission(
        self,
        user_id: uuid.UUID,
        permission: Permission,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None,
        context: Optional[SecurityContext] = None
    ) -> bool:
        """Check if user has specific permission"""
        try:
            user_permissions = self.get_user_permissions(user_id)
            
            # Basic permission check
            if permission not in user_permissions:
                return False
            
            # Additional context-based checks
            if context:
                # Check if 2FA is required for sensitive operations
                sensitive_permissions = {
                    Permission.USER_DELETE, Permission.ROLE_ASSIGN, Permission.ROLE_REVOKE,
                    Permission.SECURITY_MANAGE_POLICIES, Permission.DATA_DELETE,
                    Permission.SYSTEM_CONFIG, Permission.API_ADMIN
                }
                
                if permission in sensitive_permissions and not context.two_factor_verified:
                    self.logger.warning(f"2FA required for permission: {permission}")
                    return False
                
                # Check risk score for high-risk operations
                if context.risk_score > 0.7 and permission in sensitive_permissions:
                    self.logger.warning(f"High risk score for sensitive operation: {context.risk_score}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Permission check failed: {e}")
            return False
    
    def require_permission(
        self,
        permission: Permission,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None,
        require_2fa: bool = False
    ):
        """Decorator to require specific permission"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get current user context (would be injected by middleware)
                from .authentication import get_current_user_context
                context = get_current_user_context()
                
                if not context:
                    raise AccessDeniedError("No user context available")
                
                if not self.check_permission(
                    context.user_id, permission, resource_type, resource_id, context
                ):
                    self.log_access_denied(
                        context.user_id, permission, resource_type, resource_id
                    )
                    raise AccessDeniedError(f"Permission denied: {permission}")
                
                if require_2fa and not context.two_factor_verified:
                    raise AccessDeniedError("Two-factor authentication required")
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def assign_role(
        self,
        user_id: uuid.UUID,
        role: SecurityRole,
        assigned_by: uuid.UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Assign role to user"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise RolePermissionError("User not found")
            
            # Check if role can be assigned
            role_def = self._role_definitions.get(role)
            if not role_def or not role_def.can_be_assigned:
                raise RolePermissionError(f"Role {role} cannot be assigned")
            
            # Check maximum users limit
            if role_def.max_users:
                current_count = self.db.query(User).filter(
                    getattr(User, 'role', None) == role
                ).count()
                if current_count >= role_def.max_users:
                    raise RolePermissionError(f"Maximum users limit reached for role {role}")
            
            old_role = getattr(user, 'role', None)
            setattr(user, 'role', role)
            
            # Log role assignment
            audit_log = SecurityAuditLog(
                event_type=AuditEventType.ROLE_ASSIGNED,
                event_category="ROLE_MANAGEMENT",
                event_description=f"Role assigned to user: {role}",
                user_id=assigned_by,
                resource_type="USER",
                resource_id=str(user_id),
                success=True,
                event_details={
                    'target_user_id': str(user_id),
                    'target_username': user.username,
                    'new_role': role,
                    'old_role': old_role,
                    'reason': reason
                }
            )
            self.db.add(audit_log)
            
            # Clear permission cache
            cache_key = f"permissions:{user_id}"
            self._permission_cache.pop(cache_key, None)
            
            self.db.commit()
            
            self.logger.info(f"Role {role} assigned to user {user.username} by {assigned_by}")
            return True
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Role assignment failed: {e}")
            return False
    
    def revoke_role(
        self,
        user_id: uuid.UUID,
        revoked_by: uuid.UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Revoke role from user (set to VIEWER)"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise RolePermissionError("User not found")
            
            old_role = getattr(user, 'role', None)
            setattr(user, 'role', SecurityRole.VIEWER)
            
            # Log role revocation
            audit_log = SecurityAuditLog(
                event_type=AuditEventType.ROLE_REMOVED,
                event_category="ROLE_MANAGEMENT",
                event_description=f"Role revoked from user: {old_role}",
                user_id=revoked_by,
                resource_type="USER",
                resource_id=str(user_id),
                success=True,
                event_details={
                    'target_user_id': str(user_id),
                    'target_username': user.username,
                    'revoked_role': old_role,
                    'new_role': SecurityRole.VIEWER,
                    'reason': reason
                }
            )
            self.db.add(audit_log)
            
            # Clear permission cache
            cache_key = f"permissions:{user_id}"
            self._permission_cache.pop(cache_key, None)
            
            self.db.commit()
            
            self.logger.info(f"Role {old_role} revoked from user {user.username} by {revoked_by}")
            return True
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Role revocation failed: {e}")
            return False
    
    def get_role_users(self, role: SecurityRole) -> List[Dict[str, Any]]:
        """Get all users with specific role"""
        try:
            users = self.db.query(User).filter(
                getattr(User, 'role', None) == role
            ).all()
            
            return [{
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'created_at': user.created_at
            } for user in users]
            
        except Exception as e:
            self.logger.error(f"Failed to get role users: {e}")
            return []
    
    def get_user_role_info(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get comprehensive role information for user"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            user_role = getattr(user, 'role', SecurityRole.VIEWER)
            role_def = self._role_definitions.get(user_role)
            permissions = self.get_user_permissions(user_id)
            
            return {
                'user_id': str(user_id),
                'username': user.username,
                'current_role': user_role,
                'role_display_name': role_def.display_name if role_def else user_role,
                'role_description': role_def.description if role_def else "",
                'permissions': list(permissions),
                'permission_count': len(permissions),
                'is_system_role': role_def.is_system_role if role_def else True,
                'can_assign_roles': Permission.ROLE_ASSIGN in permissions,
                'can_manage_users': Permission.USER_CREATE in permissions
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get user role info: {e}")
            return {}
    
    def get_available_roles(self, requesting_user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Get roles that can be assigned by requesting user"""
        try:
            requester_permissions = self.get_user_permissions(requesting_user_id)
            
            # Only users with ROLE_ASSIGN can see assignable roles
            if Permission.ROLE_ASSIGN not in requester_permissions:
                return []
            
            roles = []
            for role, role_def in self._role_definitions.items():
                if role_def.can_be_assigned:
                    current_users = len(self.get_role_users(role))
                    roles.append({
                        'role': role,
                        'display_name': role_def.display_name,
                        'description': role_def.description,
                        'permission_count': len(role_def.permissions),
                        'current_users': current_users,
                        'max_users': role_def.max_users,
                        'can_assign': current_users < (role_def.max_users or float('inf'))
                    })
            
            return sorted(roles, key=lambda x: x['display_name'])
            
        except Exception as e:
            self.logger.error(f"Failed to get available roles: {e}")
            return []
    
    def validate_role_hierarchy(self, assigner_role: SecurityRole, target_role: SecurityRole) -> bool:
        """Validate if assigner can assign target role"""
        hierarchy = {
            SecurityRole.ADMIN: 5,
            SecurityRole.SECURITY_ADMIN: 4,
            SecurityRole.EDITOR: 3,
            SecurityRole.AUDITOR: 2,
            SecurityRole.VIEWER: 1
        }
        
        return hierarchy.get(assigner_role, 0) > hierarchy.get(target_role, 0)
    
    def log_access_denied(
        self,
        user_id: uuid.UUID,
        permission: Permission,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None
    ) -> None:
        """Log access denied event"""
        try:
            audit_log = SecurityAuditLog(
                event_type=AuditEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
                event_category="ACCESS_CONTROL",
                event_description=f"Access denied for permission: {permission}",
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                success=False,
                threat_level=ThreatLevel.MEDIUM,
                event_details={
                    'denied_permission': permission,
                    'resource_type': resource_type,
                    'resource_id': resource_id
                }
            )
            self.db.add(audit_log)
            self.db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to log access denied: {e}")
    
    def clear_permission_cache(self, user_id: Optional[uuid.UUID] = None) -> None:
        """Clear permission cache for user or all users"""
        if user_id:
            cache_key = f"permissions:{user_id}"
            self._permission_cache.pop(cache_key, None)
        else:
            self._permission_cache.clear()
        
        self.logger.info(f"Permission cache cleared for {'user ' + str(user_id) if user_id else 'all users'}")


# Global RBAC manager instance
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager(db: Session) -> RBACManager:
    """Get or create RBAC manager instance"""
    global _rbac_manager
    if not _rbac_manager:
        _rbac_manager = RBACManager(db)
    return _rbac_manager


# Convenience decorators
def require_admin(func):
    """Require ADMIN role"""
    def wrapper(*args, **kwargs):
        from .authentication import get_current_user_context
        context = get_current_user_context()
        if not context or context.role != SecurityRole.ADMIN:
            raise AccessDeniedError("Administrator access required")
        return func(*args, **kwargs)
    return wrapper


def require_2fa(func):
    """Require two-factor authentication"""
    def wrapper(*args, **kwargs):
        from .authentication import get_current_user_context
        context = get_current_user_context()
        if not context or not context.two_factor_verified:
            raise AccessDeniedError("Two-factor authentication required")
        return func(*args, **kwargs)
    return wrapper