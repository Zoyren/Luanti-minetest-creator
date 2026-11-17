from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NavigationSidebar(QFrame):
    """Barre latérale gauche permettant de basculer entre les 10 sections du studio."""

    section_changed = Signal(str)

    SECTIONS: List[Tuple[str, str]] = [
        ("home", "Accueil & Projets"),
        ("mob", "1. MOB (Créatures)"),
        ("block", "2. BLOCK (Nodes)"),
        ("item", "3. ITEM (Objets)"),
        ("command", "4. COMMAND & GUI"),
        ("world", "5. WORLD (Voxel 3D)"),
        ("library", "Bibliothèque"),
        ("mods", "Mods externes"),
        ("ide", "IDE Lua"),
        ("settings", "Paramètres"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("LeftNavigationSidebar")
        self.setFixedWidth(205)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(2)

        section_title = QLabel("NAVIGATION")
        section_title.setStyleSheet(
            "color: #64748B; font-size: 11px; font-weight: 700; padding: 6px 14px;"
        )
        layout.addWidget(section_title)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: Dict[str, QPushButton] = {}

        for section_id, label in self.SECTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("navButton", True)
            if section_id == "home":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, sid=section_id: self.section_changed.emit(sid))
            self.button_group.addButton(btn)
            self.buttons[section_id] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

    def select_section(self, section_id: str) -> None:
        if section_id in self.buttons:
            self.buttons[section_id].setChecked(True)
            self.section_changed.emit(section_id)