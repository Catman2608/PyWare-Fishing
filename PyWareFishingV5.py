# Imports
# GUI (Primary and fallback)
import webview
import customtkinter as ctk
from tkinter import messagebox
# Text parsing
import json
import re
# Computer vision
import cv2
import numpy as np
import mss
# Misc
import traceback
import threading
import subprocess
import requests
import io
import base64
import time
import sys
import webbrowser
import os
import shutil
from pathlib import Path
# Keyboard and Mouse clicks (platform-specific)
from pynput.keyboard import Listener as KeyListener, Key
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
elif sys.platform == "darwin":
    import Quartz
    import AppKit
elif sys.platform == "linux":
    from Xlib import X, XK, display as Xdisplay
    from Xlib.ext import xtest
# OCR (with fallback if user didn't install Tesseract)
try:
    import pytesseract
    if sys.platform == "win32":
        possible = shutil.which("tesseract")
        if possible:
            pytesseract.pytesseract.tesseract_cmd = possible
    else:
        pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
except:
    pytesseract = None
# Define platform-specific constants
# All platforms
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
macro_running = False
macro_thread = None
APP_VERSION = 5.0
BETA_VERSION = 3
DEVELOPER = "Catman2608"
def get_macos_menu_offset():
    if sys.platform != "darwin":
        return 0

    try:
        screen = AppKit.NSScreen.mainScreen()
        full_frame = screen.frame()
        visible_frame = screen.visibleFrame()
        return int(full_frame.size.height - visible_frame.size.height)

    except Exception:
        return 0

def cgimage_to_srgb_numpy(image):
    if sys.platform == "darwin":
        width = Quartz.CGImageGetWidth(image)
        height = Quartz.CGImageGetHeight(image)
        bytes_per_row = width * 4
        # Create sRGB color space
        color_space = Quartz.CGColorSpaceCreateWithName(
            Quartz.kCGColorSpaceSRGB
        )
        # Allocate buffer
        raw = np.empty((height, width, 4), dtype=np.uint8)
        # Create bitmap context targeting numpy buffer
        context = Quartz.CGBitmapContextCreate(
            raw,
            width,
            height,
            8,
            bytes_per_row,
            color_space,
            Quartz.kCGImageAlphaPremultipliedLast |
            Quartz.kCGBitmapByteOrder32Big
        )
        # Draw image into sRGB context
        Quartz.CGContextDrawImage(
            context,
            Quartz.CGRectMake(0, 0, width, height),
            image
        )
        # RGBA -> BGR
        bgr = raw[:, :, :3][:, :, ::-1]
        return bgr.copy()

    else:
        return image

# Screen dimensions via mss — use monitor[1] (primary) not monitor[0] (virtual combined).
# On Windows with DPI scaling, pywebview's x/y/width/height use physical pixels,
# so we must query the raw physical resolution, not the scaled logical resolution.
try:
    MSS = mss.MSS
except AttributeError:
    MSS = mss.mss
with MSS() as _sct:
    if len(_sct.monitors) > 1:
        _m = _sct.monitors[1]   # Primary monitor
    else:
        _m = _sct.monitors[0]   # Fallback: only one entry exists
    SCREEN_WIDTH  = _m["width"]
    SCREEN_HEIGHT = _m["height"]
    SCREEN_LEFT   = _m["left"]
    SCREEN_TOP    = _m["top"]
HALF_WIDTH = int(SCREEN_WIDTH / 2)
HALF_HEIGHT = int(SCREEN_HEIGHT / 2)
# Windows (Transparency and Ctypes WinDLL)
if sys.platform == "win32":
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    # Ctypes GUI constants
    SW_MAXIMIZE = 3
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int
    ]
    # Set DPI awareness early to ensure consistent coordinate handling
    try:
        windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_PER_MONITOR_DPI_AWARE
        # DPI awareness successfully set
    except:
        try:
            windll.user32.SetProcessDPIAware()  # Fallback for older Windows
            # DPI awareness set (fallback method)
        except:
            pass  # DPI awareness could not be set - coordinates may be inconsistent

    # Windows API related functions
    def get_scale_factor():
        return 1

    def _get_hwnd(window):
        """Return a Windows HWND int from a pywebview window/native object."""
        native = getattr(window, "native", window)
        candidates = (
            native,
            getattr(native, "Handle", None),# WinForms BrowserForm -> System.IntPtr
            getattr(window, "Handle", None),
            getattr(window, "hwnd", None),
        )
        for candidate in candidates:
            if not candidate:
                continue

            if isinstance(candidate, int):
                return candidate

            if hasattr(candidate, "value") and candidate.value:
                return int(candidate.value)

            if hasattr(candidate, "ToInt64"):
                value = int(candidate.ToInt64())
                if value:
                    return value

            if hasattr(candidate, "ToInt32"):
                value = int(candidate.ToInt32())
                if value:
                    return value

            try:
                value = int(candidate)
            except (TypeError, ValueError):
                continue

            if value:
                return value

        return None

# macOS (Keyboard, scale factor, mouse button)
elif sys.platform == "darwin":
    _scale_cache = None
    MAC_KEY_MAP = {
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
        "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20,
        "4": 21, "6": 22, "5": 23, "equal": 24, "9": 25, "7": 26, "minus": 27, "8": 28, "0": 29, "o": 31,
        "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "semicolon": 41, "comma": 43, "slash": 44, "n": 45,
        "m": 46, "period": 47, "space": 49, "return": 36, "enter": 76, "tab": 48, "escape": 53,
    }
    def get_scale_factor():
        global _scale_cache
        if _scale_cache is not None:
            return _scale_cache

        try:
            _scale_cache = float(AppKit.NSScreen.mainScreen().backingScaleFactor())
        except Exception:
            _scale_cache = 1.0
        return _scale_cache

    def get_mouse_position():
        event = Quartz.CGEventCreate(None)
        loc = Quartz.CGEventGetLocation(event)
        return loc.x, loc.y

    def _move_mouse(x, y):
        """Expects logical points."""
        point = Quartz.CGPointMake(x, y)
        Quartz.CGWarpMouseCursorPosition(point)
        Quartz.CGAssociateMouseAndMouseCursorPosition(True)
    def _mouse_event(button="left", press=True, x=None, y=None):
        """Unified cross-platform mouse event.
        button: 'left'/'right'/'middle' or 1/2/3
        press=True → down, False → up
        """
        if x is None or y is None:
            x, y = get_mouse_position()
        # Map button → (Quartz button constant, down event, up event)
        button_map = {
            "left":   (Quartz.kCGMouseButtonLeft, Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp),
            1:        (Quartz.kCGMouseButtonLeft, Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp),
            "right":  (Quartz.kCGMouseButtonRight,Quartz.kCGEventRightMouseDown,Quartz.kCGEventRightMouseUp),
            3:        (Quartz.kCGMouseButtonRight,Quartz.kCGEventRightMouseDown,Quartz.kCGEventRightMouseUp),
            "middle": (Quartz.kCGMouseButtonCenter, Quartz.kCGEventOtherMouseDown,Quartz.kCGEventOtherMouseUp),
            2:        (Quartz.kCGMouseButtonCenter, Quartz.kCGEventOtherMouseDown,Quartz.kCGEventOtherMouseUp),
        }
        key = button.lower() if isinstance(button, str) else button
        if key not in button_map:
            key = "left"
        btn, down_evt, up_evt = button_map[key]
        event_type = down_evt if press else up_evt
        event = Quartz.CGEventCreateMouseEvent(
            None,
            event_type,
            Quartz.CGPointMake(float(x), float(y)),
            btn
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    def send_key(key, delay=0.05, click_type=0):
        """
        Send a keyboard event.
        click_type:
            0 = click (press + release)   [default]
            1 = hold (press only)
            2 = release (release only)
        """
        keycode = MAC_KEY_MAP.get(str(key).lower())
        if keycode is None:
            return

        if click_type == 0:           # Click (press + release)
            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, keycode, True)   # key down
            )
            time.sleep(delay)
            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, keycode, False)  # key up
            )
        elif click_type == 1:         # Hold (press only)
            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, keycode, True)   # key down
            )
        elif click_type == 2:         # Release only
            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, keycode, False)  # key up
            )
        else:
            # Fallback to normal click if invalid value is passed
            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
            )
            time.sleep(delay)
            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
            )

# Linux (Mouse positions and Xdisplay)
elif sys.platform.startswith("linux"):
    _xdisplay = None
    def _get_xdisplay():
        global _xdisplay
        if _xdisplay is None:
            _xdisplay = Xdisplay.Display()
        return _xdisplay

    def get_scale_factor():
        """
        X11 normally works in physical pixels.
        Return 1.0 unless you implement desktop-specific scaling detection.
        """
        return 1.0

    def get_mouse_position():
        d = _get_xdisplay()
        root = d.screen().root
        pointer = root.query_pointer()
        return pointer.root_x, pointer.root_y

    def _move_mouse(x, y):
        d = _get_xdisplay()
        root = d.screen().root
        root.warp_pointer(int(x), int(y))
        d.sync()
    def _mouse_event(button="left", press=True, x=None, y=None):
        """Unified cross-platform mouse event.
        button: 'left'/'right'/'middle' or 1/2/3
        press=True → down, False → up
        """
        d = _get_xdisplay()
        if x is not None and y is not None:
            _move_mouse(x, y)   # move first so the click happens at the desired location
        button_map = {
            "left": 1, 1: 1,
            "middle": 2, 2: 2,
            "right": 3, 3: 3,
        }
        key = button.lower() if isinstance(button, str) else button
        btn = button_map.get(key, 1)
        xtest.fake_input(
            d,
            X.ButtonPress if press else X.ButtonRelease,
            btn
        )
        d.sync()
    def send_key(key, delay=0.05):
        d = _get_xdisplay()
        keysym = XK.string_to_keysym(str(key))
        if keysym == 0:
            keysym = XK.string_to_keysym(str(key).lower())
        if keysym == 0:
            return

        keycode = d.keysym_to_keycode(keysym)
        if keycode == 0:
            return

        xtest.fake_input(d, X.KeyPress, keycode)
        d.sync()
        time.sleep(delay)
        xtest.fake_input(d, X.KeyRelease, keycode)
        d.sync()

# Config management
def get_base_path():
    # 1. Check if the application is bundled/frozen
    if getattr(sys, 'frozen', False):
        # Detect if it's a macOS application bundle (.app)
        # In macOS bundles, the executable runs inside Contents/MacOS/
        if sys.platform == 'darwin' and '.app/Contents/MacOS' in sys.executable:
            return Path(sys.executable).parent.resolve(), True

        # Detect if it's a Linux packaged environment (like AppImage)
        # Linux AppImages extract to a mount point, keeping assets inside the binary environment
        elif sys.platform.startswith('linux') and 'AppRun' in sys.executable:
            return Path(sys.executable).parent.resolve(), True

        # 2. Windows EXE (One-File) or standard local folder deployment
        # Returns the directory containing the actual .exe file, NOT the temporary _MEIPASS folder
        else:
            return Path(sys.executable).parent.resolve(), True

    # 3. Running from raw source code (.py file)
    else:
        return Path(__file__).parent.resolve(), False

# Establish the global base path for PyWare Fishing V5
BASE_PATH, IS_COMPILED = get_base_path()
# Make sure base path exists
os.makedirs(BASE_PATH, exist_ok=True)
# Configs Path
LAST_CONFIG = os.path.join(BASE_PATH, "last_config.json")
CONFIGS_PATH = os.path.join(BASE_PATH, "configs")
IMAGES_PATH = os.path.join(BASE_PATH, "images")
UI_PATH = os.path.join(BASE_PATH, "ui")
# File management
def open_base_folder():
    folder = BASE_PATH
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":  # Macos
        subprocess.run(["open", folder])
    else:  # Linux
        subprocess.run(["xdg-open", folder])

