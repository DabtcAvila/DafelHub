"""
DafelHub Template Engine Service
Enterprise-grade template management and rendering system with multi-format support.
"""

import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Callable

import yaml
from pydantic import BaseModel, Field, field_validator
from jinja2 import (
    Environment, 
    FileSystemLoader, 
    Template, 
    TemplateError,
    TemplateSyntaxError,
    TemplateNotFound,
    meta
)
from jinja2.sandbox import SandboxedEnvironment

from dafelhub.core.config import settings
from dafelhub.core.logging import LoggerMixin


class TemplateFormat(str, Enum):
    """Supported template formats"""
    JINJA2 = "jinja2"
    YAML = "yaml"
    JSON = "json"
    DOCKERFILE = "dockerfile"
    SHELL = "shell"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    MARKDOWN = "markdown"
    XML = "xml"
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"


class TemplateCategory(str, Enum):
    """Template categories"""
    PROJECT = "project"
    SERVICE = "service"
    API = "api"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DEPLOYMENT = "deployment"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    TESTING = "testing"
    CUSTOM = "custom"


class TemplateMetadata(BaseModel):
    """Template metadata model"""
    id: str
    name: str
    description: str = ""
    category: TemplateCategory
    format: TemplateFormat
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: Set[str] = Field(default_factory=set)
    created_at: datetime
    updated_at: datetime
    file_path: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    extends: Optional[str] = None  # Template inheritance
    includes: List[str] = Field(default_factory=list)  # Template includes
    schema: Optional[Dict[str, Any]] = None  # JSON Schema for variables
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate template name"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Template name must contain only alphanumeric characters, hyphens, and underscores")
        return v


class TemplateRenderContext(BaseModel):
    """Template rendering context"""
    template_id: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    output_format: Optional[str] = None
    target_path: Optional[Path] = None
    dry_run: bool = False
    strict_variables: bool = True  # Fail on undefined variables
    custom_filters: Dict[str, Callable] = Field(default_factory=dict)
    globals: Dict[str, Any] = Field(default_factory=dict)


class TemplateRenderResult(BaseModel):
    """Template rendering result"""
    template_id: str
    rendered_content: str
    output_path: Optional[Path] = None
    variables_used: Set[str] = Field(default_factory=set)
    render_time: float
    success: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TemplateValidationResult(BaseModel):
    """Template validation result"""
    template_id: str
    is_valid: bool
    syntax_errors: List[str] = Field(default_factory=list)
    variable_errors: List[str] = Field(default_factory=list)
    dependency_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    variables_found: Set[str] = Field(default_factory=set)
    validated_at: datetime


class TemplateEngineError(Exception):
    """Base exception for template engine errors"""
    pass


class TemplateNotFoundError(TemplateEngineError):
    """Raised when template is not found"""
    pass


class TemplateRenderError(TemplateEngineError):
    """Raised when template rendering fails"""
    pass


class TemplateValidationError(TemplateEngineError):
    """Raised when template validation fails"""
    pass


