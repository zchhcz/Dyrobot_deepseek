"""Skills page — view available skills with triggers and prompts."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QTextEdit, QGroupBox,
    QStackedWidget, QPushButton, QFileDialog, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..core.skills import SkillManager, Skill


class SkillPage(QWidget):
    """Skills management page — view all loaded skills and their details.

    Created once at GUI startup.  If no SkillManager is available yet,
    a placeholder message is shown.  Call set_manager() once the bot has
    started to populate the page.
    """

    def __init__(self, skill_manager: SkillManager | None = None, parent=None):
        super().__init__(parent)
        self._mgr = skill_manager
        self._build_ui()
        if self._mgr is not None:
            self._populate()

    def set_manager(self, mgr: SkillManager | None) -> None:
        """Set or replace the skill manager and refresh the page."""
        self._mgr = mgr
        if mgr is not None:
            self._stack.setCurrentIndex(0)
            self._populate()
        else:
            self._stack.setCurrentIndex(1)

    # ── UI ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()

        # Page 0: real content
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Left: skill list
        left = QVBoxLayout()
        hdr = QLabel("已加载技能")
        hdr.setProperty("cssClass", "heading")
        left.addWidget(hdr)

        hint = QLabel("含关键词的消息会自动激活对应技能")
        hint.setStyleSheet("color: #a6adc8; font-size: 12px;")
        hint.setWordWrap(True)
        left.addWidget(hint)

        self._list = QListWidget()
        self._list.setMinimumWidth(200)
        self._list.setMaximumWidth(280)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list)

        # Button row
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ 添加技能")
        self._add_btn.clicked.connect(self._on_add_skill)
        self._add_btn.setMinimumHeight(32)
        btn_row.addWidget(self._add_btn)

        self._remove_btn = QPushButton("- 删除技能")
        self._remove_btn.clicked.connect(self._on_remove_skill)
        self._remove_btn.setMinimumHeight(32)
        btn_row.addWidget(self._remove_btn)

        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._refresh_btn.setMinimumHeight(32)
        btn_row.addWidget(self._refresh_btn)

        left.addLayout(btn_row)
        layout.addLayout(left)

        # Right: detail
        right = QVBoxLayout()

        self._name_label = QLabel()
        self._name_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        right.addWidget(self._name_label)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color: #a6adc8; font-size: 13px;")
        right.addWidget(self._desc_label)
        right.addSpacing(8)

        tg = QGroupBox("触发关键词")
        tl = QVBoxLayout(tg)
        self._triggers_label = QLabel()
        self._triggers_label.setWordWrap(True)
        self._triggers_label.setStyleSheet("color: #89b4fa; font-size: 13px;")
        tl.addWidget(self._triggers_label)
        right.addWidget(tg)

        pg = QGroupBox("技能提示词")
        pl = QVBoxLayout(pg)
        self._prompt_view = QTextEdit()
        self._prompt_view.setReadOnly(True)
        self._prompt_view.setFont(QFont("Consolas", 10))
        self._prompt_view.setStyleSheet(
            "QTextEdit{background:#181825;border:1px solid #585b70;border-radius:4px;padding:6px;}"
        )
        pl.addWidget(self._prompt_view)
        right.addWidget(pg, 1)

        # File path display
        path_gb = QGroupBox("文件路径")
        path_layout = QVBoxLayout(path_gb)
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: #a6adc8; font-size: 11px; font-family: Consolas, monospace;")
        path_layout.addWidget(self._path_label)
        right.addWidget(path_gb)

        right.addStretch()
        layout.addLayout(right, 1)

        self._stack.addWidget(content)  # index 0

        # Page 1: placeholder
        placeholder = QLabel("请先启动机器人以加载技能列表\n\n启动后可在技能页面查看已加载的技能")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #6c7086; font-size: 14px;")
        self._stack.addWidget(placeholder)  # index 1

        root.addWidget(self._stack)
        self._stack.setCurrentIndex(0 if self._mgr else 1)

    # ── Population ──────────────────────────────────────────────

    def _populate(self) -> None:
        if not self._mgr:
            return
        self._list.clear()
        skills = self._mgr.list_skills()
        if not skills:
            placeholder = QListWidgetItem("(没有加载任何技能)")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)
            return
        for skill in skills:
            item = QListWidgetItem(skill.name)
            item.setData(Qt.ItemDataRole.UserRole, skill)
            item.setToolTip(skill.description)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ── Events ──────────────────────────────────────────────────

    def _on_select(self, row: int) -> None:
        if row < 0:
            return
        item = self._list.item(row)
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self._name_label.setText(skill.name)
        self._desc_label.setText(skill.description or "(无描述)")
        triggers = ", ".join(skill.triggers) if skill.triggers else "(无触发词)"
        self._triggers_label.setText(triggers)
        self._prompt_view.setPlainText(skill.prompt or "(无提示词)")
        self._path_label.setText(skill.file_path or "(未关联文件)")

    def _on_add_skill(self) -> None:
        """Handle adding a new skill via file/directory dialog."""
        if not self._mgr:
            QMessageBox.warning(self, "提示", "请先启动机器人后再添加技能")
            return

        # Ask user what type they want to add
        dlg = QMessageBox(self)
        dlg.setWindowTitle("添加技能")
        dlg.setText("请选择要添加的技能类型：")
        dir_btn = dlg.addButton("技能目录（含 SKILL.md）", QMessageBox.ButtonRole.ActionRole)
        file_btn = dlg.addButton("技能文件（YAML/SKILL.md）", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.exec()

        clicked_btn = dlg.clickedButton()
        if clicked_btn == cancel_btn or clicked_btn is None:
            return

        paths = []
        if clicked_btn == dir_btn:
            # Select directory
            directory = QFileDialog.getExistingDirectory(
                self,
                "选择技能目录（包含 SKILL.md 的目录）",
                ""
            )
            if directory:
                paths = [directory]
        else:
            # Select files
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "选择技能文件",
                "",
                "支持的格式 (*.yaml *.yml SKILL.md);;YAML 文件 (*.yaml *.yml);;SKILL.md (SKILL.md);;所有文件 (*)"
            )
            paths = files

        if not paths:
            return

        added = 0
        failed = 0
        for path in paths:
            skill = self._mgr.add_skill_from_path(path, copy=True)
            if skill:
                added += 1
            else:
                failed += 1

        if added > 0:
            self._populate()
            QMessageBox.information(
                self,
                "成功",
                f"成功添加 {added} 个技能" + (f"，{failed} 个失败" if failed else "")
            )
        else:
            QMessageBox.warning(self, "失败", "未能成功添加任何技能，请检查文件格式")

    def _on_remove_skill(self) -> None:
        """Handle removing the selected skill."""
        if not self._mgr:
            return

        row = self._list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的技能")
            return

        item = self._list.item(row)
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return

        # Show confirmation dialog with option to delete file
        dlg = QMessageBox(self)
        dlg.setWindowTitle("确认删除")
        dlg.setText(f"确定要删除技能 \"{skill.name}\" 吗？")

        delete_file_cb = QCheckBox("同时删除技能文件")
        delete_file_cb.setChecked(False)
        dlg.setCheckBox(delete_file_cb)

        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        dlg.setDefaultButton(QMessageBox.StandardButton.No)

        result = dlg.exec()
        if result != QMessageBox.StandardButton.Yes:
            return

        delete_file = delete_file_cb.isChecked()
        if self._mgr.remove_skill(skill.name, delete_file=delete_file):
            self._populate()
            QMessageBox.information(self, "成功", f"已删除技能 \"{skill.name}\"")
        else:
            QMessageBox.warning(self, "失败", "删除技能失败")

    def _on_refresh(self) -> None:
        """Handle refreshing skills from directory."""
        if not self._mgr:
            QMessageBox.warning(self, "提示", "请先启动机器人后再刷新")
            return

        self._mgr.reload()
        self._populate()
        QMessageBox.information(self, "完成", "技能列表已刷新")
