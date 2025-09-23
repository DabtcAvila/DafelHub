"""
DafelHub Agent Orchestrator Service
Enterprise-grade multi-agent AI orchestration with workflow management.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Callable, Tuple

import httpx
from pydantic import BaseModel, Field, field_validator

from dafelhub.core.config import settings
from dafelhub.core.logging import LoggerMixin


class AgentProvider(str, Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    AZURE_OPENAI = "azure_openai"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"


class AgentType(str, Enum):
    """Agent specialization types"""
    PLANNER = "planner"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    TESTER = "tester"
    REVIEWER = "reviewer"
    DEPLOYER = "deployer"
    MONITOR = "monitor"
    ANALYST = "analyst"
    GENERATOR = "generator"
    VALIDATOR = "validator"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"


class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentConfig(BaseModel):
    """Agent configuration"""
    id: str
    name: str
    agent_type: AgentType
    provider: AgentProvider
    model: str
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30
    max_retries: int = 3
    system_prompt: str = ""
    custom_parameters: Dict[str, Any] = Field(default_factory=dict)
    rate_limit: Optional[int] = None  # requests per minute
    cost_per_token: float = 0.0
    tags: Set[str] = Field(default_factory=set)
    is_active: bool = True


class TaskDefinition(BaseModel):
    """Task definition for agent execution"""
    id: str
    name: str
    description: str
    agent_type: AgentType
    priority: int = 1  # 1 = highest, 10 = lowest
    input_data: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)  # Task IDs
    timeout: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    validation_rules: List[Dict[str, Any]] = Field(default_factory=list)
    output_schema: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Task execution result"""
    task_id: str
    agent_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    tokens_used: int = 0
    cost: float = 0.0
    started_at: datetime
    completed_at: Optional[datetime] = None
    validation_results: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    """Workflow definition with tasks and dependencies"""
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    tasks: List[TaskDefinition]
    global_context: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[int] = None  # Total workflow timeout
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    on_success: Optional[List[Dict[str, Any]]] = None
    on_failure: Optional[List[Dict[str, Any]]] = None
    tags: Set[str] = Field(default_factory=set)
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None


class WorkflowExecution(BaseModel):
    """Workflow execution state"""
    id: str
    workflow_id: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    task_results: Dict[str, TaskResult] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    current_tasks: List[str] = Field(default_factory=list)
    failed_tasks: List[str] = Field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentOrchestratorError(Exception):
    """Base exception for agent orchestrator errors"""
    pass


class AgentNotFoundError(AgentOrchestratorError):
    """Raised when agent is not found"""
    pass


class WorkflowExecutionError(AgentOrchestratorError):
    """Raised when workflow execution fails"""
    pass


class TaskExecutionError(AgentOrchestratorError):
    """Raised when task execution fails"""
    pass


