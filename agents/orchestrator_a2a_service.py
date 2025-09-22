"""
A2A Service wrapper for the Orchestrator Agent

This module exposes the Orchestrator agent as an A2A service that coordinates
the entire incident response workflow between all other agents in the system.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider
from a2a.server.agent_execution import AgentExecutor, RequestContext, SimpleRequestContextBuilder
from a2a.server.tasks import TaskStore, InMemoryTaskStore
from a2a.server.events import QueueManager, InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AFastAPIApplication

# Import Orchestrator agent
from .orchestrator_agent import OrchestratorAgent, AgentConfig, FailurePayload, WorkflowState

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow status enumeration"""
    STARTED = "started"
    ANALYZING = "analyzing"
    PROPOSING = "proposing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestratorAgentExecutor(AgentExecutor):
    """
    A2A AgentExecutor implementation that wraps the Orchestrator agent
    """

    def __init__(self, orchestrator_agent: OrchestratorAgent):
        self.orchestrator_agent = orchestrator_agent
        logger.info("Orchestrator AgentExecutor initialized")

    async def execute(self, task_id: str, request: Dict[str, Any], context: Optional[RequestContext] = None) -> Dict[str, Any]:
        """
        Execute an orchestration task

        Args:
            task_id: Unique task identifier
            request: Request payload containing orchestration data
            context: Optional request context

        Returns:
            Orchestration result
        """
        try:
            logger.info(f"Executing orchestration task {task_id}")

            # Route request based on action type
            action = request.get("action")
            
            if action == "start_incident_workflow":
                return await self._handle_start_incident_workflow(task_id, request)
            elif action == "update_workflow_status":
                return await self._handle_update_workflow_status(task_id, request)
            elif action == "get_workflow_status":
                return await self._handle_get_workflow_status(task_id, request)
            elif action == "cancel_workflow":
                return await self._handle_cancel_workflow(task_id, request)
            elif action == "get_active_workflows":
                return await self._handle_get_active_workflows(task_id, request)
            elif action == "health_check":
                return await self._handle_health_check(task_id, request)
            else:
                raise ValueError(f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Orchestration task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "error": str(e),
                "status": "failed",
                "message": f"Orchestration task failed: {str(e)}"
            }

    async def _handle_start_incident_workflow(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle starting a new incident workflow"""
        try:
            failure_data = request.get("failure_payload", {})
            if not failure_data:
                raise ValueError("Missing failure_payload in request")

            # Create FailurePayload object
            failure_payload = FailurePayload(
                test_title=failure_data.get("test_title", "Unknown Test"),
                status=failure_data.get("status", "failed"),
                error=failure_data.get("error", {}),
                retries=failure_data.get("retries", 0),
                trace_id=failure_data.get("trace_id", task_id),
                video_url=failure_data.get("video_url"),
                trace_url=failure_data.get("trace_url"),
                timestamp=failure_data.get("timestamp", datetime.now().isoformat())
            )

            # Start workflow via webhook handler
            workflow_id = await self.orchestrator_agent._handle_failure_webhook(failure_payload)

            result = {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "started",
                "message": f"Incident workflow {workflow_id} started successfully",
                "incident_id": failure_payload.trace_id,
                "started_at": datetime.now().isoformat()
            }

            logger.info(f"Orchestration task {task_id} completed: workflow started")
            return result

        except Exception as e:
            logger.error(f"Failed to start incident workflow: {e}")
            raise

    async def _handle_update_workflow_status(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle updating workflow status"""
        try:
            workflow_id = request.get("workflow_id")
            status = request.get("status")
            result_data = request.get("result_data", {})

            if not workflow_id or not status:
                raise ValueError("Missing workflow_id or status in request")

            # Update workflow based on status
            if status == "analysis_complete":
                await self.orchestrator_agent._handle_analysis_complete(workflow_id, result_data)
            elif status == "remediation_proposed":
                await self.orchestrator_agent._handle_remediation_proposed(workflow_id, result_data)
            elif status == "approval_received":
                await self.orchestrator_agent._handle_approval_received(workflow_id, result_data)
            elif status == "execution_complete":
                await self.orchestrator_agent._handle_execution_complete(workflow_id, result_data)
            elif status == "failed":
                await self.orchestrator_agent._fail_workflow(workflow_id, result_data.get("error_message", "Unknown error"))
            else:
                raise ValueError(f"Unknown status: {status}")

            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "updated",
                "message": f"Workflow {workflow_id} status updated to {status}"
            }

        except Exception as e:
            logger.error(f"Failed to update workflow status: {e}")
            raise

    async def _handle_get_workflow_status(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle getting workflow status"""
        try:
            workflow_id = request.get("workflow_id")
            if not workflow_id:
                raise ValueError("Missing workflow_id in request")

            workflow_state = self.orchestrator_agent.active_workflows.get(workflow_id)
            if not workflow_state:
                return {
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "status": "not_found",
                    "message": f"Workflow {workflow_id} not found"
                }

            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": workflow_state.status,
                "incident_id": workflow_state.incident_id,
                "created_at": workflow_state.created_at.isoformat(),
                "updated_at": workflow_state.updated_at.isoformat(),
                "analysis_result": workflow_state.analysis_result,
                "remediation_action": workflow_state.remediation_action,
                "approval_response": workflow_state.approval_response,
                "execution_result": workflow_state.execution_result,
                "error_message": workflow_state.error_message
            }

        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            raise

    async def _handle_cancel_workflow(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cancelling a workflow"""
        try:
            workflow_id = request.get("workflow_id")
            reason = request.get("reason", "Cancelled by user")

            if not workflow_id:
                raise ValueError("Missing workflow_id in request")

            await self.orchestrator_agent._fail_workflow(workflow_id, f"Cancelled: {reason}")

            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "cancelled",
                "message": f"Workflow {workflow_id} cancelled: {reason}"
            }

        except Exception as e:
            logger.error(f"Failed to cancel workflow: {e}")
            raise

    async def _handle_get_active_workflows(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle getting all active workflows"""
        try:
            active_workflows = []
            for workflow_id, workflow_state in self.orchestrator_agent.active_workflows.items():
                active_workflows.append({
                    "workflow_id": workflow_id,
                    "incident_id": workflow_state.incident_id,
                    "status": workflow_state.status,
                    "created_at": workflow_state.created_at.isoformat(),
                    "updated_at": workflow_state.updated_at.isoformat(),
                    "test_title": workflow_state.failure_payload.test_title
                })

            return {
                "task_id": task_id,
                "status": "success",
                "active_workflows": active_workflows,
                "total_count": len(active_workflows)
            }

        except Exception as e:
            logger.error(f"Failed to get active workflows: {e}")
            raise

    async def _handle_health_check(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check request"""
        try:
            health_status = await self.orchestrator_agent.health_check()

            return {
                "task_id": task_id,
                "status": "healthy" if health_status else "unhealthy",
                "uptime_seconds": (datetime.now() - self.orchestrator_agent.start_time).total_seconds(),
                "active_workflows": len(self.orchestrator_agent.active_workflows),
                "discovered_agents": {
                    "rca_agents": len(self.orchestrator_agent.rca_agents),
                    "remediation_agents": len(self.orchestrator_agent.remediation_agents),
                    "approval_agents": len(self.orchestrator_agent.approval_agents)
                },
                "webhook_server_running": self.orchestrator_agent.webhook_server is not None
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    async def cancel(self, task_id: str) -> None:
        """
        Cancel a running task

        Args:
            task_id: Unique task identifier to cancel
        """
        logger.info(f"Cancelling orchestration task {task_id}")
        # For now, just log the cancellation
        # In a real implementation, you might cancel the actual workflow


def create_orchestrator_agent_card() -> AgentCard:
    """
    Create the AgentCard for the Orchestrator agent service

    Returns:
        AgentCard describing the Orchestrator agent's capabilities
    """
    return AgentCard(
        name="Orchestrator Agent Service",
        description="Central coordinator for incident response workflows using ADK, A2A, and multi-agent orchestration",
        version="1.0.0",
        protocol_version="1.0",
        provider=AgentProvider(
            name="SelfHeal GKE",
            organization="SelfHeal GKE Team",
            url="https://github.com/abhitalluri/selfhealgke"
        ),
        capabilities=AgentCapabilities(),
        skills=[
            AgentSkill(
                id="start_incident_workflow_skill",
                name="start_incident_workflow",
                description="Start a new incident response workflow",
                tags=["orchestration", "workflow", "incident-response"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["start_incident_workflow"]},
                        "failure_payload": {
                            "type": "object",
                            "properties": {
                                "test_title": {"type": "string"},
                                "status": {"type": "string"},
                                "error": {"type": "object"},
                                "retries": {"type": "integer"},
                                "trace_id": {"type": "string"},
                                "video_url": {"type": ["string", "null"]},
                                "trace_url": {"type": ["string", "null"]},
                                "timestamp": {"type": ["string", "null"]}
                            },
                            "required": ["test_title", "status", "error", "retries", "trace_id"]
                        }
                    },
                    "required": ["action", "failure_payload"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "workflow_id": {"type": "string"},
                        "status": {"type": "string"},
                        "message": {"type": "string"},
                        "incident_id": {"type": "string"},
                        "started_at": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="update_workflow_status_skill",
                name="update_workflow_status",
                description="Update the status of an existing workflow",
                tags=["orchestration", "workflow", "status-update"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["update_workflow_status"]},
                        "workflow_id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["analysis_complete", "remediation_proposed", "approval_received", "execution_complete", "failed"]
                        },
                        "result_data": {"type": "object"}
                    },
                    "required": ["action", "workflow_id", "status"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "workflow_id": {"type": "string"},
                        "status": {"type": "string"},
                        "message": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="get_workflow_status_skill",
                name="get_workflow_status",
                description="Get the current status of a workflow",
                tags=["orchestration", "workflow", "status-query"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["get_workflow_status"]},
                        "workflow_id": {"type": "string"}
                    },
                    "required": ["action", "workflow_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "workflow_id": {"type": "string"},
                        "status": {"type": "string"},
                        "incident_id": {"type": "string"},
                        "created_at": {"type": "string"},
                        "updated_at": {"type": "string"},
                        "analysis_result": {"type": ["object", "null"]},
                        "remediation_action": {"type": ["object", "null"]},
                        "approval_response": {"type": ["object", "null"]},
                        "execution_result": {"type": ["object", "null"]},
                        "error_message": {"type": ["string", "null"]}
                    }
                }
            ),
            AgentSkill(
                id="cancel_workflow_skill",
                name="cancel_workflow",
                description="Cancel an active workflow",
                tags=["orchestration", "workflow", "cancellation"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["cancel_workflow"]},
                        "workflow_id": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["action", "workflow_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "workflow_id": {"type": "string"},
                        "status": {"type": "string"},
                        "message": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="get_active_workflows_skill",
                name="get_active_workflows",
                description="Get all currently active workflows",
                tags=["orchestration", "workflow", "monitoring"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["get_active_workflows"]}
                    },
                    "required": ["action"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                        "active_workflows": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "workflow_id": {"type": "string"},
                                    "incident_id": {"type": "string"},
                                    "status": {"type": "string"},
                                    "created_at": {"type": "string"},
                                    "updated_at": {"type": "string"},
                                    "test_title": {"type": "string"}
                                }
                            }
                        },
                        "total_count": {"type": "integer"}
                    }
                }
            ),
            AgentSkill(
                id="health_check_skill",
                name="health_check",
                description="Check the health and status of the orchestrator",
                tags=["orchestration", "health", "monitoring"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["health_check"]}
                    },
                    "required": ["action"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                        "uptime_seconds": {"type": "number"},
                        "active_workflows": {"type": "integer"},
                        "discovered_agents": {"type": "object"},
                        "webhook_server_running": {"type": "boolean"}
                    }
                }
            )
        ],
        preferred_transport="http",
        default_input_modes=["json-rpc"],
        default_output_modes=["json-rpc"],
        url="http://localhost:8005",  # Default URL, can be overridden
        documentation_url="https://github.com/abhitalluri/selfhealgke/blob/main/agents/README.md"
    )


