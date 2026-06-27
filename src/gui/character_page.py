"""Character page — view, edit and switch AI character profiles."""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QTextEdit, QGroupBox,
    QStackedWidget, QMessageBox, QLineEdit, QCheckBox, QScrollArea,
    QFormLayout, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..core.character import CharacterManager, Character
from ..core.skills import SkillManager, Skill


class CharacterEditorDialog(QDialog):
    """Dialog for creating or editing a character."""

    def __init__(self, character: Character | None = None,
                 skill_manager: SkillManager | None = None,
                 parent=None):
        super().__init__(parent)
        self.character = character
        self.skill_manager = skill_manager
        self._build_ui()
        if character:
            self._load_character(character)

    def _build_ui(self):
        self.setWindowTitle("编辑角色" if self.character else "新建角色")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(12)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("角色名称")
        form_layout.addRow("名称:", self.name_edit)

        # Description
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("简短描述")
        form_layout.addRow("描述:", self.desc_edit)

        # Personality
        self.personality_edit = QLineEdit()
        self.personality_edit.setPlaceholderText("性格特点")
        form_layout.addRow("性格:", self.personality_edit)

        # Background
        self.background_edit = QTextEdit()
        self.background_edit.setMaximumHeight(80)
        self.background_edit.setPlaceholderText("角色背景故事")
        form_layout.addRow("背景:", self.background_edit)

        # Speaking style
        self.style_edit = QLineEdit()
        self.style_edit.setPlaceholderText("说话风格")
        form_layout.addRow("风格:", self.style_edit)

        # System prompt
        self.prompt_group = QGroupBox("系统提示词 (留空则自动生成)")
        prompt_layout = QVBoxLayout(self.prompt_group)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(120)
        self.prompt_edit.setPlaceholderText(
            "如果留空，将根据上面的性格、背景等自动生成提示词"
        )
        prompt_layout.addWidget(self.prompt_edit)
        form_layout.addRow(self.prompt_group)

        # Bound skills
        if self.skill_manager:
            self.skills_group = QGroupBox("绑定技能 (选择后该角色自动加载这些技能)")
            skills_layout = QVBoxLayout(self.skills_group)
            self.skill_checkboxes: list[tuple[QCheckBox, str]] = []
            skills = self.skill_manager.list_skills()
            if skills:
                for skill in skills:
                    cb = QCheckBox(f"{skill.name} — {skill.description}")
                    self.skill_checkboxes.append((cb, skill.name))
                    skills_layout.addWidget(cb)
            else:
                skills_layout.addWidget(QLabel("没有可用的技能，请先添加技能"))
            form_layout.addRow(self.skills_group)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_character(self, char: Character):
        self.name_edit.setText(char.name)
        self.desc_edit.setText(char.description)
        self.personality_edit.setText(char.personality)
        self.background_edit.setPlainText(char.background)
        self.style_edit.setText(char.speaking_style)
        self.prompt_edit.setPlainText(char.system_prompt)

        # Check bound skills
        if hasattr(char, 'bound_skills'):
            for cb, skill_name in self.skill_checkboxes:
                if skill_name in char.bound_skills:
                    cb.setChecked(True)

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "验证错误", "请输入角色名称")
            return

        # Get bound skills
        bound_skills = []
        for cb, skill_name in self.skill_checkboxes:
            if cb.isChecked():
                bound_skills.append(skill_name)

        # Create or update character
        if self.character:
            self.character.name = name
            self.character.description = self.desc_edit.text().strip()
            self.character.personality = self.personality_edit.text().strip()
            self.character.background = self.background_edit.toPlainText().strip()
            self.character.speaking_style = self.style_edit.text().strip()
            self.character.system_prompt = self.prompt_edit.toPlainText().strip()
            self.character.bound_skills = bound_skills
        else:
            self.character = Character(
                name=name,
                description=self.desc_edit.text().strip(),
                personality=self.personality_edit.text().strip(),
                background=self.background_edit.toPlainText().strip(),
                speaking_style=self.style_edit.text().strip(),
                system_prompt=self.prompt_edit.toPlainText().strip(),
                bound_skills=bound_skills,
            )

        self.accept()


