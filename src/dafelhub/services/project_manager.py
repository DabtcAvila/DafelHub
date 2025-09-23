"""
DafelHub Project Manager Service
Enterprise-grade project and service management with lifecycle tracking.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, String, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from dafelhub.core.config import settings
from dafelhub.core.logging import LoggerMixin


class ProjectStatus(str, Enum):
    """Project lifecycle status"""
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ServiceType(str, Enum):
    """Available service types"""
    WEB_APP = "web_app"
    API = "api"
    MICROSERVICE = "microservice"
    MOBILE_APP = "mobile_app"
    DESKTOP_APP = "desktop_app"
    DATA_PIPELINE = "data_pipeline"
    ML_MODEL = "ml_model"
    INFRASTRUCTURE = "infrastructure"


class ProjectConfig(BaseModel):
    """Project configuration model"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=1000)
    project_type: ServiceType
    technology_stack: List[str] = Field(default_factory=list)
    repository_url: Optional[str] = None
    environment: str = "development"
    deployment_target: Optional[str] = None
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate project name"""
        if not v.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            raise ValueError("Project name must contain only alphanumeric characters, hyphens, underscores, and spaces")
        return v.strip()
    
    @field_validator('technology_stack')
    @classmethod
    def validate_tech_stack(cls, v: List[str]) -> List[str]:
        """Validate technology stack"""
        return [tech.strip().lower() for tech in v if tech.strip()]


class ServiceConfig(BaseModel):
    """Service configuration model"""
    name: str = Field(..., min_length=1, max_length=100)
    service_type: ServiceType
    port: Optional[int] = Field(None, ge=1024, le=65535)
    endpoint: Optional[str] = None
    health_check_url: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate endpoint format"""
        if v and not v.startswith('/'):
            return f"/{v}"
        return v


class ProjectMetadata(BaseModel):
    """Project metadata model"""
    id: str
    name: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    services: List[ServiceConfig]
    config: ProjectConfig
    tags: Set[str] = Field(default_factory=set)
    owner: Optional[str] = None
    team_members: List[str] = Field(default_factory=list)


class ProjectManagerError(Exception):
    """Base exception for project manager errors"""
    pass


class ProjectNotFoundError(ProjectManagerError):
    """Raised when project is not found"""
    pass


class ProjectAlreadyExistsError(ProjectManagerError):
    """Raised when trying to create a project that already exists"""
    pass


class ServiceNotFoundError(ProjectManagerError):
    """Raised when service is not found"""
    pass


