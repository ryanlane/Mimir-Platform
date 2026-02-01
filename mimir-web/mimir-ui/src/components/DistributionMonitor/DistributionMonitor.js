import React, { useState, useEffect } from 'react';
import { Activity, Database, Zap, Clock, TrendingUp, Users } from 'lucide-react';
import { useWebSocketEvent } from '../../hooks/useWebSocket';
import { api } from '../../services/api';
import './DistributionMonitor.css';

const DistributionMonitor = ({ compact = false }) => {
  const [distributionEvents, setDistributionEvents] = useState([]);
  const [performanceMetrics, setPerformanceMetrics] = useState({
    totalScenes: 0,
    activeLeases: 0,
    queueItems: 0,
    assignmentsRate: 0,
    redisConnected: false
  });
  const [eventCount, setEventCount] = useState(0);
  const [isMonitoring, setIsMonitoring] = useState(true);

  // Check Redis status on component mount
  useEffect(() => {
    const checkRedisStatus = async () => {
      try {
        const response = await api.getRedisStatus();
        if (response.data && response.data.redis_available) {
          setPerformanceMetrics(prev => ({
            ...prev,
            redisConnected: true
          }));
        }
      } catch (error) {
        console.warn('Could not check Redis status:', error);
        // Keep default false state
      }
    };

    checkRedisStatus();
  }, []);

  // Listen to distribution events via WebSocket
  useWebSocketEvent('message', (data) => {
    const eventData = typeof data === 'string' ? JSON.parse(data) : data;
    
    // Filter distribution-related events
    if (eventData.event && (
      eventData.event.includes('distribution') ||
      eventData.event.includes('content_') ||
      eventData.event.includes('epoch') ||
      eventData.event.includes('queue') ||
      eventData.event.includes('lease') ||
      eventData.event.includes('performance')
    )) {
      addDistributionEvent(eventData);
    }
  });

  const updatePerformanceMetrics = (data) => {
    setPerformanceMetrics(prev => ({
      ...prev,
      totalScenes: data.total_scenes ?? prev.totalScenes,
      activeLeases: data.active_leases ?? prev.activeLeases,
      queueItems: data.total_queue_items ?? prev.queueItems,
      assignmentsRate: data.assignments_per_minute ?? prev.assignmentsRate,
      redisConnected: data.redis_connected ?? prev.redisConnected
    }));
  };

  const addDistributionEvent = (eventData) => {
    if (!isMonitoring) return;

    setEventCount(prev => prev + 1);
    
    // If we're receiving distribution events, Redis must be connected
    if (eventData.event && (
      eventData.event.includes('distribution') ||
      eventData.event.includes('content_') ||
      eventData.event.includes('epoch') ||
      eventData.event.includes('queue') ||
      eventData.event.includes('scene_')
    )) {
      setPerformanceMetrics(prev => ({
        ...prev,
        redisConnected: true
      }));
    }
    
    const newEvent = {
      id: Date.now() + Math.random(),
      timestamp: new Date(eventData.timestamp || new Date()).toLocaleTimeString(),
      event: eventData.event,
      data: eventData.data,
      type: getEventType(eventData.event)
    };

    setDistributionEvents(prev => {
      const updated = [newEvent, ...prev];
      return updated.slice(0, compact ? 5 : 20); // Limit events
    });

    // Update performance metrics if it's a performance event
    if (eventData.event.includes('performance') && eventData.data) {
      updatePerformanceMetrics(eventData.data);
    }
  };

  const getEventType = (eventName) => {
    if (eventName.includes('content_') || eventName.includes('assignment')) return 'content';
    if (eventName.includes('performance') || eventName.includes('metrics')) return 'performance';
    if (eventName.includes('queue') || eventName.includes('epoch')) return 'queue';
    if (eventName.includes('lease')) return 'lease';
    return 'other';
  };

  const clearEvents = () => {
    setDistributionEvents([]);
    setEventCount(0);
  };

  const toggleMonitoring = () => {
    setIsMonitoring(!isMonitoring);
  };

  const getEventIcon = (type) => {
    switch (type) {
      case 'content': return <Users size={16} />;
      case 'performance': return <TrendingUp size={16} />;
      case 'queue': return <Database size={16} />;
      case 'lease': return <Clock size={16} />;
      default: return <Activity size={16} />;
    }
  };

  const getEventColor = (type) => {
    switch (type) {
      case 'content': return 'var(--color-success)';
      case 'performance': return 'var(--color-info)';
      case 'queue': return 'var(--color-warning)';
      case 'lease': return 'var(--color-accent)';
      default: return 'var(--color-primary)';
    }
  };

  if (compact) {
    return (
      <div className="distribution-monitor-compact">
        <div className="monitor-header">
          <div className="flex items-center gap-sm">
            <Zap size={18} />
            <h4>Distribution Events</h4>
            <span className="event-counter">{eventCount}</span>
          </div>
          <div className="monitor-controls">
            <button 
              className={`btn btn-xs ${isMonitoring ? 'btn-success' : 'btn-secondary'}`}
              onClick={toggleMonitoring}
              title={isMonitoring ? 'Pause monitoring' : 'Resume monitoring'}
            >
              {isMonitoring ? '⏸️' : '▶️'}
            </button>
          </div>
        </div>

        <div className="performance-indicators">
          <div className="metric-item">
            <span className="metric-label">Active Leases</span>
            <span className="metric-value">{performanceMetrics.activeLeases}</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Queue Items</span>
            <span className="metric-value">{performanceMetrics.queueItems}</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Redis</span>
            <span className={`metric-status ${performanceMetrics.redisConnected ? 'connected' : 'disconnected'}`}>
              {performanceMetrics.redisConnected ? '✅' : '❌'}
            </span>
          </div>
        </div>

        <div className="events-list-compact">
          {distributionEvents.length === 0 ? (
            <div className="empty-events">
              <span className="text-tertiary">Waiting for distribution events...</span>
            </div>
          ) : (
            distributionEvents.map(event => (
              <div key={event.id} className="event-item-compact">
                <div className="event-header">
                  <span 
                    className="event-icon" 
                    style={{ color: getEventColor(event.type) }}
                  >
                    {getEventIcon(event.type)}
                  </span>
                  <span className="event-name">{event.event}</span>
                  <span className="event-time">{event.timestamp}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="distribution-monitor">
      <div className="monitor-header">
        <div className="flex items-center gap-sm">
          <Zap size={20} />
          <h3>Distribution Monitoring</h3>
          <span className="event-counter">{eventCount} events</span>
        </div>
        <div className="monitor-controls">
          <button 
            className="btn btn-sm btn-secondary"
            onClick={clearEvents}
          >
            Clear
          </button>
          <button 
            className={`btn btn-sm ${isMonitoring ? 'btn-success' : 'btn-primary'}`}
            onClick={toggleMonitoring}
          >
            {isMonitoring ? 'Pause' : 'Resume'}
          </button>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <Database size={16} />
            <span>Total Scenes</span>
          </div>
          <div className="metric-value">{performanceMetrics.totalScenes}</div>
        </div>
        <div className="metric-card">
          <div className="metric-header">
            <Clock size={16} />
            <span>Active Leases</span>
          </div>
          <div className="metric-value">{performanceMetrics.activeLeases}</div>
        </div>
        <div className="metric-card">
          <div className="metric-header">
            <Users size={16} />
            <span>Queue Items</span>
          </div>
          <div className="metric-value">{performanceMetrics.queueItems}</div>
        </div>
        <div className="metric-card">
          <div className="metric-header">
            <TrendingUp size={16} />
            <span>Assignments/Min</span>
          </div>
          <div className="metric-value">
            {performanceMetrics.assignmentsRate.toFixed(1)}
          </div>
        </div>
      </div>

      <div className="events-section">
        <h4>Recent Events</h4>
        <div className="events-list">
          {distributionEvents.length === 0 ? (
            <div className="empty-events">
              <Activity size={24} />
              <span>Waiting for distribution events...</span>
              <p className="text-tertiary">
                Events will appear here when content assignments, queue updates, or performance metrics are received.
              </p>
            </div>
          ) : (
            distributionEvents.map(event => (
              <div key={event.id} className="event-item">
                <div className="event-header">
                  <span 
                    className="event-icon" 
                    style={{ color: getEventColor(event.type) }}
                  >
                    {getEventIcon(event.type)}
                  </span>
                  <span className="event-name">{event.event}</span>
                  <span className="event-time">{event.timestamp}</span>
                </div>
                {event.data && (
                  <div className="event-data">
                    <pre>{JSON.stringify(event.data, null, 2)}</pre>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default DistributionMonitor;
