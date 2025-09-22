"""
A2A Service wrapper for the Remediation Agent

This module exposes the Remediation agent as an A2A service that can be called by other agents
or systems using the A2A protocol.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider
from a2a.server.agent_execution import AgentExecutor, RequestContext, SimpleRequestContextBuilder
from a2a.server.tasks import TaskStore, InMemoryTaskStore
from a2a.server.events import QueueManager, InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AFastAPIApplication

# Disable ADK before importing Remediation agent to avoid validation issues
import agents.remediation_agent as remediation_module
remediation_module.ADK_AVAILABLE = False

from .remediation_agent import RemediationAgent, AgentConfig, RemediationAction, ExecutionResult

logger = logging.getLogger(__name__)


class RemediationAgentExecutor(AgentExecutor):
    """
    A2A AgentExecutor implementation that wraps the Remediation agent
    """

    def __init__(self, remediation_agent: RemediationAgent):
        self.remediation_agent = remediation_agent
        logger.info("Remediation AgentExecutor initialized")

    async def execute(self, task_id: str, request: Dict[str, Any], context: Optional[RequestContext] = None) -> Dict[str, Any]:
        """
        Execute a remediation task

        Args:
            task_id: Unique task identifier
            request: Request payload containing analysis result and approval
            context: Optional request context

        Returns:
            Remediation result
        """
        try:
            logger.info(f"Executing remediation task {task_id}")

            # Extract analysis result from request
            analysis_result = request.get("analysis_result", {})
            approved_action_id = request.get("approved_action_id")

            if not analysis_result:
                raise ValueError("Missing analysis_result in request")

            # If approved_action_id is provided, execute that specific action
            if approved_action_id:
                # Find the approved action (in real scenario, this would come from approval system)
                action = await self._get_approved_action(approved_action_id)
                if not action:
                    raise ValueError(f"Approved action {approved_action_id} not found")

                # Execute the approved action
                execution_result = await self.remediation_agent.execute_remediation(action)

                result = {
                    "task_id": task_id,
                    "action_id": action.action_id,
                    "strategy": action.strategy.value,
                    "target_service": action.target_service,
                    "success": execution_result.success,
                    "execution_time": execution_result.execution_time.isoformat(),
                    "duration_seconds": execution_result.duration_seconds,
                    "verification_status": execution_result.verification_status,
                    "error_message": execution_result.error_message,
                    "rollback_executed": getattr(execution_result, 'rollback_executed', False)
                }
            else:
                # Propose remediation action
                action = await self.remediation_agent.propose_remediation(analysis_result)

                if action:
                    result = {
                        "task_id": task_id,
                        "proposed_action": {
                            "action_id": action.action_id,
                            "strategy": action.strategy.value,
                            "target_service": action.target_service,
                            "target_namespace": action.target_namespace,
                            "risk_level": action.risk_level.value,
                            "estimated_duration": action.estimated_duration,
                            "confidence_score": action.confidence_score,
                            "impact_analysis": action.impact_analysis,
                            "verification_tests": action.verification_tests
                        },
                        "status": "proposed"
                    }
                else:
                    result = {
                        "task_id": task_id,
                        "status": "no_action",
                        "message": "No remediation action recommended"
                    }

            logger.info(f"Remediation task {task_id} completed")
            return result

        except Exception as e:
            logger.error(f"Remediation task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "error": str(e),
                "status": "failed"
            }

    async def _get_approved_action(self, action_id: str) -> Optional[RemediationAction]:
        """
        Get an approved remediation action by ID

        In a real implementation, this would query the approval system
        """
        # Mock implementation - in real scenario, this would come from approval agent
        logger.warning(f"Mock implementation: getting approved action {action_id}")
        return None

    async def cancel(self, task_id: str) -> None:
        """
        Cancel a running remediation task

        Args:
            task_id: Unique task identifier to cancel
        """
        logger.info(f"Cancelling remediation task {task_id}")
        # For now, just log the cancellation
        # In a real implementation, you might cancel the actual remediation task


def create_remediation_agent_card() -> AgentCard:
    """
    Create the AgentCard for the Remediation agent service

    Returns:
        AgentCard describing the Remediation agent's capabilities
    """
    return AgentCard(
        name="Remediation Agent Service",
        description="Intelligent remediation agent for microservices incidents using ADK, A2A, and Gemini LLM",
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
                id="propose_remediation_skill",
                name="propose_remediation",
                description="Propose intelligent remediation actions for microservices failures",
                tags=["remediation", "recovery", "microservices"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "analysis_result": {
                            "type": "object",
                            "properties": {
                                "classification": {"type": "string"},
                                "failing_service": {"type": ["string", "null"]},
                                "summary": {"type": "string"},
                                "confidence_score": {"type": "number"},
                                "evidence": {"type": "array"},
                                "trace_id": {"type": "string"}
                            },
                            "required": ["classification", "summary", "confidence_id"]
                        }
                    },
                    "required": ["analysis_result"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                        "proposed_action": {
                            "type": "object",
                            "properties": {
                                "action_id": {"type": "string"},
                                "strategy": {"type": "string"},
                                "target_service": {"type": "string"},
                                "target_namespace": {"type": "string"},
                                "risk_level": {"type": "string"},
                                "estimated_duration": {"type": "integer"},
                                "confidence_score": {"type": "number"},
                                "impact_analysis": {"type": "string"},
                                "verification_tests": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                }
            ),
            AgentSkill(
                id="execute_remediation_skill",
                name="execute_remediation",
                description="Execute approved remediation actions for microservices",
                tags=["remediation", "execution", "recovery"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "approved_action_id": {"type": "string"},
                        "analysis_result": {
                            "type": "object",
                            "properties": {
                                "classification": {"type": "string"},
                                "failing_service": {"type": ["string", "null"]},
                                "summary": {"type": "string"},
                                "confidence_score": {"type": "number"},
                                "evidence": {"type": "array"},
                                "trace_id": {"type": "string"}
                            }
                        }
                    },
                    "required": ["approved_action_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "action_id": {"type": "string"},
                        "strategy": {"type": "string"},
                        "target_service": {"type": "string"},
                        "success": {"type": "boolean"},
                        "execution_time": {"type": "string"},
                        "duration_seconds": {"type": "number"},
                        "verification_status": {"type": "string"},
                        "error_message": {"type": ["string", "null"]},
                        "rollback_executed": {"type": "boolean"}
                    }
                }
            )
        ],
        preferred_transport="http",
        default_input_modes=["json-rpc"],
        default_output_modes=["json-rpc"],
        url="http://localhost:8002",  # Default URL, can be overridden
        documentation_url="https://github.com/abhitalluri/selfhealgke/blob/main/agents/README.md"
    )


class RemediationA2AService:
    """
    A2A Service wrapper for the Remediation Agent
    """

    def __init__(self, agent_config: AgentConfig, host: str = "0.0.0.0", port: int = 8002):
        self.agent_config = agent_config
        self.host = host
        self.port = port

        # Initialize Remediation agent (will be initialized later in initialize method)
        # ADK is already disabled at module level
        self.remediation_agent = RemediationAgent(agent_config)

        # Create A2A components
        self.agent_card = create_remediation_agent_card()
        self.agent_executor = RemediationAgentExecutor(self.remediation_agent)
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

        # Add simple REST endpoints for direct calls
        from fastapi import FastAPI
        if hasattr(self.app, 'add_api_route'):
            self.app.add_api_route("/propose", self.propose_remediation_rest, methods=["POST"])
            self.app.add_api_route("/execute", self.execute_remediation_rest, methods=["POST"])
            logger.info("Added REST endpoints /propose and /execute for direct remediation calls")

        logger.info(f"Remediation A2A Service initialized on {host}:{port}")

    async def initialize(self):
        """Initialize the Remediation agent and A2A service"""
        await self.remediation_agent.initialize()
        logger.info("Remediation A2A Service fully initialized")

    async def start(self):
        """Start the A2A service"""
        import uvicorn

        # Update agent card URL
        self.agent_card.url = f"http://{self.host}:{self.port}"

        logger.info(f"Starting Remediation A2A Service on {self.host}:{self.port}")

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
            logger.info("Remediation A2A Service shutting down")
        finally:
            await self.remediation_agent.cleanup()

    async def propose_remediation_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for proposing remediation actions

        Args:
            request: Request containing analysis_result

        Returns:
            Proposed remediation action
        """
        try:
            logger.info("Received REST remediation proposal request")

            analysis_data = request.get("analysis_result", {})
            if not analysis_data:
                return {
                    "error": "Missing analysis_result in request",
                    "status": "error"
                }

            # Convert dict to AnalysisResult object
            from agents.rca_agent import AnalysisResult, FailureClassification, Evidence
            from datetime import datetime
            
            # Convert classification string to enum
            classification_str = analysis_data.get("classification", "UNKNOWN")
            try:
                classification = FailureClassification(classification_str)
            except ValueError:
                classification = FailureClassification.UNKNOWN
            
            # Convert evidence list
            evidence_list = []
            for ev in analysis_data.get("evidence", []):
                evidence_list.append(Evidence(
                    type=ev.get("type", "unknown"),
                    source=ev.get("source", "unknown"),
                    content=ev.get("content", ""),
                    severity=ev.get("severity", "UNKNOWN"),
                    timestamp=ev.get("timestamp", datetime.now()),
                    service_name=ev.get("service_name")
                ))
            
            analysis_result = AnalysisResult(
                classification=classification,
                failing_service=analysis_data.get("failing_service"),
                summary=analysis_data.get("summary", ""),
                confidence_score=analysis_data.get("confidence_score", 0.0),
                evidence=evidence_list,
                analysis_duration=analysis_data.get("analysis_duration", 0.0),
                trace_id=analysis_data.get("trace_id", "")
            )

            # Propose remediation action
            action = await self.remediation_agent.propose_remediation(analysis_result)

            if action:
                result = {
                    "status": "proposed",
                    "proposed_action": {
                        "action_id": action.action_id,
                        "strategy": action.strategy.value,
                        "target_service": action.target_service,
                        "target_namespace": action.target_namespace,
                        "risk_level": action.risk_level.value,
                        "estimated_duration": action.estimated_duration,
                        "confidence_score": action.confidence_score,
                        "impact_analysis": action.impact_analysis,
                        "verification_tests": action.verification_tests
                    }
                }
            else:
                result = {
                    "status": "no_action",
                    "message": "No remediation action recommended"
                }

            logger.info(f"REST remediation proposal completed: {result['status']}")
            return result

        except Exception as e:
            logger.error(f"REST remediation proposal failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def execute_remediation_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for executing remediation actions

        Args:
            request: Request containing approved_action_id and analysis_result

        Returns:
            Execution result
        """
        try:
            logger.info("Received REST remediation execution request")

            approved_action_id = request.get("approved_action_id")
            analysis_data = request.get("analysis_result", {})

            if not approved_action_id:
                return {
                    "error": "Missing approved_action_id in request",
                    "status": "error"
                }

            # Convert dict to AnalysisResult object
            from agents.rca_agent import AnalysisResult, FailureClassification, Evidence
            from datetime import datetime
            
            # Convert classification string to enum
            classification_str = analysis_data.get("classification", "UNKNOWN")
            try:
                classification = FailureClassification(classification_str)
            except ValueError:
                classification = FailureClassification.UNKNOWN
            
            # Convert evidence list
            evidence_list = []
            for ev in analysis_data.get("evidence", []):
                evidence_list.append(Evidence(
                    type=ev.get("type", "unknown"),
                    source=ev.get("source", "unknown"),
                    content=ev.get("content", ""),
                    severity=ev.get("severity", "UNKNOWN"),
                    timestamp=ev.get("timestamp", datetime.now()),
                    service_name=ev.get("service_name")
                ))
            
            analysis_result = AnalysisResult(
                classification=classification,
                failing_service=analysis_data.get("failing_service"),
                summary=analysis_data.get("summary", ""),
                confidence_score=analysis_data.get("confidence_score", 0.0),
                evidence=evidence_list,
                analysis_duration=analysis_data.get("analysis_duration", 0.0),
                trace_id=analysis_data.get("trace_id", "")
            )

            # In a real scenario, get the approved action from the approval system
            # For now, we'll propose and then execute (simplified flow)
            action = await self.remediation_agent.propose_remediation(analysis_result)

            if not action:
                return {
                    "status": "no_action",
                    "message": "No remediation action to execute"
                }

            # Execute the remediation
            execution_result = await self.remediation_agent.execute_remediation(action)
            
            # If execution was successful and we have a script to run, execute it
            if execution_result.success and hasattr(self.remediation_agent, '_last_script_path'):
                script_path = getattr(self.remediation_agent, '_last_script_path', None)
                if script_path and os.path.exists(script_path):
                    # Execute the script using terminal
                    import subprocess
                    try:
                        logger.info(f"Executing remediation script: {script_path}")
                        result = subprocess.run(['bash', script_path], 
                                              capture_output=True, text=True, timeout=300)
                        
                        if result.returncode == 0:
                            logger.info("Remediation script executed successfully")
                            execution_result.success = True
                        else:
                            logger.error(f"Remediation script failed: {result.stderr}")
                            execution_result.success = False
                            execution_result.error_message = result.stderr
                            
                    except subprocess.TimeoutExpired:
                        logger.error("Remediation script timed out")
                        execution_result.success = False
                        execution_result.error_message = "Script execution timed out"
                    except Exception as e:
                        logger.error(f"Failed to execute remediation script: {e}")
                        execution_result.success = False
                        execution_result.error_message = str(e)
                    finally:
                        # Clean up the script file
                        try:
                            os.unlink(script_path)
                            logger.debug(f"Cleaned up script file: {script_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up script file {script_path}: {e}")
                else:
                    logger.warning(f"Script file not found or does not exist: {script_path}")
                    execution_result.success = False
                    execution_result.error_message = "Remediation script not found"

            result = {
                "status": "completed",
                "action_id": action.action_id,
                "strategy": action.strategy.value,
                "target_service": action.target_service,
                "success": execution_result.success,
                "execution_time": execution_result.execution_time.isoformat(),
                "duration_seconds": execution_result.duration_seconds,
                "verification_status": execution_result.verification_status,
                "error_message": execution_result.error_message,
                "rollback_executed": getattr(execution_result, 'rollback_executed', False)
            }

            logger.info(f"REST remediation execution completed: {result['success']}")
            return result

        except Exception as e:
            logger.error(f"REST remediation execution failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


async def create_remediation_a2a_service(
    agent_id: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8002,
    metadata: Optional[Dict[str, Any]] = None
) -> RemediationA2AService:
    """
    Factory function to create a Remediation A2A service

    Args:
        agent_id: Optional agent ID
        host: Host to bind to
        port: Port to bind to
        metadata: Additional metadata for agent config

    Returns:
        Configured Remediation A2A service
    """
    if agent_id is None:
        agent_id = f"remediation_a2a_{int(asyncio.get_event_loop().time())}"

    if metadata is None:
        metadata = {}

    # Set default metadata if not provided
    metadata.setdefault("max_rollback_age_hours", 24)
    metadata.setdefault("verification_timeout_seconds", 300)
    metadata.setdefault("risk_tolerance", "medium")

    config = AgentConfig(
        agent_id=agent_id,
        agent_type="remediation-a2a",
        capabilities=[
            "remediation_planning",
            "service_recovery",
            "risk_assessment",
            "gemini_integration",
            "a2a_service"
        ],
        heartbeat_interval=30,
        health_check_interval=60,
        max_concurrent_tasks=5,
        metadata=metadata
    )

    service = RemediationA2AService(config, host, port)
    await service.initialize()

    return service


if __name__ == "__main__":
    # Example usage
    async def main():
        service = await create_remediation_a2a_service()
        await service.start()

    asyncio.run(main())