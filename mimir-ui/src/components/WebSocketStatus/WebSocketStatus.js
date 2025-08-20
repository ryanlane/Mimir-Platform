// WebSocket Status component for v2.1 API monitoring
import React, { useState, useEffect, useCallback } from 'react';
import { Wifi, WifiOff, Activity, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useFeatureDetection } from '../../hooks/useFeatureDetection';
import './WebSocketStatus.css';

const WebSocketStatus = () => {
  const { isConnected } = useWebSocket();
  const { supportsEnhancedWebSocket } = useFeatureDetection();
  const [wsStatus, setWsStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadWebSocketStatus = useCallback(async () => {
    if (!supportsEnhancedWebSocket()) {
      return;
    }

    try {
      setLoading(true);
      const response = await api.getWebSocketStatus();
      setWsStatus(response.data);
      console.log('📡 WebSocket status:', response.data);
    } catch (error) {
      console.error('Error loading WebSocket status:', error);
    } finally {
      setLoading(false);
    }
  }, [supportsEnhancedWebSocket]);

  useEffect(() => {
    loadWebSocketStatus();
    
    // Refresh status every 30 seconds
    const interval = setInterval(loadWebSocketStatus, 30000);
    return () => clearInterval(interval);
  }, [loadWebSocketStatus]);

  if (!supportsEnhancedWebSocket()) {
    return (
      <div className="websocket-status basic">
        <div className="status-indicator">
          {isConnected ? (
            <>
              <Wifi size={16} className="connected" />
              <span>Connected</span>
            </>
          ) : (
            <>
              <WifiOff size={16} className="disconnected" />
              <span>Disconnected</span>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="websocket-status enhanced">
      <div className="status-header">
        <div className="status-indicator">
          {isConnected ? (
            <>
              <Wifi size={16} className="connected" />
              <span>WebSocket Connected</span>
            </>
          ) : (
            <>
              <WifiOff size={16} className="disconnected" />
              <span>WebSocket Disconnected</span>
            </>
          )}
        </div>
        <button 
          className="btn btn-sm btn-tertiary" 
          onClick={loadWebSocketStatus}
          disabled={loading}
        >
          {loading ? <Activity size={14} className="spinning" /> : <Activity size={14} />}
          Refresh
        </button>
      </div>

      {wsStatus && (
        <div className="status-details">
          <div className="detail-grid">
            <div className="detail-item">
              <span className="label">Connected Clients:</span>
              <span className="value">{wsStatus.connected_clients}</span>
            </div>
            <div className="detail-item">
              <span className="label">Current Sequence:</span>
              <span className="value">{wsStatus.current_sequence_id}</span>
            </div>
            <div className="detail-item">
              <span className="label">WebSocket URL:</span>
              <span className="value mono">{wsStatus.websocket_url}</span>
            </div>
          </div>

          {wsStatus.features && (
            <div className="features-list">
              <h4>Enhanced Features:</h4>
              <div className="features-grid">
                {Object.entries(wsStatus.features).map(([feature, enabled]) => (
                  <div key={feature} className={`feature-item ${enabled ? 'enabled' : 'disabled'}`}>
                    {enabled ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                    <span>{feature.replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default WebSocketStatus;
