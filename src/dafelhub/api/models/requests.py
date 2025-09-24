"""
DafelHub API Request Models
Pydantic models for all API endpoint requests
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, validator


# =============================================================================
# AUTHENTICATION MODELS
# =============================================================================

class LoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., min_length=3, max_length=50, description="Username or email")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    remember_me: Optional[bool] = Field(default=False, description="Keep user logged in")
    mfa_code: Optional[str] = Field(default=None, min_length=6, max_length=6, description="MFA code if enabled")

    @validator('username')
    def validate_username(cls, v):
        if not v or v.isspace():
            raise ValueError('Username cannot be empty')
        return v.strip().lower()


class RegisterRequest(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    confirm_password: str = Field(..., min_length=8, max_length=100, description="Password confirmation")
    full_name: str = Field(..., min_length=2, max_length=100, description="User full name")
    company: Optional[str] = Field(default=None, max_length=100, description="Company name")
    phone: Optional[str] = Field(default=None, max_length=20, description="Phone number")

    @validator('confirm_password')
    def validate_password_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

    @validator('username')
    def validate_username(cls, v):
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username must contain only alphanumeric characters and underscores')
        return v.lower()


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="Valid refresh token")


class LogoutRequest(BaseModel):
    """User logout request"""
    all_devices: Optional[bool] = Field(default=False, description="Logout from all devices")


# =============================================================================
# ADMIN PANEL MODELS
# =============================================================================

class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    ANALYST = "analyst"


class CreateUserRequest(BaseModel):
    """Admin create user request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = Field(default=UserRole.USER)
    company: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = Field(default=True)
    permissions: Optional[List[str]] = Field(default_factory=list)


class UpdateUserRequest(BaseModel):
    """Admin update user request"""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    company: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = Field(default=None)
    permissions: Optional[List[str]] = Field(default=None)


class UpdateUserRoleRequest(BaseModel):
    """Update user role request"""
    role: UserRole = Field(..., description="New user role")
    reason: Optional[str] = Field(default=None, max_length=500, description="Reason for role change")


# =============================================================================
# DATA SOURCES / CONNECTIONS MODELS
# =============================================================================

