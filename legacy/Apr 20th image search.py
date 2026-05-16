# GUI-related
from customtkinter import *
import tkinter as tk
from tkinter import messagebox
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
# Ctypes/Quartz for special click types
if sys.platform == "win32":
    import ctypes # Windows
    import ctypes as Quartz # Used to disable quartz on Windows
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
elif sys.platform == "darwin":
    import Quartz # If you're on macOS remove the first hashtag
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
# Config directory
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()

# - SINGLE SOURCE OF TRUTH -
if getattr(sys, 'frozen', False):
    # Running as compiled app
    if sys.platform == "darwin":
        USER_CONFIG_DIR = os.path.join(
            os.path.expanduser("~"),
            "Library", "Application Support",
            "PyWareAutomateV1", "configs"
        )
    elif sys.platform == "win32":
        USER_CONFIG_DIR = os.path.join(
            os.path.expanduser("~"),
            "AppData", "Roaming",
            "PyWareAutomateV1", "configs"
        )
    else:
        USER_CONFIG_DIR = os.path.join(BASE_PATH, "configs")
else:
    # Development mode
    USER_CONFIG_DIR = os.path.join(BASE_PATH, "configs")

os.makedirs(USER_CONFIG_DIR, exist_ok=True)
# Area Selector class
class TripleAreaSelector:
    HANDLE_SIZE = 8
    def __init__(self, parent, shake_area, fish_area, friend_area, callback):
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

        self.draw_area(self.shake, "#ff007a")
        self.draw_area(self.fish, "#00daff")
        self.draw_area(self.friend, "#f7ff00")

    def draw_area(self, area, color):

        x1 = area["x"]
        y1 = area["y"]
        x2 = x1 + area["width"]
        y2 = y1 + area["height"]

        self.canvas.create_rectangle(x1, y1, x2, y2, 
                                     outline=color, width=3, 
                                     fill=color, stipple="gray25")

        for x, y in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]:
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
        handles = { "nw": (x1,y1), "ne": (x2,y1), 
                   "sw": (x1,y2), "se": (x2,y2) }
        for name,(hx,hy) in handles.items():

            if abs(x-hx) <= self.HANDLE_SIZE and abs(y-hy) <= self.HANDLE_SIZE:
                return name

        return None
    # Detect mouse input from user
    def mouse_down(self, e):
        self.start_x = e.x
        self.start_y = e.y

        for area,name in [(self.fish,"fish"),(self.shake,"shake"),(self.friend,"friend")]:

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
        for area in [self.fish,self.shake,self.friend]:
            handle = self.get_handle(e.x,e.y,area)
            if handle:
                cursor = {
                    "nw":"size_nw_se",
                    "se":"size_nw_se",
                    "ne":"size_ne_sw",
                    "sw":"size_ne_sw"
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
        self.callback(self.shake,self.fish,self.friend)
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

        # Hotkey variables
        self.hotkey_start = Key.f5
        self.hotkey_stop = Key.f7
        self.hotkey_change_areas = Key.f6 # added for the bar area selector
        self.hotkey_screenshot = Key.f8
        self.hotkey_labels = {}  # Store label widgets for dynamic updates

        # Macro state
        self.macro_running = False
        self.macro_thread = None

        # Safe defaults before key listener starts (will be overwritten by load_misc_settings)
        self.bar_areas = {"shake": None, "fish": None, "friend": None}
        self.current_rod_name = "Basic Rod"

        # Screen capture variables — MSS instances are per-thread (see _thread_local)
        self._thread_local = threading.local()
        self._monitor = {}      # pre-allocated monitor dict, reused every grab
        self._scale_cache = None  # cached DPI scale factor

        # Buffer for capture/logic thread decoupling (used in start_macro())
        self._cap_lock = threading.Lock()
        self._cap_frame = None    # latest full screen frame
        self._cap_event = threading.Event()  # signals a new frame pair is ready

        # Invalidate scale cache if the window moves to a different monitor
        if sys.platform == "darwin":
            self.bind("<Configure>", lambda e: self._invalidate_scale_cache())
            
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
            corner_radius=32,
            command=self.open_link("https://sites.google.com/view/icf-automation-network/")
        ).pack(side="left", padx=6)

        CTkButton(
            button_frame,
            text="Upcoming Features",
            corner_radius=32,
            command=self.open_link("https://docs.google.com/document/d/1WwWWMR-eN-R-GO42IioToHpWTgiXkLoiNE_4NeE-GsU/edit?tab=t.0")
        ).pack(side="left", padx=6)

        CTkButton(
            button_frame,
            text="Tutorial",
            corner_radius=32,
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
        self._apply_hotkeys_from_vars()   # Completed: ADD THIS

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

        CTkButton(basic_settings, text="Open Configs Folder", corner_radius=10, 
                  command=self.open_configs_folder
                  ).grid(row=2, column=0, padx=12, pady=12, sticky="w")

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
        fish_tolerance_var = StringVar(value="0")
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
        perfect_cast_tolerance_var = StringVar(value="14")
        self.vars["perfect_cast_tolerance"] = perfect_cast_tolerance_var
        perfect_cast_tolerance_entry = CTkEntry(color_settings, width=120, textvariable=perfect_cast_tolerance_var)
        perfect_cast_tolerance_entry.grid(row=8, column=3, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Casting:").grid(row=9, column=0, padx=12, pady=10, sticky="w")
        perfect_color2_var = StringVar(value="#d4d3ca")
        self.vars["perfect_color2"] = perfect_color2_var
        CTkEntry(color_settings, width=120, textvariable=perfect_color2_var).grid(row=9, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(color_settings, text="Tolerance:").grid(row=9, column=2, padx=12, pady=10, sticky="w")
        perfect_cast2_tolerance_var = StringVar(value="12")
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
        CTkLabel(self.normal_casting, text="Normal Casting Options", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
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

        CTkLabel(self.perfect_casting, text="Perfect Casting Options", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        CTkLabel(self.perfect_casting, text="Perfect Cast Scan FPS:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        cast_scan_delay_var = StringVar(value="0.05")
        self.vars["cast_scan_delay"] = cast_scan_delay_var
        cast_scan_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=cast_scan_delay_var)
        cast_scan_delay_entry.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        CTkLabel(self.perfect_casting, text="Failsafe Release Timeout:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        perfect_max_time_var = StringVar(value="3.5")
        self.vars["perfect_max_time"] = perfect_max_time_var
        perfect_max_time_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_max_time_var)
        perfect_max_time_entry.grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(self.perfect_casting, text="Perfect Cast Release Method:").grid(row=3, column=0, padx=12, pady=10, sticky="w" )
        release_method_var = StringVar(value="Simple")
        self.vars["release_method"] = release_method_var
        release_method_cb = CTkComboBox(self.perfect_casting, values=["Velocity-based", "Simple"], 
                               variable=release_method_var, command=lambda v: self.set_status(f"Perfect Cast Release Method: {v}")
                               )
        release_method_cb.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["release_method"] = release_method_cb

        CTkLabel(self.perfect_casting, text="Perfect Cast Release Delay:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        perfect_release_delay_var = StringVar(value="0")
        self.vars["perfect_release_delay"] = perfect_release_delay_var
        perfect_release_delay_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_release_delay_var)
        perfect_release_delay_entry.grid(row=4, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(self.perfect_casting, text="Perfect Cast Threshold (pixels):").grid(row=5, column=0, padx=12, pady=10, sticky="w")
        perfect_threshold_var = StringVar(value="30")
        self.vars["perfect_threshold"] = perfect_threshold_var
        perfect_threshold_entry = CTkEntry(self.perfect_casting, width=120, textvariable=perfect_threshold_var)
        perfect_threshold_entry.grid(row=5, column=1, padx=12, pady=10, sticky="w")

        shake_configuration = CTkFrame(scroll, border_width=2)
        shake_configuration.grid(row=3, column=0, padx=20, pady=20, sticky="nw")
        # Shake Configuration
        CTkLabel(shake_configuration, text="Shake Configuration", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
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

        CTkLabel(shake_configuration, text="Detection Method:").grid(row=4, column=0, padx=12, pady=10, sticky="w" )
        detection_method_var = StringVar(value="Fish")
        self.vars["detection_method"] = detection_method_var
        detection_cb = CTkComboBox(shake_configuration, values=["Fish", "Fish + Bar", "Friend Area"], 
                               variable=detection_method_var, command=lambda v: self.set_status(f"Detection Method: {v}")
                               )
        detection_cb.grid(row=4, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["detection_method"] = detection_cb
        CTkLabel(shake_configuration, text="Restart Method:").grid(row=5, column=0, padx=12, pady=10, sticky="w" )
        restart_method_var = StringVar(value="Fish")
        self.vars["restart_method"] = restart_method_var
        restart_cb = CTkComboBox(shake_configuration, values=["Fish", "Fish + Bar", "Friend Area"], 
                               variable=restart_method_var, command=lambda v: self.set_status(f"Restart Method: {v}")
                               )
        restart_cb.grid(row=5, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["restart_method"] = restart_cb

        ratio_settings = CTkFrame(scroll, border_width=2)
        ratio_settings.grid(row=4, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(ratio_settings, text="Minigame Timing and Limits", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(ratio_settings, text="Left Ratio From Side:").grid( row=1, column=0, padx=12, pady=10, sticky="w" )
        left_ratio_var = StringVar(value="0.5")
        self.vars["left_ratio"] = left_ratio_var
        CTkEntry( ratio_settings, width=120, textvariable=left_ratio_var ).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Right Ratio From Side:").grid( row=2, column=0, padx=12, pady=10, sticky="w" )
        right_ratio_var = StringVar(value="0.5")
        self.vars["right_ratio"] = right_ratio_var
        CTkEntry( ratio_settings, width=120, textvariable=right_ratio_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Scan Delay (seconds):").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        minigame_scan_delay_var = StringVar(value="0.05")
        self.vars["minigame_scan_delay"] = minigame_scan_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=minigame_scan_delay_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Restart Delay:").grid(row=4, column=0, padx=12, pady=10, sticky="w" )
        restart_delay_var = StringVar(value="1")
        self.vars["restart_delay"] = restart_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=restart_delay_var ).grid(row=4, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Animation Delay (seconds):").grid(row=5, column=0, padx=12, pady=10, sticky="w" )
        bait_delay_var = StringVar(value="0.6")
        self.vars["bait_delay"] = bait_delay_var
        CTkEntry(ratio_settings, width=120, textvariable=bait_delay_var).grid(row=5, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Note Tracking Ratio:").grid(row=6, column=0, padx=12, pady=10, sticky="w")
        note_track_ratio_var = StringVar(value="0.05")
        self.vars["note_track_ratio"] = note_track_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=note_track_ratio_var).grid(row=6, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(ratio_settings, text="Charge Tracking Ratio:").grid(row=7, column=0, padx=12, pady=10, sticky="w")
        charge_track_ratio_var = StringVar(value="0.23")
        self.vars["charge_track_ratio"] = charge_track_ratio_var
        CTkEntry(ratio_settings, width=120, textvariable=charge_track_ratio_var).grid(row=7, column=1, padx=12, pady=10, sticky="w")

        pid_settings = CTkFrame(scroll, border_width=2 )
        pid_settings.grid(row=5, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(pid_settings, text="PD Controller Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(pid_settings, text="Stable KP:").grid(row=1, column=0, padx=12, pady=10, sticky="w")
        p_gain_var = StringVar(value="0.6")
        self.vars["proportional_gain"] = p_gain_var
        CTkEntry(pid_settings, width=120, textvariable=p_gain_var).grid(row=1, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Stable KD:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        d_gain_var = StringVar(value="0.6")
        self.vars["derivative_gain"] = d_gain_var
        CTkEntry(pid_settings, width=120, textvariable=d_gain_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Stabilize Threshold:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        stabilize_threshold_var = StringVar(value="6")
        self.vars["stabilize_threshold"] = stabilize_threshold_var
        CTkEntry(pid_settings, width=120, textvariable=stabilize_threshold_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(pid_settings, text="Stable Clamp:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        pid_clamp_var = StringVar(value="100")
        self.vars["pid_clamp"] = pid_clamp_var
        CTkEntry(pid_settings, width=120, textvariable=pid_clamp_var).grid(row=4, column=1, padx=12, pady=10, sticky="w")

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
                               variable=discord_webhook_mode_var, command=lambda v: self.set_status(f"Auto Totem mode: {v}")
                               )
        discord_webhook_cb.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["discord_webhook_mode"] = discord_webhook_cb

        CTkLabel(discord_webhook, text="Discord Webhook Delays:").grid(row=2, column=0, padx=12, pady=10, sticky="w" )
        discord_webhook_cd_var = StringVar(value="Cycles")
        self.vars["discord_webhook_cd"] = discord_webhook_cd_var
        discord_webhook_cb = CTkComboBox(discord_webhook, values=["Time", "Cycles", "Disabled"], 
                               variable=discord_webhook_cd_var, command=lambda v: self.set_status(f"Auto Totem cd: {v}")
                               )
        discord_webhook_cb.grid(row=2, column=1, padx=12, pady=10, sticky="w")
        self.comboboxes["discord_webhook_cd"] = discord_webhook_cb

        CTkLabel(discord_webhook, text="Webhook URL:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_url_var = StringVar(value="https://discord.com/api/webhooks/XXXXXXXXXX/XXXXXXXXXX")
        self.vars["discord_webhook_url"] = discord_webhook_url_var
        CTkEntry(discord_webhook, width=260, textvariable=discord_webhook_url_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Webhook name:").grid(row=4, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_name_var = StringVar(value="I Can't Fish")
        self.vars["discord_webhook_name"] = discord_webhook_name_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_name_var).grid(row=4, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Trigger on ___ cycles:").grid(row=5, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_cycle_var = StringVar(value="3")
        self.vars["discord_webhook_cycle"] = discord_webhook_cycle_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_cycle_var).grid(row=5, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(discord_webhook, text="Trigger when time hits ___ (seconds):").grid(row=6, column=0, padx=12, pady=10, sticky="w")
        discord_webhook_time_var = StringVar(value="60")
        self.vars["discord_webhook_time"] = discord_webhook_time_var
        CTkEntry(discord_webhook, width=120, textvariable=discord_webhook_time_var).grid(row=6, column=1, padx=12, pady=10, sticky="w")

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
        
        CTkLabel(auto_totem, text="Totem Delay (seconds):").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        totem_delay_var = StringVar(value="900")
        self.vars["totem_delay"] = totem_delay_var
        CTkEntry(auto_totem, width=120, textvariable=totem_delay_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(auto_totem, text="Totem Cycles:").grid(row=3, column=0, padx=12, pady=10, sticky="w")
        totem_cycles_var = StringVar(value="70")
        self.vars["totem_cycles"] = totem_cycles_var
        CTkEntry(auto_totem, width=120, textvariable=totem_cycles_var).grid(row=3, column=1, padx=12, pady=10, sticky="w")

        use_sundial_var = StringVar(value="off")
        self.vars["use_sundial"] = use_sundial_var
        use_sundial_cb = CTkCheckBox(auto_totem, text="Use Sundial if Totem fails", variable=use_sundial_var, onvalue="on", offvalue="off")
        use_sundial_cb.grid(row=4, column=0, padx=12, pady=8, sticky="w")

        CTkLabel(auto_totem, text="Totem Fail Color:").grid(row=5, column=0, padx=12, pady=10, sticky="w")
        totem_color_var = StringVar(value="#7effad")
        self.vars["totem_color"] = totem_color_var
        CTkEntry(auto_totem, width=120, textvariable=totem_color_var).grid(row=5, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(auto_totem, text="Totem Fail Tolerance:").grid(row=6, column=0, padx=12, pady=10, sticky="w")
        totem_tolerance_var = StringVar(value="4")
        self.vars["totem_tolerance"] = totem_tolerance_var
        CTkEntry(auto_totem, width=120, textvariable=totem_tolerance_var).grid(row=6, column=1, padx=12, pady=10, sticky="w")
    
        # Auto Reconnect
        auto_reconnect = CTkFrame(scroll, border_width=2)
        auto_reconnect.grid(row=2, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(auto_reconnect, text="Auto Reconnect", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        auto_reconnect_var = StringVar(value="off")
        self.vars["auto_reconnect"] = auto_reconnect_var
        auto_reconnect_cb = CTkCheckBox(auto_reconnect, text="Auto Reconnect (Roblox)", variable=auto_reconnect_var, onvalue="on", offvalue="off")
        auto_reconnect_cb.grid(row=1, column=0, padx=12, pady=8, sticky="w")
        self.checkboxes["auto_reconnect"] = auto_reconnect_cb
        # Reconnect Link
        CTkLabel(auto_reconnect, text="Reconnect Link:").grid(row=2, column=0, padx=12, pady=10, sticky="w")
        reconnect_link_var = StringVar(value="https://www.roblox.com/games/16732694052/Fisch?privateServerLinkCode=18045795843383847993884150042526")
        self.vars["reconnect_link"] = reconnect_link_var
        CTkEntry(auto_reconnect, width=220, textvariable=reconnect_link_var).grid(row=2, column=1, padx=12, pady=10, sticky="w")

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
        if not os.path.exists(USER_CONFIG_DIR):
            return ["default"]

        folders = [
            name for name in os.listdir(USER_CONFIG_DIR)
            if os.path.isdir(os.path.join(USER_CONFIG_DIR, name))
        ]

        return folders if folders else ["default"]

    def refresh_config_dropdown(self):
        configs = self.get_config_list()
        self.config_dropdown.configure(values=configs)
    def on_config_selected(self, new_name):
        # Save current config BEFORE switching
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
    # Save and load settings
    def save_settings(self, name="default"):
        """Save all settings to a JSON config file."""
        if not os.path.exists(USER_CONFIG_DIR):
            os.makedirs(USER_CONFIG_DIR)
        
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

        config_folder = os.path.join(USER_CONFIG_DIR, name)
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
        path = os.path.join(USER_CONFIG_DIR, name, "config.json")
        
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

        # Save misc settings and show status
        self.load_misc_settings()
        self.set_status(f"Config loaded: {name}")
    
    def load_last_config(self):
        """Load the last used config."""
        last_config_path = os.path.join(USER_CONFIG_DIR, "last_config.json")
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
        last_config_path = os.path.join(USER_CONFIG_DIR, "last_config.json")
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
            path = os.path.join(USER_CONFIG_DIR, "last_config.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    self.current_rod_name = data.get("last_rod", "Basic Rod")
                    self.bar_areas = data.get("bar_areas", {"shake": None, "fish": None, "friend": None})
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
                self.bar_areas = {"fish": None, "shake": None, "friend": None}
        except:
            self.current_rod_name = "Basic Rod"
            self.bar_areas = {"fish": None, "shake": None, "friend": None}
    def save_misc_settings(self):
        """Save misc settings without overwriting last_config."""
        path = os.path.join(USER_CONFIG_DIR, "last_config.json")

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
        for key in ["shake", "fish", "friend"]:
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
            self.open_triple_area_selector()

        elif pressed_key == self._normalize_hotkey_value(self.hotkey_screenshot):
            self._take_debug_screenshot()

        elif pressed_key == self._normalize_hotkey_value(self.hotkey_stop):
            self.stop_macro()
    def set_status(self, text, key=None):
        self.status_label.configure(text=text)
    # Macro helper functions
    def open_configs_folder(self):
        folder = USER_CONFIG_DIR
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", folder])
        else:  # Linux
            subprocess.run(["xdg-open", folder])
    # Area Selector
    def open_triple_area_selector(self):
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
        # Load saved areas or fallback 
        shake_area = (self.bar_areas.get("shake") 
                      if isinstance(self.bar_areas.get("shake"), dict) else default_shake_area())
        fish_area = (self.bar_areas.get("fish") 
                     if isinstance(self.bar_areas.get("fish"), dict) else default_fish_area())
        friend_area = (self.bar_areas.get("friend") 
                       if isinstance(self.bar_areas.get("friend"), dict) else default_friend_area())
        # Callback when user closes selector 
        def on_done(shake, fish, friend):
            self.bar_areas["shake"] = shake
            self.bar_areas["fish"] = fish
            self.bar_areas["friend"] = friend
            self.save_misc_settings()
            self.area_selector = None
        # Open selector 
        self.area_selector = TripleAreaSelector(parent=self, shake_area=shake_area, fish_area=fish_area, friend_area=friend_area, callback=on_done)
        self.set_status("Area selector opened (press key again to close)")
    # HEX to BBBGGGRRR for OpenCV
    def _hex_to_bgr(self, hex_color):
        """
        Convert hex color to BGR tuple for OpenCV.
        
        Args:
            hex_color: Hex color string (e.g., "#FFFFFF")
        
        Returns:
            (B, G, R) tuple or None if invalid
        """
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
        click_mode2 = self.vars["fish_color"].get()
        if click_mode2 == "on":
            mouse_controller.position = (x, y)
            time.sleep(0.01)

            # micro-jitter
            mouse_controller.position = (x + 3, y + 3)
            mouse_controller.position = (x, y)

            mouse_controller.press(Button.left)
            time.sleep(0.04)
            mouse_controller.release(Button.left)
        else:
            if sys.platform == "win32":
                # Move cursor
                windll.SetCursorPos(x, y)
                # Important: tiny movement so Roblox registers input
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
    # Take debug screenshot
    def _take_debug_screenshot(self):
        """
        Capture the configured shake area and save a debug image.
        """
        area = self.bar_areas.get("shake")
        fallback = False
        # Validate the stored area
        try:
                x = int(area.get("x", 0))
                y = int(area.get("y", 0))
                w = int(area.get("width", 0))
                h = int(area.get("height", 0))
        except Exception:
                x   = int(self.SCREEN_WIDTH  * 0.2844)
                y    = int(self.SCREEN_HEIGHT * 0.7981)
                right  = int(self.SCREEN_WIDTH  * 0.7141)
                bottom = int(self.SCREEN_HEIGHT * 0.8370)
                w = right - x
                h = bottom - y
                fallback = True

        if w <= 0 or h <= 0:
            self.set_status("Fish area has nonpositive dimensions")
            return

        # grab the specified region
        img = self._grab_screen_region(x, y, x + w, y + h)
        if img is None:
            self.set_status("Failed to grab fish area")
            return

        try:
            cv2.imwrite("debug_bar.png", img)
            if fallback == True:
                self.set_status("Saved screenshot at default areas (debug_bar.png)")
            else:
                self.set_status("Saved screenshot (debug_bar.png)")
        except Exception as e:
            self.set_status(f"Error saving screenshot: {e}")
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
                tk_dpi = self.winfo_fpixels('1i')   # e.g. 144.0 on Retina
                scale  = tk_dpi / 72.0              # 144/72 = 2.0 on Retina
                scale  = max(1.0, min(4.0, scale))
                self._scale_cache = scale
            except Exception:
                try:
                    main_display  = Quartz.CGMainDisplayID()
                    pixel_width   = Quartz.CGDisplayPixelsWide(main_display)
                    bounds        = Quartz.CGDisplayBounds(main_display)
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

        while self.macro_running and not stop_event.is_set():

            frame = self._grab_screen_full(thread_local)

            with self._cap_lock:
                self._cap_frame = frame
                self._cap_event.set()

            if scan_delay > 0:
                time.sleep(scan_delay)

        self._cap_event.set()
    def _start_capture(self, scan_delay):
        """
        Starts a background thread that continuously grabs full frames.
        Returns a stop_event to terminate it.
        """

        self._cap_frame = None

        # Ensure these exist
        if not hasattr(self, "_cap_lock"):
            self._cap_lock = threading.Lock()
        if not hasattr(self, "_cap_event"):
            self._cap_event = threading.Event()

        self._cap_event.clear()
        stop_event = threading.Event()

        def _loop():
            thread_local = threading.local()

            while self.macro_running and not stop_event.is_set():
                frame = self._grab_screen_full(thread_local)

                with self._cap_lock:
                    self._cap_frame = frame
                    self._cap_event.set()

                if scan_delay > 0:
                    time.sleep(scan_delay)

            # Unblock any waiting threads
            self._cap_event.set()

        threading.Thread(target=_loop, daemon=True).start()
        return stop_event
    # Pixel search
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
    # Temporary strict edge detection for black bars (will be improved later)
    def _find_bar_edges_strict(
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

        h, w = frame.shape[:2]
        y = int(h * scan_height_ratio)

        # Convert to BGR
        left_bgr = np.array(self._hex_to_bgr(left_hex), dtype=np.int16)
        right_bgr = np.array(self._hex_to_bgr(right_hex), dtype=np.int16)

        # Extract single horizontal scan line
        line = frame[y].astype(np.int16)

        # Clamp tolerances
        tol_l = int(np.clip(tolerance, 0, 255))
        tol_r = int(np.clip(tolerance2, 0, 255))

        bar_x_coords = None

        # LEFT BAR COLOR 
        if left_hex is not None:
            lower_l = left_bgr - tol_l
            upper_l = left_bgr + tol_l

            left_mask = np.all((line >= lower_l) & (line <= upper_l), axis=1)
            left_indices = np.where(left_mask)[0]

            if left_indices.size > 0:
                bar_x_coords = left_indices

        # RIGHT BAR COLOR 
        if right_hex is not None:
            lower_r = right_bgr - tol_r
            upper_r = right_bgr + tol_r

            right_mask = np.all((line >= lower_r) & (line <= upper_r), axis=1)
            right_indices = np.where(right_mask)[0]

            if right_indices.size > 0:
                if bar_x_coords is not None:
                    bar_x_coords = np.concatenate([bar_x_coords, right_indices])
                else:
                    bar_x_coords = right_indices

        # FINAL EDGE EXTRACTION 
        if bar_x_coords is not None and bar_x_coords.size > 0:
            bar_left_x = int(np.min(bar_x_coords))
            bar_right_x = int(np.max(bar_x_coords))
            return bar_left_x, bar_right_x

        return None, None
    
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
        Find bar center based on arrow position (similar to IRUS 675/Comet logic)
        - If holding: arrow is RIGHT edge → box extends LEFT
        - If not holding: arrow is LEFT edge → box extends RIGHT
        - When state swaps: measure arrow-to-arrow distance = box length
        """

        current_time = time.time()

        # - Handle missing arrow -
        if arrow_centroid_x is None:
            if self.last_known_box_center_x is not None:
                return self.last_known_box_center_x, self.last_left_x, self.last_right_x
            
            if self.last_left_x is not None and self.last_right_x is not None:
                center = (self.last_left_x + self.last_right_x) / 2.0
                return center, self.last_left_x, self.last_right_x
            
            return None, None, None

        # - Detect state swap -
        state_swapped = (
            self.last_holding_state is not None and 
            is_holding != self.last_holding_state
        )

        # - Recalculate box size when swapped -
        if state_swapped and self.last_indicator_x is not None:
            new_box_size = abs(arrow_centroid_x - self.last_indicator_x)
            if new_box_size >= 10:
                self.estimated_box_length = new_box_size

        # - Default box size -
        if self.estimated_box_length is None or self.estimated_box_length <= 0:
            self.estimated_box_length = min(capture_width * 0.3, 200)

        # - Position the box -
        if is_holding:
            # arrow on RIGHT
            self.last_right_x = float(arrow_centroid_x)
            self.last_left_x = self.last_right_x - self.estimated_box_length
        else:
            # arrow on LEFT
            self.last_left_x = float(arrow_centroid_x)
            self.last_right_x = self.last_left_x + self.estimated_box_length

        # - Clamp to capture bounds -
        if self.last_left_x < 0:
            self.last_left_x = 0.0
            self.last_right_x = self.estimated_box_length

        if self.last_right_x > capture_width:
            self.last_right_x = float(capture_width)
            self.last_left_x = self.last_right_x - self.estimated_box_length

        # - Calculate center -
        box_center = (self.last_left_x + self.last_right_x) / 2.0
        self.last_known_box_center_x = box_center
        self.last_known_box_timestamp = current_time

        # - Update state -
        self.last_indicator_x = arrow_centroid_x
        self.last_holding_state = is_holding

        return box_center, self.last_left_x, self.last_right_x
    # Do pixel/image search
    def _do_pixel_search(self, img):
        fish_hex = self.vars["fish_color"].get()
        left_bar_hex = self.vars["left_color"].get()
        right_bar_hex = self.vars["right_color"].get()

        left_tol = int(self.vars["left_tolerance"].get() or 8)
        right_tol = int(self.vars["right_tolerance"].get() or 8)
        fish_tol = int(self.vars["fish_tolerance"].get() or 1)
        # macOS tolerance buffer to make configs cross-compatible
        if sys.platform == "darwin":
            left_tol += 2
            right_tol += 2
            fish_tol += 2
        fish_center = self._find_color_center(img, fish_hex, fish_tol)
        # Strict Detection (main priority)
        left_bar_center, right_bar_center = self._find_bar_edges_strict(
            img, left_bar_hex, right_bar_hex, left_tol, right_tol
        )

        # Try strict fallback for left
        if left_bar_center is None:
            l2, r2 = self._find_bar_edges_strict(
                img, right_bar_hex, right_bar_hex, right_tol, right_tol
            )
            if l2 is not None:
                left_bar_center, right_bar_center = l2, r2

        # Try strict fallback for right
        if right_bar_center is None:
            l2, r2 = self._find_bar_edges_strict(
                img, left_bar_hex, left_bar_hex, left_tol, left_tol
            )
            if r2 is not None:
                left_bar_center, right_bar_center = l2, r2
        # Normal detection (If strict fails and this doesn't detect black bars well)
        if left_bar_center is None and right_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(
                img, left_bar_hex, right_bar_hex, left_tol, right_tol
            )

        # Normal fallback for left
        if left_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(
                img, right_bar_hex, right_bar_hex, right_tol, right_tol
            )

        # Normal fallback for right
        if right_bar_center is None:
            left_bar_center, right_bar_center = self._find_bar_edges(
                img, left_bar_hex, left_bar_hex, left_tol, left_tol
            )

        return fish_center, left_bar_center, right_bar_center
    # PID-related
    def _get_pid_gains(self, inside_bar=False):
        """Get PID gains from config, with sensible defaults."""
        try:
            kp = float(self.vars["proportional_gain"].get() or 0.6)
            kd = float(self.vars["derivative_gain"].get() or 0.2)
        except:
            kp = 0.6
            kd = 0.2
        return kp, kd
    
    def _pid_control_strict(self, error, bar_center_x=None):
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
    def _reset_pid_state(self):
        """
        Reset PD/PID control state variables for a new minigame cycle.
        Ensures no derivative spikes, velocity carryover, or stabilization drift.
        """

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

        # Also reset arrow estimation state
        self.last_indicator_x = None
        self.last_holding_state = None
        self.estimated_box_length = None
        self.last_left_x = None
        self.last_right_x = None
        self.last_known_box_center_x = None
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
            # Restart: When minigame ends, loop repeats from Select Rod
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
        V2 + V3 Hybrid:
        - Uses threaded capture (V3)
        - Uses Y-distance logic (V2)
        - White detection priority:
            1. Same Y row as green
            2. Closest Y if none found
        """

        mouse_controller.press(Button.left)

        # Get scale factor
        scale = self._get_scale_factor()
        # Shake area
        shake = self.bar_areas.get("shake")
        if isinstance(shake, dict):
            shake_left   = shake["x"]
            shake_top    = shake["y"]
            shake_right  = shake["x"] + shake["width"]
            shake_bottom = shake["y"] + shake["height"]
            shake_height = shake["height"]
        else:
            # fallback (old ratio logic)
            shake_left = int(self.SCREEN_WIDTH * 0.1041)
            shake_top = int(self.SCREEN_HEIGHT * 0.0925)
            shake_right = int(self.SCREEN_WIDTH * 0.8958)
            shake_bottom = int(self.SCREEN_HEIGHT * 0.8333)
            shake_height = shake_bottom - shake_top
        shake_left_s   = int(shake_left * scale)
        shake_top_s    = int(shake_top * scale)
        shake_right_s  = int(shake_right * scale)
        shake_bottom_s = int(shake_bottom * scale)

        # SETTINGS 
        white_color     = self.vars["perfect_color2"].get()
        green_color     = self.vars["perfect_color"].get()
        white_tol       = int(self.vars["perfect_cast2_tolerance"].get())
        green_tol       = int(self.vars["perfect_cast_tolerance"].get())

        max_time        = float(self.vars["perfect_max_time"].get())
        perfect_thresh  = int(self.vars["perfect_threshold"].get())
        scan_delay      = float(self.vars["cast_scan_delay"].get())

        release_delay   = float(self.vars["perfect_release_delay"].get())
        if release_delay < 0:
            user_green_offset = abs(release_delay * 10)
            release_delay = 0
        else:
            user_green_offset = 0

        # VELOCITY 
        prev_white_y = None
        green_offset = 0

        # CAPTURE THREAD 
        stop_event = self._start_capture(scan_delay)

        start_time = time.time()

        if self.vars["fish_overlay"].get() == "Enabled":
            self.fish_overlay.show()

        # == LOOP ==
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

            self.fish_overlay.clear()

            # GREEN 
            green_pixels = self._pixel_search(region, green_color, green_tol)
            if not green_pixels:
                if time.time() - start_time > max_time:
                    break
                continue

            # Use lowest green (V2 behavior)
            green_x, green_y = max(green_pixels, key=lambda p: p[1])

            # Apply offset
            green_y += user_green_offset

            # WHITE 
            white_pixels = self._pixel_search(region, white_color, white_tol)
            if not white_pixels:
                continue

            # PRIORITY 1: SAME ROW 
            same_row = [wp for wp in white_pixels if wp[1] == green_y]

            if same_row:
                # Stable pick
                white_x = int(np.median([x for x, _ in same_row]))
                white_y = green_y

            else:
                # PRIORITY 2: CLOSEST Y 
                white_x, white_y = min(
                    white_pixels,
                    key=lambda p: abs(p[1] - green_y)
                )

            # VELOCITY 
            if self.vars["release_method"].get() == "Velocity-based":
                if prev_white_y is not None:
                    dy = white_y - prev_white_y
                    green_offset = abs(dy)

                prev_white_y = white_y
                green_y += green_offset

            # OVERLAY 
            if self.vars["fish_overlay"].get() == "Enabled":
                gy_canvas = int((green_y / shake_height) * 60)
                wy_canvas = int((white_y / shake_height) * 60)

                self.after(0, lambda y=gy_canvas: self.fish_overlay.draw(
                    bar_center=y, box_size=15, color="green", canvas_offset=0
                ))

                self.after(0, lambda y=wy_canvas: self.fish_overlay.draw(
                    bar_center=y, box_size=30, color="white", canvas_offset=0
                ))

            # RELEASE CONDITION (V2 STYLE) 
            distance = abs(green_y - white_y)

            if distance < perfect_thresh:
                time.sleep(release_delay)
                break

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
        # Get scale factor
        scale = self._get_scale_factor()
        # Shake area
        shake = self.bar_areas.get("shake")
        if isinstance(shake, dict):
            shake_left   = shake["x"]
            shake_top    = shake["y"]
            shake_right  = shake["x"] + shake["width"]
            shake_bottom = shake["y"] + shake["height"]
            shake_x = int((shake_left + shake_right) / 2)
            shake_y = int((shake_top + shake_bottom) / 2)
        else:
            # fallback (old ratio logic)
            shake_left = int(self.SCREEN_WIDTH * 0.1041)
            shake_top = int(self.SCREEN_HEIGHT * 0.0925)
            shake_right = int(self.SCREEN_WIDTH * 0.8958)
            shake_bottom = int(self.SCREEN_HEIGHT * 0.8333)
            shake_x = int(self.SCREEN_WIDTH * 0.5)
            shake_y = int(self.SCREEN_HEIGHT * 0.3)
        # Fish area
        fish = self.bar_areas.get("fish")
        if isinstance(fish, dict):
            fish_left   = fish["x"]
            fish_top    = fish["y"]
            fish_right  = fish["x"] + fish["width"]
            fish_bottom = fish["y"] + fish["height"]
            fish_width = fish["width"]
            fish_height = fish["height"]
        else:
            fish_left   = int(self.SCREEN_WIDTH  * 0.2844)
            fish_top    = int(self.SCREEN_HEIGHT * 0.7981)
            fish_right  = int(self.SCREEN_WIDTH  * 0.7141)
            fish_bottom = int(self.SCREEN_HEIGHT * 0.8370)
            fish_width = fish_right - fish_left
            fish_height = fish_bottom - fish_top
        # Friend area
        friend = self.bar_areas.get("friend")
        if isinstance(friend, dict):
            friend_left   = friend["x"]
            friend_top    = friend["y"]
            friend_right  = friend["x"] + friend["width"]
            friend_bottom = friend["y"] + friend["height"]
        else:
            friend_left = int(self.SCREEN_WIDTH * 0.0046)
            friend_top = int(self.SCREEN_HEIGHT * 0.8583)
            friend_right = int(self.SCREEN_WIDTH * 0.0401)
            friend_bottom = int(self.SCREEN_HEIGHT * 0.94)
        # Scale to retina / 4K scaling
        fish_left_s   = int(fish_left * scale)
        fish_top_s    = int(fish_top * scale)
        fish_right_s  = int(fish_right * scale)
        fish_bottom_s = int(fish_bottom * scale)

        shake_left_s   = int(shake_left * scale)
        shake_top_s    = int(shake_top * scale)
        shake_right_s  = int(shake_right * scale)
        shake_bottom_s = int(shake_bottom * scale)

        friend_left_s   = int(friend_left * scale)
        friend_right_s  = int(friend_right * scale)
        friend_top_s    = int(friend_top * scale)
        friend_bottom_s = int(friend_bottom * scale)
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
                    friend_x = self._find_color_center(
                        detection_area, "#9BFF9B", tolerance
                    )
                fish_x = self._find_color_center(
                    detection_area, fish_hex, tolerance
                )
                bar_x = self._find_color_center(
                    detection_area, bar_hex, bar_tolerance
                )
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
        # Get scale factor
        scale = self._get_scale_factor()
        # Fish area
        fish = self.bar_areas.get("fish")
        if isinstance(fish, dict):
            fish_left   = fish["x"]
            fish_top    = fish["y"]
            fish_right  = fish["x"] + fish["width"]
            fish_bottom = fish["y"] + fish["height"]
        else:
            fish_left   = int(self.SCREEN_WIDTH  * 0.2844)
            fish_top    = int(self.SCREEN_HEIGHT * 0.7981)
            fish_right  = int(self.SCREEN_WIDTH  * 0.7141)
            fish_bottom = int(self.SCREEN_HEIGHT * 0.8370)
        # Friend area
        friend = self.bar_areas.get("friend")
        if isinstance(friend, dict):
            friend_left   = friend["x"]
            friend_top    = friend["y"]
            friend_right  = friend["x"] + friend["width"]
            friend_bottom = friend["y"] + friend["height"]
        else:
            friend_left = int(self.SCREEN_WIDTH * 0.0046)
            friend_top = int(self.SCREEN_HEIGHT * 0.8583)
            friend_right = int(self.SCREEN_WIDTH * 0.0401)
            friend_bottom = int(self.SCREEN_HEIGHT * 0.94)
        # Scale to retina / 4K scaling
        fish_left_s   = int(fish_left * scale)
        fish_top_s    = int(fish_top * scale)
        fish_right_s  = int(fish_right * scale)
        fish_bottom_s = int(fish_bottom * scale)

        friend_left_s   = int(friend_left * scale)
        friend_right_s  = int(friend_right * scale)
        friend_top_s    = int(friend_top * scale)
        friend_bottom_s = int(friend_bottom * scale)

        # Misc variables
        fish_hex = self.vars["fish_color"].get()
        tolerance = int(self.vars["shake_tolerance"].get())
        scan_delay = float(self.vars["shake_scan_delay"].get())
        failsafe = int(self.vars["shake_failsafe"].get() or 20)
        detection_method = (self.vars["detection_method"].get())
        bar_hex = self.vars["left_color"].get() # Left bar color replaced by left color
        bar_tolerance = int(self.vars["left_tolerance"].get())
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
                    friend_x = self._find_color_center(
                        detection_area, "#9BFF9B", tolerance
                    )
                fish_x = self._find_color_center(
                    detection_area, fish_hex, tolerance
                )
                bar_x = self._find_color_center(
                    detection_area, bar_hex, bar_tolerance
                )
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
        # Shake area
        shake = self.bar_areas.get("shake")
        if isinstance(shake, dict):
            shake_left   = shake["x"]
            shake_top    = shake["y"]
            shake_right  = shake["x"] + shake["width"]
            shake_bottom = shake["y"] + shake["height"]
            shake_x = int((shake_left + shake_right) / 2)
            shake_y = int((shake_top + shake_bottom) / 2)
        else:
            # fallback (old ratio logic)
            shake_left = int(self.SCREEN_WIDTH * 0.1041)
            shake_top = int(self.SCREEN_HEIGHT * 0.0925)
            shake_right = int(self.SCREEN_WIDTH * 0.8958)
            shake_bottom = int(self.SCREEN_HEIGHT * 0.8333)
            shake_x = int(self.SCREEN_WIDTH * 0.5)
            shake_y = int(self.SCREEN_HEIGHT * 0.3)
        # Fish area
        fish = self.bar_areas.get("fish")
        if isinstance(fish, dict):
            fish_left   = fish["x"]
            fish_top    = fish["y"]
            fish_right  = fish["x"] + fish["width"]
            fish_bottom = fish["y"] + fish["height"]
            fish_width = fish["width"]
            fish_height = fish["height"]
        else:
            fish_left   = int(self.SCREEN_WIDTH  * 0.2844)
            fish_top    = int(self.SCREEN_HEIGHT * 0.7981)
            fish_right  = int(self.SCREEN_WIDTH  * 0.7141)
            fish_bottom = int(self.SCREEN_HEIGHT * 0.8370)
            fish_width = fish_right - fish_left
            fish_height = fish_bottom - fish_top
        # Friend area
        friend = self.bar_areas.get("friend")
        if isinstance(friend, dict):
            friend_left   = friend["x"]
            friend_top    = friend["y"]
            friend_right  = friend["x"] + friend["width"]
            friend_bottom = friend["y"] + friend["height"]
        else:
            friend_left = int(self.SCREEN_WIDTH * 0.0046)
            friend_top = int(self.SCREEN_HEIGHT * 0.8583)
            friend_right = int(self.SCREEN_WIDTH * 0.0401)
            friend_bottom = int(self.SCREEN_HEIGHT * 0.94)
        # Scale to retina / 4K scaling
        fish_left_s   = int(fish_left * scale)
        fish_top_s    = int(fish_top * scale)
        fish_right_s  = int(fish_right * scale)
        fish_bottom_s = int(fish_bottom * scale)

        shake_left_s   = int(shake_left * scale)
        shake_top_s    = int(shake_top * scale)
        shake_right_s  = int(shake_right * scale)
        shake_bottom_s = int(shake_bottom * scale)

        friend_left_s   = int(friend_left * scale)
        friend_right_s  = int(friend_right * scale)
        friend_top_s    = int(friend_top * scale)
        friend_bottom_s = int(friend_bottom * scale)

        # Reset PID gains
        self._reset_pid_state()
        # Set default values
        mouse_down = False
        fish_x = None
        controller_mode = 3
        deadzone_action = 0
        charge_cooldown_until = 0
        charge_lost_frames = 0
        last_charge_size = 0
        charge_size2 = 0
        max_left = fish_left - 20
        max_right = fish_right + 20
        # Load values from GUI
        arrow_hex = self.vars["arrow_color"].get()
        arrow_tol = int(self.vars["arrow_tolerance"].get() or 8)
        left_ratio = float(self.vars["left_ratio"].get() or 0.5)
        right_ratio = float(self.vars["right_ratio"].get() or 0.5)
        pid_clamp = float(self.vars["pid_clamp"].get() or 100)
        thresh = float(self.vars["stabilize_threshold"].get() or 8)
        restart_method = (self.vars["restart_method"].get())
        restart_delay = float(self.vars["restart_delay"].get())
        track_notes = self.vars["track_notes"].get()
        track_charges = self.vars["track_charges"].get()
        note_box_hex = self.vars["note_box_color"].get()
        note_box_tol = int(self.vars["note_box_tolerance"].get() or 8)
        note_track_ratio = float(self.vars["note_track_ratio"].get())
        charge_track_ratio = float(self.vars["charge_track_ratio"].get() or 0.23)
        # Maelstrom-style charge control variables
        maelstrom_state = "minigame"  # State machine: "minigame" or "moving_to_right"
        colors_were_missing = False  # Track if colors were lost
        maelstrom_left_section = left_ratio  # Left section ratio
        maelstrom_right_section = right_ratio  # Right section ratio
        # keyboard_controller.press(rod_slot)
        # time.sleep(0.05)
        # keyboard_controller.release(rod_slot)
        # Hold and release mouse
        def hold_mouse():
            nonlocal mouse_down
            if not mouse_down:
                # mouse_controller.press(Button.left)
                keyboard_controller.press(Key.space)
                mouse_down = True
        def release_mouse():
            nonlocal mouse_down
            if mouse_down:
                # mouse_controller.release(Button.left)
                keyboard_controller.release(Key.space)
                mouse_down = False
        # Start screen capture thread
        self._cap_frame = None
        self._cap_event.clear()
        _minigame_stop = threading.Event()

        threading.Thread(
            target=self._capture_loop_full,
            args=(_minigame_stop, float(self.vars["minigame_scan_delay"].get() or 0.05)),
            daemon=True
        ).start()
        while self.macro_running: # Main macro loop
            # Grab full screen then crop
            if not self._cap_event.wait(timeout=0.5):
                continue

            with self._cap_lock:
                frame = self._cap_frame
                self._cap_event.clear()

            if frame is None:
                _minigame_stop.set()
                return

            img = frame[fish_top_s:fish_bottom_s, fish_left_s:fish_right_s]
            note_img = frame[shake_top_s:shake_bottom_s, shake_left_s:shake_right_s]
            friend_img = frame[friend_top_s:friend_bottom_s, friend_left_s:friend_right_s]
            # Stabilize frame
            deadzone_action = deadzone_action + 1
            if deadzone_action == 2:
                deadzone_action = 0
            # Do pixel and image search
            # Image search will be added in the future, for now this is just a wrapper
            # around the pixel search with some extra logic for clicking and resetting PID state when bars are lost
            fish_x, left_x, right_x = self._do_pixel_search(img)
            arrow_center = self._find_color_center(img, arrow_hex, arrow_tol)
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
            if restart_method == "Friend Area": # Not implemented yet (this is a stub)
                friend_x = self._find_color_center(friend_img, "#9BFF9B", 2)
                if fish_x is not None:
                    self.last_fish_x = fish_x
                if left_x is not None and right_x is not None:
                    self.last_bar_left = left_x
                    self.last_bar_right = right_x
                else:
                    if friend_x is not None:
                        release_mouse()
                        time.sleep(restart_delay)
                        return
                    else:
                        fish_x = self.last_fish_x
                        if left_x is not None and right_x is not None:
                            left_x = self.last_bar_left
                            right_x = self.last_bar_right
            elif restart_method == "Fish + Bar":
                if fish_x is not None:
                    self.last_fish_x = fish_x
                else:
                    if left_x is None and right_x is None:
                        release_mouse()
                        time.sleep(restart_delay)
                        return
                    else:
                        fish_x = self.last_fish_x
            else:
                if fish_x is not None:
                    self.last_fish_x = fish_x
                else:
                    release_mouse()
                    time.sleep(restart_delay)
                    return
            # Compute bar variables for calculations
            bars_found = left_x is not None and right_x is not None
            if bars_found == True:
                bar_size = right_x - left_x # Don't add fish left here
                bar_center = (left_x + bar_size // 2) + fish_left # ADD FISH LEFT HERE
                left_deadzone = bar_size * left_ratio
                right_deadzone = bar_size * right_ratio
                max_left = fish_left + left_deadzone
                max_right = fish_right - right_deadzone
                # Compute charge values (only if charge is on to prevent CPU spikes)
                if track_charges == "on" and bars_found:
                    charge_half_size = bar_size * 0.4
                    charge_left = bar_center - charge_half_size
                    charge_right = bar_center + charge_half_size
                    charge_top = int(fish_height * charge_track_ratio * 0.8) + fish_top
                    charge_bottom = int(fish_height * charge_track_ratio * 1.2) + fish_top
                    charge_left_s   = int(charge_left * scale)
                    charge_right_s  = int(charge_right * scale)
                    charge_top_s    = int(charge_top * scale)
                    charge_bottom_s = int(charge_bottom * scale)

                    charge_img = frame[
                        charge_top_s:charge_bottom_s,
                        charge_left_s:charge_right_s
                    ]
                    charge_half_size = bar_size * 0.4
                    charge_left = bar_center - charge_half_size
                    charge_right = bar_center + charge_half_size
                    charge_top = int(fish_height * charge_track_ratio * 0.8) + fish_top
                    charge_bottom = int(fish_height * charge_track_ratio * 1.2) + fish_top
                    charge_left2, charge_right2 = self._find_bar_edges(charge_img, "#F1F1F1", "#FFFFFF", 8, 8, 0.6)
                    charge_size2 = charge_right2 - charge_left2 if charge_left2 is not None and charge_right2 is not None else None
            else:
                bar_size = None
                bar_center = None
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
                bar_left_screen  = left_x  + fish_left
                bar_right_screen = right_x + fish_left
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
            elif arrow_center:
                # Find arrow indicator
                arrow_indicator_x = self._find_arrow_indicator_x(img, arrow_hex, arrow_tol, mouse_down)
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
                    bar_left_screen  = estimated_left  + fish_left
                    bar_right_screen = estimated_right + fish_left
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
            # Draw boxes
            if self.vars["fish_overlay"].get() == "on":
                self.after(0, lambda: self.fish_overlay.draw(bar_center=bar_center,box_size=(bar_right_screen - bar_left_screen),color="pink",canvas_offset=fish_left))
                self.after(0, lambda _bc=bar_center, _bs=bar_size, _fl=fish_left: self.fish_overlay.draw(bar_center=_bc, box_size=_bs, color="green", canvas_offset=_fl, show_bar_center=True))
                self.after(0, lambda _ml=max_left, _fl=fish_left: self.fish_overlay.draw(bar_center=_ml, box_size=15, color="lightblue", canvas_offset=_fl))
                self.after(0, lambda _mr=max_right, _fl=fish_left: self.fish_overlay.draw(bar_center=_mr, box_size=15, color="lightblue", canvas_offset=_fl))
                self.after(0, lambda: self.fish_overlay.draw(bar_center=fish_x, box_size=10, color="red", canvas_offset=fish_left))
            # PID loop
            if controller_mode == 0 and bar_center is not None:
                error = fish_x - bar_center
                control = self._pid_control_strict(error, bar_center)
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
            elif controller_mode == 2:
                hold_mouse()
            elif controller_mode == 3:
                release_mouse()
            elif controller_mode == 4:
                now = time.time()

                # Cooldown
                if now < charge_cooldown_until:
                    release_mouse()
                    should_hold = False
                    continue

                # Stabilize charge detection (keep existing detection logic)
                if charge_size2 is not None and charge_size2 > 0:
                    last_charge_size = charge_size2
                    charge_lost_frames = 0
                else:
                    charge_lost_frames += 1

                if charge_lost_frames < 3:
                    effective_charge = last_charge_size
                else:
                    effective_charge = 0

                # Maelstrom-style logic: colors detected if effective_charge > 0
                colors_detected = effective_charge > 0

                # Calculate bar sections
                charge_size = bar_right_screen - bar_left_screen
                left_threshold = bar_left_screen + (charge_size * maelstrom_left_section)
                right_threshold = bar_left_screen + (charge_size * maelstrom_right_section)

                # Determine icon position sections
                in_left_section = fish_x < left_threshold
                in_middle_section = left_threshold <= fish_x <= right_threshold
                in_right_section = fish_x > right_threshold

                # Edge detection (similar to IRUS)
                edge_threshold = charge_size * left_ratio
                target_at_left_edge = fish_x < (fish_left + edge_threshold)
                target_at_right_edge = fish_x > (fish_right - edge_threshold)

                should_hold = False

                if colors_detected:
                    # Colors detected - clear the missing flag
                    colors_were_missing = False

                    # State machine logic similar to IRUS Neural
                    if target_at_right_edge:
                        # Icon at right edge of screen - spam minigame
                        maelstrom_state = "minigame"
                        should_hold = not colors_were_missing
                    else:
                        # Middle zone - state machine based on bar sections
                        if in_left_section:
                            # Left section: Enter "moving_to_right" state - release until we reach right section
                            maelstrom_state = "moving_to_right"
                            should_hold = False
                        elif in_right_section:
                            # Right section: Always play minigame
                            maelstrom_state = "minigame"
                            should_hold = not colors_were_missing
                        else:  # in_middle_section
                            # Middle section: Depends on state
                            if maelstrom_state == "moving_to_right":
                                # Coming from left - keep releasing until we reach right section
                                should_hold = False
                            else:
                                # Already in minigame state - play the minigame
                                maelstrom_state = "minigame"
                                should_hold = not colors_were_missing
                else:
                    # Colors not detected - release and set flag
                    colors_were_missing = True
                    should_hold = False

                    # Override: force release if in left section
                    if in_left_section:
                        maelstrom_state = "moving_to_right"

                # HARD STOP: release when fully charged
                effective_charge_ratio = effective_charge / bar_size if bar_size else 0
                if effective_charge_ratio >= 0.6:
                    should_hold = False
                    maelstrom_state = "cooldown"
                    charge_cooldown_until = now + 0.2

                # Execute mouse control
                if should_hold:
                    hold_mouse()
                else:
                    release_mouse()

                # Overlay
                if charge_left2 is not None and charge_right2 is not None:
                    charge_center = ((charge_left2 + charge_right2) // 2) + charge_left
                    # print(f"Charge detected: {colors_detected}, State: {maelstrom_state}, Hold: {should_hold}")
            time.sleep(0.01)
    def stop_macro(self):
        if not self.macro_running:
            return
        self.macro_running = False
        self._reset_pid_state()
        self.after(0, self.deiconify)  # show window safely
        self.set_status("Macro Status: Stopped")
if __name__ == "__main__":
    app = App()
    app.mainloop()