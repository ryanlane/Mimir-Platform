// Slow Movie Player Manager Web Component for Mimir Platform
const CHANNEL_ID = 'com.mimir.slowmovie';

const CSS = `
  :host {
    display: block;
    font-family: "Lato", system-ui, sans-serif;
    font-size: 14px;
    color: var(--color-text, #e0e0e0);
    background: transparent;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }

  .manager { display: flex; flex-direction: column; gap: 16px; padding: 16px 0; }

  /* Now Playing */
  .now-playing {
    background: var(--color-surface, #162325);
    border: 1px solid var(--color-border, #2a3a3c);
    border-radius: 8px;
    padding: 16px;
  }
  .now-playing h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-secondary, #888); margin-bottom: 12px; }
  .np-empty { color: var(--color-text-secondary, #888); font-style: italic; }
  .np-content { display: flex; align-items: center; gap: 16px; }
  .np-thumb { width: 120px; height: 68px; object-fit: cover; border-radius: 4px; background: #0a1a1c; flex-shrink: 0; }
  .np-thumb-placeholder { width: 120px; height: 68px; background: #0a1a1c; border-radius: 4px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: #444; font-size: 24px; }
  .np-info { flex: 1; min-width: 0; }
  .np-title { font-size: 16px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .np-meta { font-size: 12px; color: var(--color-text-secondary, #888); margin-top: 4px; }
  .np-progress-bar { margin-top: 10px; background: #0a1a1c; border-radius: 4px; height: 4px; overflow: hidden; }
  .np-progress-fill { height: 100%; background: var(--color-accent, #00C851); transition: width 0.3s; }
  .np-controls { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }

  /* Quiet hours badge */
  .quiet-badge {
    display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
    background: #2a1a00; border: 1px solid #6b3d00; border-radius: 12px;
    font-size: 12px; color: #ffaa44;
  }

  /* Section */
  .section { display: flex; flex-direction: column; gap: 8px; }
  .section-header { display: flex; align-items: center; justify-content: space-between; }
  .section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-secondary, #888); }

  /* Movie list */
  .movie-list { display: flex; flex-direction: column; gap: 6px; }
  .movie-card {
    background: var(--color-surface, #162325);
    border: 1px solid var(--color-border, #2a3a3c);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  .movie-card:hover { border-color: var(--color-accent, #00C851); background: var(--color-surface-hover, #1e2f31); }
  .movie-card.active { border-color: var(--color-accent, #00C851); background: #0e2418; }
  .movie-card-info { flex: 1; min-width: 0; }
  .movie-card-title { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .movie-card-meta { font-size: 12px; color: var(--color-text-secondary, #888); margin-top: 2px; }
  .movie-card-progress { margin-top: 6px; background: #0a1a1c; border-radius: 3px; height: 3px; overflow: hidden; }
  .movie-card-progress-fill { height: 100%; background: var(--color-accent, #00C851); }
  .active-pip { width: 8px; height: 8px; border-radius: 50%; background: var(--color-accent, #00C851); flex-shrink: 0; box-shadow: 0 0 6px #00C851; }
  .inactive-pip { width: 8px; height: 8px; flex-shrink: 0; }
  .movie-card-actions { display: flex; gap: 6px; flex-shrink: 0; }

  /* Buttons */
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: 6px; border: none;
    font-size: 13px; font-family: inherit; cursor: pointer;
    font-weight: 600; transition: background 0.15s, opacity 0.15s;
    white-space: nowrap;
  }
  .btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .btn-primary { background: var(--color-accent, #00C851); color: #000; }
  .btn-primary:hover:not(:disabled) { background: var(--color-accent-hover, #00d858); }
  .btn-secondary { background: var(--color-surface, #162325); color: var(--color-text, #e0e0e0); border: 1px solid var(--color-border, #2a3a3c); }
  .btn-secondary:hover:not(:disabled) { background: var(--color-surface-hover, #1e2f31); }
  .btn-danger { background: #c62828; color: #fff; }
  .btn-danger:hover:not(:disabled) { background: #d32f2f; }
  .btn-ghost { background: transparent; color: var(--color-text-secondary, #888); padding: 4px 8px; font-size: 12px; font-weight: 400; }
  .btn-ghost:hover:not(:disabled) { color: var(--color-text, #e0e0e0); }
  .btn-sm { padding: 4px 10px; font-size: 12px; }
  .btn-icon { padding: 5px 8px; }

  /* Add movie panel */
  .add-panel {
    background: var(--color-surface, #162325);
    border: 1px solid var(--color-border, #2a3a3c);
    border-radius: 8px;
    padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .add-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border, #2a3a3c); padding-bottom: 8px; }
  .add-tab { padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; color: var(--color-text-secondary, #888); background: none; border: none; font-family: inherit; }
  .add-tab.active { background: var(--color-surface-hover, #1e2f31); color: var(--color-text, #e0e0e0); font-weight: 600; }
  .input-row { display: flex; gap: 8px; align-items: flex-end; }
  .field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .field label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-text-secondary, #888); }
  .field input, .field select {
    background: var(--color-background, #0B1314); border: 1px solid var(--color-border, #2a3a3c);
    border-radius: 6px; padding: 8px 10px; font-size: 13px; font-family: inherit;
    color: var(--color-text, #e0e0e0); width: 100%;
  }
  .field input:focus, .field select:focus { outline: 2px solid var(--color-accent, #00C851); border-color: transparent; }
  .drop-zone {
    border: 2px dashed var(--color-border, #2a3a3c); border-radius: 8px;
    padding: 28px; text-align: center; cursor: pointer; transition: border-color 0.15s;
    color: var(--color-text-secondary, #888); font-size: 13px;
  }
  .drop-zone.over { border-color: var(--color-accent, #00C851); background: #0e2418; }
  .drop-zone input[type=file] { display: none; }
  .upload-progress { height: 4px; background: #0a1a1c; border-radius: 3px; overflow: hidden; }
  .upload-progress-fill { height: 100%; background: var(--color-accent, #00C851); transition: width 0.2s; }

  /* Settings */
  .settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .settings-grid.full { grid-template-columns: 1fr; }
  .toggle-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .toggle { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .toggle-slider { position: absolute; cursor: pointer; inset: 0; background: #2a3a3c; border-radius: 10px; transition: background 0.2s; }
  .toggle-slider:before { content: ''; position: absolute; width: 14px; height: 14px; left: 3px; top: 3px; background: #fff; border-radius: 50%; transition: transform 0.2s; }
  .toggle input:checked + .toggle-slider { background: var(--color-accent, #00C851); }
  .toggle input:checked + .toggle-slider:before { transform: translateX(16px); }

  /* Seek modal */
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; display: flex; align-items: center; justify-content: center; }
  .modal { background: var(--color-surface, #162325); border: 1px solid var(--color-border, #2a3a3c); border-radius: 10px; padding: 20px; min-width: 300px; max-width: 420px; width: 90%; }
  .modal h3 { font-size: 15px; margin-bottom: 14px; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
  .seek-range { width: 100%; accent-color: var(--color-accent, #00C851); margin: 12px 0 4px; }
  .seek-label { font-size: 12px; color: var(--color-text-secondary, #888); text-align: center; }

  /* Toast */
  .toast { position: fixed; bottom: 20px; right: 20px; z-index: 2000; background: var(--color-surface, #162325); border: 1px solid var(--color-accent, #00C851); border-radius: 8px; padding: 10px 16px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,0.4); animation: slide-in 0.2s ease; }
  .toast.error { border-color: #c62828; }
  @keyframes slide-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

  /* Misc */
  .empty { text-align: center; padding: 28px; color: var(--color-text-secondary, #888); font-style: italic; }
  .error-msg { color: #ef9a9a; font-size: 13px; padding: 8px 12px; background: #1a0808; border-radius: 6px; border: 1px solid #c62828; }
  .loading-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.2); border-top-color: var(--color-accent, #00C851); border-radius: 50%; animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  hr { border: none; border-top: 1px solid var(--color-border, #2a3a3c); }
`;

