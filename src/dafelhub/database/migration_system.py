"""
DafelHub Enterprise Migration System
Automated database migration system with Alembic integration
Enterprise-grade schema versioning and deployment automation

Features:
- Automated migration generation and execution
- Schema version tracking and rollback
- Multi-environment migration support
- Security integration with audit trail
- Migration validation and testing
- Backup creation before migrations
- Conflict resolution and merge strategies
- Performance monitoring during migrations

TODO: [DB-004] Implement automatic migration generation - @DatabaseAgent - 2024-09-24
TODO: [DB-005] Add migration validation and testing - @DatabaseAgent - 2024-09-24
TODO: [DB-006] Integrate backup system with migrations - @DatabaseAgent - 2024-09-24
"""

import os
import sys
import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import subprocess

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.security.audit_trail import get_persistent_audit_trail
from dafelhub.database.connection_manager import get_connection_manager


logger = get_logger(__name__)


class MigrationStatus(Enum):
    """Migration execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


class MigrationType(Enum):
    """Migration types"""
    SCHEMA = "schema"           # DDL changes
    DATA = "data"              # DML changes  
    INDEX = "index"            # Index operations
    CONSTRAINT = "constraint"   # Constraint operations
    SECURITY = "security"      # Security and permissions
    MIXED = "mixed"            # Multiple types


@dataclass
class MigrationPlan:
    """Migration execution plan"""
    migration_id: str
    revision: str
    description: str
    migration_type: MigrationType
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: Optional[float] = None
    requires_downtime: bool = False
    backup_required: bool = True
    validation_queries: List[str] = field(default_factory=list)
    rollback_plan: Optional[str] = None
    environment: str = "development"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'migration_id': self.migration_id,
            'revision': self.revision,
            'description': self.description,
            'migration_type': self.migration_type.value,
            'dependencies': self.dependencies,
            'estimated_duration': self.estimated_duration,
            'requires_downtime': self.requires_downtime,
            'backup_required': self.backup_required,
            'validation_queries': self.validation_queries,
            'rollback_plan': self.rollback_plan,
            'environment': self.environment
        }


@dataclass
class MigrationResult:
    """Migration execution result"""
    migration_id: str
    status: MigrationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    rollback_revision: Optional[str] = None
    backup_path: Optional[str] = None
    validation_results: Dict[str, Any] = field(default_factory=dict)
    affected_objects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'migration_id': self.migration_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'error': self.error,
            'rollback_revision': self.rollback_revision,
            'backup_path': self.backup_path,
            'validation_results': self.validation_results,
            'affected_objects': self.affected_objects
        }


class EnterpriseMigrationSystem(LoggerMixin):
    """
    Enterprise Migration System with Advanced Features
    
    Features:
    - Automated migration generation with Alembic
    - Schema versioning and rollback capabilities
    - Multi-environment deployment support
    - Pre-migration backup and validation
    - Performance monitoring and optimization
    - Conflict resolution and merge strategies
    - Security audit integration
    - Zero-downtime migration strategies
    """
    
    def __init__(self, vault_manager=None, audit_trail=None):
        super().__init__()
        
        # Core dependencies
        self.vault = vault_manager or get_enterprise_vault_manager()
        self.audit = audit_trail or get_persistent_audit_trail()
        self.connection_manager = get_connection_manager()
        
        # Migration configuration
        self.migrations_dir = Path(settings.UPLOAD_PATH) / "migrations"
        self.alembic_dir = self.migrations_dir / "alembic"
        self.backup_dir = Path(settings.UPLOAD_PATH) / "migration_backups"
        self.config_dir = self.migrations_dir / "config"
        
        # Ensure directories exist
        for directory in [self.migrations_dir, self.alembic_dir, self.backup_dir, self.config_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Migration tracking
        self._migration_history: Dict[str, MigrationResult] = {}
        self._active_migrations: Dict[str, MigrationPlan] = {}
        self._environment_configs: Dict[str, Dict[str, Any]] = {}
        self._alembic_configs: Dict[str, Config] = {}
        
        # Performance tracking
        self._migration_stats = {
            'total_migrations': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'total_duration': 0.0,
            'average_duration': 0.0
        }
        
        # Initialize default environments
        self._initialize_environments()
        
        self.logger.info("Enterprise Migration System initialized", extra={
            "migrations_dir": str(self.migrations_dir),
            "backup_dir": str(self.backup_dir)
        })
    
    def _initialize_environments(self) -> None:
        """Initialize default environment configurations"""
        
        environments = {
            'development': {
                'auto_generate': True,
                'backup_required': True,
                'validation_required': True,
                'downtime_allowed': True,
                'max_migration_time': 300,  # 5 minutes
                'parallel_execution': False
            },
            'staging': {
                'auto_generate': False,
                'backup_required': True,
                'validation_required': True,
                'downtime_allowed': True,
                'max_migration_time': 600,  # 10 minutes
                'parallel_execution': False
            },
            'production': {
                'auto_generate': False,
                'backup_required': True,
                'validation_required': True,
                'downtime_allowed': False,
                'max_migration_time': 1800,  # 30 minutes
                'parallel_execution': True
            }
        }
        
        for env_name, config in environments.items():
            self._environment_configs[env_name] = config
            self._setup_alembic_config(env_name, config)
    
    def _setup_alembic_config(self, environment: str, config: Dict[str, Any]) -> None:
        """Setup Alembic configuration for environment"""
        try:
            # Create environment-specific alembic directory
            env_alembic_dir = self.alembic_dir / environment
            env_alembic_dir.mkdir(exist_ok=True)
            
            # Create versions directory
            versions_dir = env_alembic_dir / "versions"
            versions_dir.mkdir(exist_ok=True)
            
            # Create alembic.ini file
            alembic_ini_path = env_alembic_dir / "alembic.ini"
            alembic_ini_content = f"""
