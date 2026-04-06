"""
Caching and Rate Limiting Service
Handles in-memory caching, rate limiting, and temporary data storage
"""
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta

from app.core.logging import get_logger


logger = get_logger(__name__)


class CacheService:
    """Service for caching and rate limiting functionality"""
    
    def __init__(self):
        # Rate limiting storage
        self.rate_limit_data: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.websocket_rate_limits: Dict[str, List[float]] = defaultdict(list)
        
        # General purpose cache with TTL support
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.cache_ttl: Dict[str, float] = {}
        
        # Performance metrics cache
        self.metrics_cache: Dict[str, Any] = {}
        self.metrics_last_updated: Optional[datetime] = None
        
        # Cleanup tracking
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
    
    def check_rate_limit(self, identifier: str, max_requests: int = 60, 
                        window_seconds: int = 60) -> Dict[str, Any]:
        """Check if request is within rate limit"""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Get or create rate limit data for this identifier
        if identifier not in self.rate_limit_data:
            self.rate_limit_data[identifier] = {
                'requests': [],
                'first_request': current_time,
                'blocked_until': None
            }
        
        limit_data = self.rate_limit_data[identifier]
        
        # Check if currently blocked
        if limit_data.get('blocked_until') and current_time < limit_data['blocked_until']:
            return {
                'allowed': False,
                'reason': 'rate_limited',
                'retry_after': limit_data['blocked_until'] - current_time,
                'requests_remaining': 0
            }
        
        # Clean old requests outside the window
        limit_data['requests'] = [
            req_time for req_time in limit_data['requests'] 
            if req_time > window_start
        ]
        
        # Check if within limits
        if len(limit_data['requests']) >= max_requests:
            # Block for the remainder of the window
            limit_data['blocked_until'] = current_time + window_seconds
            logger.warning(f"Rate limit exceeded for {identifier}: {len(limit_data['requests'])}/{max_requests}")
            
            return {
                'allowed': False,
                'reason': 'rate_limited',
                'retry_after': window_seconds,
                'requests_remaining': 0
            }
        
        # Add current request
        limit_data['requests'].append(current_time)
        requests_remaining = max_requests - len(limit_data['requests'])
        
        return {
            'allowed': True,
            'requests_remaining': requests_remaining,
            'window_reset': window_start + window_seconds
        }
    
    def check_websocket_rate_limit(self, client_id: str, max_messages: int = 10,
                                 window_seconds: int = 60) -> bool:
        """Check WebSocket message rate limit"""
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Clean old messages
        self.websocket_rate_limits[client_id] = [
            msg_time for msg_time in self.websocket_rate_limits[client_id]
            if msg_time > window_start
        ]
        
        # Check limit
        if len(self.websocket_rate_limits[client_id]) >= max_messages:
            logger.warning(f"WebSocket rate limit exceeded for {client_id}")
            return False
        
        # Add current message
        self.websocket_rate_limits[client_id].append(current_time)
        return True
    
    def set_cache(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set cache value with optional TTL"""
        current_time = time.time()
        
        self.cache[key] = {
            'value': value,
            'created_at': current_time,
            'accessed_at': current_time
        }
        
        if ttl_seconds:
            self.cache_ttl[key] = current_time + ttl_seconds
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        
        # Cleanup if needed
        self._maybe_cleanup_cache()
    
    def get_cache(self, key: str) -> Optional[Any]:
        """Get cache value if not expired"""
        if key not in self.cache:
            return None
        
        current_time = time.time()
        
        # Check TTL expiration
        if key in self.cache_ttl and current_time > self.cache_ttl[key]:
            self._remove_cache_key(key)
            return None
        
        # Update access time and move to end
        self.cache[key]['accessed_at'] = current_time
        self.cache.move_to_end(key)
        
        return self.cache[key]['value']
    
    def delete_cache(self, key: str) -> bool:
        """Delete cache entry"""
        return self._remove_cache_key(key)
    
    def _remove_cache_key(self, key: str) -> bool:
        """Remove cache key and its TTL"""
        removed = False
        if key in self.cache:
            del self.cache[key]
            removed = True
        if key in self.cache_ttl:
            del self.cache_ttl[key]
        return removed
    
    def cache_websocket_status(self, status_data: Dict[str, Any], ttl_seconds: int = 5):
        """Cache WebSocket status with short TTL"""
        self.set_cache("websocket_status", status_data, ttl_seconds)
    
    def get_websocket_status(self) -> Optional[Dict[str, Any]]:
        """Get cached WebSocket status"""
        return self.get_cache("websocket_status")
    
    def cache_performance_metrics(self, metrics: Dict[str, Any], ttl_seconds: int = 30):
        """Cache performance metrics"""
        self.metrics_cache = metrics
        self.metrics_last_updated = datetime.now()
        self.set_cache("performance_metrics", metrics, ttl_seconds)
    
    def get_performance_metrics(self) -> Optional[Dict[str, Any]]:
        """Get cached performance metrics"""
        cached = self.get_cache("performance_metrics")
        if cached:
            return {
                **cached,
                'last_updated': self.metrics_last_updated.isoformat() if self.metrics_last_updated else None
            }
        return None
    
    def _maybe_cleanup_cache(self):
        """Cleanup expired cache entries and rate limit data"""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        self.last_cleanup = current_time
        logger.debug("Starting cache cleanup")
        
        # Cleanup expired cache entries
        expired_keys = []
        for key, ttl_time in self.cache_ttl.items():
            if current_time > ttl_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_cache_key(key)
        
        # Cleanup old rate limit data (older than 1 hour)
        cleanup_threshold = current_time - 3600
        expired_identifiers = []
        
        for identifier, data in self.rate_limit_data.items():
            if (data.get('first_request', current_time) < cleanup_threshold and
                not data.get('requests')):
                expired_identifiers.append(identifier)
        
        for identifier in expired_identifiers:
            del self.rate_limit_data[identifier]
        
        # Cleanup WebSocket rate limits (older than 1 hour)
        for client_id in list(self.websocket_rate_limits.keys()):
            if not self.websocket_rate_limits[client_id]:
                del self.websocket_rate_limits[client_id]
            else:
                # Remove old messages
                self.websocket_rate_limits[client_id] = [
                    msg_time for msg_time in self.websocket_rate_limits[client_id]
                    if msg_time > cleanup_threshold
                ]
                
                if not self.websocket_rate_limits[client_id]:
                    del self.websocket_rate_limits[client_id]
        
        if expired_keys or expired_identifiers:
            logger.debug(f"Cache cleanup complete: {len(expired_keys)} cache entries, "
                        f"{len(expired_identifiers)} rate limit entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        
        # Calculate cache statistics
        total_entries = len(self.cache)
        entries_with_ttl = len(self.cache_ttl)
        expired_entries = sum(
            1 for ttl_time in self.cache_ttl.values()
            if current_time > ttl_time
        )
        
        # Rate limiting statistics
        active_rate_limits = len(self.rate_limit_data)
        blocked_clients = sum(
            1 for data in self.rate_limit_data.values()
            if data.get('blocked_until') and current_time < data['blocked_until']
        )
        
        # WebSocket rate limiting
        active_ws_limits = len(self.websocket_rate_limits)
        
        return {
            'cache': {
                'total_entries': total_entries,
                'entries_with_ttl': entries_with_ttl,
                'expired_entries': expired_entries,
                'last_cleanup': self.last_cleanup
            },
            'rate_limiting': {
                'active_limits': active_rate_limits,
                'blocked_clients': blocked_clients,
                'websocket_limits': active_ws_limits
            },
            'performance': {
                'metrics_cached': 'performance_metrics' in self.cache,
                'websocket_status_cached': 'websocket_status' in self.cache,
                'last_metrics_update': self.metrics_last_updated.isoformat() if self.metrics_last_updated else None
            }
        }
    
    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries, optionally matching a pattern"""
        if pattern:
            keys_to_remove = [key for key in self.cache.keys() if pattern in key]
            for key in keys_to_remove:
                self._remove_cache_key(key)
            logger.info(f"Cleared {len(keys_to_remove)} cache entries matching '{pattern}'")
        else:
            self.cache.clear()
            self.cache_ttl.clear()
            logger.info("Cleared all cache entries")
    
    def clear_rate_limits(self, identifier: Optional[str] = None):
        """Clear rate limit data"""
        if identifier:
            if identifier in self.rate_limit_data:
                del self.rate_limit_data[identifier]
                logger.info(f"Cleared rate limit for {identifier}")
        else:
            self.rate_limit_data.clear()
            self.websocket_rate_limits.clear()
            logger.info("Cleared all rate limit data")


# Global service instance
cache_service = CacheService()
