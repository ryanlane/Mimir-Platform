"""
Common schemas used across the API
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
