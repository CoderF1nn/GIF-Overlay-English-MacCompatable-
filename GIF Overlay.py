import sys
import os
import shutil
from pathlib import Path
from typing import Optional

# Core GUI components
from PyQt5.QtWidgets import (
    QApplication, QLabel, QFileDialog, QWidget,
    QVBoxLayout, QMenu, QMessageBox, QInputDialog,
    QDialog, QPushButton,
    QSlider, QGridLayout, QSystemTrayIcon, QAction
)
from PyQt5.QtGui import QMovie, QIcon
from PyQt5.QtCore import Qt, QSize

# --- UNIVERSAL PATH LOGIC ---
# This section prevents crashes on macOS by checking the OS first.
if sys.platform == "win32":
    CONFIG_DIR = Path(os.getenv('APPDATA', Path.home())) / "GIF Overlay"
else:
    # On Mac, we use a hidden folder in your home directory (no admin needed)
    CONFIG_DIR = Path.home() / ".gif_overlay"

# Create the folder if it doesn't exist
try:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # Fallback to current directory if home is blocked
    CONFIG_DIR = Path(".")

CONFIG_FILE = CONFIG_DIR / "last_gif_path.txt"
CONFIG_SETTINGS_FILE = CONFIG_DIR / "settings.txt"
GIF_SAVE_DIR = Path.home() / "Documents" / "GIF-save"

class GifOnTop(QWidget):
    def __init__(self):
        super().__init__()
        
        # Setup Window Properties
        self.setWindowTitle("GIF Overlay")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
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

        # 1. Load the last GIF (if it exists)
        self.load_last_gif(reset_default=False)

        # 2. Setup System Tray (Safely)
        self.setup_tray_icon()

        self.show()
        
        # If no GIF is loaded, prompt the user immediately
        if not self.current_gif_path:
            self.show_menu_at_center()

    def setup_tray_icon(self):
        """Setup the tray icon with a safety wrapper to prevent crashes."""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Handle icon path for bundled apps (PyInstaller uses _MEIPASS)
        try:
            base_dir = Path(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))))
            icon_path = base_dir / "app_icon.ico"
            
            if icon_path.exists():
                self.tray_icon.setIcon(QIcon(str(icon_path)))
            else:
                self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().SP_ComputerIcon))
        except Exception:
            # If any error occurs, use a generic system icon so the app doesn't crash
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
        """English menu items."""
        menu = QMenu(self)
        if self.is_locked:
            self.action_unlock = menu.addAction("Unlock Position")
            return menu

        change_menu = menu.addMenu("Change GIF")
        self.action_change_new = change_menu.addAction("Open New GIF...")
        self.action_change_saved = change_menu.addAction("From Saved Folder")

        menu.addSeparator()
        self.action_change_resize_opacity = menu.addAction("Resize & Opacity")
        self.action_toggle_pause = menu.addAction("Pause / Play")
        self.action_save = menu.addAction("Save to Collection")

        menu.addSeparator()
        close_menu = menu.addMenu("App Controls")
        self.action_close_minimize = close_menu.addAction("Minimize to Tray")
        self.action_close_quit = close_menu.addAction("Quit Application")

        menu.addSeparator()
        self.action_lock = menu.addAction("Lock Position")

        return menu

    def handle_menu_action(self, action):
        if self.is_locked:
            if hasattr(self, 'action_unlock') and action == self.action_unlock:
                self.is_locked = False
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
        elif action == self.action_close_minimize:
            self.hide()
        elif action == self.action_close_quit:
            QApplication.quit()
        elif action == self.action_lock:
            self.is_locked = True

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
        path, _ = QFileDialog.getOpenFileName(self, "Select GIF", "", "GIF Files (*.gif)")
        if path:
            self.load_gif(path, reset_default=True)

    def load_gif(self, path, reset_default=False):
        if not os.path.exists(path):
            return
            
        if self.movie:
            self.movie.stop()
            
        self.movie = QMovie(path)
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        
        # Determine Size
        self.movie.jumpToFrame(0)
        self.original_size = self.movie.currentPixmap().size()

        if reset_default or self.original_size.isEmpty():
            self.resize(300, 300)
            if self.movie: self.movie.setScaledSize(QSize(300, 300))
        else:
            self.resize(self.original_size)
            if self.movie: self.movie.setScaledSize(self.original_size)

        self.current_gif_path = path
        self.save_last_gif(path)

    def save_last_gif(self, path):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception:
            pass

    def load_last_gif(self, reset_default=False):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    path = f.read().strip()
                    if os.path.exists(path):
                        self.load_gif(path, reset_default=reset_default)
            except Exception:
                pass

    def open_saved_gif_dialog(self):
        if not GIF_SAVE_DIR.exists():
            QMessageBox.information(self, "Saved GIFs", "No saved GIFs yet.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select GIF", str(GIF_SAVE_DIR), "GIF Files (*.gif)")
        if path:
            self.load_gif(path, reset_default=True)

    def save_gif_to_documents(self):
        if not self.current_gif_path: return
        GIF_SAVE_DIR.mkdir(parents=True, exist_ok=True)
        name, ok = QInputDialog.getText(self, "Save GIF", "Filename:")
        if ok and name:
            if not name.endswith(".gif"): name += ".gif"
            shutil.copy2(self.current_gif_path, GIF_SAVE_DIR / name)

    def toggle_pause_gif(self):
        if self.movie:
            self.movie.setPaused(self.movie.state() == QMovie.Running)

    def open_resize_opacity_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        layout = QGridLayout(dialog)

        # Width
        layout.addWidget(QLabel("Width:"), 0, 0)
        sw = QSlider(Qt.Horizontal); sw.setRange(50, 1500); sw.setValue(self.width())
        layout.addWidget(sw, 0, 1)

        # Height
        layout.addWidget(QLabel("Height:"), 1, 0)
        sh = QSlider(Qt.Horizontal); sh.setRange(50, 1500); sh.setValue(self.height())
        layout.addWidget(sh, 1, 1)

        # Opacity
        layout.addWidget(QLabel("Opacity:"), 2, 0)
        so = QSlider(Qt.Horizontal); so.setRange(10, 100); so.setValue(int(self.windowOpacity()*100))
        layout.addWidget(so, 2, 1)

        def update():
            self.resize(sw.value(), sh.value())
            if self.movie: self.movie.setScaledSize(self.size())
            self.setWindowOpacity(so.value() / 100)

        sw.valueChanged.connect(update)
        sh.valueChanged.connect(update)
        so.valueChanged.connect(update)
        
        btn = QPushButton("Done")
        btn.clicked.connect(dialog.accept)
        layout.addWidget(btn, 3, 0, 1, 2)
        dialog.exec_()

    def show_normal(self):
        self.show()
        self.raise_()

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
    app.setQuitOnLastWindowClosed(False) # Keeps app alive in tray
    window = GifOnTop()
    sys.exit(app.exec_())
