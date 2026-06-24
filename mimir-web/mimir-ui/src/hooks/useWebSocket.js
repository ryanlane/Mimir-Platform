// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

import { useEffect, useRef, useState } from 'react';
import wsService from '../services/websocket';

// Hook for WebSocket connection management with enhanced features
export const useWebSocket = () => {
  const connectionInitialized = useRef(false);
  const stateSyncRequested = useRef(false);
  const [isConnected, setIsConnected] = useState(wsService.isConnected);
  const [currentState, setCurrentState] = useState(null);

  useEffect(() => {
    if (!connectionInitialized.current) {
      // Start connection
      wsService.connect();
      connectionInitialized.current = true;
    }

    // Enhanced event listeners
    const handleConnection = (data) => {
      setIsConnected(data.status === 'connected');
      
      // Auto-request state sync when connection is established and we don't have current state
      if (data.status === 'connected' && !currentState && !stateSyncRequested.current) {
        console.log('🔄 Connection established, requesting state sync');
        setTimeout(() => {
          wsService.requestStateSync();
          stateSyncRequested.current = true;
        }, 100); // Small delay to ensure connection is fully established
      }
    };

    const handleFullState = (state) => {
      console.log('🚀 Full state received:', state);
      setCurrentState(state);
      stateSyncRequested.current = false; // Reset flag so we can request again if needed
    };

    const handleServerError = (error) => {
      console.error('🚨 Server error:', error);
    };

    const cleanupConnection = wsService.on('connection', handleConnection);
    const cleanupFullState = wsService.on('full_state_received', handleFullState);
    const cleanupError = wsService.on('server_error', handleServerError);

    // Initialize state
    setIsConnected(wsService.isConnected);
    
    // If already connected but no state, request sync
    if (wsService.isConnected && !currentState && !stateSyncRequested.current) {
      console.log('🔄 Already connected but no state, requesting sync');
      setTimeout(() => {
        wsService.requestStateSync();
        stateSyncRequested.current = true;
      }, 100);
    }

    return () => {
      cleanupConnection();
      cleanupFullState();
      cleanupError();
      // Don't disconnect on unmount as this is a global service
    };
  }, [currentState]); // Add currentState as dependency so it can trigger sync when needed

  return {
    wsService,
    isConnected,
    currentState,
    requestStateSync: () => {
      console.log('🔄 Manual state sync requested');
      wsService.requestStateSync();
      stateSyncRequested.current = true;
    }
  };
};

// Hook for ensuring fresh state on component mount
export const useEnsureFreshState = () => {
  const { isConnected, currentState, requestStateSync } = useWebSocket();
  const syncAttempted = useRef(false);

  useEffect(() => {
    // Only request sync once per component mount, and only if we're connected but have no state
    if (isConnected && !currentState && !syncAttempted.current) {
      console.log('🔄 Component mounted without state, requesting sync');
      requestStateSync();
      syncAttempted.current = true;
    }
  }, [isConnected, currentState, requestStateSync]);

  return { isConnected, currentState, requestStateSync };
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
