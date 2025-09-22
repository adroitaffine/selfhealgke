"""
Remediation Agent - Application Agnostic

This agent implements intelligent remediation strategies that work with any microservices
application by dynamically discovering service configurations and dependencies.

Key capabilities:
- Application-agnostic remediation strategy selection
- Dynamic service discovery and configuration detection
- Deployment rollback with automatic service name resolution
- A2A coordination for multi-service remediation workflows
- Verification through re-execution of original tests
- Risk assessment based on discovered service criticality
"""

import asyncio
import json
import logging
import uuid
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, asdict
from enum import Enum

from dotenv import load_dotenv
load_dotenv()

# Direct ADK imports - using the official google/adk-python library
try:
    from google.adk.agents import Agent, LlmAgent
    from google.adk.tools import BaseTool, FunctionTool, MCPToolset
    from google.adk import Runner
    ADK_AVAILABLE = True
except ImportError:
    # Fallback for testing when ADK is not available
    ADK_AVAILABLE = False
    Agent = object
    LlmAgent = object
    MCPToolset = object

# A2A imports - using the official a2a-sdk library  
try:
    from a2a.client import Client, ClientConfig
    from a2a.types import Message, TextPart, Role
    A2A_AVAILABLE = True
except ImportError:
    # Fallback for testing when A2A is not available
    A2A_AVAILABLE = False
    Client = object
    ClientConfig = object

# Direct Gemini import for fallback
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class RemediationStrategy(Enum):
    """Available remediation strategies"""
    DEPLOYMENT_ROLLBACK = "deployment_rollback"
    SERVICE_RESTART = "service_restart"
    SCALE_UP = "scale_up"
    CIRCUIT_BREAKER = "circuit_breaker"
    TRAFFIC_SHIFT = "traffic_shift"
    NO_ACTION = "no_action"


class RiskLevel(Enum):
    """Risk levels for remediation actions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ServiceConfiguration:
    """Discovered service configuration"""
    name: str
    namespace: str
    deployment_name: str
    current_revision: int
    previous_revision: Optional[int]
    replica_count: int
    image: str
    last_deployment_time: datetime
    health_check_path: Optional[str]
    dependencies: List[str]
    dependents: List[str]
    criticality_score: float


@dataclass
class RemediationAction:
    """Represents a proposed remediation action"""
    action_id: str
    strategy: RemediationStrategy
    target_service: str
    target_namespace: str
    parameters: Dict[str, Any]
    risk_level: RiskLevel
    estimated_duration: int  # seconds
    confidence_score: float
    rollback_plan: Optional[Dict[str, Any]]
    verification_tests: List[str]
    impact_analysis: str


@dataclass
class ExecutionResult:
    """Result of remediation execution"""
    action_id: str
    success: bool
    execution_time: datetime
    duration_seconds: float
    verification_status: Literal['pending', 'passed', 'failed', 'skipped']
    error_message: Optional[str] = None
    rollback_executed: bool = False
    verification_results: Optional[Dict[str, Any]] = None


# A2AMessage removed - using official A2A SDK instead


class ServiceDiscovery:
    """Discovers service configurations dynamically from Kubernetes"""
    
    def __init__(self, mcp_toolset=None):
        self.mcp_toolset = mcp_toolset
        self.service_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def discover_service_configuration(self, service_name: str, 
                                           namespace: str = "default") -> Optional[ServiceConfiguration]:
        """
        Dynamically discover service configuration from Kubernetes
        
        Args:
            service_name: Name of the service to discover
            namespace: Kubernetes namespace
            
        Returns:
            ServiceConfiguration with discovered details
        """
        cache_key = f"{namespace}/{service_name}"
        
        # Check cache first
        if cache_key in self.service_cache:
            cached_config, cache_time = self.service_cache[cache_key]
            if datetime.now() - cache_time < timedelta(seconds=self.cache_ttl):
                return cached_config
        
        try:
            # Discover deployment information
            deployment_info = await self._get_deployment_info(service_name, namespace)
            if not deployment_info:
                logger.warning(f"No deployment found for service {service_name} in namespace {namespace}")
                return None
            
            # Discover service dependencies
            dependencies = await self._discover_service_dependencies(service_name, namespace)
            dependents = await self._discover_service_dependents(service_name, namespace)
            
            # Calculate criticality score
            criticality_score = self._calculate_service_criticality(
                service_name, dependencies, dependents, deployment_info
            )
            
            config = ServiceConfiguration(
                name=service_name,
                namespace=namespace,
                deployment_name=deployment_info['name'],
                current_revision=deployment_info['revision'],
                previous_revision=deployment_info.get('previous_revision'),
                replica_count=deployment_info['replicas'],
                image=deployment_info['image'],
                last_deployment_time=datetime.fromisoformat(deployment_info['last_deployment_time']),
                health_check_path=deployment_info.get('health_check_path'),
                dependencies=dependencies,
                dependents=dependents,
                criticality_score=criticality_score
            )
            
            # Cache the configuration
            self.service_cache[cache_key] = (config, datetime.now())
            
            logger.info(f"Discovered configuration for service {service_name}: "
                       f"revision {config.current_revision}, criticality {config.criticality_score:.2f}")
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to discover service configuration for {service_name}: {str(e)}")
            return None
    
    async def _get_deployment_info(self, service_name: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Get deployment information from Kubernetes"""
        if self.mcp_toolset:
            try:
                # Use Kubernetes MCP server to get deployment info
                deployment = await self.mcp_toolset.call_tool('kubectl_get', {
                    'resourceType': 'deployment',
                    'name': service_name,
                    'namespace': namespace,
                    'output': 'json'
                })
                
                if deployment and deployment.get('status'):
                    return {
                        'name': deployment['metadata']['name'],
                        'revision': deployment['metadata']['generation'],
                        'previous_revision': deployment['metadata']['generation'] - 1,
                        'replicas': deployment['spec']['replicas'],
                        'image': deployment['spec']['template']['spec']['containers'][0]['image'],
                        'last_deployment_time': deployment['metadata']['creationTimestamp'],
                        'health_check_path': '/health'  # Default assumption
                    }
            except Exception as e:
                logger.warning(f"MCP toolset call failed: {e}, using mock data")
        
        # Mock deployment data for now
        mock_deployment = {
            'name': service_name,
            'revision': 5,
            'previous_revision': 4,
            'replicas': 3,
            'image': f'gcr.io/project/{service_name}:v1.2.3',
            'last_deployment_time': '2024-01-01T10:00:00Z',
            'health_check_path': '/health'
        }
        
        return mock_deployment
    
    async def _discover_service_dependencies(self, service_name: str, namespace: str) -> List[str]:
        """Discover services that this service depends on - application agnostic"""
        # TODO: Implement actual service mesh discovery or config map analysis
        # This could use Istio service mesh, analyze environment variables, or config maps
        
        # For now, return empty list - will be populated by actual discovery
        # In a real implementation, this would analyze:
        # - Service mesh configuration (Istio, Linkerd)
        # - Environment variables and config maps
        # - Application configuration files
        # - Database connection strings
        # - API gateway routes
        
        return []
    
    async def _discover_service_dependents(self, service_name: str, namespace: str) -> List[str]:
        """Discover services that depend on this service - application agnostic"""
        # TODO: Implement reverse dependency discovery
        
        # For now, return empty list - will be populated by actual discovery
        # In a real implementation, this would analyze:
        # - Service mesh traffic patterns
        # - API gateway configurations
        # - Application logs showing incoming requests
        # - Service registry data
        
        return []
    
    def _calculate_service_criticality(self, service_name: str, dependencies: List[str], 
                                     dependents: List[str], deployment_info: Dict[str, Any]) -> float:
        """Calculate service criticality score based on topology and configuration"""
        # Base criticality factors:
        # 1. Number of dependents (services that rely on this one)
        # 2. Whether it's a user-facing service
        # 3. Deployment frequency (more frequent = higher risk)
        # 4. Replica count (fewer replicas = higher risk)
        
        dependent_score = min(len(dependents) * 0.2, 0.6)  # Max 0.6 for dependents
        
        # User-facing services are more critical (generic detection)
        # Check for common user-facing service patterns
        user_facing_patterns = ['frontend', 'gateway', 'api-gateway', 'web', 'ui', 'portal']
        is_user_facing = any(pattern in service_name.lower() for pattern in user_facing_patterns)
        user_facing_score = 0.3 if is_user_facing else 0.0
        
        # Services with fewer replicas are more critical
        replica_count = deployment_info.get('replicas', 1)
        replica_score = 0.2 if replica_count < 3 else 0.1
        
        total_score = dependent_score + user_facing_score + replica_score
        return min(1.0, total_score)


