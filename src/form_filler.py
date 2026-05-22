"""填写「视频编辑」弹窗中的表单信息（标题从 AI 推荐随机选取）。"""
from __future__ import annotations

import random
import re

from playwright.sync_api import Locator, Page

from src.field_settings import VideoFieldSettings

DIALOG_SELECTOR = "section.dioa-dialog__content"
KEYWORDS_COUNT_MIN = 5
KEYWORDS_COUNT_MAX = 10
KEYWORDS_EXCLUDED_SUBSTR = "循环"
CREATION_TIME_PLACEHOLDER = "正确的创作时间"
WORK_STYLE = "实拍写实"


def _dialog(page: Page) -> Locator:
    return page.locator(DIALOG_SELECTOR)


def _is_edit_dialog_open(page: Page) -> bool:
    dialog = page.locator(DIALOG_SELECTOR)
    return dialog.count() > 0 and dialog.first.is_visible()


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
    locator.click()
    locator.fill("")
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(100)


def _clear_title_field(page: Page, dialog: Locator, *, log) -> None:
    """清空标题输入框（弹窗可能带上一条视频的旧标题）。"""
    title_input = dialog.locator(
        "xpath=.//*[contains(text(),'标题准确') or contains(text(),'标题')]"
        f"/ancestor::div[1]//input[contains(@class,'dioa-input__field')][1]"
    )
    if title_input.count() == 0:
        title_input = dialog.locator("input.dioa-input__field").first
    if title_input.count() == 0:
        return
    _clear_input(title_input.first, page)
    log("  标题: 已清空")


def _keywords_field_root(dialog: Locator) -> Locator:
    """关键词输入区（锚定 textarea 父级，避免误选整个弹窗）。"""
    inp = dialog.locator(
        "xpath=.//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/ancestor::div[1]//textarea[1]"
    )
    if inp.count() > 0:
        root = inp.first.locator(
            "xpath=ancestor::div[contains(@class,'grid') or contains(@class,'flex')][1]"
        )
        if root.count() > 0:
            return root.first
    root = dialog.locator(
        "xpath=.//*[contains(normalize-space(),'关键词找素材')]"
        "/ancestor::div[contains(@class,'grid') or contains(@class,'flex')][1]"
    )
    if root.count() > 0:
        return root.first
    narrow = dialog.locator(
        "xpath=.//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/ancestor::div[1]"
    )
    if narrow.count() > 0:
        return narrow.first
    return dialog.first


def _keywords_input(dialog: Locator) -> Locator:
    root = _keywords_field_root(dialog)
    for sel in ("textarea", "input:not([type='hidden'])", "[contenteditable='true']"):
        inp = root.locator(sel).first
        if inp.count() > 0:
            return inp
    return dialog.locator(
        "xpath=.//*[contains(text(),'关键词') and not(contains(text(),'AI推荐'))]"
        "/ancestor::div[1]//textarea[1]"
    ).first


def _keywords_textarea(dialog: Locator) -> Locator:
    return _keywords_input(dialog)


def _keyword_count_from_counter(dialog: Locator) -> int | None:
    """读取页面「N/30个」计数（比 textarea 更准，含缓存标签）。"""
    root = _keywords_field_root(dialog)
    counters = root.locator("xpath=.//*[contains(text(),'/30')]")
    if counters.count() == 0:
        counters = dialog.locator("xpath=.//*[contains(text(),'/30个')]")
    for i in range(counters.count()):
        text = counters.nth(i).inner_text().strip()
        m = re.search(r"(\d+)\s*/\s*30\s*个", text)
        if m:
            return int(m.group(1))
    return None


