"""
Redis Connection Manager for Mimir Platform

This module provides Redis connectivity, health monitoring, and connection pooling
for the distributed content management system.
"""

import redis
import aioredis
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class RedisManager:
    """
    Manages Redis connections with health monitoring, connection pooling,
    and atomic operations support.
    """
    
    def __init__(self, 
                 host: str = None, 
                 port: int = None, 
                 db: int = 0,
                 password: str = None,
                 max_connections: int = 20):
        """
        Initialize Redis connection manager
        
        Args:
            host: Redis host (defaults to env REDIS_HOST or 'localhost')
            port: Redis port (defaults to env REDIS_PORT or 6379)
            db: Redis database number (defaults to 0)
            password: Redis password (defaults to env REDIS_PASSWORD)
            max_connections: Maximum connections in pool
        """
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.db = db
        self.password = password or os.getenv('REDIS_PASSWORD')
        self.max_connections = max_connections
        
        # Connection instances
        self.redis_client = None
        self.async_redis = None
        self.connection_pool = None
        
        # Health status
        self._is_connected = False
        self._last_health_check = None
        self._health_status = "unknown"
        
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize Redis connections with error handling"""
        try:
            # Create connection pool
            self.connection_pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                retry_on_timeout=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                health_check_interval=30
            )
            
            # Create synchronous client
            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            
            logger.info(f"Redis manager initialized for {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connections: {e}")
            self._health_status = "error"
    
    async def _initialize_async_connection(self):
        """Initialize async Redis connection lazily"""
        if self.async_redis is None:
            try:
                redis_url = f"redis://"
                if self.password:
                    redis_url += f":{self.password}@"
                redis_url += f"{self.host}:{self.port}/{self.db}"
                
                self.async_redis = aioredis.from_url(
                    redis_url,
                    max_connections=self.max_connections,
                    retry_on_timeout=True,
                    decode_responses=True
                )
                
                logger.info("Async Redis connection initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize async Redis connection: {e}")
                raise
    
    async def is_healthy(self) -> bool:
        """
        Check Redis connection health
        
        Returns:
            bool: True if Redis is healthy and responsive
        """
        try:
            if self.redis_client is None:
                return False
            
            # Sync ping test
            result = self.redis_client.ping()
            
            # Test async connection if available
            if self.async_redis:
                await self.async_redis.ping()
            
            self._is_connected = result
            self._last_health_check = datetime.now()
            self._health_status = "healthy" if result else "unhealthy"
            
            return result
            
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            self._is_connected = False
            self._health_status = "error"
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get detailed Redis health information
        
        Returns:
            Dict containing health status, metrics, and diagnostics
        """
        try:
            start_time = datetime.now()
            
            # Basic connectivity test
            is_healthy = await self.is_healthy()
            ping_duration = (datetime.now() - start_time).total_seconds() * 1000
            
            if not is_healthy:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Connection failed",
                    "ping_duration_ms": None,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Get Redis info
            info = self.redis_client.info()
            memory_info = self.redis_client.info('memory')
            clients_info = self.redis_client.info('clients')
            keyspace_info = self.redis_client.info('keyspace')
            
            # Calculate key count
            total_keys = 0
            if f'db{self.db}' in keyspace_info:
                total_keys = keyspace_info[f'db{self.db}'].get('keys', 0)
            
            return {
                "status": "healthy",
                "connected": True,
                "ping_duration_ms": round(ping_duration, 2),
                "redis_version": info.get('redis_version', 'unknown'),
                "uptime_seconds": info.get('uptime_in_seconds', 0),
                "memory": {
                    "used_memory_human": memory_info.get('used_memory_human', 'unknown'),
                    "used_memory_peak_human": memory_info.get('used_memory_peak_human', 'unknown'),
                    "memory_fragmentation_ratio": memory_info.get('mem_fragmentation_ratio', 0)
                },
                "clients": {
                    "connected_clients": clients_info.get('connected_clients', 0),
                    "max_clients": clients_info.get('maxclients', 0)
                },
                "database": {
                    "db_number": self.db,
                    "total_keys": total_keys
                },
                "connection": {
                    "host": self.host,
                    "port": self.port,
                    "pool_size": self.max_connections
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting Redis health status: {e}")
            return {
                "status": "error",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    @asynccontextmanager
    async def pipeline(self):
        """
        Redis pipeline for atomic operations
        
        Usage:
            async with redis_manager.pipeline() as pipe:
                pipe.set('key1', 'value1')
                pipe.set('key2', 'value2')
                await pipe.execute()
        """
        if not await self.is_healthy():
            raise ConnectionError("Redis is not available")
        
        pipe = self.redis_client.pipeline(transaction=True)
        try:
            yield pipe
        finally:
            pipe.reset()
    
    async def get_async_client(self):
        """
        Get async Redis client, initializing if necessary
        
        Returns:
            aioredis.Redis: Async Redis client
        """
        if self.async_redis is None:
            await self._initialize_async_connection()
        
        if not await self.is_healthy():
            raise ConnectionError("Redis is not available")
        
        return self.async_redis
    
    def get_sync_client(self):
        """
        Get synchronous Redis client
        
        Returns:
            redis.Redis: Sync Redis client
        """
        if not self._is_connected and not self.is_healthy():
            raise ConnectionError("Redis is not available")
        
        return self.redis_client
    
    async def set_with_ttl(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """
        Set a key with TTL using async client
        
        Args:
            key: Redis key
            value: Value to store (will be JSON encoded if not string)
            ttl_seconds: TTL in seconds
            
        Returns:
            bool: True if successful
        """
        try:
            client = await self.get_async_client()
            
            # JSON encode if not string
            if not isinstance(value, str):
                value = json.dumps(value)
            
            result = await client.setex(key, ttl_seconds, value)
            return result
            
        except Exception as e:
            logger.error(f"Error setting key {key} with TTL: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """
        Get and JSON decode a value
        
        Args:
            key: Redis key
            
        Returns:
            Decoded JSON value or None if not found
        """
        try:
            client = await self.get_async_client()
            value = await client.get(key)
            
            if value is None:
                return None
            
            # Try to JSON decode
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # Return as string if not valid JSON
                return value
                
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern
        
        Args:
            pattern: Redis key pattern (e.g., "lease:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            client = await self.get_async_client()
            keys = await client.keys(pattern)
            
            if not keys:
                return 0
            
            deleted_count = await client.delete(*keys)
            logger.info(f"Deleted {deleted_count} keys matching pattern: {pattern}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting pattern {pattern}: {e}")
            return 0
    
    async def get_keys_info(self, pattern: str = "*") -> Dict[str, Any]:
        """
        Get information about keys matching a pattern
        
        Args:
            pattern: Redis key pattern
            
        Returns:
            Dict with key information and statistics
        """
        try:
            client = await self.get_async_client()
            keys = await client.keys(pattern)
            
            key_info = {
                "pattern": pattern,
                "total_keys": len(keys),
                "keys": [],
                "by_prefix": {},
                "ttl_distribution": {}
            }
            
            # Analyze keys
            for key in keys[:100]:  # Limit to first 100 for performance
                key_type = await client.type(key)
                ttl = await client.ttl(key)
                
                key_data = {
                    "key": key,
                    "type": key_type,
                    "ttl": ttl
                }
                
                # Add size information based on type
                if key_type == "string":
                    key_data["size"] = await client.strlen(key)
                elif key_type == "list":
                    key_data["length"] = await client.llen(key)
                elif key_type == "hash":
                    key_data["fields"] = await client.hlen(key)
                elif key_type == "set":
                    key_data["members"] = await client.scard(key)
                
                key_info["keys"].append(key_data)
                
                # Group by prefix
                prefix = key.split(':')[0] if ':' in key else 'other'
                key_info["by_prefix"][prefix] = key_info["by_prefix"].get(prefix, 0) + 1
                
                # TTL distribution
                if ttl > 0:
                    ttl_bucket = f"{(ttl//60)*60}-{(ttl//60)*60+59}s"
                    key_info["ttl_distribution"][ttl_bucket] = key_info["ttl_distribution"].get(ttl_bucket, 0) + 1
                elif ttl == -1:
                    key_info["ttl_distribution"]["persistent"] = key_info["ttl_distribution"].get("persistent", 0) + 1
            
            return key_info
            
        except Exception as e:
            logger.error(f"Error getting keys info for pattern {pattern}: {e}")
            return {"error": str(e)}
    
    async def cleanup_expired_keys(self) -> Dict[str, int]:
        """
        Manually cleanup expired keys (Redis handles this automatically, 
        but this can be used for monitoring/debugging)
        
        Returns:
            Dict with cleanup statistics
        """
        try:
            stats = {
                "checked": 0,
                "expired": 0,
                "errors": 0
            }
            
            client = await self.get_async_client()
            
            # Check lease keys specifically
            lease_keys = await client.keys("lease:*")
            stats["checked"] = len(lease_keys)
            
            for key in lease_keys:
                try:
                    ttl = await client.ttl(key)
                    if ttl == -2:  # Key doesn't exist (expired)
                        stats["expired"] += 1
                except Exception:
                    stats["errors"] += 1
            
            logger.info(f"Redis cleanup check: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close Redis connections"""
        try:
            if self.async_redis:
                await self.async_redis.close()
                logger.info("Async Redis connection closed")
            
            if self.connection_pool:
                self.connection_pool.disconnect()
                logger.info("Redis connection pool closed")
                
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")


# Global Redis manager instance
redis_manager = None

def get_redis_manager() -> RedisManager:
    """
    Get global Redis manager instance
    
    Returns:
        RedisManager: Global Redis manager
    """
    global redis_manager
    if redis_manager is None:
        redis_manager = RedisManager()
    return redis_manager

async def init_redis() -> RedisManager:
    """
    Initialize Redis manager and test connection
    
    Returns:
        RedisManager: Initialized Redis manager
    """
    manager = get_redis_manager()
    
    # Test connection
    is_healthy = await manager.is_healthy()
    if is_healthy:
        logger.info("Redis initialized successfully")
    else:
        logger.warning("Redis initialization failed - fallback mode available")
    
    return manager
