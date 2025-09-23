"""
DafelHub Database Models
SQLAlchemy 2.0+ models for enterprise data management
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text,
    func, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dafelhub.services.spec_manager import SpecStatus, SpecType


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class User(Base, TimestampMixin):
    """User model for authentication and authorization"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="owner")
    specifications: Mapped[List["Specification"]] = relationship("Specification", back_populates="author")
    
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
    )


class Project(Base, TimestampMixin):
    """Project model for managing DafelHub projects"""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    project_type: Mapped[str] = mapped_column(String(50), default="saas-service")
    technology_stack: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    repository_url: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="active")
    
    # Foreign keys
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Configuration
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="projects")
    specifications: Mapped[List["Specification"]] = relationship("Specification", back_populates="project")
    deployments: Mapped[List["Deployment"]] = relationship("Deployment", back_populates="project")
    
    __table_args__ = (
        Index("ix_projects_name", "name"),
        Index("ix_projects_owner_id", "owner_id"),
        UniqueConstraint("owner_id", "name", name="uq_project_owner_name"),
    )


class Specification(Base, TimestampMixin):
    """Specification model for Spec-Driven Development"""
    __tablename__ = "specifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    spec_type: Mapped[SpecType] = mapped_column(Enum(SpecType), nullable=False)
    status: Mapped[SpecStatus] = mapped_column(Enum(SpecStatus), default=SpecStatus.DRAFT)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    
    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[str] = mapped_column(String(50), default="yaml")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Metadata
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    stakeholders: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    
    # Foreign keys
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Approval workflow
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="specifications")
    author: Mapped["User"] = relationship("User", back_populates="specifications", foreign_keys=[author_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_id])
    
    __table_args__ = (
        Index("ix_specifications_name", "name"),
        Index("ix_specifications_project_id", "project_id"),
        Index("ix_specifications_status", "status"),
        Index("ix_specifications_content_hash", "content_hash"),
        UniqueConstraint("project_id", "name", name="uq_spec_project_name"),
    )


class Agent(Base, TimestampMixin):
    """AI Agent model for multi-agent orchestration"""
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Configuration
    capabilities: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Performance metrics
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    successful_tasks: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(String, default="0.0")  # Use String for decimal precision
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="agent")
    
    __table_args__ = (
        Index("ix_agents_name", "name"),
        Index("ix_agents_type", "agent_type"),
        Index("ix_agents_provider", "provider"),
        UniqueConstraint("name", name="uq_agent_name"),
    )


class Task(Base, TimestampMixin):
    """Task model for agent execution tracking"""
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    # Execution data
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Performance metrics
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    execution_time_seconds: Mapped[Optional[float]] = mapped_column(String)  # String for precision
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(String, default="0.0")  # String for precision
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Foreign keys
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"))
    
    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="tasks")
    project: Mapped[Optional["Project"]] = relationship("Project")
    
    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_agent_id", "agent_id"),
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_created_at", "created_at"),
    )


class Deployment(Base, TimestampMixin):
    """Deployment model for tracking project deployments"""
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), nullable=False)  # dev, staging, prod
    status: Mapped[str] = mapped_column(String(20), default="pending")
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Deployment configuration
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    infrastructure: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # URLs and endpoints
    url: Mapped[Optional[str]] = mapped_column(String(500))
    health_check_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Deployment timing
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Foreign keys
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    deployed_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="deployments")
    deployed_by: Mapped["User"] = relationship("User")
    
    __table_args__ = (
        Index("ix_deployments_environment", "environment"),
        Index("ix_deployments_status", "status"),
        Index("ix_deployments_project_id", "project_id"),
        UniqueConstraint("project_id", "environment", name="uq_deployment_project_env"),
    )


class AuditLog(Base, TimestampMixin):
    """Audit log for tracking system changes"""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Change details
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    
    # User context
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
    
    __table_args__ = (
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )