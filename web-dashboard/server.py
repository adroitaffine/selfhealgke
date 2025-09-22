#!/usr/bin/env python3
"""
Simple web server for the GKE Auto-Heal Agent Dashboard
Serves the static web dashboard files and provides WebSocket endpoints
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Set, Any
from dotenv import load_dotenv

# Add parent directory to Python path for agent imports
sys.path.append(str(Path(__file__).parent.parent))

import websockets
from aiohttp import web
from aiohttp.web import Request, Response
import aiohttp

# Load environment variables
load_dotenv()
from aiohttp import web, web_ws
from aiohttp.web import Application, Request, Response, WebSocketResponse
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardServer:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.app = None
        self.websocket_connections: Set[WebSocketResponse] = set()
        self.authenticated_sessions: Dict[str, dict] = {}
        self.secret_key = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))
        
        # Store incidents in memory (in production, use database)
        self.incidents: Dict[str, dict] = {}
        
        # Demo credentials (in production, use proper authentication)
        self.demo_users = {
            'admin': {
                'password': 'admin',  # In production, use hashed passwords
                'name': 'System Administrator',
                'role': 'admin',
                'id': 1
            }
        }

    def create_app(self) -> Application:
        """Create and configure the aiohttp application"""
        app = web.Application()
        
        # Static file routes
        dashboard_dir = Path(__file__).parent
        app.router.add_static('/static/', dashboard_dir, name='static')
        app.router.add_get('/', self.serve_index)
        
        # API routes
        app.router.add_get('/health', self.handle_health_check)  # Add health check
        app.router.add_post('/api/auth/login', self.handle_login)
        app.router.add_post('/api/auth/logout', self.handle_logout)
        app.router.add_post('/api/approval/request', self.handle_approval_request)
        app.router.add_post('/api/approval/decision', self.handle_approval_decision)
        app.router.add_post('/api/incidents/approve', self.handle_approval)  # Keep for backward compatibility
        app.router.add_get('/api/incidents', self.handle_get_incidents)
        app.router.add_get('/ws', self.handle_websocket)
        
        # Webhook endpoint for receiving incident notifications
        app.router.add_post('/webhook/incident', self.handle_incident_webhook)
        
        # CORS middleware for development
        app.middlewares.append(self.cors_middleware)
        
        return app

    async def serve_index(self, request: Request) -> Response:
        """Serve the main dashboard index.html"""
        return web.FileResponse(Path(__file__).parent / 'index.html')
    
    async def handle_health_check(self, request: Request) -> Response:
        """Health check endpoint for testing"""
        return web.json_response({
            'status': 'healthy',
            'service': 'dashboard',
            'timestamp': datetime.now().isoformat(),
            'websocket_connections': len(self.websocket_connections)
        })

    @web.middleware
    async def cors_middleware(self, request: Request, handler):
        """CORS middleware for development"""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    async def handle_login(self, request: Request) -> Response:
        """Handle user authentication"""
        try:
            data = await request.json()
            username = data.get('username')
            password = data.get('password')
            
            # Validate credentials
            if username in self.demo_users:
                user_data = self.demo_users[username]
                if user_data['password'] == password:
                    # Generate session token
                    session_token = secrets.token_hex(32)
                    
                    # Store session
                    self.authenticated_sessions[session_token] = {
                        'user': user_data,
                        'created_at': datetime.now().isoformat(),
                        'last_activity': datetime.now().isoformat()
                    }
                    
                    return web.json_response({
                        'success': True,
                        'token': session_token,
                        'user': {
                            'id': user_data['id'],
                            'username': username,
                            'name': user_data['name'],
                            'role': user_data['role']
                        }
                    })
            
            return web.json_response({
                'success': False,
                'message': 'Invalid credentials'
            }, status=401)
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Authentication error'
            }, status=500)

    async def handle_logout(self, request: Request) -> Response:
        """Handle user logout"""
        try:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                if token in self.authenticated_sessions:
                    del self.authenticated_sessions[token]
            
            return web.json_response({'success': True})
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Logout error'
            }, status=500)
    
    async def handle_approval_request(self, request: Request) -> Response:
        """Handle new approval request submission"""
        try:
            data = await request.json()
            
            # Validate required fields
            required_fields = ['incident_id', 'title', 'description', 'proposed_action']
            for field in required_fields:
                if field not in data:
                    return web.json_response({
                        'success': False,
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            # Create approval request
            approval_request = {
                'request_id': f"req-{int(time.time())}",
                'incident_id': data['incident_id'],
                'title': data['title'],
                'description': data['description'],
                'classification': data.get('classification', 'Unknown'),
                'failing_service': data.get('failing_service'),
                'evidence': data.get('evidence', []),
                'proposed_action': data['proposed_action'],
                'priority': data.get('priority', 'medium'),
                'trace_id': data.get('trace_id'),
                'submitted_by': data.get('submitted_by', 'system'),
                'submitted_at': datetime.now().isoformat(),
                'status': 'pending',
                'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()  # 1 hour default
            }
            
            # Store the approval request (in production, use database)
            if not hasattr(self, 'approval_requests'):
                self.approval_requests = {}
            self.approval_requests[approval_request['request_id']] = approval_request
            
            # Broadcast to WebSocket clients
            await self.broadcast_to_websockets({
                'type': 'new_approval_request',
                'request': approval_request,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Approval request {approval_request['request_id']} created for incident {data['incident_id']}")
            
            return web.json_response({
                'success': True,
                'message': 'Approval request submitted successfully',
                'request_id': approval_request['request_id'],
                'request': approval_request
            })
            
        except Exception as e:
            logger.error(f"Approval request error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Failed to submit approval request'
            }, status=500)
    
    async def handle_approval_decision(self, request: Request) -> Response:
        """Handle approval decision submission"""
        try:
            data = await request.json()
            
            # Validate required fields
            required_fields = ['request_id', 'decision', 'user_id', 'user_name']
            for field in required_fields:
                if field not in data:
                    return web.json_response({
                        'success': False,
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            request_id = data['request_id']
            decision = data['decision']
            
            # Validate decision value
            if decision not in ['approve', 'reject', 'investigate']:
                return web.json_response({
                    'success': False,
                    'message': 'Invalid decision. Must be: approve, reject, or investigate'
                }, status=400)
            
            # Check if approval request exists
            if not hasattr(self, 'approval_requests') or request_id not in self.approval_requests:
                return web.json_response({
                    'success': False,
                    'message': 'Approval request not found'
                }, status=404)
            
            approval_request = self.approval_requests[request_id]
            
            # Check if request is still pending
            if approval_request['status'] != 'pending':
                return web.json_response({
                    'success': False,
                    'message': f'Approval request is already {approval_request["status"]}'
                }, status=409)
            
            # Update approval request with decision
            approval_request.update({
                'status': decision,
                'decision': decision,
                'decided_by': data['user_name'],
                'decided_by_id': data['user_id'],
                'decided_at': datetime.now().isoformat(),
                'reason': data.get('reason', ''),
                'signature': data.get('signature')  # For cryptographic verification
            })
            
            # If there's an associated incident, update it too
            incident_id = approval_request.get('incident_id')
            if incident_id and incident_id in self.incidents:
                incident_status = 'approved' if decision == 'approve' else 'rejected' if decision == 'reject' else 'investigating'
                self.incidents[incident_id]['status'] = incident_status
                self.incidents[incident_id]['updated_at'] = datetime.now().isoformat()
                self.incidents[incident_id]['approval_decision'] = {
                    'decision': decision,
                    'decided_by': data['user_name'],
                    'decided_at': datetime.now().isoformat(),
                    'reason': data.get('reason', '')
                }
            
            # Broadcast decision to WebSocket clients
            await self.broadcast_to_websockets({
                'type': 'approval_decision',
                'request_id': request_id,
                'decision': decision,
                'request': approval_request,
                'incident_id': incident_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Log audit event
            logger.info(f"Approval decision: {request_id} {decision} by {data['user_name']}")
            
            return web.json_response({
                'success': True,
                'message': f'Approval request {decision}d successfully',
                'request_id': request_id,
                'decision': decision,
                'request': approval_request
            })
            
        except Exception as e:
            logger.error(f"Approval decision error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Failed to process approval decision'
            }, status=500)
    
    async def handle_approval(self, request: Request) -> Response:
        """Handle incident approval/rejection/investigation"""
        try:
            # For demo, allow approval without strict authentication
            # In production, add proper authentication
            
            data = await request.json()
            incident_id = data.get('incident_id')
            action = data.get('action')  # 'approve', 'reject', or 'investigate'
            
            if not incident_id or not action:
                return web.json_response({
                    'success': False,
                    'message': 'Missing incident_id or action'
                }, status=400)
            
            if incident_id not in self.incidents:
                return web.json_response({
                    'success': False,
                    'message': 'Incident not found'
                }, status=404)
            
            # Handle investigation action differently
            if action == 'investigate':
                logger.info(f"Starting RCA investigation for incident {incident_id}")
                
                # Start RCA investigation
                investigation_result = await self._start_rca_investigation(incident_id)
                
                # Update incident with investigation details
                self.incidents[incident_id]['investigation'] = investigation_result
                self.incidents[incident_id]['status'] = 'investigating'
                self.incidents[incident_id]['updated_at'] = datetime.now().isoformat()
                
                # Broadcast investigation update
                await self.broadcast_to_websockets({
                    'type': 'investigation_started',
                    'incident_id': incident_id,
                    'investigation': investigation_result,
                    'incident': self.incidents[incident_id],
                    'timestamp': datetime.now().isoformat()
                })
                
                return web.json_response({
                    'success': True,
                    'message': f'Investigation started for incident {incident_id}',
                    'investigation': investigation_result
                })
            else:
                # Handle approve/reject
                self.incidents[incident_id]['status'] = action
                self.incidents[incident_id]['updated_at'] = datetime.now().isoformat()
                
                # Log the approval decision
                logger.info(f"Incident {incident_id} {action} by user")
                
                # Broadcast to all connected WebSocket clients
                await self.broadcast_to_websockets({
                    'type': 'approval_decision',
                    'incident_id': incident_id,
                    'action': action,
                    'incident': self.incidents[incident_id],
                    'timestamp': datetime.now().isoformat()
                })
                
                return web.json_response({
                    'success': True,
                    'message': f'Incident {action} successfully'
                })
                
                return web.json_response({
                    'success': True,
                    'message': f'Incident {action} successfully'
                })
            
        except Exception as e:
            logger.error(f"Approval error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Approval processing error'
            }, status=500)
    
    async def _start_rca_investigation(self, incident_id: str) -> Dict[str, Any]:
        """Start RCA investigation using the A2A RCA service"""
        try:
            incident = self.incidents.get(incident_id)
            if not incident:
                return {
                    'status': 'error',
                    'message': 'Incident not found',
                    'analysis': None
                }

            # Use direct HTTP call to A2A service REST endpoint
            rca_service_url = os.getenv('RCA_A2A_SERVICE_URL', 'http://localhost:8001')
            
            # Make direct HTTP call to A2A service REST endpoint
            logger.info(f"Calling RCA A2A service REST endpoint at {rca_service_url}/analyze for incident {incident_id}")

            async with aiohttp.ClientSession() as session:
                # Prepare failure payload for REST request
                failure_payload = {
                    "test_title": incident.get('title', 'Unknown Incident'),
                    "status": incident.get('status', 'failed'),
                    "error_message": incident.get('summary', 'No description'),
                    "error_stack": "",
                    "error_type": "IncidentError",
                    "retries": 0,
                    "trace_id": incident.get('trace_id', f"trace-{incident_id}"),
                    "timestamp": incident.get('timestamp')
                }

                rest_payload = {
                    "failure_payload": failure_payload
                }
                
                try:
                    async with session.post(
                        f"{rca_service_url}/analyze",
                        json=rest_payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response_text = await response.text()
                        logger.info(f"RCA A2A service response status: {response.status}")
                        
                        if response.status == 200:
                            response_data = await response.json()
                            
                            if response_data.get('status') == 'completed':
                                analysis_data = response_data
                                
                                return {
                                    'status': 'completed',
                                    'message': 'RCA investigation completed via A2A REST',
                                    'analysis': {
                                        'classification': analysis_data.get('classification', 'Unknown'),
                                        'failing_service': analysis_data.get('failing_service'),
                                        'summary': analysis_data.get('summary', 'No summary available'),
                                        'confidence_score': analysis_data.get('confidence_score', 0.0),
                                        'evidence_count': analysis_data.get('evidence_count', 0),
                                        'analysis_duration': analysis_data.get('analysis_duration', 0.0),
                                        'trace_id': analysis_data.get('trace_id', incident.get('trace_id'))
                                    },
                                    'investigation_id': f"inv-{int(time.time())}",
                                    'completed_at': datetime.now().isoformat(),
                                    'a2a_response': analysis_data
                                }
                            else:
                                error_msg = response_data.get('error', 'Unknown A2A error')
                                logger.error(f"RCA A2A service call failed: {error_msg}")
                                return {
                                    'status': 'error',
                                    'message': f'A2A service error: {error_msg}',
                                    'analysis': None,
                                    'error_details': str(response_data)
                                }
                        else:
                            logger.error(f"RCA A2A service HTTP error: {response.status} - {response_text}")
                            return {
                                'status': 'error',
                                'message': f'A2A service HTTP error: {response.status}',
                                'analysis': None,
                                'error_details': response_text
                            }
                            
                except asyncio.TimeoutError:
                    logger.error("Timeout calling RCA A2A service")
                    return {
                        'status': 'error',
                        'message': 'Timeout calling A2A service',
                        'analysis': None
                    }
                except Exception as e:
                    logger.error(f"Error calling RCA A2A service: {e}")
                    return {
                        'status': 'error',
                        'message': f'A2A service call error: {str(e)}',
                        'analysis': None,
                        'error_details': str(e)
                    }

        except Exception as e:
            logger.error(f"RCA A2A investigation failed for incident {incident_id}: {e}")
            # Fallback to direct RCA agent call if A2A fails
            logger.info(f"Falling back to direct RCA agent call for incident {incident_id}")
            return await self._start_rca_investigation_fallback(incident_id)

    async def _start_rca_investigation_fallback(self, incident_id: str) -> Dict[str, Any]:
        """Fallback RCA investigation using direct RCA agent (legacy method)"""
        try:
            incident = self.incidents.get(incident_id)
            if not incident:
                return {
                    'status': 'error',
                    'message': 'Incident not found',
                    'analysis': None
                }

            # Import and initialize RCA agent directly
            from agents.rca_agent import RCAAgent, AgentConfig, create_mock_failure_payload

            # Create RCA agent config with environment variables
            rca_config = AgentConfig(
                agent_id=f"rca-investigation-{incident_id}",
                agent_type="rca",
                capabilities=[
                    "telemetry_analysis",
                    "topology_discovery",
                    "failure_classification",
                    "gemini_integration"
                ],
                heartbeat_interval=30,
                health_check_interval=60,
                max_concurrent_tasks=5,
                metadata={
                    'gemini_api_key': os.getenv('GEMINI_API_KEY'),
                    'project_id': os.getenv('GCP_PROJECT_ID', 'default-project'),
                    'cluster_name': os.getenv('GCP_CLUSTER_NAME', 'default-cluster'),
                    'cluster_zone': os.getenv('GCP_CLUSTER_ZONE', 'us-central1-a'),
                    'namespace': os.getenv('GCP_NAMESPACE', 'default'),
                    'telemetry_window_seconds': int(os.getenv('RCA_AGENT_TELEMETRY_WINDOW_SECONDS', '300')),
                    'confidence_threshold': float(os.getenv('RCA_AGENT_CONFIDENCE_THRESHOLD', '0.7')),
                    'topology_cache_ttl': int(os.getenv('RCA_AGENT_TOPOLOGY_CACHE_TTL', '3600'))
                }
            )

            # Initialize RCA agent
            rca_agent = RCAAgent(rca_config)
            await rca_agent.initialize()

            # Create failure payload from incident data
            failure_payload = create_mock_failure_payload(
                test_title=incident.get('title', 'Unknown Incident'),
                error_message=incident.get('summary', 'No description'),
                trace_id=incident.get('trace_id', f"trace-{incident_id}")
            )

            # Run RCA analysis
            logger.info(f"Running fallback RCA analysis for incident {incident_id}")
            analysis_result = await rca_agent.analyze_failure(failure_payload)

            # Clean up
            await rca_agent.cleanup()

            return {
                'status': 'completed',
                'message': 'RCA investigation completed (fallback)',
                'analysis': {
                    'classification': analysis_result.classification.value,
                    'failing_service': analysis_result.failing_service,
                    'summary': analysis_result.summary,
                    'confidence_score': analysis_result.confidence_score,
                    'evidence_count': len(analysis_result.evidence),
                    'analysis_duration': analysis_result.analysis_duration,
                    'trace_id': analysis_result.trace_id
                },
                'investigation_id': f"inv-{int(time.time())}",
                'completed_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"RCA fallback investigation failed for incident {incident_id}: {e}")
            return {
                'status': 'error',
                'message': f'Investigation failed: {str(e)}',
                'analysis': None,
                'error_details': str(e)
            }

    async def handle_get_incidents(self, request: Request) -> Response:
        """Get list of incidents"""
        try:
            # For testing, allow access without authentication
            # In production, uncomment the auth check below
            # if not await self.verify_auth(request):
            #     return web.json_response({
            #         'success': False,
            #         'message': 'Unauthorized'
            #     }, status=401)
            
            # Return actual stored incidents
            incidents_list = list(self.incidents.values())
            
            # Sort by timestamp (newest first)
            incidents_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return web.json_response({
                'success': True,
                'incidents': incidents_list
            })
            
        except Exception as e:
            logger.error(f"Get incidents error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Failed to fetch incidents'
            }, status=500)

    async def handle_websocket(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connections for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Add to active connections
        self.websocket_connections.add(ws)
        logger.info(f"WebSocket client connected. Total connections: {len(self.websocket_connections)}")
        
        try:
            # Send welcome message
            await ws.send_str(json.dumps({
                'type': 'connection_established',
                'timestamp': datetime.now().isoformat()
            }))
            
            # Handle incoming messages
            async for msg in ws:
                if msg.type == web_ws.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_websocket_message(ws, data)
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON received from WebSocket client")
                elif msg.type == web_ws.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Remove from active connections
            self.websocket_connections.discard(ws)
            logger.info(f"WebSocket client disconnected. Total connections: {len(self.websocket_connections)}")
        
        return ws

    async def handle_websocket_message(self, ws: WebSocketResponse, data: dict):
        """Handle incoming WebSocket messages"""
        message_type = data.get('type')
        
        if message_type == 'ping':
            await ws.send_str(json.dumps({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            }))
        elif message_type == 'authenticate':
            # Handle WebSocket authentication
            token = data.get('token')
            if token and token in self.authenticated_sessions:
                await ws.send_str(json.dumps({
                    'type': 'authenticated',
                    'status': 'success',
                    'timestamp': datetime.now().isoformat()
                }))
                logger.info("WebSocket client authenticated")
            else:
                await ws.send_str(json.dumps({
                    'type': 'authentication_failed',
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                }))
        elif message_type == 'subscribe':
            # Handle subscription to specific incident types
            channels = data.get('channels', [])
            logger.info(f"Client subscribed to: {channels}")
            await ws.send_str(json.dumps({
                'type': 'subscribed',
                'channels': channels,
                'timestamp': datetime.now().isoformat()
            }))
        else:
            logger.warning(f"Unknown WebSocket message type: {message_type}")

    async def handle_incident_webhook(self, request: Request) -> Response:
        """Handle incoming incident notifications from Playwright tests"""
        try:
            data = await request.json()
            
            # Debug logging to see what data is received
            logger.info(f"Webhook received data: {json.dumps(data, indent=2)}")
            
            # Validate webhook signature (in production)
            # webhook_signature = request.headers.get('X-Webhook-Signature')
            # if not self.verify_webhook_signature(data, webhook_signature):
            #     return web.json_response({'error': 'Invalid signature'}, status=401)
            
            incident_data = data.get('incident', {})
            logger.info(f"Received incident webhook: {incident_data.get('title', 'Unknown')}")
            
            # Process the incident data
            incident = self.process_incident_data(data)
            
            # Store the incident
            self.incidents[incident['id']] = incident
            
            # Broadcast to all WebSocket clients immediately
            await self.broadcast_to_websockets({
                'type': 'new_incident',
                'incident': incident,
                'timestamp': datetime.now().isoformat(),
                'source': data.get('source', 'unknown')
            })
            
            # Also broadcast as incident update for any existing clients
            await self.broadcast_to_websockets({
                'type': 'incident_update',
                'incident_id': incident['id'],
                'update': incident,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Incident {incident['id']} broadcasted to {len(self.websocket_connections)} WebSocket clients")
            
            return web.json_response({
                'success': True,
                'message': 'Incident received and processed',
                'incident_id': incident['id'],
                'broadcasted_to': len(self.websocket_connections)
            })
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.json_response({
                'success': False,
                'message': 'Webhook processing error'
            }, status=500)
    
    def _determine_action_type(self, webhook_data: dict) -> str:
        """Determine the appropriate action type based on incident data"""
        title = webhook_data.get('title', '').lower()
        severity = webhook_data.get('status', 'medium').lower()
        
        if 'restart' in title or 'crash' in title:
            return 'restart_pod'
        elif 'memory' in title or 'oom' in title:
            return 'scale_resources'
        elif 'database' in title or 'connection' in title:
            return 'check_connectivity'
        elif 'http' in title or 'server error' in title:
            return 'investigate_service'
        elif severity == 'critical':
            return 'immediate_escalation'
        else:
            return 'investigate'
    
    def _generate_action_description(self, webhook_data: dict) -> str:
        """Generate action description based on incident data"""
        action_type = self._determine_action_type(webhook_data)
        service = webhook_data.get('failing_service', 'service')
        
        action_descriptions = {
            'restart_pod': f'Restart {service} pod to recover from crash or failure',
            'scale_resources': f'Scale up {service} resources to prevent OOM issues',
            'check_connectivity': f'Verify database/service connectivity for {service}',
            'investigate_service': f'Investigate HTTP errors and service health for {service}',
            'immediate_escalation': f'Critical issue requiring immediate attention for {service}',
            'investigate': f'Investigate and analyze {service} for potential issues'
        }
        
        return action_descriptions.get(action_type, f'Manual investigation required for {service}')

    def process_incident_data(self, data: dict) -> dict:
        """Process incoming webhook data into incident format"""
        webhook_data = data.get('incident', data)
        source = data.get('source', 'unknown')
        
        logger.info(f"Processing incident data - source: {source}")
        logger.info(f"Webhook data keys: {list(webhook_data.keys())}")
        logger.info(f"Has ai_analysis: {'ai_analysis' in webhook_data}")
        
        # Check if this is orchestrator data with AI analysis
        if source == 'complete_orchestrator_with_ai' or 'ai_analysis' in webhook_data:
            logger.info("Processing as AI-enhanced orchestrator incident data")
            # AI-enhanced orchestrator incident data
            ai_analysis = webhook_data.get('ai_analysis', {})
            return {
                'id': webhook_data.get('id', f"incident-{int(time.time())}"),
                'title': webhook_data.get('title', 'AI-Analyzed Incident'),
                'classification': ai_analysis.get('classification', webhook_data.get('classification', 'Backend Error')),
                'failing_service': webhook_data.get('failing_service', 'unknown-service'),
                'summary': f"AI Analysis: {ai_analysis.get('root_cause', webhook_data.get('summary', 'Unknown issue'))}",
                'evidence': webhook_data.get('evidence', [
                    f"AI Confidence: {ai_analysis.get('confidence', 0.7):.1%}",
                    f"Recommended Action: {ai_analysis.get('remediation_strategy', 'investigate')}",
                    f"Risk Level: {ai_analysis.get('risk_level', 'medium')}",
                    f"Analysis: {ai_analysis.get('analysis_reasoning', 'AI analysis completed')}"
                ]),
                'proposed_action': {
                    'type': ai_analysis.get('remediation_strategy', 'investigate'),
                    'target': webhook_data.get('failing_service', 'unknown-service'),
                    'description': f"AI Recommendation: {ai_analysis.get('root_cause', 'Investigate and analyze')}"
                },
                'timestamp': webhook_data.get('timestamp', datetime.now().isoformat()),
                'status': webhook_data.get('status', 'pending'),
                'trace_id': webhook_data.get('trace_id', f"trace-{int(time.time())}"),
                'test_url': webhook_data.get('test_url', ''),
                'severity': ai_analysis.get('severity', webhook_data.get('severity', 'medium')),
                'confidence': ai_analysis.get('confidence', 0.7),
                'ai_analysis': ai_analysis,
                'requires_approval': webhook_data.get('requires_approval', True)
            }
        # Check if this is real GKE monitoring data or test data
        elif source == 'gke_real_monitoring' or 'failing_service' in webhook_data:
            logger.info("Processing as real GKE incident data")
            # Real GKE incident data
            return {
                'id': webhook_data.get('id', f"incident-{int(time.time())}"),
                'title': webhook_data.get('title', 'Unknown Incident'),
                'classification': webhook_data.get('classification', 'GKE Incident'),
                'failing_service': webhook_data.get('failing_service', 'unknown-service'),
                'summary': webhook_data.get('summary', 'No description available'),
                'evidence': webhook_data.get('evidence', ['No evidence available']),
                'proposed_action': {
                    'type': self._determine_action_type(webhook_data),
                    'target': webhook_data.get('failing_service', 'unknown-service'),
                    'description': self._generate_action_description(webhook_data)
                },
                'timestamp': webhook_data.get('timestamp', datetime.now().isoformat()),
                'status': webhook_data.get('status', 'pending'),
                'trace_id': webhook_data.get('trace_id', f"trace-{int(time.time())}"),
                'test_url': webhook_data.get('test_url', ''),
                'severity': webhook_data.get('status', 'medium'),  # Map status to severity
                'confidence': webhook_data.get('test_failure_data', {}).get('confidence', 0.7),
                'namespace': webhook_data.get('test_failure_data', {}).get('namespace', 'unknown'),
                'pod_name': webhook_data.get('test_failure_data', {}).get('pod_name', 'unknown')
            }
        else:
            logger.info("Processing as legacy test data format")
            # Legacy test data format
            return {
                'id': f"incident-{int(time.time())}",
                'title': webhook_data.get('testTitle', 'Unknown Test Failure'),
                'classification': 'Test Failure',
                'failing_service': 'test-service',
                'summary': f"Test failure: {webhook_data.get('error', {}).get('message', 'Unknown error')}",
                'evidence': [
                    f"Test status: {webhook_data.get('status', 'unknown')}",
                    f"Error: {webhook_data.get('error', {}).get('message', 'No error message')}",
                    f"Retries: {webhook_data.get('retries', 0)}"
                ],
                'proposed_action': {
                    'type': 'investigate',
                    'target': 'test-service',
                    'description': 'Manual investigation required'
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                'trace_id': webhook_data.get('traceID', 'unknown'),
                'test_url': webhook_data.get('videoUrl', '')
            }

    async def broadcast_to_websockets(self, message: dict):
        """Broadcast message to all connected WebSocket clients"""
        if not self.websocket_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for ws in self.websocket_connections:
            try:
                await ws.send_str(message_str)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                disconnected.add(ws)
        
        # Remove disconnected clients
        self.websocket_connections -= disconnected

    async def verify_auth(self, request: Request) -> bool:
        """Verify request authentication"""
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header[7:]
        session = self.authenticated_sessions.get(token)
        
        if session:
            # Update last activity
            session['last_activity'] = datetime.now().isoformat()
            return True
        
        return False

    def verify_signature(self, incident_id: str, action: str, signature: str) -> bool:
        """Verify approval signature (simplified for demo)"""
        try:
            # In real implementation, use proper cryptographic verification
            decoded = base64.b64decode(signature).decode('utf-8')
            expected_data = f"{incident_id}:{action}:"
            return expected_data in decoded
        except Exception:
            return False

    async def start_server(self):
        """Start the web server"""
        self.app = self.create_app()
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Dashboard server started at http://{self.host}:{self.port}")
        logger.info("Demo credentials: admin/admin")
        
        return runner

    async def stop_server(self, runner):
        """Stop the web server"""
        await runner.cleanup()
        logger.info("Dashboard server stopped")

async def main():
    """Main entry point"""
    server = DashboardServer()
    runner = await server.start_server()
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await server.stop_server(runner)

if __name__ == '__main__':
    asyncio.run(main())