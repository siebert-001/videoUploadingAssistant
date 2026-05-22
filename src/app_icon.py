"""窗口与任务栏图标。"""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon

from src.config import resource_path

_ICON_REL = "assets/icon.ico"
_WIN_APP_ID = "guangchang.video.uploader.1"


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_WIN_APP_ID)
    except Exception:
        pass


def load_app_icon() -> QIcon | None:
    path = resource_path(_ICON_REL)
    if not path.is_file():
        return None
    icon = QIcon(str(path))
    return icon if not icon.isNull() else None


def apply_app_icon(app) -> QIcon | None:
    """设置 QApplication 图标；Windows 下固定任务栏分组 ID。"""
    _set_windows_app_id()
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    return icon
