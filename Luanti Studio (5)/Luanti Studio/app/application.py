# -*- coding: utf-8 -*-
"""
app/application.py
Point d'entrée sécurisé (évite les conflits OpenGL / HWND 0xC0000005 sur Windows).
"""

import os
import sys
import faulthandler

faulthandler.enable()
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

try:
    from PyQt6.QtCore import Qt, QCoreApplication
    from PyQt6.QtWidgets import QApplication
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except ImportError:
    from PyQt5.QtCore import Qt, QCoreApplication
    from PyQt5.QtWidgets import QApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

from app.theme import apply_workbench_theme
from app.main_window import MainWindow


def run_studio():
    app = QApplication(sys.argv)
    apply_workbench_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())