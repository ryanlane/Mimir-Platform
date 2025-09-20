import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Monitor, Layers, Activity, Play } from 'lucide-react';
import { api } from '../../services/api';
import { useEnsureFreshState, useSceneEvents } from '../../hooks/useWebSocket';
import './Dashboard.css';

// --- New Dashboard Concept -------------------------------------------------
// 1. Summary bar (displays online/offline, active scenes, unassigned displays)
// 2. Active Displays Grid (icon cards with status + scene + quick actions)
// 3. Quick Scene Launcher (recent or all scenes with counts)
// 4. Lightweight recent activity (last few scene changes) – optional
// Channel status & verbose logging removed to reduce noise.

const Dashboard = () => {
  const [displays, setDisplays] = useState([]);
  const [scenes, setScenes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activity, setActivity] = useState([]); // recent scene events
  const [mqttFeed, setMqttFeed] = useState([]); // mqtt + display status events

  const { isConnected, currentState } = useEnsureFreshState();

  // WebSocket scene events update activity + optionally refresh displays
  useSceneEvents({
    onActivated: (data) => recordActivity(`Scene "${data.sceneName || data.sceneId || data.id}" activated`),
    onDisplayed: (data) => recordActivity(`Scene "${data.sceneName || data.sceneId}" displayed`),
    onCreated: (data) => { recordActivity(`Scene "${data.sceneName || data.sceneId}" created`); refreshScenes(); },
    onDeleted: (data) => { recordActivity(`Scene "${data.sceneName || data.sceneId}" deleted`); refreshScenes(); }
  });

  const recordActivity = (msg) => setActivity(prev => [{ ts: new Date(), msg }, ...prev].slice(0, 6));
  const recordMqtt = (type, payload) => setMqttFeed(prev => [
    { ts: new Date(), type, payload },
    ...prev
  ].slice(0, 25));

  const refreshDisplays = useCallback(async () => {
    try {
      const resp = await api.getDisplays({ limit: 100 });
      const list = Array.isArray(resp.data) ? resp.data : [];
      setDisplays(list);
    } catch (e) {
      console.error('Failed to load displays', e);
    }
  }, []);

  const refreshScenes = useCallback(async () => {
    try {
      const resp = await api.getScenes({ limit: 50 });
      setScenes(resp.data.scenes || []);
    } catch (e) {
      console.error('Failed to load scenes', e);
    }
  }, []);

  // Initial load (fallback if websocket state not populated quickly)
  useEffect(() => {
    let timeout = setTimeout(() => {
      refreshDisplays();
      refreshScenes();
      setLoading(false);
    }, 500);
    return () => clearTimeout(timeout);
  }, [refreshDisplays, refreshScenes]);

  // If websocket provided displays/scenes in state
  useEffect(() => {
    if (currentState) {
      if (currentState.displays) setDisplays(currentState.displays);
      if (currentState.allScenes) setScenes(currentState.allScenes);
      setLoading(false);
    }
  }, [currentState]);

  // Listen for display status & generic mqtt-related events via websocket raw events
  useEffect(() => {
    // Access underlying ws service lazily to avoid import cycle
    const { wsService } = require('../../services/websocket');

    const cleanupDisplay = wsService.on('display_status_changed', (data) => {
      recordMqtt('display_status', data);
      // Patch local display list if present
      if (data?.displayId || data?.id) {
        setDisplays(prev => prev.map(d => (d.id === (data.displayId || data.id) ? { ...d, ...data } : d)));
      }
    });
    // Generic server forwarded mqtt message (if backend emits 'mqtt_message')
    const cleanupMqtt = wsService.on('mqtt_message', (data) => {
      recordMqtt('mqtt', data);
    });
    return () => { cleanupDisplay(); cleanupMqtt(); };
  }, []);

  // ---- Derived Metrics ----
  const onlineDisplays = displays.filter(d => d.is_online !== false);
  const offlineDisplays = displays.filter(d => d.is_online === false);
  const displaysWithScene = displays.filter(d => d.assigned_scene_id || d.assignedSceneId);
  const unassignedDisplays = displays.filter(d => !d.assigned_scene_id && !d.assignedSceneId);

  const sceneDisplayCounts = scenes.reduce((acc, s) => {
    const count = displaysWithScene.filter(d => (d.assigned_scene_id || d.assignedSceneId) === s.id).length;
    acc[s.id] = count; return acc;
  }, {});

  const handleDisplayScene = async (sceneId) => {
    try {
      await api.displayScene(sceneId);
      recordActivity(`Display scene triggered: ${sceneId}`);
      // small delay then refresh to reflect new assignments
      setTimeout(refreshDisplays, 800);
    } catch (e) {
      console.error('Failed to display scene', e);
      recordActivity(`Failed to display scene ${sceneId}`);
    }
  };

  const DisplayCard = ({ d }) => {
    const sceneName = d.assigned_scene_name || d.assignedSceneName;
    return (
      <div className={`display-card ${d.is_online !== false ? 'online' : 'offline'}`}>
        <div className="display-card-header">
          <Monitor size={18} />
          <span className="name" title={d.name}>{d.name}</span>
        </div>
        <div className="display-card-body">
          <div className="scene-line">
            {sceneName ? <span className="scene-badge">{sceneName}</span> : <span className="scene-badge empty">Unassigned</span>}
          </div>
          <div className="meta">
            <span className="loc" title={d.location || 'No location'}>{d.location || '—'}</span>
            <span className={`status-dot ${d.is_online !== false ? 'up' : 'down'}`}></span>
          </div>
        </div>
      </div>
    );
  };

  const QuickSceneList = () => {
    if (!scenes.length) return <p className="text-tertiary">No scenes</p>;
    return (
      <div className="quick-scenes">
        {scenes.slice(0, 10).map(s => (
          <button key={s.id} className="scene-chip" onClick={() => handleDisplayScene(s.id)}>
            <Layers size={14} />
            <span className="label">{s.name}</span>
            <span className="count">{sceneDisplayCounts[s.id] || 0}</span>
          </button>
        ))}
        <Link to="/scenes" className="scene-chip secondary" title="Manage scenes">Manage…</Link>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <span>Loading dashboard…</span>
      </div>
    );
  }

  return (
    <div className="dashboard new-layout">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p className="text-tertiary">Real-time overview of displays & scenes{isConnected && <span className="connection-status"> • Live</span>}</p>
      </div>
      {/* Summary Bar */}
      <div className="summary-bar">
        <div className="metric"><span className="metric-label">Displays</span><span className="metric-value">{displays.length}</span></div>
        <div className="metric"><span className="metric-label">Online</span><span className="metric-value success">{onlineDisplays.length}</span></div>
        <div className="metric"><span className="metric-label">Offline</span><span className="metric-value danger">{offlineDisplays.length}</span></div>
        <div className="metric"><span className="metric-label">Scenes Active</span><span className="metric-value">{Object.values(sceneDisplayCounts).filter(c => c>0).length}</span></div>
        <div className="metric"><span className="metric-label">Unassigned</span><span className="metric-value warning">{unassignedDisplays.length}</span></div>
      </div>

      {/* Active Displays Grid */}
      <section className="panel">
        <div className="panel-header">
          <h3><Monitor size={18} /> Active Displays</h3>
          <Link to="/displays" className="link-sm">View All</Link>
        </div>
        <div className="display-grid">
          {displays.length ? (
            displays.map(d => <DisplayCard key={d.id} d={d} />)
          ) : (
            <div className="empty">No displays discovered</div>
          )}
        </div>
      </section>

      {/* Quick Scene Launcher */}
      <section className="panel">
        <div className="panel-header">
          <h3><Play size={18} /> Quick Scenes</h3>
        </div>
        <QuickSceneList />
      </section>

      {/* Recent Activity */}
      <section className="panel activity-panel">
        <div className="panel-header">
          <h3><Activity size={18} /> Recent Activity</h3>
        </div>
        <ul className="activity-feed">
          {activity.length ? activity.map((a,i) => (
            <li key={i}><span className="ts">{a.ts.toLocaleTimeString()}</span> {a.msg}</li>
          )) : <li className="empty">No recent events</li>}
        </ul>
      </section>

      {/* Real-time Display / MQTT Feed */}
      <section className="panel activity-panel">
        <div className="panel-header">
          <h3><Activity size={18} /> Live Device Feed</h3>
        </div>
        <ul className="activity-feed">
          {mqttFeed.length ? mqttFeed.map((e,i) => (
            <li key={i}>
              <span className="ts">{e.ts.toLocaleTimeString()}</span>
              <strong>[{e.type}]</strong>&nbsp;
              {formatMqttPayload(e)}
            </li>
          )) : <li className="empty">No device updates</li>}
        </ul>
      </section>

      {/* Footer small status */}
      <div className="dashboard-footer">
        <span className={`conn-dot ${isConnected ? 'up' : 'down'}`}></span>
        {isConnected ? 'WebSocket connected' : 'Live connection unavailable'}
      </div>
    </div>
  );
};

export default Dashboard;

// Helper to format feed entries (placed after export to avoid re-renders from function identity changes)
function formatMqttPayload(entry) {
  try {
    const p = entry.payload || {};
    if (entry.type === 'display_status') {
      const name = p.name || p.displayName || p.id || 'display';
      const online = p.is_online !== false;
      return `${name} is ${online ? 'online' : 'offline'}${p.assigned_scene_name ? ' • scene=' + p.assigned_scene_name : ''}`;
    }
    if (entry.type === 'mqtt') {
      if (p.topic && p.payload) return `${p.topic}: ${truncate(JSON.stringify(p.payload), 60)}`;
    }
    return truncate(JSON.stringify(p).replace(/"/g, ''), 80);
  } catch (e) {
    return 'unparseable payload';
  }
}

function truncate(str, len) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len - 1) + '…' : str;
}
