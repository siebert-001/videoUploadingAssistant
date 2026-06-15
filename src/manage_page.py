"""卖家中心视频管理页（/seller/manage/video）列表与操作定位。"""
from __future__ import annotations

from playwright.sync_api import Page

MANAGE_VIDEO_URL = "https://www.vjshi.com/seller/manage/video"

# 打开编辑弹窗的操作文案（按优先级）
SALE_ACTION_TEXTS = ("上架销售", "去上架", "完善信息", "编辑上架")

# 待处理视频所在标签
PENDING_TAB_TEXTS = ("待上架", "待完善", "未上架", "待完善信息")

_LIST_READY_MARKERS = (
    "待上架",
    "上架销售",
    "去上架",
    "完善信息",
    "视频管理",
    "作品管理",
)

_DISCOVER_ACTIONS_SCRIPT = """
(args) => {
    const texts = args.texts || ['上架销售'];
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, [role="dialog"]');
    const isVisible = (el) => {
        if (!el || inDialog(el)) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return false;
        const r = el.getBoundingClientRect();
        return r.width > 8 && r.height > 8;
    };
    const rowFor = (el) => el.closest('tr')
        || el.closest('[class*="table-row"]')
        || el.closest('[class*="list-item"]')
        || el.closest('[class*="card"]')
        || el.closest('article')
        || el.closest('li')
        || el.closest('div.aspect-video.group')
        || el.closest('div.group.min-w-\\[320px\\]')
        || el.closest('[class*="aspect-video"]')
        || el.closest('div.group')
        || el.parentElement;

    const seen = new Set();
    const out = [];
    const nodes = document.querySelectorAll('button, a, [role="button"], span, div');
    for (const el of nodes) {
        if (!isVisible(el)) continue;
        const t = norm(el.textContent);
        if (!texts.includes(t)) continue;
        const row = rowFor(el);
        const rowText = norm(row?.innerText || '').slice(0, 120);
        const key = rowText || t + '@' + out.length;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ index: out.length, text: t, label: rowText.slice(0, 48) });
    }
    return out;
}
"""

_CLICK_ACTION_SCRIPT = """
(args) => {
    const { index, texts } = args;
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, [role="dialog"]');
    const isVisible = (el) => {
        if (!el || inDialog(el)) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 8 && r.height > 8;
    };
    const rowFor = (el) => el.closest('tr')
        || el.closest('[class*="table-row"]')
        || el.closest('[class*="list-item"]')
        || el.closest('[class*="card"]')
        || el.closest('article')
        || el.closest('li')
        || el.closest('div.aspect-video.group')
        || el.closest('div.group.min-w-\\[320px\\]')
        || el.closest('[class*="aspect-video"]')
        || el.closest('div.group')
        || el.parentElement;

    const seen = new Set();
    const targets = [];
    const nodes = document.querySelectorAll('button, a, [role="button"], span, div');
    for (const el of nodes) {
        if (!isVisible(el)) continue;
        const t = norm(el.textContent);
        if (!texts.includes(t)) continue;
        const row = rowFor(el);
        const rowText = norm(row?.innerText || '').slice(0, 120);
        const key = rowText || t + '@' + targets.length;
        if (seen.has(key)) continue;
        seen.add(key);
        targets.push(el);
    }
    const target = targets[index];
    if (!target) return false;
    target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    target.click();
    return true;
}
"""

_ENSURE_TAB_SCRIPT = """
(tabTexts) => {
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 4 && r.height > 4;
    };
    for (const text of tabTexts) {
        const nodes = document.querySelectorAll(
            'button, a, [role="tab"], li, span, div'
        );
        for (const el of nodes) {
            if (!isVisible(el)) continue;
            if (norm(el.textContent) !== text) continue;
            if (el.closest('section.dioa-dialog__content, [role="dialog"]')) continue;
            el.click();
            return text;
        }
    }
    return '';
}
"""

_LOAD_MORE_SCRIPT = """
() => {
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const labels = ['加载更多', '下一页', '查看更多'];
    for (const label of labels) {
        const nodes = document.querySelectorAll('button, a, [role="button"]');
        for (const el of nodes) {
            const t = norm(el.textContent);
            if (t !== label && !t.includes(label)) continue;
            const r = el.getBoundingClientRect();
            if (r.width < 4 || r.height < 4) continue;
            el.click();
            return label;
        }
    }
    return '';
}
"""


def ensure_manage_video_page(page: Page, *, timeout_ms: int = 30000) -> None:
    """确保位于卖家中心视频管理页。"""
    if "seller/manage/video" not in page.url:
        page.goto(MANAGE_VIDEO_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(800)


def ensure_pending_tab(page: Page) -> str:
    """若存在「待上架」等标签，优先切换。"""
    clicked = page.evaluate(_ENSURE_TAB_SCRIPT, list(PENDING_TAB_TEXTS))
    if clicked:
        page.wait_for_timeout(600)
    return str(clicked or "")


def discover_pending_actions(page: Page) -> list[dict]:
    raw = page.evaluate(
        _DISCOVER_ACTIONS_SCRIPT, {"texts": list(SALE_ACTION_TEXTS)}
    )
    return raw if isinstance(raw, list) else []


def count_pending_actions(page: Page) -> int:
    return len(discover_pending_actions(page))


def click_pending_action(page: Page, index: int) -> bool:
    return bool(
        page.evaluate(
            _CLICK_ACTION_SCRIPT,
            {"index": index, "texts": list(SALE_ACTION_TEXTS)},
        )
    )


def try_load_more(page: Page) -> bool:
    label = page.evaluate(_LOAD_MORE_SCRIPT)
    if label:
        page.wait_for_timeout(700)
        return True
    return False


def wait_for_manage_list(page: Page, *, timeout_ms: int) -> None:
    if page.get_by_text("您已退出登录", exact=False).count() > 0:
        raise RuntimeError("未登录或登录已过期，请在浏览器登录后点击「登录完成，继续上架」。")

    ensure_manage_video_page(page, timeout_ms=timeout_ms)
    ensure_pending_tab(page)

    elapsed = 0
    step = 400
    while elapsed < timeout_ms:
        if count_pending_actions(page) > 0:
            return
        for marker in _LIST_READY_MARKERS:
            if page.get_by_text(marker, exact=False).count() > 0:
                page.wait_for_timeout(300)
                if count_pending_actions(page) > 0:
                    return
        page.wait_for_timeout(step)
        elapsed += step

    raise RuntimeError(
        "未加载到视频管理列表。请确认已登录，且页面为卖家中心「视频管理」。"
    )
