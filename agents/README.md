# GKE Auto-Heal Agent - Approval System

A comprehensive human-in-the-loop approval system that integrates with a web-based dashboard to manage remediation decisions for the GKE Auto-Heal Agent.

## Overview

The Approval System consists of two main components:

1. **Approval Agent** - ADK-based agent that manages approval workflows
2. **Web Dashboard** - Real-time web interface for human decision making

## Architecture

```
External Trigger → Orchestrator → RCA Agent → Orchestrator
                      ↓                          ↓
                 Audit Agent ← Orchestrator ← Remediation Agent
                      ↓                          ↓
                Dashboard ← Orchestrator → Approval Agent
```


```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   RCA Agent     │    │  Approval Agent  │    │  Web Dashboard  │
│                 │───▶│                  │───▶│                 │
│ Proposes Action │    │ Manages Workflow │    │ Human Decision  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          │
                              ▼                          ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Audit Agent     │    │ Remediation     │
                       │                  │    │ Agent           │
                       │ Logs Decisions   │    │                 │
                       └──────────────────┘    └─────────────────┘
```

## Components

### Approval Agent (`approval_agent.py`)

The core ADK agent that:
- Receives remediation proposals from RCA Agent
- Formats approval requests for human review
- Manages approval workflows and timeouts
- Handles cryptographic signature verification
- Coordinates with other agents via A2A communication
- Maintains audit trails for all decisions

**Key Features:**
- **Real-time Notifications**: WebSocket integration for instant updates
- **Signature Verification**: Cryptographic verification of approval decisions
- **Timeout Management**: Automatic expiration of pending requests
- **Audit Integration**: Complete logging of all approval activities
- **A2A Communication**: Coordination with other agents in the system

### Web Dashboard (`web-dashboard/`)

A modern web interface that:
- Displays incident details and proposed remediation actions
- Provides one-click approve/reject/investigate actions
- Shows real-time incident notifications
- Maintains session management and authentication
- Supports keyboard shortcuts for power users

**Key Features:**
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: WebSocket-based live incident feed
- **Interactive Approval**: One-click decision making with detailed context
- **Authentication**: Secure login with session management
- **Audit Trail**: Complete history of all approval decisions

## Quick Start

### 1. Start the Web Dashboard

```bash
cd web-dashboard
pip install -r requirements.txt
python server.py
```

The dashboard will be available at `http://localhost:8080`

**Demo Credentials:**
- Username: `admin`
- Password: `admin`

### 2. Run the Approval Agent

```bash
cd agents
python approval_integration.py --mode interactive
```

This starts an interactive demo that shows various approval scenarios.

### 3. Test the Integration

1. Open the web dashboard in your browser
2. Login with the demo credentials
3. Run a demo scenario from the approval agent
4. See the incident appear in the dashboard
5. Click "Approve" or "Reject" to make a decision
6. Observe the agent receiving and processing the decision

## Configuration

### Environment Variables

The system can be configured using environment variables:

```bash
# Dashboard Configuration
export APPROVAL_DASHBOARD_URL="http://localhost:8080"
export APPROVAL_DASHBOARD_API_KEY="your-api-key"

# Security Configuration
export APPROVAL_SECRET_KEY="your-secret-key"
export APPROVAL_REQUIRE_SIGNATURE="true"

# Timeout Configuration
export APPROVAL_DEFAULT_TIMEOUT_MINUTES="30"
export APPROVAL_CRITICAL_TIMEOUT_MINUTES="10"

# Notification Channels
export APPROVAL_NOTIFICATION_CHANNELS="web_dashboard,websocket,email"

# Email Configuration (optional)
export APPROVAL_SMTP_SERVER="smtp.gmail.com"
export APPROVAL_SMTP_USERNAME="your-email@gmail.com"
export APPROVAL_SMTP_PASSWORD="your-password"

# Slack Configuration (optional)
export APPROVAL_SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
export APPROVAL_SLACK_CHANNEL="#incidents"
```