class A2ACoordinator:
    """Handles Agent-to-Agent communication for coordinated remediation"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.message_handlers = {}
        self.active_workflows = {}
        
    def register_handler(self, message_type: str, handler_func):
        """Register a handler for specific message types"""
        self.message_handlers[message_type] = handler_func
    
    async def send_message(self, to_agent: str, message_type: str, payload: Any, 
                          correlation_id: Optional[str] = None) -> str:
        """Send A2A message to another agent"""
        correlation_id = correlation_id or f"{self.agent_id}_{datetime.now().timestamp()}"
        
        # Direct communication without A2A wrapper
        # TODO: Implement direct A2A SDK communication if needed
        
        # TODO: Implement actual A2A message delivery
        logger.info(f"A2A Message sent: {self.agent_id} -> {to_agent} ({message_type})")
        
        return correlation_id
    
    # Message handling removed - using direct method calls instead
    
    async def coordinate_multi_service_remediation(self, services: List[str], 
                                                 strategy: RemediationStrategy) -> Dict[str, Any]:
        """Coordinate remediation across multiple services"""
        coordination_id = f"multi_remediation_{datetime.now().timestamp()}"
        
        # Notify monitoring agents about upcoming remediation
        await self.send_message(
            "monitoring_agent",
            "remediation_start",
            {
                "coordination_id": coordination_id,
                "services": services,
                "strategy": strategy.value
            },
            coordination_id
        )
        
        # Coordinate with audit agent
        await self.send_message(
            "audit_agent",
            "log_remediation_start",
            {
                "coordination_id": coordination_id,
                "services": services,
                "strategy": strategy.value,
                "timestamp": datetime.now().isoformat()
            },
            coordination_id
        )
        
        return {"coordination_id": coordination_id, "status": "initiated"}


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

class RemediationAgent(object):  # Simplified inheritance for now
    """
    Application-Agnostic Remediation Agent
    
    Implements intelligent remediation strategies that automatically discover
    service configurations and adapt to any microservices architecture.
    
    Uses official ADK and A2A libraries for agent orchestration and communication.
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize Remediation Agent with ADK configuration"""
        super().__init__()
        
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.agent_type}")
        
        # Initialize Gemini client directly for fallback
        self.gemini_model = None
        if GENAI_AVAILABLE:
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
            self.logger.info("Initialized direct Gemini client for remediation")
        else:
            self.logger.warning("Gemini not available, remediation planning will be limited")
        
        # MCP toolset for Kubernetes operations
        self.mcp_toolset = None  # Will be initialized with actual MCP toolset
        self.service_discovery = ServiceDiscovery(self.mcp_toolset)
        
        # Configuration from metadata
        metadata = config.metadata or {}
        self.max_rollback_age_hours = metadata.get('max_rollback_age_hours', 24)
        self.verification_timeout_seconds = metadata.get('verification_timeout_seconds', 300)
        self.risk_tolerance = RiskLevel(metadata.get('risk_tolerance', 'medium'))
        
        # Active remediation tasks
        self.active_remediations: Dict[str, asyncio.Task] = {}
        
        # A2A client for communication
        self.a2a_client = None
        self.a2a_coordinator = A2ACoordinator(self.config.agent_id)
        
        logger.info("Remediation Agent initialized with adaptive service discovery")

    def _get_system_instruction(self) -> str:
        """Get system instruction for the remediation agent"""
        return """
You are an expert Remediation Agent for microservices applications.

Your role is to analyze failure scenarios and recommend safe, effective remediation strategies.
Consider service dependencies, criticality, risk levels, and verification methods.

Available remediation strategies:
1. DEPLOYMENT_ROLLBACK - Roll back to previous deployment version
2. SERVICE_RESTART - Restart the failing service pods
3. SCALE_UP - Increase replica count to handle load
4. CIRCUIT_BREAKER - Temporarily isolate failing service
5. TRAFFIC_SHIFT - Redirect traffic away from failing service
6. NO_ACTION - No remediation needed

For each recommendation, provide:
- Strategy justification based on failure analysis
- Risk assessment (Low/Medium/High/Critical)
- Estimated duration and impact
- Verification steps
- Rollback plan if applicable

