"""
A2A Service wrapper for the Approval Agent

This module exposes the Approval agent as an A2A service that can be called by other agents
or systems using the A2A protocol.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider
from a2a.server.agent_execution import AgentExecutor, RequestContext, SimpleRequestContextBuilder
from a2a.server.tasks import TaskStore, InMemoryTaskStore
from a2a.server.events import QueueManager, InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AFastAPIApplication

# Disable ADK before importing Approval agent to avoid validation issues
import agents.approval_agent as approval_module
approval_module.ADK_AVAILABLE = False

from agents.approval_agent import ApprovalAgent, AgentConfig, ApprovalRequest, ApprovalDecision, ApprovalPriority

logger = logging.getLogger(__name__)


class ApprovalAgentExecutor(AgentExecutor):
    """
    A2A AgentExecutor implementation that wraps the Approval agent
    """

    def __init__(self, approval_agent: ApprovalAgent):
        self.approval_agent = approval_agent
        logger.info("Approval AgentExecutor initialized")

    async def execute(self, task_id: str, request: Dict[str, Any], context: Optional[RequestContext] = None) -> Dict[str, Any]:
        """
        Execute an approval task

        Args:
            task_id: Unique task identifier
            request: Request payload containing approval data
            context: Optional request context

        Returns:
            Approval result
        """
        try:
            logger.info(f"Executing approval task {task_id}")

            # Extract approval request from request
            approval_data = request.get("approval_request", {})
            if not approval_data:
                raise ValueError("Missing approval_request in request")

            # Convert priority string to enum
            priority_str = approval_data.get("priority", "medium").upper()
            priority_enum = ApprovalPriority.MEDIUM  # default
            if priority_str == "LOW":
                priority_enum = ApprovalPriority.LOW
            elif priority_str == "HIGH":
                priority_enum = ApprovalPriority.HIGH
            elif priority_str == "CRITICAL":
                priority_enum = ApprovalPriority.CRITICAL

            # Request approval
            request_id = await self.approval_agent.request_approval(
                incident_id=approval_data.get("incident_id", f"incident-{task_id}"),
                trace_id=approval_data.get("trace_id", f"trace-{task_id}"),
                title=approval_data.get("title", "Approval Request"),
                description=approval_data.get("description", "Approval needed for remediation action"),
                classification=approval_data.get("classification", "Unknown"),
                failing_service=approval_data.get("failing_service"),
                summary=approval_data.get("summary", "Remediation action requires approval"),
                evidence=approval_data.get("evidence", []),
                proposed_action=approval_data.get("proposed_action", {}),
                risk_level=approval_data.get("risk_level", "medium"),
                estimated_duration=approval_data.get("estimated_duration", 300),
                priority=priority_enum
            )

            # Get initial status
            status = await self.approval_agent.get_request_status(request_id)

            result = {
                "task_id": task_id,
                "request_id": request_id,
                "status": status.status.value if status else "unknown",
                "message": f"Approval request {request_id} submitted successfully",
                "expires_at": status.expires_at.isoformat() if status else None
            }

            logger.info(f"Approval task {task_id} completed: {result['status']}")
            return result

        except Exception as e:
            logger.error(f"Approval task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "error": str(e),
                "status": "failed",
                "message": f"Approval request failed: {str(e)}"
            }

    async def cancel(self, task_id: str) -> None:
        """
        Cancel a running task

        Args:
            task_id: Unique task identifier to cancel
        """
        logger.info(f"Cancelling approval task {task_id}")
        # For now, just log the cancellation
        # In a real implementation, you might cancel the actual approval request


def create_approval_agent_card() -> AgentCard:
    """
    Create the AgentCard for the Approval agent service

    Returns:
        AgentCard describing the Approval agent's capabilities
    """
    return AgentCard(
        name="Approval Agent Service",
        description="Human-in-the-Loop Approval agent for remediation actions using ADK, A2A, and Gemini LLM",
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
                id="request_approval_skill",
                name="request_approval",
                description="Request human approval for remediation actions",
                tags=["approval", "workflow", "human-in-the-loop"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "approval_request": {
                            "type": "object",
                            "properties": {
                                "incident_id": {"type": "string"},
                                "trace_id": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "classification": {"type": "string"},
                                "failing_service": {"type": ["string", "null"]},
                                "summary": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}},
                                "proposed_action": {"type": "object"},
                                "risk_level": {"type": "string"},
                                "estimated_duration": {"type": "integer"},
                                "priority": {"type": "string"}
                            },
                            "required": ["incident_id", "title", "description", "proposed_action"]
                        }
                    },
                    "required": ["approval_request"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "request_id": {"type": "string"},
                        "status": {"type": "string"},
                        "message": {"type": "string"},
                        "expires_at": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="get_approval_status_skill",
                name="get_approval_status",
                description="Get the status of an approval request",
                tags=["approval", "status", "workflow"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"}
                    },
                    "required": ["request_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                        "status": {"type": "string"},
                        "approved_by": {"type": ["string", "null"]},
                        "approved_at": {"type": ["string", "null"]},
                        "rejection_reason": {"type": ["string", "null"]},
                        "expires_at": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="handle_approval_decision_skill",
                name="handle_approval_decision",
                description="Process an approval decision from the dashboard",
                tags=["approval", "decision", "workflow"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "decision_data": {
                            "type": "object",
                            "properties": {
                                "request_id": {"type": "string"},
                                "decision": {"type": "string", "enum": ["approve", "reject"]},
                                "user_id": {"type": "string"},
                                "user_name": {"type": "string"},
                                "signature": {"type": "string"},
                                "reason": {"type": ["string", "null"]}
                            },
                            "required": ["request_id", "decision", "user_id", "signature"]
                        }
                    },
                    "required": ["decision_data"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "message": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="get_approval_statistics_skill",
                name="get_approval_statistics",
                description="Get approval statistics for a time period",
                tags=["approval", "statistics", "analytics"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "start_date": {"type": ["string", "null"]},
                        "end_date": {"type": ["string", "null"]}
                    }
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"}
                            }
                        },
                        "total_requests": {"type": "integer"},
                        "approved": {"type": "integer"},
                        "rejected": {"type": "integer"},
                        "expired": {"type": "integer"},
                        "pending": {"type": "integer"},
                        "approval_rate": {"type": "number"},
                        "average_response_time_seconds": {"type": "number"}
                    }
                }
            )
        ],
        preferred_transport="http",
        default_input_modes=["json-rpc"],
        default_output_modes=["json-rpc"],
        url="http://localhost:8004",  # Default URL, can be overridden
        documentation_url="https://github.com/abhitalluri/selfhealgke/blob/main/agents/README.md"
    )


class ApprovalA2AService:
    """
    A2A Service wrapper for the Approval Agent
    """

    def __init__(self, agent_config: AgentConfig, host: str = "0.0.0.0", port: int = 8004, test_mode: bool = False):
        self.agent_config = agent_config
        self.host = host
        self.port = port
        self.test_mode = test_mode

        # Initialize Approval agent (will be initialized later in initialize method)
        # ADK is already disabled at module level
        self.approval_agent = ApprovalAgent(agent_config.agent_id)

        # Create A2A components
        self.agent_card = create_approval_agent_card()
        self.agent_executor = ApprovalAgentExecutor(self.approval_agent)
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
            self.app.add_api_route("/request", self.request_approval_rest, methods=["POST"])
            self.app.add_api_route("/status/{request_id}", self.get_approval_status_rest, methods=["GET"])
            self.app.add_api_route("/decide", self.handle_approval_decision_rest, methods=["POST"])
            self.app.add_api_route("/statistics", self.get_approval_statistics_rest, methods=["GET"])
            logger.info("Added REST endpoints for direct approval calls")

        logger.info(f"Approval A2A Service initialized on {host}:{port} (test_mode: {test_mode})")

    async def initialize(self):
        """Initialize the Approval agent and A2A service"""
        await self.approval_agent.initialize()
        logger.info("Approval A2A Service fully initialized")

    async def start(self):
        """Start the A2A service"""
        import uvicorn

        # Update agent card URL
        self.agent_card.url = f"http://{self.host}:{self.port}"

        logger.info(f"Starting Approval A2A Service on {self.host}:{self.port}")

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
            logger.info("Approval A2A Service shutting down")
        finally:
            await self.approval_agent.cleanup()

    async def request_approval_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for direct approval requests

        Args:
            request: Request containing approval_request

        Returns:
            Approval request result
        """
        try:
            logger.info("Received REST approval request")

            approval_request = request.get("approval_request", {})
            if not approval_request:
                return {
                    "error": "Missing approval_request in request",
                    "status": "error"
                }

            # Convert priority string to enum
            priority_str = approval_request.get("priority", "medium").upper()
            priority_enum = ApprovalPriority.MEDIUM  # default
            if priority_str == "LOW":
                priority_enum = ApprovalPriority.LOW
            elif priority_str == "HIGH":
                priority_enum = ApprovalPriority.HIGH
            elif priority_str == "CRITICAL":
                priority_enum = ApprovalPriority.CRITICAL

            # Request approval
            request_id = await self.approval_agent.request_approval(
                incident_id=approval_request.get("incident_id", f"incident-{asyncio.get_event_loop().time()}"),
                trace_id=approval_request.get("trace_id", f"trace-{asyncio.get_event_loop().time()}"),
                title=approval_request.get("title", "Approval Request"),
                description=approval_request.get("description", "Approval needed for remediation action"),
                classification=approval_request.get("classification", "Unknown"),
                failing_service=approval_request.get("failing_service"),
                summary=approval_request.get("summary", "Remediation action requires approval"),
                evidence=approval_request.get("evidence", []),
                proposed_action=approval_request.get("proposed_action", {}),
                risk_level=approval_request.get("risk_level", "medium"),
                estimated_duration=approval_request.get("estimated_duration", 300),
                priority=priority_enum
            )

            # Get status
            status = await self.approval_agent.get_request_status(request_id)

            result = {
                "status": "success",
                "request_id": request_id,
                "approval_status": status.status.value if status else "unknown",
                "message": f"Approval request {request_id} submitted successfully",
                "expires_at": status.expires_at.isoformat() if status else None
            }

            logger.info(f"REST approval request completed: {result['request_id']}")
            return result

        except Exception as e:
            logger.error(f"REST approval request failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": f"Approval request failed: {str(e)}"
            }

    async def get_approval_status_rest(self, request_id: str) -> Dict[str, Any]:
        """
        REST endpoint for getting approval status

        Args:
            request_id: Request ID to check

        Returns:
            Approval status
        """
        try:
            logger.info(f"Received REST status request for {request_id}")

            status = await self.approval_agent.get_request_status(request_id)

            if not status:
                return {
                    "error": f"Approval request {request_id} not found",
                    "status": "error"
                }

            result = {
                "status": "success",
                "request_id": request_id,
                "approval_status": status.status.value,
                "approved_by": status.approved_by,
                "approved_at": status.approved_at.isoformat() if status.approved_at else None,
                "rejection_reason": status.rejection_reason,
                "expires_at": status.expires_at.isoformat()
            }

            logger.info(f"REST status request completed for {request_id}")
            return result

        except Exception as e:
            logger.error(f"REST status request failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": f"Status check failed: {str(e)}"
            }

    async def handle_approval_decision_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for handling approval decisions

        Args:
            request: Request containing decision_data

        Returns:
            Decision processing result
        """
        try:
            logger.info("Received REST approval decision")

            decision_data = request.get("decision_data", {})
            if not decision_data:
                return {
                    "error": "Missing decision_data in request",
                    "status": "error"
                }

            # Skip signature validation in test mode
            if not self.test_mode:
                # Validate required fields
                request_id = decision_data.get('request_id')
                decision = decision_data.get('decision')
                user_id = decision_data.get('user_id')
                signature = decision_data.get('signature')

                if not request_id or not decision or not user_id or not signature:
                    logger.error("Missing required fields in approval decision")
                    return {
                        "error": "Missing required fields in decision_data",
                        "status": "error"
                    }

                # Verify signature
                signature_data = {
                    'request_id': request_id,
                    'decision': decision,
                    'user_id': user_id,
                    'timestamp': decision_data.get('timestamp')
                }

                if not self.approval_agent.signature_manager.verify_signature(signature_data, signature):
                    logger.error(f"Invalid signature for approval decision: {request_id}")
                    return {
                        "error": "Invalid signature",
                        "status": "error"
                    }

            # Process decision
            success = await self.approval_agent.handle_approval_decision(decision_data, skip_signature_validation=self.test_mode)

            result = {
                "status": "success" if success else "error",
                "success": success,
                "message": "Decision processed successfully" if success else "Decision processing failed"
            }

            logger.info(f"REST approval decision completed: {success}")
            return result

        except Exception as e:
            logger.error(f"REST approval decision failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": f"Decision processing failed: {str(e)}"
            }

    async def get_approval_statistics_rest(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        REST endpoint for getting approval statistics

        Args:
            start_date: Start date for statistics (ISO format)
            end_date: End date for statistics (ISO format)

        Returns:
            Approval statistics
        """
        try:
            logger.info("Received REST statistics request")

            # Parse dates
            start = datetime.fromisoformat(start_date) if start_date else None
            end = datetime.fromisoformat(end_date) if end_date else None

            # Get statistics
            stats = await self.approval_agent.get_approval_statistics(start, end)

            result = {
                "status": "success",
                **stats
            }

            logger.info("REST statistics request completed")
            return result

        except Exception as e:
            logger.error(f"REST statistics request failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": f"Statistics retrieval failed: {str(e)}"
            }


