"""
DafelHub Authentication Routes
5 endpoints: login, refresh, logout, register, me
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer

from dafelhub.core.logging import get_logger
from dafelhub.security.authentication import AuthenticationManager
from dafelhub.security.jwt_manager import JWTManager
from dafelhub.security.mfa_system import MFASystem
from dafelhub.security.audit import AuditTrail
from dafelhub.database.models.user import User
from dafelhub.api.middleware import get_current_user
from dafelhub.api.models.requests import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    LogoutRequest
)
from dafelhub.api.models.responses import (
    LoginResponse,
    RefreshResponse,
    LogoutResponse,
    TokenResponse,
    UserProfile,
    BaseResponse,
    ErrorResponse
)

# Initialize components
logger = get_logger(__name__)
router = APIRouter()
auth_manager = AuthenticationManager()
jwt_manager = JWTManager()
mfa_system = MFASystem()
audit_trail = AuditTrail()
security = HTTPBearer(auto_error=False)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User Login",
    description="Authenticate user with username/email and password. Supports MFA."
)
async def login(
    request: LoginRequest,
    http_request: Request
) -> LoginResponse:
    """
    User login endpoint
    - Validates credentials
    - Handles MFA if enabled
    - Returns JWT tokens and user profile
    """
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        logger.info(
            f"Login attempt for user: {request.username}",
            extra={
                "username": request.username,
                "client_ip": client_ip,
                "user_agent": user_agent
            }
        )
        
        # Authenticate user
        auth_result = await auth_manager.authenticate_user(
            username=request.username,
            password=request.password,
            mfa_code=request.mfa_code
        )
        
        if not auth_result.success:
            # Log failed attempt
            await audit_trail.log_auth_attempt(
                username=request.username,
                success=False,
                reason=auth_result.message,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result.message
            )
        
        user = auth_result.user
        
        # Check if MFA is required but not provided
        if user.mfa_enabled and not request.mfa_code:
            return LoginResponse(
                success=True,
                message="MFA code required",
                requires_mfa=True,
                mfa_methods=["totp", "sms"],  # Available MFA methods
                access_token="",
                refresh_token="",
                expires_in=0,
                user=UserProfile(
                    user_id=str(user.id),
                    username=user.username,
                    email=user.email,
                    full_name=user.full_name,
                    roles=[],
                    permissions=[],
                    is_active=user.is_active,
                    is_verified=user.is_verified,
                    mfa_enabled=user.mfa_enabled,
                    created_at=user.created_at,
                    updated_at=user.updated_at
                )
            )
        
        # Generate JWT tokens
        token_data = {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "roles": user.roles,
            "permissions": user.permissions
        }
        
        access_token = jwt_manager.create_access_token(token_data)
        refresh_token = jwt_manager.create_refresh_token(token_data)
        
        # Update last login
        await auth_manager.update_last_login(user.id, client_ip)
        
        # Log successful login
        await audit_trail.log_auth_attempt(
            username=request.username,
            success=True,
            user_id=str(user.id),
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # Create user profile response
        user_profile = UserProfile(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            roles=user.roles,
            permissions=user.permissions,
            company=user.company,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_verified=user.is_verified,
            mfa_enabled=user.mfa_enabled,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        logger.info(
            f"User {user.username} logged in successfully",
            extra={
                "user_id": str(user.id),
                "username": user.username,
                "client_ip": client_ip
            }
        )
        
        return LoginResponse(
            success=True,
            message="Login successful",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=jwt_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile,
            requires_mfa=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Refresh Token",
    description="Refresh access token using refresh token"
)
async def refresh_token(request: RefreshTokenRequest) -> RefreshResponse:
    """
    Refresh token endpoint
    - Validates refresh token
    - Issues new access token
    """
    try:
        # Verify refresh token
        payload = jwt_manager.verify_refresh_token(request.refresh_token)
        
        # Generate new access token
        token_data = {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", [])
        }
        
        new_access_token = jwt_manager.create_access_token(token_data)
        
        logger.info(
            f"Token refreshed for user: {payload.get('username')}",
            extra={"user_id": payload.get("user_id")}
        )
        
        return RefreshResponse(
            success=True,
            message="Token refreshed successfully",
            access_token=new_access_token,
            expires_in=jwt_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except jwt_manager.InvalidTokenError as e:
        logger.warning(f"Invalid refresh token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token service error"
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="User Logout",
    description="Logout user and invalidate tokens"
)
async def logout(
    request: LogoutRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    http_request: Request = None
) -> LogoutResponse:
    """
    User logout endpoint
    - Invalidates current tokens
    - Optional: logout from all devices
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        
        # Get token from request
        authorization = http_request.headers.get("Authorization", "")
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else ""
        
        # Invalidate tokens
        devices_count = await auth_manager.logout_user(
            user_id=user_id,
            token=token,
            all_devices=request.all_devices
        )
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        
        # Log logout
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="logout",
            details={
                "all_devices": request.all_devices,
                "devices_count": devices_count
            },
            client_ip=client_ip
        )
        
        logger.info(
            f"User {username} logged out",
            extra={
                "user_id": user_id,
                "all_devices": request.all_devices,
                "devices_count": devices_count
            }
        )
        
        return LogoutResponse(
            success=True,
            message="Logout successful",
            logged_out_devices=devices_count
        )
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout service error"
        )


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="User Registration",
    description="Register new user account"
)
async def register(
    request: RegisterRequest,
    http_request: Request
) -> TokenResponse:
    """
    User registration endpoint
    - Creates new user account
    - Validates unique username/email
    - Returns JWT tokens and user profile
    """
    try:
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        logger.info(
            f"Registration attempt for user: {request.username}",
            extra={
                "username": request.username,
                "email": request.email,
                "client_ip": client_ip
            }
        )
        
        # Create user account
        user_result = await auth_manager.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            company=request.company,
            phone=request.phone
        )
        
        if not user_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=user_result.message
            )
        
        user = user_result.user
        
        # Generate JWT tokens
        token_data = {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "roles": user.roles or ["user"],
            "permissions": user.permissions or []
        }
        
        access_token = jwt_manager.create_access_token(token_data)
        refresh_token = jwt_manager.create_refresh_token(token_data)
        
        # Update last login for new user
        await auth_manager.update_last_login(user.id, client_ip)
        
        # Log successful registration
        await audit_trail.log_user_activity(
            user_id=str(user.id),
            username=user.username,
            action="register",
            details={"email": user.email},
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # Create user profile response
        user_profile = UserProfile(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            roles=user.roles or ["user"],
            permissions=user.permissions or [],
            company=user.company,
            phone=user.phone,
            is_active=user.is_active,
            is_verified=False,  # New users need email verification
            mfa_enabled=False,
            last_login=datetime.utcnow(),
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        logger.info(
            f"User {user.username} registered successfully",
            extra={
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email
            }
        )
        
        return TokenResponse(
            success=True,
            message="Registration successful",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=jwt_manager.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration service error"
        )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Current User Profile",
    description="Get current authenticated user profile"
)
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> UserProfile:
    """
    Get current user profile endpoint
    - Returns authenticated user's profile
    - Includes roles and permissions
    """
    try:
        user_id = current_user["user_id"]
        
        # Get full user profile from database
        user = await auth_manager.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.debug(
            f"Profile requested for user: {user.username}",
            extra={"user_id": user_id}
        )
        
        return UserProfile(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            roles=user.roles,
            permissions=user.permissions,
            company=user.company,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_verified=user.is_verified,
            mfa_enabled=user.mfa_enabled,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile service error"
        )