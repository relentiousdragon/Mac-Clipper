#!/usr/bin/env python3
import os
import json
import sys
import subprocess
import base64
from datetime import datetime
from time import time
from PyQt6.QtCore import (Qt, QPoint, QSize, QThread, pyqtSignal, pyqtSlot, QEvent)
from PyQt6.QtGui import (QKeySequence, QShortcut, QGuiApplication, QIcon, QColor,
                         QPalette, QImage, QAction, QPixmap)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QListWidget, QListWidgetItem,
                             QMenu, QLineEdit, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
                             QGroupBox, QCheckBox, QSpinBox, QPushButton, QSystemTrayIcon,
                             QMessageBox, QRadioButton)
import Quartz

CONFIG_PATH = os.path.expanduser("~/Library/Application Support/Mac Clipper/config.json")

def load_config():
    default_config = {
        "hotkey": {
            "key": "V",
            "modifiers": ["command", "option"]
        },
        "max_items": 50,
        "run_at_login": True,
        "theme": "system"
    }
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            return {**default_config, **config}
    except (FileNotFoundError, json.JSONDecodeError):
        return default_config

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def set_login_item(enabled):
    app_path = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "../..")) 
    app_name = os.path.basename(app_path)
    script = f"""
    tell application "System Events"
        if {str(enabled).lower()} then
            if not (exists login item "{app_name}") then
                make login item at end with properties {{path:"{app_path}", hidden:true}}
            end if
        else
            if (exists login item "{app_name}") then
                delete login item "{app_name}"
            end if
        end if
    end tell
    """
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error setting login item: {result.stderr}")
    except Exception as e:
        print(f"Exception while setting login item: {e}")

def check_accessibility():
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to UI elements enabled'],
            capture_output=True, text=True
        )
        if "true" not in result.stdout.lower():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Accessibility Permission Required")
            msg.setText("Mac Clipper needs accessibility permissions to work properly")
            msg.setInformativeText("Please enable access in System Settings > Privacy & Security > Accessibility")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return False
        return True
    except Exception:
        return False

