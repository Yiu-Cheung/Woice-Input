"""
Minimal Speech-to-Text Desktop Application
Google Speech Recognition with clean UI
"""

# Pre-load system DLLs for onnxruntime in frozen PyInstaller context.
# When sounddevice's PortAudio DLLs are bundled alongside onnxruntime,
# onnxruntime.dll fails to initialize unless its system DLL dependencies
# are pre-loaded from System32 first.
import sys
import os
if sys.platform == "win32" and getattr(sys, 'frozen', False):
    import ctypes
    _k32 = ctypes.windll.kernel32
    _k32.LoadLibraryExW.restype = ctypes.c_void_p
    _k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    _sys32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    _base = sys._MEIPASS
    # Pre-load system DLLs that onnxruntime needs
    for _dep in ['dxgi.dll', 'dbghelp.dll', 'SETUPAPI.dll', 'MSVCP140.dll', 'MSVCP140_1.dll']:
        _k32.LoadLibraryExW(os.path.join(_sys32, _dep), None, 0)
    # Add DLL search directories
    os.add_dll_directory(_base)
    _ort_capi = os.path.join(_base, "onnxruntime", "capi")
    if os.path.isdir(_ort_capi):
        os.add_dll_directory(_ort_capi)
    # Pre-load onnxruntime DLLs with LOAD_WITH_ALTERED_SEARCH_PATH
    for _dll in ['onnxruntime.dll', 'onnxruntime_providers_shared.dll']:
        for _d in [_ort_capi, _base]:
            _p = os.path.join(_d, _dll)
            if os.path.isfile(_p):
                _k32.LoadLibraryExW(_p, None, 0x00000008)
                break

try:
    from .transcription import transcribe_with_google
    from .audio_processor import process_audio
    from .overlay import FloatingOverlay
    from .config import (
        VAD_FRAME_SAMPLES, PRE_ROLL_MS, VAD_EXIT_MARGIN,
        SHORT_UTTERANCE_FLOOR, TARGET_SAMPLE_RATE,
    )
except ImportError:
    from src.transcription import transcribe_with_google
    from src.audio_processor import process_audio
    from src.overlay import FloatingOverlay
    from src.config import (
        VAD_FRAME_SAMPLES, PRE_ROLL_MS, VAD_EXIT_MARGIN,
        SHORT_UTTERANCE_FLOOR, TARGET_SAMPLE_RATE,
    )

try:
    try:
        from .vad import SileroVAD
    except ImportError:
        from src.vad import SileroVAD
    _vad_available = True
except (ImportError, FileNotFoundError) as e:
    _vad_available = False
    print(f"[WARNING] Silero VAD not available ({e}), using amplitude detection")

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import collections
import pyperclip
from pynput import keyboard
import numpy as np
import sounddevice as sd
import time
import json
import pystray
from PIL import Image, ImageDraw


