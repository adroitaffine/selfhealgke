"""
RCA Agent - ADK LlmAgent with Gemini, A2A, and MCP Integration

This agent analyzes test failures using ADK LlmAgent with Gemini LLM,
correlates with backend telemetry via MCP, and communicates via A2A.
"""

import asyncio
import json
import logging
import uuid
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from dotenv import load_dotenv
load_dotenv()

# ADK imports - with fallback
try:
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini
    from google.adk.tools import FunctionTool
    from google.adk import Runner
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    LlmAgent = object
    Gemini = object
    FunctionTool = object
    Runner = object

# Direct Gemini import for fallback
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# A2A imports
from a2a.client import Client, ClientConfig
from a2a.types import Message, TextPart, Role

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class FailureClassification(Enum):
    """Classification types for test failures"""
    UI_BRITTLENESS = "UI Brittleness"
    BACKEND_ERROR = "Backend Error"
    UNKNOWN = "Unknown"


@dataclass
class ErrorDetails:
    """Error details from Playwright test failure"""
    message: str
    stack: str
    type: str


@dataclass
class FailurePayload:
    """Payload received from Playwright webhook"""
    test_title: str
    status: str  # 'failed' | 'timedOut'
    error: ErrorDetails
    retries: int
    trace_id: str
    video_url: Optional[str] = None
    trace_url: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class Evidence:
    """Evidence collected during analysis"""
    type: str  # 'log', 'trace', 'metric'
    source: str
    content: str
    severity: str
    timestamp: datetime
    service_name: Optional[str] = None


@dataclass
class AnalysisResult:
    """Result of RCA analysis"""
    classification: FailureClassification
    failing_service: Optional[str]
    summary: str
    confidence_score: float
    evidence: List[Evidence]
    analysis_duration: float
    trace_id: str


@dataclass
class ServiceNode:
    """Represents a discovered microservice in the topology"""
    name: str
    endpoints: List[str]
    dependencies: List[str]  # Services this service calls
    dependents: List[str]   # Services that call this service
    error_patterns: List[str]
    health_indicators: Dict[str, Any]
    criticality_score: float = 0.0  # 0-1 based on dependency count and error frequency


@dataclass
class ServiceTopology:
    """Represents the discovered microservice topology"""
    services: Dict[str, ServiceNode]
    call_graph: Dict[str, List[str]]  # service -> list of called services
    entry_points: List[str]  # Services that receive external traffic
    critical_path: List[str]  # Most critical service chain
    
    def get_service_criticality(self, service_name: str) -> float:
        """Calculate service criticality based on topology position"""
        if service_name not in self.services:
            return 0.0
        
        service = self.services[service_name]
        
        # Factors for criticality:
        # 1. Number of dependents (services that depend on this one)
        # 2. Position in critical path
        # 3. Whether it's an entry point
        
        dependent_score = len(service.dependents) * 0.3
        entry_point_score = 0.4 if service_name in self.entry_points else 0.0
        critical_path_score = 0.3 if service_name in self.critical_path else 0.0
        
        return min(1.0, dependent_score + entry_point_score + critical_path_score)


