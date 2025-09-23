"""
DafelHub Specification Manager Service
Enterprise-grade specification management for Spec-Driven Development.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple

import yaml
from pydantic import BaseModel, Field, field_validator
from jinja2 import Environment, FileSystemLoader, Template

from dafelhub.core.config import settings
from dafelhub.core.logging import LoggerMixin


class SpecType(str, Enum):
    """Specification types"""
    OPENAPI = "openapi"
    ASYNCAPI = "asyncapi"
    GRAPHQL = "graphql"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    TEST = "test"
    DEPLOYMENT = "deployment"
    CUSTOM = "custom"


class SpecStatus(str, Enum):
    """Specification lifecycle status"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class SpecVersion(BaseModel):
    """Specification version model"""
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    created_at: datetime
    created_by: Optional[str] = None
    changelog: str = ""
    content_hash: str
    is_current: bool = False
    
    @field_validator('version')
    @classmethod
    def validate_semver(cls, v: str) -> str:
        """Validate semantic version format"""
        parts = v.split('.')
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError("Version must follow semantic versioning (e.g., 1.0.0)")
        return v


class SpecMetadata(BaseModel):
    """Specification metadata model"""
    id: str
    name: str
    spec_type: SpecType
    status: SpecStatus
    description: str = ""
    project_id: Optional[str] = None
    tags: Set[str] = Field(default_factory=set)
    owner: Optional[str] = None
    reviewers: List[str] = Field(default_factory=list)
    current_version: str = "1.0.0"
    versions: List[SpecVersion] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    dependencies: List[str] = Field(default_factory=list)
    references: Dict[str, str] = Field(default_factory=dict)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class SpecContent(BaseModel):
    """Specification content model"""
    spec_id: str
    version: str
    content: Union[Dict[str, Any], str]
    format: str = "yaml"  # yaml, json, markdown, etc.
    schema_validation: bool = True
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate content format"""
        allowed_formats = ['yaml', 'json', 'markdown', 'text', 'xml']
        if v.lower() not in allowed_formats:
            raise ValueError(f"Format must be one of: {', '.join(allowed_formats)}")
        return v.lower()


class SpecValidationResult(BaseModel):
    """Specification validation result"""
    spec_id: str
    version: str
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_at: datetime
    validator_version: str = "1.0.0"


class SpecDiff(BaseModel):
    """Specification difference result"""
    spec_id: str
    from_version: str
    to_version: str
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    breaking_changes: bool = False
    compatibility_score: float = 1.0


class SpecManagerError(Exception):
    """Base exception for spec manager errors"""
    pass


class SpecNotFoundError(SpecManagerError):
    """Raised when specification is not found"""
    pass


class SpecAlreadyExistsError(SpecManagerError):
    """Raised when specification already exists"""
    pass


class SpecValidationError(SpecManagerError):
    """Raised when specification validation fails"""
    pass


class SpecVersionError(SpecManagerError):
    """Raised when version operations fail"""
    pass


class SpecManager(LoggerMixin):
    """
    Enterprise specification management system
    
    Manages specification lifecycle, versioning, validation, and Spec-Driven Development workflows
    """
    
    def __init__(
        self,
        specs_path: Optional[Path] = None,
        templates_path: Optional[Path] = None
    ):
        """
        Initialize specification manager
        
        Args:
            specs_path: Path to specifications directory
            templates_path: Path to templates directory
        """
        self.specs_path = specs_path or Path.cwd() / "specs"
        self.templates_path = templates_path or Path.cwd() / "templates"
        
        # Ensure directories exist
        self.specs_path.mkdir(parents=True, exist_ok=True)
        self.templates_path.mkdir(parents=True, exist_ok=True)
        
        self._specs: Dict[str, SpecMetadata] = {}
        self._spec_locks: Dict[str, asyncio.Lock] = {}
        self._validators: Dict[SpecType, Any] = {}
        
        # Setup Jinja2 environment for templating
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_path)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        self.logger.info(
            "SpecManager initialized",
            extra={
                "specs_path": str(self.specs_path),
                "templates_path": str(self.templates_path)
            }
        )
    
    async def create_spec(
        self,
        name: str,
        spec_type: SpecType,
        content: Union[Dict[str, Any], str],
        description: str = "",
        project_id: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        spec_id: Optional[str] = None
    ) -> SpecMetadata:
        """
        Create a new specification
        
        Args:
            name: Specification name
            spec_type: Type of specification
            content: Specification content
            description: Specification description
            project_id: Associated project ID
            owner: Specification owner
            tags: Specification tags
            spec_id: Optional custom spec ID
            
        Returns:
            Created specification metadata
            
        Raises:
            SpecAlreadyExistsError: If specification already exists
        """
        spec_id = spec_id or str(uuid.uuid4())
        
        if spec_id in self._specs:
            raise SpecAlreadyExistsError(f"Specification {spec_id} already exists")
        
        # Create spec lock
        self._spec_locks[spec_id] = asyncio.Lock()
        
        async with self._spec_locks[spec_id]:
            now = datetime.now(timezone.utc)
            content_hash = self._calculate_content_hash(content)
            
            # Create initial version
            initial_version = SpecVersion(
                version="1.0.0",
                created_at=now,
                created_by=owner,
                changelog="Initial version",
                content_hash=content_hash,
                is_current=True
            )
            
            spec_metadata = SpecMetadata(
                id=spec_id,
                name=name,
                spec_type=spec_type,
                status=SpecStatus.DRAFT,
                description=description,
                project_id=project_id,
                tags=tags or set(),
                owner=owner,
                current_version="1.0.0",
                versions=[initial_version],
                created_at=now,
                updated_at=now
            )
            
            # Save specification content
            spec_content = SpecContent(
                spec_id=spec_id,
                version="1.0.0",
                content=content,
                format=self._detect_content_format(content)
            )
            
            await self._save_spec_metadata(spec_metadata)
            await self._save_spec_content(spec_content)
            
            self._specs[spec_id] = spec_metadata
            
            self.logger.info(
                "Specification created successfully",
                extra={
                    "spec_id": spec_id,
                    "spec_name": name,
                    "spec_type": spec_type.value,
                    "owner": owner,
                    "project_id": project_id
                }
            )
            
            return spec_metadata
    
    async def get_spec(
        self,
        spec_id: str,
        version: Optional[str] = None
    ) -> Tuple[SpecMetadata, SpecContent]:
        """
        Get specification by ID and optional version
        
        Args:
            spec_id: Specification identifier
            version: Specific version (defaults to current version)
            
        Returns:
            Tuple of specification metadata and content
            
        Raises:
            SpecNotFoundError: If specification not found
        """
        if spec_id not in self._specs:
            # Try to load from persistence
            spec_metadata = await self._load_spec_metadata(spec_id)
            if not spec_metadata:
                raise SpecNotFoundError(f"Specification {spec_id} not found")
            self._specs[spec_id] = spec_metadata
        
        spec_metadata = self._specs[spec_id]
        target_version = version or spec_metadata.current_version
        
        # Validate version exists
        if not any(v.version == target_version for v in spec_metadata.versions):
            raise SpecNotFoundError(
                f"Version {target_version} not found for specification {spec_id}"
            )
        
        spec_content = await self._load_spec_content(spec_id, target_version)
        if not spec_content:
            raise SpecNotFoundError(
                f"Content for specification {spec_id} version {target_version} not found"
            )
        
        return spec_metadata, spec_content
    
    async def update_spec(
        self,
        spec_id: str,
        content: Optional[Union[Dict[str, Any], str]] = None,
        metadata_updates: Optional[Dict[str, Any]] = None,
        new_version: Optional[str] = None,
        changelog: str = ""
    ) -> SpecMetadata:
        """
        Update specification content or metadata
        
        Args:
            spec_id: Specification identifier
            content: New content (creates new version if provided)
            metadata_updates: Metadata updates
            new_version: Version for new content
            changelog: Change description
            
        Returns:
            Updated specification metadata
            
        Raises:
            SpecNotFoundError: If specification not found
            SpecVersionError: If version conflicts
        """
        spec_metadata, _ = await self.get_spec(spec_id)
        
        if spec_id not in self._spec_locks:
            self._spec_locks[spec_id] = asyncio.Lock()
        
        async with self._spec_locks[spec_id]:
            now = datetime.now(timezone.utc)
            
            # Update metadata
            if metadata_updates:
                for key, value in metadata_updates.items():
                    if hasattr(spec_metadata, key):
                        if key == "status":
                            spec_metadata.status = SpecStatus(value)
                        elif key == "tags":
                            spec_metadata.tags = set(value) if isinstance(value, list) else value
                        else:
                            setattr(spec_metadata, key, value)
            
            # Create new version if content provided
            if content is not None:
                content_hash = self._calculate_content_hash(content)
                
                # Determine version
                if new_version:
                    version = new_version
                else:
                    # Auto-increment patch version
                    current = spec_metadata.current_version
                    major, minor, patch = current.split('.')
                    version = f"{major}.{minor}.{int(patch) + 1}"
                
                # Check version doesn't already exist
                if any(v.version == version for v in spec_metadata.versions):
                    raise SpecVersionError(f"Version {version} already exists")
                
                # Mark current version as not current
                for v in spec_metadata.versions:
                    v.is_current = False
                
                # Add new version
                new_version_obj = SpecVersion(
                    version=version,
                    created_at=now,
                    created_by=spec_metadata.owner,
                    changelog=changelog or "Content updated",
                    content_hash=content_hash,
                    is_current=True
                )
                
                spec_metadata.versions.append(new_version_obj)
                spec_metadata.current_version = version
                
                # Save new content
                spec_content = SpecContent(
                    spec_id=spec_id,
                    version=version,
                    content=content,
                    format=self._detect_content_format(content)
                )
                await self._save_spec_content(spec_content)
            
            spec_metadata.updated_at = now
            
            await self._save_spec_metadata(spec_metadata)
            self._specs[spec_id] = spec_metadata
            
            self.logger.info(
                "Specification updated successfully",
                extra={
                    "spec_id": spec_id,
                    "new_version": new_version if content else None,
                    "metadata_updates": list(metadata_updates.keys()) if metadata_updates else None
                }
            )
            
            return spec_metadata
    
    async def validate_spec(
        self,
        spec_id: str,
        version: Optional[str] = None
    ) -> SpecValidationResult:
        """
        Validate specification content
        
        Args:
            spec_id: Specification identifier
            version: Specification version to validate
            
        Returns:
            Validation result
        """
        spec_metadata, spec_content = await self.get_spec(spec_id, version)
        
        validation_result = SpecValidationResult(
            spec_id=spec_id,
            version=spec_content.version,
            is_valid=True,
            validated_at=datetime.now(timezone.utc)
        )
        
        try:
            # Type-specific validation
            if spec_metadata.spec_type == SpecType.OPENAPI:
                await self._validate_openapi_spec(spec_content, validation_result)
            elif spec_metadata.spec_type == SpecType.ASYNCAPI:
                await self._validate_asyncapi_spec(spec_content, validation_result)
            elif spec_metadata.spec_type == SpecType.DATABASE:
                await self._validate_database_spec(spec_content, validation_result)
            else:
                await self._validate_generic_spec(spec_content, validation_result)
            
        except Exception as e:
            validation_result.is_valid = False
            validation_result.errors.append(f"Validation error: {str(e)}")
        
        self.logger.info(
            "Specification validated",
            extra={
                "spec_id": spec_id,
                "version": spec_content.version,
                "is_valid": validation_result.is_valid,
                "errors_count": len(validation_result.errors),
                "warnings_count": len(validation_result.warnings)
            }
        )
        
        return validation_result
    
    async def compare_versions(
        self,
        spec_id: str,
        from_version: str,
        to_version: str
    ) -> SpecDiff:
        """
        Compare two versions of a specification
        
        Args:
            spec_id: Specification identifier
            from_version: Source version
            to_version: Target version
            
        Returns:
            Difference analysis
        """
        _, from_content = await self.get_spec(spec_id, from_version)
        _, to_content = await self.get_spec(spec_id, to_version)
        
        diff = SpecDiff(
            spec_id=spec_id,
            from_version=from_version,
            to_version=to_version
        )
        
        # Calculate differences
        changes = self._calculate_content_differences(
            from_content.content,
            to_content.content
        )
        
        diff.changes = changes
        diff.breaking_changes = self._has_breaking_changes(changes)
        diff.compatibility_score = self._calculate_compatibility_score(changes)
        
        self.logger.info(
            "Version comparison completed",
            extra={
                "spec_id": spec_id,
                "from_version": from_version,
                "to_version": to_version,
                "changes_count": len(changes),
                "breaking_changes": diff.breaking_changes,
                "compatibility_score": diff.compatibility_score
            }
        )
        
        return diff
    
    async def generate_from_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        spec_type: SpecType,
        name: str,
        description: str = "",
        project_id: Optional[str] = None,
        owner: Optional[str] = None
    ) -> SpecMetadata:
        """
        Generate specification from template
        
        Args:
            template_name: Template file name
            context: Template context variables
            spec_type: Type of specification to create
            name: Specification name
            description: Specification description
            project_id: Associated project ID
            owner: Specification owner
            
        Returns:
            Created specification metadata
        """
        try:
            template = self.jinja_env.get_template(template_name)
            rendered_content = template.render(**context)
            
            # Parse rendered content based on format
            if template_name.endswith('.yaml') or template_name.endswith('.yml'):
                content = yaml.safe_load(rendered_content)
            elif template_name.endswith('.json'):
                import json
                content = json.loads(rendered_content)
            else:
                content = rendered_content
            
            spec_metadata = await self.create_spec(
                name=name,
                spec_type=spec_type,
                content=content,
                description=description,
                project_id=project_id,
                owner=owner,
                tags={"template-generated", template_name}
            )
            
            self.logger.info(
                "Specification generated from template",
                extra={
                    "template_name": template_name,
                    "spec_id": spec_metadata.id,
                    "spec_type": spec_type.value
                }
            )
            
            return spec_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to generate spec from template: {e}")
            raise SpecManagerError(f"Template generation failed: {str(e)}")
    
    async def list_specs(
        self,
        project_id: Optional[str] = None,
        spec_type: Optional[SpecType] = None,
        status: Optional[SpecStatus] = None,
        owner: Optional[str] = None,
        tags: Optional[Set[str]] = None
    ) -> List[SpecMetadata]:
        """
        List specifications with optional filtering
        
        Args:
            project_id: Filter by project ID
            spec_type: Filter by specification type
            status: Filter by specification status
            owner: Filter by owner
            tags: Filter by tags (any match)
            
        Returns:
            List of matching specifications
        """
        # Load all specs from persistence if needed
        await self._load_all_specs()
        
        specs = list(self._specs.values())
        
        # Apply filters
        if project_id:
            specs = [s for s in specs if s.project_id == project_id]
        
        if spec_type:
            specs = [s for s in specs if s.spec_type == spec_type]
        
        if status:
            specs = [s for s in specs if s.status == status]
        
        if owner:
            specs = [s for s in specs if s.owner == owner]
        
        if tags:
            specs = [s for s in specs if any(tag in s.tags for tag in tags)]
        
        # Sort by updated_at descending
        specs.sort(key=lambda s: s.updated_at, reverse=True)
        
        return specs
    
    def _calculate_content_hash(self, content: Union[Dict[str, Any], str]) -> str:
        """Calculate hash of content for change detection"""
        if isinstance(content, dict):
            content_str = yaml.dump(content, sort_keys=True)
        else:
            content_str = str(content)
        
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _detect_content_format(self, content: Union[Dict[str, Any], str]) -> str:
        """Detect content format"""
        if isinstance(content, dict):
            return "yaml"
        elif isinstance(content, str):
            try:
                yaml.safe_load(content)
                return "yaml"
            except:
                try:
                    import json
                    json.loads(content)
                    return "json"
                except:
                    return "text"
        else:
            return "text"
    
    async def _validate_openapi_spec(
        self,
        spec_content: SpecContent,
        result: SpecValidationResult
    ) -> None:
        """Validate OpenAPI specification"""
        content = spec_content.content
        
        # Basic OpenAPI validation
        if isinstance(content, dict):
            if "openapi" not in content:
                result.errors.append("Missing 'openapi' field")
            if "info" not in content:
                result.errors.append("Missing 'info' field")
            if "paths" not in content:
                result.warnings.append("No 'paths' defined")
        else:
            result.errors.append("OpenAPI spec must be a dictionary/object")
        
        result.is_valid = len(result.errors) == 0
    
    async def _validate_asyncapi_spec(
        self,
        spec_content: SpecContent,
        result: SpecValidationResult
    ) -> None:
        """Validate AsyncAPI specification"""
        content = spec_content.content
        
        # Basic AsyncAPI validation
        if isinstance(content, dict):
            if "asyncapi" not in content:
                result.errors.append("Missing 'asyncapi' field")
            if "info" not in content:
                result.errors.append("Missing 'info' field")
            if "channels" not in content:
                result.warnings.append("No 'channels' defined")
        else:
            result.errors.append("AsyncAPI spec must be a dictionary/object")
        
        result.is_valid = len(result.errors) == 0
    
    async def _validate_database_spec(
        self,
        spec_content: SpecContent,
        result: SpecValidationResult
    ) -> None:
        """Validate database specification"""
        content = spec_content.content
        
        # Basic database spec validation
        if isinstance(content, dict):
            if "tables" not in content and "collections" not in content:
                result.warnings.append("No tables or collections defined")
        
        result.is_valid = len(result.errors) == 0
    
    async def _validate_generic_spec(
        self,
        spec_content: SpecContent,
        result: SpecValidationResult
    ) -> None:
        """Validate generic specification"""
        # Generic validation - just check if content is not empty
        if not spec_content.content:
            result.errors.append("Specification content is empty")
        
        result.is_valid = len(result.errors) == 0
    
    def _calculate_content_differences(
        self,
        from_content: Union[Dict[str, Any], str],
        to_content: Union[Dict[str, Any], str]
    ) -> List[Dict[str, Any]]:
        """Calculate differences between two content versions"""
        changes = []
        
        # Simple difference calculation (can be enhanced with proper diff algorithms)
        if from_content != to_content:
            changes.append({
                "type": "content_changed",
                "description": "Content has been modified",
                "severity": "minor"
            })
        
        return changes
    
    def _has_breaking_changes(self, changes: List[Dict[str, Any]]) -> bool:
        """Check if changes contain breaking changes"""
        return any(change.get("severity") == "major" for change in changes)
    
    def _calculate_compatibility_score(self, changes: List[Dict[str, Any]]) -> float:
        """Calculate compatibility score based on changes"""
        if not changes:
            return 1.0
        
        # Simple scoring (can be enhanced)
        major_changes = sum(1 for c in changes if c.get("severity") == "major")
        minor_changes = sum(1 for c in changes if c.get("severity") == "minor")
        
        score = 1.0 - (major_changes * 0.3) - (minor_changes * 0.1)
        return max(0.0, score)
    
    async def _save_spec_metadata(self, spec_metadata: SpecMetadata) -> None:
        """Save specification metadata to persistence"""
        spec_dir = self.specs_path / spec_metadata.id
        spec_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = spec_dir / "metadata.yaml"
        
        # Convert to serializable format
        data = spec_metadata.dict()
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        data["tags"] = list(data["tags"])
        data["status"] = data["status"].value
        data["spec_type"] = data["spec_type"].value
        
        # Convert versions
        for version in data["versions"]:
            version["created_at"] = version["created_at"].isoformat()
        
        with metadata_file.open("w") as f:
            yaml.dump(data, f, default_flow_style=False)
    
    async def _save_spec_content(self, spec_content: SpecContent) -> None:
        """Save specification content to persistence"""
        spec_dir = self.specs_path / spec_content.spec_id
        spec_dir.mkdir(parents=True, exist_ok=True)
        
        content_file = spec_dir / f"content_{spec_content.version}.{spec_content.format}"
        
        with content_file.open("w") as f:
            if spec_content.format == "yaml":
                yaml.dump(spec_content.content, f, default_flow_style=False)
            elif spec_content.format == "json":
                import json
                json.dump(spec_content.content, f, indent=2, ensure_ascii=False)
            else:
                f.write(str(spec_content.content))
    
    async def _load_spec_metadata(self, spec_id: str) -> Optional[SpecMetadata]:
        """Load specification metadata from persistence"""
        metadata_file = self.specs_path / spec_id / "metadata.yaml"
        
        if not metadata_file.exists():
            return None
        
        try:
            with metadata_file.open("r") as f:
                data = yaml.safe_load(f)
            
            # Convert back from serialized format
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
            data["tags"] = set(data["tags"])
            data["status"] = SpecStatus(data["status"])
            data["spec_type"] = SpecType(data["spec_type"])
            
            # Convert versions
            for version in data["versions"]:
                version["created_at"] = datetime.fromisoformat(version["created_at"])
            
            data["versions"] = [SpecVersion(**v) for v in data["versions"]]
            
            return SpecMetadata(**data)
            
        except Exception as e:
            self.logger.error(f"Failed to load spec metadata {spec_id}: {e}")
            return None
    
    async def _load_spec_content(
        self,
        spec_id: str,
        version: str
    ) -> Optional[SpecContent]:
        """Load specification content from persistence"""
        spec_dir = self.specs_path / spec_id
        
        # Try different format extensions
        for ext in ["yaml", "yml", "json", "txt", "md"]:
            content_file = spec_dir / f"content_{version}.{ext}"
            if content_file.exists():
                try:
                    with content_file.open("r") as f:
                        if ext in ["yaml", "yml"]:
                            content = yaml.safe_load(f)
                        elif ext == "json":
                            import json
                            content = json.load(f)
                        else:
                            content = f.read()
                    
                    return SpecContent(
                        spec_id=spec_id,
                        version=version,
                        content=content,
                        format=ext
                    )
                    
                except Exception as e:
                    self.logger.error(f"Failed to load spec content {spec_id}:{version}: {e}")
        
        return None
    
    async def _load_all_specs(self) -> None:
        """Load all specifications from persistence"""
        if not self.specs_path.exists():
            return
        
        for spec_dir in self.specs_path.iterdir():
            if spec_dir.is_dir() and spec_dir.name not in self._specs:
                spec_metadata = await self._load_spec_metadata(spec_dir.name)
                if spec_metadata:
                    self._specs[spec_dir.name] = spec_metadata