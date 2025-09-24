"""
DafelHub Data Sources / Connections Routes
6 endpoints: GET connections, POST connections, GET connections/{id}, PUT connections/{id}, DELETE connections/{id}, POST connections/{id}/test
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path

from dafelhub.core.logging import get_logger
from dafelhub.database.connection_manager import ConnectionManager
from dafelhub.database.connectors.connection_factory import ConnectionFactory
from dafelhub.database.health_monitor import HealthMonitor
from dafelhub.security.audit import AuditTrail
from dafelhub.api.middleware import get_current_user
from dafelhub.api.models.requests import (
    CreateConnectionRequest,
    UpdateConnectionRequest,
    TestConnectionRequest,
    PaginationRequest
)
from dafelhub.api.models.responses import (
    ConnectionsListResponse,
    CreateConnectionResponse,
    UpdateConnectionResponse,
    ConnectionResponse,
    TestConnectionResponse,
    PaginatedResponse,
    BaseResponse
)

# Initialize components
logger = get_logger(__name__)
router = APIRouter()
connection_manager = ConnectionManager()
connection_factory = ConnectionFactory()
health_monitor = HealthMonitor()
audit_trail = AuditTrail()


@router.get(
    "",
    response_model=ConnectionsListResponse,
    summary="List Database Connections",
    description="Get paginated list of database connections"
)
async def get_connections(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    type: Optional[str] = Query(None, description="Filter by connection type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ConnectionsListResponse:
    """
    Get all database connections with pagination and filtering
    - Returns user's accessible connections
    - Supports search and filtering
    - Includes connection status
    """
    try:
        user_id = current_user["user_id"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {current_user['username']} requesting connections list",
            extra={
                "user_id": user_id,
                "page": page,
                "limit": limit,
                "filters": {"type": type, "status": status, "search": search}
            }
        )
        
        # Build query filters
        filters = {"created_by": user_id}  # Users can only see their own connections
        
        # Admin can see all connections
        if "admin" in user_roles:
            filters.pop("created_by")
        
        if type:
            filters["type"] = type
        if status:
            filters["status"] = status
        if tags:
            filters["tags"] = tags.split(",")
        
        # Get connections from database
        connections_result = await connection_manager.get_connections_paginated(
            page=page,
            limit=limit,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        if not connections_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving connections"
            )
        
        # Convert to connection responses
        connection_responses = []
        for conn in connections_result.connections:
            # Get connection status
            conn_status = await health_monitor.get_connection_status(conn.id)
            
            connection_response = ConnectionResponse(
                id=str(conn.id),
                name=conn.name,
                type=conn.type,
                host=conn.host,
                port=conn.port,
                database=conn.database,
                username=conn.username,
                description=conn.description,
                ssl_enabled=conn.ssl_enabled,
                tags=conn.tags or [],
                status=conn_status.get("status", "unknown"),
                last_tested=conn.last_tested,
                created_by=str(conn.created_by),
                created_at=conn.created_at,
                updated_at=conn.updated_at
            )
            connection_responses.append(connection_response)
        
        # Create pagination info
        total_pages = (connections_result.total + limit - 1) // limit
        pagination = PaginatedResponse(
            items=connection_responses,
            total=connections_result.total,
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
            action="list_connections",
            details={
                "total_connections": connections_result.total,
                "filters_applied": filters
            }
        )
        
        logger.info(
            f"Connections list retrieved successfully",
            extra={
                "user_id": user_id,
                "total_connections": connections_result.total,
                "page": page
            }
        )
        
        return ConnectionsListResponse(
            success=True,
            message=f"Retrieved {len(connection_responses)} connections",
            connections=connection_responses,
            pagination=pagination
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get connections error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving connections"
        )


@router.post(
    "",
    response_model=CreateConnectionResponse,
    summary="Create Database Connection",
    description="Create a new database connection"
)
async def create_connection(
    request: CreateConnectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> CreateConnectionResponse:
    """
    Create new database connection
    - Tests connection before saving
    - Encrypts sensitive data
    - Validates connection parameters
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        
        logger.info(
            f"User {username} creating connection: {request.name}",
            extra={
                "user_id": user_id,
                "connection_name": request.name,
                "connection_type": request.type,
                "host": request.host
            }
        )
        
        # Test connection before creating
        try:
            connector = await connection_factory.create_connector(
                db_type=request.type,
                host=request.host,
                port=request.port,
                database=request.database,
                username=request.username,
                password=request.password,
                ssl_enabled=request.ssl_enabled,
                connection_options=request.connection_options or {}
            )
            
            # Test the connection
            test_result = await connector.test_connection()
            if not test_result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Connection test failed: {test_result.get('error', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.warning(f"Connection test failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection test failed: {str(e)}"
            )
        
        # Create connection in database
        connection_data = {
            "name": request.name,
            "type": request.type,
            "host": request.host,
            "port": request.port,
            "database": request.database,
            "username": request.username,
            "password": request.password,  # Will be encrypted by connection manager
            "description": request.description,
            "ssl_enabled": request.ssl_enabled,
            "connection_options": request.connection_options or {},
            "tags": request.tags or [],
            "created_by": user_id
        }
        
        create_result = await connection_manager.create_connection(connection_data)
        
        if not create_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_result.message
            )
        
        connection = create_result.connection
        
        # Create connection response
        connection_response = ConnectionResponse(
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
            status="active",  # Just tested successfully
            last_tested=datetime.utcnow(),
            created_by=str(connection.created_by),
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="create_connection",
            target_resource_id=str(connection.id),
            details={
                "connection_name": connection.name,
                "connection_type": connection.type,
                "host": connection.host,
                "database": connection.database
            }
        )
        
        logger.info(
            f"Connection {connection.name} created successfully",
            extra={
                "user_id": user_id,
                "connection_id": str(connection.id),
                "connection_name": connection.name
            }
        )
        
        return CreateConnectionResponse(
            success=True,
            message=f"Connection {connection.name} created successfully",
            connection=connection_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create connection error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating connection"
        )


@router.get(
    "/{connection_id}",
    response_model=ConnectionResponse,
    summary="Get Connection Details",
    description="Get detailed information about a specific connection"
)
async def get_connection(
    connection_id: str = Path(..., description="Connection ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ConnectionResponse:
    """
    Get connection details by ID
    - Returns full connection information
    - Checks user permissions
    - Excludes sensitive data for non-owners
    """
    try:
        user_id = current_user["user_id"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {current_user['username']} requesting connection: {connection_id}",
            extra={"user_id": user_id, "connection_id": connection_id}
        )
        
        # Get connection from database
        connection = await connection_manager.get_connection_by_id(connection_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check permissions (users can only see their own connections, admins can see all)
        if connection.created_by != user_id and "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this connection"
            )
        
        # Get current connection status
        conn_status = await health_monitor.get_connection_status(connection.id)
        
        # Create connection response
        connection_response = ConnectionResponse(
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
            status=conn_status.get("status", "unknown"),
            last_tested=connection.last_tested,
            created_by=str(connection.created_by),
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=current_user["username"],
            action="view_connection",
            target_resource_id=connection_id,
            details={"connection_name": connection.name}
        )
        
        logger.info(
            f"Connection details retrieved successfully",
            extra={
                "user_id": user_id,
                "connection_id": connection_id,
                "connection_name": connection.name
            }
        )
        
        return connection_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get connection error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving connection"
        )


@router.put(
    "/{connection_id}",
    response_model=UpdateConnectionResponse,
    summary="Update Connection",
    description="Update existing database connection"
)
async def update_connection(
    connection_id: str = Path(..., description="Connection ID"),
    request: UpdateConnectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> UpdateConnectionResponse:
    """
    Update database connection
    - Tests connection if credentials changed
    - Updates configuration
    - Logs all changes
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {username} updating connection: {connection_id}",
            extra={
                "user_id": user_id,
                "connection_id": connection_id,
                "update_fields": list(request.dict(exclude_unset=True).keys())
            }
        )
        
        # Get existing connection
        existing_connection = await connection_manager.get_connection_by_id(connection_id)
        
        if not existing_connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check permissions
        if existing_connection.created_by != user_id and "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this connection"
            )
        
        # Prepare update data
        update_data = request.dict(exclude_unset=True)
        
        # Test connection if credentials or connection parameters changed
        if any(field in update_data for field in ["host", "port", "database", "username", "password", "ssl_enabled"]):
            try:
                # Merge current data with updates for testing
                test_config = {
                    "host": update_data.get("host", existing_connection.host),
                    "port": update_data.get("port", existing_connection.port),
                    "database": update_data.get("database", existing_connection.database),
                    "username": update_data.get("username", existing_connection.username),
                    "password": update_data.get("password", existing_connection.password),
                    "ssl_enabled": update_data.get("ssl_enabled", existing_connection.ssl_enabled),
                }
                
                connector = await connection_factory.create_connector(
                    db_type=existing_connection.type,
                    **test_config
                )
                
                test_result = await connector.test_connection()
                if not test_result["success"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Connection test failed: {test_result.get('error', 'Unknown error')}"
                    )
                    
            except Exception as e:
                logger.warning(f"Connection test failed during update: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Connection test failed: {str(e)}"
                )
        
        # Update connection
        update_result = await connection_manager.update_connection(
            connection_id=connection_id,
            update_data=update_data,
            updated_by=user_id
        )
        
        if not update_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=update_result.message
            )
        
        connection = update_result.connection
        
        # Get updated connection status
        conn_status = await health_monitor.get_connection_status(connection.id)
        
        # Create connection response
        connection_response = ConnectionResponse(
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
            status=conn_status.get("status", "unknown"),
            last_tested=connection.last_tested,
            created_by=str(connection.created_by),
            created_at=connection.created_at,
            updated_at=connection.updated_at
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="update_connection",
            target_resource_id=connection_id,
            details={
                "connection_name": connection.name,
                "updated_fields": list(update_data.keys()),
                "changes": update_data
            }
        )
        
        logger.info(
            f"Connection {connection.name} updated successfully",
            extra={
                "user_id": user_id,
                "connection_id": connection_id,
                "updated_fields": list(update_data.keys())
            }
        )
        
        return UpdateConnectionResponse(
            success=True,
            message=f"Connection {connection.name} updated successfully",
            connection=connection_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update connection error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating connection"
        )


@router.delete(
    "/{connection_id}",
    response_model=BaseResponse,
    summary="Delete Connection",
    description="Delete database connection"
)
async def delete_connection(
    connection_id: str = Path(..., description="Connection ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> BaseResponse:
    """
    Delete database connection
    - Checks for dependent projects
    - Soft delete with cleanup
    - Logs deletion
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {username} deleting connection: {connection_id}",
            extra={"user_id": user_id, "connection_id": connection_id}
        )
        
        # Get existing connection
        existing_connection = await connection_manager.get_connection_by_id(connection_id)
        
        if not existing_connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check permissions
        if existing_connection.created_by != user_id and "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this connection"
            )
        
        # Check for dependent projects
        dependencies = await connection_manager.check_connection_dependencies(connection_id)
        if dependencies.get("has_dependencies", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete connection. It is used by {dependencies.get('projects_count', 0)} projects"
            )
        
        # Delete connection
        delete_result = await connection_manager.delete_connection(
            connection_id=connection_id,
            deleted_by=user_id
        )
        
        if not delete_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=delete_result.message
            )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="delete_connection",
            target_resource_id=connection_id,
            details={
                "connection_name": existing_connection.name,
                "connection_type": existing_connection.type
            }
        )
        
        logger.info(
            f"Connection {existing_connection.name} deleted successfully",
            extra={
                "user_id": user_id,
                "connection_id": connection_id,
                "connection_name": existing_connection.name
            }
        )
        
        return BaseResponse(
            success=True,
            message=f"Connection {existing_connection.name} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete connection error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting connection"
        )


