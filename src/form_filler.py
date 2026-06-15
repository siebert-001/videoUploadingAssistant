"""填写「视频编辑」弹窗中的表单信息（标题从 AI 推荐随机选取）。"""
from __future__ import annotations

import random
import re

from playwright.sync_api import Locator, Page

from src.exceptions import VideoSkipError
from src.field_settings import VideoFieldSettings
from src.page_eval import stable_evaluate, stable_locator_evaluate
from src.upload_page import (
    edit_dialog,
    is_dialog_form_center_ready,
    is_edit_dialog_open,
    refresh_edit_dialog_marker,
    wait_for_dialog_form_ready,
)


def _dialog(page: Page) -> Locator:
    return edit_dialog(page)


def _is_edit_dialog_open(page: Page) -> bool:
    return is_edit_dialog_open(page)


KEYWORDS_COUNT_MIN = 5
KEYWORDS_COUNT_MAX = 10
KEYWORDS_EXCLUDED_SUBSTR = "循环"
CREATION_TIME_PLACEHOLDER = "正确的创作时间"
WORK_STYLE = "实拍写实"
WORK_STYLE_OPTIONS = ("实拍写实", "立体三维", "平面二维", "抽象光影")


def _ensure_edit_dialog_open(page: Page) -> None:
    if not _is_edit_dialog_open(page):
        raise RuntimeError(
            "视频编辑弹窗已关闭（清空关键词时请勿误点弹窗右上角关闭按钮）。"
        )


def _input_near_label(dialog: Locator, label: str) -> Locator:
    """根据标签文字定位相邻输入框。"""
    return dialog.locator(
        f"xpath=.//*[contains(text(),'{label}')]/ancestor::*[self::div or self::label]"
        f"[1]//input[not(@type='checkbox') and not(@type='hidden')][1]"
    )


