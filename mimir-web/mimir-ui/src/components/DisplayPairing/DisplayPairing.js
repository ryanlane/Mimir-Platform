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

import React, { useState, useEffect, useRef } from 'react';
import { Tv2, X, Loader, Camera, Keyboard, Wrench, Copy, Check } from 'lucide-react';
import { api } from '../../services/api';
import './DisplayPairing.css';

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const INTERNAL_HOSTS = new Set([
  'localhost',
  '127.0.0.1',
  '::1',
  '0.0.0.0',
  'api',
  'db',
  'mqtt',
  'redis',
  'web',
  'discovery',
  'mimir-api',
  'mimir-db',
  'mimir-mqtt',
  'mimir-redis',
  'mimir-web',
  'mimir-discovery',
]);

const IPV4_HOST_RE = /\b(?:\d{1,3}\.){3}\d{1,3}\b/;
const PAIR_CODE_RE = /^[A-Z2-9]{6}$/;

async function provisionDisplayFromSetupUrl(setupUrl, displayName, displayLocation, publicHostHint) {
  const response = await fetch(`${api.getApiBaseUrl()}/displays/provision-from-setup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      setup_url: setupUrl,
      display_name: displayName,
      display_location: displayLocation,
      public_host_hint: publicHostHint,
    }),
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = data?.detail || `Request failed with status ${response.status}`;
    const error = new Error(detail);
    error.response = { data, status: response.status };
    throw error;
  }

  return { data };
}

function extractHostname(value) {
  if (!value) {
    return null;
  }

  try {
    return new URL(value).hostname;
  } catch {
    return String(value).trim() || null;
  }
}

function isUnusableAdvertisedHost(value) {
  const hostname = extractHostname(value);
  if (!hostname) {
    return true;
  }

  const normalized = hostname.toLowerCase();
  const baseHost = normalized.endsWith('.local') ? normalized.slice(0, -6) : normalized;
  if (INTERNAL_HOSTS.has(normalized)) {
    return true;
  }

  if (INTERNAL_HOSTS.has(baseHost)) {
    return true;
  }

  return /^[0-9a-f]{12,64}$/i.test(baseHost);
}

function isLikelyLanIpv4(value) {
  if (!value || !IPV4_HOST_RE.test(value)) {
    return false;
  }

  if (value.startsWith('127.') || value.startsWith('169.254.') || value === '0.0.0.0') {
    return false;
  }

  return true;
}

function isLikelyDockerBridgeHost(value) {
  if (!value) {
    return false;
  }

  const hostname = extractHostname(value);
  if (!hostname || !IPV4_HOST_RE.test(hostname)) {
    return false;
  }

  return /^172\.(1[6-9]|2\d|3[01])\./.test(hostname);
}

function extractPort(value, fallbackPort) {
  if (!value) {
    return fallbackPort;
  }

  try {
    const parsed = new URL(value);
    return parsed.port || fallbackPort;
  } catch {
    return fallbackPort;
  }
}

function buildHttpUrl(host, port) {
  if (!host) {
    return '';
  }
  if (!port || port === '80') {
    return `http://${host}`;
  }
  return `http://${host}:${port}`;
}

function normalizeSetupUrlInput(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) {
    return '';
  }

  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;

  try {
    const parsed = new URL(withProtocol);
    if (!parsed.pathname || parsed.pathname === '/') {
      parsed.pathname = '/setup';
    }
    parsed.search = '';
    parsed.hash = '';
    return parsed.toString();
  } catch {
    return withProtocol;
  }
}

function extractPairCodeFromValue(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) {
    return '';
  }

  if (PAIR_CODE_RE.test(trimmed.toUpperCase())) {
    return trimmed.toUpperCase();
  }

  try {
    const parsed = new URL(trimmed);
    const pairCode = parsed.searchParams.get('pair') || '';
    return PAIR_CODE_RE.test(pairCode.toUpperCase()) ? pairCode.toUpperCase() : '';
  } catch {
    return '';
  }
}

