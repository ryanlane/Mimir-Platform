import React, { useState, useEffect } from 'react';
import Navigation from './Navigation';
import MobileNavigation from './MobileNavigation';
import StatusBar from '../StatusBar/StatusBar';
import { CommandPalette } from '../CommandPalette/CommandPalette';
import { ShortcutsHelp } from '../ShortcutsHelp/ShortcutsHelp';
import './Layout.css';

const Layout = ({ children }) => {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      const inInput = e.target.tagName === 'INPUT'
        || e.target.tagName === 'TEXTAREA'
        || e.target.isContentEditable;

      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShortcutsOpen(false);
        setPaletteOpen(v => !v);
        return;
      }

      if (!inInput && e.key === '?' && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setPaletteOpen(false);
        setShortcutsOpen(v => !v);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="layout">
      <StatusBar onOpenPalette={() => setPaletteOpen(true)} />
      <div className="layout-body">
        <Navigation />
        <main className="layout-main">
          {children}
        </main>
      </div>
      <MobileNavigation />
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <ShortcutsHelp isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
};

export default Layout;
