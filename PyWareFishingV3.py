# Gui-Related
from customtkinter import *
import tkinter as tk
from tkinter import messagebox
# Save And Load
import json
import os
import subprocess
# Keyboard And Mouse
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
try:
    import Quartz
    import ctypes
except (OSError, ImportError):
    messagebox.showerror("Ctypes/Quartz Error", "Unsupported platform. Mouse click will use fallback method")
# Key Listeners
import threading
from pynput.keyboard import Listener as KeyListener, Key
macro_running = False
macro_thread = None
# Initialize Controllers
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
# Timing-Related
import time
# Opencv And Mss For Pixel Search
import cv2
import numpy as np
import mss
# Webbrowser For Opening Links
import webbrowser
# Utilities
import requests
import io
import math
import gdown
import shutil
import traceback
from collections import deque
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
# Get All Required Paths
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

BASE_PATH, IS_COMPILED = get_base_path()

CONFIG_DIR = os.path.join(BASE_PATH, "configs")
IMAGES_PATH = os.path.join(BASE_PATH, "images")
DEBUG_DIR = BASE_PATH

CONFIG_PATH = os.path.join(BASE_PATH, "last_config.json")
APP_VERSION = "3.21"

set_appearance_mode("dark")

def ensure_last_config_exists():
    """Ensure last_config.json exists at BASE_PATH, create default if missing."""
    config_file = os.path.join(BASE_PATH, "last_config.json")
    
    # Check If It Exists As A File (Not A Directory)
    if os.path.exists(config_file):
        if os.path.isdir(config_file):
            # It'S A Directory - Remove It And Recreate As File
            print(f"Removing directory at {config_file} to create file...")
            try:
                os.rmdir(config_file)  # Use Shutil.Rmtree() If Directory Has Contents
                print(f"Removed directory: {config_file}")
            except Exception as e:
                print(f"Could not remove directory: {e}")
                # Try To Rename It As Backup
                backup_path = config_file + "_backup_folder"
                os.rename(config_file, backup_path)
                print(f"Renamed directory to: {backup_path}")
        else:
            # It Exists As A File, No Action Needed
            return config_file
    
    # Create Default Config Structure
    default_config = {
        "version": None,
        "last_profile": "default",
        "last_macro_name": None,
        "settings": {},
        "tos_accepted": False
    }
    
    try:
        # Ensure The Parent Directory Exists
        os.makedirs(BASE_PATH, exist_ok=True)
        
        # Write The File
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        print(f"Created default config file at: {config_file}")
    except Exception as e:
        print(f"Error creating config file: {e}")
        pass
    
    return config_file

ensure_last_config_exists()
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(IMAGES_PATH, exist_ok=True)

def load_app_state():
    # Default State
    state = {
        "version": None,
        "tos_accepted": False
    }

    # Use Config_Path (The Actual File) Instead Of Config_Dir
    if os.path.exists(CONFIG_PATH):  # Config_Path Is The File, Config_Dir Is The Folder
        try:
            with open(CONFIG_PATH, "r") as f:
                state.update(json.load(f))
        except Exception as e:
            print(f"Error loading config: {e}")
            # Corrupted File = Treat As First Launch
            pass

    # Detection Logic
    is_first_launch = state["version"] is None
    is_new_version = state["version"] != APP_VERSION

    return state, is_first_launch, is_new_version

def save_app_state(state):
    # Ensure The Directory Exists Before Writing
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(state, f, indent=4)
        # Print(F"Successfully Saved Config To: {Config_Path}")
    except Exception as e:
        print(f"Error saving config: {e}")
        # Optionally Show Error To User
        messagebox.showerror("Save Error", f"Could not save configuration: {e}")
# ── Pack Download Helper ─────────────────────────────────────────────────────
# Drive folder that contains configs.zip and images.zip
PACK_FOLDER_URL = "https://drive.google.com/drive/folders/1pDSSKYRmMHQcv2SSrMxfzcGz4mgY-esS"

