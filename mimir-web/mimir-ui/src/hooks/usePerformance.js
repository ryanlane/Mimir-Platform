import React, { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Virtual Scrolling Hook for Large Lists
 * Provides efficient rendering for large image galleries
 */
export const useVirtualScrolling = ({
  items = [],
  itemHeight = 120,
  containerHeight = 600,
  overscan = 5,
  enabled = true
}) => {
  const [scrollTop, setScrollTop] = useState(0);
  const [isScrolling, setIsScrolling] = useState(false);
  const scrollElementRef = useRef(null);
  const scrollTimeoutRef = useRef(null);

  // Calculate visible range
  const startIndex = enabled 
    ? Math.floor(scrollTop / itemHeight)
    : 0;
  
  const endIndex = enabled 
    ? Math.min(
        startIndex + Math.ceil(containerHeight / itemHeight) + overscan,
        items.length - 1
      )
    : items.length - 1;

  const visibleStartIndex = Math.max(0, startIndex - overscan);
  const visibleEndIndex = Math.min(items.length - 1, endIndex + overscan);

  // Get visible items
  const visibleItems = enabled 
    ? items.slice(visibleStartIndex, visibleEndIndex + 1).map((item, index) => ({
        ...item,
        index: visibleStartIndex + index
      }))
    : items.map((item, index) => ({ ...item, index }));

  // Handle scroll events
  const handleScroll = useCallback((event) => {
    if (!enabled) return;
    
    const scrollTop = event.target.scrollTop;
    setScrollTop(scrollTop);
    setIsScrolling(true);

    // Clear existing timeout
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    // Set scroll end timeout
    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 150);
  }, [enabled]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  // Calculate styles for virtual container
  const getContainerStyle = () => {
    if (!enabled) {
      return {};
    }

    return {
      height: containerHeight,
      overflow: 'auto',
      position: 'relative'
    };
  };

  const getInnerStyle = () => {
    if (!enabled) {
      return {};
    }

    return {
      height: items.length * itemHeight,
      position: 'relative'
    };
  };

  const getItemStyle = (index) => {
    if (!enabled) {
      return {};
    }

    return {
      position: 'absolute',
      top: index * itemHeight,
      left: 0,
      right: 0,
      height: itemHeight
    };
  };

  return {
    visibleItems,
    startIndex: visibleStartIndex,
    endIndex: visibleEndIndex,
    isScrolling,
    scrollElementRef,
    handleScroll,
    getContainerStyle,
    getInnerStyle,
    getItemStyle,
    totalHeight: items.length * itemHeight
  };
};

/**
 * Lazy Loading Hook for Images
 * Provides intersection observer-based lazy loading
 */
export const useLazyLoading = ({
  threshold = 0.1,
  rootMargin = '50px',
  enabled = true
}) => {
  const [loadedImages, setLoadedImages] = useState(new Set());
  const [loadingImages, setLoadingImages] = useState(new Set());
  const [failedImages, setFailedImages] = useState(new Set());
  const observerRef = useRef(null);

  // Initialize intersection observer
  useEffect(() => {
    if (!enabled || !window.IntersectionObserver) {
      return;
    }

    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const img = entry.target;
            const src = img.dataset.src;
            
            if (src && !loadedImages.has(src) && !loadingImages.has(src)) {
              setLoadingImages(prev => new Set([...prev, src]));
              
              // Create actual image to load
              const imageLoader = new Image();
              imageLoader.onload = () => {
                img.src = src;
                img.classList.add('loaded');
                setLoadedImages(prev => new Set([...prev, src]));
                setLoadingImages(prev => {
                  const newSet = new Set(prev);
                  newSet.delete(src);
                  return newSet;
                });
                observerRef.current?.unobserve(img);
              };
              
              imageLoader.onerror = () => {
                img.classList.add('error');
                setFailedImages(prev => new Set([...prev, src]));
                setLoadingImages(prev => {
                  const newSet = new Set(prev);
                  newSet.delete(src);
                  return newSet;
                });
                observerRef.current?.unobserve(img);
              };
              
              imageLoader.src = src;
            }
          }
        });
      },
      {
        threshold,
        rootMargin
      }
    );

    return () => {
      observerRef.current?.disconnect();
    };
  }, [enabled, threshold, rootMargin, loadedImages, loadingImages]);

  // Register element for lazy loading
  const registerElement = useCallback((element) => {
    if (enabled && element && observerRef.current) {
      observerRef.current.observe(element);
    }
  }, [enabled]);

  // Unregister element
  const unregisterElement = useCallback((element) => {
    if (enabled && element && observerRef.current) {
      observerRef.current.unobserve(element);
    }
  }, [enabled]);

  return {
    loadedImages,
    loadingImages,
    failedImages,
    registerElement,
    unregisterElement,
    isLoading: (src) => loadingImages.has(src),
    isLoaded: (src) => loadedImages.has(src),
    hasFailed: (src) => failedImages.has(src)
  };
};

