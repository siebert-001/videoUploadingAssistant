"""可视化操作界面（PySide6）。"""
from __future__ import annotations

import html
import queue
import re
import sys
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.app_icon import apply_app_icon, load_app_icon
from src.config import clear_login_file
from src.exceptions import AutomationCancelled
from src.field_settings import (
    DEFAULT_CREATION_TIME,
    VideoFieldSettings,
    load_field_settings,
    save_field_settings,
)
from src.runner import AutomationRunner, RunnerCallbacks

APP_TITLE = "光厂视频上架助手"

# 简洁配色
C_BG = "#f0f2f5"
C_SURFACE = "#ffffff"
C_PRIMARY = "#1677ff"
C_PRIMARY_H = "#4096ff"
C_PRIMARY_LIGHT = "#e6f4ff"
C_SUCCESS = "#52c41a"
C_SUCCESS_H = "#73d13d"
C_DANGER = "#ff4d4f"
C_DANGER_H = "#ff7875"
C_TEXT = "#1f1f1f"
C_LABEL = "#434343"
C_MUTED = "#8c8c8c"
C_BORDER = "#e8e8e8"
C_DIVIDER = "#f0f0f0"
C_RULES_BG = "#fafafa"

FONT_FAMILY = "Microsoft YaHei UI"
LABEL_W = 84
WIN_MIN_WIDTH = 420
LOG_VIEW_MIN_HEIGHT = 220

FINISH_MESSAGES = {
    "user_stop": "已停止。",
    "browser_closed": "浏览器已关闭，自动化已停止。",
    "completed": "全部处理完成，自动化已停止。",
}

BTN_LABELS = {
    "idle": "开始上架",
    "wait_login": "登录完成，继续上架",
    "running": "停止上架",
}

BTN_COLORS = {
    "idle": (C_PRIMARY, C_PRIMARY_H),
    "wait_login": (C_SUCCESS, C_SUCCESS_H),
    "running": (C_DANGER, C_DANGER_H),
}


def _stylesheet() -> str:
    f = FONT_FAMILY
    return f"""
    QMainWindow {{
        background: {C_BG};
    }}
    QWidget#contentCard {{
        background: {C_SURFACE};
        border-radius: 12px;
    }}
    QWidget#hintBanner {{
        background: {C_PRIMARY_LIGHT};
        border-radius: 8px;
    }}
    QLabel#hintText {{
        font-size: 12px;
        color: {C_LABEL};
        line-height: 1.5;
        background: transparent;
    }}
    QLabel.fieldLabel {{
        color: {C_LABEL};
        font-size: 13px;
        background: transparent;
    }}
    QLabel#sectionTitle {{
        color: {C_TEXT};
        font-size: 14px;
        font-weight: 600;
        padding-left: 10px;
        border-left: 3px solid {C_PRIMARY};
        background: transparent;
    }}
    QLabel.fieldHint {{
        color: {C_MUTED};
        font-size: 12px;
        line-height: 1.55;
        background: transparent;
    }}
    QLabel.unitLabel {{
        color: {C_MUTED};
        font-size: 13px;
        background: transparent;
    }}
    QWidget#rulesCard {{
        background: {C_RULES_BG};
        border: 1px solid {C_DIVIDER};
        border-radius: 8px;
    }}
    QWidget#tabPanel {{
        background: transparent;
    }}
    QWidget#tabBarRow {{
        background: transparent;
    }}
    QFrame#tabBarLine {{
        background: {C_BORDER};
        max-height: 1px;
    }}
    QStackedWidget#tabContent {{
        background: transparent;
    }}
    QLineEdit {{
        font-family: "{f}";
        font-size: 14px;
        color: {C_TEXT};
        background: {C_SURFACE};
        border: 1px solid {C_BORDER};
        border-radius: 6px;
        padding: 8px 12px;
        min-height: 22px;
    }}
    QLineEdit:focus {{
        border: 1px solid {C_PRIMARY};
    }}
    QTextEdit#logView {{
        font-family: Consolas, "{f}", monospace;
        font-size: 12px;
        color: {C_TEXT};
        background: {C_RULES_BG};
        border: none;
        border-radius: 8px;
        padding: 4px;
    }}
    QPushButton#secondaryBtn {{
        font-family: "{f}";
        font-size: 14px;
        font-weight: 500;
        color: {C_LABEL};
        background: {C_SURFACE};
        border: 1px solid {C_BORDER};
        border-radius: 8px;
        padding: 10px 20px;
        min-height: 22px;
    }}
    QPushButton#secondaryBtn:hover {{
        color: {C_DANGER};
        border-color: {C_DANGER};
        background: #fff1f0;
    }}
    QPushButton#primaryBtn {{
        font-family: "{f}";
        font-size: 15px;
        font-weight: 600;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 20px;
        min-height: 24px;
    }}
    """


