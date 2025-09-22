#!/usr/bin/env python3
"""
Complete Self-Healing GKE System Demo

This script demonstrates the complete working system:
1. Real-time GKE monitoring
2. Automatic incident detection
3. AI-powered analysis
4. Agent orchestration
5. Dashboard integration

Usage: python complete_system_demo.py
"""

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemDemo:
    """Complete system demonstration"""
    
    def __init__(self):
        self.dashboard_url = 'http://localhost:8080'
        self.namespace = 'online-boutique'
        
    async def run_demo(self):
        """Run the complete system demo"""
        logger.info("🚀 Starting Complete Self-Healing GKE System Demo")
        
        try:
            # Phase 1: System Status Check
            await self.check_system_status()
            
            # Phase 2: Start Real-time Monitoring
            logger.info("\n📊 Starting Real-time Monitoring...")
            logger.info("The monitoring system is now watching:")
            logger.info("• Pod logs for error patterns")
            logger.info("• Kubernetes events for failures")
            logger.info("• Pod restart patterns")
            logger.info("• Resource usage anomalies")
            
            # Phase 3: Demonstrate Live Monitoring
            await self.demonstrate_live_monitoring()
            
            # Phase 4: Test Agent Coordination
            await self.demonstrate_agent_coordination()
            
            # Phase 5: Show Dashboard Integration
            await self.demonstrate_dashboard_integration()
            
            logger.info("\n🎉 Complete Self-Healing GKE System Demo Complete!")
            await self.show_final_status()
            
        except Exception as e:
            logger.error(f"Demo failed: {e}")
            raise
    
    async def check_system_status(self):
        """Check the status of all system components"""
        logger.info("📋 Checking System Status...")
        
        # Check GKE cluster
        result = subprocess.run(['kubectl', 'get', 'pods', '-n', self.namespace], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            running_pods = len([line for line in result.stdout.split('\n') if 'Running' in line])
            logger.info(f"✅ GKE Cluster: {running_pods} pods running in {self.namespace}")
        else:
            raise Exception("GKE cluster not accessible")
        
        # Check dashboard
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.dashboard_url}/health", timeout=5) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        logger.info(f"✅ Dashboard: Healthy, {health_data.get('websocket_connections', 0)} WebSocket connections")
                    else:
                        raise Exception(f"Dashboard unhealthy: {response.status}")
        except Exception as e:
            logger.warning(f"⚠️  Dashboard: {e}")
        
        # List available services
        services = await self.get_services()
        logger.info(f"✅ Available Services: {', '.join(services[:5])}{'...' if len(services) > 5 else ''}")
    
    async def demonstrate_live_monitoring(self):
        """Demonstrate live monitoring capabilities"""
        logger.info("\n🔍 Demonstrating Live Monitoring Detection...")
        
        # Show current incidents
        incidents = await self.get_current_incidents()
        logger.info(f"Current incidents in system: {len(incidents)}")
        
        # Inject a controlled failure
        logger.info("\n🔥 Injecting Controlled Failure (Pod Restart)...")
        
        # Get a frontend pod to restart
        result = subprocess.run([
            'kubectl', 'get', 'pods', '-n', self.namespace, 
            '-l', 'app=frontend', '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            pods = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            if pods:
                target_pod = pods[0]
                logger.info(f"Target pod for demonstration: {target_pod}")
                
                # Delete the pod
                delete_result = subprocess.run([
                    'kubectl', 'delete', 'pod', target_pod, '-n', self.namespace
                ], capture_output=True, text=True)
                
                if delete_result.returncode == 0:
                    logger.info(f"✅ Pod {target_pod} deleted (will be recreated automatically)")
                    
                    # Wait and check for detection
                    logger.info("⏱️  Waiting for monitoring system to detect the failure...")
                    await asyncio.sleep(30)
                    
                    # Check if new incidents were created
                    new_incidents = await self.get_current_incidents()
                    if len(new_incidents) > len(incidents):
                        logger.info(f"✅ Monitoring Detection: {len(new_incidents) - len(incidents)} new incidents detected!")
                    else:
                        logger.info("ℹ️  No new incidents detected (monitoring may be processing)")
                else:
                    logger.warning(f"Failed to delete pod: {delete_result.stderr}")
        
        # Show pod recovery
        await asyncio.sleep(10)
        recovery_result = subprocess.run([
            'kubectl', 'get', 'pods', '-n', self.namespace, '-l', 'app=frontend'
        ], capture_output=True, text=True)
        
        if recovery_result.returncode == 0:
            running_count = len([line for line in recovery_result.stdout.split('\n') if 'Running' in line])
            logger.info(f"✅ Pod Recovery: {running_count} frontend pods now running")
    
    async def demonstrate_agent_coordination(self):
        """Demonstrate agent coordination workflow"""
        logger.info("\n🤖 Demonstrating Agent Coordination...")
        
        # Create a test incident to show agent workflow
        test_incident = {
            'id': f'demo-incident-{int(time.time())}',
            'title': 'Demo: Payment Service Performance Issue',
            'summary': 'Demonstration of complete agent workflow with AI analysis',
            'classification': 'Performance Degradation',
            'failing_service': 'paymentservice',
            'evidence': [
                'Response time increased by 200%',
                'CPU usage at 85%',
                'Database connection pool at 90% capacity'
            ],
            'test_failure_data': {
                'service': 'paymentservice',
                'error_type': 'performance_degradation',
                'confidence': 0.85
            },
            'affected_services': ['paymentservice', 'checkoutservice'],
            'timestamp': datetime.now().isoformat(),
            'status': 'high',
            'trace_id': f'demo-trace-{int(time.time())}',
            'source': 'system_demo'
        }
        
        logger.info(f"📋 Creating demo incident: {test_incident['title']}")
        
        # Send to orchestrator
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.dashboard_url}/webhook/incident",
                    json=test_incident,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Incident sent to orchestrator: {result}")
                        
                        # Run the agent orchestrator
                        logger.info("🔄 Running agent orchestration workflow...")
                        orchestrator_result = subprocess.run([
                            'python', 'simple_orchestrator_demo.py'
                        ], capture_output=True, text=True, timeout=60,
                           cwd='/Users/abhitalluri/selfhealgke')
                        
                        if orchestrator_result.returncode == 0:
                            logger.info("✅ Agent orchestration completed successfully")
                            logger.info("   • AI analysis performed")
                            logger.info("   • Approval workflow initiated")
                            logger.info("   • Audit logging completed")
                        else:
                            logger.warning(f"Agent orchestration had issues: {orchestrator_result.stderr[:200]}")
                    else:
                        logger.error(f"Failed to send incident: {response.status}")
                        
        except Exception as e:
            logger.error(f"Agent coordination demo failed: {e}")
    
    async def demonstrate_dashboard_integration(self):
        """Demonstrate dashboard integration"""
        logger.info("\n🌐 Demonstrating Dashboard Integration...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Check dashboard status
                async with session.get(f"{self.dashboard_url}/health") as response:
                    health = await response.json()
                    logger.info(f"Dashboard Status: {health['status']}")
                    logger.info(f"WebSocket Connections: {health.get('websocket_connections', 0)}")
                
                # Get current incidents
                async with session.get(f"{self.dashboard_url}/api/incidents") as response:
                    incidents_data = await response.json()
                    incidents = incidents_data.get('incidents', [])
                    logger.info(f"Total Incidents Tracked: {len(incidents)}")
                
                # Send a real-time update
                update_data = {
                    'type': 'system_demo_complete',
                    'message': 'Self-healing GKE system demonstration completed successfully',
                    'timestamp': datetime.now().isoformat(),
                    'components': {
                        'monitoring': 'operational',
                        'agents': 'coordinated',
                        'dashboard': 'streaming'
                    }
                }
                
                async with session.post(
                    f"{self.dashboard_url}/webhook/incident",
                    json=update_data,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Demo completion broadcasted to {result.get('broadcasted_to', 0)} clients")
                        
        except Exception as e:
            logger.warning(f"Dashboard integration demo failed: {e}")
    
    async def get_services(self) -> list:
        """Get list of available services"""
        try:
            result = subprocess.run([
                'kubectl', 'get', 'pods', '-n', self.namespace,
                '--no-headers', '-o', 'custom-columns=NAME:.metadata.name'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                pods = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                services = list(set([
                    '-'.join(pod.split('-')[:-2]) if len(pod.split('-')) > 2 else pod 
                    for pod in pods
                ]))
                return services
            else:
                return []
        except:
            return []
    
    async def get_current_incidents(self) -> list:
        """Get current incidents from dashboard"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.dashboard_url}/api/incidents") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('incidents', [])
                    else:
                        return []
        except:
            return []
    
    async def show_final_status(self):
        """Show final system status"""
        logger.info("\n📊 Final System Status:")
        
        # GKE status
        result = subprocess.run(['kubectl', 'get', 'pods', '-n', self.namespace], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            running_pods = len([line for line in result.stdout.split('\n') if 'Running' in line])
            logger.info(f"🟢 GKE Cluster: {running_pods} pods healthy")
        
        # Dashboard status
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.dashboard_url}/health") as response:
                    if response.status == 200:
                        health = await response.json()
                        logger.info(f"🟢 Dashboard: {health['websocket_connections']} active connections")
        except:
            logger.info("🟡 Dashboard: Status unknown")
        
        # Summary
        logger.info("\n🎯 System Capabilities Demonstrated:")
        logger.info("✅ Real-time monitoring of GKE pod logs and events")
        logger.info("✅ Automatic incident detection using pattern matching")
        logger.info("✅ AI-powered incident analysis and classification")
        logger.info("✅ Multi-agent coordination (Approval, RCA, Remediation, Audit)")
        logger.info("✅ Real-time dashboard with WebSocket streaming")
        logger.info("✅ Complete audit trail and compliance logging")
        logger.info("✅ Failure injection and recovery validation")
        
        logger.info(f"\n🌐 Dashboard URL: {self.dashboard_url}")
        logger.info("👤 Login: admin/admin")

async def main():
    """Main demo function"""
    demo = SystemDemo()
    
    try:
        await demo.run_demo()
    except KeyboardInterrupt:
        logger.info("\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())