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

// File Sources: operator-configured media roots (local mounts, SMB shares)
// that any channel plugin can browse through the shared <x-file-explorer>
// picker instead of each plugin growing its own server-path input.
import React, { useState, useEffect, useCallback } from 'react';
import { HardDrive, Plus, Trash2, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import { api } from '../../services/api';
import './FileSourcesSettings.css';

const emptyDraft = { name: '', type: 'local', config: { path: '' } };

const FileSourcesSettings = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [testResults, setTestResults] = useState({}); // sourceId -> {ok, message}
  const [testingId, setTestingId] = useState(null);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listFileSources();
      setSources(res.data.sources || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isExpanded) loadSources();
  }, [isExpanded, loadSources]);

  const handleCreate = async () => {
    if (!draft.name.trim()) return;
    setSaving(true);
    try {
      await api.createFileSource(draft);
      setDraft(emptyDraft);
      setShowAdd(false);
      await loadSources();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Remove file source "${name}"? Plugins referencing it will stop finding those files.`)) return;
    try {
      await api.deleteFileSource(id);
      await loadSources();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const handleTest = async (id) => {
    setTestingId(id);
    try {
      const res = await api.testFileSource(id);
      setTestResults((prev) => ({ ...prev, [id]: res.data }));
    } catch (e) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { ok: false, message: e.response?.data?.detail || e.message },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const updateDraftConfig = (patch) => {
    setDraft((d) => ({ ...d, config: { ...d.config, ...patch } }));
  };

  return (
    <div className="settings-card">
      <div
        className="card-header"
        role="button"
        tabIndex={0}
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setIsExpanded(!isExpanded); } }}
      >
        <div className="flex items-center gap-sm">
          <HardDrive size={20} />
          <h3 className="card-title">File Sources</h3>
        </div>
        <button type="button" className="expand-button" aria-label={isExpanded ? 'Collapse section' : 'Expand section'}>
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {isExpanded && (
        <div className="card-body">
          <p className="form-help" style={{ marginTop: 0 }}>
            Named media roots (a local mounted path, or an SMB/NAS share) that any
            channel plugin can browse from its own UI — no per-plugin path
            configuration needed. Local sources are constrained to whatever your
            deployment mounted at <code>MIMIR_HOST_MEDIA</code> in docker-compose.
          </p>

          {error && <div className="error-msg">⚠ {error}</div>}

          {loading ? (
            <div className="fs-loading"><div className="fs-spinner" /></div>
          ) : sources.length === 0 ? (
            <div className="fs-empty">No file sources configured yet.</div>
          ) : (
            <div className="fs-list">
              {sources.map((s) => {
                const result = testResults[s.id];
                return (
                  <div key={s.id} className="fs-row">
                    <div className="fs-row-info">
                      <div className="fs-row-name">{s.name}</div>
                      <div className="fs-row-meta">
                        {s.type === 'local'
                          ? `local · /mnt/host-media/${s.config.path || ''}`
                          : `smb · \\\\${s.config.host}\\${s.config.share}${s.config.root_path ? `\\${s.config.root_path}` : ''}`}
                      </div>
                      {result && (
                        <div className={`fs-test-result ${result.ok ? 'ok' : 'fail'}`}>
                          {result.ok ? <CheckCircle size={12} /> : <XCircle size={12} />} {result.message}
                        </div>
                      )}
                    </div>
                    <div className="fs-row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={testingId === s.id}
                        onClick={() => handleTest(s.id)}
                      >
                        <RefreshCw size={14} /> {testingId === s.id ? 'Testing…' : 'Test'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(s.id, s.name)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {!showAdd ? (
            <button type="button" className="btn btn-secondary" style={{ marginTop: '0.75rem' }} onClick={() => setShowAdd(true)}>
              <Plus size={14} /> Add File Source
            </button>
          ) : (
            <div className="fs-add-form">
              <div className="form-group">
                <label className="form-label">Name</label>
                <input
                  className="form-input"
                  placeholder="e.g. Plex Media, NAS"
                  value={draft.name}
                  onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select
                  className="form-select"
                  value={draft.type}
                  onChange={(e) => setDraft({ ...emptyDraft, name: draft.name, type: e.target.value })}
                >
                  <option value="local">Local (mounted path)</option>
                  <option value="smb">SMB / NAS share</option>
                </select>
              </div>

              {draft.type === 'local' ? (
                <div className="form-group">
                  <label className="form-label">Subpath under mounted media root</label>
                  <input
                    className="form-input"
                    placeholder="e.g. PlexMedia/Movies"
                    value={draft.config.path || ''}
                    onChange={(e) => updateDraftConfig({ path: e.target.value })}
                  />
                  <small className="form-help">
                    Relative to whatever host directory was mounted at <code>/mnt/host-media</code>.
                  </small>
                </div>
              ) : (
                <>
                  <div className="fs-form-row">
                    <div className="form-group">
                      <label className="form-label">Host</label>
                      <input className="form-input" placeholder="192.168.1.20" value={draft.config.host || ''}
                        onChange={(e) => updateDraftConfig({ host: e.target.value })} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Share</label>
                      <input className="form-input" placeholder="Media" value={draft.config.share || ''}
                        onChange={(e) => updateDraftConfig({ share: e.target.value })} />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Root path within share (optional)</label>
                    <input className="form-input" placeholder="Movies" value={draft.config.root_path || ''}
                      onChange={(e) => updateDraftConfig({ root_path: e.target.value })} />
                  </div>
                  <div className="fs-form-row">
                    <div className="form-group">
                      <label className="form-label">Username (optional)</label>
                      <input className="form-input" value={draft.config.username || ''}
                        onChange={(e) => updateDraftConfig({ username: e.target.value })} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Password (optional)</label>
                      <input type="password" className="form-input" value={draft.config.password || ''}
                        onChange={(e) => updateDraftConfig({ password: e.target.value })} />
                    </div>
                  </div>
                </>
              )}

              <div className="fs-form-actions">
                <button type="button" className="btn btn-ghost" onClick={() => { setShowAdd(false); setDraft(emptyDraft); }}>
                  Cancel
                </button>
                <button type="button" className="btn btn-primary" disabled={saving || !draft.name.trim()} onClick={handleCreate}>
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FileSourcesSettings;