def _tab_btn_qss(active: bool) -> str:
    f = FONT_FAMILY
    if active:
        return f"""
        QPushButton#tabBtn {{
            font-family: "{f}";
            font-size: 14px;
            font-weight: 600;
            color: {C_PRIMARY};
            background: transparent;
            border: none;
            padding: 10px 4px;
        }}
        """
    return f"""
    QPushButton#tabBtn {{
        font-family: "{f}";
        font-size: 14px;
        color: {C_MUTED};
        background: transparent;
        border: none;
        padding: 10px 4px;
    }}
    QPushButton#tabBtn:hover {{
        color: {C_TEXT};
    }}
    """


class CardTabWidget(QWidget):
    """下划线式标签页。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tabPanel")
        self._index = 0
        self._buttons: list[QPushButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tab_bar = QWidget()
        self._tab_bar.setObjectName("tabBarRow")
        bar_layout = QHBoxLayout(self._tab_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(28)
        self._btn_layout = bar_layout

        line = QFrame()
        line.setObjectName("tabBarLine")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)

        self._stack = QStackedWidget()
        self._stack.setObjectName("tabContent")

        outer.addWidget(self._tab_bar)
        outer.addWidget(line)
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        outer.addWidget(self._stack, stretch=0)

    def addTab(self, widget: QWidget, label: str) -> int:
        wrap = QWidget()
        wrap_lay = QVBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 18, 0, 4)
        wrap_lay.setSpacing(0)
        wrap_lay.addWidget(widget)

        idx = self._stack.count()
        self._stack.addWidget(wrap)

        btn = QPushButton(label)
        btn.setObjectName("tabBtn")
        btn.setFlat(True)
        btn.setMinimumWidth(72)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, i=idx: self.setCurrentIndex(i))
        self._btn_layout.addWidget(btn)
        self._buttons.append(btn)
        if idx == 0:
            self._apply_tab_styles(0)
        return idx

    def setCurrentIndex(self, index: int) -> None:
        if index < 0 or index >= self._stack.count():
            return
        self._index = index
        self._stack.setCurrentIndex(index)
        self._apply_tab_styles(index)

    def currentIndex(self) -> int:
        return self._index

    def _apply_tab_styles(self, active: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(_tab_btn_qss(i == active))


def _btn_qss(bg: str, hover: str) -> str:
    return f"""
    QPushButton#primaryBtn {{
        background-color: {bg};
    }}
    QPushButton#primaryBtn:hover {{
        background-color: {hover};
    }}
    """


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("class", "fieldLabel")
    lbl.setFixedWidth(LABEL_W)
    lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
    )
    return lbl


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionTitle")
    return lbl


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("class", "fieldHint")
    lbl.setWordWrap(True)
    return lbl


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        icon = load_app_icon()
        if icon is not None:
            self.setWindowIcon(icon)
        self.setMinimumWidth(WIN_MIN_WIDTH)
        self._tab_log_index = 1

        self._cancel_flag = threading.Event()
        self._login_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._runner: AutomationRunner | None = None
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._ui_queue: queue.Queue[str] = queue.Queue()
        self._btn_state = "idle"
        self._stopping = False
        self._finish_signal_sent = False
        self._loading_settings = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_now)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_queues)

        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._watch_automation)

        self._build_ui()
        self._load_settings_to_ui()
        self._bind_autosave()

        self._poll_timer.start(100)
        self._tabs._stack.currentChanged.connect(self._on_tab_changed)
        QTimer.singleShot(0, self._fit_window_to_content)

    def _on_tab_changed(self, index: int) -> None:
        if index == self._tab_log_index:
            self._log_text.setMinimumHeight(LOG_VIEW_MIN_HEIGHT)
        else:
            self._log_text.setMinimumHeight(0)
        self._fit_window_to_content()

    def _fit_window_to_content(self) -> None:
        self.adjustSize()
        hint = self.sizeHint()
        w = max(WIN_MIN_WIDTH, hint.width())
        h = hint.height()
        self.setMinimumHeight(h)
        self.resize(w, h)

    def _build_ui(self) -> None:
        outer = QWidget()
        outer.setStyleSheet(f"background: {C_BG};")
        self.setCentralWidget(outer)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(0)

        card = QWidget()
        card.setObjectName("contentCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        self._tabs = CardTabWidget()
        card_layout.addWidget(self._tabs, stretch=0)

        # --- 视频信息 ---
        form_w = QWidget()
        form_layout = QVBoxLayout(form_w)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(16)

        form_layout.addWidget(_section_title("本地设置"))

        local_grid = QGridLayout()
        local_grid.setHorizontalSpacing(12)
        local_grid.setVerticalSpacing(12)
        local_grid.setColumnStretch(1, 1)
        local_grid.setColumnMinimumWidth(0, LABEL_W)

        self._edit_price = QLineEdit()
        self._edit_price.setPlaceholderText("80")
        self._edit_price.setMaximumWidth(100)
        unit = QLabel("元")
        unit.setProperty("class", "unitLabel")
        price_row = QHBoxLayout()
        price_row.setSpacing(8)
        price_row.addWidget(self._edit_price)
        price_row.addWidget(unit)
        price_row.addStretch()
        local_grid.addWidget(_label("个人授权价"), 0, 0, Qt.AlignmentFlag.AlignVCenter)
        local_grid.addLayout(price_row, 0, 1)

        self._edit_creation_time = QLineEdit()
        self._edit_creation_time.setPlaceholderText(DEFAULT_CREATION_TIME)
        self._edit_creation_time.setMaximumWidth(100)
        time_hint = _hint("需与页面上「创作时间」下拉选项一致")
        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self._edit_creation_time)
        time_row.addWidget(time_hint, stretch=1)
        local_grid.addWidget(_label("创作时间"), 1, 0, Qt.AlignmentFlag.AlignVCenter)
        local_grid.addLayout(time_row, 1, 1)
        form_layout.addLayout(local_grid)

        form_layout.addWidget(_section_title("页面自动填写（无需配置）"))

        rules_card = QWidget()
        rules_card.setObjectName("rulesCard")
        rules_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rules_layout = QVBoxLayout(rules_card)
        rules_layout.setContentsMargins(0, 10, 0, 10)
        rules_layout.setSpacing(0)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, LABEL_W)

        row = 0
        grid.addWidget(_label("标题"), row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(_hint("从「AI推荐标题」随机选 1 个"), row, 1)
        row += 1

        grid.addWidget(_label("关键词"), row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(
            _hint(
                "随机 5–10 个：从「AI推荐关键词」随机选取（不足则全选）\n"
                "任一关键词不得包含「循环」\n"
                "无 AI 推荐标题或关键词时跳过并标注"
            ),
            row,
            1,
        )
        row += 1

        grid.addWidget(_label("标签"), row, 0)
        grid.addWidget(_hint("固定勾选「含AI内容」"), row, 1)
        row += 1

        grid.addWidget(_label("作品风格"), row, 0)
        grid.addWidget(_hint("固定选择「实拍写实」"), row, 1)

        rules_layout.addLayout(grid)
        form_layout.addWidget(rules_card)
        self._tabs.addTab(form_w, "视频信息")

        self._log_text = QTextEdit()
        self._log_text.setObjectName("logView")
        self._log_text.setReadOnly(True)
        self._log_text.setPlaceholderText("运行日志将显示在这里…")
        self._log_text.setMinimumHeight(0)
        self._log_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self._tabs.addTab(self._log_text, "运行日志")

        self._btn_clear_login = QPushButton("清除登录")
        self._btn_clear_login.setObjectName("secondaryBtn")
        self._btn_clear_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear_login.setToolTip("删除已保存的登录信息，下次启动需重新登录")
        self._btn_clear_login.clicked.connect(self._on_clear_login)

        self._btn_main = QPushButton("开始上架")
        self._btn_main.setObjectName("primaryBtn")
        self._btn_main.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_main.clicked.connect(self._on_main_button)
        self._set_btn_state("idle")

        btn_col = QVBoxLayout()
        btn_col.setSpacing(10)
        btn_col.addWidget(self._btn_clear_login)
        btn_col.addWidget(self._btn_main)
        card_layout.addLayout(btn_col)

        outer_layout.addWidget(card)

    def _set_btn_state(self, state: str) -> None:
        self._btn_state = state
        bg, hover = BTN_COLORS[state]
        self._btn_main.setText(BTN_LABELS[state])
        self._btn_main.setStyleSheet(_btn_qss(bg, hover))
        if state == "idle" and self._watch_timer.isActive():
            self._watch_timer.stop()

    def _on_clear_login(self) -> None:
        if self._btn_state != "idle":
            QMessageBox.warning(self, "提示", "请先停止上架，再清除登录。")
            return
        if clear_login_file():
            QMessageBox.information(self, "提示", "已清除保存的登录信息，下次启动需重新登录。")
        else:
            QMessageBox.information(self, "提示", "当前没有保存的登录信息。")

    def _bind_autosave(self) -> None:
        self._edit_price.textChanged.connect(self._schedule_autosave)
        self._edit_creation_time.textChanged.connect(self._schedule_autosave)

    def _schedule_autosave(self) -> None:
        if self._loading_settings:
            return
        self._autosave_timer.start(500)

    def _autosave_now(self) -> None:
        if self._loading_settings:
            return
        try:
            save_field_settings(self._collect_field_settings())
        except Exception:
            pass

    def _collect_field_settings(self) -> VideoFieldSettings:
        try:
            price = int(self._edit_price.text().strip())
        except ValueError:
            price = 80
        creation_time = self._edit_creation_time.text().strip() or DEFAULT_CREATION_TIME
        return VideoFieldSettings(
            personal_price=price,
            creation_time=creation_time,
        )

    def _load_settings_to_ui(self) -> None:
        self._loading_settings = True
        s = load_field_settings()
        self._edit_price.setText(str(s.personal_price))
        self._edit_creation_time.setText(s.creation_time)
        self._loading_settings = False

    def _log_color(self, msg: str) -> str:
        if re.search(r"填写第\s*\d+\s*个视频信息", msg):
            return C_PRIMARY
        if re.search(r"第\s*\d+\s*个视频信息已提交", msg):
            return C_SUCCESS
        if "已跳过" in msg or "跳过" in msg:
            return C_MUTED
        if "失败" in msg or "出错" in msg or "中断" in msg:
            return C_DANGER
        if "已无待上架" in msg or "全部处理完成" in msg:
            return C_SUCCESS
        if msg.startswith("待处理") or msg.startswith("正在"):
            return C_MUTED
        if msg in FINISH_MESSAGES.values():
            return C_SUCCESS if "完成" in msg else C_MUTED
        return C_TEXT

    def _append_log(self, msg: str) -> None:
        color = self._log_color(msg)
        line = (
            f'<p style="margin:0 0 6px 0;color:{color};">'
            f"{html.escape(msg)}</p>"
        )
        self._log_text.append(line)
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _poll_queues(self) -> None:
        try:
            while True:
                self._append_log(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                action = self._ui_queue.get_nowait()
                if action == "wait_login":
                    if self._runner and self._runner.browser_was_closed():
                        continue
                    if self._cancel_flag.is_set():
                        continue
                    self._set_btn_state("wait_login")
                elif action == "listing_started":
                    self._set_btn_state("running")
                    self._tabs.setCurrentIndex(1)
                elif action in FINISH_MESSAGES:
                    self._reset_automation_ui(action)
                elif action.startswith("error:"):
                    QMessageBox.critical(self, "运行失败", action[6:])
                    self._reset_automation_ui()
        except queue.Empty:
            pass

    def _log(self, msg: str) -> None:
        self._log_queue.put(msg)

    def _on_automation_finished(self, reason: str) -> None:
        self._cancel_flag.set()
        self._login_event.set()
        if not self._finish_signal_sent:
            self._finish_signal_sent = True
        self._ui_queue.put(reason)

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                self._ui_queue.get_nowait()
            except queue.Empty:
                break

    def _reset_automation_ui(self, reason: str | None = None) -> None:
        was_active = self._btn_state != "idle"
        self._cancel_flag.set()
        self._login_event.set()
        self._stopping = False
        if not self._finish_signal_sent:
            self._finish_signal_sent = True
        if reason and reason in FINISH_MESSAGES and was_active:
            self._append_log(FINISH_MESSAGES[reason])
        self._drain_ui_queue()
        self._set_btn_state("idle")

    def _automation_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _detect_browser_gone_main_thread(self) -> bool:
        if not self._runner:
            return False
        if self._runner.browser_was_closed():
            return True
        if not AutomationRunner.browser_process_alive(self._runner.browser_pid):
            self._runner.note_browser_closed()
            return True
        return False

    def _watch_automation(self) -> None:
        if not self._automation_running():
            self._watch_timer.stop()
            return
        if self._detect_browser_gone_main_thread():
            self._reset_automation_ui("browser_closed")

    def _on_waiting_login(self) -> None:
        self._ui_queue.put("wait_login")

    def _on_listing_started(self) -> None:
        self._ui_queue.put("listing_started")

    def _wait_login_confirm(self) -> None:
        self._on_waiting_login()
        self._login_event.clear()
        while True:
            if self._cancel_flag.is_set() or (
                self._runner and self._runner.browser_was_closed()
            ):
                if self._runner and self._runner.browser_was_closed():
                    self._on_automation_finished("browser_closed")
                return
            if self._login_event.is_set():
                break
            if self._runner and self._runner.pump_wait(150):
                return

    def _on_main_button(self) -> None:
        if self._btn_state == "idle":
            self._begin_listing()
        elif self._btn_state == "wait_login":
            self._login_event.set()
        elif self._btn_state == "running":
            self._stop_listing()

    def _validate_settings(self) -> VideoFieldSettings | None:
        self._autosave_now()
        settings = self._collect_field_settings()
        if not self._edit_creation_time.text().strip():
            QMessageBox.warning(
                self,
                "提示",
                "请填写创作时间（需与页面上拉选项一致，例如 2026）。",
            )
            return None
        return settings

    def _begin_listing(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        settings = self._validate_settings()
        if not settings:
            return

        self._cancel_flag.clear()
        self._login_event.clear()
        self._stopping = False
        self._finish_signal_sent = False
        self._tabs.setCurrentIndex(1)
        self._log("正在启动…")

        callbacks = RunnerCallbacks(
            on_log=self._log,
            wait_login_confirm=self._wait_login_confirm,
            is_cancelled=lambda: (
                self._cancel_flag.is_set()
                or (self._runner is not None and self._runner.browser_was_closed())
            ),
            on_automation_finished=self._on_automation_finished,
            on_listing_started=self._on_listing_started,
        )
        self._runner = AutomationRunner(callbacks, field_settings=settings)

        def task() -> None:
            try:
                self._runner.run()
            except AutomationCancelled:
                pass
            except Exception as e:
                if not self._cancel_flag.is_set():
                    self._ui_queue.put(f"error:{e}")

        self._worker = threading.Thread(target=task, daemon=True)
        self._worker.start()
        self._watch_timer.start(120)

    def _stop_listing(self) -> None:
        if self._btn_state != "running" or self._stopping:
            return
        self._stopping = True
        if self._runner:
            self._runner.mark_user_stop()
            self._runner.close_browser()
        self._reset_automation_ui("user_stop")


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    apply_app_icon(app)
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
