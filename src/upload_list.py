import random
from typing import Callable

from playwright.sync_api import Page

from src.exceptions import AutomationCancelled, VideoSkipError
from src.field_settings import VideoFieldSettings
from src.form_filler import fill_video_form
from src.upload_page import (
    PendingVideo,
    click_sale_action_at,
    count_pending_videos,
    edit_dialog,
    ensure_pending_tab,
    is_edit_dialog_open,
    list_pending_videos,
    mark_video_skipped,
    refresh_edit_dialog_marker,
    scroll_last_sale_into_view,
    wait_for_edit_dialog,
    wait_for_dialog_form_ready,
    wait_for_upload_list_ready,
)


def ensure_page_scrollable(page: Page) -> None:
    """解除页面滚动锁定（弹窗打开时曾可能遗留 overflow:hidden）。"""
    page.evaluate(
        """() => {
            document.documentElement.style.overflow = '';
            document.body.style.overflow = '';
            document.documentElement.style.position = '';
            document.body.style.position = '';
            document.body.style.top = '';
            document.body.style.width = '';
            document.body.classList.remove('overflow-hidden');
        }"""
    )


def freeze_background_scroll(page: Page) -> None:
    page.evaluate("() => { window.__vjshiScrollY = window.scrollY; }")


def unfreeze_background_scroll(page: Page) -> None:
    ensure_page_scrollable(page)


def wait_for_upload_list(page: Page, *, timeout_ms: int) -> None:
    wait_for_upload_list_ready(page, timeout_ms=timeout_ms)


def scroll_to_load_more(page: Page, *, max_rounds: int = 30) -> int:
    if is_edit_dialog_open(page):
        return count_pending_videos(page)
    ensure_pending_tab(page)
    prev = 0
    for _ in range(max_rounds):
        if is_edit_dialog_open(page):
            break
        count = count_pending_videos(page)
        if count == 0:
            break
        scroll_last_sale_into_view(page)
        page.wait_for_timeout(600)
        if count == prev and count == count_pending_videos(page):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(600)
            if count_pending_videos(page) == count:
                break
        prev = count_pending_videos(page)
    return count_pending_videos(page)


def open_edit_dialog_for_index(page: Page, index: int = 0) -> None:
    if is_edit_dialog_open(page):
        return
    url_before = page.url
    for attempt in range(2):
        click_sale_action_at(page, index)
        for _ in range(8):
            page.wait_for_timeout(500)
            if is_edit_dialog_open(page):
                refresh_edit_dialog_marker(page)
                return
            if page.url != url_before:
                return
        if attempt == 0:
            page.wait_for_timeout(600)


def close_edit_dialog_if_open(page: Page) -> None:
    if not is_edit_dialog_open(page):
        return
    dlg = edit_dialog(page)
    for sel in (
        "button.dioa-dialog__close",
        "[class*='dialog__close']",
    ):
        close_btn = dlg.locator(sel)
        if close_btn.count() > 0 and close_btn.first.is_visible():
            close_btn.first.click()
            break
    else:
        page.keyboard.press("Escape")
    edit_dialog(page).wait_for(state="hidden", timeout=5000)
    unfreeze_background_scroll(page)


def submit_edit_dialog(page: Page, *, timeout_ms: int) -> None:
    dlg = edit_dialog(page)
    for loc in (
        dlg.locator('button[type="submit"]').filter(has_text="提交"),
        dlg.get_by_role("button", name="提交", exact=True),
        dlg.locator("button.dioa-button__root").filter(has_text="提交"),
    ):
        if loc.count() > 0:
            loc.first.scroll_into_view_if_needed()
            loc.first.click(force=True)
            return
    raise RuntimeError("未找到「提交」按钮。")


def wait_for_edit_dialog_closed(page: Page, *, timeout_ms: int) -> None:
    edit_dialog(page).wait_for(state="hidden", timeout=timeout_ms)
    unfreeze_background_scroll(page)
    page.wait_for_timeout(400)


def process_all_pending(
    page: Page,
    *,
    field_settings: VideoFieldSettings,
    timeout_ms: int,
    delay_ms: int,
    on_progress: Callable[[int, int], None] | None = None,
    on_log: Callable[[str], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    submit_enabled: bool = True,
    test_stop_after_submit: int = 0,
    pause_between_videos_sec: tuple[float, float] = (3.0, 6.0),
) -> int:
    def cancelled() -> bool:
        return bool(is_cancelled and is_cancelled())

    total = scroll_to_load_more(page)
    if total == 0:
        return 0

    submitted = 0
    skipped = 0
    failed = False
    step = 0
    skipped_keys: set[str] = set()

    def next_video() -> PendingVideo | None:
        for entry in list_pending_videos(page):
            if entry.key and entry.key not in skipped_keys:
                return entry
        return None

    while count_pending_videos(page) > 0:
        if cancelled():
            raise AutomationCancelled()

        target = next_video()
        if target is None:
            remaining = count_pending_videos(page)
            if on_log and remaining > 0:
                on_log(
                    f"剩余 {remaining} 个待上架视频均已标注跳过，结束本轮"
                    f"（成功提交 {submitted} 个，跳过 {skipped} 个）"
                )
            break

        step += 1
        if on_progress:
            on_progress(step, total)

        try:
            open_edit_dialog_for_index(page, index=target.index)
            page.wait_for_timeout(delay_ms)
            wait_for_edit_dialog(page, timeout_ms=timeout_ms)
            wait_for_dialog_form_ready(page, timeout_ms=timeout_ms)
            freeze_background_scroll(page)

            if on_log:
                on_log(f"填写第 {step} 个视频信息")
            fill_video_form(page, field_settings)
            page.wait_for_timeout(delay_ms)

            if not submit_enabled:
                ensure_page_scrollable(page)
                break

            if test_stop_after_submit > 0 and submitted >= test_stop_after_submit:
                ensure_page_scrollable(page)
                break

            submit_edit_dialog(page, timeout_ms=timeout_ms)
            wait_for_edit_dialog_closed(page, timeout_ms=timeout_ms)
            submitted += 1
            if on_log:
                on_log(f"第 {step} 个视频信息已提交")
            page.wait_for_timeout(delay_ms)

            if count_pending_videos(page) > 0:
                lo, hi = pause_between_videos_sec
                rest_sec = random.uniform(lo, hi)
                page.wait_for_timeout(int(rest_sec * 1000))
        except VideoSkipError as e:
            skipped += 1
            skipped_keys.add(target.key)
            close_edit_dialog_if_open(page)
            ensure_page_scrollable(page)
            marked = mark_video_skipped(page, target.key, str(e))
            label = target.label or target.key
            if on_log:
                mark_note = "，列表已标注" if marked else ""
                on_log(f"第 {step} 个视频已跳过: {e}（{label}{mark_note}）")
            page.wait_for_timeout(delay_ms)
            continue
        except AutomationCancelled:
            raise
        except Exception as e:
            failed = True
            close_edit_dialog_if_open(page)
            ensure_page_scrollable(page)
            if on_log:
                on_log(f"第 {step} 个视频处理失败: {e}")
            break

    ensure_page_scrollable(page)
    if on_log:
        if failed:
            on_log(f"已中断，成功提交 {submitted} 个，跳过 {skipped} 个")
        elif submitted:
            suffix = f"，跳过 {skipped} 个" if skipped else ""
            on_log(f"列表已无待上架视频，共提交 {submitted} 个{suffix}")
        elif skipped:
            on_log(f"未提交任何视频，已跳过 {skipped} 个（无 AI 推荐）")
        elif step > 0:
            on_log("未成功提交任何视频")

    return submitted if submit_enabled else step
