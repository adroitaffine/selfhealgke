"""
A2A Service wrapper for the RCA Agent

This module exposes the RCA agent as an A2A service that can be called by other agents
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

# Disable ADK before importing RCA agent to avoid validation issues
import agents.rca_agent as rca_module
rca_module.ADK_AVAILABLE = False

from .rca_agent import RCAAgent, AgentConfig, FailurePayload, AnalysisResult, ErrorDetails

logger = logging.getLogger(__name__)


class RCAAgentExecutor(AgentExecutor):
    """
    A2A AgentExecutor implementation that wraps the RCA agent
    """

    def __init__(self, rca_agent: RCAAgent):
        self.rca_agent = rca_agent
        logger.info("RCA AgentExecutor initialized")

    async def execute(self, task_id: str, request: Dict[str, Any], context: Optional[RequestContext] = None) -> Dict[str, Any]:
        """
        Execute an RCA analysis task

        Args:
            task_id: Unique task identifier
            request: Request payload containing failure data
            context: Optional request context

        Returns:
            Analysis result
        """
        try:
            logger.info(f"Executing RCA task {task_id}")

            # Extract failure payload from request
            failure_data = request.get("failure_payload", {})
            if not failure_data:
                raise ValueError("Missing failure_payload in request")

            # Convert to FailurePayload
            payload = FailurePayload(
                test_title=failure_data.get("test_title", "Unknown Test"),
                status=failure_data.get("status", "failed"),
                error=ErrorDetails(
                    message=failure_data.get("error_message", "Unknown error"),
                    stack=failure_data.get("error_stack", ""),
                    type=failure_data.get("error_type", "Error")
                ),
                retries=failure_data.get("retries", 0),
                trace_id=failure_data.get("trace_id", f"trace-{task_id}"),
                timestamp=failure_data.get("timestamp")
            )

            # Execute RCA analysis (pass dict directly)
            analysis_result = await self.rca_agent.analyze_failure(failure_data)

            # Convert result to dict (analysis_result is already a dict)
            result = {
                "task_id": task_id,
                "classification": analysis_result.get("classification", "Unknown"),
                "failing_service": analysis_result.get("failing_service"),
                "summary": analysis_result.get("summary", "No summary"),
                "confidence_score": analysis_result.get("confidence_score", 0.0),
                "evidence_count": analysis_result.get("evidence_count", 0),
                "analysis_duration": analysis_result.get("analysis_duration", 0.0),
                "trace_id": analysis_result.get("trace_id", f"trace-{task_id}"),
                "evidence": analysis_result.get("evidence", [])
            }

            logger.info(f"RCA task {task_id} completed: {result['classification']}")
            return result

        except Exception as e:
            logger.error(f"RCA task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "error": str(e),
                "classification": "Unknown",
                "failing_service": None,
                "summary": f"Analysis failed: {str(e)}",
                "confidence_score": 0.0,
                "evidence_count": 0,
                "evidence": []
            }
    
    async def cancel(self, task_id: str) -> None:
        """
        Cancel a running task

        Args:
            task_id: Unique task identifier to cancel
        """
        logger.info(f"Cancelling RCA task {task_id}")
        # For now, just log the cancellation
        # In a real implementation, you might cancel the actual analysis task


def create_rca_agent_card() -> AgentCard:
    """
    Create the AgentCard for the RCA agent service

    Returns:
        AgentCard describing the RCA agent's capabilities
    """
    return AgentCard(
        name="RCA Agent Service",
        description="Root Cause Analysis agent for microservices incidents using ADK, A2A, and Gemini LLM",
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
                id="analyze_failure_skill",
                name="analyze_failure",
                description="Analyze test failures and identify root causes in microservices",
                tags=["rca", "analysis", "microservices"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "failure_payload": {
                            "type": "object",
                            "properties": {
                                "test_title": {"type": "string"},
                                "status": {"type": "string"},
                                "error_message": {"type": "string"},
                                "error_stack": {"type": "string"},
                                "error_type": {"type": "string"},
                                "retries": {"type": "integer"},
                                "trace_id": {"type": "string"},
                                "timestamp": {"type": "string"}
                            },
                            "required": ["test_title", "error_message", "trace_id"]
                        }
                    },
                    "required": ["failure_payload"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "classification": {"type": "string"},
                        "failing_service": {"type": ["string", "null"]},
                        "summary": {"type": "string"},
                        "confidence_score": {"type": "number"},
                        "evidence_count": {"type": "integer"},
                        "analysis_duration": {"type": "number"},
                        "trace_id": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "source": {"type": "string"},
                                    "content": {"type": "string"},
                                    "severity": {"type": "string"},
                                    "service_name": {"type": ["string", "null"]},
                                    "timestamp": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            ),
            AgentSkill(
                id="get_topology_insights_skill",
                name="get_topology_insights",
                description="Get insights about discovered microservice topology",
                tags=["topology", "insights", "microservices"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {}
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "service_count": {"type": "integer"},
                        "entry_points": {"type": "array", "items": {"type": "string"}},
                        "critical_services": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "criticality_score": {"type": "number"}
                                }
                            }
                        },
                        "failure_patterns": {
                            "type": "object",
                            "properties": {
                                "total_failures_analyzed": {"type": "integer"},
                                "common_error_types": {"type": "array"},
                                "frequently_failing_services": {"type": "array"}
                            }
                        }
                    }
                }
            )
        ],
        preferred_transport="http",
        default_input_modes=["json-rpc"],
        default_output_modes=["json-rpc"],
        url="http://localhost:8001",  # Default URL, can be overridden
        documentation_url="https://github.com/abhitalluri/selfhealgke/blob/main/agents/README.md"
    )


class RCAA2AService:
    """
    A2A Service wrapper for the RCA Agent
    """

    def __init__(self, agent_config: AgentConfig, host: str = "0.0.0.0", port: int = 8001):
        self.agent_config = agent_config
        self.host = host
        self.port = port

        # Initialize RCA agent (will be initialized later in initialize method)
        # ADK is already disabled at module level
        self.rca_agent = RCAAgent(agent_config.agent_id)

        # Create A2A components
        self.agent_card = create_rca_agent_card()
        self.agent_executor = RCAAgentExecutor(self.rca_agent)
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

        # Add a simple REST endpoint for direct calls
        from fastapi import FastAPI
        if hasattr(self.app, 'add_api_route'):
            self.app.add_api_route("/analyze", self.analyze_failure_rest, methods=["POST"])
            logger.info("Added REST endpoint /analyze for direct RCA calls")

        logger.info(f"RCA A2A Service initialized on {host}:{port}")

    async def initialize(self):
        """Initialize the RCA agent and A2A service"""
        await self.rca_agent.initialize()
        logger.info("RCA A2A Service fully initialized")

    async def start(self):
        """Start the A2A service"""
        import uvicorn

        # Update agent card URL
        self.agent_card.url = f"http://{self.host}:{self.port}"

        logger.info(f"Starting RCA A2A Service on {self.host}:{self.port}")

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
            logger.info("RCA A2A Service shutting down")
        finally:
            await self.rca_agent.cleanup()

    async def analyze_failure_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for direct RCA analysis calls
        
        Args:
            request: Request containing failure_payload
            
        Returns:
            Analysis result
        """
        try:
            logger.info("Received REST analysis request")
            
            failure_payload = request.get("failure_payload", {})
            if not failure_payload:
                return {
                    "error": "Missing failure_payload in request",
                    "status": "error"
                }
            
            # Convert to FailurePayload
            payload = FailurePayload(
                test_title=failure_payload.get("test_title", "Unknown Test"),
                status=failure_payload.get("status", "failed"),
                error=ErrorDetails(
                    message=failure_payload.get("error_message", "Unknown error"),
                    stack=failure_payload.get("error_stack", ""),
                    type=failure_payload.get("error_type", "Error")
                ),
                retries=failure_payload.get("retries", 0),
                trace_id=failure_payload.get("trace_id", f"trace-{asyncio.get_event_loop().time()}"),
                timestamp=failure_payload.get("timestamp")
            )
            
            # Execute RCA analysis (pass dict directly)
            analysis_result = await self.rca_agent.analyze_failure(failure_payload)
            
            # Convert result to dict (analysis_result is already a dict)
            result = {
                "status": "completed",
                "classification": analysis_result.get("classification", "Unknown"),
                "failing_service": analysis_result.get("failing_service"),
                "summary": analysis_result.get("summary", "No summary"),
                "confidence_score": analysis_result.get("confidence_score", 0.0),
                "evidence_count": analysis_result.get("evidence_count", 0),
                "analysis_duration": analysis_result.get("analysis_duration", 0.0),
                "trace_id": analysis_result.get("trace_id", f"trace-{asyncio.get_event_loop().time()}"),
                "evidence": analysis_result.get("evidence", [])
            }
            
            logger.info(f"REST RCA analysis completed: {result['classification']}")
            return result
            
        except Exception as e:
            logger.error(f"REST RCA analysis failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "classification": "Unknown",
                "failing_service": None,
                "summary": f"Analysis failed: {str(e)}",
                "confidence_score": 0.0,
                "evidence_count": 0,
                "evidence": []
            }

    async def get_topology_insights_a2a(self) -> Dict[str, Any]:
        """
        Get topology insights directly

        Returns:
            Topology insights
        """
        return await self.rca_agent.get_topology_insights()


