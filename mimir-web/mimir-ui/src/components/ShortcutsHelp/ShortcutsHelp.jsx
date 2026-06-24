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
