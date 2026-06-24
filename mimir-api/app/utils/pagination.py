# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Pagination utilities for Mimir API
Provides pagination helpers for list endpoints
"""
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("app.utils.pagination")

T = TypeVar('T')


def _to_camel_case(field_name: str) -> str:
    """Convert snake_case field names to camelCase for frontend compatibility."""
    return ''.join(
        word.capitalize() if i > 0 else word
        for i, word in enumerate(field_name.split('_'))
    )


class PaginationMeta(BaseModel):
    """Pagination metadata for API responses"""

    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

    class Config:
        alias_generator = _to_camel_case


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper"""

    data: list[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")

    class Config:
        alias_generator = _to_camel_case


def create_pagination_meta(
    page: int,
    size: int,
    total: int
) -> PaginationMeta:
    """
    Create pagination metadata

    Args:
        page: Current page number (1-based)
        size: Number of items per page
        total: Total number of items

    Returns:
        PaginationMeta object with calculated values
    """
    if size <= 0:
        size = 1

    pages = (total + size - 1) // size  # Ceiling division
    has_next = page < pages
    has_prev = page > 1

    return PaginationMeta(
        page=page,
        size=size,
        total=total,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


def paginate_list(
    items: list[T],
    page: int,
    size: int
) -> PaginatedResponse[T]:
    """
    Paginate a list of items

    Args:
        items: List of items to paginate
        page: Current page number (1-based)
        size: Number of items per page

    Returns:
        PaginatedResponse with paginated data and metadata
    """
    total = len(items)
    start_idx = (page - 1) * size
    end_idx = start_idx + size

    paginated_items = items[start_idx:end_idx]
    pagination_meta = create_pagination_meta(page, size, total)

    return PaginatedResponse(
        data=paginated_items,
        pagination=pagination_meta
    )


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(20, ge=1, le=100, description="Number of items per page")
) -> dict[str, int]:
    """
    FastAPI dependency to get pagination parameters

    Args:
        page: Page number from query parameter
        size: Page size from query parameter

    Returns:
        Dictionary with page, size, and offset values
    """
    offset = (page - 1) * size

    return {
        "page": page,
        "size": size,
        "offset": offset,
        "limit": size
    }


def create_paginated_response(
    items: list[T],
    page: int,
    size: int,
    total: int | None = None
) -> PaginatedResponse[T]:
    """
    Create a paginated response from items and parameters

    Args:
        items: List of items for current page
        page: Current page number
        size: Page size
        total: Total number of items (if None, uses len(items))

    Returns:
        PaginatedResponse with data and metadata
    """
    if total is None:
        total = len(items)

    pagination_meta = create_pagination_meta(page, size, total)

    return PaginatedResponse(
        data=items,
        pagination=pagination_meta
    )


class SQLPaginator:
    """Helper for paginating SQLAlchemy queries"""

    @staticmethod
    def paginate_query(query, page: int, size: int):
        """
        Paginate a SQLAlchemy query

        Args:
            query: SQLAlchemy query object
            page: Page number (1-based)
            size: Page size

        Returns:
            Tuple of (items, total_count)
        """
        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * size
        items = query.offset(offset).limit(size).all()

        return items, total

    @staticmethod
    def create_response(query, page: int, size: int) -> dict[str, Any]:
        """
        Create paginated response from SQLAlchemy query

        Args:
            query: SQLAlchemy query object
            page: Page number
            size: Page size

        Returns:
            Dictionary with paginated data and metadata
        """
        items, total = SQLPaginator.paginate_query(query, page, size)
        pagination_meta = create_pagination_meta(page, size, total)

        return {
            "data": items,
            "pagination": pagination_meta.dict()
        }