async def create_rca_a2a_service(
    agent_id: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8001,
    metadata: Optional[Dict[str, Any]] = None
) -> RCAA2AService:
    """
    Factory function to create an RCA A2A service

    Args:
        agent_id: Optional agent ID
        host: Host to bind to
        port: Port to bind to
        metadata: Additional metadata for agent config

    Returns:
        Configured RCA A2A service
    """
    if agent_id is None:
        agent_id = f"rca_a2a_{int(asyncio.get_event_loop().time())}"

    if metadata is None:
        metadata = {}

    # Set default metadata if not provided
    metadata.setdefault("telemetry_window_seconds", 300)
    metadata.setdefault("confidence_threshold", 0.7)
    metadata.setdefault("topology_cache_ttl", 3600)

    config = AgentConfig(
        agent_id=agent_id,
        agent_type="rca-a2a",
        capabilities=[
            "telemetry_analysis",
            "topology_discovery",
            "failure_classification",
            "gemini_integration",
            "a2a_service"
        ],
        heartbeat_interval=30,
        health_check_interval=60,
        max_concurrent_tasks=5,
        metadata=metadata
    )

    service = RCAA2AService(config, host, port)
    await service.initialize()

    return service


if __name__ == "__main__":
    # Example usage
    async def main():
        service = await create_rca_a2a_service()
        await service.start()

    asyncio.run(main())