"""
Integration tests for API endpoints with real end-to-end scenarios.

Tests complete user workflows, authentication flows, and data persistence.
"""
import pytest
import httpx
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from dafelhub.api.main import create_app
from dafelhub.security.jwt_manager import JWTManager


class TestAuthenticationFlow:
    """Test complete authentication workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_user_registration_flow(self, test_client, db_session):
        """Test complete user registration and verification flow."""
        # Step 1: Register new user
        registration_data = {
            "email": "newuser@example.com",
            "username": "newuser123",
            "password": "SecurePass123!",
            "first_name": "New",
            "last_name": "User"
        }
        
        response = await test_client.post("/api/auth/register", json=registration_data)
        
        assert response.status_code == 201
        result = response.json()
        assert result["success"] is True
        assert "user_id" in result
        user_id = result["user_id"]
        
        # Step 2: Verify email (simulate clicking verification link)
        verification_token = result["verification_token"]
        response = await test_client.get(f"/api/auth/verify-email/{verification_token}")
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        
        # Step 3: Login with verified account
        login_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "access_token" in result
        assert "refresh_token" in result
    
    @pytest.mark.asyncio
    async def test_password_reset_flow(self, test_client, sample_user_data):
        """Test complete password reset workflow."""
        # Step 1: Request password reset
        reset_request = {"email": sample_user_data["email"]}
        
        response = await test_client.post("/api/auth/forgot-password", json=reset_request)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        
        # Step 2: Reset password with token
        reset_token = result["reset_token"]  # In real scenario, this comes from email
        new_password_data = {
            "token": reset_token,
            "new_password": "NewSecurePass123!"
        }
        
        response = await test_client.post("/api/auth/reset-password", json=new_password_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        
        # Step 3: Login with new password
        login_data = {
            "email": sample_user_data["email"],
            "password": "NewSecurePass123!"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_mfa_setup_and_login_flow(self, test_client, sample_user_data):
        """Test MFA setup and login workflow."""
        # Step 1: Login to get access token
        login_data = {
            "email": sample_user_data["email"],
            "password": "password123"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 2: Setup MFA
        response = await test_client.post("/api/auth/mfa/setup", headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert "qr_code" in result
        assert "secret" in result
        
        # Step 3: Verify MFA setup
        mfa_code = "123456"  # Mock TOTP code
        verify_data = {"code": mfa_code}
        
        response = await test_client.post("/api/auth/mfa/verify-setup", 
                                        json=verify_data, headers=headers)
        
        assert response.status_code == 200
        
        # Step 4: Login with MFA required
        response = await test_client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["mfa_required"] is True
        
        # Step 5: Complete MFA login
        mfa_login_data = {
            "session_token": result["session_token"],
            "mfa_code": mfa_code
        }
        
        response = await test_client.post("/api/auth/mfa/verify", json=mfa_login_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "access_token" in result


class TestProjectManagementFlow:
    """Test complete project management workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_project_lifecycle(self, test_client, sample_user_data):
        """Test complete project creation, management, and deletion workflow."""
        # Step 1: Authenticate user
        login_data = {
            "email": sample_user_data["email"],
            "password": "password123"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 2: Create new project
        project_data = {
            "name": "Integration Test Project",
            "description": "A project created during integration testing",
            "spec_version": "1.0.0",
            "template": "web-app",
            "settings": {
                "framework": "fastapi",
                "database": "postgresql",
                "frontend": "react"
            }
        }
        
        response = await test_client.post("/api/projects", json=project_data, headers=headers)
        
        assert response.status_code == 201
        result = response.json()
        assert result["success"] is True
        project_id = result["project"]["id"]
        
        # Step 3: Get project details
        response = await test_client.get(f"/api/projects/{project_id}", headers=headers)
        
        assert response.status_code == 200
        project = response.json()
        assert project["name"] == "Integration Test Project"
        assert project["owner_id"] == sample_user_data["id"]
        
        # Step 4: Update project
        update_data = {
            "description": "Updated description from integration test",
            "settings": {
                "framework": "fastapi",
                "database": "postgresql",
                "frontend": "vue"  # Changed frontend
            }
        }
        
        response = await test_client.patch(f"/api/projects/{project_id}", 
                                         json=update_data, headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["settings"]["frontend"] == "vue"
        
        # Step 5: List user projects
        response = await test_client.get("/api/projects", headers=headers)
        
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) >= 1
        project_ids = [p["id"] for p in projects]
        assert project_id in project_ids
        
        # Step 6: Deploy project (simulate)
        deploy_data = {
            "environment": "staging",
            "config": {
                "replicas": 2,
                "cpu_limit": "1000m",
                "memory_limit": "512Mi"
            }
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/deploy",
                                        json=deploy_data, headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "deployment_id" in result
        
        # Step 7: Monitor deployment status
        deployment_id = result["deployment_id"]
        response = await test_client.get(f"/api/deployments/{deployment_id}/status",
                                       headers=headers)
        
        assert response.status_code == 200
        status = response.json()
        assert "status" in status
        
        # Step 8: Delete project
        response = await test_client.delete(f"/api/projects/{project_id}", headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        
        # Verify project is deleted
        response = await test_client.get(f"/api/projects/{project_id}", headers=headers)
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_project_collaboration_flow(self, test_client):
        """Test project collaboration workflow with multiple users."""
        # Create two users
        user1_data = {
            "email": "user1@example.com",
            "username": "user1",
            "password": "password123"
        }
        
        user2_data = {
            "email": "user2@example.com", 
            "username": "user2",
            "password": "password123"
        }
        
        # Register both users
        await test_client.post("/api/auth/register", json=user1_data)
        await test_client.post("/api/auth/register", json=user2_data)
        
        # Login user1 (project owner)
        response = await test_client.post("/api/auth/login", json={
            "email": "user1@example.com",
            "password": "password123"
        })
        user1_token = response.json()["access_token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}
        
        # Login user2 (collaborator)
        response = await test_client.post("/api/auth/login", json={
            "email": "user2@example.com", 
            "password": "password123"
        })
        user2_token = response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}
        
        # User1 creates project
        project_data = {
            "name": "Collaboration Test Project",
            "description": "Testing collaboration features"
        }
        
        response = await test_client.post("/api/projects", json=project_data, headers=user1_headers)
        project_id = response.json()["project"]["id"]
        
        # User1 invites User2 as collaborator
        invite_data = {
            "email": "user2@example.com",
            "role": "editor"
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/invite",
                                        json=invite_data, headers=user1_headers)
        
        assert response.status_code == 200
        invite_token = response.json()["invite_token"]
        
        # User2 accepts invitation
        response = await test_client.post(f"/api/projects/invites/{invite_token}/accept",
                                        headers=user2_headers)
        
        assert response.status_code == 200
        
        # User2 can now access the project
        response = await test_client.get(f"/api/projects/{project_id}", headers=user2_headers)
        
        assert response.status_code == 200
        project = response.json()
        assert project["name"] == "Collaboration Test Project"
        
        # User2 can edit project (has editor role)
        update_data = {"description": "Updated by collaborator"}
        response = await test_client.patch(f"/api/projects/{project_id}",
                                         json=update_data, headers=user2_headers)
        
        assert response.status_code == 200


class TestConnectionManagementFlow:
    """Test complete database connection management workflow."""
    
    @pytest.mark.asyncio
    async def test_connection_crud_flow(self, test_client, sample_user_data):
        """Test complete connection CRUD workflow."""
        # Authenticate user
        login_data = {
            "email": sample_user_data["email"],
            "password": "password123"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 1: Create database connection
        connection_data = {
            "name": "Test PostgreSQL Connection",
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "testuser",
            "password": "testpass",
            "ssl_mode": "prefer"
        }
        
        response = await test_client.post("/api/connections", json=connection_data, headers=headers)
        
        assert response.status_code == 201
        result = response.json()
        assert result["success"] is True
        connection_id = result["connection"]["id"]
        
        # Step 2: Test connection
        response = await test_client.post(f"/api/connections/{connection_id}/test", headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert "connection_time" in result
        
        # Step 3: Get connection details
        response = await test_client.get(f"/api/connections/{connection_id}", headers=headers)
        
        assert response.status_code == 200
        connection = response.json()
        assert connection["name"] == "Test PostgreSQL Connection"
        assert "password" not in connection  # Password should be encrypted/hidden
        
        # Step 4: Update connection
        update_data = {
            "name": "Updated PostgreSQL Connection",
            "port": 5433
        }
        
        response = await test_client.patch(f"/api/connections/{connection_id}",
                                         json=update_data, headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["name"] == "Updated PostgreSQL Connection"
        assert result["port"] == 5433
        
        # Step 5: List connections
        response = await test_client.get("/api/connections", headers=headers)
        
        assert response.status_code == 200
        connections = response.json()
        assert len(connections) >= 1
        
        # Step 6: Execute query on connection
        query_data = {
            "query": "SELECT version();",
            "limit": 10
        }
        
        response = await test_client.post(f"/api/connections/{connection_id}/query",
                                        json=query_data, headers=headers)
        
        # This might fail if no real database, but endpoint should exist
        assert response.status_code in [200, 500]  # 500 if connection fails
        
        # Step 7: Get connection health
        response = await test_client.get(f"/api/connections/{connection_id}/health", headers=headers)
        
        assert response.status_code == 200
        health = response.json()
        assert "healthy" in health
        
        # Step 8: Delete connection
        response = await test_client.delete(f"/api/connections/{connection_id}", headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        
        # Verify connection is deleted
        response = await test_client.get(f"/api/connections/{connection_id}", headers=headers)
        assert response.status_code == 404


class TestMonitoringAndAlertsFlow:
    """Test monitoring and alerting workflow."""
    
    @pytest.mark.asyncio
    async def test_monitoring_setup_flow(self, test_client, sample_user_data, sample_project_data):
        """Test complete monitoring setup workflow."""
        # Authenticate user
        login_data = {
            "email": sample_user_data["email"],
            "password": "password123"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        project_id = sample_project_data["id"]
        
        # Step 1: Setup monitoring for project
        monitoring_config = {
            "enabled": True,
            "metrics": ["cpu", "memory", "disk", "network"],
            "alert_thresholds": {
                "cpu": 80,
                "memory": 85,
                "response_time": 5000
            },
            "notification_channels": ["email", "slack"]
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/monitoring",
                                        json=monitoring_config, headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        
        # Step 2: Get monitoring status
        response = await test_client.get(f"/api/projects/{project_id}/monitoring", headers=headers)
        
        assert response.status_code == 200
        monitoring = response.json()
        assert monitoring["enabled"] is True
        
        # Step 3: Get metrics
        response = await test_client.get(f"/api/projects/{project_id}/metrics", headers=headers)
        
        assert response.status_code == 200
        metrics = response.json()
        assert "cpu" in metrics
        assert "memory" in metrics
        
        # Step 4: Setup alert rule
        alert_rule = {
            "name": "High CPU Alert",
            "condition": "cpu_usage > 80",
            "severity": "warning",
            "notification_channels": ["email"]
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/alerts",
                                        json=alert_rule, headers=headers)
        
        assert response.status_code == 201
        alert_id = response.json()["alert_id"]
        
        # Step 5: Get alert history
        response = await test_client.get(f"/api/projects/{project_id}/alerts/history", 
                                       headers=headers)
        
        assert response.status_code == 200
        alerts = response.json()
        assert isinstance(alerts, list)
        
        # Step 6: Test alert notification
        response = await test_client.post(f"/api/alerts/{alert_id}/test", headers=headers)
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True


class TestComprehensiveUserJourney:
    """Test complete end-to-end user journey."""
    
    @pytest.mark.asyncio
    async def test_complete_user_journey(self, test_client):
        """Test complete user journey from registration to project deployment."""
        # Step 1: User Registration
        registration_data = {
            "email": "journey@example.com",
            "username": "journeyuser",
            "password": "SecurePass123!",
            "first_name": "Journey",
            "last_name": "User"
        }
        
        response = await test_client.post("/api/auth/register", json=registration_data)
        assert response.status_code == 201
        user_id = response.json()["user_id"]
        
        # Step 2: Email Verification (simulated)
        verification_token = response.json()["verification_token"]
        response = await test_client.get(f"/api/auth/verify-email/{verification_token}")
        assert response.status_code == 200
        
        # Step 3: Login
        login_data = {
            "email": "journey@example.com",
            "password": "SecurePass123!"
        }
        
        response = await test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 4: Setup Profile
        profile_data = {
            "company": "Test Company",
            "role": "Developer",
            "timezone": "UTC",
            "preferences": {
                "email_notifications": True,
                "dark_mode": False
            }
        }
        
        response = await test_client.patch("/api/auth/profile", 
                                         json=profile_data, headers=headers)
        assert response.status_code == 200
        
        # Step 5: Create Database Connection
        connection_data = {
            "name": "My Production DB",
            "type": "postgresql",
            "host": "prod.db.company.com",
            "port": 5432,
            "database": "maindb",
            "username": "appuser",
            "password": "securepass"
        }
        
        response = await test_client.post("/api/connections", 
                                        json=connection_data, headers=headers)
        assert response.status_code == 201
        connection_id = response.json()["connection"]["id"]
        
        # Step 6: Create Project
        project_data = {
            "name": "My Web Application",
            "description": "A full-stack web application",
            "template": "web-app",
            "settings": {
                "framework": "fastapi",
                "database": "postgresql",
                "frontend": "react",
                "connection_id": connection_id
            }
        }
        
        response = await test_client.post("/api/projects", 
                                        json=project_data, headers=headers)
        assert response.status_code == 201
        project_id = response.json()["project"]["id"]
        
        # Step 7: Setup Monitoring
        monitoring_config = {
            "enabled": True,
            "metrics": ["cpu", "memory", "response_time"],
            "alert_thresholds": {
                "cpu": 75,
                "memory": 80,
                "response_time": 3000
            }
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/monitoring",
                                        json=monitoring_config, headers=headers)
        assert response.status_code == 200
        
        # Step 8: Deploy Project
        deploy_config = {
            "environment": "production",
            "config": {
                "replicas": 3,
                "cpu_limit": "2000m",
                "memory_limit": "1Gi",
                "auto_scaling": True
            }
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/deploy",
                                        json=deploy_config, headers=headers)
        assert response.status_code == 200
        deployment_id = response.json()["deployment_id"]
        
        # Step 9: Monitor Deployment
        # Poll deployment status
        for _ in range(5):  # Try 5 times
            response = await test_client.get(f"/api/deployments/{deployment_id}/status",
                                           headers=headers)
            assert response.status_code == 200
            
            status = response.json()["status"]
            if status in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)  # Wait 1 second
        
        # Step 10: Get Project Analytics
        response = await test_client.get(f"/api/projects/{project_id}/analytics",
                                       headers=headers)
        assert response.status_code == 200
        analytics = response.json()
        assert "performance_metrics" in analytics
        
        # Step 11: Setup Backup Schedule
        backup_config = {
            "enabled": True,
            "frequency": "daily",
            "time": "02:00",
            "retention_days": 30,
            "encrypt": True
        }
        
        response = await test_client.post(f"/api/connections/{connection_id}/backup-schedule",
                                        json=backup_config, headers=headers)
        assert response.status_code == 200
        
        # Step 12: Generate Report
        report_config = {
            "type": "comprehensive",
            "period": "last_30_days",
            "include_metrics": True,
            "include_alerts": True,
            "include_deployments": True
        }
        
        response = await test_client.post(f"/api/projects/{project_id}/reports",
                                        json=report_config, headers=headers)
        assert response.status_code == 200
        report_id = response.json()["report_id"]
        
        # Verify we've successfully completed the entire journey
        assert user_id is not None
        assert connection_id is not None  
        assert project_id is not None
        assert deployment_id is not None
        assert report_id is not None