class XSlowMovieManager extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.api = null; // resolved in connectedCallback
    this.state = {
      movies: [],
      status: null,
      settings: null,
      loading: true,
      error: null,
      addTab: 'path',   // 'path' | 'upload'
      addPath: '',
      addTitle: '',
      uploadProgress: null,
      showSettings: false,
      showSeekModal: false,
      seekMovieId: null,
      seekFrame: 0,
      seekTotal: 0,
    };
    this._refreshTimer = null;
  }

  get channelId() { return CHANNEL_ID; }

  getApiBase() {
    return window.mimirServerBaseUrl || window.location.origin;
  }

  async apiFetch(path, opts = {}) {
    const base = this.getApiBase();
    const url = `${base}/api/channels/${this.channelId}${path}`;
    const resp = await fetch(url, { credentials: 'include', ...opts });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error(`API ${path}: ${resp.status} ${text.slice(0, 120)}`);
    }
    return resp.json();
  }

  async connectedCallback() {
    this.injectStyles();
    this.render();
    await this.loadAll();
    this.startRefresh();
  }

  disconnectedCallback() {
    this.stopRefresh();
  }

  injectStyles() {
    const style = document.createElement('style');
    style.textContent = CSS;
    this.shadowRoot.appendChild(style);
  }

  startRefresh() {
    this._refreshTimer = setInterval(() => this.loadStatus(), 15000);
  }

  stopRefresh() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
  }

  setState(patch) {
    Object.assign(this.state, patch);
    this.render();
  }

  async loadAll() {
    this.setState({ loading: true, error: null });
    try {
      const [moviesData, statusData, settingsData] = await Promise.all([
        this.apiFetch('/movies'),
        this.apiFetch('/status'),
        this.apiFetch('/settings'),
      ]);
      this.setState({
        movies: moviesData.movies || [],
        status: statusData,
        settings: settingsData,
        loading: false,
      });
    } catch (e) {
      this.setState({ loading: false, error: e.message });
    }
  }

  async loadStatus() {
    try {
      const [statusData, moviesData] = await Promise.all([
        this.apiFetch('/status'),
        this.apiFetch('/movies'),
      ]);
      this.setState({ status: statusData, movies: moviesData.movies || [] });
    } catch (_) { /* best effort */ }
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  async activateMovie(id) {
    try {
      await this.apiFetch(`/movies/${id}/activate`, { method: 'POST' });
      await this.loadAll();
      this.toast('Movie activated');
    } catch (e) { this.toast(e.message, true); }
  }

  async advanceFrame(id) {
    try {
      await this.apiFetch(`/movies/${id}/advance`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      await this.loadStatus();
      this.toast('Advanced to next frame');
    } catch (e) { this.toast(e.message, true); }
  }

  async deleteMovie(id, title) {
    if (!confirm(`Delete "${title}" from the library?`)) return;
    try {
      await this.apiFetch(`/movies/${id}`, { method: 'DELETE' });
      await this.loadAll();
      this.toast('Movie removed');
    } catch (e) { this.toast(e.message, true); }
  }

  async addByPath() {
    const path = this.state.addPath.trim();
    if (!path) { this.toast('Enter a file path', true); return; }
    try {
      await this.apiFetch('/movies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_path: path, title: this.state.addTitle.trim() || undefined }),
      });
      this.setState({ addPath: '', addTitle: '' });
      await this.loadAll();
      this.toast('Movie added');
    } catch (e) { this.toast(e.message, true); }
  }

  async uploadFile(file) {
    this.setState({ uploadProgress: 0 });
    const formData = new FormData();
    formData.append('file', file);
    try {
      const base = this.getApiBase();
      const url = `${base}/api/channels/${this.channelId}/upload`;
      const resp = await fetch(url, { method: 'POST', credentials: 'include', body: formData });
      const data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.detail || data.error || 'Upload failed');
      this.setState({ uploadProgress: null });
      await this.loadAll();
      this.toast(`"${data.movie?.title}" uploaded`);
    } catch (e) {
      this.setState({ uploadProgress: null });
      this.toast(e.message, true);
    }
  }

  async saveSettings() {
    const s = this.state.settings;
    if (!s) return;
    try {
      await this.apiFetch('/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(s),
      });
      this.toast('Settings saved');
    } catch (e) { this.toast(e.message, true); }
  }

  async seekTo() {
    const { seekMovieId, seekFrame } = this.state;
    try {
      await this.apiFetch(`/movies/${seekMovieId}/seek`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frame: seekFrame }),
      });
      this.setState({ showSeekModal: false });
      await this.loadStatus();
      this.toast(`Seeked to frame ${seekFrame}`);
    } catch (e) { this.toast(e.message, true); }
  }

  openSeek(movie) {
    this.setState({
      showSeekModal: true,
      seekMovieId: movie.id,
      seekFrame: movie.current_frame || 0,
      seekTotal: movie.total_frames || 0,
    });
  }

  toast(msg, isError = false) {
    const t = document.createElement('div');
    t.className = `toast${isError ? ' error' : ''}`;
    t.textContent = msg;
    this.shadowRoot.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }

  // ── Formatting helpers ─────────────────────────────────────────────────────

  fmtDuration(sec) {
    if (!sec) return '—';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  fmtFrames(n) {
    if (!n) return '—';
    return n.toLocaleString();
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  render() {
    const root = this.shadowRoot;
    // Remove everything except the <style> tag
    Array.from(root.children).forEach(c => { if (c.tagName !== 'STYLE') c.remove(); });

    const container = document.createElement('div');
    container.className = 'manager';
    container.innerHTML = this.buildHTML();
    root.appendChild(container);
    this.attachListeners(container);
  }

  buildHTML() {
    const { loading, error, movies, status, settings, showSettings,
            addTab, addPath, addTitle, uploadProgress, showSeekModal,
            seekFrame, seekTotal } = this.state;

    if (loading) return `<div style="padding:32px;text-align:center"><div class="loading-spinner"></div></div>`;
    if (error) return `<div class="error-msg">⚠ ${error} <button class="btn btn-ghost" id="retry-btn">Retry</button></div>`;

    const activeMovie = movies.find(m => m.is_active);
    const inQuiet = status?.in_quiet_hours;

    return `
      ${showSeekModal ? this.buildSeekModal(seekFrame, seekTotal) : ''}

      <!-- Now Playing -->
      <div class="now-playing">
        <h2>Now Playing</h2>
        ${inQuiet ? `<div class="quiet-badge" style="margin-bottom:10px">🌙 Quiet hours active — frames paused</div>` : ''}
        ${activeMovie ? this.buildNowPlaying(activeMovie, status) : `<p class="np-empty">No movie selected. Activate one from the library below.</p>`}
      </div>

      <!-- Movie Library -->
      <div class="section">
        <div class="section-header">
          <span class="section-title">Library (${movies.length})</span>
          <div style="display:flex;gap:6px">
            <button class="btn btn-secondary btn-sm" id="toggle-settings-btn">
              ${showSettings ? 'Hide Settings' : 'Settings'}
            </button>
          </div>
        </div>
        ${movies.length === 0
          ? `<div class="empty">No movies yet. Add one below.</div>`
          : `<div class="movie-list">${movies.map(m => this.buildMovieCard(m)).join('')}</div>`
        }
      </div>

      <!-- Add Movie -->
      <div class="section">
        <div class="section-title">Add Movie</div>
        <div class="add-panel">
          <div class="add-tabs">
            <button class="add-tab${addTab === 'path' ? ' active' : ''}" data-tab="path">By File Path</button>
            <button class="add-tab${addTab === 'upload' ? ' active' : ''}" data-tab="upload">Upload</button>
          </div>
          ${addTab === 'path' ? this.buildAddByPath(addPath, addTitle) : this.buildUpload(uploadProgress)}
        </div>
      </div>

      <!-- Settings -->
      ${showSettings && settings ? this.buildSettings(settings) : ''}
    `;
  }

  buildNowPlaying(movie, status) {
    const pct = movie.progress_pct ?? 0;
    const eff = status || {};
    return `
      <div class="np-content">
        <div class="np-thumb-placeholder">🎬</div>
        <div class="np-info">
          <div class="np-title">${this.esc(movie.title)}</div>
          <div class="np-meta">
            Frame ${(movie.current_frame || 0).toLocaleString()} / ${(movie.total_frames || 0).toLocaleString()}
            &nbsp;·&nbsp; ${pct}% complete
            &nbsp;·&nbsp; ${this.fmtDuration(movie.duration_seconds)}
          </div>
          <div class="np-progress-bar"><div class="np-progress-fill" style="width:${pct}%"></div></div>
        </div>
      </div>
      <div class="np-controls">
        <button class="btn btn-primary btn-sm" data-action="advance" data-id="${movie.id}">▶ Advance Frame</button>
        <button class="btn btn-secondary btn-sm" data-action="seek" data-id="${movie.id}"
          data-current="${movie.current_frame || 0}" data-total="${movie.total_frames || 0}">
          ⤢ Seek
        </button>
      </div>
    `;
  }

  buildMovieCard(m) {
    const pct = m.progress_pct ?? 0;
    const isActive = m.is_active;
    return `
      <div class="movie-card${isActive ? ' active' : ''}">
        <div class="${isActive ? 'active-pip' : 'inactive-pip'}"></div>
        <div class="movie-card-info">
          <div class="movie-card-title">${this.esc(m.title)}</div>
          <div class="movie-card-meta">
            ${(m.total_frames || 0).toLocaleString()} frames &nbsp;·&nbsp; ${this.fmtDuration(m.duration_seconds)}
            ${m.is_random ? '&nbsp;·&nbsp; 🔀 random' : ''}
          </div>
          <div class="movie-card-progress">
            <div class="movie-card-progress-fill" style="width:${pct}%"></div>
          </div>
        </div>
        <div class="movie-card-actions">
          ${!isActive ? `<button class="btn btn-primary btn-sm" data-action="activate" data-id="${m.id}">Play</button>` : ''}
          <button class="btn btn-secondary btn-sm btn-icon" data-action="seek" data-id="${m.id}"
            data-current="${m.current_frame || 0}" data-total="${m.total_frames || 0}" title="Seek">⤢</button>
          <button class="btn btn-danger btn-sm btn-icon" data-action="delete" data-id="${m.id}" data-title="${this.esc(m.title)}" title="Remove">✕</button>
        </div>
      </div>
    `;
  }

  buildAddByPath(path, title) {
    return `
      <div class="field">
        <label>Video File Path</label>
        <input type="text" id="add-path" placeholder="/mnt/media/movies/myfilm.mp4" value="${this.esc(path)}" />
      </div>
      <div class="field">
        <label>Title (optional)</label>
        <input type="text" id="add-title" placeholder="My Film" value="${this.esc(title)}" />
      </div>
      <button class="btn btn-primary" id="add-path-btn">Add Movie</button>
    `;
  }

  buildUpload(progress) {
    if (progress !== null && progress !== undefined) {
      return `
        <div>Uploading…</div>
        <div class="upload-progress"><div class="upload-progress-fill" style="width:${progress}%"></div></div>
      `;
    }
    return `
      <div class="drop-zone" id="drop-zone">
        <input type="file" id="file-input" accept=".mp4,.avi,.mov,.mkv,.webm" />
        <div>Drop a video file here or <strong>click to browse</strong></div>
        <div style="font-size:11px;margin-top:6px;color:#555">MP4, AVI, MOV, MKV, WEBM</div>
      </div>
    `;
  }

  buildSettings(s) {
    return `
      <div class="section">
        <div class="section-title">Global Settings</div>
        <div class="add-panel">
          <div class="settings-grid">
            <div class="field">
              <label>Time Per Frame</label>
              <input type="number" id="s-time-val" min="1" value="${s.time_per_frame ?? 30}" />
            </div>
            <div class="field">
              <label>Unit</label>
              <select id="s-time-unit">
                ${['seconds','minutes','hours'].map(u => `<option value="${u}"${s.time_per_frame_unit === u ? ' selected' : ''}>${u}</option>`).join('')}
              </select>
            </div>
            <div class="field">
              <label>Frames to Skip</label>
              <input type="number" id="s-skip" min="1" value="${s.skip_frames ?? 1}" />
            </div>
            <div class="field">
              <label>Video Root Path</label>
              <input type="text" id="s-root" placeholder="/mnt/media/movies" value="${this.esc(s.video_root_path ?? '')}" />
            </div>
          </div>
          <hr />
          <div class="toggle-row">
            <span>Quiet Hours</span>
            <label class="toggle">
              <input type="checkbox" id="s-quiet" ${s.use_quiet_hours ? 'checked' : ''} />
              <span class="toggle-slider"></span>
            </label>
          </div>
          ${s.use_quiet_hours ? `
          <div class="settings-grid">
            <div class="field">
              <label>Quiet Start (hour, 0–23)</label>
              <input type="number" id="s-quiet-start" min="0" max="23" value="${s.quiet_start ?? 22}" />
            </div>
            <div class="field">
              <label>Quiet End (hour, 0–23)</label>
              <input type="number" id="s-quiet-end" min="0" max="23" value="${s.quiet_end ?? 7}" />
            </div>
          </div>` : ''}
          <button class="btn btn-primary" id="save-settings-btn">Save Settings</button>
        </div>
      </div>
    `;
  }

  buildSeekModal(frame, total) {
    const pct = total > 0 ? Math.round(frame / total * 100) : 0;
    return `
      <div class="modal-overlay" id="seek-overlay">
        <div class="modal">
          <h3>Seek to Frame</h3>
          <input type="range" class="seek-range" id="seek-range" min="0" max="${total || 100}" value="${frame}" />
          <div class="seek-label">Frame ${frame.toLocaleString()} / ${(total || 0).toLocaleString()} (${pct}%)</div>
          <div class="modal-actions">
            <button class="btn btn-secondary" id="seek-cancel-btn">Cancel</button>
            <button class="btn btn-primary" id="seek-confirm-btn">Seek</button>
          </div>
        </div>
      </div>
    `;
  }

  esc(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  attachListeners(container) {
    // Retry
    container.querySelector('#retry-btn')?.addEventListener('click', () => this.loadAll());

    // Toggle settings
    container.querySelector('#toggle-settings-btn')?.addEventListener('click', () => {
      this.setState({ showSettings: !this.state.showSettings });
    });

    // Movie actions
    container.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', e => {
        e.stopPropagation();
        const action = el.dataset.action;
        const id = el.dataset.id;
        if (action === 'activate') this.activateMovie(id);
        else if (action === 'advance') this.advanceFrame(id);
        else if (action === 'delete') this.deleteMovie(id, el.dataset.title);
        else if (action === 'seek') this.openSeek({
          id,
          current_frame: parseInt(el.dataset.current || '0', 10),
          total_frames: parseInt(el.dataset.total || '0', 10),
        });
      });
    });

    // Add tabs
    container.querySelectorAll('.add-tab').forEach(tab => {
      tab.addEventListener('click', () => this.setState({ addTab: tab.dataset.tab }));
    });

    // Add by path
    container.querySelector('#add-path')?.addEventListener('input', e => { this.state.addPath = e.target.value; });
    container.querySelector('#add-title')?.addEventListener('input', e => { this.state.addTitle = e.target.value; });
    container.querySelector('#add-path-btn')?.addEventListener('click', () => this.addByPath());

    // Upload drop zone
    const dz = container.querySelector('#drop-zone');
    const fi = container.querySelector('#file-input');
    if (dz && fi) {
      dz.addEventListener('click', () => fi.click());
      fi.addEventListener('change', () => { if (fi.files[0]) this.uploadFile(fi.files[0]); });
      dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
      dz.addEventListener('dragleave', () => dz.classList.remove('over'));
      dz.addEventListener('drop', e => {
        e.preventDefault(); dz.classList.remove('over');
        if (e.dataTransfer.files[0]) this.uploadFile(e.dataTransfer.files[0]);
      });
    }

    // Settings
    const saveBtn = container.querySelector('#save-settings-btn');
    if (saveBtn) {
      const syncSettings = () => {
        const s = { ...this.state.settings };
        const tv = container.querySelector('#s-time-val');
        const tu = container.querySelector('#s-time-unit');
        const sk = container.querySelector('#s-skip');
        const rp = container.querySelector('#s-root');
        const qu = container.querySelector('#s-quiet');
        const qs = container.querySelector('#s-quiet-start');
        const qe = container.querySelector('#s-quiet-end');
        if (tv) s.time_per_frame = parseInt(tv.value, 10);
        if (tu) s.time_per_frame_unit = tu.value;
        if (sk) s.skip_frames = parseInt(sk.value, 10);
        if (rp) s.video_root_path = rp.value;
        if (qu) s.use_quiet_hours = qu.checked;
        if (qs) s.quiet_start = parseInt(qs.value, 10);
        if (qe) s.quiet_end = parseInt(qe.value, 10);
        this.state.settings = s;
      };
      // Re-render on quiet hours toggle to show/hide hours inputs
      container.querySelector('#s-quiet')?.addEventListener('change', () => { syncSettings(); this.render(); });
      saveBtn.addEventListener('click', () => { syncSettings(); this.saveSettings(); });
    }

    // Seek modal
    const seekRange = container.querySelector('#seek-range');
    if (seekRange) {
      seekRange.addEventListener('input', () => {
        this.state.seekFrame = parseInt(seekRange.value, 10);
        // Update label without full re-render
        const lbl = container.querySelector('.seek-label');
        const t = this.state.seekTotal;
        const f = this.state.seekFrame;
        const pct = t > 0 ? Math.round(f / t * 100) : 0;
        if (lbl) lbl.textContent = `Frame ${f.toLocaleString()} / ${t.toLocaleString()} (${pct}%)`;
      });
    }
    container.querySelector('#seek-confirm-btn')?.addEventListener('click', () => this.seekTo());
    container.querySelector('#seek-cancel-btn')?.addEventListener('click', () => this.setState({ showSeekModal: false }));
    container.querySelector('#seek-overlay')?.addEventListener('click', e => {
      if (e.target.id === 'seek-overlay') this.setState({ showSeekModal: false });
    });
  }
}

customElements.define('x-slow-movie-manager', XSlowMovieManager);
