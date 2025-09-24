"""
DafelHub Multi-Factor Authentication (MFA) System
Enterprise TOTP + QR Codes + Backup Codes + Recovery Workflows
"""

import uuid
import secrets
import qrcode
import pyotp
import io
import base64
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.encryption import get_vault_manager
from dafelhub.database.models import User
from .models import (
    UserSecurityProfile, SecurityAuditLog, AuditEventType,
    SecurityEvent, ThreatLevel
)
from .authentication import SecurityContext


logger = get_logger(__name__)


class MFAType(str, Enum):
    """Multi-factor authentication types"""
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"
    BACKUP_CODE = "backup_code"
    PUSH = "push"
    HARDWARE_KEY = "hardware_key"


class MFAStatus(str, Enum):
    """MFA setup status"""
    DISABLED = "disabled"
    PENDING = "pending"
    ENABLED = "enabled"
    SUSPENDED = "suspended"


@dataclass
class MFASetupResult:
    """MFA setup result with QR code and backup codes"""
    secret: str
    qr_code_base64: str
    backup_codes: List[str]
    setup_uri: str
    setup_key: str


@dataclass
class BackupCode:
    """Backup code with usage tracking"""
    code: str
    used_at: Optional[datetime] = None
    is_used: bool = False


class MFAError(Exception):
    """MFA related errors"""
    pass


