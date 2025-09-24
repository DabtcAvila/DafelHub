"""
DafelHub Enterprise Database Models Base
SQLAlchemy 2.0 async base classes and utilities
Enterprise-grade ORM foundation with security integration

Features:
- SQLAlchemy 2.0 async support
- Enterprise audit trail integration
- Automatic timestamp management
- Security-aware base models
- Connection pool integration
- Transaction context management
- Performance monitoring hooks
- Validation and serialization utilities

TODO: [DB-013] Implement enterprise base model classes - @DatabaseAgent - 2024-09-24
TODO: [DB-014] Add audit trail integration - @DatabaseAgent - 2024-09-24
TODO: [DB-015] Create serialization utilities - @DatabaseAgent - 2024-09-24
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, ClassVar
from dataclasses import dataclass
from enum import Enum
import json

from sqlalchemy import (
    MetaData, Column, String, DateTime, Boolean, Text, Integer,
    BigInteger, func, event, inspect
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.sql import Select
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.security.audit_trail import get_persistent_audit_trail
from dafelhub.database.connection_manager import get_connection_manager


logger = get_logger(__name__)

# Type variables for generic base classes
ModelType = TypeVar("ModelType", bound="EnterpriseBaseModel")
T = TypeVar("T")


class RecordStatus(Enum):
    """Record status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    ARCHIVED = "archived"
    PENDING = "pending"


class AuditAction(Enum):
    """Database audit actions"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    BULK_UPDATE = "bulk_update"
    BULK_DELETE = "bulk_delete"


@dataclass
class ModelValidationError:
    """Model validation error"""
    field: str
    message: str
    code: str
    value: Any = None


class EnterpriseMetaData(MetaData):
    """Enhanced metadata with enterprise features"""
    
    def __init__(self, *args, **kwargs):
        # Set naming convention for constraints
        naming_convention = {
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
        kwargs.setdefault('naming_convention', naming_convention)
        super().__init__(*args, **kwargs)


class EnterpriseBase(DeclarativeBase, LoggerMixin):
    """
    Enterprise Base Class for SQLAlchemy 2.0
    
    Provides:
    - Automatic audit trail integration
    - Timestamp management
    - UUID primary keys
    - Soft delete support
    - Validation framework
    - Serialization utilities
    - Performance monitoring
    """
    
    metadata = EnterpriseMetaData()
    
    # Class-level configuration
    __audit_enabled__: ClassVar[bool] = True
    __soft_delete__: ClassVar[bool] = True
    __validate_on_save__: ClassVar[bool] = True
    __searchable_fields__: ClassVar[List[str]] = []
    __serializable_fields__: ClassVar[Optional[List[str]]] = None
    __protected_fields__: ClassVar[List[str]] = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name"""
        # Convert CamelCase to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


class TimestampMixin:
    """Mixin for automatic timestamp management"""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class AuditMixin:
    """Mixin for audit trail fields"""
    
    created_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1"
    )


class SoftDeleteMixin:
    """Mixin for soft delete support"""
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    deleted_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )
    
    @property
    def is_active(self) -> bool:
        """Check if record is active (not deleted)"""
        return not self.is_deleted


class StatusMixin:
    """Mixin for record status management"""
    
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=RecordStatus.ACTIVE.value,
        server_default=f"'{RecordStatus.ACTIVE.value}'"
    )
    
    @property
    def status_enum(self) -> RecordStatus:
        """Get status as enum"""
        try:
            return RecordStatus(self.status)
        except ValueError:
            return RecordStatus.ACTIVE


class MetadataMixin:
    """Mixin for flexible metadata storage"""
    
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key"""
        if not self.metadata_json:
            return default
        return self.metadata_json.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value by key"""
        if not self.metadata_json:
            self.metadata_json = {}
        self.metadata_json[key] = value
    
    def update_metadata(self, data: Dict[str, Any]) -> None:
        """Update metadata with dictionary"""
        if not self.metadata_json:
            self.metadata_json = {}
        self.metadata_json.update(data)