# ─────────────────────────────────────────────────────────────────────────────
# Central area definitions.  To add a new selectable area:
#   1. Add an entry below (key, color, label, default ratios 0–1).
#   2. That's it — selector UI, save/load, defaults, and the show/hide menu
#      all pick it up automatically.  Use get_areas("your_key") later if needed.
# ─────────────────────────────────────────────────────────────────────────────
AREA_CONFIG = {
    "shake": {
        "color": "#ff007a",
        "label": "Shake Box",
        "default": {"x": 0.1041, "y": 0.0925, "width": 0.7917, "height": 0.6963},
    },
    "fish": {
        "color": "#00daff",
        "label": "Fish Box",
        "default": {"x": 0.2844, "y": 0.7981, "width": 0.4297, "height": 0.0389},
    },
    "friend": {
        "color": "#f7ff00",
        "label": "Friend Box (Fish End)",
        "default": {"x": 0.0046, "y": 0.8583, "width": 0.0355, "height": 0.0817},
    },
    "totem": {
        "color": "#9cff94",
        "label": "Totem Box (Day/Night)",
        "default": {"x": 0.9531, "y": 0.8333, "width": 0.0208, "height": 0.0463},
    },
    "appraisal": {
        "color": "#a36700",
        "label": "Appraisal Box (Dialogue)",
        "default": {"x": 0.3364, "y": 0.4453, "width": 0.3385, "height": 0.1629},
    },
}
# Display / iteration order (also used for number-key toggles 1–9 in the selector)
AREA_ORDER = list(AREA_CONFIG.keys())

class AreaSelector:
    """
    Fullscreen transparent overlay implemented as a second pywebview window.
    Long-lived instance: call show() / hide() / update() as needed.

    Areas are fully data-driven via the module-level AREA_CONFIG / AREA_ORDER.
    Adding a new area requires only a new entry in AREA_CONFIG.
    """
    HTML_FILE = os.path.join(UI_PATH, "area_selector.html")

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.area_window = None
        self._open = False
        self._areas = {}
        self._visible = {name: True for name in AREA_ORDER}
        self._screen_capture = None
        self._screenshot_b64 = None

    def _capture_and_crop(self):
        """Capture full screen and remove the macOS menu bar strip so the
        image matches the frameless window geometry (no menu bar)."""
        frame = self.parent_app.capture_single_frame()
        if frame is None:
            return None
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3].copy()
        menu_offset = get_macos_menu_offset()
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        self._scale = scale
        if menu_offset > 0:
            crop = int(round(menu_offset * scale))
            if 0 < crop < frame.shape[0]:
                frame = frame[crop:, :, :].copy()
        frame = np.clip(frame.astype(np.int16) - 15, 0, 255).astype(np.uint8)
        return frame

    def _encode_screenshot(self, frame):
        """Encode BGR numpy frame as a JPEG data-URL for the canvas."""
        if frame is None:
            return None
        try:
            # JPEG keeps the payload small enough for evaluate_js
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return None
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return "data:image/jpeg;base64," + b64
        except Exception:
            return None

    def show(self):
        if self._open and self.area_window:
            return
        self._screen_capture = self._capture_and_crop()
        self._screenshot_b64 = self._encode_screenshot(self._screen_capture)
        menu_offset = get_macos_menu_offset()
        self.area_window = webview.create_window(
            "Area Selector", self.HTML_FILE, js_api=self,
            transparent=True, frameless=True, easy_drag=False, on_top=True,
            resizable=False, width=SCREEN_WIDTH, height=SCREEN_HEIGHT - menu_offset,
            x=SCREEN_LEFT, y=SCREEN_TOP, background_color="#000000",
        )
        self._open = True
        self.area_window.events.closed += self._on_closed
        if sys.platform == "win32":
            def maximize_area_selector():
                try:
                    hwnd = _get_hwnd(self.area_window)
                    if hwnd:
                        user32.ShowWindow(wintypes.HWND(hwnd), SW_MAXIMIZE)
                except Exception as e:
                    try:
                        self.parent_app.set_status(f"Failed to maximize area selector: {e}")
                    except Exception:
                        print("Failed to maximize area selector:", e)
            self.area_window.events.shown += maximize_area_selector

    def _to_ratios(self, area):
        """Accept normalized areas and legacy pixel areas, store normalized values."""
        if not isinstance(area, dict):
            return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
        values = {
            "x": float(area.get("x", 0)),
            "y": float(area.get("y", 0)),
            "width": float(area.get("width", area.get("w", 0))),
            "height": float(area.get("height", area.get("h", 0))),
        }
        if any(abs(values[key]) > 1 for key in values):
            values["x"] /= SCREEN_WIDTH
            values["y"] /= SCREEN_HEIGHT
            values["width"] /= SCREEN_WIDTH
            values["height"] /= SCREEN_HEIGHT
        return values

    def update(self, area_name, area_dict):
        """Set one area by name (ratios or legacy pixels)."""
        self._areas[area_name] = self._to_ratios(area_dict)

    def update_all(self, areas_dict):
        """Bulk-load every known area from a {name: dict} mapping."""
        for name in AREA_ORDER:
            src = (areas_dict or {}).get(name)
            if not isinstance(src, dict):
                src = AREA_CONFIG[name]["default"]
            self._areas[name] = self._to_ratios(src)

    def get_area_config(self):
        """Return colours, labels, order and visibility so JS stays data-driven."""
        return {
            "order": list(AREA_ORDER),
            "areas": {
                name: {"color": cfg["color"], "label": cfg["label"]}
                for name, cfg in AREA_CONFIG.items()
            },
            "visible": dict(self._visible),
        }

    def set_visibility(self, visible_dict):
        """Keep Python in sync when the overlay panel toggles boxes."""
        if isinstance(visible_dict, dict):
            for name, val in visible_dict.items():
                if name in self._visible:
                    self._visible[name] = bool(val)

    def get_areas(self):
        """Return canvas-relative pixel boxes for JS (menu-bar offset subtracted)."""
        menu_offset = get_macos_menu_offset()
        result = {}
        for name, area in self._areas.items():
            result[name] = {
                "x": area["x"] * SCREEN_WIDTH,
                "y": area["y"] * SCREEN_HEIGHT - menu_offset,
                "width": area["width"] * SCREEN_WIDTH,
                "height": area["height"] * SCREEN_HEIGHT,
            }
        return result

    def on_mouse_move(self, mouse_x, mouse_y, current_boxes):
        if not self._open:
            return
        menu_offset = get_macos_menu_offset()
        for name in AREA_ORDER:
            box = current_boxes.get(name, {})
            if box:
                self._areas[name] = self._pixels_to_ratios(box, menu_offset)
            b = current_boxes.get(name)
            if b and self._visible.get(name, True):
                bx, by = float(b.get("x", 0)), float(b.get("y", 0))
                bw = float(b.get("width", b.get("w", 0)) or 1)
                bh = float(b.get("height", b.get("h", 0)) or 1)
                mx, my = float(mouse_x or 0), float(mouse_y or 0)
                if bx <= mx <= bx + bw and by <= my <= by + bh:
                    xr = round((mx - bx) / bw, 2)
                    yr = round((my - by) / bh, 2)
                    try:
                        self.parent_app.set_status(f"{name.upper()} → X: {xr:.2f}  Y: {yr:.2f}")
                    except Exception:
                        pass
                    break

    def _pixels_to_ratios(self, box, menu_offset=0):
        return {
            "x": float(box.get("x", 0)) / SCREEN_WIDTH,
            "y": (float(box.get("y", 0)) + menu_offset) / SCREEN_HEIGHT,
            "width": float(box.get("width", box.get("w", 0))) / SCREEN_WIDTH,
            "height": float(box.get("height", box.get("h", 0))) / SCREEN_HEIGHT,
        }

    def window_ready(self, win_x, win_y):
        """JS signals the page is ready — push the frozen screenshot."""
        if self._screenshot_b64 and self.area_window and self._open:
            # Inject via a short data reference; JS stores it and draws.
            try:
                # Pass as return value of a dedicated getter instead of
                # embedding a huge string in evaluate_js when possible.
                self.area_window.evaluate_js(
                    "window.__applyScreenshot && window.__applyScreenshot()"
                )
            except Exception:
                pass
        return None

    def save_areas(self, areas):
        if not self._open:
            return
        menu_offset = get_macos_menu_offset()
        for name in AREA_ORDER:
            if name in areas:
                self._areas[name] = self._pixels_to_ratios(areas[name], menu_offset)
        self.parent_app.bar_areas.update(self._areas)
        self.parent_app.save_misc_settings()
        self._open = False
        self.parent_app.set_status("Area selector closed")
        if self.area_window:
            try:
                self.area_window.destroy()
            except Exception:
                pass

    def get_screenshot_data(self):
        """Return the data-URL of the frozen (menu-bar-cropped) screenshot."""
        return self._screenshot_b64 or ""

    def _on_closed(self):
        if self._open:
            self.parent_app.bar_areas.update(self._areas)
            self.parent_app.save_misc_settings()
            self.parent_app.set_status("Area selector closed")
        self.area_window = None
        self._open = False

    def is_open(self):
        return self._open and self.area_window is not None

    def hide(self):
        if self.is_open():
            self.close()

    def close(self):
        if self.is_open():
            self.save_areas(self.get_areas())
