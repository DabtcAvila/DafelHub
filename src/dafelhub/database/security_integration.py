"""
Database Security Integration
Integration between DatabaseAgent and SecurityAgent systems for:
- Secure credential management via EnterpriseVaultManager
- User authentication and authorization for database access
- Audit trail for all database operations
- Connection security and encryption
"""

import asyncio
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.connections import ConnectionConfig, IDataSourceConnector
from dafelhub.core.enterprise_vault import EnterpriseVaultManager, EncryptedData
from dafelhub.database.connectors.connection_factory import DatabaseType, connection_factory
from dafelhub.security.authentication import SecurityContext, JWTManager, AuthenticationError
from dafelhub.security.audit import AuditLogger, AuditEventType, ThreatLevel
from dafelhub.security.models import SecurityRole


logger = get_logger(__name__)


class DatabasePermission(Enum):
    """Database operation permissions"""
    READ = "db:read"
    WRITE = "db:write"
    DELETE = "db:delete"
    ADMIN = "db:admin"
    SCHEMA = "db:schema"
    BACKUP = "db:backup"
    RESTORE = "db:restore"
    CREATE_DATABASE = "db:create"
    DROP_DATABASE = "db:drop"


class AccessLevel(Enum):
    """Database access levels"""
    VIEWER = "viewer"
    ANALYST = "analyst"
    DEVELOPER = "developer"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


@dataclass
class DatabaseCredential:
    """Secure database credential structure"""
    credential_id: str
    database_type: DatabaseType
    host: str
    port: int
    database: str
    username: str
    encrypted_password: EncryptedData
    ssl_enabled: bool = True
    connection_params: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'credential_id': self.credential_id,
            'database_type': self.database_type.value,
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'username': self.username,
            'encrypted_password': {
                'encrypted': self.encrypted_password.encrypted,
                'iv': self.encrypted_password.iv,
                'tag': self.encrypted_password.tag,
                'salt': self.encrypted_password.salt,
                'algorithm': self.encrypted_password.algorithm,
                'version': self.encrypted_password.version
            },
            'ssl_enabled': self.ssl_enabled,
            'connection_params': self.connection_params,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by': self.created_by,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabaseCredential':
        """Create from dictionary"""
        encrypted_pwd_data = data['encrypted_password']
        encrypted_password = EncryptedData(
            encrypted=encrypted_pwd_data['encrypted'],
            iv=encrypted_pwd_data['iv'],
            tag=encrypted_pwd_data['tag'],
            salt=encrypted_pwd_data['salt'],
            algorithm=encrypted_pwd_data['algorithm'],
            version=encrypted_pwd_data['version']
        )
        
        return cls(
            credential_id=data['credential_id'],
            database_type=DatabaseType(data['database_type']),
            host=data['host'],
            port=data['port'],
            database=data['database'],
            username=data['username'],
            encrypted_password=encrypted_password,
            ssl_enabled=data.get('ssl_enabled', True),
            connection_params=data.get('connection_params', {}),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            created_by=data.get('created_by'),
            tags=data.get('tags', [])
        )


