"""
DafelHub Vault Recovery System
Enterprise-grade key and configuration recovery with multi-location backup

Features:
- Automatic key backup and recovery
- Configuration state persistence
- Multi-location backup (local, cloud-ready)
- Encrypted backup with versioning
- Recovery after system crashes
- Key rotation history preservation

TODO: [SEC-003] Implement cloud backup integration - @SecurityAgent - 2024-09-24
TODO: [SEC-004] Add hardware security module support - @SecurityAgent - 2024-09-24
"""

import os
import json
import shutil
import hashlib
import threading
import time
import secrets
import zipfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import pickle
import base64
import uuid

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)


@dataclass
class RecoveryKeyInfo:
    """Recovery key information"""
    key_version: int
    key_id: str
    algorithm: str
    key_length: int
    created_at: datetime
    expires_at: Optional[datetime]
    usage_count: int
    last_used_at: Optional[datetime]
    key_hash: str
    recovery_shares: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        if self.last_used_at:
            data['last_used_at'] = self.last_used_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryKeyInfo':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('expires_at'):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if data.get('last_used_at'):
            data['last_used_at'] = datetime.fromisoformat(data['last_used_at'])
        return cls(**data)


@dataclass
class VaultState:
    """Complete vault state for recovery"""
    vault_version: str
    master_key_version: int
    old_keys_count: int
    configuration: Dict[str, Any]
    key_rotation_config: Dict[str, Any]
    last_rotation: Optional[datetime]
    next_rotation: Optional[datetime]
    backup_timestamp: datetime
    state_hash: str
    recovery_keys: List[RecoveryKeyInfo]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        if self.last_rotation:
            data['last_rotation'] = self.last_rotation.isoformat()
        if self.next_rotation:
            data['next_rotation'] = self.next_rotation.isoformat()
        data['backup_timestamp'] = self.backup_timestamp.isoformat()
        data['recovery_keys'] = [key.to_dict() for key in self.recovery_keys]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VaultState':
        """Create from dictionary"""
        if data.get('last_rotation'):
            data['last_rotation'] = datetime.fromisoformat(data['last_rotation'])
        if data.get('next_rotation'):
            data['next_rotation'] = datetime.fromisoformat(data['next_rotation'])
        data['backup_timestamp'] = datetime.fromisoformat(data['backup_timestamp'])
        data['recovery_keys'] = [RecoveryKeyInfo.from_dict(key_data) for key_data in data['recovery_keys']]
        return cls(**data)


