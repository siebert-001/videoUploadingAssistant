from pathlib import Path
from typing import Callable

from playwright.sync_api import Browser, BrowserContext, Error as PlaywrightError, Page, Playwright

from src.browser_stealth import apply_stealth, stealth_launch_kwargs
from src.config import login_file_path, resolve_path

LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]
LoginWaitFn = Callable[[], None]


def storage_state_exists(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def open_browser_context(playwright: Playwright, *, settings: dict) -> BrowserContext:
    """启动本机 Chrome，若有 login.json 则自动带上登录态。"""
    browser_cfg = settings["browser"]
    login_path = login_file_path()
    if settings["auth"].get("login_file"):
        login_path = resolve_path(settings["auth"]["login_file"])

    launch_kwargs: dict = {
        "headless": browser_cfg.get("headless", False),
        "slow_mo": browser_cfg.get("slow_mo", 0),
    }
    channel = browser_cfg.get("channel")
    if channel:
        launch_kwargs["channel"] = channel

    for key, value in stealth_launch_kwargs(browser_cfg).items():
        if key == "args":
            launch_kwargs.setdefault("args", [])
            launch_kwargs["args"].extend(value)
        else:
            launch_kwargs[key] = value

    no_viewport = bool(browser_cfg.get("no_viewport", True))
    context_kwargs: dict = {
        "locale": "zh-CN",
        "no_viewport": no_viewport,
    }
    viewport = browser_cfg.get("viewport")
    if viewport and not no_viewport:
        context_kwargs["viewport"] = viewport
        context_kwargs.pop("no_viewport", None)

    if storage_state_exists(login_path):
        context_kwargs["storage_state"] = str(login_path)

    try:
        browser: Browser = playwright.chromium.launch(**launch_kwargs)
        context = browser.new_context(**context_kwargs)
        apply_stealth(context, browser_cfg=browser_cfg)
        return context
    except PlaywrightError as e:
        if channel == "chrome":
            raise RuntimeError(
                "未找到本机 Google Chrome。请先安装 Chrome 浏览器后再运行。"
            ) from e
        if channel == "msedge":
            raise RuntimeError(
                "未找到本机 Microsoft Edge。请先安装 Edge 浏览器后再运行。"
            ) from e
        raise


def save_login_state(context: BrowserContext, path: Path | None = None) -> None:
    """保存登录信息到单个 JSON 文件。"""
    target = path or login_file_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(target), indexed_db=True)


def ensure_logged_in(
    page: Page,
    *,
    upload_list_url: str,
    storage_path: Path,
    settings: dict,
    on_log: LogFn | None = None,
    wait_login_confirm: LoginWaitFn | None = None,
    is_cancelled: CancelFn | None = None,
    navigation_timeout_ms: int = 30000,
) -> None:
    """首次登录后写入 login.json；之后启动自动加载。"""
    _log = on_log or print

    _goto(page, upload_list_url, timeout_ms=navigation_timeout_ms, is_cancelled=is_cancelled)
    _sleep(page, 800, is_cancelled=is_cancelled)

    if _is_logged_out(page):
        if storage_state_exists(storage_path):
            _log("本地登录已过期，请在浏览器中重新登录。")
        else:
            _log("请在浏览器中完成登录（微信扫码等）。")
        _wait_for_manual_login(
            page,
            upload_list_url=upload_list_url,
            on_log=_log,
            wait_login_confirm=wait_login_confirm,
            is_cancelled=is_cancelled,
            navigation_timeout_ms=navigation_timeout_ms,
        )
        page = _resolve_page(page)
        save_login_state(page.context, storage_path)
        _log(f"已保存登录信息: {storage_path.name}")
    else:
        if storage_state_exists(storage_path):
            _log("已使用本地登录信息。")
        else:
            _log("已登录。")
        save_login_state(_resolve_page(page).context, storage_path)


def _resolve_page(page: Page) -> Page:
    open_pages = [p for p in page.context.pages if not p.is_closed()]
    if not open_pages:
        from src.exceptions import AutomationCancelled

        raise AutomationCancelled()
    return open_pages[-1]


def _is_logged_out(page: Page) -> bool:
    page = _resolve_page(page)
    return page.get_by_text("您已退出登录", exact=False).count() > 0


def _goto(
    page: Page,
    url: str,
    *,
    timeout_ms: int,
    is_cancelled: CancelFn | None,
) -> None:
    if is_cancelled and is_cancelled():
        from src.exceptions import AutomationCancelled

        raise AutomationCancelled()
    page = _resolve_page(page)
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)


def _sleep(page: Page, ms: int, *, is_cancelled: CancelFn | None) -> None:
    elapsed = 0
    step = 200
    while elapsed < ms:
        if is_cancelled and is_cancelled():
            from src.exceptions import AutomationCancelled

            raise AutomationCancelled()
        _resolve_page(page).wait_for_timeout(min(step, ms - elapsed))
        elapsed += step


def _wait_until_logged_in(
    page: Page,
    *,
    on_log: LogFn,
    is_cancelled: CancelFn | None,
    max_wait_ms: int = 60000,
) -> None:
    on_log("正在确认登录状态…")
    elapsed = 0
    step = 500
    while elapsed < max_wait_ms:
        if is_cancelled and is_cancelled():
            from src.exceptions import AutomationCancelled

            raise AutomationCancelled()
        if not _is_logged_out(page):
            on_log("已确认登录。")
            return
        _resolve_page(page).wait_for_timeout(step)
        elapsed += step
    raise RuntimeError("仍未检测到登录，请在浏览器完成登录后再次点击「登录完成，继续上架」。")


def _wait_for_manual_login(
    page: Page,
    *,
    upload_list_url: str,
    on_log: LogFn,
    wait_login_confirm: LoginWaitFn | None,
    is_cancelled: CancelFn | None,
    navigation_timeout_ms: int = 30000,
) -> None:
    on_log("请在浏览器中完成登录（微信扫码等）。")
    _goto(page, upload_list_url, timeout_ms=navigation_timeout_ms, is_cancelled=is_cancelled)

    if wait_login_confirm is not None:
        wait_login_confirm()
        if is_cancelled and is_cancelled():
            from src.exceptions import AutomationCancelled

            raise AutomationCancelled()
        page = _resolve_page(page)
        _goto(page, upload_list_url, timeout_ms=navigation_timeout_ms, is_cancelled=is_cancelled)
        _sleep(page, 500, is_cancelled=is_cancelled)
        _wait_until_logged_in(
            page,
            on_log=on_log,
            is_cancelled=is_cancelled,
        )
        return

    while _is_logged_out(page):
        page.wait_for_timeout(1000)

    on_log("已检测到登录成功。按 Enter 保存登录态…")
    input()
