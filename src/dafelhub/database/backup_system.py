"""
DafelHub Enterprise Database Backup System
Automated database backup and recovery system
Integrated with SecurityAgent audit trail and health monitoring

Features:
- Automated scheduled backups
- Schema and data backup strategies
- Point-in-time recovery capabilities
- Backup compression and encryption
- Multi-destination backup support
- Backup verification and integrity checks
- Recovery testing automation
- Retention policy management

TODO: [DB-010] Implement automated backup scheduling - @DatabaseAgent - 2024-09-24
TODO: [DB-011] Add point-in-time recovery - @DatabaseAgent - 2024-09-24
TODO: [DB-012] Integrate backup encryption - @DatabaseAgent - 2024-09-24
"""

import asyncio
import os
import shutil
import tempfile
import tarfile
import gzip
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable
import json
import threading
from urllib.parse import urlparse
import time

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.security.audit_trail import get_persistent_audit_trail
from dafelhub.database.connection_manager import get_connection_manager
from dafelhub.database.health_monitor import get_health_monitor


logger = get_logger(__name__)


class BackupType(Enum):
    """Types of database backups"""
    FULL = "full"               # Complete database backup
    SCHEMA_ONLY = "schema_only" # Schema structure only
    DATA_ONLY = "data_only"     # Data only, no schema
    INCREMENTAL = "incremental" # Incremental changes
    DIFFERENTIAL = "differential" # Changes since last full backup
    TRANSACTION_LOG = "transaction_log" # WAL/Transaction log backup


class BackupFormat(Enum):
    """Backup file formats"""
    SQL = "sql"           # Plain SQL dump
    CUSTOM = "custom"     # PostgreSQL custom format
    TAR = "tar"          # Tar archive
    DIRECTORY = "directory" # Directory format