async function detectBrowserLanIp() {
  if (typeof window === 'undefined') {
    return null;
  }

  const RTCPeerConnectionCtor = window.RTCPeerConnection
    || window.webkitRTCPeerConnection
    || window.mozRTCPeerConnection;

  if (!RTCPeerConnectionCtor) {
    return null;
  }

  return new Promise((resolve) => {
    const discovered = new Set();
    const connection = new RTCPeerConnectionCtor({ iceServers: [] });

    const finish = (value = null) => {
      try {
        connection.onicecandidate = null;
        connection.close();
      } catch {
        // Best effort cleanup.
      }
      resolve(value);
    };

    const considerCandidate = (candidateText) => {
      const match = candidateText?.match(IPV4_HOST_RE);
      if (!match) {
        return false;
      }

      const ip = match[0];
      if (!isLikelyLanIpv4(ip) || discovered.has(ip)) {
        return false;
      }

      discovered.add(ip);
      finish(ip);
      return true;
    };

    const timer = window.setTimeout(() => finish(null), 3000);

    connection.onicecandidate = (event) => {
      if (!event?.candidate?.candidate) {
        return;
      }

      if (considerCandidate(event.candidate.candidate)) {
        window.clearTimeout(timer);
      }
    };

    connection.createDataChannel('mimir-lan-probe');
    connection.createOffer()
      .then((offer) => connection.setLocalDescription(offer))
      .then(() => {
        const sdp = connection.localDescription?.sdp || '';
        if (considerCandidate(sdp)) {
          window.clearTimeout(timer);
        }
      })
      .catch(() => {
        window.clearTimeout(timer);
        finish(null);
      });
  });
}

/**
 * DisplayPairing — modal for onboarding a display via setup URL, QR scan, or pair code.
 *
 * Props:
 *   onClose()              — called when the modal is dismissed
 *   onPaired(display)      — called with the new DisplayClientResponse on success
 *   initialCode            — optional pre-filled code (e.g. from ?pair= query param)
 */
