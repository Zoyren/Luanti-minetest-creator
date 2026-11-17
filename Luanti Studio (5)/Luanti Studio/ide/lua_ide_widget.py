# -*- coding: utf-8 -*-
"""
ide/lua_ide_widget.py
Workbench Logique combinant BlocklyEditorWidget (logic/blockly/) et l'éditeur de code Lua.
"""

try:
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
        QPlainTextEdit, QPushButton, QLabel, QCheckBox, QFrame
    )
except ImportError:
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
        QPlainTextEdit, QPushButton, QLabel, QCheckBox, QFrame
    )

from logic.blockly.blockly_editor_widget import BlocklyEditorWidget


class LuaIdeWidget(QWidget):
    """Éditeur combiné Blockly + Code Lua pour Mobs, Blocks, Items et Commands."""
    luaCodeChanged = pyqtSignal(str)

    def __init__(self, category: str = "Mobs", parent=None):
        super().__init__(parent)
        self.current_category = category
        self.manual_override = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Barre d'outils supérieure
        toolbar = QFrame()
        toolbar.setProperty("class", "InspectorPanel")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)

        self.lbl_mode = QLabel(f"🧩 Atelier Logique Blockly — Catégorie : {self.current_category}")
        self.lbl_mode.setStyleSheet("font-weight: bold; color: #60a5fa; font-size: 14px;")
        tb_layout.addWidget(self.lbl_mode)
        tb_layout.addStretch()

        btn_reset = QPushButton("➕ Insérer Bloc Événement de base")
        btn_reset.clicked.connect(lambda: self.blockly_widget.set_category(self.current_category, reset_starter=True))
        tb_layout.addWidget(btn_reset)

        btn_resize = QPushButton("🔄 Recalibrer la grille Blockly")
        btn_resize.clicked.connect(self.refresh_blockly_layout)
        tb_layout.addWidget(btn_resize)

        self.chk_manual = QCheckBox("Mode Lua Manuel")
        self.chk_manual.toggled.connect(self._on_manual_toggled)
        tb_layout.addWidget(self.chk_manual)

        layout.addWidget(toolbar)

        # Splitter Horizontal : Blockly (gauche) | Code Lua (droite)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.blockly_widget = BlocklyEditorWidget(category=self.current_category, parent=self)
        self.blockly_widget.codeChanged.connect(self._on_blockly_lua_generated)
        splitter.addWidget(self.blockly_widget)

        lua_frame = QFrame()
        lua_frame.setProperty("class", "InspectorPanel")
        lua_layout = QVBoxLayout(lua_frame)
        lua_layout.setContentsMargins(8, 8, 8, 8)

        lbl_code = QLabel("📜 Code Lua Luanti généré en direct :")
        lbl_code.setStyleSheet("font-weight: bold; color: #93c5fd;")
        lua_layout.addWidget(lbl_code)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setReadOnly(True)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_editor.setFont(font)
        self.code_editor.textChanged.connect(self._on_manual_text_changed)
        lua_layout.addWidget(self.code_editor)

        splitter.addWidget(lua_frame)
        splitter.setSizes([820, 360])
        layout.addWidget(splitter, 1)

    def _on_blockly_lua_generated(self, lua_code: str):
        if not self.manual_override:
            self.code_editor.blockSignals(True)
            self.code_editor.setPlainText(lua_code)
            self.code_editor.blockSignals(False)
            self.luaCodeChanged.emit(lua_code)

    def _on_manual_toggled(self, checked: bool):
        self.manual_override = checked
        self.code_editor.setReadOnly(not checked)

    def _on_manual_text_changed(self):
        if self.manual_override:
            self.luaCodeChanged.emit(self.code_editor.toPlainText())

    def set_category(self, category: str, insert_starter: bool = False):
        self.current_category = category
        self.lbl_mode.setText(f"🧩 Atelier Logique Blockly — Catégorie : {category}")
        self.blockly_widget.set_category(category, reset_starter=insert_starter)

    def refresh_blockly_layout(self):
        self.blockly_widget.refresh_layout()

    def get_code(self) -> str:
        return self.code_editor.toPlainText()

    def set_code(self, code: str):
        self.code_editor.setPlainText(code)


# Alias au cas où d'autres fichiers importent LuaIDEWidget en majuscules
LuaIDEWidget = LuaIdeWidget