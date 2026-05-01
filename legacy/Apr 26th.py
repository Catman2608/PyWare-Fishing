# GUI-related
from customtkinter import *
import tkinter as tk
from tkinter import messagebox
# Save and load
import json
import os
import subprocess
# Keyboard and Mouse
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
# Key Listeners
import threading
from pynput.keyboard import Listener as KeyListener, Key
macro_running = False
macro_thread = None
# Initialize controllers
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
# Timing-related
import time
# OpenCV and MSS for pixel search
import cv2
import numpy as np
import mss
# Webbrowser for opening links
import webbrowser
# Utilities
import requests
import io
import ctypes
import math
# Ctypes/Quartz for special click types
if sys.platform == "win32":
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
elif sys.platform == "darwin":
# Load CoreGraphics directly via ctypes [cite: 11]
    cg_path = ctypes.util.find_library("CoreGraphics")
    core_graphics = ctypes.CDLL(cg_path)

    # Define necessary Carbon/CoreGraphics constants
    K_CG_EVENT_LEFT_MOUSE_DOWN = 5
    K_CG_EVENT_LEFT_MOUSE_UP = 6
    K_CG_MOUSE_BUTTON_LEFT = 0
    K_CG_HID_EVENT_TAP = 0

    # Ctypes Structure for CGPoint
    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    def _mouse_event(event_type, x, y):
        """
        Zero-dependency mouse events using CoreGraphics via ctypes.
        """
        core_graphics.CGEventCreateMouseEvent.restype = ctypes.c_void_p
        core_graphics.CGEventCreateMouseEvent.argtypes = [
            ctypes.c_void_p,   # CGEventSourceRef (NULL)
            ctypes.c_uint32,   # CGEventType
            ctypes.c_double,   # CGPoint.x  (passed as two separate doubles)
            ctypes.c_double,   # CGPoint.y
            ctypes.c_uint32,   # CGMouseButton
        ]
        event = core_graphics.CGEventCreateMouseEvent(
            None,
            event_type,
            float(x),
            float(y),
            K_CG_MOUSE_BUTTON_LEFT,
        )

        if not event:
            return

        # CGEventPost(tap, event)
        core_graphics.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        core_graphics.CGEventPost.restype = None
        core_graphics.CGEventPost(K_CG_HID_EVENT_TAP, event)

        # Clean up memory (CFRelease)
        core_graphics.CFRelease.argtypes = [ctypes.c_void_p]
        core_graphics.CFRelease.restype = None
        core_graphics.CFRelease(event)

    def click(x, y):
        _mouse_event(K_CG_EVENT_LEFT_MOUSE_DOWN, x, y)
        _mouse_event(K_CG_EVENT_LEFT_MOUSE_UP, x, y)

    def _move_mouse(x, y):
        # CGWarpMouseCursorPosition takes CGPoint by value (two doubles).
        # Declare argtypes so ctypes passes them correctly.
        core_graphics.CGWarpMouseCursorPosition.argtypes = [
            ctypes.c_double,  # CGPoint.x
            ctypes.c_double,  # CGPoint.y
        ]
        core_graphics.CGWarpMouseCursorPosition.restype = ctypes.c_int32
        core_graphics.CGWarpMouseCursorPosition(float(x), float(y))
# Get all required paths
def get_base_path():
    """Unified base directory for app data."""

    if getattr(sys, 'frozen', False):
        # Compiled app → use user directory
        if sys.platform == "darwin":
            return os.path.join(
                os.path.expanduser("~"),
                "Library", "Application Support",
                "PyWareFishingV3"
            )
        elif sys.platform == "win32":
            return os.path.join(
                os.path.expanduser("~"),
                "AppData", "Roaming",
                "PyWareFishingV3"
            )
        else:
            return os.path.join(os.path.expanduser("~"), "PyWareFishingV3")

    # Dev mode → project directory
    return os.path.dirname(os.path.abspath(__file__))

def verify_images_exist(required_files):
    missing = []

    for file in required_files:
        path = os.path.join(IMAGES_PATH, file)
        if not os.path.exists(path):
            missing.append(file)

    if missing:
        msg = (
            "Missing required image files:\n\n"
            + "\n".join(missing)
            + "\n\nDownload the latest image pack here:\n"
            "https://drive.google.com/drive/folders/1e9tZwDtAaiYKTVFeArjWTIuztLgLg88a"
        )

        try:
            messagebox.showerror("Missing Images", msg)
        except:
            pass

        return False

    return True

def ensure_last_config_exists():
    """Ensure last_config.json exists at BASE_PATH, create default if missing."""
    config_file = os.path.join(BASE_PATH, "last_config.json")
    
    # Check if it exists as a FILE (not a directory)
    if os.path.exists(config_file):
        if os.path.isdir(config_file):
            # It's a directory - remove it and recreate as file
            print(f"Removing directory at {config_file} to create file...")
            try:
                os.rmdir(config_file)  # Use shutil.rmtree() if directory has contents
                print(f"Removed directory: {config_file}")
            except Exception as e:
                print(f"Could not remove directory: {e}")
                # Try to rename it as backup
                backup_path = config_file + "_backup_folder"
                os.rename(config_file, backup_path)
                print(f"Renamed directory to: {backup_path}")
        else:
            # It exists as a file, no action needed
            return config_file
    
    # Create default config structure
    default_config = {
        "version": APP_VERSION,
        "last_profile": "default",
        "last_macro_name": None,
        "settings": {},
        "tos_accepted": False
    }
    
    try:
        # Ensure the parent directory exists
        os.makedirs(BASE_PATH, exist_ok=True)
        
        # Write the file
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"Created default config file at: {config_file}")
    except Exception as e:
        print(f"Error creating config file: {e}")
    
    return config_file

BASE_PATH = get_base_path()

CONFIG_DIR = os.path.join(BASE_PATH, "configs")
IMAGES_PATH = os.path.join(BASE_PATH, "images")
DEBUG_DIR = BASE_PATH

CONFIG_PATH = os.path.join(BASE_PATH, "last_config.json")
APP_VERSION = "3.0"

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(IMAGES_PATH, exist_ok=True)

