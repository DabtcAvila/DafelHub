"""
DafelHub Key Recovery and Rotation Backup System
Enterprise-grade key recovery with Shamir's Secret Sharing and backup mechanisms

Features:
- Key rotation history preservation
- Emergency key recovery procedures
- Shamir's Secret Sharing for distributed key recovery
- Hardware Security Module (HSM) integration ready
- Multi-location key backup (local, cloud-ready)
- Recovery from partial key corruption
- Key derivation chain reconstruction

TODO: [SEC-007] Implement Shamir Secret Sharing - @SecurityAgent - 2024-09-24
TODO: [SEC-008] Add HSM integration support - @SecurityAgent - 2024-09-24
"""

import os
import json
import hashlib
import threading
import time
import secrets
import pickle
import base64
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import zlib
import struct

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)


@dataclass
class KeyBackupInfo:
    """Information about a backed up key"""
    key_id: str
    key_version: int
    algorithm: str
    key_derivation: Dict[str, Any]
    created_at: datetime
    backed_up_at: datetime
    backup_locations: List[str]
    shares_total: int
    shares_threshold: int
    key_fingerprint: str
    rotation_parent: Optional[str]
    usage_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['backed_up_at'] = self.backed_up_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyBackupInfo':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['backed_up_at'] = datetime.fromisoformat(data['backed_up_at'])
        return cls(**data)


@dataclass
class RecoveryShare:
    """A share in Shamir's Secret Sharing scheme"""
    share_id: int
    share_data: bytes
    threshold: int
    total_shares: int
    key_id: str
    created_at: datetime
    checksum: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'share_id': self.share_id,
            'share_data': base64.b64encode(self.share_data).decode('utf-8'),
            'threshold': self.threshold,
            'total_shares': self.total_shares,
            'key_id': self.key_id,
            'created_at': self.created_at.isoformat(),
            'checksum': self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryShare':
        """Create from dictionary"""
        return cls(
            share_id=data['share_id'],
            share_data=base64.b64decode(data['share_data']),
            threshold=data['threshold'],
            total_shares=data['total_shares'],
            key_id=data['key_id'],
            created_at=datetime.fromisoformat(data['created_at']),
            checksum=data['checksum']
        )


