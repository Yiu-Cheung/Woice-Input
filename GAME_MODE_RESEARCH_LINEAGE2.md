# Game Mode Research: Lineage 2 Input Injection

## Problem
Our speech-to-text app needs to type transcribed text into Lineage 2's chat input.
Lineage 2 uses GameGuard anti-cheat which blocks most external input injection methods.
**Windows native Voice Typing (Win+H) works** in Lineage 2 — we want to replicate its behavior.

---

## Methods Tested

### 1. pynput / SendInput (Normal Mode)
- **How it works**: Uses `SendInput` Win32 API to simulate keystrokes
- **Result**: BLOCKED by anti-cheat
- **Why**: `SendInput` sets the `LLMHF_INJECTED` flag on all events. GameGuard detects this flag and rejects the input.
- **Also applies to**: `keybd_event`, `KEYEVENTF_UNICODE` — all user-mode input injection via SendInput is flagged.

### 2. PostMessage WM_CHAR
- **How it works**: `PostMessageW(hwnd, WM_CHAR, ord(char), lParam)` sends character messages through the window message queue
- **Result**: BLOCKED or IGNORED
- **Why**:
  - UIPI (User Interface Privilege Isolation) silently blocks PostMessage from non-elevated to elevated processes
  - Even if delivered, Lineage 2's custom input handler may not process raw WM_CHAR for CJK text
  - Games with CJK support typically expect input through the IME pipeline, not raw WM_CHAR
- **Additional bug found**: Original code used `lParam=0` (repeat count 0). Fixed to `lParam=1`.

### 3. IME Composition (ImmSetCompositionStringW + ImmNotifyIME)
- **How it works**: Uses `imm32.dll` to inject text through the IME composition pipeline:
  1. `AttachThreadInput` to share input state with game thread
  2. `ImmGetContext(hwnd)` to get the IME context
  3. `ImmSetCompositionStringW(himc, SCS_SETSTR, text, ...)` to set composition text
  4. `ImmNotifyIME(himc, NI_COMPOSITIONSTR, CPS_COMPLETE, 0)` to commit
- **Result**: Works in Notepad, BLOCKED in Lineage 2
- **Why**: GameGuard likely hooks IME functions and validates the call stack. Synthetic IME composition from an external process is detected and rejected.

### 4. Clipboard + Ctrl+V Paste
- **Result**: NOT VIABLE
- **Why**: User confirmed copy-paste does not work in Lineage 2's chat.

### 5. Direct PostMessage of WM_IME_CHAR / WM_IME_COMPOSITION
- **Theoretical**: Post IME messages directly via PostMessage
- **Result**: NOT VIABLE
- **Why**:
  - Applications validate that IME messages come from the actual IME engine
  - Anti-cheat monitors for synthetic IME message patterns
  - UIPI blocks these messages if game is elevated

---

## Why Win+H (Windows Voice Typing) Works

Win+H uses the **Text Services Framework (TSF)**, a COM-based system integrated at the OS kernel level.

```
Win+H Architecture:
  Speech Recognition (kernel service)
    -> Text Services Framework (TSF)
      -> For TSF-aware apps: ITfInsertAtSelection (direct text insertion)
      -> For legacy apps: IME compatibility layer (generates IME messages)
        -> WM_IME_STARTCOMPOSITION
        -> WM_IME_COMPOSITION (GCS_RESULTSTR)
        -> WM_IME_ENDCOMPOSITION
```

Key differences from our approach:

| Property | Win+H | Our App |
|----------|-------|---------|
| Process level | System service (kernel) | User-mode Python |
| Manifest | `uiAccess=true` | No special manifest |
| Input pipeline | TSF -> IME engine -> messages | Direct IME API calls |
| UIPI | Bypasses (uiAccess) | Blocked (lower integrity) |
| Anti-cheat detection | Whitelisted system component | Detected as external injection |
| LLMHF_INJECTED flag | Not set (kernel path) | Set (SendInput) or N/A (PostMessage) |

