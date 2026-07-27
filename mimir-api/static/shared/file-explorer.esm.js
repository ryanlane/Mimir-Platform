// Shared File Explorer web component — <x-file-explorer>
//
// Served by mimir-api at /api/static/shared/file-explorer.esm.js (nested
// under /api so it rides through the production nginx proxy's existing
// `location ^~ /api/` rule with no extra config — a bare /static would
// collide with Create React App's own build/static/js|css output once both
// are served from the same web origin) so it can be imported by BOTH the
// React admin UI (mimir-ui) and any channel plugin's manager Web Component
// (e.g. slow_movie's manage.esm.js). One picker, backed by the platform's
// /api/sources File Sources endpoints, instead of every plugin building
// (and duplicating) its own server-path browser.
//
// Usage:
//   <script type="module" src="{apiBase}/api/static/shared/file-explorer.esm.js"></script>
//   <x-file-explorer extensions="mp4,avi,mov,mkv,webm"></x-file-explorer>
//   el.addEventListener('mimir-file-select', (e) => {
//     const { ref, sourceId, path, name, size } = e.detail;
//   });
//
// `ref` is a "source://<source_id>/<relative/path>" string — pass it back to
// the platform (e.g. as a movie's video_path) rather than a raw filesystem
// path; the API resolves it via app.services.file_sources.localize().

const CSS = `
  :host { display: block; font-family: "Lato", system-ui, sans-serif; font-size: 14px; color: var(--color-text, #e0e0e0); }
  * { box-sizing: border-box; }
  .explorer { display: flex; flex-direction: column; gap: 10px; }
  .source-row { display: flex; gap: 8px; align-items: center; }
  select {
    background: var(--color-background, #0B1314); border: 1px solid var(--color-border, #2a3a3c);
    border-radius: 6px; padding: 6px 8px; font-size: 13px; color: var(--color-text, #e0e0e0); font-family: inherit;
  }
  .breadcrumbs { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; font-size: 12px; color: var(--color-text-secondary, #888); }
  .crumb { cursor: pointer; padding: 2px 4px; border-radius: 4px; }
  .crumb:hover { background: var(--color-surface-hover, #1e2f31); color: var(--color-text, #e0e0e0); }
  .crumb.current { color: var(--color-text, #e0e0e0); font-weight: 600; cursor: default; }
  .crumb-sep { color: var(--color-text-tertiary, #555); }
  .entry-list { display: flex; flex-direction: column; gap: 4px; max-height: 340px; overflow-y: auto; }
  .entry {
    display: flex; align-items: center; gap: 10px;
    background: var(--color-background, #0B1314); border: 1px solid var(--color-border, #2a3a3c);
    border-radius: 6px; padding: 7px 10px; cursor: default;
  }
  .entry.dir { cursor: pointer; }
  .entry.dir:hover { border-color: var(--color-accent, #00C851); background: var(--color-surface-hover, #1e2f31); }
  .entry-icon { flex-shrink: 0; font-size: 14px; }
  .entry-name { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; }
  .entry-size { font-size: 11px; color: var(--color-text-secondary, #888); flex-shrink: 0; }
  .btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 6px; border: none;
    font-size: 12px; font-family: inherit; cursor: pointer; font-weight: 600;
    background: var(--color-accent, #00C851); color: #000;
  }
  .btn:hover { background: var(--color-accent-hover, #00d858); }
  .empty { text-align: center; padding: 24px; color: var(--color-text-secondary, #888); font-style: italic; font-size: 13px; }
  .error-msg { color: #ef9a9a; font-size: 13px; padding: 8px 12px; background: #1a0808; border-radius: 6px; border: 1px solid #c62828; }
  .loading { text-align: center; padding: 20px; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.2); border-top-color: var(--color-accent, #00C851); border-radius: 50%; animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
`;

