#!/usr/bin/env python3
"""
DafelHub Database Initialization Script
Comprehensive database setup integrating all agent models and configurations.

Usage:
    python -m dafelhub.database.init_database
    
Features:
- Creates all tables from SecurityAgent, DatabaseAgent, and API models
- Sets up admin user with proper RBAC roles
- Configures initial security policies
- Creates demo data for testing
- Handles database migrations and upgrades
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Database imports
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Core imports
from dafelhub.core.config import settings
from dafelhub.core.logging import get_logger
from dafelhub.core.encryption import EnterpriseVaultManager

# Security imports
from dafelhub.security.authentication import AuthenticationManager
from dafelhub.security.rbac_system import RBACManager, SecurityRole, Permission
from dafelhub.security.jwt_manager import EnterpriseJWTManager
from dafelhub.security.mfa_system import get_mfa_manager

# Database models
from dafelhub.database.models.base import Base
from dafelhub.database.models.user import User
from dafelhub.security.models import (
    UserSession, LoginAttempt, APIToken, TokenBlacklist,
    MFADevice, SecurityNotification, RiskAssessment,
    SecurityConfiguration, UserRole, RolePermission
)

# Database connection management
from dafelhub.database.connection_manager import DatabaseConnectionManager

logger = get_logger(__name__)


class DatabaseInitializer:
    """Comprehensive database initialization for DafelHub Enterprise"""
    
    def __init__(self):
        self.database_url = settings.DATABASE_URL
        self.engine = None
        self.session_factory = None
        self.vault_manager = None
        
    async def initialize(self, create_demo_data: bool = True, force_recreate: bool = False):
        """
        Initialize the complete database system
        
        Args:
            create_demo_data: Whether to create demo data for testing
            force_recreate: Whether to drop and recreate all tables
        """
        logger.info("🚀 Starting DafelHub database initialization...")
        
        try:
            # Step 1: Setup database connection
            await self._setup_database_connection()
            
            # Step 2: Initialize vault manager
            await self._setup_vault_manager()
            
            # Step 3: Create/update database schema
            await self._create_database_schema(force_recreate)
            
            # Step 4: Create initial security configuration
            await self._setup_security_configuration()
            
            # Step 5: Create admin user and RBAC setup
            await self._setup_admin_user()
            
            # Step 6: Configure default roles and permissions
            await self._setup_rbac_system()
            
            # Step 7: Create demo data if requested
            if create_demo_data:
                await self._create_demo_data()
            
            # Step 8: Validate database integrity
            await self._validate_database()
            
            logger.info("✅ Database initialization completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
            return False
            
    async def _setup_database_connection(self):
        """Setup database engine and session factory"""
        logger.info("Setting up database connection...")
        
        # Create engine with appropriate settings
        if self.database_url.startswith("sqlite"):
            # SQLite specific configuration
            self.engine = create_engine(
                self.database_url,
                echo=settings.DATABASE_ECHO,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            # PostgreSQL/MySQL configuration
            self.engine = create_engine(
                self.database_url,
                echo=settings.DATABASE_ECHO,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=settings.DATABASE_POOL_TIMEOUT,
                pool_recycle=settings.DATABASE_POOL_RECYCLE,
                pool_pre_ping=True,
            )
        
        # Create session factory
        self.session_factory = sessionmaker(bind=self.engine)
        
        # Test connection
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("✅ Database connection established")
        
    async def _setup_vault_manager(self):
        """Initialize the enterprise vault manager"""
        logger.info("Setting up enterprise vault manager...")
        
        self.vault_manager = EnterpriseVaultManager()
        
        # Initialize vault with master key
        master_key = settings.VAULT_MASTER_KEY
        if not master_key:
            logger.warning("VAULT_MASTER_KEY not set, using default (NOT FOR PRODUCTION)")
            master_key = "development-master-key-change-in-prod"
            
        await self.vault_manager.initialize(master_key)
        logger.info("✅ Enterprise vault manager initialized")
        
    async def _create_database_schema(self, force_recreate: bool = False):
        """Create or update database schema"""
        logger.info("Creating database schema...")
        
        if force_recreate:
            logger.warning("🗑️ Dropping all existing tables...")
            Base.metadata.drop_all(bind=self.engine)
            
        # Create all tables
        logger.info("Creating tables from all models...")
        Base.metadata.create_all(bind=self.engine)
        
        # Log created tables
        inspector = self.engine.dialect.inspector(self.engine)
        tables = inspector.get_table_names()
        logger.info(f"✅ Created {len(tables)} database tables: {', '.join(tables)}")
        
    async def _setup_security_configuration(self):
        """Setup initial security configuration"""
        logger.info("Setting up security configuration...")
        
        with self.session_factory() as session:
            # Check if security config already exists
            existing_config = session.query(SecurityConfiguration).first()
            if existing_config:
                logger.info("Security configuration already exists")
                return
                
            # Create initial security configuration
            security_config = SecurityConfiguration(
                password_min_length=settings.PASSWORD_MIN_LENGTH,
                password_require_uppercase=True,
                password_require_lowercase=True,
                password_require_numbers=True,
                password_require_special=True,
                account_lockout_attempts=settings.ACCOUNT_LOCKOUT_ATTEMPTS,
                account_lockout_duration_minutes=settings.ACCOUNT_LOCKOUT_DURATION_MINUTES,
                session_timeout_minutes=settings.SESSION_TIMEOUT_MINUTES,
                mfa_required_for_admin=True,
                mfa_required_for_api=False,
                audit_log_retention_days=90,
                force_password_change_days=settings.FORCE_PASSWORD_CHANGE_DAYS,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(security_config)
            session.commit()
            
        logger.info("✅ Security configuration created")
        
    async def _setup_admin_user(self):
        """Create initial admin user"""
        logger.info("Setting up admin user...")
        
        with self.session_factory() as session:
            auth_manager = AuthenticationManager(session, self.vault_manager)
            
            # Check if admin user already exists
            existing_admin = session.query(User).filter(User.username == "admin").first()
            if existing_admin:
                logger.info("Admin user already exists")
                return existing_admin
                
            # Create admin user
            admin_user = User(
                username="admin",
                email="admin@dafelhub.com",
                first_name="System",
                last_name="Administrator",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                last_login=None
            )
            
            # Set secure password
            admin_password = "DafelHub2024!Admin"  # Change in production!
            admin_user.password_hash = auth_manager.hash_password(admin_password)
            
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            
            logger.info(f"✅ Admin user created with ID: {admin_user.id}")
            logger.warning(f"🔐 Admin credentials: admin / {admin_password}")
            logger.warning("⚠️ CHANGE ADMIN PASSWORD IN PRODUCTION!")
            
            return admin_user
            
    async def _setup_rbac_system(self):
        """Setup Role-Based Access Control system"""
        logger.info("Setting up RBAC system...")
        
        with self.session_factory() as session:
            rbac_manager = RBACManager(session)
            
            # Create all security roles
            roles_to_create = [
                SecurityRole.ADMIN,
                SecurityRole.SECURITY_ADMIN,
                SecurityRole.EDITOR,
                SecurityRole.AUDITOR,
                SecurityRole.VIEWER
            ]
            
            for role in roles_to_create:
                existing_role = session.query(UserRole).filter(
                    UserRole.name == role.value
                ).first()
                
                if not existing_role:
                    user_role = UserRole(
                        name=role.value,
                        description=f"{role.value.title()} role with appropriate permissions",
                        created_at=datetime.utcnow()
                    )
                    session.add(user_role)
                    
            session.commit()
            
            # Create permissions for each role
            await self._setup_role_permissions(session)
            
            # Assign admin role to admin user
            admin_user = session.query(User).filter(User.username == "admin").first()
            if admin_user:
                rbac_manager.assign_role(admin_user.id, SecurityRole.ADMIN, admin_user.id)
                
        logger.info("✅ RBAC system configured")
        
    async def _setup_role_permissions(self, session):
        """Setup permissions for each role"""
        logger.info("Setting up role permissions...")
        
        # Define permission mappings for each role
        role_permissions = {
            SecurityRole.ADMIN.value: [p for p in Permission],
            SecurityRole.SECURITY_ADMIN.value: [
                Permission.USER_READ, Permission.USER_CREATE, Permission.USER_UPDATE,
                Permission.ROLE_READ, Permission.ROLE_CREATE, Permission.ROLE_UPDATE,
                Permission.AUDIT_READ, Permission.SECURITY_READ, Permission.SECURITY_WRITE,
                Permission.CONNECTION_READ, Permission.CONNECTION_CREATE, Permission.CONNECTION_UPDATE,
            ],
            SecurityRole.EDITOR.value: [
                Permission.USER_READ, Permission.PROJECT_READ, Permission.PROJECT_CREATE, 
                Permission.PROJECT_UPDATE, Permission.CONNECTION_READ, Permission.CONNECTION_CREATE,
                Permission.STUDIO_READ, Permission.STUDIO_EXECUTE,
            ],
            SecurityRole.AUDITOR.value: [
                Permission.USER_READ, Permission.AUDIT_READ, Permission.PROJECT_READ,
                Permission.CONNECTION_READ, Permission.SECURITY_READ,
            ],
            SecurityRole.VIEWER.value: [
                Permission.USER_READ, Permission.PROJECT_READ, Permission.CONNECTION_READ,
            ]
        }
        
        # Create role permissions
        for role_name, permissions in role_permissions.items():
            role = session.query(UserRole).filter(UserRole.name == role_name).first()
            if not role:
                continue
                
            for permission in permissions:
                existing_permission = session.query(RolePermission).filter(
                    RolePermission.role_id == role.id,
                    RolePermission.permission == permission.value
                ).first()
                
                if not existing_permission:
                    role_permission = RolePermission(
                        role_id=role.id,
                        permission=permission.value,
                        granted_by=1,  # System/Admin
                        granted_at=datetime.utcnow()
                    )
                    session.add(role_permission)
                    
        session.commit()
        logger.info("✅ Role permissions configured")
        
    async def _create_demo_data(self):
        """Create demo data for testing"""
        logger.info("Creating demo data...")
        
        with self.session_factory() as session:
            # Create demo users
            demo_users = [
                {
                    "username": "developer",
                    "email": "developer@dafelhub.com",
                    "first_name": "Demo",
                    "last_name": "Developer",
                    "role": SecurityRole.EDITOR
                },
                {
                    "username": "analyst",
                    "email": "analyst@dafelhub.com", 
                    "first_name": "Demo",
                    "last_name": "Analyst",
                    "role": SecurityRole.VIEWER
                },
                {
                    "username": "auditor",
                    "email": "auditor@dafelhub.com",
                    "first_name": "Demo", 
                    "last_name": "Auditor",
                    "role": SecurityRole.AUDITOR
                }
            ]
            
            auth_manager = AuthenticationManager(session, self.vault_manager)
            rbac_manager = RBACManager(session)
            
            for user_data in demo_users:
                # Check if user already exists
                existing_user = session.query(User).filter(
                    User.username == user_data["username"]
                ).first()
                
                if existing_user:
                    continue
                    
                # Create user
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    is_active=True,
                    is_verified=True,
                    created_at=datetime.utcnow()
                )
                
                # Set password
                password = f"{user_data['username']}123!"
                user.password_hash = auth_manager.hash_password(password)
                
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Assign role
                rbac_manager.assign_role(user.id, user_data["role"], 1)
                
                logger.info(f"✅ Demo user created: {user.username} / {password}")
                
        logger.info("✅ Demo data created")
        
    async def _validate_database(self):
        """Validate database integrity"""
        logger.info("Validating database integrity...")
        
        with self.session_factory() as session:
            # Check critical tables have data
            checks = [
                ("users", session.query(User).count()),
                ("user_roles", session.query(UserRole).count()),
                ("role_permissions", session.query(RolePermission).count()),
                ("security_configurations", session.query(SecurityConfiguration).count()),
            ]
            
            all_checks_passed = True
            for table_name, count in checks:
                if count == 0:
                    logger.error(f"❌ Table {table_name} is empty!")
                    all_checks_passed = False
                else:
                    logger.info(f"✅ Table {table_name}: {count} records")
                    
            if not all_checks_passed:
                raise Exception("Database validation failed")
                
        logger.info("✅ Database validation completed")
        
    def cleanup(self):
        """Cleanup database connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("✅ Database connections closed")