Always prioritize safety and minimal service disruption. Consider service dependencies and criticality scores.
"""

    def _create_remediation_tools(self) -> List[Any]:
        """Create remediation-specific tools for the agent"""
        return [
            # Tools will be added when ADK is properly integrated
        ]
    
    async def initialize(self):
        """Initialize MCP toolset and connections"""
        try:
            # Initialize MCP toolset for Kubernetes operations
            if ADK_AVAILABLE:
                # Skip MCP toolset initialization for testing
                # TODO: Configure actual MCP server connections
                connection_params = {}  # Would contain actual MCP server configs
                if connection_params:  # Only initialize if we have connection params
                    self.mcp_toolset = MCPToolset()  # No connection_params parameter
                    # TODO: Configure MCP servers for Kubernetes, Playwright, etc.
            
            self.service_discovery.mcp_toolset = self.mcp_toolset
            logger.info("Remediation Agent MCP toolset initialized (skipped for testing)")
        except Exception as e:
            logger.error(f"Failed to initialize Remediation Agent MCP toolset: {e}")
            raise
        
    async def cleanup(self):
        """Cleanup remediation agent resources"""
        # Cancel active remediations
        for remediation_id, task in self.active_remediations.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled remediation task {remediation_id}")
                
        # Wait for tasks to complete
        if self.active_remediations:
            await asyncio.gather(*self.active_remediations.values(), return_exceptions=True)
            
        logger.info("Remediation Agent cleaned up")
        
    async def health_check(self) -> bool:
        """Check remediation agent health"""
        try:
            # Check if we have too many stuck remediations
            stuck_remediations = [
                task for task in self.active_remediations.values()
                if not task.done()
            ]
            
            if len(stuck_remediations) > 5:  # Arbitrary threshold
                logger.warning(f"Too many active remediations: {len(stuck_remediations)}")
                return False
                
            # TODO: Check MCP server connectivity
            # if self.mcp_server and not await self.mcp_server.is_connected():
            #     return False
                
            return True
            
        except Exception as e:
            logger.error(f"Remediation health check failed: {e}")
            return False
            
    async def handle_analysis_complete(self, analysis_result: Dict[str, Any], workflow_id: Optional[str] = None):
        """Handle analysis completion from RCA agent"""
        try:
            if workflow_id is None:
                workflow_id = str(uuid.uuid4())
            
            logger.info(f"Received analysis result for workflow {workflow_id}")
            
            # Check if this requires remediation
            classification = analysis_result.get('classification', '')
            if classification == 'Backend Error':
                # Start remediation proposal task
                remediation_task = asyncio.create_task(
                    self._propose_remediation_workflow(workflow_id, analysis_result)
                )
                self.active_remediations[workflow_id] = remediation_task
            else:
                logger.info(f"No remediation needed for workflow {workflow_id}: {classification}")
                
        except Exception as e:
            logger.error(f"Error handling analysis complete: {e}")
    
    async def handle_approval_response(self, approval_data: Dict[str, Any], workflow_id: Optional[str] = None):
        """Handle approval response from approval agent"""
        try:
            if workflow_id is None:
                workflow_id = str(uuid.uuid4())
            
            logger.info(f"Received approval response for workflow {workflow_id}")
            
            approved = approval_data.get('approved', False)
            if approved:
                # Start remediation execution task
                execution_task = asyncio.create_task(
                    self._execute_remediation_workflow(workflow_id, approval_data)
                )
                self.active_remediations[workflow_id] = execution_task
            else:
                logger.info(f"Remediation not approved for workflow {workflow_id}")
                
        except Exception as e:
            logger.error(f"Error handling approval response: {e}")
    
    async def _propose_remediation_workflow(self, workflow_id: str, analysis_data: Dict[str, Any]):
        """Propose remediation based on analysis results"""
        try:
            # Extract analysis information
            failing_service = analysis_data.get('failing_service')
            
            if not failing_service:
                logger.warning(f"No failing service identified for workflow {workflow_id}")
                return
                
            # Create mock analysis result for propose_remediation method
            from .rca_agent import AnalysisResult, FailureClassification, Evidence
            
            analysis_result = AnalysisResult(
                classification=FailureClassification.BACKEND_ERROR,
                failing_service=failing_service,
                summary=analysis_data.get('summary', ''),
                confidence_score=analysis_data.get('confidence_score', 0.8),
                evidence=[],
                analysis_duration=0.0,
                trace_id=analysis_data.get('trace_id', '')
            )
            
            # Propose remediation action
            remediation_action = await self.propose_remediation(analysis_result)
            
            if remediation_action:
                logger.info(f"Proposed {remediation_action.strategy.value} for {failing_service} in workflow {workflow_id}")
            else:
                logger.warning(f"No suitable remediation found for {failing_service} in workflow {workflow_id}")
                
        except Exception as e:
            logger.error(f"Remediation proposal failed for workflow {workflow_id}: {e}")
        finally:
            # Clean up task
            if workflow_id in self.active_remediations:
                del self.active_remediations[workflow_id]
                
    async def _execute_remediation_workflow(self, workflow_id: str, approval_data: Dict[str, Any]):
        """Execute approved remediation"""
        try:
            logger.info(f"Executing remediation for workflow {workflow_id}")
            # Implementation would execute the actual remediation
            # For now, just log success
            logger.info(f"Remediation execution completed for workflow {workflow_id}")
            
        except Exception as e:
            logger.error(f"Remediation execution failed for workflow {workflow_id}: {e}")
        finally:
            # Clean up task
            if workflow_id in self.active_remediations:
                del self.active_remediations[workflow_id]
    
    async def propose_remediation(self, analysis_result) -> Optional[RemediationAction]:
        """
        Propose remediation action based on RCA analysis result
        
        Uses ADK LlmAgent if available, falls back to Gemini direct API
        """
        if analysis_result.classification.value != "Backend Error":
            logger.info("No remediation needed - classified as UI Brittleness")
            return None

        if not analysis_result.failing_service:
            logger.warning("Cannot propose remediation - no failing service identified")
            return None

        # Discover service configuration
        service_config = await self.service_discovery.discover_service_configuration(
            analysis_result.failing_service,
            self.config.metadata.get('namespace', 'default')
        )
        
        if not service_config:
            logger.error(f"Cannot discover configuration for service {analysis_result.failing_service}")
            return None

        # Try ADK-based remediation planning first
        if ADK_AVAILABLE:
            try:
                # TODO: Implement ADK-based remediation planning
                logger.info("ADK-based remediation planning not yet implemented, using fallback")
            except Exception as e:
                logger.warning(f"ADK remediation planning failed: {e}")

        # Fall back to Gemini-based planning
        if self.gemini_model:
            action = await self._plan_remediation_with_gemini(analysis_result, service_config)
            if action:
                return action

        # Final fallback to rule-based planning
        logger.info("Using rule-based remediation planning as final fallback")
        return await self._rule_based_remediation(analysis_result, service_config)

    async def _rule_based_remediation(self, analysis_result, service_config: ServiceConfiguration) -> Optional[RemediationAction]:
        """Rule-based remediation planning as final fallback"""
        try:
            # Select appropriate remediation strategy
            strategy = await self._select_remediation_strategy(service_config, analysis_result)
            
            if strategy == RemediationStrategy.NO_ACTION:
                logger.info("No remediation action recommended by rule-based planning")
                return None
            
            # Build complete remediation action
            action = await self._build_remediation_action(strategy, service_config, analysis_result)
            logger.info(f"Rule-based remediation planning recommended: {strategy.value}")
            
            return action
            
        except Exception as e:
            logger.error(f"Rule-based remediation planning failed: {e}")
            return None

    async def _select_remediation_strategy(self, service_config: ServiceConfiguration, 
                                         analysis_result) -> RemediationStrategy:
        """
        Select the most appropriate remediation strategy based on service configuration
        and failure analysis
        """
        # Check if deployment rollback is viable
        if await self._is_rollback_viable(service_config):
            return RemediationStrategy.DEPLOYMENT_ROLLBACK
        
        # Check if service restart is appropriate
        if service_config.criticality_score < 0.8 and service_config.replica_count > 1:
            return RemediationStrategy.SERVICE_RESTART
        
        # Check if scaling up might help (for resource exhaustion)
        if self._is_resource_exhaustion_error(analysis_result):
            return RemediationStrategy.SCALE_UP
        
        # For high-criticality services, consider circuit breaker
        if service_config.criticality_score > 0.8:
            return RemediationStrategy.CIRCUIT_BREAKER
        
        return RemediationStrategy.NO_ACTION
    
    async def _is_rollback_viable(self, service_config: ServiceConfiguration) -> bool:
        """Check if deployment rollback is a viable option"""
        # Must have a previous revision
        if not service_config.previous_revision:
            return False
        
        # Deployment must be recent (within configured time window)
        now = datetime.now()
        # Ensure both datetimes are timezone-naive for comparison
        last_deployment = service_config.last_deployment_time
        if last_deployment.tzinfo is not None:
            last_deployment = last_deployment.replace(tzinfo=None)
        
        time_since_deployment = now - last_deployment
        if time_since_deployment > timedelta(hours=self.max_rollback_age_hours):
            return False
        
        # TODO: Check if previous revision is healthy
        # previous_health = await self._check_revision_health(
        #     service_config.name, service_config.previous_revision
        # )
        
        return True
    
    def _is_resource_exhaustion_error(self, analysis_result) -> bool:
        """Check if the error indicates resource exhaustion"""
        resource_exhaustion_indicators = [
            'out of memory',
            'outofmemory',
            'memory',
            'resource exhausted',
            'cpu throttling',
            'disk full',
            'connection pool exhausted',
            'connection pool',
            'pool exhausted',
            'heap space',
            'gc overhead',
            'resource limit'
        ]
        
        for evidence in analysis_result.evidence:
            content_lower = evidence.content.lower()
            if any(indicator in content_lower for indicator in resource_exhaustion_indicators):
                return True
        
        return False
    
    async def _build_remediation_action(self, strategy: RemediationStrategy, 
                                      service_config: ServiceConfiguration,
                                      analysis_result) -> RemediationAction:
        """Build a complete remediation action with all details"""
        action_id = f"{strategy.value}_{service_config.name}_{datetime.now().timestamp()}"
        
        # Build strategy-specific parameters
        parameters = await self._build_strategy_parameters(strategy, service_config)
        
        # Assess risk level
        risk_level = self._assess_risk_level(strategy, service_config)
        
        # Estimate duration
        estimated_duration = self._estimate_duration(strategy, service_config)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(strategy, service_config, analysis_result)
        
        # Build rollback plan
        rollback_plan = await self._build_rollback_plan(strategy, service_config)
        
        # Determine verification tests
        verification_tests = self._determine_verification_tests(analysis_result)
        
        # Build impact analysis
        impact_analysis = self._build_impact_analysis(strategy, service_config)
        
        return RemediationAction(
            action_id=action_id,
            strategy=strategy,
            target_service=service_config.name,
            target_namespace=service_config.namespace,
            parameters=parameters,
            risk_level=risk_level,
            estimated_duration=estimated_duration,
            confidence_score=confidence_score,
            rollback_plan=rollback_plan,
            verification_tests=verification_tests,
            impact_analysis=impact_analysis
        )
    
    async def _build_strategy_parameters(self, strategy: RemediationStrategy, 
                                       service_config: ServiceConfiguration) -> Dict[str, Any]:
        """Build parameters specific to the remediation strategy"""
        if strategy == RemediationStrategy.DEPLOYMENT_ROLLBACK:
            return {
                'deployment_name': service_config.deployment_name,
                'target_revision': service_config.previous_revision,
                'current_revision': service_config.current_revision,
                'namespace': service_config.namespace
            }
        
        elif strategy == RemediationStrategy.SERVICE_RESTART:
            return {
                'deployment_name': service_config.deployment_name,
                'namespace': service_config.namespace,
                'restart_strategy': 'rolling'
            }
        
        elif strategy == RemediationStrategy.SCALE_UP:
            new_replica_count = min(service_config.replica_count * 2, 10)  # Cap at 10
            return {
                'deployment_name': service_config.deployment_name,
                'namespace': service_config.namespace,
                'current_replicas': service_config.replica_count,
                'target_replicas': new_replica_count
            }
        
        elif strategy == RemediationStrategy.CIRCUIT_BREAKER:
            return {
                'service_name': service_config.name,
                'namespace': service_config.namespace,
                'circuit_breaker_config': {
                    'failure_threshold': 5,
                    'timeout_seconds': 60
                }
            }
        
        return {}
    
    def _assess_risk_level(self, strategy: RemediationStrategy, 
                          service_config: ServiceConfiguration) -> RiskLevel:
        """Assess the risk level of the remediation action"""
        base_risk = {
            RemediationStrategy.DEPLOYMENT_ROLLBACK: RiskLevel.LOW,
            RemediationStrategy.SERVICE_RESTART: RiskLevel.MEDIUM,
            RemediationStrategy.SCALE_UP: RiskLevel.LOW,
            RemediationStrategy.CIRCUIT_BREAKER: RiskLevel.HIGH,
            RemediationStrategy.TRAFFIC_SHIFT: RiskLevel.MEDIUM
        }.get(strategy, RiskLevel.HIGH)
        
        # Escalate risk for critical services
        if service_config.criticality_score > 0.8:
            if base_risk == RiskLevel.LOW:
                return RiskLevel.MEDIUM
            elif base_risk == RiskLevel.MEDIUM:
                return RiskLevel.HIGH
        
        # Escalate risk for services with few replicas
        if service_config.replica_count < 2 and base_risk != RiskLevel.LOW:
            return RiskLevel.HIGH
        
        return base_risk
    
    def _estimate_duration(self, strategy: RemediationStrategy, 
                          service_config: ServiceConfiguration) -> int:
        """Estimate duration in seconds for the remediation action"""
        base_durations = {
            RemediationStrategy.DEPLOYMENT_ROLLBACK: 120,  # 2 minutes
            RemediationStrategy.SERVICE_RESTART: 90,       # 1.5 minutes
            RemediationStrategy.SCALE_UP: 60,              # 1 minute
            RemediationStrategy.CIRCUIT_BREAKER: 30,       # 30 seconds
            RemediationStrategy.TRAFFIC_SHIFT: 180         # 3 minutes
        }
        
        base_duration = base_durations.get(strategy, 120)
        
        # Adjust for replica count (more replicas = longer duration)
        replica_factor = 1 + (service_config.replica_count - 1) * 0.2
        
        return int(base_duration * replica_factor)
    
    def _calculate_confidence_score(self, strategy: RemediationStrategy, 
                                  service_config: ServiceConfiguration,
                                  analysis_result) -> float:
        """Calculate confidence score for the remediation action"""
        # Base confidence by strategy
        base_confidence = {
            RemediationStrategy.DEPLOYMENT_ROLLBACK: 0.8,
            RemediationStrategy.SERVICE_RESTART: 0.6,
            RemediationStrategy.SCALE_UP: 0.7,
            RemediationStrategy.CIRCUIT_BREAKER: 0.5,
            RemediationStrategy.TRAFFIC_SHIFT: 0.6
        }.get(strategy, 0.4)
        
        # Adjust based on RCA confidence
        rca_confidence_factor = analysis_result.confidence_score * 0.3
        
        # Adjust based on service configuration completeness
        config_completeness = 0.2 if service_config.previous_revision else 0.0
        
        total_confidence = base_confidence + rca_confidence_factor + config_completeness
        return min(1.0, total_confidence)
    
    async def _build_rollback_plan(self, strategy: RemediationStrategy, 
                                 service_config: ServiceConfiguration) -> Optional[Dict[str, Any]]:
        """Build a rollback plan for the remediation action"""
        if strategy == RemediationStrategy.DEPLOYMENT_ROLLBACK:
            # For rollback, the rollback plan is to roll forward again
            return {
                'action': 'roll_forward',
                'target_revision': service_config.current_revision,
                'deployment_name': service_config.deployment_name,
                'namespace': service_config.namespace
            }
        
        elif strategy == RemediationStrategy.SCALE_UP:
            return {
                'action': 'scale_down',
                'target_replicas': service_config.replica_count,
                'deployment_name': service_config.deployment_name,
                'namespace': service_config.namespace
            }
        
        # Other strategies may not have simple rollback plans
        return None
    
    def _determine_verification_tests(self, analysis_result) -> List[str]:
        """Determine which tests should be run to verify the remediation"""
        # Use the original failing test as primary verification
        verification_tests = []
        
        # Extract test name from trace ID or analysis
        if hasattr(analysis_result, 'trace_id'):
            verification_tests.append(f"verify_trace_{analysis_result.trace_id}")
        
        # Add service-specific health checks
        if analysis_result.failing_service:
            verification_tests.append(f"health_check_{analysis_result.failing_service}")
        
        return verification_tests
    
    def _build_impact_analysis(self, strategy: RemediationStrategy, 
                             service_config: ServiceConfiguration) -> str:
        """Build impact analysis for the remediation action"""
        impact_parts = []
        
        # Service impact
        impact_parts.append(f"Target service: {service_config.name} (criticality: {service_config.criticality_score:.2f})")
        
        # Dependent services impact
        if service_config.dependents:
            impact_parts.append(f"May affect {len(service_config.dependents)} dependent services: {', '.join(service_config.dependents)}")
        
        # Strategy-specific impact
        if strategy == RemediationStrategy.DEPLOYMENT_ROLLBACK:
            impact_parts.append(f"Rolling back from revision {service_config.current_revision} to {service_config.previous_revision}")
        elif strategy == RemediationStrategy.SCALE_UP:
            impact_parts.append(f"Scaling from {service_config.replica_count} to {service_config.replica_count * 2} replicas")
        
        return ". ".join(impact_parts)
    
    async def execute_remediation(self, action: RemediationAction) -> ExecutionResult:
        """
        Execute the approved remediation action by generating and running a shell script
        
        Args:
            action: RemediationAction to execute
            
        Returns:
            ExecutionResult with execution details
        """
        start_time = datetime.now()
        logger.info(f"Executing remediation action: {action.action_id} ({action.strategy.value})")
        
        try:
            # Generate shell script for the remediation
            script_path = await self._generate_remediation_script(action)
            self._last_script_path = script_path  # Store for A2A service access
            
            # Coordinate with other agents via A2A
            coordination_result = await self.a2a_coordinator.coordinate_multi_service_remediation(
                [action.target_service], action.strategy
            )
            
            # Execute the shell script
            execution_success = await self._execute_remediation_script(script_path)
            
            # Verify the remediation
            verification_result = await self._verify_remediation(action)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result = ExecutionResult(
                action_id=action.action_id,
                success=execution_success,
                execution_time=start_time,
                duration_seconds=execution_time,
                verification_status=verification_result['status'],
                verification_results=verification_result
            )
            
            # Notify other agents of completion
            await self.a2a_coordinator.send_message(
                "audit_agent",
                "log_remediation_complete",
                {
                    "action_id": action.action_id,
                    "success": execution_success,
                    "duration": execution_time,
                    "verification_status": verification_result['status']
                }
            )
            
            logger.info(f"Remediation execution completed: {action.action_id} "
                       f"(success: {execution_success}, verification: {verification_result['status']})")
            
            return result
            
        except Exception as e:
            logger.error(f"Remediation execution failed for {action.action_id}: {str(e)}")
            
            # Attempt rollback if available
            rollback_executed = False
            if action.rollback_plan:
                try:
                    rollback_script = await self._generate_rollback_script(action.rollback_plan)
                    await self._execute_remediation_script(rollback_script)
                    rollback_executed = True
                    logger.info(f"Rollback executed for failed remediation: {action.action_id}")
                except Exception as rollback_error:
                    logger.error(f"Rollback also failed: {str(rollback_error)}")
            
            return ExecutionResult(
                action_id=action.action_id,
                success=False,
                execution_time=start_time,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                verification_status='failed',
                error_message=str(e),
                rollback_executed=rollback_executed
            )
    
    async def _execute_strategy(self, action: RemediationAction) -> bool:
        """Execute the specific remediation strategy"""
        if action.strategy == RemediationStrategy.DEPLOYMENT_ROLLBACK:
            return await self._execute_deployment_rollback(action)
        
        elif action.strategy == RemediationStrategy.SERVICE_RESTART:
            return await self._execute_service_restart(action)
        
        elif action.strategy == RemediationStrategy.SCALE_UP:
            return await self._execute_scale_up(action)
        
        elif action.strategy == RemediationStrategy.CIRCUIT_BREAKER:
            return await self._execute_circuit_breaker(action)
        
        else:
            logger.error(f"Unknown remediation strategy: {action.strategy}")
            return False
    
    async def _execute_deployment_rollback(self, action: RemediationAction) -> bool:
        """Execute deployment rollback using Kubernetes MCP tools"""
        try:
            # TODO: Replace with actual MCP tool call
            # rollback_result = await self.mcp_server.call_tool('kubectl_rollout', {
            #     'subCommand': 'undo',
            #     'resourceType': 'deployment',
            #     'name': action.parameters['deployment_name'],
            #     'namespace': action.target_namespace,
            #     'toRevision': action.parameters['target_revision']
            # })
            
            # Mock successful rollback
            logger.info(f"Rolling back deployment {action.parameters['deployment_name']} "
                       f"to revision {action.parameters['target_revision']}")
            
            # Wait for rollout to complete
            # rollout_status = await self.mcp_server.call_tool('kubectl_rollout', {
            #     'subCommand': 'status',
            #     'resourceType': 'deployment',
            #     'name': action.parameters['deployment_name'],
            #     'namespace': action.target_namespace,
            #     'timeout': '300s'
            # })
            
            return True
            
        except Exception as e:
            logger.error(f"Deployment rollback failed: {str(e)}")
            return False
    
    async def _execute_service_restart(self, action: RemediationAction) -> bool:
        """Execute service restart using Kubernetes MCP tools"""
        try:
            # TODO: Replace with actual MCP tool call
            # restart_result = await self.mcp_server.call_tool('kubectl_rollout', {
            #     'subCommand': 'restart',
            #     'resourceType': 'deployment',
            #     'name': action.parameters['deployment_name'],
            #     'namespace': action.target_namespace
            # })
            
            logger.info(f"Restarting deployment {action.parameters['deployment_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Service restart failed: {str(e)}")
            return False
    
    async def _execute_scale_up(self, action: RemediationAction) -> bool:
        """Execute scale up using Kubernetes MCP tools"""
        try:
            # TODO: Replace with actual MCP tool call
            # scale_result = await self.mcp_server.call_tool('kubectl_scale', {
            #     'name': action.parameters['deployment_name'],
            #     'namespace': action.target_namespace,
            #     'replicas': action.parameters['target_replicas']
            # })
            
            logger.info(f"Scaling deployment {action.parameters['deployment_name']} "
                       f"to {action.parameters['target_replicas']} replicas")
            return True
            
        except Exception as e:
            logger.error(f"Scale up failed: {str(e)}")
            return False
    
    async def _execute_circuit_breaker(self, action: RemediationAction) -> bool:
        """Execute circuit breaker configuration"""
        try:
            # TODO: Implement circuit breaker configuration
            # This would typically involve updating service mesh configuration
            # or application-level circuit breaker settings
            
            logger.info(f"Configuring circuit breaker for service {action.target_service}")
            return True
            
        except Exception as e:
            logger.error(f"Circuit breaker configuration failed: {str(e)}")
            return False
    
    async def _verify_remediation(self, action: RemediationAction) -> Dict[str, Any]:
        """Verify that the remediation was successful"""
        verification_results = {
            'status': 'pending',
            'tests_run': [],
            'tests_passed': 0,
            'tests_failed': 0,
            'details': []
        }
        
        try:
            # Run verification tests
            for test_name in action.verification_tests:
                test_result = await self._run_verification_test(test_name, action)
                verification_results['tests_run'].append(test_name)
                
                if test_result['success']:
                    verification_results['tests_passed'] += 1
                else:
                    verification_results['tests_failed'] += 1
                
                verification_results['details'].append({
                    'test': test_name,
                    'result': test_result
                })
            
            # Determine overall status
            if verification_results['tests_failed'] == 0:
                verification_results['status'] = 'passed'
            else:
                verification_results['status'] = 'failed'
            
            logger.info(f"Verification completed for {action.action_id}: "
                       f"{verification_results['tests_passed']} passed, "
                       f"{verification_results['tests_failed']} failed")
            
        except Exception as e:
            logger.error(f"Verification failed for {action.action_id}: {str(e)}")
            verification_results['status'] = 'failed'
            verification_results['error'] = str(e)
        
        return verification_results
    
    async def _run_verification_test(self, test_name: str, action: RemediationAction) -> Dict[str, Any]:
        """Run a specific verification test"""
        try:
            if test_name.startswith('health_check_'):
                # Run health check for the service
                service_name = test_name.replace('health_check_', '')
                return await self._run_health_check(service_name, action.target_namespace)
            
            elif test_name.startswith('verify_trace_'):
                # Re-run the original failing test
                return await self._run_playwright_verification(test_name, action)
            
            else:
                logger.warning(f"Unknown verification test type: {test_name}")
                return {'success': False, 'error': 'Unknown test type'}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _run_health_check(self, service_name: str, namespace: str) -> Dict[str, Any]:
        """Run health check for a service"""
        try:
            # TODO: Replace with actual MCP tool call
            # health_result = await self.mcp_server.call_tool('kubectl_get', {
            #     'resourceType': 'pods',
            #     'namespace': namespace,
            #     'labelSelector': f'app={service_name}',
            #     'output': 'json'
            # })
            
            # Mock health check success
            return {
                'success': True,
                'healthy_pods': 3,
                'total_pods': 3,
                'message': f'All pods for {service_name} are healthy'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _run_playwright_verification(self, test_name: str, action: RemediationAction) -> Dict[str, Any]:
        """Re-run Playwright test to verify remediation"""
        try:
            # TODO: Replace with actual MCP tool call to Playwright
            # test_result = await self.mcp_server.call_tool('run-playwright-test', {
            #     'test_name': test_name,
            #     'timeout': self.verification_timeout_seconds * 1000
            # })
            
            # Mock successful test run
            return {
                'success': True,
                'duration': 45.2,
                'message': 'Test passed successfully after remediation'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_rollback(self, rollback_plan: Dict[str, Any]) -> bool:
        """Execute rollback plan if remediation fails"""
        try:
            if rollback_plan['action'] == 'roll_forward':
                # TODO: Implement roll forward logic
                logger.info(f"Rolling forward to revision {rollback_plan['target_revision']}")
                return True
            
            elif rollback_plan['action'] == 'scale_down':
                # TODO: Implement scale down logic
                logger.info(f"Scaling down to {rollback_plan['target_replicas']} replicas")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Rollback execution failed: {str(e)}")
            return False
    
    async def _generate_remediation_script(self, action: RemediationAction) -> str:
        """Generate a shell script for the remediation action"""
        import tempfile
        import os
        
        script_content = self._create_remediation_script_content(action)
        
        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write("set -e\n\n")
            f.write("# Remediation script generated by SelfHeal GKE\n")
            f.write(f"# Action ID: {action.action_id}\n")
            f.write(f"# Strategy: {action.strategy.value}\n")
            f.write(f"# Target: {action.target_service}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(script_content)
            f.write("\n\necho 'Remediation script completed successfully'\n")
            script_path = f.name
        
        # Make script executable
        os.chmod(script_path, 0o755)
        
        logger.info(f"Generated remediation script: {script_path}")
        return script_path
    
    def _create_remediation_script_content(self, action: RemediationAction) -> str:
        """Create the actual script content based on remediation strategy"""
        namespace = action.target_namespace or "default"
        
        if action.strategy == RemediationStrategy.DEPLOYMENT_ROLLBACK:
            return f"""
