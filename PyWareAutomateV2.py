# Imports
from customtkinter import *
import tkinter as tk
from tkinter import messagebox
import os
import subprocess
# Keyboard and Mouse
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
# Key Listeners
import threading
from pynput.keyboard import Listener as KeyListener, Key
macro_running = False
macro_thread = None
# Key Inputs
import threading
# Time
import time
import json
# Web browsing
import webbrowser
# Variables
import re
import numpy as np
import mss
import Quartz
import sys
# Initialize controllers
keyboard_controller = KeyboardController()
mouse_controller = MouseController()

class PlaybackError(Exception):
    """Raised immediately when a playback command fails, stopping the script."""
    pass

class AhkBreak(Exception):
    """Internal signal for AHK break statements."""
    pass

class AhkContinue(Exception):
    """Internal signal for AHK continue statements."""
    pass
# AHK scan-code → key mapping (MODULE LEVEL)
SC_TO_KEY = {
    "sc3b": "f1",
    "sc3c": "f2",
    "sc3d": "f3",
    "sc3e": "f4",
    "sc3f": "f5",
    "sc40": "f6",
    "sc41": "f7",
    "sc42": "f8",
    "sc43": "f9",
    "sc44": "f10",
    "sc57": "f11",
    "sc58": "f12",
}
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
                "PyWareAutomateV2"
            ), compiled
        elif sys.platform == "win32":
            return os.path.join(
                os.path.expanduser("~"),
                "AppData", "Roaming",
                "PyWareAutomateV2"
            ), compiled
        else:
            return os.path.join(os.path.expanduser("~"), "PyWareAutomateV2"), compiled
    compiled = False
    # Dev Mode → Project Directory
    return os.path.dirname(os.path.abspath(__file__)), compiled

BASE_PATH, IS_COMPILED = get_base_path()

CONFIG_DIR = os.path.join(BASE_PATH, "configs")
IMAGES_PATH = os.path.join(BASE_PATH, "images")
DEBUG_DIR = BASE_PATH

CONFIG_PATH = os.path.join(BASE_PATH, "last_config.json")
APP_VERSION = "2.0"
EXCLUDED_KEYS = {"active_config"}

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
        "version": APP_VERSION,
        "last_config": "default",
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