@router.post(
    "/{connection_id}/test",
    response_model=TestConnectionResponse,
    summary="Test Connection",
    description="Test database connection"
)
async def test_connection(
    connection_id: str = Path(..., description="Connection ID"),
    request: TestConnectionRequest = TestConnectionRequest(),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> TestConnectionResponse:
    """
    Test database connection
    - Validates connectivity
    - Runs health checks
    - Returns performance metrics
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {username} testing connection: {connection_id}",
            extra={"user_id": user_id, "connection_id": connection_id}
        )
        
        # Get connection from database
        connection = await connection_manager.get_connection_by_id(connection_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check permissions
        if connection.created_by != user_id and "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this connection"
            )
        
        # Test connection
        start_time = datetime.utcnow()
        
        try:
            connector = await connection_factory.create_connector(
                db_type=connection.type,
                host=connection.host,
                port=connection.port,
                database=connection.database,
                username=connection.username,
                password=connection.password,
                ssl_enabled=connection.ssl_enabled,
                timeout=request.timeout
            )
            
            test_result = await connector.test_connection(
                include_health_checks=request.run_health_checks
            )
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000  # milliseconds
            
            # Update last tested timestamp
            await connection_manager.update_last_tested(connection_id)
            
            # Update connection status in health monitor
            await health_monitor.update_connection_status(
                connection_id,
                "active" if test_result["success"] else "error",
                test_result.get("error")
            )
            
            # Prepare health checks result
            health_checks = {}
            if request.run_health_checks and test_result.get("health_checks"):
                health_checks = test_result["health_checks"]
            
            test_response = TestConnectionResponse(
                success=test_result["success"],
                message="Connection test completed",
                connection_id=connection_id,
                status="success" if test_result["success"] else "failed",
                response_time=response_time,
                database_version=test_result.get("database_version"),
                health_checks=health_checks,
                tested_at=datetime.utcnow(),
                error_message=test_result.get("error") if not test_result["success"] else None
            )
            
        except asyncio.TimeoutError:
            response_time = request.timeout * 1000
            test_response = TestConnectionResponse(
                success=False,
                message="Connection test timed out",
                connection_id=connection_id,
                status="timeout",
                response_time=response_time,
                health_checks={},
                tested_at=datetime.utcnow(),
                error_message=f"Connection timed out after {request.timeout} seconds"
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            test_response = TestConnectionResponse(
                success=False,
                message="Connection test failed",
                connection_id=connection_id,
                status="failed",
                response_time=response_time,
                health_checks={},
                tested_at=datetime.utcnow(),
                error_message=str(e)
            )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="test_connection",
            target_resource_id=connection_id,
            details={
                "connection_name": connection.name,
                "test_result": test_response.status,
                "response_time": test_response.response_time,
                "run_health_checks": request.run_health_checks
            }
        )
        
        logger.info(
            f"Connection test completed",
            extra={
                "user_id": user_id,
                "connection_id": connection_id,
                "test_result": test_response.status,
                "response_time": test_response.response_time
            }
        )
        
        return test_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test connection error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error testing connection"
        )