def _clear_input(locator: Locator, page: Page) -> None:
    """仅清空指定输入框，不用全选快捷键（避免选中整个弹窗）。"""
    locator.click()
    try:
        locator.fill("")
    except Exception:
        pass
    stable_locator_evaluate(
        locator,
        """(el) => {
            if ('value' in el) el.value = '';
            else el.textContent = '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
    )
    page.wait_for_timeout(100)


def _clear_title_field(page: Page, dialog: Locator, *, log) -> None:
    """清空标题输入框（仅操作中间栏标题区，避免误点右侧授权价）。"""
    title_input = None
    for xpath in (
        ".//*[contains(.,'标题准确')]/following::input[contains(@class,'dioa-input__field')][1]",
        ".//*[contains(.,'AI推荐标题')]/ancestor::div[contains(@class,'grid') or contains(@class,'flex')][1]"
        "//input[contains(@class,'dioa-input__field')][1]",
        ".//*[contains(.,'视频标题')]/following::input[contains(@class,'dioa-input__field')][1]",
    ):
        loc = dialog.locator(f"xpath={xpath}")
        if loc.count() > 0:
            title_input = loc.first
            break
    if title_input is None or title_input.count() == 0:
        log("  标题: 未找到输入框，跳过清空")
        return
    _clear_input(title_input, page)
    log("  标题: 已清空")


def _mark_keywords_input(page: Page, dialog: Locator) -> bool:
    """在弹窗内标记关键词输入区（适配新版 tag-input DOM）。"""
    refresh_edit_dialog_marker(page)
    return bool(
        stable_evaluate(page,
            """() => {
                const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
                    || document.querySelector('section.dioa-dialog__content');
                if (!dlg) return false;
                dlg.querySelectorAll('[data-vjshi-kw-input],[data-vjshi-kw-section]').forEach(
                    (el) => {
                        el.removeAttribute('data-vjshi-kw-input');
                        el.removeAttribute('data-vjshi-kw-section');
                    }
                );
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => {
                    if (!el) return false;
                    const st = getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const inAiZone = (el) => {
                    let node = el;
                    for (let i = 0; i < 10 && node && node !== dlg; i++) {
                        const t = norm(node.textContent || '');
                        if (t.length > 220) {
                            node = node.parentElement;
                            continue;
                        }
                        if (t.includes('AI推荐关键词')) return true;
                        node = node.parentElement;
                    }
                    return false;
                };
                const labelHints = ['关键词找素材', '关键词'];
                const findSection = () => {
                    for (const hint of labelHints) {
                        for (const el of dlg.querySelectorAll('label, span, div, p')) {
                            const t = norm(el.textContent);
                            if (!t.includes(hint) || t.includes('AI推荐')) continue;
                            if (t.length > 32) continue;
                            const section = el.closest('div[id^="formcontrol"]')
                                || el.parentElement?.parentElement
                                || el.parentElement;
                            if (section && !inAiZone(section)) return section;
                        }
                    }
                    for (const el of dlg.querySelectorAll('*')) {
                        const t = norm(el.textContent);
                        if (!/\\d+\\s*\\/\\s*30\\s*个/.test(t)) continue;
                        if (t.length > 24) continue;
                        let box = el.parentElement;
                        for (let i = 0; i < 8 && box; i++) {
                            if (!inAiZone(box)) return box;
                            box = box.parentElement;
                        }
                    }
                    return null;
                };
                const section = findSection();
                if (!section) return false;
                section.setAttribute('data-vjshi-kw-section', '1');
                const inputs = [
                    ...section.querySelectorAll(
                        'textarea, input:not([type=checkbox]):not([type=hidden]):not([type=radio]), [contenteditable="true"], [role="combobox"]'
                    ),
                ].filter((el) => visible(el) && !inAiZone(el));
                if (inputs.length) {
                    inputs[0].setAttribute('data-vjshi-kw-input', '1');
                    return true;
                }
                const clickArea = section.querySelector(
                    '[class*="tag"], [class*="chip"], [class*="select"], [class*="input"], [class*="textarea"]'
                );
                if (clickArea && visible(clickArea) && !inAiZone(clickArea)) {
                    clickArea.setAttribute('data-vjshi-kw-input', '1');
                    return true;
                }
                section.setAttribute('data-vjshi-kw-input', '1');
                return true;
            }"""
        )
    )


def _wait_keywords_area(page: Page, dialog: Locator, *, timeout_ms: int = 8000) -> bool:
    step = 250
    elapsed = 0
    while elapsed < timeout_ms:
        if _mark_keywords_input(page, dialog):
            return True
        page.wait_for_timeout(step)
        elapsed += step
    return _mark_keywords_input(page, dialog)


def _keywords_field_root(dialog: Locator) -> Locator:
    """关键词输入区（锚定输入框父级，避免误选整个弹窗）。"""
    page = dialog.page
    _mark_keywords_input(page, dialog)
    section = dialog.locator("[data-vjshi-kw-section='1']")
    if section.count() > 0:
        return section.first
    marked = dialog.locator("[data-vjshi-kw-input='1']")
    if marked.count() > 0:
        root = marked.first.locator(
            "xpath=ancestor::div[contains(@class,'grid') or contains(@class,'flex') or contains(@class,'field')][1]"
        )
        if root.count() > 0:
            return root.first
        return marked.first.locator("xpath=ancestor::div[1]")

    for xpath in (
        ".//*[contains(normalize-space(),'关键词找素材')]/ancestor::div[contains(@class,'grid') or contains(@class,'flex')][1]",
        ".//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]/ancestor::div[contains(@class,'grid') or contains(@class,'flex')][2]",
        ".//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]/ancestor::div[1]",
    ):
        root = dialog.locator(f"xpath={xpath}")
        if root.count() > 0:
            return root.first
    return dialog.locator("[data-vjshi-kw-section='1']").first


def _keywords_input(dialog: Locator) -> Locator:
    page = dialog.page
    _mark_keywords_input(page, dialog)
    marked = dialog.locator("[data-vjshi-kw-input='1']")
    if marked.count() > 0:
        return marked.first

    root = _keywords_field_root(dialog)
    for sel in (
        "textarea",
        "input:not([type='checkbox']):not([type='hidden']):not([type='radio'])",
        "[contenteditable='true']",
        "[role='combobox']",
    ):
        inp = root.locator(sel).first
        if inp.count() > 0:
            return inp

    for xpath in (
        ".//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/following::textarea[1]",
        ".//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/following::input[not(@type='checkbox')][1]",
        ".//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/ancestor::div[1]//textarea[1]",
        ".//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/ancestor::div[1]//input[contains(@class,'input')][1]",
    ):
        inp = dialog.locator(f"xpath={xpath}")
        if inp.count() > 0:
            return inp.first
    return dialog.locator("[data-vjshi-kw-input='1']").first


def _keywords_textarea(dialog: Locator) -> Locator:
    return _keywords_input(dialog)


def _keywords_selected_scope(dialog: Locator) -> Locator:
    """仅关键词已选区（不含 AI 推荐关键词按钮列表）。"""
    section = dialog.locator("[data-vjshi-kw-section='1']")
    if section.count() > 0:
        return section.first
    for xpath in (
        ".//*[contains(.,'关键词找素材')]/ancestor::div[contains(@class,'grid') or contains(@class,'flex')][1]",
        ".//*[contains(.,'关键词') and not(contains(.,'AI推荐'))]/ancestor::div[contains(@class,'grid')][1]",
    ):
        loc = dialog.locator(f"xpath={xpath}")
        if loc.count() > 0:
            return loc.first
    return _keywords_field_root(dialog)


def _keyword_count_js(page: Page, dialog: Locator) -> int:
    """仅从关键词区的「N/30个」读取已选数量（最可靠）。"""
    _mark_keywords_input(page, dialog)
    result = stable_evaluate(
        page,
        """() => {
            const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
                || document.querySelector('section.dioa-dialog__content');
            if (!dlg) return 0;
            const section = dlg.querySelector('[data-vjshi-kw-section="1"]');
            if (!section) return 0;
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            for (const el of section.querySelectorAll('*')) {
                if (el.children.length > 2) continue;
                const t = norm(el.textContent);
                const m = t.match(/^(\\d+)\\s*\\/\\s*30\\s*个$/);
                if (m) return parseInt(m[1], 10);
            }
            return 0;
        }""",
    )
    if isinstance(result, int) and 0 <= result <= 30:
        return result
    return 0


def _keyword_count(dialog: Locator) -> int:
    return _keyword_count_js(dialog.page, dialog)


def _get_keywords_list(dialog: Locator) -> list[str]:
    page = dialog.page
    _mark_keywords_input(page, dialog)
    raw = stable_evaluate(
        page,
        """() => {
            const section = document.querySelector('[data-vjshi-kw-section="1"]');
            if (!section) return [];
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const visible = (el) => {
                if (!el) return false;
                const r = el.getBoundingClientRect();
                return r.width > 2 && r.height > 2;
            };
            const out = [];
            const seen = new Set();
            for (const el of section.querySelectorAll(
                '[class*="dioa-tag"], [class*="tag__content"], span[class*="tag"], div[class*="tag"]'
            )) {
                if (!visible(el) || el.tagName === 'BUTTON') continue;
                if (el.closest('button')) continue;
                let text = norm(el.textContent);
                if (!text || text.length > 40 || text.includes('/30')) continue;
                if (seen.has(text)) continue;
                seen.add(text);
                out.push(text);
            }
            return out;
        }""",
    )
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _count_keywords_in_textarea(dialog: Locator) -> int:
    return _keyword_count(dialog)


def _focus_keywords_area(page: Page, dialog: Locator) -> bool:
    """点击关键词区域以获取焦点（新版可能无独立 textarea）。"""
    _mark_keywords_input(page, dialog)
    return bool(
        stable_evaluate(page,
            """() => {
                const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
                    || document.querySelector('section.dioa-dialog__content');
                if (!dlg) return false;
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const clickEl = (el) => {
                    if (!el || !visible(el)) return false;
                    el.scrollIntoView({ block: 'nearest' });
                    el.focus?.();
                    el.click();
                    return true;
                };
                const marked = dlg.querySelector('[data-vjshi-kw-input="1"]');
                if (clickEl(marked)) return true;
                const section = dlg.querySelector('[data-vjshi-kw-section="1"]');
                if (section) {
                    const area = section.querySelector(
                        'input, textarea, [contenteditable], [class*="tag"], [class*="input"]'
                    );
                    if (clickEl(area)) return true;
                    if (clickEl(section)) return true;
                }
                for (const el of dlg.querySelectorAll('*')) {
                    const t = norm(el.textContent);
                    if (!/\\d+\\s*\\/\\s*30\\s*个/.test(t) || t.length > 20) continue;
                    let box = el.parentElement;
                    for (let i = 0; i < 8 && box; i++) {
                        const area = box.querySelector(
                            'input, textarea, [contenteditable], [class*="tag"], [class*="input"]'
                        );
                        if (clickEl(area)) return true;
                        if (clickEl(box)) return true;
                        box = box.parentElement;
                    }
                }
                return false;
            }"""
        )
    )


def _clear_keywords_via_keyboard(page: Page, dialog: Locator, inp: Locator | None) -> None:
    """逐个移除关键词标签，不使用 Ctrl+A / 全局 Backspace。"""
    for _ in range(30):
        _ensure_edit_dialog_open(page)
        if _keyword_count(dialog) == 0:
            return
        if not _remove_one_keyword_chip(page, dialog):
            break
        page.wait_for_timeout(100)

    if _keyword_count(dialog) == 0:
        return

    if inp is not None and inp.count() > 0:
        try:
            inp.click(force=True)
            inp.fill("")
            stable_locator_evaluate(
                inp,
                """(el) => {
                    if ('value' in el) el.value = '';
                    else el.textContent = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
            )
        except Exception:
            pass
    page.wait_for_timeout(120)


def _clear_keywords_field(page: Page, dialog: Locator, *, log) -> None:
    """强制清空关键词区（含上次编辑缓存的标签）。"""
    _ensure_edit_dialog_open(page)
    if not _wait_keywords_area(page, dialog):
        raise RuntimeError("未找到关键词输入区，无法清空缓存。")

    cached = _keyword_count(dialog)
    if cached == 0:
        log("  关键词: 无需清空")
        return
    log(f"  关键词: 检测到缓存 {cached} 个，正在清空…")

    inp = _keywords_input(dialog)
    has_input = inp.count() > 0
    if not has_input and not _focus_keywords_area(page, dialog):
        section = dialog.locator("[data-vjshi-kw-section='1']")
        if section.count() > 0:
            section.first.click(force=True)
        else:
            raise RuntimeError("未找到关键词输入区，无法清空缓存。")

    _clear_keywords_via_keyboard(page, dialog, inp if has_input else None)

    remaining = _keyword_count(dialog)
    if remaining > 0:
        raise RuntimeError(
            f"无法清空关键词缓存，仍有 {remaining} 个（页面计数/输入框未归零）"
        )
    log("  关键词: 已清空")
    if not is_dialog_form_center_ready(page):
        wait_for_dialog_form_ready(page, timeout_ms=20000)


def _is_keyword_allowed(word: str) -> bool:
    return bool(word.strip()) and KEYWORDS_EXCLUDED_SUBSTR not in word


def _remove_keyword_chip_via_js(page: Page) -> bool:
    """点击关键词已选区最后一个标签的删除钮。"""
    return bool(
        stable_evaluate(
            page,
            """() => {
                const section = document.querySelector('[data-vjshi-kw-section="1"]');
                if (!section) return false;
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const tags = [...section.querySelectorAll(
                    '[class*="dioa-tag"], [class*="tag"], [class*="chip"]'
                )].filter((el) => visible(el) && el.tagName !== 'BUTTON' && !el.closest('button'));
                if (!tags.length) return false;
                const last = tags[tags.length - 1];
                const close = last.querySelector(
                    'button, [class*="close"], [class*="remove"], svg, span'
                );
                (close || last).click();
                return true;
            }""",
        )
    )


def _remove_one_keyword_chip(page: Page, dialog: Locator) -> bool:
    """移除关键词区最后一个已选词。"""
    _ensure_edit_dialog_open(page)
    before = _keyword_count(dialog)
    if before == 0:
        return False

    if _remove_keyword_chip_via_js(page):
        page.wait_for_timeout(120)
        if _keyword_count(dialog) < before:
            return True

    inp = _keywords_input(dialog)
    if inp.count() == 0:
        _focus_keywords_area(page, dialog)
        inp = _keywords_input(dialog)
    if inp.count() == 0:
        return False
    inp.click(force=True)
    page.wait_for_timeout(80)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(120)
    return _keyword_count(dialog) < before


def _trim_keywords_to_exact(page: Page, dialog: Locator, *, exact: int) -> None:
    """关键词多于 exact 时从末尾删减。"""
    for _ in range(35):
        n = _keyword_count(dialog)
        if n <= exact:
            return
        if not _remove_one_keyword_chip(page, dialog):
            break
        page.wait_for_timeout(80)
    n = _keyword_count(dialog)
    if n > exact:
        raise RuntimeError(f"关键词仍有 {n} 个，无法缩减到 {exact} 个。")


def _remove_keyword_by_text(page: Page, dialog: Locator, word: str) -> bool:
    """按词文案移除一个关键词。"""
    words = _get_keywords_list(dialog)
    if word not in words:
        return False

    area = _keywords_textarea(dialog)
    if area.count() > 0:
        allowed = [w for w in words if w != word]
        if allowed:
            area.first.fill(" ".join(allowed))
        else:
            _clear_input(area.first, page)
        page.wait_for_timeout(100)
        if word not in _get_keywords_list(dialog):
            return True

    for _ in range(len(words)):
        if word not in _get_keywords_list(dialog):
            return True
        if not _remove_one_keyword_chip(page, dialog):
            break
    return word not in _get_keywords_list(dialog)


def _remove_forbidden_keywords(page: Page, dialog: Locator) -> None:
    """删除所有含「循环」的关键词（含页面自动填入）。"""
    for _ in range(30):
        forbidden = [
            w for w in _get_keywords_list(dialog) if not _is_keyword_allowed(w)
        ]
        if not forbidden:
            return
        if not _remove_keyword_by_text(page, dialog, forbidden[0]):
            raise RuntimeError(
                f"无法移除含「{KEYWORDS_EXCLUDED_SUBSTR}」的关键词: {forbidden[0]}"
            )


AI_TITLE_LABELS = ("AI推荐标题", "AI 推荐标题")
AI_KEYWORD_LABELS = ("AI推荐关键词", "AI 推荐关键词")
AI_CHIP_ATTR = {
    "title": "data-vjshi-ai-title-idx",
    "keywords": "data-vjshi-ai-kw-idx",
}


def _ai_label_variants(labels: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for label in labels:
        if label not in out:
            out.append(label)
        compact = label.replace(" ", "")
        if compact not in out:
            out.append(compact)
    return out


def _legacy_ai_container(dialog: Locator, labels: tuple[str, ...]) -> Locator:
    """下午验证可用的 AI 推荐区定位（flex/grid + button）。"""
    for label in _ai_label_variants(labels):
        for xpath in (
            f".//*[contains(.,'{label}')]/following::div[contains(@class,'flex')][1]",
            f".//*[contains(.,'{label}')]/following::div[contains(@class,'grid')][1]",
            f".//*[contains(.,'{label}')]/following::div[contains(@class,'wrap')][1]",
            f".//*[contains(.,'{label}')]/parent::*/following-sibling::div[1]",
            f".//*[contains(.,'{label}')]/ancestor::div[contains(@class,'grid')][1]",
        ):
            container = dialog.locator(f"xpath={xpath}")
            if container.count() > 0:
                return container.first
    return dialog.locator("xpath=.//*[false]")


def _mark_ai_buttons_legacy(
    dialog: Locator,
    *,
    section: str,
    labels: tuple[str, ...],
    exclude_substr: str | None = None,
) -> list[str]:
    attr = AI_CHIP_ATTR[section]
    container = _legacy_ai_container(dialog, labels)
    if container.count() == 0:
        return []

    buttons = container.locator("button")
    texts: list[str] = []
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            if not btn.is_visible():
                continue
            text = btn.inner_text().strip()
        except Exception:
            continue
        if not text:
            continue
        if any(label in text for label in _ai_label_variants(labels)):
            continue
        if text in ("换一批", "重新生成"):
            continue
        if exclude_substr and exclude_substr in text:
            continue
        stable_locator_evaluate(
            btn,
            "(el, args) => el.setAttribute(args.attr, String(args.idx))",
            {"attr": attr, "idx": len(texts)},
        )
        texts.append(text)
    return texts


def _mark_ai_buttons_js(
    page: Page,
    dialog: Locator,
    *,
    section: str,
    labels: tuple[str, ...],
    exclude_substr: str | None = None,
) -> list[str]:
    """JS 兜底：在 AI 标签附近找 button / chip。"""
    attr = AI_CHIP_ATTR[section]
    refresh_edit_dialog_marker(page)
    raw = stable_evaluate(page,
        """(args) => {
            const { labels, attr, excludeSubstr } = args;
            const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
                || document.querySelector('section.dioa-dialog__content');
            if (!dlg) return [];
            dlg.querySelectorAll(`[${attr}]`).forEach((el) => el.removeAttribute(attr));
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const compact = (s) => norm(s).replace(/\\s+/g, '');
            const visible = (el) => {
                if (!el) return false;
                const st = getComputedStyle(el);
                if (st.display === 'none' || st.visibility === 'hidden') return false;
                const r = el.getBoundingClientRect();
                return r.width > 2 && r.height > 2;
            };
            const keys = labels.map((l) => compact(l));
            const isSectionLabel = (t) => {
                const c = compact(t);
                return keys.some((k) => c === k || c.startsWith(k));
            };
            const isNoise = (t) => !t
                || isSectionLabel(t)
                || t.includes('换一批')
                || t.includes('重新生成')
                || (excludeSubstr && t.includes(excludeSubstr));
            let labelEl = null;
            let bestLen = Infinity;
            for (const el of dlg.querySelectorAll('label, span, div, p')) {
                const t = norm(el.textContent);
                if (t.length > 64) continue;
                if (!keys.some((k) => compact(t).includes(k))) continue;
                if (t.length < bestLen) {
                    labelEl = el;
                    bestLen = t.length;
                }
            }
            if (!labelEl) return [];
            const scopes = [];
            const push = (node) => {
                if (node && !scopes.includes(node)) scopes.push(node);
            };
            push(labelEl.parentElement);
            push(labelEl.closest('div[id^="formcontrol"], div.grid, div[class*="field"]'));
            push(labelEl.parentElement?.querySelector(
                'div[class*="flex"], div[class*="grid"], div[class*="wrap"]'
            ));
            let box = labelEl;
            for (let i = 0; i < 8 && box; i++) {
                push(box.nextElementSibling);
                push(box.parentElement);
                box = box.parentElement;
            }
            const seen = new Set();
            const out = [];
            const selectors = [
                'button',
                '[role="button"]',
                'span[class*="tag"]',
                'span[class*="chip"]',
                'div[class*="tag"]',
                'div[class*="chip"]',
            ];
            for (const scope of scopes) {
                if (!scope) continue;
                for (const sel of selectors) {
                    for (const chip of scope.querySelectorAll(sel)) {
                        if (!visible(chip)) continue;
                        let text = norm(chip.textContent);
                        if (chip.children.length === 1 && chip.children[0].children.length === 0) {
                            text = norm(chip.children[0].textContent);
                        }
                        if (isNoise(text) || text.length > 48) continue;
                        if (seen.has(text)) continue;
                        seen.add(text);
                        chip.setAttribute(attr, String(out.length));
                        out.push(text);
                    }
                }
                if (out.length) break;
            }
            return out;
        }""",
        {
            "labels": _ai_label_variants(labels),
            "attr": attr,
            "excludeSubstr": exclude_substr or "",
        },
    )
    return raw if isinstance(raw, list) else []


def _find_ai_chips(
    page: Page,
    dialog: Locator,
    *,
    section: str,
    labels: tuple[str, ...],
    exclude_substr: str | None = None,
) -> list[str]:
    """优先 legacy XPath，失败再用 JS。"""
    stable_evaluate(page,
        """(attr) => {
            document.querySelectorAll(`[${attr}]`).forEach((el) => {
                el.removeAttribute(attr);
            });
        }""",
        AI_CHIP_ATTR[section],
    )
    texts = _mark_ai_buttons_legacy(
        dialog,
        section=section,
        labels=labels,
        exclude_substr=exclude_substr,
    )
    if texts:
        return texts
    return _mark_ai_buttons_js(
        page,
        dialog,
        section=section,
        labels=labels,
        exclude_substr=exclude_substr,
    )


def _ai_chip_locators(page: Page, dialog: Locator, *, section: str) -> list[tuple[str, Locator]]:
    attr = AI_CHIP_ATTR[section]
    locs = page.locator(
        f"section[data-vjshi-edit-dialog='1'] [{attr}], "
        f"section.dioa-dialog__content [{attr}]"
    )
    if locs.count() == 0:
        locs = dialog.locator(f"[{attr}]")
    out: list[tuple[str, Locator]] = []
    for i in range(locs.count()):
        item = locs.nth(i)
        try:
            text = item.inner_text().strip()
        except Exception:
            continue
        if text:
            out.append((text, item))
    return out


def _wait_ai_recommendations(page: Page, dialog: Locator, *, timeout_ms: int = 20000) -> None:
    """等待 AI 推荐标题/关键词加载完成。"""
    step = 500
    elapsed = 0
    while elapsed < timeout_ms:
        titles = len(_find_ai_chips(page, dialog, section="title", labels=AI_TITLE_LABELS))
        keywords = len(
            _find_ai_chips(
                page,
                dialog,
                section="keywords",
                labels=AI_KEYWORD_LABELS,
                exclude_substr=KEYWORDS_EXCLUDED_SUBSTR,
            )
        )
        if titles > 0 and keywords > 0:
            return
        page.wait_for_timeout(step)
        elapsed += step


def _ai_title_option_count(page: Page, dialog: Locator) -> int:
    return len(_find_ai_chips(page, dialog, section="title", labels=AI_TITLE_LABELS))


def _eligible_ai_keyword_count(page: Page, dialog: Locator) -> int:
    return len(
        _find_ai_chips(
            page,
            dialog,
            section="keywords",
            labels=AI_KEYWORD_LABELS,
            exclude_substr=KEYWORDS_EXCLUDED_SUBSTR,
        )
    )


def _ensure_ai_recommendations_available(page: Page, dialog: Locator) -> None:
    """无 AI 标题或完全无 AI 关键词时跳过本视频。"""
    wait_for_dialog_form_ready(page, timeout_ms=25000)
    titles = _ai_title_option_count(page, dialog)
    keywords = _eligible_ai_keyword_count(page, dialog)
    if titles == 0 or keywords == 0:
        page.wait_for_timeout(1500)
        wait_for_dialog_form_ready(page, timeout_ms=15000)
        titles = _ai_title_option_count(page, dialog)
        keywords = _eligible_ai_keyword_count(page, dialog)
    reasons: list[str] = []
    if titles == 0:
        reasons.append("无 AI 推荐标题")
    if keywords == 0:
        reasons.append("无 AI 推荐关键词")
    if reasons:
        raise VideoSkipError("，".join(reasons))


def _get_eligible_ai_keyword_buttons(
    page: Page, dialog: Locator
) -> list[tuple[str, Locator]]:
    _find_ai_chips(
        page,
        dialog,
        section="keywords",
        labels=AI_KEYWORD_LABELS,
        exclude_substr=KEYWORDS_EXCLUDED_SUBSTR,
    )
    eligible: list[tuple[str, Locator]] = []
    for text, btn in _ai_chip_locators(page, dialog, section="keywords"):
        if _is_keyword_allowed(text):
            eligible.append((text, btn))
    return eligible


def _click_ai_keyword_if_needed(
    page: Page,
    dialog: Locator,
    eligible: list[tuple[str, Locator]],
    *,
    target: int,
) -> None:
    """从 AI 推荐中补点关键词，直到恰好 target 个且均不含「循环」。"""
    for _ in range(target * 4):
        _remove_forbidden_keywords(page, dialog)
        current_n = _keyword_count(dialog)
        if current_n == target:
            return
        if current_n > target:
            _trim_keywords_to_exact(page, dialog, exact=target)
            continue

        current = _get_keywords_list(dialog)
        in_field = set(current)
        remaining = [(t, b) for t, b in eligible if t not in in_field]
        if not remaining:
            raise RuntimeError(
                f"AI 推荐关键词可选项不足（需 {target} 个、已排除含「{KEYWORDS_EXCLUDED_SUBSTR}」），"
                f"当前已有 {len(current)} 个"
            )

        text, btn = random.choice(remaining)
        btn.click(force=True)
        page.wait_for_timeout(150)


def _validate_keywords_final(
    dialog: Locator, *, expected: int, log
) -> list[str]:
    n = _keyword_count(dialog)
    words = _get_keywords_list(dialog)
    bad = [w for w in words if not _is_keyword_allowed(w)]
    if bad:
        raise RuntimeError(
            f"关键词不能含「{KEYWORDS_EXCLUDED_SUBSTR}」: {'、'.join(bad)}"
        )
    if n != expected:
        raise RuntimeError(
            f"关键词必须为 {expected} 个，当前 {n} 个: "
            f"{'、'.join(words) or '无'}"
        )
    log(f"  关键词: {'、'.join(words)}（共 {n} 个，不含「{KEYWORDS_EXCLUDED_SUBSTR}」）")
    return words


def _fill_keywords(page: Page, dialog: Locator, *, log) -> list[str]:
    """规则：随机 5–10 个（不超过 AI 推荐数量），且任一关键词不得包含「循环」。"""
    wait_for_dialog_form_ready(page, timeout_ms=15000)
    eligible = _get_eligible_ai_keyword_buttons(page, dialog)
    if len(eligible) == 0:
        raise VideoSkipError("无 AI 推荐关键词")

    target = random.randint(KEYWORDS_COUNT_MIN, KEYWORDS_COUNT_MAX)
    target = min(target, len(eligible))
    log(f"  关键词: 本次选取 {target} 个（AI 推荐可选 {len(eligible)} 个）")

    _remove_forbidden_keywords(page, dialog)
    current = _keyword_count(dialog)
    if current > target:
        log(f"  关键词: 当前 {current} 个，缩减到 {target} 个")
        _trim_keywords_to_exact(page, dialog, exact=target)
    elif current < target:
        log(f"  关键词: 当前 {current} 个，补选到 {target} 个")
        _click_ai_keyword_if_needed(page, dialog, eligible, target=target)
    else:
        log(f"  关键词: 当前 {current} 个，已达目标")

    _remove_forbidden_keywords(page, dialog)
    _trim_keywords_to_exact(page, dialog, exact=target)
    _click_ai_keyword_if_needed(page, dialog, eligible, target=target)
    return _validate_keywords_final(dialog, expected=target, log=log)


def fill_video_form(page: Page, settings: VideoFieldSettings, *, on_log=None) -> None:
    refresh_edit_dialog_marker(page)
    dialog = _dialog(page)
    dialog.wait_for(state="visible")
    wait_for_dialog_form_ready(page)
    _ensure_edit_dialog_open(page)

    log = on_log or (lambda _m: None)

    # 中间栏加载后勿提前清空标题/关键词（会触发 React 重渲染导致中间栏消失）
    _ensure_ai_recommendations_available(page, dialog)

    # 1. 标题：从「AI推荐标题」中随机点选（可能触发页面自动填关键词）
    _select_random_ai_title(page, dialog, log=log)
    if not is_dialog_form_center_ready(page):
        wait_for_dialog_form_ready(page, timeout_ms=15000)

    # 2. 创作时间：按界面配置选择
    _set_creation_time(page, dialog, settings.creation_time, log=log)
    if not is_dialog_form_center_ready(page):
        wait_for_dialog_form_ready(page, timeout_ms=15000)

    # 3. 关键词：随机 5–10 个，不得含「循环」（保留标题自动填入的词，只增减）
    _fill_keywords(page, dialog, log=log)

    # 4. 个人授权价：填入界面设置的价格
    _fill_personal_price(dialog, settings.personal_price, log=log)

    # 5. 作品风格：固定选「实拍写实」
    _set_work_style(page, dialog, WORK_STYLE, log=log)

    # 6. 标签：固定勾选「含AI内容」（放最后，避免被其它操作打断）
    _ensure_has_ai_content(page, dialog, log=log)


def _fill_personal_price(dialog: Locator, price: int, *, log) -> None:
    """个人授权价输入框（dioa-input）填入配置价格。"""
    text = str(price)
    price_input = dialog.locator(
        "xpath=.//*[contains(text(),'个人授权价')]/following::input[contains(@class,'dioa-input__field')][1]"
    )
    if price_input.count() == 0:
        price_input = _input_near_label(dialog, "个人授权")
    if price_input.count() == 0:
        price_input = dialog.locator("input.dioa-input__field[placeholder='18~10000']").first
    if price_input.count() == 0:
        raise RuntimeError("未找到「个人授权价」输入框。")

    field = price_input.first
    field.click()
    field.fill(text)
    log(f"  个人授权价: {text}")


def _find_ai_content_label(dialog: Locator) -> Locator:
    """定位「含AI内容」对应的 label.dioa-checkbox__root。"""
    candidates = dialog.locator(
        "xpath=.//label[contains(@class,'dioa-checkbox')][contains(.,'含AI内容')]"
    )
    for i in range(candidates.count()):
        label = candidates.nth(i)
        text = label.inner_text().strip().replace("\n", "")
        if text == "含AI内容" or (
            "含AI内容" in text and "灰片" not in text and "透明" not in text
        ):
            return label
    raise RuntimeError("未找到「含AI内容」复选框。")


def _checkbox_input_for_label(dialog: Locator, label: Locator) -> Locator | None:
    """dioa 复选框的 input 常通过 label[for] 关联，不在 label 内部。"""
    for_id = label.get_attribute("for")
    if for_id:
        by_id = dialog.locator(f'[id="{for_id}"]')
        if by_id.count() > 0:
            return by_id.first
        by_id = label.page.locator(f'[id="{for_id}"]')
        if by_id.count() > 0:
            return by_id.first
    inner = label.locator("input[type='checkbox']")
    if inner.count() > 0:
        return inner.first
    sibling = label.locator(
        "xpath=following-sibling::input[@type='checkbox'][1]"
    )
    if sibling.count() > 0:
        return sibling.first
    return None


def _ai_content_is_checked(dialog: Locator, label: Locator) -> bool:
    """仅以隐藏 input.checked 为准，避免 data-checked 误判。"""
    return bool(
        stable_locator_evaluate(
            label,
            """(el) => {
                const id = el.getAttribute('for');
                const input = id
                    ? document.getElementById(id)
                    : el.querySelector('input[type="checkbox"]');
                return !!(input && input.checked);
            }""",
        )
    )


def _click_ai_content_checkbox(dialog: Locator, label: Locator) -> None:
    """用 JS 触发 dioa 复选框（Playwright 普通 click 对此组件常无效）。"""
    stable_locator_evaluate(
        label,
        """(el) => {
            const id = el.getAttribute('for');
            let input = id
                ? document.getElementById(id)
                : el.querySelector('input[type="checkbox"]');
            if (input && !input.checked) {
                input.click();
            }
            el.click();
            const ctrl = el.querySelector('.dioa-checkbox__control');
            if (ctrl) ctrl.click();
        }""",
    )
    inp = _checkbox_input_for_label(dialog, label)
    if inp is not None:
        try:
            if not inp.is_checked():
                stable_locator_evaluate(
                    inp,
                    """(el) => {
                        el.checked = true;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""",
                )
        except Exception:
            pass


def _ensure_has_ai_content(page: Page, dialog: Locator, *, log) -> None:
    """标签区固定勾选「含AI内容」。"""
    label = _find_ai_content_label(dialog)
    label.scroll_into_view_if_needed()
    page.wait_for_timeout(150)

    if _ai_content_is_checked(dialog, label):
        log("  含AI内容: 是（已勾选）")
        return

    _click_ai_content_checkbox(dialog, label)
    page.wait_for_timeout(300)

    if not _ai_content_is_checked(dialog, label):
        label.locator(".dioa-checkbox__control").first.click(force=True)
        page.wait_for_timeout(200)

    if not _ai_content_is_checked(dialog, label):
        inp = _checkbox_input_for_label(dialog, label)
        if inp is not None:
            inp.click(force=True)
            page.wait_for_timeout(200)

    if not _ai_content_is_checked(dialog, label):
        raise RuntimeError("未能勾选「含AI内容」，请检查页面是否加载完成。")

    log("  含AI内容: 是")


def _select_random_ai_title(page: Page, dialog: Locator, *, log) -> str:
    """点击弹窗内 AI 推荐标题区域中的随机一项。"""
    _find_ai_chips(page, dialog, section="title", labels=AI_TITLE_LABELS)
    buttons = _ai_chip_locators(page, dialog, section="title")
    if not buttons:
        raise VideoSkipError("无 AI 推荐标题")
    try:
        buttons[0][1].wait_for(state="visible", timeout=10000)
    except Exception as exc:
        raise VideoSkipError("无 AI 推荐标题") from exc
    text, chosen = random.choice(buttons)
    chosen.click(force=True)
    page.wait_for_timeout(300)
    log(f"  标题(AI推荐): {text}")
    return text


def _creation_time_input(dialog: Locator) -> Locator:
    inp = dialog.locator(
        "xpath=.//*[contains(text(),'创作时间')]/following::input[@role='combobox'][1]"
    )
    if inp.count() == 0:
        inp = dialog.locator(
            "xpath=.//*[contains(text(),'创作时间')]/ancestor::div[1]"
            "//input[contains(@class,'dioa-input__field')][1]"
        )
    return inp.first


def _creation_time_current(page: Page, dialog: Locator) -> str:
    result = stable_evaluate(page,
        """(placeholder) => {
            const dialog = document.querySelector("section[data-vjshi-edit-dialog='1']") || document.querySelector('section.dioa-dialog__content');
            if (!dialog) return '';
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const inputs = dialog.querySelectorAll(
                'input[role="combobox"], input.dioa-input__field'
            );
            for (const inp of inputs) {
                let node = inp;
                for (let i = 0; i < 14 && node; i++) {
                    const t = norm(node.textContent || '');
                    if (t.includes('创作时间') && !t.includes('AI推荐')) {
                        return norm(inp.value || '');
                    }
                    node = node.parentElement;
                }
            }
            return '';
        }""",
        CREATION_TIME_PLACEHOLDER,
    )
    if result:
        return result
    inp = _creation_time_input(dialog)
    if inp.count() == 0:
        return ""
    return inp.input_value().strip()


def _creation_time_is_set(page: Page, dialog: Locator, value: str) -> bool:
    current = _creation_time_current(page, dialog)
    if not current or CREATION_TIME_PLACEHOLDER in current:
        return False
    return current == value or value in current


def _open_creation_time_dropdown(page: Page, dialog: Locator) -> None:
    opened = stable_evaluate(page,
        """() => {
            const dialog = document.querySelector("section[data-vjshi-edit-dialog='1']") || document.querySelector('section.dioa-dialog__content');
            if (!dialog) return false;
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            let input = null;
            for (const inp of dialog.querySelectorAll(
                'input[role="combobox"], input.dioa-input__field'
            )) {
                let node = inp;
                for (let i = 0; i < 14 && node; i++) {
                    const t = norm(node.textContent || '');
                    if (t.includes('创作时间') && !t.includes('AI推荐')) {
                        input = inp;
                        break;
                    }
                    node = node.parentElement;
                }
                if (input) break;
            }
            if (!input) return false;
            input.scrollIntoView({ block: 'center' });
            input.focus();
            input.click();
            const wrap = input.closest('.dioa-select, [class*="select"]') || input;
            wrap.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            wrap.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            return true;
        }"""
    )
    if not opened:
        inp = _creation_time_input(dialog)
        if inp.count() == 0:
            raise RuntimeError("未找到「创作时间」下拉框。")
        inp.scroll_into_view_if_needed()
        inp.click(force=True)
    page.wait_for_timeout(700)


def _click_creation_time_year_option(page: Page, value: str) -> bool:
    """在已展开的下拉列表中点击与本地设置一致的年份。"""
    return bool(
        stable_evaluate(page,
            """(args) => {
                const { year, placeholder } = args;
                const dialog = document.querySelector("section[data-vjshi-edit-dialog='1']") || document.querySelector('section.dioa-dialog__content');
                if (!dialog) return false;
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const st = getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const dialogRect = dialog.getBoundingClientRect();
                const candidates = [];
                for (const el of document.querySelectorAll(
                    'div, li, span, p, button, [role="option"]'
                )) {
                    let text = norm(el.textContent);
                    if (el.children.length === 1) {
                        const child = el.children[0];
                        if (child && child.children.length === 0) {
                            text = norm(child.textContent);
                        }
                    }
                    if (text !== year) continue;
                    if (!isVisible(el)) continue;
                    if (norm(el.textContent || '').includes(placeholder)) continue;
                    const r = el.getBoundingClientRect();
                    const cx = (dialogRect.left + dialogRect.right) / 2;
                    const cy = (dialogRect.top + dialogRect.bottom) / 2;
                    const mx = Math.abs((r.left + r.right) / 2 - cx);
                    const my = Math.abs((r.top + r.bottom) / 2 - cy);
                    if (mx > 420 || my > 520) {
                        continue;
                    }
                    let score = 0;
                    let p = el;
                    while (p) {
                        const cn = (p.className || '').toString();
                        if (/menu|popover|dropdown|select|option|listbox|float|portal|picker|virtual/i.test(cn)) {
                            score += 10;
                        }
                        p = p.parentElement;
                    }
                    if (el.tagName === 'INPUT') score -= 100;
                    score -= el.children.length;
                    candidates.push({ el, score, area: r.width * r.height });
                }
                if (!candidates.length) return false;
                candidates.sort((a, b) => b.score - a.score || a.area - b.area);
                const target = candidates[0].el;
                target.scrollIntoView({ block: 'nearest' });
                target.click();
                return true;
            }""",
            {"year": value, "placeholder": CREATION_TIME_PLACEHOLDER},
        )
    )


def _list_visible_creation_years(page: Page) -> list[str]:
    years = stable_evaluate(page,
        """() => {
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const isVisible = (el) => {
                if (!el) return false;
                const st = getComputedStyle(el);
                if (st.display === 'none' || st.visibility === 'hidden') return false;
                const r = el.getBoundingClientRect();
                return r.width > 2 && r.height > 2;
            };
            const out = [];
            for (const el of document.querySelectorAll('div, li, span, p, [role="option"]')) {
                const t = norm(el.textContent);
                if (!/^20\\d{2}$/.test(t)) continue;
                if (!isVisible(el)) continue;
                out.push(t);
            }
            return [...new Set(out)];
        }"""
    )
    return years if isinstance(years, list) else []


def _set_creation_time(
    page: Page, dialog: Locator, value: str, *, log
) -> None:
    """打开创作时间下拉，从选项列表点击与本地设置相同的年份。"""
    value = value.strip()
    if not value:
        raise RuntimeError("创作时间为空，请在界面「本地设置」中填写。")

    if _creation_time_is_set(page, dialog, value):
        log(f"  创作时间: {value}（已是目标值）")
        return

    last_error = ""
    for _ in range(3):
        _open_creation_time_dropdown(page, dialog)
        if _click_creation_time_year_option(page, value):
            page.wait_for_timeout(400)
            if _creation_time_is_set(page, dialog, value):
                log(f"  创作时间: {value}")
                return

        year_loc = page.get_by_text(value, exact=True)
        for i in range(year_loc.count()):
            item = year_loc.nth(i)
            try:
                if not item.is_visible():
                    continue
                box = item.bounding_box()
                if not box:
                    continue
                item.click(force=True)
                page.wait_for_timeout(400)
                if _creation_time_is_set(page, dialog, value):
                    log(f"  创作时间: {value}")
                    return
            except Exception:
                continue

        inp = _creation_time_input(dialog)
        if inp.count() > 0:
            inp.click(force=True)
            page.wait_for_timeout(300)
            try:
                inp.fill(value)
            except Exception:
                pass
            stable_locator_evaluate(
                inp,
                """(el, v) => {
                    el.value = v;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                value,
            )
            page.wait_for_timeout(200)
            inp.press("Enter")
            page.wait_for_timeout(400)
            if _creation_time_is_set(page, dialog, value):
                log(f"  创作时间: {value}")
                return

        last_error = _creation_time_current(page, dialog) or "空/占位符"

    visible = _list_visible_creation_years(page)
    hint = f"；页面可见年份: {', '.join(visible)}" if visible else ""
    raise RuntimeError(
        f"未从创作时间下拉选中 {value}（当前显示: {last_error}{hint}）"
    )


def _work_style_current(page: Page) -> str:
    return str(
        stable_evaluate(page,
            """(styleOptions) => {
                const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
                    || document.querySelector('section.dioa-dialog__content');
                if (!dlg) return '';
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const st = getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const nearCreationTime = (el) => {
                    let node = el;
                    for (let i = 0; i < 10 && node; i++) {
                        const t = norm(node.textContent || '');
                        if (t.includes('创作时间') && t.length < 100) return true;
                        node = node.parentElement;
                    }
                    return false;
                };
                const triggers = dlg.querySelectorAll(
                    'button[role="combobox"], button.dioa-select__trigger, [class*="dioa-select__trigger"]'
                );
                for (const btn of triggers) {
                    if (!isVisible(btn) || nearCreationTime(btn)) continue;
                    const text = norm(btn.innerText || btn.textContent);
                    if (styleOptions.includes(text)) return text;
                }
                for (const btn of triggers) {
                    if (!isVisible(btn) || nearCreationTime(btn)) continue;
                    const text = norm(btn.innerText || btn.textContent);
                    if (text && !/^20\\d{2}$/.test(text)) return text;
                }
                return '';
            }""",
            list(WORK_STYLE_OPTIONS),
        )
    ).strip()


def _work_style_is_set(page: Page, value: str) -> bool:
    current = _work_style_current(page)
    return current == value


def _find_work_style_trigger(page: Page) -> bool:
    """定位作品风格 combobox（button.dioa-select__trigger）并打标记。"""
    return bool(
        stable_evaluate(page,
            """(styleOptions) => {
                const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']")
                    || document.querySelector('section.dioa-dialog__content');
                if (!dlg) return false;
                document.querySelectorAll('[data-vjshi-style-trigger]').forEach((node) => {
                    node.removeAttribute('data-vjshi-style-trigger');
                });
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const st = getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const nearCreationTime = (el) => {
                    let node = el;
                    for (let i = 0; i < 10 && node; i++) {
                        const t = norm(node.textContent || '');
                        if (t.includes('创作时间') && t.length < 100) return true;
                        node = node.parentElement;
                    }
                    return false;
                };
                const triggers = [...dlg.querySelectorAll(
                    'button[role="combobox"], button.dioa-select__trigger, [class*="dioa-select__trigger"]'
                )].filter((btn) => isVisible(btn) && !nearCreationTime(btn));
                let chosen = null;
                for (const btn of triggers) {
                    const text = norm(btn.innerText || btn.textContent);
                    if (styleOptions.includes(text)) {
                        chosen = btn;
                        break;
                    }
                }
                if (!chosen && triggers.length) {
                    chosen = triggers[triggers.length - 1];
                }
                if (!chosen) return false;
                chosen.setAttribute('data-vjshi-style-trigger', '1');
                return true;
            }""",
            list(WORK_STYLE_OPTIONS),
        )
    )


def _open_work_style_dropdown(page: Page, dialog: Locator) -> bool:
    if not _find_work_style_trigger(page):
        triggers = dialog.locator(
            "button[role='combobox'], button.dioa-select__trigger"
        )
        if triggers.count() == 0:
            return False
        target = triggers.last
        try:
            target.scroll_into_view_if_needed()
            target.click(force=True)
        except Exception:
            return False
    else:
        marked = page.locator("[data-vjshi-style-trigger='1']")
        if marked.count() == 0:
            return False
        try:
            marked.first.scroll_into_view_if_needed()
            marked.first.click(force=True)
        except Exception:
            return False
    page.wait_for_timeout(600)
    return True


def _click_work_style_popover_option(page: Page, value: str) -> bool:
    """点击 portal 渲染的 .dioa-select__popover 选项。"""
    return bool(
        stable_evaluate(page,
            """(value) => {
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const st = getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const roots = document.querySelectorAll(
                    '.dioa-select__popover, .dioa-popover__positioner, [role="listbox"]'
                );
                for (const root of roots) {
                    if (!isVisible(root)) continue;
                    for (const el of root.querySelectorAll(
                        '[role="option"], .dioa-select__option, div, li, span'
                    )) {
                        let text = norm(el.textContent);
                        if (el.children.length === 1 && el.children[0].children.length === 0) {
                            text = norm(el.children[0].textContent);
                        }
                        if (text !== value) continue;
                        if (norm(el.textContent || '').length > 24) continue;
                        el.scrollIntoView({ block: 'nearest' });
                        el.click();
                        return true;
                    }
                }
                return false;
            }""",
            value,
        )
    )


def _set_work_style(
    page: Page, dialog: Locator, value: str, *, log
) -> None:
    """作品风格：点击 button.dioa-select__trigger，在 popover 中选「实拍写实」。"""
    if _work_style_is_set(page, value):
        log(f"  作品风格: {value}（已选中）")
        return

    if not _find_work_style_trigger(page):
        raise RuntimeError(
            "未找到「作品风格」下拉框（button.dioa-select__trigger）。"
        )

    for _ in range(3):
        if not _open_work_style_dropdown(page, dialog):
            continue

        page.wait_for_timeout(400)

        if _click_work_style_popover_option(page, value):
            page.wait_for_timeout(350)
            if _work_style_is_set(page, value):
                log(f"  作品风格: {value}")
                return

        for loc in (
            page.locator(".dioa-select__popover").get_by_text(value, exact=True),
            page.locator(".dioa-popover__positioner").get_by_text(value, exact=True),
            page.get_by_role("option", name=value, exact=True),
            page.locator(".dioa-select__option").filter(has_text=value),
            page.locator("[role='option']").filter(has_text=value),
        ):
            if loc.count() == 0:
                continue
            for i in range(loc.count()):
                item = loc.nth(i)
                try:
                    if not item.is_visible():
                        continue
                    item.click(force=True)
                    page.wait_for_timeout(350)
                    if _work_style_is_set(page, value):
                        log(f"  作品风格: {value}")
                        return
                except Exception:
                    continue

        page.wait_for_timeout(300)

    current = _work_style_current(page)
    raise RuntimeError(
        f"未能选中作品风格「{value}」"
        + (f"（当前显示: {current or '空'}）" if current else "")
    )


def _open_labeled_dropdown(page: Page, dialog: Locator, label: str) -> bool:
    """打开带标签的下拉框（作品风格等）。"""
    opened = stable_evaluate(page,
        """(label) => {
            const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']") || document.querySelector('section.dioa-dialog__content');
            if (!dlg) return false;
            const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            let input = null;
            for (const inp of dlg.querySelectorAll(
                'input[role="combobox"], input.dioa-input__field, button[role="combobox"]'
            )) {
                let node = inp;
                for (let i = 0; i < 14 && node; i++) {
                    const t = norm(node.textContent || '');
                    if (t.includes(label) && !t.includes('AI推荐')) {
                        input = inp;
                        break;
                    }
                    node = node.parentElement;
                }
                if (input) break;
            }
            if (!input) {
                for (const el of dlg.querySelectorAll('*')) {
                    const t = norm(el.textContent);
                    if (!t.includes(label) || t.length > 60) continue;
                    let box = el;
                    for (let i = 0; i < 14 && box; i++) {
                        const trigger = box.querySelector(
                            'button, input[role="combobox"], input.dioa-input__field, [class*="select"] button, [class*="select"] input'
                        );
                        if (trigger) {
                            input = trigger;
                            break;
                        }
                        box = box.parentElement;
                    }
                    if (input) break;
                }
            }
            if (!input) return false;
            input.scrollIntoView({ block: 'center' });
            input.focus();
            input.click();
            const wrap = input.closest('.dioa-select, [class*="select"]') || input;
            wrap.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            wrap.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            return true;
        }""",
        label,
    )
    if opened:
        page.wait_for_timeout(500)
    return bool(opened)


def _click_labeled_option(page: Page, value: str) -> bool:
    """在已展开的下拉中点击选项。"""
    return bool(
        stable_evaluate(page,
            """(value) => {
                const dialog = document.querySelector("section[data-vjshi-edit-dialog='1']") || document.querySelector('section.dioa-dialog__content');
                if (!dialog) return false;
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    if (!el) return false;
                    const st = getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2;
                };
                const dialogRect = dialog.getBoundingClientRect();
                const candidates = [];
                for (const el of document.querySelectorAll(
                    'div, li, span, button, [role="option"]'
                )) {
                    let text = norm(el.textContent);
                    if (el.children.length === 1 && el.children[0].children.length === 0) {
                        text = norm(el.children[0].textContent);
                    }
                    if (text !== value) continue;
                    if (!isVisible(el)) continue;
                    const r = el.getBoundingClientRect();
                    const cx = (dialogRect.left + dialogRect.right) / 2;
                    const cy = (dialogRect.top + dialogRect.bottom) / 2;
                    const mx = Math.abs((r.left + r.right) / 2 - cx);
                    const my = Math.abs((r.top + r.bottom) / 2 - cy);
                    if (mx > 420 || my > 520) continue;
                    let score = 0;
                    let p = el;
                    while (p) {
                        const cn = (p.className || '').toString();
                        if (/menu|popover|dropdown|select|option|listbox|float|portal|picker|virtual/i.test(cn)) {
                            score += 10;
                        }
                        p = p.parentElement;
                    }
                    if (el.tagName === 'INPUT') score -= 100;
                    score -= el.children.length;
                    candidates.push({ el, score, area: r.width * r.height });
                }
                if (!candidates.length) return false;
                candidates.sort((a, b) => b.score - a.score || a.area - b.area);
                candidates[0].el.scrollIntoView({ block: 'nearest' });
                candidates[0].el.click();
                return true;
            }""",
            value,
        )
    )


def _labeled_field_current(page: Page, label: str) -> str:
    return str(
        stable_evaluate(page,
            """(label) => {
                const dlg = document.querySelector("section[data-vjshi-edit-dialog='1']") || document.querySelector('section.dioa-dialog__content');
                if (!dlg) return '';
                const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                for (const el of dlg.querySelectorAll('*')) {
                    const t = norm(el.textContent);
                    if (!t.startsWith(label) && !t.includes(label)) continue;
                    if (t.length > 80) continue;
                    let box = el;
                    for (let i = 0; i < 12 && box; i++) {
                        const inp = box.querySelector(
                            'input[role="combobox"], input.dioa-input__field, button, [class*="select"] input'
                        );
                        if (inp) {
                            return norm(inp.value || inp.innerText || inp.textContent);
                        }
                        box = box.parentElement;
                    }
                }
                return '';
            }""",
            label,
        )
    ).strip()


def _select_dioa_option(
    page: Page, dialog: Locator, label: str, value: str, *, required: bool = True
) -> None:
    """点击带标签的下拉框并选中指定项（作品风格等）。"""
    current = _labeled_field_current(page, label)
    if value in current or current == value:
        return

    opened_once = False
    for _ in range(3):
        if _open_labeled_dropdown(page, dialog, label):
            opened_once = True
        else:
            # Playwright 备选定位
            row = dialog.locator(
                f"xpath=.//*[contains(normalize-space(),'{label}')]/ancestor::div[1]"
            )
            trigger = row.locator(
                "button, [role='combobox'], input, .dioa-select__trigger, [class*='select']"
            ).first
            if trigger.count() == 0:
                trigger = dialog.locator(
                    f"xpath=.//*[contains(normalize-space(),'{label}')]/following::*[self::button or @role='combobox' or self::input][1]"
                ).first
            if trigger.count() == 0:
                continue
            trigger.scroll_into_view_if_needed()
            trigger.click(force=True)
            opened_once = True
            page.wait_for_timeout(450)

        if _click_labeled_option(page, value):
            page.wait_for_timeout(300)
            current = _labeled_field_current(page, label)
            if value in current or current == value:
                return

        for loc in (
            page.get_by_role("option", name=value, exact=True),
            page.locator(".dioa-select__option").filter(has_text=value),
            page.locator("[class*='select__option']").filter(has_text=value),
            page.locator("[role='option']").filter(has_text=value),
            dialog.get_by_text(value, exact=True),
        ):
            if loc.count() == 0:
                continue
            for i in range(loc.count()):
                item = loc.nth(i)
                try:
                    if not item.is_visible():
                        continue
                    item.click(force=True)
                    page.wait_for_timeout(300)
                    current = _labeled_field_current(page, label)
                    if value in current or current == value:
                        return
                except Exception:
                    continue

    if not required:
        return
    current = _labeled_field_current(page, label)
    if not opened_once:
        raise RuntimeError(f"未找到「{label}」下拉框。")
    raise RuntimeError(
        f"未找到「{label}」选项: {value}"
        + (f"（当前显示: {current or '空'}）" if current else "")
    )
