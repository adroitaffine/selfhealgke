"""
Audit Agent - Compliance Tracking and Audit Trail Management

This agent maintains comprehensive audit trails for all Auto-Heal Agent operations,
ensuring compliance with security and operational requirements.

Key capabilities:
- Structured logging with incident correlation
- Compliance reporting and audit trail generation
- Security event tracking and analysis
- Regulatory compliance validation
- Audit data retention and archival
- Real-time audit event processing
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import uuid

from dotenv import load_dotenv
load_dotenv()

# ADK imports - with fallback
try:
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini
    from google.adk.tools import FunctionTool, MCPToolset
    from google.adk import Runner
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    LlmAgent = object
    Gemini = object
    FunctionTool = object
    MCPToolset = object
    Runner = object

# A2A imports
from a2a.client import Client, ClientConfig
from a2a.types import Message, TextPart, Role
A2A_AVAILABLE = True

# Direct Gemini import for fallback
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""
    INCIDENT_DETECTED = "incident_detected"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    REMEDIATION_PROPOSED = "remediation_proposed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    REMEDIATION_STARTED = "remediation_started"
    REMEDIATION_COMPLETED = "remediation_completed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    ROLLBACK_EXECUTED = "rollback_executed"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_VIOLATION = "compliance_violation"
    AGENT_ERROR = "agent_error"
    SYSTEM_HEALTH_CHECK = "system_health_check"


class ComplianceFramework(Enum):
    """Supported compliance frameworks"""
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    CUSTOM = "custom"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    severity: AuditSeverity
    
    # Core event data
    incident_id: Optional[str]
    trace_id: Optional[str]
    agent_id: str
    user_id: Optional[str]
    
    # Event details
    event_data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    # Security and compliance
    checksum: str
    compliance_tags: List[str]
    retention_period_days: int
    
    # Correlation
    correlation_id: Optional[str]
    parent_event_id: Optional[str]
    related_event_ids: List[str]


@dataclass
class ComplianceReport:
    """Compliance report for a specific framework"""
    report_id: str
    framework: ComplianceFramework
    report_period_start: datetime
    report_period_end: datetime
    generated_at: datetime
    
    # Report data
    total_events: int
    events_by_type: Dict[str, int]
    security_events: List[AuditEvent]
    compliance_violations: List[AuditEvent]
    
    # Compliance metrics
    compliance_score: float
    violations_count: int
    remediation_success_rate: float
    mean_response_time: float
    
    # Report metadata
    report_data: Dict[str, Any]
    recommendations: List[str]


@dataclass
class AuditTrail:
    """Complete audit trail for an incident"""
    incident_id: str
    trace_id: str
    created_at: datetime
    updated_at: datetime
    
    # Timeline of events
    events: List[AuditEvent]
    timeline: List[Dict[str, Any]]
    
    # Summary data
    total_duration: float
    events_count: int
    agents_involved: List[str]
    users_involved: List[str]
    
    # Compliance status
    compliance_status: Dict[str, bool]
    violations: List[str]


class AuditStorage:
    """Handles audit data storage and retrieval"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.storage_backend = config.get('storage_backend', 'local')
        self.retention_policy = config.get('retention_policy', {})
        
    async def store_event(self, event: AuditEvent) -> bool:
        """Store an audit event"""
        try:
            # Calculate checksum for integrity
            event.checksum = self._calculate_checksum(event)
            
            # Store based on backend type
            if self.storage_backend == 'local':
                return await self._store_local(event)
            elif self.storage_backend == 'gcs':
                return await self._store_gcs(event)
            elif self.storage_backend == 'bigquery':
                return await self._store_bigquery(event)
            else:
                logger.error(f"Unsupported storage backend: {self.storage_backend}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to store audit event {event.event_id}: {str(e)}")
            return False
    
    async def retrieve_events(self, 
                            incident_id: Optional[str] = None,
                            trace_id: Optional[str] = None,
                            event_type: Optional[AuditEventType] = None,
                            start_time: Optional[datetime] = None,
                            end_time: Optional[datetime] = None,
                            limit: int = 1000) -> List[AuditEvent]:
        """Retrieve audit events based on criteria"""
        try:
            if self.storage_backend == 'local':
                return await self._retrieve_local(incident_id, trace_id, event_type, start_time, end_time, limit)
            elif self.storage_backend == 'gcs':
                return await self._retrieve_gcs(incident_id, trace_id, event_type, start_time, end_time, limit)
            elif self.storage_backend == 'bigquery':
                return await self._retrieve_bigquery(incident_id, trace_id, event_type, start_time, end_time, limit)
            else:
                logger.error(f"Unsupported storage backend: {self.storage_backend}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to retrieve audit events: {str(e)}")
            return []
    
    def _calculate_checksum(self, event: AuditEvent) -> str:
        """Calculate SHA-256 checksum for event integrity"""
        # Create a deterministic string representation
        event_str = json.dumps({
            'event_id': event.event_id,
            'event_type': event.event_type.value,
            'timestamp': event.timestamp.isoformat(),
            'incident_id': event.incident_id,
            'trace_id': event.trace_id,
            'agent_id': event.agent_id,
            'event_data': event.event_data
        }, sort_keys=True)
        
        return hashlib.sha256(event_str.encode()).hexdigest()
    
    async def _store_local(self, event: AuditEvent) -> bool:
        """Store event locally (for development/testing)"""
        # TODO: Implement local file storage
        logger.debug(f"Storing event locally: {event.event_id}")
        return True
    
    async def _store_gcs(self, event: AuditEvent) -> bool:
        """Store event in Google Cloud Storage"""
        # TODO: Implement GCS storage via MCP
        logger.debug(f"Storing event in GCS: {event.event_id}")
        return True
    
    async def _store_bigquery(self, event: AuditEvent) -> bool:
        """Store event in BigQuery"""
        # TODO: Implement BigQuery storage via MCP
        logger.debug(f"Storing event in BigQuery: {event.event_id}")
        return True
    
    async def _retrieve_local(self, incident_id, trace_id, event_type, start_time, end_time, limit) -> List[AuditEvent]:
        """Retrieve events from local storage"""
        # TODO: Implement local retrieval
        return []
    
    async def _retrieve_gcs(self, incident_id, trace_id, event_type, start_time, end_time, limit) -> List[AuditEvent]:
        """Retrieve events from GCS"""
        # TODO: Implement GCS retrieval
        return []
    
    async def _retrieve_bigquery(self, incident_id, trace_id, event_type, start_time, end_time, limit) -> List[AuditEvent]:
        """Retrieve events from BigQuery"""
        # TODO: Implement BigQuery retrieval
        return []


