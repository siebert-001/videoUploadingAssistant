"""自动化执行器，供 GUI 在后台线程调用。"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable, Literal

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from src.auth import ensure_logged_in, open_browser_context
from src.config import init_app, load_settings, setup_playwright_env
from src.exceptions import AutomationCancelled
from src.field_settings import VideoFieldSettings
from src.upload_list import (
    count_pending_videos,
    ensure_page_scrollable,
    process_all_pending,
    wait_for_upload_list,
)

LogFn = Callable[[str], None]
LoginWaitFn = Callable[[], None]
NotifyFn = Callable[[], None]
FinishReason = Literal["user_stop", "browser_closed", "completed"]
OnFinishedFn = Callable[[FinishReason], None]


@dataclass
class RunnerCallbacks:
    on_log: LogFn
    wait_login_confirm: LoginWaitFn
    is_cancelled: Callable[[], bool]
    on_automation_finished: OnFinishedFn
    on_listing_started: NotifyFn


class AutomationRunner:
    def __init__(
        self,
        callbacks: RunnerCallbacks,
        *,
        field_settings: VideoFieldSettings,
    ) -> None:
        self._cb = callbacks
        self._field_settings = field_settings
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._intentional_close = False
        self._finish_notified = False
        self._completed_successfully = False
        self._browser_ready = False
        self._external_browser_close = False
        self._browser_gone = threading.Event()
        self._shutting_down = False
        self._browser_pid: int | None = None
        self._keep_browser_for_debug = False

    @property
    def intentional_close(self) -> bool:
        return self._intentional_close

    @property
    def browser_pid(self) -> int | None:
        return self._browser_pid

    def browser_was_closed(self) -> bool:
        """线程安全：供 GUI 主线程读取，不触碰 Playwright 对象。"""
        return self._browser_gone.is_set()

    @staticmethod
    def browser_process_alive(pid: int | None) -> bool:
        """主线程检测 Chromium 进程是否仍在（不访问 Playwright）。"""
        if pid is None:
            return True
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    def _mark_browser_gone(self) -> None:
        self._external_browser_close = True
        self._browser_gone.set()

    def note_browser_closed(self) -> None:
        """供 GUI 主线程在检测到进程退出时标记。"""
        self._mark_browser_gone()

    def _handlers_active(self) -> bool:
        return (
            self._browser_ready
            and not self._intentional_close
            and not self._shutting_down
        )

    def _open_pages(self) -> list:
        if self._context is None:
            return []
        try:
            return [p for p in self._context.pages if not p.is_closed()]
        except PlaywrightError:
            return []
        except Exception:
            return []

    def _adopt_active_page(self) -> bool:
        """登录跳转/新开标签时切换到仍打开的页面。"""
        pages = self._open_pages()
        if not pages:
            return False
        if self._page is None or self._page.is_closed():
            self._page = pages[-1]
            self._page.on("close", lambda _: self._on_page_closed())
        return True

    def user_closed_browser(self) -> bool:
        """检测用户是否手动关闭浏览器（仅在工作线程调用）。"""
        if not self._handlers_active():
            return False
        if self._browser_gone.is_set():
            return True
        if self._browser is None:
            return True
        try:
            if not self._browser.is_connected():
                return True
        except PlaywrightError:
            return True
        except Exception:
            return True
        if self._open_pages():
            self._adopt_active_page()
            return False
        return True

    def _capture_browser_pid(self) -> None:
        self._browser_pid = None
        if self._browser is None:
            return
        try:
            impl = self._browser._impl_obj  # type: ignore[attr-defined]
            self._browser_pid = impl._browser_process.process.pid
        except Exception:
            pass

    def pump_wait(self, ms: int) -> bool:
        """工作线程内等待并驱动 Playwright 事件；返回 True 表示应停止自动化。"""
        if self._browser_gone.is_set():
            return True
        if not self._handlers_active():
            return self._browser_gone.is_set()
        if not self._adopt_active_page():
            self._notify_manual_browser_closed()
            return True
        try:
            self._page.wait_for_timeout(ms)
        except PlaywrightError:
            if not self._adopt_active_page():
                self._mark_browser_gone()
                self._notify_manual_browser_closed()
                return True
        if self.user_closed_browser():
            self._notify_manual_browser_closed()
            return True
        return False

    def _finish(self, reason: FinishReason) -> None:
        if self._finish_notified:
            return
        self._finish_notified = True
        self._cb.on_automation_finished(reason)

    def _notify_manual_browser_closed(self) -> None:
        if self._intentional_close:
            return
        self._mark_browser_gone()
        if self._finish_notified:
            return
        self._finish("browser_closed")

    def _should_stop(self) -> bool:
        if self._cb.is_cancelled():
            return True
        if self.user_closed_browser():
            self._notify_manual_browser_closed()
            return True
        return False

    def _attach_browser_listeners(self) -> None:
        if self._browser:
            self._browser.on("disconnected", lambda _: self._notify_manual_browser_closed())
        if self._context:
            self._context.on("close", lambda _: self._on_context_closed())
            self._context.on("page", lambda p: self._on_new_page(p))

    def _on_context_closed(self) -> None:
        if self._handlers_active() and self.user_closed_browser():
            self._notify_manual_browser_closed()

    def _on_new_page(self, page) -> None:
        if not self._handlers_active():
            return
        self._page = page
        page.on("close", lambda _: self._on_page_closed())

    def _on_page_closed(self) -> None:
        if not self._handlers_active():
            return
        if self._adopt_active_page():
            return
        if self.user_closed_browser():
            self._notify_manual_browser_closed()

    def _check_cancel(self) -> None:
        if self._should_stop():
            raise AutomationCancelled()

    def _log(self, msg: str) -> None:
        self._cb.on_log(msg)

    def run(self) -> None:
        init_app()
        setup_playwright_env()
        settings = load_settings()
        url = settings["site"]["upload_list_url"]
        timeout = settings["browser"]["timeout_ms"]
        delay = settings["actions"]["delay_between_clicks_ms"]
        actions_cfg = settings["actions"]
        submit_enabled = bool(actions_cfg.get("submit_enabled", True))
        test_stop = int(actions_cfg.get("test_stop_after_submit", 0))
        pause_min = float(actions_cfg.get("pause_between_videos_sec_min", 3))
        pause_max = float(actions_cfg.get("pause_between_videos_sec_max", 6))
        if pause_max < pause_min:
            pause_min, pause_max = pause_max, pause_min

        self._keep_browser_for_debug = False
        channel = settings.get("browser", {}).get("channel", "")
        if channel == "chrome":
            self._log("正在启动本机 Google Chrome…")
        elif channel:
            self._log(f"正在启动浏览器（{channel}）…")
        else:
            self._log("正在启动浏览器…")
        self._check_cancel()

        self._playwright = sync_playwright().start()
        try:
            self._context = open_browser_context(self._playwright, settings=settings)
            self._browser = self._context.browser
            self._attach_browser_listeners()
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = self._context.new_page()
            self._page.on("close", lambda _: self._on_page_closed())
            self._browser_ready = True
            self._capture_browser_pid()

            self._check_cancel()
            ensure_logged_in(
                self._page,
                upload_list_url=url,
                on_log=self._log,
                wait_login_confirm=self._cb.wait_login_confirm,
                is_cancelled=self._should_stop,
                navigation_timeout_ms=timeout,
            )
            self._adopt_active_page()
            self._check_cancel()
            self._cb.on_listing_started()

            self._log("正在加载视频列表…")
            wait_for_upload_list(self._page, timeout_ms=timeout)

            n = count_pending_videos(self._page)
            self._log(f"待处理视频: {n} 个")
            if n == 0:
                self._log("列表中没有可点击的「上架销售」按钮（浏览器保持打开）。")
                self._keep_browser_for_debug = True
            else:
                self._check_cancel()
                done = process_all_pending(
                    self._page,
                    field_settings=self._field_settings,
                    timeout_ms=timeout,
                    delay_ms=delay,
                    on_log=self._log,
                    is_cancelled=self._should_stop,
                    submit_enabled=submit_enabled,
                    test_stop_after_submit=test_stop,
                    pause_between_videos_sec=(pause_min, pause_max),
                )
                if done > 0:
                    self._completed_successfully = True
                if done == 0:
                    self._keep_browser_for_debug = True

        except AutomationCancelled:
            raise
        except PlaywrightError:
            if not self._intentional_close:
                self._mark_browser_gone()
                self._notify_manual_browser_closed()
            raise AutomationCancelled() from None
        except Exception as e:
            self._log(f"运行出错（浏览器保持打开便于测试）: {e}")
            self._keep_browser_for_debug = True
        finally:
            if self._keep_browser_for_debug and self._page:
                try:
                    if not self._page.is_closed():
                        ensure_page_scrollable(self._page)
                except Exception:
                    pass
            if not self._keep_browser_for_debug:
                self._close_browser()
            if not self._finish_notified:
                if self._completed_successfully:
                    self._finish("completed")
                elif self._intentional_close:
                    self._finish("user_stop")
                elif self._external_browser_close or self._cb.is_cancelled():
                    self._finish("browser_closed")

    def mark_user_stop(self) -> None:
        """用户点击停止：避免重复回调，且不误判为手动关浏览器。"""
        self._intentional_close = True
        self._finish_notified = True

    def close_browser(self) -> None:
        self._intentional_close = True
        self._close_browser()

    def _close_browser(self) -> None:
        self._shutting_down = True
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._page = None
        self._browser_ready = False
        self._browser_pid = None
