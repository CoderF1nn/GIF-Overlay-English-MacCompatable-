import sys
import os
import shutil
from pathlib import Path
from typing import Optional
from PyQt5.QtWidgets import (
    QApplication, QLabel, QFileDialog, QWidget,
    QVBoxLayout, QMenu, QMessageBox, QInputDialog,
    QDialog, QPushButton,
    QSlider, QGridLayout, QSystemTrayIcon, QAction
)
from PyQt5.QtGui import QMovie, QIcon
from PyQt5.QtCore import Qt, QSize

# UNIVERSAL PATH LOGIC: Prevents crash on Mac
if sys.platform == "win32":
    CONFIG_DIR = Path(os.getenv('APPDATA', Path.home())) / "GIF Overlay"
else:
    CONFIG_DIR = Path.home() / ".config" / "GIF-Overlay"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "last_gif_path.txt"
CONFIG_SETTINGS_FILE = CONFIG_DIR / "settings.txt"
GIF_SAVE_DIR = Path.home() / "Documents" / "GIF-save"

class GifOnTop(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GIF Overlay")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)

        self.gif_label = QLabel()
        self.gif_label.setAttribute(Qt.WA_TranslucentBackground)
        self.gif_label.setStyleSheet("background: transparent;")
        self.layout.addWidget(self.gif_label)

        self.movie: Optional[QMovie] = None
        self.current_gif_path: Optional[str] = None
        self.original_size: Optional[QSize] = None
        self.drag_position = None
        self.is_locked = False

        self.resize(300, 300)
        self.load_last_gif()
        self.show()

        if not self.current_gif_path:
            self.show_menu_at_center()

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().SP_ComputerIcon))

        tray_menu = QMenu()
        show_action = QAction("Show Window", self)
        quit_action = QAction("Exit", self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)

        show_action.triggered.connect(self.show_normal)
        quit_action.triggered.connect(QApplication.quit)
        self.tray_icon.show()

    def create_menu(self):
        menu = QMenu(self)
        if self.is_locked:
            menu.addAction("Unlock").triggered.connect(self.unlock_window)
            return menu

        change_menu = menu.addMenu("Change GIF")
        change_menu.addAction("New GIF").triggered.connect(self.open_file_dialog)
        
        menu.addSeparator()
        menu.addAction("Pause / Play GIF").triggered.connect(self.toggle_pause_gif)
        
        close_menu = menu.addMenu("Close / Exit")
        close_menu.addAction("Quit App").triggered.connect(QApplication.quit)
        close_menu.addAction("Minimize to Tray").triggered.connect(self.hide)

        menu.addSeparator()
        menu.addAction("Lock Window").triggered.connect(self.lock_window)
        return menu

    def lock_window(self):
        self.is_locked = True

    def unlock_window(self):
        self.is_locked = False

    def contextMenuEvent(self, event):
        menu = self.create_menu()
        menu.exec_(self.mapToGlobal(event.pos()))

    def show_menu_at_center(self):
        menu = self.create_menu()
        menu.exec_(self.mapToGlobal(self.rect().center()))

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select GIF", "", "GIF Files (*.gif)")
        if path: self.load_gif(path)

    def load_gif(self, path):
        if self.movie: self.movie.stop()
        self.movie = QMovie(path)
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        self.current_gif_path = path
        self.save_last_gif(path)

    def save_last_gif(self, path):
        try: CONFIG_FILE.write_text(path)
        except: pass

    def load_last_gif(self):
        if CONFIG_FILE.exists():
            path = CONFIG_FILE.read_text().strip()
            if os.path.exists(path): self.load_gif(path)

    def toggle_pause_gif(self):
        if self.movie:
            self.movie.setPaused(not (self.movie.state() == QMovie.Paused))

    def show_normal(self):
        self.show()
        self.raise_()

    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if not self.is_locked and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GifOnTop()
    sys.exit(app.exec_())