function fmtSize(b) {
  if (!b) return '';
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(0)} MB`;
  return `${(b / 1e3).toFixed(0)} KB`;
}

class XFileExplorer extends HTMLElement {
  static get observedAttributes() { return ['extensions', 'api-base']; }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.state = {
      sources: [],
      sourceId: null,
      path: '',
      breadcrumbs: [],
      entries: [],
      loading: true,
      error: null,
    };
  }

  connectedCallback() {
    const style = document.createElement('style');
    style.textContent = CSS;
    this.shadowRoot.appendChild(style);
    this.loadSources();
  }

  get apiBase() {
    return this.getAttribute('api-base') || window.mimirServerBaseUrl || window.location.origin;
  }

  get extensions() {
    return this.getAttribute('extensions') || '';
  }

  async apiFetch(path) {
    const resp = await fetch(`${this.apiBase}/api${path}`, { credentials: 'include' });
    if (!resp.ok) throw new Error(`API ${path}: ${resp.status}`);
    return resp.json();
  }

  setState(patch) {
    Object.assign(this.state, patch);
    this.render();
  }

  async loadSources() {
    this.setState({ loading: true, error: null });
    try {
      const data = await this.apiFetch('/sources');
      const sources = (data.sources || []).filter((s) => s.enabled);
      const sourceId = sources[0]?.id || null;
      this.setState({ sources, sourceId, loading: false });
      if (sourceId) await this.browse(sourceId, '');
    } catch (e) {
      this.setState({ loading: false, error: e.message });
    }
  }

  async browse(sourceId, path) {
    this.setState({ loading: true, error: null });
    try {
      const data = await this.apiFetch(
        `/sources/${sourceId}/browse?path=${encodeURIComponent(path)}&extensions=${encodeURIComponent(this.extensions)}`
      );
      this.setState({
        sourceId,
        path: data.path,
        breadcrumbs: data.breadcrumbs || [],
        entries: data.entries || [],
        loading: false,
      });
    } catch (e) {
      this.setState({ loading: false, error: e.message, entries: [] });
    }
  }

  selectFile(entry) {
    const { sourceId } = this.state;
    this.dispatchEvent(new CustomEvent('mimir-file-select', {
      bubbles: true,
      composed: true,
      detail: {
        ref: `source://${sourceId}/${entry.path}`,
        sourceId,
        path: entry.path,
        name: entry.name,
        size: entry.size,
      },
    }));
  }

  render() {
    const root = this.shadowRoot;
    Array.from(root.children).forEach((c) => { if (c.tagName !== 'STYLE') c.remove(); });
    const container = document.createElement('div');
    container.className = 'explorer';
    container.innerHTML = this.buildHTML();
    root.appendChild(container);
    this.attachListeners(container);
  }

  esc(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  buildHTML() {
    const { sources, sourceId, breadcrumbs, entries, loading, error } = this.state;

    if (loading && entries.length === 0 && !error) {
      return `<div class="loading"><div class="spinner"></div></div>`;
    }
    if (sources.length === 0) {
      return `<div class="empty">No file sources configured yet.<br/>Add one in Settings &rarr; File Sources.</div>`;
    }

    const sourceOptions = sources.map((s) =>
      `<option value="${this.esc(s.id)}" ${s.id === sourceId ? 'selected' : ''}>${this.esc(s.name)}</option>`
    ).join('');

    const crumbsHtml = breadcrumbs.map((c, i) => {
      const isLast = i === breadcrumbs.length - 1;
      const label = c.name || (sources.find((s) => s.id === sourceId)?.name ?? 'Root');
      return `${i > 0 ? '<span class="crumb-sep">/</span>' : ''}<span class="crumb${isLast ? ' current' : ''}" data-path="${this.esc(c.path)}">${this.esc(label)}</span>`;
    }).join('');

    const entriesHtml = entries.length === 0
      ? `<div class="empty">Empty directory</div>`
      : `<div class="entry-list">${entries.map((e) => e.is_dir
          ? `<div class="entry dir" data-path="${this.esc(e.path)}">
               <span class="entry-icon">📁</span>
               <span class="entry-name">${this.esc(e.name)}</span>
             </div>`
          : `<div class="entry">
               <span class="entry-icon">🎬</span>
               <span class="entry-name">${this.esc(e.name)}</span>
               <span class="entry-size">${fmtSize(e.size)}</span>
               <button class="btn" data-select-path="${this.esc(e.path)}">Select</button>
             </div>`
        ).join('')}</div>`;

    return `
      <div class="source-row">
        <select id="source-select">${sourceOptions}</select>
      </div>
      <div class="breadcrumbs">${crumbsHtml}</div>
      ${error ? `<div class="error-msg">⚠ ${this.esc(error)}</div>` : ''}
      ${entriesHtml}
    `;
  }

  attachListeners(container) {
    container.querySelector('#source-select')?.addEventListener('change', (e) => {
      this.browse(e.target.value, '');
    });
    container.querySelectorAll('.entry.dir').forEach((el) => {
      el.addEventListener('click', () => this.browse(this.state.sourceId, el.dataset.path));
    });
    container.querySelectorAll('.crumb:not(.current)').forEach((el) => {
      el.addEventListener('click', () => this.browse(this.state.sourceId, el.dataset.path));
    });
    container.querySelectorAll('[data-select-path]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const entry = this.state.entries.find((e) => e.path === btn.dataset.selectPath);
        if (entry) this.selectFile(entry);
      });
    });
  }
}

if (!customElements.get('x-file-explorer')) {
  customElements.define('x-file-explorer', XFileExplorer);
}

export { XFileExplorer };
