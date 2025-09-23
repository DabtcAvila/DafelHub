"""
DafelHub Deployment Service
Enterprise-grade deployment orchestration with multi-environment support and rollback capabilities.
"""

import asyncio
import hashlib
import json
import uuid
import yaml
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple

import httpx
from pydantic import BaseModel, Field, field_validator

from dafelhub.core.config import settings
from dafelhub.core.logging import LoggerMixin


class DeploymentStrategy(str, Enum):
    """Deployment strategies"""
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    IMMEDIATE = "immediate"


class DeploymentStatus(str, Enum):
    """Deployment status"""
    PENDING = "pending"
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class EnvironmentType(str, Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    PREVIEW = "preview"
    CUSTOM = "custom"


class DeploymentTarget(str, Enum):
    """Deployment targets"""
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    AWS_ECS = "aws_ecs"
    AWS_LAMBDA = "aws_lambda"
    GCP_CLOUD_RUN = "gcp_cloud_run"
    AZURE_CONTAINER = "azure_container"
    HEROKU = "heroku"
    VERCEL = "vercel"
    NETLIFY = "netlify"
    LOCAL = "local"
    CUSTOM = "custom"


class Environment(BaseModel):
    """Environment configuration"""
    id: str
    name: str
    environment_type: EnvironmentType
    deployment_target: DeploymentTarget
    description: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)
    variables: Dict[str, str] = Field(default_factory=dict)
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    health_check_url: Optional[str] = None
    monitoring_urls: List[str] = Field(default_factory=list)
    tags: Set[str] = Field(default_factory=set)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class DeploymentConfig(BaseModel):
    """Deployment configuration"""
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    timeout: int = 600  # seconds
    health_check_timeout: int = 300
    health_check_interval: int = 10
    rollback_on_failure: bool = True
    pre_deployment_hooks: List[Dict[str, Any]] = Field(default_factory=list)
    post_deployment_hooks: List[Dict[str, Any]] = Field(default_factory=list)
    rollback_hooks: List[Dict[str, Any]] = Field(default_factory=list)
    notifications: Dict[str, Any] = Field(default_factory=dict)
    
    # Strategy-specific configurations
    rolling_config: Dict[str, Any] = Field(default_factory=dict)
    canary_config: Dict[str, Any] = Field(default_factory=dict)
    blue_green_config: Dict[str, Any] = Field(default_factory=dict)


class DeploymentArtifact(BaseModel):
    """Deployment artifact information"""
    id: str
    name: str
    version: str
    artifact_type: str  # docker_image, zip, tar, git_commit, etc.
    location: str  # URL, path, repository, etc.
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Deployment(BaseModel):
    """Deployment definition"""
    id: str
    name: str
    description: str = ""
    project_id: str
    environment_id: str
    artifact: DeploymentArtifact
    config: DeploymentConfig
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    previous_deployment_id: Optional[str] = None
    rollback_deployment_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeploymentStep(BaseModel):
    """Individual deployment step"""
    id: str
    name: str
    description: str
    step_type: str
    command: Optional[str] = None
    script: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    depends_on: List[str] = Field(default_factory=list)
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: str = ""
    error: Optional[str] = None