# Eyedropper class
class Eyedropper:
    """
    Fullscreen transparent overlay for color picking using pywebview.
    Captures a frozen screenshot (menu bar cropped so it matches the
    frameless window), renders it in the canvas, and returns the picked color.
    """
    HTML_FILE = os.path.join(UI_PATH, "eyedropper.html")

    def __init__(self, parent_app):
        self.parent = parent_app
        self.eyedropper_window = None
        self._open = False
        self._visible = False
        self.last_picked_color = None
        self._cancelled = False
        self._color_key = None
        self._scale = 1.0
        self._screen_capture = None
        self._screenshot_b64 = None
        self.left = 0
        self.top = 0
        self.width = 0
        self.height = 0

    def _capture_and_crop(self):
        """Capture full screen and remove the macOS menu bar strip so the
        image matches the frameless window geometry (no menu bar)."""
        frame = self.parent.capture_single_frame()
        if frame is None:
            return None
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3].copy()
        menu_offset = get_macos_menu_offset()
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        self._scale = scale
        if menu_offset > 0:
            crop = int(round(menu_offset * scale))
            if 0 < crop < frame.shape[0]:
                frame = frame[crop:, :, :].copy()
        return frame

    def _encode_screenshot(self, frame):
        """Encode BGR numpy frame as a JPEG data-URL for the canvas."""
        if frame is None:
            return None
        try:
            # JPEG keeps the payload small enough for evaluate_js
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return None
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return "data:image/jpeg;base64," + b64
        except Exception:
            return None

    def show(self, color_key=None):
        """Open the eyedropper overlay. Optional color_key is the settings
        field that should receive the picked color (e.g. 'fish_color')."""
        if self._open and self.eyedropper_window:
            return

        self.last_picked_color = None
        self._cancelled = False
        self._color_key = color_key

        self._screen_capture = self._capture_and_crop()
        self._screenshot_b64 = self._encode_screenshot(self._screen_capture)

        menu_offset = get_macos_menu_offset()
        win_h = max(1, SCREEN_HEIGHT - menu_offset)
        self.left = SCREEN_LEFT
        self.top = SCREEN_TOP
        self.width = SCREEN_WIDTH
        self.height = win_h

        self.eyedropper_window = webview.create_window(
            "Eyedropper",
            self.HTML_FILE,
            js_api=self,
            transparent=True,
            frameless=True,
            easy_drag=False,
            on_top=True,
            resizable=False,
            width=self.width,
            height=self.height,
            x=self.left,
            y=self.top,
            background_color="#000000",
        )
        self._open = True
        self._visible = True
        self.eyedropper_window.events.closed += self._on_closed
        if sys.platform == "win32":
            # Maximize on Windows after the window is created
            def maximize_area_selector():
                try:
                    hwnd = _get_hwnd(self.eyedropper_window)
                    if hwnd:
                        user32.ShowWindow(wintypes.HWND(hwnd), SW_MAXIMIZE)
                except Exception as e:
                    self.parent.set_status("Failed to maximize area selector:", e)
            self.eyedropper_window.events.shown += maximize_area_selector
        try:
            self.parent.set_status(
                "Eyedropper opened • Hover to preview • Click to pick • Esc to cancel"
            )
        except Exception:
            pass

    def is_open(self):
        return self._open and self.eyedropper_window is not None

    def hide(self):
        """Destroys the current window instance completely."""
        if self.eyedropper_window and self._open:
            try:
                self.eyedropper_window.destroy()
            except Exception:
                pass
            self._on_closed()

    def close(self):
        """Alias used by shutdown / toggle paths."""
        self.hide()

    # ── JS API methods (called from eyedropper.html) ──

    def window_ready(self, win_x, win_y):
        """JS signals the page is ready — push the frozen screenshot."""
        if self._screenshot_b64 and self.eyedropper_window and self._open:
            # Inject via a short data reference; JS stores it and draws.
            try:
                # Pass as return value of a dedicated getter instead of
                # embedding a huge string in evaluate_js when possible.
                self.eyedropper_window.evaluate_js(
                    "window.__applyScreenshot && window.__applyScreenshot()"
                )
            except Exception:
                pass
        return None

    def get_screenshot_data(self):
        """Return the data-URL of the frozen (menu-bar-cropped) screenshot."""
        return self._screenshot_b64 or ""

    def get_pixel_at(self, x, y):
        """Sample the frozen capture at logical canvas coordinates (x, y).
        Menu bar was already cropped out, so no y-offset is needed."""
        if not self.is_open():
            return "#000000"

        frame = self._screen_capture
        if frame is None:
            return "#000000"

        scale = self._scale if self._scale > 0 else 1.0
        px = int(x * scale)
        py = int(y * scale)

        if px < 0 or py < 0 or py >= frame.shape[0] or px >= frame.shape[1]:
            return "#000000"

        b = int(frame[py, px, 0])
        g = int(frame[py, px, 1])
        r = int(frame[py, px, 2])
        hex_color = f"#{r:02X}{g:02X}{b:02X}"

        try:
            self.parent.set_status(f"{hex_color} • Click to pick • Esc to cancel")
        except Exception:
            pass

        return hex_color

    def pick_color(self, hex_color):
        """Called by JS when user clicks to pick a color.
        Stores the color, pushes it to the main UI, and closes the overlay."""
        if not self.is_open():
            return None

        if not hex_color or not isinstance(hex_color, str):
            return None

        hex_color = hex_color.strip()
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color

        self.last_picked_color = hex_color
        self._cancelled = False

        # Write into settings vars when a target key was provided
        color_key = self._color_key
        if color_key:
            try:
                self.parent.vars[color_key] = hex_color
            except Exception:
                pass

        # Notify the main webview so the color input updates
        self._notify_main_ui(hex_color, color_key)

        try:
            self.parent.set_status(f"Picked color: {hex_color}")
        except Exception:
            pass

        self.hide()
        return hex_color

    def close_eyedropper(self):
        """Called by JS on Escape — cancel without picking."""
        if not self.is_open():
            return
        self._cancelled = True
        self.last_picked_color = None
        try:
            self.parent.set_status("Eyedropper cancelled")
        except Exception:
            pass
        self.hide()

    def _notify_main_ui(self, hex_color, color_key=None):
        """Push the picked color into the main pywebview window."""
        try:
            safe = hex_color.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            key_js = "null"
            if color_key:
                key_js = "'" + str(color_key).replace("\\", "\\\\").replace("'", "\\'") + "'"
            script = (
                f"(function(){{"
                f"var c='{safe}',k={key_js};"
                f"if(window.onColorPicked)window.onColorPicked(c,k);"
                f"if(window.setPickedColor)window.setPickedColor(c,k);"
                f"if(k){{var el=document.getElementById(k)||document.querySelector('[data-color-key=\"'+k+'\"]')"
                f"||document.querySelector('input[name=\"'+k+'\"]');"
                f"if(el){{el.value=c;el.dispatchEvent(new Event('input',{{bubbles:true}}));"
                f"el.dispatchEvent(new Event('change',{{bubbles:true}}));}}"
                f"}}"
                f"}})()"
            )
            # Main window is the first created window
            if webview.windows:
                webview.windows[0].evaluate_js(script)
        except Exception:
            pass

    def _on_closed(self, *args):
        """Lifecycle cleanup when the overlay is destroyed."""
        self.eyedropper_window = None
        self._open = False
        self._visible = False
        self._screenshot_b64 = None
        # Keep last_picked_color so the main UI can still poll it

class FishOverlay:
    HTML_FILE = os.path.join(UI_PATH, "fish_overlay.html")
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.overlay_window = None  
        self._open = False
        self._visible = False
        # Track active viewport geometry (logical points for pywebview)
        self.left = 0
        self.top = 0
        self.width = 0
        self.height = 0

    def _to_window_coords(self, left, top, width, height):
        """
        Convert physical-pixel geometry (from _get_areas / capture) into the
        logical points pywebview expects for window x/y/width/height.
        On Windows scale is always 1; on macOS Retina it is typically 2.0.
        """
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        left = int(left / scale)
        top = int(top / scale)
        width = max(1, int(width / scale))
        height = max(1, int(height / scale))
        # Clamp so the window stays on-screen (logical screen size)
        screen_w = max(1, SCREEN_WIDTH)
        screen_h = max(1, SCREEN_HEIGHT)
        left = max(0, min(left, max(0, screen_w - width)))
        top = max(0, min(top, max(0, screen_h - height)))
        return left, top, width, height

    def show(self, left, top, width, height):
        """Creates and displays the transparent frameless overlay window.

        Arguments are physical-pixel screen coordinates (same space as
        _get_areas / capture_frame). They are converted to logical points
        for pywebview.
        """
        left, top, width, height = self._to_window_coords(left, top, width, height)

        if self._open and self.overlay_window:
            # If already open, shift/resize it instead of duplicating
            self.resize(left, top, width, height, already_logical=True)
            return

        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.overlay_window = webview.create_window(
            "Fish Overlay",
            url=self.HTML_FILE,
            transparent=True,
            frameless=True,
            easy_drag=False,
            on_top=True,
            resizable=False,
            width=self.width,
            height=self.height,
            x=self.left,
            y=self.top,
            background_color="#000000",
        )
        self._open = True
        self._visible = True
        self.overlay_window.events.closed += self._on_closed

    def hide(self):
        """Destroys the current window instance completely."""
        if self.overlay_window and self._open:
            self.overlay_window.destroy()
            self._on_closed()

    def resize(self, left, top, width, height, already_logical=False):
        """Resizes and moves the window dynamically if it exists.

        By default arguments are physical pixels (same as show()).
        Pass already_logical=True when the caller has already converted them.
        """
        if not already_logical:
            left, top, width, height = self._to_window_coords(left, top, width, height)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        if self.overlay_window and self._open:
            try:
                self.overlay_window.move(self.left, self.top)
                self.overlay_window.resize(self.width, self.height)
            except Exception:
                pass

    def clear(self):
        """Clears rendering elements inside the web view context."""
        self._eval("window.fishOverlay && window.fishOverlay.clear()")

    def draw_box(self, bar_center, box_size, color, canvas_offset,
             show_bar_center=False, bar_y1=0.15, bar_y2=0.85):
        """Evaluates JS drawing contexts based on calculations inside the viewport.

        bar_center / box_size / canvas_offset are in physical pixels relative to
        the fish capture region; they are converted to logical CSS pixels for
        the overlay canvas (which matches the logical window size).
        """
        if bar_center is None:
            return

        # Ensure the overlay exists before trying to execute scripts on it
        if not self._open or not self.overlay_window:
            return

        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        bar_center = float(bar_center) / scale
        canvas_offset = float(canvas_offset) / scale
        half_size = float(box_size) / (2 * scale) if box_size else 0
        center_x = bar_center - canvas_offset
        shape = {
            "x1": center_x - half_size,
            "x2": center_x + half_size,
            "center_x": center_x,
            "color": str(color),
            "show_bar_center": bool(show_bar_center),
            "bar_y1": max(0.0, min(1.0, float(bar_y1))),
            "bar_y2": max(0.0, min(1.0, float(bar_y2))),
        }
        self._eval(f"window.fishOverlay && window.fishOverlay.draw({json.dumps(shape)})")

    def _eval(self, script):
        """Safely executes JavaScript strings within the running window environment."""
        if self.overlay_window and self._open:
            try:
                self.overlay_window.evaluate_js(script)
            except Exception:
                pass  # Suppress errors if window drops out mid-execution

    def _on_closed(self):
        """Internal callback cleaning lifecycle states upon execution exit."""
        self.overlay_window = None
        self._open = False
        self._visible = False
