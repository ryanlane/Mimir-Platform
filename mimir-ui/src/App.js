import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import AddToHomeScreenNudge from './components/AddToHomeScreen/AddToHomeScreenNudge';
import Dashboard from './pages/Dashboard/Dashboard';
import Scenes from './pages/Scenes/Scenes';
import Channels from './pages/Channels/Channels';
import Settings from './pages/Settings/Settings';
import Displays from './pages/Displays/Displays';
import Distribution from './pages/Distribution/Distribution';
import { ErrorBoundary, useToast, ToastContainer, NetworkStatus } from './components/ErrorHandling/ErrorHandling';
import CacheDebug from './utils/cacheDebug';
import './App.css';
import { usePwaUpdates } from './hooks/usePwaUpdates';
import './version';

function AppContent() {
  const toast = useToast();

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
    <>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/scenes" element={<Scenes />} />
            <Route path="/channels" element={<Channels />} />
            <Route path="/displays" element={<Displays />} />
            <Route path="/distribution" element={<Distribution />} />
            <Route path="/settings" element={<Settings />} />
            {/* Catch-all route for unmatched paths */}
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Layout>
      </Router>

      {/* Add To Home Screen Nudge */}
      <AddToHomeScreenNudge onInstalled={() => {
        toast.success('Mimir installed! Enjoy faster access.');
      }} />
      
      {/* Global Toast Container */}
      <ToastContainer toasts={toast.toasts} removeToast={toast.removeToast} />
      
      {/* Network Status Indicator */}
      <div className="network-status-container">
        <NetworkStatus onStatusChange={(isOnline, quality) => {
          if (!isOnline) {
            toast.error('Connection lost. Some features may not work properly.');
          } else if (quality === 'poor') {
            toast.warning('Poor connection detected. Performance may be affected.');
          }
        }} />
      </div>
    </>
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
