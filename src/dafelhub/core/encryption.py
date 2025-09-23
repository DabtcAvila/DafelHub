"""
DafelHub Encryption Module
Enterprise AES-256-GCM encryption adapted from Dafel-Technologies VaultManager
"""

import os
import json
import base64
import secrets
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)


class EncryptionError(Exception):
    """Encryption-related errors"""
    pass


class VaultManager(LoggerMixin):
    """
    Enterprise Vault Manager
    AES-256-GCM encryption for sensitive data with key rotation
    """
    
    _instance: Optional['VaultManager'] = None
    
    def __new__(cls) -> 'VaultManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._master_key: Optional[bytes] = None
        self._keys: Dict[str, bytes] = {}
        self._key_versions: Dict[str, int] = {}
        self._vault_file = settings.UPLOAD_PATH / "vault.enc"
        self._initialized = True
        
        # Initialize master key
        self._initialize_master_key()
        
        self.logger.info("VaultManager initialized with AES-256-GCM")
    
    @classmethod
    def get_instance(cls) -> 'VaultManager':
        """Get singleton instance"""
        return cls()
    
    def _initialize_master_key(self) -> None:
        """Initialize or load master key"""
        try:
            # Try to load existing key from environment
            master_key_b64 = os.getenv('DAFELHUB_MASTER_KEY')
            if master_key_b64:
                self._master_key = base64.b64decode(master_key_b64)
                self.logger.info("Master key loaded from environment")
                return
            
            # Generate new master key if none exists
            self._master_key = AESGCM.generate_key(bit_length=256)
            
            # Save to environment (in production, use secure key management)
            master_key_b64 = base64.b64encode(self._master_key).decode('utf-8')
            os.environ['DAFELHUB_MASTER_KEY'] = master_key_b64
            
            self.logger.warning("Generated new master key - save DAFELHUB_MASTER_KEY to environment")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize master key: {e}")
            raise EncryptionError(f"Master key initialization failed: {e}")
    
    def encrypt_data(self, data: Any, key_id: str = "default") -> str:
        """
        Encrypt data with AES-256-GCM
        
        Args:
            data: Data to encrypt (will be JSON serialized)
            key_id: Key identifier for key rotation
            
        Returns:
            Base64 encoded encrypted data with metadata
        """
        try:
            if not self._master_key:
                raise EncryptionError("Master key not available")
            
            # Serialize data
            if isinstance(data, (dict, list)):
                plaintext = json.dumps(data).encode('utf-8')
            elif isinstance(data, str):
                plaintext = data.encode('utf-8')
            else:
                plaintext = str(data).encode('utf-8')
            
            # Get or create encryption key
            encryption_key = self._get_or_create_key(key_id)
            
            # Generate random nonce (IV)
            nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
            
            # Create AESGCM cipher
            aesgcm = AESGCM(encryption_key)
            
            # Encrypt with additional authenticated data
            aad = json.dumps({
                "key_id": key_id,
                "version": self._key_versions.get(key_id, 1),
                "timestamp": datetime.now().isoformat()
            }).encode('utf-8')
            
            ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
            
            # Create encrypted package
            encrypted_package = {
                "version": "1.0",
                "key_id": key_id,
                "key_version": self._key_versions.get(key_id, 1),
                "algorithm": "AES-256-GCM",
                "nonce": base64.b64encode(nonce).decode('utf-8'),
                "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
                "aad": base64.b64encode(aad).decode('utf-8'),
                "timestamp": datetime.now().isoformat()
            }
            
            # Return base64 encoded package
            package_json = json.dumps(encrypted_package)
            result = base64.b64encode(package_json.encode('utf-8')).decode('utf-8')
            
            self.logger.debug(f"Data encrypted successfully with key: {key_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Encryption failed: {e}")
    
    def decrypt_data(self, encrypted_data: str) -> Any:
        """
        Decrypt data with AES-256-GCM
        
        Args:
            encrypted_data: Base64 encoded encrypted package
            
        Returns:
            Decrypted data (original type preserved)
        """
        try:
            if not self._master_key:
                raise EncryptionError("Master key not available")
            
            # Decode package
            package_json = base64.b64decode(encrypted_data.encode('utf-8')).decode('utf-8')
            encrypted_package = json.loads(package_json)
            
            # Validate package
            required_fields = ['key_id', 'nonce', 'ciphertext', 'aad']
            for field in required_fields:
                if field not in encrypted_package:
                    raise EncryptionError(f"Missing field in encrypted package: {field}")
            
            # Get encryption key
            key_id = encrypted_package['key_id']
            encryption_key = self._get_key(key_id)
            if not encryption_key:
                raise EncryptionError(f"Encryption key not found: {key_id}")
            
            # Decode components
            nonce = base64.b64decode(encrypted_package['nonce'].encode('utf-8'))
            ciphertext = base64.b64decode(encrypted_package['ciphertext'].encode('utf-8'))
            aad = base64.b64decode(encrypted_package['aad'].encode('utf-8'))
            
            # Create AESGCM cipher
            aesgcm = AESGCM(encryption_key)
            
            # Decrypt
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
            decrypted_str = plaintext.decode('utf-8')
            
            # Try to parse as JSON, fallback to string
            try:
                result = json.loads(decrypted_str)
            except json.JSONDecodeError:
                result = decrypted_str
            
            self.logger.debug(f"Data decrypted successfully with key: {key_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Decryption failed: {e}")
    
    def rotate_key(self, key_id: str = "default") -> None:
        """
        Rotate encryption key
        
        Args:
            key_id: Key identifier to rotate
        """
        try:
            # Generate new key
            new_key = self._derive_key(key_id, self._key_versions.get(key_id, 1) + 1)
            
            # Update version
            self._key_versions[key_id] = self._key_versions.get(key_id, 1) + 1
            
            # Store new key
            self._keys[key_id] = new_key
            
            self.logger.info(f"Key rotated successfully: {key_id} (version {self._key_versions[key_id]})")
            
        except Exception as e:
            self.logger.error(f"Key rotation failed: {e}")
            raise EncryptionError(f"Key rotation failed: {e}")
    
    def _get_or_create_key(self, key_id: str) -> bytes:
        """Get existing key or create new one"""
        if key_id in self._keys:
            return self._keys[key_id]
        
        # Create new key
        version = self._key_versions.get(key_id, 1)
        key = self._derive_key(key_id, version)
        self._keys[key_id] = key
        self._key_versions[key_id] = version
        
        return key
    
    def _get_key(self, key_id: str) -> Optional[bytes]:
        """Get existing key"""
        return self._keys.get(key_id)
    
    def _derive_key(self, key_id: str, version: int) -> bytes:
        """Derive encryption key from master key using PBKDF2"""
        if not self._master_key:
            raise EncryptionError("Master key not available")
        
        # Create salt from key_id and version
        salt_data = f"{key_id}:{version}:dafelhub".encode('utf-8')
        salt = hashes.Hash(hashes.SHA256())
        salt.update(salt_data)
        salt_bytes = salt.finalize()[:16]  # 16 bytes salt
        
        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt_bytes,
            iterations=100000,  # OWASP recommendation
        )
        
        derived_key = kdf.derive(self._master_key)
        return derived_key
    
    def get_key_info(self, key_id: str = "default") -> Dict[str, Any]:
        """Get key information"""
        return {
            "key_id": key_id,
            "version": self._key_versions.get(key_id, 0),
            "exists": key_id in self._keys,
            "algorithm": "AES-256-GCM",
            "key_derivation": "PBKDF2-SHA256"
        }
    
    def list_keys(self) -> Dict[str, Dict[str, Any]]:
        """List all keys"""
        result = {}
        for key_id in self._keys.keys():
            result[key_id] = self.get_key_info(key_id)
        return result
    
    def clear_key(self, key_id: str) -> None:
        """Clear key from memory"""
        if key_id in self._keys:
            # Overwrite key with random data before deletion
            self._keys[key_id] = secrets.token_bytes(32)
            del self._keys[key_id]
            
        if key_id in self._key_versions:
            del self._key_versions[key_id]
            
        self.logger.info(f"Key cleared from memory: {key_id}")
    
    def clear_all_keys(self) -> None:
        """Clear all keys from memory"""
        for key_id in list(self._keys.keys()):
            self.clear_key(key_id)
        
        self.logger.info("All keys cleared from memory")