class EnterpriseBaseModel(
    EnterpriseBase,
    TimestampMixin,
    AuditMixin,
    SoftDeleteMixin,
    StatusMixin,
    MetadataMixin
):
    """
    Complete Enterprise Base Model
    
    Includes all enterprise features:
    - UUID primary key
    - Automatic timestamps
    - Audit trail integration
    - Soft delete support
    - Status management
    - Flexible metadata storage
    - Validation framework
    - Serialization utilities
    """
    
    __abstract__ = True
    
    # Primary key as UUID
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    
    def __init__(self, **kwargs):
        # Initialize audit trail and vault manager
        self._audit = get_persistent_audit_trail()
        self._vault = get_enterprise_vault_manager()
        
        # Set default values
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        
        super().__init__(**kwargs)
    
    def __repr__(self) -> str:
        """String representation"""
        return f"<{self.__class__.__name__}(id='{self.id}')>"
    
    def __str__(self) -> str:
        """String representation"""
        return self.__repr__()
    
    # Validation methods
    
    def validate(self) -> List[ModelValidationError]:
        """Validate model instance"""
        errors = []
        
        # Basic validation
        if not self.id:
            errors.append(ModelValidationError(
                field='id',
                message='ID is required',
                code='required',
                value=self.id
            ))
        
        # Custom validation
        custom_errors = self._validate_custom()
        errors.extend(custom_errors)
        
        return errors
    
    def _validate_custom(self) -> List[ModelValidationError]:
        """Override in subclasses for custom validation"""
        return []
    
    def is_valid(self) -> bool:
        """Check if model is valid"""
        return len(self.validate()) == 0
    
    def validate_and_raise(self) -> None:
        """Validate and raise exception if invalid"""
        errors = self.validate()
        if errors:
            error_messages = [f"{e.field}: {e.message}" for e in errors]
            raise ValueError(f"Validation failed: {', '.join(error_messages)}")
    
    # Serialization methods
    
    def to_dict(self, include_private: bool = False, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert model to dictionary"""
        
        # Determine fields to include
        if fields:
            include_fields = set(fields)
        elif self.__serializable_fields__:
            include_fields = set(self.__serializable_fields__)
        else:
            # Get all column names
            include_fields = set(c.key for c in inspect(self.__class__).columns)
        
        # Remove protected fields unless explicitly requested
        if not include_private:
            include_fields -= set(self.__protected_fields__)
        
        result = {}
        
        for field in include_fields:
            if hasattr(self, field):
                value = getattr(self, field)
                
                # Handle special types
                if isinstance(value, datetime):
                    result[field] = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    result[field] = str(value)
                elif isinstance(value, Enum):
                    result[field] = value.value
                else:
                    result[field] = value
        
        return result
    
    def to_json(self, **kwargs) -> str:
        """Convert model to JSON string"""
        return json.dumps(self.to_dict(**kwargs), default=str)
    
    @classmethod
    def from_dict(cls: Type[ModelType], data: Dict[str, Any]) -> ModelType:
        """Create model instance from dictionary"""
        
        # Filter out fields that don't exist on the model
        columns = set(c.key for c in inspect(cls).columns)
        filtered_data = {k: v for k, v in data.items() if k in columns}
        
        # Handle datetime fields
        for field in ['created_at', 'updated_at', 'deleted_at']:
            if field in filtered_data and isinstance(filtered_data[field], str):
                try:
                    filtered_data[field] = datetime.fromisoformat(filtered_data[field])
                except ValueError:
                    pass
        
        return cls(**filtered_data)
    
    @classmethod
    def from_json(cls: Type[ModelType], json_str: str) -> ModelType:
        """Create model instance from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    # Audit trail methods
    
    def _audit_action(self, action: AuditAction, session: Optional[AsyncSession] = None, **context) -> None:
        """Record audit trail entry"""
        
        if not self.__audit_enabled__:
            return
        
        try:
            # Get current user context if available
            user_context = None
            if hasattr(self, '_current_user_id'):
                user_context = {'user_id': self._current_user_id}
            
            # Create audit entry
            self._audit.add_entry(
                f'model_{action.value}',
                {
                    'table': self.__tablename__,
                    'record_id': str(self.id),
                    'model_class': self.__class__.__name__,
                    'action': action.value,
                    'changes': self._get_change_summary(action),
                    **context
                },
                user_context=user_context
            )
            
        except Exception as e:
            # Don't fail the operation due to audit issues
            logger.warning(f"Failed to create audit entry: {e}")
    
    def _get_change_summary(self, action: AuditAction) -> Dict[str, Any]:
        """Get summary of changes for audit"""
        
        if action == AuditAction.CREATE:
            return {
                'operation': 'insert',
                'new_values': self.to_dict(include_private=False)
            }
        
        # For other actions, we would track changes using SQLAlchemy's inspection
        # This is a simplified implementation
        return {
            'operation': action.value,
            'record_id': str(self.id)
        }
    
    # Soft delete methods
    
    def soft_delete(self, deleted_by: Optional[str] = None) -> None:
        """Perform soft delete"""
        if self.__soft_delete__:
            self.is_deleted = True
            self.deleted_at = datetime.now(timezone.utc)
            self.deleted_by = deleted_by
            self.status = RecordStatus.DELETED.value
    
    def restore(self) -> None:
        """Restore soft deleted record"""
        if self.__soft_delete__:
            self.is_deleted = False
            self.deleted_at = None
            self.deleted_by = None
            self.status = RecordStatus.ACTIVE.value
    
    # Context management
    
    def set_user_context(self, user_id: str) -> None:
        """Set current user context for audit trail"""
        self._current_user_id = user_id
        
        # Update audit fields if this is a new record
        if not self.created_by:
            self.created_by = user_id
        self.updated_by = user_id


class EnterpriseRepository:
    """
    Enterprise Repository Pattern Implementation
    
    Provides:
    - Async database operations
    - Connection pool integration
    - Performance monitoring
    - Audit trail integration
    - Caching support
    - Transaction management
    """
    
    def __init__(self, model_class: Type[EnterpriseBaseModel], pool_id: str = "default"):
        self.model_class = model_class
        self.pool_id = pool_id
        self._connection_manager = get_connection_manager()
        self._audit = get_persistent_audit_trail()
        self.logger = get_logger(f"{self.__class__.__name__}.{model_class.__name__}")
    
    async def create(self, instance: ModelType, user_id: Optional[str] = None) -> ModelType:
        """Create new record"""
        
        try:
            # Set user context
            if user_id:
                instance.set_user_context(user_id)
            
            # Validate if enabled
            if instance.__validate_on_save__:
                instance.validate_and_raise()
            
            async with self._get_session() as session:
                # Audit before creation
                instance._audit_action(AuditAction.CREATE, session)
                
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                
                self.logger.info(f"Created {self.model_class.__name__}: {instance.id}")
                
                return instance
                
        except Exception as e:
            self.logger.error(f"Failed to create {self.model_class.__name__}: {e}")
            raise
    
    async def get_by_id(self, record_id: str, include_deleted: bool = False) -> Optional[ModelType]:
        """Get record by ID"""
        
        try:
            async with self._get_session() as session:
                query = session.query(self.model_class).filter(
                    self.model_class.id == record_id
                )
                
                # Exclude soft deleted records unless requested
                if not include_deleted and self.model_class.__soft_delete__:
                    query = query.filter(self.model_class.is_deleted == False)
                
                result = await query.first()
                
                if result:
                    # Audit read access
                    result._audit_action(AuditAction.READ, session)
                
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to get {self.model_class.__name__} by ID {record_id}: {e}")
            raise
    
    async def update(self, instance: ModelType, user_id: Optional[str] = None) -> ModelType:
        """Update existing record"""
        
        try:
            # Set user context
            if user_id:
                instance.set_user_context(user_id)
            
            # Update version for optimistic locking
            instance.version += 1
            instance.updated_at = datetime.now(timezone.utc)
            
            # Validate if enabled
            if instance.__validate_on_save__:
                instance.validate_and_raise()
            
            async with self._get_session() as session:
                # Audit before update
                instance._audit_action(AuditAction.UPDATE, session)
                
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                
                self.logger.info(f"Updated {self.model_class.__name__}: {instance.id}")
                
                return instance
                
        except Exception as e:
            self.logger.error(f"Failed to update {self.model_class.__name__}: {e}")
            raise
    
    async def delete(self, record_id: str, user_id: Optional[str] = None, hard_delete: bool = False) -> bool:
        """Delete record (soft or hard)"""
        
        try:
            instance = await self.get_by_id(record_id, include_deleted=True)
            
            if not instance:
                return False
            
            async with self._get_session() as session:
                if hard_delete or not self.model_class.__soft_delete__:
                    # Hard delete
                    instance._audit_action(AuditAction.DELETE, session)
                    await session.delete(instance)
                    self.logger.info(f"Hard deleted {self.model_class.__name__}: {record_id}")
                else:
                    # Soft delete
                    instance.soft_delete(deleted_by=user_id)
                    instance._audit_action(AuditAction.UPDATE, session, soft_delete=True)
                    session.add(instance)
                    self.logger.info(f"Soft deleted {self.model_class.__name__}: {record_id}")
                
                await session.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete {self.model_class.__name__} {record_id}: {e}")
            raise
    
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include_deleted: bool = False
    ) -> List[ModelType]:
        """List records with filtering and pagination"""
        
        try:
            async with self._get_session() as session:
                query = session.query(self.model_class)
                
                # Exclude soft deleted records unless requested
                if not include_deleted and self.model_class.__soft_delete__:
                    query = query.filter(self.model_class.is_deleted == False)
                
                # Apply filters
                if filters:
                    for field, value in filters.items():
                        if hasattr(self.model_class, field):
                            query = query.filter(getattr(self.model_class, field) == value)
                
                # Apply ordering
                if order_by:
                    if hasattr(self.model_class, order_by):
                        query = query.order_by(getattr(self.model_class, order_by))
                
                # Apply pagination
                if offset:
                    query = query.offset(offset)
                if limit:
                    query = query.limit(limit)
                
                results = await query.all()
                
                # Audit bulk read
                self._audit.add_entry(
                    'model_bulk_read',
                    {
                        'table': self.model_class.__tablename__,
                        'model_class': self.model_class.__name__,
                        'filters': filters or {},
                        'result_count': len(results)
                    }
                )
                
                return results
                
        except Exception as e:
            self.logger.error(f"Failed to list {self.model_class.__name__}: {e}")
            raise
    
    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False
    ) -> int:
        """Count records with filtering"""
        
        try:
            async with self._get_session() as session:
                query = session.query(self.model_class)
                
                # Exclude soft deleted records unless requested
                if not include_deleted and self.model_class.__soft_delete__:
                    query = query.filter(self.model_class.is_deleted == False)
                
                # Apply filters
                if filters:
                    for field, value in filters.items():
                        if hasattr(self.model_class, field):
                            query = query.filter(getattr(self.model_class, field) == value)
                
                return await query.count()
                
        except Exception as e:
            self.logger.error(f"Failed to count {self.model_class.__name__}: {e}")
            raise
    
    async def _get_session(self) -> AsyncSession:
        """Get database session from connection manager"""
        # This is a simplified implementation
        # In practice, you would integrate with the connection manager
        # to get the appropriate session
        
        # Placeholder for now - would need actual session factory
        raise NotImplementedError("Session factory integration needed")