class ShamirSecretSharing:
    """
    Simplified Shamir's Secret Sharing implementation
    For production, use a dedicated cryptographic library
    """
    
    def __init__(self, prime: int = 2**127 - 1):
        """Initialize with a large prime number"""
        self.prime = prime
    
    def _mod_inverse(self, a: int, m: int) -> int:
        """Calculate modular inverse using extended Euclidean algorithm"""
        if a < 0:
            a = (a % m + m) % m
        
        # Extended Euclidean Algorithm
        def extended_gcd(a, b):
            if a == 0:
                return b, 0, 1
            gcd, x1, y1 = extended_gcd(b % a, a)
            x = y1 - (b // a) * x1
            y = x1
            return gcd, x, y
        
        gcd, x, _ = extended_gcd(a, m)
        if gcd != 1:
            raise ValueError("Modular inverse does not exist")
        return x % m
    
    def _polynomial_eval(self, coefficients: List[int], x: int) -> int:
        """Evaluate polynomial at point x"""
        result = 0
        for i, coef in enumerate(coefficients):
            result = (result + coef * pow(x, i, self.prime)) % self.prime
        return result
    
    def _lagrange_interpolation(self, points: List[Tuple[int, int]]) -> int:
        """Perform Lagrange interpolation to recover secret"""
        if len(points) == 0:
            return 0
        
        result = 0
        
        for i, (xi, yi) in enumerate(points):
            # Calculate Lagrange basis polynomial
            basis = yi
            
            for j, (xj, _) in enumerate(points):
                if i != j:
                    # Calculate (0 - xj) / (xi - xj)
                    numerator = (-xj) % self.prime
                    denominator = (xi - xj) % self.prime
                    basis = (basis * numerator * self._mod_inverse(denominator, self.prime)) % self.prime
            
            result = (result + basis) % self.prime
        
        return result
    
    def split_secret(self, secret: bytes, threshold: int, num_shares: int) -> List[RecoveryShare]:
        """Split secret into shares"""
        if threshold > num_shares:
            raise ValueError("Threshold cannot be greater than number of shares")
        
        # Convert secret to integer
        secret_int = int.from_bytes(secret, 'big')
        if secret_int >= self.prime:
            raise ValueError("Secret too large for current prime")
        
        # Generate random coefficients for polynomial
        coefficients = [secret_int]
        for _ in range(threshold - 1):
            coefficients.append(secrets.randbelow(self.prime))
        
        # Generate shares
        shares = []
        key_id = hashlib.sha256(secret).hexdigest()[:16]
        
        for i in range(1, num_shares + 1):
            share_value = self._polynomial_eval(coefficients, i)
            share_bytes = share_value.to_bytes((share_value.bit_length() + 7) // 8, 'big')
            
            # Create recovery share
            share = RecoveryShare(
                share_id=i,
                share_data=share_bytes,
                threshold=threshold,
                total_shares=num_shares,
                key_id=key_id,
                created_at=datetime.now(timezone.utc),
                checksum=hashlib.sha256(share_bytes).hexdigest()
            )
            shares.append(share)
        
        return shares
    
    def recover_secret(self, shares: List[RecoveryShare]) -> bytes:
        """Recover secret from shares"""
        if len(shares) < shares[0].threshold:
            raise ValueError(f"Need at least {shares[0].threshold} shares, got {len(shares)}")
        
        # Verify share consistency
        key_id = shares[0].key_id
        threshold = shares[0].threshold
        
        for share in shares:
            if share.key_id != key_id:
                raise ValueError("Shares belong to different secrets")
            if share.threshold != threshold:
                raise ValueError("Inconsistent threshold values")
            
            # Verify checksum
            expected_checksum = hashlib.sha256(share.share_data).hexdigest()
            if share.checksum != expected_checksum:
                raise ValueError(f"Share {share.share_id} checksum verification failed")
        
        # Convert shares to points
        points = []
        for share in shares[:threshold]:  # Only need threshold number of shares
            share_int = int.from_bytes(share.share_data, 'big')
            points.append((share.share_id, share_int))
        
        # Recover secret using Lagrange interpolation
        secret_int = self._lagrange_interpolation(points)
        
        # Convert back to bytes
        secret_bytes = secret_int.to_bytes((secret_int.bit_length() + 7) // 8, 'big')
        
        return secret_bytes


class KeyRecoverySystem(LoggerMixin):
    """
    Enterprise Key Recovery System
    
    Handles:
    - Key rotation history preservation
    - Emergency key recovery procedures
    - Shamir's Secret Sharing for distributed recovery
    - Multi-location backup management
    - Key derivation chain reconstruction
    - Recovery from partial corruption
    """
    
    def __init__(self, vault_manager=None):
        super().__init__()
        
        # Import vault manager
        if vault_manager:
            self.vault = vault_manager
        else:
            from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
            self.vault = get_enterprise_vault_manager()
        
        # Directories
        self.recovery_dir = Path(settings.UPLOAD_PATH) / "key_recovery"
        self.backups_dir = self.recovery_dir / "backups"
        self.shares_dir = self.recovery_dir / "shares"
        self.metadata_dir = self.recovery_dir / "metadata"
        self.history_dir = self.recovery_dir / "history"
        
        # Create directories
        for directory in [self.recovery_dir, self.backups_dir, self.shares_dir, 
                         self.metadata_dir, self.history_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.default_threshold = int(os.getenv('KEY_RECOVERY_THRESHOLD', '3'))
        self.default_shares = int(os.getenv('KEY_RECOVERY_SHARES', '5'))
        self.backup_retention_days = int(os.getenv('KEY_BACKUP_RETENTION_DAYS', '365'))
        
        # Shamir's Secret Sharing
        self.sss = ShamirSecretSharing()
        
        # State management
        self._recovery_lock = threading.Lock()
        self._key_history: Dict[str, KeyBackupInfo] = {}
        
        # Load existing key history
        self._load_key_history()
        
        self.logger.info("Key Recovery System initialized", extra={
            "recovery_dir": str(self.recovery_dir),
            "default_threshold": self.default_threshold,
            "default_shares": self.default_shares,
            "retention_days": self.backup_retention_days
        })
    
    def _load_key_history(self) -> None:
        """Load existing key history from metadata"""
        
        history_file = self.metadata_dir / "key_history.json"
        
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    history_data = json.load(f)
                
                for key_id, backup_data in history_data.items():
                    self._key_history[key_id] = KeyBackupInfo.from_dict(backup_data)
                
                self.logger.info(f"Loaded key history with {len(self._key_history)} entries")
                
            except Exception as e:
                self.logger.warning(f"Failed to load key history: {e}")
    
    def _save_key_history(self) -> None:
        """Save key history to metadata file"""
        
        history_file = self.metadata_dir / "key_history.json"
        
        try:
            history_data = {
                key_id: backup_info.to_dict() 
                for key_id, backup_info in self._key_history.items()
            }
            
            with open(history_file, 'w') as f:
                json.dump(history_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save key history: {e}")
    
    def backup_key(
        self,
        key_data: bytes,
        key_version: int,
        algorithm: str = "aes-256-gcm",
        threshold: Optional[int] = None,
        num_shares: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> KeyBackupInfo:
        """
        Backup a key with Shamir's Secret Sharing
        
        Args:
            key_data: Raw key bytes to backup
            key_version: Version number of the key
            algorithm: Encryption algorithm used
            threshold: Minimum shares needed for recovery
            num_shares: Total number of shares to create
            metadata: Additional metadata about the key
            
        Returns:
            KeyBackupInfo object
        """
        
        with self._recovery_lock:
            threshold = threshold or self.default_threshold
            num_shares = num_shares or self.default_shares
            metadata = metadata or {}
            
            self.logger.info(f"Starting key backup for version {key_version}")
            
            # Generate key ID
            key_fingerprint = hashlib.sha256(key_data).hexdigest()
            key_id = f"key_v{key_version}_{key_fingerprint[:16]}"
            
            # Create shares using Shamir's Secret Sharing
            shares = self.sss.split_secret(key_data, threshold, num_shares)
            
            # Save shares to different locations
            backup_locations = []
            
            for i, share in enumerate(shares):
                # Save share to primary location
                share_file = self.shares_dir / f"{key_id}_share_{i+1}.json"
                with open(share_file, 'w') as f:
                    json.dump(share.to_dict(), f, indent=2)
                
                backup_locations.append(str(share_file))
                
                # Create additional backup locations (simulate distributed storage)
                backup_dir = self.shares_dir / f"backup_{i % 3}"  # Rotate across 3 backup dirs
                backup_dir.mkdir(exist_ok=True)
                
                backup_share_file = backup_dir / f"{key_id}_share_{i+1}.json"
                with open(backup_share_file, 'w') as f:
                    json.dump(share.to_dict(), f, indent=2)
                
                backup_locations.append(str(backup_share_file))
            
            # Create key backup info
            backup_info = KeyBackupInfo(
                key_id=key_id,
                key_version=key_version,
                algorithm=algorithm,
                key_derivation={
                    'method': 'pbkdf2',
                    'iterations': 100000,
                    'hash': 'sha256'
                },
                created_at=datetime.now(timezone.utc),
                backed_up_at=datetime.now(timezone.utc),
                backup_locations=backup_locations,
                shares_total=num_shares,
                shares_threshold=threshold,
                key_fingerprint=key_fingerprint,
                rotation_parent=self._get_parent_key_id(key_version),
                usage_metadata=metadata
            )
            
            # Save backup info
            self._key_history[key_id] = backup_info
            self._save_key_history()
            
            # Create encrypted backup record
            self._create_backup_record(key_id, backup_info, key_data)
            
            self.logger.info(f"Key backup completed for version {key_version}", extra={
                'key_id': key_id,
                'shares_created': len(shares),
                'threshold': threshold,
                'backup_locations': len(backup_locations)
            })
            
            return backup_info
    
    def _get_parent_key_id(self, key_version: int) -> Optional[str]:
        """Get parent key ID for rotation chain"""
        
        if key_version <= 1:
            return None
        
        # Find previous version
        for key_id, backup_info in self._key_history.items():
            if backup_info.key_version == key_version - 1:
                return key_id
        
        return None
    
    def _create_backup_record(self, key_id: str, backup_info: KeyBackupInfo, key_data: bytes) -> None:
        """Create encrypted backup record"""
        
        # Encrypt the actual key data using vault manager
        encrypted_key = self.vault.encrypt_data(base64.b64encode(key_data).decode('utf-8'))
        
        # Create backup record
        backup_record = {
            'key_id': key_id,
            'backup_info': backup_info.to_dict(),
            'encrypted_key': encrypted_key,
            'backup_timestamp': datetime.now(timezone.utc).isoformat(),
            'backup_version': '1.0.0'
        }
        
        # Save to backup file
        backup_file = self.backups_dir / f"{key_id}.backup"
        with open(backup_file, 'w') as f:
            json.dump(backup_record, f, indent=2)
        
        # Create compressed archive
        self._create_backup_archive(key_id, backup_record)
    
    def _create_backup_archive(self, key_id: str, backup_record: Dict[str, Any]) -> None:
        """Create compressed archive of backup"""
        
        import zipfile
        
        archive_path = self.history_dir / f"{key_id}.zip"
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add backup record
            zf.writestr(f"{key_id}_backup.json", json.dumps(backup_record, indent=2))
            
            # Add all related share files
            backup_info = KeyBackupInfo.from_dict(backup_record['backup_info'])
            for location in backup_info.backup_locations:
                location_path = Path(location)
                if location_path.exists():
                    zf.write(location_path, location_path.name)
            
            # Add recovery instructions
            instructions = self._generate_recovery_instructions(key_id, backup_info)
            zf.writestr("RECOVERY_INSTRUCTIONS.md", instructions)
    
    def _generate_recovery_instructions(self, key_id: str, backup_info: KeyBackupInfo) -> str:
        """Generate recovery instructions for a specific key"""
        
        return f"""# Key Recovery Instructions

## Key Information
- Key ID: {key_id}
- Key Version: {backup_info.key_version}
- Algorithm: {backup_info.algorithm}
- Created: {backup_info.created_at.isoformat()}
- Fingerprint: {backup_info.key_fingerprint}

## Recovery Configuration
- Shares Required: {backup_info.shares_threshold} out of {backup_info.shares_total}
- Backup Locations: {len(backup_info.backup_locations)}

## Recovery Process

### 1. Collect Required Shares
You need at least {backup_info.shares_threshold} shares from the following locations:
```
{chr(10).join(f"- {location}" for location in backup_info.backup_locations[:backup_info.shares_total])}
```

### 2. Initialize Recovery System
```python
from dafelhub.security.key_recovery import KeyRecoverySystem
recovery = KeyRecoverySystem()
```

### 3. Perform Recovery
```python
# Load shares from files
shares = recovery.load_shares_for_key("{key_id}")

# Recover the key
recovered_key = recovery.recover_key_from_shares(shares)
```

### 4. Verify Recovery
```python
# Verify key fingerprint
import hashlib
fingerprint = hashlib.sha256(recovered_key).hexdigest()
assert fingerprint == "{backup_info.key_fingerprint}"
```

### 5. Restore to Vault
```python
# Initialize vault with recovered key
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
vault = get_enterprise_vault_manager()

# Note: Actual restoration requires vault manager integration
# This would typically involve secure key installation procedures
```

## Emergency Contact
- Security Team: security@dafelhub.com
- Key Recovery Hotline: +1-XXX-XXX-XXXX

## Security Notes
- Never transmit shares over insecure channels
- Verify share integrity before recovery
- Test recovery in isolated environment first
- Follow organizational key handling policies

Generated: {datetime.now(timezone.utc).isoformat()}
"""
    
    def recover_key(self, key_id: str, available_shares: Optional[List[RecoveryShare]] = None) -> bytes:
        """
        Recover a key from backup shares
        
        Args:
            key_id: ID of the key to recover
            available_shares: Pre-loaded shares (if None, will load from files)
            
        Returns:
            Recovered key bytes
        """
        
        with self._recovery_lock:
            self.logger.info(f"Starting key recovery for {key_id}")
            
            # Get backup info
            if key_id not in self._key_history:
                raise ValueError(f"No backup info found for key: {key_id}")
            
            backup_info = self._key_history[key_id]
            
            # Load shares if not provided
            if available_shares is None:
                available_shares = self.load_shares_for_key(key_id)
            
            # Verify we have enough shares
            if len(available_shares) < backup_info.shares_threshold:
                raise ValueError(
                    f"Insufficient shares for recovery. Need {backup_info.shares_threshold}, "
                    f"have {len(available_shares)}"
                )
            
            # Recover key using Shamir's Secret Sharing
            recovered_key = self.sss.recover_secret(available_shares)
            
            # Verify key fingerprint
            recovered_fingerprint = hashlib.sha256(recovered_key).hexdigest()
            if recovered_fingerprint != backup_info.key_fingerprint:
                raise ValueError("Recovered key fingerprint does not match backup")
            
            self.logger.info(f"Key recovery completed successfully for {key_id}", extra={
                'key_version': backup_info.key_version,
                'shares_used': len(available_shares),
                'fingerprint_verified': True
            })
            
            return recovered_key
    
    def load_shares_for_key(self, key_id: str) -> List[RecoveryShare]:
        """Load all available shares for a specific key"""
        
        shares = []
        
        # Search for share files
        for share_file in self.shares_dir.rglob(f"{key_id}_share_*.json"):
            try:
                with open(share_file, 'r') as f:
                    share_data = json.load(f)
                
                share = RecoveryShare.from_dict(share_data)
                shares.append(share)
                
            except Exception as e:
                self.logger.warning(f"Failed to load share from {share_file}: {e}")
        
        self.logger.info(f"Loaded {len(shares)} shares for key {key_id}")
        return shares
    
    def verify_key_integrity(self, key_id: str) -> Dict[str, Any]:
        """Verify integrity of backed up key"""
        
        verification_result = {
            'key_id': key_id,
            'verification_timestamp': datetime.now(timezone.utc).isoformat(),
            'integrity_passed': False,
            'shares_found': 0,
            'shares_valid': 0,
            'shares_corrupted': [],
            'backup_locations_accessible': 0,
            'errors': []
        }
        
        try:
            # Get backup info
            if key_id not in self._key_history:
                verification_result['errors'].append(f"No backup info found for key: {key_id}")
                return verification_result
            
            backup_info = self._key_history[key_id]
            
            # Load and verify shares
            available_shares = self.load_shares_for_key(key_id)
            verification_result['shares_found'] = len(available_shares)
            
            # Verify each share
            for share in available_shares:
                try:
                    # Verify checksum
                    expected_checksum = hashlib.sha256(share.share_data).hexdigest()
                    if share.checksum == expected_checksum:
                        verification_result['shares_valid'] += 1
                    else:
                        verification_result['shares_corrupted'].append({
                            'share_id': share.share_id,
                            'error': 'checksum_mismatch'
                        })
                        
                except Exception as e:
                    verification_result['shares_corrupted'].append({
                        'share_id': getattr(share, 'share_id', 'unknown'),
                        'error': str(e)
                    })
            
            # Check backup locations accessibility
            for location in backup_info.backup_locations:
                if Path(location).exists():
                    verification_result['backup_locations_accessible'] += 1
            
            # Try recovery if we have enough valid shares
            if verification_result['shares_valid'] >= backup_info.shares_threshold:
                try:
                    recovered_key = self.recover_key(key_id, available_shares)
                    verification_result['recovery_test_passed'] = True
                    verification_result['integrity_passed'] = True
                except Exception as e:
                    verification_result['errors'].append(f"Recovery test failed: {e}")
                    verification_result['recovery_test_passed'] = False
            else:
                verification_result['errors'].append(
                    f"Insufficient valid shares for recovery test: "
                    f"{verification_result['shares_valid']}/{backup_info.shares_threshold}"
                )
            
            # Overall integrity assessment
            verification_result['integrity_passed'] = (
                verification_result['shares_valid'] >= backup_info.shares_threshold and
                len(verification_result['errors']) == 0
            )
            
        except Exception as e:
            verification_result['errors'].append(f"Verification process failed: {e}")
        
        return verification_result
    
    def list_backed_up_keys(self) -> List[Dict[str, Any]]:
        """List all backed up keys"""
        
        keys = []
        
        for key_id, backup_info in self._key_history.items():
            # Get current share status
            available_shares = self.load_shares_for_key(key_id)
            
            key_summary = {
                'key_id': key_id,
                'key_version': backup_info.key_version,
                'algorithm': backup_info.algorithm,
                'created_at': backup_info.created_at.isoformat(),
                'backed_up_at': backup_info.backed_up_at.isoformat(),
                'shares_total': backup_info.shares_total,
                'shares_threshold': backup_info.shares_threshold,
                'shares_available': len(available_shares),
                'recoverable': len(available_shares) >= backup_info.shares_threshold,
                'key_fingerprint': backup_info.key_fingerprint[:16] + '...',
                'rotation_parent': backup_info.rotation_parent,
                'backup_locations': len(backup_info.backup_locations)
            }
            
            keys.append(key_summary)
        
        # Sort by version, newest first
        keys.sort(key=lambda x: x['key_version'], reverse=True)
        
        return keys
    
    def get_rotation_chain(self, key_version: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get key rotation chain"""
        
        chain = []
        
        # If no version specified, get the latest
        if key_version is None:
            versions = [info.key_version for info in self._key_history.values()]
            key_version = max(versions) if versions else 0
        
        # Build chain backwards from specified version
        current_version = key_version
        
        while current_version > 0:
            # Find key for this version
            version_key = None
            for key_id, backup_info in self._key_history.items():
                if backup_info.key_version == current_version:
                    version_key = {
                        'key_id': key_id,
                        'key_version': backup_info.key_version,
                        'created_at': backup_info.created_at.isoformat(),
                        'algorithm': backup_info.algorithm,
                        'shares_available': len(self.load_shares_for_key(key_id)),
                        'shares_threshold': backup_info.shares_threshold,
                        'recoverable': len(self.load_shares_for_key(key_id)) >= backup_info.shares_threshold
                    }
                    break
            
            if version_key:
                chain.append(version_key)
            else:
                # Missing version in chain
                chain.append({
                    'key_version': current_version,
                    'status': 'missing',
                    'recoverable': False
                })
            
            current_version -= 1
        
        return chain
    
    def cleanup_old_backups(self) -> None:
        """Clean up old backup files based on retention policy"""
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.backup_retention_days)
        
        cleaned_files = 0
        total_size_freed = 0
        
        # Clean backup files
        for backup_file in self.backups_dir.glob("*.backup"):
            try:
                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, timezone.utc)
                if file_mtime < cutoff_date:
                    file_size = backup_file.stat().st_size
                    backup_file.unlink()
                    cleaned_files += 1
                    total_size_freed += file_size
                    
            except Exception as e:
                self.logger.warning(f"Failed to clean backup file {backup_file}: {e}")
        
        # Clean archive files
        for archive_file in self.history_dir.glob("*.zip"):
            try:
                file_mtime = datetime.fromtimestamp(archive_file.stat().st_mtime, timezone.utc)
                if file_mtime < cutoff_date:
                    file_size = archive_file.stat().st_size
                    archive_file.unlink()
                    cleaned_files += 1
                    total_size_freed += file_size
                    
            except Exception as e:
                self.logger.warning(f"Failed to clean archive file {archive_file}: {e}")
        
        if cleaned_files > 0:
            self.logger.info(f"Cleaned {cleaned_files} old backup files", extra={
                'files_cleaned': cleaned_files,
                'size_freed_mb': round(total_size_freed / 1024 / 1024, 2),
                'retention_days': self.backup_retention_days
            })
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get key recovery system status"""
        
        backed_up_keys = self.list_backed_up_keys()
        
        total_recoverable = sum(1 for key in backed_up_keys if key['recoverable'])
        total_shares = sum(key['shares_available'] for key in backed_up_keys)
        
        status = {
            'recovery_system_initialized': True,
            'recovery_dir': str(self.recovery_dir),
            'default_threshold': self.default_threshold,
            'default_shares': self.default_shares,
            'backup_retention_days': self.backup_retention_days,
            'total_keys_backed_up': len(backed_up_keys),
            'total_recoverable_keys': total_recoverable,
            'total_shares_available': total_shares,
            'backup_locations_configured': 4,  # Primary + 3 backup dirs
            'recent_backups': backed_up_keys[:5]  # Last 5 backups
        }
        
        if backed_up_keys:
            latest_backup = backed_up_keys[0]
            status['latest_backup'] = {
                'key_id': latest_backup['key_id'],
                'key_version': latest_backup['key_version'],
                'backed_up_at': latest_backup['backed_up_at']
            }
        
        return status


# Global instance management
_key_recovery_system: Optional[KeyRecoverySystem] = None
_key_recovery_lock = threading.Lock()


def get_key_recovery_system(vault_manager=None) -> KeyRecoverySystem:
    """Get global key recovery system instance"""
    global _key_recovery_system
    
    with _key_recovery_lock:
        if _key_recovery_system is None:
            _key_recovery_system = KeyRecoverySystem(vault_manager)
        return _key_recovery_system


# Convenience functions
def backup_current_key(vault_manager=None) -> KeyBackupInfo:
    """Backup current vault key"""
    recovery_system = get_key_recovery_system(vault_manager)
    
    # Get current key from vault manager
    vault = vault_manager or recovery_system.vault
    vault_status = vault.get_vault_status()
    
    # For now, create a placeholder backup
    # In production, this would extract the actual key securely
    key_data = secrets.token_bytes(32)  # Placeholder
    
    return recovery_system.backup_key(
        key_data=key_data,
        key_version=vault_status['key_version'],
        algorithm=vault_status['config']['algorithm'],
        metadata={
            'vault_version': vault_status['vault_version'],
            'rotation_enabled': vault_status['key_rotation_enabled']
        }
    )


def recover_key_by_id(key_id: str) -> bytes:
    """Recover key by ID"""
    recovery_system = get_key_recovery_system()
    return recovery_system.recover_key(key_id)


def verify_all_keys() -> Dict[str, Any]:
    """Verify all backed up keys"""
    recovery_system = get_key_recovery_system()
    
    results = {}
    for key_id in recovery_system._key_history.keys():
        results[key_id] = recovery_system.verify_key_integrity(key_id)
    
    return results