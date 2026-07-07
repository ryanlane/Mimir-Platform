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

const DEV_SERVER_PORTS = new Set(['3000', '5173']);

function getRuntimeApiOverride() {
  if (typeof window === 'undefined') return null;
  return window.mimirApiBaseUrl || localStorage.getItem('mimir-api-base-url');
}

export function ensureApiSuffix(base) {
  try {
    const u = new URL(base, window.location.origin);
    u.pathname = u.pathname.replace(/\/+$/, '') || '/';
    if (!/^\/api(\/|$)/i.test(u.pathname)) {
      u.pathname = (u.pathname === '/' ? '' : u.pathname) + '/api';
    }
    return u.toString();
  } catch {
    const t = String(base).replace(/\/+$/, '');
    return /\/api(\/|$)/i.test(t) ? t : `${t}/api`;
  }
}

export function getServerBaseUrlFromApiBase(base) {
  try {
    const u = new URL(base, window.location.origin);
    u.pathname = u.pathname.replace(/\/+$/, '').replace(/\/api$/, '') || '/';
    return u.toString().replace(/\/$/, '');
  } catch {
    return String(base).replace(/\/+$/, '').replace(/\/api$/, '');
  }
}

export function getApiBaseUrl() {
  if (process.env.REACT_APP_API_URL) {
    return ensureApiSuffix(process.env.REACT_APP_API_URL);
  }

  const raw = getRuntimeApiOverride();
  if (raw) {
    return ensureApiSuffix(raw);
  }

  if (typeof window !== 'undefined' && window.location) {
    const { hostname, origin, port } = window.location;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';

    // Production/containerized web traffic should prefer same-origin /api so
    // browsers do not need separate reachability to port 5000.
    if (!isLocalhost && !DEV_SERVER_PORTS.has(port)) {
      return ensureApiSuffix(origin);
    }

    if (!isLocalhost && DEV_SERVER_PORTS.has(port)) {
      return `http://${hostname}:5000/api`;
    }

    return 'http://localhost:5000/api';
  }

  return 'http://localhost:5000/api';
}

export function getServerBaseUrl() {
  const raw = getRuntimeApiOverride() || process.env.REACT_APP_API_URL;
  if (raw) {
    return getServerBaseUrlFromApiBase(raw);
  }

  if (typeof window !== 'undefined' && window.location) {
    const { hostname, origin, port } = window.location;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';

    if (!isLocalhost && !DEV_SERVER_PORTS.has(port)) {
      return origin.replace(/\/$/, '');
    }

    if (!isLocalhost && DEV_SERVER_PORTS.has(port)) {
      return `http://${hostname}:5000`;
    }

    return 'http://localhost:5000';
  }

  return 'http://localhost:5000';
}

export function getWebSocketBaseUrl() {
  if (typeof window !== 'undefined') {
    const storedUrl = localStorage.getItem('mimir-websocket-url');
    if (storedUrl) {
      return storedUrl;
    }
  }

  if (typeof window !== 'undefined' && window.location) {
    const { hostname, protocol, origin, port } = window.location;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
    const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';

    if (!isLocalhost && !DEV_SERVER_PORTS.has(port)) {
      const url = new URL(origin);
      url.protocol = wsProtocol;
      return url.toString().replace(/\/$/, '');
    }

    if (!isLocalhost && DEV_SERVER_PORTS.has(port)) {
      return `ws://${hostname}:5000`;
    }

    return 'ws://localhost:5000';
  }

  return 'ws://localhost:5000';
}