class ComplianceEngine:
    """Handles compliance validation and reporting"""
    
    def __init__(self, frameworks: List[ComplianceFramework]):
        self.frameworks = frameworks
        self.compliance_rules = self._load_compliance_rules()
        
    def _load_compliance_rules(self) -> Dict[ComplianceFramework, Dict[str, Any]]:
        """Load compliance rules for each framework"""
        return {
            ComplianceFramework.SOC2: {
                'required_events': [
                    AuditEventType.APPROVAL_REQUESTED,
                    AuditEventType.APPROVAL_RECEIVED,
                    AuditEventType.REMEDIATION_STARTED,
                    AuditEventType.REMEDIATION_COMPLETED
                ],
                'retention_days': 2555,  # 7 years
                'encryption_required': True,
                'access_controls': True,
                'audit_trail_completeness': 100
            },
            
            ComplianceFramework.ISO27001: {
                'required_events': [
                    AuditEventType.SECURITY_EVENT,
                    AuditEventType.INCIDENT_DETECTED,
                    AuditEventType.REMEDIATION_COMPLETED
                ],
                'retention_days': 2190,  # 6 years
                'encryption_required': True,
                'access_controls': True,
                'incident_response_time_max': 3600  # 1 hour
            },
            
            ComplianceFramework.PCI_DSS: {
                'required_events': [
                    AuditEventType.SECURITY_EVENT,
                    AuditEventType.COMPLIANCE_VIOLATION,
                    AuditEventType.REMEDIATION_COMPLETED
                ],
                'retention_days': 365,  # 1 year minimum
                'encryption_required': True,
                'access_controls': True,
                'log_integrity_checks': True
            }
        }
    
    async def validate_compliance(self, events: List[AuditEvent], 
                                framework: ComplianceFramework) -> Dict[str, Any]:
        """Validate events against compliance framework"""
        rules = self.compliance_rules.get(framework, {})
        violations = []
        compliance_score = 100.0
        
        # Check required events
        required_events = rules.get('required_events', [])
        event_types_present = {event.event_type for event in events}
        
        for required_event in required_events:
            if required_event not in event_types_present:
                violations.append(f"Missing required event type: {required_event.value}")
                compliance_score -= 10
        
        # Check retention compliance
        retention_days = rules.get('retention_days', 365)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for event in events:
            if event.timestamp < cutoff_date and not self._is_archived(event):
                violations.append(f"Event {event.event_id} exceeds retention period")
                compliance_score -= 5
        
        # Check encryption compliance
        if rules.get('encryption_required', False):
            for event in events:
                if not self._is_encrypted(event):
                    violations.append(f"Event {event.event_id} not properly encrypted")
                    compliance_score -= 15
        
        # Check response time compliance
        max_response_time = rules.get('incident_response_time_max')
        if max_response_time:
            response_time_violations = self._check_response_times(events, max_response_time)
            violations.extend(response_time_violations)
            compliance_score -= len(response_time_violations) * 5
        
        return {
            'framework': framework.value,
            'compliance_score': max(0, compliance_score),
            'violations': violations,
            'total_events_checked': len(events),
            'compliant': len(violations) == 0
        }
    
    def _is_archived(self, event: AuditEvent) -> bool:
        """Check if event is properly archived"""
        # TODO: Implement archival status check
        return False
    
    def _is_encrypted(self, event: AuditEvent) -> bool:
        """Check if event data is encrypted"""
        # TODO: Implement encryption check
        return True  # Assume encrypted for now
    
    def _check_response_times(self, events: List[AuditEvent], max_time: int) -> List[str]:
        """Check incident response times"""
        violations = []
        
        # Group events by incident
        incidents = {}
        for event in events:
            if event.incident_id:
                if event.incident_id not in incidents:
                    incidents[event.incident_id] = []
                incidents[event.incident_id].append(event)
        
        # Check response times for each incident
        for incident_id, incident_events in incidents.items():
            incident_events.sort(key=lambda e: e.timestamp)
            
            detection_time = None
            response_time = None
            
            for event in incident_events:
                if event.event_type == AuditEventType.INCIDENT_DETECTED:
                    detection_time = event.timestamp
                elif event.event_type == AuditEventType.REMEDIATION_STARTED and detection_time:
                    response_time = event.timestamp
                    break
            
            if detection_time and response_time:
                response_duration = (response_time - detection_time).total_seconds()
                if response_duration > max_time:
                    violations.append(
                        f"Incident {incident_id} response time {response_duration}s exceeds limit {max_time}s"
                    )
        
        return violations


