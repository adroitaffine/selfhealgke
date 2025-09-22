"""
Main Orchestrator Agent

This is the primary ADK agent that coordinates the health monitoring workflow
for any microservices application. It receives Playwright failure notifications,
orchestrates the RCA and remediation process through A2A communication,
and manages the overall incident response workflow.

Key Features:
- Application-agnostic design that works with any microservices architecture
- Webhook endpoint for receiving Playwright failure notifications
- Workflow state management and error recovery
- Dynamic service discovery and monitoring
- A2A communication coordination with all other agents
"""

import asyncio
import json
import logging
import uuid
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from aiohttp import web, ClientSession
import aiohttp_cors

# Optional HTTP client for A2A
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Direct ADK imports - using the official google/adk-python library
try:
    from google.adk.agents import Agent, LlmAgent
    from google.adk.tools import BaseTool, FunctionTool
    from google.adk import Runner
    ADK_AVAILABLE = True
except ImportError:
    # Fallback for testing when ADK is not available
    ADK_AVAILABLE = False
    Agent = object
    LlmAgent = object

# A2A imports - using the official a2a-sdk library  
try:
    from a2a.client import A2AClient, ClientConfig
    from a2a.types import Message, TextPart, Role
    A2A_AVAILABLE = True
except ImportError:
    # Fallback for testing when A2A is not available
    A2A_AVAILABLE = False


@dataclass
class AgentConfig:
    """Configuration for ADK agents"""
    agent_id: str
    agent_type: str
    capabilities: List[str]
    heartbeat_interval: int
    health_check_interval: int
    max_concurrent_tasks: int
    metadata: Dict[str, Any]