class OrchestratorA2AService:
    """
    A2A Service wrapper for the Orchestrator Agent
    """

    def __init__(self, agent_config: AgentConfig, host: str = "0.0.0.0", port: int = 8005):
        self.agent_config = agent_config
        self.host = host
        self.port = port

        # Initialize Orchestrator agent (will be initialized later in initialize method)
        # ADK is already disabled at module level
        self.orchestrator_agent = OrchestratorAgent(agent_config.agent_id, self.port + 1000)  # Use different port for webhook

        # Create A2A components
        self.agent_card = create_orchestrator_agent_card()
        self.agent_executor = OrchestratorAgentExecutor(self.orchestrator_agent)
        self.task_store = InMemoryTaskStore()
        self.queue_manager = InMemoryQueueManager()
        self.context_builder = SimpleRequestContextBuilder()

        # Create request handler
        self.request_handler = DefaultRequestHandler(
            agent_executor=self.agent_executor,
            task_store=self.task_store,
            queue_manager=self.queue_manager,
            request_context_builder=self.context_builder
        )

        # Create FastAPI application
        self.app = A2AFastAPIApplication(
            agent_card=self.agent_card,
            http_handler=self.request_handler
        ).build()

        # Add REST endpoints for direct calls
        from fastapi import FastAPI
        if hasattr(self.app, 'add_api_route'):
            self.app.add_api_route("/start_workflow", self.start_workflow_rest, methods=["POST"])
            self.app.add_api_route("/update_workflow", self.update_workflow_rest, methods=["POST"])
            self.app.add_api_route("/workflow/{workflow_id}", self.get_workflow_status_rest, methods=["GET"])
            self.app.add_api_route("/workflow/{workflow_id}/cancel", self.cancel_workflow_rest, methods=["POST"])
            self.app.add_api_route("/workflows", self.get_active_workflows_rest, methods=["GET"])
            self.app.add_api_route("/health", self.health_check_rest, methods=["GET"])
            logger.info("Added REST endpoints for direct orchestrator calls")

        logger.info(f"Orchestrator A2A Service initialized on {host}:{port}")

    async def initialize(self):
        """Initialize the Orchestrator agent and A2A service"""
        await self.orchestrator_agent.initialize()
        logger.info("Orchestrator A2A Service fully initialized")

    async def start(self):
        """Start the A2A service"""
        import uvicorn

        # Update agent card URL
        self.agent_card.url = f"http://{self.host}:{self.port}"

        logger.info(f"Starting Orchestrator A2A Service on {self.host}:{self.port}")

        # Start the FastAPI server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)

        try:
            await server.serve()
        except KeyboardInterrupt:
            logger.info("Orchestrator A2A Service shutting down")
        finally:
            await self.orchestrator_agent.cleanup()

    # REST endpoint implementations
    async def start_workflow_rest(self, request: dict) -> Dict[str, Any]:
        """REST endpoint for starting workflows"""
        try:
            task_id = f"rest-{asyncio.get_event_loop().time()}"
            request["action"] = "start_incident_workflow"
            result = await self.agent_executor.execute(task_id, request)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def update_workflow_rest(self, request: dict) -> Dict[str, Any]:
        """REST endpoint for updating workflow status"""
        try:
            task_id = f"rest-{asyncio.get_event_loop().time()}"
            request["action"] = "update_workflow_status"
            result = await self.agent_executor.execute(task_id, request)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def get_workflow_status_rest(self, workflow_id: str) -> Dict[str, Any]:
        """REST endpoint for getting workflow status"""
        try:
            task_id = f"rest-{asyncio.get_event_loop().time()}"
            request = {"action": "get_workflow_status", "workflow_id": workflow_id}
            result = await self.agent_executor.execute(task_id, request)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def cancel_workflow_rest(self, workflow_id: str, request: dict = None) -> Dict[str, Any]:
        """REST endpoint for cancelling workflows"""
        try:
            task_id = f"rest-{asyncio.get_event_loop().time()}"
            cancel_request = {
                "action": "cancel_workflow",
                "workflow_id": workflow_id,
                "reason": request.get("reason", "Cancelled via REST API") if request else "Cancelled via REST API"
            }
            result = await self.agent_executor.execute(task_id, cancel_request)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def get_active_workflows_rest(self) -> Dict[str, Any]:
        """REST endpoint for getting active workflows"""
        try:
            task_id = f"rest-{asyncio.get_event_loop().time()}"
            request = {"action": "get_active_workflows"}
            result = await self.agent_executor.execute(task_id, request)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    async def health_check_rest(self) -> Dict[str, Any]:
        """REST endpoint for health checks"""
        try:
            task_id = f"rest-{asyncio.get_event_loop().time()}"
            request = {"action": "health_check"}
            result = await self.agent_executor.execute(task_id, request)
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}


