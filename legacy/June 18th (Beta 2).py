# GUI
import webview
import json
import os
import re
import time
import sys
import webbrowser
# Error handling
import customtkinter as ctk
# OCR
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
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
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
elif sys.platform == "darwin":
    import Quartz
    from AppKit import NSScreen
elif sys.platform == "linux":
    from Xlib import X, XK, display as Xdisplay
    from Xlib.ext import xtest
import math
import subprocess
# Logging
import requests
import io
# Initialize Controllers
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
macro_running = False
macro_thread = None
# Ctypes & Quartz for Mouse Clicks and Special Window Properties
if sys.platform == "win32":
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    # Ctypes windows
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    LWA_ALPHA = 0x00000002
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD]
    # Set DPI scaling
    try:
        windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    # Windows API related functions
    def get_scale_factor():
        return 1
    def _get_hwnd(window):
        """Return a Windows HWND int from a pywebview window/native object."""
        native = getattr(window, "native", window)
        candidates = (
            native,
            getattr(native, "Handle", None),  # WinForms BrowserForm -> System.IntPtr
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
    def make_window_translucent(window, transparency):
        """Make a pywebview Windows window translucent once its HWND exists."""
        hwnd = None
        for _ in range(10):
            hwnd = _get_hwnd(window)
            if hwnd:
                break
            time.sleep(0.05)
        if not hwnd:
            return False
        current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_LAYERED)
        # Range is 0 (fully transparent) to 255 (fully opaque).
        opacity_alpha = int(255 * transparency)
        return bool(user32.SetLayeredWindowAttributes(hwnd, 0, opacity_alpha, LWA_ALPHA))
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
            _scale_cache = float(NSScreen.mainScreen().backingScaleFactor())
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
            "left":   (Quartz.kCGMouseButtonLeft,   Quartz.kCGEventLeftMouseDown,   Quartz.kCGEventLeftMouseUp),
            1:        (Quartz.kCGMouseButtonLeft,   Quartz.kCGEventLeftMouseDown,   Quartz.kCGEventLeftMouseUp),
            "right":  (Quartz.kCGMouseButtonRight,  Quartz.kCGEventRightMouseDown,  Quartz.kCGEventRightMouseUp),
            3:        (Quartz.kCGMouseButtonRight,  Quartz.kCGEventRightMouseDown,  Quartz.kCGEventRightMouseUp),
            "middle": (Quartz.kCGMouseButtonCenter, Quartz.kCGEventOtherMouseDown,  Quartz.kCGEventOtherMouseUp),
            2:        (Quartz.kCGMouseButtonCenter, Quartz.kCGEventOtherMouseDown,  Quartz.kCGEventOtherMouseUp),
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
    def make_window_translucent(window, transparency):
        pass
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
    def make_window_translucent(window, transparency):
        pass
def get_macos_menu_offset():
    if sys.platform != "darwin":
        return 0
    try:
        import AppKit
        screen = AppKit.NSScreen.mainScreen()
        full_frame = screen.frame()
        visible_frame = screen.visibleFrame()
        return int(full_frame.size.height - visible_frame.size.height)
    except Exception:
        return 0
def get_base_path():
    """Unified base directory for app data."""
    if getattr(sys, 'frozen', False):
        compiled = True
        # Compiled App → Use User Directory
        if sys.platform == "darwin":
            return os.path.join(
                os.path.expanduser("~"),
                "Library", "Application Support",
                "PyWareFishingV4"
            ), compiled
        elif sys.platform == "win32":
            return os.path.join(
                os.path.expanduser("~"),
                "AppData", "Roaming",
                "PyWareFishingV4"
            ), compiled
        else:
            return os.path.join(os.path.expanduser("~"), "PyWareFishingV4"), compiled
    compiled = False
    # Dev Mode → Project Directory
    return os.path.dirname(os.path.abspath(__file__)), compiled
BASE_PATH, IS_COMPILED = get_base_path()
# Get correct legacy folder
script_path = os.path.abspath(__file__)
folder_path = os.path.dirname(script_path)
filename_with_ext = os.path.basename(script_path)
filename_without_ext = os.path.splitext(filename_with_ext)[0]
if "legacy" in folder_path.lower() and not str(IS_COMPILED) == "True":
    UI_PATH = os.path.join(BASE_PATH, filename_without_ext, "ui")
else:
    UI_PATH = os.path.join(BASE_PATH, "ui")
# Configs folder
os.makedirs(BASE_PATH, exist_ok=True)
CONFIGS_FOLDER = os.path.join(BASE_PATH, "configs")
LAST_CONFIG_FILE = os.path.join(BASE_PATH, "last_config.json")
# Open base folder
def open_base_folder():
    folder = BASE_PATH
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":  # Macos
        subprocess.run(["open", folder])
    else:  # Linux
        subprocess.run(["xdg-open", folder])
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
with mss.mss() as _sct:
    if len(_sct.monitors) > 1:
        _m = _sct.monitors[1]   # Primary monitor
    else:
        _m = _sct.monitors[0]   # Fallback: only one entry exists
    SCREEN_WIDTH  = _m["width"]
    SCREEN_HEIGHT = _m["height"]
    SCREEN_LEFT   = _m["left"]
    SCREEN_TOP    = _m["top"]
# On Windows, mss reports logical (DPI-scaled) pixel dimensions.
# pywebview's create_window width/height also use logical pixels, so they match.
# However we must account for the monitor's top-left offset (multi-monitor setups
# where the primary isn't at 0,0) when positioning overlay windows.
if sys.platform == "win32":
    try:
        import ctypes as _ctypes
        _ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        pass
CONFIG_DIR = CONFIGS_FOLDER
IMAGES_PATH = os.path.join(BASE_PATH, "images")
DEBUG_DIR = BASE_PATH
CONFIG_PATH = LAST_CONFIG_FILE
APP_VERSION = "4.21"
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
    HTML_FILE = os.path.join(UI_PATH, "area_selector.html")
    def __init__(self, parent, shake_area, fish_area, friend_area, totem_area, callback):
        self.parent   = parent
        self.callback = callback
        self._open    = True
        # Actual window origin reported by JS after the window is placed.
        # Defaults to SCREEN_LEFT/TOP; overwritten by window_ready() once JS fires.
        # This corrects for macOS menu-bar push-down and any other OS chrome offset.
        self._win_origin_x = SCREEN_LEFT
        self._win_origin_y = SCREEN_TOP
        # Store areas as RATIOS (0-1 range) consistently
        self._areas = {
            "shake":  self._to_ratios(shake_area),
            "fish":   self._to_ratios(fish_area),
            "friend": self._to_ratios(friend_area),
            "totem":  self._to_ratios(totem_area),
        }
        # Create a second, frameless, transparent, fullscreen pywebview window.
        # js_api=self exposes get_areas / on_mouse_move / save_areas to JS.
        # NOTE: x/y must be the primary monitor's actual top-left offset (SCREEN_LEFT/TOP).
        # On single-monitor setups this is always 0,0.  On multi-monitor setups where the
        # primary display isn't the leftmost one, SCREEN_LEFT/TOP will be non-zero and the
        # window must be placed there to sit over the correct screen.
        if sys.platform == "win32":
            self._win = webview.create_window( "Area Selector", self.HTML_FILE, js_api=self, 
                                            # Window Style 
                                            transparent=False, frameless=True, easy_drag=False, 
                                            # Keep Above Everything 
                                            on_top=True, 
                                            # Prevent Resizing / Moving 
                                            resizable=False, 
                                            # Fullscreen Size — matches the primary monitor exactly 
                                            width=SCREEN_WIDTH, height=SCREEN_HEIGHT, 
                                            # Position at the primary monitor's actual origin (handles non-zero offsets) 
                                            x=SCREEN_LEFT, y=SCREEN_TOP, background_color="#000000")
        else:
            self._win = webview.create_window( "Area Selector", self.HTML_FILE, js_api=self, 
                                            # Window Style 
                                            transparent=True, frameless=True, easy_drag=False, 
                                            # Keep Above Everything 
                                            on_top=True, 
                                            # Prevent Resizing / Moving 
                                            resizable=False, 
                                            # Fullscreen Size — matches the primary monitor exactly 
                                            width=SCREEN_WIDTH, height=SCREEN_HEIGHT, 
                                            # Position at the primary monitor's actual origin (handles non-zero offsets) 
                                            x=SCREEN_LEFT, y=SCREEN_TOP, background_color="#000000")
        self._win.events.closed += self._on_closed
        time.sleep(0.05)
        make_window_translucent(self._win, 0.35)
    def _to_ratios(self, area):
        """Convert any area dict to ratios (0-1 range)"""
        return {
            "x": area.get("x", 0),
            "y": area.get("y", 0),
            "width": area.get("width", area.get("w", 0)),
            "height": area.get("height", area.get("h", 0)),
        }
    def _ratios_to_pixels(self, ratios, add_offset=True):
        """Convert ratio dict to pixel coordinates relative to canvas or screen"""
        x_pixels = ratios["x"] * SCREEN_WIDTH
        y_pixels = ratios["y"] * SCREEN_HEIGHT
        w_pixels = ratios["width"] * SCREEN_WIDTH
        h_pixels = ratios["height"] * SCREEN_HEIGHT
        if add_offset:
            x_pixels += self._win_origin_x
            y_pixels += self._win_origin_y
        return {
            "x": x_pixels,
            "y": y_pixels,
            "width": w_pixels,
            "height": h_pixels,
        }
    def _pixels_to_ratios(self, pixels, subtract_offset=True):
        """Convert pixel dict to ratios (0-1 range)"""
        x_pixels = pixels.get("x", 0)
        y_pixels = pixels.get("y", 0)
        if subtract_offset:
            x_pixels -= self._win_origin_x
            y_pixels -= self._win_origin_y
        return {
            "x": x_pixels / SCREEN_WIDTH,
            "y": y_pixels / SCREEN_HEIGHT,
            "width": pixels.get("w", pixels.get("width", 0)) / SCREEN_WIDTH,
            "height": pixels.get("h", pixels.get("height", 0)) / SCREEN_HEIGHT,
        }
    # ── JS API methods (called from area_selector.html) ──
    def on_hover_ratio(self, area_name, x_ratio, y_ratio):
        self.parent.set_status(
            f"{area_name.upper()} → X Ratio: {x_ratio:.3f} | Y Ratio: {y_ratio:.3f}"
        )
    def window_ready(self, win_x, win_y):
        """
        Called by JS immediately after pywebviewready fires, passing
        window.screenX / window.screenY so Python knows the actual pixel
        offset of the overlay window's top-left corner.
        On macOS, a frameless pywebview window placed at y=0 is still pushed
        below the menu bar by the window server (~25-28 px).  Without this
        correction every saved y-coordinate is shifted down by the menu bar
        height, causing a visible bottom-offset when the saved box is used to
        crop the screen capture.
        """
        if sys.platform == "darwin":
            self._win_origin_x = 0
            self._win_origin_y = 0
        else:
            self._win_origin_x = int(win_x)
            self._win_origin_y = int(win_y)
    def get_areas(self):
        """
        Called by JS on startup to get initial box positions.
        Returns pixel coordinates relative to the canvas (window-relative, not screen-absolute).
        """
        out = {}
        menu_offset = get_macos_menu_offset()
        for name, ratios in self._areas.items():
            # Convert ratios to canvas-relative pixels (no screen offset added)
            pixels = self._ratios_to_pixels(ratios, add_offset=False)
            out[name] = {
                "x": pixels["x"],
                "y": pixels["y"] - menu_offset,  # macOS adjustment
                "width": pixels["width"],
                "height": pixels["height"],
            }
        return out
    def on_mouse_move(self, mouse_x, mouse_y, current_boxes):
        """
        Called by JS on every mousemove so the main window status bar
        can show live position ratios.
        mouse_x / mouse_y are CSS-pixel coordinates relative to the overlay
        window's top-left corner (i.e. relative to SCREEN_LEFT, SCREEN_TOP).
        """
        if not self._open:
            return
        # Update cached areas with latest from JS (JS sends canvas-relative pixels)
        menu_offset = get_macos_menu_offset()
        for name in ("shake", "fish", "friend", "totem"):
            b = current_boxes.get(name, {})
            if b:
                # Canvas y has menu_offset subtracted (same as get_areas); add it back
                # so the stored ratio always reflects true screen-relative position.
                adjusted = dict(b)
                adjusted["y"] = b.get("y", 0) + menu_offset
                self._areas[name] = self._pixels_to_ratios(adjusted, subtract_offset=False)
        # Convert mouse canvas-relative to screen-absolute for hit testing
        abs_x = mouse_x + self._win_origin_x
        abs_y = mouse_y + self._win_origin_y
        for name in ("shake", "fish", "friend", "totem"):
            ratios = self._areas.get(name, {})
            if not ratios:
                continue
            # Hit test using ratios (multiply by screen dimensions)
            bx = ratios["x"] * SCREEN_WIDTH
            by = ratios["y"] * SCREEN_HEIGHT
            bw = (ratios["width"] * SCREEN_WIDTH) or 1
            bh = (ratios["height"] * SCREEN_HEIGHT) or 1
            if bx <= abs_x <= bx + bw and by <= abs_y <= by + bh:
                xr = round((abs_x - bx) / bw, 2)
                yr = round((abs_y - by) / bh, 2)
                self.parent.set_status(f"Coords: {xr}, {yr}")
                return
        self.parent.set_status("Area selector opened (press key again to close)")
    def save_areas(self, areas):
        """
        Called by JS when the user presses Escape/F6 to confirm and close.
        JS sends canvas-relative {x,y,w,h} pixels; we convert to ratios and fire callback.
        """
        if not self._open:
            return
        self._open = False
        menu_offset = get_macos_menu_offset()
        out = {}
        for name, b in areas.items():
            # Canvas pixels from JS have menu_offset already subtracted (get_areas
            # sends y = ratio*H - menu_offset), so add it back before converting to
            # ratios, otherwise y drifts up by menu_offset/SCREEN_HEIGHT each cycle.
            adjusted = dict(b)
            adjusted["y"] = b.get("y", 0) + menu_offset
            out[name] = self._pixels_to_ratios(adjusted, subtract_offset=False)
        self.callback(out["shake"], out["fish"], out["friend"], out["totem"])
        if hasattr(self.parent, "_keys_held"):
            self.parent._keys_held.discard("f6")
        self.parent.set_status("Area selector closed")
        try:
            self._win.destroy()
        except Exception:
            pass
    # ── Internal 
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
            # Build canvas-relative pixels that mirror what JS sends via save_areas:
            # get_areas sends y = ratio*H - menu_offset, so we must do the same here.
            menu_offset = get_macos_menu_offset()
            canvas_pixels = {}
            for name, ratios in self._areas.items():
                pixels = self._ratios_to_pixels(ratios, add_offset=False)
                canvas_pixels[name] = {
                    "x": pixels["x"],
                    "y": pixels["y"] - menu_offset,
                    "w": pixels["width"],
                    "h": pixels["height"],
                }
            self.save_areas(canvas_pixels)