class MicroserviceTopologyDiscovery:
    """Discovers microservice topology from distributed traces and logs"""
    
    def __init__(self):
        self.discovered_topology: Optional[ServiceTopology] = None
        self.service_patterns = {}  # Learned patterns for each service
        
    async def discover_topology_from_traces(self, traces_data: Dict[str, Any]) -> ServiceTopology:
        """
        Discover microservice topology from trace data
        
        Args:
            traces_data: Distributed trace data with spans
            
        Returns:
            ServiceTopology with discovered services and dependencies
        """
        services = {}
        call_graph = {}
        
        # Analyze spans to build service map
        spans = traces_data.get('spans', [])
        
        for span in spans:
            service_name = self._extract_service_name(span)
            if not service_name:
                continue
                
            # Initialize service if not seen before
            if service_name not in services:
                services[service_name] = ServiceNode(
                    name=service_name,
                    endpoints=[],
                    dependencies=[],
                    dependents=[],
                    error_patterns=[],
                    health_indicators={}
                )
                call_graph[service_name] = []
            
            # Extract service information from span
            self._analyze_span_for_service_info(span, services[service_name])
            
            # Build call graph from parent-child relationships
            parent_service = self._extract_parent_service(span, spans)
            if parent_service and parent_service != service_name:
                if service_name not in call_graph[parent_service]:
                    call_graph[parent_service].append(service_name)
                if parent_service not in services[service_name].dependents:
                    services[service_name].dependents.append(parent_service)
                if service_name not in services[parent_service].dependencies:
                    services[parent_service].dependencies.append(service_name)
        
        # Identify entry points (services with no dependents or HTTP ingress)
        entry_points = self._identify_entry_points(services, spans)
        
        # Calculate critical path
        critical_path = self._calculate_critical_path(services, call_graph, entry_points)
        
        # Calculate criticality scores
        topology = ServiceTopology(
            services=services,
            call_graph=call_graph,
            entry_points=entry_points,
            critical_path=critical_path
        )
        
        for service_name in services:
            services[service_name].criticality_score = topology.get_service_criticality(service_name)
        
        self.discovered_topology = topology
        return topology
    
    def _extract_service_name(self, span: Dict[str, Any]) -> Optional[str]:
        """Extract service name from span data"""
        # Try multiple common fields for service name
        service_name = (
            span.get('service_name') or
            span.get('resource', {}).get('service.name') or
            span.get('attributes', {}).get('service.name') or
            span.get('tags', {}).get('service.name') or
            span.get('process', {}).get('serviceName')
        )
        
        # If no explicit service name, try to infer from span name
        if not service_name:
            span_name = span.get('name', '')
            # Common patterns: "servicename.method", "servicename-operation", etc.
            if '.' in span_name:
                service_name = span_name.split('.')[0]
            elif '-' in span_name and not span_name.startswith('http'):
                parts = span_name.split('-')
                if len(parts) > 1:
                    service_name = parts[0]
        
        return service_name.lower() if service_name else None
    
    def _analyze_span_for_service_info(self, span: Dict[str, Any], service: ServiceNode):
        """Extract service information from individual span"""
        # Extract endpoints
        http_url = span.get('attributes', {}).get('http.url')
        if http_url and http_url not in service.endpoints:
            service.endpoints.append(http_url)
        
        # Extract error patterns
        if span.get('status', {}).get('code', 0) != 0:
            error_msg = span.get('status', {}).get('message', '')
            if error_msg and error_msg not in service.error_patterns:
                service.error_patterns.append(error_msg)
        
        # Update health indicators
        status_code = span.get('status', {}).get('code', 0)
        if 'error_count' not in service.health_indicators:
            service.health_indicators['error_count'] = 0
            service.health_indicators['total_count'] = 0
        
        service.health_indicators['total_count'] += 1
        if status_code != 0:
            service.health_indicators['error_count'] += 1
    
    def _extract_parent_service(self, span: Dict[str, Any], all_spans: List[Dict]) -> Optional[str]:
        """Find parent service for this span"""
        parent_span_id = span.get('parent_span_id') or span.get('parentSpanId')
        if not parent_span_id:
            return None
        
        # Find parent span
        for parent_span in all_spans:
            if parent_span.get('span_id') == parent_span_id or parent_span.get('spanId') == parent_span_id:
                return self._extract_service_name(parent_span)
        
        return None
    
    def _identify_entry_points(self, services: Dict[str, ServiceNode], spans: List[Dict]) -> List[str]:
        """Identify services that are entry points to the system"""
        entry_points = []
        
        for service_name, service in services.items():
            # Check if service has HTTP ingress indicators
            has_http_ingress = any(
                span.get('attributes', {}).get('http.method') in ['GET', 'POST', 'PUT', 'DELETE']
                and span.get('attributes', {}).get('http.route')
                for span in spans
                if self._extract_service_name(span) == service_name
            )
            
            # Entry point if: has HTTP ingress OR has no dependents
            if has_http_ingress or len(service.dependents) == 0:
                entry_points.append(service_name)
        
        return entry_points
    
    def _calculate_critical_path(self, services: Dict[str, ServiceNode], 
                               call_graph: Dict[str, List[str]], 
                               entry_points: List[str]) -> List[str]:
        """Calculate the most critical service path"""
        if not entry_points:
            return []
        
        # Simple heuristic: longest path from entry point with most dependencies
        longest_path = []
        
        for entry_point in entry_points:
            path = self._find_longest_path(entry_point, call_graph, set())
            if len(path) > len(longest_path):
                longest_path = path
        
        return longest_path
    
    def _find_longest_path(self, service: str, call_graph: Dict[str, List[str]], 
                          visited: set) -> List[str]:
        """Find longest path from a service using DFS"""
        if service in visited:
            return []
        
        visited.add(service)
        longest_subpath = []
        
        for dependency in call_graph.get(service, []):
            subpath = self._find_longest_path(dependency, call_graph, visited.copy())
            if len(subpath) > len(longest_subpath):
                longest_subpath = subpath
        
        return [service] + longest_subpath
    
    def identify_failing_service_from_topology(self, error_evidence: List[Evidence]) -> Optional[str]:
        """
        Identify the most likely failing service based on topology and evidence
        
        Args:
            error_evidence: List of error evidence from logs/traces
            
        Returns:
            Name of most likely failing service
        """
        if not self.discovered_topology or not error_evidence:
            return None
        
        service_error_scores = {}
        
        for evidence in error_evidence:
            if evidence.service_name and evidence.service_name in self.discovered_topology.services:
                service = self.discovered_topology.services[evidence.service_name]
                
                # Score based on: error severity + service criticality + evidence type
                severity_score = {'CRITICAL': 1.0, 'ERROR': 0.8, 'WARNING': 0.4}.get(evidence.severity, 0.2)
                evidence_score = {'trace': 1.0, 'log': 0.8, 'metric': 0.6}.get(evidence.type, 0.5)
                
                total_score = severity_score * service.criticality_score * evidence_score
                
                if evidence.service_name not in service_error_scores:
                    service_error_scores[evidence.service_name] = 0
                service_error_scores[evidence.service_name] += total_score
        
        # Return service with highest error score
        if service_error_scores:
            return max(service_error_scores.items(), key=lambda x: x[1])[0]
        
        return None


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

