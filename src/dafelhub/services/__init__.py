"""
DafelHub Services Module
Enterprise-grade services for SaaS consulting hub with Spec-Driven Development.

This module provides core business services for project management, specification handling,
template generation, AI agent orchestration, monitoring, and deployment automation.
"""

from .project_manager import (
    ProjectManager,
    ProjectConfig,
    ProjectMetadata,
    ServiceConfig,
    ProjectStatus,
    ServiceType,
    ProjectManagerError,
    ProjectNotFoundError,
    ProjectAlreadyExistsError,
    ServiceNotFoundError,
)

from .spec_manager import (
    SpecManager,
    SpecMetadata,
    SpecContent,
    SpecVersion,
    SpecValidationResult,
    SpecDiff,
    SpecType,
    SpecStatus,
    SpecManagerError,
    SpecNotFoundError,
    SpecAlreadyExistsError,
    SpecValidationError,
    SpecVersionError,
)

from .template_engine import (
    TemplateEngine,
    TemplateMetadata,
    TemplateRenderContext,
    TemplateRenderResult,
    TemplateValidationResult,
    TemplateFormat,
    TemplateCategory,
    TemplateEngineError,
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
)

from .agent_orchestrator import (
    AgentOrchestrator,
    AgentConfig,
    TaskDefinition,
    TaskResult,
    WorkflowDefinition,
    WorkflowExecution,
    AgentProvider,
    AgentType,
    TaskStatus,
    WorkflowStatus,
    AgentOrchestratorError,
    AgentNotFoundError,
    WorkflowExecutionError,
    TaskExecutionError,
)

from .monitoring_service import (
    MonitoringService,
    Metric,
    AlertRule,
    Alert,
    HealthCheck,
    HealthCheckResult,
    SystemMetrics,
    MetricType,
    AlertSeverity,
    AlertStatus,
    HealthStatus,
    MonitoringServiceError,
    MetricNotFoundError,
    AlertRuleError,
)

from .deployment_service import (
    DeploymentService,
    Environment,
    Deployment,
    DeploymentConfig,
    DeploymentArtifact,
    DeploymentPipeline,
    DeploymentStrategy,
    DeploymentStatus,
    EnvironmentType,
    DeploymentTarget,
    DeploymentServiceError,
    EnvironmentNotFoundError,
    DeploymentNotFoundError,
    DeploymentFailedError,
)


__all__ = [
    # Project Manager
    "ProjectManager",
    "ProjectConfig", 
    "ProjectMetadata",
    "ServiceConfig",
    "ProjectStatus",
    "ServiceType",
    "ProjectManagerError",
    "ProjectNotFoundError",
    "ProjectAlreadyExistsError",
    "ServiceNotFoundError",
    
    # Spec Manager
    "SpecManager",
    "SpecMetadata",
    "SpecContent",
    "SpecVersion",
    "SpecValidationResult",
    "SpecDiff",
    "SpecType",
    "SpecStatus",
    "SpecManagerError",
    "SpecNotFoundError",
    "SpecAlreadyExistsError",
    "SpecValidationError",
    "SpecVersionError",
    
    # Template Engine
    "TemplateEngine",
    "TemplateMetadata",
    "TemplateRenderContext",
    "TemplateRenderResult",
    "TemplateValidationResult",
    "TemplateFormat",
    "TemplateCategory",
    "TemplateEngineError",
    "TemplateNotFoundError",
    "TemplateRenderError",
    "TemplateValidationError",
    
    # Agent Orchestrator
    "AgentOrchestrator",
    "AgentConfig",
    "TaskDefinition",
    "TaskResult",
    "WorkflowDefinition",
    "WorkflowExecution",
    "AgentProvider",
    "AgentType",
    "TaskStatus",
    "WorkflowStatus",
    "AgentOrchestratorError",
    "AgentNotFoundError",
    "WorkflowExecutionError",
    "TaskExecutionError",
    
    # Monitoring Service
    "MonitoringService",
    "Metric",
    "AlertRule",
    "Alert",
    "HealthCheck",
    "HealthCheckResult",
    "SystemMetrics",
    "MetricType",
    "AlertSeverity",
    "AlertStatus",
    "HealthStatus",
    "MonitoringServiceError",
    "MetricNotFoundError",
    "AlertRuleError",
    
    # Deployment Service
    "DeploymentService",
    "Environment",
    "Deployment",
    "DeploymentConfig",
    "DeploymentArtifact",
    "DeploymentPipeline",
    "DeploymentStrategy",
    "DeploymentStatus",
    "EnvironmentType",
    "DeploymentTarget",
    "DeploymentServiceError",
    "EnvironmentNotFoundError",
    "DeploymentNotFoundError",
    "DeploymentFailedError",
]


# Version information
__version__ = "0.1.0"
__author__ = "Dafel Consulting"
__email__ = "contact@dafelconsulting.com"

# Service registry for easy access
SERVICES = {
    "project_manager": ProjectManager,
    "spec_manager": SpecManager,
    "template_engine": TemplateEngine,
    "agent_orchestrator": AgentOrchestrator,
    "monitoring_service": MonitoringService,
    "deployment_service": DeploymentService,
}


def get_service(service_name: str, **kwargs):
    """
    Get service instance by name
    
    Args:
        service_name: Name of the service
        **kwargs: Service initialization parameters
        
    Returns:
        Service instance
        
    Raises:
        ValueError: If service name is not found
    """
    if service_name not in SERVICES:
        available_services = ", ".join(SERVICES.keys())
        raise ValueError(f"Unknown service '{service_name}'. Available services: {available_services}")
    
    service_class = SERVICES[service_name]
    return service_class(**kwargs)


def list_services() -> list[str]:
    """
    List available services
    
    Returns:
        List of service names
    """
    return list(SERVICES.keys())


# Service documentation
SERVICE_DESCRIPTIONS = {
    "project_manager": "Manages projects and services with lifecycle tracking and configuration management.",
    "spec_manager": "Handles specification creation, versioning, validation and Spec-Driven Development workflows.",
    "template_engine": "Multi-format template rendering system with inheritance, custom filters and validation.",
    "agent_orchestrator": "Multi-agent AI orchestration with workflow management and task execution.",
    "monitoring_service": "Comprehensive monitoring with metrics collection, alerting and health checks.",
    "deployment_service": "Multi-environment deployment orchestration with multiple strategies and rollback capabilities.",
}