@dataclass
class DatabaseAccessPolicy:
    """Database access control policy"""
    policy_id: str
    name: str
    description: str
    database_patterns: List[str]  # Patterns for database names
    permissions: List[DatabasePermission]
    access_level: AccessLevel
    roles: List[SecurityRole] = field(default_factory=list)
    users: List[str] = field(default_factory=list)  # User IDs
    ip_restrictions: List[str] = field(default_factory=list)
    time_restrictions: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if policy is expired"""
        return self.expires_at is not None and datetime.now() > self.expires_at
    
    def allows_access(self, user_context: SecurityContext, 
                     database_name: str, permission: DatabasePermission) -> bool:
        """Check if policy allows access"""
        if self.is_expired():
            return False
        
        # Check role-based access
        if self.roles and user_context.role not in self.roles:
            return False
        
        # Check user-specific access
        if self.users and str(user_context.user_id) not in self.users:
            return False
        
        # Check permission
        if permission not in self.permissions:
            return False
        
        # Check database pattern matching
        if self.database_patterns:
            import re
            matches = any(
                re.match(pattern.replace('*', '.*'), database_name)
                for pattern in self.database_patterns
            )
            if not matches:
                return False
        
        # Check IP restrictions
        if self.ip_restrictions and user_context.ip_address not in self.ip_restrictions:
            return False
        
        return True


class DatabaseSecurityManager(LoggerMixin):
    """
    Database Security Manager
    Integrates database access with SecurityAgent systems:
    - Credential management via EnterpriseVaultManager
    - Authentication via SecurityContext
    - Authorization via access policies
    - Comprehensive audit logging
    """
    
    def __init__(self):
        self.vault = EnterpriseVaultManager()
        self.jwt_manager = JWTManager()
        self.audit_logger = AuditLogger()
        
        # In-memory storage for demonstration (use persistent storage in production)
        self._credentials: Dict[str, DatabaseCredential] = {}
        self._policies: Dict[str, DatabaseAccessPolicy] = {}
        self._active_connections: Dict[str, IDataSourceConnector] = {}
        
        # Default policies
        self._initialize_default_policies()
        
        self.logger.info("Database Security Manager initialized")
    
    def _initialize_default_policies(self) -> None:
        """Initialize default access policies"""
        # Admin policy - full access
        admin_policy = DatabaseAccessPolicy(
            policy_id="default_admin",
            name="Database Administrator",
            description="Full database access for administrators",
            database_patterns=["*"],
            permissions=list(DatabasePermission),
            access_level=AccessLevel.ADMIN,
            roles=[SecurityRole.SUPER_ADMIN, SecurityRole.ADMIN]
        )
        
        # Developer policy - read/write access
        dev_policy = DatabaseAccessPolicy(
            policy_id="default_developer",
            name="Developer Access",
            description="Read/write access for developers",
            database_patterns=["dev_*", "test_*", "staging_*"],
            permissions=[
                DatabasePermission.READ,
                DatabasePermission.WRITE,
                DatabasePermission.SCHEMA
            ],
            access_level=AccessLevel.DEVELOPER,
            roles=[SecurityRole.DEVELOPER, SecurityRole.DATA_ENGINEER]
        )
        
        # Analyst policy - read-only access
        analyst_policy = DatabaseAccessPolicy(
            policy_id="default_analyst",
            name="Data Analyst",
            description="Read-only access for analysts",
            database_patterns=["analytics_*", "reporting_*"],
            permissions=[DatabasePermission.READ],
            access_level=AccessLevel.ANALYST,
            roles=[SecurityRole.ANALYST, SecurityRole.DATA_SCIENTIST]
        )
        
        # Viewer policy - very limited read access
        viewer_policy = DatabaseAccessPolicy(
            policy_id="default_viewer",
            name="Read-Only Viewer",
            description="Limited read access for viewers",
            database_patterns=["public_*", "dashboard_*"],
            permissions=[DatabasePermission.READ],
            access_level=AccessLevel.VIEWER,
            roles=[SecurityRole.VIEWER]
        )
        
        self._policies.update({
            admin_policy.policy_id: admin_policy,
            dev_policy.policy_id: dev_policy,
            analyst_policy.policy_id: analyst_policy,
            viewer_policy.policy_id: viewer_policy
        })
    
    async def store_credential(self, credential: DatabaseCredential,
                             security_context: SecurityContext) -> str:
        """Store database credential securely"""
        try:
            # Audit the operation
            await self.audit_logger.log_event(
                event_type=AuditEventType.CREDENTIAL_STORED,
                user_id=str(security_context.user_id),
                resource=f"database:{credential.host}:{credential.database}",
                details={
                    'credential_id': credential.credential_id,
                    'database_type': credential.database_type.value,
                    'host': credential.host,
                    'database': credential.database,
                    'username': credential.username,
                    'ssl_enabled': credential.ssl_enabled
                },
                risk_level=ThreatLevel.LOW,
                ip_address=security_context.ip_address,
                user_agent=security_context.user_agent
            )
            
            # Store credential
            credential.created_by = str(security_context.user_id)
            credential.updated_at = datetime.now()
            self._credentials[credential.credential_id] = credential
            
            self.logger.info(f"Database credential stored: {credential.credential_id}",
                           extra_data={
                               'database_type': credential.database_type.value,
                               'host': credential.host,
                               'database': credential.database,
                               'stored_by': str(security_context.user_id)
                           })
            
            return credential.credential_id
            
        except Exception as e:
            self.logger.error(f"Failed to store credential: {str(e)}")
            raise
    
    async def get_credential(self, credential_id: str,
                           security_context: SecurityContext) -> Optional[DatabaseCredential]:
        """Get database credential with access control"""
        try:
            # Check if credential exists
            if credential_id not in self._credentials:
                return None
            
            credential = self._credentials[credential_id]
            
            # Check access permissions
            if not await self._check_credential_access(credential, security_context):
                await self.audit_logger.log_event(
                    event_type=AuditEventType.ACCESS_DENIED,
                    user_id=str(security_context.user_id),
                    resource=f"credential:{credential_id}",
                    details={'reason': 'Insufficient permissions'},
                    risk_level=ThreatLevel.MEDIUM,
                    ip_address=security_context.ip_address,
                    user_agent=security_context.user_agent
                )
                raise AuthenticationError("Insufficient permissions to access credential")
            
            # Audit successful access
            await self.audit_logger.log_event(
                event_type=AuditEventType.CREDENTIAL_ACCESSED,
                user_id=str(security_context.user_id),
                resource=f"credential:{credential_id}",
                details={
                    'database_type': credential.database_type.value,
                    'host': credential.host,
                    'database': credential.database
                },
                risk_level=ThreatLevel.LOW,
                ip_address=security_context.ip_address,
                user_agent=security_context.user_agent
            )
            
            return credential
            
        except Exception as e:
            self.logger.error(f"Failed to get credential {credential_id}: {str(e)}")
            raise
    
    async def create_secure_connection(self, credential_id: str,
                                     security_context: SecurityContext) -> IDataSourceConnector:
        """Create secure database connection using stored credentials"""
        try:
            # Get credential with access control
            credential = await self.get_credential(credential_id, security_context)
            if not credential:
                raise AuthenticationError(f"Credential not found: {credential_id}")
            
            # Decrypt password
            decrypted_password = self.vault.decrypt_data(credential.encrypted_password)
            
            # Create connection configuration
            connection_config = ConnectionConfig(
                id=f"secure_conn_{uuid.uuid4()}",
                host=credential.host,
                port=credential.port,
                database=credential.database,
                username=credential.username,
                password=decrypted_password,
                ssl=credential.ssl_enabled,
                connection_timeout=30000,
                query_timeout=60000,
                pool_size=10,
                configuration={
                    **credential.connection_params,
                    'security_context': {
                        'user_id': str(security_context.user_id),
                        'username': security_context.username,
                        'session_id': str(security_context.session_id),
                        'access_level': self._get_user_access_level(security_context).value
                    },
                    'credential_id': credential_id,
                    'audit_enabled': True
                }
            )
            
            # Create connector
            connector = connection_factory.create_connector(connection_config, credential.database_type)
            
            # Wrap with security monitoring
            secure_connector = SecureConnectorWrapper(
                connector=connector,
                security_context=security_context,
                credential=credential,
                security_manager=self
            )
            
            # Store active connection
            self._active_connections[connector.id] = secure_connector
            
            # Audit connection creation
            await self.audit_logger.log_event(
                event_type=AuditEventType.DATABASE_CONNECTION_CREATED,
                user_id=str(security_context.user_id),
                resource=f"connection:{connector.id}",
                details={
                    'credential_id': credential_id,
                    'database_type': credential.database_type.value,
                    'host': credential.host,
                    'database': credential.database,
                    'connection_id': connector.id
                },
                risk_level=ThreatLevel.LOW,
                ip_address=security_context.ip_address,
                user_agent=security_context.user_agent
            )
            
            self.logger.info(f"Secure database connection created: {connector.id}",
                           extra_data={
                               'credential_id': credential_id,
                               'user_id': str(security_context.user_id),
                               'database_type': credential.database_type.value
                           })
            
            return secure_connector
            
        except Exception as e:
            self.logger.error(f"Failed to create secure connection: {str(e)}")
            raise
    
    async def create_credential_from_config(self, config: ConnectionConfig,
                                          security_context: SecurityContext,
                                          tags: List[str] = None) -> str:
        """Create credential from connection config"""
        try:
            # Encrypt password
            encrypted_password = self.vault.encrypt_data(config.password)
            
            # Create credential
            credential = DatabaseCredential(
                credential_id=f"cred_{uuid.uuid4()}",
                database_type=DatabaseType.POSTGRESQL,  # Default, should be detected
                host=config.host,
                port=config.port,
                database=config.database,
                username=config.username,
                encrypted_password=encrypted_password,
                ssl_enabled=config.ssl,
                connection_params=config.configuration,
                tags=tags or []
            )
            
            # Auto-detect database type if possible
            try:
                from dafelhub.database.connectors.connection_factory import detect_database_type
                detection_result = detect_database_type(host=config.host, port=config.port)
                if detection_result.database_type != DatabaseType.UNKNOWN:
                    credential.database_type = detection_result.database_type
            except:
                pass  # Use default if detection fails
            
            # Store credential
            credential_id = await self.store_credential(credential, security_context)
            
            return credential_id
            
        except Exception as e:
            self.logger.error(f"Failed to create credential from config: {str(e)}")
            raise
    
    def add_access_policy(self, policy: DatabaseAccessPolicy,
                         security_context: SecurityContext) -> None:
        """Add database access policy"""
        # Only admins can add policies
        if security_context.role not in [SecurityRole.ADMIN, SecurityRole.SUPER_ADMIN]:
            raise AuthenticationError("Insufficient permissions to add access policy")
        
        policy.created_by = str(security_context.user_id)
        self._policies[policy.policy_id] = policy
        
        self.logger.info(f"Access policy added: {policy.policy_id}",
                        extra_data={
                            'policy_name': policy.name,
                            'access_level': policy.access_level.value,
                            'created_by': str(security_context.user_id)
                        })
    
    def get_user_permissions(self, security_context: SecurityContext,
                           database_name: str) -> List[DatabasePermission]:
        """Get user permissions for specific database"""
        permissions = []
        
        for policy in self._policies.values():
            if policy.allows_access(security_context, database_name, DatabasePermission.READ):
                permissions.extend(policy.permissions)
        
        # Remove duplicates
        return list(set(permissions))
    
    def check_permission(self, security_context: SecurityContext,
                        database_name: str, permission: DatabasePermission) -> bool:
        """Check if user has specific permission"""
        for policy in self._policies.values():
            if policy.allows_access(security_context, database_name, permission):
                return True
        return False
    
    async def list_user_credentials(self, security_context: SecurityContext) -> List[Dict[str, Any]]:
        """List credentials accessible to user"""
        accessible_credentials = []
        
        for credential in self._credentials.values():
            if await self._check_credential_access(credential, security_context):
                accessible_credentials.append({
                    'credential_id': credential.credential_id,
                    'database_type': credential.database_type.value,
                    'host': credential.host,
                    'port': credential.port,
                    'database': credential.database,
                    'username': credential.username,
                    'ssl_enabled': credential.ssl_enabled,
                    'tags': credential.tags,
                    'created_at': credential.created_at.isoformat(),
                    'updated_at': credential.updated_at.isoformat()
                })
        
        return accessible_credentials
    
    async def cleanup_expired_connections(self) -> None:
        """Clean up expired database connections"""
        expired_connections = []
        
        for conn_id, connector in self._active_connections.items():
            if isinstance(connector, SecureConnectorWrapper):
                if connector.is_expired():
                    expired_connections.append(conn_id)
        
        for conn_id in expired_connections:
            try:
                connector = self._active_connections[conn_id]
                await connector.disconnect()
                del self._active_connections[conn_id]
                
                self.logger.info(f"Expired connection cleaned up: {conn_id}")
            except Exception as e:
                self.logger.error(f"Error cleaning up connection {conn_id}: {str(e)}")
    
    # Private methods
    
    async def _check_credential_access(self, credential: DatabaseCredential,
                                     security_context: SecurityContext) -> bool:
        """Check if user can access credential"""
        # Super admin can access everything
        if security_context.role == SecurityRole.SUPER_ADMIN:
            return True
        
        # Admin can access most things
        if security_context.role == SecurityRole.ADMIN:
            return True
        
        # Check if user created the credential
        if credential.created_by == str(security_context.user_id):
            return True
        
        # Check access policies
        return any(
            policy.allows_access(security_context, credential.database, DatabasePermission.READ)
            for policy in self._policies.values()
        )
    
    def _get_user_access_level(self, security_context: SecurityContext) -> AccessLevel:
        """Determine user's access level"""
        if security_context.role == SecurityRole.SUPER_ADMIN:
            return AccessLevel.SUPER_ADMIN
        elif security_context.role == SecurityRole.ADMIN:
            return AccessLevel.ADMIN
        elif security_context.role in [SecurityRole.DEVELOPER, SecurityRole.DATA_ENGINEER]:
            return AccessLevel.DEVELOPER
        elif security_context.role in [SecurityRole.ANALYST, SecurityRole.DATA_SCIENTIST]:
            return AccessLevel.ANALYST
        else:
            return AccessLevel.VIEWER


