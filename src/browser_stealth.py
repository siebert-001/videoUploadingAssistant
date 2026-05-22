"""降低浏览器自动化特征（无法保证绝对不被网站检测）。"""
from __future__ import annotations

from playwright.sync_api import BrowserContext

# 每个新页面注入，隐藏 navigator.webdriver 等常见特征
STEALTH_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined,
      configurable: true,
    });
  } catch (e) {}
  if (!window.chrome) {
    window.chrome = { runtime: {} };
  }
  try {
    Object.defineProperty(navigator, 'languages', {
      get: () => ['zh-CN', 'zh', 'en-US', 'en'],
      configurable: true,
    });
    Object.defineProperty(navigator, 'plugins', {
      get: () => [1, 2, 3, 4, 5],
      configurable: true,
    });
  } catch (e) {}
})();
"""

CHROME_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
]


def stealth_enabled(browser_cfg: dict) -> bool:
    return bool(browser_cfg.get("reduce_automation_flags", True))


def stealth_launch_kwargs(browser_cfg: dict) -> dict:
    """启动参数：去掉 --enable-automation，减弱 AutomationControlled。"""
    if not stealth_enabled(browser_cfg):
        return {}
    return {
        "ignore_default_args": ["--enable-automation"],
        "args": list(CHROME_STEALTH_ARGS),
    }


def apply_stealth(context: BrowserContext, *, browser_cfg: dict) -> None:
    if not stealth_enabled(browser_cfg):
        return
    context.add_init_script(STEALTH_INIT_SCRIPT)