# Eyedropper class
class Eyedropper:
    """
    Fullscreen transparent overlay for color picking using pywebview.
    The HTML canvas handles UI rendering and mouse interaction.
    Python handles pixel capture and color conversion.
    """
    HTML_FILE = os.path.join(UI_PATH, "eyedropper.html")
    def __init__(self, parent):
        # Initialization
        self.parent = parent
        self._open = True
        self.last_picked_color = None
        self._scale = self.parent._get_scale_factor()
        self._win_origin_x = SCREEN_LEFT
        self._win_origin_y = SCREEN_TOP
        # Capture desktop before overlay appears
        self._screen_capture = self.parent._grab_screen_full()
        # Create fullscreen transparent pywebview window
        self._win = webview.create_window(
            "Eyedropper",
            self.HTML_FILE,
            js_api=self,
            transparent=True,
            frameless=True,
            easy_drag=False,
            on_top=True,
            resizable=False,
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,
            x=0,
            y=0,
            background_color="#000000",
        )
        self._win.events.closed += self._on_closed
        time.sleep(0.05)
        make_window_translucent(self._win, 0.05)
    # ── JS API methods (called from eyedropper.html) ──
    def get_pixel_at(self, x, y):
        """Gets the pixel from the full-screen capture with screen freeze (memory-based)"""
        if not self._open:
            return "#000000"
        frame = self._screen_capture
        if frame is None:
            return "#000000"
        menu_offset = get_macos_menu_offset()
        screen_x = x + self._win_origin_x
        screen_y = y + self._win_origin_y + menu_offset
        x = int(screen_x * self._scale)
        y = int(screen_y * self._scale)
        if (
            x < 0 or
            y < 0 or
            y >= frame.shape[0] or
            x >= frame.shape[1]
        ):
            return "#000000"
        b = int(frame[y, x, 0])
        g = int(frame[y, x, 1])
        r = int(frame[y, x, 2])
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        return hex_color
    def window_ready(self, win_x, win_y):
        if sys.platform == "darwin":
            self._win_origin_x = 0
            self._win_origin_y = 0
        else:
            self._win_origin_x = int(win_x)
            self._win_origin_y = int(win_y)
    def pick_color(self, hex_color):
        """
        Called by JS when user clicks to pick a color.
        Stores the color and closes the window.
        """
        if not self._open:
            return
        self.last_picked_color = hex_color
        self.parent.set_status(f"Picked color: {hex_color}")
        self._open = False
        try:
            self._win.destroy()
        except Exception:
            pass
    def close_eyedropper(self):
        """
        Called by JS when user presses Escape.
        Closes the window without picking.
        """
        if not self._open:
            return
        self._open = False
        self.parent.set_status("Eyedropper cancelled")
        try:
            self._win.destroy()
        except Exception:
            pass
    # ── Internal 
    def _on_closed(self):
        """Fires when the webview window is destroyed."""
        if self._open:
            self._open = False
            self.parent.set_status("Eyedropper closed")
    def is_open(self):
        return self._open
    def close(self):
        """Force-close from Python."""
        if self._open:
            self.close_eyedropper()
class FishOverlay:
    """Fishing minigame overlay visualization implemented with pywebview."""
    HTML_FILE = os.path.join(UI_PATH, "fish_overlay.html")
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self._win = None
        self._open = False
        self._visible = False
        self.scale_factor = get_scale_factor()
        self.width  = int(800)
        self.height = int(60)
        self.x = int(SCREEN_WIDTH * 0.5 - self.width / 2)
        self.y = int(SCREEN_HEIGHT * 0.65)
    def init_window(self):
        if self._win and self._open:
            return
        self._win = webview.create_window(
            "PyWare Fish Overlay",
            self.HTML_FILE,
            transparent=True,
            frameless=True,
            easy_drag=False,
            on_top=True,
            resizable=False,
            width=self.width,
            height=self.height,
            x=self.x,
            y=self.y,
            background_color="#000000",
        )
        self._open = True
        self._visible = True
        self._win.events.closed += self._on_closed
    def _on_closed(self):
        self._open = False
        self._visible = False
        self._win = None
    def _eval(self, script):
        if not self._win or not self._open:
            return
        try:
            self._win.evaluate_js(script)
        except Exception:
            pass
    def set_layout(self, x, y, width, height):
        scale = get_scale_factor()
        x /= scale
        y /= scale
        width /= scale
        height /= scale
        width = max(1, int(width))
        height = max(1, int(height))
        x = max( 0, min( int(x), max(0, int(self.parent_app.SCREEN_WIDTH) - width) ) )
        y = max( 0, min( int(y), max(0, int(self.parent_app.SCREEN_HEIGHT) - height) ) )
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.init_window()
        if not self._win:
            return
        try:
            self._win.resize(width, height)
            self._win.move(x, y)
        except Exception:
            pass
    def show(self):
        self.init_window()
        if self._win:
            try:
                self._win.show()
            except Exception:
                pass
            # Re-assert on_top z-order after un-hiding without stealing keyboard focus.
            # hide()/show() on edgechromium does not guarantee the window is re-stacked
            # above the game; nudging move() forces the compositor to re-evaluate z-order.
            try:
                self._win.move(self.x, self.y)
            except Exception:
                pass
        self._visible = True
    def hide(self):
        if self._win and self._open:
            try:
                self._win.hide()
            except Exception:
                pass
        self._visible = False
    def clear(self):
        self._eval("window.fishOverlay && window.fishOverlay.clear()")
    def draw(self, bar_center, box_size, color, canvas_offset,
            show_bar_center=False, bar_y1=0.15, bar_y2=0.85):
        if bar_center is None:
            return
        scale = get_scale_factor()
        self.init_window()
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
        self._eval(
            "window.fishOverlay && window.fishOverlay.draw("
            + json.dumps(shape)
            + ")"
        )

    def draw_circle(self, lane, ratio, color):
        """
        Draw a circle indicator for tranquility mode lanes.
        lane: 0-3 (column)
        ratio: vertical position 0.0 (top) .. 1.0 (bottom) within the overlay
        color: hex string
        The actual rendering is handled in fish_overlay.html JS (window.fishOverlay.drawCircle).
        This is a safe no-op if the JS side does not implement it yet.
        """
        if not self._win or not self._open:
            return
        try:
            scale = get_scale_factor()
            shape = {
                "lane": int(lane),
                "ratio": max(0.0, min(1.0, float(ratio))),
                "color": str(color),
            }
            self._eval(
                "window.fishOverlay && window.fishOverlay.drawCircle && window.fishOverlay.drawCircle("
                + json.dumps(shape)
                + ")"
            )
        except Exception:
            # Silently ignore if JS side doesn't support drawCircle yet
            pass

    def close(self):
        if self._win and self._open:
            self._open = False
            try:
                self._win.destroy()
            except Exception:
                pass
    def is_open(self):
        return self._open
class SetupGuide(ctk.CTk):
    def __init__(self, error):
        super().__init__()
        # Check if running on Windows
        ctk.set_appearance_mode("dark")
        # Set different window size for Windows
        if sys.platform == "win32":
            self.geometry("500x450")
        else:
            self.geometry("600x550")
        self.title("PyWare Fishing Setup Guide")
        self.configure(fg_color="#05051b")
        # Start hotkey listener at the beginning for macOS (only if needed)
        if not sys.platform == "win32":
            self.start_hotkey_listener()
        ctk.CTkLabel(
            self,
            text="PyWare Fishing Setup Guide",
            font=(ctk.CTkFont, 24, "bold")
        ).pack(pady=(20, 10))
        ctk.CTkLabel(
            self,
            text=(error),
            wraplength=500
        ).pack(pady=(0, 20))
        # Only show permissions text and buttons on macOS
        if not sys.platform == "win32":
            ctk.CTkLabel(
                self,
                text=(
                    "Before starting the macro, grant permissions and "
                    "copy the required folders into the PyWare Fishing directory."
                ),
                wraplength=500
            ).pack(pady=(0, 20))
            ctk.CTkButton(
                self,
                text="Accessibility Permissions",
                command=self.open_accessibility
            ).pack(pady=5)
            ctk.CTkButton(
                self,
                text="Input Monitoring",
                command=self.open_input_monitoring
            ).pack(pady=5)
            ctk.CTkButton(
                self,
                text="Screen Recording",
                command=self.open_screen_recording
            ).pack(pady=5)
        else:
            # Windows-specific setup text
            ctk.CTkLabel(
                self,
                text=(
                    "Before starting the macro, copy the required "
                    "folders into the PyWare Fishing directory."
                ),
                wraplength=400
            ).pack(pady=(0, 20))
        ctk.CTkLabel(
            self,
            text=(
                "\nRequired folders:\n\n"
                "✓ configs\n"
                "✓ images\n"
                "✓ ui"
            ),
            justify="left"
        ).pack(pady=20)
        ctk.CTkButton(
            self,
            text="Open PyWare Fishing Folder",
            command=open_base_folder
        ).pack(pady=5)
        ctk.CTkButton(
            self,
            text="Quit",
            command=self.destroy
        ).pack(side="bottom", pady=20)
    def start_hotkey_listener(self):
        """Start the hotkey listener to avoid trace trap errors"""
        try:
            self.listener = keyboard.Listener(
                on_press=lambda key: None,
                suppress=False
            )
            self.listener.start()
            # Don't stop it immediately - let it run in background
        except Exception as e:
            print(f"Failed to start hotkey listener: {e}")
    def check_accessibility(self):
        return Quartz.AXIsProcessTrusted()
    def check_screen_recording(self):
        try:
            with mss.mss() as sct:
                sct.grab({
                    "left": 0,
                    "top": 0,
                    "width": 10,
                    "height": 10
                })
            return True
        except:
            return False
    def open_accessibility(self):
        if sys.platform == "darwin":
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
            ])
            self.check_accessibility()
        else:
            print(f"YOU'RE ON {sys.platform.upper()} IT'S ALREADY GRANTED")
    def open_input_monitoring(self):
        if sys.platform == "darwin":
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
            ])
            # Only open the settings app, no listener check
        else:
            print(f"YOU'RE ON {sys.platform.upper()} IT'S ALREADY GRANTED")
    def open_screen_recording(self):
        if sys.platform == "darwin":
            subprocess.Popen([
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
            ])
            self.check_screen_recording()
        else:
            print(f"YOU'RE ON {sys.platform.upper()} IT'S ALREADY GRANTED")
    def destroy(self):
        """Clean up listener when closing"""
        if hasattr(self, 'listener'):
            self.listener.stop()
        super().destroy()