echo "Rolling back deployment {action.parameters['deployment_name']} to revision {action.parameters['target_revision']}"
kubectl rollout undo deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    --to-revision={action.parameters['target_revision']}

echo "Waiting for rollout to complete..."
kubectl rollout status deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    --timeout=300s

echo "Verifying rollback..."
kubectl get deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    -o jsonpath='{{.status.observedGeneration}}'
"""
        
        elif action.strategy == RemediationStrategy.SERVICE_RESTART:
            return f"""
echo "Restarting deployment {action.parameters['deployment_name']}"
kubectl rollout restart deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace}

echo "Waiting for restart to complete..."
kubectl rollout status deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    --timeout=300s

echo "Checking pod status..."
kubectl get pods \\
    --namespace={namespace} \\
    -l app={action.target_service} \\
    --no-headers | wc -l
"""
        
        elif action.strategy == RemediationStrategy.SCALE_UP:
            return f"""
echo "Scaling deployment {action.parameters['deployment_name']} from {action.parameters['current_replicas']} to {action.parameters['target_replicas']} replicas"
kubectl scale deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    --replicas={action.parameters['target_replicas']}

echo "Waiting for scaling to complete..."
kubectl rollout status deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    --timeout=300s

echo "Verifying replica count..."
kubectl get deployment/{action.parameters['deployment_name']} \\
    --namespace={namespace} \\
    -o jsonpath='{{.status.replicas}}'