class AuditAgentADK:
    """ADK-based Audit Agent with MCP integration"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.audit_agent = AuditAgent(config)

        # Initialize ADK components if available
        if ADK_AVAILABLE:
            try:
                # Try to initialize ADK agent - API may vary
                self.llm = Gemini()
                self.agent = LlmAgent()
            except Exception as e:
                logger.warning(f"Failed to initialize ADK LlmAgent: {e}")
                self.agent = None
        else:
            self.agent = None

        # Initialize A2A client
        if A2A_AVAILABLE:
            self.a2a_client = Client(ClientConfig())
        else:
            self.a2a_client = None

        # MCP server connection
        self.mcp_server = None

    def _get_agent_instructions(self) -> str:
        return """
        You are an Audit Agent responsible for maintaining comprehensive audit trails and ensuring compliance.

        Your responsibilities:
        1. Log all security and operational events
        2. Maintain audit trails for incident response
        3. Validate compliance with security frameworks (SOC2, ISO27001, PCI DSS)
        4. Generate compliance reports
        5. Monitor for compliance violations
        6. Ensure data retention policies are followed

        Always log events with appropriate severity levels and ensure all required metadata is captured.
        """

    def _get_mcp_tools(self) -> list:
        """Get MCP tools for audit operations"""
        if not ADK_AVAILABLE:
            return []

        tools = []

        # Audit logging tool
        async def log_audit_event(event_type: str, event_data: Dict[str, Any],
                                incident_id: Optional[str] = None) -> str:
            """Log an audit event"""
            try:
                event_type_enum = AuditEventType(event_type)
                event_id = await self.audit_agent.log_event(
                    event_type_enum,
                    event_data,
                    incident_id=incident_id
                )
                return f"Event logged with ID: {event_id}"
            except Exception as e:
                return f"Failed to log event: {str(e)}"

        if hasattr(FunctionTool, 'from_function'):
            tools.append(FunctionTool.from_function(log_audit_event))

        # Compliance check tool
        async def check_compliance(framework: str, incident_id: Optional[str] = None) -> Dict[str, Any]:
            """Check compliance for a specific framework"""
            try:
                framework_enum = ComplianceFramework(framework.lower())
                events = await self.audit_agent.storage.retrieve_events(incident_id=incident_id)
                result = await self.audit_agent.compliance_engine.validate_compliance(events, framework_enum)
                return result
            except Exception as e:
                return {"error": str(e)}

        if hasattr(FunctionTool, 'from_function'):
            tools.append(FunctionTool.from_function(check_compliance))

        # Generate compliance report tool
        async def generate_compliance_report(framework: str, days: int = 30) -> Dict[str, Any]:
            """Generate compliance report for specified period"""
            try:
                framework_enum = ComplianceFramework(framework.lower())
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)

                report = await self.audit_agent.generate_compliance_report(
                    framework_enum, start_date, end_date
                )
                return asdict(report)
            except Exception as e:
                return {"error": str(e)}

        if hasattr(FunctionTool, 'from_function'):
            tools.append(FunctionTool.from_function(generate_compliance_report))

        return tools

    async def initialize(self):
        """Initialize the ADK agent and MCP connections"""
        await self.audit_agent.initialize()

        if self.agent:
            # Initialize MCP toolset if MCP server is available
            try:
                # TODO: Initialize MCP server connection
                # self.mcp_server = await MCPToolset.connect("gcp_observability_server")
                pass
            except Exception as e:
                logger.warning(f"Failed to initialize MCP connection: {e}")

    async def log_event_adk(self, event_type: str, event_data: Dict[str, Any],
                           incident_id: Optional[str] = None) -> str:
        """Log event using ADK agent"""
        if not self.agent:
            # Fallback to direct logging
            return await self.audit_agent.log_event(
                AuditEventType(event_type),
                event_data,
                incident_id=incident_id
            )

        try:
            # Use ADK agent to process and log the event
            prompt = f"""
            Log the following audit event:
            Type: {event_type}
            Data: {json.dumps(event_data)}
            Incident ID: {incident_id or 'None'}

            Ensure proper compliance tagging and severity assessment.
            """

            response = await self.agent.run(prompt)
            return f"Event processed: {response.content}"
        except Exception as e:
            logger.error(f"ADK event logging failed: {e}")
            # Fallback to direct logging
            return await self.audit_agent.log_event(
                AuditEventType(event_type),
                event_data,
                incident_id=incident_id
            )

    async def analyze_compliance_adk(self, framework: str, incident_id: Optional[str] = None) -> Dict[str, Any]:
        """Analyze compliance using ADK agent"""
        if not self.agent:
            # Fallback to direct compliance check
            framework_enum = ComplianceFramework(framework.lower())
            events = await self.audit_agent.storage.retrieve_events(incident_id=incident_id)
            return await self.audit_agent.compliance_engine.validate_compliance(events, framework_enum)

        try:
            prompt = f"""
            Analyze compliance for framework: {framework}
            Incident ID: {incident_id or 'All incidents'}

            Provide detailed compliance assessment including:
            - Compliance score
            - Identified violations
            - Recommendations for improvement
            """

            response = await self.agent.run(prompt)
            return {"analysis": response.content}
        except Exception as e:
            logger.error(f"ADK compliance analysis failed: {e}")
            # Fallback
            framework_enum = ComplianceFramework(framework.lower())
            events = await self.audit_agent.storage.retrieve_events(incident_id=incident_id)
            return await self.audit_agent.compliance_engine.validate_compliance(events, framework_enum)


class AuditAgentA2AService:
    """A2A REST service for Audit Agent"""

    def __init__(self, audit_agent: AuditAgentADK):
        self.audit_agent = audit_agent
        self.app = None

        if A2A_AVAILABLE:
            from a2a.server import Server, ServerConfig
            from a2a.types import Message, TextPart, Role

            self.server = Server(ServerConfig())
            self._setup_routes()
        else:
            self.server = None

    def _setup_routes(self):
        """Setup A2A routes"""
        if not self.server:
            return

        @self.server.app.post("/log_event")
        async def log_event(request_data: Dict[str, Any]):
            """Log an audit event via REST"""
            try:
                event_id = await self.audit_agent.log_event_adk(
                    request_data["event_type"],
                    request_data["event_data"],
                    request_data.get("incident_id")
                )
                return {"status": "success", "event_id": event_id}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @self.server.app.post("/check_compliance")
        async def check_compliance(request_data: Dict[str, Any]):
            """Check compliance via REST"""
            try:
                result = await self.audit_agent.analyze_compliance_adk(
                    request_data["framework"],
                    request_data.get("incident_id")
                )
                return {"status": "success", "result": result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @self.server.app.get("/audit_trail/{incident_id}")
        async def get_audit_trail(incident_id: str):
            """Get audit trail via REST"""
            try:
                trail = await self.audit_agent.audit_agent.get_audit_trail(incident_id)
                if trail:
                    return {"status": "success", "trail": asdict(trail)}
                else:
                    return {"status": "not_found", "message": "Audit trail not found"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def start_service(self, host: str = "0.0.0.0", port: int = 8003):
        """Start the A2A service"""
        if self.server:
            logger.info(f"Starting Audit Agent A2A service on {host}:{port}")
            await self.server.start(host, port)
        else:
            logger.error("A2A service not available")


# Update the main AuditAgent class to use ADK patterns
class AuditAgent:
    """
    Audit Agent for Compliance Tracking and Audit Trail Management

    Maintains comprehensive audit trails for all Auto-Heal Agent operations,
    ensuring compliance with security and operational requirements.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize Audit Agent"""
        self.config = config or {}
        self.mcp_server = None  # Will be initialized with actual MCP server

        # Initialize components
        self.storage = AuditStorage(self.config.get('storage', {}))
        self.compliance_engine = ComplianceEngine(
            [ComplianceFramework(f) for f in self.config.get('compliance_frameworks', ['soc2'])]
        )

        # Initialize Gemini client directly (similar to RCA agent)
        self.gemini_model = None
        if GENAI_AVAILABLE:
            try:
                import os
                import google.generativeai as genai
                genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')  # Use available model
                logger.info("Initialized direct Gemini client for audit agent")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")
        else:
            logger.warning("Gemini not available, audit event enhancement will be limited")

        # ADK and A2A components - simplified for now
        self.adk_agent = None
        self.a2a_client = None

        # Configuration
        self.agent_id = "audit_agent"
        self.retention_policy = self.config.get('retention_policy', {})
        self.real_time_processing = self.config.get('real_time_processing', True)

        # Event correlation
        self.active_incidents = {}  # incident_id -> AuditTrail
        self.event_correlations = {}  # correlation_id -> List[event_id]

        logger.info("Audit Agent initialized with compliance tracking")

    async def initialize(self):
        """Initialize MCP connections and ADK components"""
        # Initialize ADK agent if available
        if ADK_AVAILABLE:
            try:
                # Try to initialize ADK agent - simplified
                self.adk_agent = AuditAgentADK(self.config)
            except Exception as e:
                logger.warning(f"Failed to initialize ADK components: {e}")
                self.adk_agent = None

        # Initialize A2A client if available
        if A2A_AVAILABLE:
            try:
                from a2a.client import Client, ClientConfig
                self.a2a_client = Client(ClientConfig())
            except Exception as e:
                logger.warning(f"Failed to initialize A2A client: {e}")
                self.a2a_client = None

        # Initialize MCP server connection
        try:
            # TODO: Initialize actual MCP server connection
            # self.mcp_server = MCPServer()
            # await self.mcp_server.connect()
            pass
        except Exception as e:
            logger.warning(f"Failed to initialize MCP connection: {e}")

        logger.info("Audit Agent MCP connections initialized")
    
    async def log_event(self, 
                       event_type: AuditEventType,
                       event_data: Dict[str, Any],
                       incident_id: Optional[str] = None,
                       trace_id: Optional[str] = None,
                       agent_id: Optional[str] = None,
                       user_id: Optional[str] = None,
                       severity: AuditSeverity = AuditSeverity.MEDIUM,
                       correlation_id: Optional[str] = None) -> str:
        """
        Log an audit event
        
        Args:
            event_type: Type of audit event
            event_data: Event-specific data
            incident_id: Associated incident ID
            trace_id: Distributed trace ID
            agent_id: ID of the agent generating the event
            user_id: ID of the user (if applicable)
            severity: Event severity level
            correlation_id: Correlation ID for related events
            
        Returns:
            Event ID of the logged event
        """
        # Use ADK agent if available for enhanced processing
        if self.adk_agent:
            try:
                enhanced_data = await self._enhance_event_with_adk(event_type, event_data)
                event_data.update(enhanced_data)
            except Exception as e:
                logger.warning(f"ADK event enhancement failed: {e}")

        event_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # Determine compliance tags
        compliance_tags = self._determine_compliance_tags(event_type, event_data)
        
        # Determine retention period
        retention_period = self._determine_retention_period(event_type, compliance_tags)
        
        # Create audit event
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            severity=severity,
            incident_id=incident_id,
            trace_id=trace_id,
            agent_id=agent_id or "unknown",
            user_id=user_id,
            event_data=event_data,
            metadata={
                'source': 'audit_agent',
                'version': '1.0',
                'environment': self.config.get('environment', 'development')
            },
            checksum="",  # Will be calculated during storage
            compliance_tags=compliance_tags,
            retention_period_days=retention_period,
            correlation_id=correlation_id,
            parent_event_id=None,
            related_event_ids=[]
        )
        
        # Store the event
        success = await self.storage.store_event(event)
        
        if success:
            # Update incident trail if applicable
            if incident_id:
                await self._update_incident_trail(incident_id, event)
            
            # Process correlations
            if correlation_id:
                await self._process_correlation(correlation_id, event_id)
            
            # Real-time compliance checking
            if self.real_time_processing:
                await self._check_real_time_compliance(event)
            
            # Send A2A notification if client available
            if self.a2a_client and incident_id:
                await self._send_a2a_notification(event)
            
            logger.info(f"Audit event logged: {event_id} ({event_type.value})")
        else:
            logger.error(f"Failed to store audit event: {event_id}")
        
        return event_id
    
    async def _enhance_event_with_adk(self, event_type: AuditEventType, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance event data using ADK agent or direct Gemini"""
        # Try ADK first
        if self.adk_agent and self.adk_agent.agent:
            try:
                prompt = f"""
                Analyze this audit event and provide additional context:
                Event Type: {event_type.value}
                Event Data: {json.dumps(event_data)}
                
                Provide:
                1. Risk assessment (low/medium/high/critical)
                2. Additional compliance tags
                3. Any security implications
                4. Suggested follow-up actions
                
                Return as JSON.
                """
                
                if hasattr(self.adk_agent.agent, 'run') and callable(getattr(self.adk_agent.agent, 'run')):
                    response = await self.adk_agent.agent.run(prompt)
                    # Parse JSON response
                    try:
                        enhanced = json.loads(response.content)
                        return enhanced
                    except:
                        pass
            except Exception as e:
                logger.warning(f"ADK event enhancement failed: {e}")
        
        # Fallback to direct Gemini (use pre-initialized client)
        if self.gemini_model:
            try:
                prompt = f"""
                Analyze this audit event and provide additional context:
                Event Type: {event_type.value}
                Event Data: {json.dumps(event_data)}
                
                Provide a JSON response with:
                1. risk_assessment (low/medium/high/critical)
                2. additional_compliance_tags (array)
                3. security_implications (string)
                4. suggested_actions (array)
                """
                
                response = await self.gemini_model.generate_content_async(prompt)
                # Parse JSON response
                try:
                    enhanced = json.loads(response.text)
                    return enhanced
                except:
                    return {}
            except Exception as e:
                logger.warning(f"Direct Gemini enhancement failed: {e}")
        
        return {}
    
    async def _send_a2a_notification(self, event: AuditEvent):
        """Send A2A notification for the event"""
        if not self.a2a_client:
            return
        
        try:
            message = {
                "type": "audit_event_logged",
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "incident_id": event.incident_id,
                "severity": event.severity.value,
                "timestamp": event.timestamp.isoformat(),
                "agent_id": event.agent_id
            }
            
            # Send to other agents (this would need proper A2A routing)
            # await self.a2a_client.send_message("orchestrator_agent", message)
            logger.debug(f"A2A notification sent for event {event.event_id}")
        except Exception as e:
            logger.warning(f"A2A notification failed: {e}")
    
    async def get_audit_trail(self, incident_id: str) -> Optional[AuditTrail]:
        """Get complete audit trail for an incident"""
        if incident_id in self.active_incidents:
            return self.active_incidents[incident_id]
        
        # Retrieve from storage
        events = await self.storage.retrieve_events(incident_id=incident_id)
        
        if not events:
            return None
        
        # Build audit trail
        trail = await self._build_audit_trail(incident_id, events)
        return trail
    
    async def generate_compliance_report(self, 
                                       framework: ComplianceFramework,
                                       start_date: datetime,
                                       end_date: datetime) -> ComplianceReport:
        """Generate compliance report for a specific framework"""
        logger.info(f"Generating compliance report for {framework.value} "
                   f"from {start_date} to {end_date}")
        
        # Retrieve events for the period
        events = await self.storage.retrieve_events(
            start_time=start_date,
            end_time=end_date
        )
        
        # Validate compliance
        compliance_result = await self.compliance_engine.validate_compliance(events, framework)
        
        # Calculate metrics
        metrics = await self._calculate_compliance_metrics(events, framework)
        
        # Generate report
        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            framework=framework,
            report_period_start=start_date,
            report_period_end=end_date,
            generated_at=datetime.now(),
            total_events=len(events),
            events_by_type=self._count_events_by_type(events),
            security_events=[e for e in events if e.event_type == AuditEventType.SECURITY_EVENT],
            compliance_violations=[e for e in events if e.event_type == AuditEventType.COMPLIANCE_VIOLATION],
            compliance_score=compliance_result['compliance_score'],
            violations_count=len(compliance_result['violations']),
            remediation_success_rate=metrics['remediation_success_rate'],
            mean_response_time=metrics['mean_response_time'],
            report_data=compliance_result,
            recommendations=self._generate_recommendations(compliance_result, metrics)
        )
        
        logger.info(f"Compliance report generated: {report.report_id} "
                   f"(score: {report.compliance_score:.1f}%)")
        
        return report
    
    async def search_events(self, 
                          query: Dict[str, Any],
                          limit: int = 100) -> List[AuditEvent]:
        """Search audit events based on query criteria"""
        return await self.storage.retrieve_events(
            incident_id=query.get('incident_id'),
            trace_id=query.get('trace_id'),
            event_type=AuditEventType(query['event_type']) if 'event_type' in query else None,
            start_time=query.get('start_time'),
            end_time=query.get('end_time'),
            limit=limit
        )
    
    async def validate_audit_integrity(self, event_ids: List[str]) -> Dict[str, bool]:
        """Validate integrity of audit events using checksums"""
        results = {}
        
        for event_id in event_ids:
            events = await self.storage.retrieve_events()
            event = next((e for e in events if e.event_id == event_id), None)
            
            if event:
                # Recalculate checksum and compare
                original_checksum = event.checksum
                event.checksum = ""  # Clear for recalculation
                calculated_checksum = self.storage._calculate_checksum(event)
                
                results[event_id] = original_checksum == calculated_checksum
            else:
                results[event_id] = False
        
        return results
    
    def _determine_compliance_tags(self, event_type: AuditEventType, 
                                 event_data: Dict[str, Any]) -> List[str]:
        """Determine compliance tags for an event"""
        tags = []
        
        # SOC2 tags
        if event_type in [AuditEventType.APPROVAL_REQUESTED, AuditEventType.APPROVAL_RECEIVED,
                         AuditEventType.REMEDIATION_STARTED, AuditEventType.REMEDIATION_COMPLETED]:
            tags.append('soc2')
        
        # ISO27001 tags
        if event_type in [AuditEventType.SECURITY_EVENT, AuditEventType.INCIDENT_DETECTED]:
            tags.append('iso27001')
        
        # PCI DSS tags
        if event_type == AuditEventType.SECURITY_EVENT:
            tags.append('pci_dss')
        
        # Security-related tags
        if 'security' in event_data or event_type == AuditEventType.SECURITY_EVENT:
            tags.append('security')
        
        # Privacy-related tags
        if 'pii' in event_data or 'personal_data' in event_data:
            tags.append('privacy')
            tags.append('gdpr')
        
        return tags
    
    def _determine_retention_period(self, event_type: AuditEventType, 
                                  compliance_tags: List[str]) -> int:
        """Determine retention period based on event type and compliance requirements"""
        # Default retention
        retention_days = 365
        
        # Compliance-based retention
        if 'soc2' in compliance_tags:
            retention_days = max(retention_days, 2555)  # 7 years
        
        if 'iso27001' in compliance_tags:
            retention_days = max(retention_days, 2190)  # 6 years
        
        if 'pci_dss' in compliance_tags:
            retention_days = max(retention_days, 365)  # 1 year minimum
        
        if 'gdpr' in compliance_tags:
            retention_days = max(retention_days, 2190)  # 6 years
        
        # Event-type specific retention
        if event_type in [AuditEventType.SECURITY_EVENT, AuditEventType.COMPLIANCE_VIOLATION]:
            retention_days = max(retention_days, 2555)  # 7 years for security events
        
        return retention_days
    
    async def _update_incident_trail(self, incident_id: str, event: AuditEvent):
        """Update the audit trail for an incident"""
        if incident_id not in self.active_incidents:
            # Create new audit trail
            self.active_incidents[incident_id] = AuditTrail(
                incident_id=incident_id,
                trace_id=event.trace_id or "",
                created_at=event.timestamp,
                updated_at=event.timestamp,
                events=[],
                timeline=[],
                total_duration=0.0,
                events_count=0,
                agents_involved=[],
                users_involved=[],
                compliance_status={},
                violations=[]
            )
        
        trail = self.active_incidents[incident_id]
        
        # Add event to trail
        trail.events.append(event)
        trail.events_count += 1
        trail.updated_at = event.timestamp
        
        # Update timeline
        trail.timeline.append({
            'timestamp': event.timestamp.isoformat(),
            'event_type': event.event_type.value,
            'agent_id': event.agent_id,
            'summary': self._generate_event_summary(event)
        })
        
        # Update involved parties
        if event.agent_id and event.agent_id not in trail.agents_involved:
            trail.agents_involved.append(event.agent_id)
        
        if event.user_id and event.user_id not in trail.users_involved:
            trail.users_involved.append(event.user_id)
        
        # Calculate total duration
        if len(trail.events) > 1:
            trail.total_duration = (trail.updated_at - trail.created_at).total_seconds()
    
    async def _process_correlation(self, correlation_id: str, event_id: str):
        """Process event correlation"""
        if correlation_id not in self.event_correlations:
            self.event_correlations[correlation_id] = []
        
        self.event_correlations[correlation_id].append(event_id)
        
        # Update related events for all events in this correlation
        related_events = self.event_correlations[correlation_id]
        
        # TODO: Update related_event_ids in storage for all correlated events
        logger.debug(f"Correlated event {event_id} with {len(related_events)} other events")
    
    async def _check_real_time_compliance(self, event: AuditEvent):
        """Perform real-time compliance checking"""
        # Check for immediate compliance violations
        violations = []
        
        # Check for security events without proper approval
        if (event.event_type == AuditEventType.REMEDIATION_STARTED and 
            not await self._has_prior_approval(event.incident_id)):
            violations.append("Remediation started without proper approval")
        
        # Check for excessive response times
        if event.event_type == AuditEventType.REMEDIATION_STARTED:
            response_time = await self._calculate_response_time(event.incident_id)
            if response_time and response_time > 3600:  # 1 hour
                violations.append(f"Response time {response_time}s exceeds policy limit")
        
        # Log compliance violations
        for violation in violations:
            await self.log_event(
                AuditEventType.COMPLIANCE_VIOLATION,
                {
                    'violation': violation,
                    'original_event_id': event.event_id,
                    'policy': 'real_time_compliance'
                },
                incident_id=event.incident_id,
                trace_id=event.trace_id,
                severity=AuditSeverity.HIGH
            )
    
    async def _has_prior_approval(self, incident_id: Optional[str]) -> bool:
        """Check if incident has prior approval"""
        if not incident_id:
            return False
        
        events = await self.storage.retrieve_events(incident_id=incident_id)
        return any(e.event_type == AuditEventType.APPROVAL_RECEIVED for e in events)
    
    async def _calculate_response_time(self, incident_id: Optional[str]) -> Optional[float]:
        """Calculate response time for an incident"""
        if not incident_id:
            return None
        
        events = await self.storage.retrieve_events(incident_id=incident_id)
        events.sort(key=lambda e: e.timestamp)
        
        detection_time = None
        response_time = None
        
        for event in events:
            if event.event_type == AuditEventType.INCIDENT_DETECTED:
                detection_time = event.timestamp
            elif event.event_type == AuditEventType.REMEDIATION_STARTED and detection_time:
                response_time = event.timestamp
                break
        
        if detection_time and response_time:
            return (response_time - detection_time).total_seconds()
        
        return None
    
    async def log_event_from_dict(self, event_data: Dict[str, Any]) -> str:
        """
        Log an audit event (simplified interface for testing)
        
        Args:
            event_data: Dictionary containing event information
            
        Returns:
            Event ID of the logged event
        """
        event_type = AuditEventType(event_data.get('event_type', 'system_health_check'))
        details = event_data.get('details', {})
        
        return await self.log_event(
            event_type,
            details,
            incident_id=event_data.get('incident_id'),
            trace_id=event_data.get('trace_id'),
            agent_id=event_data.get('agent_id', 'unknown'),
            user_id=event_data.get('user_id'),
            severity=AuditSeverity(event_data.get('severity', 'medium')),
            correlation_id=event_data.get('correlation_id')
        )
    
    async def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a specific audit event by ID"""
        # For testing purposes, return a mock event
        # In real implementation, this would query the storage backend
        return AuditEvent(
            event_id=event_id,
            event_type=AuditEventType.SYSTEM_HEALTH_CHECK,
            timestamp=datetime.now(),
            severity=AuditSeverity.MEDIUM,
            incident_id=None,
            trace_id=None,
            agent_id="test_agent",
            user_id=None,
            event_data={"test": "data"},
            metadata={"source": "audit_agent"},
            checksum="test_checksum",
            compliance_tags=["test"],
            retention_period_days=365,
            correlation_id=None,
            parent_event_id=None,
            related_event_ids=[]
        )

    async def _build_audit_trail(self, incident_id: str, events: List[AuditEvent]) -> Optional[AuditTrail]:
        """Build complete audit trail from events"""
        events.sort(key=lambda e: e.timestamp)
        
        if not events:
            return None
        
        # Build timeline
        timeline = []
        for event in events:
            timeline.append({
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type.value,
                'agent_id': event.agent_id,
                'summary': self._generate_event_summary(event)
            })
        
        # Calculate metrics
        total_duration = (events[-1].timestamp - events[0].timestamp).total_seconds()
        agents_involved = list(set(e.agent_id for e in events if e.agent_id))
        users_involved = list(set(e.user_id for e in events if e.user_id))
        
        # Check compliance status
        compliance_status = {}
        violations = []
        
        for framework in self.compliance_engine.frameworks:
            compliance_result = await self.compliance_engine.validate_compliance(events, framework)
            compliance_status[framework.value] = compliance_result['compliant']
            violations.extend(compliance_result['violations'])
        
        return AuditTrail(
            incident_id=incident_id,
            trace_id=events[0].trace_id or "",
            created_at=events[0].timestamp,
            updated_at=events[-1].timestamp,
            events=events,
            timeline=timeline,
            total_duration=total_duration,
            events_count=len(events),
            agents_involved=agents_involved,
            users_involved=users_involved,
            compliance_status=compliance_status,
            violations=violations
        )
    
    def _generate_event_summary(self, event: AuditEvent) -> str:
        """Generate human-readable summary for an event"""
        summaries = {
            AuditEventType.INCIDENT_DETECTED: "Incident detected from synthetic test failure",
            AuditEventType.ANALYSIS_STARTED: "Root cause analysis initiated",
            AuditEventType.ANALYSIS_COMPLETED: "Analysis completed with classification",
            AuditEventType.REMEDIATION_PROPOSED: "Remediation action proposed",
            AuditEventType.APPROVAL_REQUESTED: "Human approval requested",
            AuditEventType.APPROVAL_RECEIVED: "Approval decision received",
            AuditEventType.REMEDIATION_STARTED: "Remediation execution started",
            AuditEventType.REMEDIATION_COMPLETED: "Remediation completed successfully",
            AuditEventType.VERIFICATION_STARTED: "Verification tests initiated",
            AuditEventType.VERIFICATION_COMPLETED: "Verification completed",
            AuditEventType.ROLLBACK_EXECUTED: "Deployment rollback executed",
            AuditEventType.SECURITY_EVENT: "Security event detected",
            AuditEventType.COMPLIANCE_VIOLATION: "Compliance violation identified",
            AuditEventType.AGENT_ERROR: "Agent error occurred",
            AuditEventType.SYSTEM_HEALTH_CHECK: "System health check performed"
        }
        
        base_summary = summaries.get(event.event_type, f"Event: {event.event_type.value}")
        
        # Add specific details if available
        if event.event_data:
            if 'classification' in event.event_data:
                base_summary += f" - {event.event_data['classification']}"
            elif 'action' in event.event_data:
                base_summary += f" - {event.event_data['action']}"
            elif 'status' in event.event_data:
                base_summary += f" - {event.event_data['status']}"
        
        return base_summary
    
    def _count_events_by_type(self, events: List[AuditEvent]) -> Dict[str, int]:
        """Count events by type"""
        counts = {}
        for event in events:
            event_type = event.event_type.value
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    async def _calculate_compliance_metrics(self, events: List[AuditEvent], 
                                          framework: ComplianceFramework) -> Dict[str, Any]:
        """Calculate compliance metrics"""
        # Calculate remediation success rate
        remediation_started = len([e for e in events if e.event_type == AuditEventType.REMEDIATION_STARTED])
        remediation_completed = len([e for e in events if e.event_type == AuditEventType.REMEDIATION_COMPLETED])
        
        remediation_success_rate = (remediation_completed / remediation_started * 100) if remediation_started > 0 else 0
        
        # Calculate mean response time
        response_times = []
        incidents = {}
        
        # Group events by incident
        for event in events:
            if event.incident_id:
                if event.incident_id not in incidents:
                    incidents[event.incident_id] = []
                incidents[event.incident_id].append(event)
        
        # Calculate response times
        for incident_events in incidents.values():
            incident_events.sort(key=lambda e: e.timestamp)
            
            detection_time = None
            response_time = None
            
            for event in incident_events:
                if event.event_type == AuditEventType.INCIDENT_DETECTED:
                    detection_time = event.timestamp
                elif event.event_type == AuditEventType.REMEDIATION_STARTED and detection_time:
                    response_time = event.timestamp
                    break
            
            if detection_time and response_time:
                response_duration = (response_time - detection_time).total_seconds()
                response_times.append(response_duration)
        
        mean_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'remediation_success_rate': remediation_success_rate,
            'mean_response_time': mean_response_time,
            'total_incidents': len(incidents),
            'response_times': response_times
        }
    
    def _generate_recommendations(self, compliance_result: Dict[str, Any], 
                                metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations based on compliance results and metrics"""
        recommendations = []
        
        # Compliance-based recommendations
        if compliance_result['compliance_score'] < 90:
            recommendations.append("Improve compliance score by addressing identified violations")
        
        if len(compliance_result['violations']) > 0:
            recommendations.append("Review and remediate compliance violations")
        
        # Performance-based recommendations
        if metrics['remediation_success_rate'] < 90:
            recommendations.append("Improve remediation success rate through better testing and validation")
        
        if metrics['mean_response_time'] > 1800:  # 30 minutes
            recommendations.append("Reduce incident response time through automation improvements")
        
        # Security recommendations
        security_events = compliance_result.get('security_events', 0)
        if security_events > 0:
            recommendations.append("Review security events and strengthen security controls")
        
        return recommendations


