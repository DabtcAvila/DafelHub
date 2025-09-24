"""
DafelHub Security System - API Implementation Example
Demonstrates complete JWT + 2FA + RBAC integration
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from flask import Flask, request, jsonify, make_response
from functools import wraps
from werkzeug.exceptions import HTTPException

from sqlalchemy.orm import Session

from dafelhub.database.connection import get_db_session
from dafelhub.database.models import User
from .authentication import AuthenticationManager, SecurityContext
from .jwt_manager import JWTManager as EnterpriseJWTManager, JWTSecurityError
from .rbac_system import RBACManager, Permission, get_rbac_manager, AccessDeniedError
from .mfa_system import MFASystemManager, get_mfa_manager
from .models import SecurityRole


# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'


# Security middleware
def require_auth(f):
    """Authentication middleware decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            with get_db_session() as db:
                jwt_manager = EnterpriseJWTManager(db)
                claims = jwt_manager.verify_token(token)
                
                # Validate session context
                if not jwt_manager.validate_session_context(
                    claims, 
                    request.remote_addr, 
                    request.headers.get('User-Agent', ''),
                    strict_validation=False  # Less strict for demo
                ):
                    return jsonify({'error': 'Invalid session context'}), 401
                
                # Create security context (in production, store in thread-local or request context)
                request.security_context = SecurityContext(
                    user_id=uuid.UUID(claims.user_id),
                    username=claims.username,
                    email=claims.email,
                    role=SecurityRole(claims.role),
                    session_id=uuid.UUID(claims.session_id),
                    ip_address=claims.ip_address,
                    user_agent=request.headers.get('User-Agent', ''),
                    two_factor_verified=claims.two_factor_verified,
                    permissions=claims.permissions
                )
                
                return f(*args, **kwargs)
                
        except JWTSecurityError as e:
            return jsonify({'error': f'Token validation failed: {str(e)}'}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication error: {str(e)}'}), 500
    
    return decorated_function


def require_permission(permission: Permission):
    """Permission-based authorization decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'security_context'):
                return jsonify({'error': 'Authentication required'}), 401
            
            try:
                with get_db_session() as db:
                    rbac = get_rbac_manager(db)
                    
                    if not rbac.check_permission(
                        request.security_context.user_id,
                        permission,
                        context=request.security_context
                    ):
                        return jsonify({
                            'error': 'Permission denied',
                            'required_permission': permission,
                            'user_permissions': request.security_context.permissions
                        }), 403
                    
                    return f(*args, **kwargs)
                    
            except Exception as e:
                return jsonify({'error': f'Authorization error: {str(e)}'}), 500
        
        return decorated_function
    return decorator


# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login with optional 2FA"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        username = data.get('username')
        password = data.get('password')
        totp_code = data.get('totp_code')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        with get_db_session() as db:
            auth_manager = AuthenticationManager(db)
            
            try:
                # Authenticate user
                context = auth_manager.authenticate_user(
                    username,
                    password,
                    request.remote_addr,
                    request.headers.get('User-Agent', ''),
                    totp_code
                )
                
                # Create JWT tokens
                jwt_manager = EnterpriseJWTManager(db)
                user = db.query(User).filter(User.id == context.user_id).first()
                
                token_pair = jwt_manager.create_token_pair(
                    user,
                    context.session_id,
                    request.remote_addr,
                    request.headers.get('User-Agent', ''),
                    permissions=context.permissions
                )
                
                response_data = {
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': str(context.user_id),
                        'username': context.username,
                        'email': context.email,
                        'role': context.role
                    },
                    'tokens': {
                        'access_token': token_pair.access_token,
                        'refresh_token': token_pair.refresh_token,
                        'expires_at': token_pair.access_expires_at.isoformat(),
                        'refresh_expires_at': token_pair.refresh_expires_at.isoformat()
                    },
                    'session': {
                        'session_id': str(context.session_id),
                        'two_factor_verified': context.two_factor_verified,
                        'permissions': context.permissions
                    }
                }
                
                # Set security headers
                response = make_response(jsonify(response_data))
                for header, value in jwt_manager.get_security_headers().items():
                    response.headers[header] = value
                
                return response
                
            except Exception as e:
                error_message = str(e)
                if "Two-factor authentication required" in error_message:
                    return jsonify({
                        'error': 'Two-factor authentication required',
                        'requires_2fa': True
                    }), 200  # Not an error, just requires additional step
                elif "Account locked" in error_message:
                    return jsonify({'error': 'Account is locked'}), 423
                else:
                    return jsonify({'error': 'Invalid credentials'}), 401
                    
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500


@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        if not data or not data.get('refresh_token'):
            return jsonify({'error': 'Refresh token required'}), 400
        
        with get_db_session() as db:
            jwt_manager = EnterpriseJWTManager(db)
            
            new_access_token = jwt_manager.refresh_access_token(
                data['refresh_token'],
                request.remote_addr,
                request.headers.get('User-Agent', '')
            )
            
            response_data = {
                'success': True,
                'access_token': new_access_token
            }
            
            response = make_response(jsonify(response_data))
            for header, value in jwt_manager.get_security_headers().items():
                response.headers[header] = value
            
            return response
            
    except JWTSecurityError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': f'Token refresh failed: {str(e)}'}), 500


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout"""
    try:
        with get_db_session() as db:
            auth_manager = AuthenticationManager(db)
            auth_manager.logout_user(
                request.security_context.session_id,
                request.remote_addr,
                request.headers.get('User-Agent', '')
            )
            
            return jsonify({
                'success': True,
                'message': 'Logout successful'
            })
            
    except Exception as e:
        return jsonify({'error': f'Logout failed: {str(e)}'}), 500


# MFA endpoints
@app.route('/api/mfa/setup', methods=['POST'])
@require_auth
def setup_mfa():
    """Setup TOTP MFA for user"""
    try:
        with get_db_session() as db:
            mfa_manager = get_mfa_manager(db)
            
            setup_result = mfa_manager.setup_totp_for_user(
                request.security_context.user_id
            )
            
            return jsonify({
                'success': True,
                'qr_code': setup_result.qr_code_base64,
                'backup_codes': setup_result.backup_codes,
                'setup_key': setup_result.setup_key,
                'instructions': 'Scan QR code with authenticator app, then verify with a code'
            })
            
    except Exception as e:
        return jsonify({'error': f'MFA setup failed: {str(e)}'}), 500


@app.route('/api/mfa/verify-setup', methods=['POST'])
@require_auth  
def verify_mfa_setup():
    """Verify MFA setup with TOTP code"""
    try:
        data = request.get_json()
        if not data or not data.get('verification_code'):
            return jsonify({'error': 'Verification code required'}), 400
        
        with get_db_session() as db:
            mfa_manager = get_mfa_manager(db)
            
            success = mfa_manager.verify_totp_setup(
                request.security_context.user_id,
                data['verification_code']
            )
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'MFA setup completed successfully'
                })
            else:
                return jsonify({'error': 'Invalid verification code'}), 400
                
    except Exception as e:
        return jsonify({'error': f'MFA verification failed: {str(e)}'}), 500


