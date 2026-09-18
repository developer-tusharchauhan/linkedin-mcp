"""LinkedIn MCP - browser session management via Patchright.

One persistent Chromium profile is reused across calls so the user only logs
in once. All tool calls are serialized through a process-wide lock because a
persistent context directory can only be held by one browser at a time.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, TypeVar

from patchright.sync_api import Page, Playwright, sync_playwright

PROFILE_DIR = Path.home() / ".linkedin-mcp" / "profile"

_single_browser_lock = threading.Lock()

T = TypeVar("T")


class BrowserError(RuntimeError):
    pass


class BrowserSession:
    """Owns one Patchright browser launch for the duration of a `with` block.

    The persistent context always points at PROFILE_DIR, so cookies,
    local storage and the logged-in state survive across calls.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._pw: Playwright | None = None
        self._context = None
        self._page: Page | None = None

    def __enter__(self) -> "BrowserSession":
        _single_browser_lock.acquire()
        try:
            self._pw = sync_playwright().start()
            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=self.headless,
                viewport={"width": 1280, "height": 900},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            self._context.set_default_timeout(self.timeout_ms)
            self._page = self._context.new_page()
            return self
        except Exception:
            self._lock_release()
            raise

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserError("browser session not active")
        return self._page

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
            if self._pw is not None:
                try:
                    self._pw.stop()
                except Exception:
                    pass
        finally:
            self._lock_release()
        return False

    def _lock_release(self) -> None:
        try:
            if _single_browser_lock.locked():
                _single_browser_lock.release()
        except RuntimeError:
            pass


def in_browser(headless: bool = True, timeout_ms: int = 30000) -> Callable[[Callable[..., T]], T]:
    """Context-manager decorator helper: run a function inside a BrowserSession.

    The wrapped function receives the session and must use `session.page`.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            with BrowserSession(headless=headless, timeout_ms=timeout_ms) as session:
                return fn(session, *args, **kwargs)

        return wrapper

    return decorator