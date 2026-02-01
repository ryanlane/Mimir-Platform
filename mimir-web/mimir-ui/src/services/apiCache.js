/**
 * API Cache Service
 * Provides caching for API responses to improve performance
 */

class ApiCache {
  constructor() {
    this.cache = new Map();
    this.timeouts = new Map();
    this.defaultTTL = 5 * 60 * 1000; // 5 minutes default TTL
  }

  /**
   * Generate cache key from API endpoint and params
   */
  generateKey(endpoint, params = {}) {
    const paramString = Object.keys(params)
      .sort()
      .map(key => `${key}=${params[key]}`)
      .join('&');
    return paramString ? `${endpoint}?${paramString}` : endpoint;
  }

  /**
   * Set cache entry with TTL
   */
  set(key, data, ttl = this.defaultTTL) {
    // Clear existing timeout if exists
    if (this.timeouts.has(key)) {
      clearTimeout(this.timeouts.get(key));
    }

    // Store the data
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    });

    // Set expiration timeout
    const timeout = setTimeout(() => {
      this.delete(key);
    }, ttl);

    this.timeouts.set(key, timeout);
  }

  /**
   * Get cache entry if valid
   */
  get(key) {
    const entry = this.cache.get(key);
    if (!entry) return null;

    const now = Date.now();
    if (now - entry.timestamp > entry.ttl) {
      this.delete(key);
      return null;
    }

    return entry.data;
  }

  /**
   * Delete cache entry
   */
  delete(key) {
    if (this.timeouts.has(key)) {
      clearTimeout(this.timeouts.get(key));
      this.timeouts.delete(key);
    }
    this.cache.delete(key);
  }

  /**
   * Clear all cache entries
   */
  clear() {
    // Clear all timeouts
    for (const timeout of this.timeouts.values()) {
      clearTimeout(timeout);
    }
    this.timeouts.clear();
    this.cache.clear();
  }

  /**
   * Invalidate cache entries by pattern
   */
  invalidatePattern(pattern) {
    const regex = new RegExp(pattern);
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.delete(key);
      }
    }
  }

  /**
   * Get cache stats
   */
  getStats() {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys()),
      memoryUsage: this.getMemoryUsage()
    };
  }

  /**
   * Estimate memory usage (rough calculation)
   */
  getMemoryUsage() {
    let size = 0;
    for (const [key, entry] of this.cache.entries()) {
      size += key.length * 2; // Approximate string size
      size += JSON.stringify(entry.data).length * 2; // Approximate data size
    }
    return size;
  }
}

// Cache configurations for different types of data
export const CACHE_CONFIGS = {
  // Sub-channel config rarely changes
  SUB_CHANNEL_CONFIG: {
    ttl: 10 * 60 * 1000, // 10 minutes
    pattern: '/channels/*/subchannels/config'
  },
  
  // Sub-channel lists change when galleries are modified
  SUB_CHANNELS: {
    ttl: 5 * 60 * 1000, // 5 minutes
    pattern: '/channels/*/subchannels'
  },
  
  // Sub-channel details change when modified
  SUB_CHANNEL_DETAILS: {
    ttl: 3 * 60 * 1000, // 3 minutes
    pattern: '/channels/*/subchannels/*'
  },
  
  // Channel list rarely changes
  CHANNELS: {
    ttl: 10 * 60 * 1000, // 10 minutes
    pattern: '/channels'
  },
  
  // Display status changes frequently
  DISPLAY_STATUS: {
    ttl: 30 * 1000, // 30 seconds
    pattern: '/displays/status'
  },
  
  // Content lists change when files are added/removed
  CONTENT: {
    ttl: 2 * 60 * 1000, // 2 minutes
    pattern: '/channels/*/content'
  }
};

// Create global cache instance
export const apiCache = new ApiCache();

/**
 * Cache decorator for API methods
 */
export function withCache(cacheConfig) {
  return function(target, propertyKey, descriptor) {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function(...args) {
      // Generate cache key
      const endpoint = this.getEndpoint ? this.getEndpoint(...args) : propertyKey;
      const key = apiCache.generateKey(endpoint, args[args.length - 1]);
      
      // Try to get from cache first
      const cached = apiCache.get(key);
      if (cached) {
        console.log(`📋 Cache hit: ${key}`);
        return Promise.resolve(cached);
      }
      
      // Call original method
      try {
        const result = await originalMethod.apply(this, args);
        
        // Cache the result
        apiCache.set(key, result, cacheConfig.ttl);
        console.log(`💾 Cached: ${key}`);
        
        return result;
      } catch (error) {
        console.error(`❌ Cache miss error: ${key}`, error);
        throw error;
      }
    };
    
    return descriptor;
  };
}

/**
 * Invalidate cache when data is modified
 */
export function invalidateCache(patterns) {
  if (Array.isArray(patterns)) {
    patterns.forEach(pattern => apiCache.invalidatePattern(pattern));
  } else {
    apiCache.invalidatePattern(patterns);
  }
}

export default apiCache;
