# Windows Desktop Speech-to-Text App

## Quick Start

Double-click **`run_desktop.bat`** to launch the desktop app.

## Features

✅ **System-wide hotkeys** - Works from any application
✅ **Auto-paste** - Automatically pastes transcription into active text field
✅ **Real-time recording** - Record and transcribe with a single hotkey
✅ **Clipboard integration** - Copy transcriptions with one click

## How to Use

### Method 1: Using Hotkeys (Recommended)

1. **Start the app** by running `run_desktop.bat`
2. **Focus any text field** (Word, Notepad, browser, etc.)
3. **Press `Ctrl+Shift+Space`** to start recording
4. **Speak clearly** into your microphone
5. **Press `Ctrl+Shift+Space` again** to stop recording
6. The transcription will **automatically paste** into your active field!

### Method 2: Using the GUI

1. Click the **"Start Recording"** button
2. Speak into your microphone
3. Click the button again to stop
4. The transcription appears in the text box
5. If auto-paste is enabled, it pastes automatically
6. Use **"Copy"** button to manually copy to clipboard

## Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+Space` | Start/Stop Recording |
| `Ctrl+Shift+P` | Toggle Auto-Paste On/Off |

## Settings

- **Auto-paste to active window**: When enabled, transcription is automatically pasted into whatever text field you were focused on
- **Language**: Choose specific language or "auto" for automatic detection

## Workflow Example

**Scenario: Dictating an email**

1. Open your email client
2. Click in the email body field
3. Press `Ctrl+Shift+Space` (desktop app can be minimized)
4. Dictate your email: *"Hello team, I wanted to update you on the project progress..."*
5. Press `Ctrl+Shift+Space` to stop
6. ✨ Text automatically appears in your email!

**Scenario: Taking notes**

1. Open Notepad/Word/Notion/etc.
2. Position cursor where you want text
3. Press `Ctrl+Shift+Space`
4. Speak your notes
5. Press `Ctrl+Shift+Space`
6. Continue typing or dictate more

## Technical Details

- Uses **Whisper** for speech recognition (same as web version)
- **No internet required** for transcription
- Works with **any Windows application** that accepts text input
- Audio is processed locally on your machine

## Tips for Best Results

- **Speak clearly** at a moderate pace
- **Minimize background noise**
- Use a **good quality microphone**
- For better accuracy, select your language instead of "auto"
- Keep recordings under 30 seconds for faster processing

## Troubleshooting

### "Recording... Speak now!" but nothing happens
- Check your microphone permissions in Windows Settings
- Verify the correct microphone is selected as default device
- Try speaking louder or closer to the microphone

### Text doesn't auto-paste
- Make sure "Auto-paste to active window" is checked
- Click in the target text field before recording
- Some applications may block automated pasting (use Copy button instead)

### Hotkeys don't work
- The app must be running (can be minimized)
- Check if another application is using the same hotkey
- Try running the app as Administrator

### App won't start
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check that Python virtual environment is activated
- Look for error messages in the console

## Comparison: Desktop vs Web App

| Feature | Desktop App | Web App |
|---------|-------------|---------|
| Auto-paste to any window | ✅ Yes | ❌ No |
| Global hotkeys | ✅ Yes | ❌ No |
| Works offline | ✅ Yes | ✅ Yes |
| Real-time streaming | ❌ No | ✅ Yes |
| Ollama enhancement | ❌ No | ✅ Yes |
| Minimizes to background | ✅ Yes | ❌ No |

## Running Both Apps

You can run both apps simultaneously:
- **Desktop app**: For quick dictation with auto-paste (`run_desktop.bat`)
- **Web app**: For longer transcriptions with Ollama enhancement (`python app.py`)

## Advanced Usage

### Running from Command Line

```bash
# Activate virtual environment
venv\Scripts\activate

# Run desktop app
python desktop_app.py
```

### Customizing Hotkeys

Edit `desktop_app.py` and modify this section:

```python
self.hotkey_listener = keyboard.GlobalHotKeys({
    '<ctrl>+<shift>+<space>': self.toggle_recording,
    '<ctrl>+<shift>+p': self.toggle_auto_paste
})
```

Change the key combinations to your preference.
