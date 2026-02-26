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

# UNIVERSAL PATH LOGIC: Prevents crash on Mac by detecting the OS
if sys.platform == "win32":
    CONFIG_DIR = Path(os.getenv('APPDATA', Path.home())) / "GIF Overlay"
else:
    # On Mac, we use a hidden folder in your home directory
    CONFIG_DIR = Path.home() / ".gif_overlay"

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

        # Load settings and last used GIF on startup
        self.load_last_gif(reset_default=False)

        self.show()
        if not self.current_gif_path:
            self.show_menu_at_center()

        # Handle icon path for bundled executables
        base_dir = Path(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))))
        icon_path = base_dir / "app_icon.ico"

        self.tray_icon = QSystemTrayIcon(self)
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().SP_ComputerIcon))

        # Tray Menu translated to English
        tray_menu = QMenu()
        show_action = QAction("Show Window", self)
        quit_action = QAction("Exit", self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)

        show_action.triggered.connect(self.show_normal)
        quit_action.triggered.connect(QApplication.quit)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def save_settings(self, width: int, height: int, opacity: float):
        try:
            with open(CONFIG_SETTINGS_FILE, "w", encoding="utf-8") as f:
                f.write(f"{width}\n{height}\n{opacity}\n")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        if CONFIG_SETTINGS_FILE.exists():
            try:
                with open(CONFIG_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                    if len(lines) >= 3:
                        return int(lines[0]), int(lines[1]), float(lines[2])
            except Exception as e:
                print(f"Error loading settings: {e}")
        return None

    def reset_to_default(self):
        orig_w, orig_h = (self.original_size.width(), self.original_size.height()) if self.original_size else (300, 300)
        self.resize(orig_w, orig_h)
        if self.movie:
            self.movie.setScaledSize(QSize(orig_w, orig_h))
        self.setWindowOpacity(1.0)
        self.save_settings(orig_w, orig_h, 1.0)

    def create_menu(self):
        menu = QMenu(self)
        if self.is_locked:
            self.action_unlock = menu.addAction("Unlock Window")
            return menu

        # Main Menu translated to English
        change_menu = menu.addMenu("Change GIF")
        self.action_change_new = change_menu.addAction("Open New GIF")
        self.action_change_saved = change_menu.addAction("Open Saved GIF")

        menu.addSeparator()
        self.action_change_resize_opacity = menu.addAction("Resize and Opacity")
        
        menu.addSeparator()
        self.action_toggle_pause = menu.addAction("Pause / Play GIF")
        
        menu.addSeparator()
        self.action_save = menu.addAction("Save current GIF")

        close_menu = menu.addMenu("Close / Minimize")
        self.action_close_quit = close_menu.addAction("Quit Application")
        self.action_close_minimize = close_menu.addAction("Minimize to Tray")

        menu.addSeparator()
        self.action_lock = menu.addAction("Lock Window Position")

        return menu

    def handle_menu_action(self, action):
        if self.is_locked:
            if action == self.action_unlock:
                self.is_locked = False
                self.tray_icon.showMessage("GIF Overlay", "Window Unlocked.", QSystemTrayIcon.Information, 2000)
            return

        if action == self.action_change_new:
            self.open_file_dialog()
        elif action == self.action_change_saved:
            self.open_saved_gif_dialog()
        elif action == self.action_change_resize_opacity:
            self.open_resize_opacity_dialog()
        elif action == self.action_toggle_pause:
            self.toggle_pause_gif()
        elif action == self.action_save:
            self.save_gif_to_documents()
        elif action == self.action_close_quit:
            QApplication.quit()
        elif action == self.action_close_minimize:
            self.hide()
            self.tray_icon.showMessage("GIF Overlay", "Minimized to tray.", QSystemTrayIcon.Information, 2000)
        elif action == self.action_lock:
            self.is_locked = True
            self.tray_icon.showMessage("GIF Overlay", "Window Locked.", QSystemTrayIcon.Information, 2000)

    def contextMenuEvent(self, event):
        menu = self.create_menu()
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action:
            self.handle_menu_action(action)

    def show_menu_at_center(self):
        menu = self.create_menu()
        action = menu.exec_(self.mapToGlobal(self.rect().center()))
        if action:
            self.handle_menu_action(action)

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select GIF file", "", "GIF Files (*.gif)")
        if path:
            self.load_gif(path, reset_default=True)

    def load_gif(self, path, reset_default=False):
        if self.movie:
            self.movie.stop()
        self.movie = QMovie(path)
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        
        # Get original frame size
        self.movie.jumpToFrame(0)
        self.original_size = self.movie.currentPixmap().size()

        if reset_default:
            self.reset_to_default()
        else:
            settings = self.load_settings()
            if settings:
                w, h, o = settings
                self.resize(w, h)
                if self.movie: self.movie.setScaledSize(QSize(w, h))
                self.setWindowOpacity(o)
            else:
                self.resize(self.original_size if not self.original_size.isEmpty() else QSize(300, 300))

        self.current_gif_path = path
        self.save_last_gif(path)

    def save_last_gif(self, path):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(path)
        except:
            pass

    def load_last_gif(self, reset_default=False):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    path = f.read().strip()
                    if os.path.exists(path):
                        self.load_gif(path, reset_default=reset_default)
            except:
                pass

    def open_saved_gif_dialog(self):
        if not GIF_SAVE_DIR.exists():
            QMessageBox.information(self, "Saved GIFs", "No saved GIFs found.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select Saved GIF", str(GIF_SAVE_DIR), "GIF Files (*.gif)")
        if path:
            self.load_gif(path, reset_default=True)

    def save_gif_to_documents(self):
        if not self.current_gif_path or not os.path.exists(self.current_gif_path):
            return
        GIF_SAVE_DIR.mkdir(exist_ok=True)
        default_base = os.path.splitext(os.path.basename(self.current_gif_path))[0]
        new_name, ok = QInputDialog.getText(self, "Save GIF", "Enter file name:", text=default_base)
        if ok and new_name.strip():
            if not new_name.lower().endswith(".gif"): new_name += ".gif"
            dest = GIF_SAVE_DIR / new_name
            shutil.copy2(self.current_gif_path, dest)
            QMessageBox.information(self, "Success", f"GIF saved to:\n{dest}")

    def toggle_pause_gif(self):
        if self.movie:
            self.movie.setPaused(self.movie.state() == QMovie.Running)

    def open_resize_opacity_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Resize and Opacity")
        layout = QGridLayout(dialog)

        # Controls translated to English
        label_w = QLabel(f"Width: {self.width()}")
        slider_w = QSlider(Qt.Horizontal)
        slider_w.setRange(50, 2000)
        slider_w.setValue(self.width())

        label_h = QLabel(f"Height: {self.height()}")
        slider_h = QSlider(Qt.Horizontal)
        slider_h.setRange(50, 2000)
        slider_h.setValue(self.height())

        label_o = QLabel(f"Opacity: {int(self.windowOpacity()*100)}%")
        slider_o = QSlider(Qt.Horizontal)
        slider_o.setRange(10, 100)
        slider_o.setValue(int(self.windowOpacity()*100))

        def update_ui():
            self.resize(slider_w.value(), slider_h.value())
            if self.movie: self.movie.setScaledSize(self.size())
            self.setWindowOpacity(slider_o.value() / 100)
            label_w.setText(f"Width: {self.width()}")
            label_h.setText(f"Height: {self.height()}")
            label_o.setText(f"Opacity: {slider_o.value()}%")

        slider_w.valueChanged.connect(update_ui)
        slider_h.valueChanged.connect(update_ui)
        slider_o.valueChanged.connect(update_ui)
        
        # Save settings when the user stops sliding
        slider_w.sliderReleased.connect(lambda: self.save_settings(self.width(), self.height(), self.windowOpacity()))
        slider_h.sliderReleased.connect(lambda: self.save_settings(self.width(), self.height(), self.windowOpacity()))
        slider_o.sliderReleased.connect(lambda: self.save_settings(self.width(), self.height(), self.windowOpacity()))

        layout.addWidget(label_w, 0, 0); layout.addWidget(slider_w, 0, 1)
        layout.addWidget(label_h, 1, 0); layout.addWidget(slider_h, 1, 1)
        layout.addWidget(label_o, 2, 0); layout.addWidget(slider_o, 2, 1)

        btn_close = QPushButton("Done")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, 3, 0, 1, 2)
        dialog.exec_()

    def show_normal(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible(): self.hide()
            else: self.show_normal()

    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_locked and event.buttons() & Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GifOnTop()
    sys.exit(app.exec_())
