#!/usr/bin/env python3
"""
Approval Agent Integration Script

This script demonstrates the integration between the Approval Agent and the web dashboard,
showing how approval requests flow from the agent to the dashboard and back.
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

from approval_agent import ApprovalAgent, ApprovalDecision, ApprovalPriority
from config.approval_agent_config import get_development_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApprovalIntegrationDemo:
    """Demonstrates approval agent integration with web dashboard"""
    
    def __init__(self):
        self.agent = None
        self.running = False
        self.demo_scenarios = []
    
    async def initialize(self):
        """Initialize the approval agent"""
        logger.info("Initializing Approval Agent Integration Demo...")
        
        # Load configuration
        config = get_development_config()
        
        # Override some settings for demo
        config.dashboard.url = "http://localhost:8080"
        config.dashboard.api_key = "demo-api-key"
        config.timeouts.default_timeout_minutes = 5  # Shorter for demo
        
        # Create and initialize agent
        self.agent = ApprovalAgent(config.__dict__)
        await self.agent.initialize()
        
        logger.info("Approval Agent initialized successfully")
        
        # Setup demo scenarios
        self.setup_demo_scenarios()
    
    def setup_demo_scenarios(self):
        """Setup various demo scenarios"""
        self.demo_scenarios = [
            {
                'name': 'Payment Service Rollback',
                'incident_id': 'incident-payment-001',
                'trace_id': 'trace-payment-001',
                'title': 'Payment Service Critical Error - Rollback Required',
                'description': 'Payment service experiencing 90% error rate after deployment v2.1.0',
                'classification': 'Backend Error',
                'failing_service': 'payment-service',
                'summary': 'Database connection pool exhaustion causing payment failures',
                'evidence': [
                    'ERROR: Connection pool exhausted (max 100 connections)',
                    'Payment success rate dropped from 99.5% to 10%',
                    'Database CPU utilization at 95%',
                    'Average response time increased from 200ms to 5000ms'
                ],
                'proposed_action': {
                    'type': 'rollback',
                    'target': 'payment-service',
                    'from_version': 'v2.1.0',
                    'to_version': 'v2.0.5',
                    'description': 'Rollback payment service to last stable version',
                    'estimated_downtime': '2 minutes'
                },
                'risk_level': 'low',
                'estimated_duration': 120,
                'priority': ApprovalPriority.CRITICAL
            },
            {
                'name': 'Cart Service Scale Up',
                'incident_id': 'incident-cart-002',
                'trace_id': 'trace-cart-002',
                'title': 'Cart Service High Latency - Scale Up Required',
                'description': 'Cart service showing increased latency during peak traffic',
                'classification': 'Performance Issue',
                'failing_service': 'cart-service',
                'summary': 'High CPU utilization and memory pressure on cart service pods',
                'evidence': [
                    'Average response time: 2.5s (SLA: 500ms)',
                    'CPU utilization: 85% across all pods',
                    'Memory utilization: 90% across all pods',
                    'Queue depth increasing: 500+ pending requests'
                ],
                'proposed_action': {
                    'type': 'scale_up',
                    'target': 'cart-service',
                    'current_replicas': 3,
                    'target_replicas': 6,
                    'description': 'Scale cart service from 3 to 6 replicas',
                    'resource_impact': 'Additional 3 pods (1.5 CPU, 3GB RAM)'
                },
                'risk_level': 'low',
                'estimated_duration': 180,
                'priority': ApprovalPriority.HIGH
            },
            {
                'name': 'Database Connection Fix',
                'incident_id': 'incident-db-003',
                'trace_id': 'trace-db-003',
                'title': 'Database Connection Pool Configuration Update',
                'description': 'Multiple services experiencing database connection timeouts',
                'classification': 'Configuration Issue',
                'failing_service': 'database-proxy',
                'summary': 'Database connection pool size insufficient for current load',
                'evidence': [
                    'Connection timeout errors across 5 services',
                    'Database proxy connection pool at 100% utilization',
                    'Queue wait time: 10+ seconds',
                    'Failed requests: 15% of total traffic'
                ],
                'proposed_action': {
                    'type': 'config_update',
                    'target': 'database-proxy',
                    'parameter': 'max_connections',
                    'current_value': 100,
                    'new_value': 200,
                    'description': 'Increase database connection pool size',
                    'requires_restart': True
                },
                'risk_level': 'medium',
                'estimated_duration': 300,
                'priority': ApprovalPriority.MEDIUM
            }
        ]
    
    async def run_demo_scenario(self, scenario: Dict[str, Any]):
        """Run a single demo scenario"""
        logger.info(f"Running demo scenario: {scenario['name']}")
        
        # Create approval callback
        async def approval_callback(decision: ApprovalDecision):
            logger.info(f"Approval decision received for {scenario['name']}: {decision.decision}")
            
            if decision.decision == 'approve':
                logger.info(f"✅ Executing remediation: {scenario['proposed_action']['description']}")
                await self.simulate_remediation_execution(scenario, decision)
            else:
                logger.warning(f"❌ Remediation rejected: {decision.reason}")
                await self.handle_rejection(scenario, decision)
        
        # Submit approval request
        try:
            request_id = await self.agent.request_approval(
                incident_id=scenario['incident_id'],
                trace_id=scenario['trace_id'],
                title=scenario['title'],
                description=scenario['description'],
                classification=scenario['classification'],
                failing_service=scenario['failing_service'],
                summary=scenario['summary'],
                evidence=scenario['evidence'],
                proposed_action=scenario['proposed_action'],
                risk_level=scenario['risk_level'],
                estimated_duration=scenario['estimated_duration'],
                priority=scenario['priority'],
                callback=approval_callback
            )
            
            logger.info(f"📋 Approval request submitted: {request_id}")
            logger.info(f"🌐 Check the web dashboard at http://localhost:8080 to approve/reject")
            
            return request_id
            
        except Exception as e:
            logger.error(f"Failed to submit approval request for {scenario['name']}: {e}")
            return None
    
    async def simulate_remediation_execution(self, scenario: Dict[str, Any], decision: ApprovalDecision):
        """Simulate executing the approved remediation"""
        action = scenario['proposed_action']
        
        logger.info(f"🔧 Starting remediation execution...")
        logger.info(f"   Action: {action['type']}")
        logger.info(f"   Target: {action['target']}")
        logger.info(f"   Description: {action['description']}")
        
        # Simulate execution time
        execution_time = scenario['estimated_duration']
        logger.info(f"⏳ Estimated execution time: {execution_time} seconds")
        
        # Simulate progress updates
        for i in range(0, execution_time, 30):
            await asyncio.sleep(1)  # Shortened for demo
            progress = min(100, (i / execution_time) * 100)
            logger.info(f"   Progress: {progress:.0f}%")
        
        logger.info(f"✅ Remediation completed successfully!")
        logger.info(f"📊 Verifying system health...")
        
        # Simulate verification
        await asyncio.sleep(2)
        logger.info(f"✅ System health verification passed")
        
        # Log completion
        await self.agent._log_audit_event('remediation_completed', {
            'incident_id': scenario['incident_id'],
            'request_id': decision.request_id,
            'action_type': action['type'],
            'target': action['target'],
            'approved_by': decision.user_name,
            'execution_duration': execution_time,
            'success': True
        })
    
    async def handle_rejection(self, scenario: Dict[str, Any], decision: ApprovalDecision):
        """Handle rejected approval"""
        logger.warning(f"🚫 Remediation rejected by {decision.user_name}")
        logger.warning(f"   Reason: {decision.reason}")
        logger.info(f"📝 Incident {scenario['incident_id']} requires manual intervention")
        
        # Log rejection
        await self.agent._log_audit_event('remediation_rejected', {
            'incident_id': scenario['incident_id'],
            'request_id': decision.request_id,
            'rejected_by': decision.user_name,
            'rejection_reason': decision.reason
        })
    
    async def run_interactive_demo(self):
        """Run interactive demo with user input"""
        logger.info("🚀 Starting Interactive Approval Demo")
        logger.info("=" * 60)
        
        while self.running:
            print("\nAvailable Demo Scenarios:")
            print("=" * 40)
            
            for i, scenario in enumerate(self.demo_scenarios, 1):
                print(f"{i}. {scenario['name']}")
                print(f"   Priority: {scenario['priority'].value.upper()}")
                print(f"   Service: {scenario['failing_service']}")
                print(f"   Action: {scenario['proposed_action']['type']}")
                print()
            
            print("Commands:")
            print("1-3: Run demo scenario")
            print("s: Show approval statistics")
            print("l: List active requests")
            print("q: Quit")
            print()
            
            try:
                choice = input("Enter your choice: ").strip().lower()
                
                if choice == 'q':
                    break
                elif choice == 's':
                    await self.show_statistics()
                elif choice == 'l':
                    await self.list_active_requests()
                elif choice.isdigit():
                    scenario_index = int(choice) - 1
                    if 0 <= scenario_index < len(self.demo_scenarios):
                        await self.run_demo_scenario(self.demo_scenarios[scenario_index])
                    else:
                        print("Invalid scenario number")
                else:
                    print("Invalid choice")
                
                # Small delay to prevent overwhelming output
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in interactive demo: {e}")
    
    async def show_statistics(self):
        """Show approval statistics"""
        logger.info("📊 Approval Statistics")
        logger.info("-" * 30)
        
        try:
            stats = await self.agent.get_approval_statistics()
            
            print(f"Total Requests: {stats['total_requests']}")
            print(f"Approved: {stats['approved']}")
            print(f"Rejected: {stats['rejected']}")
            print(f"Pending: {stats['pending']}")
            print(f"Expired: {stats['expired']}")
            print(f"Approval Rate: {stats['approval_rate']:.1f}%")
            print(f"Average Response Time: {stats['average_response_time_seconds']:.1f}s")
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
    
    async def list_active_requests(self):
        """List active approval requests"""
        logger.info("📋 Active Approval Requests")
        logger.info("-" * 35)
        
        try:
            active_requests = await self.agent.list_active_requests()
            
            if not active_requests:
                print("No active requests")
                return
            
            for request in active_requests:
                print(f"Request ID: {request.request_id}")
                print(f"  Incident: {request.incident_id}")
                print(f"  Title: {request.title}")
                print(f"  Priority: {request.priority.value}")
                print(f"  Created: {request.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Expires: {request.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
        except Exception as e:
            logger.error(f"Failed to list active requests: {e}")
    
    async def run_automated_demo(self):
        """Run automated demo with all scenarios"""
        logger.info("🤖 Starting Automated Demo")
        logger.info("=" * 50)
        
        for i, scenario in enumerate(self.demo_scenarios, 1):
            logger.info(f"Running scenario {i}/{len(self.demo_scenarios)}: {scenario['name']}")
            
            request_id = await self.run_demo_scenario(scenario)
            
            if request_id:
                logger.info(f"Waiting for approval decision...")
                
                # Wait for a reasonable time for manual approval
                timeout = 60  # 1 minute timeout for demo
                start_time = datetime.now()
                
                while (datetime.now() - start_time).total_seconds() < timeout:
                    request = await self.agent.get_request_status(request_id)
                    
                    if request and request.status.value != 'pending':
                        logger.info(f"Decision received: {request.status.value}")
                        break
                    
                    await asyncio.sleep(5)
                else:
                    logger.warning(f"Timeout waiting for approval decision")
            
            # Delay between scenarios
            if i < len(self.demo_scenarios):
                logger.info("Waiting before next scenario...")
                await asyncio.sleep(10)
        
        logger.info("🏁 Automated demo completed")
    
    async def start(self, mode='interactive'):
        """Start the demo"""
        self.running = True
        
        try:
            await self.initialize()
            
            logger.info(f"🌐 Web dashboard should be running at: http://localhost:8080")
            logger.info(f"🔑 Demo credentials: admin/admin")
            logger.info("")
            
            if mode == 'interactive':
                await self.run_interactive_demo()
            elif mode == 'automated':
                await self.run_automated_demo()
            else:
                logger.error(f"Unknown mode: {mode}")
                
        except KeyboardInterrupt:
            logger.info("Demo interrupted by user")
        except Exception as e:
            logger.error(f"Demo error: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🧹 Cleaning up...")
        
        if self.agent:
            await self.agent.cleanup()
        
        self.running = False
        logger.info("Cleanup completed")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Approval Agent Integration Demo')
    parser.add_argument(
        '--mode',
        choices=['interactive', 'automated'],
        default='interactive',
        help='Demo mode (default: interactive)'
    )
    
    args = parser.parse_args()
    
    # Setup signal handlers
    demo = ApprovalIntegrationDemo()
    
    def signal_handler(signum, frame):
        logger.info("Received interrupt signal, shutting down...")
        demo.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run demo
    await demo.start(mode=args.mode)


if __name__ == "__main__":
    asyncio.run(main())