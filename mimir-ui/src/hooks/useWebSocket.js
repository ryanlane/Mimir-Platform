import { useEffect, useRef, useState } from 'react';
import wsService from '../services/websocket';

// Hook for WebSocket connection management
export const useWebSocket = () => {
  const connectionInitialized = useRef(false);

  useEffect(() => {
    if (!connectionInitialized.current) {
      wsService.connect();
      connectionInitialized.current = true;
    }

    return () => {
      // Don't disconnect on unmount as this is a global service
      // Only disconnect when the app is closing
    };
  }, []);

  return wsService;
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
