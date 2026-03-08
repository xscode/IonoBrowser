#!/usr/bin/env python3
"""
IonoBrowser — entry point.
Run this file directly:  python ionobrowser.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from ionobrowser.constants import APP_NAME, DARK_STYLE, make_app_icon
from ionobrowser.mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(DARK_STYLE)
    app.setWindowIcon(make_app_icon())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()