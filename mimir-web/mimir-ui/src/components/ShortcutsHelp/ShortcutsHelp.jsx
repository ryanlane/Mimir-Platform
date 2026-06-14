import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import './ShortcutsHelp.css';

const SHORTCUTS = [
  { keys: ['⌘', 'K'],        desc: 'Open command palette' },
  { keys: ['N'],              desc: 'New object (context-sensitive)' },
  { keys: ['↑', '↓'],        desc: 'Navigate list items' },
  { keys: ['↵'],              desc: 'Open detail panel' },
  { keys: ['Esc'],            desc: 'Close panel / cancel / dismiss' },
  { keys: ['⌘', 'S'],        desc: 'Save current editor' },
  { keys: ['⌘', '⇧', 'P'],  desc: 'Push program to screen' },
  { keys: ['?'],              desc: 'Show this help' },
];

export function ShortcutsHelp({ isOpen, onClose }) {
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape' || e.key === '?') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      <div className="sh-overlay" onClick={onClose} aria-hidden="true" />
      <div className="sh-panel" role="dialog" aria-label="Keyboard shortcuts" aria-modal="true">
        <div className="sh-header">
          <span className="sh-title">Keyboard shortcuts</span>
          <button className="sh-close" onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </div>
        <div className="sh-body">
          {SHORTCUTS.map(({ keys, desc }) => (
            <div key={desc} className="sh-row">
              <div className="sh-keys">
                {keys.map((k, i) => (
                  <React.Fragment key={i}>
                    {i > 0 && <span className="sh-plus">+</span>}
                    <kbd className="sh-key">{k}</kbd>
                  </React.Fragment>
                ))}
              </div>
              <span className="sh-desc">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default ShortcutsHelp;