class DeploymentPipeline(BaseModel):
    """Deployment pipeline with multiple stages"""
    id: str
    name: str
    description: str = ""
    project_id: str
    stages: List[Dict[str, Any]] = Field(default_factory=list)
    global_config: Dict[str, Any] = Field(default_factory=dict)
    triggers: List[Dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False
    approvers: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None


class DeploymentServiceError(Exception):
    """Base exception for deployment service errors"""
    pass


class EnvironmentNotFoundError(DeploymentServiceError):
    """Raised when environment is not found"""
    pass


class DeploymentNotFoundError(DeploymentServiceError):
    """Raised when deployment is not found"""
    pass


class DeploymentFailedError(DeploymentServiceError):
    """Raised when deployment fails"""
    pass


class DeploymentService(LoggerMixin):
    """
    Enterprise deployment orchestration service
    
    Features:
    - Multi-environment deployment management
    - Multiple deployment strategies (rolling, blue-green, canary)
    - Automated rollback capabilities
    - Health check monitoring
    - Pre/post deployment hooks
    - Deployment pipelines and approval workflows
    - Integration with multiple cloud providers
    - Artifact management and versioning
    """
    
    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        max_concurrent_deployments: int = 5,
        default_timeout: int = 600
    ):
        """
        Initialize deployment service
        
        Args:
            workspace_path: Path to workspace directory
            max_concurrent_deployments: Maximum concurrent deployments
            default_timeout: Default deployment timeout in seconds
        """
        self.workspace_path = workspace_path or Path.cwd() / "deployments"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        self.max_concurrent_deployments = max_concurrent_deployments
        self.default_timeout = default_timeout
        
        # State management
        self._environments: Dict[str, Environment] = {}
        self._deployments: Dict[str, Deployment] = {}
        self._pipelines: Dict[str, DeploymentPipeline] = {}
        self._active_deployments: Set[str] = set()
        self._deployment_locks: Dict[str, asyncio.Lock] = {}
        
        # Deployment semaphore for concurrency control
        self._deployment_semaphore = asyncio.Semaphore(max_concurrent_deployments)
        
        # HTTP client for external services
        self._http_client = httpx.AsyncClient(timeout=30.0)
        
        self.logger.info(
            "DeploymentService initialized",
            extra={
                "workspace_path": str(self.workspace_path),
                "max_concurrent_deployments": max_concurrent_deployments,
                "default_timeout": default_timeout
            }
        )
    
    async def create_environment(
        self,
        name: str,
        environment_type: EnvironmentType,
        deployment_target: DeploymentTarget,
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, str]] = None
    ) -> Environment:
        """
        Create a new deployment environment
        
        Args:
            name: Environment name
            environment_type: Type of environment
            deployment_target: Target deployment platform
            description: Environment description
            config: Environment configuration
            variables: Environment variables
            secrets: Environment secrets
            
        Returns:
            Created environment
        """
        env_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        environment = Environment(
            id=env_id,
            name=name,
            environment_type=environment_type,
            deployment_target=deployment_target,
            description=description,
            config=config or {},
            variables=variables or {},
            secrets=secrets or {},
            created_at=now,
            updated_at=now
        )
        
        # Validate environment configuration
        await self._validate_environment_config(environment)
        
        self._environments[env_id] = environment
        
        # Save environment configuration
        await self._save_environment_config(environment)
        
        self.logger.info(
            "Environment created successfully",
            extra={
                "environment_id": env_id,
                "environment_name": name,
                "environment_type": environment_type.value,
                "deployment_target": deployment_target.value
            }
        )
        
        return environment
    
    async def create_deployment(
        self,
        name: str,
        project_id: str,
        environment_id: str,
        artifact: DeploymentArtifact,
        config: Optional[DeploymentConfig] = None,
        deployed_by: Optional[str] = None,
        description: str = ""
    ) -> Deployment:
        """
        Create a new deployment
        
        Args:
            name: Deployment name
            project_id: Project identifier
            environment_id: Target environment ID
            artifact: Deployment artifact
            config: Deployment configuration
            deployed_by: User who initiated deployment
            description: Deployment description
            
        Returns:
            Created deployment
        """
        # Validate environment exists
        if environment_id not in self._environments:
            raise EnvironmentNotFoundError(f"Environment {environment_id} not found")
        
        deployment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        deployment = Deployment(
            id=deployment_id,
            name=name,
            description=description,
            project_id=project_id,
            environment_id=environment_id,
            artifact=artifact,
            config=config or DeploymentConfig(),
            created_at=now,
            deployed_by=deployed_by
        )
        
        self._deployments[deployment_id] = deployment
        self._deployment_locks[deployment_id] = asyncio.Lock()
        
        self.logger.info(
            "Deployment created successfully",
            extra={
                "deployment_id": deployment_id,
                "deployment_name": name,
                "project_id": project_id,
                "environment_id": environment_id,
                "artifact_version": artifact.version,
                "deployed_by": deployed_by
            }
        )
        
        return deployment
    
    async def deploy(self, deployment_id: str) -> Deployment:
        """
        Execute deployment
        
        Args:
            deployment_id: Deployment identifier
            
        Returns:
            Updated deployment with results
        """
        if deployment_id not in self._deployments:
            raise DeploymentNotFoundError(f"Deployment {deployment_id} not found")
        
        deployment = self._deployments[deployment_id]
        environment = self._environments[deployment.environment_id]
        
        # Check if deployment is already running
        if deployment_id in self._active_deployments:
            raise DeploymentServiceError(f"Deployment {deployment_id} is already in progress")
        
        async with self._deployment_semaphore:
            async with self._deployment_locks[deployment_id]:
                self._active_deployments.add(deployment_id)
                
                try:
                    await self._execute_deployment(deployment, environment)
                finally:
                    self._active_deployments.discard(deployment_id)
        
        return deployment
    
    async def rollback_deployment(
        self,
        deployment_id: str,
        target_deployment_id: Optional[str] = None
    ) -> Deployment:
        """
        Rollback deployment
        
        Args:
            deployment_id: Current deployment ID to rollback
            target_deployment_id: Optional specific deployment to rollback to
            
        Returns:
            Rollback deployment
        """
        if deployment_id not in self._deployments:
            raise DeploymentNotFoundError(f"Deployment {deployment_id} not found")
        
        current_deployment = self._deployments[deployment_id]
        
        # Find target deployment for rollback
        if target_deployment_id:
            if target_deployment_id not in self._deployments:
                raise DeploymentNotFoundError(f"Target deployment {target_deployment_id} not found")
            target_deployment = self._deployments[target_deployment_id]
        else:
            # Find previous successful deployment
            target_deployment = await self._find_previous_deployment(current_deployment)
            if not target_deployment:
                raise DeploymentServiceError("No previous deployment found for rollback")
        
        # Create rollback deployment
        rollback_deployment = await self.create_deployment(
            name=f"Rollback to {target_deployment.artifact.version}",
            project_id=current_deployment.project_id,
            environment_id=current_deployment.environment_id,
            artifact=target_deployment.artifact,
            config=current_deployment.config,
            deployed_by=current_deployment.deployed_by,
            description=f"Rollback from deployment {deployment_id} to {target_deployment.id}"
        )
        
        # Set rollback relationship
        current_deployment.rollback_deployment_id = rollback_deployment.id
        rollback_deployment.previous_deployment_id = deployment_id
        
        # Execute rollback
        await self.deploy(rollback_deployment.id)
        
        # Update current deployment status
        current_deployment.status = DeploymentStatus.ROLLED_BACK
        
        self.logger.info(
            "Deployment rollback completed",
            extra={
                "current_deployment_id": deployment_id,
                "rollback_deployment_id": rollback_deployment.id,
                "target_version": target_deployment.artifact.version
            }
        )
        
        return rollback_deployment
    
    async def get_deployment_logs(self, deployment_id: str) -> List[str]:
        """
        Get deployment logs
        
        Args:
            deployment_id: Deployment identifier
            
        Returns:
            List of log entries
        """
        if deployment_id not in self._deployments:
            raise DeploymentNotFoundError(f"Deployment {deployment_id} not found")
        
        return self._deployments[deployment_id].logs
    
    async def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        Get deployment status and details
        
        Args:
            deployment_id: Deployment identifier
            
        Returns:
            Deployment status information
        """
        if deployment_id not in self._deployments:
            raise DeploymentNotFoundError(f"Deployment {deployment_id} not found")
        
        deployment = self._deployments[deployment_id]
        environment = self._environments[deployment.environment_id]
        
        status = {
            "deployment_id": deployment_id,
            "name": deployment.name,
            "status": deployment.status.value,
            "environment": environment.name,
            "artifact_version": deployment.artifact.version,
            "created_at": deployment.created_at.isoformat(),
            "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
            "completed_at": deployment.completed_at.isoformat() if deployment.completed_at else None,
            "deployed_by": deployment.deployed_by,
            "error": deployment.error
        }
        
        # Add health check status if available
        if environment.health_check_url:
            try:
                health_status = await self._check_deployment_health(environment)
                status["health_status"] = health_status
            except Exception as e:
                status["health_status"] = {"status": "unknown", "error": str(e)}
        
        return status
    
    async def list_deployments(
        self,
        project_id: Optional[str] = None,
        environment_id: Optional[str] = None,
        status: Optional[DeploymentStatus] = None,
        limit: int = 50
    ) -> List[Deployment]:
        """
        List deployments with optional filtering
        
        Args:
            project_id: Filter by project ID
            environment_id: Filter by environment ID
            status: Filter by deployment status
            limit: Maximum number of deployments to return
            
        Returns:
            List of deployments
        """
        deployments = list(self._deployments.values())
        
        # Apply filters
        if project_id:
            deployments = [d for d in deployments if d.project_id == project_id]
        
        if environment_id:
            deployments = [d for d in deployments if d.environment_id == environment_id]
        
        if status:
            deployments = [d for d in deployments if d.status == status]
        
        # Sort by created_at descending and limit
        deployments.sort(key=lambda d: d.created_at, reverse=True)
        return deployments[:limit]
    
    async def list_environments(
        self,
        environment_type: Optional[EnvironmentType] = None,
        deployment_target: Optional[DeploymentTarget] = None,
        active_only: bool = True
    ) -> List[Environment]:
        """
        List environments with optional filtering
        
        Args:
            environment_type: Filter by environment type
            deployment_target: Filter by deployment target
            active_only: Only return active environments
            
        Returns:
            List of environments
        """
        environments = list(self._environments.values())
        
        # Apply filters
        if environment_type:
            environments = [e for e in environments if e.environment_type == environment_type]
        
        if deployment_target:
            environments = [e for e in environments if e.deployment_target == deployment_target]
        
        if active_only:
            environments = [e for e in environments if e.is_active]
        
        # Sort by name
        environments.sort(key=lambda e: e.name)
        return environments
    
    async def _execute_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Execute deployment with specified strategy"""
        
        deployment.status = DeploymentStatus.PREPARING
        deployment.started_at = datetime.now(timezone.utc)
        
        try:
            await self._log_deployment(deployment, "Starting deployment preparation")
            
            # Pre-deployment hooks
            if deployment.config.pre_deployment_hooks:
                await self._execute_hooks(deployment, deployment.config.pre_deployment_hooks, "pre-deployment")
            
            # Execute deployment based on strategy
            if deployment.config.strategy == DeploymentStrategy.ROLLING:
                await self._execute_rolling_deployment(deployment, environment)
            elif deployment.config.strategy == DeploymentStrategy.BLUE_GREEN:
                await self._execute_blue_green_deployment(deployment, environment)
            elif deployment.config.strategy == DeploymentStrategy.CANARY:
                await self._execute_canary_deployment(deployment, environment)
            elif deployment.config.strategy == DeploymentStrategy.RECREATE:
                await self._execute_recreate_deployment(deployment, environment)
            else:
                await self._execute_immediate_deployment(deployment, environment)
            
            # Health check
            if environment.health_check_url:
                await self._wait_for_health_check(deployment, environment)
            
            # Post-deployment hooks
            if deployment.config.post_deployment_hooks:
                await self._execute_hooks(deployment, deployment.config.post_deployment_hooks, "post-deployment")
            
            deployment.status = DeploymentStatus.DEPLOYED
            deployment.completed_at = datetime.now(timezone.utc)
            
            await self._log_deployment(deployment, "Deployment completed successfully")
            
            # Send success notifications
            await self._send_deployment_notification(deployment, "success")
            
        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error = str(e)
            deployment.completed_at = datetime.now(timezone.utc)
            
            await self._log_deployment(deployment, f"Deployment failed: {str(e)}")
            
            # Rollback on failure if configured
            if deployment.config.rollback_on_failure:
                try:
                    await self._execute_rollback_hooks(deployment)
                except Exception as rollback_error:
                    await self._log_deployment(deployment, f"Rollback failed: {str(rollback_error)}")
            
            # Send failure notifications
            await self._send_deployment_notification(deployment, "failure")
            
            raise DeploymentFailedError(f"Deployment failed: {str(e)}")
    
    async def _execute_rolling_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Execute rolling deployment strategy"""
        deployment.status = DeploymentStatus.DEPLOYING
        await self._log_deployment(deployment, "Executing rolling deployment")
        
        # Get rolling configuration
        rolling_config = deployment.config.rolling_config
        batch_size = rolling_config.get("batch_size", 1)
        max_unavailable = rolling_config.get("max_unavailable", 1)
        
        # Simulate rolling update (implementation depends on target platform)
        if environment.deployment_target == DeploymentTarget.KUBERNETES:
            await self._rolling_update_kubernetes(deployment, environment, batch_size)
        elif environment.deployment_target == DeploymentTarget.DOCKER:
            await self._rolling_update_docker(deployment, environment, batch_size)
        else:
            await self._generic_rolling_update(deployment, environment)
    
    async def _execute_blue_green_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Execute blue-green deployment strategy"""
        deployment.status = DeploymentStatus.DEPLOYING
        await self._log_deployment(deployment, "Executing blue-green deployment")
        
        # Deploy to green environment
        await self._deploy_to_green_environment(deployment, environment)
        
        # Test green environment
        await self._test_green_environment(deployment, environment)
        
        # Switch traffic to green
        await self._switch_to_green_environment(deployment, environment)
        
        # Cleanup blue environment
        await self._cleanup_blue_environment(deployment, environment)
    
    async def _execute_canary_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Execute canary deployment strategy"""
        deployment.status = DeploymentStatus.DEPLOYING
        await self._log_deployment(deployment, "Executing canary deployment")
        
        canary_config = deployment.config.canary_config
        traffic_percentage = canary_config.get("initial_traffic", 10)
        increment_percentage = canary_config.get("increment", 10)
        evaluation_interval = canary_config.get("evaluation_interval", 300)
        
        # Deploy canary version
        await self._deploy_canary_version(deployment, environment)
        
        # Gradually increase traffic
        while traffic_percentage < 100:
            await self._set_canary_traffic(deployment, environment, traffic_percentage)
            await self._log_deployment(deployment, f"Canary traffic set to {traffic_percentage}%")
            
            # Wait and evaluate
            await asyncio.sleep(evaluation_interval)
            
            # Check metrics and decide whether to continue
            metrics_ok = await self._evaluate_canary_metrics(deployment, environment)
            if not metrics_ok:
                raise DeploymentFailedError("Canary metrics evaluation failed")
            
            traffic_percentage += increment_percentage
        
        # Complete canary deployment
        await self._complete_canary_deployment(deployment, environment)
    
    async def _execute_recreate_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Execute recreate deployment strategy"""
        deployment.status = DeploymentStatus.DEPLOYING
        await self._log_deployment(deployment, "Executing recreate deployment")
        
        # Stop current version
        await self._stop_current_deployment(deployment, environment)
        
        # Deploy new version
        await self._deploy_new_version(deployment, environment)
        
        # Start new version
        await self._start_new_deployment(deployment, environment)
    
    async def _execute_immediate_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Execute immediate deployment strategy"""
        deployment.status = DeploymentStatus.DEPLOYING
        await self._log_deployment(deployment, "Executing immediate deployment")
        
        # Direct deployment without gradual rollout
        await self._deploy_immediately(deployment, environment)
    
    async def _execute_hooks(
        self,
        deployment: Deployment,
        hooks: List[Dict[str, Any]],
        hook_type: str
    ) -> None:
        """Execute deployment hooks"""
        await self._log_deployment(deployment, f"Executing {hook_type} hooks")
        
        for hook in hooks:
            hook_name = hook.get("name", "unnamed")
            await self._log_deployment(deployment, f"Executing {hook_type} hook: {hook_name}")
            
            try:
                if hook.get("type") == "command":
                    await self._execute_command_hook(deployment, hook)
                elif hook.get("type") == "script":
                    await self._execute_script_hook(deployment, hook)
                elif hook.get("type") == "webhook":
                    await self._execute_webhook_hook(deployment, hook)
                else:
                    await self._log_deployment(deployment, f"Unknown hook type: {hook.get('type')}")
                    
            except Exception as e:
                error_msg = f"Hook {hook_name} failed: {str(e)}"
                await self._log_deployment(deployment, error_msg)
                
                # Fail deployment if hook is critical
                if hook.get("critical", False):
                    raise DeploymentFailedError(error_msg)
    
    async def _execute_command_hook(
        self,
        deployment: Deployment,
        hook: Dict[str, Any]
    ) -> None:
        """Execute command hook"""
        command = hook.get("command")
        if not command:
            return
        
        timeout = hook.get("timeout", 300)
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.workspace_path / deployment.id
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        if process.returncode != 0:
            raise DeploymentServiceError(f"Command failed: {stderr.decode()}")
        
        await self._log_deployment(deployment, f"Command output: {stdout.decode()}")
    
    async def _execute_script_hook(
        self,
        deployment: Deployment,
        hook: Dict[str, Any]
    ) -> None:
        """Execute script hook"""
        script_content = hook.get("script")
        if not script_content:
            return
        
        # Write script to temporary file
        script_file = self.workspace_path / deployment.id / "hook_script.sh"
        script_file.parent.mkdir(parents=True, exist_ok=True)
        script_file.write_text(script_content)
        script_file.chmod(0o755)
        
        # Execute script
        await self._execute_command_hook(deployment, {
            "command": str(script_file),
            "timeout": hook.get("timeout", 300)
        })
    
    async def _execute_webhook_hook(
        self,
        deployment: Deployment,
        hook: Dict[str, Any]
    ) -> None:
        """Execute webhook hook"""
        url = hook.get("url")
        if not url:
            return
        
        payload = {
            "deployment_id": deployment.id,
            "deployment_name": deployment.name,
            "project_id": deployment.project_id,
            "environment_id": deployment.environment_id,
            "status": deployment.status.value,
            "artifact_version": deployment.artifact.version
        }
        
        # Add custom payload
        if hook.get("payload"):
            payload.update(hook["payload"])
        
        headers = hook.get("headers", {})
        method = hook.get("method", "POST").upper()
        timeout = hook.get("timeout", 30)
        
        async with self._http_client as client:
            if method == "POST":
                response = await client.post(url, json=payload, headers=headers, timeout=timeout)
            elif method == "PUT":
                response = await client.put(url, json=payload, headers=headers, timeout=timeout)
            else:
                response = await client.get(url, headers=headers, timeout=timeout)
            
            response.raise_for_status()
    
    async def _wait_for_health_check(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Wait for deployment health check to pass"""
        await self._log_deployment(deployment, "Waiting for health check to pass")
        
        timeout = deployment.config.health_check_timeout
        interval = deployment.config.health_check_interval
        start_time = datetime.now(timezone.utc)
        
        while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
            try:
                health_status = await self._check_deployment_health(environment)
                
                if health_status.get("status") == "healthy":
                    await self._log_deployment(deployment, "Health check passed")
                    return
                
                await self._log_deployment(
                    deployment,
                    f"Health check status: {health_status.get('status', 'unknown')}"
                )
                
            except Exception as e:
                await self._log_deployment(deployment, f"Health check error: {str(e)}")
            
            await asyncio.sleep(interval)
        
        raise DeploymentFailedError("Health check timeout")
    
    async def _check_deployment_health(self, environment: Environment) -> Dict[str, Any]:
        """Check deployment health"""
        if not environment.health_check_url:
            return {"status": "unknown", "message": "No health check URL configured"}
        
        try:
            async with self._http_client as client:
                response = await client.get(environment.health_check_url, timeout=10)
                
                if response.status_code == 200:
                    return {"status": "healthy", "response_code": response.status_code}
                else:
                    return {
                        "status": "unhealthy",
                        "response_code": response.status_code,
                        "message": f"Health check returned {response.status_code}"
                    }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _send_deployment_notification(
        self,
        deployment: Deployment,
        notification_type: str
    ) -> None:
        """Send deployment notification"""
        notifications = deployment.config.notifications
        
        if not notifications:
            return
        
        notification_config = notifications.get(notification_type)
        if not notification_config:
            return
        
        try:
            if notification_config.get("type") == "webhook":
                await self._send_webhook_notification(deployment, notification_config, notification_type)
            elif notification_config.get("type") == "email":
                await self._send_email_notification(deployment, notification_config, notification_type)
            elif notification_config.get("type") == "slack":
                await self._send_slack_notification(deployment, notification_config, notification_type)
                
        except Exception as e:
            self.logger.warning(f"Failed to send {notification_type} notification: {e}")
    
    async def _send_webhook_notification(
        self,
        deployment: Deployment,
        config: Dict[str, Any],
        notification_type: str
    ) -> None:
        """Send webhook notification"""
        url = config.get("url")
        if not url:
            return
        
        payload = {
            "event": f"deployment_{notification_type}",
            "deployment": {
                "id": deployment.id,
                "name": deployment.name,
                "status": deployment.status.value,
                "environment_id": deployment.environment_id,
                "project_id": deployment.project_id,
                "artifact_version": deployment.artifact.version,
                "deployed_by": deployment.deployed_by,
                "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
                "completed_at": deployment.completed_at.isoformat() if deployment.completed_at else None,
                "error": deployment.error
            }
        }
        
        async with self._http_client as client:
            await client.post(url, json=payload, timeout=30)
    
    async def _log_deployment(self, deployment: Deployment, message: str) -> None:
        """Add log entry to deployment"""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"[{timestamp}] {message}"
        deployment.logs.append(log_entry)
        
        self.logger.info(
            message,
            extra={"deployment_id": deployment.id, "deployment_name": deployment.name}
        )
    
    async def _validate_environment_config(self, environment: Environment) -> None:
        """Validate environment configuration"""
        # Basic validation - can be extended based on deployment target
        if environment.deployment_target == DeploymentTarget.KUBERNETES:
            required_config = ["namespace", "cluster"]
            for key in required_config:
                if key not in environment.config:
                    raise DeploymentServiceError(f"Missing required config for Kubernetes: {key}")
        
        elif environment.deployment_target == DeploymentTarget.AWS_ECS:
            required_config = ["cluster_name", "service_name"]
            for key in required_config:
                if key not in environment.config:
                    raise DeploymentServiceError(f"Missing required config for AWS ECS: {key}")
    
    async def _save_environment_config(self, environment: Environment) -> None:
        """Save environment configuration to file"""
        env_dir = self.workspace_path / "environments"
        env_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = env_dir / f"{environment.id}.yaml"
        
        # Convert to serializable format (excluding secrets)
        config_data = environment.dict(exclude={"secrets"})
        config_data["created_at"] = config_data["created_at"].isoformat()
        config_data["updated_at"] = config_data["updated_at"].isoformat()
        config_data["tags"] = list(config_data["tags"])
        config_data["environment_type"] = config_data["environment_type"].value
        config_data["deployment_target"] = config_data["deployment_target"].value
        
        with config_file.open("w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
    
    async def _find_previous_deployment(self, current_deployment: Deployment) -> Optional[Deployment]:
        """Find previous successful deployment for rollback"""
        deployments = [
            d for d in self._deployments.values()
            if (d.project_id == current_deployment.project_id and
                d.environment_id == current_deployment.environment_id and
                d.status == DeploymentStatus.DEPLOYED and
                d.id != current_deployment.id and
                d.created_at < current_deployment.created_at)
        ]
        
        # Sort by created_at descending and return most recent
        deployments.sort(key=lambda d: d.created_at, reverse=True)
        return deployments[0] if deployments else None
    
    # Platform-specific deployment implementations
    # These are placeholders - actual implementations would integrate with specific platforms
    
    async def _rolling_update_kubernetes(
        self,
        deployment: Deployment,
        environment: Environment,
        batch_size: int
    ) -> None:
        """Kubernetes rolling update implementation"""
        await self._log_deployment(deployment, f"Updating Kubernetes deployment with batch size {batch_size}")
        # Implementation would use kubectl or Kubernetes API
        
    async def _rolling_update_docker(
        self,
        deployment: Deployment,
        environment: Environment,
        batch_size: int
    ) -> None:
        """Docker rolling update implementation"""
        await self._log_deployment(deployment, f"Rolling update Docker containers with batch size {batch_size}")
        # Implementation would use Docker API or Docker Compose
    
    async def _generic_rolling_update(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Generic rolling update implementation"""
        await self._log_deployment(deployment, "Executing generic rolling update")
        # Generic implementation for unsupported platforms
    
    async def _deploy_to_green_environment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Deploy to green environment for blue-green deployment"""
        await self._log_deployment(deployment, "Deploying to green environment")
    
    async def _test_green_environment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Test green environment"""
        await self._log_deployment(deployment, "Testing green environment")
    
    async def _switch_to_green_environment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Switch traffic to green environment"""
        await self._log_deployment(deployment, "Switching traffic to green environment")
    
    async def _cleanup_blue_environment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Cleanup blue environment after successful switch"""
        await self._log_deployment(deployment, "Cleaning up blue environment")
    
    async def _deploy_canary_version(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Deploy canary version"""
        await self._log_deployment(deployment, "Deploying canary version")
    
    async def _set_canary_traffic(
        self,
        deployment: Deployment,
        environment: Environment,
        percentage: int
    ) -> None:
        """Set traffic percentage for canary deployment"""
        await self._log_deployment(deployment, f"Setting canary traffic to {percentage}%")
    
    async def _evaluate_canary_metrics(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> bool:
        """Evaluate canary metrics"""
        await self._log_deployment(deployment, "Evaluating canary metrics")
        return True  # Placeholder - would check actual metrics
    
    async def _complete_canary_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Complete canary deployment"""
        await self._log_deployment(deployment, "Completing canary deployment")
    
    async def _stop_current_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Stop current deployment for recreate strategy"""
        await self._log_deployment(deployment, "Stopping current deployment")
    
    async def _deploy_new_version(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Deploy new version"""
        await self._log_deployment(deployment, "Deploying new version")
    
    async def _start_new_deployment(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Start new deployment"""
        await self._log_deployment(deployment, "Starting new deployment")
    
    async def _deploy_immediately(
        self,
        deployment: Deployment,
        environment: Environment
    ) -> None:
        """Deploy immediately without gradual rollout"""
        await self._log_deployment(deployment, "Deploying immediately")
    
    async def _execute_rollback_hooks(self, deployment: Deployment) -> None:
        """Execute rollback hooks"""
        if deployment.config.rollback_hooks:
            await self._execute_hooks(deployment, deployment.config.rollback_hooks, "rollback")
    
    async def _send_email_notification(
        self,
        deployment: Deployment,
        config: Dict[str, Any],
        notification_type: str
    ) -> None:
        """Send email notification"""
        # Placeholder for email notification implementation
        pass
    
    async def _send_slack_notification(
        self,
        deployment: Deployment,
        config: Dict[str, Any],
        notification_type: str
    ) -> None:
        """Send Slack notification"""
        # Placeholder for Slack notification implementation
        pass
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self._http_client.aclose()
        self.logger.info("DeploymentService cleanup completed")