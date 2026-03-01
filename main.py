"""通达信配置备份与转移工具 - 入口点"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.core.version import APP_NAME, APP_VERSION
from src.ui.main_window import MainWindow
from src.ui.theme import APP_STYLE_SHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    app.setStyleSheet(APP_STYLE_SHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