# Terms Of Service Dialogue
class TermsOfServiceDialog(CTkToplevel):
    def __init__(self, parent=None, show_setup=True):
        super().__init__(parent)
        
        # Screen Size (Cache Once – Thread Safe)
        self.SCREEN_WIDTH = self.winfo_screenwidth()
        self.SCREEN_HEIGHT = self.winfo_screenheight()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Window
        self.configure(fg_color="#181836")   # <- Main Window Ultra Dark
        self.geometry("750x600")
        self.title("PyWare Automate V2 - Terms of Service")
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

        # Agree Labels
        self.agree_var = BooleanVar(value=False)
        self.accepted = False

        # Build Pages
        self.build_tos_page(self.page_tos)
        self.page_tos.grid(row=0, column=0, sticky="nsew")

        # Navigation Bar
        nav_bar = CTkFrame(self, border_color="#364167", fg_color="#181836")
        nav_bar.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        nav_bar.grid_columnconfigure((0, 1), weight=1)

        # Decline Button
        self.back_btn = CTkButton(
            nav_bar,
            text="Decline",
            command=self.on_close
        )

        # Accept Button
        self.next_btn = CTkButton(
            nav_bar,
            text="Accept",
            command=self.accept_terms,
            state="disabled"
        )

        self.back_btn.grid(row=0, column=0, padx=5, sticky="w")
        self.next_btn.grid(row=0, column=1, padx=5, sticky="e")
    # Basic Settings Tab
    def build_tos_page(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=0)
        parent.grid_columnconfigure(0, weight=1)

        textbox = CTkTextbox(
            parent,
            wrap="word",
            border_color="#364167",
            fg_color="#222244",
            text_color="#E8EAF6",
            scrollbar_button_color="#364167",
            scrollbar_button_hover_color="#4B5A8A"
        )
        textbox.grid(row=0, column=0, padx=12, pady=10, sticky="nsew")

        textbox.insert("1.0", """
PyWare Automate V2.0 - Terms of Use

By using this software, you agree to the following:


⚡ 1. USAGE & MODIFICATION

Allowed:
Use these macros for personal purposes.
Study and reverse engineer the code for educational purposes.
Modify the code for your own personal use.
Share your modifications with proper attribution.
                            
Forbidden:
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
                            
⚡ 7. ACCEPTANCE

By accepting the terms, you acknowledge that you have read, understood, and agree to these Terms of Use.
If you do not agree, please remove the software from your device.

🚀 Thank you for using PyWare Automate! 🚀
        """)
        textbox.configure(state="disabled")

        checkbox = CTkCheckBox(
            parent,
            text="I agree to the Terms of Service",
            text_color="#E8EAF6",
            fg_color="#4B7BEC",
            hover_color="#3867D6",
            border_color="#AAB2D5",
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
    def update_next_button(self):
        self.next_btn.configure(
            state="normal" if self.agree_var.get() else "disabled"
        )
    def accept_terms(self):
        self.accepted = True
        # Close TOS window
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
        self.variables = {} # Save variables for AHK playback
        self._tooltips = {}

        # Store Screen Width And Height To Use Later
        self.SCREEN_WIDTH = self.winfo_screenwidth()
        self.SCREEN_HEIGHT = self.winfo_screenheight()

        # Hotkey Variables
        self.hotkey_start = Key.f5
        self.hotkey_start_recording = Key.f6
        self.hotkey_stop = Key.f7
        self.hotkey_stop_recording = Key.f8
        self.hotkey_labels = {}  # Store Label Widgets For Dynamic Updates

        # Macro state
        self.macro_running = False
        self.macro_thread = None
        self.is_recording = False    # True only while actively recording
        self.is_playing_back = False # True only while playback is running
        
        # Start Capture Thread
        self.capture_running = False
        self.capture_thread = None
        self.latest_frame = None
        self.capture_lock = threading.Lock()
        
        # Screen Capture Variables — Mss Instances Are Per-Thread (See _Thread_Local)
        self._thread_local = threading.local()
        self._monitor = {}      # Pre-Allocated Monitor Dict, Reused Every Grab
        self._scale_cache = None  # Cached Dpi Scale Factor
        self.capture_stop_event = threading.Event()
        # Buffer For Capture/Logic Thread Decoupling (Used In Start_Macro())
        self._cap_lock = threading.Lock()
        self._cap_frame = None    # Latest Full Screen Frame
        self._cap_event = threading.Event()  # Signals A New Frame Pair Is Ready
        self._active_capture_stop = None  # Stop Event For The Currently Running Capture Thread
        self._active_capture_thread = None  # Thread Object For The Currently Running Capture Thread

        # Safe Defaults Before Key Listener Starts (Will Be Overwritten By Load_Misc_Settings)
        self.bar_areas = {"shake": None, "fish": None, "friend": None, "totem": None}
        self.current_config_name = "Basic config"

        self.dispatch_map = {
            "sleep": self._cmd_sleep,
            "mousemove": self._cmd_mousemove,
            "click": self._cmd_click,
            "send": self._cmd_send,
            "pixelsearch": self._cmd_pixelsearch,
            "pixelgetcolor": self._cmd_pixelgetcolor,
            "mousegetpos": self._cmd_mousegetpos,
            "startcapturethread": self._cmd_startcapturethread,
            "stopcapturethread": self._cmd_stopcapturethread,
            "msgbox": self._cmd_msgbox,
            "tooltip": self._cmd_tooltip,
            # "if" and "else" are handled structurally by execute_script/
            # _parse_if_node — they never reach the dispatch map.
        }

        # Invalidate Scale Cache If The Window Moves To A Different Monitor
        if sys.platform == "darwin":
            self.bind("<Configure>", lambda e: self._invalidate_scale_cache())
        
        # Show Tos Dialogue
        state, first_launch, new_version = self.load_app_state()

        # Important: Show Tos If Needed
        if first_launch or not state.get("tos_accepted", False):
            dialog = TermsOfServiceDialog(self)
            self.wait_window(dialog)

            if not dialog.accepted:
                self.destroy()
                return

            # Mark Accepted
            state["tos_accepted"] = True

        # Update Version After TOS
        state["version"] = APP_VERSION

        self.save_app_state(state)

        # Start Hotkey Listener
        self.key_listener = KeyListener(on_press=self.on_key_press)
        self.key_listener.daemon = True
        self.key_listener.start()

        # Save and load to TXT
        self.recorded_actions = []
        self.recording_file = os.path.join(CONFIG_DIR, "recording.ahk")

        self._init_builtin_variables()

        # Handle AHK errors
        self.held_keys = set()

        # Create Window
        self.configure(fg_color="#181836")   # <- Main Window Ultra Dark
        self.geometry("800x600")
        self.title("PyWare Automate V2.0")

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
            text="PYWARE AUTOMATE V2.0",
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
            text="Extras",
            width=120,
            corner_radius=8,
            command=self.open_link("https://docs.google.com/document/d/1KdWwS1qSDA4cQYQ26fNKLlIfK67wo47yRsXezuKBPrA/")
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

        self.tabs.add("Recording/Playback")
        self.tabs.add("Editor")
        self.tabs.add("Unused")

        # Build tabs
        self.build_basic_tab(self.tabs.tab("Recording/Playback"))
        self.build_editor_tab(self.tabs.tab("Editor"))
        self.build_3_tab(self.tabs.tab("Unused"))
        self._create_tooltip_pool()

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

        CTkLabel(basic_settings, text="config Type:").grid(row=1, column=0, padx=12, pady=10, sticky="w")

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

        CTkButton(basic_settings, text="Add", width=40, corner_radius=8, command=self.add_config).grid(row=1, column=2, padx=12, pady=12, sticky="w")
        CTkButton(basic_settings, text="Delete", width=40, corner_radius=8, command=self.delete_config).grid(row=1, column=3, padx=12, pady=12, sticky="w")

        CTkButton(basic_settings, text="Reset Settings", width=140, corner_radius=8, command=self.reset_settings).grid(row=3, column=0, padx=12, pady=12, sticky="w")
        # Hotkey and Hotbar Settings
        playback_and_hotkey = CTkFrame(scroll, border_width=2, border_color = "#364167", fg_color = "#222244")
        playback_and_hotkey.grid(row=1, column=0, padx=20, pady=20, sticky="nw")
        CTkLabel(playback_and_hotkey, text="Hotkey Settings", font=CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        # Key binds
        CTkLabel(playback_and_hotkey, text="Start Key").grid(row=1, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(playback_and_hotkey, text="Change Bar Areas Key").grid(row=2, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(playback_and_hotkey, text="Stop Key").grid(row=3, column=0, padx=12, pady=6, sticky="w" )
        CTkLabel(playback_and_hotkey, text="Screenshot Key").grid(row=4, column=0, padx=12, pady=6, sticky="w" )
        # Disable hotkeys
        enable_hotkeys_var = StringVar(value="off")
        self.vars["enable_hotkeys"] = enable_hotkeys_var
        sw = CTkSwitch(playback_and_hotkey, text="Toggle", variable=enable_hotkeys_var, onvalue="on", offvalue="off")
        sw.grid(row=0, column=1, padx=12, pady=8, sticky="w")
        self.switches["enable_hotkeys"] = sw
        # Keys text changer
        start_playback_key_var = StringVar(value="F5")
        self.vars["start_playback_key"] = start_playback_key_var
        start_playback_key_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=start_playback_key_var )
        start_playback_key_entry.grid(row=1, column=1, padx=12, pady=10, sticky="w")
        start_recording_key_var = StringVar(value="F6")
        self.vars["start_recording_key"] = start_recording_key_var
        start_recording_key_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=start_recording_key_var )
        start_recording_key_entry.grid(row=2, column=1, padx=12, pady=10, sticky="w")
        stop_playback_key_var = StringVar(value="F7")
        self.vars["stop_playback_key"] = stop_playback_key_var
        stop_playback_key_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=stop_playback_key_var )
        stop_playback_key_entry.grid(row=3, column=1, padx=12, pady=10, sticky="w")
        stop_recording_key_var = StringVar(value="F8")
        self.vars["stop_recording_key"] = stop_recording_key_var
        stop_recording_key_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=stop_recording_key_var)
        stop_recording_key_entry.grid(row=4, column=1, padx=12, pady=10, sticky="w")

        CTkLabel(playback_and_hotkey, text="Record and Playback", font=CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=12, pady=8, sticky="w")

        CTkLabel(playback_and_hotkey, text="Record Delay").grid(row=1, column=2, padx=12, pady=8, sticky="w") # This is the label syntax
        record_delay_var = StringVar(value="0.0") # This line is the default/placeholder value
        self.vars["record_delay"] = record_delay_var # This line makes the entry save and load
        record_delay_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=record_delay_var) # This line initializes the entry
        record_delay_entry.grid(row=1, column=3, padx=12, pady=8, sticky="w") # This line initializes the position for the entry (most important)

        CTkLabel(playback_and_hotkey, text="Playback Loops").grid(row=2, column=2, padx=12, pady=8, sticky="w") # This is the label syntax
        playback_loops_var = StringVar(value="1") # This line is the default/placeholder value
        self.vars["playback_loops"] = playback_loops_var # This line makes the entry save and load
        playback_loops_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=playback_loops_var) # This line initializes the entry
        playback_loops_entry.grid(row=2, column=3, padx=12, pady=8, sticky="w") # This line initializes the position for the entry (most important)

        CTkLabel(playback_and_hotkey, text="Playback Interval (minutes)").grid(row=3, column=2, padx=12, pady=8, sticky="w") # This is the label syntax
        playback_interval_var = StringVar(value="0") # This line is the default/placeholder value
        self.vars["playback_interval"] = playback_interval_var # This line makes the entry save and load
        playback_interval_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=playback_interval_var) # This line initializes the entry
        playback_interval_entry.grid(row=3, column=3, padx=12, pady=8, sticky="w") # This line initializes the position for the entry (most important)

        CTkLabel(playback_and_hotkey, text="Playback speed (time)").grid(row=4, column=2, padx=12, pady=8, sticky="w") # This is the label syntax
        playback_speed_var = StringVar(value="1") # This line is the default/placeholder value
        self.vars["playback_speed"] = playback_speed_var # This line makes the entry save and load
        playback_speed_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=playback_speed_var) # This line initializes the entry
        playback_speed_entry.grid(row=4, column=3, padx=12, pady=8, sticky="w") # This line initializes the position for the entry (most important)

        # scan_delay
        CTkLabel(playback_and_hotkey, text="Capture Thread Scan Delay: ").grid(row=5, column=2, padx=12, pady=8, sticky="w") # This is the label syntax
        scan_delay_var = StringVar(value="0.01") # This line is the default/placeholder value
        self.vars["scan_delay"] = scan_delay_var # This line makes the entry save and load
        scan_delay_entry = CTkEntry(playback_and_hotkey, width=120, textvariable=scan_delay_var) # This line initializes the entry
        scan_delay_entry.grid(row=5, column=3, padx=12, pady=8, sticky="w") # This line initializes the position for the entry (most important)
    # Second tab
    def build_editor_tab(self, parent):

        # Configure Grid
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Main Editor Frame
        editor_frame = CTkFrame(
            parent,
            border_width=2,
            border_color="#364167",
            fg_color="#222244"
        )

        editor_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=20,
            pady=20
        )

        editor_frame.grid_rowconfigure(1, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        # Title
        CTkLabel(
            editor_frame,
            text="AHK Script Editor",
            font=CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))

        # Textbox
        self.editor_textbox = CTkTextbox(
            editor_frame,
            wrap="none",
            font=("Consolas", 14),
            fg_color="#181836",
            text_color="#FFFFFF",
            border_width=0
        )

        self.editor_textbox.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=10
        )
    # Third tab
    def build_3_tab(self, parent):
        # This tab contains a combobox
        # CTkLabel(casting_mode, text="Casting Mode:").grid(row=1, column=0, padx=12, pady=10, sticky="w" ) # You already know what this does in the second tab
        # casting_mode_var = StringVar(value="Normal") # This line is the default/placeholder value
        # self.vars["casting_mode"] = casting_mode_var # This line makes the entry save and load
        # casting_cb = CTkComboBox(casting_mode, values=["Perfect", "Normal"], 
        #                        variable=casting_mode_var, command=lambda v: self.set_status(f"Casting Mode: {v}")
        #                        ) # These 3 lines initializes the combobox
        # casting_cb.grid(row=1, column=1, padx=12, pady=10, sticky="w") # This line initializes the position for the comboboxes (most important)
        # self.comboboxes["casting_mode"] = casting_cb # This line makes the entry save and load
        pass
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
    # Get Items To Load Tos
    def load_app_state(self):
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

        # Important: Detection Logic
        is_first_launch = state["version"] is None
        is_new_version = state["version"] != APP_VERSION

        return state, is_first_launch, is_new_version

    def save_app_state(self, state):
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
        try:
            self.save_editor_to_ahk_file(name)
        except Exception as e:
            self.set_status(f"Error saving AHK: {e}")
            return
        self.save_misc_settings()
        self._apply_hotkeys_from_vars()
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
        config_folder = os.path.join(CONFIG_DIR, name.replace(".json", ""))
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
        # Load AHK script — prefer recording.ahk on disk so the editor always
        # reflects the actual script file (handles external edits and post-record state).
        try:
            if hasattr(self, "editor_textbox"):
                ahk_path = os.path.join(CONFIG_DIR, name.replace(".json", ""), "recording.ahk")
                script = ""
                if os.path.exists(ahk_path):
                    try:
                        with open(ahk_path, "r", encoding="utf-8") as f:
                            script = f.read()
                    except Exception as e:
                        print(f"Error reading recording.ahk: {e}")
                        script = data.get("ahk_script", "")
                else:
                    # Fallback to whatever was saved in config.json
                    script = data.get("ahk_script", "")

                self.editor_textbox.delete("1.0", "end")
                self.editor_textbox.insert("1.0", script)

        except Exception as e:
            print(f"Error loading script: {e}")
        # Save Misc Settings And Show Status
        self.load_misc_settings()
        self.set_status(f"Config loaded: {name}")
    def _collect_settings_data(self):

        data = {}

        for key, var in self.vars.items():

            if key in EXCLUDED_KEYS:
                continue

            if hasattr(var, "get") and var is not None:
                try:
                    data[key] = var.get()
                except Exception as e:
                    print(f"Skipping {key}: {e}")

        # Save editor script directly into config
        if hasattr(self, "editor_textbox"):
            data["ahk_script"] = self.editor_textbox.get("1.0", "end").strip()

        return data
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
                    self.current_config_name = data.get("last_config", "Basic config")
                    # Important: Load Hotkeys If Present
                    start_playback_key = data.get("start_playback_key", "F5")
                    change_key = data.get("start_recording_key", "F6")
                    stop_recording_key = data.get("stop_recording_key", "F8")
                    stop_playback_key = data.get("stop_playback_key", "F7")

                    self.vars["start_playback_key"].set(start_playback_key)
                    self.vars["start_recording_key"].set(change_key)
                    self.vars["stop_recording_key"].set(stop_recording_key)
                    self.vars["stop_playback_key"].set(stop_playback_key)

                    # Convert To Pynput Keys
                    self.hotkey_start_recording = self._string_to_key_2(start_playback_key)
                    self.hotkey_stop_recording = self._string_to_key_2(change_key)
                    self.hotkey_start = self._string_to_key_2(stop_recording_key)
                    self.hotkey_stop = self._string_to_key_2(stop_playback_key)
            else:
                self.current_config_name = "Basic config"
        except:
            self.current_config_name = "Basic config"
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
        # Update Fields (Merge Only)
        data["last_config"] = self.current_config_name
        # Save Hotkeys
        data["start_playback_key"] = self.vars["start_playback_key"].get()
        data["start_recording_key"] = self.vars["start_recording_key"].get()
        data["stop_recording_key"] = self.vars["stop_recording_key"].get()
        data["stop_playback_key"] = self.vars["stop_playback_key"].get()
        # Write Merged Result
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    # config Utilities
    def add_config(self):
        """Add a new config configuration with user input."""
        # Create A Dialog Window To Ask For config Name
        dialog = CTkToplevel(self)
        dialog.title("Add New config")
        dialog.geometry("300x120")
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
        label = CTkLabel(dialog, text="Enter config Name:")
        label.pack(pady=10)
        
        # Entry
        entry = CTkEntry(dialog, width=250)
        entry.pack(pady=5)
        entry.focus()
        
        result = {"name": None, "confirmed": False}
        
        def on_confirm():
            new_name = entry.get().strip()
            if not new_name:
                messagebox.showwarning("Invalid Input", "config name cannot be empty!")
                return
            
            # Check If Name Already Exists
            if new_name in self.get_config_list():
                messagebox.showwarning("Duplicate Name", f"config '{new_name}' already exists!")
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
            
            # Create Config.Json With Default Settings
            config_data = {
                "stopping_distance": 2.0,
                "velocity_smoothing": 0.45,
                "movement_threshold": 3.0
            }
            
            with open(os.path.join(config_folder, "config.json"), "w") as f:
                json.dump(config_data, f, indent=4)
            
            # Update Dropdown And Select New Config
            self.config_dropdown.configure(values=self.get_config_list())
            self.config_var.set(new_name)
            self.on_config_selected(new_name)
            self.set_status(f"config '{new_name}' created and selected")

    def delete_config(self):
        """Delete current config configuration with confirmation."""
        current = self.config_var.get()

        if current == "default":
            messagebox.showwarning("Cannot Delete", "Cannot delete the default config!")
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
                import shutil
                shutil.rmtree(config_folder)
                
                # Update Dropdown And Switch To Default
                new_list = self.get_config_list()
                self.config_dropdown.configure(values=new_list)
                self.config_var.set("default")
                self.on_config_selected("default")
                self.set_status(f"config '{current}' deleted. Switched to default.")
            except Exception as e:
                messagebox.showerror("Delete Error", f"Failed to delete config: {e}")

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

    def get_default_settings(self):
        return dict(self.default_settings_data)
    def save_recording_to_txt(self):
        """Save recorded actions into a real .ahk file."""

        config_name = self.config_var.get()
        config_folder = os.path.join(CONFIG_DIR, config_name)
        os.makedirs(config_folder, exist_ok=True)

        ahk_path = os.path.join(config_folder, "recording.ahk")
        self.recording_file = ahk_path

        try:
            with open(ahk_path, "w", encoding="utf-8") as f:

                # HEADER
                f.write("; AutoHotKey Script Generated by PyWare Automate\n")
                f.write("F5:: ; Start macro\n")
                f.write("    SetBatchLines, -1\n")
                f.write("    SetKeyDelay, -1, -1\n")
                f.write("    SetMouseDelay, -1\n")
                f.write("    SetDefaultMouseSpeed, 0\n")
                f.write("    SendMode, Input\n")
                f.write("    ; ---- Start of Macro ----\n")

                # BODY
                for action in self.recorded_actions:
                    f.write(f"    {action}\n")

                # END BLOCK
                f.write("    ; ---- End of Macro ----\n")
                f.write("return\n\n")

                # EXIT HOTKEY
                f.write("F7::\n")
                f.write("    ExitApp\n")
                f.write("return\n")

                # PYWARE COMPATIBILITY LAYER
                f.write("; --- PyWare Compatibility Layer ---\n")
                f.write("StartCaptureThread() {\n")
                f.write("    return\n")
                f.write("}\n\n")

                f.write("StopCaptureThread() {\n")
                f.write("    return\n")
                f.write("}\n")
                f.write("; ---------------------------------\n\n")

            self.set_status(f"Saved AHK to: {ahk_path}")

        except Exception as e:
            self.set_status(f"Error saving AHK: {e}")
    def save_editor_to_ahk_file(self, name=None):
        """Write the current editor contents to the active config's recording.ahk."""
        if not hasattr(self, "editor_textbox"):
            return None

        config_name = name if name is not None else self.config_var.get()
        config_folder = os.path.join(CONFIG_DIR, config_name.replace(".json", ""))
        os.makedirs(config_folder, exist_ok=True)

        ahk_path = os.path.join(config_folder, "recording.ahk")
        script = self.editor_textbox.get("1.0", "end-1c")

        with open(ahk_path, "w", encoding="utf-8") as f:
            f.write(script)

        self.recording_file = ahk_path
        return ahk_path
    def load_recording_file(self):
        """
        Load the recording file from the active config subfolder.
        Structure:
            configs/ConfigName/recording.ahk
        """

        config_var = self.vars.get("active_config", self.config_var)
        config_name = config_var.get()
        config_dir = CONFIG_DIR
        config_folder = os.path.join(config_dir, config_name.replace(".json", ""))

        # Always ensure the config subfolder exists
        os.makedirs(config_folder, exist_ok=True)

        # Define expected paths
        ahk_path = os.path.join(config_folder, "recording.ahk")

        # Always guarantee file exists
        if not os.path.exists(ahk_path):
            with open(ahk_path, "w", encoding="utf-8") as f:
                f.write("")

        path = ahk_path  # ALWAYS DEFINED
        self.recording_file = path

        # Read file
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.recorded_actions = []

            for line in lines:
                line = line.strip()

                # Skip non-macro lines in AHK scripts
                if not line:
                    continue
                if line.startswith(";"):
                    continue
                if line.startswith("F5::"):
                    continue
                if line.startswith("F7::"):
                    continue
                if line.lower() == "return":
                    continue

                self.recorded_actions.append(line)

            # print("Loaded", len(self.recorded_actions), "actions from", path)

        except Exception as e:
            print("Error loading recording (load_recording_file):", e)
            self.recorded_actions = []
    def _load_recording_file_and_signal(self, done_event):
        try:
            self.load_recording_file()
        finally:
            done_event.set()
    # Key Press Functions
    def _apply_hotkeys_from_vars(self):
        """Apply hotkey StringVars to the live hotkey attributes used by on_key_press."""
        self.hotkey_start = self._string_to_key_2(self.vars["start_playback_key"].get())
        self.hotkey_start_recording = self._string_to_key_2(self.vars["start_recording_key"].get())
        self.hotkey_stop_recording = self._string_to_key_2(self.vars["stop_recording_key"].get())
        self.hotkey_stop = self._string_to_key_2(self.vars["stop_playback_key"].get())
        # Show Status Lines
    def _string_to_key_2(self, key_string):
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
        enable_hotkeys = (self.vars["enable_hotkeys"].get() or "on")
        # Save Settings (No Prompt - Auto Save Before Macro Starts)
        config_name = self.config_var.get()
        # Refresh live hotkey objects from the current StringVars
        self._apply_hotkeys_from_vars()

        auto_zoom = self.vars.get("auto_zoom")
        casting_mode = self.vars.get("casting_mode")

        if enable_hotkeys == "on":
            if pressed_key == self._normalize_hotkey_value(self.hotkey_start_recording) and not self.macro_running:
                self.save_settings(config_name, prompt=True)
                if auto_zoom is not None and casting_mode is not None and auto_zoom.get() == "on" and casting_mode.get() == "Perfect":
                    messagebox.showwarning("Error", "Auto Zoom In and Perfect Cast can't be enabled at once. \nDisable one of them to continue.")
                else:
                    self.macro_running = True
                    self.after(0, self.withdraw)
                    threading.Thread(target=self.start_recording, daemon=True).start() # This Will Start The Macro In A New Thread, Allowing The Gui To Remain Responsive
            elif pressed_key == self._normalize_hotkey_value(self.hotkey_stop_recording):
                self.stop_recording()
            elif pressed_key == self._normalize_hotkey_value(self.hotkey_start) and not self.macro_running:
                    try:
                        self.save_editor_to_ahk_file()
                    except Exception as e:
                        self.set_status(f"Error saving AHK: {e}")
                        return
                    self.macro_running = True
                    self.after(0, self.withdraw)
                    threading.Thread(target=self.start_playback, daemon=True).start() # This Will Start The Macro In A New Thread, Allowing The Gui To Remain Responsive
            elif pressed_key == self._normalize_hotkey_value(self.hotkey_stop):
                self.stop_playback()
        else:
            self.save_settings(config_name, prompt=False)
    def on_key_press(self, key):
        pressed_key = self.normalize_key(key)
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
    def _invalidate_scale_cache(self):
        """Force _get_scale_factor to re-query on next call (e.g. window moved to another monitor)."""
        self._scale_cache = None
    # Recording and playback
    def _string_to_key(self, key_string):
        key_string = key_string.strip().lower()

        # --- 1. SC-code normalization ----
        if key_string.startswith("sc"):
            sc = key_string

            # Ensure lowercase
            sc = sc.lower()

            # Direct mapping (SC63 -> f5)
            if sc in SC_TO_KEY:  # SC_TO_KEY is now module-level
                key_string = SC_TO_KEY[sc]  # replace SC-code with usable name

            # After replacement, fall through and let Key[...] handle it
            # or literal character return

        # --- 2. Normal pynput Key lookup ---
        try:
            return Key[key_string]
        except KeyError:
            return key_string  # normal character keys
    def _unified_key_press(self, key):
        """Single on_press handler: recording capture + hotkey dispatch."""
        if self.is_recording:
            self.on_key_press_record(key)
        # Always run hotkey logic so F7/F8 can stop an active recording/playback
        self.on_key_press(key)

    def _unified_key_release(self, key):
        """Single on_release handler: only needed during recording."""
        if self.is_recording:
            self.on_key_release_record(key)

    def _unified_mouse_click(self, x, y, button, pressed):
        """Single on_click handler: recording capture only."""
        if self.is_recording:
            self.on_mouse_click(x, y, button, pressed)

    def _unified_mouse_move(self, x, y):
        """Single on_move handler: recording capture only."""
        if self.is_recording:
            self.on_mouse_move(x, y)

    def on_mouse_click(self, x, y, button, pressed):
        button_name = str(button).replace("Button.", "")
        x = round(x)
        y = round(y)
        event = f"Click, {x}, {y}, {'Down' if pressed else 'Up'} {button_name}"
        self.record_action(event)

    def on_mouse_move(self, x, y):
        self.latest_mouse_move = (x, y)
    def _normalize_key_for_ahk(self, key):
        """
        Converts pynput keys into valid AHK-friendly key names.
        Fixes <63>, <65288>, ctrl_l, shift_r, etc.
        """

        # --- If key is a special Key object (Key.enter, Key.shift, etc.) ---
        if isinstance(key, Key):
            special_map = {
                Key.alt: "Alt",
                Key.alt_l: "Alt",
                Key.alt_r: "Alt",
                Key.ctrl: "Ctrl",
                Key.ctrl_l: "Ctrl",
                Key.ctrl_r: "Ctrl",
                Key.shift: "Shift",
                Key.shift_l: "Shift",
                Key.shift_r: "Shift",
                Key.enter: "Enter",
                Key.space: "Space",
                Key.tab: "Tab",
                Key.backspace: "Backspace",
                Key.delete: "Delete",
                Key.esc: "Esc",
                Key.up: "Up",
                Key.down: "Down",
                Key.left: "Left",
                Key.right: "Right",
            }
            return special_map.get(key, str(key).replace("Key.", "").title())

        # --- If it's a character key ---
        if hasattr(key, "char") and key.char:
            c = key.char
            if c.isalnum():
                return c  # safe: letters + numbers

            # return raw character, wrapping will be handled later
            return c

        # --- Fallback: convert <63> => SC063 ---
        s = str(key)

        if s.startswith("<") and s.endswith(">"):
            code = s[1:-1]
            return f"sc{code.lower()}"

        # Default clean-up
        s = s.replace("Key.", "")
        return s
    def on_key_press_record(self, key):
        key_name = self._normalize_key_for_ahk(key)

        # Always wrap in braces for AHK correctness
        event = f"Send, {{{key_name} down}}"
        self.record_action(event)

    def on_key_release_record(self, key):
        key_name = self._normalize_key_for_ahk(key)
        if key_name == "sc63": # Disable this specific unknown key
            event = f"; Disabled"
        else:
            event = f"Send, {{{key_name} up}}"
        self.record_action(event)
    def start_capture_thread(self):
        if self.capture_running:
            return
        self.capture_scan_delay = float(self.vars["scan_delay"].get())
        self.capture_running = True

        # Reset stop event
        self.capture_stop_event.clear()

        # Optional: pull from UI/config
        try:
            self.capture_scan_delay = float(self.vars.get("scan_delay", 0.01).get())
        except:
            self.capture_scan_delay = 0.01

        self.capture_thread = threading.Thread(
            target=self._capture_loop_full,
            args=(self.capture_stop_event, self.capture_scan_delay),
            daemon=True
        )
        self.capture_thread.start()
    def stop_capture_thread(self):
        if not self.capture_running:
            return

        self.capture_running = False

        # Signal stop
        self.capture_stop_event.set()

        if self.capture_thread:
            self.capture_thread.join(timeout=1)
            self.capture_thread = None
    def record_action(self, action_text):
        """Record delay + the action into recorded_actions list."""

        now = time.time()
        delay = now - self.last_action_time
        self.last_action_time = now

        # Add delay directly (NO recursive call!)
        if delay > 0.001:
            delay2 = int(delay * 1000)
            self.recorded_actions.append(f"Sleep, {delay2}")

        # Add the actual action
        self.recorded_actions.append(action_text)
    # Loops
    def add_loop_start(self, count):
        self.recorded_actions.append(f"Loop, {count}")
        self.recorded_actions.append("{")

    def add_loop_end(self):
        self.recorded_actions.append("}")
        
    # PLAYBACK ENGINE
    def execute_script(self, actions, speed=1.0):
        """
        Top-level entry point.  Parses the flat action list into a tree of
        Block objects and then runs them through _exec_block, which handles
        loops, variables, and if/else/endif nesting at every depth.
        """
        # Normalize actions: split lines that have braces mixed with keywords
        # e.g. "if (cond) {" -> "if (cond)", "{"
        # e.g. "} else {"    -> "}", "else", "{"
        normalized = []
        for line in actions:
            s = self._strip_inline_comment(line).strip()
            if not s:
                normalized.append(line)
                continue
            
            # Skip normalization for Send commands as they use braces for keys
            if s.lower().startswith("send"):
                normalized.append(s)
                continue

            # Keep function definitions intact so the parser can discard their
            # bodies without mistaking them for executable function calls.
            if self._is_function_definition(s):
                normalized.append(s)
                continue

            # Split leading } if it's not a standalone brace
            if s.startswith("}") and len(s) > 1:
                normalized.append("}")
                s = s[1:].strip()
            
            # Split trailing { if it's not a standalone brace
            if s.endswith("{") and len(s) > 1:
                normalized.append(s[:-1].strip())
                normalized.append("{")
            else:
                if s: normalized.append(s)

        block = self._parse_block(normalized, 0, len(normalized))
        self._exec_block(block, speed)

    # --- Parser -------------------------------------------------------- #

    def _parse_block(self, actions, start, end):
        """
        Converts a slice of the flat actions list (indices [start, end))
        into a list of node dicts that the executor understands.

        Node kinds
        ----------
        {"kind": "line",   "text": str}
        {"kind": "loop",   "count": int|None, "body": [nodes]}   # None = infinite
        {"kind": "while",  "condition": str,  "body": [nodes]}
        {"kind": "if",     "condition": str,
                           "then": [nodes], "else_": [nodes]}
        """
        nodes = []
        i = start

        while i < end:
            raw = actions[i].strip()

            # ---- skip structural noise ----
            if self._should_skip_line(raw):
                i += 1
                continue

            lower = raw.lower()

            # ---- Function definition blocks ----
            # Compatibility functions such as StartCaptureThread() { return }
            # should not run here, but calls like StartCaptureThread() should.
            if self._is_function_definition(raw):
                i += 1
                if i < end and actions[i].strip() == "{":
                    i += 1
                _, i = self._collect_block_body(actions, i, end)
                continue

            # ---- Loop, N  /  Loop (infinite) ----
            if re.match(r"^loop\b", lower):
                count, body_nodes, i = self._parse_loop_node(actions, i, end)
                nodes.append({"kind": "loop", "count": count, "body": body_nodes})
                continue

            # ---- While, <condition> ----
            if re.match(r"^while\b", lower):
                condition, body_nodes, i = self._parse_while_node(actions, i, end)
                nodes.append({"kind": "while", "condition": condition, "body": body_nodes})
                continue

            # ---- If, <condition> ----
            if re.match(r"^if\b", lower):
                then_nodes, else_nodes, condition, i = self._parse_if_node(actions, i, end)
                nodes.append({"kind": "if", "condition": condition,
                               "then": then_nodes, "else_": else_nodes})
                continue

            # ---- Try / Catch ----
            if re.match(r"^try\b", lower):
                result = self._parse_try_catch(actions, i)
                if result is None:
                    raise PlaybackError(f"Invalid TRY/CATCH block starting at: {actions[i]}")
                try_nodes = self._parse_block(result["try_block"], 0, len(result["try_block"]))
                catch_nodes = self._parse_block(result["catch_block"], 0, len(result["catch_block"]))
                nodes.append({
                    "kind": "try",
                    "try": try_nodes,
                    "catch": catch_nodes,
                    "catch_var": result.get("catch_var"),
                })
                i = result["end_index"]
                continue

            # ---- Else / EndIf / closing brace → handled by callers ----
            if lower in ("else", "endif") or raw == "}":
                break

            # ---- Plain line ----
            nodes.append({"kind": "line", "text": raw})
            i += 1

        return nodes

    def _collect_block_body(self, actions, i, end):
            """
            Reads lines until the matching closing brace or until a keyword
            that terminates the block (else / endif).
            Returns (body_lines, new_i).

            Supports both brace-delimited  { … }  and brace-less (one-liners).
            """
            if i < end and actions[i].strip() == "{":
                i += 1  # skip standalone opening brace

            depth = 0
            body_lines = []
            while i < end:
                stripped = actions[i].strip()

                if stripped == "{":
                    depth += 1
                    body_lines.append(stripped)  # keep inner braces for nested blocks
                    i += 1
                    continue

                if stripped.startswith("}"):
                    if depth == 0:
                        if stripped == "}":
                            i += 1
                        break
                    depth -= 1
                    body_lines.append(stripped)  # keep inner braces for nested blocks
                    i += 1
                    continue

                lower = stripped.lower()
                if depth == 0 and (lower == "else" or lower.startswith("else ") or lower == "endif" or lower.startswith("endif ")):
                    break

                body_lines.append(stripped)
                i += 1

            return body_lines, i

    def _parse_loop_node(self, actions, i, end):
        """Parse  Loop[, N]  { … }  and return (count, body_nodes, new_i)."""
        header = actions[i].strip()
        i += 1

        # Extract count from  "Loop, 10"  or  "Loop, 10 {"  or just  "Loop"
        m = re.match(r"loop\s*(?:,\s*(\d+))?", header, re.IGNORECASE)
        count = int(m.group(1)) if (m and m.group(1)) else None  # None = infinite

        # Consume optional opening brace on same line or next line
        if i < end and actions[i].strip() == "{":
            i += 1

        body_lines, i = self._collect_block_body(actions, i, end)
        body_nodes = self._parse_block(body_lines, 0, len(body_lines))
        return count, body_nodes, i

    def _parse_while_node(self, actions, i, end):
        """Parse  While, <condition>  { … }  and return (condition, body_nodes, new_i)."""
        header = actions[i].strip()
        i += 1

        m = re.match(r"while\s*,?\s*(.+)", header, re.IGNORECASE)
        condition = m.group(1).strip() if m else "False"

        if i < end and actions[i].strip() == "{":
            i += 1

        body_lines, i = self._collect_block_body(actions, i, end)
        body_nodes = self._parse_block(body_lines, 0, len(body_lines))
        return condition, body_nodes, i

    def _parse_if_node(self, actions, i, end):
        """
        Parse an If block in either AHK style:
            If, ErrorLevel = 0  { … }          (comma-separated)
            if (ErrorLevel == 0) { … }          (parenthesis-style)
        Returns (then_nodes, else_nodes, condition, new_i).
        """
        header = actions[i].strip()
        i += 1

        # Parenthesis style:  if (cond)
        m = re.match(r"if\s*\((.+)\)", header, re.IGNORECASE)
        if m:
            condition = m.group(1).strip()
        else:
            # Comma style:  If, cond  or  If cond
            m = re.match(r"if\s*,?\s*(.+)", header, re.IGNORECASE)
            condition = m.group(1).strip() if m else "False"

        if i < end and actions[i].strip() == "{":
            i += 1

        then_lines, i = self._collect_block_body(actions, i, end)
        then_nodes = self._parse_block(then_lines, 0, len(then_lines))

        # Check for Else
        else_nodes = []
        if i < end:
            raw_else = actions[i].strip()
            s = raw_else.lower()

            # Support AHK-style "else if" chains by parsing them as a nested
            # if-node inside the else branch.
            if re.match(r"^else\s+if\b", s):
                nested_header = re.sub(r"^else\s+", "", raw_else, count=1, flags=re.IGNORECASE)
                nested_actions = [nested_header] + actions[i + 1:end]
                nested_then, nested_else, nested_condition, nested_i = self._parse_if_node(
                    nested_actions, 0, len(nested_actions)
                )
                else_nodes = [{
                    "kind": "if",
                    "condition": nested_condition,
                    "then": nested_then,
                    "else_": nested_else,
                }]
                i += nested_i

            elif s == "else" or s.startswith("else{"):
                i += 1  # consume "else"
                if i < end and actions[i].strip() == "{":
                    i += 1
                else_lines, i = self._collect_block_body(actions, i, end)
                else_nodes = self._parse_block(else_lines, 0, len(else_lines))

        # Consume optional EndIf
        if i < end:
            s = actions[i].strip().lower()
            if s == "endif" or s.startswith("endif "):
                i += 1

        return then_nodes, else_nodes, condition, i

    # Executor
    def _exec_block(self, nodes, speed):
        """
        Recursively execute a list of parsed nodes.
        Respects self.macro_running so F7 stops everything immediately.
        """
        for node in nodes:
            if not self.macro_running:
                return

            kind = node["kind"]

            if kind == "line":
                self._exec_line(node["text"], speed)

            elif kind == "loop":
                count = node["count"]
                body  = node["body"]
                if count is None:
                    # Infinite loop; self.macro_running or AHK break exits it.
                    while self.macro_running:
                        try:
                            self._exec_block(body, speed)
                        except AhkContinue:
                            continue
                        except AhkBreak:
                            break
                else:
                    for _ in range(count):
                        if not self.macro_running:
                            return
                        try:
                            self._exec_block(body, speed)
                        except AhkContinue:
                            continue
                        except AhkBreak:
                            break

            elif kind == "while":
                while self.macro_running and self._evaluate_condition(
                        self._resolve_variables(node["condition"])):
                    try:
                        self._exec_block(node["body"], speed)
                    except AhkContinue:
                        continue
                    except AhkBreak:
                        break

            elif kind == "if":
                resolved_cond = self._resolve_variables(node["condition"])
                if self._evaluate_condition(resolved_cond):
                    self._exec_block(node["then"], speed)
                else:
                    self._exec_block(node["else_"], speed)

            elif kind == "try":
                try:
                    self._exec_block(node["try"], speed)
                except PlaybackError as e:
                    if node["catch"]:
                        catch_var = node.get("catch_var")
                        if catch_var:
                            self.variables[catch_var] = str(e)
                        self._exec_block(node["catch"], speed)
                    else:
                        raise

    def _exec_line(self, line, speed):
        """Execute a single resolved action line."""
        line = self._strip_inline_comment(line).strip()
        lower = line.lower()

        if lower == "break":
            raise AhkBreak()

        if lower == "continue":
            raise AhkContinue()

        # Variable assignment  (x := expr)
        if self._handle_assignment(line):
            return
        # Math shorthand  (x += 5 / x -= 2 / x *= 3 / x /= 2)
        if self._handle_math(line):
            return
        # Substitute %Var% tokens before dispatching
        line = self._handle_variable(line)
        self.playback_action(line, speed)
    # Playback functions
    def _handle_assignment(self, action):
        """
        Handles:
        x := 612
        y := ABC
        """

        if ":=" in action:
            var, value = action.split(":=", 1)

            var = var.strip()
            value = value.strip()

            # Prevent overwriting built-ins
            if var in self.builtin_variables:
                self.raise_error(
                    action,
                    f"Cannot overwrite built-in variable: {var}"
                )

            # Numeric values
            # Build a merged namespace: builtins first, then user vars (user vars win on conflict)
            eval_namespace = {**self.builtin_variables, **self.variables}
            try:
                self.variables[var] = eval(value, {}, eval_namespace)

            # Raw expression/string
            except:
                self.variables[var] = value

            return True

        return False
    def _handle_math(self, action):
        """
        Handles compound assignment operators:
            x += 5   x -= 2   x *= 3   x /= 2
        Values on the right-hand side may themselves be expressions or
        %variable% references, so we resolve them before evaluating.
        """
        for op in ("+=", "-=", "*=", "/="):
            if op in action:
                var, rhs = action.split(op, 1)
                var = var.strip()
                rhs = self._handle_variable(rhs.strip())
                try:
                    rhs_val = float(eval(rhs))
                except Exception:
                    return False

                cur = self.variables.get(var, 0)
                try:
                    cur = float(cur)
                except Exception:
                    cur = 0.0

                if op == "+=":
                    self.variables[var] = cur + rhs_val
                elif op == "-=":
                    self.variables[var] = cur - rhs_val
                elif op == "*=":
                    self.variables[var] = cur * rhs_val
                elif op == "/=":
                    self.variables[var] = cur / rhs_val if rhs_val != 0 else 0
                return True

        return False

    def _handle_variable(self, text):
        def replacer(match):
            var_name = match.group(1)

            # Priority: user variables
            if var_name in self.variables:
                return str(self.variables[var_name])

            # Then builtin variables
            if var_name in self.builtin_variables:
                return str(self.builtin_variables[var_name])

            return ""  # or keep original if you prefer strict mode

        return re.sub(r"%(\w+)%", replacer, text)
    def _should_skip_line(self, line):
        line = line.strip()

        if not line:
            return True

        # Hotkeys / labels
        if line.endswith("::"):
            return True

        # Block markers
        if line in ("{", "}"):
            return True

        # AHK boilerplate
        if line.startswith((
            "SetBatchLines",
            "SetKeyDelay",
            "SetMouseDelay",
            "SetTitleMatchMode",
            "SendMode"
        )):
            return True

        # Flow control noise
        if line.lower() == "return":
            return True

        return False

    def _strip_inline_comment(self, line):
        """
        Remove AHK inline comments while preserving semicolons inside text.
        A semicolon starts a comment when it begins a line or follows
        whitespace, matching the common AHK style used in bundled scripts.
        """
        in_single = False
        in_double = False

        for idx, char in enumerate(line):
            if char == '"' and not in_single:
                in_double = not in_double
            elif char == "'" and not in_double:
                in_single = not in_single
            elif char == ";" and not in_single and not in_double:
                if idx == 0 or line[idx - 1].isspace():
                    return line[:idx].rstrip()

        return line

    def _is_function_definition(self, line):
        if not re.match(r"^[A-Za-z_]\w*\s*\([^)]*\)\s*\{?\s*$", line):
            return False
        if re.match(r"^(if|while|loop|for)\b", line, re.IGNORECASE):
            return False
        return line.rstrip().endswith("{")
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
            # Prefer Tk scaling
            try:
                tk_dpi = self.winfo_fpixels('1i')
                scale = tk_dpi / 72.0
                scale = max(1.0, min(scale, 4.0))
                self._scale_cache = scale
                return scale
            except Exception:
                pass
            # Fallback to Quartz
            try:
                main_display = Quartz.CGMainDisplayID()
                pixel_width = Quartz.CGDisplayPixelsWide(main_display)
                bounds = Quartz.CGDisplayBounds(main_display)
                logical_width = bounds.size.width
                scale = pixel_width / logical_width if logical_width else 1.0
                scale = max(1.0, min(scale, 4.0))
                self._scale_cache = scale
            except Exception:
                self._scale_cache = 1.0
        else:
            self._scale_cache = 1.0
        return self._scale_cache
    def _invalidate_scale_cache(self):
        """Force _get_scale_factor to re-query on next call (e.g. window moved to another monitor)."""
        self._scale_cache = None
    # _handle_loop removed — loop parsing is now done by _parse_loop_node
    # inside the block-aware execute_script engine.
    def _clean_ahk_braces(self, key_raw):
        # Remove braces like {Enter}, {Down}, {Space}
        key_raw = key_raw.strip()

        if key_raw.startswith("{") and key_raw.endswith("}"):
            key_raw = key_raw[1:-1]  # strip {}

        return key_raw.lower()
    def raise_error(self, action, description="Syntax error"):
        msg = (
            f"Error: The script contains syntax errors.\n"
            f"Specifically:\n"
            f"    {action}\n"
            f"    {description}"
        )
        print(f"[PlaybackError] {action} -> {description}")
        raise PlaybackError(msg)
    def release_all_keys(self):
        for key in list(self.held_keys):
            try:
                keyboard_controller.release(key)
            except:
                pass
        self.held_keys.clear()
    def force_release_modifiers(self):
        for key in [Key.ctrl, Key.shift, Key.alt]:
            try:
                keyboard_controller.release(key)
            except:
                pass
    def _resolve_variables(self, text):
        def replacer(match):
            var_name = match.group(1)
            return str(self.variables.get(var_name, f"%{var_name}%"))

        return re.sub(r"%(.+?)%", replacer, text)
    # Functions to support pipelines
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

        _mac_floor = 0.033 if sys.platform == "darwin" else 0.0

        try:
            while not stop_event.is_set():
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
    def get_latest_frame(self):
        with self.capture_lock:
            return None if self.latest_frame is None else self.latest_frame.copy()
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
    def _find_first_pixel(self, frame, target_rgb, tolerance=8):
        tolerance = int(np.clip(tolerance, 0, 255))

        frame_i = frame.astype(np.int16)
        target = np.array(target_rgb, dtype=np.int16)

        mask = np.max(
            np.abs(frame_i - target),
            axis=-1
        ) <= tolerance
        
        coords = np.argwhere(mask)

        if coords.size > 0:
            y, x = coords[0]
            return int(x), int(y)

        return None
    def _parse_ahk_color(self, color):
        """
        Convert AHK color (0xBBGGRR) or standard hex (#RRGGBB) to RGB tuple.
        """

        if not color:
            return None

        color = color.strip().lower()

        try:
            # --- AHK format: 0xBBGGRR ---
            if color.startswith("0x"):
                value = int(color, 16)

                b = (value >> 16) & 0xFF
                g = (value >> 8) & 0xFF
                r = value & 0xFF

                return (r, g, b)  # ✅ RGB

            # --- Standard hex: #RRGGBB ---
            if color.startswith("#"):
                color = color[1:]

                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)

                return (r, g, b)

        except Exception:
            return None

        return None
    def _parse_try_catch(self, actions, start_index):
        """
        Parses AHK-style try/catch blocks:

        try {
            ...
        }
        catch e {
            ...
        }
        """
        header = actions[start_index].strip()
        if not re.match(r"^try\b", header, re.IGNORECASE):
            return None

        i = start_index + 1
        if i < len(actions) and actions[i].strip() == "{":
            i += 1

        try_block, i = self._collect_block_body(actions, i, len(actions))

        catch_block = []
        catch_var = None

        if i < len(actions):
            catch_line = actions[i].strip()
            match = re.match(r"^catch\b\s*([A-Za-z_]\w*)?", catch_line, re.IGNORECASE)

            if match:
                catch_var = match.group(1)
                i += 1

                if i < len(actions) and actions[i].strip() == "{":
                    i += 1

                catch_block, i = self._collect_block_body(actions, i, len(actions))

        return {
            "try_block": try_block,
            "catch_block": catch_block,
            "catch_var": catch_var,
            "end_index": i
        }
    def _init_builtin_variables(self):
        import sys

        # Screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Platform mapping
        if sys.platform.startswith("darwin"):
            platform_val = 0
        elif sys.platform.startswith("linux"):
            platform_val = 1
        else:
            # Windows OR standard AHK behavior
            platform_val = -1

        self.builtin_variables = {
            "A_ScreenWidth": screen_width,
            "A_ScreenHeight": screen_height,
            "A_Platform": platform_val,
        }
    # Pipelines
    def _cmd_sleep(self, action, speed):
        _, value = action.split(",", 1)
        ms = float(value.strip())   # float() accepts "400.0" and "400"
        time.sleep((ms / 1000) / speed)
    def _cmd_mousemove(self, action, speed):
        _, args = action.split(",", 1)
        x, y = [int(v.strip()) for v in args.split(",")]
        mouse_controller.position = (x, y)
    def _cmd_click(self, action, speed):
        """
        Supports AHK Click syntax variants:
          Click                          → left click at current pos
          Click, X, Y                    → left click at X, Y
          Click, X, Y, Down Right        → press right button at X, Y
          Click, Down                    → press left button at current pos
          Click, Right                   → right click at current pos
          Click, Down Right              → press right button at current pos
          (any combination of optional X, Y, Down/Up, Left/Right/Middle)
        """
        try:
            # Split off the command name; args may be empty
            if "," in action:
                _, args = action.split(",", 1)
                parts = [p.strip() for p in args.split(",")]
            else:
                parts = []

            # Classify each token: numeric → coordinate, else → modifier word
            # AHK order: [X, Y,] [Down|Up] [Left|Right|Middle]
            coords = []
            modifiers = []
            for p in parts:
                if p == "":
                    continue
                try:
                    coords.append(int(float(p)))
                except ValueError:
                    # Could be "Down Right" in one comma-field, split on spaces
                    for word in p.split():
                        modifiers.append(word.lower())

            # Resolve X, Y
            if len(coords) >= 2:
                x, y = coords[0], coords[1]
                move = True
            else:
                move = False   # stay at current cursor position

            # Resolve button and down/up from modifier words
            btn_map = {
                "left": mouse.Button.left,
                "l":    mouse.Button.left,
                "right": mouse.Button.right,
                "r":    mouse.Button.right,
                "middle": mouse.Button.middle,
                "m":    mouse.Button.middle,
            }
            direction_words = {"down", "up"}
            button_words    = set(btn_map.keys())

            down_up = "click"   # default: full click
            button  = mouse.Button.left  # default button

            for word in modifiers:
                if word in direction_words:
                    down_up = word
                elif word in button_words:
                    button = btn_map[word]

            # Move if coordinates were supplied
            if move:
                mouse_controller.position = (x, y)

            # Execute
            if down_up == "down":
                mouse_controller.press(button)
            elif down_up == "up":
                mouse_controller.release(button)
            else:
                mouse_controller.click(button)

        except PlaybackError:
            raise
        except Exception as e:
            self.raise_error(action, str(e))
    def _tap_key(self, key, hold_ms=12):
        """
        Emit a key press with a tiny hold so repeated navigation keys
        are not collapsed by target apps when replayed via pynput.
        """
        keyboard_controller.press(key)
        time.sleep(max(hold_ms, 0) / 1000.0)
        keyboard_controller.release(key)
    def _cmd_send(self, action, speed):
        _, raw = action.split(",", 1)
        raw = raw.strip()

        if raw.startswith("{") and raw.endswith("}"):
            inner = raw[1:-1].strip()
            tokens = inner.split()

            key_name = tokens[0].lower()
            key = self._string_to_key(key_name)

            if len(tokens) == 1:
                self._tap_key(key)

            elif tokens[1] == "down":
                keyboard_controller.press(key)
                self.held_keys.add(key)

            elif tokens[1] == "up":
                keyboard_controller.release(key)
                self.held_keys.discard(key)

            return

        if raw.startswith(("^", "!", "+")):
            mod = raw[0]
            key_raw = self._clean_ahk_braces(raw[1:])
            key = self._string_to_key(key_raw)

            if mod == "^":
                keyboard_controller.press(Key.ctrl)
                self._tap_key(key)
                keyboard_controller.release(Key.ctrl)

            elif mod == "!":
                keyboard_controller.press(Key.alt)
                self._tap_key(key)
                keyboard_controller.release(Key.alt)

            elif mod == "+":
                keyboard_controller.press(Key.shift)
                self._tap_key(key)
                keyboard_controller.release(Key.shift)

            return

        key_raw = self._clean_ahk_braces(raw)
        key = self._string_to_key(key_raw)
        self._tap_key(key)
    def _cmd_pixelsearch(self, action, speed):
        try:
            _, args = action.split(",", 1)
            parts = [p.strip() for p in args.split(",")]

            out_x = parts[0]
            out_y = parts[1]

            x1 = int(float(parts[2]))
            y1 = int(float(parts[3]))
            x2 = int(float(parts[4]))
            y2 = int(float(parts[5]))

            color = parts[6]

            # Strip trailing AHK options like "Fast", "RGB"
            tolerance = 8

            if len(parts) > 7:
                try:
                    tolerance = int(float(parts[7]))
                except:
                    tolerance = 8

            mode_flags = [p.lower() for p in parts[8:]]
            fast_mode = "fast" in mode_flags
            rgb_mode = "rgb" in mode_flags

            # --- Grab frame: use capture thread if running, else one-shot ---
            if self.capture_running and hasattr(self, "_cap_lock"):
                # Wait up to 200 ms for the capture thread to produce a frame
                if hasattr(self, "_cap_event"):
                    self._cap_event.wait(timeout=0.2)
                with self._cap_lock:
                    frame = self._cap_frame.copy() if self._cap_frame is not None else None
            else:
                # Capture thread is stopped — grab a fresh frame on-demand
                thread_local = threading.local()
                frame = self._grab_screen_full(thread_local)

            if frame is None:
                self.variables[out_x] = -1
                self.variables[out_y] = -1
                self.variables["ErrorLevel"] = 1
                return

            h, w = frame.shape[:2]

            # --- On macOS (Retina), mss captures at physical pixels but AHK
            #     coordinates are in logical points. Scale input coords up to
            #     physical pixels, then scale the found position back down. ---
            scale = self._get_scale_factor() if sys.platform == "darwin" else 1.0

            px1 = int(x1 * scale)
            py1 = int(y1 * scale)
            px2 = int(x2 * scale)
            py2 = int(y2 * scale)
            
            # --- Clamp region to frame bounds ---
            px1 = max(0, min(px1, w - 1))
            py1 = max(0, min(py1, h - 1))

            px2 = max(0, min(px2, w))
            py2 = max(0, min(py2, h))

            if px2 <= px1 or py2 <= py1:
                self.variables[out_x] = -1
                self.variables[out_y] = -1
                self.variables["ErrorLevel"] = 1
                return

            region = frame[py1:py2, px1:px2, :3]

            rgb = self._parse_ahk_color(color)
            if rgb is None:
                self.variables[out_x] = -1
                self.variables[out_y] = -1
                self.variables["ErrorLevel"] = 1
                return

            pos = self._find_first_pixel(region, rgb, tolerance)

            if pos is not None:
                fpx, fpy = pos

                self.variables[out_x] = int((fpx + px1) / scale)
                self.variables[out_y] = int((fpy + py1) / scale)
                self.variables["ErrorLevel"] = 0
            else:
                self.variables[out_x] = -1
                self.variables[out_y] = -1
                self.variables["ErrorLevel"] = 1

            # --- Pixel search ---
            pos = self._find_first_pixel(region, rgb, tolerance)

            if not pos == None:
                fpx, fpy = pos
                # Convert found physical-pixel position back to logical coords
                self.variables[out_x] = int((fpx + px1) / scale)
                self.variables[out_y] = int((fpy + py1) / scale)
                self.variables["ErrorLevel"] = 0
            else:
                self.variables[out_x] = -1
                self.variables[out_y] = -1
                self.variables["ErrorLevel"] = 1

        except PlaybackError:
            raise
        except Exception as e:
            self.raise_error(action, str(e))
    def _cmd_pixelgetcolor(self, action, speed):
        # AHK: PixelGetColor, OutputVar, X, Y [, RGB]
        try:
            _, args = action.split(",", 1)
            parts = [p.strip() for p in args.split(",")]

            out_var = parts[0]
            x = int(float(parts[1]))
            y = int(float(parts[2]))

            # --- Grab frame: use capture thread if running, else one-shot ---
            if self.capture_running and hasattr(self, "_cap_lock"):
                if hasattr(self, "_cap_event"):
                    self._cap_event.wait(timeout=0.2)
                with self._cap_lock:
                    frame = self._cap_frame.copy() if self._cap_frame is not None else None
            else:
                thread_local = threading.local()
                frame = self._grab_screen_full(thread_local)

            if frame is None:
                self.variables[out_var] = 0
                self.variables["ErrorLevel"] = 1
                return

            h, w = frame.shape[:2]
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))

            # frame is BGR (from mss): index [y, x] -> (B, G, R)
            b, g, r = int(frame[y, x, 0]), int(frame[y, x, 1]), int(frame[y, x, 2])

            # AHK PixelGetColor returns 0xBBGGRR
            color_val = (b << 16) | (g << 8) | r
            self.variables[out_var] = f"0x{color_val:06X}"
            self.variables["ErrorLevel"] = 0

        except PlaybackError:
            raise
        except Exception as e:
            self.raise_error(action, str(e))

    def _cmd_mousegetpos(self, action, speed):
        # AHK: MouseGetPos [, OutX, OutY]
        try:
            parts = []
            if "," in action:
                _, args = action.split(",", 1)
                parts = [p.strip() for p in args.split(",")]

            out_x = parts[0] if len(parts) > 0 else "MouseX"
            out_y = parts[1] if len(parts) > 1 else "MouseY"

            pos = mouse_controller.position
            self.variables[out_x] = int(pos[0])
            self.variables[out_y] = int(pos[1])

        except PlaybackError:
            raise
        except Exception as e:
            self.raise_error(action, str(e))

    def _cmd_startcapturethread(self, action, speed):
        self.start_capture_thread()

    def _cmd_stopcapturethread(self, action, speed):
        self.stop_capture_thread()
    def _cmd_msgbox(self, action, speed):
        try:
            # Split once after command
            _, args = action.split(",", 1)

            # Split parameters
            parts = [p.strip() for p in args.split(",")]

            # Apply variable substitution BEFORE using values
            parts = [self._handle_variable(p) for p in parts]

            # Default values
            options = None
            title = ""
            text = ""

            # AHK supports multiple forms:
            if len(parts) == 1:
                # MsgBox, Text
                text = parts[0]

            elif len(parts) == 2:
                # MsgBox, Options, Text
                options = parts[0]
                text = parts[1]

            elif len(parts) >= 3:
                # MsgBox, Options, Title, Text
                options = parts[0]
                title = parts[1]
                text = parts[2]

            # Show messagebox
            messagebox.showinfo(title if title else "recording.ahk", text)

        except PlaybackError:
            raise
        except Exception as e:
            self.raise_error(action, str(e))
    def _create_tooltip_pool(self):
        """Create the 20 reusable AHK tooltip windows hidden at startup."""
        bg_color = "#FFFFFF"

        for tooltip_id in range(1, 21):
            if tooltip_id in self._tooltips:
                continue

            tooltip = tk.Toplevel(self)
            tooltip.withdraw()
            tooltip.overrideredirect(True)
            tooltip.configure(bg=bg_color)

            label = tk.Label(
                tooltip,
                text="",
                bg=bg_color,
                fg="black",
                bd=0,
                padx=2,
                pady=0,
                font=("Segoe UI", 13),
                anchor="w",
                justify="left"
            )
            label.pack(padx=0, pady=0, ipadx=0, ipady=0)

            if sys.platform == "darwin":
                try:
                    tooltip.call(
                        "tk::unsupported::MacWindowStyle",
                        "style",
                        tooltip._w,
                        "help",
                        "noActivates doesNotActivateOnClick"
                    )
                except:
                    pass

            self._tooltips[tooltip_id] = {
                "window": tooltip,
                "label": label
            }

    def _show_tooltip(self, tooltip_id, text, x, y):
        tooltip_data = self._tooltips.get(tooltip_id)
        if not tooltip_data:
            return

        tooltip = tooltip_data["window"]
        label = tooltip_data["label"]

        label.configure(text=text)
        tooltip.update_idletasks()
        tooltip.geometry(f"+{x}+{y}")
        tooltip.deiconify()
        tooltip.attributes("-topmost", True)
        tooltip.lift()

    def _hide_tooltip(self, tooltip_id):
        tooltip_data = self._tooltips.get(tooltip_id)
        if tooltip_data:
            tooltip_data["window"].withdraw()

    def _cmd_tooltip(self, action, speed):
        """
        Parse AHK syntax
        ToolTip, Text, X, Y, ID
        """
        try:
            if "," in action:
                _, args = action.split(",", 1)
                parts = [self._handle_variable(p.strip()) for p in args.split(",")]
            else:
                parts = [""]

            text = parts[0] if len(parts) > 0 else ""

            x = int(float(parts[1])) if len(parts) > 1 and parts[1] else \
                self.variables.get("MouseX", 0)

            y = int(float(parts[2])) if len(parts) > 2 and parts[2] else \
                self.variables.get("MouseY", 0)

            tooltip_id = int(parts[3]) if len(parts) > 3 and parts[3] else 1

            if not 1 <= tooltip_id <= 20:
                raise ValueError("ToolTip ID must be between 1 and 20")

            if text == "":
                self.after(0, self._hide_tooltip, tooltip_id)
            else:
                self.after(0, self._show_tooltip, tooltip_id, text, x, y)

        except PlaybackError:
            raise

        except Exception as e:
            self.raise_error(action, str(e))
    # _cmd_if and _cmd_else have been removed.
    # Conditional logic is now handled structurally by _parse_if_node /
    # _exec_block, so "If" lines never reach the dispatch map.
    def _evaluate_condition(self, condition):
        """
        Evaluate a condition string, supporting AHK-style operators.

        Examples
        --------
        ErrorLevel = 0       →  ErrorLevel == 0
        Px != -1
        Px > 100
        x >= 5 and y < 10
        """
        condition = condition.strip()

        if condition.startswith("(") and condition.endswith(")"):
            condition = condition[1:-1]

        # Normalize operators
        condition = self._normalize_condition(condition)

        # Replace %VarName% tokens
        condition = self._handle_variable(condition)

        # Replace bare variable names (no % signs) that match known variables/builtins
        def replace_bare(match):
            name = match.group(0)
            if name in self.variables:
                val = self.variables[name]
                return str(int(val)) if isinstance(val, float) and val == int(val) else str(val)
            if name in self.builtin_variables:
                val = self.builtin_variables[name]
                return str(int(val)) if isinstance(val, float) and val == int(val) else str(val)
            return name  # leave unknown words untouched (e.g. "and", "or", "not")

        condition = re.sub(r'\b[A-Za-z_]\w*\b', replace_bare, condition)

        try:
            return bool(eval(condition))
        except Exception as e:
            self.raise_error(condition, f"IF condition error: {e}")
    def _normalize_condition(self, condition):
        # Replace <> with !=
        condition = condition.replace("<>", "!=")

        # Replace = with == ONLY when it's a comparison
        condition = re.sub(r'(?<![<>=!])=(?!=)', '==', condition)

        return condition
    # Playback
    def playback_action(self, action, speed=1.0):
        action = action.strip()
        action = self._resolve_variables(action)

        # Ignore
        if action.startswith(("SetBatchLines", "SetKeyDelay", "SetMouseDelay", "SetTitleMatchMode", "SendMode")):
            return

        if action.startswith((";", "F5::", "F7::", "ExitApp")) or action.lower() == "return":
            return

        if action.startswith(("{", "}")):
            return

        # Variable assignment
        if ":=" in action:
            action = self._handle_variable(action)
            return

        # Dispatcher
        cmd = action.split(",", 1)[0].strip().lower()
        cmd = cmd.replace("()", "") # Remove empty parentheses
        handler = self.dispatch_map.get(cmd)

        if handler:
            try:
                handler(action, speed)
            except PlaybackError:
                raise
            except Exception as e:
                self.raise_error(action, str(e))
            return

        self.raise_error(action, "Unknown or unsupported command")
    def start_recording(self):
        print("Macro Status: Recording...")
        self.macro_running = True
        self.recorded_actions = []

        config_name = self.config_var.get()  # use existing system
        config_folder = os.path.join(CONFIG_DIR, config_name)

        # Ensure folder exists
        os.makedirs(config_folder, exist_ok=True)

        # Set recording path inside config folder
        self.recording_file = os.path.join(config_folder, "recording.ahk")

        self.pending_events = []
        self.latest_mouse_move = None
        self.last_record_time = time.time()
        self.last_action_time = time.time()

        scan_delay = float(self.vars["record_delay"].get() or 0.05)

        # Signal the unified listeners to start capturing events
        self.is_recording = True

        while self.macro_running:
            now = time.time()

            if now - self.last_record_time >= scan_delay:
                # Log buffered keyboard events
                if self.pending_events:
                    self.recorded_actions.extend(self.pending_events)
                    self.pending_events.clear()

                # Log last mouse position if moved
                if self.latest_mouse_move:
                    x, y = self.latest_mouse_move
                    x = round(x)
                    y = round(y)
                    self.record_action(f"MouseMove, {x}, {y}")
                    self.latest_mouse_move = None

                self.last_record_time = now

            time.sleep(0.001)  # prevent CPU burn
    def stop_recording(self):
        if not self.macro_running:
            return

        self.macro_running = False
        self.is_recording = False
        self.after(0, self.deiconify)
        print("Macro Status: Stopped Recording")

        # convert path: recording.txt → recording.ahk
        ahk_path = self.recording_file.replace(".txt", ".ahk")
        self.recording_file = ahk_path

        try:
            with open(ahk_path, "w", encoding="utf-8") as f:

                # HEADER
                f.write("; AutoHotKey Script Generated by PyWare Automate\n")
                f.write("F5:: ; Start macro\n")
                f.write("    SetBatchLines, -1\n")
                f.write("    SetKeyDelay, -1\n")
                f.write("    SetMouseDelay, -1\n")
                f.write("    SetTitleMatchMode, 2\n")
                f.write("    SendMode, Input\n")
                f.write("    ; ---- Start of Macro ----\n")

                # BODY: recorded actions
                for action in self.recorded_actions:
                    f.write(f"    {action}\n")

                # END BLOCK
                f.write("    ; ---- End of Macro ----\n")
                f.write("return\n\n")

                # EXIT HOTKEY
                f.write("F7::\n")
                f.write("    ExitApp\n")
                f.write("return\n")

                # PYWARE COMPATIBILITY LAYER
                f.write("; --- PyWare Compatibility Layer ---\n")
                f.write("StartCaptureThread() {\n")
                f.write("    return\n")
                f.write("}\n\n")

                f.write("StopCaptureThread() {\n")
                f.write("    return\n")
                f.write("}\n")
                f.write("; ---------------------------------\n\n")

            # print("Saved", len(self.recorded_actions), "actions to", ahk_path)

            # Refresh the editor so the recorded script is immediately visible
            def _update_editor():
                try:
                    with open(ahk_path, "r", encoding="utf-8") as fread:
                        content = fread.read()
                    if hasattr(self, "editor_textbox"):
                        self.editor_textbox.delete("1.0", "end")
                        self.editor_textbox.insert("1.0", content)
                except Exception as read_err:
                    print("Error refreshing editor after recording:", read_err)
            self.after(0, _update_editor)

        except Exception as e:
            print("Error saving AHK:", e)
    def start_playback(self):
        # print("Macro Status: Started Playback")
        self.macro_running = True
        # Load actions from file (handles both .ahk and .txt, skips headers/comments)
        if threading.current_thread() is threading.main_thread():
            self.load_recording_file()
        else:
            load_done = threading.Event()
            self.after(0, self._load_recording_file_and_signal, load_done)
            load_done.wait()

        # ---- READ SETTINGS ----
        loops_raw = self.vars["playback_loops"].get().strip()
        interval_raw = self.vars["playback_interval"].get().strip()

        # default values
        try:
            loops = int(float(loops_raw))
        except:
            loops = 1

        try:
            interval_minutes = float(interval_raw)
        except:
            interval_minutes = 0.0

        interval_seconds = interval_minutes * 60

        # Read playback speed multiplier (1.0 = normal, 2.0 = 2× faster)
        try:
            speed = float(self.vars["playback_speed"].get().strip())
            if speed <= 0:
                speed = 1.0
        except:
            speed = 1.0

        # If loops is 0 → infinite loop
        infinite_loop = (loops == 0)

        loop_count = 0
        self.is_playing_back = True  # suppress hotkey processing during playback
        playback_error_msg = None

        # ---- PLAYBACK LOOP ----
        try:
            while self.macro_running and (infinite_loop or loop_count < loops):

                loop_count += 1
                # print(f"Starting loop {loop_count}")

                # Play all actions
                self.execute_script(self.recorded_actions, speed)

                if not self.macro_running:
                    break

                # If there is an interval → wait before next loop
                if interval_seconds > 0 and (infinite_loop or loop_count < loops):
                    # print(f"Waiting {interval_seconds} seconds before next loop...")
                    time.sleep(interval_seconds)

        except PlaybackError as e:
            playback_error_msg = str(e)

        # finished looping
        self.is_playing_back = False
        self.macro_running = False
        self.release_all_keys()
        self.force_release_modifiers()
        if playback_error_msg:
            self.set_status("Macro Status: Stopped (Error)")
            self.after(0, self.deiconify)
            messagebox.showerror("Script Error", playback_error_msg)
        else:
            self.set_status("Macro Status: Stopped Playback (Done)")
            self.after(0, self.deiconify)
    def stop_playback(self):
        if not self.macro_running:
            return

        self.macro_running = False
        self.is_playing_back = False
        self.release_all_keys()   # Important: IMPORTANT
        self.after(0, self.deiconify)
        self.set_status("Macro Status: Stopped Playback")
if __name__ == "__main__":
    app = App()
    app.mainloop()
