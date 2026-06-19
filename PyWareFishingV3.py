# Gui-Related
from customtkinter import *
import tkinter as tk
from tkinter import messagebox
# Save And Load
import json
import os
import subprocess
import sys
# Cocoa For macOS Overlays
if sys.platform == "darwin":
    try:
        import AppKit
        import Foundation
    except ImportError:
        AppKit = None
        Foundation = None
else:
    AppKit = None
    Foundation = None
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
import queue as _queue
import gdown
import shutil
import traceback
import zipfile
import tempfile
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
BASE_PATH, IS_COMPILED = get_base_path()
CONFIG_DIR = os.path.join(BASE_PATH, "configs")
IMAGES_PATH = os.path.join(BASE_PATH, "images")
DEBUG_DIR = BASE_PATH
CONFIG_PATH = os.path.join(BASE_PATH, "last_config.json")
APP_VERSION = "3.42"
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
    Also cleans up __MACOSX folder and moves configs folder if present.
    status_callback(msg: str) is called with progress text so the UI can
    display it.  Pass None to suppress UI updates.
    """
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
    def _cleanup_downloaded_files(download_dir):
        """
        Clean up __MACOSX folder and move configs folder contents if present.
        """
        # Delete __MACOSX folder if it exists
        macosx_path = os.path.join(download_dir, "__MACOSX")
        if os.path.exists(macosx_path) and os.path.isdir(macosx_path):
            _status("Deleting __MACOSX folder...")
            shutil.rmtree(macosx_path)
            _status("__MACOSX folder deleted.")
        # Move configs folder contents if it exists
        configs_folder = os.path.join(download_dir, "configs")
        if os.path.exists(configs_folder) and os.path.isdir(configs_folder):
            _status("Moving configs folder contents...")
            # Move contents from configs folder to the download directory
            for item in os.listdir(configs_folder):
                source = os.path.join(configs_folder, item)
                destination = os.path.join(download_dir, item)
                # If destination exists, handle appropriately
                if os.path.exists(destination):
                    if os.path.isdir(destination):
                        shutil.rmtree(destination)
                    else:
                        os.remove(destination)
                shutil.move(source, destination)
            # Remove the now-empty configs folder
            os.rmdir(configs_folder)
            _status("Configs folder contents moved successfully.")
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
            # Clean up downloaded files (remove __MACOSX, move configs folder)
            _cleanup_downloaded_files(tmp_dir)
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
def _correct_macos_color(frame):
    """
    Applies an optimized matrix transformation to correct Display P3 
    colors back into standard sRGB space instantly on macOS.
    """
    if P3_TO_SRGB_MATRIX is not None:
        # cv2.transform operates directly on the 3 channels very fast in C++
        return cv2.transform(frame, P3_TO_SRGB_MATRIX)
    return frame
# Area Selector Class
class AreaSelector:
    HANDLE_SIZE = 8
    def __init__(self, parent, shake_area, fish_area, friend_area, totem_area, callback):
        self.parent = parent
        self.callback = callback
        
        # Get scale factor from parent
        self.scale = parent._get_scale_factor()
        
        # Scale handle size for visual consistency
        self.scaled_handle_size = int(self.HANDLE_SIZE * self.scale)

        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)

        self.window.configure(bg="#222244")
        self.window.attributes("-alpha", 0.5)

        # Force Tk to compute real screen geometry before we query it.
        self.window.update_idletasks()

        # Use winfo_vrootwidth/height when available (gives the full virtual
        # root size). Fall back to screenwidth/height if not supported.
        try:
            w = self.window.winfo_vrootwidth()
            h = self.window.winfo_vrootheight()
            if w <= 0 or h <= 0:
                raise ValueError("vrootwidth/height not positive")
        except Exception:
            w = self.window.winfo_screenwidth()
            h = self.window.winfo_screenheight()

        # Position at (0, 0) in screen space.
        self.window.geometry(f"{w}x{h}+0+0")

        # Initialize mouse move and mouse tracking
        self.tracking = True
        self.tracking2 = False
        
        # Second idletasks pass so macOS actually maps the window at the
        # requested size before we start drawing.
        self.window.update_idletasks()

        self.canvas = tk.Canvas(self.window, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Store areas in logical coordinates
        self.shake = shake_area.copy()
        self.fish = fish_area.copy()
        self.friend = friend_area.copy()
        self.totem = totem_area.copy()

        self.dragging = None
        self.resize_corner = None
        self.active_area = None

        self.start_x = 0
        self.start_y = 0

        self.draw_boxes()

        self.canvas.bind("<Button-1>", self.mouse_down)
        self.canvas.bind("<B1-Motion>", self.mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.mouse_up)
        self.window.bind("<Motion>", self._on_mouse_move)

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    # Helper methods to convert between logical and physical coordinates
    def _logical_to_physical(self, x, y):
        """Convert logical coordinates to physical pixels."""
        return int(x * self.scale), int(y * self.scale)
    
    def _physical_to_logical(self, x, y):
        """Convert physical pixels to logical coordinates."""
        return x / self.scale, y / self.scale

    # DRAW 
    def draw_boxes(self):
        self.canvas.delete("all")
        self.draw_area(self.shake, "#ff007a", "Shake Box")
        self.draw_area(self.fish, "#00daff", "Fish Box")
        self.draw_area(self.friend, "#f7ff00", "Friend Box")
        self.draw_area(self.totem, "#9cff94", "Totem Box")

    def draw_area(self, area, color, label=""):
        # Convert logical coordinates to physical pixels for drawing
        x1, y1 = self._logical_to_physical(area["x"], area["y"])
        x2, y2 = self._logical_to_physical(area["x"] + area["width"], area["y"] + area["height"])
        mx = (x1 + x2) // 2
        my = (y1 + y2) // 2

        self.canvas.create_rectangle(x1, y1, x2, y2, 
                                     outline=color, width=3, 
                                     fill=color, stipple="gray25")

        # Label above the box
        if label:
            # Convert label position to physical pixels
            label_y = y1 - int(10 * self.scale)
            self.canvas.create_text(mx, label_y, text=label,
                                    fill=color, font=("Segoe UI", int(11 * self.scale), "bold"),
                                    anchor="s")

        # All 8 handles - use scaled handle size
        for x, y in [(x1, y1), (x2, y1), (x1, y2), (x2, y2),
                     (mx, y1), (mx, y2), (x1, my), (x2, my)]:
            self.canvas.create_rectangle(x - self.scaled_handle_size, y - self.scaled_handle_size,
                                         x + self.scaled_handle_size, y + self.scaled_handle_size, 
                                         fill="white", outline="")

    # Resizer / hit test (working in logical coordinates)
    def inside(self, x, y, area):
        return (
            area["x"] <= x <= area["x"] + area["width"] and
            area["y"] <= y <= area["y"] + area["height"]
        )

    def get_handle(self, x, y, area):
        # Convert physical mouse coordinates to logical for comparison
        logical_x, logical_y = self._physical_to_logical(x, y)
        
        x1 = area["x"]
        y1 = area["y"]
        x2 = x1 + area["width"]
        y2 = y1 + area["height"]
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        
        # Scale the handle size for logical coordinate hit detection
        scaled_handle_logical = self.scaled_handle_size / self.scale
        
        handles = {
            "nw": (x1, y1), "ne": (x2, y1),
            "sw": (x1, y2), "se": (x2, y2),
            "n":  (mx, y1), "s":  (mx, y2),
            "w":  (x1, my), "e":  (x2, my),
        }
        
        for name, (hx, hy) in handles.items():
            if abs(logical_x - hx) <= scaled_handle_logical and abs(logical_y - hy) <= scaled_handle_logical:
                return name
        
        return None

    # Detect mouse input from user
    def mouse_down(self, e):
        # Convert physical canvas coordinates to logical for storage
        logical_x, logical_y = self._physical_to_logical(e.x, e.y)
        self.start_x = logical_x
        self.start_y = logical_y

        for area, name in [(self.fish, "fish"), (self.shake, "shake"), 
                           (self.friend, "friend"), (self.totem, "totem")]:
            
            # Pass physical coordinates to get_handle (it converts internally)
            handle = self.get_handle(e.x, e.y, area)

            if handle:
                self.resize_corner = handle
                self.active_area = area
                return

            if self.inside(logical_x, logical_y, area):
                self.dragging = name
                self.active_area = area
                return

    def mouse_drag(self, e):
        if not self.dragging and not self.resize_corner:
            return
        
        # Convert to logical coordinates
        logical_x, logical_y = self._physical_to_logical(e.x, e.y)
        dx = logical_x - self.start_x
        dy = logical_y - self.start_y

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
            
        self.start_x = logical_x
        self.start_y = logical_y
        self.draw_boxes()

    def mouse_up(self, e):
        self.dragging = None
        self.resize_corner = None
        self.active_area = None

    def mouse_move(self, e):
        for area in [self.fish, self.shake, self.friend, self.totem]:
            handle = self.get_handle(e.x, e.y, area)
            if handle:
                cursor = {
                    "nw": "size_nw_se", "se": "size_nw_se",
                    "ne": "size_ne_sw", "sw": "size_ne_sw",
                    "n": "size_ns", "s": "size_ns",
                    "e": "size_we", "w": "size_we",
                }[handle]

                self.canvas.config(cursor=cursor)
                return

            # Convert to logical for inside check
            logical_x, logical_y = self._physical_to_logical(e.x, e.y)
            if self.inside(logical_x, logical_y, area):
                self.canvas.config(cursor="fleur")
                return

        self.canvas.config(cursor="")

    # Mouse move DETECTION functions
    def _on_mouse_move(self, event):
        if not self.tracking:
            return

        # Global mouse position in physical pixels
        physical_x = self.window.winfo_pointerx()
        physical_y = self.window.winfo_pointery()
        
        # Convert to logical coordinates for area checking
        logical_x, logical_y = self._physical_to_logical(physical_x, physical_y)
        self.tracking2 = False

        # Check areas using logical coordinates
        if self._point_in_area(logical_x, logical_y, self.shake):
            x2 = logical_x - self.shake["x"]
            y2 = logical_y - self.shake["y"]
            x_ratio = round(x2 / self.shake["width"], 2)
            y_ratio = round(y2 / self.shake["height"], 2)
            self.parent.set_status(f"SHAKE → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        elif self._point_in_area(logical_x, logical_y, self.fish):
            x2 = logical_x - self.fish["x"]
            y2 = logical_y - self.fish["y"]
            x_ratio = round(x2 / self.fish["width"], 2)
            y_ratio = round(y2 / self.fish["height"], 2)
            self.parent.set_status(f"FISH → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        elif self._point_in_area(logical_x, logical_y, self.friend):
            x2 = logical_x - self.friend["x"]
            y2 = logical_y - self.friend["y"]
            x_ratio = round(x2 / self.friend["width"], 2)
            y_ratio = round(y2 / self.friend["height"], 2)
            self.parent.set_status(f"FRIEND → X RATIO: {x_ratio}, Y RATIO: {y_ratio}")
            self.tracking2 = True

        elif self._point_in_area(logical_x, logical_y, self.totem):
            x2 = logical_x - self.totem["x"]
            y2 = logical_y - self.totem["y"]
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
        if not self.tracking2:
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
        self.window.title("PyWare Status Overlay")

        # Position (Top-Left Like V1)
        self.window.geometry(f"260x180+20+40")

        # Remove title bar and transparency
        self.window.overrideredirect(True)  # Remove title bar on macOS
        self.window.attributes("-alpha", 0.85)  # Optional Transparency

        # General settings for Windows and macOS compatibility
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
            text="PyWare Fishing V3.42",
            fg="#ca0000",
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
        self.width = 800
        self.height = 60

    def init_window(self):
        """Create and initialize the overlay window and canvas."""
        if self.window and self.window.winfo_exists():
            return

        self.window = tk.Toplevel(self.parent_app)
        self.window.title("PyWare Fish Overlay")

        # Position
        overlay_x = int(self.parent_app.SCREEN_WIDTH * 0.5) - int(self.width / 2)
        overlay_y = int(self.parent_app.SCREEN_HEIGHT * 0.65)
        self.window.geometry(f"{self.width}x{self.height}+{overlay_x}+{overlay_y}")
        
        # Remove title bar and transparency
        self.window.overrideredirect(True)  # Remove title bar on macOS
        self.window.attributes("-alpha", 0.85)  # Optional Transparency

        # General settings for Windows and macOS compatibility
        self.window.attributes("-topmost", True)
        self.canvas = tk.Canvas(
            self.window,
            width=self.width,
            height=self.height,
            bg="#1d1d1d",
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

    def set_layout(self, x, y, width, height):
        """Resize and reposition the overlay without recreating it."""
        width = max(60, int(width))
        height = max(36, int(height))
        x = max(0, min(int(x), max(0, self.parent_app.SCREEN_WIDTH - width)))
        y = max(0, min(int(y), max(0, self.parent_app.SCREEN_HEIGHT - height)))

        self.width = width
        self.height = height

        def _apply():
            self.init_window()
            if not self.window or not self.window.winfo_exists():
                return
            self.window.geometry(f"{width}x{height}+{x}+{y}")
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.configure(width=width, height=height)

        self.parent_app.after(0, _apply)

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

    def draw(self, bar_center, box_size, color, canvas_offset, show_bar_center=False, bar_y1=0.15, bar_y2=0.85):
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
        py1 = int(bar_y1 * self.height)
        py2 = int(bar_y2 * self.height)

        def _draw():
            self.canvas.create_rectangle(bx1, py1, bx2, py2,
                                        outline=color, width=2, fill="#000000")
            if show_bar_center:
                self.canvas.create_line(center_x, py1, center_x, py2,
                                       fill="gray", width=2)

        self.canvas.after(0, _draw)
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
        self.SCREEN_SCALE = ((self.SCREEN_WIDTH / 1920) + (self.SCREEN_HEIGHT / 1080)) / 2
        self.BASE_PATH = BASE_PATH
        # Calculate scaling factors
        self.scale_x_1440 = self.SCREEN_WIDTH / 2560
        self.scale_y_1440 = self.SCREEN_HEIGHT / 1440
        # Detection Variables
        self.last_fish_x = None
        self.last_bar_left = None
        self.last_bar_right = None
        self.last_cached_box_length = None  # Cached Bar Size From Minigame For Arrow Estimation
        # P/D State Variables
        self._pid_last_error = 0.0      # Previous Error Term
        self._pid_last_scan_time = None      # Timestamp Of Last Pd Sample
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
        self._last_bar_center = None
        self._reset_control_state()
        # Hotkey Variables
        self.hotkey_start = Key.f5
        self.hotkey_stop = Key.f7
        self.hotkey_change_areas = Key.f6 # Added For The Bar Area Selector
        self.hotkey_labels = {}  # Store Label Widgets For Dynamic Updates
        # Macro State
        self.macro_running = False
        self.macro_thread = None
        # Logging And Totem Trigger Counters
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
        self._fish_overlay_mode = "idle"
        self._fish_overlay_cast_bounds = None
        self.eyedropper = Eyedropper(self)
        self.status_overlay = StatusOverlay(self)
        # Start Hotkey Listener
        try:
            self.key_listener = KeyListener(on_press=self.on_key_press)
            self.key_listener.daemon = True
            self.key_listener.start()
        except Exception as e:
            print("Error: ", e)
        # Create Window
        self.configure(fg_color="#181836")   # <- Main Window Ultra Dark
        self.geometry("800x600")
        self.title("PyWare Fishing V3.42")
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
            text="PYWARE FISHING V3.42",
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
        self._apply_fish_overlay_state()
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
        self.download_btn = CTkButton(
            basic_settings,
            text="Download",
            width=40,
            corner_radius=8,
            command=self.download_configs
        )
        self.download_btn.grid(row=0, column=3, padx=12, pady=10, sticky="w")
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
        CTkButton(color_settings, text="Take Screenshot", corner_radius=10, width=120, command=self._take_debug_screenshot).grid(row=0, column=3, padx=12, pady=12, sticky="w")
        CTkLabel(color_settings, text="Left Bar:").grid(row=2, column=0, padx=12, pady=10, sticky="w") # Left/Right Bar
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
        CTkLabel(color_settings, text="Arrow:").grid(row=4, column=0, padx=12, pady=10, sticky="w") # Arrow
        arrow_color_var = StringVar(value="#848587")
        self.vars["arrow_color"] = arrow_color_var
        arrow_entry = CTkEntry(color_settings, placeholder_text="#848587", width=120, fg_color="green", textvariable=arrow_color_var)
        arrow_entry.grid(row=4, column=1, padx=12, pady=10, sticky="w")
        arrow_color_var.trace_add("write", lambda *args: self._update_entry_color(arrow_color_var, arrow_entry))
        self._update_entry_color(arrow_color_var, arrow_entry)
        CTkLabel(color_settings, text="Fish:").grid(row=5, column=0, padx=12, pady=10, sticky="w") # Fish
        fish_color_var = StringVar(value="#434B5B")
        self.vars["fish_color"] = fish_color_var
        fish_entry = CTkEntry(color_settings, placeholder_text="#434B5B", width=120, fg_color="green", textvariable=fish_color_var)
        fish_entry.grid(row=5, column=1, padx=12, pady=10, sticky="w")
        fish_color_var.trace_add("write", lambda *args: self._update_entry_color(fish_color_var, fish_entry))
        self._update_entry_color(fish_color_var, fish_entry)
        CTkLabel(color_settings, text="Click Shake:").grid(row=6, column=0, padx=12, pady=10, sticky="w" ) # Shake Color
        shake_color_var = StringVar(value="#FFFFFF")
        self.vars["shake_color"] = shake_color_var
        shake_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=shake_color_var)
        shake_entry.grid(row=6, column=1, padx=12, pady=10, sticky="w")
        shake_color_var.trace_add("write", lambda *args: self._update_entry_color(shake_color_var, shake_entry))
        self._update_entry_color(shake_color_var, shake_entry)
        CTkLabel(color_settings, text="Tracking Target:").grid(row=7, column=0, padx=12, pady=10, sticky="w") # Tracking Target
        note_box_color_var = StringVar(value="#00990c")
        self.vars["note_box_color"] = note_box_color_var
        note_box_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=note_box_color_var)
        note_box_entry.grid(row=7, column=1, padx=12, pady=10, sticky="w")
        note_box_color_var.trace_add("write", lambda *args: self._update_entry_color(note_box_color_var, note_box_entry))
        self._update_entry_color(note_box_color_var, note_box_entry)
        CTkLabel(color_settings, text="Cast Release:").grid(row=8, column=0, padx=12, pady=10, sticky="w") # Green
        perfect_color_var = StringVar(value="#64a04c")
        self.vars["perfect_color"] = perfect_color_var
        perfect_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=perfect_color_var)
        perfect_entry.grid(row=8, column=1, padx=12, pady=10, sticky="w")
        perfect_color_var.trace_add("write", lambda *args: self._update_entry_color(perfect_color_var, perfect_entry))
        self._update_entry_color(perfect_color_var, perfect_entry)
        CTkLabel(color_settings, text="Cast Hold:").grid(row=9, column=0, padx=12, pady=10, sticky="w") # White
        perfect_color2_var = StringVar(value="#d4d3ca")
        self.vars["perfect_color2"] = perfect_color2_var
        perfect2_entry = CTkEntry(color_settings, width=120, fg_color="green", textvariable=perfect_color2_var)
        perfect2_entry.grid(row=9, column=1, padx=12, pady=10, sticky="w")
        perfect_color2_var.trace_add("write", lambda *args: self._update_entry_color(perfect_color2_var, perfect2_entry))
        self._update_entry_color(perfect_color2_var, perfect2_entry)
        # Tolerance
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
        CTkLabel(color_settings, text="Tolerance:").grid(row=6, column=2, padx=12, pady=10, sticky="w" )
        shake_tolerance_var = StringVar(value="5")
        self.vars["shake_tolerance"] = shake_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=shake_tolerance_var).grid(row=6, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Tolerance:").grid(row=7, column=2, padx=12, pady=10, sticky="w")
        note_box_tolerance_var = StringVar(value="2")
        self.vars["note_box_tolerance"] = note_box_tolerance_var
        CTkEntry(color_settings, width=120, textvariable=note_box_tolerance_var).grid(row=7, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(color_settings, text="Tolerance:").grid(row=8, column=2, padx=12, pady=10, sticky="w")
        perfect_cast_tolerance_var = StringVar(value="16")
        self.vars["perfect_cast_tolerance"] = perfect_cast_tolerance_var
        perfect_cast_tolerance_entry = CTkEntry(color_settings, width=120, textvariable=perfect_cast_tolerance_var)
        perfect_cast_tolerance_entry.grid(row=8, column=3, padx=12, pady=10, sticky="w")
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
        fish_overlay_var.trace_add("write", self._on_fish_overlay_toggle)
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
        always_on_top_var = StringVar(value="off")
        self.vars["always_on_top"] = always_on_top_var
        sw = CTkSwitch(toggles, text="Always On Top", variable=always_on_top_var, onvalue="on", offvalue="off")
        sw.grid(row=3, column=1, padx=12, pady=8, sticky="w")
        self.switches["always_on_top"] = sw
        always_on_top_var.trace_add("write", self._on_always_on_top_toggle)
        lock_cursor_var = StringVar(value="off")
        self.vars["lock_cursor"] = lock_cursor_var
        sw = CTkSwitch(toggles, text="Lock Cursor", variable=lock_cursor_var, onvalue="on", offvalue="off")
        sw.grid(row=4, column=0, padx=12, pady=8, sticky="w")
        self.switches["lock_cursor"] = sw
        click_after_minigame_var = StringVar(value="off")
        self.vars["click_after_minigame"] = click_after_minigame_var
        sw = CTkSwitch(toggles, text="Click After Minigame", variable=click_after_minigame_var, onvalue="on", offvalue="off")
        sw.grid(row=4, column=1, padx=12, pady=8, sticky="w")
        self.switches["click_after_minigame"] = sw
        # hdr = self.vars["hdr"].get()
        hdr_var = StringVar(value="off")
        self.vars["hdr"] = hdr_var
        sw = CTkSwitch(toggles, text="HDR", variable=hdr_var, onvalue="on", offvalue="off")
        sw.grid(row=5, column=0, padx=12, pady=8, sticky="w")
        self.switches["hdr"] = sw
        CTkLabel(toggles, text="Misc", font=CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=12, pady=8, sticky="w")
        CTkLabel(toggles, text="Select Rod Duration").grid(row=1, column=2, padx=12, pady=8, sticky="w")
        bag_delay_var = StringVar(value="0.36")
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
            CTkLabel(toggles, text="Navigation").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        CTkLabel(toggles, text="Fishing Mode:").grid(row=4, column=2, padx=12, pady=10, sticky="w" )
        fishing_mode_var = StringVar(value="Color")
        self.vars["fishing_mode"] = fishing_mode_var
        fishing_cb = CTkComboBox(toggles, values=["Line", "Color"], 
                               variable=fishing_mode_var, command=lambda v: self.set_status(f"Fishing Mode: {v}")
                               )
        fishing_cb.grid(row=4, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["fishing_mode"] = fishing_cb
        # Normal Casting Group
        self.normal_casting = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        self.normal_casting.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(self.normal_casting, text="Casting Options", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(self.normal_casting, text="Delay").grid(row=1, column=0, padx=12, pady=8, sticky="w")
        delay_before_casting_var = StringVar(value="0.5")
        self.vars["delay_before_casting"] = delay_before_casting_var
        delay_before_casting_entry = CTkEntry(self.normal_casting, width=120, textvariable=delay_before_casting_var)
        delay_before_casting_entry.grid(row=1, column=1, padx=12, pady=8, sticky="w")
        CTkLabel(self.normal_casting, text="Casting Duration").grid(row=2, column=0, padx=12, pady=8, sticky="w")
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
        CTkLabel(self.perfect_casting, text="Delay Before Casting").grid(row=1, column=0, padx=12, pady=8, sticky="w")
        delay_before_casting_var = StringVar(value="0.5")
        self.vars["delay_before_casting"] = delay_before_casting_var
        delay_before_casting_entry = CTkEntry(self.perfect_casting, width=120, textvariable=delay_before_casting_var)
        delay_before_casting_entry.grid(row=1, column=1, padx=12, pady=8, sticky="w")
        CTkLabel(self.perfect_casting, text="Delay After Casting").grid(row=1, column=2, padx=12, pady=8, sticky="w")
        cast_delay_var = StringVar(value="0.6")
        self.vars["cast_delay"] = cast_delay_var
        cast_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=cast_delay_var)
        cast_delay_entry.grid(row=1, column=3, padx=12, pady=8, sticky="w")
        CTkLabel(self.perfect_casting, text="Threshold (percentage):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        perfect_threshold_var = StringVar(value="95.5")
        self.vars["perfect_threshold"] = perfect_threshold_var
        perfect_threshold_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_threshold_var)
        perfect_threshold_entry.grid(row=2, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(self.perfect_casting, text="Scan FPS:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        cast_scan_delay_var = StringVar(value="0.05")
        self.vars["cast_scan_delay"] = cast_scan_delay_var
        cast_scan_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=cast_scan_delay_var)
        cast_scan_delay_entry.grid(row=2, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(self.perfect_casting, text="Failsafe Release Timeout:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        perfect_max_time_var = StringVar(value="5.5")
        self.vars["perfect_max_time"] = perfect_max_time_var
        perfect_max_time_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_max_time_var)
        perfect_max_time_entry.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(self.perfect_casting, text="Delay Before Release:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        perfect_release_delay_var = StringVar(value="0")
        self.vars["perfect_release_delay"] = perfect_release_delay_var
        perfect_release_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_release_delay_var)
        perfect_release_delay_entry.grid(row=3, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(self.perfect_casting, text="Release Band Adjustments (ms)", font=CTkFont(size=14, weight="bold")).grid(row=4, column=0, columnspan=4, padx=12, pady=(18, 8), sticky="w")
        CTkLabel(self.perfect_casting, text="+ releases earlier, - releases later").grid(row=5, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="w")
        perfect_cast_bands = [
            ("<700 px/s", "perfect_cast_timing_700"),
            ("700-800 px/s", "perfect_cast_timing_800"),
            ("800-900 px/s", "perfect_cast_timing_900"),
            ("900-1000 px/s", "perfect_cast_timing_1000"),
            ("1000-1100 px/s", "perfect_cast_timing_1100"),
            ("1100-1200 px/s", "perfect_cast_timing_1200"),
            ("1200-1300 px/s", "perfect_cast_timing_1300"),
            ("1300-1400 px/s", "perfect_cast_timing_1400"),
            ("1400-1500 px/s", "perfect_cast_timing_1500"),
            ("1500-1600 px/s", "perfect_cast_timing_1600"),
            ("1600+ px/s", "perfect_cast_timing_1600plus"),
        ]
        for idx, (label, key) in enumerate(perfect_cast_bands):
            row = 6 + idx // 2
            col = (idx % 2) * 2
            CTkLabel(self.perfect_casting, text=label).grid(row=row, column=col, padx=12, pady=6, sticky="w")
            band_var = StringVar(value="0")
            self.vars[key] = band_var
            CTkEntry(self.perfect_casting, width=120, textvariable=band_var).grid(row=row, column=col + 1, padx=12, pady=6, sticky="w")
        shake_configuration = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        shake_configuration.grid(row=3, column=0, padx=20, pady=20, sticky="nw")
        # Shake Configuration
        CTkLabel(shake_configuration, text="Shake Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(shake_configuration, text="Shake Failsafe (attempts):").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        shake_failsafe_var = StringVar(value="80")
        self.vars["shake_failsafe"] = shake_failsafe_var
        CTkEntry(shake_configuration, width=120, textvariable=shake_failsafe_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")
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
        bait_delay_var = StringVar(value="0")
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
        note_track_ratio_var = StringVar(value="0.4")
        self.vars["note_track_ratio"] = note_track_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=note_track_ratio_var).grid(row=1, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(ratio_settings, text="Scan Delay (seconds):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        minigame_scan_delay_var = StringVar(value="0.01")
        self.vars["minigame_scan_delay"] = minigame_scan_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=minigame_scan_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(ratio_settings, text="Restart Delay:").grid(row=2, column=2, padx=12, pady=10, sticky="w" )
        restart_delay_var = StringVar(value="2.5")
        self.vars["restart_delay"] = restart_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=restart_delay_var ).grid(row=2, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(ratio_settings, text="Required Fish Pixels:").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        required_fish_pixels = StringVar(value="8")
        self.vars["required_fish_pixels"] = required_fish_pixels
        CTkEntry(ratio_settings, width=120, textvariable=required_fish_pixels).grid(row=3, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(ratio_settings, text="Amount of Arrows:").grid(row=3, column=0, padx=12, pady=10, sticky="w" )
        arrow_method_var = StringVar(value="2")
        self.vars["arrow_method"] = arrow_method_var
        arrow_cb = CTkComboBox(ratio_settings, values=["2", "1"],
                               variable=arrow_method_var, command=lambda v: self.set_status(f"This rod has {v} arrows")
                               )
        arrow_cb.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["arrow_method"] = arrow_cb
        CTkLabel(ratio_settings, text="Line Bar Ratio:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        line_bar_ratio_var = StringVar(value="0.45")
        self.vars["fish_line_bar_ratio"] = line_bar_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=line_bar_ratio_var).grid(row=4, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(ratio_settings, text="Min Line Density:").grid(row=4, column=2, padx=12, pady=10, sticky="w")
        line_min_density_var = StringVar(value="0.8")
        self.vars["fish_line_min_density"] = line_min_density_var
        CTkEntry(ratio_settings, width=120, textvariable=line_min_density_var).grid(row=4, column=3, padx=12, pady=10, sticky="w")
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
        # Loggings
        logging = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        logging.grid(row=0, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(logging, text="Loggings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(logging, text="Logging Mode:").grid(row=1, column=0, padx=12, pady=10, sticky="w" )
        logging_mode_var = StringVar(value="Screenshot")
        self.vars["logging_mode"] = logging_mode_var
        logging_cb = CTkComboBox(logging, values=["Screenshot", "Text", "File", "Disabled"], 
                               variable=logging_mode_var, command=lambda v: self.set_status(f"Logging mode: {v}")
                               )
        logging_cb.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["logging_mode"] = logging_cb
        CTkLabel(logging, text="Logging Type:").grid(row=1, column=2, padx=12, pady=10, sticky="w" )
        logging_trigger_var = StringVar(value="Cycles")
        self.vars["logging_trigger"] = logging_trigger_var
        logging_cb = CTkComboBox(logging, values=["Time", "Cycles", "Disabled"], 
                               variable=logging_trigger_var, command=lambda v: self.set_status(f"Logging Type: {v}")
                               )
        logging_cb.grid(row=1, column=3, padx=12, pady=10, sticky="w")
        self.comboboxes["logging_trigger"] = logging_cb
        CTkLabel(logging, text="Webhook URL:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        logging_url_var = StringVar(value="")
        self.vars["logging_url"] = logging_url_var
        CTkEntry(logging, width=120, textvariable=logging_url_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(logging, text="Webhook name:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        logging_name_var = StringVar(value="PyWare Fishing")
        self.vars["logging_name"] = logging_name_var
        CTkEntry(logging, width=120, textvariable=logging_name_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(logging, text="Cycles:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        logging_cycle_var = StringVar(value="3")
        self.vars["logging_cycle"] = logging_cycle_var
        CTkEntry(logging, width=120, textvariable=logging_cycle_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")
        CTkLabel(logging, text="Trigger in (seconds):").grid(row=3, column=2, padx=12, pady=10, sticky="w")
        logging_time_var = StringVar(value="60")
        self.vars["logging_time"] = logging_time_var
        CTkEntry(logging, width=120, textvariable=logging_time_var).grid(row=3, column=3, padx=12, pady=10, sticky="w")
        # Test webhook button
        CTkButton(logging, text="Test Webhook", width=120, command=self.test_logging
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
        CTkLabel(auto_totem, text="Trigger in (seconds):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        totem_delay_var = StringVar(value="999")
        self.vars["totem_delay"] = totem_delay_var
        CTkEntry(auto_totem, width=120, textvariable=totem_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(auto_totem, text="Cycles:").grid(row=2, column=2, padx=12, pady=10, sticky="w")
        totem_cycles_var = StringVar(value="70")
        self.vars["totem_cycles"] = totem_cycles_var
        CTkEntry(auto_totem, width=120, textvariable=logging_cycle_var).grid(row=2, column=3, padx=12, pady=10, sticky="w")
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
        CTkLabel(auto_reconnect, text="Threshold:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        reconnect_threshold_var = StringVar(value="140")
        self.vars["reconnect_threshold"] = reconnect_threshold_var
        CTkEntry(auto_reconnect, width=120, textvariable=reconnect_threshold_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")
        # reconnect_wait_time
        CTkLabel(auto_reconnect, text="Wait Time:").grid(row=1, column=2, padx=12, pady=10, sticky="w")
        reconnect_wait_time_var = StringVar(value="20")
        self.vars["reconnect_wait_time"] = reconnect_wait_time_var
        CTkEntry(auto_reconnect, width=120, textvariable=reconnect_wait_time_var).grid(row=1, column=3, padx=12, pady=10, sticky="w")
        # Mirror Ratio
        CTkLabel(auto_reconnect, text="Mirror X (Ratio):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        mirror_ratio_var = StringVar(value="0.55")
        self.vars["mirror_ratio"] = mirror_ratio_var
        CTkEntry(auto_reconnect, width=120, textvariable=mirror_ratio_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(auto_reconnect, text="Mirror Y (Ratio):").grid(row=2, column=2, padx=12, pady=10, sticky="w")
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
    def _get_var_number(self, key, default, cast=float):
        """Read a numeric GUI setting with a safe fallback."""
        try:
            value = self.vars.get(key)
            if value is None:
                return default
            raw_value = value.get() if hasattr(value, "get") else value
            if raw_value in ("", None):
                return default
            return cast(raw_value)
        except Exception:
            return default
    def _get_rod_specific_setting(self, key, default):
        """Compatibility shim for Hydra.py-derived settings now stored in self.vars."""
        return self._get_var_number(key, default, float)
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
    def save_settings(self, name="default", prompt=True, default_value=True):
        """Save all settings to a JSON config file with optional confirmation."""
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(CONFIG_PATH)
        config_folder = os.path.join(CONFIG_DIR, name)
        os.makedirs(config_folder, exist_ok=True)
        path = os.path.join(config_folder, "config.json")
        # Collect current GUI data
        data = self._collect_settings_data()
        # Load old config for comparison / revert
        old_data = None
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    old_data = json.load(f)
            except:
                old_data = None
        # Detect changes
        settings_changed = old_data != data
        # Ask user if prompt enabled
        if settings_changed and prompt:
            result = messagebox.askyesno(
                "Settings Changed",
                f"The settings for '{name}' have changed.\nDo you want to save these changes?",
                icon=messagebox.QUESTION
            )
            # User clicked NO -> revert
            if not result:
                if old_data:
                    self.load_settings(name)
                self.set_status("Cancelled: Settings reverted")
                return
        # If no prompt and default_value is False -> revert
        if not prompt and not default_value:
            if old_data:
                self.load_settings(name)
            self.set_status("Cancelled: Settings reverted")
            return
        # Save settings
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
        # Comboboxes are already saved via StringVars
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
        rod_folder = os.path.join(CONFIG_DIR, name.replace([".json"]))
        # Always load misc settings (bar_areas, hotkeys) from last_config.json
        # regardless of whether the named profile exists.
        self.load_misc_settings()
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
        # Comboboxes are already loaded via StringVars
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
        if self.verify_images_exist(required_images) == False:
            return  # Stop Instead Of Crashing
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
                    stop_key = data.get("stop_key", "F7")
                    self.vars["start_key"].set(start_key)
                    self.vars["change_bar_areas_key"].set(change_key)
                    self.vars["stop_key"].set(stop_key)
                    # Convert To Pynput Keys
                    self.hotkey_start = self._string_to_key(start_key)
                    self.hotkey_change_areas = self._string_to_key(change_key)
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
        """Reset settings to default while keeping colors."""
        current = self.config_var.get()
        result = messagebox.askyesno(
            "Confirm Reset",
            f"Are you sure you want to reset settings for '{current}' to default?\nThis will undo all customizations except colors.\nClick No in the second dialogue to confirm",
            icon=messagebox.WARNING
        )
        if result:
            config_folder = os.path.join(CONFIG_DIR, current)
            config_path = os.path.join(config_folder, "config.json")
            os.makedirs(config_folder, exist_ok=True)
            try:
                # Load existing config to preserve colors
                existing_config = {}
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        existing_config = json.load(f)
                # Get full default settings
                default_settings = self.get_default_settings()
                # Keep current colors
                for color_key in self.get_default_colors().keys():
                    if color_key in existing_config:
                        default_settings[color_key] = existing_config[color_key]
                # Save updated config
                with open(config_path, "w") as f:
                    json.dump(default_settings, f, indent=4)
                self.on_config_selected(current)
                self.set_status(
                    f"Settings for '{current}' reset to default (colors preserved)"
                )
            except Exception as e:
                messagebox.showerror(
                    "Reset Error",
                    f"Failed to reset settings: {e}"
                )
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
    def verify_images_exist(self, required_files):
        missing = []
        for file in required_files:
            path = os.path.join(IMAGES_PATH, file)
            if not os.path.exists(path):
                missing.append(file)
        if missing:
            msg = (
                "Missing required image files:\n\n"
                + "\n".join(missing)
                + "\n\nDo you want to download the config and images pack?"
            )
            result = messagebox.askyesno("Missing Images", msg)
            if not result:
                return False
            self.download_configs()
        return True
    def download_configs(self):
        """Download configs and image packs from Google Drive in the background."""
        if getattr(self, "_download_in_progress", False):
            self.set_status("Download already in progress…")
            return
        self._download_in_progress = True
        self._download_queue = _queue.Queue()
        self._download_success = False
        if hasattr(self, "download_btn"):
            self.download_btn.configure(state="disabled")
        self.set_status("Starting download…")
        def _worker():
            self._download_success = download_and_extract_packs(
                status_callback=self._download_queue.put
            )
            self._download_queue.put(None)
        threading.Thread(target=_worker, daemon=True).start()
        self._poll_download_queue()
    def _poll_download_queue(self):
        try:
            while True:
                item = self._download_queue.get_nowait()
                if item is None:
                    if self._download_success:
                        self.set_status("Completed: Packs installed successfully.")
                    else:
                        self.set_status("❌ Download failed. Install packs manually later.")
                    if hasattr(self, "download_btn"):
                        self.download_btn.configure(state="normal")
                    self._download_in_progress = False
                    return
                else:
                    self.set_status(item)
        except _queue.Empty:
            pass
        self.after(100, self._poll_download_queue)
    # Key Press Functions
    def _apply_hotkeys_from_vars(self):
        """Apply hotkey StringVars to the live hotkey attributes used by on_key_press."""
        self.hotkey_start = self._string_to_key(self.vars["start_key"].get())
        self.hotkey_change_areas = self._string_to_key(self.vars["change_bar_areas_key"].get())
        self.hotkey_stop = self._string_to_key(self.vars["stop_key"].get())
        # Show Status Lines
        self.status_overlay.set_line(f"Ready to start", row=1)
        self.status_overlay.set_line(f"Press {self.hotkey_start} to start", row=2)
        self.status_overlay.set_line(f"Press {self.hotkey_change_areas} to change bar areas", row=3)
        self.status_overlay.set_line(f"Press {self.hotkey_stop} to stop", row=4)
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
        enable_hotkeys2 = True if enable_hotkeys == "on" else False
        # Fallback
        if self.macro_running == True:
            enable_hotkeys2 = True
        if enable_hotkeys2 == True:
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
            elif pressed_key == self._normalize_hotkey_value(self.hotkey_stop):
                self.stop_macro()
        else:
            self.save_settings(config_name, prompt=False)
    def on_key_press(self, key):
        pressed_key = self.normalize_key(key)
        # Move EVERYTHING that touches tkinter into main thread
        self.after(0, self._handle_key_press_main_thread, pressed_key)
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
        self._set_fish_overlay_mode("idle")
        # Toggle Off If Already Open
        if hasattr(self, "area_selector") and self.area_selector and self.area_selector.window.winfo_exists():
            self._set_fish_overlay_mode("idle")
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
        logging_name = self.vars["logging_name"].get()
        webhook_url2 = self.vars["logging_url"].get()
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
        logging_name = self.vars["logging_name"].get()
        webhook_url2 = self.vars["logging_url"].get()
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
        logging_mode = self.vars["logging_mode"].get()
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
        webhook_url = self.vars["logging_url"].get()
        logging_name = self.vars["logging_name"].get()
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
        logging_mode = self.vars["logging_mode"].get()
        if logging_mode == "Disabled":
            self.set_status("⚠ Logging is disabled.")
            return
        if not logging_mode == "File":
            # logging_url
            webhook_url = self.vars["logging_url"].get().strip()
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
    # Take Debug Screenshot
    def _take_debug_screenshot(self):
        """
        Capture all relevant areas (shake, fish, friend, totem)
        and save debug images.
        """
        self.set_status("Saved debug screenshots (fish, shake, friend, totem, full)")
        def get_area(name, fallback_rect):
            area = self.bar_areas.get(name)
            if isinstance(area, dict):
                left   = area.get("x", 0)
                top    = area.get("y", 0)
                right  = left + area.get("width", 0)
                bottom = top  + area.get("height", 0)
                if right > left and bottom > top:
                    return left, top, right, bottom
            return fallback_rect
        # Define Areas (Same As Minigame) 
        shake = get_area("shake", (
            int(self.SCREEN_WIDTH * 0.1041),
            int(self.SCREEN_HEIGHT * 0.0925),
            int(self.SCREEN_WIDTH * 0.8958),
            int(self.SCREEN_HEIGHT * 0.7888),
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
        full_img = self._grab_screen_full()
        if full_img is None:
            self.set_status("Failed to grab full screen")
            return
        # Save full screenshot for debugging
        try:
            cv2.imwrite(os.path.join(BASE_PATH, "debug_full.png"), full_img)
        except Exception as e:
            self.set_status(f"Error saving full screenshot: {e}")
        # Helper To Crop 
        def crop(img, rect):
            l, t, r, b = rect
            # Convert logical -> physical on macOS Retina
            if sys.platform == "darwin":
                scale = self._get_scale_factor()
                l = int(l * scale)
                t = int(t * scale)
                r = int(r * scale)
                b = int(b * scale)
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
    # Grab Screen And Apply Scale Factor
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
    def _invalidate_scale_cache(self):
        """Force _get_scale_factor to re-query on next call (e.g. window moved to another monitor)."""
        self._scale_cache = None
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
            # Crop manually for coordinate consistency
            frame = frame[0:height, 0:width]
            return frame.copy()
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
        stop_event = threading.Event()
        self._active_capture_stop = stop_event  # Track the active stop event
        # Enforce minimum frame rate on macOS to prevent CPU saturation
        _mac_floor = 0.033 if sys.platform == "darwin" else 0.001  # 30 FPS floor on macOS, 1ms on others
        def _loop():
            """Background capture thread loop with proper sleep logic to prevent busy-waiting."""
            try:
                thread_local = threading.local()
                while self.macro_running and not stop_event.is_set():
                    t0 = time.perf_counter()
                    frame = self._grab_screen_full(thread_local)
                    # Update shared frame buffer
                    with self._cap_lock:
                        self._cap_frame = frame
                        self._cap_event.set()
                    # Calculate how long to sleep to maintain target frame rate
                    elapsed = time.perf_counter() - t0
                    target_frame_time = max(_mac_floor, scan_delay)
                    sleep_for = target_frame_time - elapsed
                    # CRITICAL FIX: Always sleep at least a tiny amount to prevent busy-loop
                    # This prevents 50% CPU usage when capture is faster than target rate
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                    elif sleep_for > -0.001:  # Very close to target, sleep tiny amount
                        time.sleep(0.001)  # Sleep 1ms to yield to other threads
                    # If significantly over target (sleep_for < -0.001), don't sleep but let OS scheduler run
            finally:
                # Clean up thread-local MSS resources
                sct = getattr(thread_local, "sct", None)
                if sct is not None:
                    try:
                        sct.close()
                    except Exception:
                        pass
                # Signal that thread is exiting
                self._cap_event.set()
                # Clear tracking if this is the current capture thread
                if self._active_capture_stop is stop_event:
                    self._active_capture_stop = None
                if self._active_capture_thread is threading.current_thread():
                    self._active_capture_thread = None
        # Start capture thread as daemon so it doesn't block shutdown
        thread = threading.Thread(target=_loop, daemon=True, name="PyWareCapture")
        self._active_capture_thread = thread
        thread.start()
        return stop_event
    # Pixel And Image Search
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
    def _find_vertical_bar_edges(
        self,
        frame,
        top_hex,
        bottom_hex,
        tolerance=15,
        tolerance2=15,
        scan_width_ratio=0.5
    ):
        """
        Reverse version of _find_bar_edges().
        Scans vertically instead of horizontally:
        - Finds TOP edge using top_hex
        - Finds BOTTOM edge using bottom_hex
        """
        if frame is None:
            return None, None
        if frame.size == 0 or frame.ndim < 2:
            return None, None
        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return None, None
        # Scan vertical column instead of horizontal row
        x = int(w * scan_width_ratio)
        # Convert To BGR
        top_bgr = np.array(self._hex_to_bgr(top_hex), dtype=np.int32)
        bottom_bgr = np.array(self._hex_to_bgr(bottom_hex), dtype=np.int32)
        # Extract Vertical Scan Line
        column = frame[:, x].astype(np.int32)
        # Clamp Tolerances
        tol_t = int(np.clip(tolerance, 0, 255))
        tol_b = int(np.clip(tolerance2, 0, 255))
        # Top Mask (Euclidean Distance)
        top_diff = column - top_bgr
        top_mask = np.sqrt(np.sum(top_diff ** 2, axis=1)) <= tol_t
        # Bottom Mask (Euclidean Distance)
        bottom_diff = column - bottom_bgr
        bottom_mask = np.sqrt(np.sum(bottom_diff ** 2, axis=1)) <= tol_b
        top_indices = np.where(top_mask)[0]
        bottom_indices = np.where(bottom_mask)[0]
        # Keep Same Edge Logic
        top_edge = int(top_indices[0]) if top_indices.size else None
        bottom_edge = int(bottom_indices[-1]) if bottom_indices.size else None
        return top_edge, bottom_edge
    # Other Calculations
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
    def _update_arrow_box_estimation(self, arrow_centroid_x, capture_width):
        """
        Estimate box position based on arrow indicator using geometry-based logic.
        Determines which side the arrow is on by comparing to last known center position,
        uses proximity validation for self-correction, and falls back to default size if needed.
        Args:
            arrow_centroid_x: X coordinate of arrow center
            capture_width: Width of capture region
        Returns:
            Tuple of (bar_center, left_x, right_x) or (None, None, None) if can't estimate
        """
        # Initialize tracking variables if not already done
        if not hasattr(self, '_last_bar_left_x'):
            self._last_bar_left_x = None
        if not hasattr(self, '_last_bar_right_x'):
            self._last_bar_right_x = None
        if not hasattr(self, '_last_bar_box_size'):
            self._last_bar_box_size = None
        if not hasattr(self, '_last_bar_center'):
            self._last_bar_center = None
        # Handle missing arrow
        if arrow_centroid_x is None:
            # Return last known positions if available
            if self._last_bar_center is not None:
                return self._last_bar_center, self._last_bar_left_x, self._last_bar_right_x
            return None, None, None
        # Get last known values
        last_center = self._last_bar_center
        box_size = self._last_bar_box_size
        # If we have previous bar data, determine which side the arrow is on
        if last_center is not None and box_size is not None and box_size > 0:
            last_left = self._last_bar_left_x
            last_right = self._last_bar_right_x
            # Determine which side based on center comparison
            arrow_on_left_side = arrow_centroid_x < last_center
            # SMART VALIDATION: Check if arrow is actually near the bar we think it is
            # Calculate distances to both last known bars
            dist_to_left = abs(arrow_centroid_x - last_left) if last_left is not None else float('inf')
            dist_to_right = abs(arrow_centroid_x - last_right) if last_right is not None else float('inf')
            # Self-correction: If arrow is much closer to the opposite bar, we detected wrong side!
            # Threshold: arrow should be within reasonable distance (box_size / 4) of expected bar
            proximity_threshold = box_size / 4
            if arrow_on_left_side:
                # We think arrow is on LEFT, but verify it's actually near left bar
                if dist_to_right < dist_to_left and dist_to_right < proximity_threshold:
                    # Arrow is actually closer to RIGHT bar - we were wrong!
                    arrow_on_left_side = False  # Flip the decision
            else:
                # We think arrow is on RIGHT, but verify it's actually near right bar
                if dist_to_left < dist_to_right and dist_to_left < proximity_threshold:
                    # Arrow is actually closer to LEFT bar - we were wrong!
                    arrow_on_left_side = True  # Flip the decision
            # Now apply the corrected decision
            if arrow_on_left_side:
                # Arrow is on the LEFT side - update left bar, keep right bar from memory
                bar_left_x = arrow_centroid_x
                bar_right_x = self._last_bar_right_x
                if bar_right_x is None:
                    # If no right bar in memory, calculate from box size
                    bar_right_x = bar_left_x + box_size
                # Validate: ensure left < right
                if bar_left_x < bar_right_x:
                    self._last_bar_left_x = bar_left_x
                    self._last_bar_right_x = bar_right_x
                    bar_center = (bar_left_x + bar_right_x) / 2.0
                    self._last_bar_center = bar_center
                    return bar_center, bar_left_x, bar_right_x
            else:
                # Arrow is on the RIGHT side - update right bar, keep left bar from memory
                bar_right_x = arrow_centroid_x
                bar_left_x = self._last_bar_left_x
                if bar_left_x is None:
                    # If no left bar in memory, calculate from box size
                    bar_left_x = bar_right_x - box_size
                # Validate: ensure left < right
                if bar_left_x < bar_right_x:
                    self._last_bar_left_x = bar_left_x
                    self._last_bar_right_x = bar_right_x
                    bar_center = (bar_left_x + bar_right_x) / 2.0
                    self._last_bar_center = bar_center
                    return bar_center, bar_left_x, bar_right_x
        # Fallback: Try to establish initial box size from previous positions
        elif self._last_bar_left_x is not None and self._last_bar_right_x is not None:
            box_size = self._last_bar_right_x - self._last_bar_left_x
            last_center = (self._last_bar_left_x + self._last_bar_right_x) / 2.0
            if box_size > 0:
                self._last_bar_box_size = box_size
                self._last_bar_center = last_center
                # Determine side based on arrow position relative to last center
                if arrow_centroid_x < last_center:
                    bar_left_x = arrow_centroid_x
                    bar_right_x = bar_left_x + box_size
                else:
                    bar_right_x = arrow_centroid_x
                    bar_left_x = bar_right_x - box_size
                self._last_bar_left_x = bar_left_x
                self._last_bar_right_x = bar_right_x
                bar_center = (bar_left_x + bar_right_x) / 2.0
                self._last_bar_center = bar_center
                return bar_center, bar_left_x, bar_right_x
            else:
                # Invalid box size (<=0) - use default based on capture width
                default_box_size = capture_width // 2
                bar_left_x = arrow_centroid_x
                bar_right_x = bar_left_x + default_box_size
                self._last_bar_left_x = bar_left_x
                self._last_bar_right_x = bar_right_x
                self._last_bar_box_size = default_box_size
                bar_center = (bar_left_x + bar_right_x) / 2.0
                self._last_bar_center = bar_center
                return bar_center, bar_left_x, bar_right_x
        else:
            # No previous data - assume a default box size based on capture width
            default_box_size = capture_width // 2
            # Start with arrow as left bar, calculate right from default size
            bar_left_x = arrow_centroid_x
            bar_right_x = bar_left_x + default_box_size
            # Clamp to capture bounds
            if bar_right_x > capture_width:
                bar_right_x = float(capture_width)
                bar_left_x = max(0.0, bar_right_x - default_box_size)
            # Save these initial estimates
            self._last_bar_left_x = bar_left_x
            self._last_bar_right_x = bar_right_x
            self._last_bar_box_size = default_box_size
            bar_center = (bar_left_x + bar_right_x) / 2.0
            self._last_bar_center = bar_center
            return bar_center, bar_left_x, bar_right_x
    # Get Values From Gui
    def _get_areas(self, area_key):
        # Apply Scale Factor
        scale = self._get_scale_factor()
        # FIX: Avoid mutating 'area_key' parameter tracking variable
        area_data = self.bar_areas.get(area_key)
        if isinstance(area_data, dict):
            left   = area_data["x"]
            top    = area_data["y"]
            right  = area_data["x"] + area_data["width"]
            bottom = area_data["y"] + area_data["height"]
            width  = area_data["width"]
            height = area_data["height"]
        else:
            # Passes original string key securely to fallback definition handler
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
            left = int(self.SCREEN_WIDTH * 0.45)
            top = int(self.SCREEN_HEIGHT * 0.2)
            right = int(self.SCREEN_WIDTH * 0.55)
            bottom = int(self.SCREEN_HEIGHT * 0.5)
        return left, top, right, bottom
    def _get_overlay_anchor_area(self, area_name):
        left, top, right, bottom, _, _ = self._get_areas(area_name)
        return left, top, right, bottom
    def _build_horizontal_overlay_layout(self, area_bounds):
        left, top, right, bottom = area_bounds
        width = max(60, right - left)
        height = max(36, bottom - top)
        x = left
        above_y = top - height
        below_y = bottom
        y = above_y if above_y >= 0 else below_y
        return x, y, width, height
    def _build_side_overlay_layout(self, area_bounds):
        left, top, right, bottom = area_bounds
        width = max(60, right - left)
        height = max(36, bottom - top)
        center_y = int((top + bottom) / 2)
        left_x = left - width
        right_x = right
        space_left = left
        space_right = self.SCREEN_WIDTH - right
        x = right_x if space_right >= width or space_right >= space_left else left_x
        y = center_y - int(height / 2)
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
            # Use the detected cast bounds if available to size/position the overlay
            if self._fish_overlay_cast_bounds is not None:
                cast_left, cast_top, cast_right, cast_bottom = self._fish_overlay_cast_bounds
                cast_center_x = (cast_left + cast_right) / 2
                cast_height = max(36, cast_bottom - cast_top)
                overlay_height = cast_height
                y = cast_top
            # Cast on left half → overlay on right side; cast on right half → overlay on left side
            if cast_center_x <= shake_center_x:
                x = shake_right
            else:
                x = shake_left - overlay_width
            return x, y, overlay_width, overlay_height
        if mode == "fishing":
            x, y, overlay_width, overlay_height = self._build_horizontal_overlay_layout(self._get_overlay_anchor_area("fish"))
            half_height = int(self.SCREEN_HEIGHT / 2)
            y = y - 80 if y > half_height else y + 80
            return x, y, overlay_width, overlay_height
        return self._build_horizontal_overlay_layout(self._get_overlay_anchor_area("friend"))
    def _is_fish_overlay_enabled(self):
        var = self.vars.get("fish_overlay")
        return bool(var and var.get() == "on")
    def _apply_fish_overlay_state(self):
        if not self._is_fish_overlay_enabled():
            self.fish_overlay.hide()
            self.status_overlay.hide()
            return
        x, y, width, height = self._get_fish_overlay_layout()
        self.fish_overlay.set_layout(x, y, width, height)
        self.fish_overlay.show()
        self.status_overlay.show()
    def _set_fish_overlay_mode(self, mode):
        self._fish_overlay_mode = mode
        self._apply_fish_overlay_state()
    def _on_fish_overlay_toggle(self, *args):
        self._apply_fish_overlay_state()
    def _on_always_on_top_toggle(self, *args):
        enabled = self.vars["always_on_top"].get()
        self.attributes("-topmost", enabled == "on")
    # Do Pixel/Image/Line Search
    def _do_pixel_search(self, frame):
        fish_hex = self.vars["fish_color"].get()
        left_bar_hex = self.vars["left_color"].get()
        right_bar_hex = self.vars["right_color"].get()
        try: # Handle Nonetype and int properly
            left_tol = int(self.vars["left_tolerance"].get() or 8)
            right_tol = int(self.vars["right_tolerance"].get() or 8)
            fish_tol = int(self.vars["fish_tolerance"].get() or 1)
            required_fish_pixels = int(self.vars["required_fish_pixels"].get() or 10)
        except:
            left_tol = 8
            right_tol = 8
            fish_tol = 1
            required_fish_pixels = 10
        # macOS Tolerance Buffer To Make Configs Cross-Compatible
        if sys.platform == "darwin":
            left_tol += 2
            right_tol += 2
            fish_tol += 2
        fish_center, = self._find_color_cluster(frame, fish_hex, fish_tol, required_fish_pixels)
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
    # Controllers (PID And Stopping Distance)
    def _get_pid_gains(self):
        """Get PID gains from config, with sensible defaults."""
        try:
            kp = float(self.vars["proportional_gain"].get() or 0.6)
            kd = float(self.vars["derivative_gain"].get() or 0.6)
        except:
            kp = 0.6
            kd = 0.6
        return kp, kd
    def _pid_control(self, error, bar_center=None):
        """
        Compute PD output using proportional gain system from Hydra reference.
        Uses velocity-based derivative with asymmetric damping.
        """
        now = time.perf_counter()
        pd_clamp = float(self.vars["pid_clamp"].get() or 100)
        # First Sample: Initialize State And Return Zero Control
        if self._pid_last_scan_time is None:
            self._pid_last_scan_time = now
            self._pid_last_error = error
            if bar_center is not None:
                self.last_bar_x = bar_center
            return 0.0
        dt = now - self._pid_last_scan_time
        if dt <= 0:
            return 0.0
        kp, kd = self._get_pid_gains()
        # P Term - Proportional To How Far We Need To Move
        p_term = kp * error
        # D Term - Asymmetric Damping Based On Situation
        d_term = 0.0
        if bar_center is not None and self.last_bar_x is not None and dt > 0:
            bar_velocity = (bar_center - self.last_bar_x) / dt
            error_magnitude_decreasing = abs(error) < abs(self._pid_last_error) if self._pid_last_error is not None else False
            bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
            damping_multiplier = 5.0 if (error_magnitude_decreasing and bar_moving_toward_target) else 0.2
            d_term = -kd * damping_multiplier * bar_velocity
        else:
            # Fallback To Standard Derivative
            if self._pid_last_error is not None and dt > 0:
                d_term = kd * (error - self._pid_last_error) / dt
        # Combined Control Signal (Pd Controller Output)
        control_signal = p_term + d_term
        control_signal = max(-pd_clamp, min(pd_clamp, control_signal))  # Clamp Output
        # Update History
        self._pid_last_error = error
        self._pid_last_scan_time = now
        if bar_center is not None:
            self.last_bar_x = bar_center
        return control_signal
    def _reset_control_state(self):
        """Reset controller(s) memory without touching bar estimation state."""
        # Core Pid Error + Timing State + State Variables (All Used By _Pid_Control Method)
        self._pid_last_error = 0.0          # Prevents Derivative Kick
        self._pid_last_scan_time = None          # Forces Fresh Dt On Next Frame
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
        self.color_check_target_velocity = 0.0
        self.color_check_bar_velocity  = 0.0
        self._pred_last_click_time = 0.0
    def _reset_pid_memory(self):
        """Reset only the live PD history used for the next bar-alignment step."""
        self._pid_last_error = 0.0
        self._pid_last_scan_time = None
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
        stopping_distance_multiplier, velocity_smoothing = self._get_pid_gains()
        stopping_distance_multiplier = stopping_distance_multiplier * 1.5
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
    # Main Macro Loop
    def start_macro(self):
        self.macro_running = True # Flag To Control Macro Loop And Allow Safe Stopping
        # Get Shake Area For Mouse Movement Areas
        shake_left, shake_top, shake_right, shake_bottom, shake_width, shake_height = self._get_areas("shake")
        shake_x = shake_left + int(shake_width / 2)
        shake_y = shake_top + int(shake_height / 2)
        self._reset_pid_state()
        self.set_status("Macro Status: Running")
        # Reset Logging And Totem Counters For This Run
        self.webhook_cycle_counter = 0
        self.webhook_start_time = time.time()
        self.totem_cycle_counter = 0
        self.totem_start_time = time.time()
        self.macro_start_time = time.time()
        self.macro_timer = "0h 0m"
        # Retrieve Variables From Gui
        rod_slot = str(self.vars["rod_slot"].get())
        bag_slot = str(self.vars["bag_slot"].get())
        bait_delay = float(self.vars["bait_delay"].get())
        click_after_minigame = (self.vars["click_after_minigame"].get())
        self.status_overlay.set_line(f"Made by Catman2608", row=1)
        self.status_overlay.set_line(f"Process: Auto Zoom", row=2)
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
                self._set_fish_overlay_mode("idle")
                phase = "Misc/Totem"
                _elapsed = int(time.time() - self.macro_start_time)
                self.macro_timer = f"{_elapsed // 3600}h {(_elapsed % 3600) // 60}m"
                self.status_overlay.set_line(f"Time: {self.macro_timer}", row=1)
                # Totem
                self.status_overlay.set_line(f"Process: Auto Totem", row=2)
                self._check_totem_trigger(shake_x, shake_y)
                # Reconnect
                self.status_overlay.set_line(f"Process: Auto Reconnect", row=2)
                if self.vars["auto_reconnect"].get() == "on":
                    self._auto_reconnect(shake_x, shake_y)
                # Select Rod
                self.status_overlay.set_line(f"Process: Auto Refresh", row=2)
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
                # Cast
                phase = "Casting"
                self.set_status("Casting")
                if self.vars["casting_mode"].get() == "Perfect":
                    self.status_overlay.set_line(f"Process: Casting (Perfect)", row=2)
                    self._execute_cast_perfect()
                else:
                    self.status_overlay.set_line(f"Process: Casting (Normal)", row=2)
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
                phase = "Shaking"
                self.set_status("Shaking")
                try:
                    shake_mode = self.vars["shake_mode"].get()
                except:
                    shake_mode = "Navigation"
                if shake_mode == "Click":
                    self.status_overlay.set_line(f"Process: Shaking (Click)", row=2)
                    self._execute_shake_click()
                else:
                    self.status_overlay.set_line(f"Process: Shaking (Navigation)", row=2)
                    self._execute_shake_navigation()
                if not self.macro_running:
                    break
                # Fish (Minigame)
                self.set_status("Fishing")
                phase = "Fishing"
                time.sleep(bait_delay)
                self.status_overlay.set_line(f"Process: Minigame", row=2)
                self._enter_minigame()
                # Utilities at the bottom
                self.status_overlay.set_line(f"Process: Other Utilities", row=2)
                self._check_logging_trigger()
                if click_after_minigame == "on":
                    self._click_at(shake_x, shake_y)
                # Restart: When Minigame Ends, Loop Repeats From Select Rod
        except Exception as e:
            error_text = traceback.format_exc()
            error_message = str(e).strip()
            if error_message.startswith("Macro crashed during "):
                phase = error_message[len("Macro crashed during "):].split(":", 1)[0].strip() or phase
            self._auto_bug_report(error_text, phase)
            if not self.macro_running:
                return
            self.macro_running = False
            self._reset_pid_state()
            self.after(0, self.deiconify)  # Show Window Safely
            self.set_status(f"Macro crashed during {phase}: {e}")
            if IS_COMPILED == True:
                if sys.platform == "win32":
                    messagebox.showerror(f"Macro crashed during {phase}", f"Error: {e}")
                else:
                    messagebox.showerror("why are you here", f"Macro crashed during {phase}\nError: {e}")
            else: # Explicitly Reveal The Bug And The Traceback During Development
                raise ValueError("Bug found during development") from e
    def _check_logging_trigger(self):
        """Check whether the Logging should fire based on the selected mode.
        Modes (logging_trigger):
          Cycles  – fire every N completed cycles (configurable via logging_cycle)
          Time    – fire every N seconds elapsed  (configurable via logging_time)
          Disabled – never fire
        """
        cd_mode = self.vars["logging_trigger"].get()
        if cd_mode == "Disabled":
            return  # webhook type is disabled; do nothing
        try:
            trigger_every = int(self.vars["logging_cycle"].get())
        except (ValueError, KeyError):
            trigger_every = 3  # safe fallback
        try:
            trigger_secs = float(self.vars["logging_time"].get())
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
        mode = self.vars["auto_totem_mode"].get()
        # self.SCREEN_SCALE
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
            self.send_logging(
                "Totem used successfully",
                self.totem_cycle_counter,
                show_status=False
            )
    def _auto_reconnect(self, center_x, center_y):
        reconnect_threshold = int(self.vars["reconnect_threshold"].get())
        reconnect_wait_time = int(self.vars["reconnect_wait_time"].get())
        mirror_ratio = float(self.vars["mirror_ratio"].get())
        mirror_ratio2 = float(self.vars["mirror_ratio2"].get())
        mirror_slot = str(self.vars["mirror_slot"].get())
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
    def _execute_cast_normal(self):
        """Hold left click for user cast delay"""
        # Get Variables
        delay2 = float(self.vars["delay_before_casting"].get() or 0.0)
        duration = float(self.vars["cast_duration"].get() or 0.6)
        delay = float(self.vars["cast_delay"].get() or 0.2)
        self.status_overlay.set_line(f"Casting for {duration} seconds", row=3)
        # Set Status
        time.sleep(delay2)  # Wait For Cast To Register In Other Games
        mouse_controller.press(Button.left)
        time.sleep(duration)  # Adjust Cast Strength
        mouse_controller.release(Button.left)
        time.sleep(delay)  # Wait For Cast To Register In Fisch
    @staticmethod
    def _calculate_speed_and_predict(white_positions, timestamps):
        """
        Calculate white pixel movement speed using linear regression on recent
        positions for smooth, stable velocity estimation.
        Returns velocity in pixels/second (positive = moving down, negative = up),
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
    def _execute_cast_perfect(self):
        """
        Scans for green and white Y coordinates and releases left click when
        the top white Y reaches 95% of the area from green Y to bottom white Y.
        """
        # Hold Mouse
        mouse_controller.press(Button.left)
        # Get Areas (Scale Factor Applied Inside _Get_Areas)
        shake_left_s, shake_top_s, shake_right_s, shake_bottom_s, _, shake_height = self._get_areas("shake")
        # Set overlay to casting mode — bounds will be refined once green/white are detected
        self._fish_overlay_cast_bounds = None
        self._set_fish_overlay_mode("casting")
        # Config 
        white_color = self.vars["perfect_color2"].get()
        green_color = self.vars["perfect_color"].get()
        white_tol = int(self.vars["perfect_cast2_tolerance"].get())
        green_tol = int(self.vars["perfect_cast_tolerance"].get())
        max_time = float(self.vars["perfect_max_time"].get())
        scan_delay = float(self.vars["cast_scan_delay"].get())
        delay_before_casting = float(self.vars["delay_before_casting"].get())
        cast_delay = float(self.vars["cast_delay"].get())
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
        if self.vars["fish_overlay"].get() == "Enabled":
            self.fish_overlay.show()
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
            self.status_overlay.set_line(f"Green Y: {green_y}", row=3)
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
            # Update cast overlay bounds from detected green (left/top) and white (right/bottom)
            cast_left   = shake_left_s + green_left_x
            cast_top    = shake_top_s  + green_y
            cast_right  = shake_left_s + green_right_x
            cast_bottom = shake_top_s  + white_y_bottom
            if self._fish_overlay_cast_bounds != (cast_left, cast_top, cast_right, cast_bottom):
                self._fish_overlay_cast_bounds = (cast_left, cast_top, cast_right, cast_bottom)
                self.after(0, self._apply_fish_overlay_state)
            # --- Overlay ---
            if self._is_fish_overlay_enabled():
                cast_height = max(1, white_y_bottom - green_y)
                green_ratio = 0.0
                white_ratio = current_distance / cast_height
                white_ratio = max(0.0, min(1.0, white_ratio))
                draw_x = self.fish_overlay.width / 2
                bar_height = 0.08
                self.after(0, lambda: self.fish_overlay.draw(
                    bar_center=draw_x, box_size=15, color="green", canvas_offset=0,
                    bar_y1=max(0.0, green_ratio - bar_height / 2),
                    bar_y2=min(1.0, green_ratio + bar_height / 2)
                ))
                self.after(0, lambda: self.fish_overlay.draw(
                    bar_center=draw_x, box_size=30, color="white", canvas_offset=0,
                    bar_y1=max(0.0, white_ratio - bar_height / 2),
                    bar_y2=min(1.0, white_ratio + bar_height / 2)
                ))
            # --- Velocity tracking ---
            now_pc = time.perf_counter()
            white_positions.append((0, white_y_top))   # x is irrelevant; track Y only
            white_timestamps.append(now_pc)
            if len(white_positions) > MAX_VELOCITY_SAMPLES:
                white_positions.pop(0)
                white_timestamps.pop(0)
            self.status_overlay.set_line(f"White Y: {white_y_top}", row=4)
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
                                timing_key = "perfect_cast_timing_1600plus"
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
        # Cast ended — return overlay to idle (friend area)
        self._fish_overlay_cast_bounds = None
        self._set_fish_overlay_mode("idle")
    def _execute_shake_click(self):
        """
        Search for first shake pixel then click
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
        bar_hex = self.vars["left_color"].get()
        scan_delay = float(self.vars["shake_scan_delay"].get())
        try:
            tolerance = int(self.vars["shake_tolerance"].get())
            failsafe = int(self.vars["shake_failsafe"].get() or 80)
            bar_tolerance = int(self.vars["left_tolerance"].get())
            shake_clicks = int(self.vars["shake_clicks"].get())
        except:
            tolerance = 5
            failsafe = 80
            bar_tolerance = 8
            shake_clicks = 1
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
            if shake_area is None or shake_area.size == 0:
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
                if detection_area is None or detection_area.size == 0:
                    break
                if detection_method == "Friend Area":
                    friend_x = self._find_color_center(detection_area, "#9BFF9B", tolerance)
                fish_x = self._find_color_cluster(detection_area, fish_hex, tolerance, required_fish_pixels)
                bar_x = self._find_color_center(detection_area, bar_hex, bar_tolerance)
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
        """Spams the enter key until fish detection is found"""
        self.set_status("Shake Mode: Navigation")
        # Get areas (scale factor applied inside _get_areas)
        fish_left_s, fish_top_s, fish_right_s, fish_bottom_s, _, _         = self._get_areas("fish")
        friend_left_s, friend_top_s, friend_right_s, friend_bottom_s, _, _ = self._get_areas("friend")
        # Misc variables
        fish_hex = self.vars["fish_color"].get()
        scan_delay = float(self.vars["shake_scan_delay"].get())
        detection_method = (self.vars["detection_method"].get())
        bar_hex = self.vars["left_color"].get() # Left bar color replaced by left color
        try:
            tolerance = int(self.vars["shake_tolerance"].get())
            failsafe = int(self.vars["shake_failsafe"].get() or 80)
            bar_tolerance = int(self.vars["left_tolerance"].get())
            required_fish_pixels = int(self.vars["required_fish_pixels"].get() or 10)
        except:
            tolerance = 5
            failsafe = 80
            bar_tolerance = 8
            required_fish_pixels = 10
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
                if detection_area is None or detection_area.size == 0:
                    break
                if detection_method == "Friend Area":
                    friend_x = self._find_color_center( detection_area, "#9BFF9B", tolerance )
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
        # Set overlay to fishing mode (top of fish area)
        self._set_fish_overlay_mode("fishing")
        # Get All 3 Areas
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._get_areas("shake")
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_left, fish_top, fish_right, fish_bottom, fish_width, _ = self._get_areas("fish")
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
        bar_ratio = float(self.vars["left_ratio"].get() or 0.5)
        pid_clamp = float(self.vars["pid_clamp"].get() or 100)
        restart_method = (self.vars["restart_method"].get())
        restart_delay = float(self.vars["restart_delay"].get())
        track_notes = self.vars["track_notes"].get()
        note_box_hex = self.vars["note_box_color"].get()
        note_track_ratio = float(self.vars["note_track_ratio"].get() or 0.1)
        scan_delay = float(self.vars["minigame_scan_delay"].get() or 0.05)
        lock_cursor = (self.vars["lock_cursor"].get())
        fishing_mode = (self.vars["fishing_mode"].get())
        if fishing_mode == "Line":
            bar_ratio = self._get_var_number("fish_line_bar_ratio", 0.45)
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
            note_box_tol = int(self.vars["note_box_tolerance"].get() or 8)
            arrow_tol = int(self.vars["arrow_tolerance"].get() or 8)
            arrow_method = int(self.vars["arrow_method"].get())
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
            # Step 1: Grab Full Screen Then Crop (better on macOS)
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
            self.status_overlay.set_line(f"Fishing Mode: {fishing_mode}", row=3)
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
                self.status_overlay.set_line(f"Detection source: Bars", row=4)
                detection_source = 0
            else:
                capture_width = fish_right - fish_left
                if arrow_method == 2:
                    bar_center, left_x, right_x = self._update_arrow_box_estimation(arrow_indicator_x, capture_width)
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
                self.status_overlay.set_line(f"Detection source: Arrows", row=4)
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
                        self._last_bar_center = (left_x + right_x) / 2.0
            # Tracking threshold and Stabilize Threshold is auto calculated
            tracking_threshold = (0 - round(((bar_size / fish_width) - 0.5), 2)) * 33 
            thresh = (0 - round((bar_size / fish_width), 2)) * 15
            # Fish Direction-Jump Rejection
            if fish_x is not None:
                if self.last_fish_x is not None and abs(fish_x - self.last_fish_x) > 200:
                    # Outlier Frame — Discard And Reuse Cached Value
                    fish_x = self.last_fish_x
                else:
                    # Accept This Frame And Update Cache
                    self.last_fish_x = fish_x
                self.last_fish_x = fish_x
            # Step 4: Restart Method And Cache
            if restart_method == "Friend Area":
                friend_x = self._find_color_center(friend_img, "#9BFF9B", 2)
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
                self.after(0, lambda _bc=bar_center, _bs=bar_size, _fl=fish_left: self.fish_overlay.draw(bar_center=_bc, box_size=_bs, 
                                                                                                         color="green", canvas_offset=_fl, show_bar_center=True))
                self.after(0, lambda _ml=max_left, _fl=fish_left: self.fish_overlay.draw(bar_center=_ml, box_size=15, color="lightblue", canvas_offset=_fl))
                self.after(0, lambda _mr=max_right, _fl=fish_left: self.fish_overlay.draw(bar_center=_mr, box_size=15, color="lightblue", canvas_offset=_fl))
                self.after(0, lambda: self.fish_overlay.draw(bar_center=fish_x, box_size=10, color="red", canvas_offset=fish_left))
            # Step 7: Controller
            mode_changed = controller_mode != previous_controller_mode
            error = round(fish_x - bar_center) if bar_center is not None and fish_x is not None else 0
            self.status_overlay.set_line(f"Distance: {error}", row=5)
            if controller_mode == 0 and bar_center is not None:
                if source_changed or mode_changed:
                    # Re-entering PD after a chase/reacquire frame can reuse stale
                    # error and velocity history, which causes a one-frame overshoot.
                    self._reset_pid_memory()
                control = self._pid_control(error, bar_center)
                # Map Pid Output To Mouse Clicks Using Hysteresis To Avoid Jitter/Oscillation
                control = max((0 - pid_clamp), min(pid_clamp, control))
                self.status_overlay.set_line(f"Distance: {round(control)}", row=5)
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
            time.sleep(scan_delay)
    def stop_macro(self):
        if not self.macro_running:
            return
        self.macro_running = False
        self._reset_pid_state()
        self._fish_overlay_cast_bounds = None
        self._set_fish_overlay_mode("idle")
        self.after(0, self.deiconify)  # Show Window Safely
        self.set_status("Macro Status: Stopped")
if __name__ == "__main__":
    app = App()
    app.mainloop()