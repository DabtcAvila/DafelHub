"""
DafelHub Automated Configuration Backup System
Enterprise-grade configuration backup with 15-minute intervals

Features:
- Automated configuration backup every 15 minutes
- Configuration change detection and versioning
- Encrypted configuration storage
- Rollback capabilities
- Configuration drift detection
- Compliance-ready audit trail

TODO: [SEC-005] Add configuration validation before backup - @SecurityAgent - 2024-09-24
TODO: [SEC-006] Implement configuration rollback testing - @SecurityAgent - 2024-09-24
"""

import os
import json
import shutil
import hashlib
import threading
import time
import secrets
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import yaml
import configparser
import pickle
import base64
import uuid
import fnmatch

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)


@dataclass
class ConfigurationItem:
    """Configuration item with metadata"""
    path: str
    content_type: str  # json, yaml, ini, env, python, etc.
    content_hash: str
    last_modified: datetime
    size_bytes: int
    backup_enabled: bool = True
    sensitive: bool = False
    validation_schema: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['last_modified'] = self.last_modified.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigurationItem':
        """Create from dictionary"""
        data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        return cls(**data)


@dataclass
class ConfigurationSnapshot:
    """Complete configuration snapshot"""
    snapshot_id: str
    timestamp: datetime
    configurations: List[ConfigurationItem]
    system_info: Dict[str, Any]
    change_summary: Dict[str, Any]
    validation_results: Dict[str, Any]
    snapshot_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['configurations'] = [config.to_dict() for config in self.configurations]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigurationSnapshot':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['configurations'] = [ConfigurationItem.from_dict(config_data) for config_data in data['configurations']]
        return cls(**data)