class ProjectManager(LoggerMixin):
    """
    Enterprise project and service management system
    
    Manages project lifecycle, service configurations, and deployment orchestration
    """
    
    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        db_session: Optional[Session] = None
    ):
        """
        Initialize project manager
        
        Args:
            workspace_path: Path to workspace directory
            db_session: Database session for persistence
        """
        self.workspace_path = workspace_path or Path.cwd() / "workspace"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        self.db_session = db_session
        self._projects: Dict[str, ProjectMetadata] = {}
        self._project_locks: Dict[str, asyncio.Lock] = {}
        
        self.logger.info(
            "ProjectManager initialized",
            extra={"workspace_path": str(self.workspace_path)}
        )
    
    async def create_project(
        self,
        config: ProjectConfig,
        project_id: Optional[str] = None,
        owner: Optional[str] = None
    ) -> ProjectMetadata:
        """
        Create a new project
        
        Args:
            config: Project configuration
            project_id: Optional custom project ID
            owner: Project owner identifier
            
        Returns:
            Created project metadata
            
        Raises:
            ProjectAlreadyExistsError: If project already exists
        """
        project_id = project_id or str(uuid.uuid4())
        
        if project_id in self._projects:
            raise ProjectAlreadyExistsError(f"Project {project_id} already exists")
        
        # Create project lock
        self._project_locks[project_id] = asyncio.Lock()
        
        async with self._project_locks[project_id]:
            now = datetime.now(timezone.utc)
            
            project = ProjectMetadata(
                id=project_id,
                name=config.name,
                status=ProjectStatus.PLANNING,
                created_at=now,
                updated_at=now,
                services=[],
                config=config,
                owner=owner,
                tags={"new", config.project_type.value}
            )
            
            # Create project directory
            project_dir = self.workspace_path / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # Save project metadata
            await self._save_project_metadata(project)
            
            self._projects[project_id] = project
            
            self.logger.info(
                "Project created successfully",
                extra={
                    "project_id": project_id,
                    "project_name": config.name,
                    "project_type": config.project_type.value,
                    "owner": owner
                }
            )
            
            return project
    
    async def get_project(self, project_id: str) -> ProjectMetadata:
        """
        Get project by ID
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project metadata
            
        Raises:
            ProjectNotFoundError: If project not found
        """
        if project_id not in self._projects:
            # Try to load from persistence
            project = await self._load_project_metadata(project_id)
            if not project:
                raise ProjectNotFoundError(f"Project {project_id} not found")
            self._projects[project_id] = project
            
        return self._projects[project_id]
    
    async def update_project(
        self,
        project_id: str,
        updates: Dict[str, Any]
    ) -> ProjectMetadata:
        """
        Update project configuration
        
        Args:
            project_id: Project identifier
            updates: Dictionary of updates to apply
            
        Returns:
            Updated project metadata
            
        Raises:
            ProjectNotFoundError: If project not found
        """
        project = await self.get_project(project_id)
        
        if project_id not in self._project_locks:
            self._project_locks[project_id] = asyncio.Lock()
        
        async with self._project_locks[project_id]:
            # Update allowed fields
            if "name" in updates:
                project.name = updates["name"]
            if "status" in updates:
                project.status = ProjectStatus(updates["status"])
            if "tags" in updates:
                project.tags = set(updates["tags"])
            if "team_members" in updates:
                project.team_members = updates["team_members"]
            if "config" in updates:
                # Merge config updates
                config_dict = project.config.dict()
                config_dict.update(updates["config"])
                project.config = ProjectConfig(**config_dict)
            
            project.updated_at = datetime.now(timezone.utc)
            
            await self._save_project_metadata(project)
            self._projects[project_id] = project
            
            self.logger.info(
                "Project updated successfully",
                extra={
                    "project_id": project_id,
                    "updates": list(updates.keys())
                }
            )
            
            return project
    
    async def delete_project(self, project_id: str, force: bool = False) -> bool:
        """
        Delete project
        
        Args:
            project_id: Project identifier
            force: Force deletion even if project is active
            
        Returns:
            True if deleted successfully
            
        Raises:
            ProjectNotFoundError: If project not found
            ProjectManagerError: If project cannot be deleted
        """
        project = await self.get_project(project_id)
        
        if not force and project.status == ProjectStatus.ACTIVE:
            raise ProjectManagerError(
                f"Cannot delete active project {project_id}. Use force=True to override."
            )
        
        if project_id not in self._project_locks:
            self._project_locks[project_id] = asyncio.Lock()
        
        async with self._project_locks[project_id]:
            # Archive project instead of deleting
            project.status = ProjectStatus.ARCHIVED
            project.updated_at = datetime.now(timezone.utc)
            
            await self._save_project_metadata(project)
            
            # Remove from memory but keep in persistence
            if project_id in self._projects:
                del self._projects[project_id]
            
            self.logger.info(
                "Project archived successfully",
                extra={"project_id": project_id, "force": force}
            )
            
            return True
    
    async def add_service(
        self,
        project_id: str,
        service_config: ServiceConfig
    ) -> ProjectMetadata:
        """
        Add service to project
        
        Args:
            project_id: Project identifier
            service_config: Service configuration
            
        Returns:
            Updated project metadata
            
        Raises:
            ProjectNotFoundError: If project not found
            ProjectManagerError: If service already exists
        """
        project = await self.get_project(project_id)
        
        # Check if service already exists
        existing_services = [s.name for s in project.services]
        if service_config.name in existing_services:
            raise ProjectManagerError(
                f"Service {service_config.name} already exists in project {project_id}"
            )
        
        if project_id not in self._project_locks:
            self._project_locks[project_id] = asyncio.Lock()
        
        async with self._project_locks[project_id]:
            project.services.append(service_config)
            project.updated_at = datetime.now(timezone.utc)
            
            await self._save_project_metadata(project)
            self._projects[project_id] = project
            
            self.logger.info(
                "Service added to project",
                extra={
                    "project_id": project_id,
                    "service_name": service_config.name,
                    "service_type": service_config.service_type.value
                }
            )
            
            return project
    
    async def remove_service(
        self,
        project_id: str,
        service_name: str
    ) -> ProjectMetadata:
        """
        Remove service from project
        
        Args:
            project_id: Project identifier
            service_name: Service name to remove
            
        Returns:
            Updated project metadata
            
        Raises:
            ProjectNotFoundError: If project not found
            ServiceNotFoundError: If service not found
        """
        project = await self.get_project(project_id)
        
        # Find service
        service_index = None
        for i, service in enumerate(project.services):
            if service.name == service_name:
                service_index = i
                break
        
        if service_index is None:
            raise ServiceNotFoundError(
                f"Service {service_name} not found in project {project_id}"
            )
        
        if project_id not in self._project_locks:
            self._project_locks[project_id] = asyncio.Lock()
        
        async with self._project_locks[project_id]:
            removed_service = project.services.pop(service_index)
            project.updated_at = datetime.now(timezone.utc)
            
            await self._save_project_metadata(project)
            self._projects[project_id] = project
            
            self.logger.info(
                "Service removed from project",
                extra={
                    "project_id": project_id,
                    "service_name": service_name,
                    "service_type": removed_service.service_type.value
                }
            )
            
            return project
    
    async def list_projects(
        self,
        status_filter: Optional[ProjectStatus] = None,
        owner_filter: Optional[str] = None,
        tag_filter: Optional[str] = None
    ) -> List[ProjectMetadata]:
        """
        List projects with optional filtering
        
        Args:
            status_filter: Filter by project status
            owner_filter: Filter by project owner
            tag_filter: Filter by tag
            
        Returns:
            List of matching projects
        """
        # Load all projects from persistence if needed
        await self._load_all_projects()
        
        projects = list(self._projects.values())
        
        # Apply filters
        if status_filter:
            projects = [p for p in projects if p.status == status_filter]
        
        if owner_filter:
            projects = [p for p in projects if p.owner == owner_filter]
        
        if tag_filter:
            projects = [p for p in projects if tag_filter in p.tags]
        
        # Sort by updated_at descending
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        
        return projects
    
    async def get_project_health(self, project_id: str) -> Dict[str, Any]:
        """
        Get project health status
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project health information
        """
        project = await self.get_project(project_id)
        
        health = {
            "project_id": project_id,
            "status": project.status.value,
            "services": len(project.services),
            "last_updated": project.updated_at.isoformat(),
            "health_score": 100,  # Base score
            "issues": []
        }
        
        # Check for issues
        if not project.services:
            health["health_score"] -= 20
            health["issues"].append("No services defined")
        
        if project.status == ProjectStatus.ON_HOLD:
            health["health_score"] -= 30
            health["issues"].append("Project on hold")
        
        # Check service health
        for service in project.services:
            if not service.health_check_url:
                health["health_score"] -= 5
                health["issues"].append(f"Service {service.name} has no health check")
        
        # Determine overall health
        if health["health_score"] >= 80:
            health["overall"] = "healthy"
        elif health["health_score"] >= 60:
            health["overall"] = "warning"
        else:
            health["overall"] = "critical"
        
        return health
    
    async def _save_project_metadata(self, project: ProjectMetadata) -> None:
        """
        Save project metadata to persistence layer
        
        Args:
            project: Project metadata to save
        """
        if self.db_session:
            # Save to database (implementation depends on ORM setup)
            self.logger.debug(f"Saving project {project.id} to database")
        else:
            # Save to file system
            project_file = self.workspace_path / project.id / "project.json"
            project_file.parent.mkdir(parents=True, exist_ok=True)
            
            with project_file.open("w") as f:
                import json
                # Convert to serializable format
                data = project.dict()
                data["created_at"] = data["created_at"].isoformat()
                data["updated_at"] = data["updated_at"].isoformat()
                data["tags"] = list(data["tags"])
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    async def _load_project_metadata(self, project_id: str) -> Optional[ProjectMetadata]:
        """
        Load project metadata from persistence layer
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project metadata if found, None otherwise
        """
        if self.db_session:
            # Load from database
            self.logger.debug(f"Loading project {project_id} from database")
            return None  # Placeholder
        else:
            # Load from file system
            project_file = self.workspace_path / project_id / "project.json"
            if not project_file.exists():
                return None
            
            try:
                with project_file.open("r") as f:
                    import json
                    data = json.load(f)
                    
                    # Convert back from serialized format
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                    data["tags"] = set(data["tags"])
                    data["status"] = ProjectStatus(data["status"])
                    data["config"] = ProjectConfig(**data["config"])
                    data["services"] = [ServiceConfig(**s) for s in data["services"]]
                    
                    return ProjectMetadata(**data)
            except Exception as e:
                self.logger.error(f"Failed to load project {project_id}: {e}")
                return None
    
    async def _load_all_projects(self) -> None:
        """Load all projects from persistence layer"""
        if not self.workspace_path.exists():
            return
        
        for project_dir in self.workspace_path.iterdir():
            if project_dir.is_dir() and project_dir.name not in self._projects:
                project = await self._load_project_metadata(project_dir.name)
                if project:
                    self._projects[project_dir.name] = project