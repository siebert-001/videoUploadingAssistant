import random
from typing import Callable

from playwright.sync_api import Locator, Page, expect

from src.exceptions import AutomationCancelled, VideoSkipError
from src.field_settings import VideoFieldSettings
from src.form_filler import fill_video_form
from src.video_identity import PendingVideo, list_pending_videos, mark_video_skipped

LIST_READY_SELECTOR = "div.aspect-video.group, div.group.min-w-\\[320px\\]"
DIALOG_HEADER = "视频编辑"
SALE_BUTTON_TEXT = "上架销售"
DIALOG_SELECTOR = "section.dioa-dialog__content"


def is_edit_dialog_open(page: Page) -> bool:
    dialog = page.locator(DIALOG_SELECTOR)
    return dialog.count() > 0 and dialog.first.is_visible()


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
    """记录列表滚动位置；不锁死 overflow，避免测试暂停后无法手动滚动。"""
    page.evaluate("() => { window.__vjshiScrollY = window.scrollY; }")


def unfreeze_background_scroll(page: Page) -> None:
    ensure_page_scrollable(page)


def wait_for_upload_list(page: Page, *, timeout_ms: int) -> None:
    if page.get_by_text("您已退出登录", exact=False).count() > 0:
        raise RuntimeError("未登录或登录已过期，请在浏览器登录后点击「我已登录，继续」。")
    page.locator(LIST_READY_SELECTOR).first.wait_for(state="visible", timeout=timeout_ms)


def pending_sale_buttons(page: Page) -> Locator:
    return page.get_by_role("button", name=SALE_BUTTON_TEXT, exact=True)


def count_pending_videos(page: Page) -> int:
    return pending_sale_buttons(page).count()


def scroll_to_load_more(page: Page, *, max_rounds: int = 30) -> int:
    """向下滚动列表，尽量加载全部待处理项（仅在弹窗未打开时执行）。"""
    if is_edit_dialog_open(page):
        return count_pending_videos(page)
    prev = 0
    for _ in range(max_rounds):
        if is_edit_dialog_open(page):
            break
        buttons = pending_sale_buttons(page)
        count = buttons.count()
        if count == 0:
            break
        buttons.last.scroll_into_view_if_needed()
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
    buttons = pending_sale_buttons(page)
    btn = buttons.nth(index)
    btn.evaluate(
        "el => el.scrollIntoView({block: 'nearest', inline: 'nearest'})"
    )
    expect(btn).to_be_visible()
    btn.click()


def wait_for_edit_dialog(page: Page, *, timeout_ms: int) -> None:
    dialog = page.locator(DIALOG_SELECTOR)
    dialog.wait_for(state="visible", timeout=timeout_ms)
    expect(dialog.get_by_text(DIALOG_HEADER, exact=True)).to_be_visible(timeout=timeout_ms)
    freeze_background_scroll(page)


def close_edit_dialog_if_open(page: Page) -> None:
    if not is_edit_dialog_open(page):
        return
    close_btn = page.locator("button.dioa-dialog__close")
    if close_btn.count() > 0 and close_btn.first.is_visible():
        close_btn.first.click()
        page.locator(DIALOG_SELECTOR).wait_for(state="hidden", timeout=5000)
    unfreeze_background_scroll(page)


def submit_edit_dialog(page: Page, *, timeout_ms: int) -> None:
    """点击弹窗底部「提交」按钮。"""
    dialog = page.locator(DIALOG_SELECTOR)
    submit_btn = dialog.locator('button[type="submit"]').filter(has_text="提交")
    if submit_btn.count() == 0:
        submit_btn = dialog.get_by_role("button", name="提交", exact=True)
    if submit_btn.count() == 0:
        submit_btn = page.locator("button.dioa-button__root").filter(has_text="提交")
    if submit_btn.count() == 0:
        raise RuntimeError("未找到「提交」按钮。")
    submit_btn.first.scroll_into_view_if_needed()
    submit_btn.first.click(force=True)


def wait_for_edit_dialog_closed(page: Page, *, timeout_ms: int) -> None:
    page.locator(DIALOG_SELECTOR).wait_for(state="hidden", timeout=timeout_ms)
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
    """依次处理列表：填写 →（可选）提交 → 下一个，直到列表处理完或测试停止。"""
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
