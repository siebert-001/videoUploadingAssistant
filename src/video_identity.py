"""待上架列表项的稳定标识与跳过标注。"""
from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

SALE_BUTTON_TEXT = "上架销售"

_KEY_SCRIPT = """
(saleText) => {
    const sale = saleText || '上架销售';
    const saleButtons = () => [...document.querySelectorAll('button')].filter(
        b => (b.textContent || '').trim() === sale
    );
    const cardForButton = (btn) => btn.closest('div.aspect-video.group')
        || btn.closest('div.group.min-w-\\[320px\\]')
        || btn.closest('[class*="aspect-video"]')
        || btn.parentElement?.closest('div.group')
        || btn.parentElement;

    const keyForButton = (btn, index) => {
        const card = cardForButton(btn);
        const link = card?.querySelector('a[href]');
        const href = (link?.getAttribute('href') || '').trim();
        const el = card?.querySelector('[data-vid],[data-video-id],[data-id]') || card;
        const vid = (el?.getAttribute('data-vid')
            || el?.getAttribute('data-video-id')
            || el?.getAttribute('data-id')
            || '').trim();
        const thumb = (card?.querySelector('img')?.getAttribute('src') || '').trim();
        const text = (card?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
        if (vid) return 'vid:' + vid;
        if (href && href.length > 5) return 'href:' + href;
        if (thumb) return 'thumb:' + thumb.slice(-80);
        return 'text:' + text + '#' + index;
    };

    return saleButtons().map((btn, index) => {
        const card = cardForButton(btn);
        const text = (card?.innerText || '').replace(/\\s+/g, ' ').trim();
        return {
            index,
            key: keyForButton(btn, index),
            label: text.slice(0, 48),
        };
    });
}
"""

_MARK_SKIPPED_SCRIPT = """
(args) => {
    const { key, reason, saleText } = args;
    const saleButtons = () => [...document.querySelectorAll('button')].filter(
        b => (b.textContent || '').trim() === sale
    );
    const cardForButton = (btn) => btn.closest('div.aspect-video.group')
        || btn.closest('div.group.min-w-\\[320px\\]')
        || btn.closest('[class*="aspect-video"]')
        || btn.parentElement?.closest('div.group')
        || btn.parentElement;

    const keyForButton = (btn, index) => {
        const card = cardForButton(btn);
        const link = card?.querySelector('a[href]');
        const href = (link?.getAttribute('href') || '').trim();
        const el = card?.querySelector('[data-vid],[data-video-id],[data-id]') || card;
        const vid = (el?.getAttribute('data-vid')
            || el?.getAttribute('data-video-id')
            || el?.getAttribute('data-id')
            || '').trim();
        const thumb = (card?.querySelector('img')?.getAttribute('src') || '').trim();
        const text = (card?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
        if (vid) return 'vid:' + vid;
        if (href && href.length > 5) return 'href:' + href;
        if (thumb) return 'thumb:' + thumb.slice(-80);
        return 'text:' + text + '#' + index;
    };

    for (let i = 0; i < saleButtons().length; i++) {
        const btn = saleButtons()[i];
        if (keyForButton(btn, i) !== key) continue;
        const card = cardForButton(btn);
        if (!card) return false;
        card.setAttribute('data-vjshi-tool-skipped', reason || '1');
        card.style.outline = '2px solid #faad14';
        card.style.outlineOffset = '2px';
        if (getComputedStyle(card).position === 'static') {
            card.style.position = 'relative';
        }
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


@dataclass(frozen=True)
class PendingVideo:
    index: int
    key: str
    label: str


def list_pending_videos(page: Page) -> list[PendingVideo]:
    raw = page.evaluate(_KEY_SCRIPT, SALE_BUTTON_TEXT)
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


def mark_video_skipped(page: Page, video_key: str, reason: str = "") -> bool:
    """在列表卡片上标注「已跳过」，便于识别且本会话不再打开。"""
    return bool(
        page.evaluate(
            _MARK_SKIPPED_SCRIPT,
            {"key": video_key, "reason": reason, "saleText": SALE_BUTTON_TEXT},
        )
    )
