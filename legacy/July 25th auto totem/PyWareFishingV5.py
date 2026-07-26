# Imports
# GUI (Primary and fallback)
import webview
import customtkinter as ctk
from tkinter import messagebox
# Text parsing
import json
import re
# Misc
import traceback
import threading
import subprocess
import requests
import io
import time
import sys
import webbrowser
import os
import shutil
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
    from AppKit import NSScreen
elif sys.platform == "linux":
    from Xlib import X, XK, display as Xdisplay
    from Xlib.ext import xtest
# Mathematics and Detection
import cv2
import numpy as np
import mss
from pathlib import Path
# Define platform-specific constants
# All platforms
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
macro_running = False
macro_thread = None
APP_VERSION = 5.0
BETA_VERSION = 2
DEVELOPER = "Catman2608"
def get_macos_menu_offset():
    if sys.platform != "darwin":
        return 0

    try:
        screen = NSScreen.mainScreen()
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
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    LWA_ALPHA = 0x00000002
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
    def make_window_translucent(window, transparency):
        pass

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
    def make_window_translucent(window, transparency):
        pass

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
class AreaSelector:
    """
    Fullscreen transparent overlay implemented as a second pywebview window.
    The HTML canvas handles all drawing and drag/resize interaction.
    Python is only needed for:
      - supplying initial area data  (get_areas)
      - receiving live mouse status  (on_mouse_move)
      - receiving final saved areas  (save_areas)
    """
    def __init__(self, parent, shake_area, fish_area, friend_area, totem_area, callback):
        self.area_selector_file = os.path.join(UI_PATH, "area_selector.html")
        if not os.path.isfile(self.area_selector_file):
            return

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
            self._win = webview.create_window("Area Selector", self.area_selector_file, js_api=self, 
                                              transparent=False, frameless=True, easy_drag=False, 
                                              on_top=True, resizable=False, width=SCREEN_WIDTH, height=SCREEN_HEIGHT,
                                               x=SCREEN_LEFT, y=SCREEN_TOP, background_color="#000000")
            # Maximize on Windows after the window is created
            def maximize_area_selector():
                try:
                    hwnd = _get_hwnd(self._win)
                    if hwnd:
                        user32.ShowWindow(wintypes.HWND(hwnd), SW_MAXIMIZE)
                except Exception as e:
                    print("Failed to maximize area selector:", e)
            self._win.events.shown += maximize_area_selector
        else:
            self._win = webview.create_window("Area Selector", self.area_selector_file, js_api=self, 
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
                "y": pixels["y"] - menu_offset,# macOS adjustment
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
        # Define last_xr and last_yr
        last_xr = 0
        last_yr = 0
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
                if not last_xr == xr or last_yr == yr:
                    self.parent.set_status(f"Coords: {xr}, {yr}")
                last_xr = xr
                last_yr = yr
                return

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
        self.last_picked_color = None
        self._cancelled = False
        self._scale = self.parent._get_scale_factor()
        self._win_origin_x = SCREEN_LEFT
        self._win_origin_y = SCREEN_TOP
        
        # Capture desktop before overlay appears (single frame, does not touch macro_running)
        self._screen_capture = self.parent.capture_single_frame()
            
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
        if not self.is_open():
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
        
        try:
            self.parent.set_status(f"{hex_color} • Click to pick • Esc to cancel")
        except Exception:
            pass

        return hex_color

    def window_ready(self, win_x, win_y):
        if sys.platform == "darwin":
            self._win_origin_x = 0
            self._win_origin_y = 0
        else:
            self._win_origin_x = int(win_x)
            self._win_origin_y = int(win_y)
    
    def pick_color(self, hex_color):
        """Called by JS when user clicks to pick a color."""
        if not self.is_open():
            return

        self.last_picked_color = hex_color
        self._cancelled = False
        self.parent.set_status(f"Picked color: {hex_color}")
        self._close_window()

    def close_eyedropper(self):
        """Called by JS when user presses Escape."""
        if not self.is_open():
            return

        self._cancelled = True
        self.parent.set_status("Eyedropper cancelled")
        self._close_window()

    def _on_closed(self, window=None):
        """Event handler for when the pywebview window is closed."""
        self._close_cleanup()
    
    def _close_window(self):
        """Internal method to close the window safely."""
        try:
            self._win.destroy()
        except Exception:
            pass
    
    def _close_cleanup(self):
        """Internal cleanup method called when window is closed."""
        # Set status message based on what happened
        if self.last_picked_color:
            self.parent.set_status(f"Picked color: {self.last_picked_color}")
        elif self._cancelled:
            self.parent.set_status("Eyedropper cancelled")
        else:
            self.parent.set_status("Eyedropper closed")

    def is_open(self):
        """Check if the eyedropper is still open."""
        return hasattr(self, '_win') and self._win is not None

    def close(self):
        """Force-close from Python during application shutdown."""
        if self.is_open():
            self._cancelled = False  # Don't show cancellation message
            self._close_window()

class FishOverlay:
    HTML_FILE = os.path.join(UI_PATH, "fish_overlay.html")
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.overlay_window = None  # Replaces self._win for consistency
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
        screen_w = max(1, int(SCREEN_WIDTH / scale))
        screen_h = max(1, int(SCREEN_HEIGHT / scale))
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

    def draw(self, bar_center, box_size, color, canvas_offset,
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
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
        self.current_rod_name = "Basic Rod"
        self.scale_x_1440 = self.SCREEN_WIDTH / 2560
        self.scale_y_1440 = self.SCREEN_HEIGHT / 1440
        # Screen Capture
        self.capture_thread = None
        self.capture_frame = None
        self.capture_id = 0
        self.scan_delay = 0.1
        # Other classes
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
        self.current_rod_name = "Basic Rod"
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
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
        shake_area  = self.bar_areas.get("shake")  if isinstance(self.bar_areas.get("shake"),dict) else default_shake_area()
        fish_area   = self.bar_areas.get("fish")   if isinstance(self.bar_areas.get("fish"), dict) else default_fish_area()
        friend_area = self.bar_areas.get("friend") if isinstance(self.bar_areas.get("friend"), dict) else default_friend_area()
        totem_area  = self.bar_areas.get("totem")  if isinstance(self.bar_areas.get("totem"),dict) else default_totem_area()
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
    # Debug Screenshots
    def take_debug_screenshot(self):
        """
        Capture all relevant areas (shake, fish, friend, totem, full)
        and save debug images.
        """
        shake_l, shake_t, shake_r, shake_b, _, _ = self.get_areas("shake")
        fish_l, fish_t, fish_r, fish_b, _, _ = self.get_areas("fish")
        friend_l, friend_t, friend_r, friend_b, _, _ = self.get_areas("friend")
        totem_l, totem_t, totem_r, totem_b, _, _ = self.get_areas("totem")
        full_img = self.capture_single_frame()
        if full_img is None:
            self.set_status("Full screen is empty")
            return

        # Save full screenshot for debugging
        try:
            cv2.imwrite(os.path.join(BASE_PATH, "debug_full.png"), full_img)
        except Exception as e:
            self.set_status(f"Error saving full screenshot: {e}")
            return

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

        self.set_status("Saved debug screenshots (fish, shake, friend, totem, full)")
    # Eyedropper
    def start_eyedropper(self):
        # Toggle Off If Already Open
        if hasattr(self, "eyedropper") and self.eyedropper and self.eyedropper.is_open():
            self.eyedropper.close()
            return

        # Create and show eyedropper
        self.eyedropper = Eyedropper(parent=self)
        self.set_status("Eyedropper opened • Hover to preview • Click to pick • Esc to cancel")
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
        b, g, r = self._hex_to_bgr(hex)
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
                    time.sleep(select_rod_duration)
                    self._send_key(rod_slot)
                    time.sleep(delay_after_casting / 2)
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
                            time.sleep(sundial_delay)
                            self.send_logging("**Sundial Success**", f"Cycle #{self.current_cycle}", "N/A")
                    self._send_key(target_slot)
                    time.sleep(totem_delay)
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

                    if shake_mode == "navigation":
                        self._send_key("enter")
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
            self.set_status("Macro Stopped")
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
        cast_duration = float(self._get_var_number("cast_duration", 0.5, float))
        self.hold_mouse(False)
        time.sleep(cast_duration)
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
        fish_left, fish_top, fish_right, fish_bottom, fish_width, _ = self.get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self.get_areas("friend")
        # Area Calculations
        note_height = fish_bottom - shake_top
        fish_overlay = self.vars["fish_overlay"]
        self.fish_overlay.resize(fish_left, fish_top, fish_right, fish_bottom)
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
                break

            # Fish detection
            fish_x, fish_y = self.pixel_search(fish_img, fish_color, fish_tolerance)
            if fish_x is not None:
                fish_detected = True
            else:
                fish_detected = False
            # Bar detection
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
            overlay_fish_color = "red"
            if fishing_profile == "notes":
                note_x, note_y = self.pixel_search(shake_img, tracking_color, tracking_tolerance)
                if note_x is not None and note_y is not None:
                    note_y_ratio = float(note_y / note_height)
                    if note_y_ratio > pinion_note_ratio:
                        fish_x = note_x
                        overlay_fish_color = "orange"
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
                self.fish_overlay.draw(
                    bar_center=bar_center, box_size=bar_size,
                    color="green", canvas_offset=0,
                    show_bar_center=True
                )
                if left_boundary is not None:
                    self.fish_overlay.draw(
                        bar_center=left_boundary, box_size=15,
                        color="lightblue", canvas_offset=0
                    )
                if right_boundary is not None:
                    self.fish_overlay.draw(
                        bar_center=right_boundary, box_size=15,
                        color="lightblue", canvas_offset=0
                    )
                if fish_x is not None:
                    self.fish_overlay.draw(
                        bar_center=fish_x, box_size=10,
                        color=overlay_fish_color, canvas_offset=0
                    )
            # Controller Mode Selection
            current_controller_mode = controller_mode
            if (left_x <= fish_x <= right_x) and controller_mode == "predictive":
                current_controller_mode = "normal"
            # PD controller
            current_time = time.perf_counter()
            time_delta = current_time - last_time
            last_time = current_time
            error = fish_x - bar_center
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

        self.fish_overlay.hide()

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