ensure_last_config_exists()
# Area Selector class
class AreaSelector:
    HANDLE_SIZE = 8
    def __init__(self, parent, shake_area, fish_area, friend_area, totem_area, callback):
        self.parent = parent
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)

        self.window.configure(bg="#181818")
        self.window.attributes("-alpha", 0.5)

        # Force Tk to compute real screen geometry before we query it.
        # Without this, winfo_screenwidth/height can return stale logical
        # values that don't cover the full display on Retina / 4K screens.
        self.window.update_idletasks()

        # Use winfo_vrootwidth/height when available (gives the full virtual
        # root size).  Fall back to screenwidth/height if not supported.
        try:
            w = self.window.winfo_vrootwidth()
            h = self.window.winfo_vrootheight()
            if w <= 0 or h <= 0:
                raise ValueError("vrootwidth/height not positive")
        except Exception:
            w = self.window.winfo_screenwidth()
            h = self.window.winfo_screenheight()

        # Position at (0, 0) in screen space.  On macOS the menu bar sits at
        # y=0 in logical coordinates, but overrideredirect windows can still
        # be placed there — we just need to cover the whole logical resolution.
        self.window.geometry(f"{w}x{h}+0+0")

        # Initialize mouse move and mouse tracking
        self.tracking = True
        self.tracking2 = False
        
        # Second idletasks pass so macOS actually maps the window at the
        # requested size before we start drawing.
        self.window.update_idletasks()

        self.canvas = tk.Canvas(self.window, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.shake = shake_area.copy()
        self.fish = fish_area.copy()
        self.friend = friend_area.copy()
        self.totem = totem_area.copy()

        self.dragging = None
        self.resize_corner = None
        self.active_area = None

        self.start_x = 0
        self.start_y = 0

        self.dragging = None
        self.resize_corner = None
        self.active_area = None

        self.draw_boxes()

        self.canvas.bind("<Button-1>", self.mouse_down)
        self.canvas.bind("<B1-Motion>", self.mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.mouse_up)
        self.window.bind("<Motion>", self._on_mouse_move)

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    # DRAW 

    def draw_boxes(self):

        self.canvas.delete("all")

        self.draw_area(self.shake, "#ff007a", "Shake Box")
        self.draw_area(self.fish, "#00daff", "Fish Box")
        self.draw_area(self.friend, "#f7ff00", "Friend Box")
        self.draw_area(self.totem, "#f5aefc", "Totem Box")

    def draw_area(self, area, color, label=""):

        x1 = area["x"]
        y1 = area["y"]
        x2 = x1 + area["width"]
        y2 = y1 + area["height"]
        mx = (x1 + x2) // 2
        my = (y1 + y2) // 2

        self.canvas.create_rectangle(x1, y1, x2, y2, 
                                     outline=color, width=3, 
                                     fill=color, stipple="gray25")

        # Label above the box
        if label:
            self.canvas.create_text(mx, y1 - 10, text=label,
                                    fill=color, font=("Arial", 11, "bold"),
                                    anchor="s")

        # All 8 handles: 4 corners + 4 mid-edges
        for x, y in [(x1,y1),(x2,y1),(x1,y2),(x2,y2),
                     (mx,y1),(mx,y2),(x1,my),(x2,my)]:
            self.canvas.create_rectangle(x-self.HANDLE_SIZE, y-self.HANDLE_SIZE,
                                         x+self.HANDLE_SIZE,y+self.HANDLE_SIZE, 
                                         fill="white",outline="")
    # Resizer / hit test
    def inside(self, x, y, area):
        return (
            area["x"] <= x <= area["x"] + area["width"] and
            area["y"] <= y <= area["y"] + area["height"]
        )

    def get_handle(self, x, y, area):
        x1 = area["x"]
        y1 = area["y"]
        x2 = x1 + area["width"]
        y2 = y1 + area["height"]
        mx = (x1 + x2) // 2
        my = (y1 + y2) // 2
        handles = {
            "nw": (x1, y1), "ne": (x2, y1),
            "sw": (x1, y2), "se": (x2, y2),
            "n":  (mx, y1), "s":  (mx, y2),
            "w":  (x1, my), "e":  (x2, my),
        }
        for name,(hx,hy) in handles.items():

            if abs(x-hx) <= self.HANDLE_SIZE and abs(y-hy) <= self.HANDLE_SIZE:
                return name

        return None
    # Detect mouse input from user
    def mouse_down(self, e):
        self.start_x = e.x
        self.start_y = e.y

        for area,name in [(self.fish,"fish"),(self.shake,"shake"),(self.friend,"friend"),(self.totem,"totem")]:

            handle = self.get_handle(e.x,e.y,area)

            if handle:
                self.resize_corner = handle
                self.active_area = area
                return

            if self.inside(e.x,e.y,area):
                self.dragging = name
                self.active_area = area
                return

    def mouse_drag(self, e):
        if not self.dragging and not self.resize_corner:
            return
        dx = e.x - self.start_x
        dy = e.y - self.start_y

        if self.resize_corner:

            a = self.active_area

            if "e" in self.resize_corner:
                a["width"] += dx
            if "s" in self.resize_corner:
                a["height"] += dy
            if "w" in self.resize_corner:
                a["x"] += dx
                a["width"] -= dx
            if "n" in self.resize_corner:
                a["y"] += dy
                a["height"] -= dy

        elif self.dragging:
            a = self.active_area
            a["x"] += dx
            a["y"] += dy
        self.start_x = e.x
        self.start_y = e.y
        self.draw_boxes()

    def mouse_up(self, e):
        self.dragging = None
        self.resize_corner = None
        self.active_area = None

    def mouse_move(self, e):
        for area in [self.fish,self.shake,self.friend,self.totem]:
            handle = self.get_handle(e.x,e.y,area)
            if handle:
                cursor = {
                    "nw":"size_nw_se",
                    "se":"size_nw_se",
                    "ne":"size_ne_sw",
                    "sw":"size_ne_sw",
                    "n": "size_ns",
                    "s": "size_ns",
                    "e": "size_we",
                    "w": "size_we",
                }[handle]

                self.canvas.config(cursor=cursor)
                return

            if self.inside(e.x,e.y,area):
                self.canvas.config(cursor="fleur")
                return

        self.canvas.config(cursor="")
    # Mouse move DETECTION functions
    def _on_mouse_move(self, event):
        if not self.tracking:
            return

        # Global mouse position
        x = self.window.winfo_pointerx()
        y = self.window.winfo_pointery()
        self.tracking2 = False

        # Check areas
        if self._point_in_area(x, y, self.shake):
            x2 = x - self.shake["x"]
            y2 = y - self.shake["y"]
            x_ratio = round(x2 / self.shake["width"], 2)
            y_ratio = round(y2 / self.shake["height"], 2)
            self.parent.set_status(f"SHAKE → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        elif self._point_in_area(x, y, self.fish):
            x2 = x - self.fish["x"]
            y2 = y - self.fish["y"]
            x_ratio = round(x2 / self.fish["width"], 2)
            y_ratio = round(y2 / self.fish["height"], 2)
            self.parent.set_status(f"FISH → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        elif self._point_in_area(x, y, self.friend):
            x2 = x - self.friend["x"]
            y2 = y - self.friend["y"]
            x_ratio = round(x2 / self.friend["width"], 2)
            y_ratio = round(y2 / self.friend["height"], 2)
            self.parent.set_status(f"FRIEND → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        elif self._point_in_area(x, y, self.totem):
            x2 = x - self.totem["x"]
            y2 = y - self.totem["y"]
            x_ratio = round(x2 / self.totem["width"], 2)
            y_ratio = round(y2 / self.totem["height"], 2)
            self.parent.set_status(f"TOTEM → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        else:
            self.parent.set_status("Area selector opened (press key again to close)")
            self.tracking2 = False
    def _point_in_area(self, x, y, area):
        return (
            area["x"] <= x <= area["x"] + area["width"] and
            area["y"] <= y <= area["y"] + area["height"]
        )
    # Save
    def close(self):
        if self.tracking2 == False:
            self.parent.set_status("Area selector closed")
        self.callback(self.shake, self.fish, self.friend, self.totem)
        self.window.destroy()
# Live eyedropper - can be safely pasted in other macros
class Eyedropper:
    """Encapsulates color picking eyedropper functionality."""
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.window = None
        self.last_picked_color = None

    def start(self):
        """Launch the eyedropper overlay."""
        self.window = tk.Toplevel(self.parent_app)
        w = self.parent_app.winfo_screenwidth()
        h = self.parent_app.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+0+0")
        self.window.attributes("-alpha", 0.01)
        self.window.attributes("-topmost", True)
        self.window.config(cursor="crosshair")
        self.window.bind("<Motion>", self._on_hover)
        self.window.bind("<Button-1>", self._on_click)
        self.window.bind("<Escape>", self.close)

    def _on_hover(self, event):
        """Update status with current pixel color."""
        x = self.parent_app.winfo_pointerx()
        y = self.parent_app.winfo_pointery()
        pixel = self._grab_pixel(x, y)
        if pixel:
            r, g, b = pixel
            hex_color = f"#{r:02X}{g:02X}{b:02X}"
            self.parent_app.set_status(f"Hover: {hex_color} | Click to pick")

    def _on_click(self, event):
        """Pick the color at current position."""
        x = self.parent_app.winfo_pointerx()
        y = self.parent_app.winfo_pointery()
        
        # Hide window before capturing to avoid window blending
        if self.window and self.window.winfo_exists():
            self.window.attributes("-alpha", 0.0)
            self.parent_app.update_idletasks()
        time.sleep(0.05)
        
        pixel = self._grab_pixel(x, y)
        if pixel:
            r, g, b = pixel
            self.last_picked_color = f"#{r:02X}{g:02X}{b:02X}"
            self.parent_app.set_status(f"Picked: {self.last_picked_color}")
        
        self.close()

    def _grab_pixel(self, x, y):
        """Grab RGB pixel at (x, y). Returns (r, g, b) tuple or None."""
        frame = self.parent_app._grab_screen_region(x, y, x + 1, y + 1)
        if frame is None or frame.size == 0:
            return None
        b, g, r = int(frame[0, 0, 0]), int(frame[0, 0, 1]), int(frame[0, 0, 2])
        return r, g, b

    def close(self, event=None):
        """Close the eyedropper window."""
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
# Fish/Perfect Cast Overlay
class FishOverlay:
    """Encapsulates the fishing minigame overlay visualization."""
    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.window = None
        self.canvas = None

    def init_window(self):
        """Create and initialize the overlay window and canvas."""
        if self.window and self.window.winfo_exists():
            return

        self.window = tk.Toplevel(self.parent_app)
        overlay_x = int(self.parent_app.SCREEN_WIDTH * 0.5) - 400
        overlay_y = int(self.parent_app.SCREEN_HEIGHT * 0.65)
        self.window.geometry(f"800x50+{overlay_x}+{overlay_y}")
        
        if sys.platform == "darwin":
            self.window.overrideredirect(False)
        else:
            self.window.overrideredirect(True)
        
        self.window.attributes("-topmost", True)
        self.canvas = tk.Canvas(
            self.window,
            width=800,
            height=60,
            bg="#1d1d1d",
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

    def show(self):
        """Show the overlay window."""
        self.init_window()
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()

    def hide(self):
        """Hide the overlay window."""
        if self.window and self.window.winfo_exists():
            self.window.withdraw()

    def clear(self):
        """Clear all drawn elements from the overlay."""
        if not self.canvas or not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")

    def draw(self, bar_center, box_size, color, canvas_offset, show_bar_center=False, bar_y1=10, bar_y2=40):
        """Draw a box on the overlay."""
        if bar_center is None:
            return

        self.init_window()
        box_size = int(box_size / 2) if box_size else 0
        left_edge = bar_center - box_size
        right_edge = bar_center + box_size
        bx1 = left_edge - canvas_offset
        bx2 = right_edge - canvas_offset
        center_x = bar_center - canvas_offset

        def _draw():
            self.canvas.create_rectangle(bx1, bar_y1, bx2, bar_y2, 
                                        outline=color, width=2, fill="#000000")
            if show_bar_center:
                self.canvas.create_line(center_x, bar_y1, center_x, bar_y2,
                                       fill="gray", width=2)

        self.canvas.after(0, _draw)
# Terms Of Service Dialogue
class TermsOfServiceDialog(CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.accepted = False
        self.processing = False

        self.title("PyWare Fishing V3 - Terms of Use")
        self.geometry("750x600")
        self.minsize(650, 500)

        self.grab_set()
        self.transient(parent)

        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (750 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"+{x}+{y}")

        # Container
        self.container = CTkFrame(self)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        self.pages = {}

        self._build_tos_page()
        self._build_setup_page()

        self.show_page("tos")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # -
    # PAGE SYSTEM
    # -
    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    # -
    # PAGE 1: TOS
    # -
    def _build_tos_page(self):
        page = CTkFrame(self.container)
        self.pages["tos"] = page

        CTkLabel(page, text="Terms of Use", font=CTkFont(size=20, weight="bold")).pack(pady=10)

        # Scrollable text
        self.textbox = CTkTextbox(page, wrap="word")
        self.textbox.pack(fill="both", expand=True, pady=10)

        self.textbox.insert("1.0", """
PyWare Fishing V3.0 - Terms of Use

By using this software, you agree to the following:


⚡ 1. USAGE & MODIFICATION

✅ YOU ARE ALLOWED TO:
Use these macros for personal purposes.
Study and reverse engineer the code for educational purposes.
Modify the code for your own personal use.
Share your modifications with proper attribution.
                            
❌ YOU ARE NOT ALLOWED TO:
Repackage or redistribute this software as your own.
Remove or modify credits to the author (Catman2608).
Sell or monetize this software or its derivatives.
Claim ownership of the original codebase.
                            
⚡ IF YOU SHARE MODIFICATIONS:
⚠️ You MUST credit Catman2608 as the original author.
⚠️ You MUST link to the original source (YouTube/Website).
⚠️ You MUST clearly indicate what changes you made.
                            
⚡ 2. INTENDED USE & GAME COMPLIANCE

This software suite is designed for use on multiple platforms.
You are responsible for ensuring your use complies with the platform's Terms of Service and specific game rules.
The developers and the website owner (Catman2608) are NOT responsible for any account actions (bans, suspensions) resulting from your use of this software.
Use at your own risk. (usage in Roblox games are allowed)

⚡ 3. LIABILITY DISCLAIMER

The owner and authors are NOT liable for any damages, data loss, or account issues.
There is no guarantee of functionality, compatibility, or performance.
Software is provided "as-is." Use is entirely at your own risk.
                            
⚡ 4. PRIVACY & DATA

Macros store configuration data (settings) locally on your device.
No personal data is collected or transmitted to external servers.
Your preferences are stored in a local .json file only.
                            
⚡ 5. CREDITS & ATTRIBUTION
                            
Original Author: Catman2608
YouTube: https://www.youtube.com/@HexaTitanGaming
Discord: https://discord.gg/aMZY8yrF8r
If you share, modify, or redistribute this software:
                            
📋 REQUIRED: Credit "Catman2608" as the original creator
📋 REQUIRED: Link to the original source
📋 REQUIRED: Indicate any changes you made
🚫 FORBIDDEN: Claim the entire work as your own
                            
⚡ 6. TERMS UPDATES

These terms may be updated at any time.
Continued use of the software from the PyWare Automate website constitutes acceptance of the updated terms.
                            
✅ 7. ACCEPTANCE

By accepting the terms, you acknowledge that you have read, understood, and agree to these Terms of Use.
If you do not agree, please remove the software from your device.

🚀 Thank you for using PyWare Fishing! 🚀
        """)
        self.textbox.configure(state="disabled")

        # Checkbox
        self.agree_var = tk.BooleanVar()
        self.checkbox = CTkCheckBox(
            page,
            text="I agree to the Terms",
            variable=self.agree_var,
            command=self._update_accept_state
        )
        self.checkbox.pack(anchor="w", pady=10)

        # Buttons
        btn_frame = CTkFrame(page, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.decline_btn = CTkButton(btn_frame, text="Decline", command=self.on_decline)
        self.decline_btn.pack(side="left")

        self.accept_btn = CTkButton(
            btn_frame,
            text="Accept",
            state="disabled",
            command=self.on_accept
        )
        self.accept_btn.pack(side="right")

    # -
    # PAGE 2: SETUP GUIDE
    # -
    def _build_setup_page(self):
        page = CTkFrame(self.container)
        self.pages["setup"] = page

        CTkLabel(page, text="Setup Guide", font=CTkFont(size=20, weight="bold")).pack(pady=10)

        guide_text = CTkTextbox(page)
        guide_text.pack(fill="both", expand=True, pady=10)

        guide_text.insert("1.0", """
Step 1: Download and extract the config pack and images pack:
https://drive.google.com/drive/folders/1e9tZwDtAaiYKTVFeArjWTIuztLgLg88a?usp=drive_link

Step 2: Click Open Base Folder
Step 3: Paste configs into the configs folder
Step 4: Paste images into the images folder
Step 5: Change Bar Areas

❤️ Optional:
Please subscribe to support development!
""")
        guide_text.configure(state="disabled")

        btn_frame = CTkFrame(page, fg_color="transparent")
        btn_frame.pack(fill="x")

        CTkButton(
            btn_frame,
            text="Back",
            command=lambda: self.show_page("tos")
        ).pack(side="left")

        CTkButton(
            btn_frame,
            text="Open Base Folder",
            command=self.open_base_folder
        ).pack(side="left", padx=10)

        CTkButton(
            btn_frame,
            text="Subscribe",
            command=self.open_youtube
        ).pack(side="left", padx=10)

        CTkButton(
            btn_frame,
            text="Finish",
            command=self._on_finish
        ).pack(side="right")

    # -
    # LOGIC
    # -
    def _close_and_return_to_app(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass

        self.destroy()

        if self.parent and self.parent.winfo_exists():
            self.parent.after(0, self.parent.deiconify)
            self.parent.after(0, self.parent.lift)
            self.parent.after(0, self.parent.focus_force)

    def _on_finish(self):
        self.accepted = True
        self._close_and_return_to_app()

    def _update_accept_state(self):
        if self.agree_var.get():
            self.accept_btn.configure(state="normal")
        else:
            self.accept_btn.configure(state="disabled")

    def on_accept(self):
        if not self.agree_var.get():
            return

        self.accepted = True

        # 🔥 Instead of closing → go to setup page
        self.show_page("setup")

    def on_decline(self):
        self.accepted = False
        self._close_and_return_to_app()

    def on_close(self):
        if not self.processing:
            self.accepted = False
            self._close_and_return_to_app()

    # Misc
    def open_youtube(self):
        webbrowser.open("https://www.youtube.com/@HexaTitanGaming")
    def auto_subscribe(self):
        webbrowser.open("https://www.youtube.com/@HexaTitanGaming")
    def open_base_folder(self):
        folder = BASE_PATH
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", folder])
        else:  # Linux
            subprocess.run(["xdg-open", folder])
# Main app
class App(CTk):
    def __init__(self):

        # Initialize class
        super().__init__()

        # Initialize save and load (we only use
        # entry, checkboxes and comboboxes)
        self.vars = {} # Save entry variables here
        self.checkboxes = {}
        self.comboboxes = {} # Save combobox widgets here for dynamic updates
        self.switches = {} # Save CTkSwitch widgets here for load/save

        # Store screen width and height to use later
        self.SCREEN_WIDTH = self.winfo_screenwidth()
        self.SCREEN_HEIGHT = self.winfo_screenheight()

        # Detection variables
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None

        # P/D state variables
        self.prev_error = 0.0      # previous error term
        self.last_time = None      # timestamp of last PD sample
        self.prev_measurement = None
        self.filtered_derivative = 0.0
        self.last_bar_size = None
        self.pid_source = None  # "bar" or "arrow"
        self.pid_integral = 0.0 # Used for normal PID
        self.pid_last_time = 0
        self.pid_last_error = 0.0
        self._pid_filtered_d = 0.0  # Used for derivative smoothing

        # Arrow-based box estimation variables
        self.last_indicator_x = None
        self.last_holding_state = None
        self.estimated_box_length = None
        self.last_left_x = None
        self.last_right_x = None
        self.last_known_box_center_x = None
        self._reset_predictive_control_state()

        # Hotkey variables
        self.hotkey_start = Key.f5
        self.hotkey_stop = Key.f7
        self.hotkey_change_areas = Key.f6 # added for the bar area selector
        self.hotkey_screenshot = Key.f8
        self.hotkey_labels = {}  # Store label widgets for dynamic updates

        # Macro state
        self.macro_running = False
        self.macro_thread = None

        # Discord webhook and totem trigger counters
        self.webhook_cycle_counter = 0   # incremented each fishing cycle
        self.webhook_start_time = None   # set when macro starts (for Time mode)
        self.totem_cycle_counter = 0
        self.totem_start_time = time.time()
        
        # Safe defaults before key listener starts (will be overwritten by load_misc_settings)
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
        self.current_rod_name = "Basic Rod"

        # Screen capture variables — MSS instances are per-thread (see _thread_local)
        self._thread_local = threading.local()
        self._monitor = {}      # pre-allocated monitor dict, reused every grab
        self._scale_cache = None  # cached DPI scale factor

        # Buffer for capture/logic thread decoupling (used in start_macro())
        self._cap_lock = threading.Lock()
        self._cap_frame = None    # latest full screen frame
        self._cap_event = threading.Event()  # signals a new frame pair is ready
        self._active_capture_stop = None  # stop event for the currently running capture thread
        self._active_capture_thread = None  # thread object for the currently running capture thread

        self._debug_bar_center = 0
        self._debug_bar_size = 0
        self._debug_fish_top = 0
        self._debug_fish_height = 0
        self._debug_frame = 0

        # Invalidate scale cache if the window moves to a different monitor
        if sys.platform == "darwin":
            self.bind("<Configure>", lambda e: self._invalidate_scale_cache())
        
        # Show TOS dialogue
        state, first_launch, new_version = self.load_app_state()

        # 🔥 Show TOS if needed
        if first_launch or not state.get("tos_accepted", False):
            dialog = TermsOfServiceDialog(self)
            self.wait_window(dialog)

            if not dialog.accepted:
                self.destroy()
                return

            # Mark accepted
            state["tos_accepted"] = True

        # Update version AFTER TOS
        state["version"] = APP_VERSION

        self.save_app_state(state)
        # Setup overlay and eyedropper
        self.fish_overlay = FishOverlay(self)
        self.eyedropper = Eyedropper(self)

        # Start hotkey listener
        self.key_listener = KeyListener(on_press=self.on_key_press)
        self.key_listener.daemon = True
        self.key_listener.start()

        # Create window
        self.geometry("800x600")
        self.title("PyWare Fishing V3")

        # Status Bar 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Top Bar Frame (Status + Buttons)
        top_bar = CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=20, pady=10, sticky="ew")

        top_bar.grid_columnconfigure(0, weight=1)

        # Logo Label
        logo_label = CTkLabel(
            top_bar, 
            text="PYWARE FISHING V3",
            font=CTkFont(size=16, weight="bold")
        )
        logo_label.grid(row=0, column=0, sticky="w")

        # Status label (left side)
        self.status_label = CTkLabel(top_bar, text="Macro status: Idle")
        self.status_label.grid(row=1, column=0, pady=5, sticky="w")

        # Buttons frame (right side)
        button_frame = CTkFrame(top_bar, fg_color="transparent")
        button_frame.grid(row=0, column=1, sticky="e")

        CTkButton(
            button_frame,
            text="Website",
            corner_radius=8,
            command=self.open_link("https://sites.google.com/view/icf-automation-network/")
        ).pack(side="left", padx=6)

        CTkButton(
            button_frame,
            text="Upcoming Features",
            corner_radius=8,
            command=self.open_link("https://docs.google.com/document/d/1WwWWMR-eN-R-GO42IioToHpWTgiXkLoiNE_4NeE-GsU/edit?tab=t.0")
        ).pack(side="left", padx=6)

        CTkButton(
            button_frame,
            text="Tutorial",
            corner_radius=8,
            command=self.open_link("https://docs.google.com/document/d/1qjhgcONxpZZbSAEYiSCXoUXGjQwd7Jghf4EysWC4Cps/edit?usp=drive_link")
        ).pack(side="left", padx=6)

        # Tabs 
        self.tabs = CTkTabview(
            self,
            anchor="w",
        )
        self.tabs.grid(
            row=1, column=0, columnspan=6,
            padx=20, pady=10, sticky="nsew"
        )

        self.tabs.add("Basic")
        self.tabs.add("Automation")
        self.tabs.add("Utilities")

        # Build tabs
        self.build_basic_tab(self.tabs.tab("Basic"))
        self.build_automation_tab(self.tabs.tab("Automation"))
        self.build_utilities_tab(self.tabs.tab("Utilities"))

        # Load last config and reapply hotkeys
        self.load_last_config()
        self._apply_hotkeys_from_vars()

        # Grid behavior
        self.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(0, weight=0)  # top_bar
        self.grid_rowconfigure(1, weight=1)  # tabs expand

        self.refresh_config_dropdown() # Auto refresh config
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    # Build GUI
    # Basic tab
    def build_basic_tab(self, parent):
        # Configure scroll bar
        scroll = CTkScrollableFrame(parent)
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Configure grid
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Build main GUI
        basic_settings = CTkFrame(scroll, border_width=2)
        basic_settings.grid(row=0, column=0, padx=20, pady=20, sticky="nw")

        CTkLabel(basic_settings, text="Basic Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(basic_settings, text="Rod Type:").grid(row=1, column=0, padx=12, pady=10, sticky="w")

        self.config_var = StringVar(value="default")

        self.config_dropdown = CTkComboBox(
            basic_settings,
            variable=self.config_var,
            values=self.get_config_list(),
            command=self.on_config_selected
        )
        self.config_dropdown.grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkButton(basic_settings, text="Open Base Folder", corner_radius=10, 
                  command=self.open_base_folder
                  ).grid(row=0, column=1, padx=12, pady=12, sticky="w")

        # Hotkey and Hotbar Settings
        hotkey_hotbar_settings = CTkFrame(scroll, border_width=2)
        hotkey_hotbar_settings.grid(row=1, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(hotkey_hotbar_settings, text="Hotkey Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(hotkey_hotbar_settings, text="Hotbar Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=12, pady=8, sticky="w")
        # Key binds
        CTkLabel(hotkey_hotbar_settings, text="Start Key").grid(row=1, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Change Bar Areas Key").grid(row=2, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Stop Key").grid(row=3, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Screenshot Key").grid(row=4, column=0, padx=12, pady=6, sticky="w" )
        # Keys text changer
        start_key_var = StringVar(value="F5")
        self.vars["start_key"] = start_key_var
        start_key_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=start_key_var )
        start_key_entry.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        change_bar_areas_key_var = StringVar(value="F6")
        self.vars["change_bar_areas_key"] = change_bar_areas_key_var
        change_bar_areas_key_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=change_bar_areas_key_var )
        change_bar_areas_key_entry.grid(row=2, column=1, padx=12, pady=10, sticky="w")
        stop_key_var = StringVar(value="F7")
        self.vars["stop_key"] = stop_key_var
        stop_key_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=stop_key_var )
        stop_key_entry.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        screenshot_key_var = StringVar(value="F8")
        self.vars["screenshot_key"] = screenshot_key_var
        screenshot_key_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=screenshot_key_var )
        screenshot_key_entry.grid(row=4, column=1, padx=12, pady=10, sticky="w")
        # Hotkey for items
        CTkLabel(hotkey_hotbar_settings, text="Fishing Rod Slot:").grid(row=1, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Equipment Bag Slot").grid(row=2, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Sundial Totem Slot:").grid(row=3, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Target Totem Slot:").grid(row=4, column=2, padx=12, pady=6, sticky="w" )
        # Hotkey entries
        rod_slot_var = StringVar(value="1")
        self.vars["rod_slot"] = rod_slot_var
        rod_slot_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=rod_slot_var)
        rod_slot_entry.grid(row=1, column=3, padx=12, pady=8, sticky="w")
        bag_slot_var = StringVar(value="2")
        self.vars["bag_slot"] = bag_slot_var
        bag_slot_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=bag_slot_var)
        bag_slot_entry.grid(row=2, column=3, padx=12, pady=8, sticky="w")
        sundial_slot_var = StringVar(value="6")
        self.vars["sundial_slot"] = sundial_slot_var
        sundial_slot_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=sundial_slot_var)
        sundial_slot_entry.grid(row=3, column=3, padx=12, pady=8, sticky="w")
        target_slot_var = StringVar(value="7")
        self.vars["target_slot"] = target_slot_var
        target_slot_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=target_slot_var)
        target_slot_entry.grid(row=4, column=3, padx=12, pady=8, sticky="w")

        color_settings = CTkFrame(scroll, border_width=2)
        color_settings.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(color_settings, text="Color Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkButton(color_settings, text="Pick Colors", corner_radius=10, command=self.eyedropper.start).grid(row=0, column=1, padx=12, pady=12, sticky="w")

        CTkLabel(color_settings, text="Left Bar:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        left_color_var = StringVar(value="#F1F1F1")
        self.vars["left_color"] = left_color_var
        CTkEntry(color_settings, placeholder_text="#F1F1F1", width=120, textvariable=left_color_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Right Bar:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        right_color_var = StringVar(value="#FFFFFF")
        self.vars["right_color"] = right_color_var
        CTkEntry(color_settings, placeholder_text="#FFFFFF", width=120, textvariable=right_color_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Arrow:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        arrow_color_var = StringVar(value="#848587")
        self.vars["arrow_color"] = arrow_color_var
        CTkEntry(color_settings, placeholder_text="#848587", width=120, textvariable=arrow_color_var).grid(row=4, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Fish:").grid(row=5, column=0, padx=12, pady=10, sticky="w")
        fish_color_var = StringVar(value="#434B5B")
        self.vars["fish_color"] = fish_color_var
        CTkEntry(color_settings, placeholder_text="#434B5B", width=120, textvariable=fish_color_var).grid(row=5, column=1, padx=12, pady=10, sticky="w")
        left_tolerance_var = StringVar(value="8")
        self.vars["left_tolerance"] = left_tolerance_var
        CTkLabel(color_settings, text="Tolerance:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        left_tolerance_entry = CTkEntry(color_settings, placeholder_text="8", width=120, textvariable=left_tolerance_var)
        left_tolerance_entry.grid(row=2, column=3, padx=12, pady=10, sticky="w")
        right_tolerance_var = StringVar(value="8")
        self.vars["right_tolerance"] = right_tolerance_var
        CTkLabel(color_settings, text="Tolerance:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        right_tolerance_entry = CTkEntry(color_settings, placeholder_text="8", width=120, textvariable=right_tolerance_var)
        right_tolerance_entry.grid(row=3, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Tolerance:").grid(row=4, column=2, padx=12, pady=10, sticky="w")
        arrow_tolerance_var = StringVar(value="8")
        self.vars["arrow_tolerance"] = arrow_tolerance_var
        arrow_tolerance_entry = CTkEntry(color_settings, placeholder_text="8", width=120, textvariable=arrow_tolerance_var)
        arrow_tolerance_entry.grid(row=4, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Tolerance:").grid(row=5, column=2, padx=12, pady=10, sticky="w")
        fish_tolerance_var = StringVar(value="4")
        self.vars["fish_tolerance"] = fish_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=fish_tolerance_var).grid(row=5, column=3, padx=12, pady=10, sticky="w")
        # Shake Color
        CTkLabel(color_settings, text="Click Shake:").grid(row=6, column=0, padx=12, pady=10, sticky="w" )
        shake_color_var = StringVar(value="#FFFFFF")
        self.vars["shake_color"] = shake_color_var
        CTkEntry(color_settings, width=120, textvariable=shake_color_var).grid(row=6, column=1, padx=12, pady=10, sticky="w")
        # Shake Tolerance
        CTkLabel(color_settings, text="Tolerance:").grid(row=6, column=2, padx=12, pady=10, sticky="w" )
        shake_tolerance_var = StringVar(value="5")
        self.vars["shake_tolerance"] = shake_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=shake_tolerance_var).grid(row=6, column=3, padx=12, pady=10, sticky="w")
        # note box color and tolerance
        CTkLabel(color_settings, text="Tracking Target:").grid(row=7, column=0, padx=12, pady=10, sticky="w")
        note_box_color_var = StringVar(value="#00990c")
        self.vars["note_box_color"] = note_box_color_var
        CTkEntry(color_settings, width=120, textvariable=note_box_color_var).grid(row=7, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Tolerance:").grid(row=7, column=2, padx=12, pady=10, sticky="w")
        note_box_tolerance_var = StringVar(value="2")
        self.vars["note_box_tolerance"] = note_box_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=note_box_tolerance_var).grid(row=7, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Perfect Target:").grid(row=8, column=0, padx=12, pady=10, sticky="w")
        perfect_color_var = StringVar(value="#64a04c")
        self.vars["perfect_color"] = perfect_color_var
        CTkEntry(color_settings, width=120, textvariable=perfect_color_var).grid(row=8, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Tolerance:").grid(row=8, column=2, padx=12, pady=10, sticky="w")
        perfect_cast_tolerance_var = StringVar(value="16")
        self.vars["perfect_cast_tolerance"] = perfect_cast_tolerance_var
        perfect_cast_tolerance_entry = CTkEntry(color_settings, width=120, textvariable=perfect_cast_tolerance_var)
        perfect_cast_tolerance_entry.grid(row=8, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Casting:").grid(row=9, column=0, padx=12, pady=10, sticky="w")
        perfect_color2_var = StringVar(value="#d4d3ca")
        self.vars["perfect_color2"] = perfect_color2_var
        CTkEntry(color_settings, width=120, textvariable=perfect_color2_var).grid(row=9, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Tolerance:").grid(row=9, column=2, padx=12, pady=10, sticky="w")
        perfect_cast2_tolerance_var = StringVar(value="5")
        self.vars["perfect_cast2_tolerance"] = perfect_cast2_tolerance_var
        perfect_cast2_tolerance_entry = CTkEntry(color_settings, width=120, textvariable=perfect_cast2_tolerance_var)
        perfect_cast2_tolerance_entry.grid(row=9, column=3, padx=12, pady=10, sticky="w")

    def build_automation_tab(self, parent):
        # Configure scroll bar
        scroll = CTkScrollableFrame(parent)
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Configure grid
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        # Toggles
        toggles = CTkFrame(scroll, border_width=2)
        toggles.grid(row=0, column=0, padx=20, pady=20, sticky="nw")

        CTkLabel(toggles, text="Toggles", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        fish_overlay_var = StringVar(value="off")
        self.vars["fish_overlay"] = fish_overlay_var
        sw = CTkSwitch(toggles, text="Fish Overlay", variable=fish_overlay_var, onvalue="on", offvalue="off")
        sw.grid(row=1, column=0, padx=12, pady=8, sticky="w")
        self.switches["fish_overlay"] = sw

        auto_zoom_var = StringVar(value="off")
        self.vars["auto_zoom"] = auto_zoom_var
        sw = CTkSwitch(toggles, text="Auto Zoom", variable=auto_zoom_var, onvalue="on", offvalue="off")
        sw.grid(row=1, column=1, padx=12, pady=8, sticky="w")
        self.switches["auto_zoom"] = sw
        
        auto_refresh_var = StringVar(value="off")
        self.vars["auto_refresh"] = auto_refresh_var
        sw = CTkSwitch(toggles, text="Auto Refresh", variable=auto_refresh_var, onvalue="on", offvalue="off")
        sw.grid(row=2, column=0, padx=12, pady=8, sticky="w")
        self.switches["auto_refresh"] = sw

        efficiency_mode_var = StringVar(value="off")
        self.vars["efficiency_mode"] = efficiency_mode_var
        sw = CTkSwitch(toggles, text="Efficiency Mode", variable=efficiency_mode_var, onvalue="on", offvalue="off")
        sw.grid(row=2, column=1, padx=12, pady=8, sticky="w")
        self.switches["efficiency_mode"] = sw

        track_notes_var = StringVar(value="off")
        self.vars["track_notes"] = track_notes_var
        sw = CTkSwitch(toggles, text="Track Notes", variable=track_notes_var, onvalue="on", offvalue="off")
        sw.grid(row=3, column=0, padx=12, pady=8, sticky="w")
        self.switches["track_notes"] = sw

        track_charges_var = StringVar(value="off")
        self.vars["track_charges"] = track_charges_var
        sw = CTkSwitch(toggles, text="Track Charges", variable=track_charges_var, onvalue="on", offvalue="off")
        sw.grid(row=3, column=1, padx=12, pady=8, sticky="w")
        self.switches["track_charges"] = sw
        # Misc
        misc = CTkFrame(scroll, border_width=2)
        misc.grid(row=1, column=0, padx=20, pady=20, sticky="nw")

        CTkLabel(misc, text="Misc", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(misc, text="Select Rod Delay").grid(row=1, column=0, padx=12, pady=8, sticky="w")
        bag_delay_var = StringVar(value="0.2")
        self.vars["bag_delay"] = bag_delay_var
        bag_delay_entry = CTkEntry(misc, width=120, textvariable=bag_delay_var)
        bag_delay_entry.grid(row=1, column=1, padx=12, pady=8, sticky="w")

        CTkLabel(misc, text="Casting Mode:").grid(row=2, column=0, padx=12, pady=10, sticky="w" )
        casting_mode_var = StringVar(value="Normal")
        self.vars["casting_mode"] = casting_mode_var
        casting_cb = CTkComboBox(misc, values=["Perfect", "Normal"], 
                               variable=casting_mode_var, command=lambda v: [self.set_status(f"Casting Mode: {v}"), self.update_casting_visibility(v)]
                               )
        casting_cb.grid(row=2, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["casting_mode"] = casting_cb

        CTkLabel(misc, text="Shake Mode:").grid(row=3, column=0, padx=12, pady=10, sticky="w" )
        shake_mode_var = StringVar(value="Click")
        self.vars["shake_mode"] = shake_mode_var
        shake_cb = CTkComboBox(misc, values=["Click", "Navigation"], 
                               variable=shake_mode_var, command=lambda v: self.set_status(f"Shake Mode: {v}")
                               )
        shake_cb.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["shake_mode"] = shake_cb

        # Normal Casting Group
        self.normal_casting = CTkFrame(scroll, border_width=2)
        self.normal_casting.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(self.normal_casting, text="Casting Options", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(self.normal_casting, text="Delay").grid(row=1, column=0, padx=12, pady=8, sticky="w")
        delay_before_casting_var = StringVar(value="0.0")
        self.vars["delay_before_casting"] = delay_before_casting_var
        delay_before_casting_entry = CTkEntry(self.normal_casting, width=120, textvariable=delay_before_casting_var)
        delay_before_casting_entry.grid(row=1, column=1, padx=12, pady=8, sticky="w")
        CTkLabel(self.normal_casting, text="Cast for ________ seconds").grid(row=2, column=0, padx=12, pady=8, sticky="w")
        cast_duration_var = StringVar(value="0.6")
        self.vars["cast_duration"] = cast_duration_var
        cast_duration_entry = CTkEntry(self.normal_casting, width=120, textvariable=cast_duration_var)
        cast_duration_entry.grid(row=2, column=1, padx=12, pady=8, sticky="w")
        CTkLabel(self.normal_casting, text="Delay").grid(row=3, column=0, padx=12, pady=8, sticky="w")
        cast_delay_var = StringVar(value="0.6")
        self.vars["cast_delay"] = cast_delay_var
        cast_delay_entry = CTkEntry(self.normal_casting, width=120, textvariable=cast_delay_var)
        cast_delay_entry.grid(row=3, column=1, padx=12, pady=8, sticky="w")
        # Perfect Cast Settings 
        self.perfect_casting = CTkFrame(scroll, border_width=2)
        self.perfect_casting.grid(row=2, column=0, padx=20, pady=20, sticky="nw")

        CTkLabel(self.perfect_casting, text="Casting Options", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(self.perfect_casting, text="Threshold (percentage):").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        perfect_threshold_var = StringVar(value="30")
        self.vars["perfect_threshold"] = perfect_threshold_var
        perfect_threshold_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_threshold_var)
        perfect_threshold_entry.grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(self.perfect_casting, text="Scan FPS:").grid(row=1, column=2, padx=12, pady=10, sticky="w")
        cast_scan_delay_var = StringVar(value="0.05")
        self.vars["cast_scan_delay"] = cast_scan_delay_var
        cast_scan_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=cast_scan_delay_var)
        cast_scan_delay_entry.grid(row=1, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(self.perfect_casting, text="Failsafe Release Timeout:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        perfect_max_time_var = StringVar(value="3.5")
        self.vars["perfect_max_time"] = perfect_max_time_var
        perfect_max_time_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_max_time_var)
        perfect_max_time_entry.grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(self.perfect_casting, text="Release Delay:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        perfect_release_delay_var = StringVar(value="0")
        self.vars["perfect_release_delay"] = perfect_release_delay_var
        perfect_release_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_release_delay_var)
        perfect_release_delay_entry.grid(row=2, column=3, padx=12, pady=10, sticky="w")

        shake_configuration = CTkFrame(scroll, border_width=2)
        shake_configuration.grid(row=3, column=0, padx=20, pady=20, sticky="nw")
        # Shake Configuration
        CTkLabel(shake_configuration, text="Shake Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(shake_configuration, text="Shake Failsafe (attempts):").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        shake_failsafe_var = StringVar(value="20")
        self.vars["shake_failsafe"] = shake_failsafe_var
        CTkEntry(shake_configuration, width=120, textvariable=shake_failsafe_var ).grid(row=1, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(shake_configuration, text="Shake Scan Delay:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        shake_scan_delay_var = StringVar(value="0.01")
        self.vars["shake_scan_delay"] = shake_scan_delay_var
        CTkEntry(shake_configuration, width=120, textvariable=shake_scan_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(shake_configuration, text="Amount of Clicks:").grid(row=3, column=0, padx=12, pady=10, sticky="w" )
        shake_clicks_var = StringVar(value="1")
        self.vars["shake_clicks"] = shake_clicks_var
        CTkEntry(shake_configuration, width=120, textvariable=shake_clicks_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(shake_configuration, text="Detection Method:").grid(row=1, column=2, padx=12, pady=10, sticky="w" )
        detection_method_var = StringVar(value="Fish")
        self.vars["detection_method"] = detection_method_var
        detection_cb = CTkComboBox(shake_configuration, values=["Fish", "Fish + Bar", "Friend Area"], 
                               variable=detection_method_var, command=lambda v: self.set_status(f"Detection Method: {v}")
                               )
        detection_cb.grid(row=1, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["detection_method"] = detection_cb
        CTkLabel(shake_configuration, text="Restart Method:").grid(row=2, column=2, padx=12, pady=10, sticky="w" )
        restart_method_var = StringVar(value="Fish + Bar")
        self.vars["restart_method"] = restart_method_var
        restart_cb = CTkComboBox(shake_configuration, values=["Fish", "Fish + Bar", "Friend Area"], 
                               variable=restart_method_var, command=lambda v: self.set_status(f"Restart Method: {v}")
                               )
        restart_cb.grid(row=2, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["restart_method"] = restart_cb

        CTkLabel(shake_configuration, text="Animation Delay (seconds):").grid(row=3, column=2, padx=12, pady=10, sticky="w" )
        bait_delay_var = StringVar(value="0.0")
        self.vars["bait_delay"] = bait_delay_var
        CTkEntry(shake_configuration, width=120, textvariable=bait_delay_var).grid(row=3, column=3, padx=12, pady=10, sticky="w")

        ratio_settings = CTkFrame(scroll, border_width=2)
        ratio_settings.grid(row=4, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(ratio_settings, text="Minigame Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(ratio_settings, text="Left Ratio From Side:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        left_ratio_var = StringVar(value="0.5")
        self.vars["left_ratio"] = left_ratio_var
        CTkEntry( ratio_settings, width=120, textvariable=left_ratio_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Right Ratio From Side:").grid(row=1, column=2, padx=12, pady=10, sticky="w" )
        right_ratio_var = StringVar(value="0.5")
        self.vars["right_ratio"] = right_ratio_var
        CTkEntry( ratio_settings, width=120, textvariable=right_ratio_var).grid(row=1, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Scan Delay (seconds):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        minigame_scan_delay_var = StringVar(value="0.05")
        self.vars["minigame_scan_delay"] = minigame_scan_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=minigame_scan_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Restart Delay:").grid(row=2, column=2, padx=12, pady=10, sticky="w" )
        restart_delay_var = StringVar(value="1")
        self.vars["restart_delay"] = restart_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=restart_delay_var ).grid(row=2, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Note Tracking Ratio:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        note_track_ratio_var = StringVar(value="0.05")
        self.vars["note_track_ratio"] = note_track_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=note_track_ratio_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Charge Tracking Ratio:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        charge_track_ratio_var = StringVar(value="0.23")
        self.vars["charge_track_ratio"] = charge_track_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=charge_track_ratio_var).grid(row=3, column=3, padx=12, pady=10, sticky="w")

        # Detection
        detection_settings = CTkFrame(scroll, border_width=2)
        detection_settings.grid(row=5, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(detection_settings, text="Detection Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(detection_settings, text="Stabilize Threshold:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        stabilize_threshold_var = StringVar(value="6")
        self.vars["stabilize_threshold"] = stabilize_threshold_var
        CTkEntry(detection_settings, width=120, textvariable=stabilize_threshold_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(detection_settings, text="Required Fish Pixels:").grid(row=1, column=2, padx=12, pady=10, sticky="w")
        required_fish_pixels = StringVar(value="8")
        self.vars["required_fish_pixels"] = required_fish_pixels
        CTkEntry(detection_settings, width=120, textvariable=required_fish_pixels).grid(row=1, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(detection_settings, text="Left Threshold:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        tracking_threshold_var = StringVar(value="0")
        self.vars["tracking_threshold"] = tracking_threshold_var
        CTkEntry(detection_settings, width=120, textvariable=tracking_threshold_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(detection_settings, text="Right Threshold:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        tracking_threshold2_var = StringVar(value="0")
        self.vars["tracking_threshold2"] = tracking_threshold2_var
        CTkEntry(detection_settings, width=120, textvariable=tracking_threshold2_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(detection_settings, text="Maximum Movement Speed:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        rejected_pixels_var = StringVar(value="0")
        self.vars["rejected_pixels"] = rejected_pixels_var
        CTkEntry(detection_settings, width=120, textvariable=rejected_pixels_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        pid_settings = CTkFrame(scroll, border_width=2 )
        pid_settings.grid(row=6, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(pid_settings, text="PD Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        # Stopping Distance
        CTkLabel(pid_settings, text="Movement Check Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(pid_settings, text="Stopping Distance Multiplier:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        stopping_distance_var = StringVar(value="0.9")
        self.vars["stopping_distance"] = stopping_distance_var
        CTkEntry(pid_settings, width=120, textvariable=stopping_distance_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Velocity Smoothing:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        velocity_smoothing_var = StringVar(value="0.25")
        self.vars["velocity_smoothing"] = velocity_smoothing_var
        CTkEntry(pid_settings, width=120, textvariable=velocity_smoothing_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Movement Threshold:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        movement_threshold_var = StringVar(value="6")
        self.vars["movement_threshold"] = movement_threshold_var
        CTkEntry(pid_settings, width=120, textvariable=movement_threshold_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")
        # PID
        CTkLabel(pid_settings, text="PD Controller Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=12, pady=8, sticky="w")

        CTkLabel(pid_settings, text="Proportional gain:").grid(row=1, column=2, padx=12, pady=10, sticky="w")
        p_gain_var = StringVar(value="0.8")
        self.vars["proportional_gain"] = p_gain_var
        CTkEntry(pid_settings, width=120, textvariable=p_gain_var).grid(row=1, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Derivative gain:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        d_gain_var = StringVar(value="0.4")
        self.vars["derivative_gain"] = d_gain_var
        CTkEntry(pid_settings, width=120, textvariable=d_gain_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="P/D Clamp:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        pid_clamp_var = StringVar(value="100")
        self.vars["pid_clamp"] = pid_clamp_var
        CTkEntry(pid_settings, width=120, textvariable=pid_clamp_var).grid(row=3, column=3, padx=12, pady=10, sticky="w")

        # Also show and hide here
        self.update_casting_visibility(casting_mode_var.get())
    def build_utilities_tab(self, parent):
        scroll = CTkScrollableFrame(parent)
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        # VERY important
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Discord Webhooks
        discord_webhook = CTkFrame(scroll, border_width=2)
        discord_webhook.grid(row=0, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(discord_webhook, text="Discord Webhooks", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        
        CTkLabel(discord_webhook, text="Discord Webhook Mode:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        discord_webhook_mode_var = StringVar(value="Screenshot")
        self.vars["discord_webhook_mode"] = discord_webhook_mode_var
        discord_webhook_cb = CTkComboBox(discord_webhook, values=["Screenshot", "Text", "Disabled"], 
                               variable=discord_webhook_mode_var, command=lambda v: self.set_status(f"Discord Webhook mode: {v}")
                               )
        discord_webhook_cb.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["discord_webhook_mode"] = discord_webhook_cb

        CTkLabel(discord_webhook, text="Discord Webhook Type:").grid(row=1, column=2, padx=12, pady=10, sticky="w" )
        discord_webhook_cd_var = StringVar(value="Cycles")
        self.vars["discord_webhook_cd"] = discord_webhook_cd_var
        discord_webhook_cb = CTkComboBox(discord_webhook, values=["Time", "Cycles", "Disabled"], 
                               variable=discord_webhook_cd_var, command=lambda v: self.set_status(f"Discord Webhook Type: {v}")
                               )
        discord_webhook_cb.grid(row=1, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["discord_webhook_cd"] = discord_webhook_cb

        CTkLabel(discord_webhook, text="Webhook URL:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_url_var = StringVar(value="https://discord.com/api/webhooks/XXXXXXXXXX/XXXXXXXXXX")
        self.vars["discord_webhook_url"] = discord_webhook_url_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_url_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Webhook name:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_name_var = StringVar(value="I Can't Fish")
        self.vars["discord_webhook_name"] = discord_webhook_name_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_name_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Trigger on (cycles):").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        discord_webhook_cycle_var = StringVar(value="3")
        self.vars["discord_webhook_cycle"] = discord_webhook_cycle_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_cycle_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Trigger at (seconds):").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        discord_webhook_time_var = StringVar(value="60")
        self.vars["discord_webhook_time"] = discord_webhook_time_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_time_var).grid(row=3, column=3, padx=12, pady=10, sticky="w")

        # Test webhook button
        CTkButton(discord_webhook, text="Test Webhook", command=self.test_discord_webhook
                  ).grid(row=4, column=0, columnspan=2, padx=12, pady=12, sticky="w")

        auto_bug_reports_var = StringVar(value="off")
        self.vars["auto_bug_reports"] = auto_bug_reports_var
        sw = CTkSwitch(discord_webhook, text="Auto Bug Reports", variable=auto_bug_reports_var, onvalue="on", offvalue="off")
        sw.grid(row=4, column=1, padx=12, pady=8, sticky="w")
        self.switches["auto_bug_reports"] = sw
        
        # Auto Totem
        auto_totem = CTkFrame(scroll, border_width=2)
        auto_totem.grid(row=1, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(auto_totem, text="Auto Totem", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        
        CTkLabel(auto_totem, text="Auto Totem Mode:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        auto_totem_mode_var = StringVar(value="Cycles")
        self.vars["auto_totem_mode"] = auto_totem_mode_var
        auto_totem_cb = CTkComboBox(auto_totem, values=["Cycles", "Disabled"], 
                               variable=auto_totem_mode_var, command=lambda v: self.set_status(f"Auto Totem mode: {v}")
                               )
        auto_totem_cb.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["auto_totem_mode"] = auto_totem_cb

        CTkLabel(auto_totem, text="Use Sundial When: ").grid(row=1, column=2, padx=12, pady=10, sticky="w" )
        use_sundial_mode_when_var = StringVar(value="Disabled")
        self.vars["use_sundial_mode_when"] = use_sundial_mode_when_var
        auto_totem_cb = CTkComboBox(auto_totem, values=["Day", "Night", "Disabled"], 
                               variable=use_sundial_mode_when_var, command=lambda v: self.set_status(f"Use Sundial When: {v}")
                               )
        auto_totem_cb.grid(row=1, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["use_sundial_mode_when"] = auto_totem_cb

        CTkLabel(auto_totem, text="Totem Delay (seconds):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        totem_delay_var = StringVar(value="900")
        self.vars["totem_delay"] = totem_delay_var
        CTkEntry(auto_totem, width=120, textvariable=totem_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(auto_totem, text="Totem Cycles:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        totem_cycles_var = StringVar(value="70")
        self.vars["totem_cycles"] = totem_cycles_var
        CTkEntry(auto_totem, width=120, textvariable=totem_cycles_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")
    
        # Auto Reconnect (scrapped)
        # auto_reconnect = CTkFrame(scroll, border_width=2)
        # auto_reconnect.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        # CTkLabel(auto_reconnect, text="Auto Reconnect", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        # auto_reconnect_var = StringVar(value="off")
        # self.vars["auto_reconnect"] = auto_reconnect_var
        # auto_reconnect_cb = CTkCheckBox(auto_reconnect, text="Auto Reconnect (Roblox)", variable=auto_reconnect_var, onvalue="on", offvalue="off")
        # auto_reconnect_cb.grid(row=1, column=0, padx=12, pady=8, sticky="w")
        # self.checkboxes["auto_reconnect"] = auto_reconnect_cb
        # # Reconnect Link
        # CTkLabel(auto_reconnect, text="Reconnect Link:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        # reconnect_link_var = StringVar(value="https://www.roblox.com/games/16732694052/Fisch?privateServerLinkCode=18045795843383847993884150042526")
        # self.vars["reconnect_link"] = reconnect_link_var
        # CTkEntry(auto_reconnect, width=220, textvariable=reconnect_link_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")
    # Show and hide parts of the GUI
    def update_casting_visibility(self, mode):
        if mode == "Perfect":
            self.normal_casting.grid_remove()
            self.perfect_casting.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        else:
            self.perfect_casting.grid_remove()
            self.normal_casting.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
    def open_link(self, url):
        """Open a URL in the default web browser."""
        return lambda: webbrowser.open(url)
    def set_status(self, text, key=None):
        self.status_label.configure(text=text)
    # Get config list to save
    def get_config_list(self):
        if not os.path.exists(CONFIG_DIR):
            return ["default"]
        folders = [name for name in os.listdir(CONFIG_DIR) if os.path.isdir(os.path.join(CONFIG_DIR, name))]
        return folders if folders else ["default"]
    def refresh_config_dropdown(self):
        configs = self.get_config_list()
        self.config_dropdown.configure(values=configs)
    def on_config_selected(self, new_name):
        "Save current config BEFORE switching"
        current_name = getattr(self, "_last_config", None)
        if current_name:
            self.save_settings(current_name)
        # Load new config
        self.load_settings(new_name)
        # Track current config
        self._last_config = new_name
    def save_current_config(self):
        name = self.config_var.get()
        self.save_settings(name)
        self.refresh_config_dropdown()
        self.config_dropdown.set(name)
    # Get items to load TOS
    def load_app_state(self):
        # Default state
        state = {
            "version": None,
            "tos_accepted": False
        }

        # Use CONFIG_PATH (the actual file) instead of CONFIG_DIR
        if os.path.exists(CONFIG_PATH):  # CONFIG_PATH is the file, CONFIG_DIR is the folder
            try:
                with open(CONFIG_PATH, "r") as f:
                    state.update(json.load(f))
            except Exception as e:
                print(f"Error loading config: {e}")
                # corrupted file = treat as first launch
                pass

        # Detection logic
        is_first_launch = state["version"] is None
        is_new_version = state["version"] != APP_VERSION

        return state, is_first_launch, is_new_version

    def save_app_state(self, state):
        # Ensure the directory exists before writing
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(state, f, indent=4)
            print(f"Successfully saved config to: {CONFIG_PATH}")
        except Exception as e:
            print(f"Error saving config: {e}")
            # Optionally show error to user
            messagebox.showerror("Save Error", f"Could not save configuration: {e}")
    # Save and load settings
    def save_settings(self, name="default"):
        """Save all settings to a JSON config file."""
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(CONFIG_PATH)
        data = {}
        # Save all StringVar and related variables
        try:
            for key, var in self.vars.items():
                if hasattr(var, "get") and var is not None:
                    try:
                        data[key] = var.get()
                    except Exception as e:
                        print(f"Skipping {key}: {e}")
        except Exception as e:
            print(f"Error saving vars: {e}")
        # Save checkbox states
        try:
            for key, checkbox in self.checkboxes.items():
                data[f"checkbox_{key}"] = checkbox.get()
        except Exception as e:
            print(f"Error saving checkboxes: {e}")
        # Save combobox states
        try:
            for key, combobox in self.comboboxes.items():
                data[f"combobox_{key}"] = combobox.get()
        except Exception as e:
            print(f"Error saving comboboxes: {e}")
        # Save switch states
        try:
            for key, switch in self.switches.items():
                data[f"switch_{key}"] = self.vars[key].get()
        except Exception as e:
            print(f"Error saving switches: {e}")
        config_folder = os.path.join(CONFIG_DIR, name)
        os.makedirs(config_folder, exist_ok=True)
        path = os.path.join(config_folder, "config.json")
        # Save misc settings and set status
        self.save_misc_settings()
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            self.save_last_config(name)
            self.set_status(f"Config saved: {name}")
        except Exception as e:
            self.set_status(f"Error saving config: {e}")
    def load_settings(self, name="default"):
        """Load settings from a JSON config file."""
        path = os.path.join(CONFIG_DIR, name, "config.json")
        rod_folder = os.path.join(CONFIG_DIR, name.replace(".json", ""))
        if not os.path.exists(path):
            self.set_status(f"Config not found: {name}")
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            self.set_status(f"Error loading config: {e}")
            return
        # Load StringVar and related variables
        try:
            for key, var in self.vars.items():
                if hasattr(var, 'set') and key in data:
                    var.set(data[key])
        except Exception as e:
            print(f"Error loading vars: {e}")
        # Load checkbox states
        try:
            for key, checkbox in self.checkboxes.items():
                checkbox_key = f"checkbox_{key}"
                if checkbox_key in data:
                    value = data[checkbox_key]
                    if value == "on":
                        checkbox.select()
                    else:
                        checkbox.deselect()
        except Exception as e:
            print(f"Error loading checkboxes: {e}")
        # Load combobox states
        try:
            for key, cb in self.comboboxes.items():
                combobox_key = f"combobox_{key}"
                if combobox_key in data:
                    cb.set(data[combobox_key])
        except Exception as e:
            print(f"Error loading comboboxes: {e}")
        # Load switch states (must call select/deselect to update visuals)
        try:
            for key, switch in self.switches.items():
                switch_key = f"switch_{key}"
                if switch_key in data:
                    if data[switch_key] == "on":
                        switch.select()
                    else:
                        switch.deselect()
        except Exception as e:
            print(f"Error loading switches: {e}")
        # Load templates for image search / auto totem
        left_bar_path  = os.path.join(rod_folder, "left_bar.png")
        right_bar_path = os.path.join(rod_folder, "right_bar.png")
        fish_path      = os.path.join(rod_folder, "fish.png")
        self.templates = {
            "left_bar":  cv2.imread(left_bar_path, 0)  if os.path.exists(left_bar_path)  else None,
            "right_bar": cv2.imread(right_bar_path, 0) if os.path.exists(right_bar_path) else None,
            "fish":      cv2.imread(fish_path, 0)      if os.path.exists(fish_path)      else None,
        }
        required_images = ["sun.png", "moon.png"]
        if verify_images_exist(required_images) == False:
            return  # STOP instead of crashing
        # Save misc settings and show status
        self.load_misc_settings()
        self.set_status(f"Config loaded: {name}")
    
    def load_last_config(self):
        """Load the last used config."""
        last_config_path = os.path.join(BASE_PATH, "last_config.json")
        last_config = "default"
        if os.path.exists(last_config_path):
            try:
                with open(last_config_path, "r") as f:
                    data = json.load(f)
                    last_config = data.get("last_config", "default")
            except:
                last_config = "default"
        self.load_settings(last_config)
        # Update the dropdown and internal tracker to reflect the loaded config
        self.config_var.set(last_config)
        self.config_dropdown.set(last_config)
        self._last_config = last_config
    
    def save_last_config(self, name):
        """Save the last used config name (merge into last_config.json)."""
        last_config_path = os.path.join(BASE_PATH, "last_config.json")
        data = {}
        if os.path.exists(last_config_path):
            try:
                with open(last_config_path, "r") as f:
                    data = json.load(f)
            except:
                data = {}
        data["last_config"] = name
        try:
            with open(last_config_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving last config: {e}")
    def on_close(self):
        """This function will automatically run before the app is closed"""
        if self._last_config:
            self.save_settings(self._last_config)
        self.destroy()
    def load_misc_settings(self):
        """Load miscellaneous settings from last_config.json."""
        try:
            path = os.path.join(BASE_PATH, "last_config.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    self.current_rod_name = data.get("last_rod", "Basic Rod")
                    self.bar_areas = data.get("bar_areas", {"shake": None, "fish": None, "friend": None, "totem": None})
                    # IMPORTANT: Load hotkeys if present
                    start_key = data.get("start_key", "F5")
                    change_key = data.get("change_bar_areas_key", "F6")
                    screenshot_key = data.get("screenshot_key", "F8")
                    stop_key = data.get("stop_key", "F7")

                    self.vars["start_key"].set(start_key)
                    self.vars["change_bar_areas_key"].set(change_key)
                    self.vars["screenshot_key"].set(screenshot_key)
                    self.vars["stop_key"].set(stop_key)

                    # Convert to pynput keys
                    self.hotkey_start = self._string_to_key(start_key)
                    self.hotkey_change_areas = self._string_to_key(change_key)
                    self.hotkey_screenshot = self._string_to_key(screenshot_key)
                    self.hotkey_stop = self._string_to_key(stop_key)
            else:
                self.current_rod_name = "Basic Rod"
                self.bar_areas = {"fish": None, "shake": None, "friend": None, "totem": None}
        except:
            self.current_rod_name = "Basic Rod"
            self.bar_areas = {"fish": None, "shake": None, "friend": None, "totem": None}
    def save_misc_settings(self):
        """Save misc settings without overwriting last_config."""
        path = os.path.join(BASE_PATH, "last_config.json")
        # Load existing content
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except:
                data = {}
        # Build clean bar areas
        clean_bar_areas = {}
        for key in ["shake", "fish", "friend", "totem"]:
            area = self.bar_areas.get(key)
            if isinstance(area, dict):
                clean_bar_areas[key] = {
                    "x": int(area.get("x", 0)),
                    "y": int(area.get("y", 0)),
                    "width": int(area.get("width", 0)),
                    "height": int(area.get("height", 0))
                }
            else:
                clean_bar_areas[key] = None
        # Update fields (MERGE ONLY)
        data["last_rod"] = self.current_rod_name
        data["bar_areas"] = clean_bar_areas
        # Save hotkeys
        data["start_key"] = self.vars["start_key"].get()
        data["change_bar_areas_key"] = self.vars["change_bar_areas_key"].get()
        data["screenshot_key"] = self.vars["screenshot_key"].get()
        data["stop_key"] = self.vars["stop_key"].get()
        # Write merged result
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    # Key press functions
    def _apply_hotkeys_from_vars(self):
        """Apply hotkey StringVars to the live hotkey attributes used by on_key_press."""
        self.hotkey_start = self._string_to_key(self.vars["start_key"].get())
        self.hotkey_change_areas = self._string_to_key(self.vars["change_bar_areas_key"].get())
        self.hotkey_screenshot = self._string_to_key(self.vars["screenshot_key"].get())
        self.hotkey_stop = self._string_to_key(self.vars["stop_key"].get())
    def _string_to_key(self, key_string):
        key_string = key_string.strip().lower()
        # Try special keys
        if hasattr(Key, key_string):
            return getattr(Key, key_string)
        # Fallback to character
        return key_string
    def _normalize_hotkey_value(self, hotkey):
        if isinstance(hotkey, Key):
            return str(hotkey).replace("Key.", "").lower()
        return str(hotkey).strip().lower()
    def normalize_key(self, key):
        try:
            return key.char.lower()  # letter keys
        except AttributeError:
            return str(key).replace("Key.", "").lower()
    def on_key_press(self, key):
        pressed_key = self.normalize_key(key)
        if pressed_key == self._normalize_hotkey_value(self.hotkey_start) and not self.macro_running:
            # Save settings
            config_name = self.config_var.get()
            self.save_settings(config_name)
            if self.vars["auto_zoom"].get() == "on" and self.vars["casting_mode"].get() == "Perfect":
                messagebox.showwarning("Error", "Auto Zoom In and Perfect Cast can't be enabled at once. \nDisable one of them to continue.")
            else:
                self.macro_running = True
                self.after(0, self.withdraw)
                threading.Thread(target=self.start_macro, daemon=True).start() # This will start the macro in a new thread, allowing the GUI to remain responsive
        elif pressed_key == self._normalize_hotkey_value(self.hotkey_change_areas):
            self.open_area_selector()
        elif pressed_key == self._normalize_hotkey_value(self.hotkey_screenshot):
            self._take_debug_screenshot()
        elif pressed_key == self._normalize_hotkey_value(self.hotkey_stop):
            self.stop_macro()
    def set_status(self, text, key=None):
        self.status_label.configure(text=text)
    # Macro helper functions
    def open_base_folder(self):
        folder = BASE_PATH
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", folder])
        else:  # Linux
            subprocess.run(["xdg-open", folder])
    # Area Selector
    def open_area_selector(self):
        self.update_idletasks()
        # Toggle OFF if already open
        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.window.winfo_exists():
            self.area_selector.close()
            self.area_selector = None
            return
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        # Default fallback areas 
        # 350, 150, 1500, 950
        def default_shake_area():
            left = int(screen_w * 0.1041)
            top = int(screen_h * 0.0925)
            right = int(screen_w * 0.8958)
            bottom = int(screen_h * 0.8333)
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
            # 1830, 900, 1870, 950
            left = int(screen_w * 0.9531)
            top = int(screen_h * 0.8333)
            right = int(screen_w * 0.9739)
            bottom = int(screen_h * 0.8796)
            return {"x": left, "y": top, 
                    "width": right - left, "height": bottom - top}
        # Load saved areas or fallback 
        shake_area = (self.bar_areas.get("shake") 
                      if isinstance(self.bar_areas.get("shake"), dict) else default_shake_area())
        fish_area = (self.bar_areas.get("fish") 
                     if isinstance(self.bar_areas.get("fish"), dict) else default_fish_area())
        friend_area = (self.bar_areas.get("friend") 
                       if isinstance(self.bar_areas.get("friend"), dict) else default_friend_area())
        totem_area = (self.bar_areas.get("totem") 
                       if isinstance(self.bar_areas.get("totem"), dict) else default_totem_area())
        # Callback when user closes selector 
        def on_done(shake, fish, friend, totem):
            self.bar_areas["shake"] = shake
            self.bar_areas["fish"] = fish
            self.bar_areas["friend"] = friend
            self.bar_areas["totem"] = totem
            self.save_misc_settings()
            self.area_selector = None
        # Open selector 
        self.area_selector = AreaSelector(parent=self, shake_area=shake_area, fish_area=fish_area, friend_area=friend_area, totem_area=totem_area, callback=on_done)
        self.set_status("Area selector opened (press key again to close)")
    # HEX to BBBGGGRRR for OpenCV
    def _hex_to_bgr(self, hex_color):
        "Convert hex color to BGR tuple for OpenCV."
        if hex_color is None or hex_color.lower() in ["none", "#none", ""]:
            return None
        
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            try:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (b, g, r)  # BGR format for OpenCV
            except ValueError:
                return None
        return None
    # Click at X/Y position (using ctypes)
    def _click_at(self, x, y, click_count=1):
        click_mode = 2 # Will be replaced later
        if sys.platform == "win32":
            click_mode = 0
        elif sys.platform == "darwin":
            click_mode = 1
        else:
            click_mode = 2
        if click_mode == 0:
            # Move cursor
            windll.SetCursorPos(x, y)
            # Important: tiny movement so Roblox registers input
            windll.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            for i in range(click_count):
                windll.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                windll.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                if i < click_count - 1:
                    time.sleep(0.03)
        elif click_mode == 1:
            x, y = float(x), float(y)
            # Move cursor
            _move_mouse(x, y)
            # Tiny movement (Roblox trick)
            _move_mouse(x, y + 1)

            for i in range(click_count):
                _mouse_event(K_CG_EVENT_LEFT_MOUSE_DOWN, x, y)
                _mouse_event(K_CG_EVENT_LEFT_MOUSE_UP, x, y)
                if i < click_count - 1:
                    time.sleep(0.03)
        elif click_mode == 2:
            mouse_controller.position = (x, y)
            time.sleep(0.01)
            # Jitter to prevent Roblox from crashing
            mouse_controller.position = (x + 3, y + 3)
            mouse_controller.position = (x, y)
            mouse_controller.press(Button.left)
            time.sleep(0.04)
            mouse_controller.release(Button.left)
    # Logging-related functions
    def _discord_text_worker(self, webhook_url, message_prefix, loop_count, show_status):
        """Worker function to send text webhook."""
        discord_webhook_name = self.vars["discord_webhook_name"].get()
        webhook_url2 = "https://discord.com/api/webhooks/1492827883977179216/0MCmMcW1OsXU0rDoRYRLY2V3rzSQf4ACmU9J8Gn1L-yh6dwC8WtIYw7Na7UHTIVpBB87"
        try:
            if show_status == True:
                payload = {
                    'content': f'{message_prefix}🎣 Cycle completed\n🔄 {loop_count}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': discord_webhook_name,
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
                    'username': discord_webhook_name,
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
        discord_webhook_name = self.vars["discord_webhook_name"].get()
        webhook_url2 = "https://discord.com/api/webhooks/1492827883977179216/0MCmMcW1OsXU0rDoRYRLY2V3rzSQf4ACmU9J8Gn1L-yh6dwC8WtIYw7Na7UHTIVpBB87"
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
                    'username': discord_webhook_name
                }
                response = requests.post(webhook_url, data=payload, files=files, timeout=10)
            else:
                payload = {
                    'content': f'{message_prefix}🎣 **Cycle failed**\n🔄 {loop_count}\n🕐 {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'username': discord_webhook_name
                }
                response = requests.post(webhook_url2, data=payload, files=files, timeout=10)
            if response.status_code in (200, 204):
                if show_status == True:
                    self.set_status(f"Discord screenshot sent ({loop_count})")
            else:
                self.set_status(f"Error: Discord screenshot failed: {response.status_code}")

        except Exception as e:
            self.set_status(f"Error: sending Discord screenshot: {e}")
    def test_discord_webhook(self):
        self.send_discord_webhook("**Discord Webhook is working**", "TEST", show_status=True)
    def send_bug_report(self, error_text, phase="Unknown"):
        """Send a crash/bug report via text webhook, gated by the Auto Bug Reports switch.

        Args:
            error_text: The exception message / traceback snippet.
            phase: Human-readable label for which macro phase crashed
                   (e.g. "Perfect Cast", "Shake Click", "Minigame", "Totem").
        """
        if self.vars.get("auto_bug_reports", StringVar(value="off")).get() != "on":
            return
        webhook_url = "https://discord.com/api/webhooks/1492827883977179216/0MCmMcW1OsXU0rDoRYRLY2V3rzSQf4ACmU9J8Gn1L-yh6dwC8WtIYw7Na7UHTIVpBB87"
        platform_name = {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, sys.platform)
        prefix = (
            f"**Auto Bug Report**\n"
            f"Version: `{APP_VERSION}` | "
            f"Platform: `{platform_name}` | "
            f"Phase: `{phase}`\n"
        )
        thread = threading.Thread(
            target=self._discord_text_worker,
            args=(webhook_url, prefix, error_text, False),
            daemon=True
        )
        thread.start()
    def send_discord_webhook(self, text, loop_count, show_status=True):
        if self.vars["discord_webhook_mode"].get() == "Disabled":
            self.set_status("⚠ Discord webhook is disabled.")
            return
        # discord_webhook_url
        webhook_url = self.vars["discord_webhook_url"].get().strip()

        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            self.set_status("Error: Invalid webhook URL.")
            return
        
        if show_status == True:
            self.set_status("Sending test webhook...")
        use_screenshot = self.vars["discord_webhook_mode"].get() == "Screenshot"

        if use_screenshot:
            thread = threading.Thread(
                target=self._discord_screenshot_worker,
                args=(webhook_url, f"{text}\n", loop_count, show_status),
                daemon=True
            )
        else:
            thread = threading.Thread(
                target=self._discord_text_worker,
                args=(webhook_url, f"{text}\n", loop_count, show_status),
                daemon=True
            )
        thread.start()
    # Take debug screenshot
    def _take_debug_screenshot(self):
        """
        Capture all relevant areas (shake, fish, friend, totem)
        and save debug images.
        """

        def get_area(name, fallback_rect):
            try:
                left, top, right, bottom, w, h = self._resolve_area(name, fallback_rect)
                if w <= 0 or h <= 0:
                    raise ValueError("Invalid dimensions")
                return left, top, right, bottom
            except Exception:
                return fallback_rect

        # Define areas (same as minigame) 
        shake = get_area("shake", (
            int(self.SCREEN_WIDTH * 0.1041),
            int(self.SCREEN_HEIGHT * 0.0925),
            int(self.SCREEN_WIDTH * 0.8958),
            int(self.SCREEN_HEIGHT * 0.8333),
        ))

        fish = get_area("fish", (
            int(self.SCREEN_WIDTH * 0.2844),
            int(self.SCREEN_HEIGHT * 0.7981),
            int(self.SCREEN_WIDTH * 0.7141),
            int(self.SCREEN_HEIGHT * 0.8370),
        ))

        friend = get_area("friend", (
            int(self.SCREEN_WIDTH * 0.0046),
            int(self.SCREEN_HEIGHT * 0.8583),
            int(self.SCREEN_WIDTH * 0.0401),
            int(self.SCREEN_HEIGHT * 0.94),
        ))

        totem = get_area("totem", (
            int(self.SCREEN_WIDTH * 0.45),
            int(self.SCREEN_HEIGHT * 0.2),
            int(self.SCREEN_WIDTH * 0.55),
            int(self.SCREEN_HEIGHT * 0.5),
        ))
        # Capture full screen (better for overlay debugging) 
        full_img = self._grab_screen_region(0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        if full_img is None:
            self.set_status("Failed to grab full screen")
            return
        # Helper to crop 
        def crop(img, rect):
            l, t, r, b = rect
            return img[t:b, l:r]
        # Save individual regions 
        try:
            cv2.imwrite(os.path.join(BASE_PATH, "debug_fish.png"), crop(full_img, fish))
            cv2.imwrite(os.path.join(BASE_PATH, "debug_shake.png"), crop(full_img, shake))
            cv2.imwrite(os.path.join(BASE_PATH, "debug_friend.png"), crop(full_img, friend))
            cv2.imwrite(os.path.join(BASE_PATH, "debug_totem.png"), crop(full_img, totem))
        except Exception as e:
            self.set_status(f"Error saving region screenshots: {e}")
            return
        self.set_status("Saved debug screenshots (fish, shake, friend, totem, full)")
    # Grab screen and apply scale factor
    def _get_scale_factor(self):
        """
        Return physical-pixels-per-logical-point for the display.

        Derived from Tkinter's winfo_fpixels so it reflects whichever monitor
        the window is currently on.  Falls back to Quartz if Tk isn't ready.
        Cache is invalidated by _invalidate_scale_cache() on <Configure>.
        """
        if self._scale_cache is not None:
            return self._scale_cache
            
        if sys.platform == "darwin":
            try:
                tk_dpi = self.winfo_fpixels('1i')
                scale = tk_dpi / 72.0
                self._scale_cache = max(1.0, min(4.0, scale))
            except Exception:
                try:
                    # Ctypes-only fallback for Scale Factor
                    # CGDisplayBounds returns a CGRect (origin + size), which is
                    # 4 doubles on macOS (x, y, width, height).
                    class _CGPoint(ctypes.Structure):
                        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

                    class _CGSize(ctypes.Structure):
                        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

                    class _CGRect(ctypes.Structure):
                        _fields_ = [("origin", _CGPoint), ("size", _CGSize)]

                    main_display = core_graphics.CGMainDisplayID()
                    pixel_width = core_graphics.CGDisplayPixelsWide(main_display)

                    core_graphics.CGDisplayBounds.restype = _CGRect
                    bounds = core_graphics.CGDisplayBounds(main_display)
                    logical_width = bounds.size.width

                    self._scale_cache = pixel_width / logical_width if logical_width else 1.0
                except Exception:
                    self._scale_cache = 1.0
        else:
            self._scale_cache = 1.0
        return self._scale_cache

    def _invalidate_scale_cache(self):
        """Force _get_scale_factor to re-query on next call (e.g. window moved to another monitor)."""
        self._scale_cache = None
    def _grab_screen_region(self, left, top, right, bottom):
        """Optimized path for MSS screen capture"""
        # Apply DPI scale once
        scale = self._get_scale_factor()
        left   = int(left   * scale)
        top    = int(top    * scale)
        right  = int(right  * scale)
        bottom = int(bottom * scale)
        width  = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        # Reuse the monitor dict to avoid allocation each call
        m = self._monitor
        m["left"]   = left
        m["top"]    = top
        m["width"]  = width
        m["height"] = height

        if not hasattr(self._thread_local, "sct"):
            self._thread_local.sct = mss.mss()
        img = self._thread_local.sct.grab(m)
        # mss returns BGRA; take only first 3 channels (BGR) without a copy
        return np.frombuffer(img.raw, dtype=np.uint8).reshape(height, width, 4)[:, :, :3]
    
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

        m = thread_local.monitor
        img = thread_local.sct.grab(m)

        return np.frombuffer(img.raw, dtype=np.uint8).reshape(
            m["height"], m["width"], 4
        )[:, :, :3]

    def _capture_loop_full(self, stop_event, scan_delay):
        thread_local = threading.local()

        # On macOS, mss uses Core Graphics which is slow to call in a tight loop.
        # Enforce a minimum sleep so we don't saturate the CPU and starve the game
        # and the PID thread.  At 20 fps a frame is ~0.05 s; floor at 0.033 s
        # (~30 fps) so we never spin faster than the game can produce new pixels.
        import sys as _sys
        _mac_floor = 0.033 if _sys.platform == "darwin" else 0.0

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
        # Overlapping capture threads share _cap_frame/_cap_event/_cap_lock and
        # will race each other, which causes segfaults in the MSS/CoreGraphics
        # capture path on macOS.
        self._stop_active_capture()

        self._cap_frame = None

        # Ensure these exist
        if not hasattr(self, "_cap_lock"):
            self._cap_lock = threading.Lock()
        if not hasattr(self, "_cap_event"):
            self._cap_event = threading.Event()

        self._cap_event.clear()
        stop_event = threading.Event()
        self._active_capture_stop = stop_event  # track the active stop event

        import sys as _sys
        _mac_floor = 0.033 if _sys.platform == "darwin" else 0.0

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
    # Pixel and image search
    def _find_template(self, frame, template, confidence=0.7):
        if template is None or frame is None:
            return None
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        print(max_val)
        if max_val >= confidence:
            h, w = template.shape
            return max_loc[0] + w // 2   # X relative to frame
        return None
    def _prepare_templates(self):
        """Convert templates to grayscale once."""
        for key in self.templates:
            if self.templates[key] is None:
                continue

            if len(self.templates[key].shape) == 3:
                self.templates[key] = cv2.cvtColor(
                    self.templates[key],
                    cv2.COLOR_BGR2GRAY
                )
    def _get_template_confidence(self, frame, template):
        """
        Returns max confidence of template match (0.0 → 1.0)
        """
        try:
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val
        except:
            return 0.0
    def _create_white_mask(self, frame, threshold=200):
        """
        Create mask for near-white pixels (#FFFFFF-like).
        Works in BGR space.
        """
        if frame is None:
            return None

        # White = all channels high
        lower = np.array([threshold, threshold, threshold], dtype=np.uint8)
        upper = np.array([255, 255, 255], dtype=np.uint8)

        mask = cv2.inRange(frame, lower, upper)

        # Optional: clean noise (VERY important for shaders)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)

        return mask
    def _get_template_confidence_masked(self, frame, template):
        """
        Template matching constrained to white regions.
        Keeps robustness under shaders / scaling.
        """
        try:
            if frame is None or template is None:
                return 0.0

            # Create mask from ORIGINAL frame (color)
            mask = self._create_white_mask(frame)

            # Convert frame to grayscale (like your pipeline)
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply mask → zero out non-white areas
            masked_frame = cv2.bitwise_and(gray_frame, gray_frame, mask=mask)

            result = cv2.matchTemplate(masked_frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            return max_val

        except Exception as e:
            print(f"Masked template error: {e}")
            return 0.0
    def _prepare_templates_masked(self):
        """
        Optional: make templates white-only for stronger matching.
        """
        for key in self.templates:
            tpl = self.templates.get(key)
            if tpl is None:
                continue

            if len(tpl.shape) == 3:
                # Keep only bright pixels
                gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
                _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

                self.templates[key] = mask
    def _find_first_pixel(self, frame, hex, tolerance=8):
        tolerance = int(np.clip(tolerance, 0, 255))
        b, g, r = self._hex_to_bgr(hex)
        white = np.array([b, g, r], dtype=np.int16)
        frame_i = frame.astype(np.int16)

        mask = np.all(
            np.abs(frame_i - white) <= tolerance,
            axis=-1
        )

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
        
        # Convert hex to BGR
        bgr_color = self._hex_to_bgr(target_color_hex)
        if bgr_color is None:
            return []
        
        # Create color range with tolerance
        lower_bound = np.array([
            max(0, bgr_color[0] - tolerance),
            max(0, bgr_color[1] - tolerance),
            max(0, bgr_color[2] - tolerance)
        ])
        upper_bound = np.array([
            min(255, bgr_color[0] + tolerance),
            min(255, bgr_color[1] + tolerance),
            min(255, bgr_color[2] + tolerance)
        ])
        
        # Create mask for matching colors
        mask = cv2.inRange(frame, lower_bound, upper_bound)
        y_coords, x_coords = np.where(mask > 0)
        
        # Return as list of (x, y) tuples
        if len(x_coords) > 0:
            return list(zip(x_coords, y_coords))
        return []
    def _find_color_center(self, frame, target_color_hex, tolerance=8):
        """
        Find the center point of a color cluster in a frame.
        Using vectorized detection.
        """

        if frame is None:
            return None

        # Convert color
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int16)

        # Convert frame for safe subtraction
        frame_int = frame.astype(np.int16)

        tol = int(np.clip(tolerance, 0, 255))

        # Vectorized absolute tolerance comparison
        mask = np.all(np.abs(frame_int - target_bgr) <= tol, axis=2)

        y_coords, x_coords = np.where(mask)

        if len(x_coords) == 0:
            return None

        # Center calculation (vectorized mean)
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
        # required_fish_pixels
        if frame is None:
            return None

        # COLOR MASK (vectorized like your fast version) 
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int16)
        frame_int = frame.astype(np.int16)
        tol = int(np.clip(tolerance, 0, 255))

        mask = np.all(np.abs(frame_int - target_bgr) <= tol, axis=2).astype(np.uint8)

        if not np.any(mask):
            return None

        # CONNECTED COMPONENTS (cluster detection) 
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        if num_labels <= 1:
            return None  # only background

        # Skip label 0 (background)
        largest_label = None
        largest_area = 0

        for label in range(1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]

            if area > largest_area and area >= min_area:
                largest_area = area
                largest_label = label

        if largest_label is None:
            return None

        # CENTROID 
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

        y = int(h * scan_height_ratio)

        # Convert to BGR
        left_bgr = np.array(self._hex_to_bgr(left_hex), dtype=np.int16)
        right_bgr = np.array(self._hex_to_bgr(right_hex), dtype=np.int16)

        # Extract scan line
        line = frame[y].astype(np.int16)

        # Clamp tolerances
        tol_l = int(np.clip(tolerance, 0, 255))
        tol_r = int(np.clip(tolerance2, 0, 255))

        # LEFT MASK (with lower + upper bound) 
        left_lower = left_bgr - tol_l
        left_upper = left_bgr + tol_l
        left_mask = np.all((line >= left_lower) & (line <= left_upper), axis=1)

        # RIGHT MASK (with lower + upper bound) 
        right_lower = right_bgr - tol_r
        right_upper = right_bgr + tol_r
        right_mask = np.all((line >= right_lower) & (line <= right_upper), axis=1)

        left_indices = np.where(left_mask)[0]
        right_indices = np.where(right_mask)[0]

        # Keep your original edge logic
        left_edge = int(left_indices[0]) if left_indices.size else None
        right_edge = int(right_indices[-1]) if right_indices.size else None

        return left_edge, right_edge
    # Other calculations
    def _find_arrow_indicator_x(self, frame, arrow_hex, tolerance, is_holding):
        """
        If releasing -> Left arrow -> Use min
        If holding -> Right arrow -> Use max
        """
        pixels = self._pixel_search(frame, arrow_hex, tolerance)
        if not pixels:
            return None

        xs = [x for x, _ in pixels]

        indicator_x = max(xs) if is_holding else min(xs)

        # Small jitter filter
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
        # Handle missing arrow
        if arrow_centroid_x is None:
            if self.last_known_box_center_x is not None:
                return self.last_known_box_center_x
            return None
        # Check if state swapped (holding <-> not holding)
        state_swapped = (self.last_holding_state is not None and 
                        is_holding != self.last_holding_state)
        
        # When swapping: measure new box size from arrow positions
        if state_swapped and self.last_indicator_x is not None:
            new_box_size = abs(arrow_centroid_x - self.last_indicator_x)
            if new_box_size >= 10:  # Reasonable minimum
                self.estimated_box_length = new_box_size
        
        # Set default box size if we don't have one
        if self.estimated_box_length is None or self.estimated_box_length <= 0:
            if self.last_bar_size is not None and self.last_bar_size > 0:
                self.estimated_box_length = self.last_bar_size

        # Position the box based on current hold state
        if is_holding:
            # Holding: arrow is on RIGHT, extend LEFT
            self.last_right_x = float(arrow_centroid_x)
            self.last_left_x = self.last_right_x - self.estimated_box_length
        else:
            # Not holding: arrow is on LEFT, extend RIGHT
            self.last_left_x = float(arrow_centroid_x)
            self.last_right_x = self.last_left_x + self.estimated_box_length
        
        # Clamp to capture bounds (keep arrow anchored)
        if self.last_left_x < 0:
            self.last_left_x = 0.0
            self.last_right_x = min(self.estimated_box_length, capture_width)
        
        if self.last_right_x > capture_width:
            self.last_right_x = float(capture_width)
            self.last_left_x = max(0.0, self.last_right_x - self.estimated_box_length)
        
        # Calculate and store center
        box_center = (self.last_left_x + self.last_right_x) / 2.0
        self.last_known_box_center_x = box_center
        
        # Update tracking variables for next frame
        self.last_indicator_x = arrow_centroid_x
        self.last_holding_state = is_holding

        # Return values
        left_x = self.last_left_x
        right_x = self.last_right_x
        return box_center, left_x, right_x
    # Do pixel/image search
    def _do_pixel_search(self, img):
        fish_hex = self.vars["fish_color"].get()
        left_bar_hex = self.vars["left_color"].get()
        right_bar_hex = self.vars["right_color"].get()

        left_tol = int(self.vars["left_tolerance"].get() or 8)
        right_tol = int(self.vars["right_tolerance"].get() or 8)
        fish_tol = int(self.vars["fish_tolerance"].get() or 1)

        required_fish_pixels = int(self.vars["required_fish_pixels"].get() or 10)
        # macOS tolerance buffer to make configs cross-compatible
        if sys.platform == "darwin":
            left_tol += 2
            right_tol += 2
            fish_tol += 2
        fish_center = self._find_color_cluster(img, fish_hex, fish_tol, required_fish_pixels)
        left_bar_center, right_bar_center = self._find_bar_edges(img, left_bar_hex, right_bar_hex, left_tol, right_tol)
        if left_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(img, right_bar_hex, right_bar_hex, right_tol, right_tol)
        elif right_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(img, left_bar_hex, left_bar_hex, left_tol, left_tol)
        return fish_center, left_bar_center, right_bar_center
    # Get values from GUI (repeated in cast, shake and minigame)
    def _resolve_area(self, area_key, fallback):
        area = self.bar_areas.get(area_key)

        if isinstance(area, dict):
            left = area["x"]
            top = area["y"]
            right = left + area["width"]
            bottom = top + area["height"]
        else:
            left, top, right, bottom = fallback

        width = right - left
        height = bottom - top

        return left, top, right, bottom, width, height
    def _scale_rect(self, left, top, right, bottom, scale):
        return (
            int(left * scale),
            int(top * scale),
            int(right * scale),
            int(bottom * scale),
        )
    def _load_minigame_config(self):
        v = self.vars

        return {
            "arrow_hex": v["arrow_color"].get(),
            "arrow_tol": int(v["arrow_tolerance"].get() or 8),

            "left_ratio": float(v["left_ratio"].get() or 0.5),
            "right_ratio": float(v["right_ratio"].get() or 0.5),

            "pid_clamp": float(v["pid_clamp"].get() or 100),
            "thresh": float(v["stabilize_threshold"].get() or 8),

            "restart_method": v["restart_method"].get(),
            "restart_delay": float(v["restart_delay"].get()),

            "track_notes": v["track_notes"].get(),
            "track_charges": v["track_charges"].get(),

            "note_box_hex": v["note_box_color"].get(),
            "note_box_tol": int(v["note_box_tolerance"].get() or 8),
            "note_track_ratio": float(v["note_track_ratio"].get() or 0.1),

            "charge_track_ratio": float(v["charge_track_ratio"].get() or 0.23),

            "scan_delay": float(v["minigame_scan_delay"].get() or 0.05),
            "tracking_threshold": float(v["tracking_threshold"].get() or 0),
            "tracking_threshold2": float(v["tracking_threshold2"].get() or 0),

            "rejected_pixels": float(v["rejected_pixels"].get() or 50),
        }
    # Controllers (PID and Maelstrom)
    def _get_pid_gains(self):
        """Get PID gains from config, with sensible defaults."""
        try:
            kp = float(self.vars["proportional_gain"].get() or 0.6)
            kd = float(self.vars["derivative_gain"].get() or 0.2)
        except:
            kp = 0.6
            kd = 0.2
        return kp, kd

    def _pid_control(self, error, bar_center_x=None):
        """
        Compute PD output using proportional gain system from comet reference.
        Uses velocity-based derivative with asymmetric damping.
        """

        now = time.perf_counter()
        pd_clamp = float(self.vars["pid_clamp"].get() or 100)
        # first sample: initialize state and return zero control
        if self.last_time is None:
            self.last_time = now
            self.prev_error = error
            if bar_center_x is not None:
                self.last_bar_x = bar_center_x
            return 0.0

        dt = now - self.last_time
        if dt <= 0:
            return 0.0

        kp, kd = self._get_pid_gains()

        # P term - proportional to how far we need to move
        p_term = kp * error

        # D term - asymmetric damping based on situation
        d_term = 0.0
        if bar_center_x is not None and self.last_bar_x is not None and dt > 0:
            bar_velocity = (bar_center_x - self.last_bar_x) / dt
            error_magnitude_decreasing = abs(error) < abs(self.prev_error) if self.prev_error is not None else False
            bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
            damping_multiplier = 2.0 if (error_magnitude_decreasing and bar_moving_toward_target) else 0.5
            d_term = -kd * damping_multiplier * bar_velocity
        else:
            # Fallback to standard derivative
            if self.prev_error is not None and dt > 0:
                d_term = kd * (error - self.prev_error) / dt

        # Combined control signal (PD controller output)
        control_signal = p_term + d_term
        control_signal = max(-pd_clamp, min(pd_clamp, control_signal))  # Clamp output

        # update history
        self.prev_error = error
        self.last_time = now
        if bar_center_x is not None:
            self.last_bar_x = bar_center_x

        return control_signal

    def _reset_pid_control_state(self):
        """Reset only PD/PID control memory without touching bar estimation state."""

        # Core PID error + timing state + state variables (all used by _pid_control method)
        self.prev_error = 0.0          # prevents derivative kick
        self.last_time = None          # forces fresh dt on next frame
        self.pid_last_time = None      # forces fresh dt calculation
        self.pid_prev_error = 0.0      # prevents derivative kick
        self.pid_integral = 0.0        # resets accumulated integral term

        # Bar / measurement state
        self.last_bar_x = None
        self.prev_measurement = None   # derivative source
        self.filtered_derivative = 0.0
        self.pid_source = None
    def _reset_predictive_control_state(self):
        """Reset predictive controller memory for a fresh minigame/controller cycle."""

        self._pred_prev_fish_x = None
        self._pred_prev_bar_x = None
        self._pred_prev_time = None
        self._pred_filtered_fish_vel = 0.0
        self._pred_filtered_bar_vel  = 0.0
        self._pred_last_click_time = 0.0
    def _reset_detection_cache(self):
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None
    def _cache_detection_state(self, fish_x=None, left_x=None, right_x=None):
        if fish_x is not None:
            self.last_fish_x = fish_x
        if left_x is not None and right_x is not None:
            self.last_bar_left = left_x
            self.last_bar_right = right_x
    def _reset_pid_state(self):
        """
        Reset PD/PID control state variables for a new minigame cycle.
        Ensures no derivative spikes, velocity carryover, or stabilization drift.
        """

        self._reset_pid_control_state()
        self._reset_detection_cache()

        # Also reset arrow estimation state
        self.last_indicator_x = None
        self.last_holding_state = None
        self.estimated_box_length = None
        self.last_left_x = None
        self.last_right_x = None
        self.last_known_box_center_x = None
    def _detect_charge_region(
        self,
        frame,
        bar_center,
        bar_size,
        fish_top,
        fish_height,
        charge_track_ratio,
        scale
    ):
        """
        Detect charge bar edges inside a dynamically computed region.
        Returns: (charge_left2, charge_right2, charge_size2)
        """

        # Compute region (screen space) 
        charge_half_size = bar_size * 0.4

        charge_left = bar_center - charge_half_size
        charge_right = bar_center + charge_half_size

        charge_top = int(fish_height * charge_track_ratio * 0.8) + fish_top
        charge_bottom = int(fish_height * charge_track_ratio * 1.2) + fish_top

        # Scale to capture space 
        h, w = frame.shape[:2]

        charge_left_s   = int(max(0, charge_left * scale))
        charge_right_s  = int(min(w, charge_right * scale))
        charge_top_s    = int(max(0, charge_top * scale))
        charge_bottom_s = int(min(h, charge_bottom * scale))

        # Validate region 
        if charge_right_s <= charge_left_s or charge_bottom_s <= charge_top_s:
            return None, None, None

        # Crop 
        charge_img = frame[
            charge_top_s:charge_bottom_s,
            charge_left_s:charge_right_s
        ]

        # Detect edges 
        charge_left2, charge_right2 = self._find_bar_edges(
            charge_img,
            "#F1F1F1",
            "#FFFFFF",
            8, 8, 0.6
        )

        # Compute size 
        if charge_left2 is not None and charge_right2 is not None:
            charge_size2 = charge_right2 - charge_left2
        else:
            charge_size2 = None

        return charge_left2, charge_right2, charge_size2, charge_left, charge_img
    def _compute_charge_state(
        self,
        charge_size2,
        last_charge_size,
        charge_lost_frames,
        bar_size
    ):
        """
        Stabilizes charge detection and returns usable charge state.
        """

        # Update tracking
        if charge_size2 is not None and charge_size2 > 0:
            last_charge_size = charge_size2
            charge_lost_frames = 0
        else:
            charge_lost_frames += 1

        # Stabilize (anti-flicker)
        if charge_lost_frames < 3:
            effective_charge = last_charge_size
        else:
            effective_charge = 0

        # Derived values
        colors_detected = effective_charge > 0
        effective_charge_ratio = (effective_charge / bar_size) if bar_size else 0

        return {
            "effective_charge": effective_charge,
            "effective_charge_ratio": effective_charge_ratio,
            "colors_detected": colors_detected,
            "last_charge_size": last_charge_size,
            "charge_lost_frames": charge_lost_frames,
        }
    def _charge_control(
        self,
        fish_x,
        fish_left,
        fish_right,
        bar_left_screen,
        bar_right_screen,
        bar_size,
        charge_state,
        maelstrom_state,
        colors_were_missing,
        left_ratio,
        right_ratio,
        now,
        charge_cooldown_until,
        charge_left2=None,
        charge_right2=None,
    ):
        """
        IRUS-style Maelstrom controller (adapted for pixel tracking).
        """

        # --
        # VALIDATION
        # --
        has_charge = (
            charge_left2 is not None and
            charge_right2 is not None and
            charge_state["effective_charge"] > 0
        )

        # --
        # COOLDOWN
        # --
        if now < charge_cooldown_until:
            return False, maelstrom_state, colors_were_missing, charge_cooldown_until

        # --
        # BAR SECTIONS
        # --
        charge_size = bar_right_screen - bar_left_screen
        left_threshold = bar_left_screen + (charge_size * left_ratio)
        right_threshold = bar_left_screen + (charge_size * right_ratio)

        in_left = fish_x < left_threshold
        in_middle = left_threshold <= fish_x <= right_threshold
        in_right = fish_x > right_threshold

        # Edge detection (important)
        edge_threshold = charge_size * 0.15
        at_right_edge = fish_x > (fish_right - edge_threshold)

        should_hold = False

        # --
        # MAIN LOGIC (IRUS PORT)
        # --
        if has_charge:
            # Colors detected → clear missing flag
            colors_were_missing = False

            # RIGHT EDGE OVERRIDE 
            if at_right_edge:
                maelstrom_state = "minigame"
                should_hold = not colors_were_missing
                return should_hold, maelstrom_state, colors_were_missing, charge_cooldown_until

            # LEFT SECTION 
            if in_left:
                maelstrom_state = "moving_to_right"
                should_hold = False

            # RIGHT SECTION 
            elif in_right:
                maelstrom_state = "minigame"
                should_hold = not colors_were_missing

            # MIDDLE SECTION 
            else:
                if maelstrom_state == "moving_to_right":
                    # Keep releasing until we reach right
                    should_hold = False
                else:
                    maelstrom_state = "minigame"
                    should_hold = not colors_were_missing

        else:
            # --
            # NO COLORS DETECTED
            # --
            colors_were_missing = True
            should_hold = False

            if in_left:
                maelstrom_state = "moving_to_right"

        # --
        # HARD STOP (ANTI OVERFILL)
        # --
        if charge_state["effective_charge_ratio"] >= 0.6:
            should_hold = False
            maelstrom_state = "cooldown"
            charge_cooldown_until = now + 0.2

        return should_hold, maelstrom_state, colors_were_missing, charge_cooldown_until
    def _predictive_control(self, fish_x, bar_center, bar_left, bar_right, fish_left, fish_right, hold_mouse, release_mouse):
        """
        Predictive controller ported from IRUS idiotproof.
        Uses linear stopping distance, on-bar counter-thrust, off-bar PD chase,
        and edge-unreachability logic.
        """

        # INIT FAILSAFE 
        if not hasattr(self, "_pred_prev_fish_x"):
            self._reset_predictive_control_state()

        # FAILSAFE: missing data 
        if fish_x is None or bar_center is None or bar_left is None or bar_right is None:
            release_mouse()
            return

        # READ SETTINGS 
        try:
            VEL_SMOOTH = float(self.vars["velocity_smoothing"].get())
        except:
            VEL_SMOOTH = 0.25

        try:
            stopping_mult = float(self.vars["stopping_distance"].get())
        except:
            stopping_mult = 0.9

        kp, kd = self._get_pid_gains()

        MIN_DT = 1e-3
        MAX_DT = 0.1
        MAX_VEL = 3000.0

        # TIME 
        now = time.perf_counter()
        if self._pred_prev_time is None:
            dt = 0.016
        else:
            dt = now - self._pred_prev_time
            dt = max(min(dt, MAX_DT), MIN_DT)
        self._pred_prev_time = now

        # VELOCITIES 
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

        # Smooth velocities independently then compute relative
        self._pred_filtered_fish_vel = (VEL_SMOOTH * raw_fish_vel +
                                        (1 - VEL_SMOOTH) * self._pred_filtered_fish_vel)
        self._pred_filtered_bar_vel  = (VEL_SMOOTH * raw_bar_vel +
                                        (1 - VEL_SMOOTH) * self._pred_filtered_bar_vel)

        rel_vel = self._pred_filtered_bar_vel - self._pred_filtered_fish_vel  # bar relative to fish (matches ref macro sign)

        self._pred_prev_fish_x = fish_x
        self._pred_prev_bar_x  = bar_center

        # NaN GUARD 
        if not np.isfinite(rel_vel):
            release_mouse()
            return

        # REACHABILITY (edge logic) 
        bar_width = bar_right - bar_left
        min_reachable = fish_left  + bar_width // 2
        max_reachable = fish_right - bar_width // 2

        if fish_x < min_reachable:
            # Target too far left — bar can't follow, release
            release_mouse()
            return
        elif fish_x > max_reachable:
            # Target too far right — hold to push bar right
            hold_mouse()
            return

        # STOPPING DISTANCE (linear, same as reference macro) 
        stopping_distance = abs(rel_vel) * stopping_mult

        # error: positive = bar is right of fish (same sign convention as ref macro)
        error = bar_center - fish_x

        target_on_bar = bar_left <= fish_x <= bar_right

        if target_on_bar:
            # ON-BAR: use stopping-distance / counter-thrust logic
            if error < -stopping_distance:
                # Bar is left of fish beyond stopping distance → hold to move right
                hold_mouse()
            elif error > stopping_distance:
                # Bar is right of fish beyond stopping distance → release to move left
                release_mouse()
            else:
                # Within stopping distance — counter-thrust based on relative velocity
                if rel_vel > 0:
                    # Bar moving right relative to fish → release (apply left thrust)
                    release_mouse()
                else:
                    # Bar moving left relative to fish → hold (apply right thrust)
                    hold_mouse()
        else:
            # OFF-BAR: PD chase using existing gains
            control_output = kp * error + kd * rel_vel
            if control_output > 0:
                release_mouse()   # need to move bar left
            else:
                hold_mouse()      # need to move bar right
    # Main macro loop
    def start_macro(self):
        self.macro_running = True # flag to control macro loop and allow safe stopping
        # Get shake area for mouse movement areas
        shake = self.bar_areas.get("shake")
        if isinstance(shake, dict):
            shake_left   = shake["x"]
            shake_top    = shake["y"]
            shake_right  = shake["x"] + shake["width"]
            shake_bottom = shake["y"] + shake["height"]
            shake_x = int((shake_left + shake_right) / 2)
            shake_y = int((shake_top + shake_bottom) / 2)
        else:
            shake_x = int(self.SCREEN_WIDTH * 0.5)
            shake_y = int(self.SCREEN_HEIGHT * 0.3)
        self._reset_pid_state()
        self.set_status("Macro Status: Running")

        # Reset Discord webhook and totem counters for this run
        self.webhook_cycle_counter = 0
        self.webhook_start_time = time.time()
        self.totem_cycle_counter = 0
        self.totem_start_time = time.time()
        # Retrieve variables from GUI
        rod_slot = str(self.vars["rod_slot"].get())
        bag_slot = str(self.vars["bag_slot"].get())
        bait_delay = float(self.vars["bait_delay"].get())

        if self.vars["auto_zoom"].get() == "on":
            for _ in range(20):
                mouse_controller.scroll(0, 1)
                time.sleep(0.05)
            mouse_controller.scroll(0, -1)
            time.sleep(0.1)
        # Loop: MAIN MACRO LOOP
        while self.macro_running:
            # Initial camera and cycle alignment
            mouse_controller.position = (shake_x, shake_y)
            # Totem
            self._check_totem_trigger(shake_x, shake_y)
            # Select rod
            if self.vars["auto_refresh"].get() == "on":
                bag_delay = float(self.vars["bag_delay"].get())
                self.set_status("Selecting rod")
                # Sequence
                keyboard_controller.press(bag_slot)
                time.sleep(0.05)
                keyboard_controller.release(bag_slot)
                time.sleep(bag_delay)
                keyboard_controller.press(rod_slot)
                time.sleep(0.05)
                keyboard_controller.release(rod_slot)
                time.sleep(0.2)
            if not self.macro_running:
                break
            # Toggle fish overlay
            if self.vars["fish_overlay"].get() == "on":
                self.fish_overlay.show()
            else:
                self.fish_overlay.hide()

            # Cast
            self.set_status("Casting")
            if self.vars["casting_mode"].get() == "Perfect":
                self._execute_cast_perfect()
            else:
                self._execute_cast_normal()

            # Optional delay after cast
            try:
                delay = float(self.vars["cast_duration"].get() or 0.6)
                time.sleep(delay)
            except:
                time.sleep(0.6)

            if not self.macro_running:
                break

            # Shake
            self.set_status("Shaking")
            if self.vars["shake_mode"].get() == "Click":
                self._execute_shake_click()
            else:
                self._execute_shake_navigation()

            if not self.macro_running:
                break

            # Fish (minigame)
            self.set_status("Fishing")
            time.sleep(bait_delay)
            self._enter_minigame()

            # ── Discord webhook trigger (runs after every completed cycle) ──
            self._check_discord_webhook_trigger()
            # Restart: When minigame ends, loop repeats from Select Rod
    def _check_discord_webhook_trigger(self):
        """Check whether the Discord webhook should fire based on the selected mode.

        Modes (discord_webhook_cd):
          Cycles  – fire every N completed cycles (configurable via discord_webhook_cycle)
          Time    – fire every N seconds elapsed  (configurable via discord_webhook_time)
          Disabled – never fire
        """
        cd_mode = self.vars["discord_webhook_cd"].get()

        if cd_mode == "Disabled":
            return  # webhook type is disabled; do nothing

        if cd_mode == "Cycles":
            try:
                trigger_every = int(self.vars["discord_webhook_cycle"].get())
            except (ValueError, KeyError):
                trigger_every = 3  # safe fallback

            self.webhook_cycle_counter += 1

            if trigger_every > 0 and self.webhook_cycle_counter % trigger_every == 0:
                label = f"Cycle #{self.webhook_cycle_counter}"
                self.send_discord_webhook("**Cycle Checkpoint**", label, show_status=True)

        elif cd_mode == "Time":
            try:
                trigger_secs = float(self.vars["discord_webhook_time"].get())
            except (ValueError, KeyError):
                trigger_secs = 60.0  # safe fallback

            self.webhook_cycle_counter += 1  # still count cycles for the message label
            elapsed = time.time() - self.webhook_start_time

            if trigger_secs > 0 and elapsed >= trigger_secs:
                label = f"Cycle #{self.webhook_cycle_counter} | {int(elapsed)}s elapsed"
                self.send_discord_webhook("**Time Checkpoint**", label, show_status=True)
                # Reset the timer so it fires again after another trigger_secs seconds
                self.webhook_start_time = time.time()
    def _check_totem_trigger(self, shake_x, shake_y):
        """Check whether auto totem should trigger based on mode."""

        mode = self.vars["auto_totem_mode"].get()

        if mode == "Disabled":
            return

        # 
        # CYCLES MODE
        # 
        if mode == "Cycles":
            try:
                trigger_every = int(self.vars["totem_cycles"].get())
            except:
                trigger_every = 3

            self.totem_cycle_counter += 1

            if not (trigger_every > 0 and self.totem_cycle_counter % trigger_every == 0):
                return

        # 
        # TIME MODE (NEW)
        # 
        elif mode == "Time":
            try:
                trigger_secs = float(self.vars["totem_time"].get())
            except:
                trigger_secs = 60.0

            elapsed = time.time() - self.totem_start_time

            if not (trigger_secs > 0 and elapsed >= trigger_secs):
                return

            # reset timer
            self.totem_start_time = time.time()
            self.totem_cycle_counter += 1

        else:
            return

        # EXECUTE TOTEM
        self.set_status("Using Totem")

        sundial_slot = str(self.vars["sundial_slot"].get())
        target_slot  = str(self.vars["target_slot"].get())
        use_sundial_mode_when  = self.vars["use_sundial_mode_when"].get()
        use_sundial = False

        totem_success = False
        detection_valid = False

        # IMAGE SEARCH (REPLACES COLOR)
        try:
            totem = self.bar_areas.get("totem")

            if not isinstance(totem, dict):
                return  # safety

            frame = self._grab_screen_region(
                totem["x"],
                totem["y"],
                totem["x"] + totem["width"],
                totem["y"] + totem["height"]
            )
            sun_template  = self.templates.get("sun")
            moon_template = self.templates.get("moon")

            sun_conf  = self._get_template_confidence_masked(frame, sun_template)
            moon_conf = self._get_template_confidence_masked(frame, moon_template)

            # ✅ Only mark detection valid if confidence is good
            if max(sun_conf, moon_conf) >= confidence_threshold:
                detection_valid = True
                current_time = "Day" if sun_conf > moon_conf else "Night"
            else:
                # ❌ NOT an error → just skip quietly
                return
        except Exception as e:
            if not self.macro_running:
                return
            self.macro_running = False
            self._reset_pid_state()
            self.after(0, self.deiconify)  # show window safely
            self.set_status(f"Macro crashed during totem execution: {e}")
            self.send_bug_report(f"Error: {e}", phase="Totem")
            messagebox.showerror("Macro crashed during totem execution", f"Error: {e}")

        if use_sundial_mode_when == "Day":
            # If it's currently NIGHT → use sundial to force DAY
            if current_time == "Night":
                use_sundial = True

        elif use_sundial_mode_when == "Night":
            # If it's currently DAY → use sundial to force NIGHT
            if current_time == "Day":
                use_sundial = True

        if use_sundial == True:
            time.sleep(0.2)

            # Sundial
            keyboard_controller.press(sundial_slot)
            time.sleep(0.05)
            keyboard_controller.release(sundial_slot)
            time.sleep(0.2)

            mouse_controller.position = (shake_x, shake_y)
            time.sleep(0.05)
            self._click_at(shake_x, shake_y)

            time.sleep(20)

        # Optional safety threshold
        confidence_threshold = 0.6

        if detection_valid:
            time.sleep(0.2)
            # Re-use totem
            keyboard_controller.press(target_slot)
            time.sleep(0.05)
            keyboard_controller.release(target_slot)
            time.sleep(0.4)

            mouse_controller.position = (shake_x, shake_y)
            time.sleep(0.05)
            self._click_at(shake_x, shake_y)
            time.sleep(1)

        if totem_success:
            self.send_discord_webhook("Totem used successfully", self.totem_cycle_counter, show_status=True)
    def _execute_cast_normal(self):
        """Hold left click for user cast delay"""
        # Get variables
        delay2 = float(self.vars["delay_before_casting"].get() or 0.0)
        duration = float(self.vars["cast_duration"].get() or 0.6)
        delay = float(self.vars["cast_delay"].get() or 0.2)
        # Set status
        time.sleep(delay2)  # wait for cast to register in other games
        mouse_controller.press(Button.left)
        time.sleep(duration)  # adjust cast strength
        mouse_controller.release(Button.left)
        time.sleep(delay)  # wait for cast to register in fisch
    def _execute_cast_perfect(self):
        """
        Scans for green and white Y coordinates and releases left click when
        the top white Y reaches 95% of the area from green Y to bottom white Y.
        """
        try:
            self._execute_cast_perfect_inner()
        except Exception as e:
            if not self.macro_running:
                return
            mouse_controller.release(Button.left)
            self.macro_running = False
            self._reset_pid_state()
            self.after(0, self.deiconify)
            self.set_status(f"Macro crashed during perfect cast: {e}")
            self.send_bug_report(f"Error: {e}", phase="Perfect Cast")
            messagebox.showerror("Macro crashed during perfect cast", f"Error: {e}")

    def _execute_cast_perfect_inner(self):
        """Inner body of perfect cast — called by _execute_cast_perfect."""
        # Hold mouse
        mouse_controller.press(Button.left)
        # Get scale factor
        scale = self._get_scale_factor()

        # Area 
        shake_left, shake_top, shake_right, shake_bottom, _, shake_height = self._resolve_area(
            "shake",
            (
                int(self.SCREEN_WIDTH * 0.1041),
                int(self.SCREEN_HEIGHT * 0.0925),
                int(self.SCREEN_WIDTH * 0.8958),
                int(self.SCREEN_HEIGHT * 0.8333),
            )
        )

        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s = self._scale_rect(
            shake_left, shake_top, shake_right, shake_bottom, scale)

        # Config 
        white_color = self.vars["perfect_color2"].get()
        green_color = self.vars["perfect_color"].get()
        white_tol = int(self.vars["perfect_cast2_tolerance"].get())
        green_tol = int(self.vars["perfect_cast_tolerance"].get())

        max_time = float(self.vars["perfect_max_time"].get())
        scan_delay = float(self.vars["cast_scan_delay"].get())
        release_delay = float(self.vars["perfect_release_delay"].get())
        perfect_threshold = float(self.vars["perfect_threshold"].get())

        # Idiotproof-style release timing:
        # negative values release earlier via prediction multiplier, positive values
        # push the release threshold closer to 100%.
        release_timing = max(-50.0, min(50.0, release_delay))

        target_green = np.array(self._hex_to_bgr(green_color), dtype=np.int16)
        target_white = np.array(self._hex_to_bgr(white_color), dtype=np.int16)

        tracking_mode = False
        green_left_x = None
        green_right_x = None
        green_y = None
        green_padding = 50
        reached_bottom_5_percent = True  # Always allow release; the "bottom 5%" gate was preventing release when Xs start already close together
        last_fill_percentage = None
        last_frame_time = None
        speed_samples = []
        max_speed_samples = 20

        def color_mask(img, target_bgr, tolerance):
            img_i = img.astype(np.int16)
            return np.all(np.abs(img_i - target_bgr) <= tolerance, axis=2)

        def reset_tracking():
            nonlocal tracking_mode, green_left_x, green_right_x, green_y
            nonlocal reached_bottom_5_percent, last_fill_percentage, last_frame_time
            tracking_mode = False
            green_left_x = None
            green_right_x = None
            green_y = None
            reached_bottom_5_percent = True  # Keep release always enabled on re-track
            last_fill_percentage = None
            last_frame_time = None
            speed_samples.clear()

        # Start capture thread; this remains the existing V3 capture path.
        stop_event = self._start_capture(scan_delay)
        start_time = time.time()
        if self.vars["fish_overlay"].get() == "Enabled":
            self.fish_overlay.show()

        # Perfect Cast Loop
        while self.macro_running:
            if not self._cap_event.wait(timeout=0.5):
                if time.time() - start_time > max_time:
                    break
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

            if self.vars["fish_overlay"].get() == "Enabled":
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
            print("Green: ", green_y)

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

            current_time = time.time()
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
                base_offset = 1.5 * math.log(1 + fill_speed / 25.0) # Find 

                if release_timing < 0:
                    base_multiplier = 1.0 - (release_timing / 5.0)
                    speed_scale = min(6.0, (fill_speed / 100.0) ** 2)
                    timing_multiplier = 1.0 + (base_multiplier - 1.0) * speed_scale
                    position_offset_percent = max(0.0, min(50.0, base_offset * timing_multiplier))
                else:
                    position_offset_percent = max(0.0, min(50.0, base_offset))

            predicted_fill_percentage = actual_fill_percentage + position_offset_percent
            offset_pixels = int((position_offset_percent / 100.0) * total_distance)
            predicted_white_y_top = white_y_top - offset_pixels
            print("White: ", predicted_white_y_top)

            bottom_threshold = 5.0 + position_offset_percent
            if predicted_fill_percentage <= bottom_threshold and not reached_bottom_5_percent:
                reached_bottom_5_percent = True
                last_fill_percentage = None
                last_frame_time = None
                speed_samples.clear()

            if self.vars["fish_overlay"].get() == "Enabled":
                gy_canvas = int((green_y / shake_height) * 60)
                wy_canvas = int((predicted_white_y_top / shake_height) * 60)
                self.after(0, lambda y=gy_canvas: self.fish_overlay.draw( bar_center=y, box_size=15, color="green", canvas_offset=0 ))
                self.after(0, lambda y=wy_canvas: self.fish_overlay.draw( bar_center=y, box_size=30, color="white", canvas_offset=0 ))

            if release_timing <= 0:
                release_threshold = perfect_threshold
            else:
                release_threshold = perfect_threshold + (release_timing / 50.0) * 4.5

            if reached_bottom_5_percent and predicted_fill_percentage >= release_threshold:
                break

            last_fill_percentage = actual_fill_percentage
            last_frame_time = current_time

            if time.time() - start_time > max_time:
                break

        # CLEANUP 
        stop_event.set()
        mouse_controller.release(Button.left)
    def _execute_shake_click(self):
        """
        Search for first shake pixel then click
        Duplicate pixel logic from v13 is coming soon
        """
        try:
            self._execute_shake_click_inner()
        except Exception as e:
            if not self.macro_running:
                return
            self.macro_running = False
            self._reset_pid_state()
            self.after(0, self.deiconify)
            self.set_status(f"Macro crashed during shake (click): {e}")
            self.send_bug_report(f"Error: {e}", phase="Shake Click")
            messagebox.showerror("Macro crashed during shake (click)", f"Error: {e}")

    def _execute_shake_click_inner(self):
        """Inner body of shake-click — called by _execute_shake_click."""
        # Get scale factor
        scale = self._get_scale_factor()

        # Areas 
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._resolve_area(
            "shake",
            (
                int(self.SCREEN_WIDTH * 0.1041),
                int(self.SCREEN_HEIGHT * 0.0925),
                int(self.SCREEN_WIDTH * 0.8958),
                int(self.SCREEN_HEIGHT * 0.8333),
            )
        )

        fish_left, fish_top, fish_right, fish_bottom, _, _ = self._resolve_area(
            "fish",
            (
                int(self.SCREEN_WIDTH * 0.2844),
                int(self.SCREEN_HEIGHT * 0.7981),
                int(self.SCREEN_WIDTH * 0.7141),
                int(self.SCREEN_HEIGHT * 0.8370),
            )
        )

        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._resolve_area(
            "friend",
            (
                int(self.SCREEN_WIDTH * 0.0046),
                int(self.SCREEN_HEIGHT * 0.8583),
                int(self.SCREEN_WIDTH * 0.0401),
                int(self.SCREEN_HEIGHT * 0.94),
            )
        )

        # Scaling 
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s = self._scale_rect(
            shake_left, shake_top, shake_right, shake_bottom, scale
        )

        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s = self._scale_rect(
            fish_left, fish_top, fish_right, fish_bottom, scale
        )

        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s = self._scale_rect(
            friend_left, friend_top, friend_right, friend_bottom, scale
        )
        # Misc variables
        detection_method = (self.vars["detection_method"].get())
        shake_area = self.bar_areas["shake"]
        shake_hex = self.vars["shake_color"].get()
        fish_hex = self.vars["fish_color"].get()
        tolerance = int(self.vars["shake_tolerance"].get())
        scan_delay = float(self.vars["shake_scan_delay"].get())
        failsafe = int(self.vars["shake_failsafe"].get() or 40)
        bar_hex = self.vars["left_color"].get()
        bar_tolerance = int(self.vars["left_tolerance"].get())
        shake_clicks = int(self.vars["shake_clicks"].get())

        required_fish_pixels = int(self.vars["required_fish_pixels"].get() or 10)
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
            if shake_area is None:
                time.sleep(scan_delay)
                continue
            # 2. Look for shake pixel
            shake_pixel = self._find_first_pixel(shake_area, shake_hex, tolerance)
            if shake_pixel:
                x, y = shake_pixel
                screen_x = shake_left + x
                screen_y = shake_top + y
                self._click_at(screen_x, screen_y, shake_clicks)
            # 2. Fish detection (Multiple Methods)
            detected = False
            while detected == False and self.macro_running:
                if detection_method == "Friend Area":
                    detection_area = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                else:
                    detection_area = frame[fish_top_s:fish_bottom_s, fish_left_s:fish_right_s]
                if detection_area is None:
                    break
                if detection_method == "Friend Area":
                    friend_x = self._find_color_center( detection_area, "#9bff9b", tolerance )
                fish_x = self._find_color_cluster(detection_area, fish_hex, tolerance, required_fish_pixels)
                bar_x = self._find_color_center( detection_area, bar_hex, bar_tolerance )
                if detection_method == "Friend Area":
                    if not friend_x:
                        detected = True
                        time.sleep(0.005)
                    else:
                        break
                elif detection_method == "Fish + Bar":
                    if fish_x and bar_x:
                        detected = True
                        time.sleep(0.005)
                    else:
                        break
                else:
                    if fish_x:
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
        """Spams the enter key until fish detection is found (ICF V1 logic)"""
        try:
            self._execute_shake_navigation_inner()
        except Exception as e:
            if not self.macro_running:
                return
            self.macro_running = False
            self._reset_pid_state()
            self.after(0, self.deiconify)
            self.set_status(f"Macro crashed during shake (navigation): {e}")
            self.send_bug_report(f"Error: {e}", phase="Shake Navigation")
            messagebox.showerror("Macro crashed during shake (navigation)", f"Error: {e}")

    def _execute_shake_navigation_inner(self):
        """Inner body of shake-navigation — called by _execute_shake_navigation."""
        self.set_status("Shake Mode: Navigation")
        # Get scale factor
        scale = self._get_scale_factor()

        fish_left, fish_top, fish_right, fish_bottom, _, _ = self._resolve_area(
            "fish",
            (
                int(self.SCREEN_WIDTH * 0.2844),
                int(self.SCREEN_HEIGHT * 0.7981),
                int(self.SCREEN_WIDTH * 0.7141),
                int(self.SCREEN_HEIGHT * 0.8370),
            )
        )

        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._resolve_area(
            "friend",
            (
                int(self.SCREEN_WIDTH * 0.0046),
                int(self.SCREEN_HEIGHT * 0.8583),
                int(self.SCREEN_WIDTH * 0.0401),
                int(self.SCREEN_HEIGHT * 0.94),
            )
        )

        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s = self._scale_rect(
            fish_left, fish_top, fish_right, fish_bottom, scale
        )

        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s = self._scale_rect(
            friend_left, friend_top, friend_right, friend_bottom, scale
        )

        # Misc variables
        fish_hex = self.vars["fish_color"].get()
        tolerance = int(self.vars["shake_tolerance"].get())
        scan_delay = float(self.vars["shake_scan_delay"].get())
        failsafe = int(self.vars["shake_failsafe"].get() or 20)
        detection_method = (self.vars["detection_method"].get())
        bar_hex = self.vars["left_color"].get() # Left bar color replaced by left color
        bar_tolerance = int(self.vars["left_tolerance"].get())
        required_fish_pixels = int(self.vars["required_fish_pixels"].get() or 10)
        attempts = 0
        stop_event = self._start_capture(scan_delay)
        while self.macro_running and attempts < failsafe:
            # 1. Navigation shake (Enter key)
            keyboard_controller.press(Key.enter)
            time.sleep(0.03)
            keyboard_controller.release(Key.enter)
            time.sleep(scan_delay)
            # 2. Fish detection (Multiple Methods)
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
                    return
                if detection_method == "Friend Area":
                    detection_area = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                else:
                    detection_area = frame[fish_top_s:fish_bottom_s, fish_left_s:fish_right_s]
                if detection_area is None:
                    break
                if detection_method == "Friend Area":
                    friend_x = self._find_color_center( detection_area, "#9bff9b", tolerance )
                fish_x = self._find_color_cluster(detection_area, fish_hex, tolerance, required_fish_pixels)
                bar_x = self._find_color_center( detection_area, bar_hex, bar_tolerance )
                if detection_method == "Friend Area":
                    if not friend_x:
                        detected = True
                        time.sleep(0.005)
                    else:
                        break
                elif detection_method == "Fish + Bar":
                    if fish_x and bar_x:
                        detected = True
                        time.sleep(0.005)
                    else:
                        break
                else:
                    if fish_x:
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
    def _enter_minigame(self):
        # Get scale factor
        scale = self._get_scale_factor()

        # Areas 
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._resolve_area(
            "shake",
            (
                int(self.SCREEN_WIDTH * 0.1041),
                int(self.SCREEN_HEIGHT * 0.0925),
                int(self.SCREEN_WIDTH * 0.8958),
                int(self.SCREEN_HEIGHT * 0.8333),
            )
        )

        fish_left, fish_top, fish_right, fish_bottom, fish_width, fish_height = self._resolve_area(
            "fish",
            (
                int(self.SCREEN_WIDTH * 0.2844),
                int(self.SCREEN_HEIGHT * 0.7981),
                int(self.SCREEN_WIDTH * 0.7141),
                int(self.SCREEN_HEIGHT * 0.8370),
            )
        )

        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._resolve_area(
            "friend",
            (
                int(self.SCREEN_WIDTH * 0.0046),
                int(self.SCREEN_HEIGHT * 0.8583),
                int(self.SCREEN_WIDTH * 0.0401),
                int(self.SCREEN_HEIGHT * 0.94),
            )
        )

        # Scaling 
        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s = self._scale_rect(
            fish_left, fish_top, fish_right, fish_bottom, scale
        )

        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s = self._scale_rect(
            shake_left, shake_top, shake_right, shake_bottom, scale
        )

        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s = self._scale_rect(
            friend_left, friend_top, friend_right, friend_bottom, scale
        )

        # Config 
        cfg = self._load_minigame_config()

        arrow_hex = cfg["arrow_hex"]
        arrow_tol = cfg["arrow_tol"]
        left_ratio = cfg["left_ratio"]
        right_ratio = cfg["right_ratio"]
        pid_clamp = cfg["pid_clamp"]
        thresh = cfg["thresh"]
        restart_method = cfg["restart_method"]
        restart_delay = cfg["restart_delay"]
        track_notes = cfg["track_notes"]
        track_charges = cfg["track_charges"]
        note_box_hex = cfg["note_box_hex"]
        note_box_tol = cfg["note_box_tol"]
        note_track_ratio = cfg["note_track_ratio"]
        charge_track_ratio = cfg["charge_track_ratio"]
        scan_delay = cfg["scan_delay"]
        tracking_threshold = cfg["tracking_threshold"]
        tracking_threshold2 = cfg["tracking_threshold2"]
        # Reset PID gains
        self._reset_pid_state()
        # Set default values
        mouse_down = False
        fish_x = None
        controller_mode = 3
        previous_controller_mode = controller_mode
        deadzone_action = 0
        charge_cooldown_until = 0
        charge_lost_frames = 0
        last_charge_size = 0
        charge_size2 = 0
        max_left = fish_left - 20
        max_right = fish_right + 20
        # Maelstrom-style charge control variables
        maelstrom_state = "minigame"  # State machine: "minigame" or "moving_to_right"
        colors_were_missing = False  # Track if colors were lost
        maelstrom_left_section = left_ratio  # Left section ratio
        maelstrom_right_section = right_ratio  # Right section ratio
        # Bar direction-jump rejection
        _cached_left_x = None   # last accepted left edge (local to this minigame)
        _cached_right_x = None  # last accepted right edge (local to this minigame)
        _BAR_MAX_RIGHT_JUMP = cfg["rejected_pixels"]
        charge_left2 = None
        charge_right2 = None
        charge_left = None
        # Predictive controller state 
        self._pred_prev_fish_x = None
        self._pred_prev_bar_x = None
        self._pred_prev_time = None
        self._pred_filtered_vel = 0.0
        # Hold and release mouse
        def hold_mouse():
            nonlocal mouse_down
            if not mouse_down:
                mouse_controller.press(Button.left)
                # keyboard_controller.press(Key.space)
                mouse_down = True
        def release_mouse():
            nonlocal mouse_down
            if mouse_down:
                mouse_controller.release(Button.left)
                # keyboard_controller.release(Key.space)
                mouse_down = False
        # Start screen capture thread using the tracked capture lifecycle.
        stop_event = self._start_capture(scan_delay)
        # Prepare templates for image search (disabled for now)
        # for key in ["fish", "left_bar", "right_bar"]:
        #   template = self.templates.get(key)

        #   if template is None:
        #       continue

        #   # Convert to grayscale once
        #   if len(template.shape) == 3:
        #       template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        while self.macro_running: # Main macro loop
            try:
                # Grab full screen then crop
                if not self._cap_event.wait(timeout=0.5):
                    continue

                with self._cap_lock:
                    frame = self._cap_frame
                    self._cap_event.clear()

                if frame is None:
                    stop_event.set()
                    return

                img = frame[fish_top_s:fish_bottom_s, fish_left_s:fish_right_s]
                note_img = frame[shake_top_s:shake_bottom_s, shake_left_s:shake_right_s]
                friend_img = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
                # Deadzone/simple tracking actions
                deadzone_action = deadzone_action + 1
                if deadzone_action == 2:
                    deadzone_action = 0
                # Do pixel and image search
                if False:
                    img_h = img.shape[0]
                    fish_x, left_x, right_x = self._do_image_search(img, img_h)
                else:
                    fish_x, left_x, right_x = self._do_pixel_search(img)
                # ── Bar direction-jump rejection ─────
                if left_x is not None and right_x is not None:
                    if (
                        _cached_left_x is not None
                        and left_x > _cached_left_x + _BAR_MAX_RIGHT_JUMP
                    ):
                        # Outlier frame — discard and reuse cached values
                        left_x = _cached_left_x
                        right_x = _cached_right_x
                    else:
                        # Accept this frame and update cache
                        _cached_left_x = left_x
                        _cached_right_x = right_x
                elif left_x is None and right_x is None:
                    # No bar found this frame — cache stays unchanged
                    pass
                # ───────────
                # Find arrow indicator
                arrow_indicator_x = self._find_arrow_indicator_x(img, arrow_hex, arrow_tol, mouse_down)
                if track_notes == "on":
                    note_box_pos = self._find_color_center(note_img, note_box_hex, note_box_tol)
                else:
                    note_box_pos = None
                # Convert fish X from tuple to int
                if fish_x is None:
                    pass
                elif isinstance(fish_x, (list, tuple)):
                    fish_x = fish_x[0] + fish_left
                else:
                    fish_x = fish_x + fish_left
                # Fish restart and clear overlay logic with multiple restart methods and PID reset when bars are lost
                self.fish_overlay.clear()
                if restart_method == "Friend Area":
                    friend_x = self._find_color_center(friend_img, "#9bff9b", 2)
                    # Cache fish and bar positions when found
                    self._cache_detection_state(fish_x, left_x, right_x)
                    # If friend pixel is found, restart (cycle ends)
                    if friend_x is not None:
                        release_mouse()
                        time.sleep(restart_delay)
                        return
                    # If bars not found, use cached bar positions
                    if left_x is None or right_x is None:
                        if self.last_bar_left is not None and self.last_bar_right is not None:
                            left_x = self.last_bar_left
                            right_x = self.last_bar_right
                    # If fish not found, use cached fish position
                    if fish_x is None and self.last_fish_x is not None:
                        fish_x = self.last_fish_x
                elif restart_method == "Fish + Bar":
                    if fish_x is not None:
                        self._cache_detection_state(fish_x)
                    else:
                        if left_x is None and right_x is None:
                            release_mouse()
                            time.sleep(restart_delay)
                            return
                        else:
                            fish_x = self.last_fish_x
                else:
                    if fish_x is not None:
                        self._cache_detection_state(fish_x)
                    else:
                        release_mouse()
                        time.sleep(restart_delay)
                        return
                # Compute bar variables for calculations
                bars_found = left_x is not None and right_x is not None
                if bars_found == True:
                    bar_size = right_x - left_x # Don't add fish left here
                    self.last_bar_size = bar_size
                    bar_center = (left_x + bar_size // 2) + fish_left # ADD FISH LEFT HERE
                    left_deadzone = bar_size * left_ratio
                    right_deadzone = bar_size * right_ratio
                    max_left = fish_left + left_deadzone
                    max_right = fish_right - right_deadzone
                    # Compute charge values (only if charge is on to prevent CPU spikes)
                    if track_charges == "on" and bars_found:
                        charge_left2, charge_right2, charge_size2, charge_left, _ = self._detect_charge_region(
                            frame,
                            bar_center,
                            bar_size,
                            fish_top,
                            fish_height,
                            charge_track_ratio,
                            scale
                        )
                else:
                    bar_size = None
                    bar_center = None
                    charge_left2 = None
                    charge_right2 = None
                    charge_left = None
                # Main minigame loop
                if bars_found and bar_center is not None: # Bar found
                    # Track notes
                    # note tracking logic
                    if note_box_pos is not None:
                        ## Step 1: Convert note to screen coordinates
                        shake_width = shake_right - shake_left
                        fish_width = fish_right - fish_left
                        note_screen_x = int((note_box_pos[0] / shake_width) * fish_width) + fish_left
                        note_screen_y = note_box_pos[1] - shake_top
                        note_screen_y_ratio = note_screen_y / (shake_bottom - shake_top)
                    else:
                        note_screen_x = None
                    if note_box_pos is not None and track_notes == "on":
                        if note_screen_y_ratio >= note_track_ratio:
                            fish_x = note_screen_x
                    elif track_notes == "off":
                        pass
                    # Compute bar left and bar right (screen coords)
                    bar_left_screen  = left_x  + fish_left - tracking_threshold
                    bar_right_screen = right_x + fish_left + tracking_threshold2
                    # Check max left and max right
                    if max_left is not None and fish_x <= max_left: # Max left and right check (inside bar)
                        controller_mode = 3
                    elif max_right is not None and fish_x >= max_right:
                        controller_mode = 2
                    else:
                        if bar_left_screen <= fish_x <= bar_right_screen:
                            if track_charges == "on":
                                controller_mode = 4
                            else:
                                controller_mode = 0
                        else:
                            controller_mode = 1
                elif arrow_indicator_x:
                    # Indicator failsafe
                    if arrow_indicator_x is None:
                        controller_mode = 3
                        return
                    # Capture width and estimate bar center
                    capture_width = fish_right - fish_left
                    estimated_bar_center, estimated_left, estimated_right = self._update_arrow_box_estimation(arrow_indicator_x, mouse_down, capture_width)
                    # Now use estimated bar to control
                    if estimated_bar_center is not None:
                        bar_center = int(estimated_bar_center + fish_left)
                        bar_left_screen  = estimated_left  + fish_left - tracking_threshold
                        bar_right_screen = estimated_right + fish_left + tracking_threshold2
                        bar_size = bar_right_screen - bar_left_screen
                        if bar_left_screen <= fish_x <= bar_right_screen:
                            if track_charges == "on":
                                controller_mode = 4
                            else:
                                controller_mode = 0
                        else:
                            controller_mode = 1
                    else:
                        controller_mode = 3
                # Check if outside bar to use simple tracking instead
                if track_charges == "on" and bar_left_screen <= fish_x <= bar_right_screen:
                    controller_mode = 4
                elif controller_mode == 0:
                    if not bar_left_screen <= fish_x <= bar_right_screen:
                        controller_mode = 1
                    else:
                        if self.vars["efficiency_mode"].get() == "on":
                            controller_mode = 5
                        else:
                            controller_mode = 0
                if controller_mode == 0 and previous_controller_mode != 0:
                    self._reset_pid_control_state()
                if controller_mode == 5 and previous_controller_mode != 5: # Reset stopping distance state
                    self._reset_predictive_control_state()
                # Draw boxes
                if self.vars["fish_overlay"].get() == "on":
                    self.after(0, lambda _bc=bar_center, _bs=bar_size, _fl=fish_left: self.fish_overlay.draw(bar_center=_bc, box_size=_bs, color="green", canvas_offset=_fl, show_bar_center=True, bar_y1=10, bar_y2=30))
                    self.after(0, lambda _ml=max_left, _fl=fish_left: self.fish_overlay.draw(bar_center=_ml, box_size=15, color="lightblue", canvas_offset=_fl)) # 10 and 40
                    self.after(0, lambda _mr=max_right, _fl=fish_left: self.fish_overlay.draw(bar_center=_mr, box_size=15, color="lightblue", canvas_offset=_fl))
                    self.after(0, lambda: self.fish_overlay.draw(bar_center=fish_x, box_size=10, color="red", canvas_offset=fish_left))
                # Cache values for debug
                self._debug_bar_center = bar_center
                self._debug_bar_size = bar_size
                self._debug_fish_top = fish_top
                self._debug_fish_height = fish_height
                self._debug_frame = frame
                # PID loop
                if controller_mode == 0 and bar_center is not None:
                    error = fish_x - bar_center
                    control = self._pid_control(error, bar_center)
                    # Map PID output to mouse clicks using hysteresis to avoid jitter/oscillation
                    control = max((0 - pid_clamp), min(pid_clamp, control))
                    # Stabilize Deadzone Checker
                    if control > thresh:
                        hold_mouse()
                    elif control < -thresh:
                        release_mouse()
                    else:
                        if deadzone_action == 1:
                            hold_mouse()
                        else:
                            release_mouse()
                elif controller_mode == 1 and bar_center is not None: # Simple tracking
                    control = fish_x - bar_center
                    small_error_soft_zone = max(1.0, thresh)
                    if abs(control) <= small_error_soft_zone:
                        control = 0.0
                    else:
                        control = math.copysign(abs(control) - small_error_soft_zone, control)
                    # Stabilize Deadzone Checker
                    if control > 0:
                        hold_mouse()
                    elif control < 0:
                        release_mouse()
                elif controller_mode == 2:
                    hold_mouse()
                elif controller_mode == 3:
                    release_mouse()
                elif controller_mode == 4:
                    now = time.time()

                    # TRACKING 
                    charge_state = self._compute_charge_state(
                        charge_size2,
                        last_charge_size,
                        charge_lost_frames,
                        bar_size
                    )

                    last_charge_size = charge_state["last_charge_size"]
                    charge_lost_frames = charge_state["charge_lost_frames"]
                    effective_charge = charge_state["effective_charge"]
                    # Convert charge center from crop space → screen space
                    if charge_left2 is not None and charge_right2 is not None:
                        charge_center2 = int((charge_left2 + charge_right2) / 2) / scale + charge_left
                        self.after(0, lambda: self.fish_overlay.draw(bar_center=charge_center2, box_size=effective_charge, color="orange", canvas_offset=fish_left, show_bar_center=False, bar_y1=30, bar_y2=40))

                    # CONTROL 
                    should_hold, maelstrom_state, colors_were_missing, charge_cooldown_until = self._charge_control(
                        fish_x,
                        fish_left,
                        fish_right,
                        bar_left_screen,
                        bar_right_screen,
                        bar_size,
                        charge_state,
                        maelstrom_state,
                        colors_were_missing,
                        left_ratio,
                        right_ratio,
                        now,
                        charge_cooldown_until,
                        charge_left2,
                        charge_right2
                    )

                    # EXECUTION 
                    if should_hold:
                        hold_mouse()
                    else:
                        release_mouse()
                elif controller_mode == 5 and bar_center is not None:
                    self._predictive_control(
                        fish_x,
                        bar_center,
                        bar_left_screen,
                        bar_right_screen,
                        fish_left,
                        fish_right,
                        hold_mouse,
                        release_mouse
                    )
                previous_controller_mode = controller_mode
                time.sleep(scan_delay)
            except Exception as e:
                if not self.macro_running:
                    return
                self.macro_running = False
                self._reset_pid_state()
                self.after(0, self.deiconify)  # show window safely
                self.set_status(f"Macro crashed during minigame loop: {e}")
                self.send_bug_report(f"Error: {e}", phase="Minigame")
                messagebox.showerror("Macro crashed during minigame loop", f"Error: {e}")
        if self._active_capture_stop is stop_event:
            self._stop_active_capture()
        else:
            stop_event.set()
    def stop_macro(self):
        if not self.macro_running:
            return
        self.macro_running = False
        self._stop_active_capture()
        self._reset_pid_state()
        self.after(0, self.deiconify)  # show window safely
        self.set_status("Macro Status: Stopped")
if __name__ == "__main__":
    app = App()
    app.mainloop()
