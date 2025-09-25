import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

// Register service worker for PWA capabilities
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const swUrl = '/service-worker.js';
    navigator.serviceWorker.register(swUrl).then(reg => {
      console.log('[SW] registered', reg.scope);

      // Listen for updates to the service worker.
      reg.onupdatefound = () => {
        const installing = reg.installing;
        if (!installing) return;
        installing.onstatechange = () => {
          if (installing.state === 'installed') {
            if (navigator.serviceWorker.controller) {
              // New content is available; prompt for reload
              const detail = { type: 'SW_UPDATE_AVAILABLE' };
              window.dispatchEvent(new CustomEvent('mimir:sw-update', { detail }));
              console.log('[SW] Update available. Dispatching mimir:sw-update event.');
            } else {
              console.log('[SW] Content cached for offline use.');
            }
          }
        };
      };
    }).catch(err => {
      console.warn('[SW] registration failed', err);
    });
  });

  // Optional: Listen for custom event to auto-update when user accepts.
  window.addEventListener('mimir:sw-skip-waiting', () => {
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
    }
  });
}