class CharacterPage(QWidget):
    """Character management page — list characters, view details, edit, switch.

    Created once at GUI startup. If no CharacterManager is available yet,
    a placeholder message is shown. Call set_manager() once the bot has
    started to populate the page.
    """

    character_switched = pyqtSignal(str)  # character name

    def __init__(self, character_manager: CharacterManager | None = None,
                 skill_manager: SkillManager | None = None,
                 parent=None):
        super().__init__(parent)
        self._mgr = character_manager
        self._skill_mgr = skill_manager
        self._build_ui()
        if self._mgr is not None:
            self._populate()

    def set_manager(self, mgr: CharacterManager | None,
                    skill_mgr: SkillManager | None = None) -> None:
        """Set or replace the character manager and refresh the page."""
        self._mgr = mgr
        self._skill_mgr = skill_mgr
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

        # Left: character list
        left = QVBoxLayout()
        heading = QLabel("可选角色")
        heading.setProperty("cssClass", "heading")
        left.addWidget(heading)

        self._list = QListWidget()
        self._list.setMinimumWidth(220)
        self._list.setMaximumWidth(300)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list)

        # Button row
        btn_row = QHBoxLayout()
        self._new_btn = QPushButton("+ 新建")
        self._new_btn.clicked.connect(self._on_new)
        self._new_btn.setMinimumHeight(32)
        btn_row.addWidget(self._new_btn)

        self._edit_btn = QPushButton("编辑")
        self._edit_btn.clicked.connect(self._on_edit)
        self._edit_btn.setMinimumHeight(32)
        btn_row.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("- 删除")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setMinimumHeight(32)
        btn_row.addWidget(self._delete_btn)
        left.addLayout(btn_row)

        self._switch_btn = QPushButton("切换到此角色")
        self._switch_btn.setProperty("cssClass", "primary")
        self._switch_btn.setMinimumHeight(36)
        self._switch_btn.clicked.connect(self._on_switch)
        left.addWidget(self._switch_btn)
        layout.addLayout(left)

        # Right: detail view
        right = QVBoxLayout()

        self._current_label = QLabel()
        self._current_label.setStyleSheet("color: #a6e3a1; font-size: 13px; padding: 4px 0;")
        right.addWidget(self._current_label)

        self._name_label = QLabel()
        self._name_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        right.addWidget(self._name_label)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color: #a6adc8; font-size: 13px;")
        right.addWidget(self._desc_label)
        right.addSpacing(8)

        # Personality
        pg = QGroupBox("性格")
        pl = QVBoxLayout(pg)
        self._personality_label = QLabel()
        self._personality_label.setWordWrap(True)
        pl.addWidget(self._personality_label)
        right.addWidget(pg)

        # Background
        bg = QGroupBox("背景故事")
        bl = QVBoxLayout(bg)
        self._background_label = QLabel()
        self._background_label.setWordWrap(True)
        bl.addWidget(self._background_label)
        right.addWidget(bg)

        # Speaking style
        sg = QGroupBox("说话风格")
        sl = QVBoxLayout(sg)
        self._style_label = QLabel()
        self._style_label.setWordWrap(True)
        sl.addWidget(self._style_label)
        right.addWidget(sg)

        # Bound skills
        bs = QGroupBox("绑定技能")
        bsl = QVBoxLayout(bs)
        self._bound_skills_label = QLabel()
        self._bound_skills_label.setWordWrap(True)
        bsl.addWidget(self._bound_skills_label)
        right.addWidget(bs)

        # System prompt preview
        pr = QGroupBox("系统提示词预览")
        prl = QVBoxLayout(pr)
        self._prompt_view = QTextEdit()
        self._prompt_view.setReadOnly(True)
        self._prompt_view.setFont(QFont("Consolas", 10))
        self._prompt_view.setMaximumHeight(150)
        self._prompt_view.setStyleSheet(
            "QTextEdit{background:#181825;border:1px solid #585b70;border-radius:4px;padding:6px;}"
        )
        prl.addWidget(self._prompt_view)
        right.addWidget(pr)
        right.addStretch()
        layout.addLayout(right, 1)

        self._stack.addWidget(content)  # index 0

        # Page 1: placeholder
        placeholder = QLabel("请先启动机器人以加载角色列表\n\n启动后可在角色页面查看和切换角色")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #6c7086; font-size: 14px;")
        self._stack.addWidget(placeholder)  # index 1

        root.addWidget(self._stack)
        self._stack.setCurrentIndex(0 if self._mgr else 1)

    # ── Population ──────────────────────────────────────────────

    def _populate(self) -> None:
        """Fill the list with loaded characters."""
        if not self._mgr:
            return
        self._list.clear()
        active = self._mgr.active

        for char in self._mgr.list_characters():
            item = QListWidgetItem(char.name)
            item.setData(Qt.ItemDataRole.UserRole, char)
            item.setToolTip(char.description)
            if active and char.name == active.name:
                item.setForeground(QColor("#a6e3a1"))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self._list.addItem(item)

        if active:
            for i in range(self._list.count()):
                it = self._list.item(i)
                c = it.data(Qt.ItemDataRole.UserRole)
                if c and c.name == active.name:
                    self._list.setCurrentRow(i)
                    break

        self._update_current_label()

    def _update_current_label(self) -> None:
        active = self._mgr.active if self._mgr else None
        if active:
            self._current_label.setText(f"● 当前角色: {active.name}")
        else:
            self._current_label.setText("○ 未选择角色")

    # ── Events ──────────────────────────────────────────────────

    def _on_select(self, row: int) -> None:
        if row < 0 or not self._mgr:
            return
        item = self._list.item(row)
        char = item.data(Qt.ItemDataRole.UserRole)
        if not char:
            return
        self._name_label.setText(char.name)
        self._desc_label.setText(char.description or "(无描述)")
        self._personality_label.setText(char.personality or "(未设置)")
        self._background_label.setText(char.background or "(未设置)")
        self._style_label.setText(char.speaking_style or "(未设置)")
        self._prompt_view.setPlainText(char.build_system_prompt())

        # Show bound skills
        if hasattr(char, 'bound_skills') and char.bound_skills:
            self._bound_skills_label.setText(", ".join(char.bound_skills))
        else:
            self._bound_skills_label.setText("(未绑定技能)")

    def _on_switch(self) -> None:
        if not self._mgr:
            return
        row = self._list.currentRow()
        if row < 0:
            return
        item = self._list.item(row)
        char = item.data(Qt.ItemDataRole.UserRole)
        if not char:
            return
        result = self._mgr.switch(char.name)
        if result:
            self._populate()
            self.character_switched.emit(char.name)

    def _on_new(self) -> None:
        """Create a new character."""
        if not self._mgr:
            QMessageBox.warning(self, "提示", "请先启动机器人")
            return

        dlg = CharacterEditorDialog(skill_manager=self._skill_mgr, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        char = dlg.character
        if not char:
            return

        # Save the new character
        if self._mgr.save_character(char):
            self._populate()
            # Select the new character
            for i in range(self._list.count()):
                it = self._list.item(i)
                c = it.data(Qt.ItemDataRole.UserRole)
                if c and c.name == char.name:
                    self._list.setCurrentRow(i)
                    break
            QMessageBox.information(self, "成功", f"已创建角色: {char.name}")
        else:
            QMessageBox.warning(self, "失败", "保存角色失败")

    def _on_edit(self) -> None:
        """Edit the selected character."""
        if not self._mgr:
            QMessageBox.warning(self, "提示", "请先启动机器人")
            return

        row = self._list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要编辑的角色")
            return

        item = self._list.item(row)
        char = item.data(Qt.ItemDataRole.UserRole)
        if not char:
            return

        dlg = CharacterEditorDialog(character=char,
                                     skill_manager=self._skill_mgr,
                                     parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Save the edited character
        if self._mgr.save_character(char):
            self._populate()
            # Reselect the character
            for i in range(self._list.count()):
                it = self._list.item(i)
                c = it.data(Qt.ItemDataRole.UserRole)
                if c and c.name == char.name:
                    self._list.setCurrentRow(i)
                    break
            QMessageBox.information(self, "成功", f"已更新角色: {char.name}")
        else:
            QMessageBox.warning(self, "失败", "保存角色失败")

    def _on_delete(self) -> None:
        """Delete the selected character."""
        if not self._mgr:
            QMessageBox.warning(self, "提示", "请先启动机器人")
            return

        row = self._list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的角色")
            return

        item = self._list.item(row)
        char = item.data(Qt.ItemDataRole.UserRole)
        if not char:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除角色 '{char.name}' 吗？\n\n"
            "注意：这不会删除正在运行的机器人中的角色，"
            "需要重启机器人后才会完全生效。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Ask about deleting the file
        delete_file = QMessageBox.question(
            self, "删除文件",
            "是否同时删除磁盘上的 YAML 文件？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

        # Delete the character
        key = Path(char.file_path).stem if char.file_path else char.name
        if self._mgr.delete_character(key, delete_file=delete_file):
            self._populate()
            QMessageBox.information(self, "成功", f"已删除角色: {char.name}")
        else:
            QMessageBox.warning(self, "失败", "删除角色失败")
