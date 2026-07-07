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

import React, { useState } from 'react';
import { Smartphone, Wifi, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { getServerBaseUrl, getWebSocketBaseUrl } from '../../services/runtimeUrls';
import './MobileConnectionGuide.css';

const MobileConnectionGuide = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getCurrentPageUrl = () => {
    if (typeof window === 'undefined') return '';
    const { protocol, hostname, port } = window.location;
    return `${protocol}//${hostname}${port ? `:${port}` : ''}`;
  };

  const getRecommendedApiUrl = () => {
    return getServerBaseUrl();
  };

  const getRecommendedWsUrl = () => {
    return getWebSocketBaseUrl();
  };

  return (
    <div className="mobile-guide">
      <div className="guide-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="guide-title">
          <Smartphone size={16} />
          <span>Mobile Connection Guide</span>
        </div>
        <button className="expand-button">
          {isExpanded ? '−' : '+'}
        </button>
      </div>
      
      {isExpanded && (
        <div className="guide-content">
          <div className="guide-section">
            <div className="section-icon">
              <AlertTriangle size={16} />
            </div>
            <div className="section-content">
              <h4>Common Mobile Issues</h4>
              <ul>
                <li>Scenes not loading on mobile devices</li>
                <li>Connection timeouts on iOS Safari</li>
                <li>Data not updating in real-time</li>
                <li>Works on desktop but fails on mobile</li>
              </ul>
            </div>
          </div>

          <div className="guide-section">
            <div className="section-icon">
              <Wifi size={16} />
            </div>
            <div className="section-content">
              <h4>Network Requirements</h4>
              <ul>
                <li>Mobile device must be on the same network as the Mimir server</li>
                <li>Mobile device needs access to port 5000</li>
                <li>WebSocket connections must be allowed</li>
                <li>Some corporate/public WiFi may block WebSocket connections</li>
              </ul>
            </div>
          </div>

          <div className="guide-section">
            <div className="section-icon">
              <CheckCircle size={16} />
            </div>
            <div className="section-content">
              <h4>Recommended Configuration</h4>
              <p>Based on your current page URL, try these settings:</p>
              
              <div className="recommended-config">
                <div className="config-item">
                  <label>API Base URL:</label>
                  <code>{getRecommendedApiUrl()}</code>
                </div>
                <div className="config-item">
                  <label>WebSocket Base URL:</label>
                  <code>{getRecommendedWsUrl()}</code>
                </div>
              </div>
              
              <p className="config-note">
                <Info size={14} />
                Copy these URLs to the connection configuration above and test them.
              </p>
            </div>
          </div>

          <div className="guide-section">
            <div className="section-icon">
              <Info size={16} />
            </div>
            <div className="section-content">
              <h4>Troubleshooting Steps</h4>
              <ol>
                <li>Ensure your mobile device is connected to the same WiFi network</li>
                <li>Try accessing the API URL directly in your mobile browser: <code>{getRecommendedApiUrl()}/health</code></li>
                <li>Check if your router/firewall blocks WebSocket connections</li>
                <li>Try using the server's IP address instead of hostname</li>
                <li>Disable any VPN or proxy on your mobile device</li>
                <li>Clear browser cache and reload the page</li>
              </ol>
            </div>
          </div>

          <div className="guide-section">
            <div className="section-icon">
              <Smartphone size={16} />
            </div>
            <div className="section-content">
              <h4>iOS Safari Specific</h4>
              <ul>
                <li>iOS Safari has strict WebSocket policies</li>
                <li>Ensure "Block All Cookies" is disabled in Safari settings</li>
                <li>Try using "Private Browsing" mode to rule out cache issues</li>
                <li>Consider using Chrome or Firefox on iOS as an alternative</li>
              </ul>
            </div>
          </div>

          <div className="auto-detect-info">
            <h4>Auto-Detection</h4>
            <p>
              If you leave the configuration fields blank, the app will automatically detect 
              the correct URLs based on your current page location: <strong>{getCurrentPageUrl()}</strong>
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default MobileConnectionGuide;