class TemplateEngine(LoggerMixin):
    """
    Enterprise template management and rendering system
    
    Features:
    - Multi-format template support
    - Template inheritance and composition
    - Sandboxed execution environment
    - Variable validation and schema support
    - Custom filters and functions
    - Template caching and optimization
    - Batch processing capabilities
    """
    
    def __init__(
        self,
        templates_path: Optional[Path] = None,
        cache_enabled: bool = True,
        sandbox_mode: bool = True
    ):
        """
        Initialize template engine
        
        Args:
            templates_path: Path to templates directory
            cache_enabled: Enable template caching
            sandbox_mode: Use sandboxed Jinja2 environment for security
        """
        self.templates_path = templates_path or Path.cwd() / "templates"
        self.templates_path.mkdir(parents=True, exist_ok=True)
        
        self.cache_enabled = cache_enabled
        self.sandbox_mode = sandbox_mode
        
        self._templates: Dict[str, TemplateMetadata] = {}
        self._template_cache: Dict[str, Template] = {}
        self._template_locks: Dict[str, asyncio.Lock] = {}
        
        # Setup Jinja2 environments
        self._setup_jinja_environment()
        
        # Built-in filters and functions
        self._setup_custom_filters()
        self._setup_custom_functions()
        
        self.logger.info(
            "TemplateEngine initialized",
            extra={
                "templates_path": str(self.templates_path),
                "cache_enabled": cache_enabled,
                "sandbox_mode": sandbox_mode
            }
        )
    
    def _setup_jinja_environment(self) -> None:
        """Setup Jinja2 environment with appropriate settings"""
        loader = FileSystemLoader(
            searchpath=str(self.templates_path),
            followlinks=True
        )
        
        env_class = SandboxedEnvironment if self.sandbox_mode else Environment
        
        self.jinja_env = env_class(
            loader=loader,
            autoescape=False,  # Templates may contain various formats
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            enable_async=True,
            cache_size=400 if self.cache_enabled else 0
        )
        
        # Configure undefined behavior
        from jinja2 import StrictUndefined
        self.jinja_env.undefined = StrictUndefined
    
    def _setup_custom_filters(self) -> None:
        """Setup custom Jinja2 filters"""
        
        def to_snake_case(value: str) -> str:
            """Convert string to snake_case"""
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', str(value))
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        
        def to_camel_case(value: str) -> str:
            """Convert string to camelCase"""
            components = str(value).split('_')
            return components[0] + ''.join(x.capitalize() for x in components[1:])
        
        def to_pascal_case(value: str) -> str:
            """Convert string to PascalCase"""
            return ''.join(x.capitalize() for x in str(value).split('_'))
        
        def to_kebab_case(value: str) -> str:
            """Convert string to kebab-case"""
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', str(value))
            return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()
        
        def indent_yaml(value: str, indent: int = 2) -> str:
            """Indent YAML content"""
            lines = str(value).split('\n')
            return '\n'.join(' ' * indent + line if line.strip() else line for line in lines)
        
        def quote_shell(value: str) -> str:
            """Quote string for shell safety"""
            return f"'{str(value).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
        
        def to_env_var(value: str) -> str:
            """Convert string to ENVIRONMENT_VARIABLE format"""
            return to_snake_case(value).upper()
        
        def default_if_none(value: Any, default: Any = "") -> Any:
            """Return default if value is None"""
            return value if value is not None else default
        
        # Register filters
        filters = {
            'snake_case': to_snake_case,
            'camel_case': to_camel_case,
            'pascal_case': to_pascal_case,
            'kebab_case': to_kebab_case,
            'indent_yaml': indent_yaml,
            'quote_shell': quote_shell,
            'env_var': to_env_var,
            'default_if_none': default_if_none,
        }
        
        for name, filter_func in filters.items():
            self.jinja_env.filters[name] = filter_func
    
    def _setup_custom_functions(self) -> None:
        """Setup custom Jinja2 global functions"""
        
        def generate_uuid() -> str:
            """Generate UUID"""
            return str(uuid.uuid4())
        
        def generate_secret(length: int = 32) -> str:
            """Generate random secret"""
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))
        
        def now(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
            """Get current timestamp"""
            return datetime.now().strftime(format_str)
        
        def env(var_name: str, default: str = "") -> str:
            """Get environment variable"""
            import os
            return os.getenv(var_name, default)
        
        def file_exists(path: str) -> bool:
            """Check if file exists"""
            return Path(path).exists()
        
        def read_file(path: str) -> str:
            """Read file content (sandboxed)"""
            file_path = Path(path)
            # Security: only allow reading from templates directory
            if not file_path.is_relative_to(self.templates_path):
                raise TemplateEngineError(f"Access denied to file outside templates directory: {path}")
            
            try:
                return file_path.read_text()
            except Exception as e:
                self.logger.warning(f"Failed to read file {path}: {e}")
                return ""
        
        # Register global functions
        functions = {
            'uuid': generate_uuid,
            'secret': generate_secret,
            'now': now,
            'env': env,
            'file_exists': file_exists,
            'read_file': read_file,
        }
        
        for name, func in functions.items():
            self.jinja_env.globals[name] = func
    
    async def register_template(
        self,
        name: str,
        file_path: Path,
        category: TemplateCategory,
        template_format: TemplateFormat,
        description: str = "",
        author: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        variables: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None
    ) -> TemplateMetadata:
        """
        Register a template
        
        Args:
            name: Template name
            file_path: Path to template file
            category: Template category
            template_format: Template format
            description: Template description
            author: Template author
            tags: Template tags
            variables: Default variables
            schema: JSON Schema for variable validation
            
        Returns:
            Template metadata
        """
        template_id = str(uuid.uuid4())
        
        # Validate file exists
        if not file_path.exists():
            raise TemplateNotFoundError(f"Template file not found: {file_path}")
        
        # Make path relative to templates directory
        try:
            relative_path = file_path.relative_to(self.templates_path)
        except ValueError:
            # File is outside templates directory, copy it
            relative_path = Path(name + file_path.suffix)
            target_path = self.templates_path / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(file_path.read_text())
        
        now = datetime.now(timezone.utc)
        
        metadata = TemplateMetadata(
            id=template_id,
            name=name,
            description=description,
            category=category,
            format=template_format,
            author=author,
            tags=tags or set(),
            created_at=now,
            updated_at=now,
            file_path=str(relative_path),
            variables=variables or {},
            schema=schema
        )
        
        # Analyze template for variables and dependencies
        await self._analyze_template(metadata)
        
        # Save metadata
        await self._save_template_metadata(metadata)
        
        self._templates[template_id] = metadata
        self._template_locks[template_id] = asyncio.Lock()
        
        self.logger.info(
            "Template registered successfully",
            extra={
                "template_id": template_id,
                "template_name": name,
                "category": category.value,
                "format": template_format.value,
                "file_path": str(relative_path)
            }
        )
        
        return metadata
    
    async def render_template(
        self,
        template_id: str,
        context: TemplateRenderContext
    ) -> TemplateRenderResult:
        """
        Render template with given context
        
        Args:
            template_id: Template identifier
            context: Rendering context
            
        Returns:
            Render result
        """
        start_time = datetime.now()
        
        # Get template metadata
        if template_id not in self._templates:
            await self._load_template_metadata(template_id)
        
        if template_id not in self._templates:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        template_metadata = self._templates[template_id]
        
        result = TemplateRenderResult(
            template_id=template_id,
            rendered_content="",
            success=False
        )
        
        try:
            # Get or load Jinja2 template
            jinja_template = await self._get_jinja_template(template_metadata)
            
            # Prepare render context
            render_vars = {**template_metadata.variables, **context.variables}
            
            # Add custom globals
            for key, value in context.globals.items():
                self.jinja_env.globals[key] = value
            
            # Add custom filters
            for name, filter_func in context.custom_filters.items():
                self.jinja_env.filters[name] = filter_func
            
            # Validate variables against schema if present
            if template_metadata.schema and context.strict_variables:
                validation_errors = self._validate_variables(render_vars, template_metadata.schema)
                if validation_errors:
                    result.errors.extend(validation_errors)
                    result.success = False
                    return result
            
            # Render template
            if context.dry_run:
                # Just validate without rendering
                result.rendered_content = f"[DRY RUN] Would render template {template_metadata.name}"
            else:
                if asyncio.iscoroutinefunction(jinja_template.render):
                    result.rendered_content = await jinja_template.render(**render_vars)
                else:
                    result.rendered_content = jinja_template.render(**render_vars)
            
            # Extract variables used
            ast = self.jinja_env.parse(jinja_template.source)
            result.variables_used = meta.find_undeclared_variables(ast)
            
            result.success = True
            
            # Save to output path if specified
            if context.target_path and not context.dry_run:
                context.target_path.parent.mkdir(parents=True, exist_ok=True)
                context.target_path.write_text(result.rendered_content)
                result.output_path = context.target_path
            
        except TemplateSyntaxError as e:
            result.errors.append(f"Template syntax error: {e}")
        except TemplateError as e:
            result.errors.append(f"Template error: {e}")
        except Exception as e:
            result.errors.append(f"Rendering error: {e}")
            self.logger.error(f"Template rendering failed: {e}", exc_info=True)
        
        # Calculate render time
        end_time = datetime.now()
        result.render_time = (end_time - start_time).total_seconds()
        
        self.logger.info(
            "Template rendering completed",
            extra={
                "template_id": template_id,
                "success": result.success,
                "render_time": result.render_time,
                "errors_count": len(result.errors),
                "dry_run": context.dry_run
            }
        )
        
        return result
    
    async def render_batch(
        self,
        batch_contexts: List[TemplateRenderContext]
    ) -> List[TemplateRenderResult]:
        """
        Render multiple templates in batch
        
        Args:
            batch_contexts: List of render contexts
            
        Returns:
            List of render results
        """
        tasks = []
        for context in batch_contexts:
            task = asyncio.create_task(self.render_template(context.template_id, context))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = TemplateRenderResult(
                    template_id=batch_contexts[i].template_id,
                    rendered_content="",
                    success=False,
                    errors=[f"Batch rendering error: {result}"],
                    render_time=0.0
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        self.logger.info(
            "Batch rendering completed",
            extra={
                "batch_size": len(batch_contexts),
                "successful": sum(1 for r in final_results if r.success),
                "failed": sum(1 for r in final_results if not r.success)
            }
        )
        
        return final_results
    
    async def validate_template(self, template_id: str) -> TemplateValidationResult:
        """
        Validate template syntax and structure
        
        Args:
            template_id: Template identifier
            
        Returns:
            Validation result
        """
        if template_id not in self._templates:
            await self._load_template_metadata(template_id)
        
        if template_id not in self._templates:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        template_metadata = self._templates[template_id]
        
        result = TemplateValidationResult(
            template_id=template_id,
            is_valid=True,
            validated_at=datetime.now(timezone.utc)
        )
        
        try:
            # Load template file
            template_file = self.templates_path / template_metadata.file_path
            if not template_file.exists():
                result.is_valid = False
                result.syntax_errors.append(f"Template file not found: {template_metadata.file_path}")
                return result
            
            template_content = template_file.read_text()
            
            # Parse template to check syntax
            try:
                ast = self.jinja_env.parse(template_content)
                result.variables_found = meta.find_undeclared_variables(ast)
            except TemplateSyntaxError as e:
                result.is_valid = False
                result.syntax_errors.append(f"Syntax error: {e}")
            
            # Validate dependencies
            for dep in template_metadata.dependencies:
                dep_file = self.templates_path / dep
                if not dep_file.exists():
                    result.dependency_errors.append(f"Dependency not found: {dep}")
            
            # Validate schema if present
            if template_metadata.schema:
                try:
                    import jsonschema
                    # Basic schema validation
                    jsonschema.Draft7Validator.check_schema(template_metadata.schema)
                except ImportError:
                    result.warnings.append("jsonschema not available for schema validation")
                except Exception as e:
                    result.variable_errors.append(f"Invalid schema: {e}")
            
            result.is_valid = (
                not result.syntax_errors and
                not result.variable_errors and
                not result.dependency_errors
            )
            
        except Exception as e:
            result.is_valid = False
            result.syntax_errors.append(f"Validation error: {e}")
        
        self.logger.info(
            "Template validation completed",
            extra={
                "template_id": template_id,
                "is_valid": result.is_valid,
                "errors_count": len(result.syntax_errors) + len(result.variable_errors) + len(result.dependency_errors),
                "warnings_count": len(result.warnings)
            }
        )
        
        return result
    
    async def list_templates(
        self,
        category: Optional[TemplateCategory] = None,
        format_filter: Optional[TemplateFormat] = None,
        tags: Optional[Set[str]] = None,
        author: Optional[str] = None
    ) -> List[TemplateMetadata]:
        """
        List templates with optional filtering
        
        Args:
            category: Filter by category
            format_filter: Filter by format
            tags: Filter by tags
            author: Filter by author
            
        Returns:
            List of matching templates
        """
        # Load all templates
        await self._load_all_templates()
        
        templates = list(self._templates.values())
        
        # Apply filters
        if category:
            templates = [t for t in templates if t.category == category]
        
        if format_filter:
            templates = [t for t in templates if t.format == format_filter]
        
        if author:
            templates = [t for t in templates if t.author == author]
        
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        
        # Sort by updated_at descending
        templates.sort(key=lambda t: t.updated_at, reverse=True)
        
        return templates
    
    async def delete_template(self, template_id: str) -> bool:
        """
        Delete template
        
        Args:
            template_id: Template identifier
            
        Returns:
            True if deleted successfully
        """
        if template_id not in self._templates:
            await self._load_template_metadata(template_id)
        
        if template_id not in self._templates:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        template_metadata = self._templates[template_id]
        
        # Remove files
        template_file = self.templates_path / template_metadata.file_path
        if template_file.exists():
            template_file.unlink()
        
        metadata_file = self.templates_path / ".metadata" / f"{template_id}.yaml"
        if metadata_file.exists():
            metadata_file.unlink()
        
        # Remove from memory
        del self._templates[template_id]
        if template_id in self._template_cache:
            del self._template_cache[template_id]
        if template_id in self._template_locks:
            del self._template_locks[template_id]
        
        self.logger.info(
            "Template deleted successfully",
            extra={"template_id": template_id, "template_name": template_metadata.name}
        )
        
        return True
    
    async def _analyze_template(self, metadata: TemplateMetadata) -> None:
        """Analyze template for variables and dependencies"""
        try:
            template_file = self.templates_path / metadata.file_path
            content = template_file.read_text()
            
            # Parse template to find variables
            ast = self.jinja_env.parse(content)
            variables = meta.find_undeclared_variables(ast)
            
            # Update metadata with found variables (don't overwrite existing defaults)
            for var in variables:
                if var not in metadata.variables:
                    metadata.variables[var] = None
            
            # Find includes and extends
            includes = re.findall(r'{%\s*include\s+[\'"]([^\'"]+)[\'"]', content)
            extends = re.findall(r'{%\s*extends\s+[\'"]([^\'"]+)[\'"]', content)
            
            if includes:
                metadata.includes = includes
            if extends:
                metadata.extends = extends[0]  # Only one extend allowed
                
        except Exception as e:
            self.logger.warning(f"Failed to analyze template {metadata.id}: {e}")
    
    async def _get_jinja_template(self, metadata: TemplateMetadata) -> Template:
        """Get Jinja2 template from cache or load it"""
        if not self.cache_enabled or metadata.id not in self._template_cache:
            try:
                template = self.jinja_env.get_template(metadata.file_path)
                if self.cache_enabled:
                    self._template_cache[metadata.id] = template
                return template
            except TemplateNotFound:
                raise TemplateNotFoundError(f"Template file not found: {metadata.file_path}")
        
        return self._template_cache[metadata.id]
    
    def _validate_variables(
        self,
        variables: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """Validate variables against JSON Schema"""
        errors = []
        
        try:
            import jsonschema
            jsonschema.validate(variables, schema)
        except ImportError:
            errors.append("jsonschema library not available for validation")
        except jsonschema.ValidationError as e:
            errors.append(f"Variable validation error: {e.message}")
        except Exception as e:
            errors.append(f"Schema validation error: {e}")
        
        return errors
    
    async def _save_template_metadata(self, metadata: TemplateMetadata) -> None:
        """Save template metadata"""
        metadata_dir = self.templates_path / ".metadata"
        metadata_dir.mkdir(exist_ok=True)
        
        metadata_file = metadata_dir / f"{metadata.id}.yaml"
        
        # Convert to serializable format
        data = metadata.dict()
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        data["tags"] = list(data["tags"])
        data["category"] = data["category"].value
        data["format"] = data["format"].value
        
        with metadata_file.open("w") as f:
            yaml.dump(data, f, default_flow_style=False)
    
    async def _load_template_metadata(self, template_id: str) -> Optional[TemplateMetadata]:
        """Load template metadata"""
        metadata_file = self.templates_path / ".metadata" / f"{template_id}.yaml"
        
        if not metadata_file.exists():
            return None
        
        try:
            with metadata_file.open("r") as f:
                data = yaml.safe_load(f)
            
            # Convert back from serialized format
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
            data["tags"] = set(data["tags"])
            data["category"] = TemplateCategory(data["category"])
            data["format"] = TemplateFormat(data["format"])
            
            metadata = TemplateMetadata(**data)
            self._templates[template_id] = metadata
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to load template metadata {template_id}: {e}")
            return None
    
    async def _load_all_templates(self) -> None:
        """Load all template metadata"""
        metadata_dir = self.templates_path / ".metadata"
        if not metadata_dir.exists():
            return
        
        for metadata_file in metadata_dir.glob("*.yaml"):
            template_id = metadata_file.stem
            if template_id not in self._templates:
                await self._load_template_metadata(template_id)