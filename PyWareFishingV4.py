# Imports
# GUI (Primary And Fallback)
import webview
import customtkinter as ctk
from tkinter import messagebox
# Text Parsing
import json
import re
# Misc
import traceback
import threading
import subprocess
import requests
import io
import base64
from collections import deque
import time
import sys
import webbrowser
import os
import shutil
import math
import random
from pathlib import Path
# Computer Vision
import cv2
import numpy as np
# Capture
if sys.platform == "win32":
    try:
        import dxcam
    except:
        dxcam = None
else:
    dxcam = None
import mss
# Keyboard And Mouse Clicks (Platform-specific)
from pynput.keyboard import Listener as KeyListener, Key
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
import ctypes
if sys.platform == "win32":
    from ctypes import wintypes
    try:
        import pygetwindow as gw
    except ImportError:
        gw = None
elif sys.platform == "darwin":
    import Quartz
    import AppKit
    from AppKit import NSScreen, NSWorkspace
elif sys.platform == "linux":
    from Xlib import X, XK, display as Xdisplay
    from Xlib.ext import xtest
# Check For OCR
try:
    import pytesseract
    possible = shutil.which("tesseract")
    if possible:
        pytesseract.pytesseract.tesseract_cmd = possible
except (ImportError, OSError):
    pytesseract = None
# Define Platform-Specific Constants
# All Platforms
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
APP_VERSION = 4.51
BETA_VERSION = 0
DEVELOPER = "Catman2608"

def _version_components(version):
    """Parse a dotted numeric version into comparable integer components."""
    parts = str(version).split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"Invalid app version: {version}")
    return tuple(int(part) for part in parts)

def load_misc_settings(last_config_path):
    try:
        with open(last_config_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data

    except:
        return {}

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

if sys.platform == "darwin":
    import Quartz
    _QUARTZ_SRGB_COLOR_SPACE = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    # Cache display P3 color space (what MSS typically returns on modern Macs)
    _QUARTZ_P3_COLOR_SPACE = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceDisplayP3)
else:
    _QUARTZ_SRGB_COLOR_SPACE = None
    _QUARTZ_P3_COLOR_SPACE = None
def mss_to_srgb_numpy(image, source_is_p3=True):
    """
    Convert an untagged raw MSS/Fastgrab frame buffer from Display P3 to sRGB
    using macOS native ColorSync engine for identical Quartz output.
    """
    if image is None or getattr(image, "ndim", 0) != 3 or image.shape[2] not in (3, 4):
        return image

    if sys.platform != "darwin" or not source_is_p3:
        bgr = image[:, :, :3]
        return bgr if bgr.flags["C_CONTIGUOUS"] else np.ascontiguousarray(bgr)

    height, width = image.shape[:2]
    # 1. Ensure input buffer is BGRA (4 channels required by CGDataProvider)
    if image.shape[2] == 3:
        bgra = np.empty((height, width, 4), dtype=np.uint8)
        bgra[:, :, :3] = image
        bgra[:, :, 3] = 255
    else:
        bgra = image
    # 2. Wrap raw NumPy buffer in CGImage tagged as Display P3
    bytes_per_row = width * 4
    provider = Quartz.CGDataProviderCreateWithData(None, bgra.tobytes(), len(bgra.tobytes()), None)
    src_cg_image = Quartz.CGImageCreate(
        width, height, 8, 32, bytes_per_row,
        _QUARTZ_P3_COLOR_SPACE,
        Quartz.kCGImageAlphaPremultipliedFirst | Quartz.kCGBitmapByteOrder32Little,
        provider, None, False, Quartz.kCGRenderingIntentDefault
    )
    # 3. Draw into an sRGB context (CoreGraphics handles exact ColorSync transformation)
    out_raw = np.empty((height, width, 4), dtype=np.uint8)
    context = Quartz.CGBitmapContextCreate(out_raw, width, height, 8, bytes_per_row, _QUARTZ_SRGB_COLOR_SPACE, Quartz.kCGImageAlphaPremultipliedLast | Quartz.kCGBitmapByteOrder32Big)
    Quartz.CGContextDrawImage(context, Quartz.CGRectMake(0, 0, width, height), src_cg_image)
    # 4. Extract BGR uint8 result matching Quartz/MSS consumers
    return np.ascontiguousarray(out_raw[:, :, :3][:, :, ::-1])

def cgimage_to_srgb_numpy(image):
    if sys.platform == "darwin":
        width = Quartz.CGImageGetWidth(image)
        height = Quartz.CGImageGetHeight(image)
        bytes_per_row = width * 4
        raw = np.empty((height, width, 4), dtype=np.uint8)
        context = Quartz.CGBitmapContextCreate(raw, width, height, 8, bytes_per_row, _QUARTZ_SRGB_COLOR_SPACE, Quartz.kCGImageAlphaPremultipliedLast | Quartz.kCGBitmapByteOrder32Big)
        if context is None:
            return None

        Quartz.CGContextDrawImage(context, Quartz.CGRectMake(0, 0, width, height), image)
        return raw[:, :, :3][:, :, ::-1]

    return image

def get_primary_work_area():
    """Return the usable primary screen area, excluding system UI."""
    try:
        # Windows
        if sys.platform == "win32":
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            rect = RECT()
            SPI_GETWORKAREA = 0x0030

            ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
            )

            return {
                "left": rect.left,
                "top": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
            }

        # macOS
        elif sys.platform == "darwin":
            screen = NSScreen.mainScreen()
            frame = screen.frame()
            visible = screen.visibleFrame()

            # Cocoa uses bottom-left origin; convert to top-left coordinates.
            return {
                "left": int(visible.origin.x),
                "top": int(frame.size.height - (visible.origin.y + visible.size.height)),
                "width": int(visible.size.width),
                "height": int(visible.size.height),
            }

        # Linux (X11)
        elif sys.platform.startswith("linux"):
            d = _get_xdisplay()
            root = d.screen().root

            workarea_atom = d.intern_atom("_NET_WORKAREA")
            prop = root.get_full_property(workarea_atom, X.AnyPropertyType)

            if prop and prop.value is not None and len(prop.value) >= 4:
                x, y, width, height = map(int, prop.value[:4])

                return {
                    "left": x,
                    "top": y,
                    "width": width,
                    "height": height,
                }

    except Exception:
        pass

    # Last-resort full-screen fallback
    return {
        "left": SCREEN_LEFT,
        "top": SCREEN_TOP,
        "width": SCREEN_WIDTH,
        "height": SCREEN_HEIGHT,
    }

# Reload
def reload_page(skip=True):
    if skip == False:
        return

    if sys.platform == "win32":
        # Wrap in quotes to prevent compilation issues
        args = [sys.executable, f'"{sys.argv[0]}"'] + sys.argv[1:]
        os.execv(sys.executable, args)
    else:
        # os.execv does not use a shell, so do not wrap the script path in quotes.
        # Extra quotes become part of the filename and fail on macOS/Linux.
        args = [sys.executable] + list(sys.argv)
        os.execv(sys.executable, args)
# MSS screen dimensions and attribute checking
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
# Windows (Transparency And Ctypes Windll)
if sys.platform == "win32":
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    # Ctypes GUI Constants
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
    # Set Dpi Awareness Early To Ensure Consistent Coordinate Handling
    try:
        windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_PER_MONITOR_DPI_AWARE
        # Dpi Awareness Successfully Set
    except:
        try:
            windll.user32.SetProcessDPIAware()  # Fallback for older Windows
            # Dpi Awareness Set (Fallback Method)
        except:
            pass  # DPI awareness could not be set - coordinates may be inconsistent

    # Windows Api Related Functions
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

# macOS (Keyboard, Scale Factor, Mouse Button, ScreenCaptureKit)
elif sys.platform == "darwin":
    # ScreenCaptureKit (preferred capture backend on macOS 12.3+)
    try:
        import ScreenCaptureKit as _SCK
        from collections import OrderedDict
        try:
            from Foundation import NSRunLoop
        except:
            NSRunLoop = None
        from ScreenCaptureKit import (SCShareableContent, SCContentFilter, SCStreamConfiguration, SCStream, SCStreamOutputType, SCStreamOutputTypeScreen)
        from Foundation import NSDate, NSObject
        import objc
        _SCK_AVAILABLE = True
        # PyObjC exposes the enum as a NewType. Cases are module constants
        # (SCStreamOutputTypeScreen == 0), not attributes of the NewType.
        _SCK_OUTPUT_SCREEN = SCStreamOutputTypeScreen
    except Exception as e:
        _SCK = None
        SCShareableContent = None
        SCContentFilter = None
        SCStreamConfiguration = None
        SCStream = None
        SCStreamOutputType = None
        NSDate = None
        NSObject = None
        objc = None
        _SCK_AVAILABLE = False
        _SCK_OUTPUT_SCREEN = 0
    _scale_cache = None
    MAC_KEY_MAP = {
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
        "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20,
        "4": 21, "6": 22, "5": 23, "equal": 24, "9": 25, "7": 26, "minus": 27, "-": 27, "8": 28, "0": 29, "o": 31,
        "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "quote": 39, "apostrophe": 39, "k": 40, "semicolon": 41, "comma": 43, "slash": 44, "n": 45,
        "m": 46, "period": 47, "space": 49, "return": 36, "enter": 76, "tab": 48, "backspace": 51, "delete": 51, "escape": 53,
        "command": 55, "cmd": 55, "shift": 56, "option": 58, "alt": 58, "control": 59, "ctrl": 59,
    }
    _QUARTZ_KEY_SOURCE = None

    def _get_quartz_key_source():
        # Private Source So Posted Keys Do Not Inherit Hardware Command/Fn/Globe State
        global _QUARTZ_KEY_SOURCE
        if _QUARTZ_KEY_SOURCE is None:
            _QUARTZ_KEY_SOURCE = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)
            try:
                Quartz.CGEventSourceSetLocalEventsSuppressionInterval(_QUARTZ_KEY_SOURCE, 0.0)
            except Exception:
                pass

        return _QUARTZ_KEY_SOURCE

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
    def _warp_mouse(x, y):
        """
        Instantly warps the mouse cursor to the given (x, y) coordinates
        without generating mouse-motion events.
        """
        # Define the target point
        point = Quartz.CGPointMake(float(x), float(y))
        event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft)
        # Warp the cursor
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    def _mouse_event(button="left", press=True, x=None, y=None):
        """Unified cross-platform mouse event.
        button: 'left'/'right'/'middle' or 1/2/3
        press=True → down, False → up
        """
        if x is None or y is None:
            x, y = get_mouse_position()
        # Map Button → (Quartz Button Constant, Down Event, Up Event)
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
        event = Quartz.CGEventCreateMouseEvent(None, event_type, Quartz.CGPointMake(float(x), float(y)), btn)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    def send_key(key, delay=0.05, click_type=0, flags=0):
        """
        Send a keyboard event.
        click_type:
            0 = click (press + release)   [default]
            1 = hold (press only)
            2 = release (release only)
        flags: Quartz modifier mask. Default 0 so Globe/Fn is never inherited.
        """
        keycode = MAC_KEY_MAP.get(str(key).lower())
        if keycode is None:
            return

        source = _get_quartz_key_source()
        def _post_key(down):
            event = Quartz.CGEventCreateKeyboardEvent(source, keycode, down)
            if event is None:
                return

            # Explicit Flags Only. A Null Source Inherits Combined Session Flags,
            # Often Including Globe/Fn. Two Letters Then Look Like A Double
            # Globe Tap And macOS Opens Siri / Type To Siri / Dictation.
            Quartz.CGEventSetFlags(event, flags or 0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        if click_type == 1:           # Hold (press only)
            _post_key(True)
        elif click_type == 2:         # Release only
            _post_key(False)
        else:                         # Click (press + release)
            _post_key(True)
            time.sleep(delay)
            _post_key(False)
    def send_hotkey(modifier, key, delay=0.05):
        """Modifier Down, Key Click With That Flag, Modifier Up."""
        flag_map = {
            "command": Quartz.kCGEventFlagMaskCommand,
            "cmd": Quartz.kCGEventFlagMaskCommand,
            "shift": Quartz.kCGEventFlagMaskShift,
            "option": Quartz.kCGEventFlagMaskAlternate,
            "alt": Quartz.kCGEventFlagMaskAlternate,
            "control": Quartz.kCGEventFlagMaskControl,
            "ctrl": Quartz.kCGEventFlagMaskControl,
        }
        flag = flag_map.get(str(modifier).lower(), 0)
        send_key(modifier, click_type=1, flags=flag)
        time.sleep(0.02)
        send_key(key, delay=delay, flags=flag)
        time.sleep(0.02)
        send_key(modifier, click_type=2, flags=0)
# Linux (Mouse Positions And Xdisplay)
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
        xtest.fake_input(d, X.ButtonPress if press else X.ButtonRelease, btn)
        d.sync()
    def send_key(key, delay=0.05, click_type=0):
        d = _get_xdisplay()
        keysym = XK.string_to_keysym(str(key))
        if keysym == 0:
            keysym = XK.string_to_keysym(str(key).lower())
        if keysym == 0:
            return

        keycode = d.keysym_to_keycode(keysym)
        if keycode == 0:
            return

        if click_type == 0:
            xtest.fake_input(d, X.KeyPress, keycode)
            d.sync()
            time.sleep(delay)
            xtest.fake_input(d, X.KeyRelease, keycode)
            d.sync()
        elif click_type == 1:
            xtest.fake_input(d, X.KeyPress, keycode)
            d.sync()
        elif click_type == 2:
            xtest.fake_input(d, X.KeyRelease, keycode)
            d.sync()
        else:
            xtest.fake_input(d, X.KeyPress, keycode)
            d.sync()
            time.sleep(delay)
            xtest.fake_input(d, X.KeyRelease, keycode)
            d.sync()

# Validate Tesseract Path
def get_tesseract_path(configured_path=None):
    """
    Return a valid Tesseract path for the current operating system.
    If an imported config contains a Tesseract path from another OS,
    automatically fall back to the current OS's Tesseract installation.
    """
    # 1. Try the path stored in the config first
    if configured_path:
        try:
            configured_path = str(configured_path).strip().strip('"')
            if Path(configured_path).is_file():
                return configured_path

        except (OSError, ValueError, TypeError):
            pass

    # 2. Check if Tesseract is already available in PATH
    detected = shutil.which("tesseract")
    if detected:
        return detected

    # 3. Check common paths for the CURRENT operating system
    if sys.platform == "win32":
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    elif sys.platform == "darwin":
        possible_paths = [
            "/opt/homebrew/bin/tesseract",   # Apple Silicon Homebrew
            "/usr/local/bin/tesseract",      # Intel Homebrew
        ]
    else:
        # Linux
        possible_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]
    for path in possible_paths:
        if Path(path).is_file():
            return path

    # Nothing found
    return None

def _schedule_webview_destroy(win, after=None, delay=0.05):
    """Destroy a pywebview window after the current JS/GUI call returns.
    Calling Window.destroy() from that window's js_api deadlocks pywebview
    (the bridge waits for destroy; destroy waits for the bridge). The stall
    freezes every other window too. Tear windows down from a short-lived
    thread instead.
    """
    if win is None:
        if after:
            try:
                after()
            except Exception:
                pass

        return

    def _destroy():
        if delay:
            time.sleep(delay)
        try:
            win.destroy()
        except Exception:
            pass

        if after:
            try:
                after()
            except Exception:
                pass

    threading.Thread(target=_destroy, daemon=True).start()
# Config Management
# Config management
def get_base_path():
    """Unified base directory for app data."""
    if not BETA_VERSION == 0:
        beta = "beta"
    else:
        beta = ""
    if getattr(sys, 'frozen', False):
        compiled = True
        # Compiled App → Use User Directory
        if sys.platform == "darwin":
            return os.path.join(

                os.path.expanduser("~"),
                "Library", "Application Support",
                "PyWareFishingV4", beta
            ), compiled
        elif sys.platform == "win32":
            return os.path.join(

                os.path.expanduser("~"),
                "AppData", "Roaming",
                "PyWareFishingV4", beta
            ), compiled
        else:
            return os.path.join(os.path.expanduser("~"), "PyWareFishingV4"), compiled

    compiled = False
    # Dev Mode → Project Directory
    return os.path.dirname(os.path.abspath(__file__)), compiled

