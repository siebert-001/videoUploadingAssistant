"""Playwright evaluate 重试（页面跳转/弹窗重渲染时上下文会短暂失效）。"""
from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page

_CONTEXT_LOST_MARKERS = (
    "Execution context was destroyed",
    "navigation",
    "Target closed",
    "Frame was detached",
)


def _is_context_lost(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker.lower() in msg for marker in _CONTEXT_LOST_MARKERS)


def stable_evaluate(
    page: Page,
    script: str,
    arg=None,
    *,
    retries: int = 5,
    base_wait_ms: int = 400,
) -> object:
    last: BaseException | None = None
    for attempt in range(retries):
        try:
            if arg is None:
                return page.evaluate(script)
            return page.evaluate(script, arg)
        except PlaywrightError as exc:
            last = exc
            if not _is_context_lost(exc):
                raise
            page.wait_for_timeout(base_wait_ms + attempt * 300)
    if last is not None:
        raise last
    raise RuntimeError("page.evaluate failed without exception")


def stable_locator_evaluate(
    locator: Locator,
    script: str,
    arg=None,
    *,
    retries: int = 5,
    base_wait_ms: int = 400,
) -> object:
    last: BaseException | None = None
    page = locator.page
    for attempt in range(retries):
        try:
            if arg is None:
                return locator.evaluate(script)
            return locator.evaluate(script, arg)
        except PlaywrightError as exc:
            last = exc
            if not _is_context_lost(exc):
                raise
            page.wait_for_timeout(base_wait_ms + attempt * 300)
    if last is not None:
        raise last
    raise RuntimeError("locator.evaluate failed without exception")


def wait_page_settled(page: Page, *, timeout_ms: int = 8000) -> None:
    """弹窗/局部刷新后等待页面稳定，减少 evaluate 中途上下文失效。"""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except PlaywrightError:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
    except PlaywrightError:
        pass
    page.wait_for_timeout(500)
