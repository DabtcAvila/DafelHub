"""
DafelHub Audit Logging System
SOC 2 Type II Compliant Comprehensive Audit Trail
"""

import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from .models import (
    SecurityAuditLog, SecurityEvent, ComplianceReport, UserSecurityProfile,
    AuditEventType, ThreatLevel, DataClassificationLevel
)

logger = get_logger(__name__)


class AuditLogger(LoggerMixin):
    """Comprehensive audit logging system"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_security_event(
        self,
        event_type: AuditEventType,
        category: str,
        description: str,
        user_id: Optional[uuid.UUID] = None,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        success: bool = True,
        failure_reason: Optional[str] = None,
        error_code: Optional[str] = None,
        threat_level: ThreatLevel = ThreatLevel.LOW,
        risk_indicators: List[str] = None,
        data_classification: DataClassificationLevel = DataClassificationLevel.INTERNAL,
        event_details: Dict[str, Any] = None,
        additional_metadata: Dict[str, Any] = None
    ) -> SecurityAuditLog:
        """Log comprehensive security audit event"""
        
        try:
            # Create audit log entry
            audit_log = SecurityAuditLog(
                event_type=event_type,
                event_category=category,
                event_description=description,
                event_details=event_details or {},
                user_id=user_id,
                username=username,
                user_role=user_role,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                request_id=request_id,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                success=success,
                failure_reason=failure_reason if not success else None,
                error_code=error_code,
                threat_level=threat_level,
                risk_indicators=risk_indicators or [],
                data_classification=data_classification,
                additional_metadata=additional_metadata or {}
            )
            
            # Set retention policy based on data classification and event type
            audit_log.retention_expires_at = self._calculate_retention_expiry(
                data_classification, event_type
            )
            
            self.db.add(audit_log)
            self.db.commit()
            
            # Log to application logger as well
            log_level = self._get_log_level(threat_level)
            self.logger.log(
                log_level,
                f"Security Event: {event_type.value} - {description} "
                f"(User: {username or 'N/A'}, IP: {ip_address or 'N/A'})"
            )
            
            return audit_log
            
        except Exception as e:
            self.logger.error(f"Failed to log security event: {e}")
            self.db.rollback()
            raise
    
    def log_user_action(
        self,
        action: str,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: str,
        details: Dict[str, Any] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SecurityAuditLog:
        """Log user action for audit trail"""
        
        return self.log_security_event(
            event_type=AuditEventType.DATA_ACCESS,
            category="USER_ACTION",
            description=f"User performed action: {action}",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_details=details or {},
            data_classification=DataClassificationLevel.INTERNAL
        )
    
    def log_data_access(
        self,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: str,
        access_type: str = "READ",
        data_classification: DataClassificationLevel = DataClassificationLevel.INTERNAL,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Dict[str, Any] = None
    ) -> SecurityAuditLog:
        """Log data access for compliance tracking"""
        
        event_type = {
            "READ": AuditEventType.DATA_ACCESS,
            "WRITE": AuditEventType.DATA_ACCESS,
            "DELETE": AuditEventType.DATA_DELETION,
            "EXPORT": AuditEventType.DATA_EXPORT,
            "IMPORT": AuditEventType.DATA_IMPORT
        }.get(access_type.upper(), AuditEventType.DATA_ACCESS)
        
        return self.log_security_event(
            event_type=event_type,
            category="DATA_ACCESS",
            description=f"Data {access_type.lower()} access",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            data_classification=data_classification,
            event_details=details or {},
            threat_level=ThreatLevel.MEDIUM if data_classification in [
                DataClassificationLevel.CONFIDENTIAL,
                DataClassificationLevel.RESTRICTED
            ] else ThreatLevel.LOW
        )
    
    def log_system_event(
        self,
        event_type: AuditEventType,
        description: str,
        details: Dict[str, Any] = None,
        user_id: Optional[uuid.UUID] = None,
        threat_level: ThreatLevel = ThreatLevel.LOW
    ) -> SecurityAuditLog:
        """Log system-level events"""
        
        return self.log_security_event(
            event_type=event_type,
            category="SYSTEM",
            description=description,
            user_id=user_id,
            threat_level=threat_level,
            event_details=details or {},
            data_classification=DataClassificationLevel.INTERNAL
        )
    
    def create_security_event(
        self,
        event_type: str,
        severity: ThreatLevel,
        title: str,
        description: str,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_profile_id: Optional[uuid.UUID] = None,
        event_data: Dict[str, Any] = None
    ) -> SecurityEvent:
        """Create security event for monitoring"""
        
        try:
            security_event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                title=title,
                description=description,
                source_ip=source_ip,
                user_agent=user_agent,
                user_profile_id=user_profile_id,
                event_data=event_data or {}
            )
            
            self.db.add(security_event)
            self.db.commit()
            
            self.logger.warning(
                f"Security Event Created: {title} (Severity: {severity.value})"
            )
            
            return security_event
            
        except Exception as e:
            self.logger.error(f"Failed to create security event: {e}")
            self.db.rollback()
            raise
    
    def get_audit_logs(
        self,
        user_id: Optional[uuid.UUID] = None,
        event_types: List[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecurityAuditLog]:
        """Retrieve audit logs with filtering"""
        
        query = self.db.query(SecurityAuditLog)
        
        # Apply filters
        if user_id:
            query = query.filter(SecurityAuditLog.user_id == user_id)
        
        if event_types:
            query = query.filter(SecurityAuditLog.event_type.in_(event_types))
        
        if start_date:
            query = query.filter(SecurityAuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(SecurityAuditLog.created_at <= end_date)
        
        if ip_address:
            query = query.filter(SecurityAuditLog.ip_address == ip_address)
        
        if success is not None:
            query = query.filter(SecurityAuditLog.success == success)
        
        # Order by most recent first
        query = query.order_by(desc(SecurityAuditLog.created_at))
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        return query.all()
    
    def get_security_events(
        self,
        status: Optional[str] = None,
        severity: Optional[ThreatLevel] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """Retrieve security events with filtering"""
        
        query = self.db.query(SecurityEvent)
        
        if status:
            query = query.filter(SecurityEvent.status == status)
        
        if severity:
            query = query.filter(SecurityEvent.severity == severity)
        
        if start_date:
            query = query.filter(SecurityEvent.created_at >= start_date)
        
        if end_date:
            query = query.filter(SecurityEvent.created_at <= end_date)
        
        query = query.order_by(desc(SecurityEvent.created_at)).limit(limit)
        
        return query.all()
    
    def _calculate_retention_expiry(
        self,
        data_classification: DataClassificationLevel,
        event_type: AuditEventType
    ) -> datetime:
        """Calculate retention expiry based on classification and event type"""
        
        base_date = datetime.now(timezone.utc)
        
        # Retention periods based on data classification
        retention_days = {
            DataClassificationLevel.PUBLIC: 365,  # 1 year
            DataClassificationLevel.INTERNAL: 2555,  # 7 years (SOC 2 requirement)
            DataClassificationLevel.CONFIDENTIAL: 2555,  # 7 years
            DataClassificationLevel.RESTRICTED: 3650,  # 10 years
        }
        
        # Special retention for security events
        security_events = [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.ACCOUNT_LOCKED,
            AuditEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.SECURITY_POLICY_VIOLATION
        ]
        
        if event_type in security_events:
            days = 3650  # 10 years for security events
        else:
            days = retention_days.get(data_classification, 2555)
        
        return base_date + timedelta(days=days)
    
    def _get_log_level(self, threat_level: ThreatLevel) -> int:
        """Convert threat level to logging level"""
        level_mapping = {
            ThreatLevel.LOW: 20,      # INFO
            ThreatLevel.MEDIUM: 30,   # WARNING
            ThreatLevel.HIGH: 40,     # ERROR
            ThreatLevel.CRITICAL: 50  # CRITICAL
        }
        return level_mapping.get(threat_level, 20)


class SecurityMetricsCollector(LoggerMixin):
    """Collect security metrics for monitoring and compliance"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_login_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get login-related security metrics"""
        
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        # Base query for the time period
        base_query = self.db.query(SecurityAuditLog).filter(
            and_(
                SecurityAuditLog.created_at >= start_date,
                SecurityAuditLog.created_at <= end_date
            )
        )
        
        # Login attempts
        total_attempts = base_query.filter(
            SecurityAuditLog.event_type.in_([
                AuditEventType.LOGIN_SUCCESS,
                AuditEventType.LOGIN_FAILED
            ])
        ).count()
        
        successful_logins = base_query.filter(
            SecurityAuditLog.event_type == AuditEventType.LOGIN_SUCCESS
        ).count()
        
        failed_logins = base_query.filter(
            SecurityAuditLog.event_type == AuditEventType.LOGIN_FAILED
        ).count()
        
        blocked_attempts = base_query.filter(
            SecurityAuditLog.event_type == AuditEventType.LOGIN_BLOCKED
        ).count()
        
        # Account lockouts
        lockouts = base_query.filter(
            SecurityAuditLog.event_type == AuditEventType.ACCOUNT_LOCKED
        ).count()
        
        # Success rate
        success_rate = (successful_logins / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            'total_login_attempts': total_attempts,
            'successful_logins': successful_logins,
            'failed_logins': failed_logins,
            'blocked_attempts': blocked_attempts,
            'account_lockouts': lockouts,
            'success_rate_percent': round(success_rate, 2),
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }
    
    def get_security_event_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get security event metrics"""
        
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        # Security events by severity
        events_query = self.db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.created_at >= start_date,
                SecurityEvent.created_at <= end_date
            )
        )
        
        total_events = events_query.count()
        
        # Events by severity
        severity_counts = {}
        for severity in ThreatLevel:
            count = events_query.filter(SecurityEvent.severity == severity).count()
            severity_counts[severity.value] = count
        
        # Open events
        open_events = events_query.filter(SecurityEvent.status == 'OPEN').count()
        
        return {
            'total_security_events': total_events,
            'events_by_severity': severity_counts,
            'open_events': open_events,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }
    
    def get_user_activity_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get user activity metrics"""
        
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        # Active users
        active_users = self.db.query(SecurityAuditLog.user_id).filter(
            and_(
                SecurityAuditLog.created_at >= start_date,
                SecurityAuditLog.created_at <= end_date,
                SecurityAuditLog.user_id.isnot(None)
            )
        ).distinct().count()
        
        # Data access events
        data_access_events = self.db.query(SecurityAuditLog).filter(
            and_(
                SecurityAuditLog.created_at >= start_date,
                SecurityAuditLog.created_at <= end_date,
                SecurityAuditLog.event_type.in_([
                    AuditEventType.DATA_ACCESS,
                    AuditEventType.DATA_EXPORT,
                    AuditEventType.DATA_IMPORT,
                    AuditEventType.SENSITIVE_DATA_ACCESS
                ])
            )
        ).count()
        
        return {
            'active_users': active_users,
            'data_access_events': data_access_events,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }
    
    def get_compliance_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get compliance-related metrics"""
        
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        # Compliance violations
        violations = self.db.query(SecurityAuditLog).filter(
            and_(
                SecurityAuditLog.created_at >= start_date,
                SecurityAuditLog.created_at <= end_date,
                SecurityAuditLog.event_type == AuditEventType.COMPLIANCE_VIOLATION
            )
        ).count()
        
        # Two-factor authentication adoption
        total_users = self.db.query(UserSecurityProfile).count()
        
        two_factor_enabled = self.db.query(UserSecurityProfile).filter(
            UserSecurityProfile.two_factor_enabled == True
        ).count()
        
        two_factor_adoption_rate = (
            two_factor_enabled / total_users * 100
        ) if total_users > 0 else 0
        
        # Password policy compliance
        password_changes = self.db.query(SecurityAuditLog).filter(
            and_(
                SecurityAuditLog.created_at >= start_date,
                SecurityAuditLog.created_at <= end_date,
                SecurityAuditLog.event_type == AuditEventType.PASSWORD_CHANGE
            )
        ).count()
        
        return {
            'compliance_violations': violations,
            'total_users': total_users,
            'two_factor_enabled_users': two_factor_enabled,
            'two_factor_adoption_rate_percent': round(two_factor_adoption_rate, 2),
            'password_changes': password_changes,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }


class ComplianceReporter(LoggerMixin):
    """Generate compliance reports for SOC 2 and other standards"""
    
    def __init__(self, db: Session):
        self.db = db
        self.metrics_collector = SecurityMetricsCollector(db)
    
    def generate_soc2_report(
        self,
        period_start: datetime,
        period_end: datetime,
        generated_by_id: uuid.UUID
    ) -> ComplianceReport:
        """Generate SOC 2 Type II compliance report"""
        
        try:
            # Collect all relevant metrics
            login_metrics = self.metrics_collector.get_login_metrics(period_start, period_end)
            security_metrics = self.metrics_collector.get_security_event_metrics(period_start, period_end)
            user_metrics = self.metrics_collector.get_user_activity_metrics(period_start, period_end)
            compliance_metrics = self.metrics_collector.get_compliance_metrics(period_start, period_end)
            
            # Calculate compliance score
            compliance_score = self._calculate_soc2_compliance_score({
                'login_success_rate': login_metrics['success_rate_percent'],
                'security_events': security_metrics['total_security_events'],
                'compliance_violations': compliance_metrics['compliance_violations'],
                'two_factor_adoption': compliance_metrics['two_factor_adoption_rate_percent']
            })
            
            # Generate findings and recommendations
            findings = self._generate_soc2_findings({
                **login_metrics,
                **security_metrics,
                **user_metrics,
                **compliance_metrics
            })
            
            recommendations = self._generate_soc2_recommendations(findings)
            
            # Create compliance report
            report = ComplianceReport(
                report_type="SOC2_TYPE_II",
                title=f"SOC 2 Type II Compliance Report - {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}",
                description="Comprehensive SOC 2 Type II compliance assessment",
                period_start=period_start,
                period_end=period_end,
                findings=findings,
                recommendations=recommendations,
                compliance_score=compliance_score,
                generated_by_id=generated_by_id,
                status="DRAFT"
            )
            
            self.db.add(report)
            self.db.commit()
            
            self.logger.info(f"SOC 2 compliance report generated: {report.id}")
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate SOC 2 report: {e}")
            self.db.rollback()
            raise
    
    def _calculate_soc2_compliance_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate SOC 2 compliance score"""
        
        score = 100.0
        
        # Login success rate (should be > 95%)
        if metrics['login_success_rate'] < 95:
            score -= (95 - metrics['login_success_rate']) * 0.5
        
        # Security events (penalty for high numbers)
        if metrics['security_events'] > 50:
            score -= min((metrics['security_events'] - 50) * 0.1, 10)
        
        # Compliance violations (major penalty)
        score -= metrics['compliance_violations'] * 2
        
        # Two-factor adoption (should be > 80%)
        if metrics['two_factor_adoption'] < 80:
            score -= (80 - metrics['two_factor_adoption']) * 0.3
        
        return max(score, 0.0)
    
    def _generate_soc2_findings(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SOC 2 findings based on metrics"""
        
        findings = {
            'security_controls': {
                'authentication': {
                    'login_success_rate': metrics['success_rate_percent'],
                    'failed_attempts': metrics['failed_logins'],
                    'account_lockouts': metrics['account_lockouts'],
                    'status': 'COMPLIANT' if metrics['success_rate_percent'] > 95 else 'NON_COMPLIANT'
                },
                'access_control': {
                    'active_users': metrics['active_users'],
                    'data_access_events': metrics['data_access_events'],
                    'status': 'COMPLIANT'
                },
                'monitoring': {
                    'security_events_total': metrics['total_security_events'],
                    'open_security_events': metrics['open_events'],
                    'status': 'COMPLIANT' if metrics['open_events'] < 10 else 'ATTENTION_REQUIRED'
                }
            },
            'compliance': {
                'violations': metrics['compliance_violations'],
                'two_factor_adoption': metrics['two_factor_adoption_rate_percent'],
                'password_changes': metrics['password_changes'],
                'overall_status': 'COMPLIANT' if metrics['compliance_violations'] == 0 else 'NON_COMPLIANT'
            }
        }
        
        return findings
    
    def _generate_soc2_recommendations(self, findings: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on findings"""
        
        recommendations = []
        
        # Authentication recommendations
        auth_status = findings['security_controls']['authentication']['status']
        if auth_status != 'COMPLIANT':
            recommendations.append(
                "Improve authentication controls to achieve >95% login success rate"
            )
        
        # Monitoring recommendations
        if findings['security_controls']['monitoring']['open_security_events'] > 5:
            recommendations.append(
                "Address open security events to reduce security risk"
            )
        
        # Two-factor authentication
        if findings['compliance']['two_factor_adoption'] < 80:
            recommendations.append(
                "Increase two-factor authentication adoption to >80% of users"
            )
        
        # Compliance violations
        if findings['compliance']['violations'] > 0:
            recommendations.append(
                "Address compliance violations to maintain SOC 2 certification"
            )
        
        # Default recommendations
        if not recommendations:
            recommendations.extend([
                "Continue monitoring security metrics and compliance status",
                "Maintain current security controls and access management",
                "Regular review of user access and permissions"
            ])
        
        return recommendations