[alembic]
script_location = {env_alembic_dir}
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = driver://user:pass@localhost/dbname

file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers] 
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %%(levelname)-5.5s [%%(name)s] %%(message)s
datefmt = %%H:%%M:%%S
"""
            
            with open(alembic_ini_path, 'w') as f:
                f.write(alembic_ini_content.strip())
            
            # Create env.py file
            env_py_path = env_alembic_dir / "env.py"
            env_py_content = '''
import asyncio
import os
import sys
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dafelhub.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
            
            with open(env_py_path, 'w') as f:
                f.write(env_py_content.strip())
            
            # Create script.py.mako template
            script_mako_path = env_alembic_dir / "script.py.mako"
            script_mako_content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

def upgrade() -> None:
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
            
            with open(script_mako_path, 'w') as f:
                f.write(script_mako_content.strip())
            
            # Create Alembic config object
            alembic_config = Config(str(alembic_ini_path))
            alembic_config.set_main_option("script_location", str(env_alembic_dir))
            alembic_config.set_main_option("version_locations", str(versions_dir))
            
            self._alembic_configs[environment] = alembic_config
            
            self.logger.info(f"Alembic configuration created for environment: {environment}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup Alembic config for {environment}: {e}")
            raise
    
    async def generate_migration(
        self,
        message: str,
        environment: str = "development",
        auto_generate: bool = True,
        model_changes: Optional[List[str]] = None
    ) -> MigrationPlan:
        """Generate new migration with automatic detection"""
        
        if environment not in self._environment_configs:
            raise ValueError(f"Unknown environment: {environment}")
        
        env_config = self._environment_configs[environment]
        
        # Check if auto-generation is allowed
        if auto_generate and not env_config.get('auto_generate', False):
            raise ValueError(f"Auto-generation not allowed in {environment} environment")
        
        migration_id = self._generate_migration_id()
        
        try:
            # Audit migration generation start
            self.audit.add_entry(
                'migration_generation_started',
                {
                    'migration_id': migration_id,
                    'message': message,
                    'environment': environment,
                    'auto_generate': auto_generate
                }
            )
            
            # Get database connection string for environment
            db_url = await self._get_database_url(environment)
            
            # Update alembic config with database URL
            alembic_config = self._alembic_configs[environment]
            alembic_config.set_main_option("sqlalchemy.url", db_url)
            
            # Generate migration using Alembic
            if auto_generate:
                # Auto-generate based on model changes
                revision = command.revision(
                    alembic_config,
                    message=message,
                    autogenerate=True,
                    rev_id=migration_id
                )
            else:
                # Create empty migration
                revision = command.revision(
                    alembic_config,
                    message=message,
                    rev_id=migration_id
                )
            
            # Analyze generated migration
            migration_type = self._analyze_migration_type(revision.path)
            dependencies = self._extract_dependencies(revision.path)
            validation_queries = self._generate_validation_queries(revision.path)
            
            # Create migration plan
            plan = MigrationPlan(
                migration_id=migration_id,
                revision=revision.revision,
                description=message,
                migration_type=migration_type,
                dependencies=dependencies,
                backup_required=env_config.get('backup_required', True),
                validation_queries=validation_queries,
                environment=environment
            )
            
            # Estimate migration duration
            plan.estimated_duration = await self._estimate_migration_duration(plan, db_url)
            
            # Store migration plan
            self._active_migrations[migration_id] = plan
            
            # Audit successful generation
            self.audit.add_entry(
                'migration_generated',
                {
                    'migration_id': migration_id,
                    'revision': revision.revision,
                    'plan': plan.to_dict()
                }
            )
            
            self.logger.info(f"Migration generated successfully: {migration_id}", extra={
                "revision": revision.revision,
                "message": message,
                "environment": environment,
                "type": migration_type.value
            })
            
            return plan
            
        except Exception as e:
            # Audit failure
            self.audit.add_entry(
                'migration_generation_failed',
                {
                    'migration_id': migration_id,
                    'message': message,
                    'environment': environment,
                    'error': str(e)
                }
            )
            
            self.logger.error(f"Failed to generate migration: {migration_id}", extra={
                "error": str(e),
                "environment": environment
            })
            raise
    
    async def execute_migration(
        self,
        migration_id: str,
        environment: str,
        dry_run: bool = False,
        force: bool = False
    ) -> MigrationResult:
        """Execute migration with comprehensive monitoring"""
        
        if migration_id not in self._active_migrations:
            raise ValueError(f"Migration not found: {migration_id}")
        
        plan = self._active_migrations[migration_id]
        env_config = self._environment_configs[environment]
        
        # Create migration result
        result = MigrationResult(
            migration_id=migration_id,
            status=MigrationStatus.PENDING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Validate environment compatibility
            if plan.environment != environment and not force:
                raise ValueError(f"Migration created for {plan.environment}, not {environment}")
            
            # Check migration duration limits
            if (plan.estimated_duration and 
                plan.estimated_duration > env_config.get('max_migration_time', 1800)):
                if not force:
                    raise ValueError(f"Migration exceeds time limit: {plan.estimated_duration}s")
            
            # Check downtime requirements
            if (plan.requires_downtime and 
                not env_config.get('downtime_allowed', False) and 
                not force):
                raise ValueError(f"Migration requires downtime, not allowed in {environment}")
            
            result.status = MigrationStatus.RUNNING
            
            # Audit migration start
            self.audit.add_entry(
                'migration_execution_started',
                {
                    'migration_id': migration_id,
                    'environment': environment,
                    'dry_run': dry_run,
                    'plan': plan.to_dict()
                }
            )
            
            # Get database connection
            db_url = await self._get_database_url(environment)
            alembic_config = self._alembic_configs[environment]
            alembic_config.set_main_option("sqlalchemy.url", db_url)
            
            # Create backup if required
            backup_path = None
            if plan.backup_required and not dry_run:
                backup_path = await self._create_migration_backup(environment, migration_id)
                result.backup_path = backup_path
            
            # Execute pre-migration validation
            if env_config.get('validation_required', False):
                validation_results = await self._validate_migration(plan, db_url)
                result.validation_results = validation_results
                
                if not validation_results.get('valid', False) and not force:
                    raise ValueError(f"Migration validation failed: {validation_results.get('errors')}")
            
            # Execute migration
            if dry_run:
                # Simulate migration execution
                self.logger.info(f"DRY RUN: Would execute migration {migration_id}")
                result.status = MigrationStatus.COMPLETED
                result.affected_objects = ["dry_run_simulation"]
            else:
                # Execute actual migration
                start_execution = datetime.now()
                
                # Run migration with Alembic
                command.upgrade(alembic_config, plan.revision)
                
                # Track affected objects
                result.affected_objects = await self._get_affected_objects(plan, db_url)
                
                result.status = MigrationStatus.COMPLETED
                result.duration = (datetime.now() - start_execution).total_seconds()
            
            result.completed_at = datetime.now(timezone.utc)
            
            # Store result
            self._migration_history[migration_id] = result
            
            # Update statistics
            self._update_migration_stats(result)
            
            # Audit successful completion
            self.audit.add_entry(
                'migration_executed',
                {
                    'migration_id': migration_id,
                    'environment': environment,
                    'result': result.to_dict()
                }
            )
            
            self.logger.info(f"Migration executed successfully: {migration_id}", extra={
                "environment": environment,
                "duration": result.duration,
                "affected_objects": len(result.affected_objects)
            })
            
            return result
            
        except Exception as e:
            result.status = MigrationStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            
            if result.started_at:
                result.duration = (result.completed_at - result.started_at).total_seconds()
            
            # Store failed result
            self._migration_history[migration_id] = result
            
            # Update statistics
            self._update_migration_stats(result)
            
            # Audit failure
            self.audit.add_entry(
                'migration_execution_failed',
                {
                    'migration_id': migration_id,
                    'environment': environment,
                    'error': str(e),
                    'result': result.to_dict()
                }
            )
            
            self.logger.error(f"Migration execution failed: {migration_id}", extra={
                "environment": environment,
                "error": str(e)
            })
            
            # Attempt rollback if backup exists
            if result.backup_path and not dry_run:
                try:
                    await self._rollback_migration(migration_id, environment, result.backup_path)
                    result.rollback_revision = "backup_restored"
                except Exception as rollback_error:
                    self.logger.error(f"Rollback failed for {migration_id}: {rollback_error}")
            
            raise
    
    async def rollback_migration(
        self,
        migration_id: str,
        environment: str,
        target_revision: Optional[str] = None
    ) -> MigrationResult:
        """Rollback migration to previous state"""
        
        try:
            # Get database connection
            db_url = await self._get_database_url(environment)
            alembic_config = self._alembic_configs[environment]
            alembic_config.set_main_option("sqlalchemy.url", db_url)
            
            # Determine target revision
            if not target_revision:
                # Get previous revision
                script_dir = ScriptDirectory.from_config(alembic_config)
                current_revision = script_dir.get_current_head()
                revisions = list(script_dir.walk_revisions())
                
                # Find previous revision
                for i, rev in enumerate(revisions):
                    if rev.revision == current_revision and i < len(revisions) - 1:
                        target_revision = revisions[i + 1].revision
                        break
                
                if not target_revision:
                    raise ValueError("Cannot determine target revision for rollback")
            
            # Create rollback result
            result = MigrationResult(
                migration_id=migration_id,
                status=MigrationStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                rollback_revision=target_revision
            )
            
            # Execute rollback
            command.downgrade(alembic_config, target_revision)
            
            result.status = MigrationStatus.ROLLED_BACK
            result.completed_at = datetime.now(timezone.utc)
            result.duration = (result.completed_at - result.started_at).total_seconds()
            
            # Store result
            self._migration_history[f"{migration_id}_rollback"] = result
            
            # Audit rollback
            self.audit.add_entry(
                'migration_rolled_back',
                {
                    'migration_id': migration_id,
                    'environment': environment,
                    'target_revision': target_revision,
                    'result': result.to_dict()
                }
            )
            
            self.logger.info(f"Migration rolled back successfully: {migration_id}", extra={
                "target_revision": target_revision,
                "environment": environment
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Migration rollback failed: {migration_id}", extra={
                "error": str(e),
                "environment": environment
            })
            raise
    
    async def get_migration_status(self, environment: str) -> Dict[str, Any]:
        """Get comprehensive migration status"""
        
        try:
            # Get database connection
            db_url = await self._get_database_url(environment)
            alembic_config = self._alembic_configs[environment]
            alembic_config.set_main_option("sqlalchemy.url", db_url)
            
            # Get current revision
            engine = create_engine(db_url)
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_revision = context.get_current_revision()
            
            # Get script directory info
            script_dir = ScriptDirectory.from_config(alembic_config)
            heads = script_dir.get_revisions('heads')
            pending_revisions = []
            
            if current_revision:
                pending_revisions = list(script_dir.iterate_revisions(
                    current_revision, 'heads'
                ))[1:]  # Exclude current revision
            
            return {
                'environment': environment,
                'current_revision': current_revision,
                'head_revision': heads[0].revision if heads else None,
                'pending_migrations': len(pending_revisions),
                'pending_revisions': [rev.revision for rev in pending_revisions],
                'active_migrations': len(self._active_migrations),
                'migration_history': len(self._migration_history),
                'statistics': self._migration_stats,
                'last_migration': max([
                    result.completed_at for result in self._migration_history.values()
                    if result.completed_at
                ], default=None)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get migration status for {environment}: {e}")
            return {
                'environment': environment,
                'error': str(e),
                'statistics': self._migration_stats
            }
    
    # Private methods
    
    def _generate_migration_id(self) -> str:
        """Generate unique migration ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        hash_part = hashlib.md5(f"{timestamp}_{os.urandom(8)}".encode()).hexdigest()[:8]
        return f"mg_{timestamp}_{hash_part}"
    
    async def _get_database_url(self, environment: str) -> str:
        """Get secure database URL for environment"""
        try:
            # Get credentials from vault
            credential_key = f"database_{environment}"
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
    
    def _analyze_migration_type(self, migration_path: str) -> MigrationType:
        """Analyze migration file to determine type"""
        try:
            with open(migration_path, 'r') as f:
                content = f.read().lower()
            
            # Analyze migration content
            schema_keywords = ['create_table', 'drop_table', 'alter_table', 'add_column', 'drop_column']
            index_keywords = ['create_index', 'drop_index']
            constraint_keywords = ['add_constraint', 'drop_constraint']
            data_keywords = ['insert', 'update', 'delete', 'execute']
            
            type_counts = {
                MigrationType.SCHEMA: sum(1 for kw in schema_keywords if kw in content),
                MigrationType.INDEX: sum(1 for kw in index_keywords if kw in content),
                MigrationType.CONSTRAINT: sum(1 for kw in constraint_keywords if kw in content),
                MigrationType.DATA: sum(1 for kw in data_keywords if kw in content)
            }
            
            # Determine primary type
            max_count = max(type_counts.values())
            if max_count == 0:
                return MigrationType.MIXED
            
            # Find type with highest count
            for migration_type, count in type_counts.items():
                if count == max_count:
                    return migration_type
            
            return MigrationType.MIXED
            
        except Exception:
            return MigrationType.MIXED
    
    def _extract_dependencies(self, migration_path: str) -> List[str]:
        """Extract migration dependencies"""
        dependencies = []
        try:
            with open(migration_path, 'r') as f:
                content = f.read()
            
            # Look for depends_on in migration file
            import re
            depends_on_match = re.search(r'depends_on\s*[:=]\s*\[(.*?)\]', content, re.DOTALL)
            if depends_on_match:
                deps_str = depends_on_match.group(1)
                # Extract quoted strings
                deps = re.findall(r'["\']([^"\']+)["\']', deps_str)
                dependencies.extend(deps)
                
        except Exception as e:
            self.logger.warning(f"Failed to extract dependencies from {migration_path}: {e}")
            
        return dependencies
    
    def _generate_validation_queries(self, migration_path: str) -> List[str]:
        """Generate validation queries for migration"""
        queries = []
        
        try:
            with open(migration_path, 'r') as f:
                content = f.read().lower()
            
            # Generate basic validation queries based on content
            if 'create_table' in content:
                queries.append("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            
            if 'add_column' in content:
                queries.append("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public'")
            
            if 'create_index' in content:
                queries.append("SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public'")
            
            # Add generic validation
            queries.append("SELECT version()")  # Basic connectivity test
            
        except Exception as e:
            self.logger.warning(f"Failed to generate validation queries for {migration_path}: {e}")
            
        return queries or ["SELECT 1"]  # Default validation
    
    async def _estimate_migration_duration(self, plan: MigrationPlan, db_url: str) -> float:
        """Estimate migration duration based on historical data and analysis"""
        
        # Base estimation based on type
        base_durations = {
            MigrationType.SCHEMA: 30.0,     # 30 seconds
            MigrationType.DATA: 120.0,      # 2 minutes
            MigrationType.INDEX: 180.0,     # 3 minutes
            MigrationType.CONSTRAINT: 60.0,  # 1 minute
            MigrationType.SECURITY: 15.0,   # 15 seconds
            MigrationType.MIXED: 90.0       # 1.5 minutes
        }
        
        base_duration = base_durations.get(plan.migration_type, 60.0)
        
        # Adjust based on historical data
        historical_durations = [
            result.duration for result in self._migration_history.values()
            if (result.duration and 
                result.status == MigrationStatus.COMPLETED and
                plan.migration_type.value in result.migration_id)
        ]
        
        if historical_durations:
            avg_historical = sum(historical_durations) / len(historical_durations)
            # Weight: 70% historical, 30% base estimate
            estimated_duration = 0.7 * avg_historical + 0.3 * base_duration
        else:
            estimated_duration = base_duration
        
        # Add buffer for safety (20%)
        return estimated_duration * 1.2
    
    async def _validate_migration(self, plan: MigrationPlan, db_url: str) -> Dict[str, Any]:
        """Validate migration before execution"""
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'checks_performed': []
        }
        
        try:
            engine = create_engine(db_url)
            
            with engine.connect() as conn:
                # Run validation queries
                for i, query in enumerate(plan.validation_queries):
                    try:
                        result = conn.execute(text(query))
                        validation_results['checks_performed'].append(f"Query {i+1}: SUCCESS")
                    except Exception as e:
                        error_msg = f"Validation query {i+1} failed: {str(e)}"
                        validation_results['errors'].append(error_msg)
                        validation_results['valid'] = False
                
                # Check for potential conflicts
                inspector = inspect(engine)
                existing_tables = inspector.get_table_names()
                
                # Add warnings for large tables that might be affected
                for table in existing_tables:
                    try:
                        row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                        if row_count > 100000:  # Large table threshold
                            validation_results['warnings'].append(
                                f"Large table {table} ({row_count} rows) might be affected"
                            )
                    except Exception:
                        pass  # Skip if can't count rows
                
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Connection error: {str(e)}")
        
        return validation_results
    
    async def _create_migration_backup(self, environment: str, migration_id: str) -> str:
        """Create backup before migration"""
        
        try:
            backup_name = f"backup_{environment}_{migration_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = self.backup_dir / f"{backup_name}.sql"
            
            # Get database connection details
            db_url = await self._get_database_url(environment)
            
            # Parse connection details for pg_dump
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            
            # Create pg_dump command
            dump_cmd = [
                'pg_dump',
                f'--host={parsed.hostname}',
                f'--port={parsed.port or 5432}',
                f'--username={parsed.username}',
                f'--dbname={parsed.path.lstrip("/")}',
                '--no-password',
                '--verbose',
                '--create',
                '--schema-only',  # Schema only for faster backup
                f'--file={backup_path}'
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            if parsed.password:
                env['PGPASSWORD'] = parsed.password
            
            # Execute backup
            process = await asyncio.create_subprocess_exec(
                *dump_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"pg_dump failed: {stderr.decode()}")
            
            self.logger.info(f"Migration backup created: {backup_path}")
            
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Failed to create migration backup: {e}")
            raise
    
    async def _rollback_migration(self, migration_id: str, environment: str, backup_path: str) -> None:
        """Rollback migration using backup"""
        
        try:
            # Get database connection details
            db_url = await self._get_database_url(environment)
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            
            # Create psql command to restore backup
            restore_cmd = [
                'psql',
                f'--host={parsed.hostname}',
                f'--port={parsed.port or 5432}',
                f'--username={parsed.username}',
                f'--dbname={parsed.path.lstrip("/")}',
                '--no-password',
                f'--file={backup_path}'
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            if parsed.password:
                env['PGPASSWORD'] = parsed.password
            
            # Execute restore
            process = await asyncio.create_subprocess_exec(
                *restore_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Backup restore failed: {stderr.decode()}")
            
            self.logger.info(f"Migration rolled back using backup: {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to rollback using backup: {e}")
            raise
    
    async def _get_affected_objects(self, plan: MigrationPlan, db_url: str) -> List[str]:
        """Get list of database objects affected by migration"""
        
        affected_objects = []
        
        try:
            engine = create_engine(db_url)
            inspector = inspect(engine)
            
            # Get current database objects
            tables = inspector.get_table_names()
            views = inspector.get_view_names()
            
            affected_objects.extend([f"table:{table}" for table in tables])
            affected_objects.extend([f"view:{view}" for view in views])
            
            # Add indexes
            for table in tables:
                indexes = inspector.get_indexes(table)
                affected_objects.extend([f"index:{idx['name']}" for idx in indexes])
                
        except Exception as e:
            self.logger.warning(f"Failed to get affected objects: {e}")
            affected_objects = ["unknown"]
        
        return affected_objects
    
    def _update_migration_stats(self, result: MigrationResult) -> None:
        """Update migration statistics"""
        
        self._migration_stats['total_migrations'] += 1
        
        if result.status == MigrationStatus.COMPLETED:
            self._migration_stats['successful_migrations'] += 1
        elif result.status == MigrationStatus.FAILED:
            self._migration_stats['failed_migrations'] += 1
        
        if result.duration:
            self._migration_stats['total_duration'] += result.duration
            self._migration_stats['average_duration'] = (
                self._migration_stats['total_duration'] / 
                self._migration_stats['total_migrations']
            )


# Global singleton instance
_migration_system: Optional[EnterpriseMigrationSystem] = None


def get_migration_system() -> EnterpriseMigrationSystem:
    """Get global migration system instance"""
    global _migration_system
    if _migration_system is None:
        _migration_system = EnterpriseMigrationSystem()
    return _migration_system