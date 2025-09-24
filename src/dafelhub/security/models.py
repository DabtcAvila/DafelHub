"""
DafelHub Security Database Models
SOC 2 Type II Compliant Security Models
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text,
    func, Index, UniqueConstraint, Float
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dafelhub.database.models import Base, TimestampMixin


class SecurityRole(str, Enum):
    """Security role definitions"""
    ADMIN = "ADMIN"
    EDITOR = "EDITOR" 
    VIEWER = "VIEWER"
    AUDITOR = "AUDITOR"
    SECURITY_ADMIN = "SECURITY_ADMIN"


class AuditEventType(str, Enum):
    """Comprehensive audit event types for SOC 2 compliance"""
    # Authentication Events
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_BLOCKED = "LOGIN_BLOCKED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET_COMPLETE = "PASSWORD_RESET_COMPLETE"
    
    # Account Management
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_UNLOCKED = "ACCOUNT_UNLOCKED"
    
    # Role & Permission Changes
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    
    # Two-Factor Authentication
    TWO_FACTOR_ENABLED = "TWO_FACTOR_ENABLED"
    TWO_FACTOR_DISABLED = "TWO_FACTOR_DISABLED"
    TWO_FACTOR_SUCCESS = "TWO_FACTOR_SUCCESS"
    TWO_FACTOR_FAILED = "TWO_FACTOR_FAILED"
    
    # Data Access
    DATA_ACCESS = "DATA_ACCESS"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_IMPORT = "DATA_IMPORT"
    DATA_DELETION = "DATA_DELETION"
    SENSITIVE_DATA_ACCESS = "SENSITIVE_DATA_ACCESS"
    
    # Security Events
    UNAUTHORIZED_ACCESS_ATTEMPT = "UNAUTHORIZED_ACCESS_ATTEMPT"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    SECURITY_POLICY_VIOLATION = "SECURITY_POLICY_VIOLATION"
    PRIVILEGE_ESCALATION_ATTEMPT = "PRIVILEGE_ESCALATION_ATTEMPT"
    
    # System Events
    SYSTEM_CONFIG_CHANGE = "SYSTEM_CONFIG_CHANGE"
    ENCRYPTION_KEY_ROTATION = "ENCRYPTION_KEY_ROTATION"
    BACKUP_CREATED = "BACKUP_CREATED"
    BACKUP_RESTORED = "BACKUP_RESTORED"
    
    # Compliance Events
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"
    AUDIT_REPORT_GENERATED = "AUDIT_REPORT_GENERATED"
    RETENTION_POLICY_APPLIED = "RETENTION_POLICY_APPLIED"


class ThreatLevel(str, Enum):
    """Threat severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataClassificationLevel(str, Enum):
    """Data classification levels"""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class UserSecurityProfile(Base, TimestampMixin):
    """Enhanced user security profile for SOC 2 compliance"""
    __tablename__ = "user_security_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), 
        nullable=False, 
        unique=True
    )
    
    # Security Status
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Session Management
    active_sessions: Mapped[int] = mapped_column(Integer, default=0)
    max_sessions: Mapped[int] = mapped_column(Integer, default=3)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45))
    last_login_location: Mapped[Optional[str]] = mapped_column(String(100))
    last_user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Two-Factor Authentication
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    two_factor_secret: Mapped[Optional[str]] = mapped_column(String(200))  # Encrypted
    backup_codes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))  # Encrypted
    two_factor_last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Password Security
    password_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    password_history: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)  # Encrypted
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Risk Assessment
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_risk_assessment: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Compliance Tracking
    last_security_training: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    compliance_acknowledgments: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    security_events: Mapped[List["SecurityEvent"]] = relationship(
        "SecurityEvent", 
        back_populates="user_profile"
    )
    
    __table_args__ = (
        Index("ix_user_security_profiles_user_id", "user_id"),
        Index("ix_user_security_profiles_risk_score", "risk_score"),
        Index("ix_user_security_profiles_locked", "is_locked"),
    )


