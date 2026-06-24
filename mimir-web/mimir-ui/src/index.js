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
