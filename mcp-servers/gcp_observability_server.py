#!/usr/bin/env python3
"""
Google Cloud Observability MCP Server

Provides tools for Cloud Logging and Cloud Trace API integration
with authentication and error handling for the GKE Auto-Heal Agent.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.auth import default
from google.cloud import logging as cloud_logging
from google.cloud import trace_v1
from google.oauth2 import service_account
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCPObservabilityServer:
    """MCP Server for Google Cloud Observability APIs"""
    
    def __init__(self):
        self.server = Server("gcp-observability")
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.credentials = None
        self.logging_client = None
        self.trace_client = None
        
        # Initialize clients
        self._initialize_clients()
        
        # Register tools
        self._register_tools()
    
    def _initialize_clients(self):
        """Initialize Google Cloud clients with authentication"""
        try:
            # Always use Application Default Credentials (ADC)
            # This works with both service account files and user credentials
            self.credentials, project = default()
            if not self.project_id:
                self.project_id = project
            logger.info("Using Application Default Credentials")
            
            # Initialize clients
            self.logging_client = cloud_logging.Client(
                project=self.project_id,
                credentials=self.credentials
            )
            
            self.trace_client = trace_v1.TraceServiceClient(
                credentials=self.credentials
            )
            
            logger.info(f"Initialized GCP clients for project: {self.project_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GCP clients: {e}")
            raise
    
    def _register_tools(self):
        """Register MCP tools for observability operations"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available observability tools"""
            return [

                Tool(
                    name="correlate-telemetry",
                    description="Correlate logs and traces for comprehensive analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "trace_id": {
                                "type": "string",
                                "description": "Trace ID for correlation"
                            },
                            "time_window": {
                                "type": "integer",
                                "description": "Time window in seconds (default: 300)",
                                "default": 300
                            }
                        },
                        "required": ["trace_id"]
                    }
                ),
                Tool(
                    name="build-failure-timeline",
                    description="Build chronological timeline of events for failure analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "trace_id": {
                                "type": "string",
                                "description": "Trace ID for timeline analysis"
                            },
                            "time_window": {
                                "type": "integer",
                                "description": "Time window in seconds (default: 600)",
                                "default": 600
                            },
                            "include_related_traces": {
                                "type": "boolean",
                                "description": "Include related traces in timeline",
                                "default": True
                            }
                        },
                        "required": ["trace_id"]
                    }
                ),
                Tool(
                    name="analyze-microservice-patterns",
                    description="Analyze microservice failure patterns specific to Online Boutique",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "trace_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of trace IDs to analyze for patterns"
                            },
                            "time_range": {
                                "type": "object",
                                "properties": {
                                    "start_time": {"type": "string"},
                                    "end_time": {"type": "string"}
                                },
                                "description": "Time range for pattern analysis"
                            },
                            "focus_services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Online Boutique services to focus on",
                                "default": ["frontend", "cartservice", "productcatalogservice", "checkoutservice"]
                            }
                        },
                        "required": ["trace_ids"]
                    }
                ),
                Tool(
                    name="detect-cascade-failures",
                    description="Detect cascade failure patterns across Online Boutique microservices",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "initial_trace_id": {
                                "type": "string",
                                "description": "Initial trace ID where failure started"
                            },
                            "cascade_window": {
                                "type": "integer",
                                "description": "Time window in seconds to look for cascade effects",
                                "default": 300
                            },
                            "severity_threshold": {
                                "type": "string",
                                "description": "Minimum severity to consider",
                                "default": "WARNING"
                            }
                        },
                        "required": ["initial_trace_id"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls for observability operations"""
            try:
                if name == "correlate-telemetry":
                    return await self._correlate_telemetry(arguments)
                elif name == "build-failure-timeline":
                    return await self._build_failure_timeline(arguments)
                elif name == "analyze-microservice-patterns":
                    return await self._analyze_microservice_patterns(arguments)
                elif name == "detect-cascade-failures":
                    return await self._detect_cascade_failures(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "tool": name,
                        "arguments": arguments
                    }, indent=2)
                )]
    
    async def _build_failure_timeline(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Build chronological timeline of events for failure analysis"""
        trace_id = arguments["trace_id"]
        time_window = arguments.get("time_window", 600)
        include_related_traces = arguments.get("include_related_traces", True)
        
        try:
            # Get primary trace data
            traces_result = await self._get_traces({"trace_id": trace_id, "include_spans": True})
            traces_data = json.loads(traces_result[0].text)
            
            # Get logs for the trace
            logs_result = await self._get_logs({"trace_id": trace_id, "time_window": time_window})
            logs_data = json.loads(logs_result[0].text)
            
            # Build comprehensive timeline
            timeline = self._build_comprehensive_timeline(
                logs_data["logs"], 
                traces_data["spans"],
                include_related_traces
            )
            
            # Analyze failure patterns
            failure_analysis = self._analyze_failure_patterns(timeline, traces_data["spans"])
            
            timeline_result = {
                "trace_id": trace_id,
                "timeline": timeline,
                "failure_analysis": failure_analysis,
                "metadata": {
                    "time_window": time_window,
                    "total_events": len(timeline),
                    "span_count": len(traces_data["spans"]),
                    "log_count": len(logs_data["logs"])
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(timeline_result, indent=2, default=str)
            )]
            
        except Exception as e:
            logger.error(f"Error building failure timeline for trace {trace_id}: {e}")
            raise

    async def _get_logs(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get logs by trace ID"""
        trace_id = arguments["trace_id"]
        time_window = arguments.get("time_window", 300)
        severity = arguments.get("severity", "INFO")
        service = arguments.get("service")
        
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(seconds=time_window)
            
            # Build filter
            filter_parts = [
                f'trace="projects/{self.project_id}/traces/{trace_id}"',
                f'timestamp>="{start_time.isoformat()}Z"',
                f'timestamp<="{end_time.isoformat()}Z"',
                f'severity>={severity}'
            ]
            
            if service:
                filter_parts.append(f'resource.labels.service_name="{service}"')
            
            filter_str = " AND ".join(filter_parts)
            
            # Query logs
            entries = list(self.logging_client.list_entries(
                filter_=filter_str,
                order_by=cloud_logging.DESCENDING,
                max_results=100
            ))
            
            # Format results
            log_data = []
            for entry in entries:
                log_entry = {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "severity": entry.severity,
                    "message": str(entry.payload),
                    "resource": {
                        "type": entry.resource.type if entry.resource else None,
                        "labels": dict(entry.resource.labels) if entry.resource else {}
                    },
                    "labels": dict(entry.labels) if entry.labels else {},
                    "trace": entry.trace,
                    "span_id": entry.span_id
                }
                log_data.append(log_entry)
            
            result = {
                "trace_id": trace_id,
                "log_count": len(log_data),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "logs": log_data
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
            
        except Exception as e:
            logger.error(f"Error getting logs for trace {trace_id}: {e}")
            raise
    
    async def _get_traces(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get trace data by trace ID"""
        trace_id = arguments["trace_id"]
        include_spans = arguments.get("include_spans", True)
        
        try:
            # Get trace
            project_name = f"projects/{self.project_id}"
            trace_name = f"{project_name}/traces/{trace_id}"
            
            trace = self.trace_client.get_trace(
                name=trace_name
            )
            
            # Format trace data
            trace_data = {
                "trace_id": trace_id,
                "project_id": trace.project_id,
                "spans": []
            }
            
            if include_spans and trace.spans:
                for span in trace.spans:
                    span_data = {
                        "span_id": span.span_id,
                        "name": span.name,
                        "start_time": span.start_time.isoformat() if span.start_time else None,
                        "end_time": span.end_time.isoformat() if span.end_time else None,
                        "parent_span_id": span.parent_span_id,
                        "labels": dict(span.labels) if span.labels else {}
                    }
                    trace_data["spans"].append(span_data)
            
            return [TextContent(
                type="text",
                text=json.dumps(trace_data, indent=2, default=str)
            )]
            
        except Exception as e:
            logger.error(f"Error getting trace {trace_id}: {e}")
            raise
    
    async def _correlate_telemetry(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Correlate logs and traces for comprehensive analysis"""
        trace_id = arguments["trace_id"]
        time_window = arguments.get("time_window", 300)
        
        try:
            # Get both logs and traces
            logs_result = await self._get_logs({
                "trace_id": trace_id,
                "time_window": time_window
            })
            
            traces_result = await self._get_traces({
                "trace_id": trace_id,
                "include_spans": True
            })
            
            # Parse results
            logs_data = json.loads(logs_result[0].text)
            traces_data = json.loads(traces_result[0].text)
            
            # Correlate data
            correlation = {
                "trace_id": trace_id,
                "correlation_summary": {
                    "total_logs": logs_data["log_count"],
                    "total_spans": len(traces_data["spans"]),
                    "error_logs": len([log for log in logs_data["logs"] 
                                    if log["severity"] in ["ERROR", "CRITICAL"]]),
                    "error_spans": len([span for span in traces_data["spans"]
                                      if any("error" in str(v).lower() 
                                           for v in span["labels"].values())])
                },
                "timeline": self._build_timeline(logs_data["logs"], traces_data["spans"]),
                "error_analysis": self._analyze_errors(logs_data["logs"], traces_data["spans"]),
                "service_map": self._build_service_map(traces_data["spans"]),
                "raw_data": {
                    "logs": logs_data,
                    "traces": traces_data
                }
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(correlation, indent=2, default=str)
            )]
            
        except Exception as e:
            logger.error(f"Error correlating telemetry for trace {trace_id}: {e}")
            raise
    

    
    def _build_timeline(self, logs: List[Dict], spans: List[Dict]) -> List[Dict]:
        """Build chronological timeline of events"""
        events = []
        
        # Add log events
        for log in logs:
            if log["timestamp"]:
                events.append({
                    "timestamp": log["timestamp"],
                    "type": "log",
                    "severity": log["severity"],
                    "message": log["message"][:200] + "..." if len(log["message"]) > 200 else log["message"],
                    "service": log["resource"]["labels"].get("service_name", "unknown")
                })
        
        # Add span events
        for span in spans:
            if span["start_time"]:
                events.append({
                    "timestamp": span["start_time"],
                    "type": "span_start",
                    "span_name": span["name"],
                    "span_id": span["span_id"]
                })
            if span["end_time"]:
                events.append({
                    "timestamp": span["end_time"],
                    "type": "span_end",
                    "span_name": span["name"],
                    "span_id": span["span_id"]
                })
        
        # Sort by timestamp
        events.sort(key=lambda x: x["timestamp"])
        
        return events
    
    def _analyze_errors(self, logs: List[Dict], spans: List[Dict]) -> Dict:
        """Analyze errors in logs and spans"""
        error_analysis = {
            "error_logs": [],
            "error_spans": [],
            "error_patterns": {},
            "affected_services": set()
        }
        
        # Analyze error logs
        for log in logs:
            if log["severity"] in ["ERROR", "CRITICAL"]:
                error_analysis["error_logs"].append({
                    "timestamp": log["timestamp"],
                    "message": log["message"],
                    "service": log["resource"]["labels"].get("service_name", "unknown")
                })
                
                service = log["resource"]["labels"].get("service_name", "unknown")
                error_analysis["affected_services"].add(service)
        
        # Analyze error spans
        for span in spans:
            if any("error" in str(v).lower() for v in span["labels"].values()):
                error_analysis["error_spans"].append({
                    "span_name": span["name"],
                    "span_id": span["span_id"],
                    "labels": span["labels"]
                })
        
        # Convert set to list for JSON serialization
        error_analysis["affected_services"] = list(error_analysis["affected_services"])
        
        return error_analysis
    
    def _build_comprehensive_timeline(self, logs: List[Dict], spans: List[Dict], include_related: bool = True) -> List[Dict]:
        """Build comprehensive chronological timeline with advanced correlation"""
        events = []
        
        # Add log events with enhanced context
        for log in logs:
            if log["timestamp"]:
                event = {
                    "timestamp": log["timestamp"],
                    "type": "log",
                    "severity": log["severity"],
                    "message": log["message"][:300] + "..." if len(log["message"]) > 300 else log["message"],
                    "service": log["resource"]["labels"].get("service_name", "unknown"),
                    "trace_id": log.get("trace"),
                    "span_id": log.get("span_id"),
                    "correlation_id": f"log_{hash(log['message'][:100])}",
                    "is_error": log["severity"] in ["ERROR", "CRITICAL"],
                    "context": {
                        "resource_type": log["resource"].get("type"),
                        "labels": log["labels"]
                    }
                }
                events.append(event)
        
        # Add span events with service correlation
        for span in spans:
            service_name = self._extract_service_name(span["name"])
            
            if span["start_time"]:
                events.append({
                    "timestamp": span["start_time"],
                    "type": "span_start",
                    "span_name": span["name"],
                    "span_id": span["span_id"],
                    "service": service_name,
                    "parent_span_id": span.get("parent_span_id"),
                    "correlation_id": f"span_{span['span_id']}",
                    "is_error": any("error" in str(v).lower() for v in span["labels"].values()),
                    "context": {
                        "labels": span["labels"],
                        "operation": span["name"]
                    }
                })
            
            if span["end_time"]:
                events.append({
                    "timestamp": span["end_time"],
                    "type": "span_end",
                    "span_name": span["name"],
                    "span_id": span["span_id"],
                    "service": service_name,
                    "correlation_id": f"span_{span['span_id']}_end",
                    "duration_ms": self._calculate_span_duration(span),
                    "context": {
                        "labels": span["labels"]
                    }
                })
        
        # Sort by timestamp and add sequence numbers
        events.sort(key=lambda x: x["timestamp"])
        for i, event in enumerate(events):
            event["sequence"] = i + 1
        
        return events
    
    def _analyze_failure_patterns(self, timeline: List[Dict], spans: List[Dict]) -> Dict:
        """Analyze failure patterns in the timeline"""
        analysis = {
            "failure_cascade": [],
            "error_clusters": [],
            "service_impact": {},
            "critical_path": [],
            "recommendations": []
        }
        
        # Identify failure cascade
        error_events = [e for e in timeline if e.get("is_error", False)]
        if error_events:
            analysis["failure_cascade"] = self._identify_failure_cascade(error_events)
        
        # Identify error clusters (errors happening close in time)
        analysis["error_clusters"] = self._identify_error_clusters(error_events)
        
        # Analyze service impact
        analysis["service_impact"] = self._analyze_service_impact(timeline)
        
        # Identify critical path
        analysis["critical_path"] = self._identify_critical_path(spans)
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _extract_service_name(self, span_name: str) -> str:
        """Extract service name from span name"""
        # Handle common patterns like "service/operation" or "service.operation"
        if "/" in span_name:
            return span_name.split("/")[0]
        elif "." in span_name:
            parts = span_name.split(".")
            # Look for common service patterns
            for part in parts:
                if any(svc in part.lower() for svc in ["service", "svc", "api", "server"]):
                    return part
            return parts[0]
        return span_name
    
    def _calculate_span_duration(self, span: Dict) -> Optional[int]:
        """Calculate span duration in milliseconds"""
        try:
            if span.get("start_time") and span.get("end_time"):
                start = datetime.fromisoformat(span["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(span["end_time"].replace("Z", "+00:00"))
                return int((end - start).total_seconds() * 1000)
        except Exception:
            pass
        return None
    
    def _identify_failure_cascade(self, error_events: List[Dict]) -> List[Dict]:
        """Identify failure cascade patterns"""
        cascade = []
        
        # Group errors by service and time proximity
        for i, event in enumerate(error_events):
            cascade_entry = {
                "sequence": i + 1,
                "timestamp": event["timestamp"],
                "service": event["service"],
                "error_type": event["type"],
                "message": event.get("message", event.get("span_name", "")),
                "likely_cause": i == 0,  # First error is likely the root cause
                "propagation_delay_ms": 0
            }
            
            if i > 0:
                # Calculate propagation delay
                prev_time = datetime.fromisoformat(error_events[i-1]["timestamp"].replace("Z", "+00:00"))
                curr_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                cascade_entry["propagation_delay_ms"] = int((curr_time - prev_time).total_seconds() * 1000)
            
            cascade.append(cascade_entry)
        
        return cascade
    
    def _identify_error_clusters(self, error_events: List[Dict]) -> List[Dict]:
        """Identify clusters of errors happening in close temporal proximity"""
        clusters = []
        current_cluster = []
        cluster_threshold_ms = 5000  # 5 seconds
        
        for event in error_events:
            if not current_cluster:
                current_cluster = [event]
            else:
                last_time = datetime.fromisoformat(current_cluster[-1]["timestamp"].replace("Z", "+00:00"))
                curr_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                
                if (curr_time - last_time).total_seconds() * 1000 <= cluster_threshold_ms:
                    current_cluster.append(event)
                else:
                    if len(current_cluster) > 1:
                        clusters.append({
                            "start_time": current_cluster[0]["timestamp"],
                            "end_time": current_cluster[-1]["timestamp"],
                            "error_count": len(current_cluster),
                            "affected_services": list(set(e["service"] for e in current_cluster)),
                            "events": current_cluster
                        })
                    current_cluster = [event]
        
        # Don't forget the last cluster
        if len(current_cluster) > 1:
            clusters.append({
                "start_time": current_cluster[0]["timestamp"],
                "end_time": current_cluster[-1]["timestamp"],
                "error_count": len(current_cluster),
                "affected_services": list(set(e["service"] for e in current_cluster)),
                "events": current_cluster
            })
        
        return clusters
    
    def _analyze_service_impact(self, timeline: List[Dict]) -> Dict:
        """Analyze impact on each service"""
        service_impact = {}
        
        for event in timeline:
            service = event.get("service", "unknown")
            if service not in service_impact:
                service_impact[service] = {
                    "total_events": 0,
                    "error_events": 0,
                    "first_event": event["timestamp"],
                    "last_event": event["timestamp"],
                    "error_rate": 0.0,
                    "impact_level": "low"
                }
            
            service_impact[service]["total_events"] += 1
            if event.get("is_error", False):
                service_impact[service]["error_events"] += 1
            
            service_impact[service]["last_event"] = event["timestamp"]
        
        # Calculate error rates and impact levels
        for service, impact in service_impact.items():
            if impact["total_events"] > 0:
                impact["error_rate"] = impact["error_events"] / impact["total_events"]
                
                if impact["error_rate"] > 0.5:
                    impact["impact_level"] = "critical"
                elif impact["error_rate"] > 0.2:
                    impact["impact_level"] = "high"
                elif impact["error_rate"] > 0.05:
                    impact["impact_level"] = "medium"
                else:
                    impact["impact_level"] = "low"
        
        return service_impact
    
    def _identify_critical_path(self, spans: List[Dict]) -> List[Dict]:
        """Identify the critical path through the distributed trace"""
        # Build span hierarchy
        span_map = {span["span_id"]: span for span in spans}
        root_spans = [span for span in spans if not span.get("parent_span_id")]
        
        critical_path = []
        
        for root_span in root_spans:
            path = self._trace_critical_path(root_span, span_map)
            critical_path.extend(path)
        
        return critical_path
    
    def _trace_critical_path(self, span: Dict, span_map: Dict) -> List[Dict]:
        """Trace the critical path from a root span"""
        path = [{
            "span_id": span["span_id"],
            "span_name": span["name"],
            "service": self._extract_service_name(span["name"]),
            "duration_ms": self._calculate_span_duration(span),
            "has_error": any("error" in str(v).lower() for v in span["labels"].values())
        }]
        
        # Find child spans and continue with the longest duration
        child_spans = [s for s in span_map.values() if s.get("parent_span_id") == span["span_id"]]
        
        if child_spans:
            # Choose the child with longest duration or error
            critical_child = max(child_spans, key=lambda s: (
                any("error" in str(v).lower() for v in s["labels"].values()),
                self._calculate_span_duration(s) or 0
            ))
            path.extend(self._trace_critical_path(critical_child, span_map))
        
        return path
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate recommendations based on failure analysis"""
        recommendations = []
        
        # Recommendations based on failure cascade
        if analysis["failure_cascade"]:
            root_cause = analysis["failure_cascade"][0]
            recommendations.append(
                f"Focus investigation on {root_cause['service']} service as it appears to be the root cause"
            )
        
        # Recommendations based on error clusters
        if analysis["error_clusters"]:
            cluster = analysis["error_clusters"][0]  # Most significant cluster
            recommendations.append(
                f"Investigate error cluster affecting {len(cluster['affected_services'])} services "
                f"between {cluster['start_time']} and {cluster['end_time']}"
            )
        
        # Recommendations based on service impact
        critical_services = [
            service for service, impact in analysis["service_impact"].items()
            if impact["impact_level"] == "critical"
        ]
        
        if critical_services:
            recommendations.append(
                f"Prioritize remediation for critically impacted services: {', '.join(critical_services)}"
            )
        
        # Recommendations based on critical path
        if analysis["critical_path"]:
            error_spans = [span for span in analysis["critical_path"] if span["has_error"]]
            if error_spans:
                recommendations.append(
                    f"Critical path analysis shows errors in: {', '.join(span['service'] for span in error_spans)}"
                )
        
        return recommendations

    def _build_service_map(self, spans: List[Dict]) -> Dict:
        """Build service dependency map from spans"""
        services = {}
        
        for span in spans:
            service_name = self._extract_service_name(span["name"])
            
            if service_name not in services:
                services[service_name] = {
                    "span_count": 0,
                    "error_count": 0,
                    "dependencies": set()
                }
            
            services[service_name]["span_count"] += 1
            
            if any("error" in str(v).lower() for v in span["labels"].values()):
                services[service_name]["error_count"] += 1
            
            # Track parent-child relationships
            if span.get("parent_span_id"):
                # Find parent span to determine dependency
                for parent_span in spans:
                    if parent_span["span_id"] == span["parent_span_id"]:
                        parent_service = self._extract_service_name(parent_span["name"])
                        if parent_service != service_name:
                            services[service_name]["dependencies"].add(parent_service)
                        break
        
        # Convert sets to lists for JSON serialization
        for service in services.values():
            service["dependencies"] = list(service["dependencies"])
        
        return services
    
    async def _analyze_microservice_patterns(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze microservice failure patterns specific to Online Boutique"""
        trace_ids = arguments["trace_ids"]
        time_range = arguments.get("time_range", {})
        focus_services = arguments.get("focus_services", ["frontend", "cartservice", "productcatalogservice", "checkoutservice"])
        
        try:
            pattern_analysis = {
                "trace_ids": trace_ids,
                "focus_services": focus_services,
                "patterns": {
                    "service_failure_patterns": {},
                    "dependency_patterns": {},
                    "error_propagation": {},
                    "performance_patterns": {},
                    "online_boutique_specific": {}
                },
                "recommendations": []
            }
            
            # Analyze each trace for patterns
            all_spans = []
            all_logs = []
            
            for trace_id in trace_ids:
                # Get trace data
                traces_result = await self._get_traces({"trace_id": trace_id, "include_spans": True})
                traces_data = json.loads(traces_result[0].text)
                
                # Get log data
                logs_result = await self._get_logs({"trace_id": trace_id, "time_window": 300})
                logs_data = json.loads(logs_result[0].text)
                
                all_spans.extend(traces_data.get("spans", []))
                all_logs.extend(logs_data.get("logs", []))
            
            # Analyze service failure patterns
            pattern_analysis["patterns"]["service_failure_patterns"] = self._analyze_service_failure_patterns(all_spans, all_logs, focus_services)
            
            # Analyze dependency patterns
            pattern_analysis["patterns"]["dependency_patterns"] = self._analyze_dependency_patterns(all_spans, focus_services)
            
            # Analyze error propagation
            pattern_analysis["patterns"]["error_propagation"] = self._analyze_error_propagation(all_spans, all_logs)
            
            # Analyze performance patterns
            pattern_analysis["patterns"]["performance_patterns"] = self._analyze_performance_patterns(all_spans, focus_services)
            
            # Online Boutique specific analysis
            pattern_analysis["patterns"]["online_boutique_specific"] = self._analyze_online_boutique_patterns(all_spans, all_logs)
            
            # Generate recommendations
            pattern_analysis["recommendations"] = self._generate_pattern_recommendations(pattern_analysis["patterns"])
            
            return [TextContent(
                type="text",
                text=json.dumps(pattern_analysis, indent=2, default=str)
            )]
            
        except Exception as e:
            logger.error(f"Error analyzing microservice patterns: {e}")
            raise
    
    async def _detect_cascade_failures(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Detect cascade failure patterns across Online Boutique microservices"""
        initial_trace_id = arguments["initial_trace_id"]
        cascade_window = arguments.get("cascade_window", 300)
        severity_threshold = arguments.get("severity_threshold", "WARNING")
        
        try:
            # Get initial failure data
            initial_traces = await self._get_traces({"trace_id": initial_trace_id, "include_spans": True})
            initial_data = json.loads(initial_traces[0].text)
            
            initial_logs = await self._get_logs({"trace_id": initial_trace_id, "time_window": cascade_window})
            initial_log_data = json.loads(initial_logs[0].text)
            
            # Find the failure start time
            failure_start_time = self._find_failure_start_time(initial_data["spans"], initial_log_data["logs"])
            
            # Search for related failures in the cascade window
            cascade_analysis = {
                "initial_trace_id": initial_trace_id,
                "failure_start_time": failure_start_time,
                "cascade_window_seconds": cascade_window,
                "cascade_chain": [],
                "affected_services": set(),
                "cascade_metrics": {
                    "total_affected_traces": 0,
                    "cascade_duration": 0,
                    "propagation_speed": 0,
                    "blast_radius": 0
                },
                "online_boutique_impact": {}
            }
            
            # Search for cascade failures using time-based correlation
            if failure_start_time:
                cascade_failures = await self._search_cascade_failures(
                    failure_start_time, cascade_window, severity_threshold
                )
                
                cascade_analysis["cascade_chain"] = cascade_failures
                cascade_analysis["affected_services"] = list(set(
                    failure.get("service", "unknown") for failure in cascade_failures
                ))
                
                # Calculate cascade metrics
                cascade_analysis["cascade_metrics"] = self._calculate_cascade_metrics(cascade_failures, failure_start_time)
                
                # Analyze Online Boutique specific impact
                cascade_analysis["online_boutique_impact"] = self._analyze_online_boutique_cascade_impact(cascade_failures)
            
            return [TextContent(
                type="text",
                text=json.dumps(cascade_analysis, indent=2, default=str)
            )]
            
        except Exception as e:
            logger.error(f"Error detecting cascade failures: {e}")
            raise
    
    def _analyze_service_failure_patterns(self, spans: List[Dict], logs: List[Dict], focus_services: List[str]) -> Dict:
        """Analyze failure patterns for specific services"""
        patterns = {}
        
        for service in focus_services:
            service_spans = [span for span in spans if self._extract_service_name(span["name"]) == service]
            service_logs = [log for log in logs if log["resource"]["labels"].get("service_name") == service]
            
            patterns[service] = {
                "error_rate": len([span for span in service_spans if self._is_error_span(span)]) / max(len(service_spans), 1),
                "common_errors": self._extract_common_errors(service_logs),
                "performance_issues": self._detect_performance_issues(service_spans),
                "dependency_failures": self._detect_dependency_failures(service_spans, spans)
            }
        
        return patterns
    
    def _analyze_dependency_patterns(self, spans: List[Dict], focus_services: List[str]) -> Dict:
        """Analyze dependency patterns between services"""
        dependencies = {}
        
        for service in focus_services:
            service_spans = [span for span in spans if self._extract_service_name(span["name"]) == service]
            
            dependencies[service] = {
                "upstream_dependencies": self._find_upstream_dependencies(service_spans, spans),
                "downstream_dependents": self._find_downstream_dependents(service, spans),
                "critical_path_involvement": self._analyze_critical_path_involvement(service_spans, spans)
            }
        
        return dependencies
    
    def _analyze_error_propagation(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze how errors propagate through the system"""
        propagation = {
            "propagation_chains": [],
            "propagation_speed": {},
            "error_amplification": {},
            "circuit_breaker_effectiveness": {}
        }
        
        # Find error propagation chains
        error_spans = [span for span in spans if self._is_error_span(span)]
        error_logs = [log for log in logs if log["severity"] in ["ERROR", "CRITICAL"]]
        
        # Group by time and trace relationships
        propagation["propagation_chains"] = self._build_propagation_chains(error_spans, error_logs)
        
        return propagation
    
    def _analyze_performance_patterns(self, spans: List[Dict], focus_services: List[str]) -> Dict:
        """Analyze performance patterns that might indicate issues"""
        performance = {}
        
        for service in focus_services:
            service_spans = [span for span in spans if self._extract_service_name(span["name"]) == service]
            
            durations = [self._calculate_span_duration(span) for span in service_spans if self._calculate_span_duration(span)]
            
            if durations:
                performance[service] = {
                    "avg_duration_ms": sum(durations) / len(durations),
                    "max_duration_ms": max(durations),
                    "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 20 else max(durations),
                    "slow_requests": len([d for d in durations if d > 5000]),  # > 5 seconds
                    "performance_degradation": self._detect_performance_degradation(durations)
                }
        
        return performance
    
    def _analyze_online_boutique_patterns(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze patterns specific to Online Boutique application"""
        online_boutique_patterns = {
            "checkout_flow_issues": self._analyze_checkout_flow(spans, logs),
            "cart_service_patterns": self._analyze_cart_service(spans, logs),
            "product_catalog_issues": self._analyze_product_catalog(spans, logs),
            "payment_processing": self._analyze_payment_processing(spans, logs),
            "recommendation_engine": self._analyze_recommendation_engine(spans, logs),
            "frontend_issues": self._analyze_frontend_issues(spans, logs)
        }
        
        return online_boutique_patterns
    
    def _generate_pattern_recommendations(self, patterns: Dict) -> List[str]:
        """Generate recommendations based on detected patterns"""
        recommendations = []
        
        # Service failure pattern recommendations
        for service, pattern in patterns.get("service_failure_patterns", {}).items():
            if pattern["error_rate"] > 0.1:  # > 10% error rate
                recommendations.append(f"High error rate detected in {service} ({pattern['error_rate']:.1%}). Consider scaling or investigating root cause.")
        
        # Dependency pattern recommendations
        for service, deps in patterns.get("dependency_patterns", {}).items():
            if len(deps["upstream_dependencies"]) > 5:
                recommendations.append(f"{service} has many upstream dependencies. Consider circuit breakers and fallback mechanisms.")
        
        # Performance pattern recommendations
        for service, perf in patterns.get("performance_patterns", {}).items():
            if perf.get("avg_duration_ms", 0) > 2000:  # > 2 seconds
                recommendations.append(f"{service} showing high latency ({perf['avg_duration_ms']:.0f}ms avg). Consider performance optimization.")
        
        # Online Boutique specific recommendations
        ob_patterns = patterns.get("online_boutique_specific", {})
        if ob_patterns.get("checkout_flow_issues", {}).get("failure_rate", 0) > 0.05:
            recommendations.append("Checkout flow showing failures. This directly impacts revenue - prioritize investigation.")
        
        return recommendations
    
    def _find_failure_start_time(self, spans: List[Dict], logs: List[Dict]) -> Optional[str]:
        """Find the earliest failure time from spans and logs"""
        failure_times = []
        
        # Check spans for errors
        for span in spans:
            if self._is_error_span(span) and span.get("start_time"):
                failure_times.append(span["start_time"])
        
        # Check logs for errors
        for log in logs:
            if log["severity"] in ["ERROR", "CRITICAL"] and log.get("timestamp"):
                failure_times.append(log["timestamp"])
        
        return min(failure_times) if failure_times else None
    
    async def _search_cascade_failures(self, start_time: str, window_seconds: int, severity_threshold: str) -> List[Dict]:
        """Search for cascade failures within the time window"""
        # This would typically search for related failures using time-based correlation
        # For now, return a placeholder structure
        cascade_failures = []
        
        # In a real implementation, this would:
        # 1. Search logs in the time window after start_time
        # 2. Look for error patterns that correlate with the initial failure
        # 3. Build a chain of related failures
        
        return cascade_failures
    
    def _calculate_cascade_metrics(self, cascade_failures: List[Dict], start_time: str) -> Dict:
        """Calculate metrics about the cascade failure"""
        if not cascade_failures:
            return {"total_affected_traces": 0, "cascade_duration": 0, "propagation_speed": 0, "blast_radius": 0}
        
        return {
            "total_affected_traces": len(cascade_failures),
            "cascade_duration": 0,  # Would calculate based on failure times
            "propagation_speed": 0,  # Failures per second
            "blast_radius": len(set(f.get("service", "") for f in cascade_failures))
        }
    
    def _analyze_online_boutique_cascade_impact(self, cascade_failures: List[Dict]) -> Dict:
        """Analyze cascade impact specific to Online Boutique"""
        return {
            "revenue_impact": "high" if any("checkout" in f.get("service", "").lower() for f in cascade_failures) else "medium",
            "user_experience_impact": "critical" if any("frontend" in f.get("service", "").lower() for f in cascade_failures) else "moderate",
            "business_critical_services_affected": [f.get("service") for f in cascade_failures if f.get("service") in ["checkoutservice", "paymentservice", "frontend"]]
        }
    
    # Helper methods for Online Boutique specific analysis
    def _analyze_checkout_flow(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze checkout flow specific issues"""
        checkout_spans = [span for span in spans if "checkout" in span["name"].lower()]
        checkout_logs = [log for log in logs if "checkout" in log.get("message", "").lower()]
        
        return {
            "total_checkout_attempts": len(checkout_spans),
            "failed_checkouts": len([span for span in checkout_spans if self._is_error_span(span)]),
            "failure_rate": len([span for span in checkout_spans if self._is_error_span(span)]) / max(len(checkout_spans), 1),
            "common_checkout_errors": self._extract_common_errors(checkout_logs)
        }
    
    def _analyze_cart_service(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze cart service specific patterns"""
        cart_spans = [span for span in spans if "cart" in span["name"].lower()]
        return {
            "cart_operations": len(cart_spans),
            "cart_errors": len([span for span in cart_spans if self._is_error_span(span)]),
            "avg_cart_operation_time": sum(self._calculate_span_duration(span) or 0 for span in cart_spans) / max(len(cart_spans), 1)
        }
    
    def _analyze_product_catalog(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze product catalog service patterns"""
        catalog_spans = [span for span in spans if "product" in span["name"].lower() or "catalog" in span["name"].lower()]
        return {
            "catalog_queries": len(catalog_spans),
            "catalog_errors": len([span for span in catalog_spans if self._is_error_span(span)]),
            "slow_catalog_queries": len([span for span in catalog_spans if (self._calculate_span_duration(span) or 0) > 1000])
        }
    
    def _analyze_payment_processing(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze payment processing patterns"""
        payment_spans = [span for span in spans if "payment" in span["name"].lower()]
        return {
            "payment_attempts": len(payment_spans),
            "payment_failures": len([span for span in payment_spans if self._is_error_span(span)]),
            "payment_success_rate": 1 - (len([span for span in payment_spans if self._is_error_span(span)]) / max(len(payment_spans), 1))
        }
    
    def _analyze_recommendation_engine(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze recommendation engine patterns"""
        rec_spans = [span for span in spans if "recommend" in span["name"].lower()]
        return {
            "recommendation_requests": len(rec_spans),
            "recommendation_errors": len([span for span in rec_spans if self._is_error_span(span)]),
            "avg_recommendation_time": sum(self._calculate_span_duration(span) or 0 for span in rec_spans) / max(len(rec_spans), 1)
        }
    
    def _analyze_frontend_issues(self, spans: List[Dict], logs: List[Dict]) -> Dict:
        """Analyze frontend specific issues"""
        frontend_spans = [span for span in spans if "frontend" in span["name"].lower()]
        frontend_logs = [log for log in logs if log["resource"]["labels"].get("service_name") == "frontend"]
        
        return {
            "frontend_requests": len(frontend_spans),
            "frontend_errors": len([span for span in frontend_spans if self._is_error_span(span)]),
            "user_facing_errors": len([log for log in frontend_logs if log["severity"] in ["ERROR", "CRITICAL"]]),
            "avg_response_time": sum(self._calculate_span_duration(span) or 0 for span in frontend_spans) / max(len(frontend_spans), 1)
        }
    
    # Additional helper methods
    def _is_error_span(self, span: Dict) -> bool:
        """Check if a span represents an error"""
        return any("error" in str(v).lower() or "fail" in str(v).lower() for v in span.get("labels", {}).values())
    
    def _extract_common_errors(self, logs: List[Dict]) -> List[Dict]:
        """Extract common error patterns from logs"""
        error_counts = {}
        for log in logs:
            if log["severity"] in ["ERROR", "CRITICAL"]:
                # Simple error categorization
                message = log.get("message", "")
                error_type = "unknown"
                
                if "timeout" in message.lower():
                    error_type = "timeout"
                elif "connection" in message.lower():
                    error_type = "connection_error"
                elif "not found" in message.lower():
                    error_type = "not_found"
                elif "permission" in message.lower() or "auth" in message.lower():
                    error_type = "authentication_error"
                
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return [{"error_type": k, "count": v} for k, v in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)]
    
    def _detect_performance_issues(self, spans: List[Dict]) -> List[str]:
        """Detect performance issues in spans"""
        issues = []
        durations = [self._calculate_span_duration(span) for span in spans if self._calculate_span_duration(span)]
        
        if durations:
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 5000:  # > 5 seconds
                issues.append("high_latency")
            
            if max(durations) > 30000:  # > 30 seconds
                issues.append("timeout_risk")
        
        return issues
    
    def _detect_dependency_failures(self, service_spans: List[Dict], all_spans: List[Dict]) -> List[str]:
        """Detect dependency-related failures"""
        failures = []
        
        # Look for spans that call other services and fail
        for span in service_spans:
            if self._is_error_span(span):
                # Check if this span has child spans (indicating service calls)
                child_spans = [s for s in all_spans if s.get("parent_span_id") == span["span_id"]]
                if child_spans:
                    failures.append("downstream_service_failure")
        
        return list(set(failures))
    
    def _find_upstream_dependencies(self, service_spans: List[Dict], all_spans: List[Dict]) -> List[str]:
        """Find upstream services that this service depends on"""
        dependencies = set()
        
        for span in service_spans:
            # Find parent spans
            if span.get("parent_span_id"):
                parent_spans = [s for s in all_spans if s["span_id"] == span["parent_span_id"]]
                for parent in parent_spans:
                    parent_service = self._extract_service_name(parent["name"])
                    if parent_service != self._extract_service_name(span["name"]):
                        dependencies.add(parent_service)
        
        return list(dependencies)
    
    def _find_downstream_dependents(self, service: str, all_spans: List[Dict]) -> List[str]:
        """Find services that depend on this service"""
        dependents = set()
        
        service_spans = [span for span in all_spans if self._extract_service_name(span["name"]) == service]
        
        for span in service_spans:
            # Find child spans
            child_spans = [s for s in all_spans if s.get("parent_span_id") == span["span_id"]]
            for child in child_spans:
                child_service = self._extract_service_name(child["name"])
                if child_service != service:
                    dependents.add(child_service)
        
        return list(dependents)
    
    def _analyze_critical_path_involvement(self, service_spans: List[Dict], all_spans: List[Dict]) -> Dict:
        """Analyze how involved this service is in critical paths"""
        return {
            "is_on_critical_path": len(service_spans) > 0,
            "critical_path_percentage": len(service_spans) / max(len(all_spans), 1),
            "bottleneck_risk": "high" if any(self._calculate_span_duration(span) and self._calculate_span_duration(span) > 10000 for span in service_spans) else "low"
        }
    
    def _build_propagation_chains(self, error_spans: List[Dict], error_logs: List[Dict]) -> List[Dict]:
        """Build error propagation chains"""
        chains = []
        
        # Group errors by time proximity
        sorted_errors = sorted(error_spans + error_logs, key=lambda x: x.get("start_time", x.get("timestamp", "")))
        
        current_chain = []
        last_time = None
        
        for error in sorted_errors:
            error_time = error.get("start_time", error.get("timestamp"))
            if error_time:
                if last_time and self._time_diff_seconds(last_time, error_time) > 60:  # > 1 minute gap
                    if current_chain:
                        chains.append(current_chain)
                    current_chain = []
                
                current_chain.append({
                    "service": self._extract_service_name(error.get("name", "")),
                    "time": error_time,
                    "type": "span" if "span_id" in error else "log"
                })
                last_time = error_time
        
        if current_chain:
            chains.append(current_chain)
        
        return chains
    
    def _detect_performance_degradation(self, durations: List[int]) -> bool:
        """Detect if there's performance degradation in the durations"""
        if len(durations) < 10:
            return False
        
        # Simple check: if the last 25% of requests are significantly slower than the first 25%
        first_quarter = durations[:len(durations)//4]
        last_quarter = durations[-len(durations)//4:]
        
        avg_first = sum(first_quarter) / len(first_quarter)
        avg_last = sum(last_quarter) / len(last_quarter)
        
        return avg_last > avg_first * 1.5  # 50% slower
    
    def _time_diff_seconds(self, time1: str, time2: str) -> int:
        """Calculate difference between two ISO timestamps in seconds"""
        try:
            dt1 = datetime.fromisoformat(time1.replace("Z", "+00:00"))
            dt2 = datetime.fromisoformat(time2.replace("Z", "+00:00"))
            return abs((dt2 - dt1).total_seconds())
        except Exception:
            return 0

async def main():
    """Main entry point for the MCP server"""
    try:
        server_instance = GCPObservabilityServer()
        
        async with stdio_server() as (read_stream, write_stream):
            await server_instance.server.run(
                read_stream,
                write_stream,
                server_instance.server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())