async def create_orchestrator_a2a_service(
    agent_id: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8005,
    metadata: Optional[Dict[str, Any]] = None
) -> OrchestratorA2AService:
    """
    Factory function to create an Orchestrator A2A service

    Args:
        agent_id: Optional agent ID
        host: Host to bind to
        port: Port to bind to
        metadata: Additional metadata for agent config

    Returns:
        Configured Orchestrator A2A service
    """
    if agent_id is None:
        agent_id = f"orchestrator_a2a_{int(asyncio.get_event_loop().time())}"

    if metadata is None:
        metadata = {}

    # Set default metadata if not provided
    metadata.setdefault("webhook_port", 8080)
    metadata.setdefault("max_concurrent_workflows", 10)

    config = AgentConfig(
        agent_id=agent_id,
        agent_type="orchestrator-a2a",
        capabilities=[
            "workflow_orchestration",
            "incident_coordination",
            "multi_agent_communication",
            "a2a_service"
        ],
        heartbeat_interval=30,
        health_check_interval=60,
        max_concurrent_tasks=20,
        metadata=metadata
    )

    service = OrchestratorA2AService(config, host, port)
    await service.initialize()

    return service


if __name__ == "__main__":
    # Example usage
    async def main():
        service = await create_orchestrator_a2a_service()
        await service.start()

    asyncio.run(main())