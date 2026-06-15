"""待上架列表页 DOM 定位（适配 /user/upload/video 新版布局）。"""
from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from src.page_eval import stable_evaluate, wait_page_settled

UPLOAD_LIST_PATH = "/user/upload/video"
SALE_BUTTON_TEXTS = ("上架销售", "去上架", "完善信息", "编辑上架", "上架", "填写信息")

# 列表页与弹窗（勿用 [role=dialog]，会误匹配隐藏的 popover）
DIALOG_SECTION_SELECTOR = "section.dioa-dialog__content"
DIALOG_HEADERS = ("视频编辑", "完善信息", "编辑视频", "视频信息", "上架信息")
DIALOG_HEADER = DIALOG_HEADERS[0]
DIALOG_FORM_MARKERS = ("AI推荐标题", "作品风格", "创作时间")
LIST_READY_HINTS = ("上架销售", "待上架", "上传视频", "视频编辑", "完善信息", "去上架")

_LIST_SCRIPT = """
(args) => {
    const { saleTexts } = args;
    const texts = saleTexts && saleTexts.length ? saleTexts : ['上架销售'];
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 2 && r.height > 2;
    };
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, section[class*="dioa-dialog"]');
    const isSaleAction = (el) => {
        const t = norm(el.innerText || el.textContent);
        return texts.some((x) => t === x || t.startsWith(x));
    };
    const saleActions = () => {
        const out = [];
        const seen = new Set();
        for (const el of document.querySelectorAll(
            'button, a, [role="button"], span[class*="button"], div[class*="button"], div[class*="btn"], span[class*="btn"]'
        )) {
            if (inDialog(el) || !isVisible(el) || !isSaleAction(el)) continue;
            if (seen.has(el)) continue;
            seen.add(el);
            out.push(el);
        }
        return out;
    };
    const cardForAction = (el) => {
        let node = el;
        for (let i = 0; i < 14 && node; i++) {
            const tag = (node.tagName || '').toUpperCase();
            const hasThumb = !!node.querySelector?.('img, video, [class*="aspect"], [class*="cover"]');
            const cls = (node.className || '').toString();
            if (hasThumb && (tag === 'DIV' || tag === 'LI' || tag === 'TR' || tag === 'ARTICLE')) return node;
            if (/card|item|row|video|group|aspect/i.test(cls) && hasThumb) return node;
            node = node.parentElement;
        }
        return el.closest('tr, li, article, div.group, div[class*="group"]') || el.parentElement;
    };
    const keyForAction = (el, index) => {
        const card = cardForAction(el);
        const link = card?.querySelector('a[href]');
        const href = (link?.getAttribute('href') || '').trim();
        const dataEl = card?.querySelector('[data-vid],[data-video-id],[data-id]') || card;
        const vid = (dataEl?.getAttribute('data-vid')
            || dataEl?.getAttribute('data-video-id')
            || dataEl?.getAttribute('data-id')
            || '').trim();
        const thumb = (card?.querySelector('img, video')?.getAttribute('src')
            || card?.querySelector('img, video')?.getAttribute('poster')
            || '').trim();
        const text = norm(card?.innerText).slice(0, 120);
        if (vid) return 'vid:' + vid;
        if (href && href.length > 5) return 'href:' + href;
        if (thumb) return 'thumb:' + thumb.slice(-80);
        return 'text:' + text + '#' + index;
    };
    return saleActions().map((el, index) => {
        const card = cardForAction(el);
        return {
            index,
            key: keyForAction(el, index),
            label: norm(card?.innerText).slice(0, 48),
        };
    });
}
"""

_COUNT_SCRIPT = """
(saleTexts) => {
    const texts = saleTexts && saleTexts.length ? saleTexts : ['上架销售'];
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 2 && r.height > 2;
    };
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, section[class*="dioa-dialog"]');
    let n = 0;
    for (const el of document.querySelectorAll(
        'button, a, [role="button"], span[class*="button"], div[class*="button"], div[class*="btn"], span[class*="btn"]'
    )) {
        if (inDialog(el) || !isVisible(el)) continue;
        const t = norm(el.innerText || el.textContent);
        if (texts.some((x) => t === x || t.startsWith(x))) n++;
    }
    return n;
}
"""

