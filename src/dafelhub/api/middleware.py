"""
DafelHub Enterprise API Middleware
JWT Authentication, RBAC Authorization, Request Logging, Rate Limiting
"""

import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from dafelhub.core.logging import get_logger
from dafelhub.security.jwt_manager import JWTManager
from dafelhub.security.rbac import RBACSystem
from dafelhub.security.audit import AuditTrail

logger = get_logger(__name__)

# Initialize security components
jwt_manager = JWTManager()
rbac_system = RBACSystem()
audit_trail = AuditTrail()
security = HTTPBearer()


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """JWT Authentication Middleware"""
    
    def __init__(self, app, exclude_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/info",
            "/api/v1/auth/login",
            "/api/v1/auth/register"
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process JWT authentication"""
        path = request.url.path
        
        # Skip authentication for excluded paths
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        try:
            # Extract token from Authorization header
            authorization: str = request.headers.get("Authorization")
            if not authorization:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": True,
                        "message": "Authentication required",
                        "code": "MISSING_TOKEN"
                    }
                )
            
            # Validate Bearer format
            if not authorization.startswith("Bearer "):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": True,
                        "message": "Invalid authentication format",
                        "code": "INVALID_TOKEN_FORMAT"
                    }
                )
            
            token = authorization.split(" ")[1]
            
            # Validate JWT token
            try:
                payload = jwt_manager.verify_token(token)
                
                # Add user info to request state
                request.state.user_id = payload.get("user_id")
                request.state.username = payload.get("username")
                request.state.roles = payload.get("roles", [])
                request.state.permissions = payload.get("permissions", [])
                request.state.token_payload = payload
                
                logger.info(
                    f"User authenticated: {payload.get('username')}",
                    extra={
                        "user_id": payload.get("user_id"),
                        "username": payload.get("username"),
                        "roles": payload.get("roles"),
                        "path": path
                    }
                )
                
            except jwt_manager.InvalidTokenError as e:
                logger.warning(f"Invalid token: {str(e)}", extra={"path": path})
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": True,
                        "message": "Invalid or expired token",
                        "code": "INVALID_TOKEN"
                    }
                )
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": True,
                    "message": "Authentication service error",
                    "code": "AUTH_SERVICE_ERROR"
                }
            )
        
        response = await call_next(request)
        return response


class RBACAuthorizationMiddleware(BaseHTTPMiddleware):
    """RBAC Authorization Middleware"""
    
    def __init__(self, app, route_permissions: Optional[Dict[str, str]] = None):
        super().__init__(app)
        self.route_permissions = route_permissions or {
            # Admin routes require admin role
            "/api/v1/admin": "admin",
            # Studio routes require user role minimum
            "/api/v1/studio": "user",
            # Project routes require user role minimum
            "/api/v1/projects": "user",
            # Connection routes require user role minimum
            "/api/v1/connections": "user",
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process RBAC authorization"""
        path = request.url.path
        
        # Skip if no user authenticated (handled by auth middleware)
        if not hasattr(request.state, 'user_id'):
            return await call_next(request)
        
        try:
            user_id = request.state.user_id
            user_roles = request.state.roles
            
            # Check route-specific permissions
            required_permission = None
            for route_pattern, permission in self.route_permissions.items():
                if path.startswith(route_pattern):
                    required_permission = permission
                    break
            
            if required_permission:
                # Check if user has required permission through roles
                has_permission = rbac_system.check_permission(
                    user_id=user_id,
                    resource=path,
                    action=request.method.lower(),
                    user_roles=user_roles
                )
                
                if not has_permission:
                    logger.warning(
                        f"Access denied for user {user_id} to {path}",
                        extra={
                            "user_id": user_id,
                            "username": request.state.username,
                            "roles": user_roles,
                            "required_permission": required_permission,
                            "path": path,
                            "method": request.method
                        }
                    )
                    
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": True,
                            "message": "Insufficient permissions",
                            "code": "PERMISSION_DENIED",
                            "required_permission": required_permission
                        }
                    )
                
                logger.debug(
                    f"Access granted for user {user_id} to {path}",
                    extra={
                        "user_id": user_id,
                        "username": request.state.username,
                        "roles": user_roles,
                        "path": path,
                        "method": request.method
                    }
                )
            
        except Exception as e:
            logger.error(f"Authorization error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": True,
                    "message": "Authorization service error",
                    "code": "AUTHZ_SERVICE_ERROR"
                }
            )
        
        response = await call_next(request)
        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Audit Trail and Request Logging Middleware"""
    
    def __init__(self, app, log_body: bool = False):
        super().__init__(app)
        self.log_body = log_body
    
    async def dispatch(self, request: Request, call_next):
        """Log requests for audit trail"""
        start_time = time.time()
        
        # Prepare audit data
        audit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "user_id": getattr(request.state, 'user_id', None),
            "username": getattr(request.state, 'username', 'anonymous'),
        }
        
        # Log request body for sensitive operations (optional)
        if self.log_body and request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                body = await request.body()
                if body:
                    # Don't log sensitive data like passwords
                    if "password" not in request.url.path.lower():
                        audit_data["request_body"] = body.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not read request body: {str(e)}")
        
        try:
            response = await call_next(request)
            
            # Complete audit data
            process_time = time.time() - start_time
            audit_data.update({
                "status_code": response.status_code,
                "process_time": process_time,
                "success": 200 <= response.status_code < 400
            })
            
            # Log to audit trail
            await audit_trail.log_request(audit_data)
            
            # Add audit headers
            response.headers["X-Request-ID"] = audit_data.get("request_id", "unknown")
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Log error
            audit_data.update({
                "status_code": 500,
                "error": str(e),
                "process_time": time.time() - start_time,
                "success": False
            })
            
            await audit_trail.log_request(audit_data)
            raise


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate Limiting Middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, List[float]] = {}
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting per client IP"""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old requests (older than 1 minute)
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                req_time for req_time in self.request_counts[client_ip]
                if current_time - req_time < 60
            ]
        else:
            self.request_counts[client_ip] = []
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for IP: {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "requests_count": len(self.request_counts[client_ip]),
                    "limit": self.requests_per_minute,
                    "path": request.url.path
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": True,
                    "message": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": 60
                }
            )
        
        # Add request to tracking
        self.request_counts[client_ip].append(current_time)
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.request_counts[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + 60))
        
        return response


# Dependency for extracting current user
async def get_current_user(request: Request) -> Dict[str, Any]:
    """Extract current user from request state"""
    if not hasattr(request.state, 'user_id'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return {
        "user_id": request.state.user_id,
        "username": request.state.username,
        "roles": request.state.roles,
        "permissions": request.state.permissions,
        "token_payload": request.state.token_payload
    }


# Dependency for extracting current admin user
async def get_current_admin_user(request: Request) -> Dict[str, Any]:
    """Extract current admin user from request state"""
    current_user = await get_current_user(request)
    
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


# Export middleware classes and dependencies
__all__ = [
    "JWTAuthenticationMiddleware",
    "RBACAuthorizationMiddleware", 
    "AuditLoggingMiddleware",
    "RateLimitingMiddleware",
    "get_current_user",
    "get_current_admin_user",
]