class SecurityAuditLog(Base, TimestampMixin):
    """Comprehensive security audit log for SOC 2 compliance"""
    __tablename__ = "security_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Event Information
    event_type: Mapped[AuditEventType] = mapped_column(SQLEnum(AuditEventType), nullable=False)
    event_category: Mapped[str] = mapped_column(String(50), nullable=False)
    event_description: Mapped[str] = mapped_column(Text, nullable=False)
    event_details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # User Context
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    username: Mapped[Optional[str]] = mapped_column(String(100))
    user_role: Mapped[Optional[SecurityRole]] = mapped_column(SQLEnum(SecurityRole))
    
    # Request Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    session_id: Mapped[Optional[str]] = mapped_column(String(100))
    request_id: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Geographic Information
    country: Mapped[Optional[str]] = mapped_column(String(2))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Resource Information
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    resource_name: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Result Information
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(200))
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Risk & Threat Assessment
    threat_level: Mapped[ThreatLevel] = mapped_column(
        SQLEnum(ThreatLevel), 
        default=ThreatLevel.LOW
    )
    risk_indicators: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    
    # Compliance & Retention
    data_classification: Mapped[DataClassificationLevel] = mapped_column(
        SQLEnum(DataClassificationLevel), 
        default=DataClassificationLevel.INTERNAL
    )
    retention_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Additional Metadata
    additional_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
    
    __table_args__ = (
        Index("ix_security_audit_logs_event_type", "event_type"),
        Index("ix_security_audit_logs_user_id", "user_id"),
        Index("ix_security_audit_logs_ip_address", "ip_address"),
        Index("ix_security_audit_logs_created_at", "created_at"),
        Index("ix_security_audit_logs_threat_level", "threat_level"),
        Index("ix_security_audit_logs_resource", "resource_type", "resource_id"),
    )


class SecurityEvent(Base, TimestampMixin):
    """Real-time security event tracking"""
    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Event Information
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[ThreatLevel] = mapped_column(SQLEnum(ThreatLevel), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Source Information
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))
    source_location: Mapped[Optional[str]] = mapped_column(String(100))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # User Context
    user_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("user_security_profiles.id")
    )
    
    # Status & Resolution
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN, INVESTIGATING, RESOLVED, FALSE_POSITIVE
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    
    # Alert Information
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_channels: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    
    # Additional Data
    event_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Relationships
    user_profile: Mapped[Optional["UserSecurityProfile"]] = relationship(
        "UserSecurityProfile", 
        back_populates="security_events"
    )
    resolved_by: Mapped[Optional["User"]] = relationship("User")
    
    __table_args__ = (
        Index("ix_security_events_severity", "severity"),
        Index("ix_security_events_status", "status"),
        Index("ix_security_events_source_ip", "source_ip"),
        Index("ix_security_events_created_at", "created_at"),
    )


class UserSession(Base, TimestampMixin):
    """Secure user session management"""
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Session Information
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Session Details
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Geographic Information
    country: Mapped[Optional[str]] = mapped_column(String(2))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Session Lifecycle
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    terminated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    termination_reason: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Security Information
    is_trusted_device: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_reauth: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    
    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_session_token", "session_token"),
        Index("ix_user_sessions_ip_address", "ip_address"),
        Index("ix_user_sessions_expires_at", "expires_at"),
        Index("ix_user_sessions_active", "is_active"),
    )


class SecurityPolicy(Base, TimestampMixin):
    """Security policy management"""
    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Policy Information
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Policy Content
    policy_rules: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    enforcement_level: Mapped[str] = mapped_column(
        String(20), 
        default="ENFORCED"  # ENFORCED, WARNING, DISABLED
    )
    
    # Version Control
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Ownership
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_id])
    
    __table_args__ = (
        Index("ix_security_policies_name", "name"),
        Index("ix_security_policies_category", "category"),
        Index("ix_security_policies_active", "is_active"),
        Index("ix_security_policies_effective_date", "effective_date"),
    )


class ComplianceReport(Base, TimestampMixin):
    """Compliance reporting for SOC 2 and other standards"""
    __tablename__ = "compliance_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Report Information
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # SOC2, GDPR, etc.
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Report Period
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Report Content
    findings: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    recommendations: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    compliance_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT, FINAL, ARCHIVED
    generated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    
    # File Storage
    report_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    report_checksum: Mapped[Optional[str]] = mapped_column(String(64))
    
    # Relationships
    generated_by: Mapped["User"] = relationship("User", foreign_keys=[generated_by_id])
    reviewed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by_id])
    approved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by_id])
    
    __table_args__ = (
        Index("ix_compliance_reports_type", "report_type"),
        Index("ix_compliance_reports_status", "status"),
        Index("ix_compliance_reports_period", "period_start", "period_end"),
        Index("ix_compliance_reports_score", "compliance_score"),
    )


class APIToken(Base, TimestampMixin):
    """API token management for long-lived authentication"""
    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Token Information
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    
    # Owner Information
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Token Lifecycle
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Security & Permissions
    permissions: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    ip_restrictions: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    rate_limit_per_hour: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    revoked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by_id])
    
    __table_args__ = (
        Index("ix_api_tokens_user_id", "user_id"),
        Index("ix_api_tokens_token_hash", "token_hash"),
        Index("ix_api_tokens_active", "is_active"),
        Index("ix_api_tokens_expires_at", "expires_at"),
    )