class SecureStorage(LoggerMixin):
    """
    Secure storage for sensitive configuration data
    """
    
    def __init__(self, vault_manager: Optional[VaultManager] = None):
        self.vault = vault_manager or VaultManager.get_instance()
    
    def store_connection_credentials(self, connection_id: str, credentials: Dict[str, Any]) -> None:
        """Store connection credentials securely"""
        try:
            encrypted_creds = self.vault.encrypt_data(credentials, f"conn_{connection_id}")
            
            # Store in secure location (database, secure file, etc.)
            storage_path = settings.UPLOAD_PATH / f"credentials_{connection_id}.enc"
            with open(storage_path, 'w') as f:
                f.write(encrypted_creds)
            
            self.logger.info(f"Credentials stored securely for connection: {connection_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to store credentials: {e}")
            raise
    
    def retrieve_connection_credentials(self, connection_id: str) -> Dict[str, Any]:
        """Retrieve connection credentials"""
        try:
            storage_path = settings.UPLOAD_PATH / f"credentials_{connection_id}.enc"
            
            if not storage_path.exists():
                raise EncryptionError(f"Credentials not found for connection: {connection_id}")
            
            with open(storage_path, 'r') as f:
                encrypted_creds = f.read()
            
            credentials = self.vault.decrypt_data(encrypted_creds)
            
            self.logger.debug(f"Credentials retrieved for connection: {connection_id}")
            return credentials
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve credentials: {e}")
            raise
    
    def delete_connection_credentials(self, connection_id: str) -> None:
        """Delete connection credentials"""
        try:
            storage_path = settings.UPLOAD_PATH / f"credentials_{connection_id}.enc"
            
            if storage_path.exists():
                # Overwrite file before deletion for security
                with open(storage_path, 'wb') as f:
                    f.write(secrets.token_bytes(1024))
                
                storage_path.unlink()
            
            # Clear from vault
            self.vault.clear_key(f"conn_{connection_id}")
            
            self.logger.info(f"Credentials deleted for connection: {connection_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to delete credentials: {e}")
            raise


# Singleton instances
vault_manager: Optional[VaultManager] = None
secure_storage: Optional[SecureStorage] = None


def get_vault_manager() -> VaultManager:
    """Get global vault manager instance"""
    global vault_manager
    if vault_manager is None:
        vault_manager = VaultManager.get_instance()
    return vault_manager


def get_secure_storage() -> SecureStorage:
    """Get global secure storage instance"""
    global secure_storage
    if secure_storage is None:
        secure_storage = SecureStorage()
    return secure_storage