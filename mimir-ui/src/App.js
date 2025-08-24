import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard/Dashboard';
import Scenes from './pages/Scenes/Scenes';
import Channels from './pages/Channels/Channels';
import Settings from './pages/Settings/Settings';
import Displays from './pages/Displays/Displays';
import { ErrorBoundary, useToast, ToastContainer, NetworkStatus } from './components/ErrorHandling/ErrorHandling';
import CacheDebug from './utils/cacheDebug';
import './App.css';

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

  return (
    <>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/scenes" element={<Scenes />} />
            <Route path="/channels" element={<Channels />} />
            <Route path="/displays" element={<Displays />} />
            <Route path="/settings" element={<Settings />} />
            {/* Catch-all route for unmatched paths */}
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Layout>
      </Router>
      
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