class SecureConnectorWrapper(LoggerMixin):
    """
    Secure wrapper for database connectors with:
    - Security context enforcement
    - Query auditing
    - Permission checking
    - Connection monitoring
    """
    
    def __init__(self, connector: IDataSourceConnector,
                 security_context: SecurityContext,
                 credential: DatabaseCredential,
                 security_manager: DatabaseSecurityManager):
        self.connector = connector
        self.security_context = security_context
        self.credential = credential
        self.security_manager = security_manager
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.session_timeout = timedelta(hours=2)  # 2 hour timeout
        
        # Delegate basic properties
        self.id = connector.id
        self.config = connector.config
        self.status = connector.status
        self.is_healthy = connector.is_healthy
    
    def is_expired(self) -> bool:
        """Check if connection session is expired"""
        return datetime.now() - self.last_activity > self.session_timeout
    
    async def connect(self) -> None:
        """Connect with security monitoring"""
        if self.is_expired():
            raise AuthenticationError("Connection session expired")
        
        await self.connector.connect()
        self.last_activity = datetime.now()
        
        # Audit connection
        await self.security_manager.audit_logger.log_event(
            event_type=AuditEventType.DATABASE_CONNECTION_ESTABLISHED,
            user_id=str(self.security_context.user_id),
            resource=f"database:{self.credential.host}:{self.credential.database}",
            details={
                'connection_id': self.id,
                'database_type': self.credential.database_type.value
            },
            risk_level=ThreatLevel.LOW,
            ip_address=self.security_context.ip_address,
            user_agent=self.security_context.user_agent
        )
    
    async def disconnect(self) -> None:
        """Disconnect with security monitoring"""
        await self.connector.disconnect()
        
        # Audit disconnection
        await self.security_manager.audit_logger.log_event(
            event_type=AuditEventType.DATABASE_CONNECTION_CLOSED,
            user_id=str(self.security_context.user_id),
            resource=f"database:{self.credential.host}:{self.credential.database}",
            details={'connection_id': self.id},
            risk_level=ThreatLevel.LOW,
            ip_address=self.security_context.ip_address,
            user_agent=self.security_context.user_agent
        )
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection with security checks"""
        if self.is_expired():
            raise AuthenticationError("Connection session expired")
        
        self.last_activity = datetime.now()
        return await self.connector.test_connection()
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute query with security checks and auditing"""
        if self.is_expired():
            raise AuthenticationError("Connection session expired")
        
        # Determine required permission based on query type
        query_upper = query.strip().upper()
        if query_upper.startswith('SELECT'):
            required_permission = DatabasePermission.READ
        elif query_upper.startswith(('INSERT', 'UPDATE')):
            required_permission = DatabasePermission.WRITE
        elif query_upper.startswith('DELETE'):
            required_permission = DatabasePermission.DELETE
        elif query_upper.startswith(('CREATE', 'DROP', 'ALTER')):
            required_permission = DatabasePermission.SCHEMA
        else:
            required_permission = DatabasePermission.ADMIN
        
        # Check permissions
        if not self.security_manager.check_permission(
            self.security_context, 
            self.credential.database, 
            required_permission
        ):
            await self.security_manager.audit_logger.log_event(
                event_type=AuditEventType.ACCESS_DENIED,
                user_id=str(self.security_context.user_id),
                resource=f"database:{self.credential.host}:{self.credential.database}",
                details={
                    'query_type': query_upper.split()[0],
                    'required_permission': required_permission.value,
                    'connection_id': self.id
                },
                risk_level=ThreatLevel.HIGH,
                ip_address=self.security_context.ip_address,
                user_agent=self.security_context.user_agent
            )
            raise AuthenticationError(f"Insufficient permissions for {required_permission.value}")
        
        # Execute query
        try:
            result = await self.connector.execute_query(query, params)
            self.last_activity = datetime.now()
            
            # Audit successful query
            await self.security_manager.audit_logger.log_event(
                event_type=AuditEventType.DATABASE_QUERY_EXECUTED,
                user_id=str(self.security_context.user_id),
                resource=f"database:{self.credential.host}:{self.credential.database}",
                details={
                    'query_type': query_upper.split()[0],
                    'success': result.success if hasattr(result, 'success') else True,
                    'execution_time': result.execution_time if hasattr(result, 'execution_time') else 0,
                    'rows_affected': getattr(result, 'metadata', {}).get('rows_affected', 0),
                    'connection_id': self.id
                },
                risk_level=ThreatLevel.LOW,
                ip_address=self.security_context.ip_address,
                user_agent=self.security_context.user_agent
            )
            
            return result
            
        except Exception as e:
            # Audit failed query
            await self.security_manager.audit_logger.log_event(
                event_type=AuditEventType.DATABASE_QUERY_FAILED,
                user_id=str(self.security_context.user_id),
                resource=f"database:{self.credential.host}:{self.credential.database}",
                details={
                    'query_type': query_upper.split()[0],
                    'error': str(e),
                    'connection_id': self.id
                },
                risk_level=ThreatLevel.MEDIUM,
                ip_address=self.security_context.ip_address,
                user_agent=self.security_context.user_agent
            )
            raise
    
    async def get_schema_info(self, schema_name: str = None) -> Dict[str, Any]:
        """Get schema info with security checks"""
        if self.is_expired():
            raise AuthenticationError("Connection session expired")
        
        # Check schema permission
        if not self.security_manager.check_permission(
            self.security_context, 
            self.credential.database, 
            DatabasePermission.SCHEMA
        ):
            raise AuthenticationError("Insufficient permissions for schema access")
        
        self.last_activity = datetime.now()
        return await self.connector.get_schema_info(schema_name)
    
    # Delegate other methods to the wrapped connector
    def __getattr__(self, name):
        """Delegate unknown attributes to wrapped connector"""
        if hasattr(self.connector, name):
            attr = getattr(self.connector, name)
            if callable(attr):
                # For async methods, add session check
                if asyncio.iscoroutinefunction(attr):
                    async def wrapper(*args, **kwargs):
                        if self.is_expired():
                            raise AuthenticationError("Connection session expired")
                        self.last_activity = datetime.now()
                        return await attr(*args, **kwargs)
                    return wrapper
                else:
                    def wrapper(*args, **kwargs):
                        if self.is_expired():
                            raise AuthenticationError("Connection session expired")
                        self.last_activity = datetime.now()
                        return attr(*args, **kwargs)
                    return wrapper
            return attr
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# Global security manager instance
database_security_manager = DatabaseSecurityManager()


# Convenience functions
async def create_secure_database_connection(credential_id: str,
                                          security_context: SecurityContext) -> IDataSourceConnector:
    """Create secure database connection using global security manager"""
    return await database_security_manager.create_secure_connection(credential_id, security_context)


async def store_database_credential(config: ConnectionConfig,
                                  security_context: SecurityContext,
                                  tags: List[str] = None) -> str:
    """Store database credential using global security manager"""
    return await database_security_manager.create_credential_from_config(config, security_context, tags)


def check_database_permission(security_context: SecurityContext,
                            database_name: str, 
                            permission: DatabasePermission) -> bool:
    """Check database permission using global security manager"""
    return database_security_manager.check_permission(security_context, database_name, permission)