_CLICK_SCRIPT = """
(args) => {
    const { index, saleTexts } = args;
    const texts = saleTexts && saleTexts.length ? saleTexts : ['上架销售'];
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 2 && r.height > 2;
    };
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, section[class*="dioa-dialog"]');
    const clickTarget = (el) => {
        let node = el;
        for (let i = 0; i < 8 && node; i++) {
            const tag = (node.tagName || '').toUpperCase();
            const role = node.getAttribute('role') || '';
            if (tag === 'BUTTON' || tag === 'A' || role === 'button') return node;
            node = node.parentElement;
        }
        return el;
    };
    const actions = [];
    for (const el of document.querySelectorAll(
        'button, a, [role="button"], span[class*="button"], div[class*="button"], div[class*="btn"], span[class*="btn"]'
    )) {
        if (inDialog(el) || !isVisible(el)) continue;
        const t = norm(el.innerText || el.textContent);
        if (texts.some((x) => t === x || t.startsWith(x))) actions.push(el);
    }
    const el = actions[index];
    if (!el) return { ok: false };
    document.querySelectorAll('[data-vjshi-sale-btn]').forEach((node) => {
        node.removeAttribute('data-vjshi-sale-btn');
    });
    const target = clickTarget(el);
    target.setAttribute('data-vjshi-sale-btn', '1');
    target.scrollIntoView({ block: 'center', inline: 'nearest' });
    target.focus();
    for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
        target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    }
    return { ok: true, text: norm(target.innerText || target.textContent) };
}
"""

_SCROLL_LAST_SCRIPT = """
(saleTexts) => {
    const texts = saleTexts && saleTexts.length ? saleTexts : ['上架销售'];
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 2 && r.height > 2;
    };
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, section[class*="dioa-dialog"]');
    const actions = [];
    for (const el of document.querySelectorAll(
        'button, a, [role="button"], span[class*="button"], div[class*="button"], div[class*="btn"], span[class*="btn"]'
    )) {
        if (inDialog(el) || !isVisible(el)) continue;
        const t = norm(el.innerText || el.textContent);
        if (texts.some((x) => t === x || t.startsWith(x))) actions.push(el);
    }
    const last = actions[actions.length - 1];
    if (last) {
        last.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        return true;
    }
    return false;
}
"""

_ENSURE_TAB_SCRIPT = """
() => {
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const tabs = ['待上架', '待完善', '未上架'];
    for (const label of tabs) {
        for (const el of document.querySelectorAll(
            'button, a, [role="tab"], li, span, div'
        )) {
            const t = norm(el.innerText || el.textContent);
            if (t !== label && !t.startsWith(label)) continue;
            if (el.closest('section.dioa-dialog__content, section[class*="dioa-dialog"]')) continue;
            el.click();
            return label;
        }
    }
    return '';
}
"""

_MARK_SKIPPED_SCRIPT = """
(args) => {
    const { key, reason, saleTexts } = args;
    const texts = saleTexts && saleTexts.length ? saleTexts : ['上架销售'];
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 2 && r.height > 2;
    };
    const inDialog = (el) => !!el.closest('section.dioa-dialog__content, section[class*="dioa-dialog"]');
    const cardForAction = (el) => {
        let node = el;
        for (let i = 0; i < 14 && node; i++) {
            const tag = (node.tagName || '').toUpperCase();
            const hasThumb = !!node.querySelector?.('img, video, [class*="aspect"], [class*="cover"]');
            const cls = (node.className || '').toString();
            if (hasThumb && (tag === 'DIV' || tag === 'LI' || tag === 'TR' || tag === 'ARTICLE')) return node;
            if (/card|item|row|video|group|aspect/i.test(cls) && hasThumb) return node;
            node = node.parentElement;
        }
        return el.closest('tr, li, article, div.group, div[class*="group"]') || el.parentElement;
    };
    const keyForAction = (el, index) => {
        const card = cardForAction(el);
        const link = card?.querySelector('a[href]');
        const href = (link?.getAttribute('href') || '').trim();
        const dataEl = card?.querySelector('[data-vid],[data-video-id],[data-id]') || card;
        const vid = (dataEl?.getAttribute('data-vid')
            || dataEl?.getAttribute('data-video-id')
            || dataEl?.getAttribute('data-id')
            || '').trim();
        const thumb = (card?.querySelector('img, video')?.getAttribute('src')
            || card?.querySelector('img, video')?.getAttribute('poster')
            || '').trim();
        const text = norm(card?.innerText).slice(0, 120);
        if (vid) return 'vid:' + vid;
        if (href && href.length > 5) return 'href:' + href;
        if (thumb) return 'thumb:' + thumb.slice(-80);
        return 'text:' + text + '#' + index;
    };
    const actions = [];
    for (const el of document.querySelectorAll(
        'button, a, [role="button"], span[class*="button"], div[class*="button"], div[class*="btn"], span[class*="btn"]'
    )) {
        if (inDialog(el) || !isVisible(el)) continue;
        const t = norm(el.innerText || el.textContent);
        if (texts.some((x) => t === x || t.startsWith(x))) actions.push(el);
    }
    for (let i = 0; i < actions.length; i++) {
        if (keyForAction(actions[i], i) !== key) continue;
        const card = cardForAction(actions[i]);
        if (!card) return false;
        card.setAttribute('data-vjshi-tool-skipped', reason || '1');
        card.style.outline = '2px solid #faad14';
        card.style.outlineOffset = '2px';
        if (getComputedStyle(card).position === 'static') card.style.position = 'relative';
        let badge = card.querySelector('.vjshi-skip-badge');
        if (!badge) {
            badge = document.createElement('div');
            badge.className = 'vjshi-skip-badge';
            badge.textContent = '已跳过·无AI推荐';
            badge.style.cssText = [
                'position:absolute', 'top:8px', 'left:8px', 'z-index:20',
                'padding:2px 8px', 'border-radius:4px', 'font-size:12px',
                'line-height:1.4', 'color:#ad6800', 'background:#fff7e6',
                'border:1px solid #ffd591', 'pointer-events:none',
                'font-family:system-ui,sans-serif',
            ].join(';');
            card.appendChild(badge);
        }
        return true;
    }
    return false;
}
"""