async def main():
    """Main initialization function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize DafelHub database")
    parser.add_argument("--force-recreate", action="store_true", 
                       help="Drop and recreate all tables")
    parser.add_argument("--no-demo-data", action="store_true",
                       help="Skip creating demo data")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize database
    initializer = DatabaseInitializer()
    
    try:
        success = await initializer.initialize(
            create_demo_data=not args.no_demo_data,
            force_recreate=args.force_recreate
        )
        
        if success:
            logger.info("🎉 DafelHub database initialization successful!")
            
            # Print summary
            print("\n" + "="*60)
            print("🚀 DAFELHUB DATABASE INITIALIZATION COMPLETE")
            print("="*60)
            print(f"📊 Database URL: {settings.DATABASE_URL}")
            print(f"🔐 Admin User: admin / DafelHub2024!Admin")
            print(f"🔗 API URL: http://{settings.API_HOST}:{settings.API_PORT}")
            print(f"📚 API Docs: http://{settings.API_HOST}:{settings.API_PORT}/docs")
            print("="*60)
            print("⚠️  REMEMBER TO CHANGE DEFAULT PASSWORDS IN PRODUCTION!")
            print("="*60)
            
            return 0
        else:
            logger.error("💥 Database initialization failed!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Initialization error: {e}", exc_info=True)
        return 1
        
    finally:
        initializer.cleanup()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))