class AgentOrchestrator(LoggerMixin):
    """
    Enterprise multi-agent AI orchestration system
    
    Features:
    - Multi-provider AI agent management
    - Workflow orchestration with dependencies
    - Task queuing and parallel execution
    - Resource management and cost tracking
    - Error handling and retry mechanisms
    - Agent specialization and routing
    - Performance monitoring and analytics
    """
    
    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        default_timeout: int = 300,
        enable_caching: bool = True
    ):
        """
        Initialize agent orchestrator
        
        Args:
            max_concurrent_tasks: Maximum concurrent task execution
            default_timeout: Default task timeout in seconds
            enable_caching: Enable response caching
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.default_timeout = default_timeout
        self.enable_caching = enable_caching
        
        # Agent management
        self._agents: Dict[str, AgentConfig] = {}
        self._agent_locks: Dict[str, asyncio.Lock] = {}
        
        # Workflow management
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        
        # Task queue and execution
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # HTTP client for API calls
        self._http_client = httpx.AsyncClient(timeout=30.0)
        
        # Response cache
        self._response_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._cache_ttl = 300  # 5 minutes
        
        self.logger.info(
            "AgentOrchestrator initialized",
            extra={
                "max_concurrent_tasks": max_concurrent_tasks,
                "default_timeout": default_timeout,
                "enable_caching": enable_caching
            }
        )
    
    async def register_agent(self, agent_config: AgentConfig) -> None:
        """
        Register an AI agent
        
        Args:
            agent_config: Agent configuration
        """
        # Validate API keys based on provider
        await self._validate_agent_provider(agent_config)
        
        self._agents[agent_config.id] = agent_config
        self._agent_locks[agent_config.id] = asyncio.Lock()
        
        self.logger.info(
            "Agent registered successfully",
            extra={
                "agent_id": agent_config.id,
                "agent_name": agent_config.name,
                "agent_type": agent_config.agent_type.value,
                "provider": agent_config.provider.value,
                "model": agent_config.model
            }
        )
    
    async def execute_task(
        self,
        task: TaskDefinition,
        agent_id: Optional[str] = None
    ) -> TaskResult:
        """
        Execute a single task
        
        Args:
            task: Task definition
            agent_id: Optional specific agent ID
            
        Returns:
            Task execution result
        """
        # Select agent if not specified
        if not agent_id:
            agent_id = await self._select_agent(task)
        
        if agent_id not in self._agents:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        agent = self._agents[agent_id]
        
        # Create task result
        result = TaskResult(
            task_id=task.id,
            agent_id=agent_id,
            status=TaskStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )
        
        # Check cache first
        if self.enable_caching:
            cached_result = await self._get_cached_result(task, agent_id)
            if cached_result:
                self.logger.info(
                    "Using cached result for task",
                    extra={"task_id": task.id, "agent_id": agent_id}
                )
                return cached_result
        
        try:
            async with self._agent_locks[agent_id]:
                start_time = datetime.now()
                
                # Execute task with agent
                output = await self._execute_with_agent(task, agent)
                
                # Calculate execution time
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                # Update result
                result.status = TaskStatus.COMPLETED
                result.output = output
                result.execution_time = execution_time
                result.completed_at = end_time
                
                # Validate output if schema provided
                if task.output_schema:
                    validation_results = await self._validate_output(output, task.output_schema)
                    result.validation_results = validation_results
                    
                    if any(not r.get("valid", True) for r in validation_results):
                        result.status = TaskStatus.FAILED
                        result.error = "Output validation failed"
                
                # Cache result
                if self.enable_caching and result.status == TaskStatus.COMPLETED:
                    await self._cache_result(task, agent_id, result)
        
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            
            self.logger.error(
                "Task execution failed",
                extra={
                    "task_id": task.id,
                    "agent_id": agent_id,
                    "error": str(e)
                },
                exc_info=True
            )
        
        self.logger.info(
            "Task execution completed",
            extra={
                "task_id": task.id,
                "agent_id": agent_id,
                "status": result.status.value,
                "execution_time": result.execution_time,
                "tokens_used": result.tokens_used,
                "cost": result.cost
            }
        )
        
        return result
    
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        execution_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecution:
        """
        Execute a workflow with task dependencies
        
        Args:
            workflow: Workflow definition
            execution_context: Additional execution context
            
        Returns:
            Workflow execution state
        """
        execution_id = str(uuid.uuid4())
        
        # Create execution state
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow.id,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            context={**workflow.global_context, **(execution_context or {})}
        )
        
        self._executions[execution_id] = execution
        
        self.logger.info(
            "Starting workflow execution",
            extra={
                "workflow_id": workflow.id,
                "execution_id": execution_id,
                "task_count": len(workflow.tasks)
            }
        )
        
        try:
            # Build dependency graph
            task_graph = self._build_task_dependency_graph(workflow.tasks)
            
            # Execute tasks in dependency order
            completed_tasks = set()
            failed_tasks = set()
            
            while len(completed_tasks) + len(failed_tasks) < len(workflow.tasks):
                # Find tasks that can be executed (dependencies met)
                ready_tasks = []
                for task in workflow.tasks:
                    if (task.id not in completed_tasks and 
                        task.id not in failed_tasks and
                        all(dep in completed_tasks for dep in task.dependencies)):
                        ready_tasks.append(task)
                
                if not ready_tasks:
                    # Check if we're stuck due to failed dependencies
                    remaining_tasks = [
                        t for t in workflow.tasks 
                        if t.id not in completed_tasks and t.id not in failed_tasks
                    ]
                    
                    if remaining_tasks:
                        execution.status = WorkflowStatus.FAILED
                        execution.error = "Workflow stuck: no tasks can proceed due to failed dependencies"
                        break
                
                # Execute ready tasks in parallel
                task_futures = []
                for task in ready_tasks:
                    # Update task context with execution context
                    task.context.update(execution.context)
                    
                    # Add outputs from completed tasks
                    for completed_task_id in completed_tasks:
                        if completed_task_id in execution.task_results:
                            task_result = execution.task_results[completed_task_id]
                            task.context[f"task_{completed_task_id}_output"] = task_result.output
                    
                    future = asyncio.create_task(self.execute_task(task))
                    task_futures.append((task.id, future))
                
                # Wait for all tasks to complete
                for task_id, future in task_futures:
                    try:
                        result = await future
                        execution.task_results[task_id] = result
                        execution.total_cost += result.cost
                        execution.total_tokens += result.tokens_used
                        
                        if result.status == TaskStatus.COMPLETED:
                            completed_tasks.add(task_id)
                        else:
                            failed_tasks.add(task_id)
                            execution.failed_tasks.append(task_id)
                    
                    except Exception as e:
                        # Create error result
                        error_result = TaskResult(
                            task_id=task_id,
                            agent_id="unknown",
                            status=TaskStatus.FAILED,
                            error=str(e),
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc)
                        )
                        execution.task_results[task_id] = error_result
                        failed_tasks.add(task_id)
                        execution.failed_tasks.append(task_id)
            
            # Determine final status
            if failed_tasks:
                execution.status = WorkflowStatus.FAILED
                execution.error = f"Workflow failed with {len(failed_tasks)} failed tasks"
            else:
                execution.status = WorkflowStatus.COMPLETED
            
            execution.completed_at = datetime.now(timezone.utc)
            
            # Execute success/failure hooks
            if execution.status == WorkflowStatus.COMPLETED and workflow.on_success:
                await self._execute_workflow_hooks(workflow.on_success, execution)
            elif execution.status == WorkflowStatus.FAILED and workflow.on_failure:
                await self._execute_workflow_hooks(workflow.on_failure, execution)
        
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            
            self.logger.error(
                "Workflow execution failed",
                extra={
                    "workflow_id": workflow.id,
                    "execution_id": execution_id,
                    "error": str(e)
                },
                exc_info=True
            )
        
        self.logger.info(
            "Workflow execution completed",
            extra={
                "workflow_id": workflow.id,
                "execution_id": execution_id,
                "status": execution.status.value,
                "completed_tasks": len(completed_tasks) if 'completed_tasks' in locals() else 0,
                "failed_tasks": len(failed_tasks) if 'failed_tasks' in locals() else 0,
                "total_cost": execution.total_cost,
                "total_tokens": execution.total_tokens
            }
        )
        
        return execution
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        tasks: List[TaskDefinition],
        global_context: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None
    ) -> WorkflowDefinition:
        """
        Create a new workflow
        
        Args:
            name: Workflow name
            description: Workflow description
            tasks: List of task definitions
            global_context: Global context for all tasks
            created_by: Creator identifier
            
        Returns:
            Created workflow definition
        """
        workflow_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Validate task dependencies
        task_ids = {task.id for task in tasks}
        for task in tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    raise WorkflowExecutionError(
                        f"Task {task.id} has invalid dependency: {dep}"
                    )
        
        # Check for circular dependencies
        if self._has_circular_dependencies(tasks):
            raise WorkflowExecutionError("Workflow has circular dependencies")
        
        workflow = WorkflowDefinition(
            id=workflow_id,
            name=name,
            description=description,
            tasks=tasks,
            global_context=global_context or {},
            created_at=now,
            updated_at=now,
            created_by=created_by
        )
        
        self._workflows[workflow_id] = workflow
        
        self.logger.info(
            "Workflow created successfully",
            extra={
                "workflow_id": workflow_id,
                "workflow_name": name,
                "task_count": len(tasks),
                "created_by": created_by
            }
        )
        
        return workflow
    
    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent performance metrics
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent metrics
        """
        if agent_id not in self._agents:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        # Calculate metrics from completed tasks
        agent_tasks = []
        for execution in self._executions.values():
            for task_result in execution.task_results.values():
                if task_result.agent_id == agent_id:
                    agent_tasks.append(task_result)
        
        if not agent_tasks:
            return {
                "agent_id": agent_id,
                "total_tasks": 0,
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "total_cost": 0.0,
                "total_tokens": 0
            }
        
        successful_tasks = [t for t in agent_tasks if t.status == TaskStatus.COMPLETED]
        
        metrics = {
            "agent_id": agent_id,
            "total_tasks": len(agent_tasks),
            "successful_tasks": len(successful_tasks),
            "failed_tasks": len(agent_tasks) - len(successful_tasks),
            "success_rate": len(successful_tasks) / len(agent_tasks),
            "avg_execution_time": sum(t.execution_time for t in agent_tasks) / len(agent_tasks),
            "total_cost": sum(t.cost for t in agent_tasks),
            "total_tokens": sum(t.tokens_used for t in agent_tasks),
            "avg_cost_per_task": sum(t.cost for t in agent_tasks) / len(agent_tasks),
            "avg_tokens_per_task": sum(t.tokens_used for t in agent_tasks) / len(agent_tasks),
        }
        
        return metrics
    
    async def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        provider: Optional[AgentProvider] = None,
        active_only: bool = True
    ) -> List[AgentConfig]:
        """
        List registered agents
        
        Args:
            agent_type: Filter by agent type
            provider: Filter by provider
            active_only: Only return active agents
            
        Returns:
            List of agent configurations
        """
        agents = list(self._agents.values())
        
        if agent_type:
            agents = [a for a in agents if a.agent_type == agent_type]
        
        if provider:
            agents = [a for a in agents if a.provider == provider]
        
        if active_only:
            agents = [a for a in agents if a.is_active]
        
        return agents
    
    async def _validate_agent_provider(self, agent_config: AgentConfig) -> None:
        """Validate agent provider configuration"""
        if agent_config.provider == AgentProvider.OPENAI:
            if not settings.OPENAI_API_KEY:
                raise AgentOrchestratorError("OpenAI API key not configured")
        elif agent_config.provider == AgentProvider.ANTHROPIC:
            if not settings.ANTHROPIC_API_KEY:
                raise AgentOrchestratorError("Anthropic API key not configured")
        elif agent_config.provider == AgentProvider.GOOGLE:
            if not settings.GEMINI_API_KEY:
                raise AgentOrchestratorError("Google API key not configured")
    
    async def _select_agent(self, task: TaskDefinition) -> str:
        """
        Select best agent for task based on type and availability
        
        Args:
            task: Task definition
            
        Returns:
            Selected agent ID
        """
        # Find agents that match task type
        matching_agents = [
            agent for agent in self._agents.values()
            if (agent.agent_type == task.agent_type or agent.agent_type == AgentType.CUSTOM)
            and agent.is_active
        ]
        
        if not matching_agents:
            raise AgentNotFoundError(f"No active agents found for task type {task.agent_type}")
        
        # Simple selection strategy - choose first available
        # Can be enhanced with load balancing, cost optimization, etc.
        for agent in matching_agents:
            # Check if agent is currently available
            if agent.id not in self._agent_locks or not self._agent_locks[agent.id].locked():
                return agent.id
        
        # If all agents are busy, return the first one (will wait for availability)
        return matching_agents[0].id
    
    async def _execute_with_agent(
        self,
        task: TaskDefinition,
        agent: AgentConfig
    ) -> Any:
        """Execute task with specific agent"""
        
        # Prepare messages based on provider
        if agent.provider == AgentProvider.OPENAI:
            return await self._execute_openai(task, agent)
        elif agent.provider == AgentProvider.ANTHROPIC:
            return await self._execute_anthropic(task, agent)
        elif agent.provider == AgentProvider.GOOGLE:
            return await self._execute_google(task, agent)
        else:
            raise AgentOrchestratorError(f"Unsupported provider: {agent.provider}")
    
    async def _execute_openai(self, task: TaskDefinition, agent: AgentConfig) -> Any:
        """Execute task using OpenAI API"""
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Prepare messages
        messages = []
        if agent.system_prompt:
            messages.append({"role": "system", "content": agent.system_prompt})
        
        # Add task context and input
        user_message = f"Task: {task.description}\n"
        if task.input_data:
            user_message += f"Input Data: {json.dumps(task.input_data, indent=2)}\n"
        if task.context:
            user_message += f"Context: {json.dumps(task.context, indent=2)}\n"
        
        messages.append({"role": "user", "content": user_message})
        
        payload = {
            "model": agent.model,
            "messages": messages,
            "max_tokens": agent.max_tokens,
            "temperature": agent.temperature,
            **agent.custom_parameters
        }
        
        async with self._http_client as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=agent.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    async def _execute_anthropic(self, task: TaskDefinition, agent: AgentConfig) -> Any:
        """Execute task using Anthropic API"""
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Prepare prompt
        prompt = f"Task: {task.description}\n"
        if task.input_data:
            prompt += f"Input Data: {json.dumps(task.input_data, indent=2)}\n"
        if task.context:
            prompt += f"Context: {json.dumps(task.context, indent=2)}\n"
        
        if agent.system_prompt:
            prompt = f"{agent.system_prompt}\n\n{prompt}"
        
        payload = {
            "model": agent.model,
            "max_tokens": agent.max_tokens,
            "temperature": agent.temperature,
            "messages": [{"role": "user", "content": prompt}],
            **agent.custom_parameters
        }
        
        async with self._http_client as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=agent.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            return result["content"][0]["text"]
    
    async def _execute_google(self, task: TaskDefinition, agent: AgentConfig) -> Any:
        """Execute task using Google Gemini API"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # Prepare prompt
        prompt = f"Task: {task.description}\n"
        if task.input_data:
            prompt += f"Input Data: {json.dumps(task.input_data, indent=2)}\n"
        if task.context:
            prompt += f"Context: {json.dumps(task.context, indent=2)}\n"
        
        if agent.system_prompt:
            prompt = f"{agent.system_prompt}\n\n{prompt}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": agent.temperature,
                "maxOutputTokens": agent.max_tokens,
                **agent.custom_parameters
            }
        }
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{agent.model}:generateContent?key={settings.GEMINI_API_KEY}"
        
        async with self._http_client as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=agent.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
    
    def _build_task_dependency_graph(self, tasks: List[TaskDefinition]) -> Dict[str, Set[str]]:
        """Build task dependency graph"""
        graph = {}
        for task in tasks:
            graph[task.id] = set(task.dependencies)
        return graph
    
    def _has_circular_dependencies(self, tasks: List[TaskDefinition]) -> bool:
        """Check for circular dependencies in task list"""
        graph = self._build_task_dependency_graph(tasks)
        
        # Use DFS to detect cycles
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {task_id: WHITE for task_id in graph}
        
        def has_cycle(node: str) -> bool:
            if color[node] == GRAY:
                return True
            if color[node] == BLACK:
                return False
            
            color[node] = GRAY
            for neighbor in graph[node]:
                if neighbor in color and has_cycle(neighbor):
                    return True
            color[node] = BLACK
            return False
        
        return any(has_cycle(node) for node in graph if color[node] == WHITE)
    
    async def _validate_output(
        self,
        output: Any,
        schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate task output against schema"""
        results = []
        
        try:
            import jsonschema
            jsonschema.validate(output, schema)
            results.append({"valid": True, "message": "Output validates against schema"})
        except ImportError:
            results.append({"valid": False, "message": "jsonschema not available"})
        except jsonschema.ValidationError as e:
            results.append({"valid": False, "message": f"Validation error: {e.message}"})
        except Exception as e:
            results.append({"valid": False, "message": f"Validation error: {e}"})
        
        return results
    
    async def _get_cached_result(
        self,
        task: TaskDefinition,
        agent_id: str
    ) -> Optional[TaskResult]:
        """Get cached result if available and not expired"""
        cache_key = self._generate_cache_key(task, agent_id)
        
        if cache_key in self._response_cache:
            cached_result, timestamp = self._response_cache[cache_key]
            
            # Check if cache is still valid
            if (datetime.now(timezone.utc) - timestamp).total_seconds() < self._cache_ttl:
                return cached_result
            else:
                # Remove expired cache entry
                del self._response_cache[cache_key]
        
        return None
    
    async def _cache_result(
        self,
        task: TaskDefinition,
        agent_id: str,
        result: TaskResult
    ) -> None:
        """Cache task result"""
        cache_key = self._generate_cache_key(task, agent_id)
        self._response_cache[cache_key] = (result, datetime.now(timezone.utc))
    
    def _generate_cache_key(self, task: TaskDefinition, agent_id: str) -> str:
        """Generate cache key for task and agent combination"""
        import hashlib
        
        key_data = {
            "agent_id": agent_id,
            "task_name": task.name,
            "input_data": task.input_data,
            "context": task.context
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def _execute_workflow_hooks(
        self,
        hooks: List[Dict[str, Any]],
        execution: WorkflowExecution
    ) -> None:
        """Execute workflow success/failure hooks"""
        for hook in hooks:
            try:
                # Simple webhook implementation
                if hook.get("type") == "webhook":
                    url = hook.get("url")
                    if url:
                        payload = {
                            "workflow_id": execution.workflow_id,
                            "execution_id": execution.id,
                            "status": execution.status.value,
                            "total_cost": execution.total_cost,
                            "total_tokens": execution.total_tokens
                        }
                        
                        async with self._http_client as client:
                            await client.post(url, json=payload, timeout=10)
            except Exception as e:
                self.logger.warning(f"Failed to execute workflow hook: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self._http_client.aclose()
        
        # Cancel running tasks
        for task in self._running_tasks.values():
            if not task.done():
                task.cancel()
        
        self.logger.info("AgentOrchestrator cleanup completed")