_FIND_EDIT_DIALOG_SCRIPT = """
() => {
    document.querySelectorAll('[data-vjshi-edit-dialog]').forEach((node) => {
        node.removeAttribute('data-vjshi-edit-dialog');
    });
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const headers = ['视频编辑', '完善信息', '编辑视频', '视频信息', '上架信息'];
    const markers = ['AI推荐标题', 'AI推荐关键词', '作品风格', '创作时间'];
    const isVisible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return false;
        const r = el.getBoundingClientRect();
        return r.width > 120 && r.height > 120;
    };
    const candidates = [];
    for (const sec of document.querySelectorAll(
        'section.dioa-dialog__content, section[class*="dioa-dialog__content"], section[class*="dioa-dialog"]'
    )) {
        if (!isVisible(sec)) continue;
        const t = norm(sec.innerText);
        let score = 0;
        for (const h of headers) {
            if (t.includes(h)) score += 100;
        }
        let markerHits = 0;
        for (const m of markers) {
            if (t.includes(m)) {
                score += 20;
                markerHits++;
            }
        }
        if (markerHits >= 2) score += 60;
        if (score > 0) candidates.push({ score, el: sec });
    }
    if (!candidates.length) return false;
    candidates.sort((a, b) => b.score - a.score);
    candidates[0].el.setAttribute('data-vjshi-edit-dialog', '1');
    return true;
}
"""


@dataclass(frozen=True)
class PendingVideo:
    index: int
    key: str
    label: str


def refresh_edit_dialog_marker(page: Page) -> bool:
    """用 JS 标记当前可见的编辑弹窗，适配标题文案变化。"""
    return bool(stable_evaluate(page, _FIND_EDIT_DIALOG_SCRIPT))


def edit_dialog(page: Page) -> Locator:
    """可见的视频编辑弹窗（排除隐藏 popover）。"""
    refresh_edit_dialog_marker(page)
    marked = page.locator("section[data-vjshi-edit-dialog='1']")
    if marked.count() > 0:
        return marked.first
    for header in DIALOG_HEADERS:
        dlg = page.locator(DIALOG_SECTION_SELECTOR).filter(
            has=page.get_by_text(header, exact=False)
        )
        if dlg.count() > 0:
            return dlg.first
    dlg = page.locator(DIALOG_SECTION_SELECTOR)
    for marker in DIALOG_FORM_MARKERS[:2]:
        dlg = dlg.filter(has=page.get_by_text(marker, exact=False))
    return dlg.first


def is_edit_dialog_open(page: Page) -> bool:
    try:
        if refresh_edit_dialog_marker(page):
            return True
        dlg = edit_dialog(page)
        return dlg.count() > 0 and dlg.is_visible()
    except Exception:
        return False


def wait_for_edit_dialog(page: Page, *, timeout_ms: int) -> Locator:
    step = 250
    elapsed = 0
    while elapsed < timeout_ms:
        if is_edit_dialog_open(page):
            dlg = edit_dialog(page)
            dlg.wait_for(state="visible", timeout=2000)
            return dlg
        page.wait_for_timeout(step)
        elapsed += step
    raise RuntimeError(
        "点击「上架销售」后未出现视频编辑弹窗。"
        "请确认列表按钮可手动打开弹窗，或检查页面是否改版。"
    )


