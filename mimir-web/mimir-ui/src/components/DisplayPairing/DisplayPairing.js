import React, { useState, useEffect, useRef } from 'react';
import { Tv2, X, Loader } from 'lucide-react';
import { api } from '../../services/api';
import './DisplayPairing.css';

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
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-submit if a full code was passed in via URL
  useEffect(() => {
    if (initialCode && initialCode.length === 6) {
      handleSubmit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCodeChange = (e) => {
    const raw = e.target.value.toUpperCase().replace(/[^A-Z2-9]/g, '');
    setCode(raw.slice(0, 6));
    setErrorMsg('');
  };

  const handleSubmit = async (e) => {
    e?.preventDefault();
    const trimmed = code.trim();
    if (trimmed.length !== 6) {
      setErrorMsg('Please enter the full 6-character code shown on your display.');
      return;
    }

    setStatus('submitting');
    setErrorMsg('');

    try {
      const response = await api.claimPairCode(trimmed, name || undefined, location || undefined);
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

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
  };

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
