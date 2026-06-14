import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Monitor, Layers, Database, Settings, Plus, Download, Search, ArrowRight } from 'lucide-react';
import { api } from '../../services/api';
import { persistentCache } from '../../services/persistentCache';
import './CommandPalette.css';

const TYPE_LABELS = {
  nav:     'Navigate',
  action:  'Action',
  screen:  'Screen',
  program: 'Program',
  source:  'Source',
};

const TYPE_ORDER = ['nav', 'action', 'screen', 'program', 'source'];

function buildStaticItems(navigate) {
  return [
    { id: 'nav-screens',        type: 'nav',    label: 'Go to Screens',   sublabel: 'View connected displays',    icon: Monitor,  action: () => navigate('/screens') },
    { id: 'nav-programs',       type: 'nav',    label: 'Go to Programs',  sublabel: 'Manage display programs',    icon: Layers,   action: () => navigate('/programs') },
    { id: 'nav-sources',        type: 'nav',    label: 'Go to Sources',   sublabel: 'Manage content sources',     icon: Database, action: () => navigate('/sources') },
    { id: 'nav-system',         type: 'nav',    label: 'Go to System',    sublabel: 'Settings and configuration', icon: Settings, action: () => navigate('/settings') },
    { id: 'act-new-program',    type: 'action', label: 'New Program',     sublabel: 'Create a display program',   icon: Plus,     action: () => navigate('/programs') },
    { id: 'act-install-source', type: 'action', label: 'Install Source',  sublabel: 'Install a content source',   icon: Download, action: () => navigate('/sources') },
  ];
}

function extractArray(val, key) {
  if (!val) return [];
  if (Array.isArray(val)) return val;
  if (val[key] && Array.isArray(val[key])) return val[key];
  if (val.data) {
    if (Array.isArray(val.data)) return val.data;
    if (val.data[key] && Array.isArray(val.data[key])) return val.data[key];
  }
  return [];
}

function matches(item, query) {
  const q = query.toLowerCase();
  return (
    item.label.toLowerCase().includes(q) ||
    (item.sublabel && item.sublabel.toLowerCase().includes(q))
  );
}

export function CommandPalette({ isOpen, onClose }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [allItems, setAllItems] = useState([]);
  const [selected, setSelected] = useState(0);
  const [dataLoaded, setDataLoaded] = useState(false);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const loadData = useCallback(async () => {
    const statics = buildStaticItems(navigate);
    try {
      const [scenesRaw, channelsRaw, displaysRaw] = await Promise.allSettled([
        persistentCache.getScenes({}),
        persistentCache.getChannels({}),
        api.getDisplays(),
      ]);

      const scenes   = extractArray(scenesRaw.value,   'scenes');
      const channels = extractArray(channelsRaw.value, 'channels');
      const displays = extractArray(displaysRaw.value?.data ?? displaysRaw.value, null);

      const dynamic = [
        ...displays.map(d => ({
          id: `screen-${d.id}`,
          type: 'screen',
          label: d.name || d.hostname || d.id,
          sublabel: [d.location, d.hostname].filter(Boolean).join(' · ') || d.id,
          icon: Monitor,
          action: () => navigate('/screens'),
        })),
        ...scenes.map(s => ({
          id: `program-${s.id}`,
          type: 'program',
          label: s.name,
          sublabel: `${s.channels?.length || 0} source${s.channels?.length !== 1 ? 's' : ''}`,
          icon: Layers,
          action: () => navigate('/programs'),
        })),
        ...channels.map(c => ({
          id: `source-${c.id}`,
          type: 'source',
          label: c.name,
          sublabel: c.description || c.id,
          icon: Database,
          action: () => navigate('/sources'),
        })),
      ];

      setAllItems([...statics, ...dynamic]);
    } catch {
      setAllItems(statics);
    }
    setDataLoaded(true);
  }, [navigate]);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelected(0);
      setDataLoaded(false);
      setTimeout(() => inputRef.current?.focus(), 30);
      loadData();
    }
  }, [isOpen, loadData]);

  const filteredItems = query.trim()
    ? allItems.filter(item => matches(item, query))
    : allItems;

  useEffect(() => {
    setSelected(0);
  }, [query]);

  const execute = useCallback((item) => {
    item.action();
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelected(i => Math.min(i + 1, filteredItems.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelected(i => Math.max(i - 1, 0));
      }
      if (e.key === 'Enter' && filteredItems[selected]) {
        e.preventDefault();
        execute(filteredItems[selected]);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, filteredItems, selected, execute, onClose]);

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selected}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  if (!isOpen) return null;

  // Group items by type when no query
  const grouped = !query.trim();
  const groups = grouped
    ? TYPE_ORDER
        .map(type => ({ type, items: filteredItems.filter(i => i.type === type) }))
        .filter(g => g.items.length > 0)
    : [{ type: null, items: filteredItems }];

  // flat index map for keyboard nav
  let flatIdx = 0;

  return (
    <>
      <div className="cp-overlay" onClick={onClose} aria-hidden="true" />
      <div className="cp-panel" role="dialog" aria-label="Command palette" aria-modal="true">
        <div className="cp-input-row">
          <Search size={15} className="cp-search-icon" aria-hidden="true" />
          <input
            ref={inputRef}
            className="cp-input"
            type="text"
            placeholder="Search screens, programs, sources…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <span className="cp-esc-hint">esc</span>
        </div>

        <div className="cp-list" ref={listRef} role="listbox">
          {!dataLoaded && (
            <div className="cp-loading">Loading…</div>
          )}
          {dataLoaded && filteredItems.length === 0 && (
            <div className="cp-empty">No results for "{query}"</div>
          )}
          {dataLoaded && groups.map(group => (
            <div key={group.type || 'all'} className="cp-group">
              {group.type && (
                <div className="cp-group-label">{TYPE_LABELS[group.type] || group.type}</div>
              )}
              {group.items.map(item => {
                const idx = flatIdx++;
                const isActive = idx === selected;
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    data-idx={idx}
                    role="option"
                    aria-selected={isActive}
                    className={`cp-item${isActive ? ' cp-item--active' : ''}`}
                    onClick={() => execute(item)}
                    onMouseEnter={() => setSelected(idx)}
                  >
                    <Icon size={14} className="cp-item-icon" aria-hidden="true" />
                    <span className="cp-item-label">{item.label}</span>
                    {item.sublabel && (
                      <span className="cp-item-sublabel">{item.sublabel}</span>
                    )}
                    <ArrowRight size={12} className="cp-item-arrow" aria-hidden="true" />
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        <div className="cp-footer">
          <span className="cp-hint"><kbd>↑↓</kbd> navigate</span>
          <span className="cp-hint"><kbd>↵</kbd> select</span>
          <span className="cp-hint"><kbd>esc</kbd> close</span>
          <span className="cp-hint"><kbd>?</kbd> shortcuts</span>
        </div>
      </div>
    </>
  );
}

export default CommandPalette;