class Api:
    def __init__(self):
        self.vars = {} # Save Entry Variables Here
        self.current_config = self.get_last_config()
        self.load_settings_into_vars(self.current_config)
        # Start Hotkey Listener
        try:
            self.key_listener = KeyListener(on_press=self.on_key_press)
            self.key_listener.daemon = True
            self.key_listener.start()
        except Exception as e:
            self.set_status(f"Key Listener error: {e}")
        # Store Screen Width And Height To Use Later
        self.SCREEN_WIDTH = SCREEN_WIDTH
        self.SCREEN_HEIGHT = SCREEN_HEIGHT
        self.SCREEN_LEFT = SCREEN_LEFT
        self.SCREEN_TOP = SCREEN_TOP
        self.SCREEN_SCALE = ((self.SCREEN_WIDTH / 1920) + (self.SCREEN_HEIGHT / 1080)) / 2
        # Macro State
        self.macro_running = False
        self.macro_thread = None
        # Safe Defaults Before Key Listener Starts (Will Be Overwritten By Load_Misc_Settings)
        self.bar_areas = {name: None for name in AREA_ORDER}
        self.current_rod_name = "Basic Rod"
        self.scale_x_1440 = self.SCREEN_WIDTH / 2560
        self.scale_y_1440 = self.SCREEN_HEIGHT / 1440
        # Screen Capture
        self.capture_thread = None
        self.capture_frame = None
        self.capture_id = 0
        self.scan_delay = 0.1
        # Other classes
        self.area_selector = AreaSelector(self)
        self.eyedropper = Eyedropper(self)
        self.fish_overlay = FishOverlay(self)
        # Load Settings
        self.load_misc_settings()
    def _refresh_screen_dimensions(self):
        """
        Re-query mss for the primary monitor's current resolution and update all
        screen-dimension instance variables.  Call this whenever the capture monitor
        changes (hot-plug, resolution switch, etc.) so that _get_areas, the capture pipelines,
        and the fish-overlay layout all use the correct pixel dimensions.
        Invalidating _thread_local forces the capture pipelines to rebuild its cached
        monitor dict on the next capture call.
        """
        with MSS() as _sct:
            if len(_sct.monitors) > 1:
                _m = _sct.monitors[1]
            else:
                _m = _sct.monitors[0]
        self.SCREEN_WIDTH  = _m["width"]
        self.SCREEN_HEIGHT = _m["height"]
        self.SCREEN_LEFT   = _m["left"]
        self.SCREEN_TOP    = _m["top"]
        self.SCREEN_SCALE  = ((self.SCREEN_WIDTH / 1920) + (self.SCREEN_HEIGHT / 1080)) / 2
        self.scale_x_1440  = self.SCREEN_WIDTH  / 2560
        self.scale_y_1440  = self.SCREEN_HEIGHT / 1440
        # Force the capture pipelines to rebuild the thread-local monitor dict.
        self._thread_local = threading.local()
    # Save Config
    def _get_prompt_defaults(self):
        defaults = {}
        index_path = os.path.join(UI_PATH, "index.html")
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception:
            return defaults

        input_pattern = re.compile(r"<input\b(?=[^>]*\bid\s*=\s*['\"]?([^'\"\s>]+))" r"(?=[^>]*\bplaceholder\s*=\s*['\"]([^'\"]*)['\"])[^>]*>", re.IGNORECASE,)
        for field_id, placeholder in input_pattern.findall(html):
            prompt = placeholder.strip()
            defaults[field_id] = prompt
        select_pattern = re.compile( r"<select\b(?=[^>]*\bid\s*=\s*['\"]?([^'\"\s>]+))[^>]*>" r"(.*?)</select>", re.IGNORECASE | re.DOTALL, )
        option_pattern = re.compile( r"<option\b[^>]*\bvalue\s*=\s*['\"]?([^'\"\s>]+)", re.IGNORECASE, )
        for field_id, body in select_pattern.findall(html):
            match = option_pattern.search(body)
            if match:
                defaults[field_id] = match.group(1).strip()
        return defaults

    def _get_saved_default_config(self):
        default_path = os.path.join(CONFIGS_PATH, "Default", "config.json")
        try:
            with open(default_path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}

        except Exception:
            return {}

    def _get_config_defaults(self):
        defaults = self._get_saved_default_config()
        defaults.update(self._get_prompt_defaults())
        if hasattr(self, "default_settings_data"):
            defaults.update(getattr(self, "default_settings_data", {}))
        return defaults

    def _fill_blank_settings(self, settings):
        clean_settings = dict(settings or {})
        defaults = self._get_config_defaults()
        for key, value in list(clean_settings.items()):
            if isinstance(value, str) and value.strip() == "" and key in defaults:
                clean_settings[key] = defaults[key]
        return clean_settings

    def _load_config_data(self, config_name):
        config_path = os.path.join(CONFIGS_PATH, config_name, "config.json")
        with open(config_path, "r") as f:
            settings = json.load(f)
        settings = self._fill_blank_settings(settings)
        return settings, config_path

    def save_config(self, config_name, settings, text="Settings saved"):
        try:
            if not config_name:
                return {"success": False, "error": "No config selected."}

            folder = os.path.join(CONFIGS_PATH,config_name)
            os.makedirs(folder, exist_ok=True)
            settings = self._fill_blank_settings(settings)
            self.vars.update(settings)
            self.current_config = config_name
            self.save_last_config(config_name)
            config_path = os.path.join( folder, "config.json" )
            with open(config_path, "w") as f:
                json.dump(settings,f,indent=4)
            self.set_status(text)
            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # Load Config
    def load_config(self, config_name):
        try:
            if not config_name:
                return {"success": False, "error": "No config selected."}

            settings, config_path = self._load_config_data(config_name)
            with open(config_path, "w") as f:
                json.dump(settings,f,indent=4)
            self.vars = settings.copy()
            self.current_config = config_name
            self.save_last_config(config_name)
            return {"success": True, "settings": settings}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # List Configs
    def list_configs(self):
        try:
            configs = sorted([folder for folder in os.listdir(CONFIGS_PATH) if os.path.isdir(os.path.join(CONFIGS_PATH, folder))])
            return configs

        except Exception:
            return []

    # Settings State
    def update_settings(self, settings):
        self.vars.update(settings)
        return {"success": True}

    def get_last_config(self):
        try:
            if os.path.exists(LAST_CONFIG):
                with open(LAST_CONFIG, "r") as f:
                    data = json.load(f)
                return data.get("last_config", "")

        except Exception:
            pass

        return ""

    def save_last_config(self, config_name):
        try:
            data = {}
            if os.path.exists(LAST_CONFIG):
                with open(LAST_CONFIG, "r") as f:
                    data = json.load(f)
            data["last_config"] = config_name
            with open(LAST_CONFIG, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.set_status(f"Error saving last config: {e}")
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

        try:
            settings, config_path = self._load_config_data(config_name)
            with open(config_path, "w") as f:
                json.dump(settings,f,indent=4)
            self.vars = settings
            self.current_config = config_name
            self.save_last_config(config_name)
        except Exception as e:
            self.set_status(f"Error loading config: {e}")
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

    # Delete Config
    def delete_config(self, config_name):
        try:
            folder = os.path.join( CONFIGS_PATH, config_name )
            config_path = os.path.join( folder, "config.json" )
            if os.path.exists(config_path):
                os.remove(config_path)
            if os.path.exists(folder):
                os.rmdir(folder)
            return { "success": True }

        except Exception as e:
            return { "success": False, "error": str(e) }

    def load_misc_settings(self):
        """Load miscellaneous settings from last_config.json."""
        # Defaults
        self.current_rod_name = "Default"
        self.bar_areas = {name: None for name in AREA_ORDER}
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
            # Bar Areas
            loaded_areas = data.get("bar_areas", {})
            for key in AREA_ORDER:
                area = loaded_areas.get(key)
                if isinstance(area, dict):
                    self.bar_areas[key] = {
                        "x": float(area.get("x", 0)),
                        "y": float(area.get("y", 0)),
                        "width": float(area.get("width", 0)),
                        "height": float(area.get("height", 0)),
                    }
            # Hotkeys
            start_key  = data.get("start_key", "F5")
            change_key = data.get("change_bar_areas_key", "F6")
            stop_key   = data.get("stop_key", "F7")
        except Exception as e:
            self.set_status(f"Failed to load misc settings: {e}")
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
        for key in AREA_ORDER:
            area = self.bar_areas.get(key)
            if isinstance(area, dict):
                clean_bar_areas[key] = {
                    "x": float(area.get("x", 0)),
                    "y": float(area.get("y", 0)),
                    "width": float(area.get("width", 0)),
                    "height": float(area.get("height", 0)),
                }
            else:
                clean_bar_areas[key] = None
        # Save
        data["bar_areas"] = clean_bar_areas
        # Hotkeys
        # data["start_key"] = self.vars["start_key"]
        # data["change_bar_areas_key"] = self.vars["change_bar_areas_key"]
        # data["stop_key"] = self.vars["stop_key"]
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    def open_base_folder(self):
        open_base_folder()
    def get_default_settings(self):
        return self._get_config_defaults()

    def get_default_colors(self):
        default_settings = self.get_default_settings()
        color_keys = [
            "left_color",
            "right_color",
            "arrow_color",
            "fish_color",
            "left_tolerance",
            "right_tolerance",
            "arrow_tolerance",
            "fish_tolerance",
            "shake_color",
            "shake_tolerance",
            "green_cast_color",
            "green_cast_tolerance",
            "white_cast_color",
            "white_cast_tolerance",
            "tracking_color",
            "tracking_tolerance",
            "friends_color",
            "friends_tolerance",
        ]
        return {

            key: default_settings[key]
            for key in color_keys
            if key in default_settings
        }
    def reset_settings(self, config_name):
        try:
            config_folder = os.path.join(
                CONFIGS_PATH,
                config_name
            )
            config_path = os.path.join(
                config_folder,
                "config.json"
            )
            os.makedirs(
                config_folder,
                exist_ok=True
            )
            existing_config = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    existing_config = json.load(f)
            # Full defaults
            default_settings = self.get_default_settings()
            # Preserve colors
            for color_key in self.get_default_colors().keys():
                if color_key in existing_config:
                    default_settings[color_key] = (
                        existing_config[color_key]
                    )
            with open(config_path, "w") as f:
                json.dump(
                    default_settings,
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
    def reset_colors(self, config_name):
        try:
            config_folder = os.path.join(
                CONFIGS_PATH,
                config_name
            )
            config_path = os.path.join(
                config_folder,
                "config.json"
            )
            os.makedirs(
                config_folder,
                exist_ok=True
            )
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_data = json.load(f)
            else:
                config_data = {}
            # Reset only colors
            config_data.update(
                self.get_default_colors()
            )
            with open(config_path, "w") as f:
                json.dump(
                    config_data,
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
    def reset_areas(self):
        """Reset areas to default"""
        try:
            config_path = os.path.join(
                BASE_PATH,
                "last_config.json"
            )
            if not os.path.exists(config_path):
                return {

                    "success": True
                }
            with open(config_path, "r") as f:
                config_data = json.load(f)
            # Remove saved custom areas
            config_data.pop("bar_areas", None)
            with open(config_path, "w") as f:
                json.dump(config_data,f,indent=4)
            return {"success": True}

        except Exception as e:
            return {

                "success": False,
                "error": str(e)
            }
    def export_config(self, settings):
        try:
            path = webview.windows[0].create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename="config.json"
            )
            if not path:
                return {"success": False, "error": "Cancelled"}

            if isinstance(path, (list, tuple)):
                path = path[0]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            return {"success": True, "path": path}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_link(self, url):
        """Open a URL in the default web browser."""
        try:
            webbrowser.open(url)
            return {

                "success": True
            }
        except Exception as e:
            return {

                "success": False,
                "error": str(e)
            }
    def get_macro_version(self):
        return APP_VERSION

    def set_status(self, message):
        """Push a status message to the main webview window's JS."""
        if IS_COMPILED == False:
            # print("Debug: ", message)
            pass
        try:
            safe = message.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
            window.evaluate_js("window.setStatus && window.setStatus('" + safe + "')")
        except Exception:
            pass

    def _get_scale_factor(self):
        return get_scale_factor()

    # Area Selector
    def open_area_selector(self):
        # Build current areas from bar_areas or AREA_CONFIG defaults (all keys, including appraisal)
        areas = {}
        for name in AREA_ORDER:
            a = self.bar_areas.get(name)
            areas[name] = a if isinstance(a, dict) else dict(AREA_CONFIG[name]["default"])

        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.is_open():
            self.area_selector.hide()
        else:
            self.area_selector.show()
            self.area_selector.update_all(areas)
    # Debug Screenshots
    def take_debug_screenshot(self):
        """
        Capture every area in AREA_ORDER plus a full-screen shot, and save
        debug images as debug_<name>.png / debug_full.png.
        """
        full_img = self.capture_single_frame()
        if full_img is None:
            self.set_status("Full screen is empty")
            return

        try:
            cv2.imwrite(os.path.join(BASE_PATH, "debug_full.png"), full_img)
        except Exception as e:
            self.set_status(f"Error saving full screenshot: {e}")
            return

        saved = ["full"]
        try:
            for name in AREA_ORDER:
                left, top, right, bottom, _, _ = self.get_areas(name)
                # Clamp to image bounds
                h, w = full_img.shape[:2]
                top = max(0, min(top, h - 1))
                bottom = max(top + 1, min(bottom, h))
                left = max(0, min(left, w - 1))
                right = max(left + 1, min(right, w))
                crop = full_img[top:bottom, left:right]
                if crop.size == 0:
                    continue
                cv2.imwrite(os.path.join(BASE_PATH, f"debug_{name}.png"), crop)
                saved.append(name)
        except Exception as e:
            self.set_status(f"Error saving region screenshots: {e}")
            return

        self.set_status(f"Saved debug screenshots ({', '.join(saved)})")
    # Eyedropper
    def start_eyedropper(self, color_key=None):
        """Open the color picker overlay.

        color_key (optional): settings field name to write the result into
        (e.g. 'fish_color', 'shake_color'). The main UI is also notified via
        onColorPicked / setPickedColor and by updating matching input elements.
        """
        if not hasattr(self, "eyedropper") or self.eyedropper is None:
            self.eyedropper = Eyedropper(self)

        # Toggle off if already open
        if self.eyedropper.is_open():
            self.eyedropper.hide()
            return None

        self.eyedropper.show(color_key=color_key)
        return None

    def get_last_picked_color(self):
        """Return (and clear) the most recently picked eyedropper color.
        The main UI can poll this after start_eyedropper if it does not
        implement onColorPicked / setPickedColor callbacks."""
        if not hasattr(self, "eyedropper") or self.eyedropper is None:
            return None
        color = self.eyedropper.last_picked_color
        self.eyedropper.last_picked_color = None
        return color

    # Hotkeys
    def _get_hotkeys(self):
        try:
            start_key = self.normalize_key(str(self.vars["start_stop"]))
            areas_key = self.normalize_key(str(self.vars["change_areas"]))
            stop_key = self.normalize_key(str(self.vars["force_stop"]))
        except Exception as e:
            self.set_status(f"Get hotkeys failed: {e}")
            start_key = "f5"
            areas_key = "f6"
            stop_key = "f7"
        return start_key, areas_key, stop_key

    def normalize_key(self, key):
        try:
            return key.char.lower()  # Letter Keys

        except AttributeError:
            return str(key).replace("Key.", "").lower()

    def on_key_press(self, key):
        key = self.normalize_key(key)
        start_key, bar_areas_key, stop_key = self._get_hotkeys()
        automation_mode = self.vars["automation_mode"]
        if not automation_mode == "disabled":
            if key == start_key:
                window.hide()
                if self.macro_running == True:
                    return

                else:
                    # Set flag BEFORE starting threads to avoid race where
                    # the capture thread starts, sees macro_running=False, and exits immediately.
                    self.macro_running = True
                    # Save current settings to config before starting
                    self.save_config(self.current_config, self.vars)
                    if automation_mode == "fishing":
                        self.macro_thread = threading.Thread(target=self.start_fishing, daemon=True)
                    elif automation_mode == "appraisal":
                        self.macro_thread = threading.Thread(target=self.start_appraisal, daemon=True)
                    elif automation_mode == "enchant":
                        self.macro_thread = threading.Thread(target=self.start_enchantment, daemon=True)
                    elif automation_mode == "angler":
                        self.macro_thread = threading.Thread(target=self.start_angler, daemon=True)
                    self.macro_thread.start()
                    if sys.platform == "darwin":
                        self.capture_thread = threading.Thread(target=self.capture_loop_quartz, daemon=True)
                    else:
                        self.capture_thread = threading.Thread(target=self.capture_loop_mss, daemon=True)
                    self.capture_thread.start()
            elif key == bar_areas_key:
                self.open_area_selector()
            elif key == stop_key:
                window.show()
                self.stop_macro()
        else:
            self.save_config(self.current_config, self.vars, f"Pressed: {key}")
    def _string_to_key(self, key_string):
        key_string = key_string.strip().lower()
        # Try Special Keys
        if hasattr(Key, key_string):
            return getattr(Key, key_string)

        # Fallback To Character
        return key_string

    # Keyboard/Mouse Functions (Platform-specific)
    # Hold Mouse
    def hold_mouse(self, mouse=False):
        "Hold mouse. True for right click, False for left click."
        if self.macro_running == False:
            return

        if sys.platform == "win32":
            if mouse:
                windll.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            else:
                windll.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        elif sys.platform == "darwin":
            _mouse_event(button="right" if mouse else "left", press=True)
        else:
            # Linux - now uses the unified X11 implementation
            _mouse_event(button="right" if mouse else "left", press=True)
    # Release Mouse
    def release_mouse(self, mouse=False):
        "Release mouse. True for right click, False for left click."
        if self.macro_running == False:
            return

        if sys.platform == "win32":
            if mouse:
                windll.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            else:
                windll.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif sys.platform == "darwin":
            _mouse_event(button="right" if mouse else "left", press=False)
        else:
            # Linux - now uses the unified X11 implementation
            _mouse_event(button="right" if mouse else "left", press=False)
    # Click At
    def _click_at(self, x, y, click_count=1):
        if self.macro_running == False:
            return

        # Convert coordinates if needed (Retina scaling)
        if sys.platform == "darwin":
            scale = self._get_scale_factor()
            x = int(x / scale)
            y = int(y / scale)
        # Seperate branches for Windows and macOS mouse events
        if sys.platform == "win32":
            windll.SetCursorPos(x, y)
            windll.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            for i in range(click_count):
                windll.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                windll.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                if i < click_count - 1:
                    time.sleep(0.03)
        else:
            _move_mouse(x, y)
            _move_mouse(x + 2, y + 2)
            _move_mouse(x, y)
            for i in range(click_count):
                _mouse_event(button="left", press=True)   # mouse down
                _mouse_event(button="left", press=False)  # mouse up
                if i < click_count - 1:
                    time.sleep(0.03)
    # Keyboard
    def _send_key(self, key2, delay=0.05, click_type=0):
        """
        Send a keyboard event.
        delay: Delay between send and release
        click_type:
            0 = click (press + release)   [default]
            1 = hold (press only)
            2 = release (release only)
        """
        if self.macro_running == False:
            return

        key = str(key2)
        if sys.platform == "darwin":
            send_key(key2, delay=delay, click_type=click_type)
        else:
            # Convert special key names
            special_keys = {
                "enter": Key.enter,
                "return": Key.enter,
                "tab": Key.tab,
                "space": Key.space,
                "esc": Key.esc,
                "escape": Key.esc,
                "backspace": Key.backspace,
                "delete": Key.delete,
                "up": Key.up,
                "down": Key.down,
                "left": Key.left,
                "right": Key.right,
            }
            key = special_keys.get(key.lower(), key)
            try:
                if click_type == 0:
                    keyboard_controller.press(key)
                    time.sleep(delay)
                    keyboard_controller.release(key)
                elif click_type == 1:
                    keyboard_controller.press(key)
                elif click_type == 2:
                    keyboard_controller.release(key)
            except Exception as e:
                print("Error sending keys:", e)
    # Interruptible sleep
    def interruptible_sleep(self, duration):
        duration = max(0.01, duration)
        end_time = time.perf_counter() + duration
        while time.perf_counter() < end_time:
            if not self.macro_running:
                break  # Interrupted

            remaining = end_time - time.perf_counter()
            time.sleep(min(0.01, remaining))

    # Get values
    def get_areas(self, area_key):
        # Apply Scale Factor
        scale = self._get_scale_factor()
        area_data = self.bar_areas.get(area_key)
        if (isinstance(area_data, dict) and area_data.get("width", 0) > 0 and area_data.get("height", 0) > 0):
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
        left2   = int(left * scale * self.SCREEN_WIDTH)
        top2    = int(top * scale * self.SCREEN_HEIGHT)
        right2  = int(right * scale * self.SCREEN_WIDTH)
        bottom2 = int(bottom * scale * self.SCREEN_HEIGHT)
        width2  = int(width * scale * self.SCREEN_WIDTH)
        height2 = int(height * scale * self.SCREEN_HEIGHT)
        return left2, top2, right2, bottom2, width2, height2

    def _get_default_areas(self, area):
        """Return (left, top, right, bottom) in physical pixels using AREA_CONFIG defaults."""
        cfg = AREA_CONFIG.get(area)
        if cfg:
            d = cfg["default"]
            left   = int(self.SCREEN_WIDTH  * d["x"])
            top    = int(self.SCREEN_HEIGHT * d["y"])
            right  = int(self.SCREEN_WIDTH  * (d["x"] + d["width"]))
            bottom = int(self.SCREEN_HEIGHT * (d["y"] + d["height"]))
        else:
            left, top, right, bottom = 0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT
        return left, top, right, bottom

    def _get_var_number(self, key, default, cast=float):
        """Returns a key from the GUI with Exception handling"""
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

    # Detection
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

    def capture_single_frame(self):
        """
        Capture a single full-screen frame without touching self.macro_running.
        Used by debug screenshots, eyedropper freeze, and Discord screenshot logging.
        """
        if sys.platform == "darwin":
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectInfinite,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault
            )
            if image is None:
                return None
            return cgimage_to_srgb_numpy(image)
        else:
            scale = self._get_scale_factor()
            with MSS() as sct:
                monitor = {
                    "top": 0,
                    "left": 0,
                    "width": int(SCREEN_WIDTH * scale),
                    "height": int(SCREEN_HEIGHT * scale),
                }
                return np.asarray(sct.grab(monitor))[:, :, :3]

    def capture_loop_mss(self):
        """Continuous capture loop for the macro. Assumes self.macro_running is already True."""
        if not self.macro_running:
            return

        self.capture_id = 0
        scale = self._get_scale_factor()
        with MSS() as sct:
            monitor = {
                "top": 0,
                "left": 0,
                "width": int(SCREEN_WIDTH * scale),
                "height": int(SCREEN_HEIGHT * scale),
            }
            while self.macro_running:
                self.capture_frame = np.asarray(sct.grab(monitor))[:, :, :3]
                self.capture_id += 1
                time.sleep(self.scan_delay)

    def capture_loop_quartz(self):
        """Continuous capture loop for the macro (macOS). Assumes self.macro_running is already True."""
        if not self.macro_running:
            return

        self.capture_id = 0
        while self.macro_running:
            if sys.platform == "darwin":
                image = Quartz.CGWindowListCreateImage(
                    Quartz.CGRectInfinite,
                    Quartz.kCGWindowListOptionOnScreenOnly,
                    Quartz.kCGNullWindowID,
                    Quartz.kCGWindowImageDefault
                )
            else:
                image = None
            if image is None:
                continue

            self.capture_frame = cgimage_to_srgb_numpy(image)
            self.capture_id += 1
            time.sleep(self.scan_delay)

    def pixel_search(self, frame, hex, tolerance, mode=0):
        """
        Searches for the first or last pixel based on mode.
        Mode 0: First pixel; Mode 1: Last pixel
        """
        if frame is None or frame.size == 0:
            return None, None
        try:
            tolerance = int(tolerance)
        except:
            tolerance = 5
        tolerance = int(np.clip(tolerance, 0, 255))
        try:
            b, g, r = self._hex_to_bgr(hex)
        except:
            return None, None
        lower_bound = np.array([
            max(0, b - tolerance),
            max(0, g - tolerance),
            max(0, r - tolerance)
        ], dtype=np.uint8)
        upper_bound = np.array([
            min(255, b + tolerance),
            min(255, g + tolerance),
            min(255, r + tolerance)
        ], dtype=np.uint8)
        mask = cv2.inRange(frame, lower_bound, upper_bound)
        coords = np.argwhere(mask > 0)
        if coords.size > 0:
            if mode == 0:
                y, x = coords[0]
            elif mode == 1:
                y, x = coords[-1]  # Get last pixel
            else:
                raise RuntimeError("Invalid detection mode")
            
            return int(x), int(y)

        return None, None

    def find_color_cluster(self, frame, target_color_hex, tolerance=8, min_area=10):
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
        # required_fish_pixels
        if frame is None:
            return None

        # Color Mask (Vectorized Like Your Fast Version)
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int16)
        frame_int = frame.astype(np.int16)
        tol = int(np.clip(tolerance, 0, 255))

        mask = np.all(np.abs(frame_int - target_bgr) <= tol, axis=2).astype(np.uint8)

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
                dp=1, # Inverse ratio of accumulator resolution
                minDist=scaled_min_dist,  # Increased distance between circles to avoid overlapping detections
                param1=100,   # Higher Canny threshold for edge detection
                param2=100,   # Much higher accumulator threshold - only perfect circles
                minRadius=scaled_min_radius, # Larger minimum radius to ignore small false positives
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
                    # print(f"    🔍 Circle detected at local ({x}, {y}) with radius {r} (scale: {scale_factor:.3f})")
                    return int(x), int(y)

            # Only use strict HoughCircles detection - no backup methods to avoid false positives
            return None, None

        except Exception as e:
            self.set_status(f"    Error in circle detection: {e}")
            return None, None

    def _detect_lines_in_frame(self, frame, original_width=None):
        """
        Detect vertical lines in frame using Laplacian edge detection.
        Based on b.py line detection pipeline with brightness and density filtering.
        NLM denoising removed for 10x speedup (30 FPS -> 300 FPS).
        Frame is normalized to reference fish box dimensions (1035x43 at 2560x1440)
        for consistent detection across all resolutions. line coordinates are scaled
        back to match the original frame dimensions.
        Returns list of x-coordinates of detected vertical lines.
        Args:
            frame: BGR image from dxcam/mss
            original_width: Original frame width before normalization (for coordinate scaling back)
        """
        try:
            # Get minimum line density from settings (configurable via GUI)
            MIN_LINE_DENSITY = float(self.vars.get("fish_line_min_density", 0.1))
            BRIGHTNESS_THRESHOLD = 10  # Minimum brightness for edge pixels
            # Reference fish box dimensions at 1280x720 (lower detail for better edge detection)
            # At 1280x720: fish box is 762*(1280/2560) to 1797*(1280/2560) = 381 to 898 (width=517)
            # Height: 1215*(720/1440) to 1258*(720/1440) = 607 to 629 (height=22)
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
            # Step 2: Laplacian edge detection (NLM removed for 10x speedup)
            laplacian = cv2.Laplacian(grayscale, cv2.CV_8U)
            # Step 3: Filter vertical lines by brightness threshold and density
            height, width = laplacian.shape
            # Vectorized column density calculation (10x faster than Python loop)
            column_densities = np.sum(laplacian > BRIGHTNESS_THRESHOLD, axis=0) / height
            line_coords = np.where(column_densities >= MIN_LINE_DENSITY)[0].tolist()
            # Merge adjacent lines (consecutive x-coordinates) into single lines
            # Takes the middle position of each group of adjacent pixels
            # lines must be within 2 pixels to be considered part of the same group
            if line_coords:
                merged_lines = []
                group_start = line_coords[0]
                group_end = line_coords[0]
                for i in range(1, len(line_coords)):
                    if line_coords[i] <= group_end + 2:
                        # Within 2 pixels, extend current group
                        group_end = line_coords[i]
                    else:
                        # Gap > 2 pixels detected, save current group's middle position
                        middle = (group_start + group_end) // 2
                        merged_lines.append(middle)
                        # Start new group
                        group_start = line_coords[i]
                        group_end = line_coords[i]
                # Don't forget the last group
                middle = (group_start + group_end) // 2
                merged_lines.append(middle)
                line_coords = merged_lines
            # Scale line coordinates back to original frame dimensions
            if width_scale != 1.0:
                line_coords = [int(x * width_scale) for x in line_coords]
            # Sort coordinates for consistent processing
            line_coords.sort()
            return line_coords

        except Exception as e:
            # print(f"    Error in line detection: {e}")
            return []
        
    def get_colors_at_lines(self, frame, line_coords):
        """
        Get the color at each vertical line position as #RRGGBB hex strings.
        
        Args:
            frame: BGR image
            line_coords: List of x-coordinates from _detect_lines_in_frame
        
        Returns:
            List of '#RRGGBB' color strings for each line position, or None if out of bounds
        """
        colors = []

        for x in line_coords:
            # Make sure x is within image bounds
            if 0 <= x < frame.shape[1]:
                height = frame.shape[0]

                y_center = height // 2
                # BGR tuple → convert to RRGGBB hex string
                b, g, r = frame[y_center, x].tolist()
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
            else:
                colors.append(None)

        return colors

    def auto_crop_template(self, template, lower_white=200):
        """
        Crop padding from template using the same thresholding logic
        as your image_search function
        """
        # 1. Convert to grayscale
        if len(template.shape) == 3:
            gray_temp = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            gray_temp = template
        
        # 2. Threshold to find ONLY white/bright pixels (same as image_search)
        _, thresh_temp = cv2.threshold(gray_temp, lower_white, 255, cv2.THRESH_BINARY)
        
        # 3. Find all white pixels (the actual totem content)
        coords = cv2.findNonZero(thresh_temp)
        
        # If no white pixels found, return original
        if coords is None:
            return template
        
        # 4. Get bounding box of white pixels
        x, y, w, h = cv2.boundingRect(coords)
        
        # 5. Crop the ORIGINAL template (not the thresholded version)
        #    to preserve color/quality
        cropped = template[y:y+h, x:x+w]
        
        return cropped

    def image_search(self, screenshot, template, lower_white=200, threshold=0.8):
        # 1. Resize screenshot (assuming template is already resized)
        screenshot_cropped = self.auto_crop_template(screenshot)
        template_height, template_width, _ = template.shape # template_height
        screenshot_resized = cv2.resize(screenshot_cropped, (template_width, template_height))
        
        # 2. Convert screenshot & template to grayscale
        gray_screen = cv2.cvtColor(screenshot_resized, cv2.COLOR_BGR2GRAY)
        gray_temp = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        # 3. Threshold both images so ONLY white/bright pixels remain (255) and rest is black (0)
        _, thresh_screen = cv2.threshold(gray_screen, lower_white, 255, cv2.THRESH_BINARY)
        _, thresh_temp = cv2.threshold(gray_temp, lower_white, 255, cv2.THRESH_BINARY)
        
        # 4. Perform template matching on binary masks
        result = cv2.matchTemplate(thresh_screen, thresh_temp, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            return True, max_loc, max_val
        return False, None, max_val

    def _calculate_speed_and_predict(self, white_positions, timestamps):
        """
        Calculate white pixel movement speed using linear regression on recent
        positions for smooth, stable velocity estimation.
        Returns velocity /second (positive = moving down, negative = up),
        or None if insufficient data.
        """
        if len(white_positions) < 2:
            return None

        n = len(white_positions)
        y_values = [pos[1] for pos in white_positions]
        time_values = [t - timestamps[0] for t in timestamps]
        mean_t = sum(time_values) / n
        mean_y = sum(y_values) / n
        numerator = sum(t * y for t, y in zip(time_values, y_values)) - n * mean_t * mean_y
        denominator = sum(t * t for t in time_values) - n * mean_t * mean_t
        if abs(denominator) < 0.0001:
            return None

        return numerator / denominator

    # Utility Functions
    def test_logging(self):
        logging_mode = self.vars["logging_mode"].capitalize()
        self.send_logging(f"**{logging_mode} is working**", "Macro Stopped")

    def send_logging(self, text, loop_count, catch_rate=-1):
        logging_mode = self.vars["logging_mode"].lower()
        if logging_mode == "disabled":
            self.set_status("⚠ Logging is disabled.")
            return

        webhook_url = None
        if logging_mode != "file":
            webhook_url = self.vars["logging_url"].strip()
            if not webhook_url.startswith("https://discord.com/api/webhooks/"):
                self.set_status("Error: Invalid webhook URL.")
                return

        self.set_status("Sending log...")
        if logging_mode == "screenshot":
            thread = threading.Thread(
                target=self._discord_screenshot_worker,
                args=(webhook_url, f"{text}\n", loop_count, catch_rate),
                daemon=True
            )
        elif logging_mode == "file":
            thread = threading.Thread(
                target=self._debug_log_worker,
                args=(text, loop_count, catch_rate),
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._discord_text_worker,
                args=(webhook_url, f"{text}\n", loop_count, catch_rate),
                daemon=True
            )
        thread.start()
        thread.join()  # Wait for Discord/file log to finish before continuing

    def _discord_text_worker(self, webhook_url, message_prefix, loop_count, catch_rate):
        """Worker function to send text webhook."""
        logging_name = self.vars["logging_name"]
        try:
            if catch_rate == -1:
                catch_rate = "N/A"
            payload = {
                'content': f'{message_prefix}🎣 Cycle completed\n🔄 {loop_count}\nCatch rate: {catch_rate}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                'username': logging_name,
                'embeds': [{
                    'description': f'{loop_count}',
                    'color': 0x5865F2,
                    'timestamp': time.strftime("%Y-%m-%dT%H:%M:%S")
                }]
            }
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 200 or response.status_code == 204:
                self.set_status(f"Discord text sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord text failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending Discord text: {e}")

    def _discord_screenshot_worker(self, webhook_url, message_prefix, loop_count, catch_rate):
        logging_name = self.vars["logging_name"]
        try:
            screenshot = self.capture_single_frame()
            if screenshot is None:
                self.set_status("Error: failed to capture screenshot for Discord")
                return
            # Ensure BGR for imencode (mss already BGR; quartz conversion is BGR)
            if screenshot.shape[2] == 4:
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            _, buffer = cv2.imencode(".png", screenshot)
            img_byte_arr = io.BytesIO(buffer.tobytes())
            files = {'file': ('screenshot.png', img_byte_arr, 'image/png')}
            if catch_rate == -1:
                catch_rate = "N/A"
            payload = {
                'content': f'{message_prefix}🎣 **Cycle completed**\n🔄 {loop_count}\n🎯 Catch rate: {catch_rate}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                'username': logging_name
            }
            response = requests.post(webhook_url, data=payload, files=files, timeout=10)
            if response.status_code in (200, 204):
                self.set_status(f"Discord screenshot sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord screenshot failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending Discord screenshot: {e}")

    def _debug_log_worker(self, text, loop_count, catch_rate):
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
                "==========\n"
                f"🎣 {text}\n"
                f"🔄 {loop_count}\n"
                f"🕐 {timestamp}\n"
                f"🎯 Catch rate: {catch_rate}\n"
                "==========\n\n"
            )
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
            self.set_status(f"Debug log saved ({loop_count})")
        except Exception as e:
            self.set_status(f"Error writing debug log: {e}")

    def start_appraisal(self):
        time.sleep(0.05)
        self.stop_macro("Appraisal is not implemented yet")
    def start_enchantment(self):
        time.sleep(0.05)
        self.stop_macro("Enchantment is not implemented yet")

    def start_angler(self):
        time.sleep(0.05)
        self.stop_macro("Angler is not implemented yet")

    def start_fishing(self):
        # 1. Core Config & Modes
        scale = self._get_scale_factor()
        self.macro_running = True
        
        casting_mode = self.vars["casting_mode"].lower()
        shake_mode = self.vars["shake_mode"].lower()
        logging_mode = self.vars["logging_mode"].lower()
        click_after_minigame = self.vars["click_after_minigame"].lower()
        target_time = self.vars["target_time"].lower()
        
        # 2. Hotkey & Inventory Slots
        bag_slot = str(self.vars["bag_slot"])
        rod_slot = str(self.vars["rod_slot"])
        sundial_slot = str(self.vars["sundial_slot"])
        target_slot = str(self.vars["target_slot"])
        
        # 3. Delays & Timings
        select_rod_duration = float(self.vars["select_rod_duration"])
        delay_before_casting = float(self._get_var_number("delay_before_casting", 0.5, float))
        delay_after_casting = float(self._get_var_number("cast_delay", 1.0, float))
        sundial_delay = float(self.vars["sundial_delay"])
        totem_delay = float(self.vars["totem_delay"])
        
        # 4. Screen Regions & Coordinates
        shake_left, shake_top, shake_right, shake_bottom, shake_w, shake_h = self.get_areas("shake")
        fish_left, fish_top, fish_right, fish_bottom, _, fish_height = self.get_areas("fish")
        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self.get_areas("friend")
        totem_left, totem_top, totem_right, totem_bottom, _, _ = self.get_areas("totem")
        
        shake_x = shake_left + (shake_w // 2)
        shake_y = shake_top + (shake_h // 2)
        
        # 5. Features & Overlay Settings
        shake_failsafe = int(self.vars["shake_failsafe"])
        friend_color = self.vars["friends_color"]
        friend_tolerance = int(self.vars["friends_tolerance"])
        auto_refresh = self.vars["auto_refresh"]
        auto_totem = self.vars["auto_totem"]
        fish_overlay = self.vars["fish_overlay"]
        
        # 6. Optimized OpenCV Template Matching Setup
        sun = cv2.imread(os.path.join(IMAGES_PATH, "sun.png"))
        moon = cv2.imread(os.path.join(IMAGES_PATH, "moon.png"))
        sun_resized = self.auto_crop_template(sun)
        moon_resized = self.auto_crop_template(moon)
        
        # 7. Internal Tracking State
        self.scan_delay = 0.1
        self.current_cycle = 0
        current_time = None
        
        # Catch Metrics (0 = success, 1 = failed, 2 = N/A initial state)
        self.catch_success = 2
        self.catch_rate = 0.0
        successful_catches = 0
        if fish_overlay == "on":
            # Position the overlay just above or below the fish bar so it does
            # not cover the actual minigame.  show() expects (left, top, width,
            # height) in physical pixels — NOT right/bottom.
            fish_center = int((fish_top + fish_bottom) / 2)
            if fish_center > HALF_HEIGHT:
                fish_top_overlay = fish_top - fish_height - fish_height
            else:
                fish_top_overlay = fish_top + fish_height + fish_height
            overlay_width = fish_right - fish_left
            overlay_height = fish_height
            self.fish_overlay.show(
                fish_left,
                fish_top_overlay,
                overlay_width,
                overlay_height,
            )
        # Main Loop (With bug reports)
        try:
            while self.macro_running:
                self.set_status("Resetting statistics")
                self.capture_id = 0
                if auto_refresh == "on":
                    time.sleep(delay_before_casting)
                    self._send_key(bag_slot)
                    self.interruptible_sleep(select_rod_duration)
                    self._send_key(rod_slot)
                    self.interruptible_sleep(delay_after_casting / 2)
                self.set_status("Using Utilities")
                # Auto Totem
                if auto_totem == "on":
                    self.set_status("Auto Totem")
                    if not target_time == "disabled":
                        totem = self.capture_frame[totem_top:totem_bottom, totem_left:totem_right]
                        sun_found, _, sun_confidence = self.image_search(totem, sun_resized)
                        moon_found, _, moon_confidence = self.image_search(totem, moon_resized)
                        if sun_found == False and moon_found == False:
                            current_time = None
                            self.send_logging("**Sundial Failed**", f"Cycle #{self.current_cycle}", "N/A")
                        elif sun_found == True:
                            current_time = "Day"
                        elif moon_found == True:
                            current_time = "Night"
                        else:
                            if sun_confidence > moon_confidence:
                                current_time = "Day"
                            else:
                                current_time = "Night"
                        if not target_time == current_time:
                            self._send_key(sundial_slot)
                            self.interruptible_sleep(sundial_delay)
                            self.send_logging("**Sundial Success**", f"Cycle #{self.current_cycle}", "N/A")
                    self._send_key(target_slot)
                    self.interruptible_sleep(totem_delay)
                    self._send_key(rod_slot)
                    time.sleep(delay_after_casting / 4)
                self.current_cycle = self.current_cycle + 1
                # Cast
                self.set_status("Casting")
                time.sleep(delay_before_casting)
                if casting_mode == "perfect":
                    self._execute_cast_perfect()
                else:
                    self._execute_cast_normal()
                time.sleep(delay_after_casting)
                # Shake
                self.set_status("Shaking")
                self.scan_delay = float(self.vars["shake_scan_delay"])
                for attempts in range(shake_failsafe):
                    if self.capture_frame is None:
                        attempts = attempts - 1
                        continue
                    friend_img = self.capture_frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                    friend_x, friend_y = self.pixel_search(friend_img, friend_color, friend_tolerance)
                    if friend_x is None or friend_y is None:
                        break

                    if self.macro_running == False:
                        break
                    elif shake_mode == "navigation":
                        keyboard_controller.press(Key.enter)
                        time.sleep(0.01)
                        keyboard_controller.release(Key.enter)
                    else:
                        self._execute_shake_click(shake_mode)
                    time.sleep(self.scan_delay)
                # Minigame — sets self.catch_success = 0 at start; flips to 1 if fish ever leaves the bar
                self.set_status("Playing Bar Minigame")
                self._enter_minigame()
                if click_after_minigame == "on":
                    time.sleep(select_rod_duration)
                    self._click_at(shake_x, shake_y)
                # Update catch rate after the minigame finishes
                if self.catch_success == 0:
                    successful_catches += 1
                self.catch_rate = successful_catches / self.current_cycle
                catch_rate_percentage = int(self.catch_rate * 100)
                if logging_mode != "disabled":
                    self.send_logging("**Cycle Checkpoint**", f"Cycle #{self.current_cycle}", catch_rate_percentage)
            return
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            error_lines = full_error.splitlines()
            error_line = error_lines[1].split("line ")
            error_line = error_line[1].split(",")
            error_line = error_line[0]
            try:
                # Clean the error string so it doesn't break JavaScript execution syntax
                # We escape backslashes, single quotes, and newlines
                escaped_error = full_error.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                # Construct the self-invoking JS code block
                js_code = f"""
                (function() {{
                    let confirmed = confirm("An error at line {error_line} occured. Please copy the error and report the bug:\\n{e}\\nWould you like to copy the full crash log to your clipboard?");
                    if (confirmed) {{
                        navigator.clipboard.writeText('{escaped_error}')
                            .then(() => alert("Error log copied to clipboard!"))
                            .catch(err => alert("Failed to copy error: " + err));
                    }}
                }})();
                """
                # Evaluate using the same 'window' reference your set_status uses
                window.evaluate_js(js_code)
            except Exception:
                pass # Keep it safe just like set_status

            if IS_COMPILED == False:
                print(full_error)
            self.macro_running = False
            self.stop_macro(f"Error at line {error_line}: {e}")
    def _execute_cast_perfect(self):
        """
        Scans for green and white Y coordinates and releases left click when
        the top white Y reaches 95% of the area from green Y to bottom white Y.
        """
        # Hold Mouse
        self.hold_mouse(False)
        # Get Areas (Scale Factor and Ratio Calculations Applied Inside get_areas)
        shake_left, shake_top, shake_right, shake_bottom, _, shake_height = self.get_areas("shake")
        self._fish_overlay_cast_bounds = None
        # Config 
        white_color = self.vars["white_cast_color"]
        green_color = self.vars["green_cast_color"]
        white_tol = int(self._get_var_number("perfect_cast2_tolerance", 5, int))
        green_tol = int(self._get_var_number("perfect_cast_tolerance", 16, int))
        max_time = float(self._get_var_number("perfect_max_time", 5.5, float))
        self.scan_delay = float(self.vars["cast_scan_delay"])
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
            white_tol += 5
            green_tol += 5
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
        start_time = time.time()
        # Perfect Cast Loop
        while self.macro_running:
            region = self.capture_frame[shake_top:shake_bottom, shake_left:shake_right]
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

            cast_left = shake_left + green_left_x
            cast_top = shake_top + green_y
            cast_right = shake_left + green_right_x
            cast_bottom = shake_top + white_y_bottom

            self.fish_overlay.resize(cast_left, cast_top, cast_right, cast_bottom)
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

            time.sleep(self.scan_delay)
        # Cleanup
        self.release_mouse(False)
        self._fish_overlay_cast_bounds = None
        return

    def _execute_cast_normal(self):
        if self.macro_running == False:
            return
        cast_duration = float(self._get_var_number("cast_duration", 0.5, float))
        self.hold_mouse(False)
        self.interruptible_sleep(cast_duration)
        self.release_mouse(False)
        return

    def _execute_shake_click(self, shake_mode):
        scale = self._get_scale_factor()
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self.get_areas("shake")
        shake_color = self.vars["shake_color"]
        shake_tolerance = self.vars["shake_tolerance"]
        shake_img = self.capture_frame[shake_top:shake_bottom, shake_left:shake_right]
        if shake_mode == "pixel":
            shake_x, shake_y = self.pixel_search(shake_img, shake_color, shake_tolerance)
        else:
            shake_x, shake_y = self._find_circles(shake_img)
        try:
            shake_x_screen = int((shake_x / scale) + shake_left)
            shake_y_screen = int((shake_y / scale) + shake_top)
        except:
            shake_x_screen = None
            shake_y_screen = None
        self._click_at(shake_x_screen, shake_y_screen)
        return
    def _enter_minigame(self):
        # Helper Functions
        mouse_down = False
        def hold_mouse(mouse_state=False):
            "Hold mouse. False for left click, True for right click."
            nonlocal mouse_down
            if not mouse_down:
                self.hold_mouse(mouse_state)
                mouse_down = True
        def release_mouse(mouse_state=False):
            "Release mouse. False for left click, True for right click."
            nonlocal mouse_down
            if mouse_down:
                self.release_mouse(mouse_state)
                mouse_down = False
        # Areas
        shake_left, shake_top, shake_right, shake_bottom, _, shake_height = self.get_areas("shake")
        fish_left, fish_top, fish_right, fish_bottom, fish_width, fish_height = self.get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self.get_areas("friend")
        # Area Calculations
        note_height = fish_bottom - shake_top
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == "on":
            # Position the overlay just above or below the fish bar so it does
            # not cover the actual minigame.  show() expects (left, top, width,
            # height) in physical pixels — NOT right/bottom.
            fish_center = int((fish_top + fish_bottom) / 2)
            if fish_center > HALF_HEIGHT:
                fish_top_overlay = fish_top - fish_height - fish_height
            else:
                fish_top_overlay = fish_top + fish_height + fish_height
            overlay_width = fish_right - fish_left
            overlay_height = fish_height
            self.fish_overlay.show(
                fish_left,
                fish_top_overlay,
                overlay_width,
                overlay_height,
            )
        # Colors
        left_color = self.vars["left_color"]
        right_color = self.vars["right_color"]
        arrow_color = self.vars["arrow_color"]
        fish_color = self.vars["fish_color"]
        tracking_color = self.vars["tracking_color"]
        friends_color = self.vars["friends_color"]
        # Tolerance
        try:
            left_tolerance = int(self.vars["left_tolerance"])
            right_tolerance = int(self.vars["right_tolerance"])
            arrow_tolerance = int(self.vars["arrow_tolerance"])
            fish_tolerance = int(self.vars["fish_tolerance"])
            tracking_tolerance = int(self.vars["tracking_tolerance"])
            friends_tolerance = int(self.vars["friends_tolerance"])
        except:
            left_tolerance = 8
            right_tolerance = 8
            arrow_tolerance = 8
            fish_tolerance = 4
            tracking_tolerance = 5
            friends_tolerance = 5
        # Minigame Settings
        bag_slot = str(self.vars["bag_slot"])
        bag_spam = self.vars["bag_spam"]
        lock_cursor = self.vars["lock_cursor"]
        fishing_mode = self.vars["fishing_mode"].lower()
        fishing_profile = self.vars["fishing_profile"].lower()
        bar_ratio_from_side = float(self.vars["bar_ratio_from_side"])
        restart_delay = float(self.vars["restart_delay"])
        self.scan_delay = float(self.vars["minigame_scan_delay"])
        controller_mode = self.vars["controller_mode"].lower()
        kp = self._get_var_number("kp", 0.45)
        kd = self._get_var_number("kd", 0.35)
        stopping_distance = self._get_var_number("stopping_distance", 3)
        velocity_smoothing = self._get_var_number("velocity_smoothing", 1)
        # Utility Settings
        pinion_note_ratio = float(self.vars["pinion_note_ratio"])
        # Last values (failsafe)
        is_initial_run = True
        last_arrow_x = False
        bar_detected = False
        bag_spam_cycle = 0
        fish_size = 10
        note_x = 0
        note_y_ratio = 0
        line_coords = []
        bar_size = 0
        bar_center = 0
        error = 0
        last_capture_id = 0
        last_fish_x = 0
        last_left_x = 0
        last_right_x = 0
        last_bar_center = 0
        last_bar_size = 0
        last_error = 0
        color_check_bar_velocity = 0.0
        color_check_target_velocity = 0.0
        self.catch_success = 0
        last_time = time.perf_counter()
        # Loop
        while self.macro_running:
            # Get image from self.capture_frame
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue
            if self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue
            else:
                shake_img = self.capture_frame[shake_top:fish_bottom, fish_left:fish_right]
                fish_img = self.capture_frame[fish_top:fish_bottom, fish_left:fish_right]
                friend_img = self.capture_frame[friend_top:friend_bottom, friend_left:friend_right]
            # Friend detection
            friend_x, friend_y = self.pixel_search(friend_img, friends_color, friends_tolerance)
            if friend_x is not None and friend_y is not None:
                time.sleep(restart_delay)
                return

            # Fish detection
            fish_x, fish_y = self.pixel_search(fish_img, fish_color, fish_tolerance)
            if fish_x is not None:
                fish_detected = True
            else:
                fish_detected = False
            # Bar detection (Color or Line)
            if fishing_mode == "color":
                left_x, left_y = self.pixel_search(fish_img, left_color, left_tolerance)
                right_x, right_y = self.pixel_search(fish_img, right_color, right_tolerance, 1)
                if left_x == None:
                    left_x, left_y = self.pixel_search(fish_img, right_color, right_tolerance)
                if right_x == None:
                    right_x, right_y = self.pixel_search(fish_img, left_color, left_tolerance, 1)
                # print(f"Raw coordinates: {left_x}, {right_x}, {fish_x}")
                # Check if we should scan for arrows
                if left_x is not None and right_x is not None:
                    bar_detected = True
                    bar_center = int((left_x + right_x) / 2)
                    bar_size = right_x - left_x
                    # print(f"Detection Source: Bar | Left: {left_x} | Right: {right_x}")
                else:
                    # Try arrow
                    bar_detected = False
                    # Bars not found - scan for arrows
                    arrow_x, arrow_y = self.pixel_search(fish_img, arrow_color, arrow_tolerance)
                    if arrow_x is not None:
                        bar_detected = True
                        try:
                            arrow_direction = arrow_x - last_arrow_x
                        except:
                            arrow_direction = -1
                        # Detect bar based on arrow (use previous bar ends as reference)
                        if arrow_direction > 0:
                            left_x = last_left_x
                            right_x = arrow_x
                        else:
                            left_x = arrow_x
                            right_x = last_right_x
                        bar_center = int((left_x + right_x) / 2)
                        bar_size = right_x - left_x
                        try:
                            last_half_bar_size = int(last_bar_size / 2)
                        except:
                            last_half_bar_size = int(bar_size / 2)
                        if bar_size < last_half_bar_size:
                            bar_size = last_bar_size
                            right_x = left_x + bar_size
                            bar_center = int((left_x + right_x) / 2)
                        # print(f"Detection Source: Arrows | Left: {left_x} | Right: {right_x} | Arrow: {arrow_x}")
                    else:
                        # Use Cache
                        bar_detected = False
            else:
                line_coords = self._detect_lines_in_frame(fish_img)
                colors = self.get_colors_at_lines(fish_img, line_coords)
                if is_initial_run == True:
                    fish_x = np.mean(line_coords)
                    line_mean = int(round(len(line_coords) / 2))
                    left_x = line_coords[line_mean - 1]
                    right_x = line_coords[line_mean + 1]
            # Bag Spam & Lock Cursor
            bag_spam_cycle += 1
            if bag_spam_cycle == 5:
                bag_spam_cycle = 0
                if bag_spam == "on":
                    self._send_key(bag_slot)
                if lock_cursor == "on":
                    mouse_controller.position = (shake_x, shake_y)
            # Restore from Cache
            self.fish_overlay.clear()
            if bar_detected == False:
                left_x = last_left_x
                right_x = last_right_x
                bar_center = last_bar_center
                bar_size = last_bar_size
            if fish_detected == False:
                fish_x = last_fish_x
            # Note Detection
            if fishing_profile == "notes":
                note_x, note_y = self.pixel_search(shake_img, tracking_color, tracking_tolerance)
                if note_x is not None and note_y is not None:
                    note_y_ratio = float(note_y / note_height)
                    if note_y_ratio > pinion_note_ratio:
                        fish_x = note_x
                else:
                    note_y_ratio = 0.0
                # print("Note Ratio: ", note_y_ratio, " Pinion Ratio: ", pinion_note_ratio)
                # print("Fish: ", fish_x, " Note: ", note_x)
            else:
                # print("Note Tracking Disabled")
                note_y_ratio = 0.0
                if fishing_profile == "notes":
                    # Catch fails if the note ratio becomes 1 and the bar can't catch it; stays success only if note ratio is less than 0.9
                    if note_y_ratio > 0.9:
                        self.catch_success = 1
                else:
                    # Catch fails if the fish ever leaves the bar; stays success only if fish stays inside the whole time
                    if left_x is not None and right_x is not None and fish_x is not None:
                        if not (left_x <= fish_x <= right_x):
                            self.catch_success = 1
            # Edge Boundary
            if bar_size is not None:
                boundary = bar_size * bar_ratio_from_side
                left_boundary = boundary
                right_boundary = fish_right - boundary - fish_left
            else:
                left_boundary = None
                right_boundary = fish_width
            # print("Boundary: ", left_boundary, right_boundary, " Fish: ", fish_x)
            # print("Last Cache: ", bar_center - last_bar_center)
            # Fish Overlay
            if fish_overlay == "on":
                if fishing_mode == "color":
                    self.fish_overlay.draw_box(
                        bar_center=bar_center, box_size=bar_size,
                        color="green", canvas_offset=0,
                        show_bar_center=True
                    )
                    if left_boundary is not None:
                        self.fish_overlay.draw_box(
                            bar_center=left_boundary, box_size=15,
                            color="lightblue", canvas_offset=0
                        )
                    if right_boundary is not None:
                        self.fish_overlay.draw_box(
                            bar_center=right_boundary, box_size=15,
                            color="lightblue", canvas_offset=0
                        )
                    if fish_x is not None:
                        self.fish_overlay.draw_box(
                            bar_center=fish_x, box_size=fish_size,
                            color="red", canvas_offset=0
                        )
                else:
                    self.fish_overlay.draw_box(
                        bar_center=bar_center, box_size=bar_size,
                        color="cyan", canvas_offset=0,
                        show_bar_center=True, bar_y1=0.2, bar_y2=0.8
                    )
                    for pos in range(len(line_coords)):
                        self.fish_overlay.draw_box(bar_center=line_coords[pos], box_size=0, color=colors[pos], canvas_offset=0)
            # Controller Mode Selection
            current_controller_mode = controller_mode
            if left_x is not None and right_x is not None and fish_x is not None:
                if (left_x <= fish_x <= right_x) and controller_mode == "predictive":
                    current_controller_mode = "normal"
            # PD controller
            current_time = time.perf_counter()
            time_delta = current_time - last_time
            last_time = current_time
            if fish_x is not None:
                error = fish_x - bar_center
            else:
                error = 0
                fish_x = 0
            if (fish_x < left_boundary):
                control_signal = -30
            elif (fish_x > right_boundary):
                control_signal = 30
            else:
                if current_controller_mode == "normal":
                    # Normal: Traditional PD controller
                    if is_initial_run == True:
                        control_signal = 0
                        last_error = error
                    else:
                        if time_delta < 0.001:
                            time_delta = 0.001
                        p_term = error * kp
                        d_term = ((error - last_error) / time_delta) * kd
                        control_signal = p_term + d_term
                        last_error = error
                elif current_controller_mode == "steady":
                    # Steady: Asymmetric PD controller with asymmetric damping
                    if is_initial_run == True:
                        control_signal = 0
                        last_error = error
                    else:
                        if time_delta < 0.001:
                            time_delta = 0.001
                        p_term = error * kp
                        bar_velocity = bar_center - last_bar_center
                        error_magnitude_decreasing = abs(error) < abs(last_error)
                        bar_moving_toward_target = (
                            (bar_velocity > 0 and error > 0)
                            or (bar_velocity < 0 and error < 0)
                        )
                        if note_y_ratio > pinion_note_ratio:
                            steady_kd_multiplier = 0.5
                        elif error_magnitude_decreasing and bar_moving_toward_target:
                            steady_kd_multiplier = 5.0
                        else:
                            steady_kd_multiplier = 0.2
                        d_term = ((error - last_error) / time_delta) * kd * steady_kd_multiplier
                        control_signal = p_term + d_term
                        last_error = error
                elif current_controller_mode == "predictive":
                    # Predictive: Predictive controller with linear stopping distance and counter-thrust
                    # Init Failsafe
                    if last_time == None:
                        last_time = time.perf_counter()
                    if color_check_bar_velocity is None:
                        color_check_bar_velocity = 0.0
                    if color_check_target_velocity is None:
                        color_check_target_velocity = 0.0
                    # Missing Data Failsafe
                    if fish_x is None or bar_center is None:
                        control_signal = -30
                    # Calculate Velocities
                    current_time = time.perf_counter()
                    if last_bar_center is not None and last_fish_x is not None:
                        time_delta = current_time - last_time
                        if time_delta > 0:
                            raw_bar_velocity = (bar_center - last_bar_center) / time_delta
                            raw_target_velocity = (fish_x - last_fish_x) / time_delta
                            color_check_bar_velocity = (velocity_smoothing * raw_bar_velocity + 
                                                        (1 - velocity_smoothing) * color_check_bar_velocity)
                            color_check_target_velocity = (velocity_smoothing * raw_target_velocity + 
                                                            (1 - velocity_smoothing) * color_check_target_velocity)
                    # Update Previous Values
                    last_time = current_time
                    # Calculate error and relative velocity FIRST
                    try:
                        relative_velocity = float(color_check_bar_velocity - color_check_target_velocity)
                    except:
                        color_check_bar_velocity = 0
                        color_check_target_velocity = 0
                        control_signal = -30
                    # Nan Guard AFTER variables are defined
                    if not np.isfinite(relative_velocity):
                        control_signal = -30
                    # Calculate stopping distance based on relative velocity
                    stopping_distance = abs(relative_velocity) * stopping_distance
                    # On-Bar: Use Stopping-Distance / Counter-Thrust Logic
                    if error < -stopping_distance:
                        # Bar Is Left Of Fish Beyond Stopping Distance → Hold To Move Right
                        control_signal = 30
                    elif error > stopping_distance:
                        # Bar Is Right Of Fish Beyond Stopping Distance → Release To Move Left
                        control_signal = -30
                    else:
                        # Within Stopping Distance — Counter-Thrust Based On Relative Velocity
                        if relative_velocity > 0:
                            # Bar Moving Right Relative To Fish → Release (Apply Left Thrust)
                            control_signal = -30
                        else:
                            # Bar Moving Left Relative To Fish → Hold (Apply Right Thrust)
                            control_signal = 30
            # Mouse state
            # print(f"Control Signal: {control_signal}")
            if control_signal > 0:
                hold_mouse()
            else:
                release_mouse()
            # Update Cache
            if bar_detected == True:
                last_left_x = left_x
                last_right_x = right_x
                last_bar_center = bar_center
                last_bar_size = bar_size
            if fish_detected == True:
                if not fish_x == note_x:
                    last_fish_x = fish_x
            try:
                last_arrow_x = arrow_x
            except:
                pass
            # Cleanup
            is_initial_run = False
            last_capture_id = self.capture_id
            time.sleep(self.scan_delay)
        return

    def stop_macro(self, text="Macro Stopped"):
        self.macro_running = False
        self.fish_overlay.hide()

        if (
            self.macro_thread
            and self.macro_thread.is_alive()
            and self.macro_thread is not threading.current_thread()
        ):
            self.macro_thread.join()

        if (
            self.capture_thread
            and self.capture_thread.is_alive()
            and self.capture_thread is not threading.current_thread()
        ):
            self.capture_thread.join()

        if text:
            self.set_status(text)

        try:
            window.show()
        except Exception:
            pass
try:
    with open(os.path.join(UI_PATH, "index.html"), "r", encoding="utf-8-sig") as file:
        lines = file.readline().strip()
    with open(os.path.join(UI_PATH, "style.css"), "r", encoding="utf-8-sig") as file:
        lines = file.readline().strip()
    with open(os.path.join(UI_PATH, "app.js"), "r", encoding="utf-8-sig") as file:
        lines = file.readline().strip()
except FileNotFoundError:
    open_folder = messagebox.askyesno("Missing Files", """Your installation is missing the configs, images and UI folder.
    Please report this bug in the Discord Server.\n
    Do you want to open the configs folder?""")
    if open_folder == True:
        open_base_folder()
    sys.exit(0)
api = Api()
window = webview.create_window(
    f"PyWare Fishing V{APP_VERSION}",
    os.path.join(UI_PATH, "index.html"),
    js_api=api,
    width=1000,
    height=700
)
webview.start(gui="edgechromium")