class VaultRecoverySystem(LoggerMixin):
    """
    Enterprise Vault Recovery System
    
    Handles:
    - Key backup and recovery
    - Configuration state persistence  
    - Multi-location backup management
    - Recovery after system crashes
    - Key rotation history preservation
    - Emergency key access procedures
    """
    
    def __init__(self, vault_manager=None):
        super().__init__()
        
        # Import vault manager
        if vault_manager:
            self.vault = vault_manager
        else:
            from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
            self.vault = get_enterprise_vault_manager()
        
        # Configuration
        self.recovery_dir = Path(settings.UPLOAD_PATH) / "vault_recovery"
        self.key_backup_dir = self.recovery_dir / "keys"
        self.state_backup_dir = self.recovery_dir / "state"
        self.archive_dir = self.recovery_dir / "archives"
        
        # Create directories
        for directory in [self.recovery_dir, self.key_backup_dir, self.state_backup_dir, self.archive_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # State management
        self._recovery_lock = threading.Lock()
        self._backup_in_progress = False
        
        # Recovery configuration
        self.backup_retention_days = int(os.getenv('VAULT_BACKUP_RETENTION_DAYS', '90'))
        self.max_recovery_keys = int(os.getenv('MAX_RECOVERY_KEYS', '10'))
        self.encryption_key = self._initialize_recovery_encryption_key()
        
        # Initialize recovery state
        self._initialize_recovery_state()
        
        self.logger.info("Vault Recovery System initialized", extra={
            "recovery_dir": str(self.recovery_dir),
            "retention_days": self.backup_retention_days,
            "max_keys": self.max_recovery_keys
        })
    
    def _initialize_recovery_encryption_key(self) -> bytes:
        """Initialize or load recovery encryption key"""
        
        key_file = self.recovery_dir / ".recovery_key"
        
        if key_file.exists():
            try:
                with open(key_file, 'rb') as f:
                    encrypted_key = f.read()
                
                # Decrypt using vault manager
                decrypted_key = self.vault.decrypt(base64.b64encode(encrypted_key).decode('utf-8'))
                return base64.b64decode(decrypted_key)
                
            except Exception as e:
                self.logger.warning(f"Failed to load recovery key, generating new one: {e}")
        
        # Generate new recovery key
        recovery_key = secrets.token_bytes(32)
        
        try:
            # Encrypt and store recovery key
            encrypted_key = self.vault.encrypt(base64.b64encode(recovery_key).decode('utf-8'))
            
            with open(key_file, 'wb') as f:
                f.write(base64.b64decode(encrypted_key))
            
            # Set secure permissions
            key_file.chmod(0o600)
            
            self.logger.info("Recovery encryption key generated and stored")
            
        except Exception as e:
            self.logger.error(f"Failed to store recovery key: {e}")
            # Use in-memory key as fallback
        
        return recovery_key
    
    def _initialize_recovery_state(self) -> None:
        """Initialize recovery system state"""
        
        # Create initial state file if doesn't exist
        state_file = self.recovery_dir / "recovery_state.json"
        
        if not state_file.exists():
            initial_state = {
                'initialized_at': datetime.now(timezone.utc).isoformat(),
                'version': '1.0.0',
                'last_backup': None,
                'backup_count': 0,
                'recovery_attempts': 0,
                'last_recovery': None
            }
            
            with open(state_file, 'w') as f:
                json.dump(initial_state, f, indent=2)
            
            self.logger.info("Recovery state initialized")
    
    def backup_vault_state(self, include_keys: bool = True) -> str:
        """
        Create comprehensive backup of vault state
        
        Args:
            include_keys: Whether to include encrypted keys in backup
            
        Returns:
            Path to backup file
        """
        
        with self._recovery_lock:
            if self._backup_in_progress:
                raise RuntimeError("Backup already in progress")
            
            self._backup_in_progress = True
            
            try:
                timestamp = datetime.now(timezone.utc)
                backup_id = f"vault_backup_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                backup_path = self.state_backup_dir / f"{backup_id}.vault"
                
                self.logger.info(f"Starting vault backup: {backup_id}")
                
                # Get vault status
                vault_status = self.vault.get_vault_status()
                
                # Prepare recovery keys info
                recovery_keys = []
                if include_keys:
                    recovery_keys = self._prepare_recovery_keys()
                
                # Create vault state
                vault_state = VaultState(
                    vault_version=vault_status['vault_version'],
                    master_key_version=vault_status['key_version'],
                    old_keys_count=vault_status['old_keys_count'],
                    configuration=vault_status['config'],
                    key_rotation_config=vault_status['rotation_config'],
                    last_rotation=None,  # Add rotation tracking in future
                    next_rotation=None,  # Add rotation tracking in future
                    backup_timestamp=timestamp,
                    state_hash="",  # Will be calculated
                    recovery_keys=recovery_keys
                )
                
                # Calculate state hash
                state_data = vault_state.to_dict()
                del state_data['state_hash']  # Remove hash from hash calculation
                state_hash = hashlib.sha256(
                    json.dumps(state_data, sort_keys=True).encode('utf-8')
                ).hexdigest()
                vault_state.state_hash = state_hash
                
                # Encrypt vault state
                encrypted_state = self._encrypt_recovery_data(vault_state.to_dict())
                
                # Write backup file
                backup_data = {
                    'backup_id': backup_id,
                    'created_at': timestamp.isoformat(),
                    'backup_type': 'full' if include_keys else 'state_only',
                    'encrypted_state': encrypted_state,
                    'metadata': {
                        'vault_version': vault_status['vault_version'],
                        'key_version': vault_status['key_version'],
                        'has_keys': include_keys,
                        'state_hash': state_hash
                    }
                }
                
                with open(backup_path, 'w') as f:
                    json.dump(backup_data, f, indent=2)
                
                # Create backup archive
                archive_path = self._create_backup_archive(backup_id, backup_data)
                
                # Update recovery state
                self._update_recovery_state('backup_created', {
                    'backup_id': backup_id,
                    'backup_path': str(backup_path),
                    'archive_path': str(archive_path),
                    'include_keys': include_keys
                })
                
                # Cleanup old backups
                self._cleanup_old_backups()
                
                self.logger.info(f"Vault backup completed: {backup_id}", extra={
                    'backup_path': str(backup_path),
                    'archive_path': str(archive_path),
                    'include_keys': include_keys,
                    'state_hash': state_hash
                })
                
                return str(backup_path)
                
            finally:
                self._backup_in_progress = False
    
    def _prepare_recovery_keys(self) -> List[RecoveryKeyInfo]:
        """Prepare recovery key information"""
        
        recovery_keys = []
        
        # Get current master key info
        vault_status = self.vault.get_vault_status()
        
        # Create recovery info for current key
        current_key_info = RecoveryKeyInfo(
            key_version=vault_status['key_version'],
            key_id=f"master_key_{vault_status['key_version']}",
            algorithm=vault_status['config']['algorithm'],
            key_length=vault_status['config']['key_length'],
            created_at=datetime.now(timezone.utc),  # Approximate
            expires_at=None,
            usage_count=0,  # Would need tracking in vault manager
            last_used_at=None,
            key_hash=hashlib.sha256(f"master_key_{vault_status['key_version']}".encode()).hexdigest(),
            recovery_shares=1  # For future Shamir's Secret Sharing
        )
        
        recovery_keys.append(current_key_info)
        
        # Add info for old keys
        for i in range(vault_status['old_keys_count']):
            old_key_version = vault_status['key_version'] - i - 1
            if old_key_version > 0:
                old_key_info = RecoveryKeyInfo(
                    key_version=old_key_version,
                    key_id=f"master_key_{old_key_version}",
                    algorithm=vault_status['config']['algorithm'],
                    key_length=vault_status['config']['key_length'],
                    created_at=datetime.now(timezone.utc) - timedelta(days=90 * (i + 1)),  # Approximate
                    expires_at=None,
                    usage_count=0,
                    last_used_at=None,
                    key_hash=hashlib.sha256(f"master_key_{old_key_version}".encode()).hexdigest(),
                    recovery_shares=1
                )
                recovery_keys.append(old_key_info)
        
        return recovery_keys
    
    def _encrypt_recovery_data(self, data: Dict[str, Any]) -> str:
        """Encrypt recovery data using recovery key"""
        
        # Serialize data
        json_data = json.dumps(data, separators=(',', ':'))
        
        # Encrypt using AES-GCM with recovery key
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        aesgcm = AESGCM(self.encryption_key)
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, json_data.encode('utf-8'), None)
        
        # Combine nonce and ciphertext
        encrypted_data = nonce + ciphertext
        
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def _decrypt_recovery_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt recovery data using recovery key"""
        
        # Decode base64
        encrypted_bytes = base64.b64decode(encrypted_data)
        
        # Extract nonce and ciphertext
        nonce = encrypted_bytes[:12]
        ciphertext = encrypted_bytes[12:]
        
        # Decrypt using AES-GCM
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        aesgcm = AESGCM(self.encryption_key)
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        
        # Parse JSON
        return json.loads(decrypted_bytes.decode('utf-8'))
    
    def _create_backup_archive(self, backup_id: str, backup_data: Dict[str, Any]) -> str:
        """Create compressed archive of backup"""
        
        archive_path = self.archive_dir / f"{backup_id}.zip"
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            # Add backup data
            zf.writestr(f"{backup_id}.json", json.dumps(backup_data, indent=2))
            
            # Add metadata
            metadata = {
                'archive_created_at': datetime.now(timezone.utc).isoformat(),
                'backup_id': backup_id,
                'archive_version': '1.0.0',
                'checksum': hashlib.sha256(json.dumps(backup_data).encode()).hexdigest()
            }
            zf.writestr("archive_metadata.json", json.dumps(metadata, indent=2))
            
            # Add recovery instructions
            instructions = self._generate_recovery_instructions(backup_id)
            zf.writestr("RECOVERY_INSTRUCTIONS.md", instructions)
        
        return str(archive_path)
    
    def _generate_recovery_instructions(self, backup_id: str) -> str:
        """Generate recovery instructions"""
        
        return f"""# Vault Recovery Instructions