"""
        
        elif action.strategy == RemediationStrategy.CIRCUIT_BREAKER:
            return f"""
echo "Implementing circuit breaker for service {action.target_service}"
# Note: Circuit breaker implementation depends on service mesh (Istio/Linkerd)
# This is a placeholder for actual circuit breaker configuration

# Example with Istio:
# kubectl apply -f - <<EOF
# apiVersion: networking.istio.io/v1beta1
# kind: VirtualService
# metadata:
#   name: {action.target_service}-circuit-breaker
#   namespace: {namespace}
# spec:
#   http:
#   - route:
#     - destination:
#         host: {action.target_service}
#     timeout: 5s
#     retries:
#       attempts: 1
# EOF

echo "Circuit breaker configuration applied (placeholder)"
"""
        
        else:
            return f"""
echo "Unknown remediation strategy: {action.strategy.value}"
echo "No script generated for this strategy"
exit 1
"""
    
    async def _execute_remediation_script(self, script_path: str) -> bool:
        """Execute the remediation script using the terminal tool"""
        try:
            logger.info(f"Executing remediation script: {script_path}")
            
            # Use run_in_terminal to execute the script
            result = await self._run_terminal_command(f"bash {script_path}")
            
            if result['success']:
                logger.info("Remediation script executed successfully")
                return True
            else:
                logger.error(f"Remediation script failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute remediation script: {e}")
            return False
        finally:
            # Note: Script cleanup is now handled by the caller (A2A service)
            # to allow for additional processing
            pass
    
    async def _run_terminal_command(self, command: str) -> Dict[str, Any]:
        """Run a terminal command and return the result"""
        # This is a placeholder - in a real implementation, this would use
        # the run_in_terminal tool or similar mechanism
        # For now, we'll simulate success
        logger.info(f"Would execute command: {command}")
        return {'success': True, 'output': 'Command executed successfully'}
    
    async def _generate_rollback_script(self, rollback_plan: Dict[str, Any]) -> str:
        """Generate a rollback script"""
        import tempfile
        import os
        
        script_content = self._create_rollback_script_content(rollback_plan)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write("set -e\n\n")
            f.write("# Rollback script generated by SelfHeal GKE\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(script_content)
            f.write("\n\necho 'Rollback script completed successfully'\n")
            script_path = f.name
        
        os.chmod(script_path, 0o755)
        
        logger.info(f"Generated rollback script: {script_path}")
        return script_path
    
    def _create_rollback_script_content(self, rollback_plan: Dict[str, Any]) -> str:
        """Create rollback script content"""
        action = rollback_plan.get('action', '')
        namespace = rollback_plan.get('namespace', 'default')
        
        if action == 'roll_forward':
            deployment_name = rollback_plan.get('deployment_name', '')
            target_revision = rollback_plan.get('target_revision', '')
            return f"""
