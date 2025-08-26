"""
Middleware for Mimir API
Handles cross-cutting concerns like request logging, security headers, etc.
"""
import time
import uuid
from typing import Callable, Dict, Any
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.core.logging import get_logger, log_api_request
from app.core.security import SecurityHeaders, get_client_ip

logger = get_logger("app.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log API requests with timing and metadata"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Get client info
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log successful request
            log_api_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration for failed requests too
            duration_ms = (time.time() - start_time) * 1000
            
            # Log failed request
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "duration_ms": duration_ms,
                    "error": str(e),
                    "event_type": "request_error"
                }
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        security_headers = SecurityHeaders.get_security_headers()
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, Dict[str, Any]] = {}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.rate_limit_requests:
            # Rate limiting disabled
            return await call_next(request)
        
        client_ip = get_client_ip(request)
        current_time = time.time()
        
        # Clean old entries
        self._cleanup_old_entries(current_time)
        
        # Check rate limit
        if self._is_rate_limited(client_ip, current_time):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )
        
        # Record request
        self._record_request(client_ip, current_time)
        
        return await call_next(request)
    
    def _cleanup_old_entries(self, current_time: float) -> None:
        """Remove entries older than rate limit window"""
        cutoff_time = current_time - settings.rate_limit_window
        
        for client_ip in list(self.request_counts.keys()):
            client_data = self.request_counts[client_ip]
            client_data["requests"] = [
                req_time for req_time in client_data["requests"] 
                if req_time > cutoff_time
            ]
            
            # Remove client if no recent requests
            if not client_data["requests"]:
                del self.request_counts[client_ip]
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if client has exceeded rate limit"""
        if client_ip not in self.request_counts:
            return False
        
        client_data = self.request_counts[client_ip]
        cutoff_time = current_time - settings.rate_limit_window
        
        # Count recent requests
        recent_requests = [
            req_time for req_time in client_data["requests"]
            if req_time > cutoff_time
        ]
        
        return len(recent_requests) >= settings.rate_limit_requests
    
    def _record_request(self, client_ip: str, current_time: float) -> None:
        """Record a request for the client"""
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {"requests": []}
        
        self.request_counts[client_ip]["requests"].append(current_time)


class CORSMiddleware:
    """Custom CORS middleware configuration"""
    
    @staticmethod
    def get_cors_config() -> Dict[str, Any]:
        """Get CORS configuration from settings"""
        return {
            "allow_origins": settings.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