_FORM_CENTER_READY_SCRIPT = """
() => {
    const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
        || document.querySelector('section.dioa-dialog__content');
    if (!dlg) return false;
    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
    const t = norm(dlg.innerText || '');
    const hasAiTitle = t.includes('AI推荐标题') || t.includes('AI 推荐标题');
    const hasKeywords = t.includes('AI推荐关键词') || t.includes('AI 推荐关键词')
        || t.includes('关键词找素材')
        || (/\\d+\\s*\\/\\s*30\\s*个/.test(t) && t.includes('关键词'));
    if (!hasAiTitle || !hasKeywords) return false;
    const visible = (el) => {
        if (!el) return false;
        const st = getComputedStyle(el);
        if (st.display === 'none' || st.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 8 && r.height > 8;
    };
    for (const el of dlg.querySelectorAll('button, [role="button"]')) {
        if (!visible(el)) continue;
        const bt = norm(el.textContent);
        if (!bt || bt.length > 40) continue;
        if (bt.includes('AI推荐') || bt.includes('换一批')) continue;
        return true;
    }
    return dlg.querySelector('input.dioa-input__field, textarea') !== null;
}
"""


def is_dialog_form_center_ready(page: Page) -> bool:
    """中间栏（标题/AI推荐/关键词）是否已加载。"""
    return bool(stable_evaluate(page, _FORM_CENTER_READY_SCRIPT))


def wait_for_dialog_form_ready(page: Page, *, timeout_ms: int = 30000) -> None:
    """等待弹窗中间表单区加载完成（异步接口，不能只看弹窗壳）。"""
    step = 400
    elapsed = 0
    while elapsed < timeout_ms:
        if is_dialog_form_center_ready(page):
            page.wait_for_timeout(300)
            return
        page.wait_for_timeout(step)
        elapsed += step
    raise RuntimeError(
        "弹窗中间表单（标题/AI推荐/关键词）尚未加载完成。"
        "通常与网络或页面异步加载有关，请稍后重试或手动刷新页面。"
    )


def _sale_texts_arg() -> list[str]:
    return list(SALE_BUTTON_TEXTS)


def ensure_pending_tab(page: Page) -> None:
    """新版页面若有「待上架」等标签，先切到待处理列表。"""
    page.evaluate(_ENSURE_TAB_SCRIPT)
    page.wait_for_timeout(400)


def count_pending_videos(page: Page) -> int:
    n = page.evaluate(_COUNT_SCRIPT, _sale_texts_arg())
    return int(n) if isinstance(n, (int, float)) else 0


def list_pending_videos(page: Page) -> list[PendingVideo]:
    raw = page.evaluate(_LIST_SCRIPT, {"saleTexts": _sale_texts_arg()})
    if not isinstance(raw, list):
        return []
    out: list[PendingVideo] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            PendingVideo(
                index=int(item.get("index", 0)),
                key=str(item.get("key", "")),
                label=str(item.get("label", "")),
            )
        )
    return out


def click_sale_action_at(page: Page, index: int) -> None:
    result = stable_evaluate(
        page,
        _CLICK_SCRIPT,
        {"index": index, "saleTexts": _sale_texts_arg()},
    )
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(f"未找到第 {index + 1} 个「上架销售」按钮。")
    marked = page.locator("[data-vjshi-sale-btn='1']")
    if marked.count() > 0:
        try:
            marked.first.scroll_into_view_if_needed()
            marked.first.click(force=True, timeout=5000)
        except Exception:
            pass
    page.wait_for_timeout(400)


def scroll_last_sale_into_view(page: Page) -> bool:
    return bool(page.evaluate(_SCROLL_LAST_SCRIPT, _sale_texts_arg()))


def mark_video_skipped(page: Page, video_key: str, reason: str = "") -> bool:
    return bool(
        page.evaluate(
            _MARK_SKIPPED_SCRIPT,
            {"key": video_key, "reason": reason, "saleTexts": _sale_texts_arg()},
        )
    )


def wait_for_upload_list_ready(page: Page, *, timeout_ms: int) -> None:
    """等待列表页加载出待上架项或空状态。"""
    if page.get_by_text("您已退出登录", exact=False).count() > 0:
        raise RuntimeError("未登录或登录已过期，请在浏览器登录后点击「登录完成，继续上架」。")

    ensure_pending_tab(page)

    deadline = timeout_ms
    step = 300
    elapsed = 0
    while elapsed < deadline:
        if count_pending_videos(page) > 0:
            return
        for hint in LIST_READY_HINTS:
            if page.get_by_text(hint, exact=False).count() > 0:
                page.wait_for_timeout(500)
                if count_pending_videos(page) > 0:
                    return
                return
        page.wait_for_timeout(step)
        elapsed += step

    if count_pending_videos(page) == 0:
        for hint in ("暂无", "没有", "上传"):
            if page.get_by_text(hint, exact=False).count() > 0:
                return

    raise RuntimeError(
        "未检测到待上架视频列表，请确认已打开 "
        "https://www.vjshi.com/user/upload/video 并完成登录。"
    )
