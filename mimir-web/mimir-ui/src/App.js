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

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import AddToHomeScreenNudge from './components/AddToHomeScreen/AddToHomeScreenNudge';
import Scenes from './pages/Scenes/Scenes';
import Channels from './pages/Channels/Channels';
import ChannelDetail from './pages/Channels/ChannelDetail';
import Settings from './pages/Settings/Settings';
import Displays from './pages/Displays/Displays';
import { ErrorBoundary, useToast, ToastContainer } from './components/ErrorHandling/ErrorHandling';
import CacheDebug from './utils/cacheDebug';
import './styles/theme.css';
import './App.css';
import { usePwaUpdates } from './hooks/usePwaUpdates';
import { useSystemTheme } from './hooks/useSystemTheme';

function RedirectChannelDetail() {
  const { channelId } = useParams();
  return <Navigate to={`/sources/${channelId}`} replace />;
}

export const ThemeContext = React.createContext(null);

function AppContent() {
  const toast = useToast();
  const themeState = useSystemTheme();

  // Provide toast context to the whole app
  React.createContext(toast);

  // Enable cache debugging in development
  React.useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      CacheDebug.showVisualIndicator();
      console.log('🚀 Sub-Channels Performance System Loaded');
      console.log('🔍 Use CacheDebug.testCachePerformance() to test API caching');
      console.log('🎨 Use CacheDebug.testSubChannelCache() to test sub-channel caching');
    }
  }, []);

  // Listen for service worker update availability
  React.useEffect(() => {
    const handleUpdate = () => {
      toast.info('New version available', 'info', {
        duration: 20000,
        actionLabel: 'Update',
        onAction: () => {
          window.dispatchEvent(new Event('mimir:sw-skip-waiting'));
        },
        dismissible: true
      });
    };
    window.addEventListener('mimir:sw-update', handleUpdate);

    // When the active service worker changes (after skipWaiting), reload to get fresh assets
    navigator.serviceWorker?.addEventListener('controllerchange', () => {
      // Avoid infinite loops: delay a tick before reload
      setTimeout(() => window.location.reload(), 250);
    });
    return () => {
      window.removeEventListener('mimir:sw-update', handleUpdate);
    };
  }, [toast]);

  // Initialize PWA update lifecycle (hook wires events & polling)
  usePwaUpdates({
    onUpdateAvailable: () => {
      toast.info('New version available', 'info', {
        duration: 20000,
        actionLabel: 'Update',
        onAction: () => {
          window.dispatchEvent(new Event('mimir:sw-skip-waiting'));
        },
        dismissible: true
      });
    },
    onCritical: () => {
      toast.warning('Critical update installing…', 'warning', {
        duration: 10000,
        dismissible: false
      });
      // Force skip waiting without user action
      window.dispatchEvent(new Event('mimir:sw-skip-waiting'));
    }
  });

  // Global skip-waiting handler
  React.useEffect(() => {
    const handler = async () => {
      try {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg?.waiting) {
          reg.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
      } catch (e) {
        console.warn('Skip waiting failed', e);
      }
    };
    window.addEventListener('mimir:sw-skip-waiting', handler);
    return () => window.removeEventListener('mimir:sw-skip-waiting', handler);
  }, []);


  return (
    <ThemeContext.Provider value={themeState}>
      {/* current theme: {theme} */}
      <Router>
        <Layout>
          <Routes>
            {/* Primary routes */}
            <Route path="/screens" element={<Displays />} />
            <Route path="/programs" element={<Scenes />} />
            <Route path="/sources" element={<Channels />} />
            <Route path="/sources/:channelId" element={<ChannelDetail />} />
            <Route path="/settings" element={<Settings />} />
            {/* Legacy redirects */}
            <Route path="/" element={<Navigate to="/screens" replace />} />
            <Route path="/displays" element={<Navigate to="/screens" replace />} />
            <Route path="/scenes" element={<Navigate to="/programs" replace />} />
            <Route path="/channels" element={<Navigate to="/sources" replace />} />
            <Route path="/channels/:channelId" element={<RedirectChannelDetail />} />
            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/screens" replace />} />
          </Routes>
        </Layout>
      </Router>

      {/* Add To Home Screen Nudge */}
      <AddToHomeScreenNudge onInstalled={() => {
        toast.success('Mimir installed! Enjoy faster access.');
      }} />
      
      {/* Global Toast Container */}
      <ToastContainer toasts={toast.toasts} removeToast={toast.removeToast} />
      

    </ThemeContext.Provider>
  );
}

function App() {
  return (
    <ErrorBoundary 
      showDetails={process.env.NODE_ENV === 'development'}
      onError={(error, errorInfo) => {
        console.error('🚨 App Error:', error, errorInfo);
        // Could send to error reporting service here
      }}
    >
      <AppContent />
    </ErrorBoundary>
  );
}

export default App;
