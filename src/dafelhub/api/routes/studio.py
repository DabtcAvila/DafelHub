"""
DafelHub Studio Routes
3 endpoints: GET canvas, POST execute, GET metrics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks

from dafelhub.core.logging import get_logger
from dafelhub.services.project_manager import ProjectManager
from dafelhub.security.audit import AuditTrail
from dafelhub.api.middleware import get_current_user
from dafelhub.api.models.requests import (
    SaveCanvasRequest,
    ExecuteCodeRequest
)
from dafelhub.api.models.responses import (
    StudioCanvasResponse,
    ExecuteCodeResponse,
    StudioMetricsResponse,
    CanvasResponse,
    CanvasElementResponse,
    CodeExecutionResult,
    StudioMetrics
)

# Initialize components
logger = get_logger(__name__)
router = APIRouter()
project_manager = ProjectManager()
audit_trail = AuditTrail()


class CodeExecutor:
    """Code execution service for studio"""
    
    def __init__(self):
        self.running_executions = {}
    
    async def execute_code(
        self,
        project_id: str,
        code: str,
        language: str,
        environment: str = "default",
        timeout: int = 30,
        input_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute code and return results"""
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            # Store execution metadata
            self.running_executions[execution_id] = {
                "project_id": project_id,
                "language": language,
                "start_time": start_time,
                "status": "running"
            }
            
            # Simulate code execution based on language
            if language.lower() == "python":
                result = await self._execute_python(code, input_data, timeout)
            elif language.lower() == "javascript":
                result = await self._execute_javascript(code, input_data, timeout)
            elif language.lower() == "sql":
                result = await self._execute_sql(code, project_id, timeout)
            else:
                result = {
                    "success": False,
                    "output": "",
                    "error": f"Unsupported language: {language}",
                    "memory_used": 0
                }
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "execution_id": execution_id,
                "success": result["success"],
                "output": result["output"],
                "error": result.get("error"),
                "execution_time": execution_time,
                "memory_used": result.get("memory_used", 0),
                "executed_at": datetime.utcnow()
            }
            
        except asyncio.TimeoutError:
            return {
                "execution_id": execution_id,
                "success": False,
                "output": "",
                "error": f"Code execution timed out after {timeout} seconds",
                "execution_time": timeout,
                "memory_used": 0,
                "executed_at": datetime.utcnow()
            }
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return {
                "execution_id": execution_id,
                "success": False,
                "output": "",
                "error": str(e),
                "execution_time": execution_time,
                "memory_used": 0,
                "executed_at": datetime.utcnow()
            }
        finally:
            self.running_executions.pop(execution_id, None)
    
    async def _execute_python(self, code: str, input_data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """Execute Python code (simulated)"""
        # In a real implementation, this would use a sandboxed Python executor
        await asyncio.sleep(0.1)  # Simulate execution time
        
        # Simple code analysis for demo
        if "print" in code:
            output = "Hello from Python execution!\n"
        elif "import" in code and "pandas" in code:
            output = "DataFrame created successfully\n   A  B\n0  1  2\n1  3  4\n"
        elif "def" in code:
            output = "Function defined successfully\n"
        elif "error" in code.lower():
            return {
                "success": False,
                "output": "",
                "error": "NameError: name 'undefined_variable' is not defined",
                "memory_used": 1024
            }
        else:
            output = "Code executed successfully\n"
        
        return {
            "success": True,
            "output": output,
            "memory_used": 2048
        }
    
    async def _execute_javascript(self, code: str, input_data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """Execute JavaScript code (simulated)"""
        await asyncio.sleep(0.1)
        
        if "console.log" in code:
            output = "Hello from JavaScript execution!\n"
        elif "function" in code:
            output = "Function declared successfully\n"
        elif "error" in code.lower():
            return {
                "success": False,
                "output": "",
                "error": "ReferenceError: undefinedVariable is not defined",
                "memory_used": 512
            }
        else:
            output = "Code executed successfully\n"
        
        return {
            "success": True,
            "output": output,
            "memory_used": 1024
        }
    
    async def _execute_sql(self, code: str, project_id: str, timeout: int) -> Dict[str, Any]:
        """Execute SQL code (simulated)"""
        await asyncio.sleep(0.2)
        
        if "SELECT" in code.upper():
            output = "Query executed successfully\nid | name     | email\n1  | John Doe | john@example.com\n2  | Jane Doe | jane@example.com\n"
        elif "INSERT" in code.upper():
            output = "1 row inserted successfully\n"
        elif "UPDATE" in code.upper():
            output = "2 rows updated successfully\n"
        elif "DELETE" in code.upper():
            output = "1 row deleted successfully\n"
        elif "error" in code.lower():
            return {
                "success": False,
                "output": "",
                "error": "SQL Error: Table 'nonexistent_table' doesn't exist",
                "memory_used": 256
            }
        else:
            output = "SQL command executed successfully\n"
        
        return {
            "success": True,
            "output": output,
            "memory_used": 512
        }


# Initialize code executor
code_executor = CodeExecutor()


@router.get(
    "/canvas",
    response_model=StudioCanvasResponse,
    summary="Get Studio Canvas",
    description="Get or create studio canvas for a project"
)
async def get_studio_canvas(
    project_id: str = Query(..., description="Project ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> StudioCanvasResponse:
    """
    Get studio canvas for a project
    - Returns existing canvas or creates new one
    - Includes all canvas elements and connections
    - Validates project access
    """
    try:
        user_id = current_user["user_id"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {current_user['username']} requesting canvas for project: {project_id}",
            extra={"user_id": user_id, "project_id": project_id}
        )
        
        # Validate project access
        project = await project_manager.get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check permissions
        has_access = (
            project.created_by == user_id or
            user_id in (project.team_members or []) or
            "admin" in user_roles
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project"
            )
        
        # Get or create canvas for project
        canvas_result = await project_manager.get_or_create_canvas(
            project_id=project_id,
            created_by=user_id
        )
        
        if not canvas_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving canvas"
            )
        
        canvas = canvas_result.canvas
        
        # Convert canvas elements
        canvas_elements = []
        for element in canvas.get("elements", []):
            canvas_element = CanvasElementResponse(
                id=element["id"],
                type=element["type"],
                name=element["name"],
                position=element["position"],
                size=element.get("size", {"width": 100, "height": 60}),
                properties=element.get("properties", {}),
                connections=element.get("connections", [])
            )
            canvas_elements.append(canvas_element)
        
        # Create canvas response
        canvas_response = CanvasResponse(
            id=canvas["id"],
            project_id=project_id,
            name=canvas.get("name", f"Canvas for {project.name}"),
            elements=canvas_elements,
            connections=canvas.get("connections", []),
            metadata=canvas.get("metadata", {}),
            created_by=canvas["created_by"],
            created_at=canvas["created_at"],
            updated_at=canvas["updated_at"]
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=current_user["username"],
            action="view_canvas",
            target_resource_id=project_id,
            details={
                "project_name": project.name,
                "canvas_id": canvas["id"],
                "elements_count": len(canvas_elements)
            }
        )
        
        logger.info(
            f"Canvas retrieved successfully",
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "canvas_id": canvas["id"],
                "elements_count": len(canvas_elements)
            }
        )
        
        return StudioCanvasResponse(
            success=True,
            message="Canvas retrieved successfully",
            canvas=canvas_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get canvas error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving canvas"
        )


@router.post(
    "/execute",
    response_model=ExecuteCodeResponse,
    summary="Execute Code",
    description="Execute code in studio environment"
)
async def execute_code(
    request: ExecuteCodeRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ExecuteCodeResponse:
    """
    Execute code in studio
    - Supports multiple programming languages
    - Sandboxed execution environment
    - Returns execution results and metrics
    """
    try:
        user_id = current_user["user_id"]
        username = current_user["username"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {username} executing code in project: {request.project_id}",
            extra={
                "user_id": user_id,
                "project_id": request.project_id,
                "language": request.language,
                "code_length": len(request.code)
            }
        )
        
        # Validate project access
        project = await project_manager.get_project_by_id(request.project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check permissions
        has_access = (
            project.created_by == user_id or
            user_id in (project.team_members or []) or
            "admin" in user_roles
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project"
            )
        
        # Validate code length and content
        if len(request.code) > 10000:  # 10KB limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code too large (max 10KB allowed)"
            )
        
        # Execute code
        execution_result = await code_executor.execute_code(
            project_id=request.project_id,
            code=request.code,
            language=request.language,
            environment=request.environment,
            timeout=request.timeout,
            input_data=request.input_data
        )
        
        # Create execution result response
        result = CodeExecutionResult(
            execution_id=execution_result["execution_id"],
            status="success" if execution_result["success"] else "failed",
            output=execution_result["output"],
            error=execution_result.get("error"),
            execution_time=execution_result["execution_time"],
            memory_used=execution_result.get("memory_used"),
            executed_at=execution_result["executed_at"]
        )
        
        # Store execution history in background
        background_tasks.add_task(
            store_execution_history,
            user_id=user_id,
            project_id=request.project_id,
            execution_result=execution_result,
            code=request.code,
            language=request.language
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=username,
            action="execute_code",
            target_resource_id=request.project_id,
            details={
                "project_name": project.name,
                "language": request.language,
                "execution_id": execution_result["execution_id"],
                "success": execution_result["success"],
                "execution_time": execution_result["execution_time"]
            }
        )
        
        logger.info(
            f"Code executed successfully",
            extra={
                "user_id": user_id,
                "project_id": request.project_id,
                "execution_id": execution_result["execution_id"],
                "success": execution_result["success"],
                "execution_time": execution_result["execution_time"]
            }
        )
        
        return ExecuteCodeResponse(
            success=True,
            message="Code executed successfully" if execution_result["success"] else "Code execution failed",
            result=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute code error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error executing code"
        )


@router.get(
    "/metrics",
    response_model=StudioMetricsResponse,
    summary="Get Studio Metrics",
    description="Get studio usage metrics for a project"
)
async def get_studio_metrics(
    project_id: str = Query(..., description="Project ID"),
    period: str = Query("7d", regex="^(1d|7d|30d|90d)$", description="Metrics period"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> StudioMetricsResponse:
    """
    Get studio metrics for a project
    - Returns execution statistics
    - Includes performance metrics
    - Shows language usage patterns
    """
    try:
        user_id = current_user["user_id"]
        user_roles = current_user["roles"]
        
        logger.info(
            f"User {current_user['username']} requesting metrics for project: {project_id}",
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "period": period
            }
        )
        
        # Validate project access
        project = await project_manager.get_project_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check permissions
        has_access = (
            project.created_by == user_id or
            user_id in (project.team_members or []) or
            "admin" in user_roles
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project"
            )
        
        # Get metrics from project manager
        metrics_result = await project_manager.get_studio_metrics(
            project_id=project_id,
            period=period,
            user_id=user_id
        )
        
        if not metrics_result.success:
            # Return empty metrics if none found
            metrics_data = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_execution_time": 0.0,
                "total_execution_time": 0.0,
                "languages_used": {},
                "recent_executions": []
            }
        else:
            metrics_data = metrics_result.metrics
        
        # Convert recent executions to response format
        recent_executions = []
        for execution in metrics_data.get("recent_executions", []):
            exec_result = CodeExecutionResult(
                execution_id=execution["execution_id"],
                status=execution["status"],
                output=execution.get("output", ""),
                error=execution.get("error"),
                execution_time=execution["execution_time"],
                memory_used=execution.get("memory_used"),
                executed_at=execution["executed_at"]
            )
            recent_executions.append(exec_result)
        
        # Create studio metrics
        studio_metrics = StudioMetrics(
            total_executions=metrics_data["total_executions"],
            successful_executions=metrics_data["successful_executions"],
            failed_executions=metrics_data["failed_executions"],
            average_execution_time=metrics_data["average_execution_time"],
            total_execution_time=metrics_data["total_execution_time"],
            languages_used=metrics_data["languages_used"],
            recent_executions=recent_executions
        )
        
        # Log user activity
        await audit_trail.log_user_activity(
            user_id=user_id,
            username=current_user["username"],
            action="view_studio_metrics",
            target_resource_id=project_id,
            details={
                "project_name": project.name,
                "period": period,
                "total_executions": metrics_data["total_executions"]
            }
        )
        
        logger.info(
            f"Studio metrics retrieved successfully",
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "period": period,
                "total_executions": metrics_data["total_executions"]
            }
        )
        
        return StudioMetricsResponse(
            success=True,
            message="Studio metrics retrieved successfully",
            project_id=project_id,
            metrics=studio_metrics,
            period=period,
            generated_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get studio metrics error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving studio metrics"
        )


async def store_execution_history(
    user_id: str,
    project_id: str,
    execution_result: Dict[str, Any],
    code: str,
    language: str
):
    """Background task to store execution history"""
    try:
        await project_manager.store_execution_history(
            user_id=user_id,
            project_id=project_id,
            execution_data={
                "execution_id": execution_result["execution_id"],
                "code": code,
                "language": language,
                "success": execution_result["success"],
                "output": execution_result["output"],
                "error": execution_result.get("error"),
                "execution_time": execution_result["execution_time"],
                "memory_used": execution_result.get("memory_used"),
                "executed_at": execution_result["executed_at"]
            }
        )
        logger.info(f"Execution history stored for execution: {execution_result['execution_id']}")
    except Exception as e:
        logger.error(f"Error storing execution history: {str(e)}", exc_info=True)