import React, { Component, useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, Wifi, WifiOff, CheckCircle, XCircle, Info } from 'lucide-react';
import './ErrorHandling.css';

/**
 * Error Boundary Component
 * Catches JavaScript errors in component tree
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null, 
      errorInfo: null,
      retryCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('🚨 Error Boundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
      retryCount: this.state.retryCount + 1
    });

    // Report error to monitoring service
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({ 
      hasError: false, 
      error: null, 
      errorInfo: null 
    });
  };

  render() {
    if (this.state.hasError) {
      // Custom error UI
      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <AlertTriangle className="error-icon" size={48} />
            <h2>Something went wrong</h2>
            <p className="error-message">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            
            {this.props.showDetails && (
              <details className="error-details">
                <summary>Error Details</summary>
                <pre className="error-stack">
                  {this.state.error?.stack}
                </pre>
                <pre className="error-info">
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <div className="error-actions">
              <button 
                className="retry-button"
                onClick={this.handleRetry}
                disabled={this.state.retryCount >= 3}
              >
                <RefreshCw size={16} />
                {this.state.retryCount >= 3 ? 'Max Retries Reached' : 'Try Again'}
              </button>
              
              {this.props.fallbackComponent && (
                <button 
                  className="fallback-button"
                  onClick={() => this.setState({ showFallback: true })}
                >
                  Use Fallback
                </button>
              )}
            </div>

            {this.state.showFallback && this.props.fallbackComponent}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Network Status Monitor
 * Tracks online/offline status and connection quality
 */
export const NetworkStatus = ({ onStatusChange = null }) => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [connectionQuality, setConnectionQuality] = useState('good');
  const [lastCheck, setLastCheck] = useState(Date.now());

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setConnectionQuality('good');
      if (onStatusChange) onStatusChange(true, 'good');
    };

    const handleOffline = () => {
      setIsOnline(false);
      setConnectionQuality('offline');
      if (onStatusChange) onStatusChange(false, 'offline');
    };

    // Check connection quality periodically
    const checkConnectionQuality = async () => {
      if (!isOnline) return;

      try {
        const start = performance.now();
        await fetch('/api/health', { 
          method: 'HEAD',
          cache: 'no-cache'
        });
        const end = performance.now();
        const responseTime = end - start;

        let quality = 'good';
        if (responseTime > 2000) {
          quality = 'poor';
        } else if (responseTime > 1000) {
          quality = 'slow';
        }

        setConnectionQuality(quality);
        setLastCheck(Date.now());
        
        if (onStatusChange) onStatusChange(true, quality);
      } catch (error) {
        setConnectionQuality('poor');
        if (onStatusChange) onStatusChange(true, 'poor');
      }
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Check connection quality every 30 seconds
    const qualityInterval = setInterval(checkConnectionQuality, 30000);
    
    // Initial check
    checkConnectionQuality();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(qualityInterval);
    };
  }, [isOnline, onStatusChange]);

  return (
    <div className={`network-status ${isOnline ? 'online' : 'offline'} ${connectionQuality}`}>
      {isOnline ? (
        <Wifi size={16} className="network-icon" />
      ) : (
        <WifiOff size={16} className="network-icon" />
      )}
      <span className="network-text">
        {isOnline ? (
          <>
            Online
            {connectionQuality === 'slow' && ' (Slow)'}
            {connectionQuality === 'poor' && ' (Poor)'}
          </>
        ) : (
          'Offline'
        )}
      </span>
      <span className="last-check">
        Last: {new Date(lastCheck).toLocaleTimeString()}
      </span>
    </div>
  );
};

/**
 * Toast Notification System
 * Provides user feedback for operations
 */
export const useToast = () => {
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random();
    const toast = { id, message, type, duration };
    
    setToasts(prev => [...prev, toast]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }

    return id;
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  const success = (message, duration) => addToast(message, 'success', duration);
  const error = (message, duration = 6000) => addToast(message, 'error', duration);
  const warning = (message, duration) => addToast(message, 'warning', duration);
  const info = (message, duration) => addToast(message, 'info', duration);

  return {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    warning,
    info
  };
};

/**
 * Toast Container Component
 */
export const ToastContainer = ({ toasts, removeToast }) => {
  if (!toasts.length) return null;

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <Toast 
          key={toast.id} 
          toast={toast} 
          onRemove={() => removeToast(toast.id)} 
        />
      ))}
    </div>
  );
};