# Establish the global base path for PyWare Fishing V4
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
# Central Area Definitions.  To Add A New Selectable Area:
# 1. Add An Entry Below (Key, Color, Label, Default Ratios 0-1).
# 2. That'S It — Selector Ui, Save/Load, Defaults, And The Show/Hide Menu
#      all pick it up automatically.  Use get_areas("your_key") later if needed.
AREA_CONFIG = {
    "shake": {
        "color": "#df0000",
        "label": "Shake Box",
        "default": {"x": 0.1041, "y": 0.0935, "width": 0.7917, "height": 0.7058},
    },
    "fish": {
        "color": "#00beff",
        "label": "Fish Box",
        "default": {"x": 0.2844, "y": 0.8377, "width": 0.4297, "height": 0.0376},
    },
    "fish_1_bellona": {
        "color": "#00beff",
        "label": "Fish Box 1 (Bellona)",
        "default": {"x": 0.0817, "y": 0.8488, "width": 0.3953, "height": 0.0404},
    },
    "fish_2_bellona": {
        "color": "#ff9b00",
        "label": "Fish Box 2 (Bellona)",
        "default": {"x": 0.5140, "y": 0.8488, "width": 0.3953, "height": 0.0404},
    },
    "fish_tranquility": {
        "color": "#00beff",
        "label": "Fish Box (Tranquility)",
        "default": {"x": 0.3119, "y": 0.1969, "width": 0.377, "height": 0.6561},
    },
    "friend": {
        "color": "#ffed00",
        "label": "Friend Box (Fish End)",
        "default": {"x": 0.0046, "y": 0.9031, "width": 0.0355, "height": 0.085},
    },
    "totem": {
        "color": "#00de07",
        "label": "Totem Box (Day/Night)",
        "default": {"x": 0.9493, "y": 0.8687, "width": 0.0234, "height": 0.0509},
    },
    "lullaby": {
        "color": "#7b00ff",
        "label": "Lullaby Box (Above Fish)",
        "default": {"x": 0.4222, "y": 0.7327, "width": 0.1556, "height": 0.1415},
    },
    "chat": {
        "color": "#ff008c",
        "label": "Chat Box",
        "default": {"x": 0.0030, "y": 0.0683, "width": 0.2536, "height": 0.3323},
    },
    "appraisal_hotbar": {
        "color": "#00beff",
        "label": "Hotbar Box (Appraisal)",
        "default": {"x": 0.5529, "y": 0.8905, "width": 0.0373, "height": 0.0619},
    },
    "enchantment": {
        "color": "#ffed00",
        "label": "Enchantment Box (Text)",
        "default": {"x": 0.3061, "y": 0.3932, "width": 0.3649, "height": 0.1674},
    },
    "angler_quest": {
        "color": "#00de07",
        "label": "Quest Box (Angler)",
        "default": {"x": 0.0139, "y": 0.5006, "width": 0.2316, "height": 0.1276},
    },
}
# Display / Iteration Order (Also Used For Numberkey Toggles 1-9 In The Selector)
AREA_ORDER = list(AREA_CONFIG.keys())
class AreaSelector:
    # Do not expose to JS API — holds pywebview Window (native.AccessibilityObject recursion / WebView2 COM).
    _serializable = False
    HTML_FILE = os.path.join(UI_PATH, "area_selector.html")
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.overlay_window = None  
        self._open = False
        self._visible = False
        self._areas = {}
        self._visible_areas = {}
        self._screen_capture = None
        self._screenshot_b64 = None
        self._page_ready = False
        self._pending_js = []
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
        Also clamps width/height so a bad (e.g. post-reset) size cannot make
        the overlay cover the entire screen or exceed monitor bounds.
        """
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        left = int(left)
        top = int(top)
        width = max(1, int(width))
        height = max(1, int(height))
        # SCREEN_* are physical pixels; window geometry is in logical points.
        screen_w = max(1, int(SCREEN_WIDTH * scale))
        screen_h = max(1, int(SCREEN_HEIGHT * scale))
        width = min(width, screen_w)
        height = min(height, screen_h)
        left = max(0, min(left, max(0, screen_w - width)))
        top = max(0, min(top, max(0, screen_h - height)))
        return left, top, width, height

    def show(self):
        """Creates and displays the transparent frameless overlay window.
        Arguments are physical-pixel screen coordinates (same space as _get_areas / capture_frame). They are converted to logical points
        for pywebview.
        """
        # Position below the macOS menu area; use physical pixels because
        # _to_window_coords converts its geometry to logical window points.
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        macos_offset = int(round(get_macos_menu_offset()))
        left, top, width, height = self._to_window_coords(0, macos_offset, SCREEN_WIDTH, max(1, SCREEN_HEIGHT - macos_offset))
        if self._open and self.overlay_window:
            # If already open, shift/resize it instead of duplicating
            self.resize(left, top, width, height, already_logical=True)
            return

        self._page_ready = False
        self._pending_js = []
        self._screen_capture = self._capture_and_crop()
        self._screenshot_b64 = self._encode_screenshot(self._screen_capture)
        self._view_w = float(width)
        self._view_h = float(height)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        # Thin js_api only. Do not pass self — it holds the pywebview Window,
        # and pywebview walks that into AccessibilityObject.Bounds recursion.
        outer = self
        class _AreaSelectorApi:
            def window_ready(self, win_x, win_y, width=None, height=None):
                return outer.window_ready(win_x, win_y, width, height)

            def get_screenshot_data(self):
                return outer.get_screenshot_data()

            def save_areas(self, areas):
                return outer.save_areas(areas)

        self.overlay_window = webview.create_window("Area Selector", self.HTML_FILE, js_api=_AreaSelectorApi(), transparent=False, frameless=True, easy_drag=False, on_top=True, resizable=False, focus=True, width=self.width, height=self.height, x=self.left, y=self.top, background_color="#000000", min_size=(10, 10))
        self._open = True
        self._visible = True
        self.overlay_window.events.closed += self._on_closed
        if sys.platform == "win32":
            def maximize_area_selector():
                try:
                    hwnd = _get_hwnd(self.overlay_window)
                    if hwnd:
                        user32.ShowWindow(wintypes.HWND(hwnd), SW_MAXIMIZE)
                except Exception as e:
                    try:
                        self.parent_app.set_status("Failed to maximize area selector:", e)
                    except Exception:
                        pass

            self.overlay_window.events.shown += maximize_area_selector
    def hide(self):
        """Destroys the current window instance completely.
        Clear _open BEFORE destroy so concurrent minigame threads that still
        call clear()/draw()/_eval skip the disposed WebView2 and avoid
        ObjectDisposedException (logged by pywebview as 'Error occurred in script').
        Destroy is scheduled off the JS-API thread to avoid pywebview deadlock.
        """
        win = self.overlay_window
        if not win or not self._open:
            self._open = False
            self._visible = False
            return

        self._open = False
        self._visible = False
        self.overlay_window = None
        _schedule_webview_destroy(win, after=self._on_closed)
    def window_ready(self, win_x, win_y, width=None, height=None):
        """JS signals the page is ready — record CSS client size and push screenshot.
        width/height are window.innerWidth / innerHeight (CSS pixels). Using
        these for box conversion fixes the off-screen drawing that happens
        when display scale ≠ 100% and SCREEN_* (physical) ≠ canvas size.
        """
        try:
            if width is not None and height is not None:
                w = float(width)
                h = float(height)
                if w > 0 and h > 0:
                    self._view_w = w
                    self._view_h = h
        except (TypeError, ValueError):
            pass

        if self._screenshot_b64 and self.overlay_window and self._open:
            # Inject Via A Short Data Reference; Js Stores It And Draws.
            try:
                # Pass As Return Value Of A Dedicated Getter Instead Of
                # Embedding A Huge String In Evaluate_Js When Possible.
                self.overlay_window.evaluate_js("window.__applyScreenshot && window.__applyScreenshot()")
            except Exception:
                pass

        self._page_ready = True
        self._flush_pending_js()
        return None

    def update(self, areas_dict, data):
        self.clear()
        scale = get_scale_factor() or 1.0
        if scale <= 0:
            scale = 1.0
        menu_offset_pixels = int(round(get_macos_menu_offset() * scale))
        self._visible_areas = {}
        visible_areas = []
        automation_mode = data["automation_mode"]
        special_rod = data["special_rod"]
        if automation_mode == "fishing":
            if special_rod == "bellona":
                visible_areas.append("fish_1_bellona")
                visible_areas.append("fish_2_bellona")
            elif special_rod == "tranquility":
                visible_areas.append("fish_tranquility")
            else:
                visible_areas.append("fish")
            if data["shake_mode"] != "navigation":
                if special_rod != "tranquility":
                    visible_areas.append("shake")
            if data["detection_method"] == "friend_area" or data["restart_method"] == "friend_area":
                visible_areas.append("friend")
            if data["auto_totem"] == True:
                visible_areas.append("totem")
            if data["hunt_detect"] == True:
                visible_areas.append("chat")
            elif special_rod == "lullaby":
                visible_areas.append("lullaby")
        elif automation_mode == "appraisal":
            visible_areas.append("appraisal_hotbar")
        elif automation_mode == "enchant":
            visible_areas.append("enchantment")
        elif automation_mode == "angler":
            visible_areas.append("angler_quest")
        for name in AREA_ORDER:
            area_data = (areas_dict or {}).get(name)
            if not isinstance(area_data, dict):
                # Unset: treat default as relative to the current Roblox window
                default = dict(AREA_CONFIG[name]["default"])
                try:
                    area_data = self.parent_app._map_relative_area_to_screen(default)
                except Exception:
                    area_data = default
            color = AREA_CONFIG[name]["color"]
            label = AREA_CONFIG[name].get("label", name)
            self._areas[name] = self.pixels_to_ratios(area_data)
            # Now draw the areas
            if name in visible_areas:
                self._visible_areas[name] = {"color": color, "label": label}
        # Convert ratios to logical canvas coordinates (CSS pixels).
        # SCREEN_WIDTH/HEIGHT are logical; menu_offset_pixels is physical and
        # must be converted to logical before subtracting from the canvas y.
        menu_offset_logical = menu_offset_pixels / scale
        boxes = {}
        for name, style in self._visible_areas.items():
            area = self._areas[name]
            boxes[name] = {
                "x": area["x"] * SCREEN_WIDTH,
                "y": area["y"] * SCREEN_HEIGHT - menu_offset_logical,
                "width": area["width"] * SCREEN_WIDTH,
                "height": area["height"] * SCREEN_HEIGHT,
                **style,
            }
        self._eval(f"window.fishOverlay && window.fishOverlay.setBoxes({json.dumps(boxes)})")
        # Draw cyan outline of the detected Roblox window (or full screen fallback)
        roblox = getattr(self.parent_app, "roblox_bounds", None)
        if roblox and isinstance(roblox, dict):
            try:
                left = float(roblox.get("left", 0) or 0)
                top = float(roblox.get("top", 0) or 0)
                width = float(roblox.get("width", 0) or 0)
                height = float(roblox.get("height", 0) or 0)
                # Same coordinate space as the area boxes (logical CSS pixels)
                roblox_js = {
                    "x": left,
                    "y": top - menu_offset_logical,
                    "width": width,
                    "height": height,
                    "color": "#00FFFF",
                    "label": "Roblox",
                }
                self._eval(f"window.fishOverlay && window.fishOverlay.setRobloxRect({json.dumps(roblox_js)})")
            except Exception:
                self._eval("window.fishOverlay && window.fishOverlay.setRobloxRect(null)")
        else:
            self._eval("window.fishOverlay && window.fishOverlay.setRobloxRect(null)")
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
                # Window may already be disposed (race with stop_macro / hide)
                self._open = False
                self.overlay_window = None
    def pixels_to_ratios(self, area):
        """Convert pixels to ratios by dividing values by screen width and height"""
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

    def clear(self):
        """Clears rendering elements inside the web view context."""
        self._eval("window.fishOverlay && window.fishOverlay.clear()")
    def get_screenshot_data(self):
        """Return the data-URL of the frozen (menu-bar-cropped) screenshot."""
        return self._screenshot_b64 or ""

    def save_areas(self, areas):
        """Persist the current canvas boxes as ratios relative to the Roblox window.
        0,0 = left/top of the cached Roblox bounds; 1,1 = width/height of the Roblox bounds.
        Also caches the Roblox window coordinates used for the conversion.
        Called from JS on Esc / F6 / beforeunload so changes are always written back.
        """
        if not isinstance(areas, dict):
            areas = {}
        scale = get_scale_factor() or 1.0
        if scale <= 0:
            scale = 1.0
        # menu_offset is stored/used in logical units to match the canvas and
        # SCREEN_WIDTH/HEIGHT (which are logical).
        menu_offset_logical = get_macos_menu_offset()
        # Detect and cache the Roblox window bounds (falls back to full screen)
        try:
            roblox = self.parent_app.detect_roblox()
        except Exception:
            roblox = {"left": 0, "top": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}
        r_left = float(roblox.get("left", 0) or 0)
        r_top = float(roblox.get("top", 0) or 0)
        r_w = float(roblox.get("width", 0) or 0)
        r_h = float(roblox.get("height", 0) or 0)
        if r_w < 10 or r_h < 10:
            r_left, r_top, r_w, r_h = 0.0, 0.0, float(SCREEN_WIDTH), float(SCREEN_HEIGHT)
        self.parent_app.roblox_bounds_cache = {
            "left": r_left,
            "top": r_top,
            "width": r_w,
            "height": r_h,
        }
        self.parent_app.roblox_bounds = dict(self.parent_app.roblox_bounds_cache)
        for name, box in areas.items():
            if name not in self._areas or not isinstance(box, dict):
                continue

            # Canvas pixels → absolute screen position (undo menu offset on Y)
            abs_x = float(box.get("x", 0))
            abs_y = float(box.get("y", 0)) + menu_offset_logical
            abs_w = float(box.get("width", box.get("w", 0)))
            abs_h = float(box.get("height", box.get("h", 0)))
            # Convert absolute → relative to cached Roblox window
            rel_x = (abs_x - r_left) / r_w if r_w > 0 else 0.0
            rel_y = (abs_y - r_top) / r_h if r_h > 0 else 0.0
            rel_w = abs_w / r_w if r_w > 0 else 0.0
            rel_h = abs_h / r_h if r_h > 0 else 0.0
            self._areas[name] = {
                "x": rel_x,
                "y": rel_y,
                "width": rel_w,
                "height": rel_h,
            }
            self.parent_app.bar_areas[name] = dict(self._areas[name])
        self.parent_app.save_misc_settings()
        try:
            self.parent_app.set_status(f"Areas saved relative to Roblox ({int(r_left)}, {int(r_top)}, {int(r_w)}×{int(r_h)})")
        except Exception:
            pass

        self.hide()
    def request_save_and_close(self):
        """Ask the page to persist its current boxes before closing."""
        if not self._open or not self.overlay_window:
            return

        if not self._page_ready:
            self.hide()
            return

        self.overlay_window.evaluate_js("window.fishOverlay && window.fishOverlay.saveAndClose()")
    def draw(self, x1, y1, x2, y2, color, show_bar_center=False, label=""):
        """Evaluates JS drawing contexts based on calculations inside the viewport.
        bar_center / box_size / canvas_offset are in physical pixels relative to
        the fish capture region; they are converted to logical CSS pixels for
        the overlay canvas (which matches the logical window size).
        """
        # Ensure the overlay exists before trying to execute scripts on it
        if not self._open or not self.overlay_window:
            return

        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        shape = {
            "x1": int(x1 / scale),
            "y1": int(y1 / scale),
            "x2": int(x2 / scale),
            "y2": int(y2 / scale),
            "color": str(color),
            "show_bar_center": bool(show_bar_center),
            "label": str(label or "")
        }
        self._eval(f"window.fishOverlay && window.fishOverlay.draw({json.dumps(shape)})")
    def _eval(self, script):
        """Safely executes JavaScript strings within the running window environment.
        Calls made before the page is ready are queued — evaluate_js during
        create_window can fail and must not tear the overlay down (that was dropping the screenshot)."""
        if not (self.overlay_window and self._open):
            return

        if not self._page_ready:
            self._pending_js.append(script)
            return

        try:
            self.overlay_window.evaluate_js(script)
        except Exception:
            # Page may not be attached yet; keep the window and retry later.
            self._pending_js.append(script)
    def _flush_pending_js(self):
        if not (self.overlay_window and self._open and self._page_ready):
            return

        pending = self._pending_js
        self._pending_js = []
        for script in pending:
            try:
                self.overlay_window.evaluate_js(script)
            except Exception:
                self._pending_js.append(script)
    def _capture_and_crop(self):
        """Capture full screen and remove the macOS menu bar strip so the
        image matches the frameless window geometry (no menu bar)."""
        frame = self.parent_app.capture_single_frame()
        if frame is None:
            return None

        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3].copy()
        scale = get_scale_factor()
        macos_offset = get_macos_menu_offset()
        if scale <= 0:
            scale = 1.0
        self._scale = scale
        # Crop top (macOS menu bar) so canvas y=0 aligns with menu macos_offset
        menu_bar_pixels = int(round(macos_offset * scale))
        if 0 < menu_bar_pixels < frame.shape[0]:
            frame = frame[
                menu_bar_pixels:int(round(SCREEN_HEIGHT * scale)),
                0:int(round(SCREEN_WIDTH * scale)),
            ]
        frame = np.clip(frame.astype(np.int16) - 15, 0, 255).astype(np.uint8)
        return frame

    def _encode_screenshot(self, frame):
        """Encode BGR numpy frame as a JPEG data-URL for the canvas."""
        if frame is None:
            return None

        try:
            # Jpeg Keeps The Payload Small Enough For Evaluate_Js
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return None

            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return "data:image/jpeg;base64," + b64

        except Exception:
            return None

    def is_open(self):
        return self._open

    def _on_closed(self):
        """Internal callback cleaning lifecycle states upon execution exit."""
        self.overlay_window = None
        self._open = False
        self._visible = False
# Eyedropper Class
class Eyedropper:
    """
    Fullscreen transparent overlay for color picking using pywebview.
    Captures a frozen screenshot (menu bar cropped so it matches the frameless window), renders it in the canvas, and returns the picked color.
    """
    # Prevent Pywebview From Walking This Object When The Main Api Is Js_Api
    # (Window.Native.Accessibilityobject.Bounds Recursion / Webview2 Com).
    _serializable = False
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
            # Jpeg Keeps The Payload Small Enough For Evaluate_Js
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return None

            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return "data:image/jpeg;base64," + b64

        except Exception:
            return None

    def show(self, color_key=None):
        """Open the eyedropper overlay. Optional color_key is the settings
        field that should receive the picked color (e.g. 'fish_color').
        Thin js_api object — only exposes the methods the HTML page calls.
        Do NOT pass `self` (or any object that holds a reference to the pywebview Window): on macOS Cocoa that triggers infinite recursion
        via AccessibilityObject.Bounds (same crash previously fixed for AreaSelector).
        """
        if self._open and self.eyedropper_window:
            return

        outer = self
        class _EyedropperApi:
            def window_ready(self, win_x, win_y):
                return outer.window_ready(win_x, win_y)

            def get_screenshot_data(self):
                return outer.get_screenshot_data()

            def get_pixel_at(self, x, y):
                return outer.get_pixel_at(x, y)

            def pick_color(self, hex_color):
                return outer.pick_color(hex_color)

            def close_eyedropper(self):
                return outer.close_eyedropper()

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
        self.eyedropper_window = webview.create_window("Eyedropper", self.HTML_FILE, js_api=_EyedropperApi(), transparent=False, frameless=True, easy_drag=False, on_top=True, resizable=False, focus=True, width=self.width, height=self.height, x=self.left, y=self.top, background_color="#000000")
        self._open = True
        self._visible = True
        self.eyedropper_window.events.closed += self._on_closed
        if sys.platform == "win32":
            # Maximize On Windows After The Window Is Created
            def maximize_area_selector():
                try:
                    hwnd = _get_hwnd(self.eyedropper_window)
                    if hwnd:
                        user32.ShowWindow(wintypes.HWND(hwnd), SW_MAXIMIZE)
                except Exception as e:
                    self.parent.set_status("Failed to maximize area selector:", e)
            self.eyedropper_window.events.shown += maximize_area_selector
        try:
            self.parent.set_status("Eyedropper opened • Hover to preview • Click to pick • Esc to cancel")
        except Exception:
            pass

    def is_open(self):
        return self._open and self.eyedropper_window is not None

    def hide(self):
        """Destroy the overlay without freezing the GUI.
        pywebview deadlocks if destroy() runs on the same window whose JS
        bridge is still inside pick_color() / close_eyedropper(). That also
        stalls the main window ("not responding"). Clear flags immediately,
        then destroy on a short-lived thread so the JS call can return first.
        """
        win = self.eyedropper_window
        if not win or not self._open:
            self._open = False
            self._visible = False
            return

        self._open = False
        self._visible = False
        self.eyedropper_window = None
        _schedule_webview_destroy(win, after=self._on_closed)
    def close(self):
        """Alias used by shutdown / toggle paths."""
        self.hide()
    # ── Js Api Methods (Called From Eyedropper.Html) ──
    def window_ready(self, win_x, win_y):
        """JS signals the page is ready — push the frozen screenshot."""
        if self._screenshot_b64 and self.eyedropper_window and self._open:
            # Inject Via A Short Data Reference; Js Stores It And Draws.
            try:
                # Pass As Return Value Of A Dedicated Getter Instead Of
                # Embedding A Huge String In Evaluate_Js When Possible.
                self.eyedropper_window.evaluate_js("window.__applyScreenshot && window.__applyScreenshot()")
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
        # Write Into Settings Vars When A Target Key Was Provided
        color_key = self._color_key
        if color_key:
            try:
                self.parent.vars[color_key] = hex_color
            except Exception:
                pass

        # Notify The Main Webview So The Color Input Updates
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
            # Main Window Is The First Created Window
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
        # Keep Last_Picked_Color So The Main Ui Can Still Poll It
class FishOverlay:
    # Prevent Pywebview From Walking This Object When The Main Api Is Js_Api
    # (Window.Native.Accessibilityobject.Bounds Recursion / Webview2 Com).
    _serializable = False
    HTML_FILE = os.path.join(UI_PATH, "fish_overlay.html")
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self._overlay_window = None
        self._open = False
        self._visible = False
        # Track Active Viewport Geometry (Logical Points For Pywebview)
        self.left = 0
        self.top = 0
        self.width = 0
        self.height = 0
    def _to_window_coords(self, left, top, width, height):
        """
        Convert physical-pixel geometry (from _get_areas / capture) into the
        logical points pywebview expects for window x/y/width/height.
        On Windows scale is always 1; on macOS Retina it is typically 2.0.
        Also clamps width/height so a bad (e.g. post-reset) size cannot make
        the overlay cover the entire screen or exceed monitor bounds.
        """
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        left = int(left / scale)
        top = int(top / scale)
        width = max(1, int(width / scale))
        height = max(1, int(height / scale))
        # Clamp So The Window Stays Onscreen (Logical Screen Size)
        screen_w = max(1, SCREEN_WIDTH)
        screen_h = max(1, SCREEN_HEIGHT)
        width = min(width, screen_w)
        height = min(height, screen_h)
        left = max(0, min(left, max(0, screen_w - width)))
        top = max(0, min(top, max(0, screen_h - height)))
        return left, top, width, height

    def show(self, left, top, width, height):
        """Creates and displays the transparent frameless overlay window.
        Arguments are physical-pixel screen coordinates (same space as _get_areas / capture_frame). They are converted to logical points
        for pywebview.
        """
        left, top, width, height = self._to_window_coords(left, top, width, height)
        if self._open and self._overlay_window:
            # If Already Open, Shift/Resize It Instead Of Duplicating
            self.resize(left, top, width, height, already_logical=True)
            return

        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self._overlay_window = webview.create_window("Fish Overlay", url=self.HTML_FILE, transparent=False, frameless=True, easy_drag=False, on_top=True, resizable=False, focus=False, width=self.width, height=self.height, x=self.left, y=self.top, background_color="#ffffff", min_size=(0.03 * SCREEN_WIDTH, 0.05 * SCREEN_HEIGHT))
        self._open = True
        self._visible = True
        self._overlay_window.events.closed += self._on_closed
    def hide(self):
        """Destroys the current window instance completely.
        Clear _open BEFORE destroy so concurrent minigame threads that still
        call clear()/draw()/_eval skip the disposed WebView2 and avoid
        ObjectDisposedException (logged by pywebview as 'Error occurred in script').
        Destroy is scheduled off the caller thread so a stop/hotkey/shutdown
        path cannot deadlock pywebview the way Eyedropper/AreaSelector did.
        """
        win = self._overlay_window
        if not win or not self._open:
            self._open = False
            self._visible = False
            return

        self._open = False
        self._visible = False
        self._overlay_window = None
        _schedule_webview_destroy(win, after=self._on_closed)
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
        if self._overlay_window and self._open:
            try:
                self._overlay_window.move(self.left, self.top)
                self._overlay_window.resize(self.width, self.height)
            except Exception:
                # Window May Already Be Disposed (Race With Stop_Macro / Hide)
                self._open = False
                self._overlay_window = None
    def clear(self):
        """Clears rendering elements inside the web view context."""
        self._eval("window.fishOverlay && window.fishOverlay.clear()")
    def draw(self, x1, y1, x2, y2, color, show_bar_center=False):
        """Evaluates JS drawing contexts based on calculations inside the viewport.
        bar_center / box_size / canvas_offset are in physical pixels relative to
        the fish capture region; they are converted to logical CSS pixels for
        the overlay canvas (which matches the logical window size).
        """
        # Ensure The Overlay Exists Before Trying To Execute Scripts On It
        if not self._open or not self._overlay_window:
            return

        # Failsafe if shape is None
        if x1 is None:
            return

        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        shape = {
            "x1": int(x1 / scale),
            "y1": int(y1 / scale),
            "x2": int(x2 / scale),
            "y2": int(y2 / scale),
            "color": str(color),
            "show_bar_center": bool(show_bar_center)
        }
        self._eval(f"window.fishOverlay && window.fishOverlay.draw({json.dumps(shape)})")
    def _eval(self, script):
        """Safely executes JavaScript strings within the running window environment.
        Catches ObjectDisposedException (and any other failure) that can occur
        when the overlay is destroyed from another thread while the minigame
        loop is still drawing."""
        if not (self._overlay_window and self._open):
            return

        try:
            self._overlay_window.evaluate_js(script)
        except Exception:
            # Webview2 May Already Be Disposed; Mark Closed So We Stop Trying
            self._open = False
            self._overlay_window = None
    def _on_closed(self):
        """Internal callback cleaning lifecycle states upon execution exit."""
        self._overlay_window = None
        self._open = False
        self._visible = False
class StatusOverlay:
    # Prevent Pywebview From Walking This Object When The Main Api Is Js_Api.
    # Statusoverlay.Show() Runs During Api.__Init__, So Overlay_Window Is A Live
    # Window By The Time Create_Window(..., Js_Api=Api) Runs — That Is What
    # Produced Status_Overlay.Overlay_Window.Native.Accessibilityobject.Bounds
    # recursion and the WebView2 "must be accessed from the UI thread" errors.
    _serializable = False
    HTML_FILE = os.path.join(UI_PATH, "status_overlay.html")
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self._overlay_window = None
        self._open = False
        self._visible = False
        # Track Active Viewport Geometry
        # (Logical Points For Pywebview)
        self.left = 0
        self.top = 0
        self.width = 0
        self.height = 0
    def _to_window_coords(self, left, top, width, height):
        """
        Convert physical-pixel geometry into logical points
        for pywebview.
        On Windows scale is usually 1.
        On macOS Retina it is typically 2.0.
        """
        scale = get_scale_factor()
        if scale <= 0:
            scale = 1.0
        left = int(left / scale)
        top = int(top / scale)
        width = max(1, int(width / scale))
        height = max(1, int(height / scale))
        # Clamp Window Dimensions To Screen Bounds
        screen_w = max(1, SCREEN_WIDTH)
        screen_h = max(1, SCREEN_HEIGHT)
        width = min(width, screen_w)
        height = min(height, screen_h)
        left = max(0, min(left, max(0, screen_w - width)))
        top = max(0, min(top, max(0, screen_h - height)))
        return left, top, width, height

    def show(self, left, top, width, height):
        """
        Creates and displays the status overlay window.
        Arguments are physical-pixel screen coordinates.
        """
        left, top, width, height = self._to_window_coords(left, top, width, height)
        if self._open and self._overlay_window:
            self.resize(left, top, width, height, already_logical=True)
            return

        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self._overlay_window = webview.create_window("Status Overlay", url=self.HTML_FILE, transparent=False, frameless=True, easy_drag=False, on_top=True, resizable=False, focus=False, width=self.width, height=self.height, x=self.left, y=self.top, background_color="#000000", min_size=(0.1 * SCREEN_WIDTH, 0.1 * SCREEN_HEIGHT))
        self._open = True
        self._visible = True
        self._overlay_window.events.closed += self._on_closed
    def hide(self):
        """
        Destroys the current window instance completely.
        Scheduled so hide() from stop_macro / main-window close cannot
        deadlock the pywebview GUI thread.
        """
        win = self._overlay_window
        if not win or not self._open:
            self._open = False
            self._visible = False
            return

        self._open = False
        self._visible = False
        self._overlay_window = None
        _schedule_webview_destroy(win, after=self._on_closed)
    def resize(self, left, top, width, height, already_logical=False):
        """
        Resizes and moves the window dynamically.
        By default arguments are physical pixels.
        Pass already_logical=True when already converted.
        """
        if not already_logical:
            left, top, width, height = self._to_window_coords(left, top, width, height)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        if self._overlay_window and self._open:
            try:
                self._overlay_window.move(self.left, self.top)
                self._overlay_window.resize(self.width, self.height)
            except Exception:
                self._open = False
                self._overlay_window = None
    def set_title(self, title):
        """
        Updates the overlay title.
        """
        self._eval(f"window.statusOverlay && " f"window.statusOverlay.setTitle(" f"{json.dumps(str(title))})")
    def set_main_status(self, status):
        """
        Updates the main process/status label.
        """
        self._eval(f"window.statusOverlay && " f"window.statusOverlay.setMainStatus(" f"{json.dumps(str(status))})")
    def set_line(self, number, label, value):
        """
        Updates one of the four status lines.
        number must be 1, 2, 3, or 4.
        """
        if number not in (1, 2, 3, 4):
            raise ValueError("Status line number must be 1, 2, 3, or 4")

        self._eval(f"window.statusOverlay && " f"window.statusOverlay.setLine(" f"{number}, " f"{json.dumps(str(label))}, " f"{json.dumps(str(value))})")
    def set_status(self, title, main_status, line1, line2, line3, line4=None):
        """
        Updates the entire status overlay.
        Each line should be a (label, value) tuple.
        line4 is optional.
        """
        self.set_title(title)
        self.set_main_status(main_status)
        self.set_line(1, line1[0], line1[1])
        self.set_line(2, line2[0], line2[1])
        self.set_line(3, line3[0], line3[1])
        if line4 is not None:
            self.set_line(4, line4[0], line4[1])
    def clear(self):
        """
        Resets the status overlay to its default state.
        """
        self._eval("window.statusOverlay && " "window.statusOverlay.clear()")
    def _eval(self, script):
        """
        Safely executes JavaScript within the WebView.
        Prevents calls against a WebView that has already been destroyed.
        """
        if not (self._overlay_window and self._open):
            return

        try:
            self._overlay_window.evaluate_js(script)
        except Exception:
            self._open = False
            self._overlay_window = None
    def _on_closed(self):
        """
        Cleans lifecycle state when the window closes.
        """
        self._overlay_window = None
        self._open = False
        self._visible = False
class SetupGuide(ctk.CTk):
    def __init__(self, error, stealer, pirated_build):
        super().__init__()
        # Check if running on Windows
        ctk.set_appearance_mode("dark")
        self.title(f"PyWare Fishing V{APP_VERSION} (Setup Guide)")
        self.configure(fg_color="#05051b")
        self.button_fill = "#1a0935"
        self.button_outline = "#45306e"
        # Start hotkey listener at the beginning for macOS (only if needed)
        if not sys.platform == "win32":
            self.start_hotkey_listener()
        ctk.CTkLabel(
            self,
            text=f"PyWare Fishing V{APP_VERSION} (Setup Guide)",
            font=(ctk.CTkFont, 24, "bold")
        ).pack(pady=(20, 10))
        ctk.CTkLabel(
            self,
            text=(error),
            wraplength=500
        ).pack(pady=(0, 20))
        # Only show permissions text and buttons on macOS
        if pirated_build == True:
            self.geometry("600x400")
            self.configure(fg_color="#290000")
            self.button_fill = "#480102"
            self.button_outline = "#ed000e"
            ctk.CTkLabel( self, text=(f"Please take actions against {stealer} and " "download the official PyWare Fishing from Google Drive"), wraplength=500 ).pack(pady=(0, 20))
            ctk.CTkButton( self, text="Download Official Build", command=self.open_link("https://drive.google.com/drive/folders/1e9tZwDtAaiYKTVFeArjWTIuztLgLg88a"), 
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
            ctk.CTkButton( self, text="Upcoming Features", command=self.open_link("https://docs.google.com/document/d/1WwWWMR-eN-R-GO42IioToHpWTgiXkLoiNE_4NeE-GsU"), 
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
        elif not sys.platform == "win32":
            self.geometry("600x550")
            ctk.CTkLabel(self, text=( "Before starting the macro, grant permissions and " "copy the required folders into the PyWare Fishing directory."), wraplength=500).pack(pady=(0, 20))
            ctk.CTkButton(self, text="Accessibility Permissions", command=self.open_accessibility, 
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
            ctk.CTkButton(self, text="Input Monitoring", command=self.open_input_monitoring, 
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
            ctk.CTkButton(self, text="Screen Recording", command=self.open_screen_recording, 
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
            ctk.CTkLabel(self, text=("Move configs, images and UI into the PyWare Fishing folder."), wraplength=500 ).pack(pady=(5, 10))
            ctk.CTkButton(self, text="Open PyWare Fishing Folder", command=open_base_folder,
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
        else:
            self.geometry("600x450")
            # Windows-specific setup text
            ctk.CTkLabel(self, text=("Before starting the macro, copy the required " "folders into the PyWare Fishing directory."), wraplength=400 ).pack(pady=(0, 20))
            ctk.CTkLabel(
                self,
                text=(
                    "Do you want to do this automatically or move manually?\n\n"
                    "YES → Click Move Folder, PyWare does this process automatically.\n"
                    "NO → Move configs, images and UI manually into the PyWare Fishing folder."
                ),
                justify="left",
                wraplength=500
            ).pack(pady=(5, 10))
            ctk.CTkButton(self, text="Move Folder Automatically", command=self.move_folders,
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
            ctk.CTkButton(self, text="Open PyWare Fishing Folder", command=open_base_folder,
                          fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(pady=5)
        ctk.CTkButton(self, text="Quit", command=self.destroy,
                      fg_color=self.button_fill, border_color=self.button_outline, border_width=3, corner_radius=8).pack(side="bottom", pady=20)
    def open_link(self, url):
        """Open a URL in the default web browser."""
        return lambda: webbrowser.open(url)
    def move_folders(self):
        from tkinter import messagebox
        source = os.path.dirname(sys.executable)
        folders = {
            "configs": True,
            "images": False,
            "UI": False
        }
        os.makedirs(BASE_PATH, exist_ok=True)
        keep_configs = messagebox.askyesno(
            "Keep Configs?",
            "Do you want to keep your existing configs?\n\n"
            "Yes: Keep your configs and add new configs from this update.\n"
            "No: Replace configs with the new version."
        )
        for folder, is_config in folders.items():
            old = os.path.join(source, folder)
            new = os.path.join(BASE_PATH, folder)
            if not os.path.exists(old):
                continue

            # Configs
            if is_config:
                if keep_configs:
                    # Merge new configs
                    shutil.copytree(
                        old,
                        new,
                        dirs_exist_ok=True
                    )
                else:
                    # Replace configs
                    if os.path.exists(new):
                        shutil.rmtree(new)
                    shutil.copytree(old, new)
            # Images/UI
            else:
                if os.path.exists(new):
                    shutil.rmtree(new)
                shutil.copytree(old, new)
            # Remove old folder from EXE directory
            shutil.rmtree(old)
        messagebox.showinfo(
            "Migration Complete",
            "Files have been moved successfully."
        )
        self.destroy()
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
        if sys.platform == "darwin":
            return Quartz.AXIsProcessTrusted()

        else:
            return True

    def check_screen_recording(self):
        try:
            with MSS() as sct:
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
    def __init__(self):
        self.vars = {} # Save Entry Variables Here
        self.current_config = self.get_last_config()

        # Start Hotkey Listener
        self.hotkey_state = 0
        self.rebind_target = None
        try:
            self.key_listener = KeyListener(on_press=self.on_key_press)
            self.key_listener.daemon = True
            self.key_listener.start()
        except Exception as e:
            self.set_status(f"Key Listener error: {e}")
        # Store Screen Width And Height To Use Later
        self.SCREEN_SCALE = ((SCREEN_WIDTH / 1920) + (SCREEN_HEIGHT / 1080)) / 2
        # Macro State
        self.macro_running = False
        self.macro_thread = None
        # Screen Capture
        self.capture_thread = None
        self.capture_frame = None
        self.capture_id = 0
        self.scan_delay = 0.1
        # Utility Classes
        self.area_selector = AreaSelector(self)
        self.eyedropper = Eyedropper(self)
        self.fish_overlay = FishOverlay(self)
        self.status_overlay = StatusOverlay(self)
        # Safe Defaults Before Key Listener Starts (Will Be Overwritten By Load_Misc_Settings)
        self.js_version_info = {}
        scale = get_scale_factor()
        menu_offset = get_macos_menu_offset()
        self.bar_areas = {name: None for name in AREA_ORDER}
        self.roblox_bounds_cache = None
        self.current_rod_name = "Default"
        self.session_start = 0.0
        self.catch_rate = 0.0
        # Message box synchronization (custom banner)
        self.misc_settings = {}
        self._message_box_event = None
        self._message_box_result = None
        self.perfect_catch_rate = 0.0
        self.current_cycle = 0
        self.scale_x_1440 = SCREEN_WIDTH / 2560
        self.scale_y_1440 = SCREEN_HEIGHT / 1440
        self.scale_x_1080 = SCREEN_WIDTH / 1920
        self.scale_y_1080 = SCREEN_HEIGHT / 1080
        self.status_left = 20
        self.status_top = (menu_offset * scale) + 40
        self.status_right = (300 * scale * self.scale_x_1080)
        self.status_bottom = (230 * scale * self.scale_y_1080)
        self.status_overlay.hide()
    # Pywebview Configs
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
            "pinion_notes_color",
            "pinion_notes_tolerance",
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
                json.dump(config_data, f, indent=4)
            # Also reset the in-memory areas so they take effect immediately
            if hasattr(self, "bar_areas"):
                self.bar_areas = {}
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

    def message_box_javascript(self, message, clipboard_content):
        try:
            # Clean the error string so it doesn't break JavaScript execution syntax
            # We escape backslashes, single quotes, and newlines
            escaped_error = clipboard_content.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            # Construct the self-invoking JS code block
            js_code = f"""
            (function() {{
                let confirmed = confirm("{message}");
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

    def copy_to_clipboard(self, text):
        """Copy text to the system clipboard. Returns True on success."""
        if text is None:
            return False

        text = str(text)
        try:
            if sys.platform == "darwin":
                pasteboard = AppKit.NSPasteboard.generalPasteboard()
                pasteboard.clearContents()
                # NSPasteboardTypeString Is Preferred; Fall Back To Legacy Type Name
                paste_type = getattr(AppKit, "NSPasteboardTypeString", None) or AppKit.NSStringPboardType
                return bool(pasteboard.setString_forType_(text, paste_type))

            elif sys.platform == "win32":
                # Prefer Powershell Setclipboard For Reliable Unicode Support
                try:
                    completed = subprocess.run([ "powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())", ], input=text, text=True, capture_output=True, timeout=5)
                    if completed.returncode == 0:
                        return True

                except Exception:
                    pass

                # Fallback: Clip.Exe With Utf16Le
                try:
                    completed = subprocess.run(["clip"], input=text.encode("utf-16le"), capture_output=True, timeout=5)
                    return completed.returncode == 0

                except Exception:
                    return False

            else:
                # Linux: Try Xclip, Then Xsel
                payload = text.encode("utf-8")
                for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                    try:
                        completed = subprocess.run(cmd, input=payload, capture_output=True, timeout=5)
                        if completed.returncode == 0:
                            return True

                    except FileNotFoundError:
                        continue

                    except Exception:
                        continue

                return False

        except Exception:
            return False

    def get_error_line(self, lines):
        matches = re.findall(r'\bline\s+(\d+)\b', lines)

        if not matches:
            return None

        return int(matches[-1])

    def _get_scale_factor(self):
        return get_scale_factor()

    # Area Selector
    def open_area_selector(self):
        # Detect Roblox window (falls back to full-screen coordinates) and store for the overlay
        self.roblox_bounds = self.detect_roblox()
        # Build Current Areas From Bar_Areas Or Area_Config Defaults (All Keys, Including Appraisal)
        # If a Roblox cache exists, stored areas are relative and must be mapped onto the
        # current Roblox window (or full screen if not found) before rendering.
        self.status_overlay.hide()
        areas = {}
        use_relative = isinstance(getattr(self, "roblox_bounds_cache", None), dict)
        for name in AREA_ORDER:
            a = self.bar_areas.get(name)
            # Valid stored area: map if relative cache exists, else treat as absolute (legacy)
            if (isinstance(a, dict) and float(a.get("width", 0) or 0) > 0
                    and float(a.get("height", 0) or 0) > 0):
                if use_relative:
                    areas[name] = self._map_relative_area_to_screen(a)
                else:
                    areas[name] = dict(a)
            else:
                # Unset area: treat AREA_CONFIG default as relative to the current
                # Roblox window (falls back to full-screen when Roblox is not found).
                # This ensures defaults track the Roblox window instead of the full screen.
                default = dict(AREA_CONFIG[name]["default"])
                areas[name] = self._map_relative_area_to_screen(default)
        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.is_open():
            self.area_selector.request_save_and_close()
        else:
            self.area_selector.show()
            self.area_selector.update(areas, self.vars)
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

        visible_areas = []
        automation_mode = self.vars["automation_mode"]
        special_rod = self.vars["special_rod"]
        if automation_mode == "fishing":
            if special_rod == "bellona":
                visible_areas.append("fish_1_bellona")
                visible_areas.append("fish_2_bellona")
            elif special_rod == "tranquility":
                visible_areas.append("fish_tranquility")
            else:
                visible_areas.append("fish")
            if self.vars["shake_mode"] != "navigation":
                if special_rod != "tranquility":
                    visible_areas.append("shake")
            if self.vars["detection_method"] == "friend_area" or self.vars["restart_method"] == "friend_area":
                visible_areas.append("friend")
            if self.vars["auto_totem"] == True:
                visible_areas.append("totem")
            if self.vars["hunt_detect"] == True:
                visible_areas.append("chat")
            if self.vars["sovereign_recharge"] == True:
                visible_areas.append("sovereign")
            if special_rod == "noiseform":
                visible_areas.append("noiseform")
            elif special_rod == "lullaby":
                visible_areas.append("lullaby")
            elif special_rod == "stellarwave":
                visible_areas.append("stellarwave")
        elif automation_mode == "appraisal":
            visible_areas.append("appraisal_hotbar")
        elif automation_mode == "treasure_appraisal":
            visible_areas.append("treasure_appraisal")
        elif automation_mode == "enchant":
            visible_areas.append("enchantment")
        elif automation_mode == "angler":
            visible_areas.append("angler_quest")

        saved = ["full"]
        try:
            for name in AREA_ORDER:
                if name not in visible_areas:
                    continue
                left, top, right, bottom, _, _ = self.get_areas(name)
                # Clamp To Image Bounds
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

        self.set_status(f"Took a screenshot of {', '.join(saved)}")
    def _enumerate_windows(self):
        """Cross-platform window list (similar to SolarAutomateV3.refresh_windows).
        Returns a list of dicts with keys: title, exe, left, top, width, height.
        """
        windows = []
        if sys.platform == "win32":
            if gw is None:
                return windows

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            for window in gw.getAllWindows():
                title = window.title or ""
                hwnd = getattr(window, "_hWnd", None) or getattr(window, "_hwnd", None)
                exe = ""
                if hwnd:
                    try:
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                        if handle:
                            try:
                                size = wintypes.DWORD(260)
                                buf = ctypes.create_unicode_buffer(size.value)
                                if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                                    exe = os.path.basename(buf.value) or ""
                            finally:
                                kernel32.CloseHandle(handle)
                    except Exception:
                        exe = ""
                windows.append({ "title": title, "exe": exe, "left": int(getattr(window, "left", 0) or 0), "top": int(getattr(window, "top", 0) or 0), "width": int(getattr(window, "width", 0) or 0), "height": int(getattr(window, "height", 0) or 0), })
        elif sys.platform == "darwin":
            window_list = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListExcludeDesktopElements | Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
            for window in window_list or []:
                owner = window.get(Quartz.kCGWindowOwnerName, "") or ""
                title = window.get(Quartz.kCGWindowName, "") or ""
                bounds = window.get(Quartz.kCGWindowBounds, {}) or {}
                windows.append({ "title": title, "exe": owner, "left": int(bounds.get("X", 0) or 0), "top": int(bounds.get("Y", 0) or 0), "width": int(bounds.get("Width", 0) or 0), "height": int(bounds.get("Height", 0) or 0), })
        elif sys.platform.startswith("linux"):
            try:
                disp = _get_xdisplay()
                root = disp.screen().root
                NET_CLIENT_LIST = disp.intern_atom("_NET_CLIENT_LIST")
                NET_WM_NAME = disp.intern_atom("_NET_WM_NAME")
                NET_WM_PID = disp.intern_atom("_NET_WM_PID")
                UTF8_STRING = disp.intern_atom("UTF8_STRING")
                prop = root.get_full_property(NET_CLIENT_LIST, X.AnyPropertyType)
                if prop:
                    for win_id in prop.value:
                        try:
                            window = disp.create_resource_object("window", win_id)
                        except Exception:
                            continue

                        title = ""
                        try:
                            net_name = window.get_full_property(NET_WM_NAME, UTF8_STRING)
                            if net_name and net_name.value:
                                raw = net_name.value
                                title = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                        except Exception:
                            pass

                        if not title:
                            try:
                                wm_name = window.get_wm_name()
                                if wm_name:
                                    title = wm_name if isinstance(wm_name, str) else str(wm_name)
                            except Exception:
                                pass

                        exe = ""
                        try:
                            pid_prop = window.get_full_property(NET_WM_PID, X.AnyPropertyType)
                            if pid_prop and pid_prop.value:
                                comm_path = f"/proc/{int(pid_prop.value[0])}/comm"
                                with open(comm_path, "r", encoding="utf-8") as comm:
                                    exe = comm.read().strip()
                        except Exception:
                            pass

                        left = top = width = height = 0
                        try:
                            geom = window.get_geometry()
                            width, height = geom.width, geom.height
                            try:
                                abs_coords = root.translate_coords(window, 0, 0)
                                left, top = abs_coords.x, abs_coords.y
                            except Exception:
                                left, top = geom.x, geom.y
                        except Exception:
                            pass

                        windows.append({ "title": title or "", "exe": exe, "left": int(left or 0), "top": int(top or 0), "width": int(width or 0), "height": int(height or 0), })
            except Exception:
                pass

        return windows

    def get_window_info(self, window_name):
        """Return (left, top, width, height) of the first matching window.
        Matches on title or process/owner name containing window_name (case-insensitive).
        Prefers larger windows when several match. Falls back to full screen if none found.
        Cross-platform (Windows / macOS / Linux), adapted from SolarAutomateV3 window finding.
        """
        name = (window_name or "").strip().lower()
        candidates = []
        try:
            for info in self._enumerate_windows():
                title = (info.get("title") or "").lower()
                exe = (info.get("exe") or "").lower()
                if name and (name in title or name in exe):
                    # Skip tiny / empty windows
                    if info.get("width", 0) < 50 or info.get("height", 0) < 50:
                        continue

                    candidates.append(info)
        except Exception:
            candidates = []
        if candidates:
            # Prefer windows whose title contains the name, then largest area
            def score(info):
                title = (info.get("title") or "").lower()
                area = (info.get("width") or 0) * (info.get("height") or 0)
                title_hit = 1 if name in title else 0
                return (title_hit, area)

            best = max(candidates, key=score)
            return best["left"], best["top"], best["width"], best["height"]

        # Fallback
        try:
            import pyautogui
            sw, sh = pyautogui.size()
        except Exception:
            sw, sh = getattr(self, "SCREEN_WIDTH", 1920), getattr(self, "SCREEN_HEIGHT", 1080)
        return 0, 0, abs(int(sw)), abs(int(sh))

    def detect_roblox(self):
        """Called from the Detect Roblox button. Prints and reports window bounds."""
        left, top, width, height = self.get_window_info("Roblox")
        if left == 0 and top == 0 and width == SCREEN_WIDTH and height == SCREEN_HEIGHT:
            # Fallback: primary monitor's usable work area
            work_area = get_primary_work_area()
            self.set_status(f"Detected Full Screen coordinates at {work_area}")
            return {
                "left": work_area["left"],
                "top": work_area["top"],
                "width": work_area["width"],
                "height": work_area["height"],
            }
        self.set_status(f"Detected Roblox window coordinates at {left}, {top}, {width}, {height}")
        return {"left": left, "top": top, "width": width, "height": height}

    # Point Select
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
            return str(key).replace("Key.", "").replace(" ", "").lower()

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
                # Guard to prevent area selector from being opened the second the macro started
                if self.macro_running == True:
                    return
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

    # Keyboard/Mouse Functions (Platformspecific)
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
            # Linux  Now Uses The Unified X11 Implementation
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
            # Linux - Now Uses The Unified X11 Implementation
            _mouse_event(button="right" if mouse else "left", press=False)
    # Click At
    def _click_at(self, x, y, click_count=1):
        if self.macro_running == False:
            return

        if x is None or y is None:
            return
        try:
            x = int(x)
            y = int(y)
        except:
            return

        # Convert Coordinates If Needed (Retina Scaling)
        if sys.platform == "darwin":
            scale = get_scale_factor()
            x = int(x / scale)
            y = int(y / scale)
        # Seperate Branches For Windows And macOS Mouse Events
        if sys.platform == "win32":
            windll.SetCursorPos(x, y)
            windll.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            for i in range(click_count):
                windll.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                windll.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                if i < click_count - 1:
                    time.sleep(0.03)
        else:
            try:
                _warp_mouse(x, y)
                _warp_mouse(x + 5, y + 5)
                _warp_mouse(x, y)
            except:
                _move_mouse(x, y)
                _move_mouse(x + 5, y + 5)
                _move_mouse(x, y)
            for i in range(click_count):
                _mouse_event(button="left", press=True)
                _mouse_event(button="left", press=False)
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
            # Convert Special Key Names
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
    def _type_text(self, text, per_char_delay=0.08):
        """Type A String As Individual Keys. Skips OCR Junk That Is Not In The Key Map."""
        if not text:
            return

        for char in str(text):
            if self.macro_running == False:
                return

            if char == " ":
                key = "space"
            elif char == "\n" or char == "\r" or char == "\t":
                continue

            else:
                key = char.lower()
                if sys.platform == "darwin" and key not in MAC_KEY_MAP:
                    continue

            self._send_key(key)
            time.sleep(per_char_delay)
    def _select_all_text(self):
        """Cmd+A On macOS, Ctrl+A Everywhere Else. Clears The Search Field Selection."""
        if sys.platform == "darwin":
            send_hotkey("command", "a")
        else:
            try:
                keyboard_controller.press(Key.ctrl)
                time.sleep(0.02)
                keyboard_controller.press("a")
                time.sleep(0.05)
                keyboard_controller.release("a")
                time.sleep(0.02)
                keyboard_controller.release(Key.ctrl)
            except Exception as e:
                print("Error sending select-all:", e)
    # Interruptible Sleep
    def interruptible_sleep(self, duration):
        duration = max(0.01, duration)
        end_time = time.perf_counter() + duration
        while True:
            if not self.macro_running:
                break  # Interrupted

            remaining = end_time - time.perf_counter()
            if remaining <= 0:
                break

            # Sleep For At Most 10Ms Or Whatever Fraction Of Remaining Time Is Left
            time.sleep(min(0.01, remaining))
    # Get Values
    def _map_relative_area_to_screen(self, area):
        """Convert one Roblox-relative area (0-1 within the Roblox window) into
        absolute screen ratios (0-1 of SCREEN_WIDTH/HEIGHT).
        Uses the currently detected Roblox window; falls back to full-screen
        coordinates when Roblox is not found.
        """
        if not isinstance(area, dict):
            return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}

        # Ensure we have current Roblox bounds (detect if missing)
        roblox = getattr(self, "roblox_bounds", None)
        if not isinstance(roblox, dict) or float(roblox.get("width", 0) or 0) < 10:
            try:
                roblox = self.detect_roblox()
                self.roblox_bounds = roblox
            except Exception:
                roblox = {"left": 0, "top": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}
        r_left = float(roblox.get("left", 0) or 0)
        r_top = float(roblox.get("top", 0) or 0)
        r_w = float(roblox.get("width", 0) or 0)
        r_h = float(roblox.get("height", 0) or 0)
        if r_w < 10 or r_h < 10:
            # Fallback to full screen
            r_left, r_top, r_w, r_h = 0.0, 0.0, float(SCREEN_WIDTH), float(SCREEN_HEIGHT)
        rel_x = float(area.get("x", 0))
        rel_y = float(area.get("y", 0))
        rel_w = float(area.get("width", area.get("w", 0)))
        rel_h = float(area.get("height", area.get("h", 0)))
        abs_x = r_left + rel_x * r_w
        abs_y = r_top + rel_y * r_h
        abs_w = rel_w * r_w
        abs_h = rel_h * r_h
        return {

            "x": abs_x / float(SCREEN_WIDTH) if SCREEN_WIDTH else 0.0,
            "y": abs_y / float(SCREEN_HEIGHT) if SCREEN_HEIGHT else 0.0,
            "width": abs_w / float(SCREEN_WIDTH) if SCREEN_WIDTH else 0.0,
            "height": abs_h / float(SCREEN_HEIGHT) if SCREEN_HEIGHT else 0.0,
        }
    def get_areas(self, area_key):
        """Apply scale factor.  Area values are ratios 0-1.
        If a Roblox bounds cache exists, stored areas are relative to the Roblox
        window and are mapped onto the current Roblox bounds (or full screen if Roblox is not found).  Otherwise they are treated as absolute screen ratios
        (legacy).  Returns physical pixels.
        """
        scale = get_scale_factor()
        area_data = self.bar_areas.get(area_key)
        use_relative = isinstance(getattr(self, "roblox_bounds_cache", None), dict)
        if (isinstance(area_data, dict) and float(area_data.get("width", 0) or 0) > 0
                and float(area_data.get("height", 0) or 0) > 0):
            if use_relative:
                mapped = self._map_relative_area_to_screen(area_data)
                left   = float(mapped["x"])
                top    = float(mapped["y"])
                width  = float(mapped["width"])
                height = float(mapped["height"])
            else:
                left   = float(area_data["x"])
                top    = float(area_data["y"])
                width  = float(area_data["width"])
                height = float(area_data["height"])
            right  = left + width
            bottom = top + height
        else:
            # Unset area: map the AREA_CONFIG default relative to the current Roblox
            # window so defaults follow Roblox instead of staying full-screen.
            default = AREA_CONFIG.get(area_key, {}).get("default") or {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
            mapped = self._map_relative_area_to_screen(default)
            left   = float(mapped["x"])
            top    = float(mapped["y"])
            width  = float(mapped["width"])
            height = float(mapped["height"])
            right  = left + width
            bottom = top + height
        left2   = int(left * scale * SCREEN_WIDTH)
        top2    = int(top * scale * SCREEN_HEIGHT)
        right2  = int(right * scale * SCREEN_WIDTH)
        bottom2 = int(bottom * scale * SCREEN_HEIGHT)
        width2  = int(width * scale * SCREEN_WIDTH)
        height2 = int(height * scale * SCREEN_HEIGHT)
        return left2, top2, right2, bottom2, width2, height2

    def _get_default_areas(self, area):
        """Return (left, top, right, bottom) as ratios 0-1 from AREA_CONFIG defaults.
        Must stay in ratio space so get_areas can apply scale * SCREEN_* once."""
        cfg = AREA_CONFIG.get(area)
        if cfg:
            d = cfg["default"]
            left   = float(d["x"])
            top    = float(d["y"])
            right  = left + float(d["width"])
            bottom = top + float(d["height"])
        else:
            left, top, right, bottom = 0.0, 0.0, 1.0, 1.0
        return left, top, right, bottom

    def _get_var_number(self, key, default, cast=float):
        """Returns a key from the GUI with Exception handling"""
        try:
            value = self.vars.get(key)
            if value is None:
                # Compatibility Mapping For 1600Plus Key Differences
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

    def _split_ratio(self, item, screen_coords=False):
        # Split
        splitted_items = item.replace(" ", "").split(",")
        try:
            x = float(splitted_items[0])
            y = float(splitted_items[1])
        except:
            x = 0.5
            y = 0.5
        if screen_coords == False:
            return x, y

        else:
            x_screen = int(x * SCREEN_WIDTH)
            y_screen = int(y * SCREEN_HEIGHT)
            return x_screen, y_screen

    # Detection
    def _hex_to_bgr(self, hex_color):
        "Convert hex color to BGR tuple for OpenCV."
        if hex_color is None or hex_color.lower() in ["none", "# None", ""]:
            return None

        hex_color = hex_color.lstrip('# ').strip()
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        if len(hex_color) == 6:
            try:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (b, g, r)  # Bgr Format For Opencv

            except ValueError:
                return None

        return None

    def _normalize_capture_size(self, frame):
        """Ensure the captured frame matches the physical pixel size expected by
        get_areas (SCREEN_* * scale). On macOS Retina, Quartz (kCGWindowImageDefault)
        and some ScreenCaptureKit configurations deliver the logical (point) size
        while area coordinates are scaled to physical pixels. Upscale when needed
        so crops line up. No-op when sizes already match.
        """
        if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
            return frame

        try:
            scale = get_scale_factor() or 1.0
            if scale <= 0:
                scale = 1.0
            expected_w = int(round(SCREEN_WIDTH * scale))
            expected_h = int(round(SCREEN_HEIGHT * scale))
            h, w = frame.shape[:2]
            if w == expected_w and h == expected_h:
                return frame

            # Only upscale/downscale when the ratio is close to an integer scale
            # (avoids accidental resizing of already-correct frames from other backends).
            if expected_w > 0 and expected_h > 0 and w > 0 and h > 0:
                return cv2.resize(frame, (expected_w, expected_h), interpolation=cv2.INTER_LINEAR)

        except Exception:
            pass

        return frame

    def capture_single_frame(self):
        """
        Capture a single full-screen frame without touching self.macro_running.
        Used by debug screenshots, eyedropper freeze, and Discord screenshot logging.
        """
        if sys.platform == "darwin":
            image = Quartz.CGWindowListCreateImage(Quartz.CGRectInfinite, Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID, Quartz.kCGWindowImageBestResolution)
            if image is None:
                return None

            return self._normalize_capture_size(cgimage_to_srgb_numpy(image))

        else:
            scale = get_scale_factor()
            with MSS() as sct:
                monitor = {
                    "top": 0,
                    "left": 0,
                    "width": int(SCREEN_WIDTH * scale),
                    "height": int(SCREEN_HEIGHT * scale),
                }
                return np.asarray(sct.grab(monitor))[:, :, :3]

    def capture_loop_mss(self):
        """Continuous capture loop for the macro (Windows fallback). Assumes self.macro_running is already True."""
        if not self.macro_running:
            return

        self.capture_id = 0
        scale = get_scale_factor()
        with MSS() as sct:
            monitor = {
                "top": 0,
                "left": 0,
                "width": int(SCREEN_WIDTH * scale),
                "height": int(SCREEN_HEIGHT * scale),
            }
            while self.macro_running:
                self.capture_frame = self._normalize_capture_size(np.asarray(sct.grab(monitor))[:, :, :3])
                self.capture_id += 1
                time.sleep(self.scan_delay)
    def capture_loop_quartz(self):
        """Continuous capture loop for the macro (macOS fallback). Assumes self.macro_running is already True."""
        if not self.macro_running:
            return

        self.capture_id = 0
        while self.macro_running:
            if sys.platform == "darwin":
                image = Quartz.CGWindowListCreateImage(Quartz.CGRectInfinite, Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID, Quartz.kCGWindowImageBestResolution)
            else:
                image = None
            if image is None:
                time.sleep(0.01)
                continue

            frame = cgimage_to_srgb_numpy(image)
            if frame is None:
                time.sleep(0.01)
                continue

            self.capture_frame = self._normalize_capture_size(frame)
            self.capture_id += 1
            time.sleep(self.scan_delay)

    def process_image_for_ocr(self, img):
        # Convert To Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Upscale
        gray = cv2.resize(gray,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
        # Adaptive Threshold Works Better With Different Text Colors
        binary = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,8)
        return binary

    def extract_number_from_text(self, text):
        """
        Extracts numeric value from OCR text, handling common issues.
        Returns None if no valid number is found.
        """
        # Clean Up Common OCR Artifacts
        cleaned = text.strip()
        # Replace Common OCR Mistakes (O > 0, L > 1, Etc.)
        cleaned = cleaned.replace('O', '0').replace('o', '0')
        cleaned = cleaned.replace('l', '1').replace('I', '1')
        # Find Number With Optional Decimal
        # This Pattern Handles: 0.5, .5, 100, 100.0, Etc.
        match = re.search(r'(\d+\.?\d*|\.\d+)', cleaned)
        if match:
            try:
                return float(match.group(1))

            except ValueError:
                return None

        return None

    def pixel_search(self, frame, hex, tolerance, scan_mode=0):
        """
        Searches for the first or last pixel based on mode.
        Scan mode 0: First pixel; Mode 1: Last pixel
        Uses the same per-channel tolerance box as _detect_fish_colors_in_frame:
        each BGR channel must be within [color - tolerance, color + tolerance].
        """
        if frame is None or frame.size == 0:
            return None, None

        if scan_mode not in (0, 1):
            raise RuntimeError("Invalid scan mode")

        # Convert tolerance to int, handling string inputs
        try:
            tolerance = int(tolerance)
        except (ValueError, TypeError):
            tolerance = 0
        # Failsafe: None Hex
        if hex is None:
            return None, None

        try:
            tolerance = int(np.clip(tolerance, 0, 255))
            b, g, r = self._hex_to_bgr(hex)
            # Same per-channel bounds as _detect_fish_colors_in_frame
            lower_bound = np.array([ max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance) ], dtype=np.uint8)
            upper_bound = np.array([ min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance) ], dtype=np.uint8)
            # cv2.inRange gives the same mask as the detection function
            mask = cv2.inRange(frame, lower_bound, upper_bound)
            coords = np.argwhere(mask > 0)
            if coords.size > 0:
                if scan_mode == 0:
                    y, x = coords[0]
                else:
                    y, x = coords[-1]
                return int(x), int(y)

        except:
            return None, None

        return None, None

    def pixel_search_upper(self, frame, hex, tolerance, scan_mode=0):
        """
        Searches for the first or last pixel based on mode.
        Scan mode 0: First pixel; Mode 1: Last pixel
        Uses one-sided per-channel tolerance matching _find_bar_edges:
        each BGR channel must be >= (color - tolerance).
        """
        if frame is None or frame.size == 0:
            return None, None

        if scan_mode not in (0, 1):
            raise RuntimeError("Invalid scan mode")

        # Convert tolerance to int, handling string inputs
        try:
            tolerance = int(tolerance)
        except (ValueError, TypeError):
            tolerance = 0
        # Failsafe: None Hex
        if hex is None:
            return None, None

        try:
            tol = int(np.clip(tolerance, 0, 255))
            b, g, r = self._hex_to_bgr(hex)

            # One-sided threshold like _find_bar_edges: channel >= (color - tol)
            lower_bound = np.array([
                max(0, b - tol),
                max(0, g - tol),
                max(0, r - tol),
            ], dtype=np.uint8)

            # Only lower bound is enforced; use 255 as the implicit upper bound
            mask = cv2.inRange(frame, lower_bound, np.array([255, 255, 255], dtype=np.uint8))

            coords = np.argwhere(mask > 0)
            if coords.size > 0:
                if scan_mode == 0:
                    y, x = coords[0]
                else:
                    y, x = coords[-1]
                return int(x), int(y)

        except:
            return None, None

        return None, None

    def pixel_search_lower(self, frame, hex, tolerance, scan_mode=0):
        """
        Searches for the first or last pixel based on mode.
        Scan mode 0: First pixel; Mode 1: Last pixel
        Uses one-sided per-channel tolerance (upper bound only):
        each BGR channel must be <= (color + tolerance).
        """
        if frame is None or frame.size == 0:
            return None, None

        if scan_mode not in (0, 1):
            raise RuntimeError("Invalid scan mode")

        # Convert tolerance to int, handling string inputs
        try:
            tolerance = int(tolerance)
        except (ValueError, TypeError):
            tolerance = 0
        # Failsafe: None Hex
        if hex is None:
            return None, None

        try:
            tol = int(np.clip(tolerance, 0, 255))
            b, g, r = self._hex_to_bgr(hex)

            # One-sided threshold (upper bound only): channel <= (color + tol)
            upper_bound = np.array([
                min(255, b + tol),
                min(255, g + tol),
                min(255, r + tol),
            ], dtype=np.uint8)

            # Only upper bound is enforced; 0 is the implicit lower bound
            mask = cv2.inRange(frame, np.array([0, 0, 0], dtype=np.uint8), upper_bound)

            coords = np.argwhere(mask > 0)
            if coords.size > 0:
                if scan_mode == 0:
                    y, x = coords[0]
                else:
                    y, x = coords[-1]
                return int(x), int(y)

        except:
            return None, None

        return None, None

    def pixel_search_all(self, img, color, tolerance, scan_mode=0, optimize_mode=0):
        color2 = self.vars[color]
        tolerance2 = self.vars[tolerance]
        left, right = self.pixel_search(img, color, tolerance, scan_mode)
        return left, right

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
        # Required_Fish_Pixels
        if frame is None:
            return None, None

        # Color Mask (Vectorized Like Your Fast Version)
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int16)
        frame_int = frame.astype(np.int16)
        tol = int(np.clip(tolerance, 0, 255))
        mask = np.all(np.abs(frame_int - target_bgr) <= tol, axis=2).astype(np.uint8)
        if not np.any(mask):
            return None, None

        # Connected Components (Cluster Detection)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return None, None  # Only Background

        # Skip Label 0 (Background)
        largest_label = None
        largest_area = 0
        for label in range(1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]
            if area > largest_area and area >= min_area:
                largest_area = area
                largest_label = label
        if largest_label is None:
            return None, None

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
            # Convert Bgr To Grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Scale Circle Detection Parameters Based On Resolution
            # Reference Values Are For 2560X1440 Resolution
            # Use Average Of Scale_X_1440 And Scale_Y_1440 For Uniform Circle Scaling
            scale_factor = (self.scale_x_1440 + self.scale_y_1440) / 2
            # Scale Parameters Proportionally To Resolution
            scaled_min_dist = int(150 * scale_factor)
            scaled_min_radius = int(50 * scale_factor)
            scaled_max_radius = int(300 * scale_factor)
            scaled_good_min_radius = int(50 * scale_factor)
            scaled_good_max_radius = int(120 * scale_factor)
            # Hough Circle Transform With Strict Parameters For Perfect Circles Only
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1,  # Inverse ratio of accumulator resolution
                minDist=scaled_min_dist,  # Increased distance between circles to avoid overlapping detections
                param1=100,   # Higher Canny threshold for edge detection
                param2=100,   # Much higher accumulator threshold - only perfect circles
                minRadius=scaled_min_radius,  # Larger minimum radius to ignore small false positives
                maxRadius=scaled_max_radius   # Maximum circle radius
            )
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                # Additional Filtering: Only Accept Circles With Good Radius Range For Shake Buttons
                good_circles = []
                for (x, y, r) in circles:
                    # Shake Buttons Are Typically 50120 Pixels Radius (Scaled)
                    if scaled_good_min_radius <= r <= scaled_good_max_radius:
                        good_circles.append((x, y, r))
                if good_circles:
                    # Return The Largest Good Circle (Most Likely To Be Shake Button)
                    largest_circle = max(good_circles, key=lambda c: c[2])
                    x, y, r = largest_circle
                    # print(f"    🔍 Circle detected at local ({x}, {y}) with radius {r} (scale: {scale_factor:.3f})")
                    return int(x), int(y)

            # Only Use Strict Houghcircles Detection - No Backup Methods To Avoid False Positives
            return None, None

        except Exception as e:
            self.set_status(f"    Error in circle detection: {e}")
            return None, None

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
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=scaled_min_dist, param1=100, param2=100, minRadius=scaled_min_radius, maxRadius=scaled_max_radius)
            if circles is None:
                return []

            circles = np.round(circles[0, :]).astype("int")
            # First Radius Filter
            good_circles = [
                (x, y, r)
                for (x, y, r) in circles
                if scaled_good_min_radius <= r <= scaled_good_max_radius
            ]
            if not good_circles:
                return []

            # Require Similar Sizes
            radii = [r for _, _, r in good_circles]
            median_radius = np.median(radii)
            # Allow ±15% Size Difference
            tolerance = median_radius * 0.15
            similar_circles = [
                (int(x), int(y))
                for (x, y, r) in good_circles
                if abs(r - median_radius) <= tolerance
            ]
            return similar_circles

        except Exception as e:
            self.set_status(f"    Error in circle detection: {e}")
            return []

    def _detect_lines_in_frame(self, frame, original_width=None):
        """
        Detect vertical lines in frame using Laplacian edge detection.
        Based on b.py line detection pipeline with brightness and density filtering.
        NLM denoising removed for 10x speedup (30 FPS -> 300 FPS).
        
        Frame is normalized to reference fish box dimensions (1035x43 at 2560x1440)
        for consistent detection across all resolutions. Line coordinates are scaled
        back to match the original frame dimensions.
        
        Returns list of x-coordinates of detected vertical lines.

        Args:
            frame: BGR image from dxcam/mss
            original_width: Original frame width before normalization (for coordinate scaling back)
        """
        try:
            # Get minimum line density from settings (configurable via GUI)
            MIN_LINE_DENSITY = self._get_var_number("fish_line_min_density", 0.8)
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
            # Keep only columns where at least MIN_LINE_DENSITY of pixels are above BRIGHTNESS_THRESHOLD
            height, width = laplacian.shape
            
            # Vectorized column density calculation (10x faster than Python loop)
            column_densities = np.sum(laplacian > BRIGHTNESS_THRESHOLD, axis=0) / height
            line_coordinates = np.where(column_densities >= MIN_LINE_DENSITY)[0].tolist()

            # Merge adjacent lines (consecutive x-coordinates) into single lines
            # Takes the middle position of each group of adjacent pixels
            # Lines must be within 2 pixels to be considered part of the same group
            if line_coordinates:
                merged_lines = []
                group_start = line_coordinates[0]
                group_end = line_coordinates[0]
                
                for i in range(1, len(line_coordinates)):
                    if line_coordinates[i] <= group_end + 2:
                        # Within 2 pixels, extend current group
                        group_end = line_coordinates[i]
                    else:
                        # Gap > 2 pixels detected, save current group's middle position
                        middle = (group_start + group_end) // 2
                        merged_lines.append(middle)
                        # Start new group
                        group_start = line_coordinates[i]
                        group_end = line_coordinates[i]
                
                # Don't forget the last group
                middle = (group_start + group_end) // 2
                merged_lines.append(middle)
                
                line_coordinates = merged_lines

            # Scale line coordinates back to original frame dimensions
            if width_scale != 1.0:
                line_coordinates = [int(x * width_scale) for x in line_coordinates]

            # REMOVED: Old limit of 5 lines - now handles any number of lines
            # The fish stage will intelligently pick the best 4 lines from any number detected

            return line_coordinates

        except Exception as e:
            print(f"    Error in line detection: {e}")
            return []

    def auto_crop_template(self, template, lower_white=200):
        """
        Crop padding from template using the same thresholding logic
        as your image_search function
        """
        # 1. Convert To Grayscale
        if len(template.shape) == 3:
            gray_temp = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            gray_temp = template
        # 2. Threshold To Find Only White/Bright Pixels (Same As Image_Search)
        _, thresh_temp = cv2.threshold(gray_temp, lower_white, 255, cv2.THRESH_BINARY)
        # 3. Find All White Pixels (The Actual Totem Content)
        coords = cv2.findNonZero(thresh_temp)
        # If No White Pixels Found, Return Original
        if coords is None:
            return template

        # 4. Get Bounding Box Of White Pixels
        x, y, w, h = cv2.boundingRect(coords)
        # 5. Crop The Original Template (Not The Thresholded Version)
        # To Preserve Color/Quality
        cropped = template[y:y+h, x:x+w]
        return cropped

    def image_search(self, screenshot, template, lower_white=200, threshold=0.8):
        # 1. Resize Screenshot (Assuming Template Is Already Resized)
        screenshot_cropped = self.auto_crop_template(screenshot)
        template_height, template_width, _ = template.shape # template_height
        screenshot_resized = cv2.resize(screenshot_cropped, (template_width, template_height))
        # 2. Convert Screenshot & Template To Grayscale
        gray_screen = cv2.cvtColor(screenshot_resized, cv2.COLOR_BGR2GRAY)
        gray_temp = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        # 3. Threshold Both Images So Only White/Bright Pixels Remain (255) And Rest Is Black (0)
        _, thresh_screen = cv2.threshold(gray_screen, lower_white, 255, cv2.THRESH_BINARY)
        _, thresh_temp = cv2.threshold(gray_temp, lower_white, 255, cv2.THRESH_BINARY)
        # 4. Perform Template Matching On Binary Masks
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
    def send_logging(self, text, loop_count):
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
            thread = threading.Thread(target=self._discord_screenshot_worker, args=(webhook_url, f"{text}\n", loop_count), daemon=True)
        elif logging_mode == "file":
            thread = threading.Thread(target=self._debug_log_worker, args=(text, loop_count), daemon=True)
        else:
            thread = threading.Thread(target=self._discord_text_worker, args=(webhook_url, f"{text}\n", loop_count), daemon=True)
        thread.start()
        thread.join()  # Wait for Discord/file log to finish before continuing
    def _format_duration(self, seconds):
        if seconds is None or seconds < 0:
            return "N/A"

        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h {m}m {s}s"

        if m > 0:
            return f"{m}m {s}s"

        return f"{s}s"

    def _build_discord_embed(self, message_prefix, loop_count, include_image=False):
        """Build a rich Discord embed matching the Cycle Checkpoint style."""
        clean_title = (message_prefix or "").replace("**", "").replace("\n", " ").strip()
        if not clean_title:
            clean_title = "Update"
        title = f"Solar Fishing | {clean_title}"
        # Extract a numeric cycle if present (e.g. "Cycle #1440" -> "1440")
        cycle_display = str(loop_count)
        m = re.search(r"#?\s*(\d+)", str(loop_count))
        if m:
            cycle_display = m.group(1)
        elif getattr(self, "current_cycle", 0):
            cycle_display = str(self.current_cycle)
        running = "N/A"
        if getattr(self, "session_start", None):
            running = self._format_duration(time.time() - self.session_start)
        catch_pct = int(getattr(self, "catch_rate", 0.0) * 100)
        perfect_pct = int(getattr(self, "perfect_catch_rate", 0.0) * 100)
        catch_display = f"{catch_pct}% | {perfect_pct}% Perfect"
        rod = getattr(self, "current_rod_name", None) or "Default"
        embed = {
            "title": title,
            "description": "**Fishing update**\nFishing session update",
            "color": 0x5865F2,
            "fields": [
                {"name": "Rod", "value": str(rod), "inline": False},
                {"name": "Current Cycle", "value": cycle_display, "inline": True},
                {"name": "Running time", "value": running, "inline": True},
                {"name": "Catch Rate", "value": catch_display, "inline": True},
            ],
            "footer": {"text": f"Solar Fishing V{APP_VERSION}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if include_image:
            embed["image"] = {"url": "attachment://screenshot.png"}
        return embed

    def _discord_text_worker(self, webhook_url, message_prefix, loop_count):
        """Worker function to send text webhook as a rich embed."""
        logging_name = self.vars["logging_name"]
        try:
            payload = {
                "username": logging_name,
                "embeds": [self._build_discord_embed(message_prefix, loop_count, include_image=False)],
            }
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code in (200, 204):
                self.set_status(f"Discord text sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord text failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending Discord text: {e}")
    def _discord_screenshot_worker(self, webhook_url, message_prefix, loop_count):
        logging_name = self.vars["logging_name"]
        try:
            if self.capture_frame is None:
                screenshot = self.capture_single_frame()
            else:
                screenshot = self.capture_frame
            if screenshot is None:
                self.set_status("Error: failed to capture screenshot for Discord")
                return

            # Ensure Bgr For Imencode (MSS Already Bgr; Quartz Conversion Is Bgr)
            if screenshot.shape[2] == 4:
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            _, buffer = cv2.imencode(".png", screenshot)
            img_byte_arr = io.BytesIO(buffer.tobytes())
            embed = self._build_discord_embed(message_prefix, loop_count, include_image=True)
            payload = {
                "username": logging_name,
                "embeds": [embed],
            }
            files = {"file": ("screenshot.png", img_byte_arr, "image/png")}
            response = requests.post(webhook_url, data={"payload_json": json.dumps(payload)}, files=files, timeout=15)
            if response.status_code in (200, 204):
                self.set_status(f"Discord screenshot sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord screenshot failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending Discord screenshot: {e}")
    def _debug_log_worker(self, text, loop_count):
        """Write debug logs to a text file."""
        try:
            # Use Base Path For Logs
            log_dir = BASE_PATH
            os.makedirs(log_dir, exist_ok=True)
            # Daily Log File
            log_file = os.path.join(log_dir, f"debug_{time.strftime('%Y-%m-%d')}.txt")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_entry = ("==========\n" f"🎣 {text}\n" f"🔄 {loop_count}\n" f"🕐 {timestamp}\n" "==========\n\n")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
            self.set_status(f"Debug log saved ({loop_count})")
        except Exception as e:
            self.set_status(f"Error writing debug log: {e}")
    def start_appraisal(self):
        # Validate Tesseract
        try:
            tesseract_path = get_tesseract_path(self.vars.get("tesseract_path"))
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                # Repair the imported config in memory
                self.vars["tesseract_path"] = tesseract_path
            else:
                raise RuntimeError("⚠️ Tesseract could not be found.")

            self.macro_running = True
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            result = self.message_box_javascript(f"""An error occured during appraisal.  Please copy the error and report the bug:\\n{e}\\n Would you like to copy the full crash log to your clipboard?""", "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            self.macro_running = False
            self.stop_macro(f"Appraisal error: {e}")
            return

        # Get Areas
        hotbar_left, hotbar_top, hotbar_right, hotbar_bottom, _, _ = self.get_areas("appraisal_hotbar")
        # Split Mutations (Sometimes It Contains , At The End)
        appraisal_mode = self.vars["appraisal_mode"].lower()
        appraisal_mutations = self.vars["appraisal_mutations"]
        appraisal_mutations_list = appraisal_mutations.split(",")
        # Delays
        appraisal_delay = float(self.vars["appraisal_delay"])
        # Configure appraisal delay
        # Defaults so the ratios are always bound (avoids UnboundLocalError)
        appraisal_x_ratio = 0.5
        appraisal_y_ratio = 0.5
        appraisal_x_ratio2 = 0.5
        appraisal_y_ratio2 = 0.5
        if appraisal_mode == "default":
            # Normal Appraisal
            raw_normal_appraisal_ratio = self.vars["normal_appraisal_click"]
            normal_appraisal_ratio = raw_normal_appraisal_ratio.replace(" ", "").split(",")
            try:
                appraisal_x_ratio = float(normal_appraisal_ratio[0])
                appraisal_y_ratio = float(normal_appraisal_ratio[1])
            except Exception:
                self.set_status("Warning: invalid normal_appraisal_click, using defaults")
        else:
            # Gamepass Appraisal
            raw_gamepass_appraisal_ratio = self.vars["gamepass_appraisal_click"]
            gamepass_appraisal_ratio = raw_gamepass_appraisal_ratio.replace(" ", "").split(",")
            try:
                appraisal_x_ratio = float(gamepass_appraisal_ratio[0])
                appraisal_y_ratio = float(gamepass_appraisal_ratio[1])
            except Exception:
                self.set_status("Warning: invalid gamepass_appraisal_click, using defaults")
            # Gamepass Appraisal 2
            raw_gamepass_appraisal_ratio2 = self.vars["gamepass_appraisal_click2"]
            gamepass_appraisal_ratio2 = raw_gamepass_appraisal_ratio2.replace(" ", "").split(",")
            try:
                appraisal_x_ratio2 = float(gamepass_appraisal_ratio2[0])
                appraisal_y_ratio2 = float(gamepass_appraisal_ratio2[1])
            except Exception:
                self.set_status("Warning: invalid gamepass_appraisal_click2, using defaults")
        appraisal_x = int(SCREEN_WIDTH * appraisal_x_ratio)
        appraisal_y = int(SCREEN_HEIGHT * appraisal_y_ratio)
        appraisal_x2 = int(SCREEN_WIDTH * appraisal_x_ratio2)
        appraisal_y2 = int(SCREEN_HEIGHT * appraisal_y_ratio2)
        # Other Calculations
        logging_cycle = int(self.vars["logging_cycle"])
        logging_mode = self.vars["logging_mode"].lower()
        attempts = 0.0
        # Main Loop
        time.sleep(0.1)
        if appraisal_mode == "default":
            self._send_key("e", 0.05)
        try:
            while self.macro_running:
                attempts = attempts + 1
                # Click
                if appraisal_mode == "default":
                    time.sleep(appraisal_delay)
                    self._click_at(appraisal_x, appraisal_y)
                else:
                    self._click_at(appraisal_x, appraisal_y)
                    time.sleep(appraisal_delay)
                    self._click_at(appraisal_x2, appraisal_y2)
                    time.sleep(appraisal_delay)
                    time.sleep(appraisal_delay)
                # Check If Dxcam Is Available
                if dxcam is not None:
                    self.capture_frame = self.camera.get_latest_frame()
                    self.capture_id = self.capture_id + 1
                fish = self.capture_frame[hotbar_top:hotbar_bottom, hotbar_left:hotbar_right]
                processed_img = self.process_image_for_ocr(fish)
                text = pytesseract.image_to_string(processed_img, config="--psm 7")
                for match in range(len(appraisal_mutations_list)):
                    # print("Requirements:", appraisal_mutations_list[match].lower().rstrip(",").replace(" ", ""))
                    # print("Text:", text.lower().rstrip(",").replace(" ", ""))
                    if appraisal_mutations_list[match].lower().rstrip(",").replace(" ", "") in text.lower().rstrip(",").replace(" ", ""):
                        self.stop_macro("Appraisal finished")
                if self.macro_running == False:
                    self.stop_macro("")
                if round(attempts) == attempts and logging_mode != "disabled":
                    if attempts == logging_cycle:
                        self.send_logging("**Attempts Checkpoint**", f"Attempt #{attempts}")
                    logging_cycle = logging_cycle + attempts
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            result = self.message_box_javascript(f"""An error occured during appraisal.  Please copy the error and report the bug:\\n{e}\\n Would you like to copy the full crash log to your clipboard?""", "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            self.macro_running = False
            self.stop_macro(f"Appraisal error: {e}")
            return

        self.set_status("Macro Stopped")
    def start_enchantment(self):
        # Validate Tesseract
        try:
            tesseract_path = get_tesseract_path(self.vars.get("tesseract_path"))
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                # Repair the imported config in memory
                self.vars["tesseract_path"] = tesseract_path
            else:
                raise RuntimeError("⚠️ Tesseract could not be found.")

            self.macro_running = True
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            result = self.message_box_javascript(f"""An error occured during enchantment. 
            Please copy the error and report the bug:\\n{e}\\n Would you like to copy the full crash log to your clipboard?""", "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            self.macro_running = False
            self.stop_macro(f"Enchantment error: {e}")
            return

        # Get Areas
        enchantment_left, enchantment_top, enchantment_right, enchantment_bottom, enchantment_width, enchantment_height = self.get_areas("enchantment")
        # Split Enchantments
        enchantment_mode = self.vars["enchantment_mode"].lower()
        enchant_enchants = self.vars["enchant_enchants"]
        enchant_enchants_list = enchant_enchants.split(",")
        # Positions
        enchantment_e_delay = float(self.vars["enchantment_e_delay"])
        enchantment_click_delay = float(self.vars["enchantment_click_delay"])
        enchantment_click_delay2 = float(self.vars["enchantment_click_delay2"])
        enchantment_click_delay3 = float(self.vars["enchantment_click_delay3"])
        enchantment_click_position = self.vars["enchantment_click_position"].replace(" ", "").split(",")
        try:
            enchantment_click_position_x = float(enchantment_click_position[0]) * SCREEN_WIDTH
            enchantment_click_position_y = float(enchantment_click_position[1]) * SCREEN_HEIGHT
        except:
            pass

        enchantment_click_position2 = self.vars["enchantment_click_position2"].replace(" ", "").split(",")
        try:
            enchantment_click_position_x2 = float(enchantment_click_position2[0]) * SCREEN_WIDTH
            enchantment_click_position_y2 = float(enchantment_click_position2[1]) * SCREEN_HEIGHT
        except:
            pass

        # Other Calculations
        logging_cycle = int(self.vars["logging_cycle"])
        logging_mode = self.vars["logging_mode"].lower()
        attempts = 0.0
        # Main Loop
        try:
            while self.macro_running:
                time.sleep(0.1)
                if enchantment_mode == "default":
                    self._send_key("e")
                    time.sleep(enchantment_e_delay)
                    self._click_at(enchantment_click_position_x, enchantment_click_position_y)
                    time.sleep(enchantment_click_delay)
                else:
                    self._click_at(enchantment_click_position_x, enchantment_click_position_y)
                    time.sleep(enchantment_click_delay)
                    self._click_at(enchantment_click_position_x2, enchantment_click_position_y2)
                    time.sleep(enchantment_click_delay2)
                # Check If Dxcam Is Available
                if dxcam is not None:
                    self.capture_frame = self.camera.get_latest_frame()
                    self.capture_id = self.capture_id + 1
                text = self.capture_frame[enchantment_top:enchantment_bottom, enchantment_left:enchantment_right]
                gray = self.process_image_for_ocr(text)
                text = pytesseract.image_to_string(gray, config="--psm 7")
                for match in range(len(enchant_enchants_list)):
                    # print("Requirements:", appraisal_mutations_list[match].lower().rstrip(",").replace(" ", ""))
                    # print("Text:", text.lower().rstrip(",").replace(" ", ""))
                    if enchant_enchants_list[match].lower().rstrip(",").replace(" ", "") in text.lower().rstrip(",").replace(" ", ""):
                        self.stop_macro("Enchantment finished")
                time.sleep(enchantment_click_delay3)
                if self.macro_running == False:
                    self.stop_macro("")
                if round(attempts) == attempts and logging_mode != "disabled":
                    if attempts == logging_cycle:
                        self.send_logging("**Attempts Checkpoint**", f"Attempt #{attempts}")
                    logging_cycle = logging_cycle + attempts
            self.set_status("Macro Stopped")
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            error_lines = full_error.splitlines()
            error_line = self.get_error_line(error_lines[1])
            result = self.message_box_javascript(f"""An error at line {error_line} occured.  Please copy the error and report the bug:\\n{e}\\n Would you like to copy the full crash log to your clipboard?""", "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            if IS_COMPILED == False:
                print(full_error)
            self.macro_running = False
            self.stop_macro(f"Error at line {error_line}: {e}")
    def start_angler(self):
        # Validate Tesseract
        try:
            tesseract_path = get_tesseract_path(self.vars.get("tesseract_path"))
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                # Repair the imported config in memory
                self.vars["tesseract_path"] = tesseract_path
            else:
                raise RuntimeError("⚠️ Tesseract could not be found.")

            self.macro_running = True
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            result = self.message_box_javascript(f"""An error occured during angler.  Please copy the error and report the bug:\\n{e}\\n Would you like to copy the full crash log to your clipboard?""", "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            self.macro_running = False
            self.stop_macro(f"Angler error: {e}")
            return

        # Areas
        quest_left, quest_top, quest_right, quest_bottom, _, _ = self.get_areas("angler_quest")
        backpack_slot = str(self.vars["backpack_slot"])
        # Delays
        angler_cooldown = int(self.vars["angler_cooldown"])
        angler_e_delay = float(self.vars["angler_e_delay"])
        angler_click_position = self.vars["angler_click_position"].replace(" ", "").split(",")
        try:
            angler_click_position_x = float(angler_click_position[0]) * SCREEN_WIDTH
            angler_click_position_y = float(angler_click_position[1]) * SCREEN_HEIGHT
        except:
            pass

        angler_click_position2 = self.vars["angler_click_position2"].replace(" ", "").split(",")
        try:
            angler_click_position_x2 = float(angler_click_position2[0]) * SCREEN_WIDTH
            angler_click_position_y2 = float(angler_click_position2[1]) * SCREEN_HEIGHT
        except:
            pass

        # Main Loop
        try:
            while self.macro_running:
                time.sleep(0.1)
                # Step 1: Click E → Open Quest Dialogue
                self._send_key("e")
                time.sleep(angler_e_delay)
                # Click At Angler Area (Accept Quest)
                self._click_at(angler_click_position_x, angler_click_position_y)
                # Step 2: OCR Quest Area — Get Required Fish Text
                time.sleep(3)
                quest = self.capture_frame[quest_top:quest_bottom, quest_left:quest_right]
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
                self.status_overlay.set_line(1, "Quest fish:", f"{required_fish}")
                print("Quest fish:", f"{required_fish}")
                if not required_fish or not required_fish.strip():
                    self.status_overlay.set_line(1, "Could not read fish name:", "")
                    self.interruptible_sleep(angler_cooldown)
                    continue

                # Step 3: Open Backpack
                self._send_key(backpack_slot)
                time.sleep(0.5)
                # Step 4: Click Search Bar + Type Fish Name
                self._click_at(angler_click_position_x2, angler_click_position_y2)
                time.sleep(0.5)
                # Select All So A Second Quest Does Not Append ("red snapperred snapper")
                self._select_all_text()
                time.sleep(0.1)
                self._send_key("backspace")
                time.sleep(0.2)
                # Type Fish Name (macOS Must Not Inherit Globe/Fn Or Siri Opens)
                self._type_text(required_fish, per_char_delay=0.15)
                time.sleep(1.5)
                # Step 5: Locate Quest_Text In Quest Area Via OCR And Click It
                # Check If Dxcam Is Available
                if dxcam is not None:
                    self.capture_frame = self.camera.get_latest_frame()
                    self.capture_id = self.capture_id + 1
                quest_region = self.capture_frame[quest_top:quest_bottom, quest_left:quest_right]
                gray_q = cv2.cvtColor(quest_region, cv2.COLOR_BGR2GRAY)
                gray_q = cv2.resize(gray_q, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                gray_q = cv2.threshold(gray_q, 150, 255, cv2.THRESH_BINARY)[1]
                ocr_data_q = pytesseract.image_to_data(gray_q, output_type=pytesseract.Output.DICT, config="--psm 11")
                quest_click_x, quest_click_y = None, None
                # Normalize the required fish name once.
                required_words = required_fish.strip().lower().split()
                # Tesseract gives us individual words, so combine words that belong
                # to the same OCR line. This allows:
                #   Red
                #   Snapper
                # to match "Red Snapper".
                ocr_lines = {}
                for i, text_tok in enumerate(ocr_data_q["text"]):
                    tok = text_tok.strip().lower()
                    try:
                        conf = float(ocr_data_q["conf"][i])
                    except Exception:
                        conf = -1
                    if conf < 40 or not tok:
                        continue

                    block_num = ocr_data_q["block_num"][i]
                    par_num = ocr_data_q["par_num"][i]
                    line_num = ocr_data_q["line_num"][i]
                    line_key = (block_num, par_num, line_num)
                    ocr_lines.setdefault(line_key, []).append({
                        "text": tok,
                        "left": ocr_data_q["left"][i],
                        "top": ocr_data_q["top"][i],
                        "width": ocr_data_q["width"][i],
                        "height": ocr_data_q["height"][i],
                    })
                # Search each OCR line for the required fish name.
                for words in ocr_lines.values():
                    # Tesseract normally returns words left-to-right, but sort explicitly
                    # so the matching also works reliably if the OCR ordering changes.
                    words.sort(key=lambda w: (w["top"], w["left"]))
                    for start in range(len(words)):
                        candidate_words = []
                        for end in range(start, len(words)):
                            candidate_words.append(words[end]["text"])
                            candidate = " ".join(candidate_words)
                            # Exact multi-word match.
                            if candidate == " ".join(required_words):
                                matched_words = words[start:end + 1]
                                left = min(w["left"] for w in matched_words)
                                top = min(w["top"] for w in matched_words)
                                right = max(w["left"] + w["width"] for w in matched_words)
                                bottom = max(w["top"] + w["height"] for w in matched_words)
                                # Click the center of the entire phrase.
                                quest_click_x = quest_left + ((left + right) // 2) // 3
                                quest_click_y = quest_top + ((top + bottom) // 2) // 3
                                break

                            # Don't keep extending once the candidate is longer than
                            # the required fish name.
                            if len(candidate_words) >= len(required_words):
                                break

                        if quest_click_x is not None:
                            break

                    if quest_click_x is not None:
                        break

                if quest_click_x is not None:
                    self.status_overlay.set_line(1, f"Quest text '{required_fish}' found at ", f"{quest_click_x}, {quest_click_y} — clicking")
                    self._click_at(quest_click_x, quest_click_y)
                else:
                    self.status_overlay.set_line(1, f"Quest text '{required_fish}' not found via OCR, skipping click", "")
                time.sleep(0.1)
                # Step 6: Close Backpack
                self._send_key(backpack_slot)
                time.sleep(0.5)
                # Step 7: Click E → Finish Quest (Pixel Search Or Ratio)
                self._send_key("e")
                time.sleep(1.2)
                # Click At Angler Area To Exit Quest
                self._click_at(angler_click_position_x, angler_click_position_y)
                # Step 8: Cooldown
                self.interruptible_sleep(angler_cooldown)
        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            result = self.message_box_javascript(f"""An error occured during angler. 
            Please copy the error and report the bug:\\n{e}\\n Would you like to copy the full crash log to your clipboard?""", "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            self.macro_running = False
            self.stop_macro(f"Angler error: {e}")
            return

        self.set_status("Macro Stopped")
    def start_fishing(self):
        try:
            self.status_overlay.set_main_status("Initialization")
            # 1. Core Config & Modes
            scale = get_scale_factor()
            self.macro_running = True
            self.session_start = time.time()
            casting_mode = self.vars["casting_mode"].lower()
            shake_mode = self.vars["shake_mode"].lower()
            fishing_mode = self.vars["fishing_mode"].lower()
            logging_mode = self.vars["logging_mode"].lower()
            special_rod = self.vars["special_rod"].lower()
            sovereign_recharge = self.vars["sovereign_recharge"]
            click_after_minigame = self.vars["click_after_minigame"]
            target_time = self.vars["target_time"].lower()
            logging_cycle = int(self.vars["logging_cycle"])
            hunt_cycles = int(self.vars["hunt_cycles"])
            totem_cycles = int(self.vars.get("totem_cycles", 55))
            auto_reconnect = self.vars["auto_reconnect"].lower()
            hunt_detect = int(self._get_var_number("hunt_detect", 20, float))
            minimum_percentage = float(self.vars["minimum_percentage"].strip("%"))
            maximum_percentage = float(self.vars["maximum_percentage"].strip("%"))
            # 2. Hotkey & Inventory Slots
            equipment_bag_slot = str(self.vars["equipment_bag_slot"])
            fishing_rod_slot = str(self.vars["fishing_rod_slot"])
            sundial_totem_slot = str(self.vars["sundial_totem_slot"])
            totem_1_slot = str(self.vars["totem_1_slot"])
            totem_2_slot = str(self.vars["totem_2_slot"])
            relic_slot = str(self.vars["relic_slot"])
            # 3. Delays & Timings
            select_rod_duration = float(self.vars["select_rod_duration"])
            delay_before_casting = float(self._get_var_number("delay_before_casting", 0.5, float))
            delay_after_casting = float(self._get_var_number("cast_delay", 1.0, float))
            sundial_delay = float(self.vars["sundial_delay"])
            totem_delay = float(self.vars["totem_delay"])
            status_overlay = self.vars["status_overlay"]
            # 4. Screen Regions & Coordinates
            shake_left, shake_top, shake_right, shake_bottom, shake_w, shake_h = self.get_areas("shake")
            fish_left, fish_top, fish_right, fish_bottom, _, fish_height = self.get_areas("fish")
            bellona_fish_left, bellona_fish_top, bellona_fish_right, bellona_fish_bottom, _, _ = self.get_areas("fish_1_bellona")
            friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self.get_areas("friend")
            totem_left, totem_top, totem_right, totem_bottom, _, _ = self.get_areas("totem")
            sovereign_left, sovereign_top, sovereign_right, sovereign_bottom, sovereign_width, _ = self.get_areas("sovereign")
            shake_x = shake_left + (shake_w // 2)
            shake_y = shake_top + (shake_h // 2)
            detection_method = self.vars["detection_method"].lower()
            # 5. Features & Overlay Settings
            shake_failsafe = int(self.vars["shake_failsafe"])
            auto_refresh = self.vars["auto_refresh"]
            auto_totem = self.vars["auto_totem"]
            second_totem = self.vars["second_totem"]
            fish_overlay = self.vars["fish_overlay"]
            minigame_click_position = self.vars["minigame_click_position"]
            animation_delay = float(self.vars["animation_delay"])
            minigame_click_amounts = int(float(self.vars["minigame_click_amounts"]))
            enchantment_click_position = self.vars["enchantment_click_position"].replace(" ", "").split(",")
            try:
                enchantment_click_position_x = float(enchantment_click_position[0]) * SCREEN_WIDTH
                enchantment_click_position_y = float(enchantment_click_position[1]) * SCREEN_HEIGHT
            except:
                pass

            enchantment_click_position2 = self.vars["enchantment_click_position2"].replace(" ", "").split(",")
            try:
                enchantment_click_position_x2 = float(enchantment_click_position2[0]) * SCREEN_WIDTH
                enchantment_click_position_y2 = float(enchantment_click_position2[1]) * SCREEN_HEIGHT
            except:
                pass

            enchantment_click_delay = float(self.vars["enchantment_click_delay"])
            enchantment_click_delay2 = float(self.vars["enchantment_click_delay2"])
            # 6. Optimized OpenCV Template Matching Setup
            totem_cycles2 = 0
            try:
                sun = cv2.imread(os.path.join(IMAGES_PATH, "sun.png"))
                moon = cv2.imread(os.path.join(IMAGES_PATH, "moon.png"))
                sun_resized = self.auto_crop_template(sun)
                moon_resized = self.auto_crop_template(moon)
            except:
                self.status_overlay.set_main_status("Error: Can't find sun.png and moon.png. Auto Totem is disabled.")
                self.send_logging("Error: Can't find sun.png and moon.png. Auto Totem is disabled.", 0)
                auto_totem = False
            # 7. Internal Tracking State
            self.scan_delay = 0.1
            self.current_cycle = 0
            current_time = None
            current_hunt = ""

            # Catch Metrics (0 - Success, 1 - Failed, 2 - N/A Initial State)
            self.fish_caught = 2
            self.perfect_catch = 2
            self.catch_rate = 0.0
            self.successful_catches = 0
            self.perfect_catches = 0
            logging_cycle2 = 0
            hunt_cycles2 = hunt_cycles
            self.reported_errors = []
            self.reported_errors_list = []
            # Fish Overlay
            if fish_overlay == True:
                # Position The Overlay Just Above Or Below The Fish Bar So It Does
                # Not Cover The Actual Minigame.  Show() Expects (Left, Top, Width,
                # Height) In Physical Pixels — Not Right/Bottom.
                fish_center = int((fish_top + fish_bottom) / 2)
                if fish_center > HALF_HEIGHT:
                    fish_top_overlay = fish_top + fish_height + fish_height
                else:
                    fish_top_overlay = fish_top - fish_height - fish_height
                overlay_width = fish_right - fish_left
                overlay_height = int(fish_height / 1.5)
                self.fish_overlay.show(fish_left, fish_top_overlay, overlay_width, overlay_height)
            else:
                self.fish_overlay.hide()
            # Status Overlay
            if status_overlay == True:
                # Position The Status Overlay At The Top Left, But Avoiding The macOS Menu Offset.
                self.status_overlay.show(self.status_left, self.status_top, self.status_right, self.status_bottom)
            else:
                self.status_overlay.hide()
        except Exception as e:
            full_error = traceback.format_exc()
            error_line = self.get_error_line(full_error)
            if "KeyError" in full_error:
                error_message = e.replace("_", " ").title()
                key_error_placeholder = "Missing Setting: "
            else:
                key_error_placeholder = ""
                error_message = e
            result = self.message_box_javascript(f"""An error at line {error_line} occured. 
Please copy the error and report the bug:\\n{key_error_placeholder}{error_message}\\n Would you like to copy the full crash log to your clipboard?
            """, "askyesno")
            if result == True:
                if self.copy_to_clipboard(full_error):
                    self.message_box_javascript("Error copied over to clipboard")
                else:
                    self.message_box_javascript("Failed to copy error to clipboard")
            if IS_COMPILED == False:
                print(full_error)
            self.send_logging(f"Error at line {error_line}: {e}", 0)
            self.macro_running = False
            return

        # Auto Zoom
        auto_zoom = self.vars["auto_zoom"]
        if auto_zoom == True:
            for i in range(30):
                self.status_overlay.set_line(1, "Zoom Count (In)", f"{i}/30")
                self._send_key("i", 0.05)
            self.status_overlay.set_line(1, "Zoom Count (Out)", "1/1")
            self._send_key("o", 0.01)
        # Main Loop (With Bug Reports)
        try:
            while self.macro_running:
                self.status_overlay.set_main_status("Resetting Statistics")
                self.capture_id = 0
                if auto_refresh == True:
                    time.sleep(delay_before_casting)
                    self._send_key(equipment_bag_slot)
                    self.interruptible_sleep(select_rod_duration)
                    self._send_key(fishing_rod_slot)
                    self.interruptible_sleep(delay_after_casting / 2)
                self.status_overlay.set_main_status("Using Utilities")
                # Auto Totem
                if auto_totem == True and self.current_cycle == totem_cycles2:
                    self.status_overlay.set_main_status("Auto Totem")
                    time.sleep(0.1)
                    if not target_time == "disabled":
                        if dxcam is not None:
                            self.capture_frame = self.camera.get_latest_frame()
                        totem = self.capture_frame[totem_top:totem_bottom, totem_left:totem_right]
                        sun_found, _, sun_confidence = self.image_search(totem, sun_resized)
                        moon_found, _, moon_confidence = self.image_search(totem, moon_resized)
                        if sun_found == False and moon_found == False:
                            current_time = None
                            self.send_logging("**Sundial Failed**", f"Cycle #{self.current_cycle}")
                        elif sun_found == True:
                            current_time = "day"
                        elif moon_found == True:
                            current_time = "night"
                        else:
                            if sun_confidence > moon_confidence:
                                current_time = "day"
                            else:
                                current_time = "night"
                        # Show confidence and current time in status overlay
                        time_display = current_time if current_time else "Unknown"
                        confidence_display = f"Sun {sun_confidence:.2f} / Moon {moon_confidence:.2f}"
                        self.status_overlay.set_line(1, "Current Time", time_display)
                        self.status_overlay.set_line(2, "Confidence", confidence_display)
                        if not target_time == current_time:
                            self._send_key(sundial_totem_slot)
                            self._click_at(shake_x, shake_y)
                            self.interruptible_sleep(sundial_delay)
                            self.send_logging("**Sundial Success**", f"Cycle #{self.current_cycle}")
                    self._send_key(totem_1_slot)
                    self._click_at(shake_x, shake_y)
                    self.interruptible_sleep(totem_delay)
                    if second_totem == True:
                        self._send_key(totem_2_slot)
                        self._click_at(shake_x, shake_y)
                        self.interruptible_sleep(totem_delay)
                    self._send_key(fishing_rod_slot)
                    time.sleep(delay_after_casting / 4)
                    totem_cycles2 = self.current_cycle + totem_cycles
                if auto_reconnect == "legacy":
                    self.status_overlay.set_main_status("Auto Reconnect")
                    self._auto_reconnect(shake_x, shake_y)
                if hunt_detect == True:
                    self.status_overlay.set_main_status("Hunt Detect")
                    if self.current_cycle == hunt_cycles:
                        self.hunt_detect(current_hunt)
                        hunt_cycles = hunt_cycles2 + self.current_cycle
                if sovereign_recharge == True:
                    self.status_overlay.set_main_status("Sovereign Recharge")
                    sovereign_img = self.capture_frame[sovereign_top:sovereign_bottom, sovereign_left:sovereign_right]
                    sovereign_right2, _ = self.pixel_search_all(sovereign_img, "sovereign_recharge_color", "sovereign_recharge_tolerance")
                    if sovereign_right2 is not None:
                        distance = round(abs(sovereign_right2 - sovereign_left) / sovereign_width, 2)
                        while distance < maximum_percentage:
                            if distance < minimum_percentage:
                                self._send_key(fishing_rod_slot)
                                time.sleep(0.1)
                                self._send_key(relic_slot)
                                self._click_at(enchantment_click_position_x, enchantment_click_position_y)
                                time.sleep(enchantment_click_delay)
                                self._click_at(enchantment_click_position_x2, enchantment_click_position_y2)
                                time.sleep(enchantment_click_delay2)
                            elif distance > maximum_percentage:
                                break

                            time.sleep(0.01)
                # Update Current Cycle
                self.current_cycle = self.current_cycle + 1
                # Cast
                self.status_overlay.set_main_status(f"Casting ({casting_mode})")
                time.sleep(delay_before_casting)
                if casting_mode == "perfect":
                    self._execute_cast_perfect()
                else:
                    self._execute_cast_normal()
                time.sleep(delay_after_casting)
                # Shake
                self.status_overlay.set_main_status(f"Shaking ({shake_mode})")
                self.scan_delay = float(self.vars["shake_scan_delay"])
                attempts = 0
                while attempts <= shake_failsafe:
                    self.status_overlay.set_line(1, "Attempts", attempts)
                    if dxcam is not None:
                        self.capture_frame = self.camera.get_latest_frame()
                    if self.capture_frame is None:
                        attempts = attempts - 1
                        continue

                    if detection_method == "friend_area":
                        friend_img = self.capture_frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                        friend_x, friend_y = self.pixel_search_all(friend_img, "friends_color", "friends_tolerance")
                        if friend_x is None or friend_y is None:
                            break

                    else:
                        if special_rod == "bellona":
                            fish_img = self.capture_frame[bellona_fish_top:bellona_fish_bottom, bellona_fish_left:bellona_fish_right]
                        else:
                            fish_img = self.capture_frame[fish_top:fish_bottom, fish_left:fish_right]
                        if fishing_mode == "color":
                            fish_x, fish_y = self.pixel_search_all(fish_img, "fish_color", "fish_tolerance")
                            if fish_x is not None or fish_y is not None:
                                break

                        else:
                            lines = self._detect_lines_in_frame(fish_img)
                            if len(lines) >= 4:
                                break

                    if self.macro_running == False:
                        break

                    elif shake_mode == "navigation":
                        keyboard_controller.press(Key.enter)
                        time.sleep(0.01)
                        keyboard_controller.release(Key.enter)
                    else:
                        try:
                            shake_click_x, shake_click_y = self._execute_shake_click(shake_mode)
                            if shake_click_x == last_shake_click_x and shake_click_y == last_shake_click_y:
                                attempts = attempts - 1
                            last_shake_click_x, last_shake_click_y = shake_click_x, shake_click_y
                        except UnboundLocalError:
                            last_shake_click_x = 0
                            last_shake_click_y = 0
                            shake_click_x = 0
                            shake_click_y = 0
                    attempts = attempts + 1
                    time.sleep(self.scan_delay)
                # Minigame
                # Set self.fish_caught and self.perfect_catch to defaults before entering
                time.sleep(animation_delay)
                if self.macro_running == True:
                    self.status_overlay.set_main_status(f"Playing Bar Minigame ({special_rod})")
                    if special_rod == "dreambreaker":
                        self._enter_minigame_dreambreaker()
                    elif special_rod == "bellona":
                        self._enter_minigame_bellona()
                    elif special_rod == "tranquility":
                        self._enter_minigame_tranquility()
                    elif special_rod == "lullaby":
                        self.enter_minigame_lullaby()
                    else:
                        self._enter_minigame()
                    if click_after_minigame == True:
                        try:
                            time.sleep(select_rod_duration)
                            minigame_click_positions = minigame_click_position.replace(" ", "").split(",")
                            minigame_click_position_xr = float(minigame_click_positions[0])
                            minigame_click_position_yr = float(minigame_click_positions[1])
                            minigame_click_position_x = int(minigame_click_position_xr * SCREEN_WIDTH)
                            minigame_click_position_y = int(minigame_click_position_yr * SCREEN_HEIGHT)
                            for clicks in range(minigame_click_amounts - 1):
                                self._click_at(minigame_click_position_x, minigame_click_position_y)
                                time.sleep(1)
                            self._click_at(HALF_WIDTH, HALF_HEIGHT)
                            time.sleep(2.5)
                        except:
                            pass

                # Update Catch Rate After The Minigame Finishes
                if self.perfect_catch == 0:
                    self.perfect_catches += 1
                if self.fish_caught == 0:
                    self.successful_catches += 1
                self.catch_rate = self.successful_catches / self.current_cycle if self.current_cycle else 0.0
                self.perfect_catch_rate = self.perfect_catches / self.current_cycle if self.current_cycle else 0.0
                if logging_mode != "disabled":
                    if self.current_cycle == logging_cycle:
                        self.send_logging("**Cycle Checkpoint**", f"Cycle #{self.current_cycle}")
                        logging_cycle = logging_cycle2 + self.current_cycle

        except Exception as e:
            time.sleep(0.2)
            full_error = traceback.format_exc()
            error_lines = full_error.splitlines()
            error_line = self.get_error_line(error_lines[1])
            self.message_box_javascript(f"An error at line {error_line} occured. Please copy the error and report the bug:\\n{e}\\nWould you like to copy the full crash log to your clipboard?", full_error)
            if IS_COMPILED == False:
                print(full_error)
            self.macro_running = False
            self.stop_macro(f"Error at line {error_line}: {e}")

    def _auto_reconnect(self, center_x, center_y):
        auto_reconnect = self.vars["auto_reconnect"].lower()
        reconnect_threshold = int(self.vars["reconnect_threshold"])
        reconnect_wait_time = int(self.vars["reconnect_wait_time"])
        mirror_ratio = self.vars["mirror_ratio"]
        mirror_splitted = mirror_ratio.replace(" ", "").split(",")
        self.status_overlay.set_main_status("Auto Reconnect")
        try:
            mirror_xr = float(mirror_splitted[0])
            mirror_yr = float(mirror_splitted[1])
        except:
            self.send_logging("**Reconnect Failed**", f"Cycle #{self.current_cycle}")
            return

        mystic_mirror_slot = str(self.vars["mystic_mirror_slot"])
        shake_left, shake_top, shake_right, shake_bottom, shake_width, shake_height = self.get_areas("shake")
        mirror_click_x = int(SCREEN_WIDTH * mirror_xr)
        # 0.59
        mirror_click_y = int(SCREEN_HEIGHT * mirror_yr)
        # 1520
        reconnect_threshold = int((reconnect_threshold / 1500) * (SCREEN_WIDTH / 1.8))
        if dxcam is not None:
            self.capture_frame = self.camera.get_latest_frame()
        if self.capture_frame is None:
            time.sleep(1)
        img = self.capture_frame[shake_top:shake_bottom, shake_left:shake_right]
        disconnect_x, disconnect_y = self.find_color_cluster(img, "#393b3d", 5, reconnect_threshold)
        if auto_reconnect == "legacy":
            reconnect_x, reconnect_y = self.find_color_cluster(img, "#FFFFFF", 8, int(reconnect_threshold / 2))
        else:
            reconnect_x = center_x
            reconnect_y = center_y
        if disconnect_x is not None and reconnect_x is not None:
            self.interruptible_sleep(1)
            if auto_reconnect == "legacy":
                reconnect_x_screen = reconnect_x + shake_left
                reconnect_y_screen = reconnect_y + shake_top
                self._click_at(reconnect_x_screen, reconnect_y_screen)
            else:
                self.interruptible_sleep(3)
            self.interruptible_sleep(reconnect_wait_time)
            self._click_at(center_x, center_y)
            self.interruptible_sleep(2.5)
            self._send_key(mystic_mirror_slot)
            self._click_at(center_x, center_y)
            self.interruptible_sleep(0.2)
            self._click_at(mirror_click_x, mirror_click_y)
            self.interruptible_sleep(3)
            self.send_logging("**Reconnect Success**", f"Cycle #{self.current_cycle}")
        else:
            self.send_logging("**Reconnect Failed**", f"Cycle #{self.current_cycle}")
    def hunt_detect(self, current_hunt):
        "current_hunt: Does nothing"
        try:
            tesseract_path = get_tesseract_path(self.vars.get("tesseract_path"))
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                # Repair the imported config in memory
                self.vars["tesseract_path"] = tesseract_path
            else:
                raise RuntimeError("⚠️ Tesseract could not be found.")

        except:
            return

        chat_left, chat_top, chat_right, chat_bottom = self.get_areas("chat")
        hunt_fishes = self.vars["hunt_fishes"].lower()
        user_id = int(self.vars["user_id"])
        hunt_fishes_list = hunt_fishes.split(",")
        text = self.capture_frame[
            chat_top:chat_bottom,
            chat_left:chat_right
        ]
        gray = self.process_image_for_ocr(text)
        text = pytesseract.image_to_string(gray, config="--psm 6")
        # Get The Bottommost Nonempty OCR Line
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]
        if not lines:
            return

        latest_line = lines[-1]
        # Check Only The Latest Chat Message
        latest_line_normalized = latest_line.lower().replace(" ", "")
        for hunt in hunt_fishes_list:
            hunt = hunt.strip()
            current_hunt = hunt
            if hunt.lower().replace(" ", "") in latest_line_normalized:
                self.send_logging(f"<@{user_id}> Found {hunt}", self.current_cycle)
                return current_hunt

        return current_hunt
    
    def _execute_cast_perfect(self):
        # Areas
        shake_left, shake_top, shake_right, shake_bottom, shake_width, shake_height = self.get_areas("shake")
        # Perfect Cast Settings
        perfect_cast_method = self.vars["perfect_cast_method"].lower()
        fall_scan_timeout = float(self.vars["fall_scan_timeout"])
        self.scan_delay = float(self.vars["cast_scan_delay"])
        # Last Values (Failsafe)
        last_capture_id = 0
        is_initial_run = True
        green_detected = False
        start_time = time.time()
        last_time = time.time()
        self.hold_mouse()
        green_padding = 50
        released = False
        # Simple Method Variables
        speed_samples = []
        white_positions = []
        white_timestamps = []
        max_speed_samples = 20
        release_delay = float(self.vars["release_delay_simple"])
        perfect_threshold = float(self.vars["perfect_threshold"])
        release_timing = max(-50.0, min(50.0, release_delay))
        # Velocity Method Variables
        if perfect_cast_method == "velocity":
            white_positions = []
            white_timestamps = []
            MAX_VELOCITY_SAMPLES = 10
            last_time_to_impact = None
            scaling_factor = 1920 / SCREEN_WIDTH
        if perfect_cast_method == "prediction":
            highest_cast_percentage = 100
            highest_cast_percentage_updated = False
        # Initialize Tracking Variables
        # These are ALWAYS in shake-image coordinate space
        green_abs_top = 0
        green_abs_left = 0
        green_abs_right = 0
        green_abs_bottom = 0
        reached_bottom_5_percent = True
        last_fill_percentage = None
        last_frame_time = None
        white_full_scan = False
        # Validity flags — set True only once a real detection has occurred.
        # Prevents stale default values (0 / shake_height) from being used
        # before green and white have actually been found.
        green_valid = False
        white_valid = False
        # Cached green bounds (shake-image coords), None = not yet detected
        cached_green = None  # (left, top, right, bottom)
        white_abs_bottom = shake_height
        white_abs_top = 0
        green_abs_top = 0
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == True:
            self.fish_overlay.resize(shake_right, shake_top, 35, shake_height)
        # Loop
        while self.macro_running:
            # Check If Dxcam Is Available
            if dxcam is not None:
                self.capture_frame = self.camera.get_latest_frame()
                self.capture_id = last_capture_id + 1
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue

            if self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue

            # Scan Time Calculations
            current_time = time.time()
            elapsed_time = current_time - start_time
            time_delta = current_time - last_time
            if elapsed_time >= fall_scan_timeout:
                self.release_mouse()
                released = True
                break

            if not self.macro_running:
                self.release_mouse()
                released = True
                break

            # Slice shake region
            shake_img = self.capture_frame[shake_top:shake_bottom, shake_left:shake_right]
            # GREEN DETECTION
            # Initial (or lost) -> full scan of shake_img
            # Otherwise -> scan cached green area + padding
            green_found = False
            if cached_green is None:
                # Full scan in shake_img coordinate space
                g_left, g_top = self.pixel_search_all( shake_img, "green_cast_color", "green_cast_tolerance" )
                g_right, g_bottom = self.pixel_search_all( shake_img, "green_cast_color", "green_cast_tolerance", 1 )
                if g_top is not None and g_bottom is not None and g_left is not None and g_right is not None:
                    cached_green = (g_left, g_top, g_right, g_bottom)
                    green_found = True
            else:
                # Cached scan: crop around last known green + padding
                cl, ct, cr, cb = cached_green
                pad_l = max(0, cl - green_padding)
                pad_t = max(0, ct - green_padding)
                pad_r = min(shake_width, cr + green_padding)
                pad_b = min(shake_height, cb + green_padding)
                green_img = shake_img[pad_t:pad_b, pad_l:pad_r]
                lg_left, lg_top = self.pixel_search_all( green_img, "green_cast_color", "green_cast_tolerance" )
                lg_right, lg_bottom = self.pixel_search_all( green_img, "green_cast_color", "green_cast_tolerance", 1 )
                if (lg_top is not None and lg_bottom is not None and lg_left is not None and lg_right is not None):
                    # Convert back to shake_img coords
                    g_left = lg_left + pad_l
                    g_top = lg_top + pad_t
                    g_right = lg_right + pad_l
                    g_bottom = lg_bottom + pad_t
                    cached_green = (g_left, g_top, g_right, g_bottom)
                    green_found = True
                else:
                    # Lost green - invalidate cache, rescan fully next frame
                    cached_green = None
            # Update absolute green bounds (shake coords) whenever we have them
            if green_found:
                green_abs_left, green_abs_top, green_abs_right, green_abs_bottom = cached_green
                green_valid = True
            # WHITE DETECTION
            # If green is known: scan white in [green_left:green_right, shake_top:shake_bottom]
            #   (i.e. the column below/around the green bar within the shake area)
            # If green is not known: full scan of shake_img
            white_found = False
            if green_found:
                # White scan area in shake coords: x = green left..right, y = green top..shake bottom
                # White can never be above green, so start the crop at green_abs_top.
                wl = max(0, green_abs_left)
                wr = min(shake_width, green_abs_right)
                wt = max(0, green_abs_top)      # <-- was 0
                wb = shake_height
                white_img = shake_img[wt:wb, wl:wr]
                w_left_rel, w_top_rel = self.pixel_search_all( white_img, "white_cast_color", "white_cast_tolerance" )
                w_right_rel, w_bottom_rel = self.pixel_search_all( white_img, "white_cast_color", "white_cast_tolerance", 1 )
                if (w_top_rel is not None and w_bottom_rel is not None and w_left_rel is not None and w_right_rel is not None):
                    white_abs_left = w_left_rel + wl
                    white_abs_top = w_top_rel + wt
                    white_abs_right = w_right_rel + wl
                    white_abs_bottom = w_bottom_rel + wt
                    white_found = True
            else:
                # Full scan of shake_img
                w_left_rel, w_top_rel = self.pixel_search_all( shake_img, "white_cast_color", "white_cast_tolerance" )
                w_right_rel, w_bottom_rel = self.pixel_search_all( shake_img, "white_cast_color", "white_cast_tolerance", 1 )
                if (w_top_rel is not None and w_bottom_rel is not None and w_left_rel is not None and w_right_rel is not None):
                    white_abs_left = w_left_rel
                    white_abs_top = w_top_rel
                    white_abs_right = w_right_rel
                    white_abs_bottom = w_bottom_rel
                    white_found = True
            if white_found:
                white_valid = True
            # DISTANCE (both in shake coords now)
            # Only compute once BOTH green and white have been genuinely detected
            # at least once. Otherwise the stale defaults (0 / shake_height)
            # produce total_distance == 0 and a bogus 100% fill on the first frames.
            if not (green_valid and white_valid):
                time.sleep(self.scan_delay)
                last_capture_id = self.capture_id
                last_time = current_time
                continue

            total_distance = white_abs_bottom - green_abs_top
            current_distance = white_abs_top - green_abs_top
            # Guard against degenerate/zero total distance (e.g. green top == white bottom)
            if total_distance <= 0:
                time.sleep(self.scan_delay)
                last_capture_id = self.capture_id
                last_time = current_time
                continue

            self.status_overlay.set_line(1, "Distance", f"{round(current_distance)}")
            if current_distance < 0:
                current_distance = shake_height
            # Fish Overlay
            self.fish_overlay.clear()
            if fish_overlay == True:
                self.fish_overlay.draw(5, green_abs_top, 30, green_abs_bottom, "#FF0000")
                self.fish_overlay.draw(5, white_abs_top, 30, white_abs_bottom, "#00FF00")
            # RELEASE LOGIC (only runs when we have a valid distance)
            if perfect_cast_method == "simple":
                # Simple (Percentage-Based) Method
                actual_fill_percentage = (1 - (current_distance / total_distance)) * 100
                self.status_overlay.set_line(2, "Actual Fill Percentage", f"{round(actual_fill_percentage)}")
                fill_speed = 0.0
                position_offset_percent = 0.0
                if last_fill_percentage is not None and last_frame_time is not None:
                    time_delta = current_time - last_frame_time
                    if time_delta > 0:
                        fill_change = actual_fill_percentage - last_fill_percentage
                        if fill_change < -50:
                            last_fill_percentage = None
                            last_frame_time = None
                            reached_bottom_5_percent = False
                            speed_samples.clear()
                        elif fill_change > 0:
                            instant_fill_speed = fill_change / time_delta
                            speed_samples.append(instant_fill_speed)
                            if len(speed_samples) > max_speed_samples:
                                speed_samples.pop(0)
                if speed_samples:
                    fill_speed = sum(speed_samples) / len(speed_samples)
                    base_offset = 1.5 * math.log(1 + fill_speed / 25.0)
                    if release_timing < 0:
                        base_multiplier = 1.0 - (release_timing / 5.0)
                        speed_scale = min(6.0, (fill_speed / 100.0) ** 2)
                        timing_multiplier = 1.0 + (base_multiplier - 1.0) * speed_scale
                        position_offset_percent = max(0.0, min(50.0, base_offset * timing_multiplier))
                    else:
                        position_offset_percent = max(0.0, min(50.0, base_offset))
                predicted_fill_percentage = actual_fill_percentage + position_offset_percent
                self.status_overlay.set_line(3, "Predicted Fill Percentage: ", f"{round(predicted_fill_percentage)}")
                offset_pixels = int((position_offset_percent / 100.0) * total_distance)
                predicted_white_y_top = white_abs_top - offset_pixels
                bottom_threshold = 5.0 + position_offset_percent
                if predicted_fill_percentage <= bottom_threshold and not reached_bottom_5_percent:
                    reached_bottom_5_percent = True
                    last_fill_percentage = None
                    last_frame_time = None
                    speed_samples.clear()
                if release_timing <= 0:
                    release_threshold = perfect_threshold
                else:
                    release_threshold = perfect_threshold + (release_timing / 50.0) * 4.5
                if reached_bottom_5_percent and predicted_fill_percentage >= release_threshold:
                    released = True
                    break

                last_fill_percentage = actual_fill_percentage
                last_frame_time = current_time
            elif perfect_cast_method == "velocity":  # perfect_cast_method == "velocity" (VELOCITY-BASED METHOD)
                # Velocity Tracking
                white_positions.append((0, white_abs_top))  # x is irrelevant; track Y only
                white_timestamps.append(current_time)
                if len(white_positions) > MAX_VELOCITY_SAMPLES:
                    white_positions.pop(0)
                    white_timestamps.pop(0)
                # Local_Distance: Pixels Remaining Until White Reaches Green
                local_distance = current_distance  # white_abs_top - green_abs_top; positive = white below green
                # Velocity-Band Predictive Release
                if len(white_positions) >= 3:
                    velocity_y = self._calculate_speed_and_predict(white_positions, white_timestamps)
                    min_speed = 5 * scaling_factor
                    if velocity_y is not None and abs(velocity_y) > min_speed:
                        white_above_green = white_abs_top < green_abs_top
                        moving_toward_green = (white_above_green and velocity_y > 0) or (not white_above_green and velocity_y < 0)
                        if moving_toward_green and local_distance > 0:
                            time_to_impact = local_distance / abs(velocity_y)
                            self.status_overlay.set_line(3, "Time To Impact: ", round(time_to_impact, 2))
                            # Bounce/Miss Detection: If time_to_impact Suddenly Grows When Very Close, We Passed Green
                            bounce_threshold = 40 * scaling_factor
                            if last_time_to_impact is not None and local_distance < bounce_threshold:
                                if time_to_impact > last_time_to_impact * 1.3:
                                    self.release_mouse()
                                    released = True
                            if not released:
                                # Velocity-Band Reaction Delays (Tuned At 1440P)
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
                                self.status_overlay.set_line(2, "Velocity: ", f"{timing_key.strip("perfect_cast_timing_").replace("_plus", "+")}")
                                timing_adjustment_ms = self._get_var_number(timing_key, 0, int)
                                reaction_delay += timing_adjustment_ms * 0.001
                                if time_to_impact <= reaction_delay:
                                    self.release_mouse()
                                    released = True
                            last_time_to_impact = time_to_impact
                # Slow-Speed / Emergency Distance Fallbacks
                if not released:
                    slow_threshold = total_distance * 0.05  # within 5% of green
                    emergency_threshold = total_distance * 0.025
                    self.status_overlay.set_line(3, "Local Distance: ", local_distance)
                    if local_distance <= emergency_threshold:
                        self.release_mouse()
                        released = True
                    elif local_distance <= slow_threshold and len(white_positions) >= 3:
                        # Confirm Approach: Latest Distance < Oldest Distance
                        recent_dists = [p[1] - green_abs_top for p in white_positions[-3:]]
                        if recent_dists[-1] < recent_dists[0]:
                            self.release_mouse()
                            released = True
                if released:
                    break

            elif perfect_cast_method == "prediction":  # perfect_cast_method == "prediction" (PREDICTION METHOD)
                # Simple (Percentage-Based) Method
                actual_fill_percentage = (1 - (current_distance / total_distance)) * 100
                fill_speed = 0.0
                position_offset_percent = 0.0
                if last_fill_percentage is not None and last_frame_time is not None:
                    time_delta = current_time - last_frame_time
                    if time_delta > 0:
                        fill_change = actual_fill_percentage - last_fill_percentage
                        if fill_change < -50:
                            last_fill_percentage = None
                            last_frame_time = None
                            reached_bottom_5_percent = False
                            speed_samples.clear()
                        elif fill_change > 0:
                            instant_fill_speed = fill_change / time_delta
                            speed_samples.append(instant_fill_speed)
                            if len(speed_samples) > max_speed_samples:
                                speed_samples.pop(0)
                if speed_samples:
                    fill_speed = sum(speed_samples) / len(speed_samples)
                    base_offset = 1.5 * math.log(1 + fill_speed / 25.0)
                    if release_timing < 0:
                        base_multiplier = 1.0 - (release_timing / 5.0)
                        speed_scale = min(6.0, (fill_speed / 100.0) ** 2)
                        timing_multiplier = 1.0 + (base_multiplier - 1.0) * speed_scale
                        position_offset_percent = max(0.0, min(50.0, base_offset * timing_multiplier))
                    else:
                        position_offset_percent = max(0.0, min(50.0, base_offset))
                predicted_fill_percentage = actual_fill_percentage + position_offset_percent
                offset_pixels = int((position_offset_percent / 100.0) * total_distance)
                predicted_white_y_top = white_abs_top - offset_pixels
                bottom_threshold = 5.0 + position_offset_percent
                if predicted_fill_percentage <= bottom_threshold and not reached_bottom_5_percent:
                    reached_bottom_5_percent = True
                    last_fill_percentage = None
                    last_frame_time = None
                    speed_samples.clear()
                if last_fill_percentage is not None:
                    cast_velocity = actual_fill_percentage - last_fill_percentage
                else:
                    cast_velocity = 0.1
                if cast_velocity < 0:
                    if highest_cast_percentage_updated == False:
                        # Store The Highest Percentage From The Previous Bar Movement
                        highest_cast_percentage = last_fill_percentage
                        highest_cast_percentage_updated = True
                        time.sleep(0.2)
                if release_timing <= 0:
                    release_threshold = highest_cast_percentage
                else:
                    release_threshold = highest_cast_percentage + (release_timing / 50.0) * 4.5
                self.status_overlay.set_line(2, "Highest Cast Percentage: ", round(highest_cast_percentage, 2))
                if reached_bottom_5_percent and predicted_fill_percentage >= release_threshold:
                    released = True
                    break

                last_fill_percentage = actual_fill_percentage
                last_frame_time = current_time
            if time.time() - start_time > fall_scan_timeout:
                break

            # Cleanup
            time.sleep(self.scan_delay)
            last_capture_id = self.capture_id
            is_initial_run = False
            last_time = current_time
        # Final Cleanup
        self.release_mouse()
        self._fish_overlay_cast_bounds = None
        return

    def _execute_cast_normal(self):
        if self.macro_running == False:
            return

        cast_duration = float(self._get_var_number("cast_duration", 0.5, float))
        self.status_overlay.set_line(1, "Casting For: (seconds)", cast_duration)
        self.hold_mouse(False)
        self.interruptible_sleep(cast_duration)
        self.release_mouse(False)
        return

    def _execute_shake_click(self, shake_mode):
        scale = get_scale_factor()
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self.get_areas("shake")
        shake_color = self.vars["shake_color"]
        shake_tolerance = self.vars["shake_tolerance"]
        if dxcam is not None:
            self.capture_frame = self.camera.get_latest_frame()
        shake_img = self.capture_frame[shake_top:shake_bottom, shake_left:shake_right]
        if shake_mode == "pixel":
            shake_x, shake_y = self.pixel_search_all(shake_img, "shake_color", "shake_tolerance")
        else:
            shake_x, shake_y = self._find_circles(shake_img)
        try:
            shake_x_screen = int((shake_x / scale) + shake_left)
            shake_y_screen = int((shake_y / scale) + shake_top)
        except:
            shake_x_screen = None
            shake_y_screen = None
        self._click_at(shake_x_screen, shake_y_screen)
        return shake_x_screen, shake_y_screen
    def _enter_minigame_tranquility(self):
        # Areas
        shake_left, shake_top, shake_right, shake_bottom, shake_width, shake_height = self.get_areas("fish_tranquility")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self.get_areas("friend")
        # Minigame Variables
        lead_ms = float(self.vars.get("tranquility_lead", 45))
        lead = lead_ms / 1000.0
        self.scan_delay = float(self.vars["minigame_scan_delay"])
        restart_delay = float(self.vars["restart_delay"])
        restart_method = self.vars["restart_method"].lower()
        self.ever_out = False
        self.ever_note_out_high = False
        last_capture_id = 0
        # Lane setup (relative to overlay / shake area)
        tranquility_area_ratio = shake_width / 350.0
        tranquility_big_gap = int(tranquility_area_ratio * 80)
        tranquility_small_gap = int(tranquility_area_ratio * 10)
        fish_left = []
        fish_right = []
        for pos in range(4):
            left = (tranquility_big_gap * pos) + (tranquility_small_gap * pos)
            right = (tranquility_big_gap * (pos + 1)) + (tranquility_small_gap * pos)
            fish_left.append(left)
            fish_right.append(right)
        # Overlay
        fish_center_y = int((shake_top + shake_bottom) / 2)
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == True:
            if fish_center_y > HALF_HEIGHT:
                overlay_top = shake_top - tranquility_small_gap - tranquility_small_gap
            else:
                overlay_top = shake_top + tranquility_small_gap + tranquility_small_gap
            self.fish_overlay.resize(shake_left, overlay_top, shake_width, tranquility_small_gap)
        # Tracking state (inspired by DeepFish Tq*/Mania*)
        ring_ys = [[] for _ in range(4)]  # static target y positions per lane
        notes = [[] for _ in range(4)]    # tracked notes: dicts with y, t, fired, track_n, eta
        vel_samples = []
        current_v = 0.45 * shake_height   # initial velocity estimate (px/s), similar spirit to AHK 0.645*H
        last_live_t = time.perf_counter()
        started = False
        initial_frames = 0
        time.sleep(0.5)
        while self.macro_running:
            # Capture
            if dxcam is not None:
                self.capture_frame = self.camera.get_latest_frame()
                self.capture_id = last_capture_id + 1
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue
            elif self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue
            else:
                friend_img = self.capture_frame[friend_top:friend_bottom, friend_left:friend_right]
            friend_x, friend_y = self.pixel_search_all(friend_img, "friends_color", "friends_tolerance")
            current_time = time.perf_counter()
            self.fish_overlay.clear()
            # Restart check
            if restart_method == "friend_area" or restart_method == "friends":
                if friend_x is not None:
                    # Classify based on ever_out / note tracking
                    if self.ever_note_out_high or self.ever_out:
                        self.fish_caught = 0
                        self.perfect_catch = 1
                    else:
                        self.fish_caught = 0
                        self.perfect_catch = 0
                    self.interruptible_sleep(restart_delay)
                    return
            # Process each lane
            any_moving = False
            for box in range(4):
                scan_img = self.capture_frame[shake_top:shake_bottom, fish_left[box] + shake_left:fish_right[box] + shake_left]
                circles = self._find_all_circles(scan_img)
                ys = sorted([y for (x, y) in circles])
                # Collect possible rings on early frames
                if initial_frames < 8:
                    for y in ys:
                        if not any(abs(y - ry) < 12 for ry in ring_ys[box]):
                            ring_ys[box].append(y)
                    if ring_ys[box]:
                        ring_ys[box] = sorted(set(ring_ys[box]))  # unique
                # Separate notes from kcurrent_timen rings
                note_ys = []
                for y in ys:
                    is_ring = any(abs(y - ry) < 15 for ry in ring_ys[box])
                    if not is_ring:
                        note_ys.append(y)
                # Match note_ys to existing tracked notes
                used = [False] * len(notes[box])
                new_notes = []
                for ny in note_ys:
                    best_i = -1
                    best_dist = 999
                    for i, nt in enumerate(notes[box]):
                        if used[i]:
                            continue
                        dist = abs(ny - nt["y"])
                        if dist < best_dist and dist < 60:
                            best_dist = dist
                            best_i = i
                    if best_i >= 0:
                        nt = notes[box][best_i]
                        used[best_i] = True
                        dt = current_time - nt["t"]
                        if dt > 0.004:
                            disp = ny - nt["y"]
                            if 0.3 * current_v * dt < disp < 1.8 * current_v * dt + 10:
                                vs = disp / dt
                                if 0.15 * shake_height < vs < 1.8 * shake_height:
                                    vel_samples.append(vs)
                                    if len(vel_samples) > 20:
                                        vel_samples.pop(0)
                                    if len(vel_samples) >= 3:
                                        current_v = float(np.median(vel_samples))
                                nt["track_n"] = nt.get("track_n", 0) + 1
                                any_moving = True
                        nt["y"] = ny
                        nt["t"] = current_time
                        # Update eta to nearest ring below or the lowest ring
                        target = min((ry for ry in ring_ys[box] if ry > ny - 5), default=max(ring_ys[box] or [shake_height * 0.85]))
                        if current_v > 10:
                            nt["eta"] = current_time + max(0.0, (target - ny) / current_v)
                        new_notes.append(nt)
                    else:
                        # New note
                        target = min((ry for ry in ring_ys[box] if ry > ny - 5), default=max(ring_ys[box] or [shake_height * 0.85]))
                        eta = current_time + max(0.0, (target - ny) / max(current_v, 50))
                        new_notes.append({"y": ny, "t": current_time, "fired": False, "track_n": 0, "eta": eta})
                # Keep un-matched only if recent and not passed
                for i, nt in enumerate(notes[box]):
                    if not used[i] and (current_time - nt["t"]) < 0.25 and nt["y"] < (max(ring_ys[box] or [999]) + 20):
                        new_notes.append(nt)
                notes[box] = new_notes
                # Fire logic (DeepFish style: lead + confirmed moving)
                for nt in notes[box]:
                    if not nt["fired"] and nt.get("track_n", 0) >= 2 and (current_time + lead) >= nt.get("eta", 1e9):
                        key = str(self.vars.get(f"tranquility_key_{box + 1}", "D"))
                        self._send_key(key, self.scan_delay)
                        nt["fired"] = True
                        any_moving = True
                        # Overlay flash
                        if fish_overlay:
                            try:
                                color = self.vars.get(f"tranquility_color_{box + 1}", "#FFFFFF")
                            except:
                                color = "#FFFFFF"
                            self.fish_overlay.draw(fish_left[box], 0, fish_right[box], tranquility_small_gap, color)
                # Check for misses (note passed target without fire)
                for nt in notes[box]:
                    if not nt["fired"]:
                        target = min((ry for ry in ring_ys[box] if ry > nt["y"] - 10), default=999)
                        if nt["y"] > target + 25:
                            self.ever_out = True
                            self.ever_note_out_high = True
                            nt["fired"] = True  # mark so not rechecked
                # Status
                if notes[box]:
                    self.status_overlay.set_line(box + 1, f"Lane {box + 1}: ", f"V={current_v:.0f} N={len(notes[box])}")
                else:
                    self.status_overlay.set_line(box + 1, f"Lane {box + 1}: ", "idle")
            if any_moving:
                last_live_t = current_time
                started = True
            initial_frames += 1
            # Expire if no activity for a while after start
            if started and (current_time - last_live_t) > 1.5:
                # End classification
                if self.ever_note_out_high or self.ever_out:
                    self.fish_caught = 0
                    self.perfect_catch = 1
                else:
                    self.fish_caught = 0
                    self.perfect_catch = 0
                self.interruptible_sleep(restart_delay)
                return
            time.sleep(self.scan_delay)
    def _enter_minigame_dreambreaker(self):
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
        fish_left, fish_top, fish_right, fish_bottom, fish_width, fish_height = self.get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self.get_areas("friend")
        # Area Calculations
        fish_center_x = int((fish_left + fish_right) / 2)
        fish_center_y = int((fish_top + fish_bottom) / 2)
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == True:
            # Position The Overlay Just Above Or Below The Fish Bar So It Does
            # Not Cover The Actual Minigame.  Show() Expects (Left, Top, Width,
            # Height) In Physical Pixels — Not Right/Bottom.
            fish_center = int((fish_top + fish_bottom) / 2)
            if fish_center > HALF_HEIGHT:
                fish_top_overlay = fish_top + fish_height + fish_height
            else:
                fish_top_overlay = fish_top - fish_height - fish_height
            overlay_width = fish_right - fish_left
            overlay_height = int(fish_height / 1.5)
            self.fish_overlay.show(fish_left, fish_top_overlay, overlay_width, overlay_height)
        # Minigame Settings
        lock_cursor = self.vars["lock_cursor"]
        self.scan_delay = float(self.vars["minigame_scan_delay"])
        restart_delay = float(self.vars["restart_delay"])
        restart_method = self.vars["restart_method"].lower()
        self.ever_out = False
        self.ever_note_out_high = False
        # Last Values (Failsafe)
        scale = get_scale_factor()
        last_left_x = 0
        last_right_x = 0
        last_fish_x = None
        last_capture_id = 0
        last_bar_size = 0
        last_bar_center = 0
        last_detection_source = 0
        while self.macro_running:
            # Check If Dxcam Is Available
            if dxcam is not None:
                self.capture_frame = self.camera.get_latest_frame()
                self.capture_id = last_capture_id + 1
            # Get Image From Self.Capture_Frame
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue

            elif self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue

            else:
                fish_img = self.capture_frame[fish_top:fish_bottom, fish_left:fish_right]
                friend_img = self.capture_frame[friend_top:friend_bottom, friend_left:friend_right]
            self.fish_overlay.clear()
            fish_x, fish_y = self.pixel_search_all(fish_img, "fish_color", "fish_tolerance")
            if fish_x is not None:
                last_fish_x = fish_x
            left_x, left_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 0, 1)
            right_x, right_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 1, 2)
            if left_x == None:
                left_x, left_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 0, 2)
            if right_x == None:
                right_x, right_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 1, 1)
            if left_x is None or right_x is None:
                detection_source = 1
                # Bars Not Found - Scan For Arrows
                arrow_x, arrow_y = self.pixel_search_all(fish_img, "arrow_color", "arrow_tolerance")
                # Reconstruct Missing Bar Edge From Previous Geometry Instead Of Mouse State
                if arrow_x is not None:
                    # Treat 0 As Unknown To Match The Previous None Semantics
                    if last_left_x == 0:
                        last_left_x = None
                    if last_right_x == 0:
                        last_right_x = None
                    # If Exactly One Edge Is Missing, Reconstruct It Using The Last Known Bar Size
                    if last_left_x is None and last_right_x is not None:
                        last_left_x = last_right_x - last_bar_size
                    elif last_right_x is None and last_left_x is not None:
                        last_right_x = last_left_x + last_bar_size
                if arrow_x is not None:
                    bar_detected = True
                    arrow_on_left_side = arrow_x < last_bar_center
                    dist_to_left = abs(arrow_x - last_left_x) if last_left_x is not None else fish_width
                    dist_to_right = abs(arrow_x - last_right_x) if last_right_x is not None else fish_width
                    proximity_threshold = int(last_bar_size / 4)
                    # Flip Decision If Wrong
                    if arrow_on_left_side:
                        if dist_to_right < dist_to_left and dist_to_right < proximity_threshold:
                            # Arrow Is Actually Closer To Right Bar  We Were Wrong!
                            arrow_on_left_side = False  # Flip the decision
                    else:
                        if dist_to_left < dist_to_right and dist_to_left < proximity_threshold:
                            # Arrow Is Actually Closer To Left Bar  We Were Wrong!
                            arrow_on_left_side = True  # Flip the decision
                    if arrow_on_left_side:
                        left_x = arrow_x
                        right_x = last_right_x
                        if right_x is None:
                            right_x = left_x + last_bar_size
                    else:
                        right_x = arrow_x
                        left_x = last_left_x
                        if left_x is None:
                            left_x = right_x - last_bar_size
            else:
                detection_source = 0
            if left_x is not None and right_x is not None:
                bar_size = right_x - left_x
                bar_center = left_x + int(bar_size / 2)
            else:
                bar_center = 0
                bar_size = 0
            # Track inside for catch rate (same as normal)
            currently_inside = False
            if left_x is not None and right_x is not None and fish_x is not None:
                currently_inside = left_x <= fish_x <= right_x
            if not currently_inside:
                self.ever_out = True
            # Friend And Fish Restart
            if restart_method == "friend_area":
                friend_x, friend_y = self.pixel_search_all(friend_img, "friends_color", "friends_tolerance")
                if friend_x is not None and friend_y is not None:
                    ended_inside = False
                    if left_x is not None and right_x is not None and fish_x is not None:
                        ended_inside = left_x <= fish_x <= right_x
                    if not ended_inside:
                        self.fish_caught = 1
                        self.perfect_catch = 1
                    else:
                        if self.ever_out:
                            self.fish_caught = 0
                            self.perfect_catch = 1
                        else:
                            self.fish_caught = 0
                            self.perfect_catch = 0
                    self.interruptible_sleep(restart_delay)
                    return

            else:
                try:
                    if fish_x is None:
                        ended_inside = False
                        if left_x is not None and right_x is not None and last_fish_x is not None:
                            ended_inside = left_x <= last_fish_x <= right_x
                        if not ended_inside:
                            self.fish_caught = 1
                            self.perfect_catch = 1
                        else:
                            if self.ever_out:
                                self.fish_caught = 0
                                self.perfect_catch = 1
                            else:
                                self.fish_caught = 0
                                self.perfect_catch = 0
                        self.interruptible_sleep(restart_delay)
                        return

                except:
                    time.sleep(self.scan_delay)
                    continue

            if lock_cursor == True:
                mouse_controller.position = (int(fish_center_x * scale), int(fish_center_y * scale))
            # Draw
            if fish_overlay == True:
                if left_x is not None:
                    self.fish_overlay.draw(x1=left_x, y1=overlay_height*0.15, x2=right_x, y2=overlay_height*0.85, color="green")
                if fish_x is not None:
                    self.fish_overlay.draw(x1=fish_x, y1=overlay_height*0.15, x2=fish_x + 10, y2=overlay_height*0.85, color="red")
            # Controller Output
            self.status_overlay.set_line(1, f"Detection Source: ", detection_source)
            self.status_overlay.set_line(2, f"Last Source: ", last_detection_source)
            if detection_source == 1 and last_detection_source == 0:
                if mouse_down == False:
                    hold_mouse()
                elif mouse_down == True:
                    release_mouse()
            # Cleanup
            last_bar_center = bar_center
            last_bar_size = bar_size
            last_capture_id = self.capture_id
            last_detection_source = detection_source
    def _enter_minigame_bellona(self):
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
        fish_left, fish_top, fish_right, fish_bottom, fish_width, fish_height = self.get_areas("fish_1_bellona")
        fish_left2, fish_top, fish_right2, fish_bottom, fish_width2, fish_height2 = self.get_areas("fish_2_bellona")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self.get_areas("friend")
        self.ever_out = False
        self.ever_note_out_high = False
        # Area Calculations
        fish_center = int((fish_left + fish_right2) / 2)
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == True:
            # Position The Overlay Just Above Or Below The Fish Bar So It Does
            # Not Cover The Actual Minigame.  Show() Expects (Left, Top, Width,
            # Height) In Physical Pixels — Not Right/Bottom.
            fish_center = int((fish_top + fish_bottom) / 2)
            if fish_center > HALF_HEIGHT:
                fish_top_overlay = fish_top + fish_height + fish_height
            else:
                fish_top_overlay = fish_top - fish_height - fish_height
            overlay_width = fish_right2 - fish_left
            overlay_height = int(fish_height / 1.5)
            self.fish_overlay.show(fish_left, fish_top_overlay, overlay_width, overlay_height)
        # Minigame Settings
        scale = get_scale_factor()
        equipment_bag_slot = str(self.vars["equipment_bag_slot"])
        bag_spam = self.vars["bag_spam"]
        lock_cursor = self.vars["lock_cursor"]
        restart_method = self.vars["restart_method"]
        bar_ratio_from_side = float(self.vars["bar_ratio_from_side"])
        restart_delay = float(self.vars["restart_delay"])
        self.scan_delay = float(self.vars["minigame_scan_delay"])
        kp = self._get_var_number("kp", 0.45)
        kd = self._get_var_number("kd", 0.35)
        # Cache Values
        right_bar_offset = fish_left2 - fish_left
        last_capture_id = 0
        last_bar_size1 = 0
        last_bar_center1 = 0
        last_bar_size2 = 0
        last_bar_center2 = 0
        last_left_x1 = 0
        last_left_x2 = 0
        last_right_x1 = 0
        last_right_x2 = 0
        last_fish_x1 = 0
        last_fish_x2 = 0
        last_error1 = 0
        last_error2 = 0
        last_time = time.perf_counter()
        while self.macro_running:
            # Check If Dxcam Is Available
            if dxcam is not None:
                self.capture_frame = self.camera.get_latest_frame()
                self.capture_id = last_capture_id + 1
            # Get Image From Self.Capture_Frame
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue

            elif self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue

            else:
                fish_img = self.capture_frame[fish_top:fish_bottom, fish_left:fish_right]
                fish_img2 = self.capture_frame[fish_top:fish_bottom, fish_left2:fish_right2]
                friend_img = self.capture_frame[friend_top:friend_bottom, friend_left:friend_right]
            # Fish Detection
            fish_x1, fish_y1 = self.pixel_search_all(fish_img, "fish_color", "fish_tolerance")
            fish_x2, fish_y2 = self.pixel_search_all(fish_img2, "fish_color", "fish_tolerance")
            fish_detected = True
            fish_detected2 = True
            if fish_x1 is None:
                fish_detected = False
            if fish_x2 is None:
                fish_detected2 = False
            # Left and Right bar detection
            # Bar 1
            left_x1, left_y1 = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 0, 1)
            right_x1, right_y1 = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 1, 2)
            if left_x1 == None:
                left_x1, left_y1 = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 0, 2)
            if right_x1 == None:
                right_x1, right_y1 = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 1, 1)
            # Bar 2
            left_x2, left_y2 = self.pixel_search_all(fish_img2, "left_color", "bar_tolerance", 0, 1)
            right_x2, right_y2 = self.pixel_search_all(fish_img2, "left_color", "bar_tolerance", 1, 2)
            if left_x2 == None:
                left_x2, left_y2 = self.pixel_search_all(fish_img2, "left_color", "bar_tolerance", 0, 2)
            if right_x2 == None:
                right_x2, right_y2 = self.pixel_search_all(fish_img2, "left_color", "bar_tolerance", 1, 1)
            bar_detected = True
            bar_detected2 = True
            # Bar 1 — fill missing edge from last known size, then compute center from its own edges
            if left_x1 is None and right_x1 is not None and last_bar_size1:
                left_x1 = right_x1 - last_bar_size1
            elif right_x1 is None and left_x1 is not None and last_bar_size1:
                right_x1 = left_x1 + last_bar_size1
            if left_x1 is not None and right_x1 is not None:
                bar_size1 = abs(right_x1 - left_x1)
                bar_center1 = left_x1 + int(bar_size1 / 2)
            else:
                # Try arrow for bar 1
                arrow_x1, arrow_y1 = self.pixel_search_all(fish_img, "arrow_color", "arrow_tolerance")
                if arrow_x1 is not None and last_bar_size1:
                    if arrow_x1 < last_bar_center1:
                        left_x1 = arrow_x1
                        right_x1 = arrow_x1 + last_bar_size1
                    else:
                        right_x1 = arrow_x1
                        left_x1 = right_x1 - last_bar_size1
                    bar_size1 = abs(right_x1 - left_x1)
                    bar_center1 = left_x1 + int(bar_size1 / 2)
                else:
                    bar_detected = False
                    bar_size1 = last_bar_size1
                    bar_center1 = last_bar_center1
            # Bar 2 — same logic, using its own edges (not bar 1's)
            if left_x2 is None and right_x2 is not None and last_bar_size2:
                left_x2 = right_x2 - last_bar_size2
            elif right_x2 is None and left_x2 is not None and last_bar_size2:
                right_x2 = left_x2 + last_bar_size2
            if left_x2 is not None and right_x2 is not None:
                bar_size2 = abs(right_x2 - left_x2)
                bar_center2 = left_x2 + int(bar_size2 / 2)
            else:
                # Try arrow for bar 2
                arrow_x2, arrow_y2 = self.pixel_search_all(fish_img2, "arrow_color", "arrow_tolerance")
                if arrow_x2 is not None and last_bar_size2:
                    if arrow_x2 < last_bar_center2:
                        left_x2 = arrow_x2
                        right_x2 = arrow_x2 + last_bar_size2
                    else:
                        right_x2 = arrow_x2
                        left_x2 = right_x2 - last_bar_size2
                    bar_size2 = abs(right_x2 - left_x2)
                    bar_center2 = left_x2 + int(bar_size2 / 2)
                else:
                    bar_detected2 = False
                    bar_size2 = last_bar_size2
                    bar_center2 = last_bar_center2
            # Track inside for catch rate (same as normal for dual)
            currently_inside1 = False
            if left_x1 is not None and right_x1 is not None and fish_x1 is not None:
                currently_inside1 = left_x1 <= fish_x1 <= right_x1
            currently_inside2 = False
            if left_x2 is not None and right_x2 is not None and fish_x2 is not None:
                currently_inside2 = left_x2 <= fish_x2 <= right_x2
            if not currently_inside1 or not currently_inside2:
                self.ever_out = True
            # Friend And Fish Restart
            if restart_method == "friend_area":
                friend_x, friend_y = self.pixel_search_all(friend_img, "friends_color", "friends_tolerance")
                if friend_x is not None and friend_y is not None:
                    ended_inside = currently_inside1 and currently_inside2
                    if not ended_inside:
                        self.fish_caught = 1
                        self.perfect_catch = 1
                    else:
                        if self.ever_out:
                            self.fish_caught = 0
                            self.perfect_catch = 1
                        else:
                            self.fish_caught = 0
                            self.perfect_catch = 0
                    self.interruptible_sleep(restart_delay)
                    return

            else:
                try:
                    if fish_x1 is None and fish_x2 is None:
                        # Treat as ended, use last known or out
                        ended_inside = False  # conservative
                        if not ended_inside:
                            self.fish_caught = 1
                            self.perfect_catch = 1
                        else:
                            if self.ever_out:
                                self.fish_caught = 0
                                self.perfect_catch = 1
                            else:
                                self.fish_caught = 0
                                self.perfect_catch = 0
                        self.interruptible_sleep(restart_delay)
                        return

                except:
                    time.sleep(self.scan_delay)
                    continue

            # print(f"bar_detected: {bar_detected}")
            # print(f"left_x: {left_x}, right_x: {right_x}")
            # print(f"bar_center: {bar_center}, bar_size: {bar_size}")
            # Bag Spam & Lock Cursor
            try:
                bag_spam_cycle += 1
            except:
                bag_spam_cycle = 0
            if bag_spam_cycle == 5:
                bag_spam_cycle = 0
                if bag_spam == True:
                    self._send_key(equipment_bag_slot)
                if lock_cursor == True:
                    mouse_controller.position = (int(shake_x / scale), int(shake_y / scale))
            # Restore From Cache
            self.fish_overlay.clear()
            if bar_detected == False:
                left_x1 = last_left_x1
                right_x1 = last_right_x1
                bar_center1 = last_bar_center1
                bar_size1 = last_bar_size1
            if fish_detected == False:
                fish_x1 = last_fish_x1
            if bar_detected2 == False:
                left_x2 = last_left_x2
                right_x2 = last_right_x2
                bar_center2 = last_bar_center2
                bar_size2 = last_bar_size2
            if fish_detected2 == False:
                fish_x2 = last_fish_x2
            # Edge Boundary For Left And Right Bar
            # Coordinates are relative to each cropped fish area (same as _enter_minigame).
            # right_bar_offset is applied only when drawing bar 2 onto the shared overlay.
            boundary1 = bar_size1 * bar_ratio_from_side if bar_size1 else 0
            boundary2 = bar_size2 * bar_ratio_from_side if bar_size2 else 0
            left_boundary1 = boundary1
            right_boundary1 = fish_width - boundary1
            left_boundary2 = boundary2
            right_boundary2 = fish_width2 - boundary2
            if fish_overlay == True:
                # Bar 1 (relative coords already match overlay origin)
                self.fish_overlay.draw(x1=left_x1, y1=overlay_height*0.15, x2=right_x1, y2=overlay_height*0.85, color="green", show_bar_center=True)
                if left_boundary1 is not None:
                    self.fish_overlay.draw(x1=left_boundary1, y1=overlay_height*0.15, x2=left_boundary1 + 15, y2=overlay_height*0.85, color="lightblue")
                if right_boundary1 is not None:
                    self.fish_overlay.draw(x1=right_boundary1 - 15, y1=overlay_height*0.15, x2=right_boundary1, y2=overlay_height*0.85, color="lightblue")
                if fish_x1 is not None:
                    self.fish_overlay.draw(x1=fish_x1, y1=overlay_height*0.15, x2=fish_x1 + 15, y2=overlay_height*0.85, color="red")
                # Bar 2 — shift by right_bar_offset so it lines up on the shared overlay
                self.fish_overlay.draw(x1=left_x2 + right_bar_offset, y1=overlay_height*0.15, x2=right_x2 + right_bar_offset, y2=overlay_height*0.85, color="green", show_bar_center=True)
                if left_boundary2 is not None:
                    self.fish_overlay.draw(x1=left_boundary2 + right_bar_offset, y1=overlay_height*0.15, x2=left_boundary2 + 15 + right_bar_offset, y2=overlay_height*0.85, color="lightblue")
                if right_boundary2 is not None:
                    self.fish_overlay.draw(x1=right_boundary2 - 15 + right_bar_offset, y1=overlay_height*0.15, x2=right_boundary2 + right_bar_offset, y2=overlay_height*0.85, color="lightblue")
                if fish_x2 is not None:
                    self.fish_overlay.draw(x1=fish_x2 + right_bar_offset, y1=overlay_height*0.15, x2=fish_x2 + 15 + right_bar_offset, y2=overlay_height*0.85, color="red")
            current_time = time.perf_counter()
            time_delta = current_time - last_time
            if time_delta < 0.001:
                time_delta = 0.001
            # Both fish_x and bar_center are relative to their own cropped area,
            # so the subtraction is valid (no absolute/relative mix).
            try:
                error1 = (fish_x1 if fish_x1 is not None else last_fish_x1) - (bar_center1 or 0)
            except TypeError:
                error1 = 0
            try:
                error2 = (fish_x2 if fish_x2 is not None else last_fish_x2) - (bar_center2 or 0)
            except TypeError:
                error2 = 0
            p_term1 = error1 / time_delta * self.scan_delay
            d_term1 = (error1 - last_error1) / time_delta
            control_signal1 = p_term1 * kp + d_term1 * kd
            p_term2 = error2 / time_delta * self.scan_delay
            d_term2 = (error2 - last_error2) / time_delta
            control_signal2 = p_term2 * kp + d_term2 * kd
            if bag_spam_cycle == 3:
                self.status_overlay.set_line(1, "Bar Velocity (1)", round(error1 - last_error1))
                self.status_overlay.set_line(2, "Distance (1)", round(error1))
                self.status_overlay.set_line(3, "Bar Velocity (2)", round(error2 - last_error2))
                self.status_overlay.set_line(4, "Distance (2)", round(error2))
            if control_signal1 > 0:
                hold_mouse(False)
            else:
                release_mouse(False)
            if control_signal2 > 0:
                hold_mouse(True)
            else:
                release_mouse(True)
            if bar_detected == True:
                last_left_x1 = left_x1
                last_right_x1 = right_x1
                last_bar_center1 = bar_center1
                last_bar_size1 = bar_size1
            if bar_detected2 == True:
                last_left_x2 = left_x2
                last_right_x2 = right_x2
                last_bar_center2 = bar_center2
                last_bar_size2 = bar_size2
            if fish_detected == True:
                last_fish_x1 = fish_x1
            if fish_detected2 == True:
                last_fish_x2 = fish_x2
            last_error1 = error1
            last_error2 = error2
            last_time = current_time
    def enter_minigame_lullaby(self):
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
        lullaby_left, lullaby_top, lullaby_right, lullaby_bottom, lullaby_width, _ = self.get_areas("lullaby")
        fish_left, fish_top, fish_right, fish_bottom, fish_width, fish_height = self.get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self.get_areas("friend")
        restart_method = self.vars.get("restart_method", "friend_area")
        restart_delay = float(self.vars.get("restart_delay", 0.5))
        self.ever_out = False
        self.ever_note_out_high = False
        # Area Calculations
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == True:
            fish_center = int((lullaby_top + lullaby_bottom) / 2)
            if fish_center > HALF_HEIGHT:
                fish_top_overlay = lullaby_top - fish_height - fish_height
            else:
                fish_top_overlay = lullaby_top + fish_height + fish_height
            overlay_width = fish_right - fish_left
            overlay_height = int(fish_height / 1.5)
            self.fish_overlay.resize(lullaby_left, fish_top_overlay, lullaby_width, overlay_height)
        # Collect all bar colors for multi-color masks
        left_colors = []
        for i in range(1, 16):
            key = "left_color" if i == 1 else f"left_color_{i}"
            tol_key = "bar_tolerance" if i == 1 else f"bar_tolerance_{i}"
            c = self.vars.get(key)
            if not c:
                break

            try:
                t = int(self.vars.get(tol_key, 8))
            except:
                t = 8
            left_colors.append((np.array(self._hex_to_bgr(c), dtype=np.int16), t))
        if not left_colors:
            left_colors = [(np.array([241, 241, 241], dtype=np.int16), 8)]
        left_bgr, bar_tolerance = left_colors[0]
        right_bgr, right_tolerance = left_colors[-1] if len(left_colors) > 1 else left_colors[0]
        # Minigame Variables
        lullaby_metronome_padding = int(self.vars["lullaby_metronome_padding"])
        lullaby_mask_lost_ratio = float(self.vars["lullaby_mask_lost_ratio"])
        # Cache Variables
        is_initial_run = True
        last_capture_id = 0
        lullaby_area_x1 = 0
        lullaby_area_x2 = 0
        lullaby_area_y1 = 0
        lullaby_area_y2 = 0
        metronome_inside = False
        last_metronome_inside = False
        # Initial Color Masks
        initial_left_mask = None
        initial_right_mask = None
        # Baseline Mask Bounding Boxes
        initial_left_coords = None
        initial_right_coords = None
        while self.macro_running:
            # Check If Dxcam Is Available
            if dxcam is not None:
                self.capture_frame = self.camera.get_latest_frame()
                self.capture_id = last_capture_id + 1
            # Get Image From Self.Capture_Frame
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue

            elif self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue

            # Initial Run
            # Find The Lullaby Area And Save The Initial Color Masks.
            if is_initial_run:
                lullaby_img = self.capture_frame[
                    lullaby_top:lullaby_bottom,
                    lullaby_left:lullaby_right
                ]
                # Current Frame As Int16 So Subtraction Cannot Overflow
                lullaby_pixels = lullaby_img.astype(np.int16)
                # Create Initial Masks (Colors Already Converted To Bgr Above)
                left_diff = np.abs(lullaby_pixels - left_bgr)
                right_diff = np.abs(lullaby_pixels - right_bgr)
                initial_left_mask = np.all(left_diff <= bar_tolerance, axis=2)
                initial_right_mask = np.all(right_diff <= right_tolerance, axis=2)
                # Get Coordinates Of The Initial Masks
                left_y, left_x = np.where(initial_left_mask)
                right_y, right_x = np.where(initial_right_mask)
                # Make Sure Both Colors Were Found
                if (len(left_x) == 0 or len(right_x) == 0):
                    time.sleep(self.scan_delay)
                    last_capture_id = self.capture_id
                    continue

                # Save Initial Mask Coordinates
                initial_left_coords = (left_x, left_y)
                initial_right_coords = (right_x, right_y)
                # Calculate The Complete Initial Lullaby Area
                lullaby_area_x1 = min(left_x.min(), right_x.min())
                lullaby_area_x2 = max(left_x.max(), right_x.max())
                lullaby_area_y1 = min(left_y.min(), right_y.min())
                lullaby_area_y2 = max(left_y.max(), right_y.max())
                # Add Padding For The Metronome
                lullaby_area_x1 = max(0, lullaby_area_x1 - lullaby_metronome_padding)
                lullaby_area_x2 = min(lullaby_img.shape[1], lullaby_area_x2 + lullaby_metronome_padding)
                lullaby_area_y1 = max(0, lullaby_area_y1 - lullaby_metronome_padding)
                lullaby_area_y2 = min(lullaby_img.shape[0], lullaby_area_y2 + lullaby_metronome_padding)
                # Switch To The Smaller Region After Initialization.
                is_initial_run = False
            # Subsequent Runs
            # Only Capture/Process The Smaller Lullaby Region.
            else:
                lullaby_img2 = self.capture_frame[
                    lullaby_top + lullaby_area_y1:
                    lullaby_top + lullaby_area_y2,
                    lullaby_left + lullaby_area_x1:
                    lullaby_left + lullaby_area_x2
                ]
                # Create Current Color Masks Only Inside The Small Area
                current_pixels = lullaby_img2.astype(np.int16)
                current_left_mask = np.all(np.abs(current_pixels - left_bgr) <= bar_tolerance, axis=2)
                current_right_mask = np.all(np.abs(current_pixels - right_bgr) <= right_tolerance, axis=2)
                # Compare Current Masks Against The Initial Masks.
                # The Initial Masks Are In Full Lullaby Coordinates,
                # So Crop Them To The Same Smaller Region First.
                initial_left_small = initial_left_mask[
                    lullaby_area_y1:lullaby_area_y2,
                    lullaby_area_x1:lullaby_area_x2
                ]
                initial_right_small = initial_right_mask[
                    lullaby_area_y1:lullaby_area_y2,
                    lullaby_area_x1:lullaby_area_x2
                ]
                # Pixels That Existed Initially But Disappeared Now
                left_missing_mask = (initial_left_small & ~current_left_mask)
                right_missing_mask = (initial_right_small & ~current_right_mask)
                # Calculate How Much Of The Original Mask Disappeared
                initial_left_count = np.count_nonzero(initial_left_small)
                initial_right_count = np.count_nonzero(initial_right_small)
                left_missing_count = np.count_nonzero(left_missing_mask)
                right_missing_count = np.count_nonzero(right_missing_mask)
                # Calculate The Total Mask Count
                initial_mask_count = initial_left_count + initial_right_count
                current_mask_count = (np.count_nonzero(current_left_mask) + np.count_nonzero(current_right_mask))
                # If The Current Mask Is Larger Than The Initial Mask,
                # Update The Initial Mask Count To Prevent The Metronome
                # From Occupying Too Much Of The Baseline.
                if current_mask_count > initial_mask_count:
                    initial_mask_count = current_mask_count
                mask_missing_count = left_missing_count + right_missing_count
                self.status_overlay.set_line(1, "Initial Mask Count: ", initial_mask_count)
                self.status_overlay.set_line(2, "Current Mask Count: ", mask_missing_count)
                if left_missing_count + right_missing_count == 0:
                    continue # Invalid detection

                # Decide whether the metronome is inside or not
                # Target: Ratio would be 0.28
                metronome_ratio = mask_missing_count / initial_mask_count
                lullaby_mask_contain_ratio = 1 - lullaby_mask_lost_ratio
                if metronome_ratio < lullaby_mask_contain_ratio:
                    metronome_inside = True
                else:
                    metronome_inside = False
                self.status_overlay.set_line(3, "Metronome Ratio: ", round(metronome_ratio, 2))
                # Track for catch rate (same as notes)
                if not metronome_inside:
                    self.ever_out = True
                    if metronome_ratio > 0.9:
                        self.ever_note_out_high = True
                # Metronome Logic (Metronome_Inside = True)
                if not metronome_inside == False:
                    if last_metronome_inside != metronome_inside:
                        hold_mouse()
                        time.sleep(0.05)
                        release_mouse()
            last_metronome_inside = metronome_inside
            # Restart logic like _enter_minigame
            if restart_method == "friend_area":
                friend_img = self.capture_frame[friend_top:friend_bottom, friend_left:friend_right]
                friend_x, friend_y = self.pixel_search_all(friend_img, "friends_color", "friends_tolerance")
                if friend_x is not None and friend_y is not None:
                    # Set catch status
                    if not metronome_inside:
                        self.fish_caught = 1
                        self.perfect_catch = 1
                    else:
                        if self.ever_out or self.ever_note_out_high:
                            self.fish_caught = 0
                            self.perfect_catch = 1
                        else:
                            self.fish_caught = 0
                            self.perfect_catch = 0
                    self.interruptible_sleep(restart_delay)
                    return

            else:
                # Fallback: if no metronome detection for a while or similar, but for now use friend or end on lost
                pass

            time.sleep(self.scan_delay)
            last_capture_id = self.capture_id

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
        noiseform_left, noiseform_top, noiseform_right, noiseform_bottom, noiseform_width, noiseform_height = self.get_areas("noiseform")
        # Area Calculations
        note_height = fish_bottom - shake_top
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_center_x_relative = fish_width / 2
        fish_center_y = int((fish_top + fish_bottom) / 2)
        fish_overlay = self.vars["fish_overlay"]
        if fish_overlay == True:
            # Position The Overlay Just Above Or Below The Fish Bar So It Does
            # Not Cover The Actual Minigame.  Show() Expects (Left, Top, Width,
            # Height) In Physical Pixels — Not Right/Bottom.
            if fish_center_y > HALF_HEIGHT:
                fish_top_overlay = fish_top + fish_height + fish_height
            else:
                fish_top_overlay = fish_top - fish_height - fish_height
            overlay_width = fish_right - fish_left
            overlay_height = int(fish_height / 1.5)
            self.fish_overlay.resize(fish_left, fish_top_overlay, overlay_width, overlay_height)
        # Minigame Settings
        scale = get_scale_factor()
        equipment_bag_slot = str(self.vars["equipment_bag_slot"])
        bag_spam = self.vars["bag_spam"]
        lock_cursor = self.vars["lock_cursor"]
        fishing_mode = self.vars["fishing_mode"].lower()
        special_rod = self.vars["special_rod"].lower()
        restart_method = self.vars["restart_method"]
        bar_ratio_from_side = float(self.vars["bar_ratio_from_side"])
        restart_delay = float(self.vars["restart_delay"])
        self.scan_delay = float(self.vars["minigame_scan_delay"])
        controller_mode = self.vars["controller_mode"].lower()
        kp = max(abs(float(self.vars["kp"])), 0.01)
        kd = max(abs(float(self.vars["kd"])), 0.01)
        stopping_distance = max(abs(float(self.vars["stopping_distance"])), 0.01)
        velocity_smoothing = min(max(abs(float(self.vars["velocity_smoothing"])), 0.01), 1.0)
        # Utility Settings
        pinion_note_ratio = float(self.vars["pinion_note_ratio"])
        # State Flags & Timers
        is_initial_run = True
        bar_detected = False
        self.catch_success = 0
        self.ever_out = False
        self.ever_note_out_high = False
        pinion_note_ratio_2 = 0
        last_time = time.perf_counter()
        # Teleport Detection Variables  Prevent Sudden Jumps Unless Consistent
        # Use Percentage-Based Threshold: If Line Moves > 50% Of Screen Width, It'S Likely Detection Error
        # At 1032Px Width, 50%  ~516Px, Which Catches Major Detection Errors While Allowing Natural Movement
        TELEPORT_THRESHOLD_PERCENT = 0.50  # 50% of fish area width
        TELEPORT_THRESHOLD = int(fish_center_x_relative * TELEPORT_THRESHOLD_PERCENT)  # Convert to pixels
        TELEPORT_CONFIRM_TIME = 0.15  # Time in seconds to confirm a teleport (150ms)
        # Tracking For Potential Teleports
        potential_teleport_target_left = None
        potential_teleport_target_right = None
        potential_teleport_left_bar = None
        potential_teleport_right_bar = None
        teleport_first_detected_time = None
        initial_target_gap = None
        # Current Minigame Frame Tracking
        bar_size = 0
        bar_center = 0
        error = 0
        line_coords = []
        note_x = 0
        note_y_ratio = 0
        time_delta = 0
        # Failsafe & Previous Frame Tracking (History)
        last_capture_id = 0
        last_fish_x = fish_center_x_relative
        last_fish_x2 = None
        last_left_x = fish_center_x_relative - (fish_width * 0.15)
        last_right_x = fish_center_x_relative + (fish_width * 0.15)
        last_bar_center = fish_center_x_relative
        last_bar_size = 0
        last_error = 0
        # Velocities & Mechanics
        right_bar_cycle = 0
        bag_spam_cycle = 0
        color_check_bar_velocity = 0.0
        color_check_target_velocity = 0.0
        time.sleep(0.1)
        # Loop
        while self.macro_running:
            current_time = time.perf_counter()
            # Check If Dxcam Is Available
            if dxcam is not None:
                self.capture_frame = self.camera.get_latest_frame()
                self.capture_id = last_capture_id + 1
            # Get Image From Self.Capture_Frame
            if self.capture_id == last_capture_id:
                time.sleep(self.scan_delay)
                continue

            elif self.capture_frame is None:
                time.sleep(self.scan_delay)
                continue

            else:
                shake_img = self.capture_frame[shake_top:fish_bottom, fish_left:fish_right]
                fish_img = self.capture_frame[fish_top:fish_bottom, fish_left:fish_right]
                friend_img = self.capture_frame[friend_top:friend_bottom, friend_left:friend_right]
                noiseform_img = self.capture_frame[noiseform_top:noiseform_bottom, noiseform_left:noiseform_right]
                frame_interpolation = False
            # Reset Per-Frame Detection So A Failed Line Scan Cannot
            # Reuse Stale Coordinates From The Previous Iteration.
            left_x = None
            right_x = None
            fish_x = None
            fish_x2 = None
            # Fish Detection
            fish_x, fish_y = self.pixel_search_all(fish_img, "fish_color", "fish_tolerance")
            if fish_x is not None:
                fish_detected = True
            else:
                fish_detected = False
            # Bar Detection (Color, Line or Both)
            if fishing_mode == "color":
                left_x, left_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 0, 1)
                right_x, right_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 1, 2)
                if left_x == None:
                    left_x, left_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 0, 2)
                if right_x == None:
                    right_x, right_y = self.pixel_search_all(fish_img, "left_color", "bar_tolerance", 1, 1)
                # print(f"Raw coordinates: {left_x}, {right_x}, {fish_x}")
                # Check If We Should Scan For Arrows
                if left_x is not None and right_x is not None:
                    bar_detected = True
                    self.status_overlay.set_line(1, "Detection Source: ", "Bar")
                elif left_x is not None and (last_right_x is not None or last_bar_size):
                    # Only The Left Edge Was Found — Keep The Bar Live And
                    # Fill The Missing Right Edge From Last Size / Last Right.
                    if last_bar_size:
                        right_x = left_x + last_bar_size
                    elif last_right_x is not None:
                        right_x = last_right_x
                    bar_detected = True
                elif right_x is not None and (last_left_x is not None or last_bar_size):
                    # Only The Right Edge Was Found — Fill The Missing Left.
                    if last_bar_size:
                        left_x = right_x - last_bar_size
                    elif last_left_x is not None:
                        left_x = last_left_x
                    bar_detected = True
                else:
                    # Try Arrow
                    bar_detected = False
                    # Bars Not Found - Scan For Arrows
                    arrow_x, arrow_y = self.pixel_search_all(fish_img, "arrow_color", "arrow_tolerance")
                    try: last_bar_size = float(last_bar_size)
                    except: last_bar_size = 0
                    try: last_bar_center = float(last_bar_center)
                    except: last_bar_center = 0
                    # Reconstruct Missing Bar Edge From Previous Geometry Instead Of Mouse State
                    if arrow_x is not None:
                        # Treat 0 As Unknown To Match The Previous None Semantics
                        if last_left_x == 0:
                            last_left_x = None
                        if last_right_x == 0:
                            last_right_x = None
                    if arrow_x is not None:
                        # If we have previous bar data, determine which side the arrow is on
                        bar_detected = True
                        if last_bar_center is not None and bar_size is not None and bar_size > 0:
                            arrow_on_left_side = arrow_x < last_bar_center
                            dist_to_left = abs(arrow_x - last_left_x) if last_left_x is not None else fish_width
                            dist_to_right = abs(arrow_x - last_right_x) if last_right_x is not None else fish_width
                            if bar_size is not None:
                                proximity_threshold = int(bar_size / 4)
                            else:
                                proximity_threshold = int(last_bar_size / 4)
                            # Flip decision if wrong
                            if arrow_on_left_side:
                                if dist_to_right < dist_to_left and dist_to_right < proximity_threshold:
                                    # Arrow is actually closer to RIGHT bar - we were wrong!
                                    arrow_on_left_side = False  # Flip the decision
                            else:
                                if dist_to_left < dist_to_right and dist_to_left < proximity_threshold:
                                    # Arrow is actually closer to LEFT bar - we were wrong!
                                    arrow_on_left_side = True  # Flip the decision
                            if arrow_on_left_side:
                                left_x = arrow_x
                                right_x = last_right_x
                                if right_x is None:
                                    right_x = left_x + last_bar_size
                            else:
                                right_x = arrow_x
                                left_x = last_left_x
                                if left_x is None:
                                    left_x = right_x - last_bar_size
                            self.status_overlay.set_line(1, "Detection Source: ", "Arrows (Last center found)")
                        # Fallback: Try to establish initial box size from previous positions
                        elif last_left_x is not None and last_right_x is not None:
                            bar_size = last_right_x - last_left_x
                            last_bar_center = (last_left_x + last_right_x) / 2
                            # Determine side based on arrow position relative to last center
                            if arrow_x < last_bar_center:
                                left_x = arrow_x
                                right_x = left_x + bar_size
                            else:
                                right_x = arrow_x
                                left_x = right_x - bar_size
                            self.status_overlay.set_line(1, "Detection Source: ", "Arrows (Cache found)")
                    else:
                        # Use Cache
                        bar_detected = False
                        self.status_overlay.set_line(1, "Detection Source: ", "Cache")
                if left_x is not None and right_x is not None:
                    bar_center = int((left_x + right_x) / 2)
                    bar_size = right_x - left_x
                else:
                    bar_center = 0
                    bar_size = 0
            elif fishing_mode == "line":
                # Line Mode: Handle Cache Logic Inside The Branch
                line_coords = self._detect_lines_in_frame(fish_img)
                bar_detected = False
                fish_detected = False
                if len(line_coords) > 2:
                    if is_initial_run or initial_target_gap is None:
                        # Initial Run: Find 2 Closest Lines To Center As Target Lines
                        distance_coords = sorted([(abs(coord - fish_center_x_relative), coord) for coord in line_coords], key=lambda x: x[0])
                        target_pair = sorted([distance_coords[0][1], distance_coords[1][1]])
                        fish_x = target_pair[0]
                        fish_x2 = target_pair[1]
                        initial_target_gap = fish_x2 - fish_x
                        # Find Bars - Closest To Left Of Left Target, Closest To Right Of Right Target
                        left_candidates = [x for x in line_coords if x < fish_x]
                        right_candidates = [x for x in line_coords if x > fish_x2]
                        left_x = max(left_candidates) if left_candidates else fish_x
                        right_x = min(right_candidates) if right_candidates else fish_x2
                        if int(fish_width / 50) < (fish_x2 - fish_x):
                            fish_x2 = fish_x + int(fish_width / 50)
                            right_x = target_pair[1]
                        # Store For Next Run
                        last_fish_x = fish_x
                        last_fish_x2 = fish_x2
                        last_left_x = left_x
                        last_right_x = right_x
                        # print(f"📏 Initial: Target=({fish_x}, {fish_x2}), Gap={initial_target_gap}, Bars=({left_x}, {right_x})")
                        self.status_overlay.set_line(1, "Initial Positions: ", f"{fish_x}, {left_x}, {right_x}")
                        is_initial_run = False
                    else:
                        # Subsequent Runs: Simple Rules
                        # Rule 1: Find Pair With Gap Matching initial_target_gap
                        best_gap_diff = float('inf')
                        fish_x = last_fish_x
                        fish_x2 = last_fish_x2
                        for i in range(len(line_coords) - 1):
                            curr_left = line_coords[i]
                            curr_right = line_coords[i + 1]
                            curr_gap = curr_right - curr_left
                            gap_diff = abs(curr_gap - initial_target_gap)
                            if gap_diff < best_gap_diff:
                                best_gap_diff = gap_diff
                                fish_x = curr_left
                                fish_x2 = curr_right
                        # If Best Gap Is More Than 4X Initial Gap, Keep Old Positions
                        if fish_x is not None and fish_x2 is not None:
                            actual_gap = fish_x2 - fish_x
                        else:
                            actual_gap = 6 * (SCREEN_WIDTH / 1920)
                        if actual_gap > initial_target_gap * 4:
                            fish_x = last_fish_x
                            fish_x2 = last_fish_x2
                        # Rule 2: Bars  Line Closest To Old Bar Position
                        # Critical: Exclude Target Lines From Bar Candidates
                        other_lines = [x for x in line_coords if x != fish_x and x != fish_x2]
                        if len(other_lines) >= 2:
                            # We Have At Least 2 Nontarget Lines - Pick Closest To Last Positions
                            if last_left_x is not None:
                                left_x = min(other_lines, key=lambda x: abs(x - last_left_x))
                            else:
                                left_x = other_lines[0]
                            # Find Closest To Last Right Bar (Excluding The One We Picked For Left)
                            remaining_lines = [x for x in other_lines if x != left_x]
                            if remaining_lines and last_right_x is not None:
                                right_x = min(remaining_lines, key=lambda x: abs(x - last_right_x))
                            elif remaining_lines:
                                right_x = remaining_lines[0]
                            else:
                                # Should Not Happen If Len(Other_Lines) > 2
                                right_x = last_right_x if last_right_x is not None else fish_x2
                        elif len(other_lines) == 1:
                            # Only 3 Total Lines (2 Target + 1 Other)
                            # Assign The Single Line To Closest Bar, Use Last Position For The Other
                            single_line = other_lines[0]
                            if last_left_x is not None and last_right_x is not None:
                                # Determine Which Bar This Line Is Closer To
                                dist_to_left = abs(single_line - last_left_x)
                                dist_to_right = abs(single_line - last_right_x)
                                if dist_to_left < dist_to_right:
                                    left_x = single_line
                                    right_x = last_right_x  # Use last position
                                else:
                                    right_x = single_line
                                    left_x = last_left_x  # Use last position
                            else:
                                # No Previous Positions - Just Assign To Left Bar
                                left_x = single_line
                                right_x = fish_x2  # Fallback
                        else:
                            # No Other Lines Besides Targets (Only 2 Total Lines)
                            # Use Last Known Bar Positions Only  Never Use Target Lines As Bars
                            left_x = last_left_x if last_left_x is not None else fish_x
                            right_x = last_right_x if last_right_x is not None else fish_x2
                    # Percentage-Based Anti-Teleport Validation
                    # Check If Lines Jumped More Than Threshold (Likely Detection Error Or Occlusion)
                    if last_fish_x is not None and last_fish_x2 is not None:
                        # Calculate Actual Jump Distances
                        try: fish_x = float(fish_x)
                        except: fish_x = fish_width / 2
                        try: fish_x2 = float(fish_x2)
                        except: fish_x2 = fish_width / 2
                        try: left_x = float(left_x)
                        except: left_x = fish_width / 2
                        try: right_x = float(right_x)
                        except: right_x = fish_width / 2
                        target_left_jump = abs(fish_x - last_fish_x)
                        target_right_jump = abs(fish_x2 - last_fish_x2)
                        left_bar_jump = abs(left_x - last_left_x) if last_left_x is not None else 0
                        right_bar_jump = abs(right_x - last_right_x) if last_right_x is not None else 0
                        max_jump = max(target_left_jump, target_right_jump, left_bar_jump, right_bar_jump)
                        # If Movement Exceeds Threshold Percentage Of Screen Width, It Might Be A Teleport
                        if max_jump > TELEPORT_THRESHOLD:
                            # Potential Teleport - Check If It'S Consistent At This New Position
                            if (potential_teleport_target_left == fish_x and potential_teleport_target_right == fish_x2 and potential_teleport_left_bar == left_x and potential_teleport_right_bar == right_x):
                                # Same Position Detected Again - Track Time
                                if teleport_first_detected_time is None:
                                    teleport_first_detected_time = current_time
                                # Check If Teleport Has Been Consistent Long Enough
                                time_since_first_detection = current_time - teleport_first_detected_time
                                if time_since_first_detection >= TELEPORT_CONFIRM_TIME:
                                    # Teleport Confirmed - Accept New Positions
                                    # print(f"⚠️ TELEPORT CONFIRMED after {time_since_first_detection:.3f}s - Accepting new positions (jump: {max_jump:.0f}px > {TELEPORT_THRESHOLD}px threshold)")
                                    self.status_overlay.set_line(1, "Teleport confirmed after: ", time_since_first_detection)
                                    last_fish_x = fish_x
                                    last_fish_x2 = fish_x2
                                    last_left_x = left_x
                                    last_right_x = right_x
                                    # Reset Teleport Tracking
                                    potential_teleport_target_left = None
                                    potential_teleport_target_right = None
                                    potential_teleport_left_bar = None
                                    potential_teleport_right_bar = None
                                    teleport_first_detected_time = None
                                else:
                                    # Still Confirming - Use Old Positions For Tracking
                                    self.status_overlay.set_line(1, "Potential Teleport: ", f"{max_jump:.0f}px > {TELEPORT_THRESHOLD}px")
                                    # print(f"⏳ Potential teleport (jump: {max_jump:.0f}px > {TELEPORT_THRESHOLD}px, confirming: {time_since_first_detection:.3f}s/{TELEPORT_CONFIRM_TIME}s) - Using last positions")
                                    fish_x = last_fish_x
                                    fish_x2 = last_fish_x2
                                    left_x = last_left_x
                                    right_x = last_right_x
                            else:
                                # New Potential Teleport Position - Start Tracking
                                potential_teleport_target_left = fish_x
                                potential_teleport_target_right = fish_x2
                                potential_teleport_left_bar = left_x
                                potential_teleport_right_bar = right_x
                                teleport_first_detected_time = current_time
                                # Use Old Positions While Confirming
                                self.status_overlay.set_line(1, "New Teleport: ", f"{max_jump:.0f}px > {TELEPORT_THRESHOLD}px")
                                # print(f"🔍 New teleport candidate detected (jump: {max_jump:.0f}px > {TELEPORT_THRESHOLD}px threshold) - Starting confirmation")
                                fish_x = last_fish_x
                                fish_x2 = last_fish_x2
                                left_x = last_left_x
                                right_x = last_right_x
                        else:
                            # Normal Movement - Accept Immediately And Reset Teleport Tracking
                            last_fish_x = fish_x
                            last_fish_x2 = fish_x2
                            last_left_x = left_x
                            last_right_x = right_x
                            potential_teleport_target_left = None
                            potential_teleport_target_right = None
                            potential_teleport_left_bar = None
                            potential_teleport_right_bar = None
                            teleport_first_detected_time = None
                    else:
                        # First Run - Just Accept Positions
                        last_fish_x = fish_x
                        last_fish_x2 = fish_x2
                        last_left_x = left_x
                        last_right_x = right_x
                # Line Mode Previously Never Set Bar_Detected / Bar_Center, So
                # The Overlay Could Move (left_x/right_x) While Predictive
                # Velocity Stayed At 0 (Bar_Center Frozen At Last_Bar_Center).
                if left_x is not None and right_x is not None:
                    bar_detected = True
                    bar_size = right_x - left_x
                    bar_center = (left_x + right_x) / 2.0
                if fish_x is not None:
                    fish_detected = True
            # Friend And Fish Restart
            if restart_method == "friend_area":
                friend_x, friend_y = self.pixel_search_all(friend_img, "friends_color", "friends_tolerance")
                if friend_x is not None and friend_y is not None:
                    # Classify catch based on tracking
                    ended_inside = False
                    if left_x is not None and right_x is not None and fish_x is not None:
                        ended_inside = left_x <= fish_x <= right_x
                    if not ended_inside:
                        self.fish_caught = 1
                        self.perfect_catch = 1
                    else:
                        if self.ever_out or self.ever_note_out_high:
                            self.fish_caught = 0
                            self.perfect_catch = 1
                        else:
                            self.fish_caught = 0
                            self.perfect_catch = 0
                    self.interruptible_sleep(restart_delay)
                    return

            else:
                try:
                    if fish_x is None:
                        # Same classification when minigame ends (fish disappears)
                        ended_inside = False
                        # Use last known if available, but since fish_x is None, treat as out or use last
                        if left_x is not None and right_x is not None and last_fish_x is not None:
                            ended_inside = left_x <= last_fish_x <= right_x
                        if not ended_inside:
                            self.fish_caught = 1
                            self.perfect_catch = 1
                        else:
                            if self.ever_out or self.ever_note_out_high:
                                self.fish_caught = 0
                                self.perfect_catch = 1
                            else:
                                self.fish_caught = 0
                                self.perfect_catch = 0
                        self.interruptible_sleep(restart_delay)
                        return

                except:
                    time.sleep(self.scan_delay)
                    continue

            # print(f"bar_detected: {bar_detected}")
            # print(f"left_x: {left_x}, right_x: {right_x}")
            # print(f"bar_center: {bar_center}, bar_size: {bar_size}")
            # Bag Spam & Lock Cursor
            bag_spam_cycle += 1
            if bag_spam_cycle == 5:
                bag_spam_cycle = 0
                if bag_spam == True:
                    self._send_key(equipment_bag_slot, float(self.scan_delay / 3))
                if lock_cursor == True:
                    mouse_controller.position = (int(shake_x / scale), int(shake_y / scale))
            # Restore From Cache
            self.fish_overlay.clear()
            if bar_detected == False:
                left_x = last_left_x
                right_x = last_right_x
                bar_center = last_bar_center
                bar_size = last_bar_size
                bar_detected = True
            if fish_detected == False:
                fish_x = last_fish_x
                fish_detected = True
            # Set Status
            if bar_center is not None and last_bar_center is not None:
                bar_velocity2 = round(bar_center - last_bar_center, 2)
                self.status_overlay.set_line(2, "Bar Velocity: ", bar_velocity2)
            else:
                bar_velocity2 = 0
                self.status_overlay.set_line(2, "", "")
            # Note Detection
            if special_rod == "pinion":
                note_x, note_y = self.pixel_search_all(shake_img, "pinion_notes_color", "pinion_notes_tolerance")
                if note_x is not None and note_y is not None:
                    note_y_ratio = round(float(note_y / note_height), 2)
                    pinion_error = abs((bar_center - note_x) / fish_width)
                    if pinion_error > 0.4:
                        pinion_note_ratio_2 = pinion_note_ratio / 2
                    else:
                        pinion_note_ratio_2 = pinion_note_ratio
                    if note_y_ratio > pinion_note_ratio_2:
                        fish_x = note_x
                else:
                    note_y_ratio = 0.0
                if fish_x == note_x and last_fish_x != note_x:
                    last_fish_x = note_x
                    last_left_x = left_x
                    last_right_x = right_x
                    last_bar_center = bar_center
                    last_bar_size = bar_size
                self.status_overlay.set_line(4, "Note Ratio: ", f"{round(note_y_ratio, 2)}/{pinion_note_ratio_2}")
                # print("Note Ratio: ", note_y_ratio, " Pinion Ratio: ", pinion_note_ratio)
                # print("Fish: ", fish_x, " Note: ", note_x)
            else:
                # print("Note Tracking Disabled")
                note_y_ratio = 0.0
            # Track whether fish/note is inside the bar for catch classification
            currently_inside = False
            if left_x is not None and right_x is not None and fish_x is not None:
                currently_inside = left_x <= fish_x <= right_x
            if not currently_inside:
                self.ever_out = True
            # For notes and shapes: high note ratio while out -> normal catch (not perfect)
            if special_rod in "pinion":
                if note_y_ratio > 0.9 and not currently_inside:
                    self.ever_note_out_high = True
            else:
                # For normal / reverse / dual the ever_out is enough
                pass

            # Edge Boundary
            if bar_size is not None:
                boundary = bar_size * bar_ratio_from_side
                left_boundary = boundary
                right_boundary = fish_right - boundary - fish_left
            else:
                boundary = 0
                left_boundary = 0
                right_boundary = fish_width
            # print("Boundary: ", left_boundary, right_boundary, " Fish: ", fish_x)
            # print("Last Cache: ", bar_center - last_bar_center)
            # Clamp Extreme Values
            if left_x is not None:
                left_x = min(abs(left_x), fish_width)
            if right_x is not None:
                right_x = min(abs(right_x), fish_width)
            if fish_x is not None:
                fish_x = min(abs(fish_x), fish_width)
            # Recompute Bar Geometry From The Same Edges The Overlay Draws
            # So Predictive Velocity Matches What The User Sees.
            if left_x is not None and right_x is not None:
                bar_size = right_x - left_x
                bar_center = (left_x + right_x) / 2.0
            # Fish Overlay
            if fish_overlay == True:
                if fishing_mode == "color":
                    self.fish_overlay.draw(
                        x1=left_x, y1=overlay_height*0.15, x2=right_x, y2=overlay_height*0.85, color="green",
                        show_bar_center=True
                    )
                    if left_boundary is not None:
                        self.fish_overlay.draw(
                            x1=left_boundary, y1=overlay_height*0.15, x2=left_boundary + 15, y2=overlay_height*0.85, color="lightblue"
                        )
                    if right_boundary is not None:
                        self.fish_overlay.draw(
                            x1=right_boundary - 15, y1=overlay_height*0.15, x2=right_boundary, y2=overlay_height*0.85, color="lightblue"
                        )
                    if fish_x is not None:
                        self.fish_overlay.draw(
                            x1=fish_x, y1=overlay_height*0.15, x2=fish_x + 10, y2=overlay_height*0.85, color="red"
                        )
                else:
                    if bar_center > 0 and bar_size > 0 and fish_x > 0:
                        self.fish_overlay.draw(
                            x1=left_x, y1=overlay_height*0.15, x2=right_x, y2=overlay_height*0.85, color="green",
                            show_bar_center=True
                        )
                        self.fish_overlay.draw(
                            x1=fish_x, y1=overlay_height*0.15, x2=fish_x + 10, y2=overlay_height*0.85, color="red",
                        )
                    else:
                        for pos in range(len(line_coords)):
                            self.fish_overlay.draw(x1=line_coords[pos], y1=overlay_height*0.15, x2=line_coords[pos], y2=overlay_height*0.85, color="green")
            # Time Delta Is Measured Between Captured Frames.
            time_delta = current_time - last_time
            if time_delta < 0.001:
                time_delta = 0.001
            # print("(left_x - last_left_x) / time_delta:", (left_x - last_left_x) / self.scan_delay)
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
                if controller_mode == "default":
                    # Normal: Traditional Pd Controller
                    if is_initial_run == True:
                        control_signal = 0
                        last_error = error
                    else:
                        p_term_multiplier = time_delta / self.scan_delay
                        p_term = int(error / p_term_multiplier) * kp
                        d_term = ((error - last_error) / time_delta) * kd
                        control_signal = p_term + d_term
                        # Tracking Override: If notes are detected use simple tracking
                        if special_rod == "pinion" and not left_x <= fish_x <= right_x:
                            control_signal = error
                        last_error = error
                elif controller_mode == "steady":
                    # ASYMMETRIC DAMPING CONTROL
                    # Strong braking when approaching target (prevents overshoot)
                    # Weak damping when chasing target (allows fast catch-up)
                    if is_initial_run == True:
                        control_signal = 0
                        last_error = error
                    else:
                        p_term_multiplier = time_delta / self.scan_delay
                        p_term = int(error / p_term_multiplier) * kp
                        bar_velocity = bar_center - last_bar_center
                        error_magnitude_decreasing = abs(error) < abs(last_error)
                        bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
                        if error_magnitude_decreasing and bar_moving_toward_target:
                            # APPROACHING TARGET - Very strong damping to prevent overshoot (5x)
                            steady_kd_multiplier = 5.0
                        else:
                            # CHASING TARGET - Minimal damping to allow fast movement (0.2x)
                            steady_kd_multiplier = 0.2
                        # Tracking Override: If notes are detected the KD multiplier 
                        # is calculated based on error
                        if special_rod == "pinion":
                            pinion_error = min(300, abs(error))
                            pinion_error_ratio = abs(pinion_error - 300) / 60
                            if pinion_error_ratio < 0.5:
                                steady_kd_multiplier = 0
                            else:
                                steady_kd_multiplier = pinion_error_ratio
                        d_term = ((error - last_error) / time_delta) * kd * steady_kd_multiplier
                        control_signal = p_term + d_term
                        last_error = error
                elif controller_mode == "predictive":
                    # Predictive: Predictive Controller With Linear Stopping Distance And Counter-thrust
                    # Init Failsafe
                    if color_check_bar_velocity is None:
                        color_check_bar_velocity = 0.0
                    if color_check_target_velocity is None:
                        color_check_target_velocity = 0.0
                    # Missing Data Failsafe
                    if fish_x is None or bar_center is None:
                        control_signal = -30
                    # Calculate Velocities
                    if last_bar_center is not None and last_fish_x is not None:
                        if time_delta > 0:
                            raw_bar_velocity = (bar_center - last_bar_center) / time_delta
                            # If The Center Is Unchanged But The Overlay Edges Moved
                            # (Resize / One-Edge Fill), Use Average Edge Velocity.
                            if (
                                raw_bar_velocity == 0
                                and last_left_x is not None
                                and last_right_x is not None
                                and left_x is not None
                                and right_x is not None
                            ):
                                edge_velocity = (
                                    (left_x - last_left_x) + (right_x - last_right_x)
                                ) / (2.0 * time_delta)
                                if edge_velocity != 0:
                                    raw_bar_velocity = edge_velocity
                            raw_target_velocity = (fish_x - last_fish_x) / time_delta
                            color_check_bar_velocity = (velocity_smoothing * raw_bar_velocity + 
                                                        (1 - velocity_smoothing) * color_check_bar_velocity)
                            color_check_target_velocity = (velocity_smoothing * raw_target_velocity + 
                                                            (1 - velocity_smoothing) * color_check_target_velocity)
                    # Calculate Error And Relative Velocity First
                    try:
                        relative_velocity = float(color_check_bar_velocity - color_check_target_velocity)
                    except:
                        color_check_bar_velocity = 0
                        color_check_target_velocity = 0
                        control_signal = -30
                    # Nan Guard After Variables Are Defined
                    if not np.isfinite(relative_velocity):
                        control_signal = -30
                    # Calculate Stopping Distance Based On Relative Velocity
                    stopping_distance2 = abs(relative_velocity) * stopping_distance
                    if left_x <= fish_x <= right_x:
                        # On-bar: Use Stopping-distance / Counter-thrust Logic
                        if error > stopping_distance2:
                            # Bar Is Left Of Fish Beyond Stopping Distance → Hold To Move Right
                            self.status_overlay.set_line(3, "Tracking:", "> (Chase)")
                            control_signal = 30
                        elif error < -stopping_distance2:
                            # Bar Is Right Of Fish Beyond Stopping Distance → Release To Move Left
                            self.status_overlay.set_line(3, "Tracking:", "< (Chase)")
                            control_signal = -30
                        else:
                            # Within Stopping Distance — Counter-thrust Based On Relative Velocity
                            if relative_velocity > 0:
                                # Bar Moving Right Relative To Fish → Release (Apply Left Thrust)
                                self.status_overlay.set_line(3, "Tracking:", "< (Relative)")
                                control_signal = -30
                            else:
                                # Bar Moving Left Relative To Fish → Hold (Apply Right Thrust)
                                self.status_overlay.set_line(3, "Tracking:", "> (Relative)")
                                control_signal = 30
                    else:
                        control_signal = kp * error + kd * relative_velocity
                        self.status_overlay.set_line(3, "Tracking:", "> (PD)" if control_signal > 0 else "< (PD)")
                else:
                    control_signal = error
            # Mouse State
            if control_signal > 0:
                hold_mouse()
            else:
                release_mouse()
            if bar_detected == True:
                last_left_x = left_x
                last_right_x = right_x
                last_bar_center = bar_center
                last_bar_size = bar_size
            if fish_detected == True:
                last_fish_x = fish_x
            last_time = current_time
            # Cleanup
            is_initial_run = False
            last_capture_id = self.capture_id
            time.sleep(self.scan_delay)
        return

    def stop_macro(self, text="Macro Stopped"):
        self.macro_running = False
        try:
            self.fish_overlay.hide()
        except:
            pass

        try:
            self.status_overlay.hide()
        except:
            pass

        if (self.macro_thread and self.macro_thread.is_alive() and self.macro_thread is not threading.current_thread()):
            self.macro_thread.join()
        if (self.capture_thread and self.capture_thread.is_alive() and self.capture_thread is not threading.current_thread()):
            self.capture_thread.join()
        # Fully Release Dxcamera So A Later Dxcam.Create() Does Not Hit The
        # "instance already exists ... Delete the old object with `del obj`" warning.
        try:
            if self.camera is not None:
                try:
                    self.camera.stop()
                except Exception:
                    pass

                try:
                    del self.camera
                except Exception:
                    pass

                self.camera = None
        except Exception:
            pass

        if not text == "":
            self.set_status(text)
        try:
            window.show()
        except Exception:
            pass
def check_setup_guide():
    # Failsafe
    cleaned = 0
    js_beta_version = 0
    pirated_build = False
    beta_ver = int(BETA_VERSION) if isinstance(BETA_VERSION, str) else BETA_VERSION
    beta_version_message = f"beta {beta_ver}" if beta_ver > 0 else ""
    if beta_ver == 0:
        error_message = "You have downloaded PyWare Fishing for the first time."
    else:
        error_message = """You have downloaded a beta version of PyWare Fishing.
This uses a different folder to prevent crashes on the stable version"""
    
    try:
        with open(os.path.join(UI_PATH, "app.js"), "r", encoding="utf-8-sig") as file:
            # Read first two lines
            lines = [file.readline().strip() for _ in range(3)]
            # Parse first line for APP_VERSION
            first_line = lines[0]
            cleaned = float(first_line.replace("const APP_VERSION = ", "").replace('"', "").replace(";", ""))
            # Parse second line for BETA_VERSION
            second_line = lines[1]
            js_beta_version = float(second_line.replace("const BETA_VERSION = ", "").replace('"', "").replace(";", ""))
            # Parse third line for DEVELOPER
            third_line = lines[2]
            js_developer = third_line.replace("const DEVELOPER = ", "").replace('"', "").replace(";", "")
        # Compatibility for 4.4 - 4.41 update
        if js_developer == "let currentConfig = null" or js_developer == "":
            js_developer = DEVELOPER
        # Check release version, beta version and developer
        if not js_developer == DEVELOPER:
            show_setup_guide = True
            pirated_build = True
            error_message = """You tried to download an unauthorized version of PyWare Fishing.
Unofficial builds are unsupported and heavily restricted to prevent modification theft."""
        elif cleaned == APP_VERSION and (js_beta_version is None or js_beta_version == beta_ver):
            show_setup_guide = False
        else:
            show_setup_guide = True
            # Build detailed version mismatch message
            version_info = []
            if cleaned != APP_VERSION:
                version_info.append(f"Release version: {cleaned} → {APP_VERSION}")
            if js_beta_version is not None and js_beta_version != beta_ver:
                version_info.append(f"Beta version: {js_beta_version} → {beta_ver}")
            version_change = " & ".join(version_info)
            if APP_VERSION > cleaned or (APP_VERSION == cleaned and beta_ver > js_beta_version):
                error_message = f"""
You have updated from {version_change}.
Please open the base folder and move the new configs (optional), images and UI folder there."""
            else:
                error_message = f"""
The macro automatically updated from {version_change}. 
Please redownload the application from the Google Drive."""
    except FileNotFoundError:
        # File doesn't exist - first time setup
        show_setup_guide = True
        error_message = "You have downloaded PyWare Fishing for the first time. (File Not Found)"
        js_developer = DEVELOPER  # Set default developer
    except Exception as e:
        error_message = f"""Something went wrong during setup. 
Error: {e}"""
        show_setup_guide = True
        js_developer = DEVELOPER  # Set default developer on other errors too
    
    return show_setup_guide, error_message, js_developer, pirated_build

show_setup_guide, error_message, js_developer, pirated_build = check_setup_guide()
if show_setup_guide == True:
    dialogue = SetupGuide(error_message, js_developer, pirated_build)
    dialogue.mainloop()
show_setup_guide, error_message, js_developer, pirated_build = check_setup_guide()
if show_setup_guide == True:
    sys.exit(0)
index_html = "https://catman2608.github.io/PyWare-Backend/SolarFishingV4/index.html" if IS_COMPILED else os.path.join(UI_PATH, "index.html")
api = Api()
window = webview.create_window(
    f"PyWare Fishing V{APP_VERSION}",
    index_html,
    js_api=api,
    width=1000,
    height=700
)
webview.start(gui="edgechromium")
