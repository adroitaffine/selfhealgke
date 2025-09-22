"""
A2A Service wrapper for the Audit Agent

This module exposes the Audit agent as an A2A service that can be called by other agents
or systems using the A2A protocol.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider
from a2a.server.agent_execution import AgentExecutor, RequestContext, SimpleRequestContextBuilder
from a2a.server.tasks import TaskStore, InMemoryTaskStore
from a2a.server.events import QueueManager, InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AFastAPIApplication

# Disable ADK before importing Audit agent to avoid validation issues
import agents.audit_agent as audit_module
audit_module.ADK_AVAILABLE = False

from .audit_agent import AuditAgent, ComplianceFramework, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class AuditAgentExecutor(AgentExecutor):
    """
    A2A AgentExecutor implementation that wraps the Audit agent
    """

    def __init__(self, audit_agent: AuditAgent):
        self.audit_agent = audit_agent
        logger.info("Audit AgentExecutor initialized")

    async def execute(self, task_id: str, request: Dict[str, Any], context: Optional[RequestContext] = None) -> Dict[str, Any]:
        """
        Execute an Audit task

        Args:
            task_id: Unique task identifier
            request: Request payload containing audit data
            context: Optional request context

        Returns:
            Audit result
        """
        try:
            logger.info(f"Executing Audit task {task_id}")

            # Extract request type and handle accordingly
            action = request.get("action", "log_event")

            if action == "log_event":
                return await self._handle_log_event(task_id, request)
            elif action == "get_audit_trail":
                return await self._handle_get_audit_trail(task_id, request)
            elif action == "generate_compliance_report":
                return await self._handle_generate_compliance_report(task_id, request)
            elif action == "check_compliance":
                return await self._handle_check_compliance(task_id, request)
            else:
                raise ValueError(f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Audit task {task_id} failed: {e}")
            return {
                "task_id": task_id,
                "error": str(e),
                "status": "error"
            }

    async def _handle_log_event(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle log event request"""
        event_data = request.get("event_data", {})
        event_type = AuditEventType(event_data.get("event_type", "system_health_check"))
        details = event_data.get("details", {})

        event_id = await self.audit_agent.log_event(
            event_type=event_type,
            event_data=details,
            incident_id=event_data.get("incident_id"),
            trace_id=event_data.get("trace_id"),
            agent_id=event_data.get("agent_id", "audit_agent"),
            user_id=event_data.get("user_id"),
            severity=AuditSeverity(event_data.get("severity", "medium")),
            correlation_id=event_data.get("correlation_id")
        )

        return {
            "task_id": task_id,
            "action": "log_event",
            "event_id": event_id,
            "status": "success"
        }

    async def _handle_get_audit_trail(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get audit trail request"""
        incident_id = request.get("incident_id")
        if not incident_id:
            raise ValueError("Missing incident_id for audit trail request")

        trail = await self.audit_agent.get_audit_trail(incident_id)
        if trail:
            return {
                "task_id": task_id,
                "action": "get_audit_trail",
                "incident_id": trail.incident_id,
                "trace_id": trail.trace_id,
                "created_at": trail.created_at.isoformat(),
                "updated_at": trail.updated_at.isoformat(),
                "events_count": trail.events_count,
                "total_duration": trail.total_duration,
                "agents_involved": trail.agents_involved,
                "users_involved": trail.users_involved,
                "compliance_status": trail.compliance_status,
                "violations": trail.violations,
                "timeline": trail.timeline,
                "status": "success"
            }
        else:
            return {
                "task_id": task_id,
                "action": "get_audit_trail",
                "error": "Audit trail not found",
                "status": "not_found"
            }

    async def _handle_generate_compliance_report(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generate compliance report request"""
        framework_name = request.get("framework", "soc2")
        days = request.get("days", 30)

        framework = ComplianceFramework(framework_name.lower())
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        report = await self.audit_agent.generate_compliance_report(
            framework, start_date, end_date
        )

        return {
            "task_id": task_id,
            "action": "generate_compliance_report",
            "report_id": report.report_id,
            "framework": report.framework,
            "report_period_start": report.report_period_start.isoformat(),
            "report_period_end": report.report_period_end.isoformat(),
            "generated_at": report.generated_at.isoformat(),
            "total_events": report.total_events,
            "compliance_score": report.compliance_score,
            "violations_count": report.violations_count,
            "remediation_success_rate": report.remediation_success_rate,
            "mean_response_time": report.mean_response_time,
            "recommendations": report.recommendations,
            "status": "success"
        }

    async def _handle_check_compliance(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check compliance request"""
        framework_name = request.get("framework", "soc2")
        incident_id = request.get("incident_id")

        framework = ComplianceFramework(framework_name.lower())
        events = await self.audit_agent.storage.retrieve_events(incident_id=incident_id)
        result = await self.audit_agent.compliance_engine.validate_compliance(events, framework)

        return {
            "task_id": task_id,
            "action": "check_compliance",
            "framework": framework_name,
            "incident_id": incident_id,
            "compliance_score": result["compliance_score"],
            "violations": result["violations"],
            "compliant": result["compliant"],
            "status": "success"
        }

    async def cancel(self, task_id: str) -> None:
        """
        Cancel a running task

        Args:
            task_id: Unique task identifier to cancel
        """
        logger.info(f"Cancelling Audit task {task_id}")
        # For now, just log the cancellation
        # In a real implementation, you might cancel the actual audit task


def create_audit_agent_card() -> AgentCard:
    """
    Create the AgentCard for the Audit agent service

    Returns:
        AgentCard describing the Audit agent's capabilities
    """
    return AgentCard(
        name="Audit Agent Service",
        description="Audit Agent for compliance tracking and audit trail management using ADK, A2A, and MCP",
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
                id="log_event_skill",
                name="log_event",
                description="Log an audit event with compliance tracking",
                tags=["audit", "compliance", "logging"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["log_event"]},
                        "event_data": {
                            "type": "object",
                            "properties": {
                                "event_type": {"type": "string"},
                                "details": {"type": "object"},
                                "incident_id": {"type": ["string", "null"]},
                                "trace_id": {"type": ["string", "null"]},
                                "agent_id": {"type": ["string", "null"]},
                                "user_id": {"type": ["string", "null"]},
                                "severity": {"type": "string"},
                                "correlation_id": {"type": ["string", "null"]}
                            },
                            "required": ["event_type", "details"]
                        }
                    },
                    "required": ["action", "event_data"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "action": {"type": "string"},
                        "event_id": {"type": "string"},
                        "status": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="get_audit_trail_skill",
                name="get_audit_trail",
                description="Retrieve complete audit trail for an incident",
                tags=["audit", "trail", "incident"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["get_audit_trail"]},
                        "incident_id": {"type": "string"}
                    },
                    "required": ["action", "incident_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "action": {"type": "string"},
                        "incident_id": {"type": "string"},
                        "trace_id": {"type": "string"},
                        "created_at": {"type": "string"},
                        "updated_at": {"type": "string"},
                        "events_count": {"type": "integer"},
                        "total_duration": {"type": "number"},
                        "agents_involved": {"type": "array", "items": {"type": "string"}},
                        "users_involved": {"type": "array", "items": {"type": "string"}},
                        "compliance_status": {"type": "object"},
                        "violations": {"type": "array"},
                        "timeline": {"type": "array"},
                        "status": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="generate_compliance_report_skill",
                name="generate_compliance_report",
                description="Generate compliance report for specified framework and period",
                tags=["compliance", "report", "audit"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["generate_compliance_report"]},
                        "framework": {"type": "string", "enum": ["soc2", "iso27001", "pci_dss"]},
                        "days": {"type": "integer", "default": 30}
                    },
                    "required": ["action"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "action": {"type": "string"},
                        "report_id": {"type": "string"},
                        "framework": {"type": "string"},
                        "report_period_start": {"type": "string"},
                        "report_period_end": {"type": "string"},
                        "generated_at": {"type": "string"},
                        "total_events": {"type": "integer"},
                        "compliance_score": {"type": "number"},
                        "violations_count": {"type": "integer"},
                        "remediation_success_rate": {"type": "number"},
                        "mean_response_time": {"type": "number"},
                        "recommendations": {"type": "array"},
                        "status": {"type": "string"}
                    }
                }
            ),
            AgentSkill(
                id="check_compliance_skill",
                name="check_compliance",
                description="Check compliance against a specific framework",
                tags=["compliance", "validation", "audit"],
                input_modes=["json-rpc"],
                output_modes=["json-rpc"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["check_compliance"]},
                        "framework": {"type": "string", "enum": ["soc2", "iso27001", "pci_dss"]},
                        "incident_id": {"type": ["string", "null"]}
                    },
                    "required": ["action"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "action": {"type": "string"},
                        "framework": {"type": "string"},
                        "incident_id": {"type": ["string", "null"]},
                        "compliance_score": {"type": "number"},
                        "violations": {"type": "array"},
                        "compliant": {"type": "boolean"},
                        "status": {"type": "string"}
                    }
                }
            )
        ],
        preferred_transport="http",
        default_input_modes=["json-rpc"],
        default_output_modes=["json-rpc"],
        url="http://localhost:8003",  # Default URL, can be overridden
        documentation_url="https://github.com/abhitalluri/selfhealgke/blob/main/agents/README.md"
    )


class AuditA2AService:
    """
    A2A Service wrapper for the Audit Agent
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8003):
        self.host = host
        self.port = port

        # Initialize Audit agent (will be initialized later in initialize method)
        # ADK is already disabled at module level
        config = {
            'storage': {'storage_backend': 'local'},
            'compliance_frameworks': ['soc2', 'iso27001', 'pci_dss'],
            'environment': 'development'
        }
        self.audit_agent = AuditAgent(config)

        # Create A2A components
        self.agent_card = create_audit_agent_card()
        self.agent_executor = AuditAgentExecutor(self.audit_agent)
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
        if hasattr(self.app, 'add_api_route'):
            self.app.add_api_route("/log_event", self.log_event_rest, methods=["POST"])
            self.app.add_api_route("/get_audit_trail", self.get_audit_trail_rest, methods=["POST"])
            self.app.add_api_route("/compliance_report", self.generate_compliance_report_rest, methods=["POST"])
            self.app.add_api_route("/check_compliance", self.check_compliance_rest, methods=["POST"])
            logger.info("Added REST endpoints for direct Audit calls")

        logger.info(f"Audit A2A Service initialized on {host}:{port}")

    async def initialize(self):
        """Initialize the Audit agent and A2A service"""
        await self.audit_agent.initialize()
        logger.info("Audit A2A Service fully initialized")

    async def start(self):
        """Start the A2A service"""
        import uvicorn

        # Update agent card URL
        self.agent_card.url = f"http://{self.host}:{self.port}"

        logger.info(f"Starting Audit A2A Service on {self.host}:{self.port}")

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
            logger.info("Audit A2A Service shutting down")
        finally:
            # Cleanup if needed
            pass

    async def log_event_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for direct audit event logging

        Args:
            request: Request containing event_data

        Returns:
            Logging result
        """
        try:
            logger.info("Received REST log event request")

            event_data = request.get("event_data", {})
            if not event_data:
                return {
                    "error": "Missing event_data in request",
                    "status": "error"
                }

            event_type = AuditEventType(event_data.get("event_type", "system_health_check"))
            details = event_data.get("details", {})

            event_id = await self.audit_agent.log_event(
                event_type=event_type,
                event_data=details,
                incident_id=event_data.get("incident_id"),
                trace_id=event_data.get("trace_id"),
                agent_id=event_data.get("agent_id", "audit_agent"),
                user_id=event_data.get("user_id"),
                severity=AuditSeverity(event_data.get("severity", "medium")),
                correlation_id=event_data.get("correlation_id")
            )

            result = {
                "status": "success",
                "event_id": event_id
            }

            logger.info(f"REST audit event logged: {event_id}")
            return result

        except Exception as e:
            logger.error(f"REST audit event logging failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_audit_trail_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for getting audit trail

        Args:
            request: Request containing incident_id

        Returns:
            Audit trail result
        """
        try:
            logger.info("Received REST get audit trail request")

            incident_id = request.get("incident_id")
            if not incident_id:
                return {
                    "error": "Missing incident_id in request",
                    "status": "error"
                }

            trail = await self.audit_agent.get_audit_trail(incident_id)
            if trail:
                result = {
                    "status": "success",
                    "incident_id": trail.incident_id,
                    "trace_id": trail.trace_id,
                    "created_at": trail.created_at.isoformat(),
                    "updated_at": trail.updated_at.isoformat(),
                    "events_count": trail.events_count,
                    "total_duration": trail.total_duration,
                    "agents_involved": trail.agents_involved,
                    "users_involved": trail.users_involved,
                    "compliance_status": trail.compliance_status,
                    "violations": trail.violations,
                    "timeline": trail.timeline
                }
            else:
                result = {
                    "status": "not_found",
                    "message": "Audit trail not found"
                }

            logger.info(f"REST audit trail retrieved for incident: {incident_id}")
            return result

        except Exception as e:
            logger.error(f"REST get audit trail failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def generate_compliance_report_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for generating compliance report

        Args:
            request: Request containing framework and days

        Returns:
            Compliance report result
        """
        try:
            logger.info("Received REST generate compliance report request")

            framework_name = request.get("framework", "soc2")
            days = request.get("days", 30)

            framework = ComplianceFramework(framework_name.lower())
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            report = await self.audit_agent.generate_compliance_report(
                framework, start_date, end_date
            )

            result = {
                "status": "success",
                "report_id": report.report_id,
                "framework": report.framework,
                "report_period_start": report.report_period_start.isoformat(),
                "report_period_end": report.report_period_end.isoformat(),
                "generated_at": report.generated_at.isoformat(),
                "total_events": report.total_events,
                "compliance_score": report.compliance_score,
                "violations_count": report.violations_count,
                "remediation_success_rate": report.remediation_success_rate,
                "mean_response_time": report.mean_response_time,
                "recommendations": report.recommendations
            }

            logger.info(f"REST compliance report generated: {report.report_id}")
            return result

        except Exception as e:
            logger.error(f"REST generate compliance report failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def check_compliance_rest(self, request: dict) -> Dict[str, Any]:
        """
        REST endpoint for checking compliance

        Args:
            request: Request containing framework and optional incident_id

        Returns:
            Compliance check result
        """
        try:
            logger.info("Received REST check compliance request")

            framework_name = request.get("framework", "soc2")
            incident_id = request.get("incident_id")

            framework = ComplianceFramework(framework_name.lower())
            events = await self.audit_agent.storage.retrieve_events(incident_id=incident_id)
            result_data = await self.audit_agent.compliance_engine.validate_compliance(events, framework)

            result = {
                "status": "success",
                "framework": framework_name,
                "incident_id": incident_id,
                "compliance_score": result_data["compliance_score"],
                "violations": result_data["violations"],
                "compliant": result_data["compliant"]
            }

            logger.info(f"REST compliance check completed for framework: {framework_name}")
            return result

        except Exception as e:
            logger.error(f"REST check compliance failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


async def create_audit_a2a_service(
    host: str = "0.0.0.0",
    port: int = 8003
) -> AuditA2AService:
    """
    Factory function to create an Audit A2A service

    Args:
        host: Host to bind to
        port: Port to bind to

    Returns:
        Configured Audit A2A service
    """
    service = AuditA2AService(host, port)
    await service.initialize()

    return service


if __name__ == "__main__":
    # Example usage
    async def main():
        service = await create_audit_a2a_service()
        await service.start()

    asyncio.run(main())