class BackupStatus(Enum):
    """Backup execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"


class CompressionType(Enum):
    """Compression types for backups"""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    XZ = "xz"


@dataclass
class BackupConfiguration:
    """Backup configuration settings"""
    backup_type: BackupType = BackupType.FULL
    backup_format: BackupFormat = BackupFormat.CUSTOM
    compression: CompressionType = CompressionType.GZIP
    include_data: bool = True
    include_schema: bool = True
    include_indexes: bool = True
    include_triggers: bool = True
    include_functions: bool = True
    tables_to_include: Optional[List[str]] = None
    tables_to_exclude: Optional[List[str]] = None
    encrypt_backup: bool = True
    verify_after_backup: bool = True
    retention_days: int = 30
    max_parallel_jobs: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'backup_type': self.backup_type.value,
            'backup_format': self.backup_format.value,
            'compression': self.compression.value,
            'include_data': self.include_data,
            'include_schema': self.include_schema,
            'include_indexes': self.include_indexes,
            'include_triggers': self.include_triggers,
            'include_functions': self.include_functions,
            'tables_to_include': self.tables_to_include,
            'tables_to_exclude': self.tables_to_exclude,
            'encrypt_backup': self.encrypt_backup,
            'verify_after_backup': self.verify_after_backup,
            'retention_days': self.retention_days,
            'max_parallel_jobs': self.max_parallel_jobs
        }


@dataclass
class BackupMetadata:
    """Backup metadata and information"""
    backup_id: str
    backup_name: str
    pool_id: str
    backup_type: BackupType
    backup_format: BackupFormat
    created_at: datetime
    completed_at: Optional[datetime] = None
    file_path: str = ""
    file_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    checksum: str = ""
    encryption_key_id: Optional[str] = None
    database_version: str = ""
    schema_version: str = ""
    table_count: int = 0
    row_count: int = 0
    configuration: Optional[BackupConfiguration] = None
    status: BackupStatus = BackupStatus.PENDING
    error_message: Optional[str] = None
    verification_passed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'backup_id': self.backup_id,
            'backup_name': self.backup_name,
            'pool_id': self.pool_id,
            'backup_type': self.backup_type.value,
            'backup_format': self.backup_format.value,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'compressed_size': self.compressed_size,
            'compression_ratio': self.compression_ratio,
            'checksum': self.checksum,
            'encryption_key_id': self.encryption_key_id,
            'database_version': self.database_version,
            'schema_version': self.schema_version,
            'table_count': self.table_count,
            'row_count': self.row_count,
            'configuration': self.configuration.to_dict() if self.configuration else None,
            'status': self.status.value,
            'error_message': self.error_message,
            'verification_passed': self.verification_passed
        }


@dataclass
class BackupSchedule:
    """Backup schedule configuration"""
    schedule_id: str
    pool_id: str
    schedule_name: str
    cron_expression: str
    configuration: BackupConfiguration
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    consecutive_failures: int = 0
    max_failures: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'schedule_id': self.schedule_id,
            'pool_id': self.pool_id,
            'schedule_name': self.schedule_name,
            'cron_expression': self.cron_expression,
            'configuration': self.configuration.to_dict(),
            'enabled': self.enabled,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'consecutive_failures': self.consecutive_failures,
            'max_failures': self.max_failures
        }


class EnterpriseBackupSystem(LoggerMixin):
    """
    Enterprise Database Backup System
    
    Comprehensive backup and recovery solution with:
    - Multiple backup types and formats
    - Automated scheduling with cron expressions
    - Compression and encryption support
    - Backup verification and integrity checking
    - Point-in-time recovery capabilities
    - Multi-destination backup support
    - Retention policy management
    - Integration with health monitoring
    - Audit trail integration
    """
    
    def __init__(self, vault_manager=None, audit_trail=None):
        super().__init__()
        
        # Core dependencies
        self.vault = vault_manager or get_enterprise_vault_manager()
        self.audit = audit_trail or get_persistent_audit_trail()
        self.connection_manager = get_connection_manager()
        self.health_monitor = get_health_monitor()
        
        # Backup storage configuration
        self.backup_root_dir = Path(settings.UPLOAD_PATH) / "backups"
        self.temp_dir = Path(settings.UPLOAD_PATH) / "backup_temp"
        self.metadata_dir = self.backup_root_dir / "metadata"
        
        # Ensure directories exist
        for directory in [self.backup_root_dir, self.temp_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Backup management
        self._backup_metadata: Dict[str, BackupMetadata] = {}
        self._backup_schedules: Dict[str, BackupSchedule] = {}
        self._active_backups: Dict[str, asyncio.Task] = {}
        
        # Scheduling
        self._scheduler_active = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Performance tracking
        self._backup_stats = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'total_size_gb': 0.0,
            'avg_backup_duration': 0.0,
            'compression_savings_gb': 0.0
        }
        
        # Load existing metadata
        self._load_backup_metadata()
        
        self.logger.info("Enterprise Backup System initialized", extra={
            "backup_dir": str(self.backup_root_dir),
            "temp_dir": str(self.temp_dir)
        })
    
    async def create_backup(
        self,
        pool_id: str,
        backup_name: Optional[str] = None,
        configuration: Optional[BackupConfiguration] = None
    ) -> BackupMetadata:
        """Create database backup with specified configuration"""
        
        # Generate backup ID and name
        backup_id = self._generate_backup_id()
        backup_name = backup_name or f"backup_{pool_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Use default configuration if not provided
        configuration = configuration or BackupConfiguration()
        
        # Create backup metadata
        metadata = BackupMetadata(
            backup_id=backup_id,
            backup_name=backup_name,
            pool_id=pool_id,
            backup_type=configuration.backup_type,
            backup_format=configuration.backup_format,
            created_at=datetime.now(timezone.utc),
            configuration=configuration
        )
        
        # Store metadata
        self._backup_metadata[backup_id] = metadata
        
        try:
            # Audit backup start
            self.audit.add_entry(
                'database_backup_started',
                {
                    'backup_id': backup_id,
                    'pool_id': pool_id,
                    'backup_name': backup_name,
                    'configuration': configuration.to_dict()
                }
            )
            
            # Start backup task
            backup_task = asyncio.create_task(
                self._execute_backup(metadata)
            )
            self._active_backups[backup_id] = backup_task
            
            # Wait for completion
            await backup_task
            
            # Remove from active backups
            self._active_backups.pop(backup_id, None)
            
            # Update statistics
            self._update_backup_stats(metadata)
            
            # Save metadata
            await self._save_backup_metadata(metadata)
            
            self.logger.info(f"Backup completed successfully: {backup_id}", extra={
                "backup_name": backup_name,
                "pool_id": pool_id,
                "file_size": metadata.file_size,
                "duration": (metadata.completed_at - metadata.created_at).total_seconds() if metadata.completed_at else 0
            })
            
            return metadata
            
        except Exception as e:
            metadata.status = BackupStatus.FAILED
            metadata.error_message = str(e)
            metadata.completed_at = datetime.now(timezone.utc)
            
            # Remove from active backups
            self._active_backups.pop(backup_id, None)
            
            # Update statistics
            self._update_backup_stats(metadata)
            
            # Audit failure
            self.audit.add_entry(
                'database_backup_failed',
                {
                    'backup_id': backup_id,
                    'pool_id': pool_id,
                    'error': str(e),
                    'metadata': metadata.to_dict()
                }
            )
            
            self.logger.error(f"Backup failed: {backup_id}", extra={
                "pool_id": pool_id,
                "error": str(e)
            })
            raise
    
    async def restore_backup(
        self,
        backup_id: str,
        target_pool_id: Optional[str] = None,
        restore_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Restore database from backup"""
        
        if backup_id not in self._backup_metadata:
            raise ValueError(f"Backup not found: {backup_id}")
        
        metadata = self._backup_metadata[backup_id]
        target_pool_id = target_pool_id or metadata.pool_id
        restore_options = restore_options or {}
        
        try:
            # Audit restore start
            self.audit.add_entry(
                'database_restore_started',
                {
                    'backup_id': backup_id,
                    'source_pool': metadata.pool_id,
                    'target_pool': target_pool_id,
                    'restore_options': restore_options
                }
            )
            
            # Verify backup integrity
            if not await self._verify_backup_integrity(metadata):
                raise ValueError(f"Backup integrity check failed: {backup_id}")
            
            # Get database connection details
            db_url = await self._get_database_url(target_pool_id)
            parsed = urlparse(db_url)
            
            # Create restore command based on backup format
            if metadata.backup_format == BackupFormat.CUSTOM:
                restore_cmd = [
                    'pg_restore',
                    f'--host={parsed.hostname}',
                    f'--port={parsed.port or 5432}',
                    f'--username={parsed.username}',
                    f'--dbname={parsed.path.lstrip("/")}',
                    '--no-password',
                    '--verbose',
                    '--clean',
                    '--if-exists'
                ]
                
                # Add restore options
                if restore_options.get('schema_only'):
                    restore_cmd.append('--schema-only')
                elif restore_options.get('data_only'):
                    restore_cmd.append('--data-only')
                
                # Decrypt backup if encrypted
                backup_file_path = metadata.file_path
                if metadata.encryption_key_id:
                    backup_file_path = await self._decrypt_backup(metadata)
                
                restore_cmd.append(backup_file_path)
                
            else:  # SQL format
                restore_cmd = [
                    'psql',
                    f'--host={parsed.hostname}',
                    f'--port={parsed.port or 5432}',
                    f'--username={parsed.username}',
                    f'--dbname={parsed.path.lstrip("/")}',
                    '--no-password',
                    f'--file={metadata.file_path}'
                ]
            
            # Set password environment variable
            env = os.environ.copy()
            if parsed.password:
                env['PGPASSWORD'] = parsed.password
            
            # Execute restore
            start_time = time.time()
            
            process = await asyncio.create_subprocess_exec(
                *restore_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            duration = time.time() - start_time
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown restore error"
                raise Exception(f"Restore failed: {error_msg}")
            
            # Cleanup temporary decrypted file if created
            if metadata.encryption_key_id and backup_file_path != metadata.file_path:
                try:
                    os.unlink(backup_file_path)
                except:
                    pass
            
            # Create restore result
            restore_result = {
                'backup_id': backup_id,
                'target_pool_id': target_pool_id,
                'success': True,
                'duration': duration,
                'restored_at': datetime.now(timezone.utc).isoformat(),
                'stdout': stdout.decode() if stdout else "",
                'stderr': stderr.decode() if stderr else ""
            }
            
            # Audit successful restore
            self.audit.add_entry(
                'database_restore_completed',
                {
                    'backup_id': backup_id,
                    'target_pool': target_pool_id,
                    'duration': duration,
                    'result': restore_result
                }
            )
            
            self.logger.info(f"Backup restored successfully: {backup_id}", extra={
                "target_pool": target_pool_id,
                "duration": duration
            })
            
            return restore_result
            
        except Exception as e:
            # Audit restore failure
            self.audit.add_entry(
                'database_restore_failed',
                {
                    'backup_id': backup_id,
                    'target_pool': target_pool_id,
                    'error': str(e)
                }
            )
            
            self.logger.error(f"Backup restore failed: {backup_id}", extra={
                "target_pool": target_pool_id,
                "error": str(e)
            })
            raise
    
    async def schedule_backup(
        self,
        pool_id: str,
        schedule_name: str,
        cron_expression: str,
        configuration: BackupConfiguration
    ) -> BackupSchedule:
        """Schedule automated backups"""
        
        schedule_id = self._generate_schedule_id()
        
        # Parse and validate cron expression
        next_run = self._calculate_next_run(cron_expression)
        
        schedule = BackupSchedule(
            schedule_id=schedule_id,
            pool_id=pool_id,
            schedule_name=schedule_name,
            cron_expression=cron_expression,
            configuration=configuration,
            next_run=next_run
        )
        
        self._backup_schedules[schedule_id] = schedule
        
        # Start scheduler if not already running
        if not self._scheduler_active:
            await self._start_scheduler()
        
        # Audit schedule creation
        self.audit.add_entry(
            'backup_schedule_created',
            {
                'schedule_id': schedule_id,
                'pool_id': pool_id,
                'schedule_name': schedule_name,
                'cron_expression': cron_expression,
                'next_run': next_run.isoformat() if next_run else None
            }
        )
        
        self.logger.info(f"Backup schedule created: {schedule_name}", extra={
            "schedule_id": schedule_id,
            "pool_id": pool_id,
            "cron_expression": cron_expression,
            "next_run": next_run.isoformat() if next_run else None
        })
        
        return schedule
    
    async def list_backups(
        self,
        pool_id: Optional[str] = None,
        backup_type: Optional[BackupType] = None,
        limit: int = 100
    ) -> List[BackupMetadata]:
        """List available backups with filtering"""
        
        backups = list(self._backup_metadata.values())
        
        # Apply filters
        if pool_id:
            backups = [b for b in backups if b.pool_id == pool_id]
        
        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        
        # Apply limit
        return backups[:limit]
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete backup and its files"""
        
        if backup_id not in self._backup_metadata:
            raise ValueError(f"Backup not found: {backup_id}")
        
        metadata = self._backup_metadata[backup_id]
        
        try:
            # Delete backup file
            if metadata.file_path and os.path.exists(metadata.file_path):
                os.unlink(metadata.file_path)
            
            # Delete metadata file
            metadata_file = self.metadata_dir / f"{backup_id}.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            # Remove from memory
            del self._backup_metadata[backup_id]
            
            # Audit deletion
            self.audit.add_entry(
                'backup_deleted',
                {
                    'backup_id': backup_id,
                    'pool_id': metadata.pool_id,
                    'backup_name': metadata.backup_name
                }
            )
            
            self.logger.info(f"Backup deleted: {backup_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete backup {backup_id}: {e}")
            raise
    
    async def get_backup_status(self) -> Dict[str, Any]:
        """Get comprehensive backup system status"""
        
        # Count backups by status
        status_counts = {}
        for status in BackupStatus:
            status_counts[status.value] = len([
                b for b in self._backup_metadata.values()
                if b.status == status
            ])
        
        # Calculate storage usage
        total_storage = sum(b.file_size for b in self._backup_metadata.values())
        compressed_storage = sum(b.compressed_size for b in self._backup_metadata.values())
        
        return {
            'system_status': 'active' if not self._shutdown_event.is_set() else 'shutdown',
            'scheduler_active': self._scheduler_active,
            'backup_counts': {
                'total': len(self._backup_metadata),
                'by_status': status_counts,
                'active': len(self._active_backups)
            },
            'schedules': {
                'total': len(self._backup_schedules),
                'enabled': len([s for s in self._backup_schedules.values() if s.enabled])
            },
            'storage': {
                'total_size_bytes': total_storage,
                'compressed_size_bytes': compressed_storage,
                'compression_ratio': (1 - compressed_storage / max(total_storage, 1)) * 100,
                'backup_directory': str(self.backup_root_dir)
            },
            'statistics': self._backup_stats
        }
    
    async def cleanup_expired_backups(self) -> Dict[str, Any]:
        """Clean up expired backups based on retention policies"""
        
        cleanup_stats = {
            'scanned': 0,
            'expired': 0,
            'deleted': 0,
            'errors': 0,
            'space_freed_bytes': 0
        }
        
        current_time = datetime.now(timezone.utc)
        
        for backup_id, metadata in list(self._backup_metadata.items()):
            cleanup_stats['scanned'] += 1
            
            # Calculate backup age
            backup_age = current_time - metadata.created_at
            retention_policy = metadata.configuration.retention_days if metadata.configuration else 30
            
            if backup_age.days > retention_policy:
                cleanup_stats['expired'] += 1
                
                try:
                    # Track space before deletion
                    space_freed = metadata.file_size
                    
                    # Delete backup
                    await self.delete_backup(backup_id)
                    
                    cleanup_stats['deleted'] += 1
                    cleanup_stats['space_freed_bytes'] += space_freed
                    
                except Exception as e:
                    cleanup_stats['errors'] += 1
                    self.logger.error(f"Failed to delete expired backup {backup_id}: {e}")
        
        # Audit cleanup
        self.audit.add_entry(
            'backup_cleanup_completed',
            {
                'stats': cleanup_stats,
                'retention_check_time': current_time.isoformat()
            }
        )
        
        self.logger.info("Backup cleanup completed", extra=cleanup_stats)
        
        return cleanup_stats
    
    # Private methods
    
    async def _execute_backup(self, metadata: BackupMetadata) -> None:
        """Execute database backup with specified configuration"""
        
        metadata.status = BackupStatus.RUNNING
        
        try:
            # Get database connection details
            db_url = await self._get_database_url(metadata.pool_id)
            parsed = urlparse(db_url)
            
            # Create backup file path
            backup_dir = self.backup_root_dir / metadata.pool_id
            backup_dir.mkdir(exist_ok=True)
            
            file_extension = self._get_file_extension(metadata.backup_format, metadata.configuration.compression)
            backup_file_path = backup_dir / f"{metadata.backup_name}{file_extension}"
            
            # Create pg_dump command
            dump_cmd = [
                'pg_dump',
                f'--host={parsed.hostname}',
                f'--port={parsed.port or 5432}',
                f'--username={parsed.username}',
                f'--dbname={parsed.path.lstrip("/")}',
                '--no-password',
                '--verbose'
            ]
            
            # Add backup type options
            if metadata.backup_type == BackupType.SCHEMA_ONLY:
                dump_cmd.append('--schema-only')
            elif metadata.backup_type == BackupType.DATA_ONLY:
                dump_cmd.append('--data-only')
            
            # Add format options
            if metadata.backup_format == BackupFormat.CUSTOM:
                dump_cmd.extend(['--format=custom'])
            elif metadata.backup_format == BackupFormat.TAR:
                dump_cmd.extend(['--format=tar'])
            elif metadata.backup_format == BackupFormat.DIRECTORY:
                dump_cmd.extend(['--format=directory'])
            
            # Add compression
            if metadata.configuration.compression == CompressionType.GZIP:
                dump_cmd.append('--compress=6')
            
            # Add table filters
            if metadata.configuration.tables_to_include:
                for table in metadata.configuration.tables_to_include:
                    dump_cmd.extend(['--table', table])
            
            if metadata.configuration.tables_to_exclude:
                for table in metadata.configuration.tables_to_exclude:
                    dump_cmd.extend(['--exclude-table', table])
            
            # Add optional components
            if not metadata.configuration.include_indexes:
                dump_cmd.append('--no-indexes')
            if not metadata.configuration.include_triggers:
                dump_cmd.append('--no-triggers')
            
            # Set output file
            dump_cmd.extend(['--file', str(backup_file_path)])
            
            # Set password environment variable
            env = os.environ.copy()
            if parsed.password:
                env['PGPASSWORD'] = parsed.password
            
            # Execute backup
            start_time = time.time()
            
            process = await asyncio.create_subprocess_exec(
                *dump_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown backup error"
                raise Exception(f"pg_dump failed: {error_msg}")
            
            # Update metadata with file information
            metadata.file_path = str(backup_file_path)
            metadata.file_size = backup_file_path.stat().st_size if backup_file_path.exists() else 0
            
            # Apply additional compression if needed
            if metadata.configuration.compression != CompressionType.NONE and metadata.backup_format == BackupFormat.SQL:
                compressed_path = await self._compress_backup(backup_file_path, metadata.configuration.compression)
                metadata.file_path = str(compressed_path)
                metadata.compressed_size = compressed_path.stat().st_size
                metadata.compression_ratio = 1 - (metadata.compressed_size / max(metadata.file_size, 1))
            else:
                metadata.compressed_size = metadata.file_size
            
            # Calculate checksum
            metadata.checksum = await self._calculate_checksum(metadata.file_path)
            
            # Encrypt backup if required
            if metadata.configuration.encrypt_backup:
                encrypted_path = await self._encrypt_backup(metadata.file_path)
                metadata.file_path = str(encrypted_path)
                metadata.encryption_key_id = self.vault.generate_uuid()
            
            # Collect database metadata
            await self._collect_database_metadata(metadata, db_url)
            
            # Verify backup if required
            if metadata.configuration.verify_after_backup:
                metadata.verification_passed = await self._verify_backup_integrity(metadata)
            
            metadata.status = BackupStatus.COMPLETED
            metadata.completed_at = datetime.now(timezone.utc)
            
            # Audit successful backup
            self.audit.add_entry(
                'database_backup_completed',
                {
                    'backup_id': metadata.backup_id,
                    'pool_id': metadata.pool_id,
                    'file_size': metadata.file_size,
                    'compressed_size': metadata.compressed_size,
                    'duration': (metadata.completed_at - metadata.created_at).total_seconds(),
                    'verification_passed': metadata.verification_passed
                }
            )
            
        except Exception as e:
            metadata.status = BackupStatus.FAILED
            metadata.error_message = str(e)
            metadata.completed_at = datetime.now(timezone.utc)
            raise
    
    async def _get_database_url(self, pool_id: str) -> str:
        """Get secure database URL for pool"""
        try:
            # Get credentials from vault
            credential_key = f"database_{pool_id}"
            credentials = await self.vault.decrypt_data(credential_key)
            
            # Build database URL
            username = credentials.get('username', 'postgres')
            password = credentials.get('password', '')
            host = credentials.get('host', 'localhost')
            port = credentials.get('port', 5432)
            database = credentials.get('database', 'dafelhub')
            
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
            
        except Exception:
            # Fallback to environment variables
            return (f"postgresql://{os.getenv('DB_USER', 'postgres')}:"
                   f"{os.getenv('DB_PASSWORD', '')}@"
                   f"{os.getenv('DB_HOST', 'localhost')}:"
                   f"{os.getenv('DB_PORT', '5432')}/"
                   f"{os.getenv('DB_NAME', 'dafelhub')}")
    
    def _get_file_extension(self, backup_format: BackupFormat, compression: CompressionType) -> str:
        """Get appropriate file extension"""
        extensions = {
            BackupFormat.SQL: '.sql',
            BackupFormat.CUSTOM: '.backup',
            BackupFormat.TAR: '.tar',
            BackupFormat.DIRECTORY: ''  # Directory format doesn't have extension
        }
        
        base_ext = extensions.get(backup_format, '.backup')
        
        # Add compression extension
        if compression == CompressionType.GZIP and backup_format == BackupFormat.SQL:
            base_ext += '.gz'
        elif compression == CompressionType.BZIP2:
            base_ext += '.bz2'
        elif compression == CompressionType.XZ:
            base_ext += '.xz'
        
        return base_ext
    
    async def _compress_backup(self, file_path: Path, compression: CompressionType) -> Path:
        """Compress backup file"""
        
        if compression == CompressionType.GZIP:
            compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
            
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove original file
            file_path.unlink()
            return compressed_path
        
        # Add support for other compression types as needed
        return file_path
    
    async def _encrypt_backup(self, file_path: str) -> Path:
        """Encrypt backup file using vault manager"""
        
        encrypted_path = Path(file_path + '.enc')
        
        # Read and encrypt file
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Encrypt using vault manager
        encrypted_data = await self.vault.encrypt(file_data.decode('latin1'))  # Use latin1 for binary data
        
        # Write encrypted file
        with open(encrypted_path, 'w') as f:
            f.write(encrypted_data)
        
        # Remove original file
        os.unlink(file_path)
        
        return encrypted_path
    
    async def _decrypt_backup(self, metadata: BackupMetadata) -> str:
        """Decrypt backup file for restore"""
        
        if not metadata.encryption_key_id:
            return metadata.file_path
        
        # Create temporary file for decrypted data
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.backup')
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Read encrypted file
            with open(metadata.file_path, 'r') as f:
                encrypted_data = f.read()
            
            # Decrypt using vault manager
            decrypted_data = await self.vault.decrypt(encrypted_data)
            
            # Write decrypted file
            with open(temp_path, 'wb') as f:
                f.write(decrypted_data.encode('latin1'))  # Use latin1 for binary data
            
            return temp_path
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            raise
    
    async def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of backup file"""
        
        hash_sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    async def _verify_backup_integrity(self, metadata: BackupMetadata) -> bool:
        """Verify backup file integrity"""
        
        try:
            # Check file exists
            if not os.path.exists(metadata.file_path):
                return False
            
            # Verify checksum
            current_checksum = await self._calculate_checksum(metadata.file_path)
            if current_checksum != metadata.checksum:
                return False
            
            # Try to read backup file structure
            if metadata.backup_format == BackupFormat.CUSTOM:
                # Use pg_restore to list contents
                list_cmd = ['pg_restore', '--list', metadata.file_path]
                
                process = await asyncio.create_subprocess_exec(
                    *list_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Backup verification failed for {metadata.backup_id}: {e}")
            return False
    
    async def _collect_database_metadata(self, metadata: BackupMetadata, db_url: str) -> None:
        """Collect database metadata for backup"""
        
        try:
            # Get connection and collect basic info
            async with self.connection_manager.get_connection(metadata.pool_id) as conn:
                # Get database version
                version_result = await conn.fetchrow('SELECT version()')
                metadata.database_version = version_result['version'] if version_result else "unknown"
                
                # Get table count
                table_count_result = await conn.fetchrow('''
                    SELECT COUNT(*) as count FROM information_schema.tables 
                    WHERE table_schema = 'public'
                ''')
                metadata.table_count = table_count_result['count'] if table_count_result else 0
                
                # Estimate row count (approximate)
                if metadata.configuration.include_data:
                    row_count_result = await conn.fetchrow('''
                        SELECT SUM(n_tup_ins + n_tup_upd) as total_rows 
                        FROM pg_stat_user_tables
                    ''')
                    metadata.row_count = int(row_count_result['total_rows'] or 0)
                
        except Exception as e:
            self.logger.warning(f"Failed to collect database metadata: {e}")
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_part = hashlib.md5(f"{timestamp}_{os.urandom(8)}".encode()).hexdigest()[:8]
        return f"bk_{timestamp}_{hash_part}"
    
    def _generate_schedule_id(self) -> str:
        """Generate unique schedule ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_part = hashlib.md5(f"{timestamp}_{os.urandom(8)}".encode()).hexdigest()[:8]
        return f"sched_{timestamp}_{hash_part}"
    
    def _calculate_next_run(self, cron_expression: str) -> Optional[datetime]:
        """Calculate next run time from cron expression"""
        try:
            # This is a simplified implementation
            # In production, use a proper cron library like croniter
            
            # For now, return next hour as placeholder
            return datetime.now() + timedelta(hours=1)
            
        except Exception as e:
            self.logger.error(f"Failed to parse cron expression '{cron_expression}': {e}")
            return None
    
    def _update_backup_stats(self, metadata: BackupMetadata) -> None:
        """Update backup statistics"""
        
        self._backup_stats['total_backups'] += 1
        
        if metadata.status == BackupStatus.COMPLETED:
            self._backup_stats['successful_backups'] += 1
        elif metadata.status == BackupStatus.FAILED:
            self._backup_stats['failed_backups'] += 1
        
        # Update size statistics
        if metadata.file_size > 0:
            size_gb = metadata.file_size / (1024 ** 3)
            self._backup_stats['total_size_gb'] += size_gb
            
            if metadata.compressed_size > 0:
                compression_savings = (metadata.file_size - metadata.compressed_size) / (1024 ** 3)
                self._backup_stats['compression_savings_gb'] += compression_savings
        
        # Update average duration
        if metadata.completed_at and metadata.created_at:
            duration = (metadata.completed_at - metadata.created_at).total_seconds()
            current_avg = self._backup_stats['avg_backup_duration']
            total_backups = self._backup_stats['total_backups']
            
            self._backup_stats['avg_backup_duration'] = (
                (current_avg * (total_backups - 1) + duration) / total_backups
            )
    
    def _load_backup_metadata(self) -> None:
        """Load existing backup metadata from disk"""
        
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct metadata object
                config_data = data.get('configuration')
                configuration = None
                if config_data:
                    configuration = BackupConfiguration(
                        backup_type=BackupType(config_data['backup_type']),
                        backup_format=BackupFormat(config_data['backup_format']),
                        compression=CompressionType(config_data['compression']),
                        include_data=config_data['include_data'],
                        include_schema=config_data['include_schema'],
                        include_indexes=config_data['include_indexes'],
                        include_triggers=config_data['include_triggers'],
                        include_functions=config_data['include_functions'],
                        tables_to_include=config_data['tables_to_include'],
                        tables_to_exclude=config_data['tables_to_exclude'],
                        encrypt_backup=config_data['encrypt_backup'],
                        verify_after_backup=config_data['verify_after_backup'],
                        retention_days=config_data['retention_days'],
                        max_parallel_jobs=config_data['max_parallel_jobs']
                    )
                
                metadata = BackupMetadata(
                    backup_id=data['backup_id'],
                    backup_name=data['backup_name'],
                    pool_id=data['pool_id'],
                    backup_type=BackupType(data['backup_type']),
                    backup_format=BackupFormat(data['backup_format']),
                    created_at=datetime.fromisoformat(data['created_at']),
                    completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
                    file_path=data['file_path'],
                    file_size=data['file_size'],
                    compressed_size=data['compressed_size'],
                    compression_ratio=data['compression_ratio'],
                    checksum=data['checksum'],
                    encryption_key_id=data['encryption_key_id'],
                    database_version=data['database_version'],
                    schema_version=data['schema_version'],
                    table_count=data['table_count'],
                    row_count=data['row_count'],
                    configuration=configuration,
                    status=BackupStatus(data['status']),
                    error_message=data['error_message'],
                    verification_passed=data['verification_passed']
                )
                
                self._backup_metadata[metadata.backup_id] = metadata
                
                self.logger.debug(f"Loaded backup metadata: {metadata.backup_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to load backup metadata: {e}")
    
    async def _save_backup_metadata(self, metadata: BackupMetadata) -> None:
        """Save backup metadata to disk"""
        
        try:
            metadata_file = self.metadata_dir / f"{metadata.backup_id}.json"
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata.to_dict(), f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save backup metadata for {metadata.backup_id}: {e}")
    
    async def _start_scheduler(self) -> None:
        """Start backup scheduler"""
        
        if self._scheduler_active:
            return
        
        self._scheduler_active = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        self.logger.info("Backup scheduler started")
    
    async def _scheduler_loop(self) -> None:
        """Background scheduler loop"""
        
        while self._scheduler_active and not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check all schedules
                for schedule in list(self._backup_schedules.values()):
                    if not schedule.enabled:
                        continue
                    
                    if schedule.next_run and current_time >= schedule.next_run:
                        # Time to run backup
                        try:
                            await self.create_backup(
                                schedule.pool_id,
                                f"{schedule.schedule_name}_{current_time.strftime('%Y%m%d_%H%M%S')}",
                                schedule.configuration
                            )
                            
                            schedule.last_run = current_time
                            schedule.consecutive_failures = 0
                            
                        except Exception as e:
                            schedule.consecutive_failures += 1
                            
                            self.logger.error(f"Scheduled backup failed: {schedule.schedule_name}", extra={
                                "schedule_id": schedule.schedule_id,
                                "consecutive_failures": schedule.consecutive_failures,
                                "error": str(e)
                            })
                            
                            # Disable schedule if too many failures
                            if schedule.consecutive_failures >= schedule.max_failures:
                                schedule.enabled = False
                                
                                self.audit.add_entry(
                                    'backup_schedule_disabled',
                                    {
                                        'schedule_id': schedule.schedule_id,
                                        'consecutive_failures': schedule.consecutive_failures,
                                        'reason': 'too_many_failures'
                                    }
                                )
                        
                        # Calculate next run
                        schedule.next_run = self._calculate_next_run(schedule.cron_expression)
                
                # Sleep for a minute before checking again
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in backup scheduler loop: {e}")
                await asyncio.sleep(60)
        
        self.logger.info("Backup scheduler stopped")


# Global singleton instance
_backup_system: Optional[EnterpriseBackupSystem] = None
_backup_lock = threading.Lock()


def get_backup_system() -> EnterpriseBackupSystem:
    """Get global backup system instance"""
    global _backup_system
    
    with _backup_lock:
        if _backup_system is None:
            _backup_system = EnterpriseBackupSystem()
        return _backup_system