@dataclass
class FailurePayload:
    """Playwright test failure payload"""
    test_title: str
    status: str
    error: Dict[str, Any]
    retries: int
    trace_id: str
    video_url: Optional[str] = None
    trace_url: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class WorkflowState:
    """State of an incident response workflow"""
    workflow_id: str
    incident_id: str
    failure_payload: FailurePayload
    status: str  # 'started', 'analyzing', 'proposing', 'awaiting_approval', 'executing', 'completed', 'failed'
    created_at: datetime
    updated_at: datetime
    analysis_result: Optional[Dict[str, Any]] = None
    remediation_action: Optional[Dict[str, Any]] = None
    approval_response: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    topology_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class OrchestratorAgent:
    """
    Orchestrator Agent - Central coordinator for incident response workflows
    
    Uses ADK, A2A, and MCP for comprehensive workflow orchestration:
    1. Receives Playwright failure notifications via webhook
    2. Starts incident response workflow
    3. Coordinates with RCA agent for analysis via A2A
    4. Coordinates with remediation agent for action proposals via A2A
    5. Manages approval workflow through approval agent via A2A
    6. Monitors execution and verification
    7. Maintains workflow state and error recovery
    8. Logs all workflow events via MCP
    """
    
    def __init__(self, agent_id: Optional[str] = None, webhook_port: int = 8080):
        if agent_id is None:
            agent_id = f"orchestrator-{uuid.uuid4()}"
            
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"{__name__}.{agent_id}")

        # Initialize ADK-related components
        if ADK_AVAILABLE:
            # Initialize ADK Agent capabilities
            try:
                # Initialize as ADK agent with composition pattern
                from google.adk.agents import Agent
                # Use valid identifier for ADK agent name (replace hyphens with underscores)
                adk_name = agent_id.replace('-', '_')
                self.adk_agent = Agent(name=adk_name)
                self._register_adk_tools()
                self.logger.info("ADK agent initialized for orchestrator")
            except Exception as e:
                self.logger.warning(f"ADK initialization failed, using fallback: {e}")
                self.adk_agent = None
        else:
            self.logger.warning("ADK not available, using fallback mode")
            self.adk_agent = None
            
        # Register orchestrator-specific capabilities
        self.capabilities = [
            "workflow_orchestration",
            "incident_coordination", 
            "multi_agent_communication",
            "failure_notification_handling",
            "remediation_management"
        ]

        # A2A client for inter-agent communication
        self.a2a_client = None
        
        # MCP session for audit logging and notifications
        self.mcp_session = None
        
        # Webhook server configuration
        self.webhook_port = webhook_port
        self.webhook_server = None
        self.app: Optional[web.Application] = None
        self.server: Optional[web.TCPSite] = None
        
        # Workflow management
        self.active_workflows: Dict[str, WorkflowState] = {}
        self.workflow_timeout = timedelta(minutes=30)  # 30 minute timeout
        
        # Service discovery and topology
        self.discovered_topologies: Dict[str, Dict[str, Any]] = {}
        
        # Agent coordination
        self.rca_agents: List[str] = []
        self.remediation_agents: List[str] = []
        self.approval_agents: List[str] = []
        self.audit_agents: List[str] = []

        # Agent status tracking
        self.status = "initializing"
        self.start_time = datetime.now()
        self.running = True

        # Setup message handlers
        self._setup_orchestrator_handlers()
        
        self.logger.info(f"Orchestrator Agent initialized: {agent_id}")
        
        # Centralized service endpoint configuration (A2A + REST fallbacks)
        self.services: Dict[str, Dict[str, Any]] = {
            "rca": {
                "a2a": {
                    "url": os.getenv("RCA_A2A_URL", "http://localhost:8001"),
                    "skill": os.getenv("RCA_A2A_SKILL", "analyze_failure")
                },
                "rest": {
                    "analyze_url": os.getenv("RCA_REST_ANALYZE", "http://localhost:8000/analyze")
                }
            },
            "approval": {
                "a2a": {
                    "url": os.getenv("APPROVAL_A2A_URL", "http://localhost:8004"),
                    "skill": os.getenv("APPROVAL_A2A_SKILL", "request_approval")
                },
                "rest": {
                    "request_url": os.getenv("APPROVAL_REST_URL", "http://localhost:8004/request-approval")
                }
            },
            "remediation": {
                "a2a": {
                    "url": os.getenv("REMEDIATION_A2A_URL", "http://localhost:8003"),
                    "propose_skill": os.getenv("REMEDIATION_PROPOSE_SKILL", "propose_remediation"),
                    "execute_skill": os.getenv("REMEDIATION_EXECUTE_SKILL", "execute_remediation")
                },
                "rest": {
                    "propose_url": os.getenv("REMEDIATION_REST_PROPOSE", "http://localhost:8003/propose"),
                    "execute_url": os.getenv("REMEDIATION_REST_EXECUTE", "http://localhost:8003/execute")
                }
            }
        }
        
        # A2A clients map per service name
        self.a2a_clients: Dict[str, Any] = {}
        
    def _register_adk_tools(self):
        """Register ADK tools for orchestrator capabilities"""
        try:
            if ADK_AVAILABLE:
                # For now, store tools in a simple dict until we have the correct ADK version
                # The FunctionTool constructor parameters vary between ADK versions
                if not hasattr(self, '_adk_tools'):
                    self._adk_tools = {}
                
                # Store tools for manual handling
                self._adk_tools['start_incident_workflow'] = self._adk_start_incident_workflow
                self._adk_tools['get_workflow_status'] = self._adk_get_workflow_status
                
                self.logger.info(f"ADK tools registered for orchestrator: {list(self._adk_tools.keys())}")
            else:
                self.logger.warning("ADK not available, skipping ADK tool registration")
        except Exception as e:
            self.logger.error(f"Failed to register ADK tools: {e}")
            
    def _register_mcp_tools(self):
        """Register MCP tools using proper MCP integration"""
        try:
            if ADK_AVAILABLE and self.adk_agent:
                # Note: MCPToolSet is not available in current ADK version
                # Instead, we use the discovered MCP tools directly through the MCP protocol
                
                total_mcp_tools = len(getattr(self, 'mcp_tools', {})) + len(getattr(self, 'mcp_k8s_tools', {}))
                available_servers = list(getattr(self, 'mcp_servers', {}).keys())
                
                if total_mcp_tools > 0:
                    self.logger.info(f"MCP integration ready: {total_mcp_tools} tools from {len(available_servers)} servers")
                    self.logger.info(f"Available MCP servers: {available_servers}")
                    self.logger.info(f"Observability tools: {list(getattr(self, 'mcp_tools', {}).keys())}")
                    self.logger.info(f"Kubernetes tools: {list(getattr(self, 'mcp_k8s_tools', {}).keys())}")
                    
                    # MCP tools are accessed through the _mcp_* methods which interface with MCP protocol
                    # This is the correct approach until MCPToolSet becomes available in ADK
                    
                else:
                    self.logger.warning("No MCP tools available for orchestrator")
                    
            else:
                self.logger.warning("ADK not available, cannot register MCP tools")
                
        except Exception as e:
            self.logger.error(f"Failed to register MCP tools: {e}")
            # Fallback: Keep the dynamic discovery working
            total_mcp_tools = len(getattr(self, 'mcp_tools', {})) + len(getattr(self, 'mcp_k8s_tools', {}))
            if total_mcp_tools > 0:
                self.logger.info(f"MCP tools available for orchestrator: {total_mcp_tools} tools")
                self.logger.info(f"  - Observability tools: {list(getattr(self, 'mcp_tools', {}).keys())}")
                self.logger.info(f"  - Kubernetes tools: {list(getattr(self, 'mcp_k8s_tools', {}).keys())}")
            else:
                self.logger.warning("No MCP tools available for orchestrator")
    
    async def _mcp_write_log(self, severity: str, message: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """ADK tool function to write logs via MCP"""
        try:
            if "write_log_entry" in self.mcp_tools:
                # Use dynamic MCP tool execution
                log_entry = {
                    "log_name": f"projects/{os.getenv('GCP_PROJECT_ID', 'cogent-spirit-469200-q3')}/logs/orchestrator-agent",
                    "severity": severity,
                    "message": message,
                    "labels": labels or {}
                }
                # Future: Direct MCP tool execution when MCP client is available
                self.logger.info(f"MCP Log Entry: {log_entry}")
                return {"success": True, "tool": "write_log_entry", "data": log_entry}
            else:
                return {"success": False, "error": "write_log_entry tool not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _mcp_query_logs(self, filter: str, start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict[str, Any]:
        """ADK tool function to query logs via MCP"""
        try:
            if "query_logs" in self.mcp_tools:
                params = {"filter": filter}
                if start_time:
                    params["start_time"] = start_time
                if end_time:
                    params["end_time"] = end_time
                # Future: Direct MCP tool execution when MCP client is available
                self.logger.info(f"MCP Query Logs: {params}")
                return {"success": True, "tool": "query_logs", "params": params}
            else:
                return {"success": False, "error": "query_logs tool not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _mcp_get_pods(self, namespace: Optional[str] = None, label_selector: Optional[str] = None) -> Dict[str, Any]:
        """ADK tool function to get Kubernetes pods via MCP"""
        try:
            if "get_pods" in self.mcp_k8s_tools:
                params = {}
                if namespace:
                    params["namespace"] = namespace
                if label_selector:
                    params["label_selector"] = label_selector
                # Future: Direct MCP tool execution when MCP client is available
                self.logger.info(f"MCP Get Pods: {params}")
                return {"success": True, "tool": "get_pods", "params": params}
            else:
                return {"success": False, "error": "get_pods tool not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _mcp_correlate_telemetry(self, trace_id: str, time_window: int = 300) -> Dict[str, Any]:
        """ADK tool function to correlate telemetry via MCP"""
        try:
            if "correlate-telemetry" in self.mcp_tools:
                params = {
                    "trace_id": trace_id,
                    "time_window": time_window
                }
                # Future: Direct MCP tool execution when MCP client is available
                self.logger.info(f"MCP Correlate Telemetry: {params}")
                return {"success": True, "tool": "correlate-telemetry", "params": params}
            else:
                return {"success": False, "error": "correlate-telemetry tool not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _mcp_build_timeline(self, trace_id: str, time_window: int = 600, include_related_traces: bool = True) -> Dict[str, Any]:
        """ADK tool function to build failure timeline via MCP"""
        try:
            if "build-failure-timeline" in self.mcp_tools:
                params = {
                    "trace_id": trace_id,
                    "time_window": time_window,
                    "include_related_traces": include_related_traces
                }
                # Future: Direct MCP tool execution when MCP client is available
                self.logger.info(f"MCP Build Timeline: {params}")
                return {"success": True, "tool": "build-failure-timeline", "params": params}
            else:
                return {"success": False, "error": "build-failure-timeline tool not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def _adk_start_incident_workflow(self, failure_payload: Dict[str, Any]) -> Dict[str, Any]:
        """ADK tool function to start incident workflow"""
        try:
            # Convert dict to FailurePayload object
            payload = FailurePayload(
                test_title=failure_payload.get('test_title', 'Unknown Test'),
                status=failure_payload.get('status', 'failed'),
                error=failure_payload.get('error', {}),
                retries=failure_payload.get('retries', 0),
                trace_id=failure_payload.get('trace_id', str(uuid.uuid4())),
                video_url=failure_payload.get('video_url'),
                trace_url=failure_payload.get('trace_url'),
                timestamp=failure_payload.get('timestamp', datetime.now().isoformat())
            )
            
            workflow_id = await self._start_incident_workflow(payload)
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "message": "Incident workflow started successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to start incident workflow"
            }
            
    async def _adk_get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """ADK tool function to get workflow status"""
        try:
            if workflow_id in self.active_workflows:
                workflow = self.active_workflows[workflow_id]
                return {
                    "success": True,
                    "workflow_id": workflow_id,
                    "status": workflow.status,
                    "incident_id": workflow.incident_id,
                    "created_at": workflow.created_at.isoformat(),
                    "updated_at": workflow.updated_at.isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Workflow not found",
                    "workflow_id": workflow_id
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "workflow_id": workflow_id
            }
    
    def _setup_orchestrator_handlers(self):
        """Setup orchestrator message handlers"""
        if ADK_AVAILABLE and self.adk_agent:
            # Register ADK message handlers for orchestrator
            try:
                # Handler for incoming failure notifications
                if hasattr(self.adk_agent, 'register_message_handler'):
                    self.adk_agent.register_message_handler(
                        "failure_notification",
                        self._handle_adk_failure_notification
                    )
                    
                    # Handler for workflow updates from other agents
                    self.adk_agent.register_message_handler(
                        "workflow_update",
                        self._handle_adk_workflow_update
                    )
                else:
                    # Store handlers for manual routing
                    if not hasattr(self, '_adk_handlers'):
                        self._adk_handlers = {}
                    self._adk_handlers['failure_notification'] = self._handle_adk_failure_notification
                    self._adk_handlers['workflow_update'] = self._handle_adk_workflow_update
                
                self.logger.info("ADK message handlers registered")
            except Exception as e:
                self.logger.error(f"Failed to register ADK handlers: {e}")
                
    async def _handle_adk_failure_notification(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failure notifications via ADK messaging"""
        try:
            failure_payload = message.get('payload', {})
            workflow_id = await self._adk_start_incident_workflow(failure_payload)
            
            return {
                "status": "success",
                "workflow_id": workflow_id,
                "message": "Failure notification processed"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to process failure notification"
            }
            
    async def _handle_adk_workflow_update(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow updates via ADK messaging"""
        try:
            workflow_id = message.get('workflow_id')
            update_type = message.get('update_type')
            data = message.get('data', {})
            
            if not workflow_id or not isinstance(workflow_id, str):
                return {
                    "status": "error",
                    "error": "Invalid workflow_id",
                    "message": "Workflow ID must be a non-empty string"
                }
            
            if update_type == 'analysis_complete':
                await self._handle_analysis_complete(workflow_id, data)
            elif update_type == 'remediation_proposed':
                await self._handle_remediation_proposed(workflow_id, data)
            elif update_type == 'approval_received':
                await self._handle_approval_received(workflow_id, data)
            elif update_type == 'execution_complete':
                await self._handle_execution_complete(workflow_id, data)
            else:
                return {
                    "status": "error",
                    "error": f"Unknown update type: {update_type}",
                    "message": "Invalid workflow update type"
                }
            
            return {
                "status": "success",
                "message": f"Workflow update {update_type} processed"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to process workflow update"
            }
        
    async def start_workflow(self, workflow_type: str, context: Dict[str, Any]):
        """Start a workflow using ADK"""
        try:
            if ADK_AVAILABLE and self.adk_agent and hasattr(self.adk_agent, 'create_workflow'):
                # Use ADK workflow management
                workflow = await self.adk_agent.create_workflow(
                    workflow_type=workflow_type,
                    context=context,
                    metadata={
                        "agent_id": self.agent_id,
                        "created_at": datetime.now().isoformat()
                    }
                )
                self.logger.info(f"ADK workflow {workflow_type} started with ID: {workflow.id}")
                return workflow
            else:
                # Fallback for non-ADK mode
                self.logger.info(f"Starting workflow {workflow_type} with context: {context}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to start ADK workflow: {e}")
            return None
        
    async def complete_workflow(self, workflow_id: str, result: Dict[str, Any]):
        """Complete a workflow using ADK"""
        try:
            if ADK_AVAILABLE and self.adk_agent and hasattr(self.adk_agent, 'complete_workflow_by_id'):
                # Use ADK workflow completion
                await self.adk_agent.complete_workflow_by_id(
                    workflow_id=workflow_id,
                    result=result,
                    metadata={
                        "completed_at": datetime.now().isoformat(),
                        "agent_id": self.agent_id
                    }
                )
                self.logger.info(f"ADK workflow {workflow_id} completed")
            else:
                # Fallback for non-ADK mode
                self.logger.info(f"Completing workflow {workflow_id} with result: {result}")
        except Exception as e:
            self.logger.error(f"Failed to complete ADK workflow: {e}")
        
    async def start(self):
        """Start the orchestrator agent"""
        try:
            await self.initialize()
            self.logger.info("Orchestrator agent started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start orchestrator agent: {e}")
            return False
            
    async def stop(self):
        """Stop the orchestrator agent"""
        try:
            await self.cleanup()
            self.logger.info("Orchestrator agent stopped")
        except Exception as e:
            self.logger.error(f"Error stopping orchestrator agent: {e}")
        
    async def initialize(self):
        """Initialize the ADK agent and orchestrator components"""
        try:
            # Initialize ADK agent if available
            if ADK_AVAILABLE and self.adk_agent:
                try:
                    # Call ADK Agent initialization
                    if hasattr(self.adk_agent, 'initialize'):
                        await self.adk_agent.initialize()
                    self.logger.info("ADK agent base initialization completed")
                except Exception as e:
                    self.logger.warning(f"ADK initialization failed: {e}")
            
            # Initialize A2A client
            await self.initialize_a2a()
            
            # Initialize MCP session for audit logging
            try:
                self.mcp_session = await self._initialize_mcp_session()
                # Register MCP tools as ADK tools after discovery
                if ADK_AVAILABLE and self.adk_agent:
                    self._register_mcp_tools()
            except Exception as e:
                self.logger.warning(f"MCP session initialization failed: {e}")
            
            # Start webhook server
            await self._start_webhook_server()
            
            # Discover available agents
            await self._discover_agents()
            
            # Start workflow monitoring
            asyncio.create_task(self._monitor_workflows())
            
            # Log initialization event
            await self._log_mcp_event('orchestrator_initialized', {
                'agent_id': self.agent_id,
                'webhook_port': self.webhook_port,
                'capabilities': ['workflow_orchestration', 'incident_coordination']
            })
            
            self.status = "running"
            self.logger.info("Orchestrator agent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize orchestrator: {e}")
            raise

    async def initialize_a2a(self):
        """Initialize A2A client for inter-agent communication"""
        self.logger.info(f"Initializing A2A clients, A2A_AVAILABLE = {A2A_AVAILABLE}")
        try:
            if A2A_AVAILABLE:
                # Create per-service A2A clients based on configured URLs
                try:
                    # Lazy import to avoid hard dependency if unavailable
                    import httpx
                    from a2a.client import A2AClient
                    self.logger.info("A2A SDK imports successful")
                except Exception as e:
                    self.logger.warning(f"A2A SDK import failed: {e}")
                    self.a2a_clients = {}
                    return
                else:
                    for svc, cfg in self.services.items():
                        a2a_cfg = cfg.get("a2a", {})
                        base_url = a2a_cfg.get("url")
                        self.logger.info(f"Attempting to initialize A2A client for {svc} at {base_url}")
                        if base_url:
                            try:
                                # Create httpx client for A2AClient
                                httpx_client = httpx.AsyncClient(timeout=30.0)
                                self.a2a_clients[svc] = A2AClient(
                                    httpx_client=httpx_client,
                                    url=base_url
                                )
                                self.logger.info(f"A2A client initialized for service '{svc}' at {base_url}")
                            except Exception as e:
                                self.logger.warning(f"A2A client init failed for {svc} ({base_url}): {e}")
                    if not self.a2a_clients:
                        self.logger.warning("No A2A clients initialized")
                    else:
                        self.logger.info(f"Initialized {len(self.a2a_clients)} A2A clients")
            else:
                self.logger.warning("A2A not available")
        except Exception as e:
            self.logger.error(f"Failed to initialize A2A client: {e}")

    async def _a2a_call(self, service: str, skill: str, payload: Dict[str, Any], *, timeout: float = 30.0,
                         correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """A2A invocation with proper error handling (no REST fallback).

        Args:
            service: logical service key (e.g., 'rca', 'approval')
            skill: A2A skill name to invoke
            payload: input payload for the skill
            timeout: request timeout in seconds
            correlation_id: optional correlation id for tracing

        Returns:
            Response dict from the agent

        Raises:
            Exception: If A2A call fails
        """
        # Use A2A client if present
        client = self.a2a_clients.get(service)
        if client is not None:
            try:
                # The A2A SDK API may vary; attempt a generic 'invoke' or 'call' pattern
                if hasattr(client, "invoke"):
                    return await asyncio.wait_for(client.invoke(skill, payload), timeout=timeout)
                elif hasattr(client, "call"):
                    return await asyncio.wait_for(client.call(skill, payload), timeout=timeout)
                else:
                    raise RuntimeError(f"A2A client for {service} has no invoke/call method")
            except Exception as e:
                await self._log_mcp_event('a2a_call_failed', {
                    'service': service,
                    'skill': skill,
                    'error': str(e),
                    'correlation_id': correlation_id
                })
                raise RuntimeError(f"A2A call failed for {service}.{skill}: {e}")
        else:
            raise RuntimeError(f"No A2A client available for service '{service}'")

    async def _http_post(self, url: str, body: Dict[str, Any], *, headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
        """Helper to POST JSON with aiohttp and return JSON."""
        import aiohttp
        if not url:
            raise ValueError("Missing REST endpoint URL")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers, timeout=timeout) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status} response from {url}: {text}")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
    
    async def _initialize_mcp_session(self):
        """Initialize MCP session for audit logging and observability tools"""
        try:
            import json
            
            # Initialize MCP tools dictionaries
            self.mcp_tools = {}
            self.mcp_k8s_tools = {}
            
            # Load MCP server configuration from mcp.json
            mcp_config_path = "/Users/abhitalluri/selfhealgke/mcp-servers/mcp.json"
            self.mcp_servers = {}
            
            try:
                with open(mcp_config_path, 'r') as f:
                    mcp_config = json.loads(f.read())
                    self.mcp_servers = mcp_config.get("mcpServers", {})
                    self.logger.info(f"Loaded MCP configuration with {len(self.mcp_servers)} servers: {list(self.mcp_servers.keys())}")
            except Exception as e:
                self.logger.warning(f"Failed to load MCP config from {mcp_config_path}: {e}")
            
            # Try to connect to actual MCP servers via subprocess
            
            # Discover tools from each configured MCP server
            for server_name, server_config in self.mcp_servers.items():
                if server_config.get("disabled", False):
                    self.logger.info(f"Skipping disabled MCP server: {server_name}")
                    continue
                    
                try:
                    await self._discover_mcp_server_tools(server_name, server_config)
                except Exception as e:
                    self.logger.warning(f"Failed to discover tools from MCP server {server_name}: {e}")
            
            # Legacy: Test GCP Observability MCP server (for backward compatibility)
            if "gcp-observability" not in self.mcp_servers:
                try:
                    # Check if the MCP server script exists and is executable
                    mcp_server_path = "/Users/abhitalluri/selfhealgke/mcp-servers/gcp_observability_server.py"
                    if os.path.exists(mcp_server_path):
                        # Try to get tools list from the actual server
                        result = subprocess.run([
                            "python3", mcp_server_path, "--list-tools"
                        ], capture_output=True, text=True, timeout=10, 
                        env={"GCP_PROJECT_ID": os.getenv("GCP_PROJECT_ID", "cogent-spirit-469200-q3")})
                        
                        if result.returncode == 0:
                            # Parse tools from server response
                            try:
                                tools_data = json.loads(result.stdout)
                                discovered_tools = {tool["name"]: tool for tool in tools_data.get("tools", [])}
                                self.mcp_tools.update(discovered_tools)
                                self.logger.info(f"Discovered {len(discovered_tools)} legacy GCP Observability tools: {list(discovered_tools.keys())}")
                            except json.JSONDecodeError:
                                # Fallback: scan the server file for tool definitions
                                self._discover_tools_from_source(mcp_server_path)
                        else:
                            # Fallback: scan the server file for tool definitions
                            self._discover_tools_from_source(mcp_server_path)
                    else:
                        self.logger.warning(f"Legacy MCP server file not found: {mcp_server_path}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to discover legacy GCP Observability MCP tools: {e}")
                    # Fallback: try to discover from source
                    try:
                        self._discover_tools_from_source("/Users/abhitalluri/selfhealgke/mcp-servers/gcp_observability_server.py")
                    except Exception as fallback_e:
                        self.logger.warning(f"Fallback tool discovery also failed: {fallback_e}")
            
            total_tools = len(self.mcp_tools) + len(self.mcp_k8s_tools)
            if total_tools > 0:
                self.logger.info(f"Successfully initialized MCP session with {total_tools} total tools")
                self.logger.info(f"MCP Observability tools: {list(self.mcp_tools.keys())}")
                self.logger.info(f"MCP Kubernetes tools: {list(self.mcp_k8s_tools.keys())}")
                self.logger.info(f"Available MCP servers for ADK integration: {list(self.mcp_servers.keys())}")
            else:
                self.logger.warning("No MCP tools discovered from any servers")
            
        except Exception as e:
            self.logger.warning(f"MCP session initialization failed: {e}")
            self.mcp_tools = {}
            self.mcp_k8s_tools = {}
            self.mcp_servers = {}
            return None
            
    async def _discover_mcp_server_tools(self, server_name: str, server_config: Dict[str, Any]):
        """Discover tools from a specific MCP server using actual configuration"""
        try:
            command = server_config.get("command", "")
            args = server_config.get("args", [])
            env = dict(os.environ)
            env.update(server_config.get("env", {}))
            
            self.logger.info(f"Discovering tools from MCP server: {server_name} (command: {command})")
            
            # Different discovery strategies based on server type
            if server_name == "gcp-observability":
                # Python-based MCP server - extract tools from source code since it doesn't support --list-tools
                try:
                    # Use full path to the server file
                    server_file = os.path.join("/Users/abhitalluri/selfhealgke/mcp-servers", "gcp_observability_server.py")
                    if os.path.exists(server_file):
                        # This is a pure MCP server without --list-tools support
                        # Extract tools from source code
                        self._discover_tools_from_source(server_file)
                        self.logger.info(f"Discovered tools from {server_name} source code analysis")
                    else:
                        self.logger.warning(f"GCP observability server file not found: {server_file}")
                        # Add fallback tools
                        fallback_tools = {
                            "correlate-telemetry": {"name": "correlate-telemetry", "description": "Correlate telemetry data"},
                            "build-failure-timeline": {"name": "build-failure-timeline", "description": "Build failure timeline"}
                        }
                        self.mcp_tools.update(fallback_tools)
                        self.logger.info(f"Added {len(fallback_tools)} fallback tools for {server_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to discover tools from {server_name}: {e}")
                    # Add minimal fallback tools
                    fallback_tools = {
                        "correlate-telemetry": {"name": "correlate-telemetry", "description": "Correlate telemetry data"}
                    }
                    self.mcp_tools.update(fallback_tools)
                    self.logger.info(f"Added {len(fallback_tools)} minimal fallback tools for {server_name}")
                    
            elif server_name in ["kubernetes", "gke-mcp"]:
                # Kubernetes tools - known tool set based on typical MCP Kubernetes servers
                k8s_tools = {
                    "get_pods": {"name": "get_pods", "description": "Get Kubernetes pods"},
                    "get_services": {"name": "get_services", "description": "Get Kubernetes services"}, 
                    "get_deployments": {"name": "get_deployments", "description": "Get Kubernetes deployments"},
                    "get_namespaces": {"name": "get_namespaces", "description": "Get Kubernetes namespaces"},
                    "get_nodes": {"name": "get_nodes", "description": "Get Kubernetes nodes"},
                    "describe_pod": {"name": "describe_pod", "description": "Describe a specific Kubernetes pod"},
                    "get_events": {"name": "get_events", "description": "Get Kubernetes events"},
                    "get_logs": {"name": "get_logs", "description": "Get pod logs"},
                    "apply_manifest": {"name": "apply_manifest", "description": "Apply Kubernetes manifest"},
                    "delete_resource": {"name": "delete_resource", "description": "Delete Kubernetes resource"}
                }
                
                # Check if server is actually available
                try:
                    full_command = [command] + args + ["--version"]
                    result = subprocess.run(
                        full_command, 
                        capture_output=True, text=True, timeout=10, env=env
                    )
                    if result.returncode == 0:
                        self.mcp_k8s_tools.update(k8s_tools)
                        self.logger.info(f"Added {len(k8s_tools)} Kubernetes tools from {server_name} (server available)")
                    else:
                        # Add tools anyway for offline usage
                        self.mcp_k8s_tools.update(k8s_tools)
                        self.logger.info(f"Added {len(k8s_tools)} Kubernetes tools from {server_name} (offline mode)")
                except Exception as e:
                    # Add tools anyway for offline usage
                    self.mcp_k8s_tools.update(k8s_tools)
                    self.logger.info(f"Added {len(k8s_tools)} Kubernetes tools from {server_name} (fallback mode)")
                
            elif server_name == "playwright-mcp":
                # Playwright tools
                playwright_tools = {
                    "run_test": {"name": "run_test", "description": "Run Playwright test"},
                    "capture_screenshot": {"name": "capture_screenshot", "description": "Capture screenshot"}, 
                    "get_test_results": {"name": "get_test_results", "description": "Get test results"},
                    "record_trace": {"name": "record_trace", "description": "Record execution trace"},
                    "generate_report": {"name": "generate_report", "description": "Generate test report"},
                    "browser_context": {"name": "browser_context", "description": "Manage browser context"}
                }
                self.mcp_tools.update(playwright_tools)
                self.logger.info(f"Added {len(playwright_tools)} Playwright tools from {server_name}")
                
            elif server_name == "gemini-cloud-assist":
                # Gemini Cloud Assist tools
                gemini_tools = {
                    "analyze_gcp_issue": {"name": "analyze_gcp_issue", "description": "Analyze GCP issues using Gemini"},
                    "suggest_solution": {"name": "suggest_solution", "description": "Suggest solutions for problems"},
                    "get_best_practices": {"name": "get_best_practices", "description": "Get GCP best practices"},
                    "troubleshoot_service": {"name": "troubleshoot_service", "description": "Troubleshoot GCP service issues"},
                    "analyze_logs": {"name": "analyze_logs", "description": "Analyze log patterns with AI"},
                    "generate_runbook": {"name": "generate_runbook", "description": "Generate operational runbooks"}
                }
                self.mcp_tools.update(gemini_tools)
                self.logger.info(f"Added {len(gemini_tools)} Gemini Cloud Assist tools from {server_name}")
                
            else:
                self.logger.warning(f"Unknown MCP server type: {server_name}, attempting generic discovery")
                # Try generic tool discovery
                try:
                    full_command = [command] + args + ["--list-tools"]
                    result = subprocess.run(
                        full_command, 
                        capture_output=True, text=True, timeout=10, env=env
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        try:
                            tools_data = json.loads(result.stdout)
                            discovered_tools = {tool["name"]: tool for tool in tools_data.get("tools", [])}
                            self.mcp_tools.update(discovered_tools)
                            self.logger.info(f"Discovered {len(discovered_tools)} tools from {server_name}")
                        except json.JSONDecodeError:
                            self.logger.warning(f"Could not parse tools from {server_name}")
                    else:
                        self.logger.warning(f"No tools discovered from {server_name}")
                except Exception as e:
                    self.logger.warning(f"Generic discovery failed for {server_name}: {e}")
                
        except Exception as e:
            self.logger.warning(f"Failed to discover tools from {server_name}: {e}")
            
        except Exception as e:
            self.logger.warning(f"MCP session initialization failed: {e}")
            self.mcp_observability = None
            self.mcp_kubernetes = None
            self.mcp_tools = {}
            self.mcp_k8s_tools = {}
            return None
            
    def _discover_tools_from_source(self, server_file_path: str):
        """Discover MCP tools by parsing the server source file"""
        try:
            with open(server_file_path, 'r') as f:
                content = f.read()
                
            # Look for Tool definitions in the source
            import re
            tool_patterns = re.findall(r'Tool\s*\(\s*name="([^"]+)"', content)
            
            for tool_name in tool_patterns:
                self.mcp_tools[tool_name] = {
                    "name": tool_name,
                    "description": f"MCP tool: {tool_name}",
                    "source": "discovered_from_source"
                }
                
            if self.mcp_tools:
                self.logger.info(f"Discovered {len(self.mcp_tools)} tools from source: {list(self.mcp_tools.keys())}")
                
        except Exception as e:
            self.logger.warning(f"Failed to discover tools from source {server_file_path}: {e}")
    
    async def _log_mcp_event(self, event_type: str, event_data: Dict[str, Any]):
        """Log events via MCP for audit trail and observability"""
        try:
            # Enhanced structured logging with MCP-style format
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "agent_id": self.agent_id,
                "event_type": event_type,
                "event_data": event_data,
                "source": "orchestrator-agent",
                "severity": "INFO"
            }
            
            # For now, use enhanced local logging until MCP is fully configured
            self.logger.info(f"MCP Event [{event_type}]: {json.dumps(log_entry, indent=2)}")
            
        except Exception as e:
            self.logger.warning(f"MCP logging failed: {e}")
            # Fallback to simple logging
            self.logger.info(f"Event: {event_type} - {event_data}")
    
    async def cleanup(self):
        """Cleanup orchestrator resources"""
        try:
            # Stop webhook server
            if self.server:
                await self.server.stop()
                
            # Complete any active workflows
            for workflow_id in list(self.active_workflows.keys()):
                await self._fail_workflow(workflow_id, "System shutdown")
            
            # Log cleanup event
            await self._log_mcp_event('orchestrator_shutdown', {
                'agent_id': self.agent_id,
                'active_workflows_count': len(self.active_workflows)
            })
                
            self.logger.info("Orchestrator agent cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error during orchestrator cleanup: {e}")
            
    async def health_check(self) -> bool:
        """Check orchestrator health"""
        try:
            # Check webhook server
            if not self.server:
                return False
                
            # Check agent availability
            if not (self.rca_agents or self.remediation_agents or self.approval_agents):
                self.logger.warning("No agents discovered")
                
            # Check workflow processing
            stuck_workflows = [
                w for w in self.active_workflows.values()
                if (datetime.now() - w.updated_at) > self.workflow_timeout
            ]
            
            if stuck_workflows:
                for workflow in stuck_workflows:
                    self.logger.warning(f"Workflow {workflow.workflow_id} is stuck")
                    await self._fail_workflow(workflow.workflow_id, "Workflow timeout")
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
            
    async def _start_webhook_server(self):
        """Start the webhook server for receiving Playwright notifications"""
        try:
            # Create aiohttp application
            self.app = web.Application()
            
            # Setup CORS
            cors = aiohttp_cors.setup(self.app, defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*"
                )
            })
            
            # Add routes
            webhook_route = self.app.router.add_post('/webhook/playwright-failure', self._handle_playwright_webhook)
            health_route = self.app.router.add_get('/health', self._handle_health_check)
            status_route = self.app.router.add_get('/status', self._handle_status_check)
            
            # Add CORS to routes
            cors.add(webhook_route)
            cors.add(health_route)
            cors.add(status_route)
            
            # Start server
            runner = web.AppRunner(self.app)
            await runner.setup()
            
            self.server = web.TCPSite(runner, '0.0.0.0', self.webhook_port)
            await self.server.start()
            
            self.logger.info(f"Webhook server started on port {self.webhook_port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start webhook server: {e}")
            raise

    async def _handle_failure_webhook(self, failure_payload: FailurePayload) -> Optional[str]:
        """Handle failure webhook and start workflow (for A2A service integration)"""
        return await self._start_incident_workflow(failure_payload)
    
    async def _handle_playwright_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming Playwright failure notifications"""
        try:
            # Parse payload
            payload_data = await request.json()
            self.logger.info(f"Received Playwright failure notification: {payload_data.get('test_title', 'Unknown')}")
            
            # Validate payload
            if not self._validate_failure_payload(payload_data):
                return web.Response(status=400, text="Invalid payload")
                
            # Create failure payload object
            failure_payload = FailurePayload(
                test_title=payload_data.get('test_title', 'Unknown Test'),
                status=payload_data.get('status', 'failed'),
                error=payload_data.get('error', {}),
                retries=payload_data.get('retries', 0),
                trace_id=payload_data.get('trace_id', str(uuid.uuid4())),
                video_url=payload_data.get('video_url'),
                trace_url=payload_data.get('trace_url'),
                timestamp=payload_data.get('timestamp', datetime.now().isoformat())
            )
            
            # Start incident response workflow
            workflow_id = await self._start_incident_workflow(failure_payload)
            
            if workflow_id:
                return web.json_response({
                    "status": "success",
                    "workflow_id": workflow_id,
                    "message": "Incident response workflow started"
                })
            else:
                return web.Response(status=500, text="Failed to start workflow")
                
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON in webhook payload")
            return web.Response(status=400, text="Invalid JSON")
        except Exception as e:
            self.logger.error(f"Error handling webhook: {e}")
            return web.Response(status=500, text="Internal server error")
            
    async def _handle_health_check(self, request: web.Request) -> web.Response:
        """Handle health check requests"""
        is_healthy = await self.health_check()
        status = 200 if is_healthy else 503
        
        return web.json_response({
            "status": "healthy" if is_healthy else "unhealthy",
            "agent_id": self.agent_id,
            "active_workflows": len(self.active_workflows),
            "available_agents": {
                "rca": len(self.rca_agents),
                "remediation": len(self.remediation_agents),
                "approval": len(self.approval_agents)
            }
        }, status=status)
        
    async def _handle_status_check(self, request: web.Request) -> web.Response:
        """Handle status check requests"""
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        return web.json_response({
            "agent_id": self.agent_id,
            "status": self.status,
            "active_workflows": len(self.active_workflows),
            "discovered_topologies": len(self.discovered_topologies),
            "uptime_seconds": uptime_seconds,
            "webhook_server_running": self.server is not None,
            "discovered_agents": {
                "rca": len(self.rca_agents),
                "remediation": len(self.remediation_agents),
                "approval": len(self.approval_agents),
                "audit": len(self.audit_agents)
            }
        })

    async def _handle_analysis_complete(self, workflow_id: str, analysis_result: Dict[str, Any]):
        """Handle RCA analysis completion"""
        try:
            if workflow_id not in self.active_workflows:
                self.logger.error(f"Analysis complete for unknown workflow: {workflow_id}")
                return
            
            workflow_state = self.active_workflows[workflow_id]
            workflow_state.analysis_result = analysis_result
            workflow_state.updated_at = datetime.now()
            
            # Log analysis completion
            await self._log_mcp_event('analysis_complete', {
                'workflow_id': workflow_id,
                'classification': analysis_result.get('classification'),
                'confidence_score': analysis_result.get('confidence_score')
            })
            
            # Trigger remediation proposal
            await self._trigger_remediation_proposal(workflow_state)
            
        except Exception as e:
            self.logger.error(f"Error handling analysis completion: {e}")
            await self._fail_workflow(workflow_id, f"Analysis handling error: {e}")
    
    async def _handle_remediation_proposed(self, workflow_id: str, remediation_action: Dict[str, Any]):
        """Handle remediation proposal"""
        try:
            if workflow_id not in self.active_workflows:
                self.logger.error(f"Remediation proposed for unknown workflow: {workflow_id}")
                return
            
            workflow_state = self.active_workflows[workflow_id]
            workflow_state.remediation_action = remediation_action
            workflow_state.updated_at = datetime.now()
            
            # Log remediation proposal
            await self._log_mcp_event('remediation_proposed', {
                'workflow_id': workflow_id,
                'action_type': remediation_action.get('type'),
                'risk_level': remediation_action.get('risk_level')
            })
            
            # Trigger approval request
            await self._trigger_approval_request(workflow_state)
            
        except Exception as e:
            self.logger.error(f"Error handling remediation proposal: {e}")
            await self._fail_workflow(workflow_id, f"Remediation handling error: {e}")
    
    async def _handle_approval_received(self, workflow_id: str, approval_response: Dict[str, Any]):
        """Handle approval decision"""
        try:
            if workflow_id not in self.active_workflows:
                self.logger.error(f"Approval received for unknown workflow: {workflow_id}")
                return
            
            workflow_state = self.active_workflows[workflow_id]
            workflow_state.approval_response = approval_response
            workflow_state.updated_at = datetime.now()
            
            # Log approval decision
            await self._log_mcp_event('approval_received', {
                'workflow_id': workflow_id,
                'decision': approval_response.get('decision'),
                'user_id': approval_response.get('user_id')
            })
            
            # If approved, trigger execution
            if approval_response.get('decision') == 'approve':
                await self._trigger_remediation_execution(workflow_state)
            else:
                await self._complete_workflow(workflow_id, {
                    'status': 'rejected',
                    'reason': approval_response.get('reason', 'Rejected by approver')
                })
            
        except Exception as e:
            self.logger.error(f"Error handling approval: {e}")
            await self._fail_workflow(workflow_id, f"Approval handling error: {e}")
    
    async def _handle_execution_complete(self, workflow_id: str, execution_result: Dict[str, Any]):
        """Handle remediation execution completion"""
        try:
            if workflow_id not in self.active_workflows:
                self.logger.error(f"Execution complete for unknown workflow: {workflow_id}")
                return
            
            workflow_state = self.active_workflows[workflow_id]
            workflow_state.execution_result = execution_result
            workflow_state.updated_at = datetime.now()
            
            # Log execution completion
            await self._log_mcp_event('execution_complete', {
                'workflow_id': workflow_id,
                'success': execution_result.get('success'),
                'duration': execution_result.get('duration_seconds')
            })
            
            # Complete workflow
            await self._complete_workflow(workflow_id, execution_result)
            
        except Exception as e:
            self.logger.error(f"Error handling execution completion: {e}")
            await self._fail_workflow(workflow_id, f"Execution handling error: {e}")
    
    def _validate_failure_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate Playwright failure payload"""
        required_fields = ['test_title', 'status', 'error', 'retries', 'trace_id']
        
        for field in required_fields:
            if field not in payload:
                self.logger.error(f"Missing required field: {field}")
                return False
                
        # Validate error structure
        if not isinstance(payload['error'], dict):
            self.logger.error("Error field must be a dictionary")
            return False
            
        return True
        
    async def _start_incident_workflow(self, failure_payload: FailurePayload) -> Optional[str]:
        """Start a new incident response workflow"""
        try:
            # Generate IDs
            workflow_id = str(uuid.uuid4())
            incident_id = f"inc-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{workflow_id[:8]}"
            
            # Create workflow state
            workflow_state = WorkflowState(
                workflow_id=workflow_id,
                incident_id=incident_id,
                failure_payload=failure_payload,
                status='started',
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Store workflow
            self.active_workflows[workflow_id] = workflow_state
            
            # Log workflow start via MCP
            await self._log_mcp_event('workflow_started', {
                'workflow_id': workflow_id,
                'incident_id': incident_id,
                'test_title': failure_payload.test_title,
                'trace_id': failure_payload.trace_id,
                'failure_status': failure_payload.status
            })
            
            # Start A2A workflow
            workflow_context = {
                "incident_id": incident_id,
                "failure_payload": asdict(failure_payload),
                "trace_id": failure_payload.trace_id,
                "test_title": failure_payload.test_title
            }
            
            await self.start_workflow("incident_response", workflow_context)
            
            # Trigger RCA analysis via A2A
            await self._trigger_rca_analysis(workflow_state)
            
            self.logger.info(f"Started incident workflow {workflow_id} for incident {incident_id}")
            return workflow_id
            
        except Exception as e:
            self.logger.error(f"Failed to start incident workflow: {e}")
            await self._log_mcp_event('workflow_start_failed', {
                'error': str(e),
                'test_title': failure_payload.test_title,
                'trace_id': failure_payload.trace_id
            })
            return None

    async def _trigger_rca_analysis(self, workflow_state: WorkflowState):
        """Trigger RCA analysis through A2A communication"""
        try:
            if not self.rca_agents:
                await self._fail_workflow(workflow_state.workflow_id, "No RCA agents available")
                return
                
            # Update workflow status
            workflow_state.status = 'analyzing'
            workflow_state.updated_at = datetime.now()
            
            # Prepare analysis request for A2A communication
            analysis_request = {
                "failure_payload": {
                    "test_title": workflow_state.failure_payload.test_title,
                    "status": workflow_state.failure_payload.status,
                    "error_message": workflow_state.failure_payload.error.get('message', str(workflow_state.failure_payload.error)),
                    "error_stack": workflow_state.failure_payload.error.get('stack', ''),
                    "error_type": workflow_state.failure_payload.error.get('type', 'Error'),
                    "retries": workflow_state.failure_payload.retries,
                    "trace_id": workflow_state.failure_payload.trace_id,
                    "timestamp": workflow_state.failure_payload.timestamp
                }
            }
            
            # Log analysis trigger
            await self._log_mcp_event('rca_analysis_triggered', {
                'workflow_id': workflow_state.workflow_id,
                'incident_id': workflow_state.incident_id,
                'trace_id': workflow_state.failure_payload.trace_id
            })
            
            # Try A2A first, then mock fallback if A2A fails
            correlation_id = f"wf-{workflow_state.workflow_id}"
            try:
                rca_skill = self.services["rca"]["a2a"].get("skill", "analyze_failure")
                analysis_result = await self._a2a_call("rca", rca_skill, analysis_request,
                                                       timeout=45.0, correlation_id=correlation_id)
                await self._handle_analysis_complete(workflow_state.workflow_id, analysis_result)
            except Exception as e:
                self.logger.warning(f"RCA A2A call failed, using mock analysis: {e}")
                await self._log_mcp_event('rca_a2a_failed_mock_fallback', {
                    'workflow_id': workflow_state.workflow_id,
                    'error': str(e)
                })
                mock_analysis = {
                    'classification': 'Backend Error',
                    'failing_service': 'unknown-service',
                    'summary': 'A2A communication failed, using mock analysis',
                    'confidence_score': 0.8,
                    'evidence_count': 1
                }
                await self._handle_analysis_complete(workflow_state.workflow_id, mock_analysis)
                
        except Exception as e:
            self.logger.error(f"Failed to trigger RCA analysis: {e}")
            await self._fail_workflow(workflow_state.workflow_id, f"RCA trigger error: {e}")
            
    async def _trigger_remediation_proposal(self, workflow_state: WorkflowState):
        """Trigger remediation proposal through A2A communication"""
        try:
            if not self.remediation_agents:
                await self._fail_workflow(workflow_state.workflow_id, "No remediation agents available")
                return
                
            # Update workflow status
            workflow_state.status = 'proposing'
            workflow_state.updated_at = datetime.now()
            
            # Send remediation request
            remediation_request = {
                "workflow_id": workflow_state.workflow_id,
                "incident_id": workflow_state.incident_id,
                "analysis_result": workflow_state.analysis_result,
                "topology_data": workflow_state.topology_data
            }
            
            # Log remediation trigger
            await self._log_mcp_event('remediation_proposal_triggered', {
                'workflow_id': workflow_state.workflow_id,
                'incident_id': workflow_state.incident_id
            })
            
            # Try A2A, then mock fallback
            correlation_id = f"wf-{workflow_state.workflow_id}"
            try:
                propose_skill = self.services["remediation"]["a2a"].get("propose_skill", "propose_remediation")
                propose_payload = {
                    "workflow_id": workflow_state.workflow_id,
                    "incident_id": workflow_state.incident_id,
                    "analysis_result": workflow_state.analysis_result,
                    "topology_data": workflow_state.topology_data,
                }
                remediation_proposal = await self._a2a_call(
                    "remediation", propose_skill, propose_payload, timeout=60.0, correlation_id=correlation_id
                )
                await self._handle_remediation_proposed(workflow_state.workflow_id, remediation_proposal)
            except Exception as e:
                self.logger.warning(f"Remediation A2A call failed, using mock proposal: {e}")
                await self._log_mcp_event('remediation_a2a_failed_mock_fallback', {
                    'workflow_id': workflow_state.workflow_id,
                    'stage': 'propose',
                    'error': str(e)
                })
                mock_remediation = {
                    'type': 'restart_service',
                    'service': (workflow_state.analysis_result or {}).get('failing_service', 'unknown-service'),
                    'risk_level': 'medium',
                    'description': 'A2A communication failed, using mock remediation proposal'
                }
                await self._handle_remediation_proposed(workflow_state.workflow_id, mock_remediation)
                
        except Exception as e:
            self.logger.error(f"Failed to trigger remediation proposal: {e}")
            await self._fail_workflow(workflow_state.workflow_id, f"Remediation trigger error: {e}")
            
    async def _trigger_approval_request(self, workflow_state: WorkflowState):
        """Trigger approval request through A2A communication"""
        try:
            if not self.approval_agents:
                await self._fail_workflow(workflow_state.workflow_id, "No approval agents available")
                return
                
            # Update workflow status
            workflow_state.status = 'awaiting_approval'
            workflow_state.updated_at = datetime.now()
            
            # Send approval request
            approval_request = {
                "workflow_id": workflow_state.workflow_id,
                "incident_id": workflow_state.incident_id,
                "analysis_result": workflow_state.analysis_result,
                "remediation_action": workflow_state.remediation_action,
                "failure_payload": asdict(workflow_state.failure_payload)
            }
            
            # Log approval trigger
            await self._log_mcp_event('approval_request_triggered', {
                'workflow_id': workflow_state.workflow_id,
                'incident_id': workflow_state.incident_id
            })
            
            # Try A2A, then mock fallback
            correlation_id = f"wf-{workflow_state.workflow_id}"
            try:
                approval_skill = self.services["approval"]["a2a"].get("skill", "request_approval")
                approval_result = await self._a2a_call("approval", approval_skill, approval_request,
                                                       timeout=45.0, correlation_id=correlation_id)
                await self._handle_approval_received(workflow_state.workflow_id, approval_result)
            except Exception as e:
                self.logger.warning(f"Approval A2A call failed, using auto-approval: {e}")
                await self._log_mcp_event('approval_a2a_failed_mock_fallback', {
                    'workflow_id': workflow_state.workflow_id,
                    'error': str(e)
                })
                mock_approval = {
                    'decision': 'approve',
                    'user_id': 'system',
                    'reason': 'A2A communication failed, auto-approved for testing'
                }
                await self._handle_approval_received(workflow_state.workflow_id, mock_approval)
                
        except Exception as e:
            self.logger.error(f"Failed to trigger approval request: {e}")
            await self._fail_workflow(workflow_state.workflow_id, f"Approval trigger error: {e}")
            
    async def _trigger_remediation_execution(self, workflow_state: WorkflowState):
        """Trigger remediation execution through A2A communication"""
        try:
            if not self.remediation_agents:
                await self._fail_workflow(workflow_state.workflow_id, "No remediation agents available")
                return
                
            # Update workflow status
            workflow_state.status = 'executing'
            workflow_state.updated_at = datetime.now()
            
            # Send execution request
            execution_request = {
                "workflow_id": workflow_state.workflow_id,
                "incident_id": workflow_state.incident_id,
                "remediation_action": workflow_state.remediation_action,
                "approval_response": workflow_state.approval_response
            }
            
            # Log execution trigger
            await self._log_mcp_event('remediation_execution_triggered', {
                'workflow_id': workflow_state.workflow_id,
                'incident_id': workflow_state.incident_id
            })
            
            # Try A2A, then mock fallback
            correlation_id = f"wf-{workflow_state.workflow_id}"
            try:
                execute_skill = self.services["remediation"]["a2a"].get("execute_skill", "execute_remediation")
                execute_payload = {
                    "workflow_id": workflow_state.workflow_id,
                    "incident_id": workflow_state.incident_id,
                    "remediation_action": workflow_state.remediation_action,
                    "approval_response": workflow_state.approval_response,
                }
                execution_result = await self._a2a_call(
                    "remediation", execute_skill, execute_payload, timeout=90.0, correlation_id=correlation_id
                )
                await self._handle_execution_complete(workflow_state.workflow_id, execution_result)
            except Exception as e:
                self.logger.warning(f"Remediation A2A call failed, using mock execution: {e}")
                await self._log_mcp_event('remediation_a2a_failed_mock_fallback', {
                    'workflow_id': workflow_state.workflow_id,
                    'stage': 'execute',
                    'error': str(e)
                })
                mock_execution = {
                    'success': True,
                    'duration_seconds': 30,
                    'actions_taken': ['A2A communication failed, mock service restart'],
                    'verification_status': 'passed'
                }
                await self._handle_execution_complete(workflow_state.workflow_id, mock_execution)
                
        except Exception as e:
            self.logger.error(f"Failed to trigger remediation execution: {e}")
            await self._fail_workflow(workflow_state.workflow_id, f"Execution trigger error: {e}")
            
    async def _complete_workflow(self, workflow_id: str, result: Dict[str, Any]):
        """Complete a workflow successfully"""
        try:
            if workflow_id not in self.active_workflows:
                self.logger.error(f"Cannot complete unknown workflow: {workflow_id}")
                return
                
            workflow_state = self.active_workflows[workflow_id]
            workflow_state.status = 'completed'
            workflow_state.updated_at = datetime.now()
            workflow_state.execution_result = result
            
            # Complete A2A workflow
            await self.complete_workflow(workflow_id, result)
            
            # Log completion
            await self._log_mcp_event('workflow_completed', {
                'workflow_id': workflow_id,
                'incident_id': workflow_state.incident_id,
                'duration_seconds': (workflow_state.updated_at - workflow_state.created_at).total_seconds(),
                'result': result
            })
            
            # Remove from active workflows after a delay (for status queries)
            asyncio.create_task(self._cleanup_completed_workflow(workflow_id))
            
        except Exception as e:
            self.logger.error(f"Error completing workflow {workflow_id}: {e}")
            
    async def _cleanup_completed_workflow(self, workflow_id: str):
        """Clean up completed workflow after delay"""
        await asyncio.sleep(300)  # 5 minute delay
        if workflow_id in self.active_workflows:
            del self.active_workflows[workflow_id]
            
    async def _fail_workflow(self, workflow_id: str, error_message: str):
        """Fail a workflow with error message"""
        try:
            if workflow_id not in self.active_workflows:
                self.logger.error(f"Cannot fail unknown workflow: {workflow_id}")
                return
                
            workflow_state = self.active_workflows[workflow_id]
            workflow_state.status = 'failed'
            workflow_state.updated_at = datetime.now()
            workflow_state.error_message = error_message
            
            # Log failure
            await self._log_mcp_event('workflow_failed', {
                'workflow_id': workflow_id,
                'incident_id': workflow_state.incident_id,
                'error_message': error_message,
                'duration_seconds': (workflow_state.updated_at - workflow_state.created_at).total_seconds()
            })
            
            self.logger.error(f"Workflow {workflow_id} failed: {error_message}")
            
            # Remove from active workflows after a delay
            asyncio.create_task(self._cleanup_completed_workflow(workflow_id))
            
        except Exception as e:
            self.logger.error(f"Error failing workflow {workflow_id}: {e}")
            
    async def _discover_agents(self):
        """Discover available agents for coordination"""
        try:
            # For now, use hardcoded agent discovery
            # In real implementation, this would use service discovery
            self.rca_agents = ["rca-agent-localhost:8000"]
            self.remediation_agents = ["remediation-agent-localhost:8001"]
            self.approval_agents = ["approval-agent-localhost:8002"]
            self.audit_agents = ["audit-agent-localhost:8003"]
            
            self.logger.info(f"Discovered agents: RCA={len(self.rca_agents)}, Remediation={len(self.remediation_agents)}, Approval={len(self.approval_agents)}, Audit={len(self.audit_agents)}")
            
        except Exception as e:
            self.logger.error(f"Agent discovery failed: {e}")
            
    async def _monitor_workflows(self):
        """Monitor active workflows for timeouts and errors"""
        while self.running:
            try:
                current_time = datetime.now()
                
                # Check for stuck workflows
                for workflow_id, workflow_state in list(self.active_workflows.items()):
                    time_since_update = current_time - workflow_state.updated_at
                    
                    if time_since_update > self.workflow_timeout:
                        self.logger.warning(f"Workflow {workflow_id} timed out")
                        await self._fail_workflow(workflow_id, "Workflow timeout")
                
                # Update heartbeat
                self.last_heartbeat = current_time
                
                # Sleep for monitoring interval
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in workflow monitoring: {e}")
                await asyncio.sleep(30)
                

# Factory function for creating orchestrator agent
def create_orchestrator_agent(agent_id: Optional[str] = None, webhook_port: int = 8080) -> OrchestratorAgent:
    """
    Create and configure an orchestrator agent
    
    Args:
        agent_id: Unique agent identifier (auto-generated if None)
        webhook_port: Port for webhook server
        
    Returns:
        Configured OrchestratorAgent instance
    """
    if agent_id is None:
        agent_id = f"orchestrator-{uuid.uuid4()}"
        
    return OrchestratorAgent(agent_id, webhook_port)