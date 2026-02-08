"""
Test script to diagnose desktop app issues
"""
import sys

print("=" * 50)
print("Testing desktop app dependencies...")
print("=" * 50)

# Test 1: Import all required modules
print("\n1. Testing imports...")
try:
    import tkinter as tk
    print("   [OK] tkinter")
except Exception as e:
    print(f"   [FAIL] tkinter: {e}")
    sys.exit(1)

try:
    import pystray
    print("   [OK] pystray")
except Exception as e:
    print(f"   [FAIL] pystray: {e}")
    sys.exit(1)

try:
    from pynput import keyboard
    print("   [OK] pynput.keyboard")
except Exception as e:
    print(f"   [FAIL] pynput.keyboard: {e}")
    sys.exit(1)

try:
    import numpy as np
    print("   [OK] numpy")
except Exception as e:
    print(f"   [FAIL] numpy: {e}")
    sys.exit(1)

try:
    import sounddevice as sd
    print("   [OK] sounddevice")
except Exception as e:
    print(f"   [FAIL] sounddevice: {e}")
    sys.exit(1)

try:
    import speech_recognition as sr
    print("   [OK] speech_recognition")
except Exception as e:
    print(f"   [FAIL] speech_recognition: {e}")
    sys.exit(1)

# Test 2: Check if src modules exist
print("\n2. Testing src modules...")
try:
    from src.transcription import transcribe_with_google
    print("   [OK] src.transcription")
except Exception as e:
    print(f"   [FAIL] src.transcription: {e}")
    sys.exit(1)

try:
    from src.audio_processor import process_audio
    print("   [OK] src.audio_processor")
except Exception as e:
    print(f"   [FAIL] src.audio_processor: {e}")
    sys.exit(1)

# Test 3: Check if overlay module exists
print("\n3. Testing overlay module...")
try:
    from overlay import FloatingOverlay
    print("   [OK] overlay.py")
except Exception as e:
    print(f"   [FAIL] overlay.py: {e}")
    sys.exit(1)

# Test 4: Try creating a simple tray icon
print("\n4. Testing tray icon creation...")
try:
    from PIL import Image, ImageDraw

    icon_image = Image.new('RGB', (64, 64), color='white')
    draw = ImageDraw.Draw(icon_image)
    draw.ellipse([16, 16, 48, 48], fill='#4CAF50')

    menu = pystray.Menu(
        pystray.MenuItem("Test", lambda: print("Clicked!"))
    )

    test_icon = pystray.Icon("test", icon_image, "Test Icon", menu)
    print("   [OK] Tray icon created successfully")
except Exception as e:
    print(f"   [FAIL] Tray icon creation failed: {e}")
    sys.exit(1)

# Test 5: Try creating hotkey listener
print("\n5. Testing hotkey listener...")
try:
    listener = keyboard.GlobalHotKeys({
        '<ctrl>+<shift>+<space>': lambda: print("Hotkey pressed!")
    })
    print("   [OK] Hotkey listener created successfully")
    listener.stop()
except Exception as e:
    print(f"   [FAIL] Hotkey listener failed: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("Test complete!")
print("=" * 50)

input("\nPress Enter to exit...")