def _get_keywords_list(dialog: Locator) -> list[str]:
    inp = _keywords_input(dialog)
    if inp.count() > 0:
        try:
            text = inp.input_value().strip()
        except Exception:
            text = inp.inner_text().strip()
        if text:
            return [w for w in text.split() if w.strip()]

    root = _keywords_field_root(dialog)
    chips = root.locator(
        "xpath=.//*[contains(@class,'tag') or contains(@class,'chip')]"
        "[not(ancestor::*[contains(text(),'AI推荐关键词')])]"
    )
    words: list[str] = []
    for i in range(chips.count()):
        t = chips.nth(i).inner_text().strip()
        if t and t not in words:
            words.append(t)
    return words


def _keyword_count(dialog: Locator) -> int:
    counter = _keyword_count_from_counter(dialog)
    textarea_n = len(_get_keywords_list(dialog))
    if counter is not None:
        return max(counter, textarea_n)
    return textarea_n


def _count_keywords_in_textarea(dialog: Locator) -> int:
    return _keyword_count(dialog)


def _clear_keywords_via_keyboard(page: Page, dialog: Locator, inp: Locator) -> None:
    """用键盘逐个删词，不点击任何 close 按钮（避免关掉整个编辑弹窗）。"""
    for _ in range(40):
        _ensure_edit_dialog_open(page)
        if _keyword_count(dialog) == 0:
            return
        inp.click(force=True)
        page.wait_for_timeout(60)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(80)

    inp.click(force=True)
    page.wait_for_timeout(60)
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(80)
    try:
        inp.fill("")
    except Exception:
        pass
    inp.evaluate(
        """(el) => {
            if ('value' in el) el.value = '';
            else el.textContent = '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )
    page.wait_for_timeout(120)


def _clear_keywords_field(page: Page, dialog: Locator, *, log) -> None:
    """强制清空关键词区（含上次编辑缓存的标签）。"""
    _ensure_edit_dialog_open(page)
    cached = _keyword_count(dialog)
    if cached > 0:
        log(f"  关键词: 检测到缓存 {cached} 个，正在清空…")

    inp = _keywords_input(dialog)
    if inp.count() == 0:
        raise RuntimeError("未找到关键词输入框，无法清空缓存。")

    _clear_keywords_via_keyboard(page, dialog, inp)

    remaining = _keyword_count(dialog)
    if remaining > 0:
        raise RuntimeError(
            f"无法清空关键词缓存，仍有 {remaining} 个（页面计数/输入框未归零）"
        )
    log("  关键词: 已清空")


def _is_keyword_allowed(word: str) -> bool:
    return bool(word.strip()) and KEYWORDS_EXCLUDED_SUBSTR not in word


def _remove_one_keyword_chip(page: Page, dialog: Locator) -> bool:
    """移除关键词区最后一个已选词（仅用键盘，避免误关弹窗）。"""
    _ensure_edit_dialog_open(page)
    inp = _keywords_input(dialog)
    if inp.count() > 0:
        before = _keyword_count(dialog)
        inp.click(force=True)
        page.wait_for_timeout(60)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(100)
        if _keyword_count(dialog) < before:
            return True

    area = _keywords_textarea(dialog)
    if area.count() == 0:
        return False
    text = area.first.input_value().strip()
    parts = [w for w in text.split() if w.strip()]
    if len(parts) <= 1:
        _clear_input(area.first, page)
        return len(parts) > 0
    area.first.fill(" ".join(parts[:-1]))
    page.wait_for_timeout(100)
    return True


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


def _trim_keywords_to_exact(page: Page, dialog: Locator, *, exact: int) -> None:
    """关键词多于 exact 时从末尾删减。"""
    for _ in range(30):
        n = _keyword_count(dialog)
        if n <= exact:
            return
        if not _remove_one_keyword_chip(page, dialog):
            raise RuntimeError(f"关键词仍有 {n} 个，无法缩减到 {exact} 个。")
    n = _keyword_count(dialog)
    if n > exact:
        raise RuntimeError(f"关键词仍有 {n} 个，无法缩减到 {exact} 个。")


def _get_eligible_ai_keyword_buttons(
    dialog: Locator,
) -> list[tuple[str, Locator]]:
    container = dialog.locator(
        "xpath=.//*[contains(text(),'AI推荐关键词')]/following::div[contains(@class,'flex')][1]"
    )
    if container.count() == 0:
        container = dialog.locator(
            "xpath=.//*[contains(text(),'AI推荐关键词')]/parent::*/following-sibling::div[1]"
        )
    buttons = container.locator("button")
    buttons.first.wait_for(state="visible", timeout=10000)

    eligible: list[tuple[str, Locator]] = []
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        text = btn.inner_text().strip()
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
                f"AI推荐关键词可选项不足（需 {target} 个、已排除含「{KEYWORDS_EXCLUDED_SUBSTR}」），"
                f"当前已有 {len(current)} 个: {'、'.join(current) or '无'}"
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
    """规则：随机 5–10 个，且任一关键词不得包含「循环」。"""
    target = random.randint(KEYWORDS_COUNT_MIN, KEYWORDS_COUNT_MAX)
    log(f"  关键词: 本次随机选取 {target} 个")
    _clear_keywords_field(page, dialog, log=log)
    if _keyword_count(dialog) != 0:
        raise RuntimeError("关键词清空后仍有残留，无法继续填写。")
    eligible = _get_eligible_ai_keyword_buttons(dialog)
    if len(eligible) < target:
        raise RuntimeError(
            f"AI推荐关键词可选项不足 {target} 个（已排除含「{KEYWORDS_EXCLUDED_SUBSTR}」的项，"
            f"当前可选 {len(eligible)} 个）"
        )

    _click_ai_keyword_if_needed(page, dialog, eligible, target=target)
    _remove_forbidden_keywords(page, dialog)
    _trim_keywords_to_exact(page, dialog, exact=target)
    return _validate_keywords_final(dialog, expected=target, log=log)


def fill_video_form(page: Page, settings: VideoFieldSettings, *, on_log=None) -> None:
    dialog = _dialog(page)
    dialog.wait_for(state="visible")
    page.wait_for_timeout(300)
    _ensure_edit_dialog_open(page)

    log = on_log or (lambda _m: None)

    # 弹窗打开时先清掉上次缓存的关键词
    if _keyword_count(dialog) > 0:
        _clear_keywords_field(page, dialog, log=log)
        _ensure_edit_dialog_open(page)

    _clear_title_field(page, dialog, log=log)

    # 1. 标题：从「AI推荐标题」中随机点选（可能触发页面自动填关键词）
    _select_random_ai_title(page, dialog, log=log)

    # 2. 创作时间：按界面配置选择
    _set_creation_time(page, dialog, settings.creation_time, log=log)

    # 3. 关键词：随机 5–10 个，不得含「循环」
    _fill_keywords(page, dialog, log=log)

    # 4. 个人授权价：填入界面设置的价格
    _fill_personal_price(dialog, settings.personal_price, log=log)

    # 5. 作品风格：固定选「实拍写实」
    _select_dioa_option(page, dialog, "作品风格", WORK_STYLE)
    log(f"  作品风格: {WORK_STYLE}")

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
        label.evaluate(
            """(el) => {
                const id = el.getAttribute('for');
                const input = id
                    ? document.getElementById(id)
                    : el.querySelector('input[type="checkbox"]');
                return !!(input && input.checked);
            }"""
        )
    )


def _click_ai_content_checkbox(dialog: Locator, label: Locator) -> None:
    """用 JS 触发 dioa 复选框（Playwright 普通 click 对此组件常无效）。"""
    label.evaluate(
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
        }"""
    )
    inp = _checkbox_input_for_label(dialog, label)
    if inp is not None:
        try:
            if not inp.is_checked():
                inp.evaluate(
                    """(el) => {
                        el.checked = true;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }"""
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
    container = dialog.locator(
        "xpath=.//*[contains(text(),'AI推荐标题')]/following::div[contains(@class,'flex')][1]"
    )
    if container.count() == 0:
        container = dialog.locator(
            "xpath=.//*[contains(text(),'AI推荐标题')]/parent::*/following-sibling::div[1]"
        )
    buttons = container.locator("button")
    buttons.first.wait_for(state="visible", timeout=10000)
    count = buttons.count()
    if count == 0:
        raise RuntimeError("未找到 AI 推荐标题选项，请确认弹窗已加载。")
    chosen = buttons.nth(random.randrange(count))
    title = chosen.inner_text().strip()
    chosen.click(force=True)
    page.wait_for_timeout(300)
    log(f"  标题(AI推荐): {title}")
    return title


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


def _creation_time_is_set(dialog: Locator, value: str) -> bool:
    inp = _creation_time_input(dialog)
    if inp.count() == 0:
        return False
    current = inp.input_value().strip()
    if not current or CREATION_TIME_PLACEHOLDER in current:
        return False
    return current == value or value in current


def _select_creation_time_option(page: Page, value: str) -> None:
    """创作时间为 combobox + 弹出年份列表，必须点击选项。"""
    option = page.get_by_role("option", name=value, exact=True)
    if option.count() == 0:
        option = page.locator("div.dioa-select__option").filter(has_text=value)
    if option.count() == 0:
        option = page.locator(f"div[role='option']:has-text('{value}')")
    if option.count() == 0:
        raise RuntimeError(f"未找到创作时间选项: {value}")
    option.first.click(force=True)


def _set_creation_time(
    page: Page, dialog: Locator, value: str, *, log
) -> None:
    """按配置的创作时间打开下拉并点击对应选项。"""
    value = value.strip()
    if not value:
        raise RuntimeError("创作时间为空，请在界面「本地设置」中填写。")
    inp = _creation_time_input(dialog)
    if inp.count() == 0:
        raise RuntimeError("未找到「创作时间」下拉框。")

    if _creation_time_is_set(dialog, value):
        log(f"  创作时间: {value}（已是目标值）")
        return

    inp.scroll_into_view_if_needed()
    inp.click(force=True)
    page.wait_for_timeout(400)
    _select_creation_time_option(page, value)
    page.wait_for_timeout(300)

    if not _creation_time_is_set(dialog, value):
        inp.click(force=True)
        page.wait_for_timeout(400)
        _select_creation_time_option(page, value)
        page.wait_for_timeout(300)

    if not _creation_time_is_set(dialog, value):
        current = inp.input_value().strip()
        raise RuntimeError(
            f"创作时间未选中 {value}（当前显示: {current or '空/占位符'}）"
        )

    log(f"  创作时间: {value}")


def _select_dioa_option(
    page: Page, dialog: Locator, label: str, value: str, *, required: bool = True
) -> None:
    """点击 dioa 下拉（创作时间、作品风格等），选中指定项。"""
    row = dialog.locator(
        f"xpath=.//*[contains(text(),'{label}')]/ancestor::div[1]"
    )
    trigger = row.locator(
        "button, [role='combobox'], input, .dioa-select__trigger"
    ).first
    if trigger.count() == 0:
        trigger = dialog.locator(
            f"xpath=.//*[contains(text(),'{label}')]/following::button[1]"
        ).first
    if trigger.count() == 0:
        raise RuntimeError(f"未找到「{label}」下拉框。")

    trigger.click(force=True)
    page.wait_for_timeout(400)

    option = page.get_by_role("option", name=value, exact=True)
    if option.count() == 0:
        option = page.locator("div.dioa-select__option", has_text=value)
    if option.count() == 0:
        option = page.locator("div[role='option']", has_text=value)
    if option.count() == 0:
        option = dialog.get_by_text(value, exact=True)
    if option.count() == 0:
        if not required:
            return
        raise RuntimeError(f"未找到「{label}」选项: {value}")
    option.first.click(force=True)
    page.wait_for_timeout(200)
