/**
 * GKE Auto-Heal Agent Dashboard
 * Web-based approval interface for incident management
 */

class IncidentDashboard {
    constructor() {
        this.websocket = null;
        this.isAuthenticated = false;
        this.currentUser = null;
        this.incidents = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.checkAuthentication();
        this.updateConnectionStatus('disconnected');
        
        // Always connect WebSocket for incident streaming
        this.connectWebSocket();
        this.loadInitialData();
        
        // Show auth modal only if user tries to perform actions
        // but allow viewing incidents without auth
        if (!this.isAuthenticated) {
            // Don't show auth modal immediately, let users view incidents
            console.log('Not authenticated - showing read-only mode');
        }
    }

    setupEventListeners() {
        // Authentication form
        const authForm = document.getElementById('authForm');
        authForm.addEventListener('submit', (e) => this.handleAuthentication(e));

        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        logoutBtn.addEventListener('click', () => this.handleLogout());

        // Close modal buttons
        const closeApprovalModal = document.getElementById('closeApprovalModal');
        closeApprovalModal.addEventListener('click', () => this.hideApprovalModal());

        // Window events
        window.addEventListener('beforeunload', () => this.disconnect());
        window.addEventListener('focus', () => this.handleWindowFocus());
        window.addEventListener('blur', () => this.handleWindowBlur());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    checkAuthentication() {
        // Check for stored authentication token
        const token = localStorage.getItem('auth_token');
        const user = localStorage.getItem('current_user');
        
        if (token && user) {
            this.isAuthenticated = true;
            this.currentUser = JSON.parse(user);
            this.updateUserDisplay();
        }
    }

    async handleAuthentication(event) {
        event.preventDefault();
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        try {
            // Simulate authentication (in real implementation, this would call an API)
            const response = await this.authenticateUser(username, password);
            
            if (response.success) {
                this.isAuthenticated = true;
                this.currentUser = response.user;
                
                // Store authentication data
                localStorage.setItem('auth_token', response.token);
                localStorage.setItem('current_user', JSON.stringify(response.user));
                
                this.updateUserDisplay();
                this.hideAuthModal();
                this.connectWebSocket();
                this.loadInitialData();
                
                this.showToast('Authentication successful', 'success');
            } else {
                this.showToast('Authentication failed: ' + response.message, 'error');
            }
        } catch (error) {
            console.error('Authentication error:', error);
            this.showToast('Authentication error: ' + error.message, 'error');
        }
    }

    async authenticateUser(username, password) {
        // Call actual API endpoint
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                return result;
            } else {
                return {
                    success: false,
                    message: result.message || 'Authentication failed'
                };
            }
        } catch (error) {
            return {
                success: false,
                message: 'Network error: ' + error.message
            };
        }
    }

    handleLogout() {
        this.isAuthenticated = false;
        this.currentUser = null;
        
        // Clear stored data
        localStorage.removeItem('auth_token');
        localStorage.removeItem('current_user');
        
        // Disconnect WebSocket
        this.disconnect();
        
        // Show auth modal
        this.showAuthModal();
        
        // Clear incidents
        this.incidents.clear();
        this.updateIncidentDisplay();
        
        this.showToast('Logged out successfully', 'success');
    }

    updateUserDisplay() {
        const userNameElement = document.getElementById('userName');
        if (this.currentUser) {
            userNameElement.textContent = this.currentUser.name;
        } else {
            userNameElement.textContent = 'Not authenticated';
        }
    }

    connectWebSocket() {
        // Always connect WebSocket for incident streaming, regardless of auth
        try {
            // Connect to actual WebSocket server
            const wsUrl = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsHost = window.location.host;
            this.websocket = new WebSocket(`${wsUrl}//${wsHost}/ws`);
            
            this.websocket.onopen = () => {
                console.log('WebSocket connected');
                this.updateConnectionStatus('connected');
                this.reconnectAttempts = 0;
                
                // Send authentication message if available
                const token = localStorage.getItem('auth_token');
                if (token) {
                    this.websocket.send(JSON.stringify({
                        type: 'authenticate',
                        token: token
                    }));
                } else {
                    // Subscribe to incidents even without auth (read-only)
                    this.websocket.send(JSON.stringify({
                        type: 'subscribe',
                        channels: ['incidents', 'updates']
                    }));
                }
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('WebSocket message parsing error:', error);
                }
            };
            
            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateConnectionStatus('disconnected');
                this.scheduleReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('disconnected');
            };
            
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.updateConnectionStatus('disconnected');
            this.scheduleReconnect();
        }
    }
    
    handleWebSocketMessage(message) {
        console.log('WebSocket message received:', message);
        
        switch (message.type) {
            case 'connection_established':
                console.log('WebSocket connection established');
                break;
                
            case 'new_incident':
                console.log('New incident received:', message.incident);
                this.handleIncidentNotification(message.incident);
                break;
                
            case 'approval_decision':
                this.handleApprovalUpdate(message);
                break;
                
            case 'incident_update':
                this.handleIncidentUpdate(message);
                break;
                
            case 'subscribed':
                console.log('Subscribed to channels:', message.channels);
                break;
                
            case 'authenticated':
                console.log('WebSocket authenticated successfully');
                break;
                
            case 'pong':
                // Handle ping/pong for keepalive
                break;
                
            default:
                console.log('Unknown WebSocket message type:', message.type, message);
        }
    }

    handleIncidentNotification(incident) {
        console.log('Received incident notification:', incident);
        
        // Store incident
        this.incidents.set(incident.id, incident);
        
        // Update display
        this.updateIncidentDisplay();
        this.updateStatusCounts();
        
        // Show notification
        this.showToast(`New incident: ${incident.title}`, 'warning');
        
        // Play notification sound (if enabled)
        this.playNotificationSound();
    }
    
    handleApprovalUpdate(message) {
        const { incident_id, action, timestamp } = message;
        
        // Update local incident status
        const incident = this.incidents.get(incident_id);
        if (incident) {
            incident.status = action === 'approve' ? 'approved' : 'rejected';
            incident.updated_at = timestamp;
            
            this.updateIncidentDisplay();
            this.updateStatusCounts();
            
            this.showToast(`Incident ${incident_id} ${action}d`, 'success');
        }
    }
    
    handleIncidentUpdate(message) {
        const { incident_id, update } = message;
        
        // Update local incident data
        const incident = this.incidents.get(incident_id);
        if (incident) {
            Object.assign(incident, update);
            this.updateIncidentDisplay();
            this.updateStatusCounts();
        }
    }

    updateIncidentDisplay() {
        const incidentList = document.getElementById('incidentList');
        
        if (this.incidents.size === 0) {
            incidentList.innerHTML = this.getEmptyStateHTML();
            return;
        }
        
        const incidentsArray = Array.from(this.incidents.values())
            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        incidentList.innerHTML = incidentsArray
            .map(incident => this.createIncidentCardHTML(incident))
            .join('');
        
        // Add event listeners to action buttons
        this.attachIncidentEventListeners();
    }

    createIncidentCardHTML(incident) {
        const timeAgo = this.getTimeAgo(incident.timestamp);
        const classificationClass = incident.classification.toLowerCase().replace(' ', '-');
        const urgentClass = incident.classification === 'Backend Error' ? 'urgent' : '';
        
        return `
            <div class="incident-card ${urgentClass}" data-incident-id="${incident.id}">
                <div class="incident-header">
                    <div>
                        <div class="incident-title">${incident.title}</div>
                        <div class="incident-time">${timeAgo}</div>
                    </div>
                    <div class="incident-status ${incident.status}">
                        ${incident.status.charAt(0).toUpperCase() + incident.status.slice(1)}
                    </div>
                </div>
                
                <div class="incident-details">
                    <div class="incident-classification ${classificationClass}">
                        ${incident.classification}
                    </div>
                    
                    <div class="incident-summary">
                        ${incident.summary}
                    </div>
                    
                    ${incident.failing_service ? `
                        <div class="incident-service">
                            <strong>Failing Service:</strong> ${incident.failing_service}
                        </div>
                    ` : ''}
                    
                    <div class="incident-evidence">
                        <h4>Evidence:</h4>
                        ${incident.evidence.map(evidence => `
                            <div class="evidence-item">• ${evidence}</div>
                        `).join('')}
                    </div>
                    
                    ${incident.proposed_action ? `
                        <div class="incident-evidence">
                            <h4>Proposed Action:</h4>
                            <div class="evidence-item">
                                <strong>${incident.proposed_action.type.toUpperCase()}:</strong> 
                                ${incident.proposed_action.description}
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                ${incident.status === 'pending' ? `
                    <div class="incident-actions">
                        <button class="action-btn investigate" data-action="investigate" data-incident-id="${incident.id}">
                            <i class="fas fa-search"></i>
                            Investigate
                        </button>
                        <button class="action-btn reject" data-action="reject" data-incident-id="${incident.id}">
                            <i class="fas fa-times"></i>
                            Reject
                        </button>
                        <button class="action-btn approve" data-action="approve" data-incident-id="${incident.id}">
                            <i class="fas fa-check"></i>
                            Approve
                        </button>
                    </div>
                ` : incident.status === 'investigating' ? `
                    <div class="incident-actions">
                        <button class="action-btn reject" data-action="reject" data-incident-id="${incident.id}">
                            <i class="fas fa-times"></i>
                            Reject
                        </button>
                        <button class="action-btn approve" data-action="approve" data-incident-id="${incident.id}">
                            <i class="fas fa-check"></i>
                            Approve
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
    }

    attachIncidentEventListeners() {
        const actionButtons = document.querySelectorAll('.action-btn');
        actionButtons.forEach(button => {
            button.addEventListener('click', (e) => this.handleIncidentAction(e));
        });
    }

    async handleIncidentAction(event) {
        const button = event.currentTarget;
        const action = button.dataset.action;
        const incidentId = button.dataset.incidentId;
        const incident = this.incidents.get(incidentId);
        
        if (!incident) return;
        
        // Disable button during processing
        button.disabled = true;
        const originalHTML = button.innerHTML;
        button.innerHTML = '<div class="loading"></div> Processing...';
        
        try {
            switch (action) {
                case 'approve':
                    await this.approveIncident(incident);
                    break;
                case 'reject':
                    await this.rejectIncident(incident);
                    break;
                case 'investigate':
                    await this.investigateIncident(incident);
                    break;
            }
        } catch (error) {
            console.error('Action error:', error);
            this.showToast('Action failed: ' + error.message, 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalHTML;
        }
    }

    async approveIncident(incident) {
        // Send approval to backend API
        const response = await this.sendApprovalDecision(incident.id, 'approve');
        
        if (response.success) {
            // Update incident status locally
            incident.status = 'approved';
            incident.approved_by = this.currentUser?.name || 'User';
            incident.approved_at = new Date().toISOString();
            
            this.updateIncidentDisplay();
            this.updateStatusCounts();
            
            this.showToast(`Incident ${incident.id} approved successfully`, 'success');
        } else {
            throw new Error(response.message || 'Approval failed');
        }
    }

    async rejectIncident(incident) {
        const response = await this.sendApprovalDecision(incident.id, 'reject');
        
        if (response.success) {
            incident.status = 'rejected';
            incident.rejected_by = this.currentUser?.name || 'User';
            incident.rejected_at = new Date().toISOString();
            
            this.updateIncidentDisplay();
            this.updateStatusCounts();
            
            this.showToast(`Incident ${incident.id} rejected`, 'success');
        } else {
            throw new Error(response.message || 'Rejection failed');
        }
    }

    async investigateIncident(incident) {
        // Trigger RCA investigation via backend API
        const response = await this.sendInvestigationRequest(incident.id);
        
        if (response.success) {
            // Update incident status locally
            incident.status = 'investigating';
            incident.investigation = response.investigation;
            incident.updated_at = new Date().toISOString();
            
            this.updateIncidentDisplay();
            this.updateStatusCounts();
            
            this.showToast(`RCA investigation started for incident ${incident.id}`, 'success');
            
            // Show investigation results in modal
            this.showInvestigationResults(incident, response.investigation);
        } else {
            throw new Error(response.message || 'Investigation failed');
        }
    }

    async sendInvestigationRequest(incidentId) {
        try {
            const response = await fetch('/api/incidents/approve', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token') || 'demo-token'}`
                },
                body: JSON.stringify({
                    incident_id: incidentId,
                    action: 'investigate',
                    user_id: this.currentUser?.id || 1,
                    timestamp: new Date().toISOString()
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                return result;
            } else {
                return {
                    success: false,
                    message: result.message || 'Investigation request failed'
                };
            }
        } catch (error) {
            return {
                success: false,
                message: 'Network error: ' + error.message
            };
        }
    }

    async sendApprovalDecision(incidentId, action) {
        try {
            // First, create an approval request if one doesn't exist
            const approvalRequest = await this.createApprovalRequest(incidentId, action);
            if (!approvalRequest.success) {
                throw new Error(approvalRequest.message || 'Failed to create approval request');
            }

            // Then submit the decision
            const decisionResponse = await fetch('/api/approval/decision', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token') || 'demo-token'}`
                },
                body: JSON.stringify({
                    request_id: approvalRequest.request_id,
                    decision: action,
                    user_id: this.currentUser?.id || 1,
                    user_name: this.currentUser?.name || 'User',
                    reason: '',
                    signature: this.generateSignature(incidentId, action),
                    timestamp: new Date().toISOString()
                })
            });
            
            const result = await decisionResponse.json();
            
            if (decisionResponse.ok && result.success) {
                return result;
            } else {
                return {
                    success: false,
                    message: result.message || 'Approval decision failed'
                };
            }
        } catch (error) {
            return {
                success: false,
                message: 'Network error: ' + error.message
            };
        }
    }

    async createApprovalRequest(incidentId, action) {
        try {
            const incident = this.incidents.get(incidentId);
            if (!incident) {
                throw new Error('Incident not found');
            }

            const response = await fetch('/api/approval/request', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token') || 'demo-token'}`
                },
                body: JSON.stringify({
                    incident_id: incidentId,
                    title: incident.title,
                    description: incident.summary,
                    classification: incident.classification,
                    failing_service: incident.failing_service,
                    evidence: incident.evidence,
                    proposed_action: incident.proposed_action,
                    priority: incident.severity === 'critical' ? 'high' : 'medium',
                    trace_id: incident.trace_id,
                    submitted_by: this.currentUser?.name || 'system'
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                return result;
            } else {
                return {
                    success: false,
                    message: result.message || 'Failed to create approval request'
                };
            }
        } catch (error) {
            return {
                success: false,
                message: 'Network error: ' + error.message
            };
        }
    }

    showIncidentDetails(incident) {
        const modalBody = document.getElementById('approvalModalBody');
        
        modalBody.innerHTML = `
            <div class="incident-details-modal">
                <h3>${incident.title}</h3>
                
                <div class="detail-section">
                    <h4>Classification</h4>
                    <div class="incident-classification ${incident.classification.toLowerCase().replace(' ', '-')}">
                        ${incident.classification}
                    </div>
                </div>
                
                <div class="detail-section">
                    <h4>Summary</h4>
                    <p>${incident.summary}</p>
                </div>
                
                ${incident.failing_service ? `
                    <div class="detail-section">
                        <h4>Failing Service</h4>
                        <p>${incident.failing_service}</p>
                    </div>
                ` : ''}
                
                <div class="detail-section">
                    <h4>Evidence</h4>
                    <ul>
                        ${incident.evidence.map(evidence => `<li>${evidence}</li>`).join('')}
                    </ul>
                </div>
                
                ${incident.proposed_action ? `
                    <div class="detail-section">
                        <h4>Proposed Action</h4>
                        <p><strong>Type:</strong> ${incident.proposed_action.type}</p>
                        <p><strong>Target:</strong> ${incident.proposed_action.target}</p>
                        <p><strong>Description:</strong> ${incident.proposed_action.description}</p>
                    </div>
                ` : ''}
                
                <div class="detail-section">
                    <h4>Technical Details</h4>
                    <p><strong>Trace ID:</strong> ${incident.trace_id}</p>
                    <p><strong>Timestamp:</strong> ${new Date(incident.timestamp).toLocaleString()}</p>
                    ${incident.test_url ? `<p><strong>Test URL:</strong> <a href="${incident.test_url}" target="_blank">${incident.test_url}</a></p>` : ''}
                </div>
                
                ${incident.status === 'pending' ? `
                    <div class="modal-actions">
                        <button class="action-btn reject" onclick="dashboard.rejectIncident(dashboard.incidents.get('${incident.id}')); dashboard.hideApprovalModal();">
                            <i class="fas fa-times"></i>
                            Reject
                        </button>
                        <button class="action-btn approve" onclick="dashboard.approveIncident(dashboard.incidents.get('${incident.id}')); dashboard.hideApprovalModal();">
                            <i class="fas fa-check"></i>
                            Approve
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
        
        this.showApprovalModal();
    }

    showInvestigationResults(incident, investigation) {
        const modalBody = document.getElementById('approvalModalBody');
        
        const analysis = investigation.analysis || {};
        
        modalBody.innerHTML = `
            <div class="investigation-results-modal">
                <h3>RCA Investigation Results</h3>
                <p><strong>Incident:</strong> ${incident.title}</p>
                <p><strong>Status:</strong> ${investigation.status}</p>
                
                ${investigation.status === 'completed' ? `
                    <div class="investigation-summary">
                        <h4>Analysis Summary</h4>
                        <div class="analysis-details">
                            <p><strong>Classification:</strong> ${analysis.classification || 'Unknown'}</p>
                            <p><strong>Failing Service:</strong> ${analysis.failing_service || 'Unknown'}</p>
                            <p><strong>Confidence Score:</strong> ${analysis.confidence_score ? (analysis.confidence_score * 100).toFixed(1) + '%' : 'N/A'}</p>
                            <p><strong>Evidence Count:</strong> ${analysis.evidence_count || 0}</p>
                            <p><strong>Analysis Duration:</strong> ${analysis.analysis_duration ? analysis.analysis_duration.toFixed(2) + 's' : 'N/A'}</p>
                            <p><strong>Trace ID:</strong> ${analysis.trace_id || incident.trace_id}</p>
                        </div>
                        
                        <div class="analysis-summary-text">
                            <h4>Detailed Analysis</h4>
                            <p>${analysis.summary || 'No detailed analysis available'}</p>
                        </div>
                    </div>
                ` : investigation.status === 'error' ? `
                    <div class="investigation-error">
                        <h4>Investigation Failed</h4>
                        <p><strong>Error:</strong> ${investigation.message}</p>
                        ${investigation.error_details ? `<p><strong>Details:</strong> ${investigation.error_details}</p>` : ''}
                    </div>
                ` : `
                    <div class="investigation-pending">
                        <h4>Investigation in Progress</h4>
                        <p>The RCA analysis is currently running. Please wait for completion.</p>
                        <div class="loading-spinner"></div>
                    </div>
                `}
                
                <div class="modal-actions">
                    <button class="action-btn secondary" onclick="dashboard.hideApprovalModal();">
                        <i class="fas fa-times"></i>
                        Close
                    </button>
                </div>
            </div>
        `;
        
        this.showApprovalModal();
    }

    generateSignature(incidentId, action) {
        // In real implementation, this would generate a cryptographic signature
        const data = `${incidentId}:${action}:${this.currentUser.id}:${Date.now()}`;
        return btoa(data); // Simple base64 encoding for demo
    }

    logAuditEvent(eventType, details) {
        const auditEvent = {
            event_type: eventType,
            user: this.currentUser.name,
            user_id: this.currentUser.id,
            timestamp: new Date().toISOString(),
            details: details
        };
        
        console.log('Audit Event:', auditEvent);
        
        // In real implementation, this would send to audit logging service
    }

    updateStatusCounts() {
        const pendingCount = Array.from(this.incidents.values())
            .filter(incident => incident.status === 'pending').length;
        
        const resolvedCount = Array.from(this.incidents.values())
            .filter(incident => incident.status === 'approved').length;
        
        document.getElementById('pendingCount').textContent = pendingCount;
        document.getElementById('resolvedCount').textContent = resolvedCount;
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connectionStatus');
        const statusText = statusElement.querySelector('span');
        
        statusElement.className = `connection-status ${status}`;
        statusText.textContent = status === 'connected' ? 'Connected' : 'Disconnected';
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            const delay = Math.pow(2, this.reconnectAttempts) * 1000; // Exponential backoff
            this.reconnectAttempts++;
            
            setTimeout(() => {
                console.log(`Reconnection attempt ${this.reconnectAttempts}`);
                this.connectWebSocket();
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
            this.showToast('Connection lost. Please refresh the page.', 'error');
        }
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        this.updateConnectionStatus('disconnected');
    }

    // Modal management
    showAuthModal() {
        document.getElementById('authModal').classList.add('show');
    }

    hideAuthModal() {
        document.getElementById('authModal').classList.remove('show');
    }

    showApprovalModal() {
        document.getElementById('approvalModal').classList.add('show');
    }

    hideApprovalModal() {
        document.getElementById('approvalModal').classList.remove('show');
    }

    // Utility methods
    getTimeAgo(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diffInSeconds = Math.floor((now - time) / 1000);
        
        if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
        return `${Math.floor(diffInSeconds / 86400)}d ago`;
    }

    getEmptyStateHTML() {
        return `
            <div class="empty-state">
                <i class="fas fa-clipboard-check"></i>
                <h3>No incidents</h3>
                <p>All systems are running smoothly. New incidents will appear here when detected.</p>
            </div>
        `;
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Hide toast after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 5000);
    }

    playNotificationSound() {
        // Create audio context for notification sound
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);
            
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.2);
        } catch (error) {
            console.log('Audio notification not available');
        }
    }

    handleKeyboardShortcuts(event) {
        // Keyboard shortcuts for power users
        if (event.ctrlKey || event.metaKey) {
            switch (event.key) {
                case 'r':
                    event.preventDefault();
                    this.loadInitialData();
                    break;
                case 'l':
                    event.preventDefault();
                    this.handleLogout();
                    break;
            }
        }
        
        // Escape key to close modals
        if (event.key === 'Escape') {
            this.hideApprovalModal();
        }
    }

    handleWindowFocus() {
        // Reconnect if needed when window gains focus
        if (!this.websocket && this.isAuthenticated) {
            this.connectWebSocket();
        }
    }

    handleWindowBlur() {
        // Optional: Reduce activity when window loses focus
    }

    async loadInitialData() {
        // Load initial dashboard data
        try {
            document.getElementById('systemStatus').textContent = 'Active';
            this.updateStatusCounts();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showToast('Failed to load dashboard data', 'error');
        }
    }
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new IncidentDashboard();
});

// Export for global access
window.dashboard = dashboard;