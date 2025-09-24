"""
DafelHub Security Module
SOC 2 Type II Compliant Security System
Financial Services Grade Security Implementation
"""

from .authentication import (
    AuthenticationManager,
    JWTManager,
    TwoFactorAuthManager,
    SecurityContext,
    create_security_context,
    get_current_user_context,
    AuthenticationError,
    AccountLockedException,
    TwoFactorRequiredException
)

# New JWT Management System
from .jwt_manager import (
    JWTManager as EnterpriseJWTManager,
    TokenBlacklistManager,
    TokenType,
    TokenStatus,
    TokenClaims,
    TokenPair,
    JWTSecurityError
)

# Role-Based Access Control System
from .rbac_system import (
    RBACManager,
    Permission,
    ResourceType,
    PermissionGrant,
    RoleDefinition,
    RolePermissionError,
    AccessDeniedError as RBACAccessDeniedError,
    get_rbac_manager,
    require_admin,
    require_2fa
)

# Multi-Factor Authentication System  
from .mfa_system import (
    MFASystemManager,
    MFAType,
    MFAStatus,
    MFASetupResult,
    BackupCode,
    MFAError,
    get_mfa_manager
)

from .audit import (
    AuditLogger,
    AuditEventType,
    SecurityEvent,
    ComplianceReporter,
    SecurityMetricsCollector
)

from .rbac import (
    RoleBasedAccessControl,
    SecurityRole,
    Permission,
    AccessDeniedError,
    check_permission,
    require_role
)

from .monitoring import (
    SecurityMonitor,
    ThreatDetector,
    AccountLockoutManager,
    SecurityDashboard,
    AlertManager
)

from .compliance import (
    ComplianceManager,
    SOCCompliance,
    SecurityPolicy,
    DataClassification,
    RetentionPolicy
)

# Recovery and Backup Systems
from .audit_trail import (
    PersistentAuditTrail,
    AuditTrailEntry,
    AuditTrailState,
    get_persistent_audit_trail,
    audit_event,
    audit_security_event
)

from .recovery_system import (
    VaultRecoverySystem,
    RecoveryKeyInfo,
    VaultState,
    get_vault_recovery_system,
    backup_vault,
    restore_vault,
    verify_backup
)

from .config_backup import (
    ConfigurationBackupSystem,
    ConfigurationSnapshot,
    ConfigurationItem,
    get_config_backup_system,
    create_config_backup,
    restore_config_backup,
    list_config_backups
)

from .key_recovery import (
    KeyRecoverySystem,
    KeyBackupInfo,
    RecoveryShare,
    ShamirSecretSharing,
    get_key_recovery_system,
    backup_current_key,
    recover_key_by_id,
    verify_all_keys
)

__all__ = [
    # Core Authentication
    'AuthenticationManager',
    'JWTManager', 
    'TwoFactorAuthManager',
    'SecurityContext',
    'create_security_context',
    'get_current_user_context',
    'AuthenticationError',
    'AccountLockedException', 
    'TwoFactorRequiredException',
    
    # Enterprise JWT Management
    'EnterpriseJWTManager',
    'TokenBlacklistManager',
    'TokenType',
    'TokenStatus', 
    'TokenClaims',
    'TokenPair',
    'JWTSecurityError',
    
    # Role-Based Access Control
    'RBACManager',
    'Permission',
    'ResourceType',
    'PermissionGrant',
    'RoleDefinition',
    'RolePermissionError',
    'RBACAccessDeniedError',
    'get_rbac_manager',
    'require_admin',
    'require_2fa',
    
    # Multi-Factor Authentication
    'MFASystemManager',
    'MFAType',
    'MFAStatus',
    'MFASetupResult',
    'BackupCode',
    'MFAError',
    'get_mfa_manager',
    
    # Audit & Logging
    'AuditLogger',
    'AuditEventType',
    'SecurityEvent',
    'ComplianceReporter',
    'SecurityMetricsCollector',
    
    # Access Control
    'RoleBasedAccessControl',
    'SecurityRole',
    'Permission',
    'AccessDeniedError',
    'check_permission',
    'require_role',
    
    # Monitoring
    'SecurityMonitor',
    'ThreatDetector',
    'AccountLockoutManager', 
    'SecurityDashboard',
    'AlertManager',
    
    # Compliance
    'ComplianceManager',
    'SOCCompliance',
    'SecurityPolicy',
    'DataClassification',
    'RetentionPolicy',
    
    # Recovery and Backup Systems
    'PersistentAuditTrail',
    'AuditTrailEntry', 
    'AuditTrailState',
    'get_persistent_audit_trail',
    'audit_event',
    'audit_security_event',
    
    # Vault Recovery
    'VaultRecoverySystem',
    'RecoveryKeyInfo',
    'VaultState', 
    'get_vault_recovery_system',
    'backup_vault',
    'restore_vault',
    'verify_backup',
    
    # Configuration Backup
    'ConfigurationBackupSystem',
    'ConfigurationSnapshot',
    'ConfigurationItem',
    'get_config_backup_system',
    'create_config_backup',
    'restore_config_backup',
    'list_config_backups',
    
    # Key Recovery
    'KeyRecoverySystem',
    'KeyBackupInfo',
    'RecoveryShare',
    'ShamirSecretSharing',
    'get_key_recovery_system',
    'backup_current_key',
    'recover_key_by_id',
    'verify_all_keys'
]