/**
 * Optimized Image Component with Lazy Loading
 */
export const LazyImage = ({
  src,
  alt,
  className = '',
  placeholder = null,
  errorFallback = null,
  onLoad = null,
  onError = null,
  ...props
}) => {
  const [isIntersecting, setIsIntersecting] = useState(false);
  const [loadState, setLoadState] = useState('pending'); // pending, loading, loaded, error
  const imgRef = useRef(null);
  const observerRef = useRef(null);

  useEffect(() => {
    const img = imgRef.current;
    if (!img || !window.IntersectionObserver) {
      setIsIntersecting(true);
      return;
    }

    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsIntersecting(true);
          observerRef.current?.disconnect();
        }
      },
      {
        threshold: 0.1,
        rootMargin: '50px'
      }
    );

    observerRef.current.observe(img);

    return () => {
      observerRef.current?.disconnect();
    };
  }, []);

  const handleLoad = useCallback(() => {
    setLoadState('loaded');
    onLoad?.();
  }, [onLoad]);

  const handleError = useCallback(() => {
    setLoadState('error');
    onError?.();
  }, [onError]);

  const handleLoadStart = useCallback(() => {
    setLoadState('loading');
  }, []);

  return (
    <div className={`lazy-image-container ${className}`} {...props}>
      {loadState === 'pending' && placeholder && (
        <div className="lazy-image-placeholder">
          {placeholder}
        </div>
      )}
      
      {loadState === 'loading' && (
        <div className="lazy-image-loading">
          <div className="loading-spinner"></div>
        </div>
      )}
      
      {loadState === 'error' && errorFallback && (
        <div className="lazy-image-error">
          {errorFallback}
        </div>
      )}
      
      <img
        ref={imgRef}
        src={isIntersecting ? src : undefined}
        alt={alt}
        className={`lazy-image ${loadState}`}
        onLoad={handleLoad}
        onError={handleError}
        onLoadStart={handleLoadStart}
        style={{
          opacity: loadState === 'loaded' ? 1 : 0,
          transition: 'opacity 0.3s ease'
        }}
      />
    </div>
  );
};

/**
 * Performance Monitoring Hook
 * Tracks component render performance
 */
export const usePerformanceMonitoring = (componentName) => {
  const renderCountRef = useRef(0);
  const startTimeRef = useRef(null);

  useEffect(() => {
    renderCountRef.current += 1;
    startTimeRef.current = performance.now();
    
    return () => {
      if (startTimeRef.current) {
        const renderTime = performance.now() - startTimeRef.current;
        console.log(`📊 ${componentName} render #${renderCountRef.current}: ${renderTime.toFixed(2)}ms`);
      }
    };
  });

  const measureOperation = useCallback((operationName, operation) => {
    const start = performance.now();
    const result = operation();
    const end = performance.now();
    console.log(`⏱️ ${componentName} - ${operationName}: ${(end - start).toFixed(2)}ms`);
    return result;
  }, [componentName]);

  return { measureOperation, renderCount: renderCountRef.current };
};

const performanceHooks = {
  useVirtualScrolling,
  useLazyLoading,
  LazyImage,
  usePerformanceMonitoring
};

export default performanceHooks;
