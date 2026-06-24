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

import React, { useState, useMemo } from 'react';
import { Activity } from 'lucide-react';
import './MqttFeed.css';

/**
 * MqttFeed
 * Live streaming list of MQTT-derived events forwarded over the WebSocket.
 *
 * Props:
 *  - feed: Array<{ ts: Date, type: string, payload: { topic?: string, payload?: any } }>
 *  - maxItems?: number (default 200 render cap after filtering)
 *
 * Features:
 *  - Topic substring filter
 *  - Hide heartbeats toggle (topics ending /heartbeat)
 *  - Collapse JSON (summarize to first few keys)
 *  - Basic topic classification (status | heartbeat | event | other)
 */
export default function MqttFeed({ feed, maxItems = 200, defaultShowHeartbeats = false }) {
  const [filter, setFilter] = useState('');
  const [showHeartbeats, setShowHeartbeats] = useState(defaultShowHeartbeats);
  const [collapse, setCollapse] = useState(true);

  const filtered = useMemo(() => {
    return (feed || [])
      .filter(entry => {
        if (!entry || !entry.payload) return false;
        const topic = entry.payload.topic || '';
        if (!topic.startsWith('mimir/')) return false;
        if (!showHeartbeats && /\/heartbeat$/.test(topic)) return false;
        if (filter && !topic.toLowerCase().includes(filter.toLowerCase())) return false;
        return true;
      })
      .slice(0, maxItems);
  }, [feed, filter, showHeartbeats, maxItems]);

  const classify = (e) => {
    const t = e?.payload?.topic || '';
    if (/\/status$/.test(t)) return 'status';
    if (/\/heartbeat$/.test(t)) return 'heartbeat';
    if (/\/evt$/.test(t)) return 'event';
    if (/\/cmd$/.test(t)) return 'command';
    return 'other';
  };

  const truncate = (str, len) => {
    if (!str) return '';
    return str.length > len ? str.slice(0, len - 1) + '…' : str;
  };

  const rawCount = (feed || []).length;
  const filteredCount = filtered.length;

  return (
    <section className="panel activity-panel mqtt-panel">
      <div className="panel-header">
        <h3><Activity size={18} /> Live MQTT Feed</h3>
        <div className="mqtt-feed-controls">
          <input
            type="text"
            placeholder="Filter topic..."
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="mqtt-filter-input"
          />
          <label className="mqtt-toggle">
            <input type="checkbox" checked={showHeartbeats} onChange={e => setShowHeartbeats(e.target.checked)} />
            <span>Heartbeats</span>
          </label>
          <label className="mqtt-toggle">
            <input type="checkbox" checked={collapse} onChange={e => setCollapse(e.target.checked)} />
            <span>Collapse JSON</span>
          </label>
        </div>
      </div>
      <ul className="activity-feed mqtt-feed">
        {filteredCount ? filtered.map((e, i) => {
          const topic = e?.payload?.topic;
          const kind = classify(e);
          const payload = e?.payload?.payload; // decoded json or raw string
          let rendered = '';
          try {
            if (collapse && typeof payload === 'object') {
              const keys = Object.keys(payload).slice(0, 4);
              const summary = keys.reduce((acc, k) => { acc[k] = payload[k]; return acc; }, {});
              rendered = JSON.stringify(summary);
            } else if (typeof payload === 'object') {
              rendered = JSON.stringify(payload);
            } else if (typeof payload === 'string') {
              rendered = payload;
            } else {
              rendered = String(payload);
            }
          } catch {
            rendered = '[unrenderable]';
          }
          return (
            <li key={i} className={`mqtt-feed-item kind-${kind}`}>
              <span className="ts" title={e.ts.toLocaleString()}>{e.ts.toLocaleTimeString()}</span>
              <span className="topic" title={topic}>{topic || 'unknown-topic'}</span>
              <span className="kind-badge" title={kind}>{kind}</span>
              <span className="payload" title={rendered}>{truncate(rendered, collapse ? 100 : 300)}</span>
            </li>
          );
        }) : (
          <li className="empty">
            {rawCount === 0 ? (
              'No MQTT messages received yet'
            ) : (
              <span>
                No messages match filters{!showHeartbeats && ' (heartbeats hidden)'}.
                {!showHeartbeats && (
                  <button
                    type="button"
                    style={{ marginLeft: 6 }}
                    onClick={() => setShowHeartbeats(true)}
                    className="link-button"
                  >Show Heartbeats</button>
                )}
              </span>
            )}
          </li>
        )}
      </ul>
      <div style={{ padding: '4px 6px', fontSize: '0.55rem', opacity: 0.6 }}>
        {filteredCount} shown / {rawCount} total {rawCount && !showHeartbeats ? '(heartbeats hidden)' : ''}
      </div>
    </section>
  );
}