/**
 * Individual Toast Component
 */
export const Toast = ({ toast, onRemove }) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Trigger enter animation
    const timer = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  const handleRemove = () => {
    setIsVisible(false);
    setTimeout(onRemove, 300); // Wait for exit animation
  };

  const getIcon = () => {
    switch (toast.type) {
      case 'success': return <CheckCircle size={16} />;
      case 'error': return <XCircle size={16} />;
      case 'warning': return <AlertTriangle size={16} />;
      default: return <Info size={16} />;
    }
  };

  return (
    <div 
      className={`toast toast-${toast.type} ${isVisible ? 'visible' : ''}`}
      onClick={handleRemove}
    >
      <div className="toast-icon">
        {getIcon()}
      </div>
      <div className="toast-content">
        <div className="toast-message">{toast.message}</div>
      </div>
      <button className="toast-close" onClick={handleRemove}>
        ×
      </button>
    </div>
  );
};

/**
 * Retry Hook
 * Provides retry logic for failed operations
 */
export const useRetry = (operation, maxRetries = 3, delay = 1000) => {
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [lastError, setLastError] = useState(null);

  const executeWithRetry = async (...args) => {
    let attempt = 0;
    setIsRetrying(true);
    setLastError(null);

    while (attempt <= maxRetries) {
      try {
        const result = await operation(...args);
        setIsRetrying(false);
        setRetryCount(0);
        return result;
      } catch (error) {
        attempt++;
        setRetryCount(attempt);
        setLastError(error);

        if (attempt <= maxRetries) {
          // Exponential backoff
          const backoffDelay = delay * Math.pow(2, attempt - 1);
          await new Promise(resolve => setTimeout(resolve, backoffDelay));
        } else {
          setIsRetrying(false);
          throw error;
        }
      }
    }
  };

  const reset = () => {
    setRetryCount(0);
    setLastError(null);
    setIsRetrying(false);
  };

  return {
    executeWithRetry,
    isRetrying,
    retryCount,
    lastError,
    reset,
    canRetry: retryCount < maxRetries
  };
};

/**
 * Loading States Component
 * Provides consistent loading UI
 */
export const LoadingState = ({ 
  type = 'spinner', 
  message = 'Loading...', 
  size = 'medium',
  overlay = false 
}) => {
  const getSpinner = () => {
    switch (type) {
      case 'dots':
        return (
          <div className="loading-dots">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        );
      case 'bars':
        return (
          <div className="loading-bars">
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
          </div>
        );
      default:
        return <div className="loading-spinner"></div>;
    }
  };

  const content = (
    <div className={`loading-state ${size}`}>
      {getSpinner()}
      {message && <div className="loading-message">{message}</div>}
    </div>
  );

  if (overlay) {
    return (
      <div className="loading-overlay">
        {content}
      </div>
    );
  }

  return content;
};

/**
 * Graceful Degradation Hook
 * Provides fallback behavior when features fail
 */
export const useGracefulDegradation = (features = []) => {
  const [availableFeatures, setAvailableFeatures] = useState(new Set());
  const [checkedFeatures, setCheckedFeatures] = useState(new Set());

  const checkFeature = async (featureName, testFunction) => {
    if (checkedFeatures.has(featureName)) {
      return availableFeatures.has(featureName);
    }

    try {
      const isAvailable = await testFunction();
      if (isAvailable) {
        setAvailableFeatures(prev => new Set([...prev, featureName]));
      }
      setCheckedFeatures(prev => new Set([...prev, featureName]));
      return isAvailable;
    } catch (error) {
      console.warn(`Feature ${featureName} is not available:`, error);
      setCheckedFeatures(prev => new Set([...prev, featureName]));
      return false;
    }
  };

  const isFeatureAvailable = (featureName) => {
    return availableFeatures.has(featureName);
  };

  const withFallback = (featureName, primaryComponent, fallbackComponent) => {
    if (isFeatureAvailable(featureName)) {
      return primaryComponent;
    }
    return fallbackComponent;
  };

  return {
    checkFeature,
    isFeatureAvailable,
    withFallback,
    availableFeatures: Array.from(availableFeatures)
  };
};

const errorHandling = {
  ErrorBoundary,
  NetworkStatus,
  useToast,
  ToastContainer,
  Toast,
  useRetry,
  LoadingState,
  useGracefulDegradation
};

export default errorHandling;
