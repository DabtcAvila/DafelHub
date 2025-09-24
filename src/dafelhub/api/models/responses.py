"""
DafelHub API Response Models
Pydantic models for all API endpoint responses
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from pydantic import BaseModel, Field


# =============================================================================
# COMMON RESPONSE MODELS
# =============================================================================

class BaseResponse(BaseModel):
    """Base response model"""
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = Field(default=False)
    error_code: Optional[str] = Field(default=None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")


class PaginatedResponse(BaseModel):
    """Paginated response model"""
    items: List[Any] = Field(..., description="Response items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Has next page")
    has_previous: bool = Field(..., description="Has previous page")


# =============================================================================
# AUTHENTICATION RESPONSE MODELS
# =============================================================================

class TokenResponse(BaseResponse):
    """Token response model"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: "UserProfile" = Field(..., description="User profile information")


class UserProfile(BaseModel):
    """User profile model"""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    roles: List[str] = Field(..., description="User roles")
    permissions: List[str] = Field(..., description="User permissions")
    company: Optional[str] = Field(default=None, description="Company name")
    phone: Optional[str] = Field(default=None, description="Phone number")
    avatar_url: Optional[str] = Field(default=None, description="Avatar URL")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Email verification status")
    mfa_enabled: bool = Field(..., description="MFA enabled status")
    last_login: Optional[datetime] = Field(default=None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Account update timestamp")


class LoginResponse(TokenResponse):
    """Login response model"""
    requires_mfa: Optional[bool] = Field(default=False, description="MFA required")
    mfa_methods: Optional[List[str]] = Field(default=None, description="Available MFA methods")


class RefreshResponse(BaseResponse):
    """Refresh token response model"""
    access_token: str = Field(..., description="New JWT access token")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class LogoutResponse(BaseResponse):
    """Logout response model"""
    logged_out_devices: int = Field(..., description="Number of devices logged out")


# =============================================================================
# ADMIN PANEL RESPONSE MODELS
# =============================================================================

class AdminUserResponse(BaseModel):
    """Admin user response model"""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    role: str = Field(..., description="User role")
    company: Optional[str] = Field(default=None, description="Company name")
    phone: Optional[str] = Field(default=None, description="Phone number")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Email verification status")
    permissions: List[str] = Field(..., description="User permissions")
    last_login: Optional[datetime] = Field(default=None, description="Last login timestamp")
    login_count: int = Field(..., description="Total login count")
    projects_count: int = Field(..., description="Number of projects")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Account update timestamp")


class AdminUsersListResponse(BaseResponse):
    """Admin users list response"""
    users: List[AdminUserResponse] = Field(..., description="Users list")
    pagination: PaginatedResponse = Field(..., description="Pagination info")


class CreateUserResponse(BaseResponse):
    """Create user response model"""
    user: AdminUserResponse = Field(..., description="Created user")


class UpdateUserResponse(BaseResponse):
    """Update user response model"""
    user: AdminUserResponse = Field(..., description="Updated user")


class AuditLogEntry(BaseModel):
    """Audit log entry model"""
    id: str = Field(..., description="Log entry ID")
    timestamp: datetime = Field(..., description="Event timestamp")
    user_id: Optional[str] = Field(default=None, description="User ID")
    username: Optional[str] = Field(default=None, description="Username")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    details: Dict[str, Any] = Field(..., description="Additional details")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent")
    status: str = Field(..., description="Operation status")


class AuditLogResponse(BaseResponse):
    """Audit log response model"""
    logs: List[AuditLogEntry] = Field(..., description="Audit log entries")
    pagination: PaginatedResponse = Field(..., description="Pagination info")


# =============================================================================
# DATA SOURCES / CONNECTIONS RESPONSE MODELS
# =============================================================================

class ConnectionResponse(BaseModel):
    """Database connection response model"""
    id: str = Field(..., description="Connection ID")
    name: str = Field(..., description="Connection name")
    type: str = Field(..., description="Database type")
    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    description: Optional[str] = Field(default=None, description="Connection description")
    ssl_enabled: bool = Field(..., description="SSL enabled status")
    tags: List[str] = Field(..., description="Connection tags")
    status: str = Field(..., description="Connection status")
    last_tested: Optional[datetime] = Field(default=None, description="Last test timestamp")
    created_by: str = Field(..., description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class ConnectionsListResponse(BaseResponse):
    """Connections list response"""
    connections: List[ConnectionResponse] = Field(..., description="Connections list")
    pagination: PaginatedResponse = Field(..., description="Pagination info")


class CreateConnectionResponse(BaseResponse):
    """Create connection response model"""
    connection: ConnectionResponse = Field(..., description="Created connection")


class UpdateConnectionResponse(BaseResponse):
    """Update connection response model"""
    connection: ConnectionResponse = Field(..., description="Updated connection")


class TestConnectionResponse(BaseResponse):
    """Test connection response model"""
    connection_id: str = Field(..., description="Connection ID")
    status: str = Field(..., description="Test status (success/failed)")
    response_time: float = Field(..., description="Connection response time in milliseconds")
    database_version: Optional[str] = Field(default=None, description="Database version")
    health_checks: Dict[str, Any] = Field(..., description="Health check results")
    tested_at: datetime = Field(..., description="Test timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")


# =============================================================================
# PROJECTS RESPONSE MODELS
# =============================================================================

class ProjectResponse(BaseModel):
    """Project response model"""
    id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Project description")
    type: str = Field(..., description="Project type")
    status: str = Field(..., description="Project status")
    tech_stack: List[str] = Field(..., description="Technologies used")
    repository_url: Optional[str] = Field(default=None, description="Git repository URL")
    deployment_url: Optional[str] = Field(default=None, description="Deployment URL")
    database_connections: List[str] = Field(..., description="Database connection IDs")
    team_members: List[str] = Field(..., description="Team member user IDs")
    tags: List[str] = Field(..., description="Project tags")
    metadata: Dict[str, Any] = Field(..., description="Additional metadata")
    created_by: str = Field(..., description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class ProjectsListResponse(BaseResponse):
    """Projects list response"""
    projects: List[ProjectResponse] = Field(..., description="Projects list")
    pagination: PaginatedResponse = Field(..., description="Pagination info")


class CreateProjectResponse(BaseResponse):
    """Create project response model"""
    project: ProjectResponse = Field(..., description="Created project")


class ProjectDetailsResponse(BaseResponse):
    """Project details response model"""
    project: ProjectResponse = Field(..., description="Project details")
    connections: List[ConnectionResponse] = Field(..., description="Associated connections")
    team_members_details: List[UserProfile] = Field(..., description="Team members details")
    recent_activity: List[Dict[str, Any]] = Field(..., description="Recent project activity")
    statistics: Dict[str, Any] = Field(..., description="Project statistics")


# =============================================================================
# STUDIO RESPONSE MODELS
# =============================================================================

class CanvasElementResponse(BaseModel):
    """Canvas element response model"""
    id: str = Field(..., description="Element ID")
    type: str = Field(..., description="Element type")
    name: str = Field(..., description="Element name")
    position: Dict[str, float] = Field(..., description="Element position")
    size: Dict[str, float] = Field(..., description="Element size")
    properties: Dict[str, Any] = Field(..., description="Element properties")
    connections: List[str] = Field(..., description="Connected element IDs")


class CanvasResponse(BaseModel):
    """Canvas response model"""
    id: str = Field(..., description="Canvas ID")
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Canvas name")
    elements: List[CanvasElementResponse] = Field(..., description="Canvas elements")
    connections: List[Dict[str, Any]] = Field(..., description="Element connections")
    metadata: Dict[str, Any] = Field(..., description="Canvas metadata")
    created_by: str = Field(..., description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class StudioCanvasResponse(BaseResponse):
    """Studio canvas response model"""
    canvas: CanvasResponse = Field(..., description="Canvas data")


class CodeExecutionResult(BaseModel):
    """Code execution result model"""
    execution_id: str = Field(..., description="Execution ID")
    status: str = Field(..., description="Execution status")
    output: str = Field(..., description="Execution output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    memory_used: Optional[int] = Field(default=None, description="Memory used in bytes")
    executed_at: datetime = Field(..., description="Execution timestamp")


class ExecuteCodeResponse(BaseResponse):
    """Execute code response model"""
    result: CodeExecutionResult = Field(..., description="Execution result")


class StudioMetrics(BaseModel):
    """Studio metrics model"""
    total_executions: int = Field(..., description="Total code executions")
    successful_executions: int = Field(..., description="Successful executions")
    failed_executions: int = Field(..., description="Failed executions")
    average_execution_time: float = Field(..., description="Average execution time")
    total_execution_time: float = Field(..., description="Total execution time")
    languages_used: Dict[str, int] = Field(..., description="Languages usage statistics")
    recent_executions: List[CodeExecutionResult] = Field(..., description="Recent executions")


class StudioMetricsResponse(BaseResponse):
    """Studio metrics response model"""
    project_id: str = Field(..., description="Project ID")
    metrics: StudioMetrics = Field(..., description="Studio metrics")
    period: str = Field(..., description="Metrics period")
    generated_at: datetime = Field(..., description="Metrics generation timestamp")


# =============================================================================
# HEALTH AND SYSTEM RESPONSE MODELS
# =============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Environment name")
    uptime: float = Field(..., description="Service uptime in seconds")
    checks: Dict[str, Dict[str, Any]] = Field(..., description="Individual health checks")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")


# Update forward references
TokenResponse.model_rebuild()

# Export all models
__all__ = [
    # Common
    "BaseResponse",
    "ErrorResponse",
    "PaginatedResponse",
    
    # Authentication
    "TokenResponse",
    "UserProfile",
    "LoginResponse",
    "RefreshResponse",
    "LogoutResponse",
    
    # Admin
    "AdminUserResponse",
    "AdminUsersListResponse",
    "CreateUserResponse",
    "UpdateUserResponse",
    "AuditLogEntry",
    "AuditLogResponse",
    
    # Connections
    "ConnectionResponse",
    "ConnectionsListResponse",
    "CreateConnectionResponse",
    "UpdateConnectionResponse",
    "TestConnectionResponse",
    
    # Projects
    "ProjectResponse",
    "ProjectsListResponse",
    "CreateProjectResponse",
    "ProjectDetailsResponse",
    
    # Studio
    "CanvasElementResponse",
    "CanvasResponse",
    "StudioCanvasResponse",
    "CodeExecutionResult",
    "ExecuteCodeResponse",
    "StudioMetrics",
    "StudioMetricsResponse",
    
    # Health
    "HealthCheckResponse",
]