### Configuration Files

You can also use configuration files:

```python
from agents.config.approval_agent_config import get_development_config

config = get_development_config()
agent = ApprovalAgent(config.__dict__)
```

## Usage Examples

### Basic Approval Request

```python
from agents.approval_agent import ApprovalAgent, ApprovalPriority

agent = ApprovalAgent()
await agent.initialize()

# Define callback for approval decision
async def handle_decision(decision):
    if decision.decision == 'approve':
        print(f"Approved by {decision.user_name}")
        # Execute remediation
    else:
        print(f"Rejected: {decision.reason}")

# Request approval
request_id = await agent.request_approval(
    incident_id="incident-123",
    trace_id="trace-456",
    title="Payment Service Rollback Required",
    description="Payment service experiencing high error rates",
    classification="Backend Error",
    failing_service="payment-service",
    summary="Database connection timeouts causing payment failures",
    evidence=[
        "ERROR: Database connection timeout after 30s",
        "Payment success rate dropped to 60%",
        "CPU utilization at 95%"
    ],
    proposed_action={
        "type": "rollback",
        "target": "payment-service",
        "from_version": "v2.1.0",
        "to_version": "v2.0.5",
        "description": "Rollback to previous stable version"
    },
    priority=ApprovalPriority.CRITICAL,
    callback=handle_decision
)
```

### Handling Approval Decisions

```python
# This is typically called by the web dashboard webhook
decision_data = {
    'request_id': request_id,
    'decision': 'approve',
    'user_id': 'admin',
    'user_name': 'System Administrator',
    'timestamp': datetime.now().isoformat(),
    'signature': signature,
    'reason': 'Approved for immediate rollback'
}

success = await agent.handle_approval_decision(decision_data)
```

### Getting Approval Statistics

```python
stats = await agent.get_approval_statistics()
print(f"Approval rate: {stats['approval_rate']:.1f}%")
print(f"Average response time: {stats['average_response_time_seconds']:.1f}s")
```

## Security Features

### Cryptographic Signatures

All approval decisions are cryptographically signed to prevent tampering:

```python
from agents.approval_agent import SignatureManager

signature_manager = SignatureManager("your-secret-key")

# Generate signature
signature = signature_manager.generate_signature(decision_data)

# Verify signature
is_valid = signature_manager.verify_signature(decision_data, signature)
```

### Authentication

The web dashboard requires authentication:
- Session-based authentication with secure tokens
- Configurable session timeouts
- Audit logging of all authentication events

### Audit Trail

Complete audit trail for compliance:
- All approval requests logged
- All decisions recorded with user information
- Cryptographic integrity verification
- Configurable retention policies

## Integration with Other Agents

### RCA Agent Integration

```python
# RCA Agent proposes remediation
from agents.rca_agent import RCAAgent
from agents.approval_agent import ApprovalAgent

rca_agent = RCAAgent()
approval_agent = ApprovalAgent()

# RCA analysis complete, request approval
analysis_result = await rca_agent.analyze_failure(failure_payload)

if analysis_result.classification == "Backend Error":
    remediation_action = await rca_agent.propose_remediation(analysis_result)
    
    # Request human approval
    request_id = await approval_agent.request_approval(
        incident_id=analysis_result.incident_id,
        title=f"Remediation Required: {analysis_result.failing_service}",
        # ... other parameters
        proposed_action=remediation_action
    )
```

### Remediation Agent Integration

```python
# Approval callback triggers remediation
async def execute_remediation(decision):
    if decision.decision == 'approve':
        from agents.remediation_agent import RemediationAgent
        
        remediation_agent = RemediationAgent()
        result = await remediation_agent.execute_action(
            decision.proposed_action
        )
        
        if result.success:
            print("Remediation completed successfully")
        else:
            print(f"Remediation failed: {result.error_message}")
```

### Audit Agent Integration

