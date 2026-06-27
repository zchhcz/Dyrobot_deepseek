"""Settings page — form-based config.yaml editor."""

from pathlib import Path
import yaml
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

DEFAULT_CONFIG_PATH = "config.yaml"


class SettingsPage(QWidget):
    """Config editor page. Changes are written to config.yaml on save."""

    config_saved = pyqtSignal()

    def __init__(self, config: dict, config_path: str = DEFAULT_CONFIG_PATH, parent=None):
        super().__init__(parent)
        self._config = config
        self._config_path = Path(config_path)
        self._modified = False
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        # Main layout with scroll
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # ── Header ──
        header_row = QHBoxLayout()
        title = QLabel("配置设置")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        header_row.addWidget(title)
        header_row.addStretch()

        self._restart_badge = QLabel("⚠ 需要重启机器人才能生效")
        self._restart_badge.setStyleSheet(
            "color: #f9e2af; font-size: 12px; background: #45475a; "
            "border-radius: 4px; padding: 4px 10px;"
        )
        self._restart_badge.hide()
        header_row.addWidget(self._restart_badge)

        self._save_btn = QPushButton("💾  保存配置")
        self._save_btn.setProperty("cssClass", "primary")
        self._save_btn.setMinimumHeight(36)
        self._save_btn.clicked.connect(self._on_save)
        header_row.addWidget(self._save_btn)

        layout.addLayout(header_row)

        # ── DeepSeek Section ──
        ds_group = QGroupBox("DeepSeek API")
        ds_form = QFormLayout(ds_group)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")
        self._api_key_edit.textChanged.connect(self._mark_modified)
        ds_form.addRow("API Key:", self._api_key_edit)

        self._model_edit = QLineEdit()
        self._model_edit.textChanged.connect(self._mark_modified)
        ds_form.addRow("Model:", self._model_edit)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(64, 32768)
        self._max_tokens_spin.setSingleStep(256)
        self._max_tokens_spin.valueChanged.connect(self._mark_modified)
        ds_form.addRow("Max Tokens:", self._max_tokens_spin)

        self._temp_spin = QDoubleSpinBox()
        self._temp_spin.setRange(0.0, 2.0)
        self._temp_spin.setSingleStep(0.1)
        self._temp_spin.valueChanged.connect(self._mark_modified)
        ds_form.addRow("Temperature:", self._temp_spin)

        layout.addWidget(ds_group)

        # ── Bot Section ──
        bot_group = QGroupBox("机器人")
        bot_form = QFormLayout(bot_group)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._mark_modified)
        bot_form.addRow("名称:", self._name_edit)

        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(["mention", "all"])
        self._trigger_combo.currentTextChanged.connect(self._mark_modified)
        bot_form.addRow("触发模式:", self._trigger_combo)

        self._cooldown_spin = QDoubleSpinBox()
        self._cooldown_spin.setRange(0.5, 60.0)
        self._cooldown_spin.setSingleStep(0.5)
        self._cooldown_spin.valueChanged.connect(self._mark_modified)
        bot_form.addRow("回复间隔(秒):", self._cooldown_spin)

        self._char_combo = QComboBox()
        self._char_combo.setEditable(True)
        self._char_combo.currentTextChanged.connect(self._mark_modified)
        bot_form.addRow("默认角色:", self._char_combo)

        layout.addWidget(bot_group)

        # ── Groups Section ──
        groups_group = QGroupBox("群聊列表")
        groups_layout = QVBoxLayout(groups_group)

        self._groups_table = QTableWidget(0, 2)
        self._groups_table.setHorizontalHeaderLabels(["群名称", "群 URL"])
        self._groups_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._groups_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._groups_table.setMinimumHeight(100)
        self._groups_table.cellChanged.connect(self._mark_modified)
        groups_layout.addWidget(self._groups_table)

        grp_btn_row = QHBoxLayout()
        add_grp_btn = QPushButton("+ 添加群")
        add_grp_btn.clicked.connect(self._add_group_row)
        grp_btn_row.addWidget(add_grp_btn)

        rm_grp_btn = QPushButton("- 删除选中")
        rm_grp_btn.clicked.connect(self._remove_group_row)
        grp_btn_row.addWidget(rm_grp_btn)
        grp_btn_row.addStretch()
        groups_layout.addLayout(grp_btn_row)

        layout.addWidget(groups_group)

        # ── Context Section ──
        ctx_group = QGroupBox("上下文")
        ctx_form = QFormLayout(ctx_group)

        self._history_spin = QSpinBox()
        self._history_spin.setRange(1, 100)
        self._history_spin.valueChanged.connect(self._mark_modified)
        ctx_form.addRow("历史轮数:", self._history_spin)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(60, 86400)
        self._timeout_spin.setSingleStep(300)
        self._timeout_spin.setSuffix(" 秒")
        self._timeout_spin.valueChanged.connect(self._mark_modified)
        ctx_form.addRow("会话超时:", self._timeout_spin)

        layout.addWidget(ctx_group)

        # ── Browser Section ──
        br_group = QGroupBox("浏览器")
        br_form = QFormLayout(br_group)

        self._headless_cb = QCheckBox()
        self._headless_cb.toggled.connect(self._mark_modified)
        br_form.addRow("无头模式:", self._headless_cb)

        self._slowmo_spin = QSpinBox()
        self._slowmo_spin.setRange(0, 2000)
        self._slowmo_spin.setSingleStep(10)
        self._slowmo_spin.setSuffix(" ms")
        self._slowmo_spin.valueChanged.connect(self._mark_modified)
        br_form.addRow("输入延迟:", self._slowmo_spin)

        layout.addWidget(br_group)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ── Load / Save ──

    def _load_config(self) -> None:
        """Populate form fields from the config dict."""
        # DeepSeek
        ds = self._config.get("deepseek", {})
        self._api_key_edit.setText(ds.get("api_key", ""))
        self._model_edit.setText(ds.get("model", "deepseek-chat"))
        self._max_tokens_spin.setValue(ds.get("max_tokens", 2048))
        self._temp_spin.setValue(ds.get("temperature", 0.7))

        # Bot
        bot = self._config.get("bot", {})
        self._name_edit.setText(bot.get("name", "小助手"))
        idx = self._trigger_combo.findText(bot.get("trigger_mode", "mention"))
        if idx >= 0:
            self._trigger_combo.setCurrentIndex(idx)
        self._cooldown_spin.setValue(bot.get("reply_cooldown", 2.0))

        # Populate character combo from filesystem
        char_dir = bot.get("characters_dir", "characters")
        self._char_combo.clear()
        char_path = Path(char_dir)
        if char_path.exists():
            for yf in sorted(char_path.glob("*.yaml")):
                self._char_combo.addItem(yf.stem)
        default_char = bot.get("character", "default")
        idx = self._char_combo.findText(default_char)
        if idx >= 0:
            self._char_combo.setCurrentIndex(idx)
        elif self._char_combo.count() > 0:
            self._char_combo.setCurrentText(default_char)

        # Groups
        groups = self._config.get("groups", [])
        self._groups_table.blockSignals(True)
        self._groups_table.setRowCount(len(groups))
        for i, g in enumerate(groups):
            self._groups_table.setItem(i, 0, QTableWidgetItem(g.get("name", "")))
            self._groups_table.setItem(i, 1, QTableWidgetItem(g.get("url", "")))
        self._groups_table.blockSignals(False)

        # Context
        ctx = self._config.get("context", {})
        self._history_spin.setValue(ctx.get("max_history_rounds", 10))
        self._timeout_spin.setValue(ctx.get("session_timeout", 1800))

        # Browser
        br = self._config.get("browser", {})
        self._headless_cb.setChecked(br.get("headless", False))
        self._slowmo_spin.setValue(br.get("slow_mo", 100))

        self._modified = False

    def _collect_config(self) -> dict:
        """Build a config dict from form fields."""
        groups = []
        for row in range(self._groups_table.rowCount()):
            name_item = self._groups_table.item(row, 0)
            url_item = self._groups_table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            url = url_item.text().strip() if url_item else ""
            if name or url:
                groups.append({"name": name, "url": url})

        return {
            "deepseek": {
                "api_key": self._api_key_edit.text().strip(),
                "model": self._model_edit.text().strip(),
                "max_tokens": self._max_tokens_spin.value(),
                "temperature": self._temp_spin.value(),
            },
            "bot": {
                "name": self._name_edit.text().strip(),
                "trigger_mode": self._trigger_combo.currentText(),
                "reply_cooldown": self._cooldown_spin.value(),
                "character": self._char_combo.currentText().strip(),
                "characters_dir": self._config.get("bot", {}).get("characters_dir", "characters"),
                "skills_dir": self._config.get("bot", {}).get("skills_dir", "skills"),
            },
            "groups": groups,
            "context": {
                "max_history_rounds": self._history_spin.value(),
                "session_timeout": self._timeout_spin.value(),
            },
            "browser": {
                "headless": self._headless_cb.isChecked(),
                "slow_mo": self._slowmo_spin.value(),
            },
        }

    def _on_save(self) -> None:
        """Validate and save config to config.yaml."""
        new_config = self._collect_config()

        # Validate
        api_key = new_config.get("deepseek", {}).get("api_key", "")
        if not api_key or api_key == "sk-your-api-key-here":
            QMessageBox.warning(self, "验证错误", "请设置有效的 DeepSeek API Key")
            return

        groups = new_config.get("groups", [])
        if not groups:
            QMessageBox.warning(self, "验证错误", "请至少添加一个群聊")
            return

        # Write
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.dump(new_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法写入配置文件:\n{e}")
            return

        # Update internal config reference
        self._config.clear()
        self._config.update(new_config)
        self._modified = False
        self._restart_badge.show()
        self.config_saved.emit()

    # ── Helpers ──

    def _mark_modified(self, *args) -> None:
        """Mark config as modified."""
        self._modified = True

    def _add_group_row(self) -> None:
        """Add a blank row to the groups table."""
        row = self._groups_table.rowCount()
        self._groups_table.insertRow(row)
        self._groups_table.setItem(row, 0, QTableWidgetItem(""))
        self._groups_table.setItem(row, 1, QTableWidgetItem(""))
        self._mark_modified()

    def _remove_group_row(self) -> None:
        """Remove the selected row from the groups table."""
        rows = set()
        for idx in self._groups_table.selectedIndexes():
            rows.add(idx.row())
        for row in sorted(rows, reverse=True):
            self._groups_table.removeRow(row)
        if rows:
            self._mark_modified()
