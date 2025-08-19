import { useEffect, useRef, useState } from 'react';
import wsService from '../services/websocket';

// Hook for WebSocket connection management with enhanced features
export const useWebSocket = () => {
  const connectionInitialized = useRef(false);
  const [isConnected, setIsConnected] = useState(wsService.isConnected);
  const [currentState, setCurrentState] = useState(null);

  useEffect(() => {
    if (!connectionInitialized.current) {
      wsService.connect();
      connectionInitialized.current = true;
    }

    // Enhanced event listeners
    const handleConnection = (data) => {
      setIsConnected(data.status === 'connected');
    };

    const handleFullState = (state) => {
      console.log('🚀 Full state received:', state);
      setCurrentState(state);
    };

    const handleServerError = (error) => {
      console.error('🚨 Server error:', error);
    };

    const cleanupConnection = wsService.on('connection', handleConnection);
    const cleanupFullState = wsService.on('full_state_received', handleFullState);
    const cleanupError = wsService.on('server_error', handleServerError);

    // Initialize state
    setIsConnected(wsService.isConnected);

    return () => {
      cleanupConnection();
      cleanupFullState();
      cleanupError();
      // Don't disconnect on unmount as this is a global service
    };
  }, []);

  return {
    wsService,
    isConnected,
    currentState,
    requestStateSync: () => wsService.requestStateSync()
  };
};

// Hook for listening to specific WebSocket events
export const useWebSocketEvent = (eventType, callback) => {
  useEffect(() => {
    const cleanup = wsService.on(eventType, callback);
    return cleanup;
  }, [eventType, callback]);
};

// Hook for scene-related events
export const useSceneEvents = (callbacks) => {
  const { 
    onActivated, 
    onDeactivated, 
    onCreated, 
    onUpdated, 
    onDeleted, 
    onDisplayed 
  } = callbacks;

  useEffect(() => {
    const cleanupFunctions = [];

    if (onActivated) {
      cleanupFunctions.push(wsService.onSceneActivated(onActivated));
    }
    if (onDeactivated) {
      cleanupFunctions.push(wsService.onSceneDeactivated(onDeactivated));
    }
    if (onCreated) {
      cleanupFunctions.push(wsService.onSceneCreated(onCreated));
    }
    if (onUpdated) {
      cleanupFunctions.push(wsService.onSceneUpdated(onUpdated));
    }
    if (onDeleted) {
      cleanupFunctions.push(wsService.onSceneDeleted(onDeleted));
    }
    if (onDisplayed) {
      cleanupFunctions.push(wsService.onSceneDisplayed(onDisplayed));
    }

    return () => {
      cleanupFunctions.forEach(cleanup => cleanup());
    };
  }, [onActivated, onDeactivated, onCreated, onUpdated, onDeleted, onDisplayed]);
};

// Hook for connection status
export const useWebSocketConnection = () => {
  const [connectionStatus, setConnectionStatus] = useState(wsService.getConnectionStatus());

  useEffect(() => {
    const updateStatus = () => {
      setConnectionStatus(wsService.getConnectionStatus());
    };

    const cleanup = wsService.onConnection(updateStatus);
    
    // Update status immediately
    updateStatus();

    return cleanup;
  }, []);

  return connectionStatus;
};