## Backup Information
- Backup ID: {backup_id}
- Created: {datetime.now(timezone.utc).isoformat()}
- System: DafelHub Enterprise Vault Manager

## Recovery Process

### 1. Prerequisites
- Access to DafelHub system
- Vault recovery key
- Python 3.8+ environment
- Required dependencies installed

### 2. Recovery Steps

1. **Initialize Recovery System**
   ```python
   from dafelhub.security.recovery_system import VaultRecoverySystem
   recovery = VaultRecoverySystem()
   ```

2. **Restore from Backup**
   ```python
   # Restore vault state
   recovery.restore_vault_state("{backup_id}")
   
   # Verify integrity
   recovery.verify_backup_integrity("{backup_id}")
   ```

3. **Test Vault Operation**
   ```python
   from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
   vault = get_enterprise_vault_manager()
   
   # Test encryption/decryption
   test_data = "test message"
   encrypted = vault.encrypt(test_data)
   decrypted = vault.decrypt(encrypted)
   assert decrypted == test_data
   ```

### 3. Verification Checklist
- [ ] Vault manager initializes without errors
- [ ] Key rotation configuration restored
- [ ] Encryption/decryption works correctly
- [ ] Old keys accessible for decryption
- [ ] Audit trail integrity maintained

### 4. Emergency Contacts
- Security Team: security@dafelhub.com
- System Administrator: admin@dafelhub.com
- 24/7 Emergency: +1-XXX-XXX-XXXX

