# GKE Auto-Heal Agent Web Dashboard

A web-based approval interface for the GKE Auto-Heal Agent that provides real-time incident notifications and human-in-the-loop approval workflows.

## Features

- **Real-time Incident Notifications**: WebSocket-based real-time updates for new incidents
- **Authentication & Session Management**: Secure login with session management
- **Interactive Approval Interface**: One-click approve/reject/investigate actions
- **Incident Details Modal**: Comprehensive incident information display
- **Audit Trail**: Complete logging of all approval decisions
- **Responsive Design**: Works on desktop and mobile devices
- **Keyboard Shortcuts**: Power user shortcuts for common actions

## Architecture

The dashboard consists of:

1. **Frontend**: HTML/CSS/JavaScript single-page application
2. **Backend**: Python aiohttp server with WebSocket support
3. **Authentication**: Session-based authentication with demo credentials
4. **WebSocket**: Real-time communication for incident updates
5. **Webhook Endpoint**: Receives incident notifications from Playwright tests

## Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Install dependencies:
```bash
cd web-dashboard
pip install -r requirements.txt
```

2. Start the server:
```bash
python server.py
```

3. Open your browser and navigate to:
```
http://localhost:8080
```

4. Login with demo credentials:
- Username: `admin`
- Password: `admin`

## Usage

### Authentication

The dashboard requires authentication before accessing incident data. Use the demo credentials or configure your own authentication system.

### Incident Management

1. **View Incidents**: All incidents appear in the main dashboard with status indicators
2. **Investigate**: Click "Investigate" to view detailed incident information
3. **Approve/Reject**: Use the action buttons to approve or reject proposed remediation actions
4. **Real-time Updates**: New incidents appear automatically via WebSocket connection

### Keyboard Shortcuts

- `Ctrl/Cmd + R`: Refresh dashboard data
- `Ctrl/Cmd + L`: Logout
- `Escape`: Close modal dialogs

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout

### Approval System
- `POST /api/approval/request` - Submit new approval request
- `POST /api/approval/decision` - Submit approval decision

### Incidents
- `GET /api/incidents` - Get incident list
- `POST /api/incidents/approve` - Approve/reject/investigate incident (legacy)

### WebSocket
- `GET /ws` - WebSocket connection for real-time updates

### Webhooks
- `POST /webhook/incident` - Receive incident notifications from agents

## Configuration

### Environment Variables

- `DASHBOARD_SECRET_KEY`: Secret key for session management (auto-generated if not set)
- `DASHBOARD_HOST`: Server host (default: localhost)
- `DASHBOARD_PORT`: Server port (default: 8080)

### Demo Users

The server includes demo users for testing:

```python
demo_users = {
    'admin': {
        'password': 'admin',
        'name': 'System Administrator',
        'role': 'admin'
    }
}
```

## Integration with Playwright MCP Server

The dashboard is designed to work with the official Playwright MCP server for browser automation and testing:

1. **Test Execution**: Playwright MCP server runs synthetic tests
2. **Failure Detection**: Custom reporter captures test failures
3. **Webhook Notification**: Failure data sent to dashboard webhook
4. **Real-time Display**: Incidents appear immediately in the dashboard
5. **User Interaction**: Users can approve/reject proposed actions
6. **Callback Processing**: Decisions are sent back to the agent system

## Security Features

- **Session Management**: Secure session tokens with expiration
- **Signature Verification**: Cryptographic verification of approval decisions
- **CORS Protection**: Configurable CORS policies
- **Input Validation**: Comprehensive input validation and sanitization
- **Audit Logging**: Complete audit trail of all user actions

## Development

### File Structure

```
web-dashboard/
├── index.html          # Main dashboard HTML
├── styles.css          # Dashboard styles
├── dashboard.js        # Frontend JavaScript
├── server.py          # Backend server
├── requirements.txt   # Python dependencies
└── README.md         # This file
```

### Extending the Dashboard

1. **Add New Incident Types**: Modify the `process_incident_data` method
2. **Custom Authentication**: Replace the demo authentication system
3. **Additional Actions**: Add new action buttons and handlers
4. **Styling**: Customize the CSS for your organization's branding

### Testing

To test the dashboard with sample incidents:

1. Start the server
2. Login to the dashboard
3. Send a test webhook:

```bash
curl -X POST http://localhost:8080/webhook/incident \
  -H "Content-Type: application/json" \
  -d '{
    "testTitle": "Checkout Flow Test",
    "status": "failed",
    "error": {
      "message": "Timeout waiting for payment button"
    },
    "retries": 3,
    "traceID": "trace-12345"
  }'
```

## Production Deployment

For production deployment:

1. **Use HTTPS**: Configure SSL/TLS certificates
2. **Authentication**: Implement proper authentication (OAuth, SAML, etc.)
3. **Database**: Replace in-memory storage with persistent database
4. **Load Balancing**: Use multiple server instances behind a load balancer
5. **Monitoring**: Add health checks and monitoring
6. **Security**: Implement rate limiting, input validation, and security headers

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**: Check firewall settings and server logs
2. **Authentication Issues**: Verify credentials and session storage
3. **Incident Not Appearing**: Check webhook endpoint and server logs
4. **Browser Compatibility**: Ensure modern browser with WebSocket support

### Logs

Server logs provide detailed information about:
- Authentication attempts
- WebSocket connections
- Incident processing
- Error conditions

Check the console output for debugging information.

## License

This dashboard is part of the GKE Auto-Heal Agent project and follows the same license terms.