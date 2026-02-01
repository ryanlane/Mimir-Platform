import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/theme.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { applyPwaModeOnLoad } from './services/pwaServiceWorker';

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

// Service Worker (PWA)
// Default: disabled, because a stale or mis-bound SW can cause navigation refreshes to
// incorrectly fall back to /offline.html. Users can enable it in Settings.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    applyPwaModeOnLoad();
  });
}