@app.route('/api/mfa/status', methods=['GET'])
@require_auth
def mfa_status():
    """Get MFA status for current user"""
    try:
        with get_db_session() as db:
            mfa_manager = get_mfa_manager(db)
            
            status = mfa_manager.get_mfa_status(request.security_context.user_id)
            
            return jsonify({
                'success': True,
                'mfa_status': status
            })
            
    except Exception as e:
        return jsonify({'error': f'Failed to get MFA status: {str(e)}'}), 500


# User management endpoints (admin only)
@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_permission(Permission.USER_LIST)
def list_users():
    """List all users (admin only)"""
    try:
        with get_db_session() as db:
            users = db.query(User).all()
            
            user_list = [{
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'role': getattr(user, 'role', SecurityRole.VIEWER),
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            } for user in users]
            
            return jsonify({
                'success': True,
                'users': user_list,
                'total': len(user_list)
            })
            
    except Exception as e:
        return jsonify({'error': f'Failed to list users: {str(e)}'}), 500


@app.route('/api/admin/users/<user_id>/role', methods=['PUT'])
@require_auth
@require_permission(Permission.ROLE_ASSIGN)
def assign_user_role(user_id):
    """Assign role to user (admin only)"""
    try:
        data = request.get_json()
        if not data or not data.get('role'):
            return jsonify({'error': 'Role required'}), 400
        
        new_role = SecurityRole(data['role'])
        
        with get_db_session() as db:
            rbac = get_rbac_manager(db)
            
            success = rbac.assign_role(
                uuid.UUID(user_id),
                new_role,
                request.security_context.user_id,
                data.get('reason', 'Role assignment via API')
            )
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Role {new_role} assigned successfully'
                })
            else:
                return jsonify({'error': 'Role assignment failed'}), 500
                
    except ValueError as e:
        return jsonify({'error': f'Invalid role: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Role assignment failed: {str(e)}'}), 500


# Security info endpoints
@app.route('/api/security/profile', methods=['GET'])
@require_auth
def security_profile():
    """Get current user's security profile"""
    try:
        with get_db_session() as db:
            rbac = get_rbac_manager(db)
            mfa_manager = get_mfa_manager(db)
            
            role_info = rbac.get_user_role_info(request.security_context.user_id)
            mfa_status = mfa_manager.get_mfa_status(request.security_context.user_id)
            
            return jsonify({
                'success': True,
                'profile': {
                    'user_info': {
                        'id': str(request.security_context.user_id),
                        'username': request.security_context.username,
                        'email': request.security_context.email,
                        'role': request.security_context.role
                    },
                    'role_info': role_info,
                    'mfa_status': mfa_status,
                    'session_info': {
                        'session_id': str(request.security_context.session_id),
                        'ip_address': request.security_context.ip_address,
                        'two_factor_verified': request.security_context.two_factor_verified,
                        'permissions': request.security_context.permissions
                    }
                }
            })
            
    except Exception as e:
        return jsonify({'error': f'Failed to get security profile: {str(e)}'}), 500


@app.route('/api/security/permissions', methods=['GET'])
@require_auth
def user_permissions():
    """Get current user's permissions"""
    try:
        with get_db_session() as db:
            rbac = get_rbac_manager(db)
            
            permissions = rbac.get_user_permissions(request.security_context.user_id)
            available_roles = rbac.get_available_roles(request.security_context.user_id)
            
            return jsonify({
                'success': True,
                'permissions': list(permissions),
                'available_roles': available_roles,
                'current_role': request.security_context.role
            })
            
    except Exception as e:
        return jsonify({'error': f'Failed to get permissions: {str(e)}'}), 500


# Error handlers
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle HTTP exceptions"""
    return jsonify({
        'error': e.description,
        'status_code': e.code
    }), e.code


@app.errorhandler(Exception)
def handle_general_exception(e):
    """Handle general exceptions"""
    return jsonify({
        'error': 'Internal server error',
        'message': str(e)
    }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)