class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.listeners = new Map();
    this.isConnected = false;
  }

  connect(baseUrl = 'ws://172.31.79.107:5000') {
    try {
      this.ws = new WebSocket(`${baseUrl}/ws`);
      
      this.ws.onopen = (event) => {
        console.log('🟢 WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connection', { status: 'connected', event });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📨 WebSocket message received:', message);
          
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
