"""
DafelHub Role-Based Access Control (RBAC) System
SOC 2 Type II Compliant Access Control with Financial Services Grade Security
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
from functools import wraps
from dataclasses import dataclass

from sqlalchemy.orm import Session

from dafelhub.core.logging import get_logger, LoggerMixin
from .models import SecurityRole, AuditEventType
from .authentication import SecurityContext, get_current_user_context
from .audit import AuditLogger

logger = get_logger(__name__)


class AccessDeniedError(Exception):
    """Access denied exception"""
    pass


class Permission(str, Enum):
    """System permissions"""
    # User Management
    CREATE_USER = "CREATE_USER"
    READ_USER = "READ_USER"
    UPDATE_USER = "UPDATE_USER"
    DELETE_USER = "DELETE_USER"
    MANAGE_USERS = "MANAGE_USERS"
    
    # Project Management
    CREATE_PROJECT = "CREATE_PROJECT"
    READ_PROJECT = "READ_PROJECT"
    UPDATE_PROJECT = "UPDATE_PROJECT"
    DELETE_PROJECT = "DELETE_PROJECT"
    MANAGE_PROJECTS = "MANAGE_PROJECTS"
    
    # Specification Management
    CREATE_SPEC = "CREATE_SPEC"
    READ_SPEC = "READ_SPEC"
    UPDATE_SPEC = "UPDATE_SPEC"
    DELETE_SPEC = "DELETE_SPEC"
    APPROVE_SPEC = "APPROVE_SPEC"
    
    # Data Source Management
    CREATE_DATA_SOURCE = "CREATE_DATA_SOURCE"
    READ_DATA_SOURCE = "READ_DATA_SOURCE"
    UPDATE_DATA_SOURCE = "UPDATE_DATA_SOURCE"
    DELETE_DATA_SOURCE = "DELETE_DATA_SOURCE"
    EXPORT_DATA = "EXPORT_DATA"
    IMPORT_DATA = "IMPORT_DATA"
    
    # Agent Management
    CREATE_AGENT = "CREATE_AGENT"
    READ_AGENT = "READ_AGENT"
    UPDATE_AGENT = "UPDATE_AGENT"
    DELETE_AGENT = "DELETE_AGENT"
    EXECUTE_AGENT = "EXECUTE_AGENT"
    
    # Deployment Management
    CREATE_DEPLOYMENT = "CREATE_DEPLOYMENT"
    READ_DEPLOYMENT = "READ_DEPLOYMENT"
    UPDATE_DEPLOYMENT = "UPDATE_DEPLOYMENT"
    DELETE_DEPLOYMENT = "DELETE_DEPLOYMENT"
    DEPLOY_TO_PRODUCTION = "DEPLOY_TO_PRODUCTION"
    
    # Security & Audit
    READ_AUDIT_LOGS = "READ_AUDIT_LOGS"
    READ_SECURITY_EVENTS = "READ_SECURITY_EVENTS"
    MANAGE_SECURITY = "MANAGE_SECURITY"
    GENERATE_COMPLIANCE_REPORTS = "GENERATE_COMPLIANCE_REPORTS"
    
    # System Administration
    MANAGE_SYSTEM_CONFIG = "MANAGE_SYSTEM_CONFIG"
    MANAGE_ENCRYPTION_KEYS = "MANAGE_ENCRYPTION_KEYS"
    MANAGE_BACKUPS = "MANAGE_BACKUPS"
    
    # Special Permissions
    SUDO = "SUDO"  # Super admin override
    IMPERSONATE_USER = "IMPERSONATE_USER"


@dataclass
class RoleDefinition:
    """Role definition with permissions and metadata"""
    role: SecurityRole
    name: str
    description: str
    permissions: Set[Permission]
    is_system_role: bool = True
    inherits_from: Optional[SecurityRole] = None


class RoleRegistry(LoggerMixin):
    """Registry of role definitions"""
    
    def __init__(self):
        self._roles: Dict[SecurityRole, RoleDefinition] = {}
        self._setup_default_roles()
    
    def _setup_default_roles(self):
        """Setup default system roles"""
        
        # VIEWER Role - Read-only access
        self._roles[SecurityRole.VIEWER] = RoleDefinition(
            role=SecurityRole.VIEWER,
            name="Viewer",
            description="Read-only access to projects and specifications",
            permissions={
                Permission.READ_PROJECT,
                Permission.READ_SPEC,
                Permission.READ_DATA_SOURCE,
                Permission.READ_AGENT,
                Permission.READ_DEPLOYMENT,
            }
        )
        
        # EDITOR Role - Can create and modify content
        self._roles[SecurityRole.EDITOR] = RoleDefinition(
            role=SecurityRole.EDITOR,
            name="Editor",
            description="Can create and modify projects, specifications, and data sources",
            permissions={
                # Inherit viewer permissions
                *self._roles[SecurityRole.VIEWER].permissions,
                
                # Project permissions
                Permission.CREATE_PROJECT,
                Permission.UPDATE_PROJECT,
                
                # Specification permissions
                Permission.CREATE_SPEC,
                Permission.UPDATE_SPEC,
                
                # Data source permissions
                Permission.CREATE_DATA_SOURCE,
                Permission.UPDATE_DATA_SOURCE,
                Permission.EXPORT_DATA,
                Permission.IMPORT_DATA,
                
                # Agent permissions
                Permission.CREATE_AGENT,
                Permission.UPDATE_AGENT,
                Permission.EXECUTE_AGENT,
                
                # Deployment permissions (non-production)
                Permission.CREATE_DEPLOYMENT,
                Permission.UPDATE_DEPLOYMENT,
            },
            inherits_from=SecurityRole.VIEWER
        )
        
        # ADMIN Role - Full administrative access
        self._roles[SecurityRole.ADMIN] = RoleDefinition(
            role=SecurityRole.ADMIN,
            name="Administrator",
            description="Full administrative access to all system resources",
            permissions={
                # Inherit editor permissions
                *self._roles[SecurityRole.EDITOR].permissions,
                
                # User management
                Permission.CREATE_USER,
                Permission.READ_USER,
                Permission.UPDATE_USER,
                Permission.DELETE_USER,
                Permission.MANAGE_USERS,
                
                # Full project management
                Permission.DELETE_PROJECT,
                Permission.MANAGE_PROJECTS,
                
                # Full specification management
                Permission.DELETE_SPEC,
                Permission.APPROVE_SPEC,
                
                # Full data source management
                Permission.DELETE_DATA_SOURCE,
                
                # Full agent management
                Permission.DELETE_AGENT,
                
                # Full deployment management
                Permission.DELETE_DEPLOYMENT,
                Permission.DEPLOY_TO_PRODUCTION,
                
                # Audit and security
                Permission.READ_AUDIT_LOGS,
                Permission.READ_SECURITY_EVENTS,
                
                # System administration
                Permission.MANAGE_SYSTEM_CONFIG,
                Permission.MANAGE_BACKUPS,
            },
            inherits_from=SecurityRole.EDITOR
        )
        
        # AUDITOR Role - Security and compliance focused
        self._roles[SecurityRole.AUDITOR] = RoleDefinition(
            role=SecurityRole.AUDITOR,
            name="Auditor",
            description="Security auditing and compliance reporting access",
            permissions={
                # Basic read access
                Permission.READ_PROJECT,
                Permission.READ_SPEC,
                Permission.READ_USER,
                
                # Audit and security (full access)
                Permission.READ_AUDIT_LOGS,
                Permission.READ_SECURITY_EVENTS,
                Permission.GENERATE_COMPLIANCE_REPORTS,
                
                # Limited data access for auditing
                Permission.READ_DATA_SOURCE,
                Permission.READ_DEPLOYMENT,
            }
        )
        
        # SECURITY_ADMIN Role - Security management
        self._roles[SecurityRole.SECURITY_ADMIN] = RoleDefinition(
            role=SecurityRole.SECURITY_ADMIN,
            name="Security Administrator",
            description="Security and encryption key management",
            permissions={
                # Inherit auditor permissions
                *self._roles[SecurityRole.AUDITOR].permissions,
                
                # Security management
                Permission.MANAGE_SECURITY,
                Permission.MANAGE_ENCRYPTION_KEYS,
                
                # User security management
                Permission.READ_USER,
                Permission.UPDATE_USER,  # For security profile updates
                
                # Special permissions
                Permission.SUDO,  # Emergency override capability
            },
            inherits_from=SecurityRole.AUDITOR
        )
        
        self.logger.info("Default roles configured successfully")
    
    def get_role_definition(self, role: SecurityRole) -> Optional[RoleDefinition]:
        """Get role definition"""
        return self._roles.get(role)
    
    def get_all_roles(self) -> Dict[SecurityRole, RoleDefinition]:
        """Get all role definitions"""
        return self._roles.copy()
    
    def add_custom_role(self, role_def: RoleDefinition) -> None:
        """Add custom role definition"""
        self._roles[role_def.role] = role_def
        self.logger.info(f"Custom role added: {role_def.name}")


class RoleBasedAccessControl(LoggerMixin):
    """Role-based access control implementation"""
    
    def __init__(self, db: Session):
        self.db = db
        self.role_registry = RoleRegistry()
        self.audit_logger = AuditLogger(db)
    
    def check_permission(
        self,
        user_context: SecurityContext,
        permission: Permission,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None
    ) -> bool:
        """Check if user has specific permission"""
        
        try:
            # Get user role definition
            role_def = self.role_registry.get_role_definition(user_context.role)
            if not role_def:
                self.logger.warning(f"Unknown role: {user_context.role}")
                return False
            
            # Check if permission is granted
            has_permission = permission in role_def.permissions
            
            # Special case: SUDO permission overrides everything
            if not has_permission and Permission.SUDO in role_def.permissions:
                has_permission = True
                self.logger.warning(
                    f"SUDO permission used by {user_context.username} "
                    f"for {permission.value}"
                )
            
            # Log permission check
            self.audit_logger.log_security_event(
                event_type=AuditEventType.DATA_ACCESS if has_permission else AuditEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
                category="ACCESS_CONTROL",
                description=f"Permission check: {permission.value}",
                user_id=user_context.user_id,
                username=user_context.username,
                user_role=user_context.role.value,
                ip_address=user_context.ip_address,
                user_agent=user_context.user_agent,
                resource_type=resource_type,
                resource_id=resource_id,
                success=has_permission,
                failure_reason="Insufficient permissions" if not has_permission else None,
                event_details={
                    'permission': permission.value,
                    'user_role': user_context.role.value,
                    'permission_granted': has_permission
                }
            )
            
            return has_permission
            
        except Exception as e:
            self.logger.error(f"Permission check failed: {e}")
            return False
    
    def require_permission(
        self,
        user_context: SecurityContext,
        permission: Permission,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None
    ) -> None:
        """Require specific permission or raise AccessDeniedError"""
        
        if not self.check_permission(user_context, permission, resource_id, resource_type):
            error_msg = f"Access denied: {permission.value} permission required"
            self.logger.warning(
                f"Access denied for user {user_context.username}: "
                f"{permission.value} on {resource_type}:{resource_id}"
            )
            raise AccessDeniedError(error_msg)
    
    def get_user_permissions(self, user_context: SecurityContext) -> Set[Permission]:
        """Get all permissions for user"""
        
        role_def = self.role_registry.get_role_definition(user_context.role)
        if not role_def:
            return set()
        
        return role_def.permissions.copy()
    
    def can_access_resource(
        self,
        user_context: SecurityContext,
        resource_type: str,
        resource_id: str,
        action: str = "READ"
    ) -> bool:
        """Check if user can access specific resource"""
        
        # Map action to permission
        permission_mapping = {
            "CREATE": {
                "PROJECT": Permission.CREATE_PROJECT,
                "SPEC": Permission.CREATE_SPEC,
                "DATA_SOURCE": Permission.CREATE_DATA_SOURCE,
                "AGENT": Permission.CREATE_AGENT,
                "DEPLOYMENT": Permission.CREATE_DEPLOYMENT,
                "USER": Permission.CREATE_USER,
            },
            "READ": {
                "PROJECT": Permission.READ_PROJECT,
                "SPEC": Permission.READ_SPEC,
                "DATA_SOURCE": Permission.READ_DATA_SOURCE,
                "AGENT": Permission.READ_AGENT,
                "DEPLOYMENT": Permission.READ_DEPLOYMENT,
                "USER": Permission.READ_USER,
            },
            "UPDATE": {
                "PROJECT": Permission.UPDATE_PROJECT,
                "SPEC": Permission.UPDATE_SPEC,
                "DATA_SOURCE": Permission.UPDATE_DATA_SOURCE,
                "AGENT": Permission.UPDATE_AGENT,
                "DEPLOYMENT": Permission.UPDATE_DEPLOYMENT,
                "USER": Permission.UPDATE_USER,
            },
            "DELETE": {
                "PROJECT": Permission.DELETE_PROJECT,
                "SPEC": Permission.DELETE_SPEC,
                "DATA_SOURCE": Permission.DELETE_DATA_SOURCE,
                "AGENT": Permission.DELETE_AGENT,
                "DEPLOYMENT": Permission.DELETE_DEPLOYMENT,
                "USER": Permission.DELETE_USER,
            }
        }
        
        permission = permission_mapping.get(action.upper(), {}).get(resource_type.upper())
        if not permission:
            self.logger.warning(f"Unknown permission mapping: {action} on {resource_type}")
            return False
        
        return self.check_permission(
            user_context, permission, resource_id, resource_type
        )
    
    def assign_role(
        self,
        user_id: uuid.UUID,
        role: SecurityRole,
        assigned_by: SecurityContext
    ) -> None:
        """Assign role to user (requires admin permission)"""
        
        # Check if current user can manage users
        self.require_permission(assigned_by, Permission.MANAGE_USERS)
        
        # Log role assignment
        self.audit_logger.log_security_event(
            event_type=AuditEventType.ROLE_ASSIGNED,
            category="ACCESS_CONTROL",
            description=f"Role assigned: {role.value}",
            user_id=assigned_by.user_id,
            username=assigned_by.username,
            user_role=assigned_by.role.value,
            ip_address=assigned_by.ip_address,
            user_agent=assigned_by.user_agent,
            resource_type="USER",
            resource_id=str(user_id),
            success=True,
            event_details={
                'assigned_role': role.value,
                'target_user_id': str(user_id),
                'assigned_by': assigned_by.username
            }
        )
        
        self.logger.info(f"Role {role.value} assigned to user {user_id} by {assigned_by.username}")


# Decorator functions for permission checking
def require_role(required_role: SecurityRole):
    """Decorator to require specific role"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = get_current_user_context()
            if not context:
                raise AccessDeniedError("No authentication context")
            
            if context.role != required_role and Permission.SUDO not in context.permissions:
                raise AccessDeniedError(f"Role {required_role.value} required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(required_permission: Permission):
    """Decorator to require specific permission"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = get_current_user_context()
            if not context:
                raise AccessDeniedError("No authentication context")
            
            # This would need to be integrated with a global RBAC instance
            # For now, check if permission is in context
            if required_permission not in context.permissions and Permission.SUDO not in context.permissions:
                raise AccessDeniedError(f"Permission {required_permission.value} required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def check_permission(
    user_context: SecurityContext,
    permission: Permission,
    resource_id: Optional[str] = None,
    resource_type: Optional[str] = None
) -> bool:
    """Global function to check permission"""
    # This would need access to a global RBAC instance
    # For now, check if permission is in context
    role_registry = RoleRegistry()
    role_def = role_registry.get_role_definition(user_context.role)
    
    if not role_def:
        return False
    
    return permission in role_def.permissions or Permission.SUDO in role_def.permissions


# Additional utility functions
def get_role_hierarchy() -> Dict[SecurityRole, int]:
    """Get role hierarchy levels (higher number = more privileges)"""
    return {
        SecurityRole.VIEWER: 1,
        SecurityRole.AUDITOR: 2,
        SecurityRole.EDITOR: 3,
        SecurityRole.ADMIN: 4,
        SecurityRole.SECURITY_ADMIN: 5,
    }


def role_has_higher_privilege(role1: SecurityRole, role2: SecurityRole) -> bool:
    """Check if role1 has higher privilege than role2"""
    hierarchy = get_role_hierarchy()
    return hierarchy.get(role1, 0) > hierarchy.get(role2, 0)


def can_manage_user_role(manager_role: SecurityRole, target_role: SecurityRole) -> bool:
    """Check if manager can manage user with target role"""
    # Admins can manage all roles except SECURITY_ADMIN
    if manager_role == SecurityRole.ADMIN:
        return target_role != SecurityRole.SECURITY_ADMIN
    
    # Security admins can manage all roles
    if manager_role == SecurityRole.SECURITY_ADMIN:
        return True
    
    # Others cannot manage roles
    return False