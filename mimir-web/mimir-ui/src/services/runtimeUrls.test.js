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

import {
  ensureApiSuffix,
  getApiBaseUrl,
  getServerBaseUrl,
  getWebSocketBaseUrl,
} from './runtimeUrls';

describe('runtimeUrls', () => {
  const originalLocation = window.location;

  function setLocation(url) {
    delete window.location;
    window.location = new URL(url);
  }

  beforeEach(() => {
    localStorage.clear();
    delete window.mimirApiBaseUrl;
    setLocation('http://localhost:3000/');
    delete process.env.REACT_APP_API_URL;
  });

  afterAll(() => {
    delete window.location;
    window.location = originalLocation;
  });

  it('prefers same-origin api for non-dev hosted UI', () => {
    setLocation('http://mimir.local:8080/displays');

    expect(getApiBaseUrl()).toBe('http://mimir.local:8080/api');
    expect(getServerBaseUrl()).toBe('http://mimir.local:8080');
    expect(getWebSocketBaseUrl()).toBe('ws://mimir.local:8080');
  });

  it('keeps direct backend routing for CRA dev ports on remote hosts', () => {
    setLocation('http://192.168.1.50:3000/');

    expect(getApiBaseUrl()).toBe('http://192.168.1.50:5000/api');
    expect(getServerBaseUrl()).toBe('http://192.168.1.50:5000');
    expect(getWebSocketBaseUrl()).toBe('ws://192.168.1.50:5000');
  });

  it('normalizes explicit api overrides', () => {
    window.mimirApiBaseUrl = 'http://mimir.local:8080';

    expect(ensureApiSuffix(window.mimirApiBaseUrl)).toBe('http://mimir.local:8080/api');
    expect(getApiBaseUrl()).toBe('http://mimir.local:8080/api');
    expect(getServerBaseUrl()).toBe('http://mimir.local:8080');
  });
});