```python
# Automatic audit logging
await approval_agent.request_approval(
    # ... parameters
    callback=lambda decision: audit_agent.log_event(
        'approval_decision',
        {
            'decision': decision.decision,
            'user': decision.user_name,
            'incident_id': decision.incident_id
        }
    )
)
```

## Testing

### Unit Tests

```bash
cd agents
python -m pytest tests/test_approval_agent.py -v
```

### Integration Tests

```bash
# Start web dashboard
cd web-dashboard
python server.py &

# Run integration demo
cd agents
python approval_integration.py --mode automated
```

### Manual Testing

1. Start the web dashboard
2. Run the interactive demo
3. Test various approval scenarios
4. Verify audit trails and statistics

## Monitoring and Observability

### Metrics

The approval system exposes metrics for monitoring:
- Approval request rate
- Decision latency
- Approval/rejection ratios
- Timeout rates
- Error rates

### Logging

Structured logging for all operations:
```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "level": "INFO",
  "event": "approval_requested",
  "incident_id": "incident-123",
  "request_id": "req-456",
  "priority": "critical",
  "expires_at": "2024-01-01T10:10:00Z"
}
```

### Health Checks

Built-in health checks for:
- Web dashboard connectivity
- WebSocket connection status
- Agent responsiveness
- Database connectivity (if configured)

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check dashboard server is running
   - Verify firewall settings
   - Check authentication credentials

2. **Approval Requests Not Appearing**
   - Verify dashboard URL configuration
   - Check API key authentication
   - Review server logs for errors

3. **Signature Verification Failed**
   - Ensure secret keys match between components
   - Check system clock synchronization
   - Verify data integrity

### Debug Mode

Enable debug logging:
```bash
export APPROVAL_LOG_LEVEL="DEBUG"
python approval_integration.py
```

### Log Analysis

Check logs for common patterns:
```bash
# Approval request patterns
grep "approval_requested" logs/approval_agent.log

# Decision patterns
grep "approval_decision" logs/approval_agent.log

# Error patterns
grep "ERROR" logs/approval_agent.log
```

## Production Deployment

### Security Considerations

1. **Use Strong Secret Keys**: Generate cryptographically secure keys
2. **Enable HTTPS**: Use SSL/TLS for all communications
3. **Implement Rate Limiting**: Prevent abuse of approval endpoints
4. **Regular Key Rotation**: Rotate secret keys periodically
5. **Audit Log Protection**: Secure audit logs against tampering

### Scalability

1. **Load Balancing**: Use multiple dashboard instances
2. **Database Backend**: Replace in-memory storage with persistent database
3. **Caching**: Implement Redis for session and state management
4. **Monitoring**: Set up comprehensive monitoring and alerting

### High Availability

1. **Redundant Agents**: Deploy multiple approval agent instances
2. **Health Checks**: Implement proper health check endpoints
3. **Graceful Degradation**: Handle partial system failures
4. **Backup Systems**: Implement fallback approval mechanisms

## API Reference

### Approval Agent API

#### `request_approval()`
Request human approval for a remediation action.

**Parameters:**
- `incident_id` (str): Unique incident identifier
- `trace_id` (str): Distributed trace ID
- `title` (str): Human-readable title
- `description` (str): Detailed description
- `classification` (str): Issue classification
- `failing_service` (str): Name of failing service
- `summary` (str): Brief summary
- `evidence` (List[str]): Supporting evidence
- `proposed_action` (Dict): Proposed remediation action
- `priority` (ApprovalPriority): Request priority
- `callback` (callable): Decision callback function

**Returns:**
- `str`: Request ID for tracking

#### `handle_approval_decision()`
Process approval decision from web dashboard.

**Parameters:**
- `decision_data` (Dict): Decision data with signature

**Returns:**
- `bool`: True if decision processed successfully

### Web Dashboard API

#### `POST /api/approval/request`
Submit new approval request.

#### `POST /api/approval/decision`
Submit approval decision.

#### `GET /ws`
WebSocket endpoint for real-time updates.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This approval system is part of the GKE Auto-Heal Agent project and follows the same license terms.