class GlobalHotkeyListener(QThread):
    activated = pyqtSignal()
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = True
        self.key_map = {
            "A": 0, "B": 11, "C": 8, "D": 2, "E": 14, "F": 3, "G": 5, "H": 4,
            "I": 34, "J": 38, "K": 40, "L": 37, "M": 46, "N": 45, "O": 31,
            "P": 35, "Q": 12, "R": 15, "S": 1, "T": 17, "U": 32, "V": 9,
            "W": 13, "X": 7, "Y": 16, "Z": 6,
        }
        self.accessibility_granted = False  

    def modifier_to_quartz(self, modifier):
        return {
            "command": Quartz.kCGEventFlagMaskCommand,
            "option": Quartz.kCGEventFlagMaskAlternate,
            "control": Quartz.kCGEventFlagMaskControl,
            "shift": Quartz.kCGEventFlagMaskShift
        }.get(modifier, 0)
        
    def run(self):
        keycode = self.key_map.get(self.config["hotkey"]["key"], 9)
        modifiers_mask = 0
        for mod in self.config["hotkey"]["modifiers"]:
            modifiers_mask |= self.modifier_to_quartz(mod)
            
        event_mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        retry_count = 0  
        
        while self.running:
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                event_mask,
                self.hotkey_callback,
                None
            )
            if tap:
                self.accessibility_granted = True
                runLoopSource = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
                Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), runLoopSource, Quartz.kCFRunLoopDefaultMode)
                Quartz.CGEventTapEnable(tap, True)
                print("Event tap created successfully")
                while self.running:
                    Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.1, False)
                break
            else:
                retry_count += 1
                if retry_count > 10:
                    print("Failed to create event tap after 10 attempts. Exiting.")
                    self.show_error_and_exit()
                    break
                if not self.accessibility_granted:
                    print(f"Failed to create event tap. Retrying in 10 seconds... (Attempt {retry_count}/10)")
                    self.check_accessibility_and_notify()
                self.sleep(10)

    def check_accessibility_and_notify(self):
        if check_accessibility():
            self.accessibility_granted = True
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Welcome to Mac Clipper!")
            msg.setText("Accessibility permissions have been granted. Mac Clipper is now ready to use!")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

    def show_error_and_exit(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Error: Accessibility Permission Denied")
        msg.setText("Mac Clipper could not start because accessibility permissions were not granted.")
        msg.setInformativeText("Please enable access in System Settings > Privacy & Security > Accessibility and restart the application.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        QApplication.quit()

    def hotkey_callback(self, proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventKeyDown:
            current_keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            current_flags = Quartz.CGEventGetFlags(event)
            
            keycode = self.key_map.get(self.config["hotkey"]["key"], 9)
            modifiers_mask = 0
            for mod in self.config["hotkey"]["modifiers"]:
                modifiers_mask |= self.modifier_to_quartz(mod)
                
            if current_keycode == keycode and current_flags & modifiers_mask == modifiers_mask:
                self.activated.emit()
                return None
        return event

class ClipboardWatcher(QThread):
    changed = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.last_content = ""
        
    def run(self):
        clipboard = QGuiApplication.clipboard()
        while True:
            image = clipboard.image()
            if image and not image.isNull():
                buffer = self.imageToBuffer(image)
                b64 = base64.b64encode(buffer).decode()
                item = "image:" + b64
            else:
                text = clipboard.text().strip()
                if text:
                    item = "text:" + text
                else:
                    item = ""
            if item and item != self.last_content:
                self.last_content = item
                clip_type = "image" if item.startswith("image:") else "text"
                self.changed.emit({
                    "type": clip_type,
                    "data": item,
                    "time": datetime.now().strftime("%H:%M")
                })
            self.msleep(500)

    def imageToBuffer(self, image):
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        data = buffer.data()
        return bytes(data)

class ClipboardManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        
        QApplication.setApplicationName("Mac Clipper")
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
        
        self.setWindowTitle("Mac Clipper")
        self.setFixedSize(450, 600)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.gear_icon = QIcon(self.create_gear_icon(QColor(0, 0, 0))) 
        self.gear_icon_white = QIcon(self.create_gear_icon(QColor(255, 255, 255))) 
        
        self.watcher = ClipboardWatcher()
        self.watcher.changed.connect(self.handle_clipboard_change)
        self.watcher.start()
        
        self.items = []
        self.max_items = self.config["max_items"]
        self.load_pinned()
        
        set_login_item(self.config["run_at_login"])
        
        self.previous_app = ""
        
        self.hotkey_listener = GlobalHotkeyListener(self.config)
        self.hotkey_listener.activated.connect(self.toggle_visibility)
        self.hotkey_listener.start()
        
        self.setup_ui()
        self.setup_fallback_hotkey()
        self.setup_menu_bar()
        self.apply_theme(self.config["theme"])
        
        self.last_toggle_time = 0

    def create_gear_icon(self, color):
        """Create a gear icon pixmap with the specified color"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        from PyQt6.QtGui import QPainter, QPen, QBrush
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        
        painter.drawEllipse(4, 4, 16, 16)
        painter.drawLine(12, 2, 12, 6)
        painter.drawLine(12, 18, 12, 22)
        painter.drawLine(2, 12, 6, 12)
        painter.drawLine(18, 12, 22, 12)
        
        painter.end()
        return pixmap

    def handle_clipboard_change(self, clip):
        if not clip or not clip.get("data"):
            return
        if any(item["data"] == clip["data"] for item in self.items):
            return
        print(f"New clip detected at {clip['time']}")
        self.items.insert(0, clip)
        if len(self.items) > self.max_items:
            unpinned = [item for item in self.items if not item.get("pinned", False)]
            if len(unpinned) > self.max_items - len([i for i in self.items if i.get("pinned", False)]):
                for item in reversed(unpinned):
                    if len(self.items) > self.max_items:
                        self.items.remove(item)
        self.update_list()

    def setup_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("MainWidget")
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(60)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        header_inner_layout = QHBoxLayout()
        header_inner_layout.setContentsMargins(0, 0, 0, 0)
        header_inner_layout.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("SearchBar")
        self.search.setPlaceholderText("Search clipboard history...")
        self.search.textChanged.connect(self.filter_items)
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        header_inner_layout.addWidget(self.search)

        self.settings_button = QPushButton()
        self.settings_button.setObjectName("SettingsButton")
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setFlat(True)
        self.settings_button.setText("⚙️") 
        self.settings_button.clicked.connect(self.show_preferences)
        header_inner_layout.addWidget(self.settings_button)

        header_layout.addLayout(header_inner_layout)
        layout.addWidget(header)
        
        self.list = QListWidget()
        self.list.setObjectName("ClipList")
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list)
        
        footer = QLabel("⌘⌥V to toggle • Click or press Enter to paste • Right-click for options")
        footer.setObjectName("Footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFixedHeight(30)
        layout.addWidget(footer)
        
        central_widget.setLayout(layout)
        self.update_list()

    def setup_settings_button(self):
        self.settings_button.setStyleSheet("""
            QPushButton#SettingsButton {
                background: transparent;
                border: none;
            }
            QPushButton#SettingsButton:hover {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 15px;
            }
        """)

    def get_system_theme(self):
        try:
            output = subprocess.check_output(["defaults", "read", "-g", "AppleInterfaceStyle"], stderr=subprocess.DEVNULL)
            return "dark" if output.decode().strip() == "Dark" else "light"
        except subprocess.CalledProcessError:
            return "light"

    def apply_theme(self, theme):
        if theme == "system":
            theme = self.get_system_theme()
        
        if theme == "dark":
            self.settings_button.setText("⚙️")
            self.setStyleSheet("""
                #MainWidget {
                    background: #2d2d2d;
                    border-radius: 12px;
                    border: 1px solid #444;
                }
                #Header {
                    background: #252525;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                    border-bottom: 1px solid #444;
                }
                #SearchBar {
                    background: #3a3a3a;
                    border: 1px solid #444;
                    border-radius: 8px;
                    padding: 8px;
                    color: #f0f0f0;
                    font-size: 14px;
                    selection-background-color: #4a6da7;
                }
                #SearchBar:focus {
                    border: 1px solid #4a6da7;
                }
                #ClipList {
                    background: #2d2d2d;
                    border: none;
                    border-radius: 0;
                    padding: 5px;
                }
                #ClipList::item {
                    border-radius: 6px;
                    margin: 3px;
                    padding: 4px;
                }
                #ClipList::item:selected {
                    background: #3a3a3a;
                }
                #ClipList QLabel {
                    color: #f0f0f0;  /* Ensure text clips are visible in dark mode */
                }
                #Footer {
                    background: #252525;
                    color: #888;
                    font-size: 11px;
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                    border-top: 1px solid #444;
                }
            """)
        else:  
            self.settings_button.setText("⚙️")  
            self.setStyleSheet("""
                #MainWidget {
                    background: #ffffff;
                    border-radius: 12px;
                    border: 1px solid #d0d0d0;
                }
                #Header {
                    background: #f5f5f5;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                    border-bottom: 1px solid #d0d0d0;
                }
                #SearchBar {
                    background: white;
                    border: 1px solid #d0d0d0;
                    border-radius: 8px;
                    padding: 8px;
                    color: #333;
                    font-size: 14px;
                    selection-background-color: #4a6da7;
                }
                #SearchBar:focus {
                    border: 1px solid #4a6da7;
                }
                #ClipList {
                    background: #ffffff;
                    border: none;
                    border-radius: 0;
                    padding: 5px;
                }
                #ClipList::item {
                    border-radius: 6px;
                    color: #333;
                    margin: 3px;
                    padding: 4px;
                }
                #ClipList::item:selected {
                    background: #e0e0e0;
                }
                #ClipList QLabel {
                    color: #333;  /* Ensure text clips are visible in light mode */
                }
                #Footer {
                    background: #f5f5f5;
                    color: #666;
                    font-size: 11px;
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                    border-top: 1px solid #d0d0d0;
                }
            """)
        self.settings_button.setText("⚙️")  

    def setup_menu_bar(self):
        menu_bar = self.menuBar()
        
        app_menu = menu_bar.addMenu("Mac Clipper")
        
        show_action = QAction("Show Clipboard", self)
        show_action.triggered.connect(self.show_clipboard)
        app_menu.addAction(show_action)
        
        preferences_action = QAction("Preferences...", self)
        preferences_action.triggered.connect(self.show_preferences)
        app_menu.addAction(preferences_action)
        
        app_menu.addSeparator()
        
        quit_action = QAction("Quit Mac Clipper", self)
        quit_action.triggered.connect(self.quit_app)
        app_menu.addAction(quit_action)

    def setup_fallback_hotkey(self):
        self.shortcut = QShortcut(QKeySequence("Ctrl+Alt+V"), self)
        self.shortcut.activated.connect(self.toggle_visibility)
        self.enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.enter_shortcut.activated.connect(self.paste_selected)

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down:
                self.list.setFocus()
                if self.list.count() > 0:
                    self.list.setCurrentRow(0)
                return True
        return super().eventFilter(obj, event)

    def paste_selected(self):
        if item := self.list.currentItem():
            if data := item.data(Qt.ItemDataRole.UserRole):
                self.copy_to_clipboard(data)
                self.paste_to_frontmost_app()

    def on_item_clicked(self, item):
        if data := item.data(Qt.ItemDataRole.UserRole):
            self.copy_to_clipboard(data)
            self.paste_to_frontmost_app()

    def copy_to_clipboard(self, content):
        clipboard = QGuiApplication.clipboard()
        if content.startswith("image:"):
            b64_str = content[len("image:"):]
            img_bytes = base64.b64decode(b64_str)
            image = QImage()
            if image.loadFromData(img_bytes, "PNG"):
                clipboard.setImage(image)
                print("Image copied to clipboard")
            else:
                print("Error loading image")
        elif content.startswith("text:"):
            text = content[len("text:"):]
            clipboard.setText(text)
            print(f"Text copied to clipboard: {text[:50]}...")

    @pyqtSlot()
    def toggle_visibility(self):
        now = time()
        if now - self.last_toggle_time < 0.20:
            print("Toggle ignored (too fast)")
            return
        self.last_toggle_time = now

        if self.isVisible():
            self.hide()
            print("Window hidden")
        else:
            self.show_clipboard()

    def show_clipboard(self):
        try:
            output = subprocess.check_output(
                ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
                stderr=subprocess.DEVNULL
            )
            self.previous_app = output.decode().strip()
        except subprocess.CalledProcessError:
            self.previous_app = ""
        self.show()
        self.raise_()
        self.activateWindow()
        self.move_center()
        self.search.setFocus()
        print("Window shown, previous app:", self.previous_app)

    def move_center(self):
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 3
        self.move(QPoint(x, y))

    def update_list(self):
        self.list.clear()
        if not self.items:
            effective_theme = self.config["theme"]
            if effective_theme == "system":
                effective_theme = self.get_system_theme()
            credits = QLabel()
            credits.setTextFormat(Qt.TextFormat.RichText)
            credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
            credits.setWordWrap(True)
            credits.setOpenExternalLinks(True)
            credits.setMinimumHeight(120)
            credits.setText("""
                <div style="font-size:14px; color:{color};">
                    <b>Made by Agent</b><br>
                    🐙 Github: <a style="color:#4a6da7;" href="https://github.com/relentiousdragon">relentiousdragon</a><br>
                    💬 Discord: agentzzrp<br>
                    🌐 Website: <a style="color:#4a6da7;" href="https://agent.is-a.dev">agent.is-a.dev</a>
                </div>
            """.format(color="#333" if effective_theme == "light" else "#f0f0f0"))
            item = QListWidgetItem()
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(credits.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, credits)
            return

        pinned_items = [item for item in self.items if item.get("pinned", False)]
        unpinned_items = [item for item in self.items if not item.get("pinned", False)]
        sorted_items = pinned_items + unpinned_items

        for clip in sorted_items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, clip["data"])
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            label.setMargin(10)
            
            if clip["type"] == "image":
                b64_str = clip["data"][len("image:"):]
                pin_html = (
                    '<div style="position: absolute; top: 5px; right: 5px; background: rgba(45,45,45,0.7); '
                    'border-radius: 50%; width: 20px; height: 20px; display: flex; '
                    'justify-content: center; align-items: center;">'
                    '<span style="color:#4a6da7; font-size:12px;">📌</span>'
                    '</div>'
                    if clip.get("pinned") else ""
                )
                html = f'''
                <div style="display: flex; flex-direction: column; align-items: center;">
                    <div style="position: relative; margin-bottom: 5px;">
                        <img src="data:image/png;base64,{b64_str}" 
                             style="display: block; max-width: 200px; max-height: 200px; border-radius: 4px;"/>
                        {pin_html}
                    </div>
                    <div style="color: #888; font-size: 11px; margin-top: 4px;">
                        {clip["time"]}
                    </div>
                </div>
                '''
                label.setText(html)
            else:
                text = clip["data"][len("text:"):]
                display_text = text.replace("\n", " ").strip()
                if len(display_text) > 100:
                    display_text = display_text[:100] + "..."
                
                effective_theme = self.config["theme"]
                if effective_theme == "system":
                    effective_theme = self.get_system_theme()
                
                text_color = "#4a6da7" if clip.get("pinned") else ("#333" if effective_theme == "light" else "#f0f0f0")
            pin_html = '<span style="color: #4a6da7;">📌</span>' if clip.get("pinned") else ""
            label.setText(
                f'<div style="color: {text_color}; font-size: 13px;">'
                f'{display_text}</div>'
                f'<div style="color: #888; font-size: 11px; margin-top: 4px;">'
                f'{clip["time"]} {pin_html}'
                f'</div>'
            )
            
            min_height = 80 if clip["type"] == "text" else 220
            list_item.setSizeHint(label.sizeHint().expandedTo(QSize(label.sizeHint().width(), min_height)))
            self.list.addItem(list_item)
            self.list.setItemWidget(list_item, label)

    def filter_items(self):
        query = self.search.text().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if data := item.data(Qt.ItemDataRole.UserRole):
                item.setHidden(query not in data.lower())

    def contextMenuEvent(self, event):
        item = self.list.itemAt(self.list.viewport().mapFromGlobal(event.globalPos()))
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        menu = QMenu(self)
        copy_action = menu.addAction(QIcon.fromTheme("edit-copy"), "Copy")
        paste_action = menu.addAction(QIcon.fromTheme("edit-paste"), "Paste")
        pin_action = menu.addAction(QIcon.fromTheme("pin"), "Toggle Pin")
        menu.addSeparator()
        delete_action = menu.addAction(QIcon.fromTheme("edit-delete"), "Delete")
        action = menu.exec(event.globalPos())
        if action == copy_action:
            self.copy_to_clipboard(data)
        elif action == paste_action:
            self.copy_to_clipboard(data)
            self.paste_to_frontmost_app()
        elif action == pin_action:
            self.toggle_pin(data)
        elif action == delete_action:
            self.delete_item(data)

    def toggle_pin(self, data):
        for clip in self.items:
            if clip["data"] == data:
                clip["pinned"] = not clip.get("pinned", False)
                break
        self.save_pinned()
        self.update_list()

    def delete_item(self, data):
        self.items = [clip for clip in self.items if clip["data"] != data]
        self.save_pinned()
        self.update_list()

    def paste_to_frontmost_app(self):
        try:
            if self.previous_app and self.previous_app != "Mac Clipper":
                script = f'tell application "{self.previous_app}" to activate'
                subprocess.run(["osascript", "-e", script], check=True)
            script = """
            tell application "System Events"
                keystroke "v" using command down
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=True)
            self.hide()
            print("Pasted to front app")
        except subprocess.CalledProcessError as e:
            print(f"Error pasting: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to paste to the application '{self.previous_app}'. Please ensure it is running and accessible."
            )

    def save_pinned(self):
        pinned = [clip for clip in self.items if clip.get("pinned", False)]
        with open(os.path.expanduser("~/pinned_clips.json"), "w") as f:
            json.dump(pinned, f)

    def load_pinned(self):
        try:
            with open(os.path.expanduser("~/pinned_clips.json"), "r") as f:
                pinned = json.load(f)
            self.items = pinned
            print(f"Loaded {len(self.items)} pinned clips")
        except (FileNotFoundError, json.JSONDecodeError):
            self.items = []

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos'):
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def show_preferences(self):
        self.prefs_window = PreferencesWindow(self)
        self.prefs_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.prefs_window.show()

    def apply_config(self):
        self.config = load_config()
        self.max_items = self.config["max_items"]
        set_login_item(self.config["run_at_login"])
        self.apply_theme(self.config["theme"])
        
        self.hotkey_listener.running = False
        self.hotkey_listener.wait()
        self.hotkey_listener = GlobalHotkeyListener(self.config)
        self.hotkey_listener.activated.connect(self.toggle_visibility)
        self.hotkey_listener.start()

    def quit_app(self):
        self.hotkey_listener.running = False
        self.hotkey_listener.wait()
        self.watcher.quit()
        QApplication.quit()

class PreferencesWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mac Clipper Preferences")
        self.setFixedSize(450, 650)  
        
        self.config = load_config()
        
        central = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)  
        layout.setSpacing(15)  
        
        hotkey_group = QGroupBox("Hotkey Configuration")
        hotkey_layout = QVBoxLayout()
        hotkey_layout.setSpacing(10)  
        
        self.key_edit = QLineEdit(self.config["hotkey"]["key"])
        self.key_edit.setFixedHeight(30)  
        self.command_check = QCheckBox("Command (⌘)")
        self.command_check.setChecked("command" in self.config["hotkey"]["modifiers"])
        self.option_check = QCheckBox("Option (⌥)")
        self.option_check.setChecked("option" in self.config["hotkey"]["modifiers"])
        self.control_check = QCheckBox("Control (⌃)")
        self.control_check.setChecked("control" in self.config["hotkey"]["modifiers"])
        self.shift_check = QCheckBox("Shift (⇧)")
        self.shift_check.setChecked("shift" in self.config["hotkey"]["modifiers"])
        
        hotkey_layout.addWidget(QLabel("Key:"))
        hotkey_layout.addWidget(self.key_edit)
        hotkey_layout.addWidget(self.command_check)
        hotkey_layout.addWidget(self.option_check)
        hotkey_layout.addWidget(self.control_check)
        hotkey_layout.addWidget(self.shift_check)
        hotkey_group.setLayout(hotkey_layout)
        
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout()
        theme_layout.setSpacing(10)
        self.theme_system = QRadioButton("System Theme")
        self.theme_light = QRadioButton("Light Mode")
        self.theme_dark = QRadioButton("Dark Mode")
        
        if self.config["theme"] == "system":
            self.theme_system.setChecked(True)
        elif self.config["theme"] == "light":
            self.theme_light.setChecked(True)
        else:
            self.theme_dark.setChecked(True)
            
        theme_layout.addWidget(self.theme_system)
        theme_layout.addWidget(self.theme_light)
        theme_layout.addWidget(self.theme_dark)
        theme_group.setLayout(theme_layout)
        
        other_settings_group = QGroupBox("Other Settings")
        other_settings_layout = QVBoxLayout()
        other_settings_layout.setSpacing(10)
        
        self.max_items_spin = QSpinBox()
        self.max_items_spin.setRange(10, 200)
        self.max_items_spin.setValue(self.config["max_items"])
        
        self.startup_check = QCheckBox("Launch at login")
        self.startup_check.setChecked(self.config["run_at_login"])
        
        other_settings_layout.addWidget(QLabel("Maximum items to store:"))
        other_settings_layout.addWidget(self.max_items_spin)
        other_settings_layout.addWidget(self.startup_check)
        other_settings_group.setLayout(other_settings_layout)
        
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save Preferences")
        save_btn.setFixedHeight(40)
        save_btn.clicked.connect(self.save_prefs)
        quit_btn = QPushButton("Quit")
        quit_btn.setFixedHeight(40)
        quit_btn.clicked.connect(self.quit_app)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(quit_btn)

        layout.addWidget(hotkey_group)
        layout.addWidget(theme_group)
        layout.addWidget(other_settings_group)
        layout.addStretch(1)  
        layout.addLayout(button_layout)
        central.setLayout(layout)
        self.setCentralWidget(central)

    def save_prefs(self):
        modifiers = []
        if self.command_check.isChecked():
            modifiers.append("command")
        if self.option_check.isChecked():
            modifiers.append("option")
        if self.control_check.isChecked():
            modifiers.append("control")
        if self.shift_check.isChecked():
            modifiers.append("shift")
            
        theme = "system"
        if self.theme_light.isChecked():
            theme = "light"
        elif self.theme_dark.isChecked():
            theme = "dark"
            
        self.config = {
            "hotkey": {
                "key": self.key_edit.text().upper(),
                "modifiers": modifiers
            },
            "max_items": self.max_items_spin.value(),
            "run_at_login": self.startup_check.isChecked(),
            "theme": theme
        }
        
        save_config(self.config)
        self.parent().apply_config()
        
        self.parent().apply_theme(self.config["theme"])
        self.parent().update_list()
        
        self.close()

    def quit_app(self):
        self.parent().quit_app()

if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_PluginApplication, True)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Mac Clipper")
    
    if not check_accessibility():
        sys.exit(1)
    
    manager = ClipboardManager()
    manager.hide()
    sys.exit(app.exec())
