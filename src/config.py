"""应用路径与内置配置（全部写死在代码中，改参数请编辑本文件后重新打包）。"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parent.parent

ROOT = APP_ROOT

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def resource_path(relative: str) -> Path:
    """打包后从 _MEIPASS 取资源，开发时从项目 assets/ 取。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", APP_ROOT))
    else:
        base = ASSETS_DIR.parent
    return base / relative


# 登录成功后生成在 exe 同目录的单个文件
LOGIN_FILENAME = "login.json"

# ---------------------------------------------------------------------------
# 内置默认参数（无需外部 settings.yaml）
# ---------------------------------------------------------------------------
UPLOAD_LIST_URL = "https://www.vjshi.com/user/upload/video"

BROWSER_HEADLESS = False
BROWSER_SLOW_MO = 80
BROWSER_TIMEOUT_MS = 30000
BROWSER_CHANNEL = "chrome"  # 本机 Google Chrome；留空则用 Playwright 自带 Chromium
BROWSER_REDUCE_AUTOMATION_FLAGS = True
BROWSER_NO_VIEWPORT = True

DELAY_BETWEEN_CLICKS_MS = 1500
PAUSE_BETWEEN_VIDEOS_SEC_MIN = 3
PAUSE_BETWEEN_VIDEOS_SEC_MAX = 6
SUBMIT_ENABLED = True
TEST_STOP_AFTER_SUBMIT = 0  # 0=连续提交直到列表处理完


def _build_settings() -> dict:
    return {
        "site": {"upload_list_url": UPLOAD_LIST_URL},
        "browser": {
            "headless": BROWSER_HEADLESS,
            "slow_mo": BROWSER_SLOW_MO,
            "timeout_ms": BROWSER_TIMEOUT_MS,
            "channel": BROWSER_CHANNEL,
            "reduce_automation_flags": BROWSER_REDUCE_AUTOMATION_FLAGS,
            "no_viewport": BROWSER_NO_VIEWPORT,
        },
        "auth": {"login_file": LOGIN_FILENAME},
        "actions": {
            "delay_between_clicks_ms": DELAY_BETWEEN_CLICKS_MS,
            "pause_between_videos_sec_min": PAUSE_BETWEEN_VIDEOS_SEC_MIN,
            "pause_between_videos_sec_max": PAUSE_BETWEEN_VIDEOS_SEC_MAX,
            "submit_enabled": SUBMIT_ENABLED,
            "test_stop_after_submit": TEST_STOP_AFTER_SUBMIT,
        },
    }


def init_app() -> None:
    """无需预建目录；登录成功后才会生成 login.json。"""
    return


def login_file_path() -> Path:
    return APP_ROOT / LOGIN_FILENAME


def setup_playwright_env() -> None:
    """使用本机 Chrome 时无需设置 PLAYWRIGHT_BROWSERS_PATH。"""
    import os

    if BROWSER_CHANNEL:
        return
    browsers_dir = APP_ROOT / "ms-playwright"
    browsers_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir))


def load_settings() -> dict:
    return copy.deepcopy(_build_settings())


def resolve_path(relative: str) -> Path:
    return APP_ROOT / relative
