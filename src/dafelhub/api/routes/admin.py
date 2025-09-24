"""
DafelHub Admin Panel Routes
6 endpoints: GET users, POST users, PUT users/{id}, DELETE users/{id}, PUT users/{id}/role, GET audit
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from dafelhub.core.logging import get_logger
from dafelhub.security.authentication import AuthenticationManager
from dafelhub.security.rbac import RBACSystem
from dafelhub.security.audit import AuditTrail
from dafelhub.database.models.user import User
from dafelhub.database.connection_manager import get_db
from dafelhub.api.middleware import get_current_admin_user
from dafelhub.api.models.requests import (
    CreateUserRequest,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    PaginationRequest
)
from dafelhub.api.models.responses import (
    AdminUsersListResponse,
    CreateUserResponse,
    UpdateUserResponse,
    AdminUserResponse,
    AuditLogResponse,
    AuditLogEntry,
    PaginatedResponse,
    BaseResponse
)

# Initialize components
logger = get_logger(__name__)
router = APIRouter()
auth_manager = AuthenticationManager()
rbac_system = RBACSystem()
audit_trail = AuditTrail()


@router.get(
    "/users",
    response_model=AdminUsersListResponse,
    summary="List All Users",
    description="Get paginated list of all users (admin only)"
)
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username, email, or full name"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status (active/inactive)"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_admin: Dict[str, Any] = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> AdminUsersListResponse:
    """
    Get all users with pagination and filtering
    - Admin only endpoint
    - Supports search and filtering
    - Returns user statistics
    """
    try:
        logger.info(
            f"Admin {current_admin['username']} requesting users list",
            extra={
                "admin_id": current_admin["user_id"],
                "page": page,
                "limit": limit,
                "search": search,
                "filters": {"role": role, "status": status}
            }
        )
        
        # Build query filters
        filters = {}
        if role:
            filters["role"] = role
        if status == "active":
            filters["is_active"] = True
        elif status == "inactive":
            filters["is_active"] = False
        
        # Get users from database
        users_result = await auth_manager.get_users_paginated(
            page=page,
            limit=limit,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        if not users_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving users"
            )
        
        # Convert to admin user responses
        admin_users = []
        for user in users_result.users:
            # Get additional user statistics
            user_stats = await auth_manager.get_user_statistics(user.id)
            
            admin_user = AdminUserResponse(
                user_id=str(user.id),
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role or "user",
                company=user.company,
                phone=user.phone,
                is_active=user.is_active,
                is_verified=user.is_verified,
                permissions=user.permissions or [],
                last_login=user.last_login,
                login_count=user_stats.get("login_count", 0),
                projects_count=user_stats.get("projects_count", 0),
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            admin_users.append(admin_user)
        
        # Create pagination info
        total_pages = (users_result.total + limit - 1) // limit
        pagination = PaginatedResponse(
            items=admin_users,
            total=users_result.total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
        # Log admin activity
        await audit_trail.log_admin_activity(
            admin_id=current_admin["user_id"],
            admin_username=current_admin["username"],
            action="list_users",
            details={
                "total_users": users_result.total,
                "filters_applied": filters,
                "search_query": search
            }
        )
        
        logger.info(
            f"Users list retrieved successfully",
            extra={
                "admin_id": current_admin["user_id"],
                "total_users": users_result.total,
                "page": page
            }
        )
        
        return AdminUsersListResponse(
            success=True,
            message=f"Retrieved {len(admin_users)} users",
            users=admin_users,
            pagination=pagination
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get users error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving users"
        )


@router.post(
    "/users",
    response_model=CreateUserResponse,
    summary="Create New User",
    description="Create a new user account (admin only)"
)
async def create_user(
    request: CreateUserRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
) -> CreateUserResponse:
    """
    Create new user account
    - Admin only endpoint
    - Sets role and permissions
    - Sends welcome email
    """
    try:
        logger.info(
            f"Admin {current_admin['username']} creating user: {request.username}",
            extra={
                "admin_id": current_admin["user_id"],
                "new_username": request.username,
                "new_email": request.email,
                "role": request.role
            }
        )
        
        # Create user account
        user_result = await auth_manager.create_user_by_admin(
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role,
            company=request.company,
            phone=request.phone,
            is_active=request.is_active,
            permissions=request.permissions,
            created_by=current_admin["user_id"]
        )
        
        if not user_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=user_result.message
            )
        
        user = user_result.user
        
        # Create admin user response
        admin_user = AdminUserResponse(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role or "user",
            company=user.company,
            phone=user.phone,
            is_active=user.is_active,
            is_verified=user.is_verified,
            permissions=user.permissions or [],
            last_login=None,
            login_count=0,
            projects_count=0,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        # Log admin activity
        await audit_trail.log_admin_activity(
            admin_id=current_admin["user_id"],
            admin_username=current_admin["username"],
            action="create_user",
            target_user_id=str(user.id),
            details={
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active
            }
        )
        
        logger.info(
            f"User {user.username} created successfully by admin",
            extra={
                "admin_id": current_admin["user_id"],
                "new_user_id": str(user.id),
                "username": user.username
            }
        )
        
        return CreateUserResponse(
            success=True,
            message=f"User {user.username} created successfully",
            user=admin_user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create user error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )


@router.put(
    "/users/{user_id}",
    response_model=UpdateUserResponse,
    summary="Update User",
    description="Update existing user details (admin only)"
)
async def update_user(
    user_id: str = Path(..., description="User ID to update"),
    request: UpdateUserRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
) -> UpdateUserResponse:
    """
    Update user account details
    - Admin only endpoint
    - Updates user information
    - Logs all changes
    """
    try:
        logger.info(
            f"Admin {current_admin['username']} updating user: {user_id}",
            extra={
                "admin_id": current_admin["user_id"],
                "target_user_id": user_id,
                "update_fields": list(request.dict(exclude_unset=True).keys())
            }
        )
        
        # Get existing user
        existing_user = await auth_manager.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent admins from deactivating themselves
        if user_id == current_admin["user_id"] and request.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )
        
        # Update user
        update_data = request.dict(exclude_unset=True)
        user_result = await auth_manager.update_user_by_admin(
            user_id=user_id,
            update_data=update_data,
            updated_by=current_admin["user_id"]
        )
        
        if not user_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=user_result.message
            )
        
        user = user_result.user
        user_stats = await auth_manager.get_user_statistics(user.id)
        
        # Create admin user response
        admin_user = AdminUserResponse(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role or "user",
            company=user.company,
            phone=user.phone,
            is_active=user.is_active,
            is_verified=user.is_verified,
            permissions=user.permissions or [],
            last_login=user.last_login,
            login_count=user_stats.get("login_count", 0),
            projects_count=user_stats.get("projects_count", 0),
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        # Log admin activity
        await audit_trail.log_admin_activity(
            admin_id=current_admin["user_id"],
            admin_username=current_admin["username"],
            action="update_user",
            target_user_id=user_id,
            details={
                "updated_fields": list(update_data.keys()),
                "changes": update_data
            }
        )
        
        logger.info(
            f"User {user.username} updated successfully",
            extra={
                "admin_id": current_admin["user_id"],
                "user_id": user_id,
                "updated_fields": list(update_data.keys())
            }
        )
        
        return UpdateUserResponse(
            success=True,
            message=f"User {user.username} updated successfully",
            user=admin_user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )


@router.delete(
    "/users/{user_id}",
    response_model=BaseResponse,
    summary="Delete User",
    description="Delete user account (admin only)"
)
async def delete_user(
    user_id: str = Path(..., description="User ID to delete"),
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
) -> BaseResponse:
    """
    Delete user account
    - Admin only endpoint
    - Soft delete with data retention
    - Cannot delete own account
    """
    try:
        logger.info(
            f"Admin {current_admin['username']} deleting user: {user_id}",
            extra={
                "admin_id": current_admin["user_id"],
                "target_user_id": user_id
            }
        )
        
        # Prevent admins from deleting themselves
        if user_id == current_admin["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        # Get existing user
        existing_user = await auth_manager.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Delete user (soft delete)
        delete_result = await auth_manager.delete_user_by_admin(
            user_id=user_id,
            deleted_by=current_admin["user_id"]
        )
        
        if not delete_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=delete_result.message
            )
        
        # Log admin activity
        await audit_trail.log_admin_activity(
            admin_id=current_admin["user_id"],
            admin_username=current_admin["username"],
            action="delete_user",
            target_user_id=user_id,
            details={
                "deleted_username": existing_user.username,
                "deleted_email": existing_user.email
            }
        )
        
        logger.info(
            f"User {existing_user.username} deleted successfully",
            extra={
                "admin_id": current_admin["user_id"],
                "deleted_user_id": user_id,
                "deleted_username": existing_user.username
            }
        )
        
        return BaseResponse(
            success=True,
            message=f"User {existing_user.username} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user"
        )


@router.put(
    "/users/{user_id}/role",
    response_model=UpdateUserResponse,
    summary="Update User Role",
    description="Update user role and permissions (admin only)"
)
async def update_user_role(
    user_id: str = Path(..., description="User ID to update"),
    request: UpdateUserRoleRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
) -> UpdateUserResponse:
    """
    Update user role
    - Admin only endpoint
    - Updates role and associated permissions
    - Cannot change own role
    """
    try:
        logger.info(
            f"Admin {current_admin['username']} updating role for user: {user_id}",
            extra={
                "admin_id": current_admin["user_id"],
                "target_user_id": user_id,
                "new_role": request.role
            }
        )
        
        # Prevent admins from changing their own role
        if user_id == current_admin["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role"
            )
        
        # Get existing user
        existing_user = await auth_manager.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        old_role = existing_user.role
        
        # Update user role
        role_result = await rbac_system.update_user_role(
            user_id=user_id,
            new_role=request.role,
            reason=request.reason,
            changed_by=current_admin["user_id"]
        )
        
        if not role_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=role_result.message
            )
        
        # Get updated user
        updated_user = await auth_manager.get_user_by_id(user_id)
        user_stats = await auth_manager.get_user_statistics(user_id)
        
        # Create admin user response
        admin_user = AdminUserResponse(
            user_id=str(updated_user.id),
            username=updated_user.username,
            email=updated_user.email,
            full_name=updated_user.full_name,
            role=updated_user.role or "user",
            company=updated_user.company,
            phone=updated_user.phone,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            permissions=updated_user.permissions or [],
            last_login=updated_user.last_login,
            login_count=user_stats.get("login_count", 0),
            projects_count=user_stats.get("projects_count", 0),
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at
        )
        
        # Log admin activity
        await audit_trail.log_admin_activity(
            admin_id=current_admin["user_id"],
            admin_username=current_admin["username"],
            action="update_user_role",
            target_user_id=user_id,
            details={
                "old_role": old_role,
                "new_role": request.role,
                "reason": request.reason
            }
        )
        
        logger.info(
            f"User role updated successfully",
            extra={
                "admin_id": current_admin["user_id"],
                "user_id": user_id,
                "old_role": old_role,
                "new_role": request.role
            }
        )
        
        return UpdateUserResponse(
            success=True,
            message=f"User role updated from {old_role} to {request.role}",
            user=admin_user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user role error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user role"
        )


@router.get(
    "/audit",
    response_model=AuditLogResponse,
    summary="Audit Logs",
    description="Get system audit logs (admin only)"
)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
) -> AuditLogResponse:
    """
    Get audit logs
    - Admin only endpoint
    - Supports filtering and pagination
    - Returns system activity logs
    """
    try:
        logger.info(
            f"Admin {current_admin['username']} requesting audit logs",
            extra={
                "admin_id": current_admin["user_id"],
                "filters": {
                    "user_id": user_id,
                    "action": action,
                    "resource": resource,
                    "date_range": f"{date_from} - {date_to}" if date_from or date_to else None
                }
            }
        )
        
        # Build filters
        filters = {}
        if user_id:
            filters["user_id"] = user_id
        if action:
            filters["action"] = action
        if resource:
            filters["resource"] = resource
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to
        
        # Get audit logs
        logs_result = await audit_trail.get_audit_logs(
            page=page,
            limit=limit,
            filters=filters
        )
        
        if not logs_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving audit logs"
            )
        
        # Convert to audit log entries
        audit_entries = []
        for log in logs_result.logs:
            entry = AuditLogEntry(
                id=str(log.id),
                timestamp=log.timestamp,
                user_id=log.user_id,
                username=log.username,
                action=log.action,
                resource=log.resource,
                details=log.details or {},
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                status=log.status
            )
            audit_entries.append(entry)
        
        # Create pagination info
        total_pages = (logs_result.total + limit - 1) // limit
        pagination = PaginatedResponse(
            items=audit_entries,
            total=logs_result.total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
        # Log admin activity
        await audit_trail.log_admin_activity(
            admin_id=current_admin["user_id"],
            admin_username=current_admin["username"],
            action="view_audit_logs",
            details={
                "filters_applied": filters,
                "total_logs": logs_result.total
            }
        )
        
        logger.info(
            f"Audit logs retrieved successfully",
            extra={
                "admin_id": current_admin["user_id"],
                "total_logs": logs_result.total,
                "page": page
            }
        )
        
        return AuditLogResponse(
            success=True,
            message=f"Retrieved {len(audit_entries)} audit log entries",
            logs=audit_entries,
            pagination=pagination
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get audit logs error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs"
        )