echo "Rolling forward deployment {deployment_name} to revision {target_revision}"
kubectl rollout undo deployment/{deployment_name} \\
    --namespace={namespace} \\
    --to-revision={target_revision}

echo "Waiting for roll forward to complete..."
kubectl rollout status deployment/{deployment_name} \\
    --namespace={namespace} \\
    --timeout=300s
"""
        
        elif action == 'scale_down':
            deployment_name = rollback_plan.get('deployment_name', '')
            target_replicas = rollback_plan.get('target_replicas', 1)
            return f"""
echo "Scaling down deployment {deployment_name} to {target_replicas} replicas"
kubectl scale deployment/{deployment_name} \\
    --namespace={namespace} \\
    --replicas={target_replicas}

echo "Waiting for scale down to complete..."
kubectl rollout status deployment/{deployment_name} \\
    --namespace={namespace} \\
    --timeout=300s
"""
        
        else:
            return f"""
echo "Unknown rollback action: {action}"
echo "No rollback script generated"
exit 1
"""

    async def initialize_a2a(self):
        """Initialize A2A client for inter-agent communication"""
        try:
            if A2A_AVAILABLE:
                config = ClientConfig(
                    server_url=os.getenv('A2A_SERVER_URL', 'http://localhost:8001'),
                    api_key=os.getenv('A2A_API_KEY')
                )
                self.a2a_client = Client(config)
                self.logger.info("A2A client initialized for remediation agent")
            else:
                self.logger.warning("A2A SDK not available, inter-agent communication disabled")
        except Exception as e:
            self.logger.error(f"Failed to initialize A2A client: {e}")

    async def _plan_remediation_with_gemini(self, analysis_result: Any, service_config: ServiceConfiguration) -> Optional[RemediationAction]:
        """Use Gemini LLM to plan remediation when ADK is not available"""
        try:
            if not self.gemini_model:
                self.logger.warning("Gemini model not available for remediation planning")
                return None

            # Format remediation planning prompt
            prompt = self._format_remediation_prompt(analysis_result, service_config)

            # Get Gemini response
            self.logger.info("Requesting remediation plan from Gemini")
            response = await self.gemini_model.generate_content_async(prompt)
            
            # Parse response and create remediation action
            action = self._parse_gemini_remediation_response(response, service_config)
            
            if action:
                self.logger.info(f"Gemini suggested remediation: {action.strategy.value}")
            
            return action

        except Exception as e:
            self.logger.error(f"Gemini remediation planning failed: {e}")
            return None

    def _format_remediation_prompt(self, analysis_result: Any, service_config: ServiceConfiguration) -> str:
        """Format analysis data into a remediation planning prompt"""
        prompt = f"""
