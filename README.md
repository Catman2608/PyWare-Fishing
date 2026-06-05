# Project Environment Setup Guide

## 📋 Overview

This guide walks through setting up Python and all required modules for running the project. The application uses GUI automation, OCR, screen capture, and cross-platform OS features.

---

## 1️⃣ Prerequisites

- **OS**: Windows or macOS (project is not tested on Linux)
- **Administrator/Root access** may be needed for certain system-level operations
- **Internet connection** for downloading packages

---

## 2️⃣ Install Python

### Option A: Using the Official Installer (Recommended)
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download and run the installer
3. ✅ **Important**: Check *"Add Python to PATH"* during installation

### Option B: Using Homebrew (macOS only)
```bash
# Install via official website, or with homebrew if using a script:
python -m ensurepip --upgrade  # pip may not be installed by default on macOS
```

### Verify Installation
Open Terminal/Command Prompt and run:
```bash
python --version
# or
python3 --version
```
Expected output: `Python 3.8+`

---

## 3️⃣ Create Virtual Environment (Recommended)

Never install packages directly into the system Python!

```bash
# Navigate to your project folder
cd /path/to/your/project

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate

# macOS/Linux:
source .venv/bin/activate
```

Verify activation by checking that the prompt shows `(venv)` before your project folder name.

---

## 4️⃣ Install Required Modules

### Method A: Using requirements.txt (Best Practice)

If you have a `requirements.txt` file, simply run:
```bash
pip install -r requirements.txt
```

### Method B: Installing Individual Packages

If building from scratch, install the dependencies manually:

```bash
# Core packages
pip install webview numpy mss pytesseract pynput requests opencv-python

# macOS specific (for screen capture on Apple Silicon/M1):
pip install opencv-python-headless  # Better compatibility for macOS

# Alternative (if above fails with M1/Apple Silicon):
pip install opencv-contrib-python-headless
```

### Complete Package List Reference
| Module | Command | Purpose |
|--------|---------|---------|
| `webview` | `pip install webview` | GUI window creation |
| `numpy` | `pip install numpy` | Numerical operations, image arrays |
| `mss` | `pip install mss` | Screenshot capture (multi-screen support) |
| `pytesseract` | `pip install pytesseract` | OCR engine wrapper for Tesseract |
| `pynput` | `pip install pynput` | Keyboard/mouse automation & listening |
| `requests` | `pip install requests` | HTTP/HTTPS API calls |
| `opencv-python` or `opencv-python-headless` | `pip install opencv-python` | Image processing (cv2) |

---

## 5️⃣ Platform-Specific Setup

### 🍎 macOS — Tesseract OCR Installation

Tesseract is not included with Python. Install it first:

```bash
# Option 1: Using Homebrew (macOS only)
brew install tesseract

# Option 2: Using MacPorts
sudo port install tesseract

# Verify installation location
which tesseract
```

Then in your code, the path is already configured to:
```python
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
```

> **Note for Apple Silicon (M1/M2/M3)**: If you encounter issues with OpenCV on Mac, prefer `opencv-python-headless` or use Rosetta translation.

### 🪟 Windows — Additional Requirements
- Ensure Administrator privileges when running the script if it needs to capture system-level input/output
- The built-in Python libraries (`json`, `os`, `re`, `time`, `sys`) require no installation
- `threading` and `subprocess` are part of standard Python

---

## 6️⃣ Verify Installation

Create a test script `test_imports.py`:

```python
import webview, json, os, re, time, sys
from tkinter import messagebox
import pytesseract
print("Tesseract path:", pytesseract.pytesseract.tesseract_cmd)

from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController, Button

import cv2, numpy as np, mss
if sys.platform == "win32":
    import ctypes, wintypes
elif sys.platform == "darwin":
    from Quartz import NSScreen  # noqa: F401 (just verifying the import works)

import requests, io

print("✅ All modules imported successfully!")
```

Run it with `python test_imports.py` — no errors means your setup is complete.

---

## 7️⃣ Troubleshooting Quick Fixes

| Error | Solution |
|-------|----------|
| `_tkinter.TclError: No such file or directory` | Install tkinter: `pip install tkinter` (macOS) or reinstall Python with "Add to PATH" checked |
| `ModuleNotFoundError: No module named 'tesseract'` | Install Tesseract OS package first, then `pip install pytesseract` |
| `M1 Mac — OpenCV error about libGL` | Use `opencv-python-headless` instead of regular opencv |
| Permission denied on screenshot/capture | Run the script as Administrator (Windows) or with elevated privileges (macOS) |

---

## 📁 Project Structure Recommendation

```text
your-project/
├── .venv/                 # Virtual environment (hidden)
├── src/                   # Your source code
│   └── main.py            # Entry point
├── requirements.txt       # Lock your dependencies here!
├── test_imports.py        # Verification script above
└── README.md              # This file, updated with your details
```

---

## 💡 Final Tips

1. **Pin versions** in `requirements.txt` to avoid environment drift:
   ```text
   webview==4.x.x
   numpy==1.x.x
   opencv-python-headless==4.x.x
   ```

2. Keep the virtual environment activated while developing — it saves time and prevents conflicts with system Python.

3. If you share your project publicly, always provide a `requirements.txt` so others can reproduce your setup easily!