class Api:
    GENERIC_PLACEHOLDERS = {
        "tolerance",
    }
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
        # Detection Variables
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None
        self.last_cached_box_length = None  # Cached Bar Size From Minigame For Arrow Estimation
        self.last_input_time = 0.0
        self.cooldown_duration = 1.0  # 1 second cooldown
        # P/D State Variables
        self._pid_last_error = 0.0      # Previous Error Term
        self._pid_last_scan_time = None      # Timestamp Of Last Pd Sample
        self.last_bar_size = None
        self._normal_prev_bar_center = None  # Last bar center for _normal_control D-term
        # Arrow-Based Box Estimation Variables
        self.last_indicator_x = None
        self.last_holding_state = None
        self.pending_holding_state = None
        self.pending_indicator_x = None
        self.estimated_box_length = None
        self._last_bar_left_x = None
        self._last_bar_right_x = None
        self._last_bar_box_size = None
        self._last_bar_center = None
        self.last_arrow_delta = None
        # Estimation internal position state — initialised here so that
        # the first arrow_centroid_x=None call never raises AttributeError
        self.last_known_box_center_x = None
        self.last_left_x = None
        self.last_right_x = None
        # Safe Defaults Before Key Listener Starts (Will Be Overwritten By Load_Misc_Settings)
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
        self.current_rod_name = "Basic Rod"
        self.scale_x_1440 = self.SCREEN_WIDTH / 2560
        self.scale_y_1440 = self.SCREEN_HEIGHT / 1440
        # Screen capture variables — MSS instances are per-thread (see _thread_local)
        self._thread_local = threading.local()
        self._monitor = {}      # pre-allocated monitor dict, reused every grab
        self._scale_cache = None  # cached DPI scale factor
        # Buffer for capture/logic thread decoupling (used in start_macro())
        self._cap_lock = threading.Lock()
        self._cap_frame = None    # latest full screen frame
        self._cap_event = threading.Event()  # signals a new frame pair is ready
        # Capture thread state tracking (prevents multiple threads and race conditions)
        self._active_capture_stop = None   # threading.Event to stop current capture thread
        self._active_capture_thread = None # Current background capture thread
        self.webhook_cycle_counter = 0
        self.totem_cycle_counter = 0
        self.webhook_start_time = 0
        self.totem_start_time = 0
        self.fish_overlay = FishOverlay(self)
        self._fish_overlay_mode = "idle"
        self._fish_overlay_cast_bounds = None
        # Save settings (create folder if missing)
        os.makedirs(CONFIGS_FOLDER, exist_ok=True)
        self.load_misc_settings()
    def _refresh_screen_dimensions(self):
        """
        Re-query mss for the primary monitor's current resolution and update all
        screen-dimension instance variables.  Call this whenever the capture monitor
        changes (hot-plug, resolution switch, etc.) so that _get_areas, _grab_screen_full,
        and the fish-overlay layout all use the correct pixel dimensions.
        Invalidating _thread_local forces _grab_screen_full to rebuild its cached
        monitor dict on the next capture call.
        """
        with mss.mss() as _sct:
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
        # Force _grab_screen_full to rebuild the thread-local monitor dict.
        self._thread_local = threading.local()
    def start_eyedropper(self):
        # Toggle Off If Already Open
        if hasattr(self, "eyedropper") and self.eyedropper and self.eyedropper.is_open():
            self.eyedropper.close()
            return
        # Create and show eyedropper
        self.eyedropper = Eyedropper(parent=self)
        self.set_status("Eyedropper opened • Hover to preview • Click to pick • Esc to cancel")
    # 
    # Save Config
    # 
    def _get_prompt_defaults(self):
        defaults = {}
        index_path = os.path.join(UI_PATH, "index.html")
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception:
            return defaults
        input_pattern = re.compile(
            r"<input\b(?=[^>]*\bid\s*=\s*['\"]?([^'\"\s>]+))"
            r"(?=[^>]*\bplaceholder\s*=\s*['\"]([^'\"]*)['\"])[^>]*>",
            re.IGNORECASE,
        )
        for field_id, placeholder in input_pattern.findall(html):
            prompt = placeholder.strip()
            if prompt and prompt.lower() not in self.GENERIC_PLACEHOLDERS:
                defaults[field_id] = prompt
        select_pattern = re.compile(
            r"<select\b(?=[^>]*\bid\s*=\s*['\"]?([^'\"\s>]+))[^>]*>"
            r"(.*?)</select>",
            re.IGNORECASE | re.DOTALL,
        )
        option_pattern = re.compile(
            r"<option\b[^>]*\bvalue\s*=\s*['\"]?([^'\"\s>]+)",
            re.IGNORECASE,
        )
        for field_id, body in select_pattern.findall(html):
            if field_id == "disabled":
                continue
            match = option_pattern.search(body)
            if match:
                defaults[field_id] = match.group(1).strip()
        return defaults
    def _get_saved_default_config(self):
        default_path = os.path.join(
            CONFIGS_FOLDER,
            "Default",
            "config.json"
        )
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
        config_path = os.path.join(
            CONFIGS_FOLDER,
            config_name,
            "config.json"
        )
        with open(config_path, "r") as f:
            settings = json.load(f)
        settings = self._fill_blank_settings(settings)
        return settings, config_path
    def save_config(self, config_name, settings, text="Settings saved"):
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
            settings = self._fill_blank_settings(settings)
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
            self.set_status(text)
            return {
                "success": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    # 
    # Load Config
    # 
    def load_config(self, config_name):
        try:
            if not config_name:
                return {
                    "success": False,
                    "error": "No config selected."
                }
            settings, config_path = self._load_config_data(config_name)
            with open(config_path, "w") as f:
                json.dump(
                    settings,
                    f,
                    indent=4
                )
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
    # 
    # List Configs
    # 
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
    # 
    # Settings State
    # 
    def update_settings(self, settings):
        self.vars.update(settings)
        self._apply_fish_overlay_state()
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
            self.set_status("Error saving last config:", e)
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
                json.dump(
                    settings,
                    f,
                    indent=4
                )
            self.vars = settings
            self.current_config = config_name
            self.save_last_config(config_name)
        except Exception as e:
            self.set_status("Error loading config:", e)
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
    # 
    # Delete Config
    # 
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
        for key in ["shake", "fish", "friend", "totem"]:
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
        data["last_rod"] = self.current_rod_name
        data["bar_areas"] = clean_bar_areas
        # Optional Hotkeys
        # data["start_key"] = ...
        # data["change_bar_areas_key"] = ...
        # data["stop_key"] = ...
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
                CONFIG_DIR,
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
                CONFIG_DIR,
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
    def reset_areas(self, config_name):
        try:
            config_folder = os.path.join(
                CONFIG_DIR,
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
            config_data["bar_areas"] = {
                "shake": {
                    "x": 0.1041,
                    "y": 0.0925,
                    "width": 0.7917,
                    "height": 0.6963
                },
                "fish": {
                    "x": 0.2844,
                    "y": 0.7981,
                    "width": 0.4297,
                    "height": 0.0389
                },
                "friend": {
                    "x": 0.0046,
                    "y": 0.8583,
                    "width": 0.0355,
                    "height": 0.0817
                },
                "totem": {
                    "x": 0.9531,
                    "y": 0.8333,
                    "width": 0.0208,
                    "height": 0.0463
                }
            }
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
        try:
            safe = message.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")
            window.evaluate_js("window.setStatus && window.setStatus('" + safe + "')")
        except Exception:
            pass
    # Area Selector
    def _get_scale_factor(self):
        return get_scale_factor()
    def open_area_selector(self):
        # Toggle Off If Already Open
        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.is_open():
            self.area_selector.close()
            return
        # Default Fallback Areas
        def default_shake_area():
            left = 0.1041
            top = 0.0925
            right = 0.8958
            bottom = 0.7888
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        def default_fish_area():
            left = 0.2844
            top = 0.7981
            right = 0.7141
            bottom = 0.8370
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        def default_friend_area():
            left = 0.0046
            top = 0.8583
            right = 0.0401
            bottom = 0.94
            return {"x": left, "y": top,
                    "width": right - left, "height": bottom - top}
        def default_totem_area():
            left = 0.9531
            top = 0.8333
            right = 0.9739
            bottom = 0.8796
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
    # Main macro functions
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
                if self.macro_running == True:
                    return
                else:
                    # Save current settings to config before starting
                    self.save_config(self.current_config, self.vars)
                    if automation_mode == "fishing" or automation_mode == "tranquility":
                        threading.Thread(target=self.start_fishing, daemon=True).start()
                    elif automation_mode == "appraisal":
                        threading.Thread(target=self.start_appraisal, daemon=True).start()
                    elif automation_mode == "enchant":
                        threading.Thread(target=self.start_enchantment, daemon=True).start()
                    elif automation_mode == "angler":
                        threading.Thread(target=self.start_angler, daemon=True).start()
            elif key == bar_areas_key:
                self.open_area_selector()
            elif key == stop_key:
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
        # Convert coordinates if needed (Retina scaling)
        if sys.platform == "darwin":
            scale = self._get_scale_factor()
            x = int(x / scale)
            y = int(y / scale)
        # Move cursor to target
        _move_mouse(x, y)
        # Tiny jiggle so Roblox registers the input
        if sys.platform == "win32":
            windll.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
        else:
            _move_mouse(x + 1, y + 1)
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
        key = str(key2)
        if sys.platform == "darwin":
            send_key(key, delay=delay, click_type=click_type)
        else:
            try:
                if click_type == 0:           # click
                    keyboard_controller.press(key)
                    time.sleep(delay)
                    keyboard_controller.release(key)
                elif click_type == 1:         # hold
                    keyboard_controller.press(key)
                elif click_type == 2:         # release
                    keyboard_controller.release(key)
            except Exception as e:
                print("Error sending keys: ", e)
    # Screen Capture and Capture Thread
    def _grab_screen_region(self, left, top, right, bottom):
        """Optimized path for MSS screen capture with macOS color handling. Coordinates are expected to be already scaled."""
        width = right - left
        height = bottom - top
        if sys.platform == "darwin":
            region = Quartz.CGRectMake(left, top, width, height) # Get region
            # Capture full screen
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectInfinite,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault
            )
            if image is None:
                return None
            frame = cgimage_to_srgb_numpy(image)
            # Manual crop using actual coordinates
            cropped = frame[top:bottom, left:right]
            return cropped.copy()
        else:
            width  = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                return None
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
            return bgr_frame
    def _grab_screen_full(self, thread_local=None):
        # Fallback like grab_screen_region
        if thread_local is None:
            thread_local = self._thread_local
        scale = self._get_scale_factor()
        width = int(self.SCREEN_WIDTH * scale)
        height = int(self.SCREEN_HEIGHT * scale)
        if sys.platform == "darwin":
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectInfinite,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault
            )
            if image is None:
                return None
            frame = cgimage_to_srgb_numpy(image)
            # Crop manually for coordinate consistency.
            # cgimage_to_srgb_numpy already returns an owned copy, so no second
            # .copy() is needed here — the slice is just a view into that buffer.
            return frame[0:height, 0:width]
        else:
            if not hasattr(thread_local, "sct"):
                thread_local.sct = mss.mss()
            cached = getattr(thread_local, "monitor", None)
            if cached is None or cached["width"] != width or cached["height"] != height:
                thread_local.monitor = {
                    "left": 0,
                    "top": 0,
                    "width": width,
                    "height": height
                }
            m = thread_local.monitor
            img = thread_local.sct.grab(m)
            # Convert MSS image safely
            frame = np.array(img, dtype=np.uint8)
            # Remove alpha channel
            bgr_frame = frame[:, :, :3]
            return bgr_frame
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
    def _stop_active_capture(self, join_timeout=2.0):
        """Stops the current capture thread with proper cleanup and synchronization.
        Args:
            join_timeout: Maximum seconds to wait for thread to exit (increased from 1.0 to 2.0)
        """
        stop_event = getattr(self, "_active_capture_stop", None)
        thread = getattr(self, "_active_capture_thread", None)
        if stop_event is not None:
            stop_event.set()
        # Wake up anything waiting on a frame
        if hasattr(self, "_cap_event"):
            self._cap_event.set()
        # Ensure thread exits before returning
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(join_timeout)
            # If thread is still alive after timeout, log it (indicates a stuck thread)
            if thread.is_alive():
                print(f"WARNING: Capture thread did not exit within {join_timeout}s")
        # Clean up frame and state
        with self._cap_lock:
            self._cap_frame = None
        if hasattr(self, "_cap_event"):
            self._cap_event.clear()
        self._active_capture_stop = None
        self._active_capture_thread = None
    def _start_capture(self, scan_delay):
        """
        Starts a background thread that continuously grabs full frames.
        Stops any previously running capture thread first to prevent races.
        Returns a stop_event to terminate the new thread.
        IMPORTANT: Always call _stop_active_capture() before calling this to prevent
        multiple capture threads from running simultaneously (causes CPU spikes).
        """
        # Stop any existing capture thread to prevent overlapping threads
        # which causes segfaults (especially on macOS Quartz) and CPU spike
        self._stop_active_capture()
        self._cap_frame = None
        # Ensure capture synchronization primitives exist
        if not hasattr(self, "_cap_lock"):
            self._cap_lock = threading.Lock()
        if not hasattr(self, "_cap_event"):
            self._cap_event = threading.Event()
        self._cap_event.clear()
        # Back-pressure: producer skips a capture cycle if the consumer hasn't
        # processed the previous frame yet.  Both counters are plain ints written
        # under _cap_lock; no atomics needed because only one producer thread
        # writes _cap_frame_id and consumers are expected to bump _cap_consumed_id.
        self._cap_frame_id = 0
        self._cap_consumed_id = 0
        stop_event = threading.Event()
        self._active_capture_stop = stop_event  # Track the active stop event
        # Enforce minimum frame rate on macOS to prevent CPU saturation
        _mac_floor = 0.033 if sys.platform == "darwin" else 0.001  # 30 FPS floor on macOS, 1ms on others
        def _loop():
            """Background capture thread loop.
            Key design decisions:
            - Back-pressure via _cap_frame_id / _cap_consumed_id: the producer skips
              a capture cycle when the consumer hasn't yet processed the previous frame.
              This prevents the producer and consumer from doing numpy/C work simultaneously
              across two cores (the GIL releases during CGWindowListCreateImage / numpy
              memcpy, so both threads genuinely run in parallel).
            - stop_event.wait() instead of time.sleep(): wakes immediately when the
              macro is stopped, so the thread exits without waiting out a full sleep interval.
            """
            try:
                thread_local = threading.local()
                target_frame_time = max(_mac_floor, scan_delay)
                while self.macro_running and not stop_event.is_set():
                    # Back-pressure: skip this cycle if the consumer hasn't cleared
                    # the previous frame yet.  We still sleep to avoid a busy-spin.
                    with self._cap_lock:
                        producer_ahead = (self._cap_frame_id != self._cap_consumed_id)
                    if producer_ahead:
                        stop_event.wait(0.005)  # 5 ms yield; wakes early on stop
                        continue
                    t0 = time.perf_counter()
                    frame = self._grab_screen_full(thread_local)
                    with self._cap_lock:
                        self._cap_frame = frame
                        self._cap_frame_id += 1
                        self._cap_event.set()
                    # Sleep for the remainder of the target frame interval.
                    # stop_event.wait() wakes immediately if stop is requested,
                    # unlike time.sleep() which cannot be interrupted.
                    elapsed = time.perf_counter() - t0
                    sleep_for = target_frame_time - elapsed
                    if sleep_for > 0:
                        stop_event.wait(sleep_for)
                    else:
                        # Over budget - yield briefly so the OS scheduler can run
                        # the consumer and the game process.
                        stop_event.wait(0.001)
            finally:
                # Clean up thread-local MSS resources
                sct = getattr(thread_local, "sct", None)
                if sct is not None:
                    try:
                        sct.close()
                    except Exception:
                        pass
                # Wake any consumer blocked on _cap_event so it can detect the stop
                self._cap_event.set()
                # Clear tracking references
                if self._active_capture_stop is stop_event:
                    self._active_capture_stop = None
                if self._active_capture_thread is threading.current_thread():
                    self._active_capture_thread = None
        # Start capture thread as daemon so it doesn't block shutdown
        thread = threading.Thread(target=_loop, daemon=True, name="PyWareCapture")
        self._active_capture_thread = thread
        thread.start()
        return stop_event
    # Take Debug Screenshot (no _)
    def take_debug_screenshot(self):
        """
        Capture all relevant areas (shake, fish, friend, totem)
        and save debug images.
        """
        self.set_status("Saved debug screenshots (fish, shake, friend, totem, full)")
        # Define Areas (Same As Minigame) 
        shake_l, shake_t, shake_r, shake_b, _, _ = self._get_areas("shake")
        fish_l, fish_t, fish_r, fish_b, _, _ = self._get_areas("fish")
        friend_l, friend_t, friend_r, friend_b, _, _ = self._get_areas("friend")
        totem_l, totem_t, totem_r, totem_b, _, _ = self._get_areas("totem")
        # Capture Full Screen (Better For Overlay Debugging) 
        full_img = self._grab_screen_full()
        if full_img is None:
            self.set_status("Failed to grab full screen")
            return
        # Save full screenshot for debugging
        try:
            cv2.imwrite(os.path.join(BASE_PATH, "debug_full.png"), full_img)
        except Exception as e:
            self.set_status(f"Error saving full screenshot: {e}")
        # Save Individual Regions
        try:
            cv2.imwrite(
                os.path.join(BASE_PATH, "debug_fish.png"),
                full_img[fish_t:fish_b, fish_l:fish_r]
            )
            cv2.imwrite(
                os.path.join(BASE_PATH, "debug_shake.png"),
                full_img[shake_t:shake_b, shake_l:shake_r]
            )
            cv2.imwrite(
                os.path.join(BASE_PATH, "debug_friend.png"),
                full_img[friend_t:friend_b, friend_l:friend_r]
            )
            cv2.imwrite(
                os.path.join(BASE_PATH, "debug_totem.png"),
                full_img[totem_t:totem_b, totem_l:totem_r]
            )
        except Exception as e:
            self.set_status(f"Error saving region screenshots: {e}")
            return
    # Get values (with fallback)
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
        left2   = int(left * scale * self.SCREEN_WIDTH)
        top2    = int(top * scale * self.SCREEN_HEIGHT)
        right2  = int(right * scale * self.SCREEN_WIDTH)
        bottom2 = int(bottom * scale * self.SCREEN_HEIGHT)
        width2  = int(width * scale * self.SCREEN_WIDTH)
        height2 = int(height * scale * self.SCREEN_HEIGHT)
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
    def _get_overlay_anchor_area(self, area_name):
        left, top, right, bottom, _, _ = self._get_areas(area_name)
        return left, top, right, bottom
    def _build_horizontal_overlay_layout(self, area_bounds):
        left, top, right, bottom = area_bounds
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = left
        above_y = top - height
        below_y = bottom
        y = above_y if above_y >= 0 else below_y
        return x, y, width, height
    def _get_fish_overlay_layout(self, mode=None):
        mode = mode or self._fish_overlay_mode
        if mode == "casting":
            shake_left, shake_top, shake_right, shake_bottom = self._get_overlay_anchor_area("shake")
            shake_height = shake_bottom - shake_top
            shake_center_x = (shake_left + shake_right) / 2
            overlay_width = 60
            overlay_height = max(36, shake_height)
            y = shake_top
            cast_center_x = shake_center_x
            if self._fish_overlay_cast_bounds is not None:
                cast_left, cast_top, cast_right, cast_bottom = self._fish_overlay_cast_bounds
                cast_center_x = (cast_left + cast_right) / 2
                overlay_height = max(36, cast_bottom - cast_top)
                y = cast_top
            x = shake_right if cast_center_x <= shake_center_x else shake_left - overlay_width
            return x, y, overlay_width, overlay_height
        elif mode == "fishing":
            x, y, overlay_width, overlay_height = self._build_horizontal_overlay_layout(
                self._get_overlay_anchor_area("fish")
            )
            half_height = int(self.SCREEN_HEIGHT / 2)
            y = y - 80 if y > half_height else y + 80
            return x, y, overlay_width, overlay_height
        elif mode == "tranquility":
            shake_left, shake_top, shake_right, shake_bottom = self._get_overlay_anchor_area("shake")
            fish_left, fish_top, fish_right, fish_bottom = self._get_overlay_anchor_area("fish")
            shake_height = shake_bottom - shake_top
            fish_height = fish_bottom - fish_top
            overlay_width = fish_height
            overlay_height = shake_height
            x = int(shake_left - 20 - (fish_left / 2))
            y = shake_top
            return x, y, overlay_width, overlay_height
        return self._build_horizontal_overlay_layout(self._get_overlay_anchor_area("friend"))
    def _is_fish_overlay_enabled(self):
        return self.vars.get("fish_overlay") == "on"
    def _apply_fish_overlay_state(self):
        if not hasattr(self, "fish_overlay"):
            return
        if not self._is_fish_overlay_enabled() or self._fish_overlay_mode == "idle":
            self.fish_overlay.hide()
            return
        x, y, width, height = self._get_fish_overlay_layout()
        self.fish_overlay.set_layout(x, y, width, height)
        self.fish_overlay.show()
    def _set_fish_overlay_mode(self, mode):
        "Set the fish overlay mode to either casting, fishing and tranquility"
        self._fish_overlay_mode = mode
        self._apply_fish_overlay_state()
    def _on_fish_overlay_toggle(self, *args):
        self._apply_fish_overlay_state()
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
    def _find_last_pixel(self, frame, hex, tolerance=8):
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
            y, x = coords[-1]  # Changed from [0] to [-1]
            return int(x), int(y)
        return None
    def _find_color_bounds(self, frame, hex_color, tolerance=8):
        """
        Returns (left_x, right_x) for all matching pixels.
        """
        if frame is None or frame.size == 0:
            return None
        tolerance = int(np.clip(tolerance, 0, 255))
        b, g, r = self._hex_to_bgr(hex_color)
        target = np.array([b, g, r], dtype=np.int32)
        frame_i = frame.astype(np.int32)
        diff = frame_i - target
        mask = np.sqrt(np.sum(diff ** 2, axis=-1)) <= tolerance
        y_coords, x_coords = np.where(mask)
        if len(x_coords) == 0:
            return None
        return int(np.min(x_coords)), int(np.max(x_coords))
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
                    # print(f"    🔍 Circle detected at local ({x}, {y}) with radius {r} (scale: {scale_factor:.3f})")
                    return (int(x), int(y))
            # Only use strict HoughCircles detection - no backup methods to avoid false positives
            return None
        except Exception as e:
            self.set_status(f"    Error in circle detection: {e}")
            return None
    def _find_all_circles(self, frame):
        """
        Detect all circles in frame.
        Returns:
            [(x1, y1), (x2, y2), ...]
            or [] if no valid circles found.
        All returned circles must have similar radii to reduce false positives.
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            scale_factor = (self.scale_x_1440 + self.scale_y_1440) / 2
            scaled_min_dist = int(150 * scale_factor)
            scaled_min_radius = int(50 * scale_factor)
            scaled_max_radius = int(300 * scale_factor)
            scaled_good_min_radius = int(50 * scale_factor)
            scaled_good_max_radius = int(120 * scale_factor)
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=scaled_min_dist,
                param1=100,
                param2=100,
                minRadius=scaled_min_radius,
                maxRadius=scaled_max_radius
            )
            if circles is None:
                return []
            circles = np.round(circles[0, :]).astype("int")
            # First radius filter
            good_circles = [
                (x, y, r)
                for (x, y, r) in circles
                if scaled_good_min_radius <= r <= scaled_good_max_radius
            ]
            if not good_circles:
                return []
            # Require similar sizes
            radii = [r for _, _, r in good_circles]
            median_radius = np.median(radii)
            # Allow ±15% size difference
            tolerance = median_radius * 0.15
            similar_circles = [
                (x, y)
                for (x, y, r) in good_circles
                if abs(r - median_radius) <= tolerance
            ]
            return similar_circles
        except Exception as e:
            self.set_status(f"    Error in circle detection: {e}")
            return []
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
    def _update_arrow_box_estimation(self, arrow_centroid_x, is_holding, capture_width):
        """
        Estimate bar position from the arrow indicator (geometry-first, spike-guarded).
        Strategy
        --------
        Side detection (geometry-first):
          • If a prior centre exists: arrow < centre → LEFT edge, else RIGHT edge.
          • Cold-start only (no history): fall back to is_holding semantics.
            – Not holding → arrow on LEFT;  Holding → arrow on RIGHT.
        Box size (priority order):
          1. self._last_bar_box_size — live-synced from direct pixel detection.
          2. capture_width * 0.30    — last-resort default.
        Spike guard:
          Per-frame centre movement is clamped to box_size * 0.40.
          This suppresses is_holding-lag spikes and stale-cache artefacts without
          introducing visible lag for legitimate bar movement.
        Args:
            arrow_centroid_x : X pixel of the arrow centroid (capture-region coords).
            is_holding       : True if the mouse button is currently held.
            capture_width    : Width of the capture region in pixels.
        Returns:
            (bar_center, left_x, right_x) — all None on cold-start failure.
        """
        # ── 0. Arrow absent ──────────────────────────────────────────────────
        if arrow_centroid_x is None:
            if self.last_known_box_center_x is not None:
                return self.last_known_box_center_x, self.last_left_x, self.last_right_x
            return None, None, None
        # ── 1. Box-size resolution ───────────────────────────────────────────
        # Prefer the directly-detected bar size (synced every frame direct
        # detection succeeds, see the warm-start sync block in _enter_minigame).
        if self._last_bar_box_size is not None and self._last_bar_box_size > 0:
            box_size = float(self._last_bar_box_size)
        else:
            box_size = capture_width * 0.30  # last-resort default
        # ── 2. Geometry-first side detection ────────────────────────────────
        # Using the previous centre to decide which side the arrow is on avoids
        # the 1-frame is_holding lag that causes the spike in both older versions.
        if self.last_known_box_center_x is not None:
            arrow_on_left = (arrow_centroid_x < self.last_known_box_center_x)
        else:
            # Cold-start: no position history — bootstrap from is_holding.
            arrow_on_left = not is_holding  # not holding → arrow is on LEFT edge
        # ── 3. Candidate edges ───────────────────────────────────────────────
        if arrow_on_left:
            new_left_x  = float(arrow_centroid_x)
            new_right_x = new_left_x + box_size
        else:
            new_right_x = float(arrow_centroid_x)
            new_left_x  = new_right_x - box_size
        # ── 4. Clamp to capture bounds ───────────────────────────────────────
        if new_left_x < 0:
            new_left_x  = 0.0
            new_right_x = box_size
        elif new_right_x > capture_width:
            new_right_x = float(capture_width)
            new_left_x  = new_right_x - box_size
        new_center = (new_left_x + new_right_x) / 2.0
        # ── 5. Per-frame velocity cap (spike guard) ──────────────────────────
        # If the centre would jump more than 40 % of the box width in a single
        # frame, clamp the movement.  This is a hard backstop that catches any
        # residual artefact (e.g. a momentary wrong side-decision) without
        # suppressing real fast bar movement.
        if self.last_known_box_center_x is not None:
            max_delta = box_size * 0.40
            delta = new_center - self.last_known_box_center_x
            if abs(delta) > max_delta:
                clamped = self.last_known_box_center_x + math.copysign(max_delta, delta)
                half        = box_size / 2.0
                new_left_x  = clamped - half
                new_right_x = clamped + half
                new_center  = clamped
        # ── 6. Commit ────────────────────────────────────────────────────────
        self.last_left_x             = new_left_x
        self.last_right_x            = new_right_x
        self.last_known_box_center_x = new_center
        self.last_indicator_x        = arrow_centroid_x
        self.last_holding_state      = is_holding
        return new_center, new_left_x, new_right_x
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
    def _do_pixel_search(self, frame, fish_hex, left_bar_hex, right_bar_hex, fish_tol, left_tol, right_tol):
        fish_center = self._find_color_cluster(frame, fish_hex, fish_tol, 5)
        bar_pixels = []
        bounds = self._find_color_bounds(frame, left_bar_hex, left_tol)
        if bounds:
            bar_pixels.extend(bounds)
        bounds = self._find_color_bounds(frame, right_bar_hex, right_tol)
        if bounds:
            bar_pixels.extend(bounds)
        if bar_pixels:
            left_bar_center = min(bar_pixels)
            right_bar_center = max(bar_pixels)
        else:
            left_bar_center = None
            right_bar_center = None
        try:
            fish_center = fish_center[0]
        except:
            fish_center = None
        return fish_center, left_bar_center, right_bar_center
    def do_circle_search(self, detection_img):
        circles = self._find_all_circles(detection_img)
        if not circles:
            return {}
        height, width = detection_img.shape[:2]
        lanes = {
            0: [],
            1: [],
            2: [],
            3: []
        }
        for x, y in circles:
            x_ratio = x / width
            y_ratio = y / height
            lane = round(x_ratio * 4)
            if lane < 0:
                lane = 0
            elif lane > 3:
                lane = 3
            lanes[lane].append(y_ratio)
        results = {}
        for lane in range(4):
            notes = sorted(lanes[lane])
            if len(notes) == 0:
                results[lane] = {
                    "notes": [],
                    "bottom": None
                }
                continue
            # The circle with the largest y_ratio (lowest on screen) is the stationary bottom target.
            # All others (if any) are falling notes above it. This supports multiple falling notes
            # per lane (double/triple notes) as requested.
            bottom_ratio = notes[-1]
            falling_notes = notes[:-1]
            results[lane] = {
                "notes": falling_notes,
                "bottom": bottom_ratio
            }
        return results
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
            self.set_status(f"    Error in line detection: {e}")
            return None, None, None
    # PID control
    def _reset_pid_state(self):
        """Reset all PID controller state variables before a new minigame."""
        self._pid_last_error = None
        self._pid_last_target_x = None
        self._pid_last_scan_time = None
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None
        self.last_cached_box_length = None  # Cached Bar Size From Minigame For Arrow Estimation
        self.last_input_time = 0.0
        self.cooldown_duration = 1.0  # 1 second cooldown
        # P/D State Variables
        self._pid_last_error = 0.0      # Previous Error Term
        self._pid_last_scan_time = None      # Timestamp Of Last Pd Sample
        self.last_bar_size = None
        self._normal_prev_bar_center = None  # Last bar center for _normal_control D-term
        # Arrow-Based Box Estimation Variables
        self.last_indicator_x = None
        self.last_holding_state = None
        self.pending_holding_state = None
        self.pending_indicator_x = None
        self.estimated_box_length = None
        self._last_bar_left_x = None
        self._last_bar_right_x = None
        self._last_bar_box_size = None
        self._last_bar_center = None
        self.last_arrow_delta = None
        self._ema_arrow_x = None        # EMA-smoothed arrow x; reset per minigame
        # Estimation internal position state
        self.last_known_box_center_x = None
        self.last_left_x = None
        self.last_right_x = None
        # Predictive Controller
        self._pred_prev_fish_x = None
        self._pred_prev_bar_x = None
        self._pred_prev_time = None
        self.color_check_target_velocity = 0.0
        self.color_check_bar_velocity  = 0.0
        self._pred_last_click_time = 0.0
        # Dual Fishing
        self._pid_last_error2      = 0.0
        self._pid_last_target_x2   = 0.0
        self._pid_last_scan_time2  = 0.0
        # Spammy Controller
        self.current_frame = 0
        self.state = "release"
        self.current_frame2 = 0
        self.state2 = "release"
    def _normal_control(self, error2):
        """
        Replaced FischGPT controller with early V2.0 controller to resolve DMCA takedown
        """
        # Initialization
        now = time.perf_counter()
        error = min(100, error2)
        if self._pid_last_scan_time is None:
            self._pid_last_scan_time = now
            self._pid_last_error = error
            return 0.0
        dt = now - self._pid_last_scan_time
        if dt <= 0:
            return 0.0
        kp       = self._get_var_number("kp", 0.93)
        kd       = self._get_var_number("kd", 0.07)
        # Derivative
        derivative = (error - self._pid_last_error) / dt
        derivative = min(100, derivative)
        output = (kp * error + kd * derivative)
        self._pid_last_error = error
        self._pid_last_scan_time = now
        return output
    def _steady_control(self, error, bar_center):
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
        bar_center   = bar_center
        target_line_last_x = bar_center + error  # fish_x = bar_center + error
        current_time = time.perf_counter()
        # P term – proportional to distance
        p_term = kp * error
        # D term – asymmetric damping
        d_term = 0.0
        bar_velocity = 0
        time_delta = 0
        if (
            self._pid_last_scan_time is not None
            and self._pid_last_target_x is not None
            and self._pid_last_error is not None
        ):
            time_delta = current_time - self._pid_last_scan_time
            if time_delta > 0.001:
                # Bar velocity: how fast the bar centre moved since last frame
                last_bar_x   = self._pid_last_target_x - self._pid_last_error
                bar_velocity = (bar_center - last_bar_x) / time_delta
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
        else:
            # Fallback to standard derivative
            if self._pid_last_error is not None and time_delta > 0:
                d_term = kd * (error - self._pid_last_error) / time_delta
        # Update state for next frame
        self._pid_last_error      = error
        self._pid_last_target_x   = target_line_last_x
        self._pid_last_scan_time  = current_time
        # Combined and clamped control signal
        control_signal = p_term + d_term
        control_signal = max(-pd_clamp, min(pd_clamp, control_signal))
        return control_signal
    def _steady_control2(self, error, bar_center):
        """
        Asymmetric PD controller (2).
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
        bar_center   = bar_center
        target_line_last_x = bar_center + error  # fish_x = bar_center + error
        current_time = time.perf_counter()
        # P term – proportional to distance
        p_term = kp * error
        # D term – asymmetric damping
        d_term = 0.0
        bar_velocity = 0
        time_delta = 0
        if (
            self._pid_last_scan_time2 is not None
            and self._pid_last_target_x2 is not None
            and self._pid_last_error2 is not None
        ):
            time_delta = current_time - self._pid_last_scan_time2
            if time_delta > 0.001:
                # Bar velocity: how fast the bar centre moved since last frame
                last_bar_x   = self._pid_last_target_x2 - self._pid_last_error2
                bar_velocity = (bar_center - last_bar_x) / time_delta
                error_magnitude_decreasing = abs(error) < abs(self._pid_last_error2)
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
        else:
            # Fallback to standard derivative
            if self._pid_last_error2 is not None and time_delta > 0:
                d_term = kd * (error - self._pid_last_error2) / time_delta
        # Update state for next frame
        self._pid_last_error2      = error
        self._pid_last_target_x2   = target_line_last_x
        self._pid_last_scan_time2  = current_time
        # Combined and clamped control signal
        control_signal = p_term + d_term
        control_signal = max(-pd_clamp, min(pd_clamp, control_signal))
        return control_signal
    def _spammy_control2(self, fish_x, bar_center, bar_size):
        # Initialization
        spam_ratio = self._get_var_number("spam_ratio", 0.3)
        velocity_multiplier = self._get_var_number("velocity_multiplier", 3)
        hold_frames = int(self.vars["hold_frames"])
        release_frames = int(self.vars["release_frames"])
        error = fish_x - bar_center
        if hold_frames > release_frames:
            larger_frame = hold_frames
            smaller_frame = release_frames
        else:
            larger_frame = release_frames
            smaller_frame = hold_frames
        if error > 0:
            hold_frames = larger_frame
            release_frames = smaller_frame
        elif error < 0:
            hold_frames = smaller_frame
            release_frames = larger_frame
        if self.state2 == "hold":
            self.current_frame2 += 1
            if self.current_frame2 >= hold_frames:
                self.state2 = "release"
                self.current_frame2 = 0
        elif self.state2 == "release":
            self.current_frame2 += 1
            if self.current_frame2 >= release_frames:
                self.state2 = "hold"
                self.current_frame2 = 0
        # Calculations
        spam_distance = int(bar_size * spam_ratio)
        try:
            raw_velocity = bar_center - self._pid_last_bar_x
            if raw_velocity != 0:
                self._last_velocity = raw_velocity
        except AttributeError:
            self._last_velocity = 0
        velocity = getattr(self, "_last_velocity", 0)
        spam_distance = spam_distance + (abs(velocity) * velocity_multiplier)
        # Update cache
        self._pid_last_error      = error
        self._pid_last_bar_x = bar_center
        # print(error, velocity, spam_distance)
        if abs(error) < abs(spam_distance):
            # print("Spam")
            if self.state == "hold":
                return True
            else:
                return False
        elif error < 0:
            # print("Release")
            return False
        else:
            # print("Hold")
            return True
    def _spammy_control(self, fish_x, bar_center, bar_size):
        # Initialization
        spam_ratio = self._get_var_number("spam_ratio", 0.3)
        velocity_multiplier = self._get_var_number("velocity_multiplier", 3)
        hold_frames = int(self.vars["hold_frames"])
        release_frames = int(self.vars["release_frames"])
        error = fish_x - bar_center
        if hold_frames > release_frames:
            larger_frame = hold_frames
            smaller_frame = release_frames
        else:
            larger_frame = release_frames
            smaller_frame = hold_frames
        if error > 0:
            hold_frames = larger_frame
            release_frames = smaller_frame
        elif error < 0:
            hold_frames = smaller_frame
            release_frames = larger_frame
        if self.state == "hold":
            self.current_frame += 1
            if self.current_frame >= hold_frames:
                self.state = "release"
                self.current_frame = 0
        elif self.state == "release":
            self.current_frame += 1
            if self.current_frame >= release_frames:
                self.state = "hold"
                self.current_frame = 0
        # Calculations
        spam_distance = int(bar_size * spam_ratio)
        try:
            raw_velocity = bar_center - self._pid_last_bar_x
            if raw_velocity != 0:
                self._last_velocity = raw_velocity
        except AttributeError:
            self._last_velocity = 0
        velocity = getattr(self, "_last_velocity", 0)
        spam_distance = spam_distance + (abs(velocity) * velocity_multiplier)
        # Update cache
        self._pid_last_error      = error
        self._pid_last_bar_x = bar_center
        # print(error, velocity, spam_distance)
        if abs(error) < abs(spam_distance):
            # print("Spam")
            if self.state == "hold":
                return True
            else:
                return False
        elif error < 0:
            # print("Release")
            return False
        else:
            # print("Hold")
            return True
    def _predictive_control(self, fish_x, bar_center, fish_left, fish_right, bar_left, bar_right):
        """
        Predictive controller ported from Hydra idiotproof.
        Uses linear stopping distance, on-bar counter-thrust, off-bar PD chase,
        and edge-unreachability logic.
        Check legacy/May 3rd.py for PD chase controller
        Args:
        fish_x: Fish X
        bar_center: Bar Center
        fish_left: Left of fish capture area
        fish_right: Right of fish capture area
        bar_left: Bar Left
        bar_right: Bar Right
        """
        # Init Failsafe 
        if not hasattr(self, "_pred_prev_fish_x"):
            self._reset_control_state()
        # Failsafe: Missing Data
        if fish_x is None or bar_center is None or bar_left is None or bar_right is None:
            should_hold = False
            return should_hold
        # Read Settings
        stopping_distance_multiplier = self._get_var_number("stopping_distance", 0.93)
        velocity_smoothing = self._get_var_number("velocity_smoothing", 0.07)
        MIN_DT = 1e-3
        MAX_DT = 0.1
        MAX_VEL = 3000.0
        # Time 
        now = time.perf_counter()
        if self._pred_prev_time is None:
            dt = 0.016
        else:
            dt = now - self._pred_prev_time
            dt = max(min(dt, MAX_DT), MIN_DT)
        self._pred_prev_time = now
        # Velocities 
        if self._pred_prev_fish_x is not None:
            raw_fish_vel = (fish_x - self._pred_prev_fish_x) / dt
        else:
            raw_fish_vel = 0.0
        if self._pred_prev_bar_x is not None:
            raw_bar_vel = (bar_center - self._pred_prev_bar_x) / dt
        else:
            raw_bar_vel = 0.0
        raw_fish_vel = max(min(raw_fish_vel, MAX_VEL), -MAX_VEL)
        raw_bar_vel  = max(min(raw_bar_vel,  MAX_VEL), -MAX_VEL)
        # Smooth Velocities Independently Then Compute Relative
        self.color_check_target_velocity = (velocity_smoothing * raw_fish_vel +
                                        (1 - velocity_smoothing) * self.color_check_target_velocity)
        self.color_check_bar_velocity  = (velocity_smoothing * raw_bar_vel +
                                        (1 - velocity_smoothing) * self.color_check_bar_velocity)
        relative_velocity = self.color_check_bar_velocity - self.color_check_target_velocity  # Bar Relative To Fish (Matches Ref Macro Sign)
        self._pred_prev_fish_x = fish_x
        self._pred_prev_bar_x  = bar_center
        # Nan Guard 
        if not np.isfinite(relative_velocity):
            should_hold = False
            return should_hold
        # Reachability (Edge Logic) 
        bar_width = bar_right - bar_left
        min_reachable = fish_left  + bar_width // 2
        max_reachable = fish_right - bar_width // 2
        if fish_x < min_reachable:
            # Target Too Far Left — Bar Can't Follow, Release
            should_hold = False
            return should_hold
        elif fish_x > max_reachable:
            # Target Too Far Right — Hold To Push Bar Right
            should_hold = True
            return should_hold
        # Calculate stopping distance based on relative velocity
        stopping_distance = abs(relative_velocity) * stopping_distance_multiplier
        # Error: Positive = Bar Is Right Of Fish (Same Sign Convention As Ref Macro)
        error = bar_center - fish_x
        # On-Bar: Use Stopping-Distance / Counter-Thrust Logic
        if error < -stopping_distance:
            # Bar Is Left Of Fish Beyond Stopping Distance → Hold To Move Right
            should_hold = True
        elif error > stopping_distance:
            # Bar Is Right Of Fish Beyond Stopping Distance → Release To Move Left
            should_hold = False
        else:
            # Within Stopping Distance — Counter-Thrust Based On Relative Velocity
            if relative_velocity > 0:
                # Bar Moving Right Relative To Fish → Release (Apply Left Thrust)
                should_hold = False
            else:
                # Bar Moving Left Relative To Fish → Hold (Apply Right Thrust)
                should_hold = True
        return should_hold
    # Utility Functions
    def _discord_text_worker(self, webhook_url, message_prefix, loop_count, show_status, catch_rate):
        """Worker function to send text webhook."""
        logging_name = self.vars["logging_name"]
        webhook_url2 = self.vars["logging_url"]
        try:
            if show_status == True:
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
            else:
                payload = {
                    'content': f'{message_prefix}🎣 Cycle failed\n🔄 {loop_count}\nCatch rate: {catch_rate}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
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
    def _discord_screenshot_worker(self, webhook_url, message_prefix, loop_count, show_status, catch_rate):
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
                    'content': f'{message_prefix}🎣 **Cycle completed**\n🔄 {loop_count}\nCatch rate: {catch_rate}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': logging_name
                }
                response = requests.post(webhook_url, data=payload, files=files, timeout=10)
            else:
                payload = {
                    'content': f'{message_prefix}🎣 **Cycle failed**\n🔄 {loop_count}\nCatch rate: {catch_rate}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
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
    def _debug_log_worker(self, text, loop_count, show_status, catch_rate):
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
                f"Catch rate: {catch_rate}\n"
                "==========\n\n"
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
                    "==========\n"
                    "🐞 AUTO BUG REPORT\n"
                    f"📂 Phase: {phase}\n"
                    f"🕐 {timestamp}\n"
                    "--------\n"
                    f"{report_text}\n"
                    "==========\n\n"
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
    def send_logging(self, text, loop_count, catch_rate=-1, show_status=True):
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
                args=(webhook_url, f"{text}\n", loop_count, show_status, catch_rate),
                daemon=True
            )
        elif logging_mode == "File":
            thread = threading.Thread(
                target=self._debug_log_worker,
                args=(text, loop_count, show_status, catch_rate),
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._discord_text_worker,
                args=(webhook_url, f"{text}\n", loop_count, show_status, catch_rate),
                daemon=True
            )
        thread.start()
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
            self.set_status("Totem detection: sun.png or moon.png missing.")
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
    # Start utilities
    def start_angler(self):
        self._stop_active_capture()
        self.macro_running = True
        dialogue_left, dialogue_top, dialogue_right, dialogue_bottom, dialogue_width, dialogue_height = self._get_areas("shake")
        backpack_left, backpack_top, backpack_right, backpack_bottom, _, _ = self._get_areas("fish")
        quest_left, quest_top, quest_right, quest_bottom, _, _ = self._get_areas("friend")
        tesseract_path = self.vars["tesseract_path"]
        tolerance = int(self.vars["shake_tolerance"])
        shake_pixel = self.vars["shake_color"]
        backpack_slot = str(self.vars["backpack_slot"])
        utility_restart_delay = int(self.vars["utility_restart_delay"])
        angler_click_mode = self.vars["angler_click_mode"].capitalize()
        # Angler Key
        angler_x_ratio = float(self.vars["angler_click_x"])
        angler_y_ratio = float(self.vars["angler_click_y"])
        angler_click_x = int(dialogue_width * angler_x_ratio) + dialogue_left
        angler_click_y = int(dialogue_height * angler_y_ratio) + dialogue_top
        # Backpack Key
        backpack_x_ratio = self.vars["backpack_x"]
        backpack_y_ratio = self.vars["backpack_y"]
        backpack_x = int(dialogue_width * backpack_x_ratio) + dialogue_left
        backpack_y = int(dialogue_height * backpack_y_ratio) + dialogue_top
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        # Check for utilities
        self._check_logging_trigger(-1)
        # Main loop
        while self.macro_running:
            time.sleep(0.1)
            # STEP 1: CLICK E → OPEN QUEST DIALOGUE
            self._send_key("e")
            time.sleep(1.2)
            img = self._grab_screen_full()
            shake = img[dialogue_top:dialogue_bottom, dialogue_left:dialogue_right]
            if angler_click_mode == "Search":
                try:
                    dialogue = self._find_first_pixel(shake, shake_pixel, tolerance)
                    if dialogue is not None:
                        dialogue_x, dialogue_y = dialogue
                        self._click_at(dialogue_left + dialogue_x, dialogue_top + dialogue_y)
                    time.sleep(1.2)
                except Exception as e:
                    self.set_status(e)
                    self.stop_macro(f"Angler/Quest failed: {e}")
                    break
            else:
                self._click_at(angler_click_x, angler_click_y)
            # STEP 2: OCR QUEST AREA — GET REQUIRED FISH TEXT
            time.sleep(2)
            img = self._grab_screen_full()
            quest = img[quest_top:quest_bottom, quest_left:quest_right]
            gray = cv2.cvtColor(quest, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]
            quest_text = pytesseract.image_to_string(gray)
            lines = [
                line.strip().lower()
                for line in quest_text.splitlines()
                if line.strip()
            ]
            required_fish = lines[-1] if lines else ""
            self.set_status(f"Quest fish: {required_fish}")
            if not required_fish:
                self.set_status("Could not read fish name")
                time.sleep(utility_restart_delay)
                continue
            # STEP 3: OPEN BACKPACK
            self._send_key(backpack_slot)
            time.sleep(0.5)
            # STEP 4: CLICK SEARCH BAR + TYPE FISH NAME
            self._click_at(backpack_x, backpack_y)
            time.sleep(0.25)
            # Clear previous search
            keyboard.press("ctrl")
            keyboard.press("a")
            keyboard.release("a")
            keyboard.release("ctrl")
            time.sleep(0.1)
            keyboard.press("backspace")
            keyboard.release("backspace")
            time.sleep(0.1)
            # Type fish name
            for char in required_fish:
                self._send_key(char)
            time.sleep(0.5)
            # STEP 5: LOCATE quest_text IN QUEST AREA VIA OCR AND CLICK IT
            img = self._grab_screen_full()
            quest_region = img[quest_top:quest_bottom, quest_left:quest_right]
            gray_q = cv2.cvtColor(quest_region, cv2.COLOR_BGR2GRAY)
            gray_q = cv2.resize(gray_q, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray_q = cv2.threshold(gray_q, 150, 255, cv2.THRESH_BINARY)[1]
            ocr_data_q = pytesseract.image_to_data(
                gray_q,
                output_type=pytesseract.Output.DICT,
                config="--psm 11"
            )
            quest_click_x, quest_click_y = None, None
            for i, text_tok in enumerate(ocr_data_q["text"]):
                tok = text_tok.strip().lower()
                try:
                    conf = float(ocr_data_q["conf"][i])
                except Exception:
                    conf = -1
                if conf < 40 or not tok:
                    continue
                if tok in required_fish or required_fish in tok:
                    qx = ocr_data_q["left"][i]
                    qy = ocr_data_q["top"][i]
                    qw = ocr_data_q["width"][i]
                    qh = ocr_data_q["height"][i]
                    # Undo the 3× upscale to get back to screen coords
                    quest_click_x = quest_left + (qx + qw // 2) // 3
                    quest_click_y = quest_top  + (qy + qh // 2) // 3
                    break
            if quest_click_x is not None:
                self.set_status(
                    f"Quest text '{required_fish}' found at "
                    f"{quest_click_x}, {quest_click_y} — clicking"
                )
                self._click_at(quest_click_x, quest_click_y)
            else:
                self.set_status(
                    f"Quest text '{required_fish}' not found via OCR, skipping click"
                )
            time.sleep(0.25)
            # STEP 6: CLOSE BACKPACK
            self._send_key(backpack_slot)
            time.sleep(0.5)
            # STEP 7: CLICK E → FINISH QUEST (PIXEL SEARCH OR RATIO)
            self._send_key("e")
            time.sleep(1.2)
            img = self._grab_screen_full()
            shake = img[dialogue_top:dialogue_bottom, dialogue_left:dialogue_right]
            if angler_click_mode == "Search":
                dialogue = self._find_first_pixel(shake, shake_pixel, tolerance)
                if dialogue is not None:
                    dialogue_x, dialogue_y = dialogue
                    self._click_at(dialogue_left + dialogue_x, dialogue_top + dialogue_y)
                time.sleep(1.2)
            else:
                self._click_at(angler_click_x, angler_click_y)
            # STEP 8: COOLDOWN
            time.sleep(utility_restart_delay)
    # Start enchanting
    def start_enchantment(self):
        self._stop_active_capture()
        self.macro_running = True
        tesseract_path = self.vars["tesseract_path"]
        mutation_enchant = self.vars["mutation_enchant"]
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        dialogue_left, dialogue_top, dialogue_right, dialogue_bottom, dialogue_width, dialogue_height = self._get_areas("shake")
        x = float(self.vars["appraisal_enchant_x"])
        y = float(self.vars["appraisal_enchant_y"])
        x_scaled = int(dialogue_width * x) + dialogue_left
        y_scaled = int(dialogue_height * y) + dialogue_top
        try:
            e_delay = float(self.vars["e_delay"])
            click_delay = float(self.vars["click_delay"])
            click_delay2 = float(self.vars["click_delay2"])
        except:
            e_delay = 1.0
            click_delay = 1.0
            click_delay2 = 6.0
        # Check for utilities
        self._check_logging_trigger(-1)
        # Main loop
        time.sleep(0.1)
        while self.macro_running:
            time.sleep(0.1)
            self._send_key("e")
            time.sleep(e_delay)
            self._click_at(x_scaled, y_scaled)
            time.sleep(click_delay)
            img = self._grab_screen_full()
            enchantment = img[dialogue_top:dialogue_bottom, dialogue_left:dialogue_right]
            gray = cv2.cvtColor(enchantment, cv2.COLOR_BGR2GRAY)
            # Upscale image
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            # Sharpen contrast
            gray = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]
            text = pytesseract.image_to_string(gray)
            if mutation_enchant.lower() in text.lower():
                self.stop_macro("Enchanting finished")
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
            time.sleep(click_delay2)
    # Start appraisal
    def start_appraisal(self):
        self._stop_active_capture()
        self.macro_running = True
        dialogue_left, dialogue_top, dialogue_right, dialogue_bottom, dialogue_width, dialogue_height = self._get_areas("shake")
        hotbar_left, hotbar_top, hotbar_right, hotbar_bottom, _, _ = self._get_areas("fish")
        tesseract_path = self.vars["tesseract_path"]
        mutation_enchant = self.vars["mutation_enchant"]
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        appraisal_x_ratio = float(self.vars["appraisal_enchant_x"])
        appraisal_y_ratio = float(self.vars["appraisal_enchant_y"])
        appraisal_x = int(dialogue_width * appraisal_x_ratio) + dialogue_left
        appraisal_y = int(dialogue_height * appraisal_y_ratio) + dialogue_top
        click_delay = int(self.vars["click_delay"])
        # Check for utilities
        self._check_logging_trigger(-1)
        # Main loop
        time.sleep(0.1)
        self._send_key("e", 0.05)
        while self.macro_running:
            # Click
            time.sleep(click_delay)
            self._click_at(appraisal_x, appraisal_y)
            # Detection
            img = self._grab_screen_full()
            fish = img[hotbar_top:hotbar_bottom, hotbar_left:hotbar_right]
            gray = cv2.cvtColor(fish, cv2.COLOR_BGR2GRAY)
            # Upscale image
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            # Sharpen contrast
            gray = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]
            text = pytesseract.image_to_string(gray)
            if mutation_enchant.lower() in text.lower():
                self.stop_macro("Appraisal finished")
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
    # Start main automation
    def start_fishing(self):
        self._stop_active_capture()
        self.macro_running = True
        cycle = 0
        catch_success = 0
        catch_rate = 1
        catch_rate_show = 100
        successful_catches = 0
        rod_slot = str(self.vars["rod_slot"])
        bag_slot = str(self.vars["bag_slot"])
        shake_left, shake_top, shake_right, shake_bottom, shake_width, shake_height = self._get_areas("shake")
        shake_x = shake_left + int(shake_width / 2)
        shake_y = shake_top + int(shake_height / 2)
        auto_zoom = self.vars.get("auto_zoom", "off")
        auto_refresh = self.vars.get("auto_refresh", "off")
        casting_mode = self.vars.get("casting_mode", "Normal")
        shake_mode = self.vars.get("shake_mode", "Navigation")
        automation_mode = self.vars["automation_mode"]
        if self.macro_running == True:
            if auto_zoom == "on":
                for _ in range(20):
                    mouse_controller.scroll(0, 1)
                    time.sleep(0.05)
                mouse_controller.scroll(0, -1)
                time.sleep(0.1)
        else:
            self.stop_macro("Macro Already Stopped")
        while self.macro_running:
            # Misc / Utilities
            cycle = cycle + 1
            # Select Rod
            if auto_refresh == "on":
                bag_delay = self._get_var_number("select_rod_duration", self._get_var_number("bag_delay", 0.36, float), float)
                self.set_status("Selecting rod")
                # Sequence
                time.sleep(bag_delay * 1.5)
                self._send_key(bag_slot)
                time.sleep(bag_delay)
                self._send_key(rod_slot)
                time.sleep(0.2)
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
            # Logging
            self._check_logging_trigger(catch_rate_show)
            # Totem
            self._check_totem_trigger(shake_x, shake_y)
            if self.vars["auto_reconnect"] == "on":
                self._auto_reconnect(shake_x, shake_y)
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
            # Cast
            if casting_mode == "perfect" or casting_mode == "Perfect":
                self._execute_cast_perfect()
            else:
                self.execute_cast_normal()
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
            # Shake
            if shake_mode == "navigation" or shake_mode == "Navigation":
                self._execute_shake_navigation()
            else:
                self._execute_shake_click(shake_mode)
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
            # Minigame
            if automation_mode == "tranquility" or automation_mode == "Tranquility":
                self._enter_minigame_tranquility()
            else:
                catch_success = self._enter_minigame()
            successful_catches = successful_catches + 1 if catch_success == True else successful_catches
            catch_rate = (successful_catches / cycle)
            catch_rate_show = round(catch_rate * 100)
            if self.macro_running == False:
                self.stop_macro("Macro Already Stopped")
    # Utilities
    def _check_logging_trigger(self, catch_rate=-1):
        """
        Check whether the Logging should fire based on the selected mode.
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
                self.send_logging("**Cycle Checkpoint**", label, catch_rate, show_status=False)
        elif cd_mode == "Time":
            self.webhook_cycle_counter += 1  # still count cycles for the message label
            elapsed = time.time() - self.webhook_start_time
            if trigger_secs > 0 and elapsed >= trigger_secs:
                label = f"Cycle #{self.webhook_cycle_counter} | {int(elapsed)}s elapsed"
                self.send_logging("**Time Checkpoint**", label, catch_rate, show_status=False)
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
        rod_slot  = str(self.vars["rod_slot"])
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
            self._send_key(sundial_slot)
            time.sleep(0.2)
            mouse_controller.position = (shake_x, shake_y)
            time.sleep(0.05)
            self._click_at(shake_x, shake_y)
            # Wait For Time Transition
            time.sleep(sundial_delay)
        # Use Target Totem
        time.sleep(0.2)
        self._send_key(target_slot)
        time.sleep(0.4)
        mouse_controller.position = (shake_x, shake_y)
        time.sleep(0.05)
        self._click_at(shake_x, shake_y)
        time.sleep(1)
        self._send_key(rod_slot)
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
        self._fish_overlay_cast_bounds = None
        self._set_fish_overlay_mode("casting")
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
                self._cap_consumed_id = self._cap_frame_id  # back-pressure release
                self._cap_event.clear()
            if frame is None:
                stop_event.set()
                return
            region = frame[shake_top_s:shake_bottom_s, shake_left_s:shake_right_s]
            if region.size == 0:
                if time.time() - start_time > max_time:
                    break
                continue
            if self._is_fish_overlay_enabled():
                self.fish_overlay.clear()
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
            cast_left = shake_left_s + green_left_x
            cast_top = shake_top_s + green_y
            cast_right = shake_left_s + green_right_x
            cast_bottom = shake_top_s + white_y_bottom
            if self._fish_overlay_cast_bounds != (cast_left, cast_top, cast_right, cast_bottom):
                self._fish_overlay_cast_bounds = (cast_left, cast_top, cast_right, cast_bottom)
                self._apply_fish_overlay_state()
            if self._is_fish_overlay_enabled():
                cast_height = max(1, white_y_bottom - green_y)
                white_ratio = max(0.0, min(1.0, current_distance / cast_height))
                draw_x = self.fish_overlay.width / 2
                bar_height = 0.08
                self.fish_overlay.draw(
                    bar_center=draw_x, box_size=15, color="green", canvas_offset=0,
                    bar_y1=0.0, bar_y2=min(1.0, bar_height / 2)
                )
                self.fish_overlay.draw(
                    bar_center=draw_x, box_size=30, color="white", canvas_offset=0,
                    bar_y1=max(0.0, white_ratio - bar_height / 2),
                    bar_y2=min(1.0, white_ratio + bar_height / 2)
                )
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
        self._fish_overlay_cast_bounds = None
        self._set_fish_overlay_mode("idle")
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
        friend_color = self.vars["friends_color"]
        friend_tol = int(self.vars["friends_tolerance"])
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
                self._cap_consumed_id = self._cap_frame_id  # back-pressure release
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
                friend_x = self._find_color_center(detection_area, friend_color, friend_tol)
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
        friend_color = self.vars["friends_color"]
        friend_tol = int(self.vars["friends_tolerance"])
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
                    self._cap_consumed_id = self._cap_frame_id  # back-pressure release
                    self._cap_event.clear()
                if frame is None:
                    stop_event.set()
                    # print("Finished (no frame)")
                    return
                detection_area = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                if detection_area is None or detection_area.size == 0:
                    break
                friend_x = self._find_color_center(detection_area, friend_color, friend_tol)
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
                # print("Finished (fish detected)")
                return  # exit shake cleanly
            attempts += 1
            time.sleep(scan_delay)
    def _enter_minigame_tranquility(self):
        # Get colors
        left_color = self.vars["left_color"]
        right_color = self.vars["right_color"]
        arrow_color = self.vars["arrow_color"]
        fish_color = self.vars["fish_color"]
        # Get misc variables
        target = float(self.vars["tranquility_note_ratio"]) - 0.2
        target_delay = float(self.vars["target_delay"]) + 0.06
        tranquility_mode = self.vars["tranquility_mode"]
        scan_delay = float(self.vars["minigame_scan_delay"])
        restart_delay = float(self.vars["restart_delay"])
        friend_color = self.vars["friends_color"]
        friend_tol = int(self.vars["friends_tolerance"])
        # Get hotkeys
        tranquility_key_1 = str(self.vars["tranquility_key_1"])
        tranquility_key_2 = str(self.vars["tranquility_key_2"])
        tranquility_key_3 = str(self.vars["tranquility_key_3"])
        tranquility_key_4 = str(self.vars["tranquility_key_4"])
        # Get areas
        shake_left, shake_top, shake_right, shake_bottom, _, shake_height = self._get_areas("shake")
        fish_left, fish_top, fish_right, fish_bottom, _, fish_height = self._get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._get_areas("friend")
        # Start Screen Capture Thread (via _start_capture so it's tracked and
        # any previously running capture thread is stopped before this one begins)
        _minigame_stop = self._start_capture(scan_delay)
        while self.macro_running:
            # Step 1: Grab Full Screen Then Crop (better on macOS)
            if not self._cap_event.wait(timeout=0.5):
                continue
            with self._cap_lock:
                frame = self._cap_frame
                self._cap_consumed_id = self._cap_frame_id  # back-pressure release
                self._cap_event.clear()
            if frame is None:
                _minigame_stop.set()
                self._set_fish_overlay_mode("idle")
                return
            self._set_fish_overlay_mode("tranquility")
            # Step 2: Crop images
            friend_img = frame[friend_top:friend_bottom, friend_left:friend_right]
            detection_img = frame[shake_top:shake_bottom, shake_left:shake_right]
            # Step 3: Detection
            lane_data = self.do_circle_search(detection_img)
            # Step 4: Restart Method — Friend Area (green present = minigame ended)
            friend_x = self._find_color_center(friend_img, friend_color, friend_tol)
            if friend_x is not None:
                keyboard_controller.release(tranquility_key_1)
                keyboard_controller.release(tranquility_key_2)
                keyboard_controller.release(tranquility_key_3)
                keyboard_controller.release(tranquility_key_4)
                time.sleep(restart_delay)
                self._set_fish_overlay_mode("idle")
                return
            keys = [
                tranquility_key_1,
                tranquility_key_2,
                tranquility_key_3,
                tranquility_key_4
            ]
            colors = [
                left_color,
                right_color,
                arrow_color,
                fish_color
            ]
            lane_distances = {}
            for lane in range(4):
                lane_info = lane_data.get(lane)
                if not lane_info:
                    continue
                bottom_ratio = lane_info["bottom"]
                if bottom_ratio is None:
                    continue
                note_distances = []
                for note_ratio in lane_info["notes"]:
                    note_distances.append(bottom_ratio - note_ratio)
                lane_distances[lane] = note_distances
            # Step 7: Draw
            try:
                for lane in range(4):
                    lane_info = lane_data.get(lane)
                    if not lane_info:
                        continue
                    bottom_ratio = lane_info["bottom"]
                    if bottom_ratio is None:
                        continue
                    for note_ratio in lane_info["notes"]:
                        # draw falling note
                        self.fish_overlay.draw_circle(
                            lane=lane,
                            ratio=note_ratio,
                            color=colors[lane]
                        )
                    # draw stationary circle
                    self.fish_overlay.draw_circle(
                        lane=lane,
                        ratio=bottom_ratio,
                        color=colors[lane]
                    )
            except:
                pass
            # Step 8: Compare note ratios to user given target (based on tranquility mode)
            if tranquility_mode.lower() == "rapid":
                for lane in range(4):
                    for distance in lane_distances.get(lane, []):
                        if distance <= target:
                            time.sleep(target_delay)
                            self._send_key(keys[lane])
                            # Note: no break here so that if multiple notes in the SAME lane
                            # are aligned close enough this frame (rare but possible), we press
                            # once per note. Different lanes are handled by outer loop.
            elif tranquility_mode.lower() == "steady":
                for lane in range(4):
                    should_press = False
                    for distance in lane_distances.get(lane, []):
                        if distance <= target:
                            should_press = True
                            break
                    if should_press:
                        time.sleep(target_delay)
                        self._send_key(keys[lane], 0.03, 1)
                    else:
                        self._send_key(keys[lane], 0.03, 2)
            time.sleep(scan_delay)
    def _enter_minigame(self):
        # Areas
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._get_areas("shake")
        fish_left, fish_top, fish_right, fish_bottom, fish_width, _ = self._get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._get_areas("friend")
        self._reset_pid_state()
        mouse_down = False
        self._set_fish_overlay_mode("fishing")
        # Colors
        arrow_hex = self.vars["arrow_color"]
        note_box_hex = self.vars["tracking_color"]
        note_track_ratio = float(self.vars["pinion_note_ratio"] or 0.1)
        friend_color = self.vars["friends_color"]
        friend_tol = int(self.vars["friends_tolerance"])
        note_box_tol = self._get_var_number("tracking_tolerance", 8)
        arrow_tol = self._get_var_number("arrow_tolerance", 8)

        fish_hex = self.vars["fish_color"]
        left_bar_hex = self.vars["left_color"]
        right_bar_hex = self.vars["right_color"]
        try: # Handle Nonetype and int properly
            left_tol = int(self.vars["left_tolerance"] or 8)
            right_tol = int(self.vars["right_tolerance"] or 8)
            fish_tol = int(self.vars["fish_tolerance"] or 4)
        except:
            left_tol = 8
            right_tol = 8
            fish_tol = 4
        # Minigame Settings
        bar_ratio = float(self.vars["bar_ratio_from_side"] or 0.5)
        restart_delay = float(self.vars["restart_delay"])
        track_notes = self.vars["track_notes"]
        scan_delay = float(self.vars["minigame_scan_delay"] or 0.05)
        lock_cursor = (self.vars["lock_cursor"])
        dual_fishing = (self.vars["dual_fishing"]).lower()
        fishing_mode = (self.vars["fishing_mode"])
        minigame_controller_mode = self.vars["controller_mode"].lower()

        metronome_fishing = self.vars["metronome_fishing"]
        lullaby_metronome_ratio = float(self.vars["lullaby_metronome_ratio"])
        lullaby_fishing_ratio = float(self.vars["lullaby_fishing_ratio"])
        # Utility Settings
        catch_success = True
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_area_center = int((fish_right - fish_left) / 2) + fish_left
        scale = self._get_scale_factor()
        deadzone_action = 0
        canvas_offset = 0
        # Cache variables for detection stability
        detection_cache = {
            'last_valid_bar_left': None,
            'last_valid_bar_right': None,
            'last_valid_bar_center': None,
            'last_valid_bar_size': None,
            'last_valid_fish_x': None,
            'consecutive_failures': 0,
            'last_detection_time': 0,
            'estimation_mode': False
        }
        # Helper Functions
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
        # Start Capture Thread (with failsafe)
        _minigame_stop = self._start_capture(scan_delay)
        while self.macro_running:
            # Step 1: Grab Full Screen Then Crop (better on macOS)
            if not self._cap_event.wait(timeout=0.5):
                continue
            with self._cap_lock:
                frame = self._cap_frame
                self._cap_consumed_id = self._cap_frame_id
                self._cap_event.clear()
            if frame is None:
                _minigame_stop.set()
                self._set_fish_overlay_mode("idle")
                return catch_success
            # Step 2: Crop images based on dual fishing mode
            if dual_fishing == "on":
                # Fish images
                fish_img = frame[fish_top:fish_bottom, fish_left:fish_area_center]
                fish_img2 = frame[fish_top:fish_bottom, fish_area_center:fish_right]
                # Note images
                note_img = frame[shake_top:fish_bottom, fish_left:fish_area_center]
                note_img2 = frame[shake_top:fish_bottom, fish_area_center:fish_right]
                # Make sure to recalculate fish width
                fish_width = fish_area_center - fish_left
                fish_width2 = fish_right - fish_area_center
            elif metronome_fishing == "on":
                lullaby_metronome_pos = int((fish_bottom - fish_top) * lullaby_metronome_ratio)
                lullaby_fishing_top = int((fish_bottom - fish_top) * lullaby_fishing_ratio)
                # 1 fish 1 metronome 1 note image
                fish_img = frame[lullaby_fishing_top:fish_bottom, fish_left:fish_right]
                metronome_img = frame[fish_top:lullaby_fishing_top, fish_left:fish_right]
                note_img = frame[shake_top:fish_bottom, fish_left:fish_right]
            else:
                # 1 fish and 1 note image
                fish_img = frame[fish_top:fish_bottom, fish_left:fish_right]
                note_img = frame[shake_top:fish_bottom, fish_left:fish_right]
            # Keep 1 friend image
            friend_img = frame[friend_top:friend_bottom, friend_left:friend_right]
            # Step 3: Detection with caching
            self.fish_overlay.clear()
            # Left Side / Main Image
            if fishing_mode == "Line":
                fish_x, left_x, right_x = self._do_line_search(fish_img)
            else:
                fish_x, left_x, right_x = self._do_pixel_search(fish_img, fish_hex, left_bar_hex, right_bar_hex, fish_tol, left_tol, right_tol)
            # Middle Side / Metronome
            if metronome_fishing == "on":
                left_metronome = self._find_color_cluster(metronome_img, left_bar_hex, left_tol)
                right_metronome = self._find_color_cluster(metronome_img, right_bar_hex, right_tol)
                target_metronome = self._find_color_cluster(metronome_img, fish_hex, fish_tol)
                try:
                    target_metronome = target_metronome[0]
                    metronome_center_x = int((left_metronome[0] + right_metronome[0]) / 2)
                    metronome_center_y = int((left_metronome[1] + right_metronome[1]) / 2)
                except:
                    target_metronome = None
                    metronome_center_x = None
                    metronome_center_y = None
            # Right Side (Only Triggers If dual_fishing Is True)
            # Dual Fishing: LEFT (primary) is strong, RIGHT (secondary) is basic controls (no overlay)
            if dual_fishing == "on":
                if fishing_mode == "Line":
                    fish_x2, left_x2, right_x2 = self._do_line_search(fish_img2)
                else:
                    fish_x2, left_x2, right_x2 = self._do_pixel_search(fish_img2)
                arrow_indicator_x2 = self._find_first_pixel(fish_img2, arrow_hex, arrow_tol)
            arrow_indicator_x = self._find_first_pixel(fish_img, arrow_hex, arrow_tol)
            if track_notes == "on":
                note_coords = self._find_color_center(note_img, note_box_hex, note_box_tol)
            else:
                note_coords = None
            # Extract arrow x coordinate safely
            try:
                arrow_indicator_x = arrow_indicator_x[0]
            except (TypeError, IndexError):
                arrow_indicator_x = None
            # Step 4: Bar detection with cache fallback
            bar_size2 = 0
            if dual_fishing == "on": # Extra variables for secondary bar
                bar2_detected = (left_x2 is not None and right_x2 is not None)
            else:
                bar2_detected = False
            try:
                if bar2_detected:
                    bar_size2 = int(right_x2 - left_x2)
                    bar_center2 = left_x2 + (bar_size2 / 2)
                    detection_source2 = 0
                elif dual_fishing == "on":
                    left_x2 = arrow_indicator_x2
                    right_x2 = arrow_indicator_x2 + 30
                    bar_center2 = arrow_indicator_x2 + 15
                    detection_source2 = 1
                else:
                    bar_center2 = 0
                    left_x2 = 0
                    right_x2 = 0
            except:
                bar_center2 = 0
                left_x2 = 0
                right_x2 = 0
            bar_detected = (left_x is not None and right_x is not None)
            detection_source = 2
            if bar_detected:
                # Valid detection - update cache
                self._last_bar_left_x = left_x
                self._last_bar_right_x = right_x
                self._last_bar_center = (left_x + right_x) / 2.0
                self._last_bar_box_size = abs(right_x - left_x)
                detection_cache['consecutive_failures'] = 0
                detection_cache['estimation_mode'] = False
                bar_center = self._last_bar_center
                bar_size = self._last_bar_box_size
                detection_source = 0
                # Arrow estimation (Warm state)
                self._last_bar_box_size      = bar_size
                self.last_known_box_center_x = bar_center
                self.last_left_x             = left_x
                self.last_right_x            = right_x
            else:
                # Use cache
                detection_cache['consecutive_failures'] += 1
                if self._last_bar_left_x is not None:
                    # Use cached values if available
                    left_x = self._last_bar_left_x
                    right_x = self._last_bar_right_x
                    bar_size = self._last_bar_box_size
                    # Only estimate if arrow indicator exists and cache is stale
                    if arrow_indicator_x is not None and detection_cache['consecutive_failures'] > 3:
                        estimated_center, left_x, right_x = self._update_arrow_box_estimation(
                            arrow_indicator_x, mouse_down, fish_width
                        )
                        if estimated_center is not None:
                            bar_center = estimated_center
                            # Recalculate bar_size from the estimated edges so that
                            # thresh/deadzone are based on the actual span, not the
                            # stale last_valid_bar_size (which caused Size=231 while
                            # Right-Left=413 in the logs).
                            bar_size = abs(right_x - left_x)
                            # On the first frame entering estimation mode, the error
                            # derivative is meaningless: error was frozen for N stale
                            # frames then jumped when estimation fired.  Clear the
                            # D-term state for this one transition frame only.
                            if not detection_cache['estimation_mode']:
                                self._pid_last_scan_time = None
                            detection_cache['estimation_mode'] = True
                        else:
                            bar_center = self._last_bar_center
                    else:
                        bar_center = self._last_bar_center
                    detection_source = 1
                else:
                    # No cache available, try estimation
                    if arrow_indicator_x is not None:
                        bar_center, left_x, right_x = self._update_arrow_box_estimation(
                            arrow_indicator_x, mouse_down, fish_width
                        )
                        if bar_center is not None:
                            bar_size = abs(right_x - left_x) if right_x and left_x else 100
                            detection_source = 2
                        else:
                            bar_center = None
                            bar_size = 0
                    else:
                        bar_center = None
                        bar_size = 0
            # Step 5: Validate and sanitize detection results
            if dual_fishing == "on":
                if bar_center is not None and left_x is not None and right_x is not None:
                    # Ensure bar_size is positive and reasonable
                    bar_size = max(bar_size, 10)  # Minimum bar size
                    bar_size = min(bar_size, fish_width)  # Maximum bar size
                    deadzone_size = bar_size * bar_ratio
                    max_left = deadzone_size
                    max_right = (fish_area_center - fish_left) - deadzone_size
                    # Clamp max bounds
                    max_left = max(0, min(max_left, fish_width))
                    max_right = max(0, min(max_right, fish_width))
                else:
                    bar_size = 0
                    bar_center = None
                    max_left = fish_left
                    max_right = fish_area_center
                # Max Left and Right for second bar
                if bar_center2 is not None and left_x2 is not None and right_x2 is not None:
                    # Ensure bar_size is positive and reasonable
                    bar_size2 = max(bar_size2, 10)  # Minimum bar size
                    bar_size2 = min(bar_size2, fish_width)  # Maximum bar size
                    deadzone_size2 = bar_size2 * bar_ratio
                    max_left2 = deadzone_size2
                    max_right2 = (fish_right - fish_area_center) - deadzone_size2
                    # Clamp max bounds
                    max_left2 = max(0, min(max_left2, fish_width))
                    max_right2 = max(0, min(max_right2, fish_width))
                else:
                    bar_size2 = 0
                    bar_center2 = None
                    max_left2 = fish_area_center
                    max_right2 = fish_right
            else:
                if bar_center is not None and left_x is not None and right_x is not None:
                    # Ensure bar_size is positive and reasonable
                    bar_size = max(bar_size, 10)  # Minimum bar size
                    bar_size = min(bar_size, fish_width)  # Maximum bar size
                    deadzone_size = bar_size * bar_ratio
                    max_left = deadzone_size
                    max_right = (fish_right - fish_left) - deadzone_size
                    # Clamp max bounds
                    max_left = max(0, min(max_left, fish_width))
                    max_right = max(0, min(max_right, fish_width))
                else:
                    bar_size = 0
                    bar_center = None
                    max_left = fish_left
                    max_right = fish_right
            # Step 6: Update deadzone action counter
            deadzone_action = (deadzone_action + 1) % 4
            # Step 7: Calculate threshold
            thresh = 0
            thresh2 = 0
            if dual_fishing == "on":
                if bar_size2 > 0:
                    thresh2 = max(1, (1 - round((bar_size2 / fish_width2), 2)) * 8 * scale)
                else:
                    thresh2 = 5  # Default threshold
            else:
                if bar_size > 0:
                    thresh = max(1, (1 - round((bar_size / fish_width), 2)) * 8 * scale)
                else:
                    thresh = 5  # Default threshold
            # Step 8: Restart detection (using Friend Area)
            friend_x = self._find_color_center(friend_img, friend_color, friend_tol)
            if friend_x is not None:
                release_mouse()
                release_mouse(True)
                time.sleep(restart_delay)
                self._set_fish_overlay_mode("idle")
                return catch_success
            # Step 9: Special tracking logic
            if note_coords is not None and track_notes == "on" and bar_center is not None:
                note_screen_y_ratio = note_coords[1] / (fish_bottom - fish_top)
                if note_screen_y_ratio >= note_track_ratio:
                    fish_x = note_coords[0]
                    self._pid_last_target_x = fish_x
            # Update fish_x cache
            if fish_x is not None:
                self._pid_last_target_x = fish_x
            elif self._pid_last_target_x is not None:
                fish_x = self._pid_last_target_x
            # Step 10: Check if fish is within bounds
            if bar_center is not None and fish_x is not None and left_x is not None and right_x is not None:
                try:
                    if not (left_x <= fish_x <= right_x):
                        catch_success = False
                except TypeError:
                    pass
            # Step 11: Controller mode selection
            controller_mode = 0
            if bar_center is not None and fish_x is not None:
                if max_left is not None and fish_x <= max_left:
                    controller_mode = 4
                elif max_right is not None and fish_x >= max_right:
                    controller_mode = 3
                else:
                    if minigame_controller_mode == "steady":
                        controller_mode = 0
                    if minigame_controller_mode == "spammy":
                        controller_mode = 6
                    elif minigame_controller_mode == "normal":
                        controller_mode = 1
                    elif minigame_controller_mode == "predictive":
                        controller_mode = 5
                    if (track_notes == "on" or minigame_controller_mode == "predictive") and left_x is not None:
                        if not (left_x <= fish_x <= right_x):
                            controller_mode = 2
            controller_mode2 = 0
            try:
                if dual_fishing == "on" and  bar_center2 is not None and fish_x2 is not None:
                    if (track_notes == "on" or minigame_controller_mode == "predictive") and left_x2 is not None:
                        if not (left_x2 <= fish_x2 <= right_x2):
                            controller_mode2 = 2
                    else:
                        if max_left2 is not None and fish_x2 <= max_left2:
                            controller_mode2 = 4
                        elif max_right2 is not None and fish_x2 >= max_right2:
                            controller_mode2 = 3
                        elif minigame_controller_mode == "spammy":
                            controller_mode2 = 6
                        else:
                            controller_mode2 = 0
            except:
                controller_mode2 = 0
            # Step 12: Draw overlay if enabled
            if dual_fishing == "on":
                canvas_offset2 = 0 - abs(fish_area_center - fish_left)
                if self._is_fish_overlay_enabled() and bar_center is not None:
                    self.fish_overlay.draw(
                        bar_center=bar_center2, box_size=bar_size2,
                        color="green", canvas_offset=canvas_offset2,
                        show_bar_center=True
                    )
                    if max_left is not None:
                        self.fish_overlay.draw(
                            bar_center=max_left2, box_size=15,
                            color="lightblue", canvas_offset=canvas_offset2
                        )
                    if max_right is not None:
                        self.fish_overlay.draw(
                            bar_center=max_right2, box_size=15,
                            color="lightblue", canvas_offset=canvas_offset2
                        )
                    if fish_x is not None:
                        self.fish_overlay.draw(
                            bar_center=fish_x2, box_size=10,
                            color="red", canvas_offset=canvas_offset2
                        )
            if self._is_fish_overlay_enabled() and bar_center is not None:
                self.fish_overlay.draw(
                    bar_center=bar_center, box_size=bar_size,
                    color="green", canvas_offset=canvas_offset,
                    show_bar_center=True
                )
                if max_left is not None:
                    self.fish_overlay.draw(
                        bar_center=max_left, box_size=15,
                        color="lightblue", canvas_offset=canvas_offset
                    )
                if max_right is not None:
                    self.fish_overlay.draw(
                        bar_center=max_right, box_size=15,
                        color="lightblue", canvas_offset=canvas_offset
                    )
                if fish_x is not None:
                    self.fish_overlay.draw(
                        bar_center=fish_x, box_size=10,
                        color="red", canvas_offset=canvas_offset
                    )
            # Step 13: Controller logic
            controller_found = 1
            controller_found2 = 1
            if dual_fishing == "on" and bar_center2 is not None and fish_x2 is not None:
                controller_found2 = 1
                error2 = fish_x2 - bar_center2
                if controller_mode2 == 0 or controller_mode2 == 1 or controller_mode2 == 5:
                    control2 = self._steady_control2(error2, bar_center2)
                    controller_found2 = 0
                elif controller_mode2 == 6:
                    should_hold = self._spammy_control2(fish_x2, bar_center2, bar_size2)
                    if should_hold:
                        hold_mouse(True)
                    else:
                        release_mouse(True)
                    controller_found2 = 1
                elif controller_mode2 == 2:
                    control2 = error2
                    controller_found2 = 0
                elif controller_mode2 == 3:
                    hold_mouse(True)
                    controller_found2 = 1
                elif controller_mode2 == 4:
                    release_mouse(True)
                    controller_found2 = 1
            if bar_center is not None and fish_x is not None:
                error = fish_x - bar_center
                # Execute controller action
                if controller_mode == 0:  # PID (Steady)
                    control = self._steady_control(error, bar_center)
                    controller_found = 0
                elif controller_mode == 1:  # PID (Normal)
                    control = self._normal_control(error)
                    controller_found = 0
                elif controller_mode == 2:  # Simple Tracking
                    control = error
                    controller_found = 0
                elif controller_mode == 3:  # Force hold
                    hold_mouse()
                    controller_found = 1
                elif controller_mode == 4:  # Force release
                    release_mouse()
                    controller_found = 1
                elif controller_mode == 5:  # Predictive control
                    should_hold = self._predictive_control(
                        fish_x, bar_center, fish_left, fish_right, left_x, right_x
                    )
                    if metronome_fishing == "on":
                        pass
                    if should_hold:
                        hold_mouse()
                    else:
                        release_mouse()
                    controller_found = 1
                elif controller_mode == 6:  # Spammy
                    should_hold = self._spammy_control(fish_x, bar_center, bar_size)
                    controller_found = 1
                    if should_hold:
                        hold_mouse()
                    else:
                        release_mouse()
            if controller_found == 0:
                if -thresh <= control <= thresh:
                    release_mouse() if deadzone_action == 0 else hold_mouse()
                elif control > thresh:
                    hold_mouse()
                elif control < -thresh:
                    release_mouse()
            if dual_fishing == "on" and controller_found2 == 0:
                if -thresh2 <= control2 <= thresh2:
                    release_mouse(True) if deadzone_action == 0 else hold_mouse(True)
                elif control2 > thresh2:
                    hold_mouse(True)
                elif control2 < -thresh2:
                    release_mouse(True)
            time.sleep(scan_delay)
    def stop_macro(self, text="Macro Stopped"):
        self.macro_running = False
        self._fish_overlay_cast_bounds = None
        self._stop_active_capture(join_timeout=1.0)
        self._set_fish_overlay_mode("idle")
        self.set_status(text)
        try:
            window.show()
        except Exception:
            pass
# Check for version
def check_setup_guide():
    cleaned = 0 # Failsafe
    error_message = "You have downloaded PyWare Fishing for the first time."
    try:
        with open(os.path.join(UI_PATH, "app.js"), "r") as file:
            first_line = file.readline().strip()
            cleaned = first_line.replace("const APP_VERSION = ", "").replace('"', "").replace(";", "")
        if cleaned == APP_VERSION:
            show_setup_guide = False
        else:
            show_setup_guide = True
            if APP_VERSION > cleaned:
                error_message = f"""
    You have updated from version {cleaned} to version {APP_VERSION}.
    By default, macOS automatically resets the permissions after you update."""
            else:
                error_message = f"""
    The macro automatically updated from version {APP_VERSION} to version {cleaned}. 
    Please redownload the EXE from the Google Drive."""
    except:
        show_setup_guide = True
    return show_setup_guide, error_message
show_setup_guide, error_message = check_setup_guide()
if show_setup_guide == True:
    dialogue = SetupGuide(error_message)
    dialogue.mainloop()
show_setup_guide, error_message = check_setup_guide()
if show_setup_guide == False:
    # =========================
    # WINDOW
    # =========================
    api = Api()
    window = webview.create_window(
        "PyWare Fishing V4.21",
        os.path.join(UI_PATH, "index.html"),
        js_api=api,
        width=1000,
        height=700
    )
    def on_main_window_closed():
        """Clean shutdown for all background systems."""
        try:
            # Stop macro loop
            api.macro_running = False
        except:
            pass
        try:
            # Stop capture thread
            api._stop_active_capture(join_timeout=1.0)
        except:
            pass
        try:
            # Close area selector if open
            if hasattr(api, "area_selector") and api.area_selector:
                api.area_selector.close()
        except:
            pass
        try:
            # Close eyedropper if open
            if hasattr(api, "eyedropper") and api.eyedropper:
                api.eyedropper.close()
        except:
            pass
        try:
            # Close fish overlay if open
            if hasattr(api, "fish_overlay") and api.fish_overlay:
                api.fish_overlay.close()
        except:
            pass
        try:
            # Stop pynput listener
            if hasattr(api, "key_listener") and api.key_listener:
                api.key_listener.stop()
        except:
            pass
        try:
            # Close MSS instance for current thread
            if hasattr(api._thread_local, "sct"):
                api._thread_local.sct.close()
        except:
            pass
    # Attach shutdown handler
    window.events.closed += on_main_window_closed
    webview.start(gui="edgechromium")