def download_and_extract_packs(status_callback=None):
    """
    Downloads configs.zip and images.zip from the Drive folder,
    extracts configs.zip → CONFIG_DIR, images.zip → IMAGES_PATH.

    Handles nested zip structures like:
      configs.zip → configs/configs/<files>   (strips the outer wrapper)
      images.zip  → images/images/<files>     (strips the outer wrapper)

    status_callback(msg: str) is called with progress text so the UI can
    display it.  Pass None to suppress UI updates.
    """
    import zipfile
    import tempfile

    def _status(msg):
        print(msg)
        if status_callback:
            status_callback(msg)

    def _extract_flat(zip_path, dest_dir):
        """
        Extract zip into dest_dir, stripping any common leading path prefix
        so files always land directly in dest_dir regardless of how many
        wrapper folders the zip contains.

        e.g.  configs/configs/rod1.json  →  <dest_dir>/rod1.json
              images/images/sun.png      →  <dest_dir>/sun.png
              rod1.json                  →  <dest_dir>/rod1.json  (no prefix)
        """
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [m for m in zf.infolist() if not m.filename.endswith("/")]

            if not members:
                return  # empty zip

            # Find the longest common leading path shared by all members
            # e.g. ["configs/configs/a.json", "configs/configs/b.json"]
            #   → common prefix parts = ["configs", "configs"]
            def parts(name):
                return name.replace("\\", "/").split("/")[:-1]  # drop filename

            common = parts(members[0].filename)
            for m in members[1:]:
                p = parts(m.filename)
                # Keep only the shared leading portion
                common = [c for c, q in zip(common, p) if c == q]
                if not common:
                    break

            prefix = "/".join(common) + "/" if common else ""

            for member in members:
                rel = member.filename.replace("\\", "/")
                if prefix and rel.startswith(prefix):
                    rel = rel[len(prefix):]  # strip the wrapper folder(s)
                if not rel:
                    continue
                out_path = os.path.join(dest_dir, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())

    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(IMAGES_PATH, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            _status("Downloading packs from Google Drive…")
            # gdown downloads every file in the folder into tmp_dir
            gdown.download_folder(
                url=PACK_FOLDER_URL,
                output=tmp_dir,
                quiet=True,
                use_cookies=False
            )

            # ── configs.zip ──────────────────────────────────────────────
            configs_zip = os.path.join(tmp_dir, "configs.zip")
            if os.path.exists(configs_zip):
                _status("Extracting configs.zip…")
                _extract_flat(configs_zip, CONFIG_DIR)
                _status(f"Config pack installed → {CONFIG_DIR}")
            else:
                _status("Warning: configs.zip not found in download.")

            # ── images.zip ───────────────────────────────────────────────
            images_zip = os.path.join(tmp_dir, "images.zip")
            if os.path.exists(images_zip):
                _status("Extracting images.zip…")
                _extract_flat(images_zip, IMAGES_PATH)
                _status(f"Image pack installed → {IMAGES_PATH}")
            else:
                _status("Warning: images.zip not found in download.")

        _status("Done! Both packs installed successfully.")
        return True

    except Exception as e:
        _status(f"Download/extract failed: {e}")
        return False

# Area Selector Class
class AreaSelector:
    HANDLE_SIZE = 8
    def __init__(self, parent, shake_area, fish_area, friend_area, totem_area, callback):
        self.parent = parent
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)

        self.window.configure(bg="#222244")
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
        self.draw_area(self.totem, "#9cff94", "Totem Box")

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
                                    fill=color, font=("Segoe UI", 11, "bold"),
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
# Live Eyedropper - Can Be Safely Pasted In Other Macros
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
        self.window.configure(bg="#111111")
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
# Status Overlay
class StatusOverlay:
    """Encapsulates the text-based status overlay (v1 → v3 refactor)."""

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.window = None
        self.labels = {}

    def init_window(self):
        """Create and initialize the overlay window."""
        if self.window and self.window.winfo_exists():
            return

        self.window = tk.Toplevel(self.parent_app)

        # Position (Top-Left Like V1)
        self.window.geometry(f"260x180+20+40")

        # Window Behavior (Aligned With Fishoverlay Style)
        if sys.platform == "darwin":
            self.window.overrideredirect(False)
            self.window.attributes("-transparent", True)
        else:
            self.window.overrideredirect(True)

        self.window.attributes("-topmost", True)
        self.window.configure(bg="black")

        # Optional Transparency
        try:
            self.window.attributes("-alpha", 0.93)
        except:
            pass

        # Disable Interaction On Windows (Same Intent As V1)
        if sys.platform.startswith("win"):
            try:
                self.window.attributes("-disabled", True)
            except:
                pass

        # Grid Config
        self.window.grid_columnconfigure(0, weight=1)

        # Title
        title = tk.Label(
            self.window,
            text="PyWare Fishing V3.21",
            fg="# 00C8Ff",
            bg="black",
            font=("Segoe UI", 12, "bold")
        )
        title.grid(row=0, column=0, pady=(8, 2), sticky="n")

        # Create 7 Status Lines (Changed From 5 To 7)
        for row in range(1, 8):
            lbl = tk.Label(
                self.window,
                text="",
                fg="white",
                bg="black",
                font=("Segoe UI", 10)
            )
            lbl.grid(row=row, column=0, sticky="n")
            self.labels[row] = lbl

    # Lifecycle

    def show(self):
        """Show the overlay."""
        self.init_window()
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()

    def hide(self):
        """Hide the overlay."""
        if self.window and self.window.winfo_exists():
            self.window.withdraw()

    def destroy(self):
        """Destroy overlay completely."""
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
        self.labels.clear()

    # Content Control

    def set_line(self, text, row=1):
        """Set text for a specific row (like ToolTip)."""
        if not self.window or not self.window.winfo_exists():
            return

        lbl = self.labels.get(row)
        if not lbl:
            return

        def _update():
            lbl.config(text=text)

        lbl.after(0, _update)

    def clear(self):
        """Clear all lines."""
        if not self.window or not self.window.winfo_exists():
            return

        def _clear():
            for lbl in self.labels.values():
                lbl.config(text="")

        self.window.after(0, _clear)
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
    def __init__(self, parent=None, show_setup=True):
        super().__init__(parent)

        self._show_setup = show_setup   # whether to present the setup / download page
        
        # Screen Size (Cache Once – Thread Safe)
        self.SCREEN_WIDTH = self.winfo_screenwidth()
        self.SCREEN_HEIGHT = self.winfo_screenheight()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Window
        self.configure(fg_color="#181836")   # <- Main Window Ultra Dark
        self.geometry("750x600")
        self.title("PyWare Fishing V3.21 - Terms of Service")
        self.minsize(650, 500)
        
        # Center Window
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (750 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"+{x}+{y}")

        # Status Bar
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header Stays Fixed
        self.grid_rowconfigure(1, weight=1)  # Content Expands
        self.grid_rowconfigure(2, weight=0)  # Nav Bar Fixed
        
        # Top Bar Frame (Status + Buttons)
        top_bar = CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=20, pady=10, sticky="ew")

        top_bar.grid_columnconfigure(0, weight=1)

        # Logo Label
        logo_label = CTkLabel(
            top_bar, 
            text="TERMS OF SERVICE",
            font=CTkFont(size=16, weight="bold")
        )
        logo_label.grid(row=0, column=0, sticky="w")

        # Main Content Container
        self.container = CTkFrame(self, border_color = "#364167", fg_color = "#222244") # 181836
        self.container.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Pages
        self.page_tos = CTkFrame(self.container, border_color = "#364167", fg_color = "#222244")
        self.page_setup = CTkFrame(self.container, border_color = "#364167", fg_color = "#222244")

        for page in (self.page_tos, self.page_setup):
            page.grid(row=0, column=0, sticky="nsew")

        # Agree Labels
        self.agree_var = BooleanVar(value=False)
        self.accepted = False

        # Build Pages
        self.build_tos_page(self.page_tos)
        if self._show_setup:
            self.build_setup_page(self.page_setup)

        # Navigation Bar
        nav_bar = CTkFrame(self, border_color = "#364167", fg_color = "#181836")
        nav_bar.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        nav_bar.grid_columnconfigure(1, weight=1)  # spacer between back and action btn

        self.back_btn   = CTkButton(nav_bar, text="Back",   command=self.go_back)
        # Single right-side action button: label changes per page
        # Page 0 (_show_setup=True)  → "Next"   (advances to setup page)
        # Page 0 (_show_setup=False) → "Finish" (closes dialog)
        # Page 1                     → "Finish" (closes dialog after Yes/No chosen)
        self.next_btn   = CTkButton(nav_bar, text="Next",   command=self.go_next)

        self.back_btn.grid(row=0, column=0, padx=5, sticky="w")
        self.next_btn.grid(row=0, column=2, padx=5, sticky="e")

        # Initial State
        self.current_page = 0
        self.show_page(0)
    # Basic Settings Tab
    def build_tos_page(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        textbox = CTkTextbox(parent, wrap="word", border_color = "#364167", fg_color = "#222244")
        textbox.grid(row=0, column=0, padx=12, pady=10, sticky="nsew")

        textbox.insert("1.0", """
PyWare Fishing V3.21 - Terms of Use

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
        textbox.configure(state="disabled")

        checkbox = CTkCheckBox(
            parent,
            text="I agree to the Terms of Service",
            variable=self.agree_var,
            command=self.update_next_button
        )
        checkbox.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")
    # Second Tab
    def build_setup_page(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # ── Info text ────────────────────────────────────────────────────
        textbox = CTkTextbox(parent, wrap="word", border_color="#364167",
                             fg_color="#222244", height=220)
        textbox.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="nsew")

        textbox.insert("1.0", """Setup Guide

Would you like to automatically download and install the Config Pack and Image Pack?

• YES  – The app will download configs.zip and images.zip from Google Drive
         and place them in the correct folders for you automatically.

• NO   – Skip the download. You can install packs manually later:
         Step 1: Download configs.zip and images.zip from the Drive link below.
         Step 2: Click "Open Base Folder" to locate your install directory.
         Step 3: Extract configs.zip into the  configs/  folder.
         Step 4: Extract images.zip  into the  images/  folder.
         Step 5: Set up your Bar Areas in the main app.

Drive link: https://drive.google.com/drive/folders/1pDSSKYRmMHQcv2SSrMxfzcGz4mgY-esS
        """)
        textbox.configure(state="disabled")

        # ── Download prompt ──────────────────────────────────────────────
        prompt_frame = CTkFrame(parent, fg_color="transparent")
        prompt_frame.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")

        CTkLabel(
            prompt_frame,
            text="Download Config & Image Pack now?",
            font=CTkFont(size=13, weight="bold")
        ).pack(side="left", padx=(0, 12))

        self._yes_btn = CTkButton(
            prompt_frame, text="Yes",
            fg_color="#2ecc71", hover_color="#27ae60",
            command=self._on_download_yes
        )
        self._yes_btn.pack(side="left", padx=4)

        self._no_btn = CTkButton(
            prompt_frame, text="No / Skip",
            fg_color="#555577", hover_color="#444466",
            command=self._on_download_no
        )
        self._no_btn.pack(side="left", padx=4)

        # ── Status / progress label ──────────────────────────────────────
        self._dl_status_var = tk.StringVar(value="")
        self._dl_status_label = CTkLabel(
            parent,
            textvariable=self._dl_status_var,
            wraplength=640,
            justify="left",
            font=CTkFont(size=11),
            text_color="#aaaacc"
        )
        self._dl_status_label.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="w")

    def _set_dl_status(self, msg):
        """Set status label directly (must be called from main thread)."""
        self._dl_status_var.set(msg)
        self.update_idletasks()

    def _poll_dl_queue(self):
        """Poll the thread-safe queue and apply any pending status messages."""
        try:
            import queue as _queue
            while True:
                item = self._dl_queue.get_nowait()
                if item is None:
                    # Sentinel — download finished, apply final state
                    if self._dl_success:
                        self._set_dl_status("✅ Packs installed! Click Finish to launch the app.")
                    else:
                        self._set_dl_status("❌ Download failed. You can install packs manually later.")
                    self.next_btn.configure(state="normal")
                    self._no_btn.configure(state="normal")
                    return  # stop polling
                else:
                    self._set_dl_status(item)
        except _queue.Empty:
            pass
        # Keep polling every 100 ms while download is running
        self._poll_id = self.after(100, self._poll_dl_queue)

    def _on_download_yes(self):
        """Kick off the download in a background thread so the UI stays live."""
        import queue as _queue
        self._yes_btn.configure(state="disabled")
        self._no_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        self._set_dl_status("Starting download…")

        self._dl_queue = _queue.Queue()
        self._dl_success = False

        def _worker():
            self._dl_success = download_and_extract_packs(
                status_callback=self._dl_queue.put   # just put strings in the queue
            )
            self._dl_queue.put(None)  # sentinel to signal completion

        threading.Thread(target=_worker, daemon=True).start()
        self._poll_id = self.after(100, self._poll_dl_queue)

    def _on_download_no(self):
        """Skip the download and allow the user to finish setup."""
        self._set_dl_status("Skipped download. Install packs manually before running macros.")
        self.next_btn.configure(state="normal")
    def show_page(self, index):
        self.current_page = index

        if index == 0:
            self.page_tos.tkraise()
            self.back_btn.configure(state="normal")
            agreed = self.agree_var.get()
            # Label depends on whether there is a setup page to advance to
            next_label = "Next" if self._show_setup else "Finish"
            self.next_btn.configure(
                text=next_label,
                state="normal" if agreed else "disabled"
            )
        elif index == 1:
            self.page_setup.tkraise()
            self.back_btn.configure(state="normal")
            # Finish stays disabled until the user clicks Yes or No/Skip
            self.next_btn.configure(text="Finish", state="disabled")

    def go_back(self):
        if self.current_page == 1:
            self.show_page(0)
        elif self.current_page == 0:
            self.on_close()

    def update_next_button(self):
        if self.current_page == 0:
            next_label = "Next" if self._show_setup else "Finish"
            self.next_btn.configure(
                text=next_label,
                state="normal" if self.agree_var.get() else "disabled"
            )

    def go_next(self):
        if self.current_page == 0 and self.agree_var.get():
            if self._show_setup:
                self.show_page(1)
            else:
                # No setup page — TOS acceptance alone is enough
                self.accepted = True
                self.destroy()
        elif self.current_page == 1:
            # Finish button on setup page
            self.accepted = True
            self.destroy()

    def on_close(self):
        if not self.accepted:
            self.accepted = False
        self.destroy()
# Main App
class App(CTk):
    def __init__(self):

        # Initialize Class
        super().__init__()

        # Initialize Save And Load (We Only Use
        # Entry, Checkboxes And Comboboxes)
        self.vars = {} # Save Entry Variables Here
        self.checkboxes = {}
        self.comboboxes = {} # Save Combobox Widgets Here For Dynamic Updates
        self.switches = {} # Save Ctkswitch Widgets Here For Load/Save

        # Store Screen Width And Height To Use Later
        self.SCREEN_WIDTH = self.winfo_screenwidth()
        self.SCREEN_HEIGHT = self.winfo_screenheight()
        self.BASE_PATH = BASE_PATH

        # Detection Variables
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None
        self.last_cached_box_length = None  # Cached Bar Size From Minigame For Arrow Estimation

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
        self._reset_control_state()

        # Hotkey Variables
        self.hotkey_start = Key.f5
        self.hotkey_stop = Key.f7
        self.hotkey_change_areas = Key.f6 # Added For The Bar Area Selector
        self.hotkey_screenshot = Key.f8
        self.hotkey_labels = {}  # Store Label Widgets For Dynamic Updates

        # Macro State
        self.macro_running = False
        self.macro_thread = None

        # Discord Webhook And Totem Trigger Counters
        self.webhook_cycle_counter = 0   # Incremented Each Fishing Cycle
        self.webhook_start_time = None   # Set When Macro Starts (For Time Mode)
        self.totem_cycle_counter = 0
        self.totem_start_time = time.time()
        
        # Safe Defaults Before Key Listener Starts (Will Be Overwritten By Load_Misc_Settings)
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
        self.current_rod_name = "Basic Rod"

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

        # Invalidate Scale Cache If The Window Moves To A Different Monitor
        if sys.platform == "darwin":
            self.bind("<Configure>", lambda e: self._invalidate_scale_cache())
        # Setup Overlay And Eyedropper
        self.fish_overlay = FishOverlay(self)
        self.eyedropper = Eyedropper(self)
        self.status_overlay = StatusOverlay(self)

        # Start Hotkey Listener
        self.key_listener = None
        self.after(100, self.start_listeners)

        # Create Window
        self.configure(fg_color="#181836")   # <- Main Window Ultra Dark
        self.geometry("800x600")
        self.title("PyWare Fishing V3.21")

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
            text="PYWARE FISHING V3.21",
            font=CTkFont(size=16, weight="bold")
        )
        logo_label.grid(row=0, column=0, sticky="w")

        # Status Label (Left Side)
        self.status_label = CTkLabel(top_bar, text="Macro status: Idle")
        self.status_label.grid(row=1, column=0, pady=5, sticky="w")

        # Buttons Frame (Right Side)
        button_frame = CTkFrame(top_bar, fg_color="transparent")
        button_frame.grid(row=0, column=1, sticky="e")

        CTkButton(
            button_frame,
            text="Upcoming",
            width=120,
            corner_radius=8,
            command=self.open_link("https://docs.google.com/document/d/1WwWWMR-eN-R-GO42IioToHpWTgiXkLoiNE_4NeE-GsU/edit?tab=t.0")
        ).pack(side="left", padx=6)

        CTkButton(
            button_frame,
            text="Website",
            width=120,
            corner_radius=8,
            command=self.open_link("https://sites.google.com/view/icf-automation-network/")
        ).pack(side="left", padx=6)

        CTkButton(
            button_frame,
            text="Tutorial",
            width=120,
            corner_radius=8,
            command=self.open_link("https://docs.google.com/document/d/1EgzNRa5nxw90zxP4aij3DXl7cbarKNW_ozISom4McV0/")
        ).pack(side="left", padx=6)

        # Tabs
        self.tabs = CTkTabview(
            self,
            anchor="w",
            border_color = "#414167", fg_color = "#222244"
        )

        self.tabs._segmented_button.configure(
            fg_color="#414167",
            selected_color="#676780",
            selected_hover_color="#525267",
            unselected_color="#414167",
            unselected_hover_color="#565680",
            text_color="#FFFFFF"
        )

        self.tabs.grid(
            row=1, column=0, columnspan=6,
            padx=20, pady=10, sticky="nsew"
        )

        self.tabs.add("Basic")
        self.tabs.add("Automation")
        self.tabs.add("Utilities")

        # Build Tabs
        self.build_basic_tab(self.tabs.tab("Basic"))
        self.build_automation_tab(self.tabs.tab("Automation"))
        self.build_utilities_tab(self.tabs.tab("Utilities"))

        # Load Last Config, Reapply Hotkeys And Set Reset Values
        self.load_last_config()
        self._apply_hotkeys_from_vars()
        self.default_settings_data = self._collect_settings_data()

        # Grid Behavior
        self.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(0, weight=0)  # Top_Bar
        self.grid_rowconfigure(1, weight=1)  # Tabs Expand

        self.refresh_config_dropdown() # Auto Refresh Config
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    # Build Gui
    # Basic Tab
    def build_basic_tab(self, parent):
        # Configure scroll bar
        scroll = CTkScrollableFrame(parent, fg_color = "#222244")
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Configure grid
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Build main GUI
        basic_settings = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
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

        CTkButton(
            basic_settings, 
            text="🔄", 
            width=40,
            corner_radius=8,
            command=self.refresh_config_dropdown
        ).grid(row=0, column=2, padx=12, pady=10, sticky="w")

        CTkButton(basic_settings, text="Open Base Folder", corner_radius=8, 
                  command=self.open_base_folder,
                  width=140
                  ).grid(row=0, column=1, padx=12, pady=12, sticky="w")

        CTkButton(basic_settings, text="Add", width=40, corner_radius=8, command=self.add_rod).grid(row=1, column=2, padx=12, pady=12, sticky="w")
        CTkButton(basic_settings, text="Delete", width=40, corner_radius=8, command=self.delete_rod).grid(row=1, column=3, padx=12, pady=12, sticky="w")

        CTkButton(basic_settings, text="Reset Settings", width=120, corner_radius=8, command=self.reset_settings).grid(row=3, column=0, padx=12, pady=12, sticky="w")
        CTkButton(basic_settings, text="Reset Colors", width=140, corner_radius=8, command=self.reset_colors).grid(row=3, column=1, padx=12, pady=12, sticky="w")
        # Hotkey and Hotbar Settings
        hotkey_hotbar_settings = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        hotkey_hotbar_settings.grid(row=1, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(hotkey_hotbar_settings, text="Hotkey Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(hotkey_hotbar_settings, text="Hotbar Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=12, pady=8, sticky="w")
        # Key binds
        CTkLabel(hotkey_hotbar_settings, text="Start Key").grid(row=1, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Change Bar Areas Key").grid(row=2, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Stop Key").grid(row=3, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Screenshot Key").grid(row=4, column=0, padx=12, pady=6, sticky="w" )
        # Disable hotkeys
        enable_hotkeys_var = StringVar(value="off")
        self.vars["enable_hotkeys"] = enable_hotkeys_var
        sw = CTkSwitch(hotkey_hotbar_settings, text="Toggle", variable=enable_hotkeys_var, onvalue="on", offvalue="off")
        sw.grid(row=0, column=1, padx=12, pady=8, sticky="w")
        self.switches["enable_hotkeys"] = sw
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
        screenshot_key_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=screenshot_key_var)
        screenshot_key_entry.grid(row=4, column=1, padx=12, pady=10, sticky="w")
        # Hotkey for items
        CTkLabel(hotkey_hotbar_settings, text="Fishing Rod:").grid(row=1, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Equipment Bag:").grid(row=2, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Sundial Totem:").grid(row=3, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Target Totem:").grid(row=4, column=2, padx=12, pady=6, sticky="w" )
        CTkLabel(hotkey_hotbar_settings, text="Mystic Mirror:").grid(row=5, column=2, padx=12, pady=6, sticky="w" )
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
        mirror_slot_var = StringVar(value="8")
        self.vars["mirror_slot"] = mirror_slot_var
        mirror_slot_entry = CTkEntry(hotkey_hotbar_settings, width=120, textvariable=mirror_slot_var)
        mirror_slot_entry.grid(row=5, column=3, padx=12, pady=8, sticky="w")

        color_settings = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        color_settings.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(color_settings, text="Color Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkButton(color_settings, text="Pick Colors", corner_radius=10, width=120, command=self.eyedropper.start).grid(row=0, column=1, padx=12, pady=12, sticky="w")

        CTkLabel(color_settings, text="Left Bar:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        left_color_var = StringVar(value="#F1F1F1")
        self.vars["left_color"] = left_color_var
        left_entry = CTkEntry(color_settings, placeholder_text="#F1F1F1", width=120, fg_color="green", textvariable=left_color_var)
        left_entry.grid(row=2, column=1, padx=12, pady=10, sticky="w")
        left_color_var.trace_add("write", lambda *args: self._update_entry_color(left_color_var, left_entry))
        self._update_entry_color(left_color_var, left_entry)
        CTkLabel(color_settings, text="Right Bar:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        right_color_var = StringVar(value="#FFFFFF")
        self.vars["right_color"] = right_color_var
        right_entry = CTkEntry(color_settings, placeholder_text="#FFFFFF", width=120, fg_color="green", textvariable=right_color_var)
        right_entry.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        right_color_var.trace_add("write", lambda *args: self._update_entry_color(right_color_var, right_entry))
        self._update_entry_color(right_color_var, right_entry)
        CTkLabel(color_settings, text="Arrow:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        arrow_color_var = StringVar(value="#848587")
        self.vars["arrow_color"] = arrow_color_var
        arrow_entry = CTkEntry(color_settings, placeholder_text="#848587", width=120, fg_color="green", textvariable=arrow_color_var)
        arrow_entry.grid(row=4, column=1, padx=12, pady=10, sticky="w")
        arrow_color_var.trace_add("write", lambda *args: self._update_entry_color(arrow_color_var, arrow_entry))
        self._update_entry_color(arrow_color_var, arrow_entry)
        CTkLabel(color_settings, text="Fish:").grid(row=5, column=0, padx=12, pady=10, sticky="w")
        fish_color_var = StringVar(value="#434B5B")
        self.vars["fish_color"] = fish_color_var
        fish_entry = CTkEntry(color_settings, placeholder_text="#434B5B", width=120, fg_color="green", textvariable=fish_color_var)
        fish_entry.grid(row=5, column=1, padx=12, pady=10, sticky="w")
        fish_color_var.trace_add("write", lambda *args: self._update_entry_color(fish_color_var, fish_entry))
        self._update_entry_color(fish_color_var, fish_entry)
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
        shake_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=shake_color_var)
        shake_entry.grid(row=6, column=1, padx=12, pady=10, sticky="w")
        shake_color_var.trace_add("write", lambda *args: self._update_entry_color(shake_color_var, shake_entry))
        self._update_entry_color(shake_color_var, shake_entry)
        # Shake Tolerance
        CTkLabel(color_settings, text="Tolerance:").grid(row=6, column=2, padx=12, pady=10, sticky="w" )
        shake_tolerance_var = StringVar(value="5")
        self.vars["shake_tolerance"] = shake_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=shake_tolerance_var).grid(row=6, column=3, padx=12, pady=10, sticky="w")
        # note box color and tolerance
        CTkLabel(color_settings, text="Tracking Target:").grid(row=7, column=0, padx=12, pady=10, sticky="w")
        note_box_color_var = StringVar(value="#00990c")
        self.vars["note_box_color"] = note_box_color_var
        note_box_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=note_box_color_var)
        note_box_entry.grid(row=7, column=1, padx=12, pady=10, sticky="w")
        note_box_color_var.trace_add("write", lambda *args: self._update_entry_color(note_box_color_var, note_box_entry))
        self._update_entry_color(note_box_color_var, note_box_entry)
        CTkLabel(color_settings, text="Tolerance:").grid(row=7, column=2, padx=12, pady=10, sticky="w")
        note_box_tolerance_var = StringVar(value="2")
        self.vars["note_box_tolerance"] = note_box_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=note_box_tolerance_var).grid(row=7, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Perfect Target:").grid(row=8, column=0, padx=12, pady=10, sticky="w")
        perfect_color_var = StringVar(value="#64a04c")
        self.vars["perfect_color"] = perfect_color_var
        perfect_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=perfect_color_var)
        perfect_entry.grid(row=8, column=1, padx=12, pady=10, sticky="w")
        perfect_color_var.trace_add("write", lambda *args: self._update_entry_color(perfect_color_var, perfect_entry))
        self._update_entry_color(perfect_color_var, perfect_entry)

        CTkLabel(color_settings, text="Tolerance:").grid(row=8, column=2, padx=12, pady=10, sticky="w")
        perfect_cast_tolerance_var = StringVar(value="16")
        self.vars["perfect_cast_tolerance"] = perfect_cast_tolerance_var
        perfect_cast_tolerance_entry = CTkEntry(color_settings, width=120, textvariable=perfect_cast_tolerance_var)
        perfect_cast_tolerance_entry.grid(row=8, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Casting:").grid(row=9, column=0, padx=12, pady=10, sticky="w")
        perfect_color2_var = StringVar(value="#d4d3ca")
        self.vars["perfect_color2"] = perfect_color2_var
        perfect2_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=perfect_color2_var)
        perfect2_entry.grid(row=9, column=1, padx=12, pady=10, sticky="w")
        perfect_color2_var.trace_add("write", lambda *args: self._update_entry_color(perfect_color2_var, perfect2_entry))
        self._update_entry_color(perfect_color2_var, perfect2_entry)

        CTkLabel(color_settings, text="Tolerance:").grid(row=9, column=2, padx=12, pady=10, sticky="w")
        perfect_cast2_tolerance_var = StringVar(value="5")
        self.vars["perfect_cast2_tolerance"] = perfect_cast2_tolerance_var
        perfect_cast2_tolerance_entry = CTkEntry(color_settings, width=120, textvariable=perfect_cast2_tolerance_var)
        perfect_cast2_tolerance_entry.grid(row=9, column=3, padx=12, pady=10, sticky="w")

    def build_automation_tab(self, parent):
        # Configure scroll bar
        scroll = CTkScrollableFrame(parent, fg_color = "#222244")
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # Configure grid
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        # Toggles
        toggles = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
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

        CTkLabel(toggles, text="Misc", font=CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=12, pady=8, sticky="w")

        CTkLabel(toggles, text="Select Rod Duration").grid(row=1, column=2, padx=12, pady=8, sticky="w")
        bag_delay_var = StringVar(value="0.2")
        self.vars["bag_delay"] = bag_delay_var
        bag_delay_entry = CTkEntry(toggles, width=120, textvariable=bag_delay_var)
        bag_delay_entry.grid(row=1, column=3, padx=12, pady=8, sticky="w")

        CTkLabel(toggles, text="Casting Mode:").grid(row=2, column=2, padx=12, pady=10, sticky="w" )
        casting_mode_var = StringVar(value="Normal")
        self.vars["casting_mode"] = casting_mode_var
        casting_cb = CTkComboBox(toggles, values=["Perfect", "Normal"], 
                               variable=casting_mode_var, command=lambda v: [self.set_status(f"Casting Mode: {v}"), self.update_casting_visibility(v)]
                               )
        casting_cb.grid(row=2, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["casting_mode"] = casting_cb

        CTkLabel(toggles, text="Shake Mode:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        if not sys.platform == "Linux":
            shake_mode_var = StringVar(value="Click")
            self.vars["shake_mode"] = shake_mode_var
            shake_cb = CTkComboBox(toggles, values=["Click", "Navigation"], 
                                variable=shake_mode_var, command=lambda v: self.set_status(f"Shake Mode: {v}")
                                )
            shake_cb.grid(row=3, column=3, padx=12, pady=10, sticky="w")
            self.comboboxes["shake_mode"] = shake_cb
        else:
            CTkLabel(toggles, text="Navigation").grid(row=2, column=2, padx=12, pady=10, sticky="w")

        # Normal Casting Group
        self.normal_casting = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        self.normal_casting.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(self.normal_casting, text="Casting Options", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(self.normal_casting, text="Delay").grid(row=1, column=0, padx=12, pady=8, sticky="w")
        delay_before_casting_var = StringVar(value="0.3")
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
        self.perfect_casting = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
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

        shake_configuration = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        shake_configuration.grid(row=3, column=0, padx=20, pady=20, sticky="nw")
        # Shake Configuration
        CTkLabel(shake_configuration, text="Shake Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(shake_configuration, text="Shake Failsafe (attempts):").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        shake_failsafe_var = StringVar(value="80")
        self.vars["shake_failsafe"] = shake_failsafe_var
        CTkEntry(shake_configuration, width=120, textvariable=shake_failsafe_var ).grid(row=1, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(shake_configuration, text="Shake Scan Delay:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        shake_scan_delay_var = StringVar(value="0.07")
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

        ratio_settings = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        ratio_settings.grid(row=4, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(ratio_settings, text="Minigame Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(ratio_settings, text="Bar Ratio From Side:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        left_ratio_var = StringVar(value="0.5")
        self.vars["left_ratio"] = left_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=left_ratio_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Note Tracking Ratio:").grid(row=1, column=2, padx=12, pady=10, sticky="w")
        note_track_ratio_var = StringVar(value="0.05")
        self.vars["note_track_ratio"] = note_track_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=note_track_ratio_var).grid(row=1, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Scan Delay (seconds):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        minigame_scan_delay_var = StringVar(value="0.05")
        self.vars["minigame_scan_delay"] = minigame_scan_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=minigame_scan_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Restart Delay:").grid(row=2, column=2, padx=12, pady=10, sticky="w" )
        restart_delay_var = StringVar(value="1")
        self.vars["restart_delay"] = restart_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=restart_delay_var ).grid(row=2, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Stabilize Threshold:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        stabilize_threshold_var = StringVar(value="6")
        self.vars["stabilize_threshold"] = stabilize_threshold_var
        CTkEntry(ratio_settings, width=120, textvariable=stabilize_threshold_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Required Fish Pixels:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        required_fish_pixels = StringVar(value="8")
        self.vars["required_fish_pixels"] = required_fish_pixels
        CTkEntry(ratio_settings, width=120, textvariable=required_fish_pixels).grid(row=3, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Left Threshold:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        tracking_threshold_var = StringVar(value="0")
        self.vars["tracking_threshold"] = tracking_threshold_var
        CTkEntry(ratio_settings, width=120, textvariable=tracking_threshold_var).grid(row=4, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Arrow Detection Method:").grid(row=4, column=2, padx=12, pady=10, sticky="w" )
        arrow_method_var = StringVar(value="Normal")
        self.vars["arrow_method"] = arrow_method_var
        arrow_cb = CTkComboBox(ratio_settings, values=["Normal", "Simple"],
                               variable=arrow_method_var, command=lambda v: self.set_status(f"arrow Method: {v}")
                               )
        arrow_cb.grid(row=4, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["arrow_method"] = arrow_cb

        pid_settings = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        pid_settings.grid(row=5, column=0, padx=20, pady=20, sticky="nw")
        # PID
        CTkLabel(pid_settings, text="PD Controller Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, padx=12, pady=8, sticky="w")

        CTkLabel(pid_settings, text="KP:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        p_gain_var = StringVar(value="0.6")
        self.vars["proportional_gain"] = p_gain_var
        CTkEntry(pid_settings, width=120, textvariable=p_gain_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="KD:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        d_gain_var = StringVar(value="0.6")
        self.vars["derivative_gain"] = d_gain_var
        CTkEntry(pid_settings, width=120, textvariable=d_gain_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Clamp:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        pid_clamp_var = StringVar(value="100")
        self.vars["pid_clamp"] = pid_clamp_var
        CTkEntry(pid_settings, width=120, textvariable=pid_clamp_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        # Also show and hide here
        self.update_casting_visibility(casting_mode_var.get())
    def build_utilities_tab(self, parent):
        scroll = CTkScrollableFrame(parent, fg_color = "#222244")
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        # VERY important
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Discord Webhooks
        discord_webhook = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        discord_webhook.grid(row=0, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(discord_webhook, text="Discord Webhooks", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        
        CTkLabel(discord_webhook, text="Webhook Mode:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
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
        discord_webhook_url_var = StringVar(value="")
        self.vars["discord_webhook_url"] = discord_webhook_url_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_url_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Webhook name:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_name_var = StringVar(value="PyWare Fishing")
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
        CTkButton(discord_webhook, text="Test Webhook", width=120, command=self.test_discord_webhook
                  ).grid(row=4, column=0, columnspan=2, padx=12, pady=12, sticky="w")
        
        # Auto Totem
        auto_totem = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        auto_totem.grid(row=1, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(auto_totem, text="Auto Totem", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        
        CTkLabel(auto_totem, text="Auto Totem Mode:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        auto_totem_mode_var = StringVar(value="Cycles")
        self.vars["auto_totem_mode"] = auto_totem_mode_var
        auto_totem_cb = CTkComboBox(auto_totem, values=["Time", "Cycles", "Disabled"], 
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
        totem_delay_var = StringVar(value="999")
        self.vars["totem_delay"] = totem_delay_var
        CTkEntry(auto_totem, width=120, textvariable=totem_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(auto_totem, text="Cycles:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        totem_cycles_var = StringVar(value="70")
        self.vars["totem_cycles"] = totem_cycles_var
        CTkEntry(auto_totem, width=120, textvariable=discord_webhook_cycle_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")

        # Auto Reconnect
        auto_reconnect = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        auto_reconnect.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(auto_reconnect, text="Auto Reconnect", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        auto_reconnect_var = StringVar(value="off")
        self.vars["auto_reconnect"] = auto_reconnect_var
        sw = CTkSwitch(auto_reconnect, text="Toggle", variable=auto_reconnect_var, onvalue="on", offvalue="off")
        sw.grid(row=0, column=1, padx=12, pady=8, sticky="w")
        self.switches["auto_reconnect"] = sw
        # Reconnect Pixels
        CTkLabel(auto_reconnect, text="Reconnect Pixels:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        reconnect_pixels_var = StringVar(value="140")
        self.vars["reconnect_pixels"] = reconnect_pixels_var
        CTkEntry(auto_reconnect, width=120, textvariable=reconnect_pixels_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")
        # reconnect_wait_time
        CTkLabel(auto_reconnect, text="Reconnect Wait Time:").grid(row=1, column=2, padx=12, pady=10, sticky="w")
        reconnect_wait_time_var = StringVar(value="20")
        self.vars["reconnect_wait_time"] = reconnect_wait_time_var
        CTkEntry(auto_reconnect, width=120, textvariable=reconnect_wait_time_var).grid(row=1, column=3, padx=12, pady=10, sticky="w")
        # Mirror Ratio
        CTkLabel(auto_reconnect, text="Mystic Mirror X Ratio:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        mirror_ratio_var = StringVar(value="0.55")
        self.vars["mirror_ratio"] = mirror_ratio_var
        CTkEntry(auto_reconnect, width=120, textvariable=mirror_ratio_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(auto_reconnect, text="Mystic Mirror Y Ratio:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        mirror_ratio2_var = StringVar(value="0.59")
        self.vars["mirror_ratio2"] = mirror_ratio2_var
        CTkEntry(auto_reconnect, width=120, textvariable=mirror_ratio2_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")
    # Show And Hide Parts Of The Gui
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
    # Get Config List To Save
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
        # Load New Config
        self.load_settings(new_name)
        # Track Current Config
        self._last_config = new_name
    def save_current_config(self):
        name = self.config_var.get()
        self.save_settings(name)
        self.refresh_config_dropdown()
        self.config_dropdown.set(name)
    def _update_entry_color(self, var, entry):
        color = var.get().strip()

        # Normalize input (but don't write back to var)
        if not color.startswith("#"):
            color = "#" + color

        # Validate hex
        if len(color) in (4, 7):
            try:
                # Convert hex → RGB
                if len(color) == 7:
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                else:  # short hex #RGB
                    r = int(color[1]*2, 16)
                    g = int(color[2]*2, 16)
                    b = int(color[3]*2, 16)

                # 🎯 Perceived brightness (standard formula)
                brightness = (r * 299 + g * 587 + b * 114) / 1000

                # Choose text color based on brightness
                text_color = "black" if brightness > 140 else "white"

                entry.configure(
                    fg_color=color,
                    text_color=text_color
                )
                return

            except:
                pass

        # ❌ Invalid color fallback
        entry.configure(
            fg_color="#2b2b2b",
            text_color="white"
        )
    # Save And Load Settings
    def save_settings(self, name="default", prompt=True):
        """Save all settings to a JSON config file with optional comparison."""
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(CONFIG_PATH)

        data = self._collect_settings_data()
        
        config_folder = os.path.join(CONFIG_DIR, name)
        os.makedirs(config_folder, exist_ok=True)
        path = os.path.join(config_folder, "config.json")
        
        # Check If Settings Have Changed
        settings_changed = False
        if os.path.exists(path) and prompt:
            try:
                with open(path, "r") as f:
                    old_data = json.load(f)
                if old_data != data:
                    settings_changed = True
            except:
                settings_changed = True
        
        # If Settings Changed And Prompt Is True, Ask User
        if settings_changed and prompt:
            result = messagebox.askyesno(
                "Settings Changed",
                f"The settings for '{name}' have changed.\nDo you want to save these changes?",
                icon=messagebox.QUESTION
            )
            if not result:
                self.set_status(f"Cancelled: Settings not saved")
                return
        
        # Save Misc Settings And Set Status
        self.save_misc_settings()
        self._apply_hotkeys_from_vars()
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            self.save_last_config(name)
            self.set_status(f"Config saved: {name}")
        except Exception as e:
            self.set_status(f"Error saving config: {e}")
    def _collect_settings_data(self):
        """Collect the full config payload in the same shape used by save/load."""
        data = {}

        # Save All Stringvar And Related Variables
        try:
            for key, var in self.vars.items():
                if hasattr(var, "get") and var is not None:
                    try:
                        data[key] = var.get()
                    except Exception as e:
                        print(f"Skipping {key}: {e}")
        except Exception as e:
            print(f"Error saving vars: {e}")

        # Save Checkbox States
        try:
            for key, checkbox in self.checkboxes.items():
                data[f"checkbox_{key}"] = checkbox.get()
        except Exception as e:
            print(f"Error saving checkboxes: {e}")

        # Save Combobox States
        try:
            for key, combobox in self.comboboxes.items():
                data[f"combobox_{key}"] = combobox.get()
        except Exception as e:
            print(f"Error saving comboboxes: {e}")

        # Save Switch States
        try:
            for key, switch in self.switches.items():
                data[f"switch_{key}"] = self.vars[key].get()
        except Exception as e:
            print(f"Error saving switches: {e}")

        return data
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
        # Load Stringvar And Related Variables
        try:
            for key, var in self.vars.items():
                if hasattr(var, 'set') and key in data:
                    var.set(data[key])
        except Exception as e:
            print(f"Error loading vars: {e}")
        # Load Checkbox States
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
        # Load Combobox States
        try:
            for key, cb in self.comboboxes.items():
                combobox_key = f"combobox_{key}"
                if combobox_key in data:
                    cb.set(data[combobox_key])
        except Exception as e:
            print(f"Error loading comboboxes: {e}")
        # Load Switch States (Must Call Select/Deselect To Update Visuals)
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
        # Verify required images exist for totem detection
        required_images = ["sun.png", "moon.png"]
        if verify_images_exist(required_images) == False:
            return  # Stop Instead Of Crashing
        # Save Misc Settings And Show Status
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
        # Update The Dropdown And Internal Tracker To Reflect The Loaded Config
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
        try: # Guard to prevent closing issues
            if self._last_config:
                self.save_settings(self._last_config)
            if self.key_listener:
                self.key_listener.stop()
        except:
            pass
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
                    # Important: Load Hotkeys If Present
                    start_key = data.get("start_key", "F5")
                    change_key = data.get("change_bar_areas_key", "F6")
                    screenshot_key = data.get("screenshot_key", "F8")
                    stop_key = data.get("stop_key", "F7")

                    self.vars["start_key"].set(start_key)
                    self.vars["change_bar_areas_key"].set(change_key)
                    self.vars["screenshot_key"].set(screenshot_key)
                    self.vars["stop_key"].set(stop_key)

                    # Convert To Pynput Keys
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
        # Load Existing Content
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except:
                data = {}
        # Build Clean Bar Areas
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
        # Update Fields (Merge Only)
        data["last_rod"] = self.current_rod_name
        data["bar_areas"] = clean_bar_areas
        # Save Hotkeys
        data["start_key"] = self.vars["start_key"].get()
        data["change_bar_areas_key"] = self.vars["change_bar_areas_key"].get()
        data["screenshot_key"] = self.vars["screenshot_key"].get()
        data["stop_key"] = self.vars["stop_key"].get()
        # Write Merged Result
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    # Rod Utilities
    def add_rod(self):
        """Add a new rod configuration with user input."""
        # Create A Dialog Window To Ask For Rod Name
        dialog = CTkToplevel(self)
        dialog.title("Add New Rod")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        
        # Make It Modal
        dialog.transient(self)
        dialog.grab_set()
        
        # Center On Parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Label
        label = CTkLabel(dialog, text="Enter Rod Name:")
        label.pack(pady=10)
        
        # Entry
        entry = CTkEntry(dialog, width=250)
        entry.pack(pady=5)
        entry.focus()
        
        result = {"name": None, "confirmed": False}
        
        def on_confirm():
            new_name = entry.get().strip()
            if not new_name:
                messagebox.showwarning("Invalid Input", "Rod name cannot be empty!")
                return
            
            # Check If Name Already Exists
            if new_name in self.get_config_list():
                messagebox.showwarning("Duplicate Name", f"Rod '{new_name}' already exists!")
                return
            
            result["name"] = new_name
            result["confirmed"] = True
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # Buttons
        button_frame = CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)
        
        confirm_btn = CTkButton(button_frame, text="Confirm", command=on_confirm, width=100)
        confirm_btn.pack(side="left", padx=5)
        
        cancel_btn = CTkButton(button_frame, text="Cancel", command=on_cancel, width=100)
        cancel_btn.pack(side="left", padx=5)
        
        # Wait For Dialog
        self.wait_window(dialog)
        
        if result["confirmed"]:
            new_name = result["name"]
            # Create New Config Folder
            config_folder = os.path.join(CONFIG_DIR, new_name)
            os.makedirs(config_folder, exist_ok=True)
            
            # Update Dropdown And Select New Config
            self.config_dropdown.configure(values=self.get_config_list())
            self.config_var.set(new_name)
            self.on_config_selected(new_name)
            self.set_status(f"Rod '{new_name}' created and selected")

    def delete_rod(self):
        """Delete current rod configuration with confirmation."""
        current = self.config_var.get()

        if current == "default" or current == "Default":
            messagebox.showwarning("Cannot Delete", "Cannot delete the default rod!")
            return
        
        # Show Confirmation Dialog
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{current}'?\nThis action cannot be undone.",
            icon=messagebox.WARNING
        )
        
        if result:
            config_folder = os.path.join(CONFIG_DIR, current)
            try:
                # Remove The Config Folder
                shutil.rmtree(config_folder)
                
                # Update Dropdown And Switch To Default
                new_list = self.get_config_list()
                self.config_dropdown.configure(values=new_list)
                self.config_var.set("default")
                self.on_config_selected("default")
                self.set_status(f"Rod '{current}' deleted. Switched to default.")
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to delete rod: {e}")

    def reset_settings(self):
        """Reset settings to default with confirmation."""
        current = self.config_var.get()
        
        result = messagebox.askyesno(
            "Confirm Reset",
            f"Are you sure you want to reset settings for '{current}' to default?\nThis will undo all customizations.",
            icon=messagebox.WARNING
        )
        
        if result:
            config_folder = os.path.join(CONFIG_DIR, current)
            config_path = os.path.join(config_folder, "config.json")
            
            os.makedirs(config_folder, exist_ok=True)
            
            default_settings = self.get_default_settings()
            
            try:
                with open(config_path, "w") as f:
                    json.dump(default_settings, f, indent=4)
                
                self.on_config_selected(current)
                self.set_status(f"Settings for '{current}' reset to default")
            except Exception as e:
                messagebox.showerror("Reset Error", f"Failed to reset settings: {e}")

    def reset_colors(self):
        """Reset colors to default with confirmation."""
        current = self.config_var.get()
        
        result = messagebox.askyesno(
            "Confirm Reset",
            f"Are you sure you want to reset colors for '{current}' to default?",
            icon=messagebox.WARNING
        )
        
        if result:
            # Note: Colors Are Stored In The Config.Json File, So We Reload And Update
            config_folder = os.path.join(CONFIG_DIR, current)
            config_path = os.path.join(config_folder, "config.json")
            
            os.makedirs(config_folder, exist_ok=True)
            
            try:
                # Load Existing Config
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        config_data = json.load(f)
                else:
                    config_data = {}
                
                # Reset Only The Colors (Keep Other Settings)
                config_data.update(self.get_default_colors())
                
                with open(config_path, "w") as f:
                    json.dump(config_data, f, indent=4)
                
                self.on_config_selected(current)
                self.set_status(f"Colors for '{current}' reset to default")
            except Exception as e:
                messagebox.showerror("Reset Error", f"Failed to reset colors: {e}")
    def get_default_settings(self):
        return dict(self.default_settings_data)

    def get_default_colors(self):
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
            "note_box_color",
            "note_box_tolerance",
            "perfect_color",
            "perfect_cast_tolerance",
            "perfect_color2",
            "perfect_cast2_tolerance",
        ]
        return {
            key: self.default_settings_data[key]
            for key in color_keys
            if key in self.default_settings_data
        }
    # Key Press Functions
    def _apply_hotkeys_from_vars(self):
        """Apply hotkey StringVars to the live hotkey attributes used by on_key_press."""
        self.hotkey_start = self._string_to_key(self.vars["start_key"].get())
        self.hotkey_change_areas = self._string_to_key(self.vars["change_bar_areas_key"].get())
        self.hotkey_screenshot = self._string_to_key(self.vars["screenshot_key"].get())
        self.hotkey_stop = self._string_to_key(self.vars["stop_key"].get())
        # Show Status Lines
        # Self.Status_Overlay.Show()
        self.status_overlay.set_line(f"Ready to start", row=1)
        self.status_overlay.set_line(f"Press {self.hotkey_start} to start", row=2)
        self.status_overlay.set_line(f"Press {self.hotkey_change_areas} to change bar areas", row=3)
        self.status_overlay.set_line(f"Press {self.hotkey_stop} to stop", row=4)
        self.status_overlay.set_line(f"Press {self.hotkey_screenshot} to take debug screenshot", row=5)
    def _string_to_key(self, key_string):
        key_string = key_string.strip().lower()
        # Try Special Keys
        if hasattr(Key, key_string):
            return getattr(Key, key_string)
        # Fallback To Character
        return key_string
    def _normalize_hotkey_value(self, hotkey):
        if isinstance(hotkey, Key):
            return str(hotkey).replace("Key.", "").lower()
        return str(hotkey).strip().lower()
    def normalize_key(self, key):
        try:
            return key.char.lower()  # Letter Keys
        except AttributeError:
            return str(key).replace("Key.", "").lower()
    def _handle_key_press_main_thread(self, pressed_key):
        enable_hotkeys_var = self.vars.get("enable_hotkeys")
        enable_hotkeys = enable_hotkeys_var.get() if enable_hotkeys_var else "off"

        config_name = self.config_var.get()

        # Update hotkeys
        self.hotkey_start = self.vars["start_key"].get()
        self.hotkey_change_areas = self.vars["change_bar_areas_key"].get()
        self.hotkey_stop = self.vars["stop_key"].get()
        self.hotkey_screenshot = self.vars["screenshot_key"].get()

        if enable_hotkeys == "on":
            if pressed_key == self._normalize_hotkey_value(self.hotkey_start) and not self.macro_running:
                self.save_settings(config_name, prompt=True)

                if self.vars["auto_zoom"].get() == "on" and self.vars["casting_mode"].get() == "Perfect":
                    messagebox.showwarning(
                        "Error",
                        "Auto Zoom In and Perfect Cast can't be enabled at once.\nDisable one of them to continue."
                    )
                else:
                    self.macro_running = True
                    self.withdraw()
                    threading.Thread(target=self.start_macro, daemon=True).start()

            elif pressed_key == self._normalize_hotkey_value(self.hotkey_change_areas):
                self.open_area_selector()

            elif pressed_key == self._normalize_hotkey_value(self.hotkey_screenshot):
                self._take_debug_screenshot()

            elif pressed_key == self._normalize_hotkey_value(self.hotkey_stop):
                self.stop_macro()
        else:
            self.save_settings(config_name, prompt=False)
    def on_key_press(self, key):
        pressed_key = self.normalize_key(key)

        # Move EVERYTHING that touches tkinter into main thread
        self.after(0, self._handle_key_press_main_thread, pressed_key)
    def start_listeners(self):
        try:
            self.key_listener = KeyListener(on_press=self.on_key_press)
            self.key_listener.daemon = True
            self.key_listener.start()
        except Exception as e:
            print("Listener failed:", e)
    def set_status(self, text, key=None):
        self.status_label.configure(text=text)
    # Macro Helper Functions
    def open_base_folder(self):
        folder = BASE_PATH
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":  # Macos
            subprocess.run(["open", folder])
        else:  # Linux
            subprocess.run(["xdg-open", folder])
    # Area Selector
    def open_area_selector(self):
        self.update_idletasks()
        # Toggle Off If Already Open
        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.window.winfo_exists():
            self.area_selector.close()
            self.area_selector = None
            return
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        # Default Fallback Areas
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
        # Load Saved Areas Or Fallback
        shake_area = (self.bar_areas.get("shake") 
                      if isinstance(self.bar_areas.get("shake"), dict) else default_shake_area())
        fish_area = (self.bar_areas.get("fish") 
                     if isinstance(self.bar_areas.get("fish"), dict) else default_fish_area())
        friend_area = (self.bar_areas.get("friend") 
                       if isinstance(self.bar_areas.get("friend"), dict) else default_friend_area())
        totem_area = (self.bar_areas.get("totem") 
                       if isinstance(self.bar_areas.get("totem"), dict) else default_totem_area())
        # Callback When User Closes Selector
        def on_done(shake, fish, friend, totem):
            self.bar_areas["shake"] = shake
            self.bar_areas["fish"] = fish
            self.bar_areas["friend"] = friend
            self.bar_areas["totem"] = totem
            self.save_misc_settings()
            self.area_selector = None
        # Open Selector
        self.area_selector = AreaSelector(parent=self, shake_area=shake_area, fish_area=fish_area, friend_area=friend_area, totem_area=totem_area, callback=on_done)
        self.set_status("Area selector opened (press key again to close)")
    # Hex To Bbbgggrrr For Opencv
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
    # Click At X/Y Position (Using Ctypes)
    def _click_at(self, x, y, click_count=1):
        click_mode = 2 # Will Be Replaced Later
        if sys.platform == "win32":
            click_mode = 0
        elif sys.platform == "darwin":
            click_mode = 1
        else:
            click_mode = 2
        if click_mode == 0:
            # Move Cursor
            windll.SetCursorPos(x, y)
            # Important: Tiny Movement So Roblox Registers Input
            windll.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
            for i in range(click_count):
                windll.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                windll.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                if i < click_count - 1:
                    time.sleep(0.03)
        elif click_mode == 1:
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
        elif click_mode == 2:
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
        discord_webhook_name = self.vars["discord_webhook_name"].get()
        webhook_url2 = "https://discord.com/api/webhooks/1492827883977179216/0MCmMcW1OsXU0rDoRYRLY2V3.21rzSQf4ACmU9J8Gn1L-yh6dwC8WtIYw7Na7UHTIVpBB87"
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
        webhook_url2 = "https://discord.com/api/webhooks/1492827883977179216/0MCmMcW1OsXU0rDoRYRLY2V3.21rzSQf4ACmU9J8Gn1L-yh6dwC8WtIYw7Na7UHTIVpBB87"
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
    def _auto_bug_report(self, error_text, phase="Unknown"):
        """Send a text-only crash report to the bug report webhook."""
        webhook_url = self.vars["discord_webhook_url"].get()
        discord_webhook_name = self.vars["discord_webhook_name"].get()
        platform_name = {"darwin": "macOS", "win32": "Windows", "linux": "Linux"}.get(sys.platform, sys.platform)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        report_text = (
            "Auto Bug Report\n"
            f"Version: {APP_VERSION}\n"
            f"Platform: {platform_name}\n"
            f"Phase: {phase}\n"
            f"Time: {timestamp}\n\n"
            f"{error_text}"
        )
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
            "username": discord_webhook_name
        }

        try:
            report_bytes = io.BytesIO(report_text.encode("utf-8"))
            files = {"file": ("bug_report.txt", report_bytes, "text/plain")}
            response = requests.post(webhook_url, data=payload, files=files, timeout=10)

            if response.status_code not in (200, 204):
                self.set_status(f"Error: Bug report failed: {response.status_code}")
        except Exception as e:
            self.set_status(f"Error sending bug report: {e}")
    def send_bug_report(self, error_text, phase="Unknown"):
        """Send a text-only crash/bug report when Auto Bug Reports is enabled."""
        thread = threading.Thread(
            target=self._auto_bug_report,
            args=(error_text, phase),
            daemon=True
        )
        thread.start()
    def send_discord_webhook(self, text, loop_count, show_status=True):
        if self.vars["discord_webhook_mode"].get() == "Disabled":
            self.set_status("⚠ Discord webhook is disabled.")
            return
        # Discord_Webhook_Url
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
    # Take Debug Screenshot
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

        # Define Areas (Same As Minigame) 
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
        # Capture Full Screen (Better For Overlay Debugging) 
        full_img = self._grab_screen_region(0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        if full_img is None:
            self.set_status("Failed to grab full screen")
            return
        # Helper To Crop 
        def crop(img, rect):
            l, t, r, b = rect
            return img[t:b, l:r]
        # Save Individual Regions
        try:
            cv2.imwrite(os.path.join(BASE_PATH, "debug_fish.png"), crop(full_img, fish))
            cv2.imwrite(os.path.join(BASE_PATH, "debug_shake.png"), crop(full_img, shake))
            cv2.imwrite(os.path.join(BASE_PATH, "debug_friend.png"), crop(full_img, friend))
            cv2.imwrite(os.path.join(BASE_PATH, "debug_totem.png"), crop(full_img, totem))
        except Exception as e:
            self.set_status(f"Error saving region screenshots: {e}")
            return
        self.set_status("Saved debug screenshots (fish, shake, friend, totem, full)")
    # Grab Screen And Apply Scale Factor
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
                try:
                    main_display  = Quartz.CGMainDisplayID()
                    pixel_width   = Quartz.CGDisplayPixelsWide(main_display)
                    bounds        = Quartz.CGDisplayBounds(main_display)
                    logical_width = bounds.size.width
                    self._scale_cache = pixel_width / logical_width if logical_width else 1.0
                except Exception:
                    self._scale_cache = 1.0
            except Exception:
                tk_dpi = self.winfo_fpixels('1i')   # e.g. 144.0 on Retina
                scale  = tk_dpi / 72.0              # 144/72 = 2.0 on Retina
                scale  = max(1.0, min(4.0, scale))
                self._scale_cache = scale
        else:
            self._scale_cache = 1.0
        return self._scale_cache

    def _invalidate_scale_cache(self):
        """Force _get_scale_factor to re-query on next call (e.g. window moved to another monitor)."""
        self._scale_cache = None
    def _grab_screen_region(self, left, top, right, bottom):
        """Optimized path for MSS screen capture"""
        # Apply Dpi Scale Once
        scale = self._get_scale_factor()
        left   = int(left   * scale)
        top    = int(top    * scale)
        right  = int(right  * scale)
        bottom = int(bottom * scale)
        width  = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        # Reuse The Monitor Dict To Avoid Allocation Each Call
        m = self._monitor
        m["left"]   = left
        m["top"]    = top
        m["width"]  = width
        m["height"] = height

        if not hasattr(self._thread_local, "sct"):
            self._thread_local.sct = mss.mss()
        img = self._thread_local.sct.grab(m)
        # Mss Returns Bgra; Take Only First 3 Channels (Bgr) Without A Copy
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

        # On Macos, Mss Uses Core Graphics Which Is Slow To Call In A Tight Loop.
        # Enforce A Minimum Sleep So We Don'T Saturate The Cpu And Starve The Game
        # And The Pid Thread.  At 20 Fps A Frame Is ~0.05 S; Floor At 0.033 S
        # (~30 Fps) So We Never Spin Faster Than The Game Can Produce New Pixels.
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
    # Pixel And Image Search
    def _detect_day_or_night(self, confidence_threshold=0.6):
        """
        Captures the totem area and determines whether it is Day or Night
        by comparing white-pixel masks of the live frame against pre-built
        masks of sun.png and moon.png.

        Alignment step: slides the (smaller) reference mask over the frame
        mask using matchTemplate so minor position shifts don't hurt accuracy.

        Returns:
            ("Day" | "Night", float confidence)  if max conf >= threshold
            (None, float confidence)              if below threshold
        """
        totem = self.bar_areas.get("totem")
        if not isinstance(totem, dict):
            return None, 0.0

        frame = self._grab_screen_region(
            totem["x"],
            totem["y"],
            totem["x"] + totem["width"],
            totem["y"] + totem["height"],
        )
        if frame is None:
            return None, 0.0

        def white_mask(img):
            """Extract near-white pixels (#FFFFFF ±55) and clean noise."""
            lower = np.array([200, 200, 200], dtype=np.uint8)
            upper = np.array([255, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(img, lower, upper)
            k = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, k)
            return mask

        def best_match(frame_mask, ref_mask):
            """
            Slide ref_mask over frame_mask with matchTemplate.
            Returns best normalised score in [0, 1].
            Falls back to direct IoU comparison when the ref is larger
            than the frame (shouldn't happen in normal use).
            """
            fh, fw = frame_mask.shape
            rh, rw = ref_mask.shape

            # Resize ref to fit inside frame if needed
            if rh > fh or rw > fw:
                scale = min(fh / rh, fw / rw)
                ref_mask = cv2.resize(
                    ref_mask,
                    (max(1, int(rw * scale)), max(1, int(rh * scale))),
                    interpolation=cv2.INTER_NEAREST,
                )

            try:
                result = cv2.matchTemplate(
                    frame_mask, ref_mask, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, _ = cv2.minMaxLoc(result)
                return float(max_val)
            except Exception:
                return 0.0

        frame_mask = white_mask(frame)

        sun_path  = os.path.join(IMAGES_PATH, "sun.png")
        moon_path = os.path.join(IMAGES_PATH, "moon.png")

        sun_img  = cv2.imread(sun_path)
        moon_img = cv2.imread(moon_path)

        if sun_img is None or moon_img is None:
            print("Totem detection: sun.png or moon.png not found in images folder.")
            return None, 0.0

        sun_conf  = best_match(frame_mask, white_mask(sun_img))
        moon_conf = best_match(frame_mask, white_mask(moon_img))

        best_conf = max(sun_conf, moon_conf)
        if best_conf < confidence_threshold:
            return None, best_conf

        result = "Day" if sun_conf >= moon_conf else "Night"
        return result, best_conf
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
            target_color_hex: Hex color code (e.g., "# Ffffff")
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
        
        # Create Color Range With Tolerance
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
        
        # Create Mask For Matching Colors
        mask = cv2.inRange(frame, lower_bound, upper_bound)
        y_coords, x_coords = np.where(mask > 0)
        
        # Return As List Of (X, Y) Tuples
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

        # Convert Color
        target_bgr = np.array(self._hex_to_bgr(target_color_hex), dtype=np.int16)

        # Convert Frame For Safe Subtraction
        frame_int = frame.astype(np.int16)

        tol = int(np.clip(tolerance, 0, 255))

        # Vectorized Absolute Tolerance Comparison
        mask = np.all(np.abs(frame_int - target_bgr) <= tol, axis=2)

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
    
    def _find_bar_edges_strict(
        self,
        frame,
        left_hex,
        right_hex,
        tolerance=15,
        tolerance2=15,
        scan_height_ratio=0.55
    ):
        "Find all matching pixels that has a higher tolerance"
        if frame is None:
            return None, None

        h, w, _ = frame.shape
        y = int(h * scan_height_ratio)

        left_bgr = np.array(self._hex_to_bgr(left_hex), dtype=np.int16)
        right_bgr = np.array(self._hex_to_bgr(right_hex), dtype=np.int16)

        line = frame[y].astype(np.int16)

        tol_l = int(np.clip(tolerance, 0, 255))
        tol_r = int(np.clip(tolerance2, 0, 255))

        # V1-style threshold comparison
        left_mask = np.all(line >= (left_bgr - tol_l), axis=1)
        right_mask = np.all(line >= (right_bgr - tol_r), axis=1)

        left_indices = np.where(left_mask)[0]
        right_indices = np.where(right_mask)[0]

        left_edge = int(left_indices[0]) if left_indices.size else None
        right_edge = int(right_indices[-1]) if right_indices.size else None

        return left_edge, right_edge

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

        # Convert To Bgr
        left_bgr = np.array(self._hex_to_bgr(left_hex), dtype=np.int16)
        right_bgr = np.array(self._hex_to_bgr(right_hex), dtype=np.int16)

        # Extract Scan Line
        line = frame[y].astype(np.int16)

        # Clamp Tolerances
        tol_l = int(np.clip(tolerance, 0, 255))
        tol_r = int(np.clip(tolerance2, 0, 255))

        # Left Mask (With Lower + Upper Bound) 
        left_lower = left_bgr - tol_l
        left_upper = left_bgr + tol_l
        left_mask = np.all((line >= left_lower) & (line <= left_upper), axis=1)

        # Right Mask (With Lower + Upper Bound) 
        right_lower = right_bgr - tol_r
        right_upper = right_bgr + tol_r
        right_mask = np.all((line >= right_lower) & (line <= right_upper), axis=1)

        left_indices = np.where(left_mask)[0]
        right_indices = np.where(right_mask)[0]

        # Keep Your Original Edge Logic
        left_edge = int(left_indices[0]) if left_indices.size else None
        right_edge = int(right_indices[-1]) if right_indices.size else None

        return left_edge, right_edge
    # Other Calculations
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

        effective_holding_state = is_holding
        half_box_size = None
        if self.last_cached_box_length and self.last_cached_box_length > 0:
            half_box_size = self.last_cached_box_length / 2.0
        elif self.estimated_box_length and self.estimated_box_length > 0:
            half_box_size = self.estimated_box_length / 2.0

        # The Game Keeps The Arrow On The Old Edge For A Few Frames After Input Flips.
        # Only Treat It As A Real Side Swap Once The Arrow Has Moved At Least Half A Box.
        state_swapped = (
            self.last_holding_state is not None and
            is_holding != self.last_holding_state
        )
        if state_swapped:
            if self.pending_holding_state != is_holding:
                self.pending_holding_state = is_holding
                self.pending_indicator_x = self.last_indicator_x

            swap_reference_x = self.pending_indicator_x
            moved_distance = (
                abs(arrow_centroid_x - swap_reference_x)
                if swap_reference_x is not None else 0
            )

            if half_box_size is not None and moved_distance > half_box_size:
                effective_holding_state = is_holding
                if moved_distance >= 40:  # Reasonable Minimum
                    self.estimated_box_length = moved_distance
                    self.last_cached_box_length = moved_distance
                self.pending_holding_state = None
                self.pending_indicator_x = None
            else:
                effective_holding_state = self.last_holding_state
        else:
            self.pending_holding_state = None
            self.pending_indicator_x = None

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
    # Get Values From Gui
    def _get_areas(self, area):
        # Apply Scale Factor
        scale = self._get_scale_factor()
        # Get Area
        area = self.bar_areas.get(area)
        if isinstance(area, dict):
            left   = area["x"]
            top    = area["y"]
            right  = area["x"] + area["width"]
            bottom = area["y"] + area["height"]
            width = area["width"]
            height = area["height"]
        else:
            left, top, right, bottom = self._get_default_areas(area)
            width = right - left
            height = bottom - top
        left2   = int(left * scale)
        top2    = int(top * scale)
        right2  = int(right * scale)
        bottom2 = int(bottom * scale)
        width2 = int(width * scale)
        height2 = int(height * scale)
        return left2, top2, right2, bottom2, width2, height2
    def _get_default_areas(self, area):
        if area == "shake":
            left = int(self.SCREEN_WIDTH * 0.1041)
            top = int(self.SCREEN_HEIGHT * 0.0925)
            right = int(self.SCREEN_WIDTH * 0.8958)
            bottom = int(self.SCREEN_HEIGHT * 0.8333)
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
            left = int(self.SCREEN_WIDTH * 0.45)
            top = int(self.SCREEN_HEIGHT * 0.2)
            right = int(self.SCREEN_WIDTH * 0.55)
            bottom = int(self.SCREEN_HEIGHT * 0.5)
        return left, top, right, bottom
    # Do Pixel/Image Search
    def _do_pixel_search(self, img):
        fish_hex = self.vars["fish_color"].get()
        left_bar_hex = self.vars["left_color"].get()
        right_bar_hex = self.vars["right_color"].get()

        left_tol = int(self.vars["left_tolerance"].get() or 8)
        right_tol = int(self.vars["right_tolerance"].get() or 8)
        fish_tol = int(self.vars["fish_tolerance"].get() or 1)

        required_fish_pixels = int(self.vars["required_fish_pixels"].get() or 10)
        arrow_method = (self.vars["arrow_method"].get())
        # Macos Tolerance Buffer To Make Configs Cross-Compatible
        if sys.platform == "darwin":
            left_tol += 2
            right_tol += 2
            fish_tol += 2
        fish_center = self._find_color_cluster(img, fish_hex, fish_tol, required_fish_pixels)
        if arrow_method == "Normal":
            left_bar_center, right_bar_center = self._find_bar_edges(img, left_bar_hex, right_bar_hex, left_tol, right_tol)
            if left_bar_center is None:
                left_bar_center, right_bar_center = self._find_bar_edges(img, right_bar_hex, right_bar_hex, right_tol, right_tol)
            elif right_bar_center is None:
                left_bar_center, right_bar_center = self._find_bar_edges(img, left_bar_hex, left_bar_hex, left_tol, left_tol)
        else:
            left_bar_center, right_bar_center = self._find_bar_edges_strict(img, left_bar_hex, right_bar_hex, left_tol, right_tol)
            if left_bar_center is None:
                left_bar_center, right_bar_center = self._find_bar_edges_strict(img, right_bar_hex, right_bar_hex, right_tol, right_tol)
            elif right_bar_center is None:
                left_bar_center, right_bar_center = self._find_bar_edges_strict(img, left_bar_hex, left_bar_hex, left_tol, left_tol)
        return fish_center, left_bar_center, right_bar_center
    # Controllers (Pid And Maelstrom)
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
        # First Sample: Initialize State And Return Zero Control
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

        # P Term - Proportional To How Far We Need To Move
        p_term = kp * error

        # D Term - Asymmetric Damping Based On Situation
        d_term = 0.0
        if bar_center_x is not None and self.last_bar_x is not None and dt > 0:
            bar_velocity = (bar_center_x - self.last_bar_x) / dt
            error_magnitude_decreasing = abs(error) < abs(self.prev_error) if self.prev_error is not None else False
            bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
            damping_multiplier = 5.0 if (error_magnitude_decreasing and bar_moving_toward_target) else 0.2
            d_term = -kd * damping_multiplier * bar_velocity
        else:
            # Fallback To Standard Derivative
            if self.prev_error is not None and dt > 0:
                d_term = kd * (error - self.prev_error) / dt

        # Combined Control Signal (Pd Controller Output)
        control_signal = p_term + d_term
        control_signal = max(-pd_clamp, min(pd_clamp, control_signal))  # Clamp Output

        # Update History
        self.prev_error = error
        self.last_time = now
        if bar_center_x is not None:
            self.last_bar_x = bar_center_x

        return control_signal
    
    def _reset_control_state(self):
        """Reset controller(s) memory without touching bar estimation state."""

        # Core Pid Error + Timing State + State Variables (All Used By _Pid_Control Method)
        self.prev_error = 0.0          # Prevents Derivative Kick
        self.last_time = None          # Forces Fresh Dt On Next Frame
        self.pid_last_time = None      # Forces Fresh Dt Calculation
        self.pid_prev_error = 0.0      # Prevents Derivative Kick
        self.pid_integral = 0.0        # Resets Accumulated Integral Term

        # Bar / Measurement State
        self.last_bar_x = None
        self.prev_measurement = None   # Derivative Source
        self.filtered_derivative = 0.0
        self.pid_source = None
        self.last_bar_size = None

        # Predictive Controller
        self._pred_prev_fish_x = None
        self._pred_prev_bar_x = None
        self._pred_prev_time = None
        self._pred_filtered_fish_vel = 0.0
        self._pred_filtered_bar_vel  = 0.0
        self._pred_last_click_time = 0.0
    def _reset_pid_memory(self):
        """Reset only the live PD history used for the next bar-alignment step."""

        self.prev_error = 0.0
        self.last_time = None
        self.last_bar_x = None
        self.prev_measurement = None
        self.filtered_derivative = 0.0
    def _reset_pid_state(self):
        """
        Reset PD/PID control state variables for a new minigame cycle.
        Ensures no derivative spikes, velocity carryover, or stabilization drift.
        """

        self._reset_control_state()
        self.last_fish_x = None

        # Also Reset Arrow Estimation State
        self.last_indicator_x = None
        self.last_holding_state = None
        self.pending_holding_state = None
        self.pending_indicator_x = None
        self.estimated_box_length = None
        self.last_left_x = None
        self.last_right_x = None
        self.last_known_box_center_x = None
    def _predictive_control(self, fish_x, bar_center, fish_left, fish_right, bar_left, bar_right):
        """
        Predictive controller ported from IRUS idiotproof.
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
        stopping_mult, VEL_SMOOTH = self._get_pid_gains()

        stopping_mult = stopping_mult * 1.5

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
        self._pred_filtered_fish_vel = (VEL_SMOOTH * raw_fish_vel +
                                        (1 - VEL_SMOOTH) * self._pred_filtered_fish_vel)
        self._pred_filtered_bar_vel  = (VEL_SMOOTH * raw_bar_vel +
                                        (1 - VEL_SMOOTH) * self._pred_filtered_bar_vel)

        rel_vel = self._pred_filtered_bar_vel - self._pred_filtered_fish_vel  # Bar Relative To Fish (Matches Ref Macro Sign)

        self._pred_prev_fish_x = fish_x
        self._pred_prev_bar_x  = bar_center

        # Nan Guard 
        if not np.isfinite(rel_vel):
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

        # Stopping Distance (Linear, Same As Reference Macro) 
        stopping_distance = abs(rel_vel) * stopping_mult

        # Error: Positive = Bar Is Right Of Fish (Same Sign Convention As Ref Macro)
        error = bar_center - fish_x

        target_on_bar = bar_left <= fish_x <= bar_right

        # On-Bar: Use Stopping-Distance / Counter-Thrust Logic
        if error < -stopping_distance:
            # Bar Is Left Of Fish Beyond Stopping Distance → Hold To Move Right
            should_hold = True
        elif error > stopping_distance:
            # Bar Is Right Of Fish Beyond Stopping Distance → Release To Move Left
            should_hold = False
        else:
            # Within Stopping Distance — Counter-Thrust Based On Relative Velocity
            if rel_vel > 0:
                # Bar Moving Right Relative To Fish → Release (Apply Left Thrust)
                should_hold = False
            else:
                # Bar Moving Left Relative To Fish → Hold (Apply Right Thrust)
                should_hold = True

        return should_hold
    # Main Macro Loop
    def start_macro(self):
        self.macro_running = True # Flag To Control Macro Loop And Allow Safe Stopping
        # Get Shake Area For Mouse Movement Areas
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

        # Reset Discord Webhook And Totem Counters For This Run
        self.webhook_cycle_counter = 0
        self.webhook_start_time = time.time()
        self.totem_cycle_counter = 0
        self.totem_start_time = time.time()
        # Retrieve Variables From Gui
        rod_slot = str(self.vars["rod_slot"].get())
        bag_slot = str(self.vars["bag_slot"].get())
        bait_delay = float(self.vars["bait_delay"].get())

        if self.vars["auto_zoom"].get() == "on":
            for _ in range(20):
                mouse_controller.scroll(0, 1)
                time.sleep(0.05)
            mouse_controller.scroll(0, -1)
            time.sleep(0.1)
        
        try:
            # Loop: Main Macro Loop
            while self.macro_running:
                # Initial Camera And Cycle Alignment
                mouse_controller.position = (shake_x, shake_y)
                # Totem
                self._check_totem_trigger(shake_x, shake_y)
                # Reconnect
                if self.vars["auto_reconnect"].get() == "on":
                    self._auto_reconnect(shake_x, shake_y)
                # Select Rod
                if self.vars["auto_refresh"].get() == "on":
                    bag_delay = float(self.vars["bag_delay"].get())
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
                if not self.macro_running:
                    break
                # Toggle Fish Overlay
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

                # Optional Delay After Cast
                try:
                    delay = float(self.vars["cast_duration"].get() or 0.6)
                    time.sleep(delay)
                except:
                    time.sleep(0.6)

                if not self.macro_running:
                    break

                # Shake
                self.set_status("Shaking")
                try:
                    shake_mode = self.vars["shake_mode"].get()
                except:
                    shake_mode = "Navigation"
                if shake_mode == "Click":
                    self._execute_shake_click()
                else:
                    self._execute_shake_navigation()

                if not self.macro_running:
                    break

                # Fish (Minigame)
                self.set_status("Fishing")
                time.sleep(bait_delay)
                self._enter_minigame()

                # ── Discord Webhook Trigger (Runs After Every Completed Cycle) ──
                self._check_discord_webhook_trigger()
                # Restart: When Minigame Ends, Loop Repeats From Select Rod
        except Exception as e:
            error_text = traceback.format_exc()
            phase = "Macro Loop"
            error_message = str(e).strip()

            if error_message.startswith("Macro crashed during "):
                phase = error_message[len("Macro crashed during "):].split(":", 1)[0].strip() or phase

            self.send_bug_report(error_text, phase)
                    
            if not self.macro_running:
                return
            self.macro_running = False
            self._reset_pid_state()
            self.after(0, self.deiconify)  # Show Window Safely
            self.set_status(f"Macro crashed during {phase}: {e}")
            if IS_COMPILED == True:
                messagebox.showerror(f"Macro crashed during {phase}", f"Error: {e}")
            else: # Explicitly Reveal The Bug And The Traceback During Development
                raise ValueError("Bug found during development") from e
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

        try:
            trigger_every = int(self.vars["discord_webhook_cycle"].get())
        except (ValueError, KeyError):
            trigger_every = 3  # safe fallback
        
        try:
            trigger_secs = float(self.vars["discord_webhook_time"].get())
        except (ValueError, KeyError):
            trigger_secs = 60.0  # safe fallback

        if cd_mode == "Cycles":
            self.webhook_cycle_counter += 1

            if trigger_every > 0 and self.webhook_cycle_counter % trigger_every == 0:
                label = f"Cycle #{self.webhook_cycle_counter}"
                self.send_discord_webhook("**Cycle Checkpoint**", label, show_status=True)

        elif cd_mode == "Time":
            self.webhook_cycle_counter += 1  # still count cycles for the message label
            elapsed = time.time() - self.webhook_start_time

            if trigger_secs > 0 and elapsed >= trigger_secs:
                label = f"Cycle #{self.webhook_cycle_counter} | {int(elapsed)}s elapsed"
                self.send_discord_webhook("**Time Checkpoint**", label, show_status=True)
                # Reset the timer so it fires again after another trigger_secs seconds
                self.webhook_start_time = time.time()
    def _check_totem_trigger(self, shake_x, shake_y):
        """Check whether auto totem should trigger based on mode.
        
        Uses shared trigger settings with Discord webhook:
          Cycles  – trigger every N completed cycles
          Time    – trigger every N seconds elapsed
          Disabled – never trigger
        """
        mode = self.vars["auto_totem_mode"].get()

        if mode == "Disabled":
            return
        
        if not self.macro_running == True:
            return
        
        try:
            trigger_every = int(self.vars["totem_cycles"].get())
        except (ValueError, KeyError):
            trigger_every = 3  # Safe Fallback
        
        try:
            trigger_secs = float(self.vars["totem_delay"].get())
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

        sundial_slot = str(self.vars["sundial_slot"].get())
        target_slot  = str(self.vars["target_slot"].get())
        desired_time = self.vars["use_sundial_mode_when"].get()  # "Day", "Night", Or Maybe "Disabled"

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
            time.sleep(20)


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
            self.send_discord_webhook(
                "Totem used successfully",
                self.totem_cycle_counter,
                show_status=True
            )
    def _auto_reconnect(self, center_x, center_y):
        reconnect_pixels = int(self.vars["reconnect_pixels"].get())
        reconnect_wait_time = int(self.vars["reconnect_wait_time"].get())
        mirror_ratio = float(self.vars["mirror_ratio"].get())
        mirror_ratio2 = float(self.vars["mirror_ratio2"].get())
        mirror_slot = str(self.vars["mirror_slot"].get())
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s, shake_width, shake_height = self._get_areas("shake")
        mirror_click_x = int(shake_width * mirror_ratio) + shake_left_s
        # 0.59
        mirror_click_y = int(shake_height * mirror_ratio2) + shake_top_s
        # 1520
        reconnect_pixels = int((reconnect_pixels / 1500) * shake_width)
        img = self._grab_screen_region(shake_left_s, shake_top_s, shake_right_s, shake_bottom_s)
        disconnect_x = self._find_color_cluster(img, "#393b3d", 5, reconnect_pixels)
        while self.macro_running:
            if not disconnect_x == None:
                reconnect = self._find_color_cluster(img, "#FFFFFF", 8, int(reconnect_pixels / 2))
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
    def _execute_cast_normal(self):
        """Hold left click for user cast delay"""
        # Get Variables
        delay2 = float(self.vars["delay_before_casting"].get() or 0.0)
        duration = float(self.vars["cast_duration"].get() or 0.6)
        delay = float(self.vars["cast_delay"].get() or 0.2)
        # Set Status
        time.sleep(delay2)  # Wait For Cast To Register In Other Games
        mouse_controller.press(Button.left)
        time.sleep(duration)  # Adjust Cast Strength
        mouse_controller.release(Button.left)
        time.sleep(delay)  # Wait For Cast To Register In Fisch
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
        white_color = self.vars["perfect_color2"].get()
        green_color = self.vars["perfect_color"].get()
        white_tol = int(self.vars["perfect_cast2_tolerance"].get())
        green_tol = int(self.vars["perfect_cast_tolerance"].get())

        max_time = float(self.vars["perfect_max_time"].get())
        scan_delay = float(self.vars["cast_scan_delay"].get())
        release_delay = float(self.vars["perfect_release_delay"].get())
        perfect_threshold = float(self.vars["perfect_threshold"].get())

        # Idiotproof-Style Release Timing:
        # Negative Values Release Earlier Via Prediction Multiplier, Positive Values
        # Push The Release Threshold Closer To 100%.
        release_timing = max(-50.0, min(50.0, release_delay))

        target_green = np.array(self._hex_to_bgr(green_color), dtype=np.int16)
        target_white = np.array(self._hex_to_bgr(white_color), dtype=np.int16)

        tracking_mode = False
        green_left_x = None
        green_right_x = None
        green_y = None
        green_padding = 50
        reached_bottom_5_percent = True  # Always Allow Release; The "Bottom 5%" Gate Was Preventing Release When Xs Start Already Close Together
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
            reached_bottom_5_percent = True  # Keep Release Always Enabled On Re-Track
            last_fill_percentage = None
            last_frame_time = None
            speed_samples.clear()

        # Start Capture Thread; This Remains The Existing V3.21 Capture Path.
        stop_event = self._start_capture(scan_delay)
        start_time = time.time()
        if self.vars["fish_overlay"].get() == "Enabled":
            self.fish_overlay.show()

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
            self.status_overlay.set_line(f"Green Y: {green_y}", row=4)

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
            self.status_overlay.set_line(f"White Y: {predicted_white_y_top}", row=4)

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

        # Cleanup
        stop_event.set()
        mouse_controller.release(Button.left)
    def _execute_shake_click(self):
        """
        Search for first shake pixel then click
        Duplicate pixel logic from v13 is coming soon
        """
        # Get areas (scale factor applied inside _get_areas)
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s, _, _ = self._get_areas("shake")
        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s, _, _     = self._get_areas("fish")
        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self._get_areas("friend")
        shake_x = (shake_left_s + shake_right_s) // 2
        shake_y = (shake_top_s  + shake_bottom_s) // 2
        # Misc variables
        detection_method = (self.vars["detection_method"].get())
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
                screen_x = shake_left_s + x
                screen_y = shake_top_s + y
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
        self.set_status("Shake Mode: Navigation")
        # Get areas (scale factor applied inside _get_areas)
        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s, _, _         = self._get_areas("fish")
        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self._get_areas("friend")

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
        # Get All 3 Areas
        _, shake_top, _, _, _, _ = self._get_areas("shake")
        fish_left, fish_top, fish_right, fish_bottom, fish_width, fish_height = self._get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._get_areas("friend")
        self._reset_pid_state()
        mouse_down = False
        controller_mode = 3
        previous_controller_mode = controller_mode
        deadzone_action = 0
        self._pred_prev_fish_x = None
        self._pred_prev_bar_x = None
        self._pred_prev_time = None
        self._pred_filtered_vel = 0.0
        # Load Values From Gui
        arrow_hex = self.vars["arrow_color"].get()
        arrow_tol = int(self.vars["arrow_tolerance"].get() or 8)
        bar_ratio = float(self.vars["left_ratio"].get() or 0.5)
        pid_clamp = float(self.vars["pid_clamp"].get() or 100)
        thresh = float(self.vars["stabilize_threshold"].get() or 8)
        detection_method = (self.vars["detection_method"].get())
        restart_method = (self.vars["restart_method"].get())
        restart_delay = float(self.vars["restart_delay"].get())
        track_notes = self.vars["track_notes"].get()
        note_box_hex = self.vars["note_box_color"].get()
        note_box_tol = int(self.vars["note_box_tolerance"].get() or 8)
        note_track_ratio = float(self.vars["note_track_ratio"].get() or 0.1)
        scan_delay = float(self.vars["minigame_scan_delay"].get() or 0.05)
        tracking_threshold = int(self.vars["tracking_threshold"].get() or 0)
        previous_detection_source = None
        self.last_bar_size = None
        # Get Default Positions
        if detection_method == "Fish":
            img = self._grab_screen_region(fish_left, fish_top, fish_right, fish_bottom)
            left_x, right_x = self._find_bar_edges(img, arrow_hex, arrow_hex, arrow_tol, arrow_tol)
            self.last_cached_box_length = right_x - left_x if left_x and right_x else None
        self._last_should_hold = False
        self._last_input_time = 0
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
        # Start Screen Capture Thread
        self._cap_frame = None
        self._cap_event.clear()
        _minigame_stop = threading.Event()

        threading.Thread(
            target=self._capture_loop_full,
            args=(_minigame_stop, scan_delay),
            daemon=True
        ).start()
        # Prepare Templates For Image Search (Disabled For Now)
        # for key in ["fish", "left_bar", "right_bar"]:
        #    template = self.templates.get(key)

        #    if template is None:
        #        continue

        #    # Convert to grayscale once
        #    if len(template.shape) == 3:
        #        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
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
            # Step 2: Pixel Search
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
            # Step 3: Calculations
            bars_found = left_x is not None and right_x is not None # Check 1
            if bars_found:
                detection_source = 0
            else:
                capture_width = fish_right - fish_left
                bar_center, left_x, right_x = self._update_arrow_box_estimation(arrow_indicator_x, mouse_down, capture_width)
                bars_found = True # Check 2
                detection_source = 1
            source_changed = (
                previous_detection_source is not None and
                detection_source != previous_detection_source
            )
            if source_changed:
                # Clear PD history when we switch between real bars and arrow-estimated bars.
                # This prevents stale bar velocity/error state from causing a one-frame spike.
                self._reset_control_state()
            previous_detection_source = detection_source
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

                # ✅ New: Cache Real Box Size
                if left_x is not None and right_x is not None:
                    bar_size = abs(right_x - left_x)
                    if bar_size > 0:
                        self.last_cached_box_length = bar_size

                        # Sync Arrow Estimation Immediately
                        self.estimated_box_length = bar_size
            # Step 4: Restart Method And Cache
            if restart_method == "Friend Area":
                friend_x = self._find_color_center(friend_img, "# 9Bff9B", 2)
                if friend_x is not None:
                    release_mouse()
                    time.sleep(restart_delay)
                    return
                if fish_x == None:
                    fish_x = self.last_fish_x
                if left_x == None or right_x == None:
                    left_x = self.last_left_x
                    right_x = self.last_right_x
            elif restart_method == "Fish + Bar":
                if fish_x == None and (left_x == None or right_x == None):
                    release_mouse()
                    time.sleep(restart_delay)
                    return
                elif fish_x == None:
                    fish_x = self.last_fish_x
            else:
                if fish_x == None:
                    release_mouse()
                    time.sleep(restart_delay)
                    return
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
                bar_left_screen  = left_x  + fish_left - tracking_threshold if not left_x == None else None
                bar_right_screen = right_x + fish_left + tracking_threshold if not right_x == None else None
                # Check Max Left And Max Right
                if fish_x == None:
                    fish_x = 0
                if max_left and fish_x <= max_left: # Max Left And Right Check (Inside Bar)
                    controller_mode = 3
                elif max_right and fish_x >= max_right:
                    controller_mode = 2
                else:
                    if bar_left_screen <= fish_x <= bar_right_screen:
                        controller_mode = 0
                        if self.vars["efficiency_mode"].get() == "on":
                            controller_mode = 5
                    else:
                        controller_mode = 1
            # Step 6: Draw Boxes
            self.fish_overlay.clear() # Make Sure To Clear Overlay
            if self.vars["fish_overlay"].get() == "on":
                self.after(0, lambda _bc=bar_center, _bs=bar_size, _fl=fish_left: self.fish_overlay.draw(bar_center=_bc, box_size=_bs, color="green", canvas_offset=_fl, show_bar_center=True))
                self.after(0, lambda _ml=max_left, _fl=fish_left: self.fish_overlay.draw(bar_center=_ml, box_size=15, color="lightblue", canvas_offset=_fl))
                self.after(0, lambda _mr=max_right, _fl=fish_left: self.fish_overlay.draw(bar_center=_mr, box_size=15, color="lightblue", canvas_offset=_fl))
                self.after(0, lambda: self.fish_overlay.draw(bar_center=fish_x, box_size=10, color="red", canvas_offset=fish_left))
            # Step 7: Controller
            mode_changed = controller_mode != previous_controller_mode
            if controller_mode == 0 and bar_center is not None:
                if source_changed or mode_changed:
                    # Re-entering PD after a chase/reacquire frame can reuse stale
                    # error and velocity history, which causes a one-frame overshoot.
                    self._reset_pid_memory()
                error = fish_x - bar_center
                control = self._pid_control(error, bar_center)
                # Map Pid Output To Mouse Clicks Using Hysteresis To Avoid Jitter/Oscillation
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
            elif controller_mode == 1 and bar_center is not None: # Simple Tracking
                control = fish_x - bar_center
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
            time.sleep(0.01)
    def stop_macro(self):
        if not self.macro_running:
            return
        self.macro_running = False
        self._reset_pid_state()
        self.after(0, self.deiconify)  # Show Window Safely
        self.set_status("Macro Status: Stopped")

def ensure_terms_accepted():
    """
    Shows the TOS dialog when needed, then saves state.

    Rules:
    • First launch  → show TOS + Setup page (download prompt).
    • Version bump  → show TOS again (notify user TOS may have changed)
                       + Setup page (offer re-download of packs).
    • Normal launch → skip dialog entirely if TOS was already accepted.

    Returns True if the app should proceed, False if the user declined.
    """
    state, first_launch, is_new_version = load_app_state()

    needs_tos   = first_launch or not state.get("tos_accepted", False)
    needs_setup = first_launch or is_new_version or not state.get("tos_accepted", False)

    if needs_tos or needs_setup:
        terms_host = tk.Tk()
        terms_host.withdraw()
        terms_host.update_idletasks()

        # Pass show_setup so the dialog can present the download prompt on updates
        dialog = TermsOfServiceDialog(terms_host, show_setup=needs_setup)
        terms_host.wait_window(dialog)

        accepted = getattr(dialog, "accepted", False)
        terms_host.destroy()

        if not accepted:
            return False

        state["tos_accepted"] = True

    state["version"] = APP_VERSION
    save_app_state(state)
    return True

if __name__ == "__main__":
    if ensure_terms_accepted():
        app = App()
        app.mainloop()