class ConnectionType(str, Enum):
    """Database connection types"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"


class CreateConnectionRequest(BaseModel):
    """Create database connection request"""
    name: str = Field(..., min_length=3, max_length=100, description="Connection name")
    type: ConnectionType = Field(..., description="Database type")
    host: str = Field(..., min_length=1, max_length=255, description="Database host")
    port: int = Field(..., ge=1, le=65535, description="Database port")
    database: str = Field(..., min_length=1, max_length=100, description="Database name")
    username: str = Field(..., min_length=1, max_length=100, description="Database username")
    password: str = Field(..., min_length=1, max_length=255, description="Database password")
    description: Optional[str] = Field(default=None, max_length=500, description="Connection description")
    ssl_enabled: Optional[bool] = Field(default=False, description="Enable SSL connection")
    connection_options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional options")
    tags: Optional[List[str]] = Field(default_factory=list, description="Connection tags")


class UpdateConnectionRequest(BaseModel):
    """Update database connection request"""
    name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    database: Optional[str] = Field(default=None, min_length=1, max_length=100)
    username: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    ssl_enabled: Optional[bool] = Field(default=None)
    connection_options: Optional[Dict[str, Any]] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)


class TestConnectionRequest(BaseModel):
    """Test database connection request"""
    timeout: Optional[int] = Field(default=30, ge=5, le=300, description="Connection timeout in seconds")
    run_health_checks: Optional[bool] = Field(default=True, description="Run additional health checks")


# =============================================================================
# PROJECTS MODELS
# =============================================================================

class ProjectType(str, Enum):
    """Project type enumeration"""
    WEB_APPLICATION = "web_application"
    MOBILE_APP = "mobile_app"
    API_SERVICE = "api_service"
    DATA_PIPELINE = "data_pipeline"
    MACHINE_LEARNING = "machine_learning"
    MICROSERVICE = "microservice"
    FRONTEND = "frontend"
    BACKEND = "backend"


class ProjectStatus(str, Enum):
    """Project status enumeration"""
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    DEPLOYED = "deployed"
    MAINTENANCE = "maintenance"
    ARCHIVED = "archived"


class CreateProjectRequest(BaseModel):
    """Create project request"""
    name: str = Field(..., min_length=3, max_length=100, description="Project name")
    description: str = Field(..., min_length=10, max_length=1000, description="Project description")
    type: ProjectType = Field(..., description="Project type")
    status: Optional[ProjectStatus] = Field(default=ProjectStatus.PLANNING, description="Project status")
    tech_stack: List[str] = Field(..., min_items=1, description="Technologies used")
    repository_url: Optional[str] = Field(default=None, description="Git repository URL")
    deployment_url: Optional[str] = Field(default=None, description="Deployment URL")
    database_connections: Optional[List[str]] = Field(default_factory=list, description="Database connection IDs")
    team_members: Optional[List[str]] = Field(default_factory=list, description="Team member user IDs")
    tags: Optional[List[str]] = Field(default_factory=list, description="Project tags")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @validator('repository_url')
    def validate_repository_url(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Repository URL must be a valid HTTP/HTTPS URL')
        return v


# =============================================================================
# STUDIO MODELS
# =============================================================================

class CanvasElementType(str, Enum):
    """Canvas element types"""
    DATABASE = "database"
    API = "api"
    SERVICE = "service"
    FRONTEND = "frontend"
    QUEUE = "queue"
    CACHE = "cache"
    STORAGE = "storage"


class CanvasElement(BaseModel):
    """Canvas element model"""
    id: str = Field(..., description="Element ID")
    type: CanvasElementType = Field(..., description="Element type")
    name: str = Field(..., min_length=1, max_length=100, description="Element name")
    position: Dict[str, float] = Field(..., description="Element position (x, y)")
    size: Optional[Dict[str, float]] = Field(default=None, description="Element size (width, height)")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Element properties")
    connections: Optional[List[str]] = Field(default_factory=list, description="Connected element IDs")


class SaveCanvasRequest(BaseModel):
    """Save canvas request"""
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., min_length=3, max_length=100, description="Canvas name")
    elements: List[CanvasElement] = Field(..., description="Canvas elements")
    connections: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Element connections")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Canvas metadata")


class ExecuteCodeRequest(BaseModel):
    """Execute code in studio request"""
    project_id: str = Field(..., description="Project ID")
    code: str = Field(..., min_length=1, description="Code to execute")
    language: str = Field(..., description="Programming language")
    environment: Optional[str] = Field(default="default", description="Execution environment")
    timeout: Optional[int] = Field(default=30, ge=5, le=300, description="Execution timeout")
    input_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Input data for code")


# =============================================================================
# COMMON MODELS
# =============================================================================

class PaginationRequest(BaseModel):
    """Pagination request model"""
    page: Optional[int] = Field(default=1, ge=1, description="Page number")
    limit: Optional[int] = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: Optional[str] = Field(default="asc", regex="^(asc|desc)$", description="Sort order")


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., min_length=1, max_length=100, description="Search query")
    fields: Optional[List[str]] = Field(default=None, description="Fields to search in")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Search filters")


class BulkOperationRequest(BaseModel):
    """Bulk operation request"""
    operation: str = Field(..., description="Operation type (create, update, delete)")
    items: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100, description="Items to process")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Operation options")


# Export all models
__all__ = [
    # Authentication
    "LoginRequest",
    "RegisterRequest", 
    "RefreshTokenRequest",
    "LogoutRequest",
    
    # Admin
    "UserRole",
    "CreateUserRequest",
    "UpdateUserRequest",
    "UpdateUserRoleRequest",
    
    # Connections
    "ConnectionType",
    "CreateConnectionRequest",
    "UpdateConnectionRequest",
    "TestConnectionRequest",
    
    # Projects
    "ProjectType",
    "ProjectStatus",
    "CreateProjectRequest",
    
    # Studio
    "CanvasElementType",
    "CanvasElement",
    "SaveCanvasRequest",
    "ExecuteCodeRequest",
    
    # Common
    "PaginationRequest",
    "SearchRequest",
    "BulkOperationRequest",
]