async def create_approval_a2a_service(
    agent_id: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8004,
    metadata: Optional[Dict[str, Any]] = None,
    test_mode: bool = False
) -> ApprovalA2AService:
    """
    Factory function to create an Approval A2A service

    Args:
        agent_id: Optional agent ID
        host: Host to bind to
        port: Port to bind to
        metadata: Additional metadata for agent config
        test_mode: Enable test mode (skips signature validation)

    Returns:
        Configured Approval A2A service
    """
    if agent_id is None:
        agent_id = f"approval_a2a_{int(asyncio.get_event_loop().time())}"

    if metadata is None:
        metadata = {}

    # Set default metadata if not provided
    metadata.setdefault("dashboard_url", "http://localhost:8080")
    metadata.setdefault("api_key", "default-api-key")

    config = AgentConfig(
        agent_id=agent_id,
        agent_type="approval-a2a",
        capabilities=[
            "approval_workflow",
            "human_in_the_loop",
            "dashboard_integration",
            "a2a_service"
        ],
        metadata=metadata
    )

    service = ApprovalA2AService(config, host, port, test_mode=test_mode)
    await service.initialize()

    return service


if __name__ == "__main__":
    # Example usage
    async def main():
        service = await create_approval_a2a_service()
        await service.start()

    asyncio.run(main())