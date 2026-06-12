"""
Common schemas used across the API
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    total: int
    limit: int
    offset: int

    @property
    def has_next(self) -> bool:
        return (self.offset + self.limit) < self.total

    @property
    def has_previous(self) -> bool:
        return self.offset > 0

    @property
    def page(self) -> int:
        return (self.offset // self.limit) + 1

    @property
    def pages(self) -> int:
        return (self.total + self.limit - 1) // self.limit


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields"""
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    class Config:
        populate_by_name = True


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    message: str
    details: dict[str, Any] | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: dict[str, Any] | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str  # "healthy", "degraded", "unhealthy"
    checks: dict[str, dict[str, Any]]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    uptime_seconds: float | None = None


class ApiResponse(BaseModel):
    """Generic API response wrapper"""
    success: bool
    data: Any | None = None
    error: str | None = None
    message: str | None = None
    meta: dict[str, Any] | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    data: list[Any]
    meta: PaginationMeta
    total: int

    @classmethod
    def create(cls, data: list[Any], total: int, limit: int, offset: int):
        """Create paginated response"""
        return cls(
            data=data,
            meta=PaginationMeta(total=total, limit=limit, offset=offset),
            total=total
        )


class FilterParams(BaseModel):
    """Common filter parameters"""
    search: str | None = None
    sort_by: str | None = Field(None, alias="sortBy")
    sort_order: str | None = Field("asc", alias="sortOrder")

    class Config:
        populate_by_name = True


class PaginationParams(BaseModel):
    """Common pagination parameters"""
    limit: int = Field(default=20, ge=1, le=100, description="Number of items per page")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")

    class Config:
        populate_by_name = True


class BulkOperation(BaseModel):
    """Bulk operation request"""
    operation: str  # "create", "update", "delete"
    items: list[dict[str, Any]]
    options: dict[str, Any] | None = None


class BulkOperationResult(BaseModel):
    """Bulk operation result"""
    operation: str
    total_items: int
    successful_items: int
    failed_items: int
    errors: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
