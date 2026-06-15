"""应用路径与内置配置（全部写死在代码中，改参数请编辑本文件后重新打包）。"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

# 用户数据目录名（macOS Application Support 等，使用 ASCII 避免路径问题）
APP_ID = "VjshiVideoTool"

if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent

# 兼容旧代码引用
APP_ROOT = BUNDLE_DIR
ROOT = BUNDLE_DIR

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

LOGIN_FILENAME = "login.json"


def _is_bundle_writable() -> bool:
    """Windows 单文件 exe 旁通常可写；macOS .app 内 MacOS 目录只读。"""
    if not getattr(sys, "frozen", False):
        return True
    if sys.platform == "darwin":
        exe = Path(sys.executable).resolve()
        if exe.parent.name == "MacOS" and ".app" in str(exe):
            return False
    try:
        probe = BUNDLE_DIR / ".write_probe"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    """
    可写数据目录：
    - 开发环境：项目根目录
    - Windows 打包：exe 同目录（可写时）
    - macOS .app / 只读位置：~/Library/Application Support/APP_ID
    """
    if not getattr(sys, "frozen", False):
        return BUNDLE_DIR
    if _is_bundle_writable():
        return BUNDLE_DIR
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_ID
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    path = base / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> Path:
    """打包后从 _MEIPASS 取资源，开发时从项目 assets/ 取。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", BUNDLE_DIR))
    else:
        base = ASSETS_DIR.parent
    return base / relative


# ---------------------------------------------------------------------------
# 内置默认参数（无需外部 settings.yaml）
# ---------------------------------------------------------------------------
UPLOAD_LIST_URL = "https://www.vjshi.com/user/upload/video"

BROWSER_HEADLESS = False
BROWSER_SLOW_MO = 0
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
        "actions": {
            "delay_between_clicks_ms": DELAY_BETWEEN_CLICKS_MS,
            "pause_between_videos_sec_min": PAUSE_BETWEEN_VIDEOS_SEC_MIN,
            "pause_between_videos_sec_max": PAUSE_BETWEEN_VIDEOS_SEC_MAX,
            "submit_enabled": SUBMIT_ENABLED,
            "test_stop_after_submit": TEST_STOP_AFTER_SUBMIT,
        },
    }


def init_app() -> None:
    if getattr(sys, "frozen", False):
        data_dir()


def login_file_path() -> Path:
    return data_dir() / LOGIN_FILENAME


def login_file_exists() -> bool:
    path = login_file_path()
    return path.is_file() and path.stat().st_size > 0


def clear_login_file() -> bool:
    """删除已保存的登录 cookie，下次启动需重新登录。"""
    path = login_file_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def setup_playwright_env() -> None:
    """使用本机 Chrome 时无需设置 PLAYWRIGHT_BROWSERS_PATH。"""
    import os

    if BROWSER_CHANNEL:
        return
    browsers_dir = data_dir() / "ms-playwright"
    browsers_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir))


def load_settings() -> dict:
    return copy.deepcopy(_build_settings())


def resolve_path(relative: str) -> Path:
    rel = relative.strip().replace("\\", "/")
    if rel in (LOGIN_FILENAME, f"auth/{LOGIN_FILENAME}"):
        return login_file_path()
    return data_dir() / rel
