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
    from .vad import SileroVAD
    _vad_available = True
except (ImportError, FileNotFoundError) as e:
    _vad_available = False
    print(f"[WARNING] Silero VAD not available ({e}), using amplitude detection")

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import pyperclip
from pynput import keyboard
import numpy as np
import sounddevice as sd
import time
import json
import pystray
from PIL import Image, ImageDraw
from .transcription import transcribe_with_google
from .audio_processor import process_audio
from .overlay import FloatingOverlay

SETTINGS_FILE = "settings.json"


class SettingsDialog:
    def __init__(self, parent, settings):
        self.settings = settings
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.grab_set()
        self.dialog.attributes('-topmost', True)

        # Center dialog on screen
        dialog_width = 450
        dialog_height = 680
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

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
        self.vad_threshold_var = tk.DoubleVar(value=settings.get('vad_threshold', 0.5))
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

            self.settings['language'] = self.language_var.get()
            self.settings['microphone'] = self.microphone_var.get()
            self.settings['game_mode'] = self.game_mode_var.get()
            self.settings['continuous'] = self.continuous_var.get()
            self.settings['pause_threshold'] = pause_threshold
            self.settings['silence_threshold'] = silence_threshold
            self.settings['idle_timeout'] = idle_timeout
            self.settings['vad_threshold'] = self.vad_threshold_var.get()

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

    def _load_settings(self):
        """Load settings from file or return defaults"""
        default_settings = {
            'language': 'yue',
            'continuous': False,
            'pause_threshold': 1.5,  # Seconds of silence before processing
            'silence_threshold': 0.01,  # Audio amplitude threshold for silence detection
            'game_mode': False,  # Use PostMessage/WM_CHAR instead of SendInput (for games with anti-cheat)
            'game_mode_char_delay': 0.01,  # Delay between characters in game mode (seconds)
            'idle_timeout': 10,  # Auto-stop recording after N seconds of silence (0 = disabled)
            'vad_threshold': 0.5,  # Silero VAD speech probability threshold (0.0-1.0)
            'overlay_enabled': False,
            'overlay_opacity': 0.90,
            'overlay_width': 400,
            'overlay_height': 150,
            'overlay_position': 'bottom-right',
            'overlay_max_lines': 10,
            'overlay_font_size': 11,
            'microphone': 'auto'
        }

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
        # Create idle icon (green) and recording icon (red)
        self._icon_idle = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(self._icon_idle)
        draw.ellipse([16, 16, 48, 48], fill='#4CAF50')

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

    def _check_voice_activity(self, audio_chunk):
        """Check if audio chunk contains speech using Silero VAD or amplitude fallback.

        Args:
            audio_chunk: 1D numpy float32 array of audio samples

        Returns:
            bool: True if speech detected
        """
        if self.vad_available:
            vad_threshold = self.settings.get('vad_threshold', 0.5)
            max_prob = 0.0
            # Process in 512-sample frames (required by Silero VAD)
            for i in range(0, len(audio_chunk) - 511, 512):
                frame = audio_chunk[i:i + 512]
                prob = self.vad.process(frame)
                max_prob = max(max_prob, prob)
            return max_prob >= vad_threshold
        else:
            return np.max(np.abs(audio_chunk)) >= self.settings['silence_threshold']

    def _update_tray(self):
        """Refresh tray icon and menu state."""
        if self.tray_icon:
            is_active = self.continuous_mode or self.is_recording
            self.tray_icon.icon = self._icon_recording if is_active else self._icon_idle
            self.tray_icon.update_menu()

    def start(self):
        """Start continuous mode or recording"""
        print(f"[DEBUG] start() called, continuous={self.settings['continuous']}")
        if self.settings['continuous']:
            self.start_continuous_mode()
        else:
            self.start_recording()
        self._update_tray()

    def stop(self):
        """Stop continuous mode or recording"""
        if self.settings['continuous']:
            self.stop_continuous_mode()
        else:
            self.stop_recording()
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
        """Record audio from microphone"""
        print("[DEBUG] _record_audio() thread started")
        idle_timeout = self.settings.get('idle_timeout', 10)
        silence_threshold = self.settings['silence_threshold']
        idle_duration = 0.0
        check_interval = 0.1  # 100ms

        def callback(indata, frames, time, status):
            if status:
                print(f"[DEBUG] Audio callback status: {status}")
            if self.is_recording:
                self.audio_data.append(indata.copy())

        try:
            mic_device = self._get_microphone_device()
            print(f"[DEBUG] Opening audio stream (sample_rate={self.sample_rate}, device={mic_device})")
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                device=mic_device,
                callback=callback
            ):
                print("[DEBUG] Audio stream opened, recording...")
                while self.is_recording:
                    sd.sleep(int(check_interval * 1000))
                    # Idle auto-stop for manual recording
                    if idle_timeout > 0 and self.audio_data:
                        latest = self.audio_data[-1].flatten()
                        if self._check_voice_activity(latest):
                            idle_duration = 0.0
                        else:
                            idle_duration += check_interval
                            if idle_duration >= idle_timeout:
                                print(f"[DEBUG] Manual recording idle timeout ({idle_duration:.1f}s), auto-stopping...")
                                self._ui_update(self.stop_recording)
                                break
            print("[DEBUG] Audio stream closed")
        except Exception as e:
            print(f"[DEBUG] ERROR in _record_audio: {e}")

    def stop_recording(self):
        """Stop recording and transcribe"""
        if not self.is_recording:
            return

        self.is_recording = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_var.set("Processing...")

        threading.Thread(target=self._process_audio, daemon=True).start()

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
            result = transcribe_with_google(temp_path, language)
            transcription = result["text"]
            print(f"[DEBUG] Transcription result: '{transcription}'")

            # Clean up
            try:
                os.unlink(temp_path)
            except Exception:
                pass

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
        """Continuous recording loop with Voice Activity Detection"""
        print("[DEBUG] _continuous_loop() started")
        # Reset VAD hidden state for a fresh stream
        if self.vad_available:
            self.vad.reset_states()
        pause_threshold = self.settings['pause_threshold']
        silence_threshold = self.settings['silence_threshold']
        idle_timeout = self.settings.get('idle_timeout', 10)
        vad_mode = "Silero VAD" if self.vad_available else "amplitude"
        print(f"[DEBUG] Continuous settings: pause={pause_threshold}s, silence={silence_threshold}, idle_timeout={idle_timeout}s, detection={vad_mode}")

        audio_buffer = []  # Accumulates audio while speaking
        silence_buffer = []  # Accumulates audio during silence
        silence_duration = 0.0
        is_speaking = False
        chunk_duration = 0.1  # Process in 100ms chunks
        loop_count = 0
        idle_duration = 0.0  # Time since last voice activity

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"[DEBUG] Continuous audio callback status: {status}")
            if self.continuous_mode:
                audio_buffer.append(indata.copy())

        try:
            mic_device = self._get_microphone_device()
            print(f"[DEBUG] Opening continuous audio stream (device={mic_device})...")
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                device=mic_device,
                callback=audio_callback
            ):
                print("[DEBUG] Continuous audio stream opened, entering main loop...")
                while self.continuous_mode:
                    loop_count += 1
                    if loop_count % 50 == 0:  # Print every 5 seconds
                        print(f"[DEBUG] Continuous loop running... (iteration {loop_count})")
                    time.sleep(chunk_duration)

                    if not audio_buffer:
                        continue

                    # Get latest audio chunk
                    chunk = np.concatenate(audio_buffer, axis=0).flatten()
                    audio_buffer.clear()

                    # Check if chunk contains voice (Silero VAD or amplitude fallback)
                    is_voice = self._check_voice_activity(chunk)

                    if is_voice:
                        # Voice detected — reset idle timer
                        idle_duration = 0.0
                        if not is_speaking:
                            # Start of new speech
                            print(f"[DEBUG] Voice detected! (detection={vad_mode})")
                            is_speaking = True
                            silence_buffer = []
                            silence_duration = 0.0

                        # Add to speech buffer
                        silence_buffer.extend(chunk)

                        # Check if buffer is getting too large (prevent memory issues and force processing)
                        buffer_duration = len(silence_buffer) / self.sample_rate
                        max_buffer_duration = 30.0  # Force process after 30 seconds of continuous speech

                        if buffer_duration >= max_buffer_duration:
                            print(f"[DEBUG] Buffer reached max duration ({buffer_duration:.2f}s), forcing process...")
                            # Force process even without pause
                            speech_audio = np.array(silence_buffer, dtype=np.float32)

                            threading.Thread(
                                target=self._process_continuous_chunk,
                                args=(speech_audio,),
                                daemon=True
                            ).start()

                            # Reset buffer but keep speaking state
                            silence_buffer = []
                            silence_duration = 0.0

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
                                # Check if actual voice content is long enough
                                total_duration = len(silence_buffer) / self.sample_rate
                                voice_duration = total_duration - silence_duration

                                if voice_duration < 0.5:
                                    print(f"[DEBUG] SKIPPED - voice too short ({voice_duration:.2f}s), likely noise")
                                elif len(silence_buffer) > 0:
                                    speech_audio = np.array(silence_buffer, dtype=np.float32)

                                    print(f"[DEBUG] Processing audio chunk: {len(speech_audio)} samples, {total_duration:.2f}s (voice: {voice_duration:.2f}s)")

                                    threading.Thread(
                                        target=self._process_continuous_chunk,
                                        args=(speech_audio,),
                                        daemon=True
                                    ).start()

                                # Reset for next speech segment
                                silence_buffer = []
                                silence_duration = 0.0
                                is_speaking = False
                                idle_duration = 0.0

                # Flush remaining audio buffer when stopping
                if is_speaking and len(silence_buffer) > 0:
                    speech_audio = np.array(silence_buffer, dtype=np.float32)
                    total_duration = len(speech_audio) / self.sample_rate
                    voice_duration = total_duration - silence_duration
                    if voice_duration < 0.5:
                        print(f"[DEBUG] Flush SKIPPED - voice too short ({voice_duration:.2f}s), likely noise")
                    elif total_duration >= 0.3:
                        print(f"[DEBUG] Flushing remaining buffer: {len(speech_audio)} samples, {total_duration:.2f}s (voice: {voice_duration:.2f}s)")
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

        print("[DEBUG] _continuous_loop() ended")

    def _process_continuous_chunk(self, audio_data):
        """Process continuous audio chunk"""
        try:
            print(f"[DEBUG] _process_continuous_chunk called with {len(audio_data)} samples")

            temp_path, _, _ = process_audio(audio_data, self.sample_rate)

            language = self.settings['language'] if self.settings['language'] != "auto" else None
            print(f"[DEBUG] Sending to Google SR...")
            result = transcribe_with_google(temp_path, language)
            transcription = result["text"]
            print(f"[DEBUG] Got transcription: '{transcription}'")

            try:
                os.unlink(temp_path)
            except Exception:
                pass

            if transcription.strip():
                def update_ui():
                    print(f"[DEBUG] Inserting: '{transcription}'")
                    self.output_text.insert(tk.END, transcription + " ")
                    self.output_text.see(tk.END)

                    # Paste BEFORE overlay update (overlay show can affect focus)
                    self.paste_to_active_window(transcription + " ")

                    # Update overlay after paste
                    if self.overlay_window:
                        self.overlay_window.update_text(transcription + " ")

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
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.overlay_window:
            self.overlay_window.destroy()
        self.root.destroy()


def main():
    app = SimpleSTTApp()
    app.run()


if __name__ == "__main__":
    main()