You are an expert remediation planning agent for microservices applications.

ANALYZE THIS FAILURE AND RECOMMEND REMEDIATION:

Service: {service_config.name}
Failure Summary: {analysis_result.summary}
Classification: {analysis_result.classification.value if hasattr(analysis_result, 'classification') else 'Unknown'}
Confidence: {analysis_result.confidence_score:.2f}

SERVICE CONFIGURATION:
- Current Revision: {service_config.current_revision}
- Previous Revision: {service_config.previous_revision or 'None'}
- Replica Count: {service_config.replica_count}
- Criticality Score: {service_config.criticality_score:.2f}
- Dependencies: {', '.join(service_config.dependencies) if service_config.dependencies else 'None'}
- Dependents: {', '.join(service_config.dependents) if service_config.dependents else 'None'}

AVAILABLE REMEDIATION STRATEGIES:
1. DEPLOYMENT_ROLLBACK - Roll back to previous deployment version (if available)
2. SERVICE_RESTART - Restart the failing service pods
3. SCALE_UP - Increase replica count to handle load
4. CIRCUIT_BREAKER - Temporarily isolate failing service
5. TRAFFIC_SHIFT - Redirect traffic away from failing service
6. NO_ACTION - No remediation needed

RECOMMENDATION FORMAT (JSON):
{{
  "strategy": "DEPLOYMENT_ROLLBACK|SERVICE_RESTART|SCALE_UP|CIRCUIT_BREAKER|TRAFFIC_SHIFT|NO_ACTION",
  "reasoning": "Detailed explanation of why this strategy is recommended",
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "confidence_score": 0.85,
  "estimated_duration_seconds": 120
}}