# Event listeners for audit trail

@event.listens_for(EnterpriseBaseModel, 'before_insert', propagate=True)
def before_insert(mapper, connection, target):
    """Handle before insert events"""
    if hasattr(target, '_audit_action'):
        try:
            # Note: This would need to be adapted for async
            pass
        except Exception as e:
            logger.warning(f"Audit trail error on insert: {e}")


@event.listens_for(EnterpriseBaseModel, 'before_update', propagate=True)
def before_update(mapper, connection, target):
    """Handle before update events"""
    target.updated_at = datetime.now(timezone.utc)
    target.version += 1


@event.listens_for(EnterpriseBaseModel, 'before_delete', propagate=True)
def before_delete(mapper, connection, target):
    """Handle before delete events"""
    if hasattr(target, '_audit_action'):
        try:
            # Note: This would need to be adapted for async
            pass
        except Exception as e:
            logger.warning(f"Audit trail error on delete: {e}")


# Utility functions

def create_all_tables(engine: Engine) -> None:
    """Create all tables in the database"""
    EnterpriseBase.metadata.create_all(engine)


async def create_all_tables_async(engine) -> None:
    """Create all tables in the database (async)"""
    async with engine.begin() as conn:
        await conn.run_sync(EnterpriseBase.metadata.create_all)


def get_repository(model_class: Type[EnterpriseBaseModel], pool_id: str = "default") -> EnterpriseRepository:
    """Get repository instance for model class"""
    return EnterpriseRepository(model_class, pool_id)


# Export main components
__all__ = [
    'EnterpriseBase',
    'EnterpriseBaseModel',
    'EnterpriseRepository',
    'TimestampMixin',
    'AuditMixin',
    'SoftDeleteMixin',
    'StatusMixin',
    'MetadataMixin',
    'RecordStatus',
    'AuditAction',
    'ModelValidationError',
    'create_all_tables',
    'create_all_tables_async',
    'get_repository'
]