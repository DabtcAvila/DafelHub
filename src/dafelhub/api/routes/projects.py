"""
DafelHub Projects Routes
3 endpoints: GET projects, POST projects, GET projects/{id}
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path

from dafelhub.core.logging import get_logger
from dafelhub.services.project_manager import ProjectManager
from dafelhub.database.connection_manager import ConnectionManager
from dafelhub.security.audit import AuditTrail
from dafelhub.api.middleware import get_current_user
from dafelhub.api.models.requests import (
    CreateProjectRequest,
    PaginationRequest
)
from dafelhub.api.models.responses import (
    ProjectsListResponse,
    CreateProjectResponse,
    ProjectDetailsResponse,
    ProjectResponse,
    ConnectionResponse,
    UserProfile,
    PaginatedResponse
)

# Initialize components
logger = get_logger(__name__)
router = APIRouter()
project_manager = ProjectManager()
connection_manager = ConnectionManager()
audit_trail = AuditTrail()


@router.get(
    "",
    response_model=ProjectsListResponse,
    summary="List Projects",
    description="Get paginated list of projects"
)
async def get_projects(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    type: Optional[str] = Query(None, description="Filter by project type"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    tech_stack: Optional[str] = Query(None, description="Filter by technology (comma-separated)"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ProjectsListResponse:
    """
    Get all projects with pagination and filtering
    - Returns user's accessible projects
    - Supports comprehensive search and filtering
    - Includes project statistics
    """
    try:
        user_id = current_user["user_id"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {current_user['username']} requesting projects list",
            extra={
                "user_id": user_id,
                "page": page,
                "limit": limit,
                "filters": {
                    "type": type,
                    "status": status,
                    "search": search,
                    "tech_stack": tech_stack,
                    "tags": tags
                }
            }
        )
        
        # Build query filters
        filters = {}
        
        # Users can see projects they created or are team members of
        if "admin" not in user_roles:
            filters["user_access"] = user_id
        
        if type:
            filters["type"] = type
        if status:
            filters["status"] = status
        if tech_stack:
            filters["tech_stack"] = tech_stack.split(",")
        if tags:
            filters["tags"] = tags.split(",")
        
        # Get projects from database
        projects_result = await project_manager.get_projects_paginated(
            page=page,
            limit=limit,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            user_id=user_id
        )
        
        if not projects_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving projects"
            )
        
        # Convert to project responses
        project_responses = []
        for project in projects_result.projects:
            project_response = ProjectResponse(
                id=str(project.id),
                name=project.name,
                description=project.description,
                type=project.type,
                status=project.status,
                tech_stack=project.tech_stack or [],
                repository_url=project.repository_url,
                deployment_url=project.deployment_url,
                database_connections=project.database_connections or [],
                team_members=project.team_members or [],
                tags=project.tags or [],
                metadata=project.metadata or {},
                created_by=str(project.created_by),
                created_at=project.created_at,
                updated_at=project.updated_at
            )
            project_responses.append(project_response)
        
        # Create pagination info
        total_pages = (projects_result.total + limit - 1) // limit
        pagination = PaginatedResponse(
            items=project_responses,
            total=projects_result.total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=current_user["username"],
            action="list_projects",
            details={
                "total_projects": projects_result.total,
                "filters_applied": filters,
                "search_query": search
            }
        )
        
        logger.info(
            f"Projects list retrieved successfully",
            extra={
                "user_id": user_id,
                "total_projects": projects_result.total,
                "page": page
            }
        )
        
        return ProjectsListResponse(
            success=True,
            message=f"Retrieved {len(project_responses)} projects",
            projects=project_responses,
            pagination=pagination
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get projects error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving projects"
        )


@router.post(
    "",
    response_model=CreateProjectResponse,
    summary="Create Project",
    description="Create a new project"
)
async def create_project(
    request: CreateProjectRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> CreateProjectResponse:
    """
    Create new project
    - Validates database connections
    - Sets up project structure
    - Assigns project owner and team
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        
        logger.info(
            f"User {username} creating project: {request.name}",
            extra={
                "user_id": user_id,
                "project_name": request.name,
                "project_type": request.type,
                "tech_stack": request.tech_stack
            }
        )
        
        # Validate database connections if provided
        if request.database_connections:
            for conn_id in request.database_connections:
                connection = await connection_manager.get_connection_by_id(conn_id)
                if not connection:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Database connection {conn_id} not found"
                    )
                
                # Check if user has access to the connection
                if connection.created_by != user_id and "admin" not in current_user["roles"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Access denied to database connection {conn_id}"
                    )
        
        # Prepare project data
        project_data = {
            "name": request.name,
            "description": request.description,
            "type": request.type,
            "status": request.status,
            "tech_stack": request.tech_stack,
            "repository_url": request.repository_url,
            "deployment_url": request.deployment_url,
            "database_connections": request.database_connections or [],
            "team_members": request.team_members or [],
            "tags": request.tags or [],
            "metadata": request.metadata or {},
            "created_by": user_id
        }
        
        # Add creator to team members if not already included
        if user_id not in project_data["team_members"]:
            project_data["team_members"].insert(0, user_id)
        
        # Create project
        create_result = await project_manager.create_project(project_data)
        
        if not create_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_result.message
            )
        
        project = create_result.project
        
        # Create project response
        project_response = ProjectResponse(
            id=str(project.id),
            name=project.name,
            description=project.description,
            type=project.type,
            status=project.status,
            tech_stack=project.tech_stack or [],
            repository_url=project.repository_url,
            deployment_url=project.deployment_url,
            database_connections=project.database_connections or [],
            team_members=project.team_members or [],
            tags=project.tags or [],
            metadata=project.metadata or {},
            created_by=str(project.created_by),
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
        # Initialize project workspace and resources
        await project_manager.initialize_project_workspace(
            project_id=str(project.id),
            created_by=user_id
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="create_project",
            target_resource_id=str(project.id),
            details={
                "project_name": project.name,
                "project_type": project.type,
                "tech_stack": project.tech_stack,
                "team_members_count": len(project.team_members or []),
                "database_connections_count": len(project.database_connections or [])
            }
        )
        
        logger.info(
            f"Project {project.name} created successfully",
            extra={
                "user_id": user_id,
                "project_id": str(project.id),
                "project_name": project.name
            }
        )
        
        return CreateProjectResponse(
            success=True,
            message=f"Project {project.name} created successfully",
            project=project_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create project error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating project"
        )


@router.get(
    "/{project_id}",
    response_model=ProjectDetailsResponse,
    summary="Get Project Details",
    description="Get detailed information about a specific project"
)
async def get_project(
    project_id: str = Path(..., description="Project ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ProjectDetailsResponse:
    """
    Get project details by ID
    - Returns full project information
    - Includes associated connections and team details
    - Shows recent project activity
    """
    try:
        user_id = current_user["user_id"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {current_user['username']} requesting project: {project_id}",
            extra={"user_id": user_id, "project_id": project_id}
        )
        
        # Get project from database
        project = await project_manager.get_project_by_id(project_id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check permissions (project owner, team member, or admin)
        has_access = (
            project.created_by == user_id or
            user_id in (project.team_members or []) or
            "admin" in user_roles
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project"
            )
        
        # Get associated database connections
        connections = []
        if project.database_connections:
            for conn_id in project.database_connections:
                connection = await connection_manager.get_connection_by_id(conn_id)
                if connection:
                    conn_response = ConnectionResponse(
                        id=str(connection.id),
                        name=connection.name,
                        type=connection.type,
                        host=connection.host,
                        port=connection.port,
                        database=connection.database,
                        username=connection.username,
                        description=connection.description,
                        ssl_enabled=connection.ssl_enabled,
                        tags=connection.tags or [],
                        status="unknown",  # Would need health check
                        last_tested=connection.last_tested,
                        created_by=str(connection.created_by),
                        created_at=connection.created_at,
                        updated_at=connection.updated_at
                    )
                    connections.append(conn_response)
        
        # Get team members details
        team_members_details = []
        if project.team_members:
            for member_id in project.team_members:
                # This would require integration with user management
                # For now, creating basic profile
                member_profile = UserProfile(
                    user_id=member_id,
                    username=f"user_{member_id}",
                    email=f"user_{member_id}@example.com",
                    full_name=f"User {member_id}",
                    roles=["user"],
                    permissions=[],
                    is_active=True,
                    is_verified=True,
                    mfa_enabled=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                team_members_details.append(member_profile)
        
        # Get recent project activity
        recent_activity = await project_manager.get_project_activity(
            project_id=project_id,
            limit=10
        )
        
        # Get project statistics
        statistics = await project_manager.get_project_statistics(project_id)
        
        # Create project response
        project_response = ProjectResponse(
            id=str(project.id),
            name=project.name,
            description=project.description,
            type=project.type,
            status=project.status,
            tech_stack=project.tech_stack or [],
            repository_url=project.repository_url,
            deployment_url=project.deployment_url,
            database_connections=project.database_connections or [],
            team_members=project.team_members or [],
            tags=project.tags or [],
            metadata=project.metadata or {},
            created_by=str(project.created_by),
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=current_user["username"],
            action="view_project",
            target_resource_id=project_id,
            details={
                "project_name": project.name,
                "project_type": project.type
            }
        )
        
        logger.info(
            f"Project details retrieved successfully",
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "project_name": project.name
            }
        )
        
        return ProjectDetailsResponse(
            success=True,
            message=f"Project {project.name} details retrieved successfully",
            project=project_response,
            connections=connections,
            team_members_details=team_members_details,
            recent_activity=recent_activity.get("activities", []),
            statistics=statistics.get("stats", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving project"
        )