class ConfigurationBackupSystem(LoggerMixin):
    """
    Automated Configuration Backup System
    
    Features:
    - 15-minute automated backup intervals
    - Configuration change detection
    - Encrypted backup storage
    - Version management and rollback
    - Configuration validation
    - Drift detection and alerting
    """
    
    def __init__(self, vault_manager=None):
        super().__init__()
        
        # Import vault manager for encryption
        if vault_manager:
            self.vault = vault_manager
        else:
            from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
            self.vault = get_enterprise_vault_manager()
        
        # Configuration paths
        self.backup_dir = Path(settings.UPLOAD_PATH) / "config_backup"
        self.snapshots_dir = self.backup_dir / "snapshots"
        self.archives_dir = self.backup_dir / "archives"
        self.metadata_dir = self.backup_dir / "metadata"
        
        # Create directories
        for directory in [self.backup_dir, self.snapshots_dir, self.archives_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Backup configuration
        self.backup_interval = 15 * 60  # 15 minutes in seconds
        self.max_snapshots = int(os.getenv('MAX_CONFIG_SNAPSHOTS', '100'))
        self.retention_days = int(os.getenv('CONFIG_RETENTION_DAYS', '30'))
        
        # Configuration paths to monitor
        self.config_paths = self._initialize_config_paths()
        self.exclude_patterns = self._initialize_exclude_patterns()
        
        # State management
        self._backup_lock = threading.Lock()
        self._backup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._last_snapshot: Optional[ConfigurationSnapshot] = None
        
        # Change detection
        self._file_checksums: Dict[str, str] = {}
        self._last_scan_time = datetime.now(timezone.utc)
        
        # Initialize system
        self._load_last_snapshot()
        self._start_backup_scheduler()
        
        self.logger.info("Configuration Backup System initialized", extra={
            "backup_dir": str(self.backup_dir),
            "backup_interval_minutes": self.backup_interval // 60,
            "config_paths": len(self.config_paths),
            "max_snapshots": self.max_snapshots
        })
    
    def _initialize_config_paths(self) -> List[str]:
        """Initialize configuration paths to monitor"""
        
        base_paths = [
            # Core configuration files
            str(Path.cwd() / "package.json"),
            str(Path.cwd() / "pyproject.toml"),
            str(Path.cwd() / "requirements.txt"),
            str(Path.cwd() / "_config.yml"),
            str(Path.cwd() / "mkdocs.yml"),
            str(Path.cwd() / "docker-compose.yml"),
            str(Path.cwd() / "Dockerfile"),
            str(Path.cwd() / "tailwind.config.js"),
            
            # DafelHub specific configs
            str(Path.cwd() / "src" / "dafelhub" / "core" / "config.py"),
            str(Path.cwd() / "src" / "package.json"),
            str(Path.cwd() / "src" / "tsconfig.json"),
            
            # Security configurations
            str(Path.cwd() / "src" / "dafelhub" / "security"),
            
            # Database configurations
            str(Path.cwd() / "src" / "dafelhub" / "database"),
            
            # Monitoring configurations
            str(Path.cwd() / "src" / "dafelhub" / "monitoring"),
            
            # API configurations
            str(Path.cwd() / "src" / "dafelhub" / "api"),
            
            # Documentation configs
            str(Path.cwd() / "docs" / "config"),
            
            # CI/CD configurations
            str(Path.cwd() / ".github"),
            
            # Environment files (will be handled specially)
            str(Path.cwd() / ".env*"),
            str(Path.cwd() / "*.env")
        ]
        
        # Add custom paths from environment
        custom_paths = os.getenv('CONFIG_BACKUP_PATHS', '').split(',')
        base_paths.extend([path.strip() for path in custom_paths if path.strip()])
        
        # Filter existing paths
        existing_paths = []
        for path in base_paths:
            path_obj = Path(path)
            if '*' in path or '?' in path:
                # Handle glob patterns
                try:
                    matches = list(Path.cwd().glob(path))
                    existing_paths.extend([str(match) for match in matches if match.exists()])
                except:
                    pass
            elif path_obj.exists():
                existing_paths.append(str(path_obj))
        
        return existing_paths
    
    def _initialize_exclude_patterns(self) -> List[str]:
        """Initialize patterns to exclude from backup"""
        
        default_patterns = [
            "*.log",
            "*.tmp",
            "*.temp",
            "*.cache",
            "*.pyc",
            "__pycache__/*",
            ".git/*",
            ".gitignore",
            "node_modules/*",
            "*.secret",
            "*.key",
            "*.pem",
            "*.p12",
            "*.pfx",
            "*.jks",
            "*.keystore",
            "*password*",
            "*secret*",
            ".env.local",
            ".env.production",
            "uploads/*",
            "logs/*",
            "memory/*",
            "vault_recovery/*",
            "audit_backup/*",
            "config_backup/*"
        ]
        
        # Add custom exclude patterns
        custom_patterns = os.getenv('CONFIG_BACKUP_EXCLUDE', '').split(',')
        default_patterns.extend([pattern.strip() for pattern in custom_patterns if pattern.strip()])
        
        return default_patterns
    
    def _should_exclude_file(self, file_path: str) -> bool:
        """Check if file should be excluded from backup"""
        
        file_path_normalized = str(Path(file_path).resolve())
        
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path_normalized, pattern) or fnmatch.fnmatch(Path(file_path).name, pattern):
                return True
        
        return False
    
    def _detect_content_type(self, file_path: Path) -> str:
        """Detect configuration file content type"""
        
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        
        if suffix == '.json' or name.endswith('.json'):
            return 'json'
        elif suffix in ['.yaml', '.yml'] or name.endswith(('.yaml', '.yml')):
            return 'yaml'
        elif suffix in ['.ini', '.cfg', '.conf'] or name.endswith(('.ini', '.cfg', '.conf')):
            return 'ini'
        elif name.startswith('.env') or suffix == '.env':
            return 'env'
        elif suffix == '.py':
            return 'python'
        elif suffix == '.js':
            return 'javascript'
        elif suffix == '.ts':
            return 'typescript'
        elif suffix == '.toml':
            return 'toml'
        elif suffix in ['.xml', '.html', '.htm']:
            return 'xml'
        elif name in ['dockerfile', 'Dockerfile']:
            return 'dockerfile'
        elif name.endswith(('docker-compose.yml', 'docker-compose.yaml')):
            return 'docker-compose'
        else:
            return 'text'
    
    def _is_sensitive_config(self, file_path: Path, content: str) -> bool:
        """Determine if configuration contains sensitive information"""
        
        sensitive_indicators = [
            'password', 'secret', 'key', 'token', 'credential',
            'private', 'auth', 'cert', 'ssl', 'tls', 'api_key',
            'database_url', 'connection_string', 'aws_', 'azure_',
            'gcp_', 'stripe_', 'paypal_', 'oauth'
        ]
        
        # Check file path
        file_path_lower = str(file_path).lower()
        for indicator in sensitive_indicators:
            if indicator in file_path_lower:
                return True
        
        # Check content (first 1000 characters to avoid full scan)
        content_sample = content[:1000].lower()
        for indicator in sensitive_indicators:
            if indicator in content_sample:
                return True
        
        return False
    
    def _scan_configurations(self) -> List[ConfigurationItem]:
        """Scan all configuration files"""
        
        configurations = []
        
        for config_path in self.config_paths:
            path_obj = Path(config_path)
            
            if path_obj.is_file():
                configurations.extend(self._scan_single_file(path_obj))
            elif path_obj.is_dir():
                configurations.extend(self._scan_directory(path_obj))
        
        return configurations
    
    def _scan_single_file(self, file_path: Path) -> List[ConfigurationItem]:
        """Scan a single configuration file"""
        
        if self._should_exclude_file(str(file_path)):
            return []
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Get file stats
            stat = file_path.stat()
            
            # Calculate content hash
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # Detect content type
            content_type = self._detect_content_type(file_path)
            
            # Check if sensitive
            is_sensitive = self._is_sensitive_config(file_path, content)
            
            configuration = ConfigurationItem(
                path=str(file_path.resolve()),
                content_type=content_type,
                content_hash=content_hash,
                last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                size_bytes=stat.st_size,
                backup_enabled=True,
                sensitive=is_sensitive
            )
            
            return [configuration]
            
        except Exception as e:
            self.logger.warning(f"Failed to scan configuration file {file_path}: {e}")
            return []
    
    def _scan_directory(self, dir_path: Path, max_depth: int = 3, current_depth: int = 0) -> List[ConfigurationItem]:
        """Recursively scan directory for configuration files"""
        
        if current_depth >= max_depth:
            return []
        
        configurations = []
        
        try:
            for item in dir_path.iterdir():
                if item.is_file():
                    # Check if it's a configuration file
                    if self._is_config_file(item):
                        configurations.extend(self._scan_single_file(item))
                
                elif item.is_dir() and not self._should_exclude_file(str(item)):
                    # Recursively scan subdirectories
                    configurations.extend(self._scan_directory(item, max_depth, current_depth + 1))
        
        except PermissionError:
            self.logger.warning(f"Permission denied scanning directory: {dir_path}")
        except Exception as e:
            self.logger.warning(f"Failed to scan directory {dir_path}: {e}")
        
        return configurations
    
    def _is_config_file(self, file_path: Path) -> bool:
        """Check if file is likely a configuration file"""
        
        config_extensions = {
            '.json', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.env',
            '.toml', '.xml', '.properties', '.config'
        }
        
        config_names = {
            'dockerfile', 'makefile', 'requirements.txt', 'package.json',
            'pyproject.toml', 'setup.py', 'setup.cfg', 'tox.ini',
            'pytest.ini', '.gitignore', '.dockerignore'
        }
        
        return (
            file_path.suffix.lower() in config_extensions or
            file_path.name.lower() in config_names or
            file_path.name.startswith('.env') or
            'config' in file_path.name.lower()
        )
    
    def _detect_changes(self, current_configs: List[ConfigurationItem]) -> Dict[str, Any]:
        """Detect changes from last snapshot"""
        
        changes = {
            'new_files': [],
            'modified_files': [],
            'deleted_files': [],
            'moved_files': [],
            'total_changes': 0
        }
        
        if self._last_snapshot is None:
            # First backup - all files are new
            changes['new_files'] = [config.path for config in current_configs]
            changes['total_changes'] = len(current_configs)
            return changes
        
        # Create maps for comparison
        current_map = {config.path: config for config in current_configs}
        last_map = {config.path: config for config in self._last_snapshot.configurations}
        
        # Find new and modified files
        for path, config in current_map.items():
            if path not in last_map:
                changes['new_files'].append(path)
            elif config.content_hash != last_map[path].content_hash:
                changes['modified_files'].append({
                    'path': path,
                    'old_hash': last_map[path].content_hash,
                    'new_hash': config.content_hash,
                    'old_modified': last_map[path].last_modified.isoformat(),
                    'new_modified': config.last_modified.isoformat()
                })
        
        # Find deleted files
        for path in last_map:
            if path not in current_map:
                changes['deleted_files'].append(path)
        
        # Calculate total changes
        changes['total_changes'] = (
            len(changes['new_files']) +
            len(changes['modified_files']) +
            len(changes['deleted_files'])
        )
        
        return changes
    
    def _validate_configurations(self, configurations: List[ConfigurationItem]) -> Dict[str, Any]:
        """Validate configuration files"""
        
        validation_results = {
            'total_files': len(configurations),
            'valid_files': 0,
            'invalid_files': 0,
            'warnings': 0,
            'errors': [],
            'file_results': {}
        }
        
        for config in configurations:
            file_result = self._validate_single_config(config)
            validation_results['file_results'][config.path] = file_result
            
            if file_result['valid']:
                validation_results['valid_files'] += 1
            else:
                validation_results['invalid_files'] += 1
            
            if file_result.get('warnings'):
                validation_results['warnings'] += len(file_result['warnings'])
            
            if file_result.get('errors'):
                validation_results['errors'].extend(file_result['errors'])
        
        return validation_results
    
    def _validate_single_config(self, config: ConfigurationItem) -> Dict[str, Any]:
        """Validate a single configuration file"""
        
        result = {
            'path': config.path,
            'content_type': config.content_type,
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            with open(config.path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Validate based on content type
            if config.content_type == 'json':
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    result['valid'] = False
                    result['errors'].append(f"Invalid JSON: {e}")
            
            elif config.content_type in ['yaml', 'yml']:
                try:
                    yaml.safe_load(content)
                except yaml.YAMLError as e:
                    result['valid'] = False
                    result['errors'].append(f"Invalid YAML: {e}")
            
            elif config.content_type == 'ini':
                try:
                    parser = configparser.ConfigParser()
                    parser.read_string(content)
                except configparser.Error as e:
                    result['valid'] = False
                    result['errors'].append(f"Invalid INI: {e}")
            
            elif config.content_type == 'toml':
                try:
                    import tomli
                    tomli.loads(content)
                except Exception as e:
                    result['warnings'].append(f"Could not validate TOML: {e}")
            
            # Check for sensitive data in non-sensitive files
            if not config.sensitive and self._contains_credentials(content):
                result['warnings'].append("File may contain sensitive information")
            
            # Check file size
            if config.size_bytes > 10 * 1024 * 1024:  # 10MB
                result['warnings'].append(f"Large configuration file: {config.size_bytes // 1024 // 1024}MB")
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Validation error: {e}")
        
        return result
    
    def _contains_credentials(self, content: str) -> bool:
        """Check if content contains credential-like patterns"""
        
        import re
        
        credential_patterns = [
            r'password\s*[:=]\s*["\']?[^"\'\s]+',
            r'secret\s*[:=]\s*["\']?[^"\'\s]+',
            r'key\s*[:=]\s*["\']?[A-Za-z0-9+/=]{20,}',
            r'token\s*[:=]\s*["\']?[A-Za-z0-9+/=]{20,}',
            r'api[_-]?key\s*[:=]\s*["\']?[^"\'\s]+',
            r'[A-Za-z0-9+/]{40,}={0,2}',  # Base64-like strings
            r'-----BEGIN [A-Z ]+-----',  # PEM format
        ]
        
        content_lower = content.lower()
        for pattern in credential_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True
        
        return False
    
    def create_snapshot(self, force: bool = False) -> ConfigurationSnapshot:
        """Create configuration snapshot"""
        
        with self._backup_lock:
            self.logger.info("Starting configuration snapshot creation")
            
            # Scan configurations
            configurations = self._scan_configurations()
            
            # Detect changes
            changes = self._detect_changes(configurations)
            
            # Skip if no changes and not forced
            if not force and changes['total_changes'] == 0:
                self.logger.info("No configuration changes detected, skipping snapshot")
                return self._last_snapshot
            
            # Validate configurations
            validation_results = self._validate_configurations(configurations)
            
            # Get system info
            system_info = self._get_system_info()
            
            # Create snapshot
            snapshot_id = f"config_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Calculate snapshot hash
            snapshot_data = {
                'configurations': [config.to_dict() for config in configurations],
                'system_info': system_info,
                'change_summary': changes
            }
            
            snapshot_hash = hashlib.sha256(
                json.dumps(snapshot_data, sort_keys=True).encode('utf-8')
            ).hexdigest()
            
            snapshot = ConfigurationSnapshot(
                snapshot_id=snapshot_id,
                timestamp=datetime.now(timezone.utc),
                configurations=configurations,
                system_info=system_info,
                change_summary=changes,
                validation_results=validation_results,
                snapshot_hash=snapshot_hash
            )
            
            # Save snapshot
            self._save_snapshot(snapshot)
            
            # Update last snapshot
            self._last_snapshot = snapshot
            
            # Log results
            self.logger.info("Configuration snapshot created", extra={
                'snapshot_id': snapshot_id,
                'total_files': len(configurations),
                'changes': changes['total_changes'],
                'validation_errors': validation_results['invalid_files']
            })
            
            return snapshot
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for snapshot"""
        
        system_info = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
            'platform': os.name,
            'python_version': os.sys.version,
            'working_directory': str(Path.cwd()),
            'environment_variables': {
                k: '***REDACTED***' if any(secret in k.lower() for secret in ['password', 'secret', 'key', 'token'])
                else v for k, v in os.environ.items()
                if not k.startswith('_') and len(k) < 100
            },
            'git_info': self._get_git_info()
        }
        
        return system_info
    
    def _get_git_info(self) -> Dict[str, Any]:
        """Get Git repository information"""
        
        git_info = {}
        
        try:
            # Get current branch
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                git_info['branch'] = result.stdout.strip()
            
            # Get latest commit
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                git_info['commit'] = result.stdout.strip()
            
            # Get commit message
            result = subprocess.run(['git', 'log', '-1', '--pretty=format:%s'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                git_info['last_commit_message'] = result.stdout.strip()
            
            # Get repository status
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                git_info['has_uncommitted_changes'] = bool(result.stdout.strip())
                git_info['uncommitted_files'] = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            git_info['error'] = f"Failed to get Git info: {e}"
        
        return git_info
    
    def _save_snapshot(self, snapshot: ConfigurationSnapshot) -> None:
        """Save snapshot to disk with encryption"""
        
        snapshot_file = self.snapshots_dir / f"{snapshot.snapshot_id}.snapshot"
        
        try:
            # Prepare snapshot data
            snapshot_data = snapshot.to_dict()
            
            # Create file content map for backup
            file_contents = {}
            for config in snapshot.configurations:
                if not config.sensitive and Path(config.path).exists():
                    try:
                        with open(config.path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        # Encrypt sensitive content
                        if config.sensitive:
                            content = self.vault.encrypt_data(content)
                        file_contents[config.path] = {
                            'content': content,
                            'encrypted': config.sensitive
                        }
                    except Exception as e:
                        self.logger.warning(f"Failed to read file for backup: {config.path}: {e}")
            
            # Add file contents to snapshot
            snapshot_data['file_contents'] = file_contents
            
            # Encrypt entire snapshot
            encrypted_snapshot = self.vault.encrypt_data(snapshot_data)
            
            # Save to file
            with open(snapshot_file, 'w') as f:
                json.dump({
                    'snapshot_id': snapshot.snapshot_id,
                    'timestamp': snapshot.timestamp.isoformat(),
                    'encrypted_data': encrypted_snapshot,
                    'metadata': {
                        'total_files': len(snapshot.configurations),
                        'snapshot_hash': snapshot.snapshot_hash,
                        'has_changes': snapshot.change_summary['total_changes'] > 0
                    }
                }, f, indent=2)
            
            # Create metadata file
            metadata_file = self.metadata_dir / f"{snapshot.snapshot_id}.json"
            with open(metadata_file, 'w') as f:
                json.dump({
                    'snapshot_id': snapshot.snapshot_id,
                    'timestamp': snapshot.timestamp.isoformat(),
                    'configurations_count': len(snapshot.configurations),
                    'changes_summary': snapshot.change_summary,
                    'validation_results': snapshot.validation_results,
                    'system_info': snapshot.system_info,
                    'snapshot_hash': snapshot.snapshot_hash
                }, f, indent=2)
            
            # Cleanup old snapshots
            self._cleanup_old_snapshots()
            
        except Exception as e:
            self.logger.error(f"Failed to save snapshot: {e}")
            raise
    
    def _load_last_snapshot(self) -> None:
        """Load the most recent snapshot"""
        
        try:
            # Find most recent snapshot
            snapshot_files = list(self.snapshots_dir.glob("*.snapshot"))
            if not snapshot_files:
                return
            
            # Sort by modification time
            latest_file = max(snapshot_files, key=lambda f: f.stat().st_mtime)
            
            # Load snapshot metadata
            with open(latest_file, 'r') as f:
                snapshot_file_data = json.load(f)
            
            # Decrypt snapshot data
            encrypted_data = snapshot_file_data['encrypted_data']
            snapshot_data = self.vault.decrypt_data(encrypted_data)
            
            # Remove file contents to save memory
            if 'file_contents' in snapshot_data:
                del snapshot_data['file_contents']
            
            self._last_snapshot = ConfigurationSnapshot.from_dict(snapshot_data)
            
            self.logger.info("Loaded last configuration snapshot", extra={
                'snapshot_id': self._last_snapshot.snapshot_id,
                'timestamp': self._last_snapshot.timestamp.isoformat(),
                'total_files': len(self._last_snapshot.configurations)
            })
            
        except Exception as e:
            self.logger.warning(f"Failed to load last snapshot: {e}")
            self._last_snapshot = None
    
    def _cleanup_old_snapshots(self) -> None:
        """Clean up old snapshots based on retention policy"""
        
        # Get all snapshots
        snapshot_files = list(self.snapshots_dir.glob("*.snapshot"))
        metadata_files = list(self.metadata_dir.glob("*.json"))
        
        # Sort by creation time
        snapshot_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Keep only max_snapshots
        if len(snapshot_files) > self.max_snapshots:
            files_to_delete = snapshot_files[self.max_snapshots:]
            
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    
                    # Delete corresponding metadata file
                    snapshot_id = file_path.stem
                    metadata_file = self.metadata_dir / f"{snapshot_id}.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    self.logger.debug(f"Deleted old snapshot: {file_path.name}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to delete old snapshot {file_path}: {e}")
        
        # Clean up by retention days
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        
        for file_path in snapshot_files:
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
            if file_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    
                    # Delete corresponding metadata file
                    snapshot_id = file_path.stem
                    metadata_file = self.metadata_dir / f"{snapshot_id}.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    self.logger.debug(f"Deleted expired snapshot: {file_path.name}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to delete expired snapshot {file_path}: {e}")
    
    def _start_backup_scheduler(self) -> None:
        """Start automatic backup scheduler"""
        
        def backup_loop():
            """Background backup loop"""
            self.logger.info("Configuration backup scheduler started")
            
            while not self._shutdown_event.is_set():
                try:
                    # Wait for interval or shutdown
                    if self._shutdown_event.wait(self.backup_interval):
                        break  # Shutdown requested
                    
                    # Create snapshot
                    self.create_snapshot()
                    
                except Exception as e:
                    self.logger.error(f"Scheduled configuration backup failed: {e}")
        
        # Start backup thread
        self._backup_thread = threading.Thread(
            target=backup_loop,
            name="ConfigBackupScheduler",
            daemon=True
        )
        self._backup_thread.start()
        
        self.logger.info(f"Configuration backup scheduler started with {self.backup_interval // 60} minute intervals")
    
    def restore_snapshot(self, snapshot_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Restore configuration from snapshot"""
        
        restore_result = {
            'snapshot_id': snapshot_id,
            'restore_timestamp': datetime.now(timezone.utc).isoformat(),
            'dry_run': dry_run,
            'files_restored': 0,
            'files_failed': 0,
            'errors': [],
            'warnings': [],
            'success': False
        }
        
        try:
            # Find snapshot file
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.snapshot"
            if not snapshot_file.exists():
                raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")
            
            # Load snapshot
            with open(snapshot_file, 'r') as f:
                snapshot_file_data = json.load(f)
            
            # Decrypt snapshot data
            encrypted_data = snapshot_file_data['encrypted_data']
            snapshot_data = self.vault.decrypt_data(encrypted_data)
            
            snapshot = ConfigurationSnapshot.from_dict(snapshot_data)
            file_contents = snapshot_data.get('file_contents', {})
            
            self.logger.info(f"Starting configuration restore from snapshot: {snapshot_id}", extra={
                'dry_run': dry_run,
                'total_files': len(snapshot.configurations)
            })
            
            # Restore files
            for config in snapshot.configurations:
                try:
                    if config.path in file_contents:
                        file_data = file_contents[config.path]
                        content = file_data['content']
                        
                        # Decrypt if encrypted
                        if file_data.get('encrypted'):
                            content = self.vault.decrypt_data(content)
                        
                        if not dry_run:
                            # Create directory if needed
                            Path(config.path).parent.mkdir(parents=True, exist_ok=True)
                            
                            # Write file
                            with open(config.path, 'w', encoding='utf-8') as f:
                                f.write(content)
                        
                        restore_result['files_restored'] += 1
                        
                    else:
                        restore_result['warnings'].append(f"No content available for: {config.path}")
                
                except Exception as e:
                    restore_result['files_failed'] += 1
                    restore_result['errors'].append(f"Failed to restore {config.path}: {e}")
                    self.logger.error(f"Failed to restore file {config.path}: {e}")
            
            restore_result['success'] = restore_result['files_failed'] == 0
            
            if restore_result['success']:
                self.logger.info(f"Configuration restore completed successfully", extra=restore_result)
            else:
                self.logger.warning(f"Configuration restore completed with errors", extra=restore_result)
            
        except Exception as e:
            restore_result['errors'].append(f"Restore process failed: {e}")
            self.logger.error(f"Configuration restore failed: {e}")
        
        return restore_result
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots"""
        
        snapshots = []
        
        for metadata_file in self.metadata_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                snapshots.append({
                    'snapshot_id': metadata['snapshot_id'],
                    'timestamp': metadata['timestamp'],
                    'configurations_count': metadata['configurations_count'],
                    'total_changes': metadata['changes_summary']['total_changes'],
                    'validation_errors': metadata['validation_results']['invalid_files'],
                    'has_git_info': 'git_info' in metadata['system_info'],
                    'git_branch': metadata['system_info'].get('git_info', {}).get('branch'),
                    'git_commit': metadata['system_info'].get('git_info', {}).get('commit', '')[:8],
                    'snapshot_hash': metadata['snapshot_hash']
                })
                
            except Exception as e:
                self.logger.warning(f"Failed to read snapshot metadata {metadata_file}: {e}")
        
        # Sort by timestamp, newest first
        snapshots.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return snapshots
    
    def get_status(self) -> Dict[str, Any]:
        """Get configuration backup system status"""
        
        snapshots = self.list_snapshots()
        
        status = {
            'backup_system_active': self._backup_thread is not None and self._backup_thread.is_alive(),
            'backup_interval_minutes': self.backup_interval // 60,
            'last_snapshot_id': self._last_snapshot.snapshot_id if self._last_snapshot else None,
            'last_snapshot_timestamp': self._last_snapshot.timestamp.isoformat() if self._last_snapshot else None,
            'total_snapshots': len(snapshots),
            'config_paths_monitored': len(self.config_paths),
            'max_snapshots': self.max_snapshots,
            'retention_days': self.retention_days,
            'backup_dir': str(self.backup_dir),
            'recent_snapshots': snapshots[:5]  # Last 5 snapshots
        }
        
        if self._last_snapshot:
            status.update({
                'last_snapshot_files': len(self._last_snapshot.configurations),
                'last_snapshot_changes': self._last_snapshot.change_summary['total_changes'],
                'last_snapshot_validation_errors': self._last_snapshot.validation_results['invalid_files']
            })
        
        return status
    
    def shutdown(self) -> None:
        """Shutdown configuration backup system"""
        
        self.logger.info("Shutting down Configuration Backup System")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for backup thread to finish
        if self._backup_thread and self._backup_thread.is_alive():
            self._backup_thread.join(timeout=30)
        
        # Create final snapshot
        try:
            self.create_snapshot(force=True)
            self.logger.info("Final configuration snapshot created")
        except Exception as e:
            self.logger.error(f"Failed to create final snapshot: {e}")
        
        self.logger.info("Configuration Backup System shutdown complete")


# Global instance management
_config_backup_system: Optional[ConfigurationBackupSystem] = None
_backup_system_lock = threading.Lock()


def get_config_backup_system(vault_manager=None) -> ConfigurationBackupSystem:
    """Get global configuration backup system instance"""
    global _config_backup_system
    
    with _backup_system_lock:
        if _config_backup_system is None:
            _config_backup_system = ConfigurationBackupSystem(vault_manager)
        return _config_backup_system


# Convenience functions
def create_config_backup() -> ConfigurationSnapshot:
    """Create configuration backup snapshot"""
    backup_system = get_config_backup_system()
    return backup_system.create_snapshot(force=True)


def restore_config_backup(snapshot_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """Restore configuration from backup"""
    backup_system = get_config_backup_system()
    return backup_system.restore_snapshot(snapshot_id, dry_run)


def list_config_backups() -> List[Dict[str, Any]]:
    """List available configuration backups"""
    backup_system = get_config_backup_system()
    return backup_system.list_snapshots()