### Why we can't replicate Win+H:
1. **uiAccess=true** requires: signed executable + installed in Program Files + manifest declaration
2. **Kernel-level input**: Only system services can inject input without LLMHF_INJECTED
3. **TSF Text Input Processor**: Requires implementing complex COM interfaces (ITfTextInputProcessor, ITfKeyEventSink, etc.) and registering as a system TIP
4. **Anti-cheat whitelisting**: GameGuard whitelists Windows system components by path/signature

---

## UIPI (User Interface Privilege Isolation)

A critical factor that may explain failures:

- Windows Vista+ enforces UIPI: processes at lower integrity cannot send window messages to higher integrity processes
- `PostMessageW` returns 0 (silently fails) when blocked by UIPI
- Games often run elevated (admin) or their anti-cheat service elevates them
- **Fix**: Run our app as administrator (same integrity level)

### How to check:
```python
import ctypes
is_admin = ctypes.windll.shell32.IsUserAnAdmin()  # Returns True if admin
```

### How to run as admin:
```bat
powershell -Command "Start-Process python -ArgumentList 'desktop_app.py' -Verb RunAs"
```

---

## Possible Future Approaches (Not Implemented)

### A. Virtual Keyboard Driver
- Create a kernel-mode HID driver that simulates a real keyboard
- Input would be indistinguishable from physical keyboard
- **Complexity**: Requires signed kernel driver (Microsoft WHQL certification)
- **Feasibility**: Very low for a Python project

### B. TSF Text Input Processor (TIP)
- Register as a legitimate Text Input Processor via COM
- Would be treated as a system input method
- **Complexity**: Extremely high — requires implementing 5+ COM interfaces in C++/C#
- **Feasibility**: Possible but requires compiled COM server, not practical in Python

### C. Windows Accessibility / UI Automation
- Use `IUIAutomationValuePattern::SetValue` to set text in UI controls
- **Problem**: Game UI controls don't expose UIA patterns (custom engine rendering)
- **Feasibility**: Won't work for games

### D. Named Pipe / Memory Injection
- Inject text directly into the game's memory (chat buffer)
- **Problem**: Extremely game-version-specific, anti-cheat detects memory manipulation
- **Feasibility**: Not recommended, likely violates ToS

### E. OCR + Synthetic Touch Input
- Use `InputInjector` (UWP) to inject touch/pen input
- **Problem**: Requires `inputInjectionBrokered` capability (signed apps only)
- **Feasibility**: Not available for regular apps

---

## Current Implementation Status

The game mode in `desktop_app.py` implements:
1. **Primary**: IME composition via `imm32.dll` (works for standard apps)
2. **Fallback**: PostMessage WM_CHAR with correct lParam (works for some apps)
3. **Proper 64-bit ctypes types**: All Win32 API calls have correct restype/argtypes
4. **Background thread paste**: Does not block Tkinter main thread

### What works:
- Standard Windows applications (Notepad, browsers, etc.)
- Applications that process WM_CHAR or IME messages

### What doesn't work:
- Games with strict anti-cheat (Lineage 2, games using GameGuard/XIGNCODE3/EasyAntiCheat)
- Elevated processes when our app runs non-elevated (UIPI)

### Recommendation for Lineage 2 users:
1. **Try running the app as administrator** first (fixes UIPI issues)
2. If still blocked, **use Win+H** (Windows Voice Typing) — it's the only method that bypasses GameGuard
3. Our app can still be used for transcription display (overlay) while Win+H handles the actual typing

---

## References
- [ImmSetCompositionStringW - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/imm/nf-imm-immsetcompositionstringw)
- [ImmNotifyIME - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/imm/nf-imm-immnotifyime)
- [Text Services Framework - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/tsf/text-services-framework)
- [Using an IME in a Game - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/using-an-input-method-editor-in-a-game)
- [User Interface Privilege Isolation (UIPI)](https://learn.microsoft.com/en-us/archive/blogs/vishalsi/what-is-user-interface-privilege-isolation-uipi-on-vista)
- [LLMHF_INJECTED flag - Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-msllhookstruct)