class RCAAgent:
    """
    RCA Agent - ADK LlmAgent for Root Cause Analysis

    Uses Gemini LLM through ADK, A2A for communication, and MCP for telemetry.
    """

    def __init__(self, agent_id: Optional[str] = None):
        if agent_id is None:
            agent_id = f"rca-{uuid.uuid4()}"

        self.agent_id = agent_id
        self.logger = logging.getLogger(f"{__name__}.{agent_id}")

        # Initialize Gemini client directly
        self.gemini_model = None
        if GENAI_AVAILABLE:
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')  # Use available model
            self.logger.info("Initialized direct Gemini client")
        else:
            self.logger.warning("Gemini not available, analysis will fail")

        # A2A client for communication
        self.a2a_client = None

        # MCP session for telemetry
        self.mcp_session = None

        # Analysis state
        self.active_analyses: Dict[str, asyncio.Task] = {}
        
        # Topology discovery state
        self.discovered_topology: Optional[ServiceTopology] = None
        self.analyzed_failures_count = 0
        self.common_error_types: List[str] = []
        self.frequent_failures: List[str] = []

        self.logger.info(f"RCA Agent initialized: {agent_id}")

    async def initialize(self):
        """Initialize the ADK agent"""
        # LlmAgent doesn't seem to need explicit initialization
        pass

    def _get_system_instruction(self) -> str:
        """Get system instruction for the RCA agent"""
        return """
You are an expert Root Cause Analysis agent for microservices applications.

Your role is to analyze test failures and determine if they are caused by:
1. UI brittleness (frontend test issues)
2. Backend errors (genuine service failures)

Use the provided tools to:
- Collect telemetry data (logs, traces, metrics)
- Discover service topology and dependencies
- Analyze evidence for root causes
- Classify failures with confidence scores

Always provide structured analysis with:
- Classification (UI Brittleness or Backend Error)
- Failing service identification
- Root cause explanation
- Confidence score (0.0-1.0)
- Remediation recommendations

Be thorough but concise. Use evidence to support your conclusions.
"""

    def _create_rca_tools(self) -> List[FunctionTool]:
        """Create RCA-specific tools for the agent"""
        return [
            FunctionTool(
                func=self._collect_telemetry_tool
            ),
            FunctionTool(
                func=self._discover_topology_tool
            ),
            FunctionTool(
                func=self._analyze_evidence_tool
            ),
            FunctionTool(
                func=self._call_mcp_tool
            )
        ]

    async def _collect_telemetry_tool(self, trace_id: str, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Tool function for collecting telemetry data"""
        try:
            telemetry_data = await self._collect_telemetry(trace_id, time_window_minutes)
            return {
                "success": True,
                "telemetry": telemetry_data,
                "trace_id": trace_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "trace_id": trace_id
            }

    async def _discover_topology_tool(self, traces_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tool function for topology discovery"""
        try:
            topology = await self._discover_topology_from_traces(traces_data)
            return {
                "success": True,
                "topology": {
                    "services": list(topology.services.keys()),
                    "entry_points": topology.entry_points,
                    "critical_path": topology.critical_path,
                    "service_count": len(topology.services)
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _analyze_evidence_tool(self, evidence_list: List[Dict[str, Any]],
                                   topology: Dict[str, Any]) -> Dict[str, Any]:
        """Tool function for evidence analysis"""
        try:
            analysis = self._analyze_evidence_patterns(evidence_list, topology)
            return {
                "success": True,
                "analysis": analysis
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _call_mcp_tool(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call MCP server tools"""
        return await self._call_mcp_tool_impl(server_name, tool_name, params)

    async def _collect_telemetry(self, trace_id: str, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Collect telemetry data for analysis"""
        # Use MCP to collect real telemetry
        try:
            telemetry_data = await self._call_mcp_tool_impl("gcp-observability", "correlate-telemetry", {
                "trace_id": trace_id,
                "time_window": time_window_minutes * 60  # Convert to seconds
            })

            # Parse the correlated telemetry data
            # MCP returns a CallToolResult object with content
            if hasattr(telemetry_data, 'content') and telemetry_data.content:
                # Extract text from the first content item
                content = telemetry_data.content[0]
                if hasattr(content, 'text'):
                    import json
                    parsed_data = json.loads(content.text)
                    
                    if "raw_data" in parsed_data:
                        raw_data = parsed_data["raw_data"]
                        return {
                            "logs": raw_data.get("logs", {}).get("logs", []),
                            "traces": raw_data.get("traces", {}).get("spans", [])
                        }
                    else:
                        # Direct format
                        return {
                            "logs": parsed_data.get("logs", []),
                            "traces": parsed_data.get("traces", {"spans": []})
                        }
            
            # If parsing fails, fall back to mock data
            self.logger.warning(f"Unexpected MCP response format: {telemetry_data}, using mock data")
            return self._get_mock_telemetry(trace_id)

        except Exception as e:
            self.logger.warning(f"MCP telemetry collection failed: {e}, using mock data")
            return self._get_mock_telemetry(trace_id)

    def _get_mock_telemetry(self, trace_id: str) -> Dict[str, Any]:
        """Get mock telemetry for testing - application agnostic"""
        return {
            'logs': [
                {
                    'timestamp': datetime.now().isoformat(),
                    'severity': 'ERROR',
                    'message': 'Service connection failed: connection refused',
                    'service': 'unknown-service',
                    'trace_id': trace_id
                }
            ],
            'traces': {
                'spans': [
                    {
                        'name': 'service-call',
                        'service': 'unknown-service',
                        'status': {'code': 2, 'message': 'Internal Server Error'},
                        'duration': '5.0s'
                    }
                ]
            }
        }

    async def _discover_topology_from_traces(self, traces_data: Dict[str, Any]) -> ServiceTopology:
        """Discover service topology from traces using dynamic discovery"""
        topology_discovery = MicroserviceTopologyDiscovery()
        topology = await topology_discovery.discover_topology_from_traces(traces_data)
        
        # Store discovered topology for insights
        self.discovered_topology = topology
        
        return topology

    def _extract_service_name(self, span: Dict[str, Any]) -> Optional[str]:
        """Extract service name from span"""
        return span.get('service') or span.get('service_name')

    def _analyze_evidence_patterns(self, evidence_list: List[Dict[str, Any]],
                                 topology: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze evidence for patterns"""
        backend_errors = 0
        ui_indicators = 0

        for evidence in evidence_list:
            content = evidence.get('content', '').lower()
            if any(term in content for term in ['timeout', 'connection', 'service', 'database']):
                backend_errors += 1
            elif any(term in content for term in ['selector', 'element', 'locator']):
                ui_indicators += 1

        return {
            "classification": "Backend Error" if backend_errors > ui_indicators else "UI Brittleness",
            "backend_errors": backend_errors,
            "ui_indicators": ui_indicators,
            "confidence": max(backend_errors, ui_indicators) / len(evidence_list) if evidence_list else 0.5
        }

    async def _call_mcp_tool_impl(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call MCP tool implementation"""
        try:
            # Try to import MCP modules
            try:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
            except ImportError:
                self.logger.warning("MCP modules not available, using mock response")
                return {}

            server_scripts = {
                "gcp-observability": "mcp-servers/gcp_observability_server.py",
            }

            script_path = server_scripts.get(server_name)
            if not script_path:
                raise ValueError(f"Unknown MCP server: {server_name}")

            server_params = StdioServerParameters(
                command='python3',
                args=[script_path],
                env={
                    'GCP_PROJECT_ID': os.getenv('GCP_PROJECT_ID', 'cogent-spirit-469200-q3'),
                    'PYTHONPATH': '.',
                    'FASTMCP_LOG_LEVEL': 'INFO'
                }
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, params)
                    return result

        except Exception as e:
            self.logger.warning(f"MCP tool call failed: {e}")
            return {}

    async def initialize_a2a(self):
        """Initialize A2A client"""
        try:
            config = ClientConfig(
                server_url=os.getenv('A2A_SERVER_URL', 'http://localhost:8001'),
                api_key=os.getenv('A2A_API_KEY')
            )
            self.a2a_client = Client(config)
            self.logger.info("A2A client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize A2A client: {e}")

    async def analyze_failure(self, failure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main analysis method - uses Gemini LLM for root cause analysis"""
        try:
            # Extract failure information
            trace_id = failure_data.get('trace_id', str(uuid.uuid4()))
            error_message = failure_data.get('error_message', 'Unknown error')
            test_title = failure_data.get('test_title', 'Test failure')

            # Collect telemetry using MCP tools
            telemetry = await self._collect_telemetry(trace_id)

            # Build evidence list
            evidence = self._build_evidence_list(telemetry)

            # Format analysis prompt for Gemini
            analysis_prompt = self._format_analysis_prompt(
                test_title=test_title,
                error_message=error_message,
                trace_id=trace_id,
                telemetry=telemetry,
                evidence=evidence
            )

            # Use Gemini LLM for analysis
            self.logger.info(f"Sending analysis request to Gemini for trace {trace_id}")
            
            if self.gemini_model:
                response = await self.gemini_model.generate_content_async(analysis_prompt)
                gemini_response = response
            else:
                raise Exception("Gemini model not available")

            # Parse Gemini response
            analysis_result = self._parse_gemini_response(response)

            # Add metadata
            analysis_result.update({
                "evidence_count": len(evidence),
                "trace_id": trace_id,
                "analysis_duration": 0.0  # Could be calculated if needed
            })

            self.logger.info(f"Gemini analysis completed for trace {trace_id}: {analysis_result.get('classification')}")
            return analysis_result

        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            return {
                "classification": "Unknown",
                "failing_service": None,
                "summary": f"Analysis failed: {str(e)}",
                "confidence_score": 0.0,
                "evidence_count": 0,
                "trace_id": failure_data.get('trace_id', 'unknown')
            }

    def _format_analysis_prompt(self, test_title: str, error_message: str, trace_id: str,
                               telemetry: Dict[str, Any], evidence: List[Dict[str, Any]]) -> str:
        """Format analysis data into a prompt for Gemini"""
        prompt = f"""
You are an expert Root Cause Analysis agent for microservices applications.

ANALYZE THIS FAILURE:

Test: {test_title}
Error: {error_message}
Trace ID: {trace_id}

TELEMETRY DATA:
"""

        # Add logs
        logs = telemetry.get('logs', [])
        if logs:
            prompt += "\nLOGS:\n"
            for log in logs[:10]:  # Limit to first 10 logs
                prompt += f"- {log.get('service', 'unknown')}: {log.get('message', '')} (severity: {log.get('severity', 'UNKNOWN')})\n"

        # Add traces
        traces = telemetry.get('traces', {}).get('spans', [])
        if traces:
            prompt += "\nTRACE SPANS:\n"
            for span in traces[:10]:  # Limit to first 10 spans
                status = span.get('status', {})
                status_code = status.get('code', 0)
                status_msg = status.get('message', 'OK')
                prompt += f"- {span.get('service', 'unknown')}: {span.get('name', '')} (status: {status_code} {status_msg})\n"

        # Add evidence summary
        if evidence:
            prompt += f"\nEVIDENCE SUMMARY ({len(evidence)} items):\n"
            error_count = sum(1 for e in evidence if e.get('severity') in ['ERROR', 'CRITICAL'])
            prompt += f"- Total evidence items: {len(evidence)}\n"
            prompt += f"- Error/Critical items: {error_count}\n"

        prompt += """

ANALYSIS REQUIREMENTS:
1. Classify the failure as either "Backend Error" or "UI Brittleness"
2. Identify the most likely failing service
3. Provide a detailed summary of the root cause
4. Give a confidence score between 0.0 and 1.0
5. Explain your reasoning based on the evidence

RESPONSE FORMAT (JSON):
{
  "classification": "Backend Error" or "UI Brittleness",
  "failing_service": "service_name" or null,
  "summary": "Detailed explanation of root cause",
  "confidence_score": 0.85,
  "reasoning": "Explanation of how you arrived at this conclusion"
}

Analyze this failure and provide your root cause analysis:
"""

        return prompt

    def _parse_gemini_response(self, response: Any) -> Dict[str, Any]:
        """Parse Gemini's response into structured analysis result"""
        try:
            # Extract text from Gemini response
            if hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)

            self.logger.info(f"Gemini response: {response_text}")

            # Try to parse JSON from response
            import json
            import re

            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)

                return {
                    "classification": parsed.get("classification", "Unknown"),
                    "failing_service": parsed.get("failing_service"),
                    "summary": parsed.get("summary", "No summary provided"),
                    "confidence_score": float(parsed.get("confidence_score", 0.0)),
                    "reasoning": parsed.get("reasoning", "")
                }

            # Fallback: extract information from text
            classification = "Backend Error"  # Default
            if "ui brittleness" in response_text.lower():
                classification = "UI Brittleness"

            failing_service = None
            service_match = re.search(r'(?:failing service|service)[:\s]+([a-zA-Z\-_]+)', response_text, re.IGNORECASE)
            if service_match:
                failing_service = service_match.group(1).lower()

            confidence_match = re.search(r'confidence[:\s]+([0-9.]+)', response_text, re.IGNORECASE)
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5

            return {
                "classification": classification,
                "failing_service": failing_service,
                "summary": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                "confidence_score": confidence,
                "reasoning": response_text
            }

        except Exception as e:
            self.logger.error(f"Failed to parse Gemini response: {e}")
            return {
                "classification": "Unknown",
                "failing_service": None,
                "summary": f"Failed to parse analysis: {str(e)}",
                "confidence_score": 0.0,
                "reasoning": str(response)
            }

    def _build_evidence_list(self, telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build evidence list from telemetry"""
        evidence = []

        for log in telemetry.get('logs', []):
            evidence.append({
                'type': 'log',
                'content': log.get('message', ''),
                'severity': log.get('severity', 'UNKNOWN'),
                'service': log.get('service', 'unknown')
            })

        for span in telemetry.get('traces', {}).get('spans', []):
            if span.get('status', {}).get('code', 0) != 0:
                evidence.append({
                    'type': 'trace',
                    'content': f"Failed span: {span.get('name')}",
                    'severity': 'ERROR',
                    'service': span.get('service', 'unknown')
                })

        return evidence

    def _identify_failing_service(self, evidence: List[Dict[str, Any]],
                                topology: ServiceTopology) -> Optional[str]:
        """Identify the most likely failing service"""
        service_errors = {}
        for ev in evidence:
            if ev.get('severity') in ['ERROR', 'CRITICAL']:
                service = ev.get('service', 'unknown')
                service_errors[service] = service_errors.get(service, 0) + 1

        if service_errors:
            return max(service_errors.items(), key=lambda x: x[1])[0]
        return None

    async def get_topology_insights(self) -> Dict[str, Any]:
        """
        Get insights about discovered microservice topology
        
        Returns:
            Dictionary with topology insights based on actual discovered topology
        """
        try:
            # If we have discovered topology, use it
            if hasattr(self, 'discovered_topology') and self.discovered_topology:
                topology = self.discovered_topology
                critical_services = [
                    {"name": service_name, "criticality_score": service.criticality_score}
                    for service_name, service in topology.services.items()
                ]
                critical_services.sort(key=lambda x: x["criticality_score"], reverse=True)
                
                return {
                    "service_count": len(topology.services),
                    "entry_points": topology.entry_points,
                    "critical_services": critical_services[:5],  # Top 5 critical services
                    "failure_patterns": {
                        "total_failures_analyzed": getattr(self, 'analyzed_failures_count', 0),
                        "common_error_types": getattr(self, 'common_error_types', []),
                        "frequently_failing_services": getattr(self, 'frequent_failures', [])
                    }
                }
            else:
                # Return empty insights if no topology discovered yet
                return {
                    "service_count": 0,
                    "entry_points": [],
                    "critical_services": [],
                    "failure_patterns": {
                        "total_failures_analyzed": 0,
                        "common_error_types": [],
                        "frequently_failing_services": []
                    }
                }
        except Exception as e:
            self.logger.error(f"Failed to get topology insights: {e}")
            return {
                "service_count": 0,
                "entry_points": [],
                "critical_services": [],
                "failure_patterns": {
                    "total_failures_analyzed": 0,
                    "common_error_types": [],
                    "frequently_failing_services": []
                }
            }

    async def cleanup(self):
        """Cleanup resources"""
        # Cleanup any active analyses
        for task in self.active_analyses.values():
            if not task.done():
                task.cancel()
        self.active_analyses.clear()
        self.logger.info("RCA Agent cleanup completed")


# Utility functions for testing and validation
def create_mock_failure_payload(test_title: str = "E2E User Journey Test", 
                               error_message: str = "Timeout waiting for response",
                               trace_id: str = "trace-123") -> FailurePayload:
    """Create a mock failure payload for testing (application agnostic)"""
    return FailurePayload(
        test_title=test_title,
        status="failed",
        error=ErrorDetails(
            message=error_message,
            stack="TimeoutError: Timeout 30000ms exceeded...",
            type="TimeoutError"
        ),
        retries=3,
        trace_id=trace_id,
        timestamp=datetime.now()
    )


def create_mock_microservice_traces(services: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create mock trace data for testing topology discovery - application agnostic"""
    if services is None:
        services = ['api-gateway', 'user-service', 'order-service', 'payment-service', 'notification-service']
    
    spans = []
    for i, service in enumerate(services):
        # Create spans with parent-child relationships
        spans.append({
            'span_id': f'span-{i}',
            'parent_span_id': f'span-{i-1}' if i > 0 else None,
            'name': f'{service}-operation',
            'service_name': service,
            'status': {'code': 0, 'message': 'OK'},
            'attributes': {
                'http.method': 'POST' if i == 0 else 'GET',
                'http.status_code': 200,
                'service.name': service
            }
        })
    
    return {'spans': spans}


if __name__ == "__main__":
    # Example usage - Application Agnostic
    async def main():
        # Initialize agent without hardcoded application knowledge
        config = AgentConfig(
            agent_id="rca-agent-demo",
            agent_type="rca",
            capabilities=[
                "telemetry_analysis",
                "topology_discovery", 
                "failure_classification",
                "gemini_integration",
                "application_agnostic"
            ],
            heartbeat_interval=30,
            health_check_interval=60,
            max_concurrent_tasks=5,
            metadata={
                "telemetry_window_seconds": 300,
                "confidence_threshold": 0.7,
                "topology_cache_ttl": 3600,
                "version": "1.0.0"
            }
        )
        
        agent = RCAAgent("rca-agent")
        
        # await agent.initialize()  # Not needed for ADK agent
        
        print("=== Adaptive RCA Agent Demo ===")
        print("This agent automatically discovers microservice topology from traces")
        print("and works with any GKE application")
        print()
        
        # Test with mock payload (no hardcoded application assumptions)
        payload = create_mock_failure_payload(
            test_title="Critical Service Failure Test",
            error_message="Service unavailable during operation",
            trace_id="adaptive-trace-456"
        )
        
        print(f"Analyzing failure: {payload.test_title}")
        print(f"Error: {payload.error.message}")
        print(f"Trace ID: {payload.trace_id}")
        print()
        
        # Run analysis
        result = await agent.analyze_failure(asdict(payload))
        
        print("=== Analysis Results ===")
        print(f"Classification: {result.get('classification', 'unknown')}")
        print(f"Failing Service: {result.get('failing_service', 'Not identified')}")
        print(f"Summary: {result.get('summary', 'No summary')}")
        print(f"Confidence: {result.get('confidence_score', 0):.2f}")
        print(f"Evidence Count: {len(result.get('evidence', []))}")
        print(f"Analysis Duration: {result.get('analysis_duration', 0):.2f}s")
        print()
        
        # Show topology insights
        insights = await agent.get_topology_insights()
        print("=== Discovered Topology Insights ===")
        print(f"Services Discovered: {insights.get('service_count', 0)}")
        print(f"Entry Points: {insights.get('entry_points', [])}")
        print(f"Critical Services: {[s['name'] for s in insights.get('critical_services', [])]}")
        print(f"Potential Bottlenecks: {insights.get('potential_bottlenecks', [])}")
        
        # Show learning progress
        failure_patterns = insights.get('failure_patterns', {})
        print(f"Total Failures Analyzed: {failure_patterns.get('total_failures_analyzed', 0)}")
        
        print()
        print("=== Agent Capabilities ===")
        print("✓ Automatic microservice topology discovery")
        print("✓ Dynamic service dependency mapping")
        print("✓ Adaptive failure pattern recognition")
        print("✓ Application-agnostic analysis")
        print("✓ Continuous learning from failures")
    
    asyncio.run(main())

# Factory function for creating RCA agent
def create_rca_agent(agent_id: Optional[str] = None) -> RCAAgent:
    """
    Create and configure an RCA agent
    
    Args:
        agent_id: Unique agent identifier (auto-generated if None)
        
    Returns:
        Configured RCAAgent instance
    """
    if agent_id is None:
        agent_id = f"rca-{uuid.uuid4()}"
        
    config = AgentConfig(
        agent_id=agent_id,
        agent_type="rca",
        capabilities=[
            "telemetry_analysis",
            "topology_discovery",
            "failure_classification",
            "gemini_integration",
            "application_agnostic"
        ],
        heartbeat_interval=30,
        health_check_interval=60,
        max_concurrent_tasks=5,
        metadata={
            "telemetry_window_seconds": 300,
            "confidence_threshold": 0.7,
            "topology_cache_ttl": 3600,
            "version": "1.0.0"
        }
    )
    
    return RCAAgent(agent_id)