def _app_dir():
    """Directory the app should anchor data files to, independent of cwd.

    Frozen exe -> the exe's folder; source -> the project root (parent of src/).
    Anchoring SETTINGS_FILE here keeps settings working no matter how the app is
    launched (e.g. auto-start at login, where cwd is not the project dir).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


SETTINGS_FILE = os.path.join(_app_dir(), "settings.json")

# --- Windows auto-start (per-user Run key; no admin required) ---
_AUTOSTART_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_VALUE_NAME = "SpeechToText"


def _autostart_command():
    """Command Windows runs at login to launch this app (cwd-independent)."""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    # Source mode: mirror run.bat (set project as working dir, run via pythonw
    # so there is no console window) so `-m src` and settings.json both resolve.
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, 'pythonw.exe')
    python_exe = pythonw if os.path.exists(pythonw) else sys.executable
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f'cmd /c start "" /D "{project_dir}" "{python_exe}" -m src'


def is_autostart_enabled():
    """True if the login Run-key entry exists (Windows only)."""
    if sys.platform != 'win32':
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_RUN_KEY) as key:
            winreg.QueryValueEx(key, _AUTOSTART_VALUE_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    """Add or remove the login Run-key entry. Returns True on success."""
    if sys.platform != 'win32':
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTOSTART_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _AUTOSTART_VALUE_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, _AUTOSTART_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        print(f"[DEBUG] set_autostart failed: {e}")
        return False


def _default_settings():
    """Return a fresh dict of default settings (single source of truth).

    Used both for first-run defaults and for the Settings "Reset to Defaults"
    button, so the two never drift apart.
    """
    return {
        'language': 'yue',
        'continuous': True,
        'pause_threshold': 1.5,  # Seconds of silence before processing
        'silence_threshold': 0.01,  # Audio amplitude threshold for silence detection
        'game_mode': False,  # Use PostMessage/WM_CHAR instead of SendInput (for games with anti-cheat)
        'game_mode_char_delay': 0.01,  # Delay between characters in game mode (seconds)
        'idle_timeout': 60,  # Auto-stop recording after N seconds of silence (0 = disabled)
        'vad_threshold': 0.4,  # Silero VAD speech probability threshold to ENTER speech (0.0-1.0)
        'vad_exit_threshold': 0.4 - VAD_EXIT_MARGIN,  # Hysteresis: stay capturing until prob drops below this (0.25)
        'short_utterance_floor': SHORT_UTTERANCE_FLOOR,  # Min voiced duration (s) to keep a segment
        'offline_fallback': False,  # Use local Whisper when online recognizer fails after retries
        'sound_cues': True,  # Play a short beep on start (high) / stop (low)
        'auto_start': True,  # Launch automatically on login (registry Run key / LaunchAgent)
        'overlay_enabled': False,
        'overlay_opacity': 0.90,
        'overlay_width': 400,
        'overlay_height': 150,
        'overlay_position': 'bottom-right',
        'overlay_max_lines': 10,
        'overlay_font_size': 11,
        'microphone': 'auto',
    }


class SettingsDialog:
    def __init__(self, parent, settings):
        self.settings = settings
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.grab_set()
        self.dialog.attributes('-topmost', True)

        # Window is auto-fit to its content at the end of __init__ so nothing is
        # cut off (no manual resize needed). Only the minimum width is fixed here.
        self._dialog_min_width = 470

        # Language
        lang_frame = tk.Frame(self.dialog)
        lang_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(lang_frame, text="Language:", font=("Arial", 10, "bold")).pack(anchor='w')
        self.language_var = tk.StringVar(value=settings['language'])
        lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.language_var,
            values=["auto", "yue", "en", "es", "fr", "de", "zh", "ja", "ko", "pt", "ru", "it"],
            state="readonly",
            width=20
        )
        lang_combo.pack(pady=5, fill=tk.X)

        # Microphone selection
        mic_frame = tk.Frame(self.dialog)
        mic_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(mic_frame, text="Microphone:", font=("Arial", 10, "bold")).pack(anchor='w')
        mic_devices = SimpleSTTApp._get_input_devices()
        mic_names = ["auto"] + [name for _, name in mic_devices]
        self.microphone_var = tk.StringVar(value=settings.get('microphone', 'auto'))
        mic_combo = ttk.Combobox(
            mic_frame,
            textvariable=self.microphone_var,
            values=mic_names,
            state="readonly",
            width=40
        )
        mic_combo.pack(pady=5, fill=tk.X)

        # Game Mode
        self.game_mode_var = tk.BooleanVar(value=settings.get('game_mode', False))
        game_mode_cb = tk.Checkbutton(
            self.dialog,
            text="Game Mode (anti-cheat compatible typing via PostMessage)",
            variable=self.game_mode_var,
            font=("Arial", 10)
        )
        game_mode_cb.pack(pady=5, padx=20)

        # Continuous mode
        self.continuous_var = tk.BooleanVar(value=settings['continuous'])
        continuous_cb = tk.Checkbutton(
            self.dialog,
            text="Continuous transcription mode",
            variable=self.continuous_var,
            font=("Arial", 10)
        )
        continuous_cb.pack(pady=5, padx=20)

        # Voice pause threshold
        pause_frame = tk.Frame(self.dialog)
        pause_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(pause_frame, text="Voice pause threshold (seconds):", font=("Arial", 10)).pack(anchor='w')
        self.pause_var = tk.StringVar(value=str(settings['pause_threshold']))
        pause_entry = tk.Entry(pause_frame, textvariable=self.pause_var, width=10)
        pause_entry.pack(pady=5, anchor='w')

        # Silence threshold
        silence_frame = tk.Frame(self.dialog)
        silence_frame.pack(pady=5, padx=20, fill=tk.X)

        tk.Label(silence_frame, text="Silence threshold (0.001-0.1):", font=("Arial", 10)).pack(anchor='w')
        self.silence_var = tk.StringVar(value=str(settings['silence_threshold']))
        silence_entry = tk.Entry(silence_frame, textvariable=self.silence_var, width=10)
        silence_entry.pack(pady=5, anchor='w')

        # Idle auto-stop timeout
        idle_frame = tk.Frame(self.dialog)
        idle_frame.pack(pady=5, padx=20, fill=tk.X)

        tk.Label(idle_frame, text="Idle auto-stop (seconds, 0=disabled):", font=("Arial", 10)).pack(anchor='w')
        self.idle_timeout_var = tk.StringVar(value=str(settings.get('idle_timeout', 10)))
        idle_entry = tk.Entry(idle_frame, textvariable=self.idle_timeout_var, width=10)
        idle_entry.pack(pady=5, anchor='w')

        # VAD threshold
        vad_frame = tk.Frame(self.dialog)
        vad_frame.pack(pady=5, padx=20, fill=tk.X)

        tk.Label(vad_frame, text="VAD threshold (0.0-1.0, speech detection sensitivity):", font=("Arial", 10)).pack(anchor='w')
        self.vad_threshold_var = tk.DoubleVar(value=settings.get('vad_threshold', 0.4))
        vad_slider = tk.Scale(
            vad_frame,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=self.vad_threshold_var,
            length=200
        )
        vad_slider.pack(pady=5, anchor='w')

        # VAD exit threshold (hysteresis floor)
        vad_exit_frame = tk.Frame(self.dialog)
        vad_exit_frame.pack(pady=5, padx=20, fill=tk.X)

        tk.Label(vad_exit_frame, text="VAD exit threshold (hysteresis, keeps capturing until below this):", font=("Arial", 10)).pack(anchor='w')
        self.vad_exit_threshold_var = tk.DoubleVar(value=settings.get('vad_exit_threshold', 0.25))
        vad_exit_slider = tk.Scale(
            vad_exit_frame,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=self.vad_exit_threshold_var,
            length=200
        )
        vad_exit_slider.pack(pady=5, anchor='w')

        # Short-utterance floor
        floor_frame = tk.Frame(self.dialog)
        floor_frame.pack(pady=5, padx=20, fill=tk.X)

        tk.Label(floor_frame, text="Short-utterance floor (seconds, min voiced to keep):", font=("Arial", 10)).pack(anchor='w')
        self.short_utterance_floor_var = tk.StringVar(value=str(settings.get('short_utterance_floor', 0.15)))
        floor_entry = tk.Entry(floor_frame, textvariable=self.short_utterance_floor_var, width=10)
        floor_entry.pack(pady=5, anchor='w')

        # Offline fallback (local Whisper)
        self.offline_fallback_var = tk.BooleanVar(value=settings.get('offline_fallback', False))
        offline_cb = tk.Checkbutton(
            self.dialog,
            text="Offline fallback (use local Whisper when online fails)",
            variable=self.offline_fallback_var,
            font=("Arial", 10)
        )
        offline_cb.pack(pady=5, padx=20, anchor='w')

        # Sound cues (start/stop beep)
        self.sound_cues_var = tk.BooleanVar(value=settings.get('sound_cues', True))
        sound_cb = tk.Checkbutton(
            self.dialog,
            text="Sound cues (beep on start / stop)",
            variable=self.sound_cues_var,
            font=("Arial", 10)
        )
        sound_cb.pack(pady=5, padx=20, anchor='w')

        # Auto-start on Windows login (reflects the actual registry state)
        self.auto_start_var = tk.BooleanVar(value=is_autostart_enabled())
        autostart_cb = tk.Checkbutton(
            self.dialog,
            text="Start automatically on Windows login",
            variable=self.auto_start_var,
            font=("Arial", 10)
        )
        autostart_cb.pack(pady=5, padx=20, anchor='w')

        # Overlay settings
        overlay_frame = tk.LabelFrame(self.dialog, text="Floating Overlay", font=("Arial", 10, "bold"), padx=10, pady=10)
        overlay_frame.pack(pady=10, padx=20, fill=tk.X)

        self.overlay_enabled_var = tk.BooleanVar(value=settings.get('overlay_enabled', False))
        overlay_cb = tk.Checkbutton(
            overlay_frame,
            text="Enable floating overlay",
            variable=self.overlay_enabled_var,
            font=("Arial", 10)
        )
        overlay_cb.pack(anchor='w')

        # Opacity slider
        opacity_subframe = tk.Frame(overlay_frame)
        opacity_subframe.pack(fill=tk.X, pady=5)
        tk.Label(opacity_subframe, text="Opacity:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.overlay_opacity_var = tk.DoubleVar(value=settings.get('overlay_opacity', 0.90))
        opacity_slider = tk.Scale(
            opacity_subframe,
            from_=0.3,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=self.overlay_opacity_var,
            length=200
        )
        opacity_slider.pack(side=tk.LEFT, padx=5)

        # Position dropdown
        position_subframe = tk.Frame(overlay_frame)
        position_subframe.pack(fill=tk.X, pady=5)
        tk.Label(position_subframe, text="Position:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.overlay_position_var = tk.StringVar(value=settings.get('overlay_position', 'bottom-right'))
        position_combo = ttk.Combobox(
            position_subframe,
            textvariable=self.overlay_position_var,
            values=["top-left", "top-right", "bottom-left", "bottom-right", "center"],
            state="readonly",
            width=15
        )
        position_combo.pack(side=tk.LEFT, padx=5)

        # Max lines
        lines_subframe = tk.Frame(overlay_frame)
        lines_subframe.pack(fill=tk.X, pady=5)
        tk.Label(lines_subframe, text="Max lines:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.overlay_max_lines_var = tk.StringVar(value=str(settings.get('overlay_max_lines', 10)))
        lines_entry = tk.Entry(lines_subframe, textvariable=self.overlay_max_lines_var, width=10)
        lines_entry.pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(pady=20)

        save_btn = tk.Button(
            btn_frame,
            text="💾 Save Settings",
            command=self.save,
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            width=18,
            height=2
        )
        save_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = tk.Button(
            btn_frame,
            text="✖ Cancel",
            command=self.dialog.destroy,
            font=("Arial", 11),
            width=12,
            height=2
        )
        cancel_btn.pack(side=tk.LEFT, padx=10)

        reset_btn = tk.Button(
            btn_frame,
            text="↺ Reset to Defaults",
            command=self.reset_defaults,
            font=("Arial", 10),
            width=16,
            height=2
        )
        reset_btn.pack(side=tk.LEFT, padx=10)

        # Auto-fit the window to its content so every control (incl. Save/Cancel)
        # is visible without manual resizing.
        self.dialog.update_idletasks()
        width = max(self._dialog_min_width, self.dialog.winfo_reqwidth())
        height = self.dialog.winfo_reqheight()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        # Keep within the screen; allow resize as a fallback on very small screens
        height = min(height, screen_height - 60)
        x = (screen_width - width) // 2
        y = max(0, (screen_height - height) // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        self.dialog.minsize(width, min(height, 500))

    def reset_defaults(self):
        """Restore all form controls to default values (review, then Save to apply)."""
        if not messagebox.askyesno(
            "Reset Settings",
            "Restore all settings to their default values?\n"
            "Click Save Settings afterwards to apply."
        ):
            return
        d = _default_settings()
        self.language_var.set(d['language'])
        self.microphone_var.set(d['microphone'])
        self.game_mode_var.set(d['game_mode'])
        self.continuous_var.set(d['continuous'])
        self.pause_var.set(str(d['pause_threshold']))
        self.silence_var.set(str(d['silence_threshold']))
        self.idle_timeout_var.set(str(d['idle_timeout']))
        self.vad_threshold_var.set(d['vad_threshold'])
        self.vad_exit_threshold_var.set(d['vad_exit_threshold'])
        self.short_utterance_floor_var.set(str(d['short_utterance_floor']))
        self.offline_fallback_var.set(d['offline_fallback'])
        self.sound_cues_var.set(d['sound_cues'])
        self.auto_start_var.set(d['auto_start'])
        self.overlay_enabled_var.set(d['overlay_enabled'])
        self.overlay_opacity_var.set(d['overlay_opacity'])
        self.overlay_position_var.set(d['overlay_position'])
        self.overlay_max_lines_var.set(str(d['overlay_max_lines']))

    def save(self):
        try:
            pause_threshold = float(self.pause_var.get())
            if pause_threshold < 0.5 or pause_threshold > 5.0:
                messagebox.showerror("Error", "Pause threshold must be between 0.5 and 5.0 seconds")
                return

            silence_threshold = float(self.silence_var.get())
            if silence_threshold < 0.001 or silence_threshold > 0.1:
                messagebox.showerror("Error", "Silence threshold must be between 0.001 and 0.1")
                return

            idle_timeout = int(self.idle_timeout_var.get())
            if idle_timeout < 0:
                messagebox.showerror("Error", "Idle timeout must be 0 or positive")
                return

            short_utterance_floor = float(self.short_utterance_floor_var.get())
            if short_utterance_floor < 0.0 or short_utterance_floor > 5.0:
                messagebox.showerror("Error", "Short-utterance floor must be between 0.0 and 5.0 seconds")
                return

            vad_threshold = self.vad_threshold_var.get()
            vad_exit_threshold = self.vad_exit_threshold_var.get()
            # Hysteresis invariant: exit must not exceed enter
            if vad_exit_threshold > vad_threshold:
                vad_exit_threshold = vad_threshold

            self.settings['language'] = self.language_var.get()
            self.settings['microphone'] = self.microphone_var.get()
            self.settings['game_mode'] = self.game_mode_var.get()
            self.settings['continuous'] = self.continuous_var.get()
            self.settings['pause_threshold'] = pause_threshold
            self.settings['silence_threshold'] = silence_threshold
            self.settings['idle_timeout'] = idle_timeout
            self.settings['vad_threshold'] = vad_threshold
            self.settings['vad_exit_threshold'] = vad_exit_threshold
            self.settings['short_utterance_floor'] = short_utterance_floor
            self.settings['offline_fallback'] = self.offline_fallback_var.get()
            self.settings['sound_cues'] = self.sound_cues_var.get()
            self.settings['auto_start'] = self.auto_start_var.get()
            # Apply auto-start to the Windows registry
            set_autostart(self.auto_start_var.get())

            # Save overlay settings
            self.settings['overlay_enabled'] = self.overlay_enabled_var.get()
            self.settings['overlay_opacity'] = self.overlay_opacity_var.get()
            self.settings['overlay_position'] = self.overlay_position_var.get()
            self.settings['overlay_max_lines'] = int(self.overlay_max_lines_var.get())

            # Save to file
            try:
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(self.settings, f, indent=2)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
                return

            self.dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid threshold values")


class SimpleSTTApp:
    def __init__(self):
        print("[DEBUG] Initializing SimpleSTTApp...")
        self.root = tk.Tk()
        self.root.title("Speech-to-Text")
        print("[DEBUG] Tkinter root created")

        # Set fixed window size
        window_width = 300
        window_height = 250

        # Center the window
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Load settings from file or use defaults
        self.settings = self._load_settings()

        # State
        self.is_recording = False
        self.audio_data = []
        self.sample_rate = 16000
        self.continuous_mode = False
        self.continuous_thread = None
        # Voice Activity Detection (Silero VAD)
        self.vad = None
        self.vad_available = _vad_available
        if self.vad_available:
            try:
                self.vad = SileroVAD()
                print("[DEBUG] Silero VAD initialized")
            except Exception as e:
                self.vad_available = False
                print(f"[WARNING] Silero VAD init failed: {e}, using amplitude detection")

        # Persistent microphone stream + rolling pre-roll buffer.
        # The stream stays open while the app runs; the callback always fills the
        # pre-roll (recent audio) and, while a session is active, the session blocks.
        self._mic_stream = None
        self._mic_blocksize = VAD_FRAME_SAMPLES
        self._mic_lock = threading.Lock()
        self._preroll = collections.deque()          # recent 1D float32 blocks
        self._preroll_samples = 0
        self._preroll_target = int(PRE_ROLL_MS / 1000.0 * self.sample_rate)
        self._session_active = False
        self._session_blocks = []                    # blocks captured during a session

        # Overlay window (created lazily on first toggle)
        self.overlay_window = None

        # System tray
        self.tray_icon = None
        self.tray_running = False
        print("[DEBUG] Creating tray icon...")
        self._create_tray_icon()
        print("[DEBUG] Tray icon created")

        print("[DEBUG] Creating UI...")
        self._create_ui()
        print("[DEBUG] UI created")

        print("[DEBUG] Setting up hotkeys...")
        self._setup_hotkeys()
        print("[DEBUG] Hotkeys set up")

        # Handle minimize to tray
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Unmap>", self.on_minimize)

        # Start minimized to tray by default
        print("[DEBUG] Hiding window and starting tray icon...")
        self.root.withdraw()
        self.tray_running = True
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        print("[DEBUG] Tray icon thread started")

        # Create overlay (starts hidden, auto-shows when text arrives)
        self.root.after(500, self._init_overlay)

        # Open the persistent mic stream shortly after startup (off the UI thread)
        # so the pre-roll is already filling before the first hotkey press.
        self.root.after(800, lambda: threading.Thread(target=self._ensure_mic_stream, daemon=True).start())

    def _load_settings(self):
        """Load settings from file or return defaults"""
        default_settings = _default_settings()

        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    saved_settings = json.load(f)
                    # Merge with defaults to handle new settings
                    default_settings.update(saved_settings)
        except Exception:
            pass  # Use defaults if loading fails

        # Remove deprecated settings
        default_settings.pop('buffer_size', None)
        default_settings.pop('auto_paste', None)

        # Ensure hysteresis is consistent (exit must not exceed enter)
        if default_settings.get('vad_exit_threshold', 0.0) > default_settings.get('vad_threshold', 0.5):
            default_settings['vad_exit_threshold'] = max(
                0.0, default_settings['vad_threshold'] - VAD_EXIT_MARGIN
            )

        return default_settings

    def _ui_update(self, callback, *args):
        """Schedule a UI update to run on the main thread."""
        self.root.after(0, callback, *args)

    @staticmethod
    def _get_input_devices():
        """Get list of physical microphone input devices, filtering out loopback/virtual devices."""
        excluded = ['stereo mix', 'loopback', 'what u hear', 'cable output', 'virtual']
        devices = sd.query_devices()
        mic_devices = []
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = dev['name']
                if not any(ex in name.lower() for ex in excluded):
                    mic_devices.append((i, name))
        return mic_devices

    def _get_microphone_device(self):
        """Get the sounddevice device index for the configured microphone."""
        mic_setting = self.settings.get('microphone', 'auto')

        if mic_setting != 'auto':
            # User selected a specific device - find it by name
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0 and dev['name'] == mic_setting:
                    return i

        # Auto mode: pick first physical microphone
        mic_devices = self._get_input_devices()
        if mic_devices:
            return mic_devices[0][0]

        # Fallback to system default
        return None

    def _init_overlay(self):
        """Create overlay window (starts hidden, auto-shows when text arrives)."""
        if self.overlay_window is None:
            self.overlay_window = FloatingOverlay(self)
            self.overlay_window.create_overlay(self.settings)

    def _create_tray_icon(self):
        """Create system tray icon"""
        # Create idle icon (grey) and recording icon (red)
        self._icon_idle = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(self._icon_idle)
        draw.ellipse([16, 16, 48, 48], fill='#9E9E9E')

        self._icon_recording = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(self._icon_recording)
        draw.ellipse([16, 16, 48, 48], fill='#F44336')

        icon_image = self._icon_idle

        # Create tray menu
        menu = pystray.Menu(
            pystray.MenuItem(
                "Start/Stop",
                self.toggle_transcription,
                default=True,
                checked=lambda item: self.continuous_mode or self.is_recording
            ),
            pystray.MenuItem(
                "Game Mode",
                self.toggle_game_mode,
                checked=lambda item: self.settings.get('game_mode', False)
            ),
            pystray.MenuItem(
                "Start on login",
                self.toggle_autostart,
                checked=lambda item: is_autostart_enabled()
            ),
            pystray.MenuItem("Settings", self.open_settings_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_app)
        )

        self.tray_icon = pystray.Icon("STT", icon_image, "Speech-to-Text", menu)

    def on_minimize(self, event):
        """Handle window minimize event"""
        if event.widget == self.root:
            if self.root.state() == 'iconic':  # Window is minimized
                self.hide_window()

    def hide_window(self):
        """Hide window and show in tray"""
        self.root.withdraw()
        if self.tray_icon and not self.tray_running:
            self.tray_running = True
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        """Show window from tray"""
        self.root.after(0, self._show_window_impl)

    def _show_window_impl(self):
        """Implementation of show window (runs in main thread)"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def tray_start(self, icon=None, item=None):
        """Start transcription from tray"""
        self.root.after(0, self.start)

    def tray_stop(self, icon=None, item=None):
        """Stop transcription from tray"""
        self.root.after(0, self.stop)

    def toggle_transcription(self, icon=None, item=None):
        """Toggle transcription start/stop from tray"""
        if self.continuous_mode or self.is_recording:
            self.root.after(0, self.stop)
        else:
            self.root.after(0, self.start)

    def toggle_game_mode(self, icon=None, item=None):
        """Toggle game mode from tray"""
        self.root.after(0, self._toggle_game_mode_impl)

    def _toggle_game_mode_impl(self):
        """Implementation of toggle game mode (runs in main thread)"""
        current = self.settings.get('game_mode', False)
        self.settings['game_mode'] = not current

        # Save settings
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass  # Ignore save errors

    def toggle_autostart(self, icon=None, item=None):
        """Toggle auto-start on login from tray"""
        self.root.after(0, self._toggle_autostart_impl)

    def _toggle_autostart_impl(self):
        """Implementation of toggle auto-start (runs in main thread)"""
        new_state = not is_autostart_enabled()
        if set_autostart(new_state):
            self.settings['auto_start'] = new_state
            try:
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(self.settings, f, indent=2)
            except Exception:
                pass  # Ignore save errors
        self._update_tray()

    def open_settings_from_tray(self, icon=None, item=None):
        """Open settings dialog from tray"""
        self.root.after(0, self._open_settings_from_tray_impl)

    def _open_settings_from_tray_impl(self):
        """Implementation of open settings from tray (runs in main thread)"""
        self.open_settings()

    def toggle_overlay(self, icon=None, item=None):
        """Toggle overlay from tray"""
        self.root.after(0, self._toggle_overlay_impl)

    def _toggle_overlay_impl(self):
        """Implementation of toggle overlay (runs in main thread)"""
        # Create overlay if it doesn't exist
        if self.overlay_window is None:
            self.overlay_window = FloatingOverlay(self)
            self.overlay_window.create_overlay(self.settings)

        # Toggle visibility
        self.overlay_window.toggle_visibility()
        self.settings['overlay_enabled'] = self.overlay_window.is_visible

        # Save settings
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass  # Ignore save errors

    def quit_app(self, icon=None, item=None):
        """Quit application"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.on_closing)

    def _create_ui(self):
        """Create minimal UI"""
        # Top bar
        top_frame = tk.Frame(self.root, bg="#f0f0f0")
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        # Settings button
        settings_btn = tk.Button(
            top_frame,
            text="⚙️ Settings",
            command=self.open_settings,
            font=("Arial", 10),
            width=12
        )
        settings_btn.pack(side=tk.LEFT)

        # Start/Stop buttons
        button_frame = tk.Frame(top_frame)
        button_frame.pack(side=tk.RIGHT)

        self.start_btn = tk.Button(
            button_frame,
            text="▶ Start",
            command=self.start,
            font=("Arial", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            width=10
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            button_frame,
            text="⏹ Stop",
            command=self.stop,
            font=("Arial", 11, "bold"),
            bg="#f44336",
            fg="white",
            width=10,
            state='disabled'
        )
        self.stop_btn.pack(side=tk.LEFT)

        # Status bar
        self.status_var = tk.StringVar(value="Ready (Press Ctrl+Shift+Space to record)")
        status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Arial", 9),
            fg="#666",
            anchor='w'
        )
        status_label.pack(fill=tk.X, padx=10, pady=5)

        # Large text area
        text_frame = tk.Frame(self.root)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.output_text = scrolledtext.ScrolledText(
            text_frame,
            font=("Arial", 12),
            wrap=tk.WORD,
            bg="#ffffff"
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # Bottom bar
        bottom_frame = tk.Frame(self.root, bg="#f0f0f0")
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)

        copy_btn = tk.Button(
            bottom_frame,
            text="📋 Copy",
            command=self.copy_to_clipboard,
            font=("Arial", 10),
            width=10
        )
        copy_btn.pack(side=tk.LEFT)

        clear_btn = tk.Button(
            bottom_frame,
            text="🗑 Clear",
            command=self.clear_text,
            font=("Arial", 10),
            width=10
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

    def _setup_hotkeys(self):
        """Setup global hotkeys"""
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+<space>': self.toggle_recording
        })
        self.hotkey_listener.start()

    def open_settings(self):
        """Open settings dialog"""
        SettingsDialog(self.root, self.settings)

    def _speech_probability(self, audio_chunk):
        """Return the chunk's speech score in [0.0, 1.0].

        Silero VAD: max speech probability across the 512-sample frames in the
        chunk. Amplitude fallback: 1.0 if the chunk exceeds `silence_threshold`,
        else 0.0 — so the same hysteresis state machine works for both paths.

        Args:
            audio_chunk: 1D numpy float32 array of audio samples

        Returns:
            float: speech score between 0.0 and 1.0
        """
        if self.vad_available:
            max_prob = 0.0
            # Process in 512-sample frames (required by Silero VAD)
            for i in range(0, len(audio_chunk) - (VAD_FRAME_SAMPLES - 1), VAD_FRAME_SAMPLES):
                frame = audio_chunk[i:i + VAD_FRAME_SAMPLES]
                prob = self.vad.process(frame)
                max_prob = max(max_prob, prob)
            return max_prob
        else:
            return 1.0 if np.max(np.abs(audio_chunk)) >= self.settings['silence_threshold'] else 0.0

    def _check_voice_activity(self, audio_chunk):
        """Boolean voice check against the enter threshold (no hysteresis).

        Used by manual-mode idle detection where a simple present/absent
        decision is sufficient.

        Args:
            audio_chunk: 1D numpy float32 array of audio samples

        Returns:
            bool: True if speech detected
        """
        return self._speech_probability(audio_chunk) >= self.settings.get('vad_threshold', 0.5)

    # ---- Persistent microphone stream + pre-roll ring buffer ----

    def _mic_callback(self, indata, frames, time_info, status):
        """PortAudio callback: always fill the pre-roll; feed the session if active."""
        if status:
            print(f"[DEBUG] Mic callback status: {status}")
        block = indata.reshape(-1).copy()  # 1D float32
        with self._mic_lock:
            self._preroll.append(block)
            self._preroll_samples += len(block)
            # Trim pre-roll to ~target samples (robust to variable block sizes)
            while self._preroll_samples > self._preroll_target and len(self._preroll) > 1:
                removed = self._preroll.popleft()
                self._preroll_samples -= len(removed)
            if self._session_active:
                self._session_blocks.append(block)

    def _ensure_mic_stream(self):
        """Open the persistent input stream if not already open. Idempotent.

        Prefers an explicit 512-sample blocksize (VAD frame aligned); on failure
        falls back to a host-chosen block size. The carry-over framing in
        `_vad_max_prob` keeps VAD correct regardless of the actual block size.
        """
        if self._mic_stream is not None:
            return True
        mic_device = self._get_microphone_device()
        last_err = None
        for blocksize in (VAD_FRAME_SAMPLES, 0):  # 512, then host default
            try:
                stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype=np.float32,
                    device=mic_device,
                    blocksize=blocksize,
                    callback=self._mic_callback,
                )
                stream.start()
                self._mic_stream = stream
                self._mic_blocksize = blocksize or stream.blocksize
                print(f"[DEBUG] Persistent mic stream opened (device={mic_device}, blocksize={blocksize})")
                self._update_tray()
                return True
            except Exception as e:
                last_err = e
                print(f"[DEBUG] Mic stream open failed (blocksize={blocksize}): {e}")
        self._ui_update(self.status_var.set, f"⚠ Microphone unavailable: {last_err}")
        return False

    def _close_mic_stream(self):
        """Stop and close the persistent input stream."""
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception as e:
                print(f"[DEBUG] Error closing mic stream: {e}")
            self._mic_stream = None

    def _begin_session(self, seed_preroll):
        """Start consuming captured blocks. Optionally seed with the pre-roll
        snapshot (used by manual mode so audio around the hotkey press is kept).
        Snapshot + activation happen under one lock to avoid dropping a block."""
        with self._mic_lock:
            self._session_blocks = list(self._preroll) if seed_preroll else []
            self._session_active = True

    def _end_session(self):
        """Stop consuming captured blocks (pre-roll keeps filling)."""
        with self._mic_lock:
            self._session_active = False
            self._session_blocks = []

    def _drain_session_blocks(self):
        """Return and clear the blocks captured since the last drain."""
        with self._mic_lock:
            blocks = self._session_blocks
            self._session_blocks = []
        return blocks

    def _snapshot_preroll(self):
        """Return a copy of the current pre-roll blocks (recent audio incl. now)."""
        with self._mic_lock:
            return list(self._preroll)

    def _vad_max_prob(self, samples, carry):
        """Feed contiguous 512-sample frames to the VAD, carrying leftover samples.

        Ensures no audio is dropped between calls and the streaming VAD state
        stays coherent. Returns (max_probability, leftover_carry).

        Args:
            samples: 1D float32 array of newly captured audio
            carry: 1D float32 leftover from the previous call

        Returns:
            tuple(float, np.ndarray): max speech score and the new leftover
        """
        buf = np.concatenate([carry, samples]) if carry.size else samples
        if not self.vad_available:
            score = 1.0 if (buf.size and np.max(np.abs(buf)) >= self.settings['silence_threshold']) else 0.0
            return score, np.empty(0, dtype=np.float32)

        max_prob = 0.0
        i = 0
        n = len(buf)
        while i + VAD_FRAME_SAMPLES <= n:
            frame = buf[i:i + VAD_FRAME_SAMPLES]
            max_prob = max(max_prob, self.vad.process(frame))
            i += VAD_FRAME_SAMPLES
        return max_prob, buf[i:]

    def _play_cue(self, kind):
        """Play a short start/stop beep (Windows only), if enabled in settings.

        start -> higher pitch, stop -> lower pitch. Runs off the caller thread
        since winsound.Beep is blocking.
        """
        if not self.settings.get('sound_cues', True) or sys.platform != 'win32':
            return
        freq = 880 if kind == 'start' else 440

        def _beep():
            try:
                import winsound
                winsound.Beep(freq, 120)
            except Exception as e:
                print(f"[DEBUG] sound cue failed: {e}")

        threading.Thread(target=_beep, daemon=True).start()

    def _update_tray(self):
        """Refresh tray icon, tooltip, and menu state."""
        if self.tray_icon:
            is_active = self.continuous_mode or self.is_recording
            self.tray_icon.icon = self._icon_recording if is_active else self._icon_idle
            if is_active:
                self.tray_icon.title = "Speech-to-Text (recording)"
            elif self._mic_stream is not None:
                self.tray_icon.title = "Speech-to-Text (mic live)"
            else:
                self.tray_icon.title = "Speech-to-Text"
            self.tray_icon.update_menu()

    def start(self):
        """Start continuous mode or recording"""
        print(f"[DEBUG] start() called, continuous={self.settings['continuous']}")
        if self.settings['continuous']:
            self.start_continuous_mode()
        else:
            self.start_recording()
        self._play_cue('start')
        self._update_tray()

    def stop(self):
        """Stop continuous mode or recording"""
        if self.settings['continuous']:
            self.stop_continuous_mode()
        else:
            self.stop_recording()
        self._play_cue('stop')
        self._update_tray()

    def toggle_recording(self):
        """Hotkey toggle - works for both manual and continuous modes"""
        if self.continuous_mode or self.is_recording:
            self.root.after(0, self.stop)
        else:
            self.root.after(0, self.start)

    def start_recording(self):
        """Start manual recording"""
        print("[DEBUG] start_recording() called")
        if self.continuous_mode:
            print("[DEBUG] Already in continuous mode, skipping")
            return

        self.is_recording = True
        self.audio_data = []
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_var.set("🎤 Recording... Speak now!")
        print("[DEBUG] Recording started, is_recording=True")

        threading.Thread(target=self._record_audio, daemon=True).start()

    def _record_audio(self):
        """Record audio from the persistent mic stream (with pre-roll onset)."""
        print("[DEBUG] _record_audio() thread started")
        idle_timeout = self.settings.get('idle_timeout', 10)
        vad_threshold = self.settings.get('vad_threshold', 0.5)
        idle_duration = 0.0
        check_interval = 0.1  # 100ms
        carry = np.empty(0, dtype=np.float32)

        # Fresh VAD state for idle detection on this session
        if self.vad_available:
            self.vad.reset_states()

        if not self._ensure_mic_stream():
            print("[DEBUG] No mic stream available, aborting recording")
            self._ui_update(self.stop_recording)
            return

        # Seed the session with the pre-roll so audio around the hotkey press is
        # retained (first drain returns the pre-roll blocks).
        self._begin_session(seed_preroll=True)
        try:
            print("[DEBUG] Recording from persistent stream...")
            while self.is_recording:
                time.sleep(check_interval)
                blocks = self._drain_session_blocks()
                if not blocks:
                    continue
                self.audio_data.extend(blocks)

                # Idle auto-stop using contiguous VAD frames over the new audio
                if idle_timeout > 0:
                    samples = np.concatenate(blocks)
                    prob, carry = self._vad_max_prob(samples, carry)
                    if prob >= vad_threshold:
                        idle_duration = 0.0
                    else:
                        idle_duration += check_interval
                        if idle_duration >= idle_timeout:
                            print(f"[DEBUG] Manual recording idle timeout ({idle_duration:.1f}s), auto-stopping...")
                            self._ui_update(self.stop_recording)
                            break
        except Exception as e:
            print(f"[DEBUG] ERROR in _record_audio: {e}")
        finally:
            self._end_session()
            print("[DEBUG] Recording session ended")

    def stop_recording(self):
        """Stop recording and transcribe"""
        if not self.is_recording:
            return

        self.is_recording = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_var.set("Processing...")

        threading.Thread(target=self._process_audio, daemon=True).start()

    def _transcribe(self, temp_path, language):
        """Transcribe a temp WAV via Google SR, with optional offline fallback.

        On a transient online failure, falls back to local Whisper only when the
        `offline_fallback` setting is enabled; otherwise reports the failure.

        Returns:
            dict: {"text": str, "status": "ok"|"no_speech"|"failed", ...}
        """
        result = transcribe_with_google(temp_path, language)
        if result.get("status") == "failed" and self.settings.get('offline_fallback', False):
            print(f"[DEBUG] Online SR failed ({result.get('error')}), trying offline Whisper fallback...")
            try:
                try:
                    from .transcription import transcribe_with_whisper
                except ImportError:
                    from src.transcription import transcribe_with_whisper
                whisper_result = transcribe_with_whisper(temp_path, language)
                text = whisper_result.get("text", "").strip()
                return {"text": text, "status": "ok" if text else "no_speech"}
            except Exception as e:
                print(f"[DEBUG] Offline Whisper fallback failed: {e}")
                return {"text": "", "status": "failed", "error": str(e)}
        return result

    def _process_audio(self):
        """Process and transcribe recorded audio"""
        print("[DEBUG] _process_audio() called")
        try:
            if not self.audio_data:
                print("[DEBUG] No audio data to process")
                self._ui_update(self.status_var.set, "No audio recorded")
                return

            print(f"[DEBUG] Audio chunks captured: {len(self.audio_data)}")

            # Combine audio chunks
            audio_array = np.concatenate(self.audio_data, axis=0).flatten()
            print(f"[DEBUG] Combined audio size: {len(audio_array)} samples")

            # Process audio
            print("[DEBUG] Processing audio...")
            temp_path, duration, _ = process_audio(audio_array, self.sample_rate)
            print(f"[DEBUG] Audio processed, duration={duration:.2f}s, temp_path={temp_path}")

            # Transcribe
            self._ui_update(self.status_var.set, "Transcribing...")
            language = self.settings['language'] if self.settings['language'] != "auto" else None
            print(f"[DEBUG] Transcribing with language={language}...")
            result = self._transcribe(temp_path, language)
            transcription = result.get("text", "")
            status = result.get("status", "ok")
            print(f"[DEBUG] Transcription result: status={status}, text='{transcription}'")

            # Clean up
            try:
                os.unlink(temp_path)
            except Exception:
                pass

            # Surface failures instead of silently dropping the recording
            if status == "failed":
                msg = f"⚠ Transcription failed: {result.get('error', 'service error')}"
                print(f"[DEBUG] {msg}")
                self._ui_update(self.status_var.set, msg)
                if self.overlay_window:
                    self._ui_update(self.overlay_window.update_text, "[transcription failed]\n")
                return
            if status == "no_speech" or not transcription.strip():
                self._ui_update(self.status_var.set, "No speech recognized")
                return

            # Update UI on main thread
            def update_ui():
                print("[DEBUG] Updating UI with transcription...")
                self.output_text.insert(tk.END, transcription + "\n")
                self.output_text.see(tk.END)

                # Paste BEFORE overlay update (overlay show can affect focus)
                print("[DEBUG] Auto-pasting...")
                self.paste_to_active_window(transcription)
                self.status_var.set(f"Transcribed and pasted! ({duration:.1f}s)")

                # Update overlay after paste
                if self.overlay_window:
                    self.overlay_window.update_text(transcription + "\n")

            self._ui_update(update_ui)
            print("[DEBUG] _process_audio() completed successfully")

        except Exception as e:
            print(f"[DEBUG] ERROR in _process_audio: {e}")
            import traceback
            traceback.print_exc()
            self._ui_update(self.status_var.set, f"Error: {str(e)}")

    def start_continuous_mode(self):
        """Start continuous transcription"""
        print("[DEBUG] start_continuous_mode() called")
        if self.continuous_mode:
            print("[DEBUG] Already in continuous mode")
            return

        self.continuous_mode = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_var.set("🔴 LIVE - Continuous transcription active...")
        print("[DEBUG] Continuous mode enabled, starting thread...")

        self.continuous_thread = threading.Thread(
            target=self._continuous_loop,
            daemon=True
        )
        self.continuous_thread.start()
        print("[DEBUG] Continuous thread started")

    def stop_continuous_mode(self):
        """Stop continuous transcription"""
        self.continuous_mode = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_var.set("Continuous mode stopped")

    def _continuous_loop(self):
        """Continuous transcription loop consuming the persistent mic stream."""
        print("[DEBUG] _continuous_loop() started")
        # Reset VAD hidden state for a fresh stream
        if self.vad_available:
            self.vad.reset_states()
        pause_threshold = self.settings['pause_threshold']
        idle_timeout = self.settings.get('idle_timeout', 10)
        vad_threshold = self.settings.get('vad_threshold', 0.5)
        vad_exit_threshold = self.settings.get('vad_exit_threshold', max(0.0, vad_threshold - VAD_EXIT_MARGIN))
        if vad_exit_threshold > vad_threshold:
            vad_exit_threshold = vad_threshold  # enforce hysteresis invariant
        short_utterance_floor = self.settings.get('short_utterance_floor', SHORT_UTTERANCE_FLOOR)
        vad_mode = "Silero VAD" if self.vad_available else "amplitude"
        print(f"[DEBUG] Continuous settings: pause={pause_threshold}s, vad_enter={vad_threshold}, vad_exit={vad_exit_threshold}, floor={short_utterance_floor}s, idle_timeout={idle_timeout}s, detection={vad_mode}")

        silence_buffer = []  # Accumulates audio for the current speech segment
        silence_duration = 0.0
        voiced_duration = 0.0  # Time (s) of strong voice (prob >= enter) in current segment
        is_speaking = False
        chunk_duration = 0.1  # Process in 100ms chunks
        loop_count = 0
        idle_duration = 0.0  # Time since last voice activity
        carry = np.empty(0, dtype=np.float32)  # leftover for contiguous VAD framing

        if not self._ensure_mic_stream():
            print("[DEBUG] No mic stream available, aborting continuous mode")
            self._ui_update(self.stop)
            return

        self._begin_session(seed_preroll=False)
        try:
            print("[DEBUG] Continuous mode consuming persistent stream...")
            while self.continuous_mode:
                loop_count += 1
                if loop_count % 50 == 0:  # Print every 5 seconds
                    print(f"[DEBUG] Continuous loop running... (iteration {loop_count})")
                time.sleep(chunk_duration)

                blocks = self._drain_session_blocks()
                if not blocks:
                    continue

                # Contiguous audio chunk (blocks are 512-aligned)
                chunk = np.concatenate(blocks)

                # Speech score over contiguous VAD frames (carry-over, no dropped tail)
                prob, carry = self._vad_max_prob(chunk, carry)
                # Hysteresis: once capturing, hold until prob drops below exit;
                # otherwise require prob to reach the (higher) enter threshold.
                if is_speaking:
                    is_voice = prob >= vad_exit_threshold
                else:
                    is_voice = prob >= vad_threshold
                # Strong voice = above enter threshold; used for short-utterance gating
                is_strong_voice = prob >= vad_threshold

                if is_voice:
                    # Voice detected — reset idle timer
                    idle_duration = 0.0
                    if not is_speaking:
                        # Onset: seed with the pre-roll (recent audio incl. this
                        # chunk) so the soft attack of the first word is kept.
                        print(f"[DEBUG] Voice detected! (prob={prob:.2f}, detection={vad_mode})")
                        is_speaking = True
                        silence_buffer = []
                        for b in self._snapshot_preroll():
                            silence_buffer.extend(b)
                        silence_duration = 0.0
                        voiced_duration = chunk_duration if is_strong_voice else 0.0
                    else:
                        # Continuing speech — append this chunk
                        silence_buffer.extend(chunk)
                        if is_strong_voice:
                            voiced_duration += chunk_duration

                    # Force process if the buffer grows too large
                    buffer_duration = len(silence_buffer) / self.sample_rate
                    max_buffer_duration = 30.0  # Force process after 30s of continuous speech

                    if buffer_duration >= max_buffer_duration:
                        print(f"[DEBUG] Buffer reached max duration ({buffer_duration:.2f}s), forcing process...")
                        speech_audio = np.array(silence_buffer, dtype=np.float32)
                        threading.Thread(
                            target=self._process_continuous_chunk,
                            args=(speech_audio,),
                            daemon=True
                        ).start()
                        # Reset buffer but keep speaking state
                        silence_buffer = []
                        silence_duration = 0.0
                        voiced_duration = 0.0

                else:
                    # Silence detected
                    if not is_speaking:
                        # Not speaking — accumulate idle time
                        idle_duration += chunk_duration
                        if idle_timeout > 0 and idle_duration >= idle_timeout:
                            print(f"[DEBUG] Idle timeout reached ({idle_duration:.1f}s >= {idle_timeout}s), auto-stopping...")
                            self._ui_update(self.stop)
                            break

                    if is_speaking:
                        print(f"[DEBUG] Silence detected while speaking, duration={silence_duration:.2f}s")
                        # Continue accumulating silence
                        silence_buffer.extend(chunk)
                        silence_duration += chunk_duration

                        # Check if pause threshold exceeded
                        if silence_duration >= pause_threshold:
                            # Gate on actual voiced (strong-speech) duration
                            total_duration = len(silence_buffer) / self.sample_rate

                            if voiced_duration < short_utterance_floor:
                                print(f"[DEBUG] SKIPPED - voiced too short ({voiced_duration:.2f}s < {short_utterance_floor}s), likely noise")
                            elif len(silence_buffer) > 0:
                                speech_audio = np.array(silence_buffer, dtype=np.float32)
                                print(f"[DEBUG] Processing audio chunk: {len(speech_audio)} samples, {total_duration:.2f}s (voiced: {voiced_duration:.2f}s)")
                                threading.Thread(
                                    target=self._process_continuous_chunk,
                                    args=(speech_audio,),
                                    daemon=True
                                ).start()

                            # Reset for next speech segment
                            silence_buffer = []
                            silence_duration = 0.0
                            voiced_duration = 0.0
                            is_speaking = False
                            idle_duration = 0.0

            # Flush remaining audio buffer when stopping
            if is_speaking and len(silence_buffer) > 0:
                speech_audio = np.array(silence_buffer, dtype=np.float32)
                total_duration = len(speech_audio) / self.sample_rate
                if voiced_duration < short_utterance_floor:
                    print(f"[DEBUG] Flush SKIPPED - voiced too short ({voiced_duration:.2f}s < {short_utterance_floor}s), likely noise")
                elif total_duration >= 0.3:
                    print(f"[DEBUG] Flushing remaining buffer: {len(speech_audio)} samples, {total_duration:.2f}s (voiced: {voiced_duration:.2f}s)")
                    threading.Thread(
                        target=self._process_continuous_chunk,
                        args=(speech_audio,),
                        daemon=True
                    ).start()

        except Exception as e:
            print(f"[DEBUG] ERROR in _continuous_loop: {e}")
            import traceback
            traceback.print_exc()
            self._ui_update(self.status_var.set, f"Error: {str(e)}")
            self.continuous_mode = False
        finally:
            self._end_session()

        print("[DEBUG] _continuous_loop() ended")

    def _process_continuous_chunk(self, audio_data):
        """Process continuous audio chunk"""
        try:
            print(f"[DEBUG] _process_continuous_chunk called with {len(audio_data)} samples")

            temp_path, _, _ = process_audio(audio_data, self.sample_rate)

            language = self.settings['language'] if self.settings['language'] != "auto" else None
            print(f"[DEBUG] Sending to recognizer...")
            result = self._transcribe(temp_path, language)
            transcription = result.get("text", "")
            status = result.get("status", "ok")
            print(f"[DEBUG] Got transcription: status={status}, text='{transcription}'")

            try:
                os.unlink(temp_path)
            except Exception:
                pass

            # This chunk was classified as speech — a failure/empty here is a missed
            # transcription, surfaced rather than silently dropped.
            if status == "failed":
                msg = f"⚠ Transcription failed: {result.get('error', 'service error')}"
                print(f"[DEBUG] {msg}")
                self._ui_update(self.status_var.set, msg)
                if self.overlay_window:
                    self._ui_update(self.overlay_window.update_text, "[transcription failed]\n")
                return

            if not transcription.strip():
                print("[DEBUG] Empty result on detected speech (missed transcription)")
                self._ui_update(self.status_var.set, "⚠ Speech detected but not recognized")
                return

            def update_ui():
                print(f"[DEBUG] Inserting: '{transcription}'")
                self.output_text.insert(tk.END, transcription + " ")
                self.output_text.see(tk.END)

                # Paste BEFORE overlay update (overlay show can affect focus)
                self.paste_to_active_window(transcription + " ")

                # Update overlay after paste
                if self.overlay_window:
                    self.overlay_window.update_text(transcription + " ")

                # Clear any transient warning back to the live status
                self.status_var.set("🔴 LIVE - Continuous transcription active...")

            self._ui_update(update_ui)

        except ValueError as e:
            print(f"[DEBUG] ValueError: {e}")
        except Exception as e:
            print(f"[DEBUG] Exception: {e}")

    def paste_to_active_window(self, text):
        """Type text to active window.

        Game Mode: uses PostMessage/WM_CHAR to bypass anti-cheat detection.
        Normal Mode: uses pynput (SendInput) for maximum compatibility.
        """
        if self.settings.get('game_mode', False):
            # Game Mode: use PostMessage to bypass anti-cheat (like Win+H voice typing)
            print(f"[DEBUG] Game Mode: typing via PostMessage/WM_CHAR")
            try:
                time.sleep(0.05)  # Brief delay to ensure window focus
                success = self._post_message_type(text)
                if not success:
                    print(f"[DEBUG] PostMessage typing failed - no foreground window")
            except Exception as e:
                print(f"[DEBUG] Failed to type text via PostMessage: {e}")
        else:
            # Normal mode: use pynput (SendInput) for best compatibility
            try:
                from pynput.keyboard import Controller
                keyboard_controller = Controller()
                time.sleep(0.05)  # Brief delay to ensure window focus
                keyboard_controller.type(text)
            except Exception as e:
                print(f"[DEBUG] Failed to type text: {e}")

    def _post_message_type(self, text):
        """Type text using PostMessage/WM_CHAR (bypasses SendInput detection).

        Sends characters through the Windows message queue using PostMessageW,
        which is how Windows native voice typing (Win+H) delivers text.
        Unlike SendInput, this does not set the LLMHF_INJECTED flag.

        Uses AttachThreadInput + GetFocus to find the actual focused child
        control (e.g. a game's chat input box) rather than the top-level window.
        """
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        WM_CHAR = 0x0102
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        VK_RETURN = 0x0D

        # Get foreground window
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        # Attach to target thread to access its focused control
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        current_tid = kernel32.GetCurrentThreadId()
        attached = False

        if target_tid != current_tid:
            attached = user32.AttachThreadInput(current_tid, target_tid, True)

        try:
            # GetFocus returns the actual focused child (e.g. chat input box)
            focused = user32.GetFocus()
            if focused:
                hwnd = focused
                print(f"[DEBUG] PostMessage: using focused child window {hwnd}")
            else:
                print(f"[DEBUG] PostMessage: using foreground window {hwnd}")
        finally:
            if attached:
                user32.AttachThreadInput(current_tid, target_tid, False)

        # Send characters to the focused control
        char_delay = self.settings.get('game_mode_char_delay', 0.01)

        for char in text:
            if char in ('\n', '\r'):
                # Enter key: send WM_KEYDOWN + WM_KEYUP for VK_RETURN
                lparam_down = 1 | (0x1C << 16)
                lparam_up = 1 | (0x1C << 16) | (1 << 30) | (1 << 31)
                user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, lparam_down)
                time.sleep(char_delay)
                user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, lparam_up)
            else:
                # All characters including Unicode/CJK: send WM_CHAR
                user32.PostMessageW(hwnd, WM_CHAR, ord(char), 0)

            time.sleep(char_delay)

        return True

    def copy_to_clipboard(self):
        """Copy text to clipboard"""
        text = self.output_text.get(1.0, tk.END).strip()
        if text:
            pyperclip.copy(text)
            self.status_var.set("✓ Copied to clipboard!")
        else:
            self.status_var.set("Nothing to copy")

    def clear_text(self):
        """Clear output text"""
        self.output_text.delete(1.0, tk.END)
        # Clear overlay if exists
        if self.overlay_window:
            self.overlay_window.clear_text()

        self.status_var.set("Text cleared")

    def run(self):
        """Run the application"""
        print("[DEBUG] Starting mainloop...")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("[DEBUG] App is running. Check system tray for icon.")
        self.root.mainloop()
        print("[DEBUG] Mainloop ended")

    def on_closing(self):
        """Cleanup on close"""
        self.is_recording = False
        self.continuous_mode = False
        self._end_session()
        self._close_mic_stream()
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.overlay_window:
            self.overlay_window.destroy()
        self.root.destroy()


def _acquire_single_instance_lock():
    """Ensure only one instance of the app runs at a time (Windows only).

    Uses a named mutex. Returns the mutex handle if acquired,
    or None if another instance is already running.
    """
    if sys.platform != "win32":
        return True

    import ctypes
    kernel32 = ctypes.windll.kernel32
    ERROR_ALREADY_EXISTS = 183
    MUTEX_NAME = "Global\\SpeechToText_SingleInstance"

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if handle:
            kernel32.CloseHandle(handle)
        return None

    return handle


def main():
    mutex = _acquire_single_instance_lock()
    if mutex is None:
        # Another instance is already running
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "SpeechToText is already running.\nCheck the system tray.",
                "SpeechToText",
                0x40  # MB_ICONINFORMATION
            )
        print("Another instance is already running. Exiting.")
        sys.exit(0)

    try:
        app = SimpleSTTApp()
        app.run()
    finally:
        # Release mutex
        if sys.platform == "win32" and mutex is not True:
            import ctypes
            ctypes.windll.kernel32.ReleaseMutex(mutex)
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
