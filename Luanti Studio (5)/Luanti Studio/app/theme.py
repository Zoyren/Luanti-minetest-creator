# -*- coding: utf-8 -*-
"""
app/theme.py
Gestionnaire de thème sombre Aéré & Haute Visibilité 3.0 pour Luanti Studio (Tâche B) :
- Espacement généreux (padding/margins) pour éliminer l'effet "collé/compact"
- En-tête à 2 niveaux (MainHeaderBar + WorkbenchTabBar) pour éviter tout débordement horizontal
- Hauteur minimale confortable sur tous les champs et boutons
- SpinBoxes codées par couleur d'axe (X Rouge, Y Vert, Z Bleu)
"""

DARK_WORKBENCH_QSS = """
/* === GLOBAL === */
QMainWindow, QWidget {
    background-color: #14171f;
    color: #f1f5f9;
    font-family: "Segoe UI", "Inter", "Ubuntu", sans-serif;
    font-size: 13px;
}

/* === DOCK WIDGETS (FENÊTRES DÉTACHABLES AÉRÉES) === */
QDockWidget {
    color: #60a5fa;
    font-weight: bold;
}
QDockWidget::title {
    background-color: #0f131a;
    border: 1px solid #2563eb;
    border-radius: 5px;
    padding: 8px 12px;
    margin: 2px;
    text-align: left;
}

/* === SEPARATEURS (SPLITTERS LARGES ET FACILES À SAISIR) === */
QSplitter::handle {
    background-color: #0d1016;
}
QSplitter::handle:horizontal {
    width: 6px;
    margin: 0px 2px;
}
QSplitter::handle:vertical {
    height: 6px;
    margin: 2px 0px;
}
QSplitter::handle:hover {
    background-color: #3b82f6;
}

/* === ONGLETS D'INSPECTEURS (QTABWIDGET AÉRÉS) === */
QTabWidget::pane {
    border: 1px solid #2e3646;
    background-color: #1a1e28;
    border-radius: 6px;
    top: -1px;
    padding: 4px;
}
QTabBar::tab {
    background-color: #11141c;
    color: #94a3b8;
    border: 1px solid #282e3d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 14px;
    margin-right: 4px;
    font-weight: 600;
}
QTabBar::tab:hover {
    background-color: #1e2433;
    color: #f8fafc;
}
QTabBar::tab:selected {
    background-color: #2563eb;
    color: #ffffff;
    border-color: #60a5fa;
}

/* === RAIL LATERAL DES CATEGORIES === */
QFrame#CategoryRail {
    background-color: #111319;
    border-right: 1px solid #262932;
}

QPushButton.CategoryButton {
    background-color: #171b24;
    color: #cbd5e1;
    border: 1px solid #262c3a;
    border-left: 4px solid transparent;
    border-radius: 5px;
    padding: 9px 12px;
    margin-bottom: 2px;
    text-align: left;
    font-weight: 600;
    font-size: 13px;
}
QPushButton.CategoryButton:hover {
    background-color: #202634;
    color: #ffffff;
    border-color: #3b82f6;
}
QPushButton.CategoryButton:checked {
    background-color: #1e293b;
    color: #60a5fa;
    border: 1px solid #3b82f6;
    border-left: 4px solid #38bdf8;
}

/* === BARRE SUPÉRIEURE NIVEAU 1 (PROJET, ÉLÉMENT ACTIF & ACTIONS GLOBALES) === */
QFrame#MainHeaderBar {
    background-color: #0d1016;
    border-bottom: 1px solid #1e293b;
}

/* === BARRE SUPÉRIEURE NIVEAU 2 (ONGLETS DES WORKBENCHES) === */
QFrame#WorkbenchTopBar {
    background-color: #12161f;
    border-bottom: 1px solid #283040;
}

QPushButton.WorkbenchTab {
    background-color: #191e2b;
    color: #94a3b8;
    border: 1px solid #2a3244;
    border-radius: 6px;
    padding: 7px 14px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton.WorkbenchTab:hover {
    background-color: #232a3b;
    color: #f8fafc;
    border-color: #475569;
}
QPushButton.WorkbenchTab:checked {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #60a5fa;
}

/* === PANNEAUX D'INSPECTEUR & GROUPBOX RESPIRANTS === */
QFrame.InspectorPanel {
    background-color: #1a1e28;
    border: 1px solid #2d3446;
    border-radius: 8px;
}

QGroupBox {
    background-color: #171b24;
    border: 1px solid #2e3646;
    border-radius: 8px;
    margin-top: 18px;
    padding-top: 16px;
    padding-bottom: 10px;
    padding-left: 10px;
    padding-right: 10px;
    font-weight: bold;
    color: #93c5fd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 2px 8px;
    background-color: #1e2433;
    border: 1px solid #334155;
    border-radius: 4px;
}

/* === CHAMPS DE SAISIE AÉRÉS & SPINBOXES AXES X/Y/Z === */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0f1218;
    color: #f8fafc;
    border: 1px solid #333c4d;
    border-radius: 5px;
    padding: 5px 9px;
    min-height: 22px;
    selection-background-color: #2563eb;
}
QPlainTextEdit, QTextEdit {
    background-color: #0f1218;
    color: #f8fafc;
    border: 1px solid #333c4d;
    border-radius: 5px;
    padding: 6px 8px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #60a5fa;
    background-color: #0b0e14;
}

QDoubleSpinBox#AxisX {
    border-left: 3px solid #ef4444;
    font-weight: bold;
}
QDoubleSpinBox#AxisY {
    border-left: 3px solid #22c55e;
    font-weight: bold;
}
QDoubleSpinBox#AxisZ {
    border-left: 3px solid #3b82f6;
    font-weight: bold;
}

/* === BOUTONS CONFORTABLES === */
QPushButton {
    background-color: #252b3b;
    color: #e2e8f0;
    border: 1px solid #384152;
    border-radius: 5px;
    padding: 6px 12px;
    min-height: 22px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #323a4f;
    border-color: #60a5fa;
}
QPushButton:pressed {
    background-color: #1e222b;
}
QPushButton:checked {
    background-color: #1d4ed8;
    color: #ffffff;
    border: 1px solid #facc15;
}
QPushButton#PrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
    border-color: #93c5fd;
}
QPushButton#DangerButton {
    background-color: #7f1d1d;
    color: #fecaca;
    border: 1px solid #b91c1c;
}
QPushButton#DangerButton:hover {
    background-color: #991b1b;
}

/* === LISTES ET ARBRES AÉRÉS === */
QListWidget, QTreeWidget {
    background-color: #10131a;
    border: 1px solid #2b3242;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget::item, QTreeWidget::item {
    padding: 7px 10px;
    margin-bottom: 2px;
    border-radius: 4px;
    border-bottom: 1px solid #181c26;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: bold;
}
QListWidget::item:hover, QTreeWidget::item:hover {
    background-color: #1e2430;
}

/* === ZONES DE DÉFILEMENT (SCROLLAREAS) === */
QScrollArea {
    background-color: transparent;
    border: none;
}

/* === BARRES DE DÉFILEMENT (SCROLLBARS) === */
QScrollBar:vertical {
    background: #10131a;
    width: 10px;
    margin: 2px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #60a5fa;
}
QScrollBar:horizontal {
    background: #10131a;
    height: 10px;
    margin: 2px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 28px;
    border-radius: 5px;
}

/* === CHECKBOX === */
QCheckBox {
    spacing: 8px;
    padding: 3px 2px;
    color: #e2e8f0;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 1px solid #475569;
    border-radius: 4px;
    background-color: #0f1218;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #60a5fa;
}
"""


def apply_workbench_theme(app_or_widget):
    """Applique le thème sombre Aéré 3.0 à l'application ou à la fenêtre."""
    app_or_widget.setStyleSheet(DARK_WORKBENCH_QSS)


def apply_theme(app_or_widget, theme_name: str = "dark"):
    """Alias de rétrocompatibilité avec app/application.py."""
    apply_workbench_theme(app_or_widget)