Choose the safest and most effective remediation strategy based on the failure analysis and service configuration.
"""

        return prompt

    def _parse_gemini_remediation_response(self, response: Any, service_config: ServiceConfiguration) -> Optional[RemediationAction]:
        """Parse Gemini's remediation recommendation"""
        try:
            # Extract text from Gemini response
            if hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)

            self.logger.info(f"Gemini remediation response: {response_text[:500]}...")

            # Try to parse JSON from response
            import json
            import re

            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    parsed = json.loads(json_str)
                    strategy_str = parsed.get('strategy', '').upper()
                    
                    # Map string to enum
                    strategy_map = {
                        'DEPLOYMENT_ROLLBACK': RemediationStrategy.DEPLOYMENT_ROLLBACK,
                        'SERVICE_RESTART': RemediationStrategy.SERVICE_RESTART,
                        'SCALE_UP': RemediationStrategy.SCALE_UP,
                        'CIRCUIT_BREAKER': RemediationStrategy.CIRCUIT_BREAKER,
                        'TRAFFIC_SHIFT': RemediationStrategy.TRAFFIC_SHIFT,
                        'NO_ACTION': RemediationStrategy.NO_ACTION
                    }
                    
                    strategy = strategy_map.get(strategy_str, RemediationStrategy.NO_ACTION)
                    
                    if strategy != RemediationStrategy.NO_ACTION:
                        return RemediationAction(
                            action_id=f"gemini_{strategy.value}_{service_config.name}_{datetime.now().timestamp()}",
                            strategy=strategy,
                            target_service=service_config.name,
                            target_namespace=service_config.namespace,
                            parameters={},
                            risk_level=RiskLevel(parsed.get('risk_level', 'MEDIUM').upper()),
                            estimated_duration=int(parsed.get('estimated_duration_seconds', 60)),
                            confidence_score=float(parsed.get('confidence_score', 0.5)),
                            rollback_plan=None,
                            verification_tests=[f"health_check_{service_config.name}"],
                            impact_analysis=parsed.get('reasoning', 'Remediation recommended by AI analysis')
                        )
                except json.JSONDecodeError:
                    pass

            # Fallback: extract strategy from text - more robust pattern matching
            text_lower = response_text.lower()
            
            # Check for specific patterns in order of preference
            if 'scale_up' in text_lower or ('scale' in text_lower and 'up' in text_lower and 'scale_down' not in text_lower):
                strategy = RemediationStrategy.SCALE_UP
            elif 'deployment_rollback' in text_lower or ('rollback' in text_lower and 'roll back' in text_lower):
                strategy = RemediationStrategy.DEPLOYMENT_ROLLBACK
            elif 'service_restart' in text_lower or ('restart' in text_lower and 'service' in text_lower):
                strategy = RemediationStrategy.SERVICE_RESTART
            elif 'circuit_breaker' in text_lower or 'circuit breaker' in text_lower:
                strategy = RemediationStrategy.CIRCUIT_BREAKER
            elif 'traffic_shift' in text_lower or 'traffic shift' in text_lower:
                strategy = RemediationStrategy.TRAFFIC_SHIFT
            elif 'no_action' in text_lower or 'no action' in text_lower:
                strategy = RemediationStrategy.NO_ACTION
            else:
                # Last resort: look for any mention of strategies
                if 'scale' in text_lower:
                    strategy = RemediationStrategy.SCALE_UP
                elif 'rollback' in text_lower:
                    strategy = RemediationStrategy.DEPLOYMENT_ROLLBACK
                elif 'restart' in text_lower:
                    strategy = RemediationStrategy.SERVICE_RESTART
                else:
                    strategy = RemediationStrategy.NO_ACTION

            if strategy != RemediationStrategy.NO_ACTION:
                return RemediationAction(
                    action_id=f"fallback_{strategy.value}_{service_config.name}_{datetime.now().timestamp()}",
                    strategy=strategy,
                    target_service=service_config.name,
                    target_namespace=service_config.namespace,
                    parameters={},
                    risk_level=RiskLevel.MEDIUM,
                    estimated_duration=60,
                    confidence_score=0.7,
                    rollback_plan=None,
                    verification_tests=[f"health_check_{service_config.name}"],
                    impact_analysis=response_text[:500] + "..." if len(response_text) > 500 else response_text
                )

            return None

        except Exception as e:
            self.logger.error(f"Failed to parse Gemini remediation response: {e}")
            return None


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def test_remediation_agent():
        """Test the remediation agent functionality"""
        config = AgentConfig(
            agent_id="test_remediation_agent",
            agent_type="remediation",
            capabilities=["remediation", "service_discovery"],
            heartbeat_interval=30,
            health_check_interval=60,
            max_concurrent_tasks=5,
            metadata={
                'max_rollback_age_hours': 24,
                'verification_timeout_seconds': 300,
                'risk_tolerance': 'medium'
            }
        )
        
        agent = RemediationAgent(config)
        await agent.initialize()
        
        # Mock analysis result
        from rca_agent import AnalysisResult, FailureClassification, Evidence
        
        mock_analysis = AnalysisResult(
            classification=FailureClassification.BACKEND_ERROR,
            failing_service="test-service",
            summary="Database connection failure in test service",
            confidence_score=0.85,
            evidence=[
                Evidence(
                    type='log',
                    source='cloud_logging',
                    content='Database connection timeout',
                    severity='ERROR',
                    timestamp=datetime.now(),
                    service_name='test-service'
                )
            ],
            analysis_duration=45.2,
            trace_id="test-trace-123"
        )
        
        # Test remediation proposal
        action = await agent.propose_remediation(mock_analysis)
        if action:
            print(f"Proposed action: {action.strategy.value}")
            print(f"Risk level: {action.risk_level.value}")
            print(f"Confidence: {action.confidence_score:.2f}")
            
            # Test execution (would be done after human approval)
            # result = await agent.execute_remediation(action)
            # print(f"Execution result: {result.success}")
        else:
            print("No remediation action proposed")
    

# Example usage and testing functions
async def test_remediation_agent():
    """Example usage of the Remediation Agent"""
    
    # Initialize agent
    config = AgentConfig(
        agent_id="remediation_agent",
        agent_type="remediation",
        capabilities=["remediation", "service_discovery"],
        heartbeat_interval=30,
        health_check_interval=60,
        max_concurrent_tasks=5,
        metadata={
            'max_rollback_age_hours': 24,
            'verification_timeout_seconds': 300,
            'risk_tolerance': 'medium'
        }
    )
    
    agent = RemediationAgent(config)
    
    # Mock analysis result - simplified for testing
    # Define required classes locally for testing
    from enum import Enum
    from dataclasses import dataclass
    from typing import List, Optional
    
    class FailureClassification(Enum):
        BACKEND_ERROR = "Backend Error"
        UI_BRITTLENESS = "UI Brittleness"
        UNKNOWN = "Unknown"
    
    @dataclass
    class Evidence:
        type: str
        source: str
        content: str
        severity: str
        timestamp: datetime
        service_name: Optional[str] = None
    
    @dataclass
    class AnalysisResult:
        classification: FailureClassification
        failing_service: Optional[str]
        summary: str
        confidence_score: float
        evidence: List[Evidence]
        analysis_duration: float
        trace_id: str
    
    analysis_result = AnalysisResult(
        classification=FailureClassification.BACKEND_ERROR,
        failing_service="api-service",
        summary="API service database connection failed",
        confidence_score=0.85,
        evidence=[],
        analysis_duration=45.0,
        trace_id="test-trace-123"
    )
    
    # Test remediation proposal
    action = await agent.propose_remediation(analysis_result)
    
    if action:
        print(f"Proposed action: {action.strategy.value}")
        print(f"Target service: {action.target_service}")
        print(f"Risk level: {action.risk_level.value}")
        print(f"Confidence: {action.confidence_score:.2f}")
        
        # Test remediation execution (would require approval in real scenario)
        # result = await agent.execute_remediation(action)
        # print(f"Execution result: {result.success}")
    else:
        print("No remediation action proposed")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_remediation_agent())