class TokenBlacklist(Base, TimestampMixin):
    """JWT token blacklist for revoked tokens"""
    __tablename__ = "token_blacklist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Token Information
    jti: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # JWT ID
    token_type: Mapped[str] = mapped_column(String(20), nullable=False)  # access, refresh, etc.
    
    # User & Session Context
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user_sessions.id"))
    
    # Revocation Details
    revoked_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Token Lifecycle
    original_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    session: Mapped[Optional["UserSession"]] = relationship("UserSession")
    revoked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by_id])
    
    __table_args__ = (
        Index("ix_token_blacklist_jti", "jti"),
        Index("ix_token_blacklist_user_id", "user_id"),
        Index("ix_token_blacklist_expires", "original_expires_at"),
    )


class MFADevice(Base, TimestampMixin):
    """Multi-factor authentication device registration"""
    __tablename__ = "mfa_devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Device Information
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)  # totp, sms, hardware_key
    
    # User Association
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Device Configuration
    encrypted_secret: Mapped[Optional[str]] = mapped_column(String(500))  # For TOTP devices
    phone_number: Mapped[Optional[str]] = mapped_column(String(20))  # For SMS devices
    device_identifier: Mapped[Optional[str]] = mapped_column(String(200))  # For hardware keys
    
    # Usage Statistics
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Security
    created_ip: Mapped[Optional[str]] = mapped_column(String(45))
    created_user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    
    __table_args__ = (
        Index("ix_mfa_devices_user_id", "user_id"),
        Index("ix_mfa_devices_type", "device_type"),
        Index("ix_mfa_devices_active", "is_active"),
        UniqueConstraint("user_id", "name", name="uq_mfa_devices_user_name"),
    )


class SecurityNotification(Base, TimestampMixin):
    """Security notifications and alerts"""
    __tablename__ = "security_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Notification Information
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[ThreatLevel] = mapped_column(SQLEnum(ThreatLevel), nullable=False)
    
    # Target User
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Notification Channels
    channels: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)  # email, sms, push, in_app
    
    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Related Event
    security_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("security_events.id"))
    
    # Additional Data
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    security_event: Mapped[Optional["SecurityEvent"]] = relationship("SecurityEvent")
    
    __table_args__ = (
        Index("ix_security_notifications_user_id", "user_id"),
        Index("ix_security_notifications_type", "notification_type"),
        Index("ix_security_notifications_severity", "severity"),
        Index("ix_security_notifications_read", "is_read"),
        Index("ix_security_notifications_sent", "is_sent"),
    )


class RiskAssessment(Base, TimestampMixin):
    """User risk assessment and scoring"""
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # User Association
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Risk Scoring
    overall_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    behavioral_score: Mapped[float] = mapped_column(Float, default=0.0)
    geographic_score: Mapped[float] = mapped_column(Float, default=0.0)
    temporal_score: Mapped[float] = mapped_column(Float, default=0.0)
    device_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Risk Factors
    risk_factors: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    risk_indicators: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    # Assessment Context
    assessment_trigger: Mapped[str] = mapped_column(String(50), nullable=False)  # login, api_call, etc.
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    location: Mapped[Optional[str]] = mapped_column(String(100))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Validity
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Actions Taken
    actions_recommended: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    actions_taken: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    
    __table_args__ = (
        Index("ix_risk_assessments_user_id", "user_id"),
        Index("ix_risk_assessments_score", "overall_risk_score"),
        Index("ix_risk_assessments_trigger", "assessment_trigger"),
        Index("ix_risk_assessments_valid_until", "valid_until"),
    )


class SecurityConfiguration(Base, TimestampMixin):
    """System security configuration settings"""
    __tablename__ = "security_configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Configuration Information
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Data Type & Validation
    data_type: Mapped[str] = mapped_column(String(20), default="string")  # string, integer, boolean, json
    validation_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # Security & Access
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    access_level: Mapped[SecurityRole] = mapped_column(SQLEnum(SecurityRole), default=SecurityRole.ADMIN)
    
    # Change Management
    last_modified_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    change_reason: Mapped[Optional[str]] = mapped_column(String(200))
    previous_value: Mapped[Optional[str]] = mapped_column(Text)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_restart: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    last_modified_by: Mapped[Optional["User"]] = relationship("User")
    
    __table_args__ = (
        Index("ix_security_configurations_key", "key"),
        Index("ix_security_configurations_category", "category"),
        Index("ix_security_configurations_active", "is_active"),
    )