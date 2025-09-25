import React, { useRef, useState, useEffect } from 'react';
import './PullToRefresh.css';

/**
 * PullToRefresh component
 * Wrap page content. On mobile (pointer: coarse) allows user to pull downward from top to trigger onRefresh.
 * Props:
 *  - onRefresh: async function or function returning promise
 *  - threshold (number): distance in px required to trigger refresh (default 70)
 *  - maxPull (number): maximum translation (default 140)
 *  - disabled (bool): disable interaction
 *  - className (string)
 */
const PullToRefresh = ({
  onRefresh,
  threshold = 70,
  maxPull = 140,
  disabled = false,
  className = '',
  children
}) => {
  const startYRef = useRef(null);
  const pullingRef = useRef(false);
  const containerRef = useRef(null);
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState('idle'); // idle | pulling | ready | refreshing
  const isTouchCapable = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;

  useEffect(() => {
    if (!isTouchCapable || disabled) return; // Only attach on touch devices
    const el = containerRef.current;
    if (!el) return;

    const onTouchStart = (e) => {
      if (window.scrollY > 0) return; // Only when at top of page
      if (pullingRef.current || state === 'refreshing') return;
      startYRef.current = e.touches ? e.touches[0].clientY : e.clientY;
      pullingRef.current = true;
      setState('idle');
    };

    const onTouchMove = (e) => {
      if (!pullingRef.current || startYRef.current == null) return;
      const currentY = e.touches ? e.touches[0].clientY : e.clientY;
      const delta = currentY - startYRef.current;
      if (delta <= 0) {
        setOffset(0);
        setState('idle');
        return;
      }
      const limited = Math.min(delta, maxPull);
      setOffset(limited);
      if (limited >= threshold) {
        setState('ready');
      } else {
        setState(limited > 0 ? 'pulling' : 'idle');
      }
    };

    const endPull = async () => {
      if (!pullingRef.current) return;
      const shouldRefresh = state === 'ready';
      pullingRef.current = false;
      startYRef.current = null;
      if (shouldRefresh && onRefresh) {
        setState('refreshing');
        try {
          await Promise.resolve(onRefresh());
        } catch (e) {
          console.warn('PullToRefresh refresh error', e);
        } finally {
          // Animate back after short delay to show spinner state
          setTimeout(() => {
            setOffset(0);
            setState('idle');
          }, 350);
        }
      } else {
        setOffset(0);
        setState('idle');
      }
    };

    const onTouchEnd = () => endPull();
    const onTouchCancel = () => endPull();

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: true });
    el.addEventListener('touchend', onTouchEnd);
    el.addEventListener('touchcancel', onTouchCancel);

    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
      el.removeEventListener('touchcancel', onTouchCancel);
    };
  }, [onRefresh, threshold, maxPull, disabled, state, isTouchCapable]);

  const indicatorText = {
    idle: 'Pull to refresh',
    pulling: 'Keep pulling…',
    ready: 'Release to refresh',
    refreshing: 'Refreshing…'
  }[state];

  return (
    <div className={`ptr-wrapper ${className}`} ref={containerRef}>
      <div
        className={`ptr-indicator state-${state}`}
        style={{ height: maxPull, transform: `translateY(${offset - maxPull}px)` }}
        aria-hidden={state === 'idle' ? 'true' : 'false'}
      >
        <div className="ptr-indicator-inner" role="status" aria-live="polite">
          <div className="ptr-spinner" />
          <span className="ptr-text">{indicatorText}</span>
        </div>
      </div>
      <div className="ptr-content" style={{ transform: `translateY(${offset}px)` }}>
        {children}
      </div>
    </div>
  );
};

export default PullToRefresh;
