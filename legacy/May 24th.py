# Unused: Work on later

# GUI
import webview
import json
import os
import time
import sys
# Keyboard And Mouse
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
# Key Listeners
import threading
from pynput.keyboard import Listener as KeyListener, Key
# OpenCV/Numpy/MSS
import cv2
import numpy as np
import mss
import ctypes
import Quartz
import math
# Logging
import requests
import io
# Initialize Controllers
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
macro_running = False
macro_thread = None
# Ctypes/Quartz For Special Click Types
if sys.platform == "win32":
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
elif sys.platform == "darwin":
    def _move_mouse(x, y):
        point = Quartz.CGPointMake(float(x), float(y))
        Quartz.CGWarpMouseCursorPosition(point)
        Quartz.CGAssociateMouseAndMouseCursorPosition(True)

    def _mouse_event(event_type, x, y):
        event = Quartz.CGEventCreateMouseEvent(
            None,
            event_type,
            Quartz.CGPointMake(float(x), float(y)),
            Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
def get_base_path():
    """Unified base directory for app data."""

    if getattr(sys, 'frozen', False):
        compiled = True
        # Compiled App → Use User Directory
        if sys.platform == "darwin":
            return os.path.join(
                os.path.expanduser("~"),
                "Library", "Application Support",
                "PyWareFishingV3"
            ), compiled
        elif sys.platform == "win32":
            return os.path.join(
                os.path.expanduser("~"),
                "AppData", "Roaming",
                "PyWareFishingV3"
            ), compiled
        else:
            return os.path.join(os.path.expanduser("~"), "PyWareFishingV3"), compiled
    compiled = False
    # Dev Mode → Project Directory
    return os.path.dirname(os.path.abspath(__file__)), compiled

BASE_PATH, IS_COMPILED = get_base_path()

# =========================
# CONFIG FOLDER
# =========================
CONFIGS_FOLDER = os.path.join(BASE_PATH, "configs")
LAST_CONFIG_FILE = os.path.join(BASE_PATH, "last_config.json")
os.makedirs(CONFIGS_FOLDER, exist_ok=True)

# Pre-compiled transformation matrix (Display P3 -> sRGB approximation for OpenCV BGR)
# Designed for cv2.transform() which expects an array of shape (1, 3, 3) or (3, 4)
if sys.platform == "darwin":
    # Columns are mapped to match BGR channel ordering
    P3_TO_SRGB_MATRIX = np.array([
        [ 1.0983, -0.0786, -0.0197],  # B_out depends heavily on B_in
        [ 0.0000,  1.0720, -0.0720],  # G_out 
        [ 0.0000, -0.2248,  1.2249]   # R_out depends heavily on R_in
    ], dtype=np.float32)
else:
    P3_TO_SRGB_MATRIX = None

# Screen dimensions via mss (no tkinter needed)
with mss.mss() as _sct:
    _m = _sct.monitors[0]
    SCREEN_WIDTH  = _m["width"]
    SCREEN_HEIGHT = _m["height"]

CONFIG_DIR = CONFIGS_FOLDER
IMAGES_PATH = os.path.join(BASE_PATH, "images")
DEBUG_DIR = BASE_PATH

CONFIG_PATH = LAST_CONFIG_FILE
APP_VERSION = "4.0"
# Area Selector — pywebview-based (no tkinter)
class AreaSelector:
    """
    Fullscreen transparent overlay implemented as a second pywebview window.
    The HTML canvas handles all drawing and drag/resize interaction.
    Python is only needed for:
      - supplying initial area data  (get_areas)
      - receiving live mouse status  (on_mouse_move)
      - receiving final saved areas  (save_areas)
    """

    # Path to the overlay HTML relative to the ui/ folder
    HTML_FILE = "ui/area_selector.html"

    def __init__(self, parent, shake_area, fish_area, friend_area, totem_area, callback):
        self.parent   = parent
        self.callback = callback
        self._open    = True

        # Store areas as plain dicts (width/height keys)
        self._areas = {
            "shake":  shake_area.copy(),
            "fish":   fish_area.copy(),
            "friend": friend_area.copy(),
            "totem":  totem_area.copy(),
        }

        # Create a second, frameless, transparent, fullscreen pywebview window.
        # js_api=self exposes get_areas / on_mouse_move / save_areas to JS.
        self._win = webview.create_window(
            "Area Selector",
            self.HTML_FILE,

            js_api=self,

            # Window Style
            transparent=True,
            frameless=True,
            easy_drag=False,

            # Keep Above Everything
            on_top=True,

            # Prevent Resizing / Moving
            resizable=False,

            # Fullscreen Size
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,

            # Lock Position
            x=0,
            y=0,

            background_color="#000000",
        )
        self._win.events.closed += self._on_closed

    # ── JS API methods (called from area_selector.html) ───────────────────────

    def get_areas(self):
        """Called by JS on startup to get initial box positions."""
        return self._areas

    def on_mouse_move(self, mouse_x, mouse_y, current_boxes):
        """
        Called by JS on every mousemove so the main window status bar
        can show live position ratios.
        """
        if not self._open:
            return

        # Keep Python's cached areas completely in sync with live dragging in JS
        for name in ("shake", "fish", "friend", "totem"):
            b = current_boxes.get(name, {})
            if b:
                self._areas[name] = {
                    "x":      int(b.get("x", 0)),
                    "y":      int(b.get("y", 0)),
                    "width":  int(b.get("w", b.get("width", 0))),
                    "height": int(b.get("h", b.get("height", 0))),
                }

        for name in ("shake", "fish", "friend", "totem"):
            b = current_boxes.get(name, {})
            if not b:
                continue
            bx, by = b.get("x", 0), b.get("y", 0)
            bw, bh = b.get("w", 1) or b.get("width", 1), b.get("h", 1) or b.get("height", 1)
            if bx <= mouse_x <= bx + bw and by <= mouse_y <= by + bh:
                xr = round((mouse_x - bx) / bw, 2)
                yr = round((mouse_y - by) / bh, 2)
                self.parent.set_status(f"{name.upper()} → X RATIO: {xr}, Y RATIO: {yr}")
                return
        self.parent.set_status("Area selector opened (press key again to close)")

    def save_areas(self, areas):
        """
        Called by JS when the user presses Escape/F6 to confirm and close.
        Converts {x,y,w,h} → {x,y,width,height} then fires the Python callback.
        """
        if not self._open:
            return
        self._open = False
        out = {}
        for name, b in areas.items():
            out[name] = {
                "x":      b["x"],
                "y":      b["y"],
                "width":  b.get("w", b.get("width", 0)),
                "height": b.get("h", b.get("height", 0)),
            }
        self.callback(out["shake"], out["fish"], out["friend"], out["totem"])
        if hasattr(self.parent, "_keys_held"):
            self.parent._keys_held.discard("f6")
        self.parent.set_status("Area selector closed")
        try:
            self._win.destroy()
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_closed(self):
        """Fires when the webview window is destroyed for any reason."""
        if self._open:
            # Window closed without save_areas (e.g. OS close); still fire callback
            self._open = False
            self.callback(
                self._areas["shake"], self._areas["fish"],
                self._areas["friend"], self._areas["totem"],
            )
            self.parent.set_status("Area selector closed")

    def is_open(self):
        return self._open

    def close(self):
        """Force-close from Python (e.g. hotkey toggle)."""
        if self._open:
            self.save_areas({
                name: {"x": b["x"], "y": b["y"],
                       "w": b.get("w", b.get("width",0)),
                       "h": b.get("h", b.get("height",0))}
                for name, b in self._areas.items()
            })
class Api:
    def __init__(self):
        self.vars = {} # Save Entry Variables Here
        self.current_config = self.get_last_config()
        self.load_settings_into_vars(self.current_config)
        # Key hit detection (press + release = one hit, prevents repeat-key misfires)
        self._keys_held = set()
        # Start Hotkey Listener
        try:
            self.key_listener = KeyListener(on_press=self.on_key_press, on_release=self.on_key_release)
            self.key_listener.daemon = True
            self.key_listener.start()
        except Exception as e:
            print("Error: ", e)
        # Store Screen Width And Height To Use Later
        self.SCREEN_WIDTH = SCREEN_WIDTH
        self.SCREEN_HEIGHT = SCREEN_HEIGHT
        self.SCREEN_SCALE = ((self.SCREEN_WIDTH / 1920) + (self.SCREEN_HEIGHT / 1080)) / 2
        # Macro State
        self.macro_running = False
        self.macro_thread = None
        # Detection Variables
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None
        self.last_cached_box_length = None  # Cached Bar Size From Minigame For Arrow Estimation
        self.last_input_time = 0.0
        self.cooldown_duration = 1.0  # 1 second cooldown
        # P/D State Variables
        self.prev_error = 0.0      # Previous Error Term
        self.last_time = None      # Timestamp Of Last Pd Sample
        self.prev_measurement = None
        self.filtered_derivative = 0.0
        self.last_bar_size = None
        self.pid_source = None  # "Bar" Or "Arrow"
        self.pid_integral = 0.0 # Used For Normal Pid
        self.pid_last_time = 0
        self.pid_last_error = 0.0
        self._pid_filtered_d = 0.0  # Used For Derivative Smoothing

        # Arrow-Based Box Estimation Variables
        self.last_indicator_x = None
        self.last_holding_state = None
        self.pending_holding_state = None
        self.pending_indicator_x = None
        self.estimated_box_length = None
        self.last_left_x = None
        self.last_right_x = None
        self.last_known_box_center_x = None
        
        # Arrow estimation tracking
        self._last_bar_left_x = None
        self._last_bar_right_x = None
        self._last_bar_box_size = None
        self._last_bar_center_x = None
        self.last_arrow_delta = None
        # Safe Defaults Before Key Listener Starts (Will Be Overwritten By Load_Misc_Settings)
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
        self.current_rod_name = "Basic Rod"
        # Calculate scaling factors
        self.scale_x_1440 = self.SCREEN_WIDTH / 2560
        self.scale_y_1440 = self.SCREEN_HEIGHT / 1440
        # Screen Capture Variables — Mss Instances Are Per-Thread (See _Thread_Local)
        self._thread_local = threading.local()
        self._monitor = {}      # Pre-Allocated Monitor Dict, Reused Every Grab
        self._scale_cache = None  # Cached Dpi Scale Factor

        # Buffer For Capture/Logic Thread Decoupling (Used In Start_Macro())
        self._cap_lock = threading.Lock()
        self._cap_frame = None    # Latest Full Screen Frame
        self._cap_event = threading.Event()  # Signals A New Frame Pair Is Ready
        self._active_capture_stop = None  # Stop Event For The Currently Running Capture Thread
        self._active_capture_thread = None  # Thread Object For The Currently Running Capture Thread

        self.webhook_cycle_counter = 0
        self.totem_cycle_counter = 0

        self.load_misc_settings()
    def start_eyedropper(self):
        pass
    # ---------------------
    # Save Config
    # ---------------------
    def save_config(self, config_name, settings):
        try:
            if not config_name:
                return {
                    "success": False,
                    "error": "No config selected."
                }
            folder = os.path.join(
                CONFIGS_FOLDER,
                config_name
            )
            os.makedirs(folder, exist_ok=True)
            self.vars.update(settings)
            self.current_config = config_name
            self.save_last_config(config_name)
            config_path = os.path.join(
                folder,
                "config.json"
            )
            with open(config_path, "w") as f:
                json.dump(
                    settings,
                    f,
                    indent=4
                )
            return {
                "success": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    # ---------------------
    # Load Config
    # ---------------------
    def load_config(self, config_name):
        try:
            if not config_name:
                return {
                    "success": False,
                    "error": "No config selected."
                }
            config_path = os.path.join(
                CONFIGS_FOLDER,
                config_name,
                "config.json"
            )
            with open(config_path, "r") as f:
                settings = json.load(f)
            self.vars = settings.copy()
            self.current_config = config_name
            self.save_last_config(config_name)
            return {
                "success": True,
                "settings": settings
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    # ---------------------
    # List Configs
    # ---------------------
    def list_configs(self):
        try:
            configs = []
            for folder in os.listdir(CONFIGS_FOLDER):
                full_path = os.path.join(
                    CONFIGS_FOLDER,
                    folder
                )
                if os.path.isdir(full_path):
                    configs.append(folder)
            return configs
        except Exception as e:
            return []
    # ---------------------
    # Settings State
    # ---------------------
    def update_settings(self, settings):
        self.vars.update(settings)
        return {
            "success": True
        }
    def get_last_config(self):
        try:
            if os.path.exists(LAST_CONFIG_FILE):
                with open(LAST_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                return data.get("last_config", "")
        except Exception:
            pass
        return ""
    def save_last_config(self, config_name):
        try:
            data = {}
            if os.path.exists(LAST_CONFIG_FILE):
                with open(LAST_CONFIG_FILE, "r") as f:
                    data = json.load(f)
            data["last_config"] = config_name
            with open(LAST_CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print("Error saving last config:", e)
    def resolve_config_name(self, config_name):
        configs = self.list_configs()
        if config_name in configs:
            return config_name
        for name in configs:
            if name.lower() == str(config_name).lower():
                return name
        return configs[0] if configs else ""
    def load_settings_into_vars(self, config_name):
        config_name = self.resolve_config_name(config_name)
        if not config_name:
            return
        config_path = os.path.join(
            CONFIGS_FOLDER,
            config_name,
            "config.json"
        )
        try:
            with open(config_path, "r") as f:
                self.vars = json.load(f)
            self.current_config = config_name
            self.save_last_config(config_name)
        except Exception as e:
            print("Error loading config:", e)
    def get_startup_config(self):
        config_name = self.resolve_config_name(self.current_config)
        if not config_name:
            return {
                "success": False,
                "error": "No configs found."
            }
        result = self.load_config(config_name)
        if result.get("success"):
            result["config_name"] = config_name
        return result
    # ---------------------
    # Delete Config
    # ---------------------
    def delete_config(self, config_name):
        try:
            folder = os.path.join(
                CONFIGS_FOLDER,
                config_name
            )
            config_path = os.path.join(
                folder,
                "config.json"
            )
            if os.path.exists(config_path):
                os.remove(config_path)
            if os.path.exists(folder):
                os.rmdir(folder)
            return {
                "success": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    def load_misc_settings(self):
        """Load miscellaneous settings from last_config.json."""

        # Defaults
        self.current_rod_name = "Basic Rod"

        self.bar_areas = {
            "shake": None,
            "fish": None,
            "friend": None,
            "totem": None
        }

        # Default Hotkeys
        start_key  = "F5"
        change_key = "F6"
        stop_key   = "F7"

        try:
            path = os.path.join(BASE_PATH, "last_config.json")

            if not os.path.exists(path):
                return

            with open(path, "r") as f:
                data = json.load(f)

            # Rod
            self.current_rod_name = data.get("last_rod", "Basic Rod")

            # Bar Areas
            loaded_areas = data.get("bar_areas", {})

            for key in ["shake", "fish", "friend", "totem"]:
                area = loaded_areas.get(key)

                if isinstance(area, dict):
                    self.bar_areas[key] = {
                        "x": int(area.get("x", 0)),
                        "y": int(area.get("y", 0)),
                        "width": int(area.get("width", 0)),
                        "height": int(area.get("height", 0)),
                    }

            # Hotkeys
            start_key  = data.get("start_key", "F5")
            change_key = data.get("change_bar_areas_key", "F6")
            stop_key   = data.get("stop_key", "F7")

        except Exception as e:
            print(f"Failed to load misc settings: {e}")

        # Convert Hotkeys
        self.hotkey_start = self._string_to_key(start_key)
        self.hotkey_change_areas = self._string_to_key(change_key)
        self.hotkey_stop = self._string_to_key(stop_key)
    def save_misc_settings(self):
        """Save miscellaneous settings."""

        path = os.path.join(BASE_PATH, "last_config.json")

        # Existing Data
        data = {}

        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except:
                pass

        # Clean Areas
        clean_bar_areas = {}

        for key in ["shake", "fish", "friend", "totem"]:

            area = self.bar_areas.get(key)

            if isinstance(area, dict):

                clean_bar_areas[key] = {
                    "x": int(area.get("x", 0)),
                    "y": int(area.get("y", 0)),
                    "width": int(area.get("width", 0)),
                    "height": int(area.get("height", 0)),
                }

            else:
                clean_bar_areas[key] = None

        # Save
        data["last_rod"] = self.current_rod_name
        data["bar_areas"] = clean_bar_areas

        # Optional Hotkeys
        # data["start_key"] = ...
        # data["change_bar_areas_key"] = ...
        # data["stop_key"] = ...

        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    # Area Selector
    def _get_scale_factor(self):
        """
        Return display backing scale factor.
        macOS returns true Retina pixel ratio.
        Other platforms return 1.0.
        """
        if self._scale_cache is not None:
            return self._scale_cache

        if sys.platform == "darwin":
            try:
                display_id = Quartz.CGMainDisplayID()

                pixel_width = Quartz.CGDisplayPixelsWide(display_id)

                bounds = Quartz.CGDisplayBounds(display_id)
                logical_width = bounds.size.width

                scale = pixel_width / logical_width if logical_width else 1.0

                # Normalize tiny floating-point errors
                if abs(scale - 1.0) < 0.15:
                    scale = 1.0
                elif abs(scale - 2.0) < 0.15:
                    scale = 2.0

                self._scale_cache = scale

            except Exception:
                self._scale_cache = 1.0

        else:
            self._scale_cache = 1.0
        return self._scale_cache
    def open_area_selector(self):
        # Toggle Off If Already Open
        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.is_open():
            self.area_selector.close()
            return
        screen_w = SCREEN_WIDTH
        screen_h = SCREEN_HEIGHT
        # Default Fallback Areas
        def default_shake_area():
            left = int(screen_w * 0.1041)
            top = int(screen_h * 0.0925)
            right = int(screen_w * 0.8958)
            bottom = int(screen_h * 0.7888)
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        def default_fish_area():
            left = int(screen_w * 0.2844)
            top = int(screen_h * 0.7981)
            right = int(screen_w * 0.7141)
            bottom = int(screen_h * 0.8370)
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        def default_friend_area():
            left = int(screen_w * 0.0046)
            top = int(screen_h * 0.8583)
            right = int(screen_w * 0.0401)
            bottom = int(screen_h * 0.94)
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        def default_totem_area():
            left = int(screen_w * 0.9531)
            top = int(screen_h * 0.8333)
            right = int(screen_w * 0.9739)
            bottom = int(screen_h * 0.8796)
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        # Load Saved Areas Or Fallback
        shake_area  = self.bar_areas.get("shake")  if isinstance(self.bar_areas.get("shake"),  dict) else default_shake_area()
        fish_area   = self.bar_areas.get("fish")   if isinstance(self.bar_areas.get("fish"),   dict) else default_fish_area()
        friend_area = self.bar_areas.get("friend") if isinstance(self.bar_areas.get("friend"), dict) else default_friend_area()
        totem_area  = self.bar_areas.get("totem")  if isinstance(self.bar_areas.get("totem"),  dict) else default_totem_area()
        # Callback when the selector window saves and closes
        def on_done(shake, fish, friend, totem):
            self.bar_areas["shake"]  = shake
            self.bar_areas["fish"]   = fish
            self.bar_areas["friend"] = friend
            self.bar_areas["totem"]  = totem
            self.save_misc_settings()
            self.area_selector = None
        # Open the pywebview overlay — no tkinter needed, no thread restrictions
        self.area_selector = AreaSelector(
            parent=self,
            shake_area=shake_area, fish_area=fish_area,
            friend_area=friend_area, totem_area=totem_area,
            callback=on_done,
        )
        self.set_status("Area selector opened")
    # Macro helper functions
    # Click At X/Y Position
    def _click_at(self, x, y, click_count=1):
        if sys.platform == "win32":
            # Move Cursor
            windll.SetCursorPos(x, y)
            # Important: Tiny Movement So Roblox Registers Input
            windll.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            for i in range(click_count):
                windll.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                windll.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                if i < click_count - 1:
                    time.sleep(0.03)
        elif sys.platform == "darwin":
            x = int(x)
            y = int(y)

            # Move cursor
            _move_mouse(x, y)

            # Tiny movement (Roblox trick)
            _move_mouse(x, y + 1)

            for i in range(click_count):
                _mouse_event(Quartz.kCGEventLeftMouseDown, x, y)
                _mouse_event(Quartz.kCGEventLeftMouseUp, x, y)

                if i < click_count - 1:
                    time.sleep(0.03)
        else:
            mouse_controller.position = (x, y)
            time.sleep(0.01)
            # Jitter To Prevent Roblox From Crashing
            mouse_controller.position = (x + 3, y + 3)
            mouse_controller.position = (x, y)
            mouse_controller.press(Button.left)
            time.sleep(0.04)
            mouse_controller.release(Button.left)
    # Logging-Related Functions
    def _discord_text_worker(self, webhook_url, message_prefix, loop_count, show_status):
        """Worker function to send text webhook."""
        logging_name = self.vars["logging_name"]
        webhook_url2 = self.vars["logging_url"]
        try:
            if show_status == True:
                payload = {
                    'content': f'{message_prefix}🎣 Cycle completed\n🔄 {loop_count}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': logging_name,
                    'embeds': [{
                        'description': f'{loop_count}',
                        'color': 0x5865F2,
                        'timestamp': time.strftime("%Y-%m-%dT%H:%M:%S")
                    }]
                }
                response = requests.post(webhook_url, json=payload, timeout=10)
            else:
                payload = {
                    'content': f'{message_prefix}🎣 Cycle failed\n🔄 {loop_count}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': logging_name,
                    'embeds': [{
                        'description': f'{loop_count}',
                        'color': 0x5865F2,
                        'timestamp': time.strftime("%Y-%m-%dT%H:%M:%S")
                    }]
                }
                response = requests.post(webhook_url2, json=payload, timeout=10)
            if response.status_code == 200 or response.status_code == 204:
                if show_status == True:
                    self.set_status(f"Discord text sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord text failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending Discord text: {e}")
    def _discord_screenshot_worker(self, webhook_url, message_prefix, loop_count, show_status):
        logging_name = self.vars["logging_name"]
        webhook_url2 = self.vars["logging_url"]
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = np.array(sct.grab(monitor))

            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

            _, buffer = cv2.imencode(".png", screenshot)
            img_byte_arr = io.BytesIO(buffer.tobytes())

            files = {'file': ('screenshot.png', img_byte_arr, 'image/png')}
            if show_status == True:
                payload = {
                    'content': f'{message_prefix}🎣 **Cycle completed**\n🔄 {loop_count}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': logging_name
                }
                response = requests.post(webhook_url, data=payload, files=files, timeout=10)
            else:
                payload = {
                    'content': f'{message_prefix}🎣 **Cycle failed**\n🔄 {loop_count}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': logging_name
                }
                response = requests.post(webhook_url2, data=payload, files=files, timeout=10)
            if response.status_code in (200, 204):
                if show_status == True:
                    self.set_status(f"Discord screenshot sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord screenshot failed: {response.status_code}")

        except Exception as e:
            self.set_status(f"Error: sending Discord screenshot: {e}")
    def _debug_log_worker(self, text, loop_count, show_status=False):
        """Write debug logs to a text file."""
        try:
            # Use base path for logs
            log_dir = BASE_PATH
            os.makedirs(log_dir, exist_ok=True)

            # Daily log file
            log_file = os.path.join(
                log_dir,
                f"debug_{time.strftime('%Y-%m-%d')}.txt"
            )

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            log_entry = (
                "==================================================\n"
                f"🎣 {text}\n"
                f"🔄 {loop_count}\n"
                f"🕐 {timestamp}\n"
                "==================================================\n\n"
            )

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

            if show_status:
                self.set_status(f"Debug log saved ({loop_count})")

        except Exception as e:
            self.set_status(f"Error writing debug log: {e}")
    def test_logging(self):
        self.send_logging("**Logging is working**", "TEST", show_status=True)
    def _auto_bug_report(self, error_text, phase="Unknown"):
        """Send a text-only crash report to the bug report webhook or save to file."""
        # Safely get values and reset state
        self._set_fish_overlay_mode("idle")
        logging_mode = self.vars["logging_mode"]
        if logging_mode == "Disabled":
            return

        platform_name = {"darwin": "macOS", "win32": "Windows", "linux": "Linux"}.get(sys.platform, sys.platform)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare the report text
        report_text = (
            "Auto Bug Report\n"
            f"Version: {APP_VERSION}\n"
            f"Platform: {platform_name}\n"
            f"Phase: {phase}\n"
            f"Time: {timestamp}\n\n"
            f"{error_text}"
        )

        if logging_mode == "File":
            try:
                log_dir = BASE_PATH
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, f"debug_{time.strftime('%Y-%m-%d')}.txt")
                
                log_entry = (
                    "==================================================\n"
                    "🐞 AUTO BUG REPORT\n"
                    f"📂 Phase: {phase}\n"
                    f"🕐 {timestamp}\n"
                    "--------------------------------------------------\n"
                    f"{report_text}\n"
                    "==================================================\n\n"
                )
                
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(log_entry)
                
                self.set_status(f"Bug report saved to file ({phase})")
                return
            except Exception as e:
                self.set_status(f"Error saving bug report to file: {e}")
                return

        webhook_url = self.vars["logging_url"]
        logging_name = self.vars["logging_name"]
        
        crash_line = "Unknown"
        for line in reversed(error_text.splitlines()):
            if line.strip().startswith('File "') and ", line " in line:
                crash_line = line.strip()
                break

        payload = {
            "content": (
                "**Auto Bug Report**\n"
                f"Version: `{APP_VERSION}` | Platform: `{platform_name}` | Phase: `{phase}`\n"
                f"Crash line: `{crash_line}`\n"
                "Full traceback with line numbers is attached as text."
            ),
            "username": logging_name
        }

        try:
            report_bytes = io.BytesIO(report_text.encode("utf-8"))
            files = {"file": ("bug_report.txt", report_bytes, "text/plain")}
            response = requests.post(webhook_url, data=payload, files=files, timeout=10)

            if response.status_code not in (200, 204):
                self.set_status(f"Error: Bug report failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending bug report: {e}")
    def send_logging(self, text, loop_count, show_status=True):
        logging_mode = self.vars["logging_mode"]
        if logging_mode == "Disabled":
            self.set_status("⚠ Logging is disabled.")
            return
        if not logging_mode == "File":
            # logging_url
            webhook_url = self.vars["logging_url"].strip()

            if not webhook_url.startswith("https://discord.com/api/webhooks/"):
                self.set_status("Error: Invalid webhook URL.")
                return
        
        if show_status == True:
            self.set_status("Sending test webhook...")

        if logging_mode == "Screenshot":
            thread = threading.Thread(
                target=self._discord_screenshot_worker,
                args=(webhook_url, f"{text}\n", loop_count, show_status),
                daemon=True
            )
        elif logging_mode == "File":
            thread = threading.Thread(
                target=self._debug_log_worker,
                args=(text, loop_count, show_status),
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._discord_text_worker,
                args=(webhook_url, f"{text}\n", loop_count, show_status),
                daemon=True
            )
        thread.start()
    def _grab_screen_full(self, thread_local):
        scale = self._get_scale_factor()

        if not hasattr(thread_local, "sct"):
            thread_local.sct = mss.mss()

        if not hasattr(thread_local, "monitor"):
            thread_local.monitor = {
                "left": 0,
                "top": 0,
                "width": int(self.SCREEN_WIDTH * scale),
                "height": int(self.SCREEN_HEIGHT * scale)
            }

        hdr = self.vars.get("hdr", "off")

        m = thread_local.monitor
        img = thread_local.sct.grab(m)

        # Convert the mss image object directly to a numpy array to handle channel alignment
        frame = np.array(img, dtype=np.uint8)
        
        bgr_frame = frame[:, :, :3]
        
        # Mathematical shift correction safely applied for macOS stability
        if hdr == "on":
            return self._correct_macos_color(bgr_frame)
        else:
            return bgr_frame
    def _correct_macos_color(self, frame):
        """
        Applies an optimized matrix transformation to correct Display P3 
        colors back into standard sRGB space instantly on macOS.
        """
        if P3_TO_SRGB_MATRIX is not None:
            # cv2.transform operates directly on the 3 channels very fast in C++
            return cv2.transform(frame, P3_TO_SRGB_MATRIX)
        return frame
    def _capture_loop_full(self, stop_event, scan_delay):
        thread_local = threading.local()

        # On Macos, Mss Uses Core Graphics Which Is Slow To Call In A Tight Loop.
        # Enforce A Minimum Sleep So We Don'T Saturate The Cpu And Starve The Game
        # And The Pid Thread.  At 20 Fps A Frame Is ~0.05 S; Floor At 0.033 S
        # (~30 Fps) So We Never Spin Faster Than The Game Can Produce New Pixels.
        _mac_floor = 0.033 if sys.platform == "darwin" else 0.0

        try:
            while self.macro_running and not stop_event.is_set():
                t0 = time.perf_counter()
                frame = self._grab_screen_full(thread_local)

                with self._cap_lock:
                    self._cap_frame = frame
                    self._cap_event.set()

                elapsed = time.perf_counter() - t0
                sleep_for = max(_mac_floor, scan_delay) - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            sct = getattr(thread_local, "sct", None)
            if sct is not None:
                try:
                    sct.close()
                except Exception:
                    pass
            self._cap_event.set()
    def _stop_active_capture(self, join_timeout=0.2):
        stop_event = getattr(self, "_active_capture_stop", None)
        thread = getattr(self, "_active_capture_thread", None)

        if stop_event is not None:
            stop_event.set()

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(join_timeout)

        self._active_capture_stop = None
        self._active_capture_thread = None

    def _start_capture(self, scan_delay):
        """
        Starts a background thread that continuously grabs full frames.
        Stops any previously running capture thread first to prevent races.
        Returns a stop_event to terminate the new thread.
        """
        # Overlapping Capture Threads Share _Cap_Frame/_Cap_Event/_Cap_Lock And
        # Will Race Each Other, Which Causes Segfaults In The Mss/Coregraphics
        # Capture Path On Macos.
        self._stop_active_capture()

        self._cap_frame = None

        # Ensure These Exist
        if not hasattr(self, "_cap_lock"):
            self._cap_lock = threading.Lock()
        if not hasattr(self, "_cap_event"):
            self._cap_event = threading.Event()

        self._cap_event.clear()
        stop_event = threading.Event()
        self._active_capture_stop = stop_event  # Track The Active Stop Event

        _mac_floor = 0.033 if sys.platform == "darwin" else 0.0

        def _loop():
            try:
                thread_local = threading.local()

                while self.macro_running and not stop_event.is_set():
                    t0 = time.perf_counter()
                    frame = self._grab_screen_full(thread_local)

                    with self._cap_lock:
                        self._cap_frame = frame
                        self._cap_event.set()

                    elapsed = time.perf_counter() - t0
                    sleep_for = max(_mac_floor, scan_delay) - elapsed
                    if sleep_for > 0:
                        time.sleep(sleep_for)
            finally:
                sct = getattr(thread_local, "sct", None)
                if sct is not None:
                    try:
                        sct.close()
                    except Exception:
                        pass
                self._cap_event.set()
                if self._active_capture_stop is stop_event:
                    self._active_capture_stop = None
                if self._active_capture_thread is threading.current_thread():
                    self._active_capture_thread = None

        thread = threading.Thread(target=_loop, daemon=True, name="PyWareCapture")
        self._active_capture_thread = thread
        thread.start()
        return stop_event
    
    def _get_areas(self, area_key):
        # Apply Scale Factor
        scale = self._get_scale_factor()
        
        area_data = self.bar_areas.get(area_key)
        if isinstance(area_data, dict):
            left   = area_data["x"]
            top    = area_data["y"]
            right  = area_data["x"] + area_data["width"]
            bottom = area_data["y"] + area_data["height"]
            width  = area_data["width"]
            height = area_data["height"]
        else:
            left, top, right, bottom = self._get_default_areas(area_key)
            width  = right - left
            height = bottom - top
            
        left2   = int(left * scale)
        top2    = int(top * scale)
        right2  = int(right * scale)
        bottom2 = int(bottom * scale)
        width2  = int(width * scale)
        height2 = int(height * scale)
        return left2, top2, right2, bottom2, width2, height2

    def _get_default_areas(self, area):
        if area == "shake":
            left = int(self.SCREEN_WIDTH * 0.1041)
            top = int(self.SCREEN_HEIGHT * 0.0925)
            right = int(self.SCREEN_WIDTH * 0.8958)
            bottom = int(self.SCREEN_HEIGHT * 0.7888)
        elif area == "fish":
            left   = int(self.SCREEN_WIDTH  * 0.2844)
            top    = int(self.SCREEN_HEIGHT * 0.7981)
            right  = int(self.SCREEN_WIDTH  * 0.7141)
            bottom = int(self.SCREEN_HEIGHT * 0.8370)
        elif area == "friend":
            left = int(self.SCREEN_WIDTH * 0.0046)
            top = int(self.SCREEN_HEIGHT * 0.8583)
            right = int(self.SCREEN_WIDTH * 0.0401)
            bottom = int(self.SCREEN_HEIGHT * 0.94)
        else:
            left = int(self.SCREEN_WIDTH * 0.9531)
            top = int(self.SCREEN_HEIGHT * 0.8333)
            right = int(self.SCREEN_WIDTH * 0.9739)
            bottom = int(self.SCREEN_HEIGHT * 0.8796)
        return left, top, right, bottom

    def _grab_screen_region(self, left, top, right, bottom):
        """Optimized path for MSS screen capture with macOS color handling. Coordinates are expected to be already scaled."""
        width  = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None
        
        hdr = self.vars.get("hdr", "off")

        # Use a local dict rather than self._monitor to avoid concurrent mutation
        m = {"left": left, "top": top, "width": width, "height": height}

        if not hasattr(self._thread_local, "sct"):
            self._thread_local.sct = mss.mss()
        img = self._thread_local.sct.grab(m)
        
        # MSS Returns BGRA. We convert the memory view to a standard numpy array safely.
        frame = np.array(img, dtype=np.uint8) 
        
        # Slice to BGR (dropping Alpha channel).
        bgr_frame = frame[:, :, :3]
        
        # Mathematical shift correction safely applied for macOS stability
        if hdr == "on":
            return self._correct_macos_color(bgr_frame)
        else:
            return bgr_frame

    def _detect_day_or_night(self, confidence_threshold=0.7):
        """
        Robust day/night detection using white-mask template matching.
        """

        totem_left, totem_top, totem_right, totem_bottom, _, _ = self._get_areas("totem")

        frame2 = self._grab_screen_region(totem_left, totem_top, totem_right, totem_bottom)
        if frame2 is None or frame2.size == 0:
            return None, 0.0
        image_size = int(50 / self.SCREEN_SCALE)
        frame = cv2.resize(frame2, (image_size, image_size))

        def white_mask(img):
            lower = np.array([200, 200, 200], dtype=np.uint8)
            upper = np.array([255, 255, 255], dtype=np.uint8)

            mask = cv2.inRange(img, lower, upper)

            # If completely empty, return early
            if mask is None or mask.size == 0:
                return None

            k = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, k)

            return mask

        def best_match(frame_mask, ref_mask):
            if frame_mask is None or ref_mask is None:
                return 0.0

            if frame_mask.size == 0 or ref_mask.size == 0:
                return 0.0

            fh, fw = frame_mask.shape
            rh, rw = ref_mask.shape

            # Ensure valid dimensions
            if fh == 0 or fw == 0 or rh == 0 or rw == 0:
                return 0.0

            # Resize reference if needed
            if rh > fh or rw > fw:
                scale = min(fh / rh, fw / rw)
                new_w = max(1, int(rw * scale))
                new_h = max(1, int(rh * scale))

                if new_w <= 0 or new_h <= 0:
                    return 0.0

                ref_mask = cv2.resize(ref_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                rh, rw = ref_mask.shape

            # Final safety check (CRITICAL)
            if rh > fh or rw > fw:
                return 0.0

            try:
                result = cv2.matchTemplate(frame_mask, ref_mask, cv2.TM_CCOEFF_NORMED)

                # THIS prevents your exact crash
                if result is None or result.size == 0:
                    return 0.0

                _, max_val, _, _ = cv2.minMaxLoc(result)
                return float(max_val)

            except Exception:
                return 0.0

        frame_mask = white_mask(frame)
        if frame_mask is None:
            return None, 0.0

        sun_path  = os.path.join(IMAGES_PATH, "sun.png")
        moon_path = os.path.join(IMAGES_PATH, "moon.png")

        sun_img  = cv2.imread(sun_path)
        moon_img = cv2.imread(moon_path)

        if sun_img is None or moon_img is None:
            print("Totem detection: sun.png or moon.png missing.")
            return None, 0.0

        sun_mask  = white_mask(sun_img)
        moon_mask = white_mask(moon_img)

        sun_conf  = best_match(frame_mask, sun_mask)
        moon_conf = best_match(frame_mask, moon_mask)

        best_conf = max(sun_conf, moon_conf)

        if best_conf < confidence_threshold:
            return None, best_conf

        result = "Day" if sun_conf >= moon_conf else "Night"
        return result, best_conf
    def _find_first_pixel(self, frame, hex, tolerance=8):
        if frame is None or frame.size == 0:
            return None
        tolerance = int(np.clip(tolerance, 0, 255))
        b, g, r = self._hex_to_bgr(hex)
        target = np.array([b, g, r], dtype=np.int32)
        frame_i = frame.astype(np.int32)

        diff = frame_i - target
        mask = np.sqrt(np.sum(diff ** 2, axis=-1)) <= tolerance

        coords = np.argwhere(mask)
        if coords.size > 0:
            y, x = coords[0]
            return int(x), int(y)

        return None
    def _pixel_search(self, frame, target_color_hex, tolerance=8):
        """
        Search for a specific color in a frame and return all matching pixel coordinates.
        
        Args:
            frame: BGR numpy array from cv2/mss
            target_color_hex: Hex color code (e.g., "#FFFFFF")
            tolerance: Color tolerance range (0-255)
        
        Returns:
            List of (x, y) tuples of matching pixels, or empty list if none found
        """
        if frame is None or frame.size == 0:
            return []
        
        # Convert Hex To Bgr
        bgr_color = self._hex_to_bgr(target_color_hex)
        if bgr_color is None:
            return []
        
        # Create Mask For Matching Colors (Euclidean Distance)
        target = np.array(bgr_color, dtype=np.int32)
        frame_int = frame.astype(np.int32)
        diff = frame_int - target
        dist = np.sqrt(np.sum(diff ** 2, axis=-1))
        mask = (dist <= tolerance).astype(np.uint8) * 255
        y_coords, x_coords = np.where(mask > 0)
        
        # Return As List Of (X, Y) Tuples
        if len(x_coords) > 0:
            return list(zip(x_coords, y_coords))
        return []
    def _find_circles(self, frame):
        """
        Detect circles in frame using strict Hough Circle Transform for perfect circles only.
        Specifically optimized for SHAKE button detection with strict filtering.
        Returns (center_x, center_y) of the best circle found, or None if no circles.

        Args:
            frame: BGR image from dxcam/mss
        """
        try:
            # Convert BGR to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Scale circle detection parameters based on resolution
            # Reference values are for 2560x1440 resolution
            # Use average of scale_x_1440 and scale_y_1440 for uniform circle scaling
            scale_factor = (self.scale_x_1440 + self.scale_y_1440) / 2

            # Scale parameters proportionally to resolution
            scaled_min_dist = int(150 * scale_factor)
            scaled_min_radius = int(50 * scale_factor)
            scaled_max_radius = int(300 * scale_factor)
            scaled_good_min_radius = int(50 * scale_factor)
            scaled_good_max_radius = int(120 * scale_factor)

            # Hough Circle Transform with strict parameters for perfect circles only
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1,           # Inverse ratio of accumulator resolution
                minDist=scaled_min_dist,    # Increased distance between circles to avoid overlapping detections
                param1=100,     # Higher Canny threshold for edge detection
                param2=100,     # Much higher accumulator threshold - only perfect circles
                minRadius=scaled_min_radius,   # Larger minimum radius to ignore small false positives
                maxRadius=scaled_max_radius   # Maximum circle radius
            )

            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")

                # Additional filtering: Only accept circles with good radius range for SHAKE buttons
                good_circles = []
                for (x, y, r) in circles:
                    # SHAKE buttons are typically 50-120 pixels radius (scaled)
                    if scaled_good_min_radius <= r <= scaled_good_max_radius:
                        good_circles.append((x, y, r))

                if good_circles:
                    # Return the largest good circle (most likely to be SHAKE button)
                    largest_circle = max(good_circles, key=lambda c: c[2])
                    x, y, r = largest_circle
                    print(f"    🔍 Circle detected at local ({x}, {y}) with radius {r} (scale: {scale_factor:.3f})")
                    return (int(x), int(y))

            # Only use strict HoughCircles detection - no backup methods to avoid false positives
            return None

        except Exception as e:
            print(f"    Error in circle detection: {e}")
            return None
    def _find_color_center(self, frame, target_color_hex, tolerance=8):
        """
        Find the center point of a color cluster in a frame
        Using vectorized detection
        Returns: Tuple of X, Y
        """

        if frame is None:
            return None

        # Convert Color
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int32)

        # Convert Frame For Safe Subtraction
        frame_int = frame.astype(np.int32)

        tol = int(np.clip(tolerance, 0, 255))

        # Euclidean Distance Comparison
        diff = frame_int - target_bgr
        mask = np.sqrt(np.sum(diff ** 2, axis=2)) <= tol

        y_coords, x_coords = np.where(mask)

        if len(x_coords) == 0:
            return None

        # Center Calculation (Vectorized Mean)
        center_x = int(np.mean(x_coords))
        center_y = int(np.mean(y_coords))

        return (center_x, center_y)
    def _find_color_cluster(self, frame, target_color_hex, tolerance=8, min_area=10):
        """
        Find the largest color cluster and return its center.

        Args:
            frame: BGR image
            target_color_hex: hex color string
            tolerance: color tolerance
            min_area: minimum cluster size to be valid

        Returns:
            (center_x, center_y) or None
        """
        # Required_Fish_Pixels
        if frame is None:
            return None

        # Color Mask (Vectorized Like Your Fast Version) 
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int32)
        frame_int = frame.astype(np.int32)
        tol = int(np.clip(tolerance, 0, 255))

        mask = (np.sqrt(np.sum((frame_int - target_bgr) ** 2, axis=2)) <= tol).astype(np.uint8)

        if not np.any(mask):
            return None

        # Connected Components (Cluster Detection) 
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        if num_labels <= 1:
            return None  # Only Background

        # Skip Label 0 (Background)
        largest_label = None
        largest_area = 0

        for label in range(1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]

            if area > largest_area and area >= min_area:
                largest_area = area
                largest_label = label

        if largest_label is None:
            return None

        # Centroid 
        center_x, center_y = centroids[largest_label]

        return int(center_x), int(center_y)
    def _find_bar_edges(
        self,
        frame,
        left_hex,
        right_hex,
        tolerance=15,
        tolerance2=15,
        scan_height_ratio=0.55
    ):
        if frame is None:
            return None, None

        if frame.size == 0 or frame.ndim < 2:
            return None, None

        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return None, None

        center_y = int(np.clip(h * scan_height_ratio, 0, h - 1))

        # Convert To Bgr
        left_bgr = np.array(self._hex_to_bgr(left_hex), dtype=np.int32)
        right_bgr = np.array(self._hex_to_bgr(right_hex), dtype=np.int32)

        # Clamp Tolerances
        tol_l = int(np.clip(tolerance, 0, 255))
        tol_r = int(np.clip(tolerance2, 0, 255))

        left_edge = None
        right_edge = None

        # Scan multiple Y values, starting from the preferred row and moving outward.
        for offset in range(h):
            if offset == 0:
                y_values = (center_y,)
            else:
                y_values = (center_y - offset, center_y + offset)

            for y in y_values:
                if y < 0 or y >= h:
                    continue

                line = frame[y].astype(np.int32)

                # Left Mask (Euclidean Distance)
                left_diff = line - left_bgr
                left_mask = np.sqrt(np.sum(left_diff ** 2, axis=1)) <= tol_l

                # Right Mask (Euclidean Distance)
                right_diff = line - right_bgr
                right_mask = np.sqrt(np.sum(right_diff ** 2, axis=1)) <= tol_r

                left_indices = np.where(left_mask)[0]
                right_indices = np.where(right_mask)[0]

                current_left = int(left_indices[0]) if left_indices.size else None
                current_right = int(right_indices[-1]) if right_indices.size else None

                if current_left is not None and left_edge is None:
                    left_edge = current_left
                if current_right is not None and right_edge is None:
                    right_edge = current_right

                # Fast path: return immediately once a row contains both edges.
                if current_left is not None and current_right is not None:
                    return current_left, current_right

        return left_edge, right_edge
    def _find_arrow_indicator_x(self, frame, arrow_hex, tolerance, is_holding):
        """
        If releasing -> Left arrow -> Use min
        If holding -> Right arrow -> Use max
        """
        if sys.platform == "darwin":
            tolerance += 8
        pixels = self._pixel_search(frame, arrow_hex, tolerance)
        if not pixels:
            return None

        xs = [x for x, _ in pixels]

        indicator_x = max(xs) if is_holding else min(xs)

        # Small Jitter Filter
        if self.last_indicator_x is not None:
            if abs(indicator_x - self.last_indicator_x) < 2:
                indicator_x = self.last_indicator_x

        return indicator_x
    def _update_arrow_box_estimation(self, arrow_centroid_x, is_holding, capture_width):
        """
        Estimate box position based on arrow indicator using IRUS-style logic.
        
        If holding: arrow is on RIGHT edge, extend LEFT
        If not holding: arrow is on LEFT edge, extend RIGHT
        When state swaps: measure distance between arrows to get box size
        
        Args:
            arrow_centroid_x: X coordinate of arrow center
            is_holding: Whether mouse button is currently held
            capture_width: Width of capture region
        
        Returns:
            Estimated bar center X coordinate, or None if can't estimate
        """

        # Define Values First
        left_x = self.last_left_x
        right_x = self.last_right_x

        # Handle Missing Arrow
        if arrow_centroid_x is None:
            if self.last_known_box_center_x is not None:
                return self.last_known_box_center_x, left_x, right_x
            return None, None, None  # Hard Fail Instead Of Bad Estimation

        # Set Default Box Size If We Don'T Have One
        if not self.estimated_box_length or self.estimated_box_length <= 0:
            if self.last_cached_box_length and self.last_cached_box_length > 0:
                self.estimated_box_length = self.last_cached_box_length
            else:
                return None, None, None  # Hard Fail Instead Of Bad Estimation
        # Detect Arrow Direction Swap
        state_swapped = False

        if (
            self.last_indicator_x is not None and
            arrow_centroid_x is not None
        ):
            # Current movement direction
            delta = arrow_centroid_x - self.last_indicator_x

            # Check if movement direction flipped
            if (
                hasattr(self, "last_arrow_delta") and
                self.last_arrow_delta is not None
            ):
                state_swapped = (
                    (self.last_arrow_delta > 0 and delta < 0) or
                    (self.last_arrow_delta < 0 and delta > 0)
                )

            # Save for next frame
            self.last_arrow_delta = delta

        # Use actual hold state normally
        effective_holding_state = is_holding

        # If arrow suddenly reversed direction,
        # edge ownership likely swapped
        if state_swapped:
            effective_holding_state = not effective_holding_state
        # Position The Box Based On Current Hold State
        if effective_holding_state:
            # Holding: Arrow Is On Right, Extend Left
            self.last_right_x = float(arrow_centroid_x)
            self.last_left_x = self.last_right_x - self.estimated_box_length
        else:
            # Not Holding: Arrow Is On Left, Extend Right
            self.last_left_x = float(arrow_centroid_x)
            self.last_right_x = self.last_left_x + self.estimated_box_length
        
        # Clamp To Capture Bounds (Keep Arrow Anchored)
        if self.last_left_x < 0:
            self.last_left_x = 0.0
            self.last_right_x = min(self.estimated_box_length, capture_width)
        
        if self.last_right_x > capture_width:
            self.last_right_x = float(capture_width)
            self.last_left_x = max(0.0, self.last_right_x - self.estimated_box_length)
        
        # Calculate And Store Center
        box_center = (self.last_left_x + self.last_right_x) / 2.0
        self.last_known_box_center_x = box_center
        
        # Update Tracking Variables For Next Frame
        self.last_indicator_x = arrow_centroid_x
        self.last_holding_state = effective_holding_state

        return box_center, self.last_left_x, self.last_right_x
    # Main macro functions
    def normalize_key(self, key):
        try:
            return key.char.lower()  # Letter Keys
        except AttributeError:
            return str(key).replace("Key.", "").lower()
    def on_key_press(self, key):
        # Track which keys are currently held so on_key_release can confirm a
        # full press+release cycle (a "hit") before acting. This prevents OS
        # key-repeat events from firing the action multiple times.
        self._keys_held.add(self.normalize_key(key))

    def on_key_release(self, key):
        key = self.normalize_key(key)
        # Only act if this release follows a genuine press (i.e. a real "hit")
        if key not in self._keys_held:
            return
        self._keys_held.discard(key)
        if key == "f5":
            if self.macro_running == False:
                threading.Thread(target=self.start_fishing, daemon=True).start()
            else:
                return
        elif key == "f6":
            self.open_area_selector()
        elif key == "f7":
            self.stop_macro()
    def _string_to_key(self, key_string):
        key_string = key_string.strip().lower()
        # Try Special Keys
        if hasattr(Key, key_string):
            return getattr(Key, key_string)
        # Fallback To Character
        return key_string
    def _get_var_number(self, key, default, cast=float):
        """Read a numeric GUI setting with a safe fallback."""
        try:
            value = self.vars.get(key)
            if value is None:
                # Compatibility mapping for 1600plus key differences
                if key == "perfect_cast_timing_1600_plus":
                    value = self.vars.get("perfect_cast_timing_1600plus")
                if value is None:
                    return default
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    return default
            return cast(value)
        except Exception:
            return default
    def _hex_to_bgr(self, hex_color):
        "Convert hex color to BGR tuple for OpenCV."
        if hex_color is None or hex_color.lower() in ["none", "# None", ""]:
            return None
        
        hex_color = hex_color.lstrip('# ')
        if len(hex_color) == 6:
            try:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (b, g, r)  # Bgr Format For Opencv
            except ValueError:
                return None
        return None
    # Do Pixel/Image/Line Search
    def _do_pixel_search(self, frame):
        fish_hex = self.vars["fish_color"]
        left_bar_hex = self.vars["left_color"]
        right_bar_hex = self.vars["right_color"]
        try: # Handle Nonetype and int properly
            left_tol = int(self.vars["left_tolerance"] or 8)
            right_tol = int(self.vars["right_tolerance"] or 8)
            fish_tol = int(self.vars["fish_tolerance"] or 1)
        except:
            left_tol = 8
            right_tol = 8
            fish_tol = 1
        # macOS Tolerance Buffer To Make Configs Cross-Compatible
        if sys.platform == "darwin":
            left_tol += 2
            right_tol += 2
            fish_tol += 2
        fish_center = self._find_color_cluster(frame, fish_hex, fish_tol, 5)
        try:
            fish_center = fish_center[0]
        except:
            pass
        left_bar_center, right_bar_center = self._find_bar_edges(frame, left_bar_hex, right_bar_hex, left_tol, right_tol)
        if left_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(frame, right_bar_hex, right_bar_hex, right_tol, right_tol)
        elif right_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(frame, left_bar_hex, left_bar_hex, left_tol, left_tol)
        return fish_center, left_bar_center, right_bar_center
    def _do_line_search(self, frame, original_width=None):
        """
        Detect vertical lines in frame and identify fish and bar positions.
        Based on Hydra.py line detection pipeline with brightness and density filtering.
        Uses line identification logic similar to _execute_fish_stage_line.
        
        Frame is normalized to reference fish box dimensions (517x22 at 720p)
        for consistent detection across all resolutions. Line coordinates are scaled
        back to match the original frame dimensions.
        
        Returns tuple of (fish_x, left_bar_x, right_bar_x):
            - fish_x: Center X coordinate of the two target lines (fish)
            - left_bar_x: X coordinate of the left bar line
            - right_bar_x: X coordinate of the right bar line
            Returns (None, None, None) if unable to identify lines

        Args:
            frame: BGR image from MSS
            original_width: Original frame width before normalization (for coordinate scaling back)
        """
        try:
            # Get minimum line density from settings (configurable via GUI)
            MIN_LINE_DENSITY = self._get_rod_specific_setting("fish_line_min_density", 0.8)
            BRIGHTNESS_THRESHOLD = 10  # Minimum brightness for edge pixels
            
            # Reference fish box dimensions at 1280x720
            REFERENCE_FISH_WIDTH = 517   # Fish box width at 720p
            REFERENCE_FISH_HEIGHT = 22   # Fish box height at 720p
            
            # Store original dimensions for coordinate scaling
            original_height, original_frame_width = frame.shape[:2]
            if original_width is None:
                original_width = original_frame_width
            
            # Normalize frame to reference dimensions for consistent detection
            if original_frame_width != REFERENCE_FISH_WIDTH or original_height != REFERENCE_FISH_HEIGHT:
                frame = cv2.resize(frame, (REFERENCE_FISH_WIDTH, REFERENCE_FISH_HEIGHT), interpolation=cv2.INTER_LINEAR)
                width_scale = original_width / REFERENCE_FISH_WIDTH
            else:
                width_scale = 1.0

            # Step 1: Convert to grayscale
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Step 2: Laplacian edge detection
            laplacian = cv2.Laplacian(grayscale, cv2.CV_8U)

            # Step 3: Filter vertical lines by brightness threshold and density
            height, width = laplacian.shape
            
            # Vectorized column density calculation
            column_densities = np.sum(laplacian > BRIGHTNESS_THRESHOLD, axis=0) / height
            line_coordinates = np.where(column_densities >= MIN_LINE_DENSITY)[0].tolist()

            # Merge adjacent lines into single lines
            if line_coordinates:
                merged_lines = []
                group_start = line_coordinates[0]
                group_end = line_coordinates[0]
                
                for i in range(1, len(line_coordinates)):
                    if line_coordinates[i] <= group_end + 2:
                        group_end = line_coordinates[i]
                    else:
                        middle = (group_start + group_end) // 2
                        merged_lines.append(middle)
                        group_start = line_coordinates[i]
                        group_end = line_coordinates[i]
                
                middle = (group_start + group_end) // 2
                merged_lines.append(middle)
                
                line_coordinates = merged_lines

            # Scale line coordinates back to original frame dimensions
            if width_scale != 1.0:
                line_coordinates = [int(x * width_scale) for x in line_coordinates]

            # Initialize state variables if not already done
            if not hasattr(self, '_line_state'):
                self._line_state = {
                    'initial_target_gap': None,
                    'last_target_left_x': None,
                    'last_target_right_x': None,
                    'last_left_bar_x': None,
                    'last_right_bar_x': None,
                    'is_initial_run': True
                }

            state = self._line_state
            image_center_x = original_width // 2

            # Need at least 2 lines to identify fish and bars
            if len(line_coordinates) < 2:
                return None, None, None

            # INITIAL RUN: Find 2 closest lines to center as target (fish) lines
            if state['is_initial_run'] or state['initial_target_gap'] is None:
                distance_coords = sorted(
                    [(abs(coord - image_center_x), coord) for coord in line_coordinates],
                    key=lambda x: x[0]
                )
                target_pair = sorted([distance_coords[0][1], distance_coords[1][1]])
                target_left_x = target_pair[0]
                target_right_x = target_pair[1]
                initial_target_gap = target_right_x - target_left_x

                # Find bars - closest to left of left target, closest to right of right target
                left_candidates = [x for x in line_coordinates if x < target_left_x]
                right_candidates = [x for x in line_coordinates if x > target_right_x]
                
                left_bar_x = max(left_candidates) if left_candidates else target_left_x
                right_bar_x = min(right_candidates) if right_candidates else target_right_x

                # Update state
                state['last_target_left_x'] = target_left_x
                state['last_target_right_x'] = target_right_x
                state['last_left_bar_x'] = left_bar_x
                state['last_right_bar_x'] = right_bar_x
                state['initial_target_gap'] = initial_target_gap
                state['is_initial_run'] = False

            else:
                # SUBSEQUENT RUNS: Find pair with gap matching initial_target_gap
                best_gap_diff = float('inf')
                target_left_x = state['last_target_left_x']
                target_right_x = state['last_target_right_x']

                for i in range(len(line_coordinates) - 1):
                    curr_left = line_coordinates[i]
                    curr_right = line_coordinates[i + 1]
                    curr_gap = curr_right - curr_left
                    gap_diff = abs(curr_gap - state['initial_target_gap'])

                    if gap_diff < best_gap_diff:
                        best_gap_diff = gap_diff
                        target_left_x = curr_left
                        target_right_x = curr_right
                
                # If best gap is more than 4x initial gap, keep old positions
                actual_gap = target_right_x - target_left_x
                if actual_gap > state['initial_target_gap'] * 4:
                    target_left_x = state['last_target_left_x']
                    target_right_x = state['last_target_right_x']
                
                # Find bars from non-target lines
                other_lines = [x for x in line_coordinates if x != target_left_x and x != target_right_x]
                
                if len(other_lines) >= 2:
                    # Pick closest to last positions
                    left_bar_x = min(other_lines, key=lambda x: abs(x - state['last_left_bar_x'])) if state['last_left_bar_x'] is not None else other_lines[0]
                    remaining_lines = [x for x in other_lines if x != left_bar_x]
                    right_bar_x = min(remaining_lines, key=lambda x: abs(x - state['last_right_bar_x'])) if remaining_lines and state['last_right_bar_x'] is not None else (remaining_lines[0] if remaining_lines else state['last_right_bar_x'])
                
                elif len(other_lines) == 1:
                    # Only one non-target line - assign to closest bar
                    single_line = other_lines[0]
                    if state['last_left_bar_x'] is not None and state['last_right_bar_x'] is not None:
                        dist_to_left = abs(single_line - state['last_left_bar_x'])
                        dist_to_right = abs(single_line - state['last_right_bar_x'])
                        if dist_to_left < dist_to_right:
                            left_bar_x = single_line
                            right_bar_x = state['last_right_bar_x']
                        else:
                            right_bar_x = single_line
                            left_bar_x = state['last_left_bar_x']
                    else:
                        left_bar_x = single_line
                        right_bar_x = target_right_x
                else:
                    # No other lines - use last known positions
                    left_bar_x = state['last_left_bar_x'] if state['last_left_bar_x'] is not None else target_left_x
                    right_bar_x = state['last_right_bar_x'] if state['last_right_bar_x'] is not None else target_right_x
                
                # Update state with new values
                state['last_target_left_x'] = target_left_x
                state['last_target_right_x'] = target_right_x
                state['last_left_bar_x'] = left_bar_x
                state['last_right_bar_x'] = right_bar_x

            # Calculate centers
            fish_x = (target_left_x + target_right_x) / 2.0
            left_x = left_bar_x
            right_x = right_bar_x

            return fish_x, left_x, right_x

        except Exception as e:
            print(f"    Error in line detection: {e}")
            return None, None, None
    # PID control
    def _reset_pid_state(self):
        """Reset all PID controller state variables before a new minigame."""
        self._pid_last_error = None
        self._pid_last_target_x = None
        self._pid_last_scan_time = None

    def _pid_control(self, error, bar_center):
        """
        Asymmetric PD controller.

        Args:
            error:      fish_x - bar_center  (positive = target is right of bar)
            bar_center: current bar centre in screen coordinates

        Returns:
            Clamped control signal (float).  Positive → hold, negative → release.
        """
        # Gains and clamp from GUI settings
        kp       = self._get_var_number("kp", 0.93)
        kd       = self._get_var_number("kd", 0.07)
        pd_clamp = self._get_var_number("pid_clamp", 100.0)

        # Reconstruct fish_x (target position) from error and bar_center
        bar_center_x   = bar_center
        target_line_last_x = bar_center_x + error  # fish_x = bar_center + error

        current_time = time.perf_counter()

        # P term – proportional to distance
        p_term = kp * error

        # D term – asymmetric damping
        d_term = 0.0
        if (
            self._pid_last_scan_time is not None
            and self._pid_last_target_x is not None
            and self._pid_last_error is not None
        ):
            time_delta = current_time - self._pid_last_scan_time
            if time_delta > 0.001:
                # Bar velocity: how fast the bar centre moved since last frame
                last_bar_x   = self._pid_last_target_x - self._pid_last_error
                bar_velocity = (bar_center_x - last_bar_x) / time_delta

                error_magnitude_decreasing = abs(error) < abs(self._pid_last_error)
                bar_moving_toward_target = (
                    (bar_velocity > 0 and error > 0)
                    or (bar_velocity < 0 and error < 0)
                )

                if error_magnitude_decreasing and bar_moving_toward_target:
                    # APPROACHING – strong damping to prevent overshoot
                    d_term = -kd * 5.0 * bar_velocity
                else:
                    # CHASING – light damping to allow fast movement
                    d_term = -kd * 0.2 * bar_velocity

        # Update state for next frame
        self._pid_last_error      = error
        self._pid_last_target_x   = target_line_last_x
        self._pid_last_scan_time  = current_time

        # Combined and clamped control signal
        control_signal = p_term + d_term
        control_signal = max(-pd_clamp, min(pd_clamp, control_signal))
        return control_signal
    # Start macro
    def start_macro(self):
        self.macro_running = True
        # rod_slot = str(self.vars["rod_slot"])
        # bag_slot = str(self.vars["bag_slot"])
        shake_left, shake_top, shake_right, shake_bottom, shake_width, shake_height = self._get_areas("shake")
        shake_x = shake_left + int(shake_width / 2)
        shake_y = shake_top + int(shake_height / 2)
        rod_slot = str(1)
        bag_slot = str(2)
        auto_zoom = self.vars.get("auto_zoom", "off")
        auto_refresh = self.vars.get("auto_refresh", "off")
        casting_mode = self.vars.get("casting_mode", "Normal")
        shake_mode = self.vars.get("shake_mode", "Navigation")
        if auto_zoom == "on":
            for _ in range(20):
                mouse_controller.scroll(0, 1)
                time.sleep(0.05)
            mouse_controller.scroll(0, -1)
            time.sleep(0.1)
        while self.macro_running:
            # Misc / Utilities
            # Select Rod
            if auto_refresh == "on":
                bag_delay = self._get_var_number("select_rod_duration", self._get_var_number("bag_delay", 0.36, float), float)
                self.set_status("Selecting rod")
                # Sequence
                time.sleep(bag_delay * 1.5)
                keyboard_controller.press(bag_slot)
                time.sleep(0.05)
                keyboard_controller.release(bag_slot)
                time.sleep(bag_delay)
                keyboard_controller.press(rod_slot)
                time.sleep(0.05)
                keyboard_controller.release(rod_slot)
                time.sleep(0.2)
            # Logging
            self._check_logging_trigger()
            # Totem
            self._check_totem_trigger(shake_x, shake_y)
            if self.vars["auto_reconnect"] == "on":
                self._auto_reconnect(shake_x, shake_y)
            # Cast
            if casting_mode == "Perfect":
                self._execute_cast_perfect()
            else:
                self.execute_cast_normal()
            # Shake
            if shake_mode == "Navigation":
                self._execute_shake_navigation()
            else:
                self._execute_shake_click(shake_mode)
            # Minigame
            self._enter_minigame()
    # Utilities
    def _check_logging_trigger(self):
        """Check whether the Logging should fire based on the selected mode.

        Modes (logging_trigger):
          Cycles  – fire every N completed cycles (configurable via logging_cycle)
          Time    – fire every N seconds elapsed  (configurable via logging_time)
          Disabled – never fire
        """
        cd_mode = self.vars["logging_trigger"]

        if cd_mode == "Disabled":
            return  # webhook type is disabled; do nothing

        try:
            trigger_every = int(self.vars["logging_cycle"])
        except (ValueError, KeyError):
            trigger_every = 3  # safe fallback
        
        try:
            trigger_secs = float(self.vars["logging_time"])
        except (ValueError, KeyError):
            trigger_secs = 60.0  # safe fallback

        if cd_mode == "Cycles":
            self.webhook_cycle_counter += 1

            if trigger_every > 0 and self.webhook_cycle_counter % trigger_every == 0:
                label = f"Cycle #{self.webhook_cycle_counter}"
                self.send_logging("**Cycle Checkpoint**", label, show_status=False)

        elif cd_mode == "Time":
            self.webhook_cycle_counter += 1  # still count cycles for the message label
            elapsed = time.time() - self.webhook_start_time

            if trigger_secs > 0 and elapsed >= trigger_secs:
                label = f"Cycle #{self.webhook_cycle_counter} | {int(elapsed)}s elapsed"
                self.send_logging("**Time Checkpoint**", label, show_status=False)
                # Reset the timer so it fires again after another trigger_secs seconds
                self.webhook_start_time = time.time()
    def _check_totem_trigger(self, shake_x, shake_y):
        """Check whether auto totem should trigger based on mode.
        
        Uses shared trigger settings with Logging:
          Cycles  – trigger every N completed cycles
          Time    – trigger every N seconds elapsed
          Disabled – never trigger
        """
        mode = self.vars["auto_totem_mode"]
        # self.SCREEN_SCALE

        if mode == "Disabled":
            return
        
        if not self.macro_running == True:
            return
        
        try:
            trigger_every = int(self.vars["totem_cycles"])
        except (ValueError, KeyError):
            trigger_every = 3  # Safe Fallback
        
        try:
            trigger_secs = float(self.vars["totem_delay"])
        except (ValueError, KeyError):
            trigger_secs = 60.0  # Safe Fallback

        # Cycles Mode
        if mode == "Cycles":
            self.totem_cycle_counter += 1

            if not (trigger_every > 0 and self.totem_cycle_counter % trigger_every == 0):
                return

        # Time Mode
        elif mode == "Time":
            elapsed = time.time() - self.totem_start_time

            if not (trigger_secs > 0 and elapsed >= trigger_secs):
                return

            # Reset Timer Before Execution So It Starts Fresh Regardless Of Success/Failure
            self.totem_start_time = time.time()
            self.totem_cycle_counter += 1

        else:
            return
        # Execute Totem
        self.set_status("Using Totem")

        sundial_slot = str(self.vars["sundial_slot"])
        target_slot  = str(self.vars["target_slot"])
        sundial_delay  = int(self.vars["sundial_delay"])
        desired_time = self.vars["use_sundial_mode_when"]  # "Day", "Night", Or Maybe "Disabled"

        totem_success = False

        confidence_threshold = 0.6

        # Detect Day / Night
        current_time, best_conf = self._detect_day_or_night(confidence_threshold)
        if current_time is None:
            return  # Below confidence threshold — skip this cycle


        # Decide Whether To Use Sundial
        use_sundial = (
            desired_time in ["Day", "Night"] and
            current_time != desired_time
        )


        # Use Sundial (If Needed)
        if use_sundial:
            time.sleep(0.2)

            keyboard_controller.press(sundial_slot)
            time.sleep(0.05)
            keyboard_controller.release(sundial_slot)

            time.sleep(0.2)

            mouse_controller.position = (shake_x, shake_y)
            time.sleep(0.05)
            self._click_at(shake_x, shake_y)

            # Wait For Time Transition
            time.sleep(sundial_delay)


        # Use Target Totem
        time.sleep(0.2)

        keyboard_controller.press(target_slot)
        time.sleep(0.05)
        keyboard_controller.release(target_slot)

        time.sleep(0.4)

        mouse_controller.position = (shake_x, shake_y)
        time.sleep(0.05)
        self._click_at(shake_x, shake_y)

        time.sleep(1)

        totem_success = True

        # Webhook
        if totem_success:
            self.send_logging(
                "Totem used successfully",
                self.totem_cycle_counter,
                show_status=False
            )
    def _auto_reconnect(self, center_x, center_y):
        reconnect_threshold = int(self.vars["reconnect_threshold"])
        reconnect_wait_time = int(self.vars["reconnect_wait_time"])
        mirror_ratio = float(self.vars["mirror_ratio"])
        mirror_ratio2 = float(self.vars["mirror_ratio2"])
        mirror_slot = str(self.vars["mirror_slot"])
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s, shake_width, shake_height = self._get_areas("shake")
        mirror_click_x = int(shake_width * mirror_ratio) + shake_left_s
        # 0.59
        mirror_click_y = int(shake_height * mirror_ratio2) + shake_top_s
        # 1520
        reconnect_threshold = int((reconnect_threshold / 1500) * shake_width)
        img = self._grab_screen_region(shake_left_s, shake_top_s, shake_right_s, shake_bottom_s)
        disconnect_area = self._find_color_cluster(img, "#393b3d", 5, reconnect_threshold)
        while self.macro_running:
            if not disconnect_area == None:
                reconnect = self._find_color_cluster(img, "#FFFFFF", 8, int(reconnect_threshold / 2))
                time.sleep(1)
                reconnect_x = reconnect[0] + shake_left_s if not reconnect == None else shake_left_s
                reconnect_y = reconnect[1] + shake_top_s if not reconnect == None else shake_top_s
                self._click_at(reconnect_x, reconnect_y)
                time.sleep(reconnect_wait_time)
                self._click_at(center_x, center_y)
                time.sleep(2.5)
                keyboard_controller.press(mirror_slot)
                time.sleep(0.05)
                keyboard_controller.release(mirror_slot)
                self._click_at(center_x, center_y)
                time.sleep(0.2)
                self._click_at(mirror_click_x, mirror_click_y)
            return
    # Casting
    def _execute_cast_perfect(self):
        """
        Scans for green and white Y coordinates and releases left click when
        the top white Y reaches 95% of the area from green Y to bottom white Y.
        """
        # Hold Mouse
        mouse_controller.press(Button.left)
        # Get Areas (Scale Factor Applied Inside _Get_Areas)
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s, _, shake_height = self._get_areas("shake")

        # Config 
        white_color = self.vars.get("white_cast_color", self.vars.get("perfect_color2", "#d4d3ca"))
        green_color = self.vars.get("green_cast_color", self.vars.get("perfect_color", "#64a04c"))
        white_tol = int(self._get_var_number("perfect_cast2_tolerance", 5, int))
        green_tol = int(self._get_var_number("perfect_cast_tolerance", 16, int))

        max_time = float(self._get_var_number("perfect_max_time", 5.5, float))
        scan_delay = float(self._get_var_number("cast_scan_delay", 0.05, float))
        delay_before_casting = float(self._get_var_number("delay_before_casting", 0.5, float))
        cast_delay = float(self._get_var_number("cast_delay", 0.6, float))

        target_green = np.array(self._hex_to_bgr(green_color), dtype=np.int32)
        target_white = np.array(self._hex_to_bgr(white_color), dtype=np.int32)

        # Resolution scaling: velocity bands are tuned at 1440p height
        scaling_factor = self.SCREEN_HEIGHT / 1440.0

        tracking_mode = False
        green_left_x = None
        green_right_x = None
        green_y = None
        green_padding = 50

        # Velocity tracking — up to 5 samples for linear regression
        white_positions = []    # (x, y) in region-relative coords
        white_timestamps = []   # parallel perf_counter values
        MAX_VELOCITY_SAMPLES = 5
        last_time_to_impact = None

        if sys.platform == "darwin":
            white_tol += 15
            green_tol += 15

        def color_mask(img, target_bgr, tolerance):
            img_i = img.astype(np.int32)
            diff = img_i - target_bgr
            return np.sqrt(np.sum(diff ** 2, axis=2)) <= tolerance

        def reset_tracking():
            nonlocal tracking_mode, green_left_x, green_right_x, green_y
            nonlocal last_time_to_impact
            tracking_mode = False
            green_left_x = None
            green_right_x = None
            green_y = None
            last_time_to_impact = None
            white_positions.clear()
            white_timestamps.clear()

        # Start Capture Thread; This Remains The Existing V3.42 Capture Path.
        stop_event = self._start_capture(scan_delay)
        start_time = time.time()

        time.sleep(delay_before_casting)
        # Perfect Cast Loop
        while self.macro_running:
            if not self._cap_event.wait(timeout=0.5):
                continue
            with self._cap_lock:
                frame = self._cap_frame
                self._cap_event.clear()
            if frame is None:
                stop_event.set()
                return
            region = frame[shake_top_s:shake_bottom_s, shake_left_s:shake_right_s]
            if region.size == 0:
                if time.time() - start_time > max_time:
                    break
                continue

            if not tracking_mode:
                mask = color_mask(region, target_green, green_tol)
                rows, cols = np.nonzero(mask)

                if rows.size > 0:
                    found_y = int(rows[0])
                    cols_in_row = cols[rows == found_y]
                    green_left_x = int(np.min(cols_in_row))
                    green_right_x = int(np.max(cols_in_row))
                    green_y = found_y
                    tracking_mode = True
                elif time.time() - start_time > max_time:
                    break
                continue


            green_top = max(0, green_y - green_padding)
            green_bottom = min(region.shape[0], green_y + green_padding)
            green_left = max(0, green_left_x - green_padding)
            green_right = min(region.shape[1], green_right_x + green_padding)

            green_frame = region[green_top:green_bottom, green_left:green_right]
            if green_frame.size == 0:
                reset_tracking()
                continue

            mask = color_mask(green_frame, target_green, green_tol)
            rows, cols = np.nonzero(mask)
            if rows.size == 0:
                reset_tracking()
                continue

            found_y_relative = int(rows[0])
            cols_in_row = cols[rows == found_y_relative]
            green_left_x = int(np.min(cols_in_row)) + green_left
            green_right_x = int(np.max(cols_in_row)) + green_left
            green_y = found_y_relative + green_top
            self.set_status(f"Green Y: {green_y}")

            if green_right_x <= green_left_x:
                reset_tracking()
                continue

            scan_bottom = int(region.shape[0] * 0.9)
            white_frame = region[green_y:scan_bottom, green_left_x:green_right_x]
            if white_frame.size == 0:
                if time.time() - start_time > max_time:
                    break
                continue

            mask_white = color_mask(white_frame, target_white, white_tol)
            rows_white, _ = np.nonzero(mask_white)
            if rows_white.size == 0:
                if time.time() - start_time > max_time:
                    break
                continue

            white_y_top = int(rows_white[0]) + green_y
            white_y_bottom = int(rows_white[-1]) + green_y
            total_distance = white_y_bottom - green_y
            current_distance = white_y_top - green_y
            if total_distance <= 0:
                continue

            # --- Velocity tracking ---
            now_pc = time.perf_counter()
            white_positions.append((0, white_y_top))   # x is irrelevant; track Y only
            white_timestamps.append(now_pc)
            if len(white_positions) > MAX_VELOCITY_SAMPLES:
                white_positions.pop(0)
                white_timestamps.pop(0)

            self.set_status(f"White Y: {white_y_top}")

            # local_distance: pixels remaining until white reaches green
            local_distance = current_distance  # white_y_top - green_y; positive = white below green

            # --- Velocity-band predictive release ---
            released = False
            if len(white_positions) >= 3:
                velocity_y = self._calculate_speed_and_predict(white_positions, white_timestamps)
                min_speed = 5 * scaling_factor
                if velocity_y is not None and abs(velocity_y) > min_speed:
                    white_above_green = white_y_top < green_y
                    moving_toward_green = (white_above_green and velocity_y > 0) or (not white_above_green and velocity_y < 0)
                    if moving_toward_green and local_distance > 0:
                        time_to_impact = local_distance / abs(velocity_y)

                        # Bounce/miss detection: if TtI suddenly grows when very close, we passed green
                        bounce_threshold = 40 * scaling_factor
                        if last_time_to_impact is not None and local_distance < bounce_threshold:
                            if time_to_impact > last_time_to_impact * 1.3:
                                mouse_controller.release(Button.left)
                                released = True

                        if not released:
                            # Velocity-band reaction delays (tuned at 1440p)
                            v = abs(velocity_y)
                            if v < 700 * scaling_factor:
                                reaction_delay = 0.060
                                timing_key = "perfect_cast_timing_700"
                            elif v < 800 * scaling_factor:
                                reaction_delay = 0.058
                                timing_key = "perfect_cast_timing_800"
                            elif v < 900 * scaling_factor:
                                reaction_delay = 0.057
                                timing_key = "perfect_cast_timing_900"
                            elif v < 1000 * scaling_factor:
                                reaction_delay = 0.056
                                timing_key = "perfect_cast_timing_1000"
                            elif v < 1100 * scaling_factor:
                                reaction_delay = 0.055
                                timing_key = "perfect_cast_timing_1100"
                            elif v < 1200 * scaling_factor:
                                reaction_delay = 0.050
                                timing_key = "perfect_cast_timing_1200"
                            elif v < 1300 * scaling_factor:
                                reaction_delay = 0.048
                                timing_key = "perfect_cast_timing_1300"
                            elif v < 1400 * scaling_factor:
                                reaction_delay = 0.047
                                timing_key = "perfect_cast_timing_1400"
                            elif v < 1500 * scaling_factor:
                                reaction_delay = 0.046
                                timing_key = "perfect_cast_timing_1500"
                            elif v < 1600 * scaling_factor:
                                reaction_delay = 0.050
                                timing_key = "perfect_cast_timing_1600"
                            else:
                                reaction_delay = 0.049
                                timing_key = "perfect_cast_timing_1600_plus"

                            timing_adjustment_ms = self._get_var_number(timing_key, 0, int)
                            reaction_delay += timing_adjustment_ms * 0.001

                            if time_to_impact <= reaction_delay:
                                mouse_controller.release(Button.left)
                                released = True

                        last_time_to_impact = time_to_impact

            # Slow-speed / emergency distance fallbacks
            if not released:
                slow_threshold = total_distance * 0.05  # within 5% of green
                emergency_threshold = total_distance * 0.025
                if local_distance <= emergency_threshold:
                    mouse_controller.release(Button.left)
                    released = True
                elif local_distance <= slow_threshold and len(white_positions) >= 3:
                    # Confirm approach: latest distance < oldest distance
                    recent_dists = [p[1] - green_y for p in white_positions[-3:]]
                    if recent_dists[-1] < recent_dists[0]:
                        mouse_controller.release(Button.left)
                        released = True

            if released:
                break

            if time.time() - start_time > max_time:
                break

        # Cleanup
        stop_event.set()
        mouse_controller.release(Button.left)
        time.sleep(cast_delay)
        return
    def execute_cast_normal(self):
        delay_before_casting = float(self._get_var_number("delay_before_casting", 0.5, float))
        cast_duration = float(self._get_var_number("cast_duration", 0.5, float))
        delay_after_casting = float(self._get_var_number("delay_after_casting", 1, float))
        time.sleep(delay_before_casting)
        mouse_controller.press(Button.left)
        time.sleep(cast_duration)
        mouse_controller.release(Button.left)
        time.sleep(delay_after_casting)
        return
    def _execute_shake_click(self, shake_mode):
        """
        IF shake_mode = pixel: Search for pixel
        IF shake_mode = circle: Search for largest circle
        THEN click on the circle
        """
        # Get areas (scale factor applied inside _get_areas)
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s, _, _ = self._get_areas("shake")
        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s, _, _     = self._get_areas("fish")
        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self._get_areas("friend")
        shake_x = (shake_left_s + shake_right_s) // 2
        shake_y = (shake_top_s  + shake_bottom_s) // 2
        # Misc variables
        shake_hex = self.vars["shake_color"]
        scan_delay = float(self.vars["shake_scan_delay"])
        try:
            tolerance = int(self.vars["shake_tolerance"])
            failsafe = int(self.vars["shake_failsafe"] or 80)
            shake_clicks = int(self.vars["shake_clicks"])
        except:
            tolerance = 5
            failsafe = 80
            shake_clicks = 1

        # Initialize attempts and stop event
        attempts = 0
        stop_event = self._start_capture(scan_delay)
        while self.macro_running and attempts < failsafe:
            # Grab full screen then crop
            if not self._cap_event.wait(timeout=0.5):
                continue
            with self._cap_lock:
                frame = self._cap_frame
                self._cap_event.clear()
            if frame is None:
                stop_event.set()
                return
            shake_area = frame[shake_top_s:shake_bottom_s, shake_left_s:shake_right_s]
            if shake_area is None or shake_area.size == 0:
                time.sleep(scan_delay)
                continue
            # 1. Look for shake pixel
            if shake_mode == "Pixel":
                shake_pixel = self._find_first_pixel(shake_area, shake_hex, tolerance)
            else:
                shake_pixel = self._find_circles(shake_area)
            if shake_pixel:
                x, y = shake_pixel
                screen_x = shake_left_s + x
                screen_y = shake_top_s + y
                self._click_at(screen_x, screen_y, shake_clicks)
            # 2. Fish detection — Friend Area (green gone = minigame started)
            detected = False
            while detected == False and self.macro_running:
                detection_area = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                if detection_area is None or detection_area.size == 0:
                    break
                friend_x = self._find_color_center(detection_area, "#9BFF9B", tolerance)
                if not friend_x:
                    detected = True
                    time.sleep(0.005)
                else:
                    break
            # 3. Fish detected → enter minigame
            if detected == True:
                self.set_status("Entering Minigame")
                mouse_controller.press(Button.left)
                time.sleep(0.003)
                mouse_controller.release(Button.left)
                return  # exit shake cleanly
            attempts += 1
            time.sleep(scan_delay)
    def _execute_shake_navigation(self):
        """Spams the enter key until fish detection is found"""
        self.set_status("Shake Mode: Navigation")
        # Get areas (scale factor applied inside _get_areas)
        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s, _, _         = self._get_areas("fish")
        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self._get_areas("friend")

        # Misc variables
        scan_delay = float(self.vars["shake_scan_delay"])
        try:
            tolerance = int(self.vars["shake_tolerance"])
            failsafe = int(self.vars["shake_failsafe"] or 80)
        except:
            tolerance = 5
            failsafe = 80
        if sys.platform == "darwin":
            tolerance += 15
        attempts = 0
        stop_event = self._start_capture(scan_delay)
        while self.macro_running and attempts < failsafe:
            # 1. Navigation shake (Enter key)
            keyboard_controller.press(Key.enter)
            time.sleep(0.03)
            keyboard_controller.release(Key.enter)
            time.sleep(scan_delay)
            # 2. Fish detection — Friend Area (green gone = minigame started)
            detected = False
            while detected == False and self.macro_running:
                # Grab full screen then crop
                if not self._cap_event.wait(timeout=0.5):
                    continue
                with self._cap_lock:
                    frame = self._cap_frame
                    self._cap_event.clear()
                if frame is None:
                    stop_event.set()
                    print("Finished (no frame)")
                    return
                detection_area = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                if detection_area is None or detection_area.size == 0:
                    break
                friend_x = self._find_color_center(detection_area, "#9BFF9B", tolerance)
                if not friend_x:
                    detected = True
                    time.sleep(0.005)
                else:
                    break
            # 3. Fish detected → enter minigame
            if detected == True:
                self.set_status("Entering Minigame")
                mouse_controller.press(Button.left)
                time.sleep(0.003)
                mouse_controller.release(Button.left)
                print("Finished (fish detected)")
                return  # exit shake cleanly
            attempts += 1
            time.sleep(scan_delay)
    def _enter_minigame(self):
        # Get All 3 Areas
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._get_areas("shake")
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_left, fish_top, fish_right, fish_bottom, fish_width, _ = self._get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._get_areas("friend")
        self._reset_pid_state()
        mouse_down = False
        controller_mode = 0
        self._pred_prev_fish_x = None
        self._pred_prev_bar_x = None
        self._pred_prev_time = None
        self._pred_filtered_vel = 0.0
        # Load Values From Gui
        arrow_hex = self.vars["arrow_color"]
        bar_ratio = float(self.vars["bar_ratio_from_side"] or 0.5)
        restart_delay = float(self.vars["restart_delay"])
        track_notes = self.vars["track_notes"]
        note_box_hex = self.vars["tracking_color"]
        note_track_ratio = float(self.vars["note_tracking_ratio"] or 0.1)
        scan_delay = float(self.vars["minigame_scan_delay"] or 0.05)
        lock_cursor = (self.vars["lock_cursor"])
        fishing_mode = (self.vars["fishing_mode"])
        if fishing_mode == "Line":
            line_lost_timeout = restart_delay
            self._line_state = {
                'initial_target_gap': None,
                'last_target_left_x': None,
                'last_target_right_x': None,
                'last_left_bar_x': None,
                'last_right_bar_x': None,
                'is_initial_run': True
            }
        else:
            line_lost_timeout = 0.0
        try:
            note_box_tol = int(self.vars["note_box_tolerance"] or 8)
            arrow_tol = int(self.vars["arrow_tolerance"] or 8)
            arrow_method = int(self.vars["arrow_method"])
        except:
            note_box_tol = 8
            arrow_tol = 8
            arrow_method = 2
        previous_detection_source = None
        self.last_bar_size = None
        self.scan_height_ratio = None
        self._last_should_hold = False
        self._last_input_time = 0
        last_line_seen_time = time.perf_counter()
        # Hold And Release Mouse
        def hold_mouse():
            nonlocal mouse_down
            if not mouse_down:
                mouse_controller.press(Button.left)
                # Keyboard_Controller.Press(Key.Space)
                mouse_down = True
        def release_mouse():
            nonlocal mouse_down
            if mouse_down:
                mouse_controller.release(Button.left)
                # Keyboard_Controller.Release(Key.Space)
                mouse_down = False
        # Start Screen Capture Thread (via _start_capture so it's tracked and
        # any previously running capture thread is stopped before this one begins)
        _minigame_stop = self._start_capture(scan_delay)
        while self.macro_running:
            # Step 1: Grab Full Screen Then Crop (Better On Macos)
            if not self._cap_event.wait(timeout=0.5):
                continue

            with self._cap_lock:
                frame = self._cap_frame
                self._cap_event.clear()

            if frame is None:
                _minigame_stop.set()
                return
            img = frame[fish_top:fish_bottom, fish_left:fish_right]
            note_img = frame[shake_top:fish_bottom, fish_left:fish_right]
            friend_img = frame[friend_top:friend_bottom, friend_left:friend_right]
            if lock_cursor == "on": # Lock cursor if enabled
                mouse_controller.position = (shake_x, shake_y)
            # Step 2: Detection
            if fishing_mode == "Line":
                fish_x, left_x, right_x = self._do_line_search(img)
            else:
                fish_x, left_x, right_x = self._do_pixel_search(img)
            arrow_indicator_x = self._find_arrow_indicator_x(img, arrow_hex, arrow_tol, mouse_down)
            if track_notes == "on":
                note_box_pos = self._find_color_center(note_img, note_box_hex, note_box_tol)
            else:
                note_box_pos = None
            # Convert Fish X From Tuple To Int
            if fish_x is None:
                pass
            elif isinstance(fish_x, (list, tuple)):
                fish_x = fish_x[0] + fish_left
            else:
                fish_x = fish_x + fish_left
            if fishing_mode == "Line":
                line_has_full_detection = fish_x is not None and left_x is not None and right_x is not None
                if line_has_full_detection:
                    last_line_seen_time = time.perf_counter()
                elif time.perf_counter() - last_line_seen_time <= line_lost_timeout:
                    if fish_x is None and self.last_fish_x is not None:
                        fish_x = self.last_fish_x
                    if (left_x is None or right_x is None) and self.last_left_x is not None and self.last_right_x is not None:
                        left_x = self.last_left_x
                        right_x = self.last_right_x
            # Step 3: Calculations
            bars_found = left_x is not None and right_x is not None # Check 1
            if bars_found:
                detection_source = 0
            else:
                if arrow_method == 2:
                    bar_center, left_x, right_x = self._update_arrow_box_estimation(arrow_indicator_x, mouse_down, fish_width)
                else:
                    # This ensures rods with 1 arrow can be tracked normally
                    bar_center = self._find_color_cluster(img, arrow_hex, arrow_tol, 10)
                    try:
                        bar_center = bar_center[0]
                    except:
                        pass
                    left_x = bar_center - 20 if not bar_center == None else 0
                    right_x = bar_center + 20 if not bar_center == None else 0
                bars_found = True # Check 2
                detection_source = 1
            
            if bars_found and not (left_x == None or right_x == None): # Bar Or Arrows Found
                bar_size = abs(right_x - left_x)
                bar_center = (left_x + bar_size // 2) + fish_left # Add Fish Left Here
                left_deadzone = bar_size * bar_ratio
                right_deadzone = bar_size * bar_ratio
                max_left = fish_left + left_deadzone
                max_right = fish_right - right_deadzone
            else:
                bar_size = 0
                bar_center = None
                max_left = fish_left
                max_right = fish_right
            if detection_source == 0:
                self.last_left_x = left_x
                self.last_right_x = right_x

                # Completed: Cache Real Box Size
                if left_x is not None and right_x is not None:
                    bar_size = abs(right_x - left_x)
                    if bar_size > 0:
                        self.last_cached_box_length = bar_size

                        # Sync Arrow Estimation Immediately
                        self.estimated_box_length = bar_size
                        
                        # Completed: Sync Hydra-style tracking variables for improved arrow estimation
                        self._last_bar_left_x = left_x
                        self._last_bar_right_x = right_x
                        self._last_bar_box_size = bar_size
                        self._last_bar_center_x = (left_x + right_x) / 2.0
            # Fish Direction-Jump Rejection
            if fish_x is not None:
                if self.last_fish_x is not None and abs(fish_x - self.last_fish_x) > 200:
                    # Outlier Frame — Discard And Reuse Cached Value
                    fish_x = self.last_fish_x
                else:
                    # Accept This Frame And Update Cache
                    self.last_fish_x = fish_x
                self.last_fish_x = fish_x
            # Step 4: Restart Method — Friend Area (green present = minigame ended)
            friend_x = self._find_color_center(friend_img, "#9BFF9B", 5)
            if friend_x is not None:
                release_mouse()
                time.sleep(restart_delay)
                return
            if fish_x == None:
                fish_x = self.last_fish_x
            if left_x == None or right_x == None:
                left_x = self.last_left_x
                right_x = self.last_right_x
            # Position Bar Based On State
            if not mouse_down:
                right_x = left_x + bar_size if not left_x == None else None
            else:
                left_x = right_x - bar_size if not right_x == None else None
            # Step 5: Apply Max Left/Right Calculations
            if bars_found and bar_center is not None: # Bar Found
                if note_box_pos is not None:
                    # Direct Mapping (Already In Fish Space)
                    note_screen_x = note_box_pos[0] + fish_left
                    note_screen_y = note_box_pos[1]
                    note_screen_y_ratio = note_screen_y / (fish_bottom - fish_top)
                else:
                    note_screen_x = None
                if note_box_pos is not None and track_notes == "on":
                    if note_screen_y_ratio >= note_track_ratio:
                        fish_x = note_screen_x
                elif track_notes == "off":
                    pass
                # Compute Bar Left And Bar Right (Screen Coords)
                bar_left_screen  = left_x  + fish_left if not left_x == None else None
                bar_right_screen = right_x + fish_left if not right_x == None else None
                # Check Max Left And Max Right
                if fish_x == None:
                    fish_x = 0
                if max_left and fish_x <= max_left: # Max Left And Right Check (Inside Bar)
                    controller_mode = 3
                elif max_right and fish_x >= max_right:
                    controller_mode = 2
                else:
                    controller_mode = 0
                    if self.vars["efficiency_mode"] == "on":
                        controller_mode = 5
            # Step 7: Controller
            error = round(fish_x - bar_center) if bar_center is not None and fish_x is not None else 0
            if controller_mode == 0 and bar_center is not None:
                control = self._pid_control(error, bar_center)
                # Map PID Output To Mouse Clicks Using Hysteresis To Avoid Jitter/Oscillation
                # Stabilize Deadzone Checker
                if control > 0:
                    hold_mouse()
                else:
                    release_mouse()
            elif controller_mode == 2:
                hold_mouse()
            elif controller_mode == 3:
                release_mouse()
            elif controller_mode == 5 and bar_center is not None:
                should_hold = self._predictive_control(fish_x, bar_center, 
                                                   fish_left, fish_right, 
                                                   bar_left_screen, bar_right_screen)
                if should_hold:
                    hold_mouse()
                else:
                    release_mouse()
            previous_controller_mode = controller_mode
            now = time.perf_counter()
            time.sleep(scan_delay)
    def set_status(self, message):
        """Push a status message to the main webview window's JS."""
        try:
            safe = message.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
            window.evaluate_js("window.setStatus && window.setStatus('" + safe + "')")
        except Exception:
            pass
    def stop_macro(self):
        self.macro_running = False
        try:
            window.show()
        except Exception:
            pass
# =========================
# WINDOW
# =========================
api = Api()
window = webview.create_window(
    "PyWare Fishing V4",
    "ui/index.html",
    js_api=api,
    width=1000,
    height=700
)
webview.start()
