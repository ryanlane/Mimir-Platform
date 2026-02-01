import React, { useEffect, useRef, useState } from 'react';
import wsService from '../../../services/websocket';
import PropTypes from 'prop-types';
import './SceneLiveStatus.css';

/**
 * SceneLiveStatus
 * Displays real-time scene activation/deactivation and content refresh events via WebSocket.
 * Shows current active scene, last event age, and a rolling log (in-memory, capped).
 */
const MAX_LOG = 25;

const SceneLiveStatus = ({ initialSceneId, initialSceneName }) => {
  const [activeScene, setActiveScene] = useState(
    initialSceneId ? { id: initialSceneId, name: initialSceneName } : null
  );
  const [lastEventTs, setLastEventTs] = useState(null);
  const [eventLog, setEventLog] = useState([]);
  const [connected, setConnected] = useState(wsService.isConnected);
  const intervalRef = useRef(null);
  const [, forceTick] = useState(0); // force re-render for relative time updates

  const pushLog = (entry) => {
    setEventLog(prev => [entry, ...prev].slice(0, MAX_LOG));
    setLastEventTs(Date.now());
  };

  useEffect(() => {
    const cleanupFns = [];

    cleanupFns.push(wsService.on('connection', (c) => {
      setConnected(c.status === 'connected');
      pushLog({ type: 'connection', status: c.status, ts: Date.now() });
    }));

    cleanupFns.push(wsService.on('scene_activated', (data) => {
      const sceneId = data?.sceneId || data?.scene_id || data?.id;
      const sceneName = data?.sceneName || data?.scene_name || data?.name;
      setActiveScene(sceneId ? { id: sceneId, name: sceneName } : null);
      pushLog({ type: 'scene_activated', sceneId, sceneName, ts: Date.now() });
    }));

    cleanupFns.push(wsService.on('scene_deactivated', (data) => {
      pushLog({ type: 'scene_deactivated', prev: activeScene, ts: Date.now() });
      setActiveScene(null);
    }));

    cleanupFns.push(wsService.on('scene_content_refreshed', (data) => {
      pushLog({ type: 'scene_content_refreshed', sceneId: data?.scene_id || data?.sceneId, ts: Date.now(), meta: data });
    }));

    cleanupFns.push(wsService.on('scene_updated', (data) => {
      pushLog({ type: 'scene_updated', sceneId: data?.scene_id || data?.id, ts: Date.now() });
    }));

    cleanupFns.push(wsService.on('scene_displayed', (data) => {
      pushLog({ type: 'scene_displayed', sceneId: data?.scene_id || data?.id, ts: Date.now() });
    }));

    // Keep relative time updated
    intervalRef.current = setInterval(() => forceTick(x => x + 1), 5000);

    return () => {
      cleanupFns.forEach(fn => fn && fn());
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const ageLabel = () => {
    if (!lastEventTs) return '—';
    const secs = Math.floor((Date.now() - lastEventTs) / 1000);
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    return `${mins}m ago`;
  };

  return (
    <div className="scene-live-status">
      <div className="sls-header">
        <span className={`sls-conn ${connected ? 'up' : 'down'}`}>{connected ? 'WS Live' : 'WS Down'}</span>
        <span className="sls-active-label">Active Scene:</span>
        {activeScene ? (
          <span className="sls-active" title={activeScene.id}>{activeScene.name}</span>
        ) : (
          <span className="sls-none">None</span>
        )}
        <span className="sls-last-event">Last Event: {ageLabel()}</span>
      </div>
      {eventLog.length > 0 && (
        <div className="sls-log">
          {eventLog.slice(0, 8).map((e, idx) => (
            <div key={idx} className={`sls-log-row type-${e.type}`}> 
              <span className="time">{new Date(e.ts).toLocaleTimeString()}</span>
              <span className="etype">{e.type.replace(/scene_/,'')}</span>
              {e.sceneName && <span className="ename">{e.sceneName}</span>}
              {e.sceneId && !e.sceneName && <span className="eid" title={e.sceneId}>{e.sceneId.slice(0,8)}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

SceneLiveStatus.propTypes = {
  initialSceneId: PropTypes.string,
  initialSceneName: PropTypes.string
};

export default SceneLiveStatus;