class MFASystemManager(LoggerMixin):
    """Comprehensive MFA system manager"""
    
    def __init__(self, db: Session):
        self.db = db
        self.vault = get_vault_manager()
        self.issuer_name = "DafelHub Enterprise"
        self.qr_size = 10
        self.qr_border = 4
        
        # TOTP configuration
        self.totp_window = 1  # Allow 1 step before/after for time sync issues
        self.totp_interval = 30  # Standard 30-second interval
        
        # Backup codes configuration
        self.backup_codes_count = 10
        self.backup_code_length = 8
    
    def setup_totp_for_user(
        self,
        user_id: uuid.UUID,
        issuer_name: Optional[str] = None
    ) -> MFASetupResult:
        """Set up TOTP for user and generate QR code"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise MFAError("User not found")
            
            # Get or create security profile
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile:
                security_profile = UserSecurityProfile(user_id=user_id)
                self.db.add(security_profile)
                self.db.flush()
            
            # Generate TOTP secret
            secret = pyotp.random_base32()
            issuer = issuer_name or self.issuer_name
            
            # Create TOTP URI for QR code
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=user.email,
                issuer_name=issuer
            )
            
            # Generate QR code
            qr_code_base64 = self._generate_qr_code(provisioning_uri)
            
            # Generate backup codes
            backup_codes = self._generate_backup_codes()
            
            # Encrypt and store secret
            encrypted_secret = self.vault.encrypt_data(secret, f"2fa_{user_id}")
            security_profile.two_factor_secret = encrypted_secret
            
            # Encrypt and store backup codes
            encrypted_backup_codes = [
                self.vault.encrypt_data(code, f"backup_{user_id}_{i}")
                for i, code in enumerate(backup_codes)
            ]
            security_profile.backup_codes = encrypted_backup_codes
            
            # Update MFA status to pending (user needs to verify setup)
            security_profile.two_factor_enabled = False  # Will be enabled after verification
            
            self.db.commit()
            
            # Log MFA setup initiation
            self._log_mfa_event(
                user_id=user_id,
                event_type=AuditEventType.TWO_FACTOR_ENABLED,
                description="TOTP setup initiated",
                success=True,
                event_details={'mfa_type': MFAType.TOTP}
            )
            
            setup_result = MFASetupResult(
                secret=secret,
                qr_code_base64=qr_code_base64,
                backup_codes=backup_codes,
                setup_uri=provisioning_uri,
                setup_key=secret
            )
            
            self.logger.info(f"TOTP setup initiated for user: {user.username}")
            return setup_result
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"TOTP setup failed: {e}")
            raise MFAError(f"TOTP setup failed: {e}")
    
    def verify_totp_setup(
        self,
        user_id: uuid.UUID,
        verification_code: str
    ) -> bool:
        """Verify TOTP setup with user-provided code"""
        try:
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile or not security_profile.two_factor_secret:
                raise MFAError("TOTP not set up for user")
            
            # Decrypt secret
            secret = self.vault.decrypt_data(security_profile.two_factor_secret)
            
            # Verify code
            totp = pyotp.TOTP(secret)
            if totp.verify(verification_code, valid_window=self.totp_window):
                # Enable TOTP
                security_profile.two_factor_enabled = True
                security_profile.two_factor_last_used = datetime.now(timezone.utc)
                self.db.commit()
                
                # Log successful setup
                self._log_mfa_event(
                    user_id=user_id,
                    event_type=AuditEventType.TWO_FACTOR_ENABLED,
                    description="TOTP setup completed and verified",
                    success=True,
                    event_details={
                        'mfa_type': MFAType.TOTP,
                        'verification_successful': True
                    }
                )
                
                self.logger.info(f"TOTP setup completed for user: {user_id}")
                return True
            else:
                # Log failed verification
                self._log_mfa_event(
                    user_id=user_id,
                    event_type=AuditEventType.TWO_FACTOR_FAILED,
                    description="TOTP setup verification failed",
                    success=False,
                    event_details={
                        'mfa_type': MFAType.TOTP,
                        'verification_failed': True
                    }
                )
                
                self.logger.warning(f"TOTP setup verification failed for user: {user_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"TOTP setup verification failed: {e}")
            raise MFAError(f"TOTP setup verification failed: {e}")
    
    def verify_totp_code(
        self,
        user_id: uuid.UUID,
        code: str,
        context: Optional[SecurityContext] = None
    ) -> bool:
        """Verify TOTP code during authentication"""
        try:
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile or not security_profile.two_factor_enabled:
                raise MFAError("TOTP not enabled for user")
            
            # Decrypt secret
            secret = self.vault.decrypt_data(security_profile.two_factor_secret)
            
            # Verify TOTP code
            totp = pyotp.TOTP(secret, interval=self.totp_interval)
            is_valid = totp.verify(code, valid_window=self.totp_window)
            
            # Update last used timestamp
            if is_valid:
                security_profile.two_factor_last_used = datetime.now(timezone.utc)
                self.db.commit()
                
                self._log_mfa_event(
                    user_id=user_id,
                    event_type=AuditEventType.TWO_FACTOR_SUCCESS,
                    description="TOTP verification successful",
                    success=True,
                    ip_address=context.ip_address if context else None,
                    user_agent=context.user_agent if context else None,
                    event_details={'mfa_type': MFAType.TOTP}
                )
            else:
                self._log_mfa_event(
                    user_id=user_id,
                    event_type=AuditEventType.TWO_FACTOR_FAILED,
                    description="TOTP verification failed",
                    success=False,
                    ip_address=context.ip_address if context else None,
                    user_agent=context.user_agent if context else None,
                    event_details={'mfa_type': MFAType.TOTP}
                )
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"TOTP verification failed: {e}")
            return False
    
    def verify_backup_code(
        self,
        user_id: uuid.UUID,
        backup_code: str,
        context: Optional[SecurityContext] = None
    ) -> bool:
        """Verify and consume backup code"""
        try:
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile or not security_profile.backup_codes:
                raise MFAError("No backup codes available for user")
            
            # Decrypt and check backup codes
            for i, encrypted_code in enumerate(security_profile.backup_codes):
                try:
                    decrypted_code = self.vault.decrypt_data(encrypted_code)
                    
                    if decrypted_code == backup_code.upper().strip():
                        # Mark code as used by removing it
                        security_profile.backup_codes.pop(i)
                        self.db.commit()
                        
                        self._log_mfa_event(
                            user_id=user_id,
                            event_type=AuditEventType.TWO_FACTOR_SUCCESS,
                            description="Backup code used successfully",
                            success=True,
                            ip_address=context.ip_address if context else None,
                            user_agent=context.user_agent if context else None,
                            event_details={
                                'mfa_type': MFAType.BACKUP_CODE,
                                'remaining_codes': len(security_profile.backup_codes)
                            }
                        )
                        
                        # Alert if running low on backup codes
                        if len(security_profile.backup_codes) <= 2:
                            self._create_low_backup_codes_alert(user_id, len(security_profile.backup_codes))
                        
                        self.logger.info(f"Backup code used for user: {user_id}")
                        return True
                        
                except Exception as decrypt_error:
                    self.logger.warning(f"Failed to decrypt backup code {i}: {decrypt_error}")
                    continue
            
            # Log failed backup code attempt
            self._log_mfa_event(
                user_id=user_id,
                event_type=AuditEventType.TWO_FACTOR_FAILED,
                description="Invalid backup code used",
                success=False,
                ip_address=context.ip_address if context else None,
                user_agent=context.user_agent if context else None,
                event_details={'mfa_type': MFAType.BACKUP_CODE}
            )
            
            return False
            
        except Exception as e:
            self.logger.error(f"Backup code verification failed: {e}")
            return False
    
    def regenerate_backup_codes(self, user_id: uuid.UUID) -> List[str]:
        """Regenerate backup codes for user"""
        try:
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile:
                raise MFAError("User security profile not found")
            
            # Generate new backup codes
            backup_codes = self._generate_backup_codes()
            
            # Encrypt and store new codes
            encrypted_backup_codes = [
                self.vault.encrypt_data(code, f"backup_{user_id}_{i}")
                for i, code in enumerate(backup_codes)
            ]
            security_profile.backup_codes = encrypted_backup_codes
            
            self.db.commit()
            
            # Log backup code regeneration
            self._log_mfa_event(
                user_id=user_id,
                event_type=AuditEventType.TWO_FACTOR_ENABLED,
                description="Backup codes regenerated",
                success=True,
                event_details={
                    'action': 'regenerate_backup_codes',
                    'codes_generated': len(backup_codes)
                }
            )
            
            self.logger.info(f"Backup codes regenerated for user: {user_id}")
            return backup_codes
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Backup code regeneration failed: {e}")
            raise MFAError(f"Backup code regeneration failed: {e}")
    
    def disable_mfa_for_user(
        self,
        user_id: uuid.UUID,
        disabled_by: uuid.UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Disable MFA for user (admin action)"""
        try:
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile:
                raise MFAError("User security profile not found")
            
            # Disable MFA
            security_profile.two_factor_enabled = False
            security_profile.two_factor_secret = None
            security_profile.backup_codes = []
            security_profile.two_factor_last_used = None
            
            self.db.commit()
            
            # Log MFA disable
            self._log_mfa_event(
                user_id=user_id,
                event_type=AuditEventType.TWO_FACTOR_DISABLED,
                description="MFA disabled by administrator",
                success=True,
                event_details={
                    'disabled_by': str(disabled_by),
                    'reason': reason or 'Administrative action'
                }
            )
            
            self.logger.info(f"MFA disabled for user: {user_id} by {disabled_by}")
            return True
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"MFA disable failed: {e}")
            return False
    
    def get_mfa_status(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get comprehensive MFA status for user"""
        try:
            security_profile = self.db.query(UserSecurityProfile).filter(
                UserSecurityProfile.user_id == user_id
            ).first()
            
            if not security_profile:
                return {
                    'enabled': False,
                    'status': MFAStatus.DISABLED,
                    'methods': [],
                    'backup_codes_available': 0
                }
            
            backup_codes_count = len(security_profile.backup_codes or [])
            
            return {
                'enabled': security_profile.two_factor_enabled,
                'status': MFAStatus.ENABLED if security_profile.two_factor_enabled else MFAStatus.DISABLED,
                'methods': [MFAType.TOTP] if security_profile.two_factor_secret else [],
                'backup_codes_available': backup_codes_count,
                'last_used': security_profile.two_factor_last_used,
                'needs_backup_codes': backup_codes_count <= 2,
                'setup_pending': security_profile.two_factor_secret and not security_profile.two_factor_enabled
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get MFA status: {e}")
            return {'enabled': False, 'status': MFAStatus.DISABLED}
    
    def _generate_qr_code(self, provisioning_uri: str) -> str:
        """Generate QR code image as base64 string"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.qr_size,
                border=self.qr_border,
            )
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{qr_base64}"
            
        except Exception as e:
            self.logger.error(f"QR code generation failed: {e}")
            raise MFAError(f"QR code generation failed: {e}")
    
    def _generate_backup_codes(self) -> List[str]:
        """Generate cryptographically secure backup codes"""
        codes = []
        for _ in range(self.backup_codes_count):
            # Generate random hex string and format
            code = secrets.token_hex(self.backup_code_length // 2).upper()
            # Format as XXXX-XXXX for readability
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        
        return codes
    
    def _log_mfa_event(
        self,
        user_id: uuid.UUID,
        event_type: AuditEventType,
        description: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        event_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log MFA-related security event"""
        try:
            audit_log = SecurityAuditLog(
                event_type=event_type,
                event_category="MFA",
                event_description=description,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                threat_level=ThreatLevel.LOW if success else ThreatLevel.MEDIUM,
                event_details=event_details or {}
            )
            self.db.add(audit_log)
            self.db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to log MFA event: {e}")
    
    def _create_low_backup_codes_alert(self, user_id: uuid.UUID, remaining_codes: int) -> None:
        """Create alert for low backup codes"""
        try:
            security_event = SecurityEvent(
                event_type="LOW_BACKUP_CODES",
                severity=ThreatLevel.LOW,
                title="Low Backup Codes Warning",
                description=f"User has only {remaining_codes} backup codes remaining",
                user_profile_id=self.db.query(UserSecurityProfile).filter(
                    UserSecurityProfile.user_id == user_id
                ).first().id,
                event_data={
                    'user_id': str(user_id),
                    'remaining_codes': remaining_codes,
                    'recommendation': 'Generate new backup codes'
                }
            )
            self.db.add(security_event)
            self.db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to create low backup codes alert: {e}")
    
    def generate_recovery_codes(
        self,
        user_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        reason: str
    ) -> List[str]:
        """Generate one-time recovery codes for MFA reset"""
        try:
            recovery_codes = []
            for _ in range(3):  # Generate 3 recovery codes
                code = secrets.token_urlsafe(16).upper()
                recovery_codes.append(code)
            
            # Log recovery code generation
            self._log_mfa_event(
                user_id=user_id,
                event_type=AuditEventType.TWO_FACTOR_ENABLED,
                description="Recovery codes generated by administrator",
                success=True,
                event_details={
                    'action': 'generate_recovery_codes',
                    'admin_user_id': str(admin_user_id),
                    'reason': reason,
                    'codes_generated': len(recovery_codes)
                }
            )
            
            self.logger.info(f"Recovery codes generated for user: {user_id} by admin: {admin_user_id}")
            return recovery_codes
            
        except Exception as e:
            self.logger.error(f"Recovery code generation failed: {e}")
            raise MFAError(f"Recovery code generation failed: {e}")


# Global MFA manager instance
_mfa_manager: Optional[MFASystemManager] = None


def get_mfa_manager(db: Session) -> MFASystemManager:
    """Get or create MFA manager instance"""
    global _mfa_manager
    if not _mfa_manager:
        _mfa_manager = MFASystemManager(db)
    return _mfa_manager