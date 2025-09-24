"""
DafelHub Enterprise Database Models
SQLAlchemy 2.0 async models with enterprise features

This module provides enterprise-grade database models with:
- SQLAlchemy 2.0 async support
- Automatic audit trail integration
- Security-aware base classes
- Connection pool integration
- Performance monitoring
- Validation framework
"""

from .base import (
    EnterpriseBase,
    EnterpriseBaseModel,
    EnterpriseRepository,
    TimestampMixin,
    AuditMixin,
    SoftDeleteMixin,
    StatusMixin,
    MetadataMixin,
    RecordStatus,
    AuditAction,
    ModelValidationError,
    create_all_tables,
    create_all_tables_async,
    get_repository
)

# Import model classes
from .user import User, UserRole, UserPermission, get_user_repository

# Export all public components
__all__ = [
    # Base classes and mixins
    'EnterpriseBase',
    'EnterpriseBaseModel',
    'EnterpriseRepository',
    'TimestampMixin',
    'AuditMixin',
    'SoftDeleteMixin',
    'StatusMixin',
    'MetadataMixin',
    
    # Enums and types
    'RecordStatus',
    'AuditAction',
    'ModelValidationError',
    
    # Utility functions
    'create_all_tables',
    'create_all_tables_async',
    'get_repository',
    
    # Model classes
    'User',
    'UserRole',
    'UserPermission',
    
    # Repository functions
    'get_user_repository',
]

# Version information
__version__ = '1.0.0'
__author__ = 'DatabaseAgent'