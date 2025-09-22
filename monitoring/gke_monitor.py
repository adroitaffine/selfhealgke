#!/usr/bin/env python3
"""
GKE Real-time Monitoring Service

This service monitors actual GKE pod logs and events to detect real incidents
and automatically trigger the agent orchestrator workflow.
"""

import asyncio
import json
import logging
import re
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from collections import defaultdict, deque
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class IncidentPattern:
    """Pattern for detecting incidents"""
    name: str
    severity: str
    patterns: List[str]
    threshold: int
    time_window_minutes: int

@dataclass
class RealIncident:
    """Real incident detected from monitoring"""
    incident_id: str
    title: str
    description: str
    severity: str
    confidence: float
    pod_name: str
    namespace: str
    log_samples: List[str]
    timestamp: datetime
    affected_services: List[str]

class GKEMonitoringService:
    """Real-time GKE monitoring service"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.orchestrator_url = config.get('orchestrator_url', 'http://localhost:8080')
        self.monitored_namespaces = config.get('namespaces', ['online-boutique', 'default'])
        
        # State tracking
        self.log_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.detected_incidents: Set[str] = set()
        self.running_processes: Dict[str, subprocess.Popen] = {}
        
        # Incident detection patterns
        self.patterns = [
            IncidentPattern(
                name="Database Connection Error",
                severity="high",
                patterns=[
                    r"connection.*timeout",
                    r"database.*unavailable",
                    r"connection.*refused",
                    r"failed.*connect.*database",
                    r"sqlalchemy.*timeout"
                ],
                threshold=2,
                time_window_minutes=5
            ),
            IncidentPattern(
                name="HTTP Server Error",
                severity="medium",
                patterns=[
                    r"http.*5\d\d",
                    r"internal server error",
                    r"service unavailable",
                    r"gateway timeout",
                    r"error.*status.*5\d\d"
                ],
                threshold=3,
                time_window_minutes=3
            ),
            IncidentPattern(
                name="Out of Memory",
                severity="critical",
                patterns=[
                    r"outofmemoryerror",
                    r"oomkilled",
                    r"out of memory",
                    r"memory.*exhausted",
                    r"cannot allocate memory"
                ],
                threshold=1,
                time_window_minutes=1
            ),
            IncidentPattern(
                name="Application Crash",
                severity="high",
                patterns=[
                    r"panic:",
                    r"fatal error",
                    r"segmentation fault",
                    r"core dumped",
                    r"unexpected error",
                    r"exception.*unhandled"
                ],
                threshold=1,
                time_window_minutes=2
            ),
            IncidentPattern(
                name="Performance Degradation",
                severity="medium",
                patterns=[
                    r"timeout.*exceeded",
                    r"request.*slow",
                    r"response.*time.*high",
                    r"latency.*threshold",
                    r"performance.*degraded",
                    r"slow.*query"
                ],
                threshold=5,
                time_window_minutes=10
            )
        ]
        
        logger.info("GKE Monitoring Service initialized")
    
    async def start_monitoring(self):
        """Start all monitoring tasks"""
        logger.info("🚀 Starting real-time GKE monitoring...")
        
        try:
            # Test kubectl connectivity
            await self.test_kubectl_access()
            
            # Start monitoring tasks
            tasks = [
                asyncio.create_task(self.monitor_pod_logs()),
                asyncio.create_task(self.monitor_pod_events()),
                asyncio.create_task(self.monitor_pod_status()),
                asyncio.create_task(self.cleanup_task())
            ]
            
            await asyncio.gather(*tasks)
            
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring failed: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def test_kubectl_access(self):
        """Test kubectl access to cluster"""
        try:
            result = subprocess.run(
                ['kubectl', 'get', 'pods', '-n', 'online-boutique', '--no-headers'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                pod_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
                logger.info(f"✅ kubectl access confirmed - {pod_count} pods in online-boutique namespace")
            else:
                raise Exception(f"kubectl failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"kubectl access test failed: {e}")
            raise
    
    async def monitor_pod_logs(self):
        """Monitor pod logs for all pods in monitored namespaces"""
        logger.info("📋 Starting pod log monitoring...")
        
        for namespace in self.monitored_namespaces:
            try:
                # Get current pods
                result = subprocess.run(
                    ['kubectl', 'get', 'pods', '-n', namespace, '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    pods = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                    
                    for pod_name in pods:
                        # Start log monitoring for each pod
                        asyncio.create_task(self.monitor_single_pod_logs(pod_name, namespace))
                        await asyncio.sleep(0.5)  # Stagger start times
                
            except Exception as e:
                logger.error(f"Error getting pods for namespace {namespace}: {e}")
    
    async def monitor_single_pod_logs(self, pod_name: str, namespace: str):
        """Monitor logs for a single pod"""
        log_key = f"{namespace}/{pod_name}"
        
        try:
            # Start kubectl logs process
            cmd = [
                'kubectl', 'logs', '-f', 
                '--namespace', namespace,
                pod_name,
                '--tail=10'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.running_processes[log_key] = process
            logger.info(f"📊 Monitoring logs: {log_key}")
            
            # Read logs line by line
            while process.poll() is None:
                try:
                    line = process.stdout.readline()
                    if line:
                        line = line.strip()
                        if line:
                            await self.analyze_log_line(line, pod_name, namespace)
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(f"Error reading log line for {log_key}: {e}")
                    break
            
        except Exception as e:
            logger.warning(f"Error monitoring logs for {log_key}: {e}")
        finally:
            # Cleanup process
            if log_key in self.running_processes:
                try:
                    self.running_processes[log_key].terminate()
                    del self.running_processes[log_key]
                except:
                    pass
    
    async def analyze_log_line(self, log_line: str, pod_name: str, namespace: str):
        """Analyze a log line for incident patterns"""
        log_line_lower = log_line.lower()
        current_time = datetime.now()
        
        for pattern in self.patterns:
            for regex in pattern.patterns:
                if re.search(regex, log_line_lower, re.IGNORECASE):
                    # Found a pattern match
                    buffer_key = f"{pattern.name}:{namespace}:{pod_name}"
                    
                    # Add to buffer
                    self.log_buffers[buffer_key].append({
                        'timestamp': current_time,
                        'log_line': log_line,
                        'pattern': regex,
                        'pod_name': pod_name,
                        'namespace': namespace
                    })
                    
                    # Check threshold
                    await self.check_incident_threshold(buffer_key, pattern)
                    break
    
    async def check_incident_threshold(self, buffer_key: str, pattern: IncidentPattern):
        """Check if incident threshold is met"""
        buffer = self.log_buffers[buffer_key]
        current_time = datetime.now()
        
        # Count recent occurrences
        time_threshold = current_time - timedelta(minutes=pattern.time_window_minutes)
        recent_entries = [
            entry for entry in buffer 
            if entry['timestamp'] >= time_threshold
        ]
        
        if len(recent_entries) >= pattern.threshold:
            # Threshold met - create incident
            incident_key = f"{buffer_key}-{int(current_time.timestamp())}"
            
            if incident_key not in self.detected_incidents:
                self.detected_incidents.add(incident_key)
                await self.create_real_incident(buffer_key, pattern, recent_entries)
    
    async def create_real_incident(self, buffer_key: str, pattern: IncidentPattern, entries: List[Dict]):
        """Create a real incident from detected patterns"""
        latest_entry = entries[-1]
        
        incident = RealIncident(
            incident_id=f"gke-real-{int(time.time())}-{hash(buffer_key) % 10000}",
            title=f"{pattern.name} in {latest_entry['namespace']}/{latest_entry['pod_name']}",
            description=f"Detected {len(entries)} occurrences of {pattern.name} in the last {pattern.time_window_minutes} minutes",
            severity=pattern.severity,
            confidence=min(0.7 + (len(entries) * 0.1), 1.0),
            pod_name=latest_entry['pod_name'],
            namespace=latest_entry['namespace'],
            log_samples=[entry['log_line'] for entry in entries[-5:]],  # Last 5 samples
            timestamp=datetime.now(),
            affected_services=[latest_entry['pod_name']]
        )
        
        logger.info(f"🚨 REAL INCIDENT DETECTED: {incident.title}")
        logger.info(f"   Severity: {incident.severity} | Confidence: {incident.confidence:.2f}")
        logger.info(f"   Log samples: {len(incident.log_samples)} entries")
        
        # Send to orchestrator
        await self.send_to_orchestrator(incident)
    
    async def monitor_pod_events(self):
        """Monitor Kubernetes events for pod issues"""
        logger.info("📋 Starting Kubernetes event monitoring...")
        
        while True:
            try:
                # Get recent events
                result = subprocess.run([
                    'kubectl', 'get', 'events',
                    '--sort-by=.metadata.creationTimestamp',
                    '-o', 'json'
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    events_data = json.loads(result.stdout)
                    await self.analyze_events(events_data.get('items', []))
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.warning(f"Error monitoring events: {e}")
                await asyncio.sleep(60)
    
    async def analyze_events(self, events: List[Dict]):
        """Analyze Kubernetes events for incidents"""
        current_time = datetime.now()
        recent_threshold = current_time - timedelta(minutes=5)
        
        for event in events:
            try:
                event_time_str = event.get('metadata', {}).get('creationTimestamp', '')
                if not event_time_str:
                    continue
                
                # Parse event time
                event_time = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                
                if event_time < recent_threshold:
                    continue
                
                event_type = event.get('type', '')
                reason = event.get('reason', '')
                message = event.get('message', '')
                
                # Check for incident patterns
                if event_type == 'Warning' and any(
                    keyword in reason.lower() or keyword in message.lower()
                    for keyword in ['failed', 'error', 'unhealthy', 'oomkilled', 'crash']
                ):
                    await self.create_event_incident(event)
                    
            except Exception as e:
                logger.warning(f"Error analyzing event: {e}")
    
    async def create_event_incident(self, event: Dict):
        """Create incident from Kubernetes event"""
        reason = event.get('reason', 'Unknown')
        message = event.get('message', 'No details')
        involved_object = event.get('involvedObject', {})
        pod_name = involved_object.get('name', 'unknown')
        namespace = involved_object.get('namespace', 'unknown')
        
        incident = RealIncident(
            incident_id=f"k8s-event-{int(time.time())}-{hash(str(event)) % 10000}",
            title=f"Kubernetes Event: {reason}",
            description=message,
            severity="medium" if event.get('type') == 'Warning' else "high",
            confidence=0.8,
            pod_name=pod_name,
            namespace=namespace,
            log_samples=[f"Event: {reason} - {message}"],
            timestamp=datetime.now(),
            affected_services=[pod_name]
        )
        
        logger.info(f"🚨 K8S EVENT INCIDENT: {incident.title}")
        await self.send_to_orchestrator(incident)
    
    async def monitor_pod_status(self):
        """Monitor pod status changes and restarts"""
        logger.info("📋 Starting pod status monitoring...")
        
        pod_status_cache = {}
        
        while True:
            try:
                for namespace in self.monitored_namespaces:
                    result = subprocess.run([
                        'kubectl', 'get', 'pods', '-n', namespace,
                        '-o', 'json'
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        pods_data = json.loads(result.stdout)
                        await self.analyze_pod_status(pods_data.get('items', []), pod_status_cache)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.warning(f"Error monitoring pod status: {e}")
                await asyncio.sleep(60)
    
    async def analyze_pod_status(self, pods: List[Dict], status_cache: Dict):
        """Analyze pod status for issues"""
        for pod in pods:
            try:
                pod_name = pod.get('metadata', {}).get('name', '')
                namespace = pod.get('metadata', {}).get('namespace', '')
                pod_key = f"{namespace}/{pod_name}"
                
                status = pod.get('status', {})
                container_statuses = status.get('containerStatuses', [])
                
                # Check restart counts
                total_restarts = sum(
                    container.get('restartCount', 0) 
                    for container in container_statuses
                )
                
                # Compare with cached status
                if pod_key in status_cache:
                    if total_restarts > status_cache[pod_key]['restarts']:
                        restart_diff = total_restarts - status_cache[pod_key]['restarts']
                        await self.create_restart_incident(pod_name, namespace, restart_diff)
                
                status_cache[pod_key] = {
                    'restarts': total_restarts,
                    'phase': status.get('phase', 'Unknown'),
                    'last_check': datetime.now()
                }
                
            except Exception as e:
                logger.warning(f"Error analyzing pod status: {e}")
    
    async def create_restart_incident(self, pod_name: str, namespace: str, restart_count: int):
        """Create incident for pod restart"""
        incident = RealIncident(
            incident_id=f"restart-{int(time.time())}-{hash(f'{namespace}/{pod_name}') % 10000}",
            title=f"Pod Restart: {namespace}/{pod_name}",
            description=f"Pod restarted {restart_count} time(s) unexpectedly",
            severity="medium" if restart_count == 1 else "high",
            confidence=0.9,
            pod_name=pod_name,
            namespace=namespace,
            log_samples=[f"Restart count increased by {restart_count}"],
            timestamp=datetime.now(),
            affected_services=[pod_name]
        )
        
        logger.info(f"🚨 POD RESTART INCIDENT: {incident.title}")
        await self.send_to_orchestrator(incident)
    
    async def send_to_orchestrator(self, incident: RealIncident):
        """Send real incident to orchestrator"""
        try:
            # Extract service name from pod name (remove deployment hash)
            service_name = incident.pod_name
            if '-' in incident.pod_name:
                parts = incident.pod_name.split('-')
                if len(parts) >= 2:
                    service_name = '-'.join(parts[:-2]) if len(parts) > 2 else parts[0]
            
            incident_data = {
                'id': incident.incident_id,
                'title': incident.title,
                'summary': incident.description,
                'classification': self._classify_incident_type(incident),
                'failing_service': service_name,
                'evidence': incident.log_samples,
                'test_failure_data': {
                    'pod_name': incident.pod_name,
                    'namespace': incident.namespace,
                    'confidence': incident.confidence,
                    'source': 'gke_real_monitoring',
                    'pattern_matched': incident.log_samples[0] if incident.log_samples else 'No pattern'
                },
                'affected_services': incident.affected_services,
                'timestamp': incident.timestamp.isoformat(),
                'status': incident.severity,
                'trace_id': f"real-trace-{incident.incident_id}",
                'source': 'gke_real_monitoring'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.orchestrator_url}/webhook/incident",
                    json=incident_data,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Real incident sent to orchestrator: {result}")
                    else:
                        logger.error(f"❌ Failed to send incident: {response.status}")
                        
        except Exception as e:
            logger.error(f"Error sending incident to orchestrator: {e}")
    
    def _classify_incident_type(self, incident: RealIncident) -> str:
        """Classify the incident type based on the title and patterns"""
        title_lower = incident.title.lower()
        
        if 'database' in title_lower or 'connection' in title_lower:
            return 'Database Connectivity Issue'
        elif 'http' in title_lower or 'server error' in title_lower:
            return 'HTTP Service Error'
        elif 'memory' in title_lower or 'oom' in title_lower:
            return 'Resource Exhaustion'
        elif 'restart' in title_lower or 'crash' in title_lower:
            return 'Pod Failure'
        elif 'performance' in title_lower or 'slow' in title_lower:
            return 'Performance Degradation'
        else:
            return 'Service Issue'
    
    async def cleanup_task(self):
        """Periodic cleanup task"""
        while True:
            try:
                # Clean old incident tracking
                if len(self.detected_incidents) > 1000:
                    self.detected_incidents.clear()
                    logger.info("Cleaned incident tracking cache")
                
                await asyncio.sleep(300)  # Every 5 minutes
                
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(60)
    
    async def cleanup(self):
        """Cleanup all resources"""
        logger.info("🧹 Cleaning up monitoring processes...")
        
        for log_key, process in self.running_processes.items():
            try:
                process.terminate()
                logger.info(f"Terminated log process for {log_key}")
            except:
                pass
        
        self.running_processes.clear()
        logger.info("Cleanup complete")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get monitoring status"""
        return {
            'active_log_monitors': len(self.running_processes),
            'monitored_namespaces': self.monitored_namespaces,
            'detected_incidents': len(self.detected_incidents),
            'pattern_count': len(self.patterns),
            'log_buffer_sizes': {k: len(v) for k, v in self.log_buffers.items()}
        }

async def main():
    """Main function"""
    config = {
        'orchestrator_url': 'http://localhost:8080',
        'namespaces': ['online-boutique', 'default']
    }
    
    monitor = GKEMonitoringService(config)
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped")
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
        raise
    finally:
        await monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())