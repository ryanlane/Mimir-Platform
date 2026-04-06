"""
Security utilities for Mimir API
Handles authentication, authorization, and security middleware
"""
import hashlib
import secrets
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("app.security")

# Initialize security scheme
security = HTTPBearer(auto_error=False)


def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage"""
    salt = settings.secret_key.encode()
    return hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000).hex()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash"""
    return hash_api_key(api_key) == hashed_key


async def get_current_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Extract and validate API key from Authorization header
    Returns None if no API key provided (for optional auth)
    """
    if not credentials:
        return None
    
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Use Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # TODO: Implement actual API key validation against database
    # For now, just return the token
    return credentials.credentials


async def require_api_key(
    api_key: Optional[str] = Depends(get_current_api_key)
) -> str:
    """
    Require a valid API key for the endpoint
    Raises HTTPException if no valid API key provided
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # TODO: Validate API key against database/store
    logger.info("API key authentication", extra={"api_key_prefix": api_key[:8] + "..."})
    return api_key


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded IP first (behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct connection
    if request.client:
        return request.client.host
    
    return "unknown"


def generate_request_id() -> str:
    """Generate a unique request ID for tracing"""
    timestamp = str(int(time.time() * 1000))
    random_part = secrets.token_hex(4)
    return f"req_{timestamp}_{random_part}"


class SecurityHeaders:
    """Security headers for API responses"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get standard security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }


def validate_file_path(file_path: str, allowed_root: str) -> bool:
    """
    Validate file path to prevent path traversal attacks
    Ensures the resolved path is within the allowed root directory
    """
    import os
    from pathlib import Path
    
    try:
        # Resolve paths to absolute paths
        allowed_root_abs = os.path.abspath(allowed_root)
        file_path_abs = os.path.abspath(os.path.join(allowed_root, file_path))
        
        # Check if file path is within allowed root
        return file_path_abs.startswith(allowed_root_abs)
    except (OSError, ValueError):
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent security issues"""
    import re
    
    # Remove path separators and dangerous characters
    filename = re.sub(r'[/\\:*?"<>|]', '', filename)
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip('. ')
    
    # Ensure filename is not empty and not a reserved name
    if not filename or filename.lower() in ['con', 'prn', 'aux', 'nul']:
        filename = 'file'
    
    return filename
