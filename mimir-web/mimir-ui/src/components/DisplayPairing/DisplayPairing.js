import React, { useState, useEffect, useRef } from 'react';
import { Tv2, X, Loader } from 'lucide-react';
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
 * DisplayPairing — modal for registering a display via 6-character code or QR scan.
 *
 * Props:
 *   onClose()              — called when the modal is dismissed
 *   onPaired(display)      — called with the new DisplayClientResponse on success
 *   initialCode            — optional pre-filled code (e.g. from ?pair= query param)
 */
const DisplayPairing = ({ onClose, onPaired, initialCode = '' }) => {
  const [code, setCode] = useState(initialCode.toUpperCase());
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [status, setStatus] = useState('idle'); // idle | submitting | success | error
  const [errorMsg, setErrorMsg] = useState('');
  const [connectionConfig, setConnectionConfig] = useState(null);
  const [connectionConfigError, setConnectionConfigError] = useState('');
  const [detectedLanHost, setDetectedLanHost] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
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
            <p>Display paired successfully!</p>
            <button className="pairing-btn-primary" onClick={onClose}>Done</button>
          </div>
        ) : (
          <form className="pairing-form" onSubmit={handleSubmit}>
            <p className="pairing-instructions">
              Enter the 6-character code shown on your display, or scan its QR code.
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

            <details className="pairing-details">
              <summary>Advanced manual setup</summary>
              <div className="pairing-advanced">
                <p className="pairing-advanced-text">
                  Use this when the display cannot auto-discover or auto-bootstrap from the service.
                </p>

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
            </details>

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
      </div>
    </div>
  );
};

export default DisplayPairing;
