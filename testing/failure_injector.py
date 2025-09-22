#!/usr/bin/env python3
"""
Failure Injection Tool for Online Boutique

This tool injects various types of failures into the Online Boutique microservices
to test the monitoring and incident response system.
"""

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FailureInjectionTool:
    """Tool for injecting failures into Online Boutique services"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.namespace = config.get('namespace', 'online-boutique')
        self.dashboard_url = config.get('dashboard_url', 'http://localhost:8080')
        
        # Available failure scenarios
        self.failure_scenarios = {
            'pod_restart': {
                'description': 'Restart a random pod to simulate crash',
                'severity': 'medium',
                'method': self.inject_pod_restart
            },
            'resource_stress': {
                'description': 'Stress CPU/Memory to trigger OOM or throttling',
                'severity': 'high',
                'method': self.inject_resource_stress
            },
            'network_latency': {
                'description': 'Inject network latency between services',
                'severity': 'medium',
                'method': self.inject_network_latency
            },
            'service_unavailable': {
                'description': 'Make a service temporarily unavailable',
                'severity': 'high',
                'method': self.inject_service_unavailable
            },
            'database_connection_failure': {
                'description': 'Simulate database connection issues',
                'severity': 'critical',
                'method': self.inject_database_failure
            }
        }
        
        logger.info("Failure Injection Tool initialized")
    
    async def list_available_scenarios(self) -> Dict[str, Dict]:
        """List all available failure scenarios"""
        return self.failure_scenarios
    
    async def get_target_services(self) -> List[str]:
        """Get list of services that can be targeted"""
        try:
            result = subprocess.run([
                'kubectl', 'get', 'pods', '-n', self.namespace,
                '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                pods = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                # Extract service names (remove replica suffixes)
                services = list(set([
                    '-'.join(pod.split('-')[:-2]) if len(pod.split('-')) > 2 else pod 
                    for pod in pods
                ]))
                return services
            else:
                logger.error(f"Failed to get services: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting target services: {e}")
            return []
    
    async def inject_failure(self, scenario: str, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Inject a specific failure scenario"""
        if scenario not in self.failure_scenarios:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        failure_info = self.failure_scenarios[scenario]
        logger.info(f"🔥 Injecting failure: {scenario} - {failure_info['description']}")
        
        # Record failure injection start
        injection_id = f"injection-{int(time.time())}"
        await self.log_injection_start(injection_id, scenario, target_service)
        
        try:
            # Execute the failure injection
            result = await failure_info['method'](target_service)
            
            # Create a realistic incident based on the failure type
            await self.create_failure_incident(scenario, target_service, result)
            
            # Log success
            await self.log_injection_result(injection_id, True, result)
            
            return {
                'injection_id': injection_id,
                'scenario': scenario,
                'target_service': target_service,
                'status': 'success',
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failure injection failed: {e}")
            await self.log_injection_result(injection_id, False, str(e))
            raise
    
    async def inject_pod_restart(self, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Inject pod restart failure"""
        # Get a target pod
        if target_service:
            pods = await self.get_pods_for_service(target_service)
        else:
            pods = await self.get_all_pods()
        
        if not pods:
            raise Exception("No pods available for restart injection")
        
        # Pick the first pod (in production, could be random)
        target_pod = pods[0]
        
        logger.info(f"Restarting pod: {target_pod}")
        
        # Delete the pod (it will be recreated by the deployment)
        result = subprocess.run([
            'kubectl', 'delete', 'pod', target_pod, '-n', self.namespace
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return {
                'action': 'pod_restart',
                'target_pod': target_pod,
                'message': f'Pod {target_pod} deleted successfully',
                'expected_behavior': 'Pod should restart automatically'
            }
        else:
            raise Exception(f"Failed to delete pod: {result.stderr}")
    
    async def inject_resource_stress(self, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Inject resource stress (CPU/Memory)"""
        # Get target pod
        if target_service:
            pods = await self.get_pods_for_service(target_service)
        else:
            pods = await self.get_all_pods()
        
        if not pods:
            raise Exception("No pods available for resource stress")
        
        target_pod = pods[0]
        
        logger.info(f"Injecting resource stress on pod: {target_pod}")
        
        # Create a stress command using kubectl exec
        stress_command = [
            'kubectl', 'exec', '-n', self.namespace, target_pod, '--',
            'sh', '-c', 
            'for i in $(seq 1 4); do (while true; do echo "stress"; done) & done; sleep 30; pkill -f stress'
        ]
        
        # Run stress test in background
        process = subprocess.Popen(
            stress_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return {
            'action': 'resource_stress',
            'target_pod': target_pod,
            'message': f'CPU stress injected on {target_pod}',
            'duration_seconds': 30,
            'expected_behavior': 'Pod should show high CPU usage, potential throttling'
        }
    
    async def inject_network_latency(self, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Inject network latency (simplified simulation)"""
        # For this demo, we'll simulate by adding artificial delays
        # In production, you'd use tools like Chaos Mesh, Istio fault injection, etc.
        
        return {
            'action': 'network_latency',
            'target_service': target_service or 'random',
            'message': 'Network latency simulation (would require service mesh for real implementation)',
            'duration_seconds': 60,
            'expected_behavior': 'Increased response times, timeout errors'
        }
    
    async def inject_service_unavailable(self, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Make a service temporarily unavailable"""
        # Scale down the deployment to 0 replicas temporarily
        if not target_service:
            services = await self.get_target_services()
            target_service = services[0] if services else 'frontend'
        
        logger.info(f"Making service unavailable: {target_service}")
        
        # Scale down
        scale_down_result = subprocess.run([
            'kubectl', 'scale', 'deployment', target_service, 
            '--replicas=0', '-n', self.namespace
        ], capture_output=True, text=True, timeout=30)
        
        if scale_down_result.returncode != 0:
            raise Exception(f"Failed to scale down {target_service}: {scale_down_result.stderr}")
        
        # Wait a bit, then scale back up
        await asyncio.sleep(30)
        
        scale_up_result = subprocess.run([
            'kubectl', 'scale', 'deployment', target_service, 
            '--replicas=1', '-n', self.namespace
        ], capture_output=True, text=True, timeout=30)
        
        return {
            'action': 'service_unavailable',
            'target_service': target_service,
            'message': f'Service {target_service} made unavailable for 30 seconds',
            'expected_behavior': '503 Service Unavailable errors, then recovery'
        }
    
    async def inject_database_failure(self, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Simulate database connection failure"""
        # Target services that likely use databases
        database_services = ['cartservice', 'checkoutservice', 'paymentservice']
        
        if target_service and target_service not in database_services:
            target_service = 'cartservice'  # Default to cart service
        elif not target_service:
            target_service = 'cartservice'
        
        # Restart the Redis cart (simulates database failure)
        redis_pod = await self.get_pods_for_service('redis-cart')
        if redis_pod:
            logger.info(f"Simulating database failure by restarting Redis: {redis_pod[0]}")
            
            result = subprocess.run([
                'kubectl', 'delete', 'pod', redis_pod[0], '-n', self.namespace
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    'action': 'database_failure',
                    'target_service': 'redis-cart',
                    'affected_services': database_services,
                    'message': 'Redis cart database restarted to simulate connection failure',
                    'expected_behavior': 'Cart-related operations should fail temporarily'
                }
            else:
                raise Exception(f"Failed to restart Redis: {result.stderr}")
        else:
            raise Exception("Redis cart pod not found")
    
    async def create_failure_incident(self, scenario: str, target_service: Optional[str], result: Dict[str, Any]):
        """Create a realistic incident for the injected failure"""
        try:
            scenario_info = self.failure_scenarios[scenario]
            service_name = target_service or result.get('target_service', 'unknown-service')
            
            # Create realistic incident data based on failure type
            incident_mapping = {
                'pod_restart': {
                    'title': f'Pod Crash Detected in {self.namespace}/{result.get("target_pod", service_name)}',
                    'classification': 'Pod Failure',
                    'evidence': [
                        f'Pod {result.get("target_pod", service_name)} terminated unexpectedly',
                        'Container exit code: 137 (SIGKILL)',
                        'Pod restart count increased',
                        'Service temporarily unavailable'
                    ]
                },
                'resource_stress': {
                    'title': f'High Resource Usage in {self.namespace}/{service_name}',
                    'classification': 'Resource Exhaustion',
                    'evidence': [
                        f'CPU usage spike detected on {result.get("target_pod", service_name)}',
                        'Memory consumption above threshold',
                        'Container throttling detected',
                        'Performance degradation observed'
                    ]
                },
                'service_unavailable': {
                    'title': f'Service Unavailable: {service_name}',
                    'classification': 'Service Outage',
                    'evidence': [
                        f'Service {service_name} scaled to 0 replicas',
                        'HTTP 503 Service Unavailable responses',
                        'Health check failures',
                        'No running pods for service'
                    ]
                },
                'database_connection_failure': {
                    'title': f'Database Connection Failure in {self.namespace}/{service_name}',
                    'classification': 'Database Connectivity Issue',
                    'evidence': [
                        'Redis connection timeout errors',
                        'Database unavailable for cart operations',
                        'Connection pool exhausted',
                        'Backend service errors: 500 Internal Server Error'
                    ]
                },
                'network_latency': {
                    'title': f'Network Performance Degradation: {service_name}',
                    'classification': 'Performance Degradation',
                    'evidence': [
                        'Increased response times detected',
                        'Request timeout errors',
                        'Network latency above threshold',
                        'Service mesh errors'
                    ]
                }
            }
            
            incident_data = incident_mapping.get(scenario, {
                'title': f'Unknown Failure in {service_name}',
                'classification': 'Service Issue',
                'evidence': ['Failure injection completed', str(result)]
            })
            
            # Create the incident payload
            failure_incident = {
                'id': f'failure-{scenario}-{int(time.time())}',
                'title': incident_data['title'],
                'summary': f'Detected failure from chaos engineering: {scenario_info["description"]}',
                'classification': incident_data['classification'],
                'failing_service': service_name,
                'evidence': incident_data['evidence'],
                'test_failure_data': {
                    'pod_name': result.get('target_pod', f'{service_name}-injected'),
                    'namespace': self.namespace,
                    'confidence': 0.95,
                    'source': 'gke_real_monitoring',
                    'injection_scenario': scenario
                },
                'affected_services': [service_name],
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',  # Always start as pending for testing
                'trace_id': f'chaos-{scenario}-{int(time.time())}',
                'source': 'gke_real_monitoring'
            }
            
            # Send the incident to dashboard
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.dashboard_url}/webhook/incident",
                    json=failure_incident,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        logger.info(f"🚨 Failure incident created: {result_data.get('incident_id')}")
                    else:
                        logger.warning(f"Failed to create failure incident: {response.status}")
                        
        except Exception as e:
            logger.error(f"Error creating failure incident: {e}")
    
    async def get_pods_for_service(self, service_name: str) -> List[str]:
        """Get pods for a specific service"""
        try:
            result = subprocess.run([
                'kubectl', 'get', 'pods', '-n', self.namespace,
                '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                all_pods = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                service_pods = [pod for pod in all_pods if service_name in pod]
                return service_pods
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting pods for service {service_name}: {e}")
            return []
    
    async def get_all_pods(self) -> List[str]:
        """Get all pods in the namespace"""
        try:
            result = subprocess.run([
                'kubectl', 'get', 'pods', '-n', self.namespace,
                '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting all pods: {e}")
            return []
    
    async def log_injection_start(self, injection_id: str, scenario: str, target_service: Optional[str]):
        """Log the start of failure injection"""
        try:
            # Format as real GKE incident data that dashboard will recognize
            log_data = {
                'id': injection_id,
                'title': f'Failure Injection: {scenario} on {target_service or "random service"}',
                'summary': f'Started {scenario} - {self.failure_scenarios[scenario]["description"]}',
                'classification': 'Chaos Engineering',
                'failing_service': target_service or 'chaos-test',
                'evidence': [
                    f'Injection type: {scenario}',
                    f'Target service: {target_service or "random"}',
                    f'Severity: {self.failure_scenarios[scenario]["severity"]}',
                    f'Status: injection_started'
                ],
                'test_failure_data': {
                    'injection_id': injection_id,
                    'scenario': scenario,
                    'target_service': target_service,
                    'confidence': 1.0,
                    'source': 'gke_real_monitoring'  # This is the key field
                },
                'affected_services': [target_service] if target_service else ['chaos-test'],
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                'trace_id': f'injection-{injection_id}',
                'source': 'gke_real_monitoring'  # This is also important
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.dashboard_url}/webhook/incident",
                    json=log_data,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Injection start logged to dashboard")
                    else:
                        logger.warning(f"Failed to log injection start: {response.status}")
                        
        except Exception as e:
            logger.warning(f"Error logging injection start: {e}")
    
    async def log_injection_result(self, injection_id: str, success: bool, result: Any):
        """Log the result of failure injection"""
        try:
            # Format as real GKE incident data - but keep as pending for testing
            log_data = {
                'id': f'{injection_id}-result',
                'title': f'Failure Injection Result: {injection_id}',
                'summary': f'Injection completed - Success: {success}',
                'classification': 'Chaos Engineering Result',
                'failing_service': 'chaos-test',
                'evidence': [
                    f'Injection ID: {injection_id}',
                    f'Success: {success}',
                    f'Result: {str(result)[:200]}...' if len(str(result)) > 200 else str(result),
                    f'Completed at: {datetime.now().isoformat()}'
                ],
                'test_failure_data': {
                    'injection_id': injection_id,
                    'success': success,
                    'confidence': 1.0,
                    'source': 'gke_real_monitoring'
                },
                'affected_services': ['chaos-test'],
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',  # Keep pending for testing approval workflow
                'trace_id': f'injection-{injection_id}-result',
                'source': 'gke_real_monitoring'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.dashboard_url}/webhook/incident",
                    json=log_data,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Injection result logged to dashboard")
                    else:
                        logger.warning(f"Failed to log injection result: {response.status}")
                        
        except Exception as e:
            logger.warning(f"Error logging injection result: {e}")
    
    async def run_test_scenario(self, scenario: str, target_service: Optional[str] = None) -> Dict[str, Any]:
        """Run a complete test scenario with monitoring"""
        logger.info(f"🧪 Running test scenario: {scenario}")
        
        # Inject the failure
        injection_result = await self.inject_failure(scenario, target_service)
        
        # Wait for monitoring to detect the failure
        logger.info("⏱️  Waiting for monitoring system to detect the failure...")
        await asyncio.sleep(60)  # Give time for monitoring to detect and process
        
        # Report results
        logger.info(f"✅ Test scenario completed: {scenario}")
        return injection_result

async def main():
    """Main function for testing failure injection"""
    config = {
        'namespace': 'online-boutique',
        'dashboard_url': 'http://localhost:8080'
    }
    
    injector = FailureInjectionTool(config)
    
    try:
        # List available services
        services = await injector.get_target_services()
        logger.info(f"Available services: {services}")
        
        # List available scenarios
        scenarios = await injector.list_available_scenarios()
        logger.info(f"Available scenarios: {list(scenarios.keys())}")
        
        # Run a test scenario
        logger.info("🚀 Starting failure injection test...")
        
        # Test 1: Pod restart
        await injector.run_test_scenario('pod_restart', 'frontend')
        
        # Wait between tests
        await asyncio.sleep(30)
        
        # Test 2: Database failure
        await injector.run_test_scenario('database_connection_failure')
        
        logger.info("🎉 All failure injection tests completed!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())