# A2A Message Handlers for integration with other agents
class AuditAgentA2AHandlers:
    """A2A message handlers for Audit Agent"""
    
    def __init__(self, audit_agent: AuditAgent):
        self.audit_agent = audit_agent
    
    async def handle_log_incident_detected(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incident detection notification"""
        event_id = await self.audit_agent.log_event(
            AuditEventType.INCIDENT_DETECTED,
            message.get('payload', {}),
            incident_id=message.get('incident_id'),
            trace_id=message.get('trace_id'),
            agent_id=message.get('from_agent'),
            severity=AuditSeverity.HIGH
        )
        
        return {'status': 'logged', 'event_id': event_id}
    
    async def handle_log_analysis_result(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis completion notification"""
        payload = message.get('payload', {})
        
        event_id = await self.audit_agent.log_event(
            AuditEventType.ANALYSIS_COMPLETED,
            {
                'classification': payload.get('classification'),
                'failing_service': payload.get('failing_service'),
                'confidence_score': payload.get('confidence_score'),
                'analysis_duration': payload.get('analysis_duration')
            },
            incident_id=message.get('incident_id'),
            trace_id=message.get('trace_id'),
            agent_id=message.get('from_agent'),
            severity=AuditSeverity.MEDIUM
        )
        
        return {'status': 'logged', 'event_id': event_id}
    
    async def handle_log_approval_decision(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle approval decision notification"""
        payload = message.get('payload', {})
        
        event_type = (AuditEventType.APPROVAL_RECEIVED if payload.get('approved') 
                     else AuditEventType.APPROVAL_REQUESTED)
        
        event_id = await self.audit_agent.log_event(
            event_type,
            {
                'decision': payload.get('decision'),
                'user_id': payload.get('user_id'),
                'action_proposed': payload.get('action_proposed'),
                'approval_method': payload.get('approval_method', 'web_interface')
            },
            incident_id=message.get('incident_id'),
            trace_id=message.get('trace_id'),
            agent_id=message.get('from_agent'),
            user_id=payload.get('user_id'),
            severity=AuditSeverity.HIGH
        )
        
        return {'status': 'logged', 'event_id': event_id}
    
    async def handle_log_remediation_complete(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle remediation completion notification"""
        payload = message.get('payload', {})
        
        event_id = await self.audit_agent.log_event(
            AuditEventType.REMEDIATION_COMPLETED,
            {
                'action_id': payload.get('action_id'),
                'success': payload.get('success'),
                'duration': payload.get('duration'),
                'verification_status': payload.get('verification_status'),
                'strategy': payload.get('strategy')
            },
            incident_id=message.get('incident_id'),
            trace_id=message.get('trace_id'),
            agent_id=message.get('from_agent'),
            severity=AuditSeverity.MEDIUM if payload.get('success') else AuditSeverity.HIGH
        )
        
        return {'status': 'logged', 'event_id': event_id}


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def test_audit_agent():
        # Initialize audit agent
        config = {
            'storage': {'storage_backend': 'local'},
            'compliance_frameworks': ['soc2', 'iso27001'],
            'environment': 'development'
        }
        
        agent = AuditAgent(config)
        await agent.initialize()
        
        # Log some test events
        incident_id = "test_incident_001"
        trace_id = "trace_123456"
        
        # Log incident detection
        await agent.log_event_from_dict({
            'event_type': 'incident_detected',
            'details': {
                'test_name': 'checkout_flow_test',
                'error_message': 'Timeout waiting for payment confirmation',
                'service': 'payment-service'
            },
            'incident_id': incident_id,
            'trace_id': trace_id,
            'agent_id': 'rca_agent',
            'severity': 'high'
        })
        
        # Log analysis completion
        await agent.log_event_from_dict({
            'event_type': 'analysis_completed',
            'details': {
                'classification': 'Backend Error',
                'failing_service': 'payment-service',
                'confidence_score': 0.85
            },
            'incident_id': incident_id,
            'trace_id': trace_id,
            'agent_id': 'rca_agent',
            'severity': 'medium'
        })
        
        # Log approval
        await agent.log_event_from_dict({
            'event_type': 'approval_received',
            'details': {
                'decision': 'approved',
                'user_id': 'sre_engineer_1',
                'action_proposed': 'deployment_rollback'
            },
            'incident_id': incident_id,
            'trace_id': trace_id,
            'agent_id': 'approval_agent',
            'user_id': 'sre_engineer_1',
            'severity': 'high'
        })
        
        # Get audit trail
        trail = await agent.get_audit_trail(incident_id)
        if trail:
            print(f"Audit trail for {incident_id}:")
            print(f"  Events: {trail.events_count}")
            print(f"  Duration: {trail.total_duration:.2f}s")
            print(f"  Agents involved: {trail.agents_involved}")
            print(f"  Compliance status: {trail.compliance_status}")
        
        # Generate compliance report
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        report = await agent.generate_compliance_report(
            ComplianceFramework.SOC2,
            start_date,
            end_date
        )
        
        print(f"\nCompliance Report ({report.framework.value}):")
        print(f"  Score: {report.compliance_score:.1f}%")
        print(f"  Total events: {report.total_events}")
        print(f"  Violations: {report.violations_count}")
        print(f"  Success rate: {report.remediation_success_rate:.1f}%")
    
    # Run test
    asyncio.run(test_audit_agent())