const DisplayPairing = ({ onClose, onPaired, initialCode = '' }) => {
  const [mode, setMode] = useState(initialCode.trim() ? 'pair' : 'setup');
  const [code, setCode] = useState(initialCode.toUpperCase());
  const [setupUrl, setSetupUrl] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [status, setStatus] = useState('idle'); // idle | submitting | success | error
  const [successMsg, setSuccessMsg] = useState('');
  const [refreshOnSuccess, setRefreshOnSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [scanError, setScanError] = useState('');
  const [qrScanLoading, setQrScanLoading] = useState(false);
  const [connectionConfig, setConnectionConfig] = useState(null);
  const [connectionConfigError, setConnectionConfigError] = useState('');
  const [detectedLanHost, setDetectedLanHost] = useState('');
  const [provisionBundle, setProvisionBundle] = useState(null);
  const [provisionBundleLoading, setProvisionBundleLoading] = useState(false);
  const [provisionBundleCopied, setProvisionBundleCopied] = useState(false);
  const inputRef = useRef(null);
  const setupInputRef = useRef(null);
  const qrInputRef = useRef(null);

  useEffect(() => {
    if (mode === 'pair') {
      inputRef.current?.focus();
      return;
    }

    if (mode === 'setup') {
      setupInputRef.current?.focus();
    }
  }, [mode]);

  useEffect(() => {
    let cancelled = false;

    api.getDisplayConnectionConfig()
      .then((response) => {
        if (!cancelled) {
          setConnectionConfig(response.data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConnectionConfigError('Connection details are unavailable right now.');
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.location) {
      return undefined;
    }

    if (!isUnusableAdvertisedHost(window.location.hostname)) {
      return undefined;
    }

    let cancelled = false;

    detectBrowserLanIp().then((ip) => {
      if (!cancelled && ip) {
        setDetectedLanHost(ip);
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const normalizedCode = initialCode.trim().toUpperCase();
    if (normalizedCode.length !== 6) {
      return undefined;
    }

    let cancelled = false;

    const autoClaim = async () => {
      setStatus('submitting');
      setErrorMsg('Waiting for the display to finish registering its pairing code…');

      const deadline = Date.now() + 15000;
      while (!cancelled && Date.now() < deadline) {
        try {
          const statusResponse = await api.getPairCodeStatus(normalizedCode);
          if (statusResponse?.data?.status === 'pending') {
            await submitPairCode(normalizedCode);
            return;
          }
        } catch (err) {
          if (err?.response?.status && err.response.status !== 404) {
            throw err;
          }
        }

        await wait(1000);
      }

      if (!cancelled) {
        setStatus('error');
        setErrorMsg('Display is not ready to pair yet. Wait for the pairing-ready message on the display, then try again.');
      }
    };

    autoClaim().catch((err) => {
      if (cancelled) {
        return;
      }
      const detail = err?.response?.data?.detail || err.message || 'Unknown error';
      setStatus('error');
      setErrorMsg(detail);
    });

    return () => {
      cancelled = true;
    };
  }, [initialCode]);

  const handleCodeChange = (e) => {
    const raw = e.target.value.toUpperCase().replace(/[^A-Z2-9]/g, '');
    setCode(raw.slice(0, 6));
    setErrorMsg('');
  };

  const handleSetupUrlChange = (e) => {
    setSetupUrl(e.target.value);
    setErrorMsg('');
    setScanError('');
  };

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    setErrorMsg('');
    setScanError('');
  };

  const submitPairCode = async (pairCode) => {
    setStatus('submitting');
    setErrorMsg('');

    try {
      const response = await api.claimPairCode(pairCode, name || undefined, location || undefined);
      setStatus('success');
      onPaired?.(response.data);
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Unknown error';
      setErrorMsg(
        detail.includes('not found') || detail.includes('expired')
          ? 'Code not found or expired. Check the display and try again.'
          : detail
      );
      setStatus('error');
    }
  };

  const handleSubmit = async (e) => {
    e?.preventDefault();
    const trimmed = code.trim();
    if (trimmed.length !== 6) {
      setErrorMsg('Please enter the full 6-character code shown on your display.');
      return;
    }

    await submitPairCode(trimmed);
  };

  const handleSetupSubmit = async () => {
    const normalizedSetupUrl = normalizeSetupUrlInput(setupUrl);
    if (!normalizedSetupUrl) {
      setErrorMsg('Paste the setup URL shown on the display first.');
      return;
    }

    setStatus('submitting');
    setErrorMsg('');
    setScanError('');

    try {
      const publicHostHint = browserReachableHost
        || detectedLanHost
        || (!isLikelyDockerBridgeHost(backendReachableHost) ? backendReachableHost : '')
        || '';

      if (!publicHostHint) {
        setStatus('error');
        setErrorMsg('Cannot determine the Mimir server LAN address from this browser session. Open Mimir using its LAN IP or set PUBLIC_HOST and MQTT_PUBLIC_HOST.');
        return;
      }

      const response = await provisionDisplayFromSetupUrl(
        normalizedSetupUrl,
        name || undefined,
        location || undefined,
        publicHostHint,
      );
      setSetupUrl(response?.data?.setup_url || normalizedSetupUrl);
      setSuccessMsg(
        response?.data?.message
          || 'Provisioning sent. The display should finish registering within a few seconds.'
      );
      setRefreshOnSuccess(true);
      setStatus('success');
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Unknown error';
      setErrorMsg(detail);
      setStatus('error');
    }
  };

  const handleGetProvisionBundle = async () => {
    setProvisionBundleLoading(true);
    setProvisionBundleCopied(false);
    try {
      const response = await api.getProvisionBundle();
      setProvisionBundle(response.data);
    } catch {
      setProvisionBundle({ error: 'Failed to generate bundle. Check server connectivity.' });
    } finally {
      setProvisionBundleLoading(false);
    }
  };

  const handleCopyBundle = async () => {
    if (!provisionBundle?.bundle || !navigator?.clipboard?.writeText) {
      return;
    }
    await navigator.clipboard.writeText(provisionBundle.bundle);
    setProvisionBundleCopied(true);
    window.setTimeout(() => setProvisionBundleCopied(false), 2000);
  };

  const handleScanQrClick = () => {
    setScanError('');
    qrInputRef.current?.click();
  };

  const handleQrFileSelected = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }

    if (typeof window === 'undefined' || typeof window.BarcodeDetector === 'undefined' || typeof window.createImageBitmap !== 'function') {
      setScanError('QR scanning is not supported in this browser. Paste the setup URL instead.');
      return;
    }

    setQrScanLoading(true);
    setScanError('');
    setErrorMsg('');

    let bitmap;
    try {
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
      bitmap = await window.createImageBitmap(file);
      const results = await detector.detect(bitmap);
      const rawValue = results?.[0]?.rawValue?.trim();

      if (!rawValue) {
        setScanError('No QR code was found in that image.');
        return;
      }

      const pairCode = extractPairCodeFromValue(rawValue);
      if (pairCode) {
        setMode('pair');
        setCode(pairCode);
        return;
      }

      const normalizedSetupUrl = normalizeSetupUrlInput(rawValue);
      if (normalizedSetupUrl) {
        setMode('setup');
        setSetupUrl(normalizedSetupUrl);
        return;
      }

      setScanError('QR code did not contain a Mimir setup URL or pairing code.');
    } catch {
      setScanError('Unable to read that QR code image. Paste the setup URL instead.');
    } finally {
      if (bitmap?.close) {
        bitmap.close();
      }
      setQrScanLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
  };

  const handleSuccessDone = () => {
    if (refreshOnSuccess && onPaired) {
      onPaired();
      return;
    }
    onClose();
  };

  const invalidPlatformUrl = isUnusableAdvertisedHost(connectionConfig?.platform_url);
  const invalidMqttHost = isUnusableAdvertisedHost(connectionConfig?.host);
  const browserHost = (() => {
    if (typeof window === 'undefined' || !window.location) {
      return '';
    }

    return window.location.hostname;
  })();

  const browserReachableHost = !isUnusableAdvertisedHost(browserHost) ? browserHost : '';
  const fallbackReachableHost = browserReachableHost || detectedLanHost;
  const backendReachableHost = !invalidPlatformUrl
    ? extractHostname(connectionConfig?.platform_url)
    : (!invalidMqttHost ? extractHostname(connectionConfig?.host) : '');
  const manualSetupHost = backendReachableHost || fallbackReachableHost;
  const platformPort = extractPort(connectionConfig?.platform_url, '5000');
  const mqttPort = String(connectionConfig?.port || 1883);
  const manualPlatformUrl = backendReachableHost && !invalidPlatformUrl
    ? connectionConfig.platform_url
    : buildHttpUrl(manualSetupHost, platformPort);
  const manualMqttHost = manualSetupHost;
  const hasUsableConnectionConfig = Boolean(manualPlatformUrl && manualMqttHost);
  const suggestedPublicHost = manualSetupHost || (() => {
    if (browserReachableHost) {
      return browserReachableHost;
    }

    return detectedLanHost || '192.168.1.50';
  })();

  const manualEnvLines = [];

  if (hasUsableConnectionConfig && manualPlatformUrl) {
    manualEnvLines.push(`PLATFORM_URL=${manualPlatformUrl}`);
  }
  if (hasUsableConnectionConfig && manualMqttHost) {
    manualEnvLines.push(`MQTT_BROKER_HOST=${manualMqttHost}`);
  }
  if (hasUsableConnectionConfig && mqttPort) {
    manualEnvLines.push(`MQTT_BROKER_PORT=${mqttPort}`);
  }
  if (hasUsableConnectionConfig && connectionConfig?.username) {
    manualEnvLines.push(`MQTT_USERNAME=${connectionConfig.username}`);
  }
  if (hasUsableConnectionConfig && connectionConfig?.password) {
    manualEnvLines.push(`MQTT_PASSWORD=${connectionConfig.password}`);
  }

  const manualScriptArgs = [];
  if (hasUsableConnectionConfig && manualPlatformUrl) {
    manualScriptArgs.push(`--platform-url ${manualPlatformUrl}`);
  }
  if (hasUsableConnectionConfig && manualMqttHost) {
    manualScriptArgs.push(`--mqtt-host ${manualMqttHost}`);
  }
  if (hasUsableConnectionConfig && mqttPort) {
    manualScriptArgs.push(`--mqtt-port ${mqttPort}`);
  }
  if (hasUsableConnectionConfig && connectionConfig?.username) {
    manualScriptArgs.push(`--mqtt-username ${connectionConfig.username}`);
  }

  const manualConfigHint = [
    `PUBLIC_HOST=${suggestedPublicHost}`,
    `MQTT_PUBLIC_HOST=${suggestedPublicHost}`,
    `REACT_APP_API_URL=http://${suggestedPublicHost}:5000`,
    '# Optional if you advertise mimir.local on your LAN',
    '# PUBLIC_MDNS_HOST=mimir.local',
  ].join('\n');

  const usingBrowserDetectedHost = Boolean(!backendReachableHost && fallbackReachableHost);
  const showPublicHostWarning = connectionConfig && !backendReachableHost;

  const renderOptionalInfo = () => (
    <details className="pairing-details">
      <summary>Optional display info</summary>
      <div className="pairing-optional">
        <label>
          Name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Living Room Display"
            disabled={status === 'submitting'}
          />
        </label>
        <label>
          Location
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Living Room"
            disabled={status === 'submitting'}
          />
        </label>
      </div>
    </details>
  );

  return (
    <div className="pairing-overlay" onKeyDown={handleKeyDown} role="dialog" aria-modal="true" aria-label="Pair a display">
      <div className="pairing-modal">
        <div className="pairing-header">
          <Tv2 size={20} />
          <h2>Add a Display</h2>
          <button className="pairing-close" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {status === 'success' ? (
          <div className="pairing-success">
            <div className="pairing-success-icon">✓</div>
            <p>{successMsg || 'Display paired successfully!'}</p>
            <button className="pairing-btn-primary" onClick={handleSuccessDone}>Done</button>
          </div>
        ) : (
          <div className="pairing-form">
            <input
              ref={qrInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="pairing-hidden-input"
              onChange={handleQrFileSelected}
            />

            <p className="pairing-instructions">
              Start with the display setup URL when possible. Pair code remains available as a fallback.
            </p>

            <div className="pairing-mode-tabs" role="tablist" aria-label="Display onboarding options">
              <button
                type="button"
                className={`pairing-mode-tab ${mode === 'setup' ? 'pairing-mode-tab--active' : ''}`}
                onClick={() => handleModeChange('setup')}
                disabled={status === 'submitting'}
              >
                <Camera size={14} />
                Setup URL
              </button>
              <button
                type="button"
                className={`pairing-mode-tab ${mode === 'pair' ? 'pairing-mode-tab--active' : ''}`}
                onClick={() => handleModeChange('pair')}
                disabled={status === 'submitting'}
              >
                <Keyboard size={14} />
                Pair Code
              </button>
              <button
                type="button"
                className={`pairing-mode-tab ${mode === 'manual' ? 'pairing-mode-tab--active' : ''}`}
                onClick={() => handleModeChange('manual')}
                disabled={status === 'submitting'}
              >
                <Wrench size={14} />
                Manual
              </button>
            </div>

            {mode === 'setup' && (
              <>
                <div className="pairing-setup-card">
                  <div className="pairing-setup-actions">
                    <button
                      type="button"
                      className="pairing-btn-secondary"
                      onClick={handleScanQrClick}
                      disabled={status === 'submitting' || qrScanLoading}
                    >
                      {qrScanLoading ? <Loader size={14} className="pairing-spinner" /> : <Camera size={14} />}
                      {qrScanLoading ? 'Reading QR…' : 'Scan QR Code'}
                    </button>
                    <span className="pairing-setup-hint">
                      On phones this can open the camera. On desktop, upload a photo of the QR.
                    </span>
                  </div>

                  <label className="pairing-field">
                    <span>Setup URL</span>
                    <input
                      ref={setupInputRef}
                      type="text"
                      value={setupUrl}
                      onChange={handleSetupUrlChange}
                      placeholder="http://192.168.1.41:7777/setup"
                      spellCheck={false}
                      autoComplete="off"
                      autoCorrect="off"
                      disabled={status === 'submitting'}
                    />
                  </label>

                  <p className="pairing-setup-note">
                    Paste the URL shown in the display QR code or on the setup page. Mimir will send the provision bundle directly to that device.
                  </p>
                </div>

                {scanError && <p className="pairing-advanced-error">{scanError}</p>}
                {errorMsg && <p className="pairing-error">{errorMsg}</p>}

                {renderOptionalInfo()}

                <div className="pairing-actions">
                  <button type="button" className="pairing-btn-secondary" onClick={onClose} disabled={status === 'submitting'}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="pairing-btn-primary"
                    onClick={handleSetupSubmit}
                    disabled={!setupUrl.trim() || status === 'submitting'}
                  >
                    {status === 'submitting' ? (
                      <><Loader size={14} className="pairing-spinner" /> Provisioning…</>
                    ) : (
                      'Provision Display'
                    )}
                  </button>
                </div>
              </>
            )}

            {mode === 'pair' && (
              <form className="pairing-section" onSubmit={handleSubmit}>
                <p className="pairing-instructions">
                  Enter the 6-character code shown on the display, or scan a QR code that contains the pair code.
                </p>

                <div className="pairing-code-row">
                  <input
                    ref={inputRef}
                    className={`pairing-code-input ${errorMsg ? 'pairing-code-input--error' : ''}`}
                    type="text"
                    value={code}
                    onChange={handleCodeChange}
                    placeholder="ABC123"
                    maxLength={6}
                    spellCheck={false}
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="characters"
                    disabled={status === 'submitting'}
                    aria-label="Pairing code"
                  />
                </div>

                {errorMsg && <p className="pairing-error">{errorMsg}</p>}

                {renderOptionalInfo()}

                <div className="pairing-actions">
                  <button type="button" className="pairing-btn-secondary" onClick={onClose} disabled={status === 'submitting'}>
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="pairing-btn-primary"
                    disabled={code.length !== 6 || status === 'submitting'}
                  >
                    {status === 'submitting' ? (
                      <><Loader size={14} className="pairing-spinner" /> Pairing…</>
                    ) : (
                      'Pair Display'
                    )}
                  </button>
                </div>
              </form>
            )}

            {mode === 'manual' && (
              <div className="pairing-section">
                <div className="pairing-advanced">
                  <p className="pairing-advanced-text">
                    Use this when the display cannot auto-discover or when direct setup URL provisioning is unavailable.
                  </p>

                  <div className="pairing-provision-section">
                    <div className="pairing-advanced-label">Provision Bundle</div>
                    <p className="pairing-advanced-text">
                      Open <code>http://&lt;device-ip&gt;:7777/setup</code> on the display device, then paste this one-time bundle.
                    </p>
                    {!provisionBundle ? (
                      <button
                        type="button"
                        className="pairing-btn-secondary pairing-bundle-btn"
                        onClick={handleGetProvisionBundle}
                        disabled={provisionBundleLoading}
                      >
                        {provisionBundleLoading ? <Loader size={13} className="pairing-spinner" /> : null}
                        {provisionBundleLoading ? 'Generating…' : 'Get Provision Bundle'}
                      </button>
                    ) : provisionBundle.error ? (
                      <p className="pairing-advanced-error">{provisionBundle.error}</p>
                    ) : (
                      <div className="pairing-bundle-result">
                        <pre className="pairing-advanced-code pairing-bundle-code">{provisionBundle.bundle}</pre>
                        <button
                          type="button"
                          className="pairing-btn-secondary pairing-bundle-copy"
                          onClick={handleCopyBundle}
                        >
                          {provisionBundleCopied ? <Check size={13} /> : <Copy size={13} />}
                          {provisionBundleCopied ? 'Copied!' : 'Copy'}
                        </button>
                      </div>
                    )}
                  </div>

                  {showPublicHostWarning && (
                    <div className="pairing-advanced-warning">
                      <p className="pairing-advanced-warning-text">
                        Mimir is currently advertising a loopback or Docker-internal hostname. Remote displays cannot reach that address.
                        This setup uses the machine address visible from your browser instead. Set these values in a local <code>.env</code> file in the service repo, then restart <code>docker compose up -d --build</code>.
                      </p>
                      <pre className="pairing-advanced-code">{manualConfigHint}</pre>
                    </div>
                  )}

                  {usingBrowserDetectedHost && (
                    <p className="pairing-advanced-note">
                      Manual setup is using <strong>{manualSetupHost}</strong> as the machine address for this device.
                    </p>
                  )}

                  {manualScriptArgs.length > 0 && (
                    <>
                      <div className="pairing-advanced-label">Run on the display</div>
                      <pre className="pairing-advanced-code">./scripts/setup_connection.sh {manualScriptArgs.join(' ')}</pre>
                    </>
                  )}

                  {manualEnvLines.length > 0 && (
                    <>
                      <div className="pairing-advanced-label">Manual .env values</div>
                      <pre className="pairing-advanced-code">{manualEnvLines.join('\n')}</pre>
                    </>
                  )}

                  {connectionConfigError && (
                    <p className="pairing-advanced-error">{connectionConfigError}</p>
                  )}
                </div>

                <div className="pairing-actions">
                  <button type="button" className="pairing-btn-secondary" onClick={onClose} disabled={status === 'submitting'}>
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DisplayPairing;
