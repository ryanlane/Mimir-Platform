import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Monitor, Layers, Activity } from 'lucide-react';
import { api } from '../../services/api';
import { useEnsureFreshState, useSceneEvents } from '../../hooks/useWebSocket';
import './Dashboard.css';
import MqttFeed from '../../components/MqttFeed/MqttFeed';
import Header from '../../components/Header/Header';

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
  const [channels, setChannels] = useState([]); // channel metadata
  const [channelUsage, setChannelUsage] = useState({}); // channel_id -> count of scenes using
  const [schedulerJobs, setSchedulerJobs] = useState([]); // raw jobs
  const [sceneNextRuns, setSceneNextRuns] = useState({}); // sceneId -> timestamp (ms)
  const [nextGlobalRun, setNextGlobalRun] = useState(null); // earliest next run (ms)
  const [now, setNow] = useState(Date.now()); // ticking clock for countdowns
  // Distribution overview (minimal subset migrated from deprecated Distribution page)
  const [distributionOverview, setDistributionOverview] = useState(null);

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
  ].slice(0, 500)); // allow deeper history for debugging

  // --- Normalization Helpers ----------------------------------------------
  const normalizeDisplay = useCallback((d) => {
    if (!d || typeof d !== 'object') return null;
    // Some API responses wrap assigned_scene_id as an object { id, subchannel_id }
    let assignedScene = d.assigned_scene_id || d.assignedSceneId || d.scene_id || null;
    if (assignedScene && typeof assignedScene === 'object') {
      assignedScene = assignedScene.id || assignedScene.scene_id || null;
    }
    return {
      id: d.id || d.display_id || d.device_id || d.hostname || d.name,
      name: d.name || d.display_name || d.hostname || 'Unnamed',
      location: d.location || d.site || d.room || null,
      is_online: d.is_online !== undefined ? d.is_online : (d.online !== undefined ? d.online : true),
      assigned_scene_id: assignedScene,
      assigned_scene_name: d.assigned_scene_name || d.assignedSceneName || d.scene_name || d.scene || null,
      last_seen: d.last_seen || d.lastSeen || null
    };
  }, []);

  const normalizeScene = useCallback((s) => {
    if (!s || typeof s !== 'object') return null;
    return {
      id: s.id || s.scene_id,
      name: s.name || s.scene_name || 'Unnamed Scene',
      is_active: s.is_active !== undefined ? s.is_active : s.active,
      channels: s.channels || [],
      distribution_mode: s.distribution_mode || s.mode || null
    };
  }, []);

  const normalizeDisplayArray = useCallback((arr) => (Array.isArray(arr) ? arr.map(normalizeDisplay).filter(Boolean) : []), [normalizeDisplay]);
  const normalizeSceneArray = useCallback((arr) => (Array.isArray(arr) ? arr.map(normalizeScene).filter(Boolean) : []), [normalizeScene]);

  const refreshDisplays = useCallback(async () => {
    try {
      const MAX_LIMIT = 100; // Backend enforces le=100
      const resp = await api.getDisplays({ limit: MAX_LIMIT });
      // Possible shapes: { displays: [...] }, { data: [...] }, [...]
      const raw = resp.data?.displays || resp.data?.data || resp.data?.items || (Array.isArray(resp.data) ? resp.data : []);
      if (!raw || !raw.length) {
        console.debug('[Dashboard] Displays fetch returned empty shape', resp.data);
      }
      setDisplays(normalizeDisplayArray(raw));
    } catch (e) {
      console.error('Failed to load displays', e);
    }
  }, [normalizeDisplayArray]);

  const refreshScenes = useCallback(async () => {
    try {
      const resp = await api.getScenes({ limit: 200 });
      // Expected shape: { scenes: [...] }
      const raw = resp.data?.scenes || resp.data?.items || (Array.isArray(resp.data) ? resp.data : []);
      setScenes(normalizeSceneArray(raw));
    } catch (e) {
      console.error('Failed to load scenes', e);
    }
  }, [normalizeSceneArray]);

  const refreshChannels = useCallback(async () => {
    try {
      const resp = await api.getChannels();
      const raw = resp.data?.channels || resp.data || [];
      setChannels(raw);
    } catch (e) {
      console.error('Failed to load channels', e);
    }
  }, []);

  useEffect(() => { refreshChannels(); }, [refreshChannels]);

  // Lightweight distribution overview loader (non-blocking)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await api.getDistributionOverview().catch(e => {
          // Treat missing endpoint as non-fatal (feature may be disabled)
          if (process.env.NODE_ENV !== 'production') {
            console.debug('[Dashboard] Distribution overview unavailable:', e?.message);
          }
          return { data: null };
        });
        if (!cancelled) {
          setDistributionOverview(resp.data || null);
        }
      } catch (e) {/* silent */}
    })();
    // refresh every 60s if present
    const interval = setInterval(() => {
      api.getDistributionOverview().then(r => {
        if (!cancelled) setDistributionOverview(r.data || null);
      }).catch(() => {/* silent */});
    }, 60000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // recompute channel usage whenever scenes or channels change
  useEffect(() => {
    if (!channels.length || !scenes.length) {
      setChannelUsage({});
      return;
    }
    // Scenes have channels array; normalize IDs (could be objects or strings)
    const usage = {};
    scenes.forEach(s => {
      (s.channels || []).forEach(ch => {
        let id = null;
        if (typeof ch === 'string') id = ch;
        else if (ch && typeof ch === 'object') id = ch.id || ch.channel_id || ch.name; // fallback to name
        if (id) usage[id] = (usage[id] || 0) + 1;
      });
    });
    setChannelUsage(usage);
  }, [scenes, channels]);

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
      if (currentState.displays) setDisplays(normalizeDisplayArray(currentState.displays));
      else if (currentState.displayClients) setDisplays(normalizeDisplayArray(currentState.displayClients));
      if (currentState.allScenes) setScenes(normalizeSceneArray(currentState.allScenes));
      setLoading(false);
    }
  }, [currentState, normalizeDisplayArray, normalizeSceneArray]);

  // Listen for display status & generic mqtt-related events via websocket raw events
  useEffect(() => {
    const { wsService } = require('../../services/websocket');
    const cleanupDisplay = wsService.on('display_status_changed', (data) => {
      recordMqtt('display_status', data);
      const nd = normalizeDisplay(data);
      if (!nd || !nd.id) return;
      setDisplays(prev => {
        const idx = prev.findIndex(p => p.id === nd.id);
        if (idx === -1) return [...prev, nd];
        const copy = [...prev];
        copy[idx] = { ...copy[idx], ...nd };
        return copy;
      });
    });
    const cleanupMqtt = wsService.on('mqtt_message', (data) => {
      try {
        console.debug('[Dashboard] mqtt_message event', data);
        const topic = data?.topic || '';
        if (!topic.startsWith('mimir/')) return;
        // normalize shape expected by feed component (payload.payload)
        recordMqtt('mqtt', { topic, payload: data.payload, raw_payload: data.raw_payload });
      } catch (err) {
        console.warn('Failed handling mqtt_message event', err, data);
      }
    });
    return () => { cleanupDisplay(); cleanupMqtt(); };
  }, [normalizeDisplay]);

  // Tick every second for live countdowns
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const refreshSchedulerJobs = useCallback(async () => {
    try {
      const resp = await api.getSchedulerJobs({ limit: 200 });
      const jobs = resp.data?.jobs || resp.data || [];
      setSchedulerJobs(jobs);
    } catch (e) {
      console.error('Failed to load scheduler jobs', e);
    }
  }, []);

  // Map jobs to scene next run times
  useEffect(() => {
    const mapping = {};
    let earliest = null;
    schedulerJobs.forEach(job => {
      // Heuristic: job.action_type === 'refresh_scene' or job references scene_ids
      const sceneIds = job.scene_ids || job.sceneIds || [];
      const nextRunRaw = job.next_run || job.nextRun || job.next_execution_time;
      if (!nextRunRaw) return;
      const ts = typeof nextRunRaw === 'number' ? nextRunRaw * (nextRunRaw < 10_000_000_000 ? 1000 : 1) : Date.parse(nextRunRaw);
      if (Number.isNaN(ts)) return;
      sceneIds.forEach(sid => {
        if (!mapping[sid] || ts < mapping[sid]) mapping[sid] = ts;
      });
      if (!earliest || ts < earliest) earliest = ts;
    });
    setSceneNextRuns(mapping);
    setNextGlobalRun(earliest);
  }, [schedulerJobs]);

  // Initial + periodic polling for scheduler jobs (every 60s)
  useEffect(() => {
    refreshSchedulerJobs();
    const id = setInterval(refreshSchedulerJobs, 60000);
    return () => clearInterval(id);
  }, [refreshSchedulerJobs]);

  // ---- Derived Metrics ----
  const onlineDisplays = displays.filter(d => d.is_online !== false);
  const offlineDisplays = displays.filter(d => d.is_online === false);
  const displaysWithScene = displays.filter(d => d.assigned_scene_id || d.assignedSceneId);
  const unassignedDisplays = displays.filter(d => !d.assigned_scene_id && !d.assignedSceneId);

  const sceneDisplayCounts = scenes.reduce((acc, s) => {
    const count = displaysWithScene.filter(d => {
      const assigned = d.assigned_scene_id || d.assignedSceneId;
      return assigned === s.id;
    }).length;
    acc[s.id] = count; return acc;
  }, {});

  const formatDelta = (futureTs) => {
    if (!futureTs) return null;
    const diff = Math.max(0, futureTs - now);
    const s = Math.floor(diff / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h) return `${h}h ${m}m ${sec}s`;
    if (m) return `${m}m ${sec}s`;
    return `${sec}s`;
  };

  const DisplayCard = ({ d }) => {
    const sceneName = d.assigned_scene_name || d.assignedSceneName;
    return (
      <div className={`dashboard-display-card ${d.is_online !== false ? 'online' : 'offline'}`}>
        <div className="dashboard-display-card-header">
          <Monitor size={18} />
          <span className="name" title={d.name}>{d.name}</span>
        </div>
  <div className="dashboard-display-card-body">
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

  // Extend ScenesOverview card with schedule badge
  const ScenesOverview = () => {
    if (!scenes.length) return <p className="text-tertiary">No scenes</p>;
    return (
      <div className="scenes-overview-grid">
        {scenes.map(s => {
          const count = sceneDisplayCounts[s.id] || 0;
          const nextRun = sceneNextRuns[s.id];
          const delta = formatDelta(nextRun);
          return (
            <div key={s.id} className={`scene-overview-card ${s.is_active ? 'active' : ''}`}> 
              <div className="soc-header">
                <Layers size={14} />
                <span className="soc-name" title={s.name}>{s.name}</span>
              </div>
              <div className="soc-body">
                <span className="soc-count" title="Assigned displays">{count} display{count === 1 ? '' : 's'}</span>
                {s.distribution_mode && <span className="soc-mode" title="Distribution mode">{s.distribution_mode}</span>}
              </div>
              {delta && <div className="soc-next-run" title={new Date(nextRun).toLocaleString()}>↻ {delta}</div>}
            </div>
          );
        })}
        <Link to="/scenes" className="scene-overview-card manage-link" title="Manage scenes">Manage…</Link>
      </div>
    );
  };

  // Global countdown banner (earliest scene refresh)
  const GlobalNextRefresh = () => {
    if (!nextGlobalRun) return null;
    const delta = formatDelta(nextGlobalRun);
    if (!delta) return null;
    return (
      <div className="global-next-refresh" title={new Date(nextGlobalRun).toLocaleString()}>
        Next scheduled scene refresh in <strong>{delta}</strong>
      </div>
    );
  };

  const ChannelUsageBar = () => {
    if (!channels.length) return <div className="channel-usage-bar empty">No channels</div>;
    return (
      <div className="channel-usage-bar">
        {channels.map(ch => {
          const id = ch.id || ch.channel_id || ch.identifier;
          const count = channelUsage[id] || 0;
          return (
            <div key={id} className={`channel-usage-item ${count === 0 ? 'unused' : ''}`} title={`${count} scene(s)`}>
              <span className="c-name">{ch.name || id}</span>
              <span className="c-count">{count}</span>
            </div>
          );
        })}
      </div>
    );
  };

  // (MqttFeed extracted to components/MqttFeed)

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
      <Header title="Dashboard" icon="Home" iconSize={36} description="Real-time overview of displays & scenes" />

      {/* Summary Bar */}
      <div className="summary-bar">
        <div className="metric"><span className="metric-label">Displays</span><span className="metric-value">{displays.length}</span></div>
        <div className="metric"><span className="metric-label">Online</span><span className="metric-value success">{onlineDisplays.length}</span></div>
        <div className="metric"><span className="metric-label">Offline</span><span className="metric-value danger">{offlineDisplays.length}</span></div>
        <div className="metric"><span className="metric-label">Scenes Active</span><span className="metric-value">{Object.values(sceneDisplayCounts).filter(c => c>0).length}</span></div>
        <div className="metric"><span className="metric-label">Unassigned</span><span className="metric-value warning">{unassignedDisplays.length}</span></div>
      </div>
      <GlobalNextRefresh />

      {/* Distribution Mini Stats (if available) */}
      {distributionOverview && (
        <div className="summary-bar distribution-mini">
          <div className="metric"><span className="metric-label">Queues</span><span className="metric-value">{distributionOverview.total_queue_items ?? 0}</span></div>
          <div className="metric"><span className="metric-label">Active Leases</span><span className="metric-value">{distributionOverview.active_leases ?? 0}</span></div>
          <div className="metric"><span className="metric-label">Dist Sys</span><span className={`metric-value ${distributionOverview.distribution_available ? 'success' : 'danger'}`}>{distributionOverview.distribution_available ? 'Active' : 'Down'}</span></div>
          <div className="metric"><span className="metric-label">Redis</span><span className={`metric-value ${distributionOverview.redis_available ? 'success' : 'danger'}`}>{distributionOverview.redis_available ? 'Up' : 'Down'}</span></div>
        </div>
      )}

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

      {/* Scenes Overview */}
      <section className="panel">
        <div className="panel-header">
          <h3><Layers size={18} /> Scenes Overview</h3>
          <Link to="/scenes" className="link-sm">View All</Link>
        </div>
        <ScenesOverview />
      </section>

      {/* Channel Usage Status */}
      <section className="panel">
        <div className="panel-header">
          <h3><Layers size={18} /> Channel Usage</h3>
        </div>
        <ChannelUsageBar />
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

  {/* Live MQTT Feed */}
  <MqttFeed feed={mqttFeed} />

      {/* Footer small status */}
      <div className="dashboard-footer">
        <span className={`conn-dot ${isConnected ? 'up' : 'down'}`}></span>
        {isConnected ? 'WebSocket connected' : 'Live connection unavailable'}
      </div>
    </div>
  );
};

export default Dashboard;

// truncate helper removed; logic now internal to MqttFeed component
