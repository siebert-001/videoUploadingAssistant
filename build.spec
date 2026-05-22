# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 单文件 exe（使用本机 Chrome，无需自带 Chromium）。"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")

_icon = ROOT / "assets" / "icon.ico"
datas = list(playwright_datas)
if _icon.is_file():
    datas.append((str(_icon), "assets"))

hiddenimports = [
    "src",
    "src.gui",
    "src.runner",
    "src.auth",
    "src.browser_stealth",
    "src.config",
    "src.form_filler",
    "src.upload_list",
    "src.field_settings",
    "src.exceptions",
    "src.app_icon",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
] + playwright_hiddenimports

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=playwright_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtQuick",
        "PySide6.QtQml",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="光厂视频上架助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
    icon=str(_icon) if _icon.is_file() else None,
)