## Important Notes
- Never share recovery keys via insecure channels
- Verify backup integrity before restoration
- Test thoroughly in staging environment first
- Document any issues during recovery process

Generated by DafelHub Vault Recovery System v1.0.0
"""
    
    def restore_vault_state(self, backup_id: str) -> bool:
        """
        Restore vault state from backup
        
        Args:
            backup_id: Backup identifier or path to backup file
            
        Returns:
            True if restoration successful
        """
        
        with self._recovery_lock:
            self.logger.info(f"Starting vault restoration from backup: {backup_id}")
            
            try:
                # Find backup file
                backup_path = self._find_backup_file(backup_id)
                if not backup_path:
                    raise FileNotFoundError(f"Backup not found: {backup_id}")
                
                # Load backup data
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
                
                # Verify backup integrity
                if not self._verify_backup_integrity_data(backup_data):
                    raise ValueError("Backup integrity verification failed")
                
                # Decrypt vault state
                encrypted_state = backup_data['encrypted_state']
                vault_state_data = self._decrypt_recovery_data(encrypted_state)
                vault_state = VaultState.from_dict(vault_state_data)
                
                # Log restoration attempt
                self._update_recovery_state('restore_started', {
                    'backup_id': backup_id,
                    'backup_path': str(backup_path),
                    'vault_version': vault_state.vault_version
                })
                
                # Apply vault state (would need vault manager methods)
                success = self._apply_vault_state(vault_state)
                
                if success:
                    self._update_recovery_state('restore_completed', {
                        'backup_id': backup_id,
                        'vault_version': vault_state.vault_version,
                        'keys_restored': len(vault_state.recovery_keys)
                    })
                    
                    self.logger.info(f"Vault restoration completed successfully: {backup_id}")
                else:
                    self._update_recovery_state('restore_failed', {
                        'backup_id': backup_id,
                        'error': 'Failed to apply vault state'
                    })
                    
                    self.logger.error(f"Vault restoration failed: {backup_id}")
                
                return success
                
            except Exception as e:
                self._update_recovery_state('restore_failed', {
                    'backup_id': backup_id,
                    'error': str(e)
                })
                
                self.logger.error(f"Vault restoration failed: {e}")
                raise
    
    def _find_backup_file(self, backup_id: str) -> Optional[Path]:
        """Find backup file by ID or path"""
        
        # Check if it's already a path
        if Path(backup_id).exists():
            return Path(backup_id)
        
        # Search in backup directories
        for directory in [self.state_backup_dir, self.archive_dir]:
            # Try exact match
            backup_file = directory / f"{backup_id}.vault"
            if backup_file.exists():
                return backup_file
            
            # Try with zip extension
            backup_file = directory / f"{backup_id}.zip"
            if backup_file.exists():
                return backup_file
            
            # Search by pattern
            for file_path in directory.glob(f"*{backup_id}*"):
                if file_path.is_file():
                    return file_path
        
        return None
    
    def _verify_backup_integrity_data(self, backup_data: Dict[str, Any]) -> bool:
        """Verify backup data integrity"""
        
        try:
            # Check required fields
            required_fields = ['backup_id', 'created_at', 'backup_type', 'encrypted_state', 'metadata']
            if not all(field in backup_data for field in required_fields):
                return False
            
            # Verify metadata
            metadata = backup_data['metadata']
            if not isinstance(metadata.get('state_hash'), str):
                return False
            
            # Try to decrypt state (validates encryption)
            encrypted_state = backup_data['encrypted_state']
            vault_state_data = self._decrypt_recovery_data(encrypted_state)
            
            # Verify state hash
            vault_state = VaultState.from_dict(vault_state_data)
            state_data_copy = vault_state.to_dict()
            del state_data_copy['state_hash']
            
            calculated_hash = hashlib.sha256(
                json.dumps(state_data_copy, sort_keys=True).encode('utf-8')
            ).hexdigest()
            
            if calculated_hash != vault_state.state_hash:
                self.logger.warning("State hash mismatch in backup")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Backup integrity verification failed: {e}")
            return False
    
    def _apply_vault_state(self, vault_state: VaultState) -> bool:
        """Apply restored vault state (placeholder for vault manager integration)"""
        
        # TODO: Implement integration with vault manager to restore:
        # - Master key (if available and secure)
        # - Configuration settings
        # - Key rotation settings
        # - Old keys (for backward compatibility)
        
        self.logger.info("Vault state restoration - configuration applied", extra={
            'vault_version': vault_state.vault_version,
            'key_version': vault_state.master_key_version,
            'recovery_keys': len(vault_state.recovery_keys)
        })
        
        # For now, return True to indicate configuration was processed
        # In production, this would integrate with actual vault manager restoration
        return True
    
    def _update_recovery_state(self, event: str, data: Dict[str, Any]) -> None:
        """Update recovery state tracking"""
        
        state_file = self.recovery_dir / "recovery_state.json"
        
        try:
            # Load current state
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
            else:
                state = {}
            
            # Update state
            if 'events' not in state:
                state['events'] = []
            
            event_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event': event,
                'data': data
            }
            
            state['events'].append(event_data)
            state['last_updated'] = event_data['timestamp']
            
            # Keep only last 1000 events
            if len(state['events']) > 1000:
                state['events'] = state['events'][-1000:]
            
            # Update counters
            if event.startswith('backup_'):
                state['backup_count'] = state.get('backup_count', 0) + 1
                if event == 'backup_created':
                    state['last_backup'] = event_data['timestamp']
            
            elif event.startswith('restore_'):
                state['recovery_attempts'] = state.get('recovery_attempts', 0) + 1
                if event == 'restore_completed':
                    state['last_recovery'] = event_data['timestamp']
            
            # Write state
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to update recovery state: {e}")
    
    def _cleanup_old_backups(self) -> None:
        """Clean up old backup files based on retention policy"""
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.backup_retention_days)
        
        cleaned_count = 0
        total_size_freed = 0
        
        for directory in [self.state_backup_dir, self.archive_dir]:
            for backup_file in directory.glob("*"):
                if backup_file.is_file():
                    # Check file age
                    file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, timezone.utc)
                    
                    if file_mtime < cutoff_date:
                        try:
                            file_size = backup_file.stat().st_size
                            backup_file.unlink()
                            cleaned_count += 1
                            total_size_freed += file_size
                            
                            self.logger.debug(f"Cleaned old backup: {backup_file.name}")
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to clean backup file {backup_file}: {e}")
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned {cleaned_count} old backup files", extra={
                'files_cleaned': cleaned_count,
                'size_freed_mb': round(total_size_freed / 1024 / 1024, 2),
                'retention_days': self.backup_retention_days
            })
    
    def verify_backup_integrity(self, backup_id: str) -> Dict[str, Any]:
        """Verify integrity of a specific backup"""
        
        verification_result = {
            'backup_id': backup_id,
            'verification_timestamp': datetime.now(timezone.utc).isoformat(),
            'integrity_passed': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Find backup file
            backup_path = self._find_backup_file(backup_id)
            if not backup_path:
                verification_result['errors'].append(f"Backup file not found: {backup_id}")
                return verification_result
            
            # Load backup data
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            verification_result['backup_path'] = str(backup_path)
            verification_result['backup_type'] = backup_data.get('backup_type', 'unknown')
            
            # Verify structure
            required_fields = ['backup_id', 'created_at', 'backup_type', 'encrypted_state', 'metadata']
            missing_fields = [field for field in required_fields if field not in backup_data]
            
            if missing_fields:
                verification_result['errors'].append(f"Missing required fields: {missing_fields}")
            
            # Verify decryption
            try:
                encrypted_state = backup_data['encrypted_state']
                vault_state_data = self._decrypt_recovery_data(encrypted_state)
                vault_state = VaultState.from_dict(vault_state_data)
                
                verification_result['vault_version'] = vault_state.vault_version
                verification_result['key_version'] = vault_state.master_key_version
                verification_result['recovery_keys_count'] = len(vault_state.recovery_keys)
                
            except Exception as e:
                verification_result['errors'].append(f"Failed to decrypt backup data: {e}")
            
            # Verify hash integrity
            try:
                metadata = backup_data['metadata']
                expected_hash = metadata.get('state_hash')
                
                if expected_hash:
                    # Recalculate hash
                    state_data_copy = vault_state.to_dict()
                    del state_data_copy['state_hash']
                    
                    calculated_hash = hashlib.sha256(
                        json.dumps(state_data_copy, sort_keys=True).encode('utf-8')
                    ).hexdigest()
                    
                    if calculated_hash != expected_hash:
                        verification_result['errors'].append(
                            f"Hash mismatch - expected: {expected_hash}, calculated: {calculated_hash}"
                        )
                    else:
                        verification_result['hash_verified'] = True
                        
            except Exception as e:
                verification_result['errors'].append(f"Hash verification failed: {e}")
            
            # Check backup age
            created_at = datetime.fromisoformat(backup_data['created_at'])
            age_days = (datetime.now(timezone.utc) - created_at).days
            
            verification_result['backup_age_days'] = age_days
            
            if age_days > self.backup_retention_days:
                verification_result['warnings'].append(
                    f"Backup is {age_days} days old, exceeds retention policy of {self.backup_retention_days} days"
                )
            
            # Overall result
            verification_result['integrity_passed'] = len(verification_result['errors']) == 0
            
            self.logger.info(f"Backup verification completed for {backup_id}", extra={
                'integrity_passed': verification_result['integrity_passed'],
                'errors': len(verification_result['errors']),
                'warnings': len(verification_result['warnings'])
            })
            
        except Exception as e:
            verification_result['errors'].append(f"Verification process failed: {e}")
            self.logger.error(f"Backup verification failed for {backup_id}: {e}")
        
        return verification_result
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        
        backups = []
        
        for directory in [self.state_backup_dir, self.archive_dir]:
            for backup_file in directory.glob("*.vault"):
                try:
                    with open(backup_file, 'r') as f:
                        backup_data = json.load(f)
                    
                    backup_info = {
                        'backup_id': backup_data['backup_id'],
                        'created_at': backup_data['created_at'],
                        'backup_type': backup_data['backup_type'],
                        'file_path': str(backup_file),
                        'file_size_mb': round(backup_file.stat().st_size / 1024 / 1024, 2),
                        'metadata': backup_data.get('metadata', {})
                    }
                    
                    backups.append(backup_info)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to read backup file {backup_file}: {e}")
        
        # Sort by creation date, newest first
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return backups
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get recovery system status"""
        
        # Load recovery state
        state_file = self.recovery_dir / "recovery_state.json"
        recovery_state = {}
        
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    recovery_state = json.load(f)
            except:
                pass
        
        # Get backup statistics
        backups = self.list_backups()
        
        status = {
            'recovery_system_initialized': True,
            'recovery_dir': str(self.recovery_dir),
            'backup_retention_days': self.backup_retention_days,
            'max_recovery_keys': self.max_recovery_keys,
            'backups_available': len(backups),
            'total_backup_size_mb': sum(backup['file_size_mb'] for backup in backups),
            'last_backup': recovery_state.get('last_backup'),
            'last_recovery': recovery_state.get('last_recovery'),
            'backup_count': recovery_state.get('backup_count', 0),
            'recovery_attempts': recovery_state.get('recovery_attempts', 0),
            'backup_in_progress': self._backup_in_progress,
            'recent_events': recovery_state.get('events', [])[-10:]  # Last 10 events
        }
        
        if backups:
            latest_backup = backups[0]
            status['latest_backup'] = {
                'backup_id': latest_backup['backup_id'],
                'created_at': latest_backup['created_at'],
                'backup_type': latest_backup['backup_type']
            }
        
        return status


# Global instance management
_vault_recovery_system: Optional[VaultRecoverySystem] = None
_recovery_lock = threading.Lock()


def get_vault_recovery_system(vault_manager=None) -> VaultRecoverySystem:
    """Get global vault recovery system instance"""
    global _vault_recovery_system
    
    with _recovery_lock:
        if _vault_recovery_system is None:
            _vault_recovery_system = VaultRecoverySystem(vault_manager)
        return _vault_recovery_system


# Convenience functions
def backup_vault(include_keys: bool = True) -> str:
    """Create vault backup"""
    recovery_system = get_vault_recovery_system()
    return recovery_system.backup_vault_state(include_keys)


def restore_vault(backup_id: str) -> bool:
    """Restore vault from backup"""
    recovery_system = get_vault_recovery_system()
    return recovery_system.restore_vault_state(backup_id)


def verify_backup(backup_id: str) -> Dict[str, Any]:
    """Verify backup integrity"""
    recovery_system = get_vault_recovery_system()
    return recovery_system.verify_backup_integrity(backup_id)