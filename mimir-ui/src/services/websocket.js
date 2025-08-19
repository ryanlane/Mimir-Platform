class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.listeners = new Map();
    this.isConnected = false;
    
    // Enhanced features for new API
    this.lastSequenceId = 0;
    this.currentState = null;
    this.heartbeatInterval = null;
    this.heartbeatTimeout = null;
    this.connectionId = null;
    
    // Auto-connect on initialization
    this.connect();
  }

  connect(baseUrl = 'ws://172.31.79.107:5000') {
    try {
      console.log('🔌 Connecting to enhanced WebSocket...');
      this.ws = new WebSocket(`${baseUrl}/ws`);
      
      this.ws.onopen = (event) => {
        console.log('🟢 Enhanced WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connection', { status: 'connected', event });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📨 Enhanced WebSocket message received:', message);
          
          // Update sequence tracking
          if (message.sequenceId) {
            this.lastSequenceId = message.sequenceId;
          }
          
          // Handle special events
          this.handleSpecialEvents(message);
          
          // Emit the specific event type
          this.emit(message.event, message.data);
          
          // Also emit a general 'message' event
          this.emit('message', message);
        } catch (error) {
          console.error('❌ Error parsing WebSocket message:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log('🔴 WebSocket disconnected:', event.code, event.reason);
        this.isConnected = false;
        this.stopHeartbeat();
        this.emit('connection', { status: 'disconnected', event });
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        this.emit('error', error);
      };

    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error);
      this.scheduleReconnect();
    }
  }

  // Handle special enhanced events
  handleSpecialEvents(message) {
    switch (message.event) {
      case 'connection_established':
        console.log('🚀 Connection established with full state');
        this.connectionId = message.data.connectionId;
        this.currentState = message.data.currentState;
        this.emit('full_state_received', message.data.currentState);
        break;
        
      case 'ping':
        console.log('💓 Received ping, sending pong');
        this.sendPong(message.data.timestamp);
        break;
        
      case 'state_sync_response':
        console.log('🔄 Received state sync response');
        this.currentState = message.data.currentState;
        this.emit('state_sync_received', message.data);
        break;
        
      case 'error':
        console.error('🚨 Server error:', message.data);
        this.emit('server_error', message.data);
        break;
        
      default:
        // Regular events, no special handling needed
        break;
    }
  }

  // Send pong response to server ping
  sendPong(timestamp) {
    if (this.isConnected && this.ws) {
      this.ws.send(JSON.stringify({
        event: 'pong',
        data: { timestamp }
      }));
    }
  }

  // Request state synchronization
  requestStateSync() {
    if (this.isConnected && this.ws) {
      console.log('🔄 Requesting state sync from sequence:', this.lastSequenceId);
      this.ws.send(JSON.stringify({
        event: 'state_sync_request',
        data: { lastKnownSequenceId: this.lastSequenceId }
      }));
    }
  }

  // Start heartbeat monitoring (client-side)
  startHeartbeat() {
    // Clear any existing heartbeat
    this.stopHeartbeat();
    
    // Monitor for server pings - if we don't receive one in 60 seconds, something's wrong
    this.heartbeatTimeout = setTimeout(() => {
      console.warn('⚠️ No heartbeat received from server, connection may be stale');
      this.emit('heartbeat_timeout');
    }, 60000);
  }

  // Stop heartbeat monitoring
  stopHeartbeat() {
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  // Get current application state
  getCurrentState() {
    return this.currentState;
  }

  // Get last sequence ID
  getLastSequenceId() {
    return this.lastSequenceId;
  }

  // Get connection ID
  getConnectionId() {
    return this.connectionId;
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
    
    console.log(`⏰ Scheduling WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
    
    setTimeout(() => {
      if (!this.isConnected) {
        this.connect();
      }
    }, delay);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
      this.isConnected = false;
    }
  }

  // Event listener management
  on(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType).add(callback);

    // Return cleanup function
    return () => {
      this.off(eventType, callback);
    };
  }

  off(eventType, callback) {
    if (this.listeners.has(eventType)) {
      this.listeners.get(eventType).delete(callback);
    }
  }

  emit(eventType, data) {
    if (this.listeners.has(eventType)) {
      this.listeners.get(eventType).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`❌ Error in WebSocket event handler for ${eventType}:`, error);
        }
      });
    }
  }

  // Convenience methods for common events
  onSceneActivated(callback) {
    return this.on('scene_activated', callback);
  }

  onSceneDeactivated(callback) {
    return this.on('scene_deactivated', callback);
  }

  onSceneCreated(callback) {
    return this.on('scene_created', callback);
  }

  onSceneUpdated(callback) {
    return this.on('scene_updated', callback);
  }

  onSceneDeleted(callback) {
    return this.on('scene_deleted', callback);
  }

  onSceneDisplayed(callback) {
    return this.on('scene_displayed', callback);
  }

  onConnection(callback) {
    return this.on('connection', callback);
  }

  // Get connection status
  getConnectionStatus() {
    return {
      connected: this.isConnected,
      readyState: this.ws?.readyState,
      reconnectAttempts: this.reconnectAttempts
    };
  }
}

// Create singleton instance
const wsService = new WebSocketService();

export default wsService;
