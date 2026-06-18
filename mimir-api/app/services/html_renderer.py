"""Shared HTML-to-image rendering service.

Maintains a single headless Chromium browser process for the lifetime of the
server.  All plugins render through this one instance — no per-plugin browser
overhead.

Usage from any plugin (async context):

    from app.services.html_renderer import html_renderer_service

    png_bytes = await html_renderer_service.render(html_string, width=800, height=480)

The service degrades gracefully: if Playwright is not installed or Chromium is
not available, ``render()`` raises ``HtmlRendererUnavailableError`` and the
caller can fall back to its own PIL renderer.

Lifecycle is managed by the server lifespan (app/main.py):

    await html_renderer_service.start()
    ...
    await html_renderer_service.stop()
"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

logger = logging.getLogger("mimir.services.html_renderer")

WaitUntil = Literal["load", "domcontentloaded", "networkidle", "commit"]


class HtmlRendererUnavailableError(RuntimeError):
    """Raised when Playwright / Chromium is not available."""


class HtmlRendererService:
    """Singleton service wrapping a persistent Playwright Chromium browser."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()
        self._available: bool | None = None  # None = not yet checked

    # ------------------------------------------------------------------
    # Lifecycle

    async def start(self) -> None:
        """Launch the browser.  Called once at server startup."""
        try:
            from playwright.async_api import async_playwright  # type: ignore[import]
        except ImportError:
            logger.warning(
                "[html-renderer] playwright not installed — HTML rendering unavailable. "
                "Run: pip install playwright && playwright install chromium"
            )
            self._available = False
            return

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",   # avoids /dev/shm exhaustion in Docker
                    "--disable-gpu",
                    "--font-render-hinting=none", # crisper text at display resolutions
                ],
            )
            self._available = True
            logger.info("[html-renderer] Chromium browser started (shared across all plugins)")
        except Exception as exc:
            self._available = False
            logger.warning("[html-renderer] Chromium launch failed — HTML rendering unavailable: %s", exc)

    async def stop(self) -> None:
        """Close the browser and Playwright.  Called at server shutdown."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._available = False
        logger.info("[html-renderer] Chromium browser stopped")

    # ------------------------------------------------------------------
    # Public API

    @property
    def available(self) -> bool:
        """True if Playwright is installed and Chromium launched successfully."""
        return self._available is True and self._browser is not None

    async def render(
        self,
        html: str,
        width: int = 800,
        height: int = 480,
        wait_until: WaitUntil = "domcontentloaded",
        device_scale_factor: float = 1.0,
        jpeg_quality: int = 92,
    ) -> bytes:
        """Render *html* at the given viewport size and return JPEG bytes.

        Parameters
        ----------
        html:
            Complete HTML document string (inline CSS/JS, no external network
            requests needed).
        width / height:
            Viewport dimensions in CSS pixels.
        wait_until:
            Playwright page-load event to wait for before screenshotting.
            ``"domcontentloaded"`` is fastest for self-contained HTML; use
            ``"networkidle"`` if the template loads external resources.
        device_scale_factor:
            Set >1 for HiDPI screenshots (e.g. 2.0 doubles resolution).
        jpeg_quality:
            JPEG compression quality (1-100).

        Raises
        ------
        HtmlRendererUnavailableError
            If Playwright is not installed or Chromium is not running.
        """
        if not self.available:
            raise HtmlRendererUnavailableError(
                "HTML renderer is not available — Playwright/Chromium not installed or failed to start"
            )

        # Serialise page creation so we don't open hundreds of tabs under load
        async with self._lock:
            page = await self._browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=device_scale_factor,
            )

        try:
            await page.set_content(html, wait_until=wait_until)
            png_bytes = await page.screenshot(
                type="jpeg",
                quality=jpeg_quality,
                clip={"x": 0, "y": 0, "width": width, "height": height},
            )
            return png_bytes
        finally:
            await page.close()

    async def render_url(
        self,
        url: str,
        width: int = 800,
        height: int = 480,
        wait_until: WaitUntil = "networkidle",
        jpeg_quality: int = 92,
    ) -> bytes:
        """Render a URL instead of an HTML string.  Useful for local dev servers."""
        if not self.available:
            raise HtmlRendererUnavailableError("HTML renderer unavailable")

        async with self._lock:
            page = await self._browser.new_page(
                viewport={"width": width, "height": height},
            )

        try:
            await page.goto(url, wait_until=wait_until)
            return await page.screenshot(
                type="jpeg",
                quality=jpeg_quality,
                clip={"x": 0, "y": 0, "width": width, "height": height},
            )
        finally:
            await page.close()


# Global singleton — import this in plugins and services
html_renderer_service = HtmlRendererService()
