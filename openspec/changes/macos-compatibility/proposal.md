## Why

The app is currently Windows-only: several core features use Win32 APIs (single-instance mutex, Game Mode `PostMessage` typing, auto-start via the registry `Run` key, `winsound` beeps, frozen-exe DLL pre-loading), and the build targets a Windows PyInstaller exe. Users on macOS — both Intel (x86_64) and Apple Silicon (arm64) — cannot run it. This change plans the work to make the app run on macOS and to produce distributable macOS builds for both architectures.

## What Changes

- Add macOS implementations for the OS-integrated features that are currently Win32-only:
  - **Auto-start**: a `~/Library/LaunchAgents/*.plist` LaunchAgent (instead of the registry `Run` key)
  - **Sound cues**: `afplay`/`NSSound`/terminal bell (instead of `winsound.Beep`)
  - **Single-instance**: a lock file / POSIX mechanism (instead of a named mutex)
- Resolve the macOS GUI threading constraint: AppKit (the `pystray` menu-bar backend) and Tk both require the main thread, while today the tray runs on a daemon thread. Choose and implement a macOS-compatible tray/main-loop model.
- Hide or disable **Game Mode** on macOS (the `PostMessage`/`WM_CHAR` anti-cheat trick has no macOS equivalent); keep normal typing via `pynput`.
- Document and handle the macOS **permissions** flow (Accessibility + Input Monitoring) required for global hotkeys and typing into the active app.
- Add a macOS **packaging** path: PyInstaller `.app` build, the dual-architecture strategy (Intel + Apple Silicon), and code-signing + notarization for distribution. **BREAKING (build):** the single Windows `.spec`/`build.bat` no longer covers all targets; a macOS build path is added alongside.
- Keep all existing Windows behavior unchanged (every macOS branch is `sys.platform`-guarded).

## Capabilities

### New Capabilities
- `macos-runtime-support`: The application runs correctly on macOS (Intel and Apple Silicon), with platform-appropriate implementations of auto-start, sound cues, single-instance, the tray/main-loop model, Game-Mode hiding, and the required-permissions flow.
- `macos-packaging`: A repeatable build process that produces distributable macOS apps for both Intel and Apple Silicon, signed and notarized for Gatekeeper.

### Modified Capabilities
<!-- None at the spec level. Existing Windows behavior is preserved; macOS branches are additive and platform-guarded. -->

## Impact

- **Code**: `src/desktop_app.py` (single-instance lock, auto-start, sound cues, Game-Mode gating, tray/main-loop model, frozen-path guards), possibly a small `src/platform_*.py` split for OS-specific helpers.
- **Build**: new `build_scripts/desktop_app_mac.spec` (or a parametrized spec) + a macOS build script; `docs/` notes for signing/notarization and the dual-arch strategy.
- **Dependencies**: macOS needs `pyobjc` (pulled in by `pynput`/`pystray` on macOS); `rumps` may be added if the menu bar is reimplemented natively. onnxruntime/soundfile/sounddevice already ship macOS wheels (separate x86_64 / arm64).
- **Constraints**: macOS builds **cannot be cross-compiled from Windows** — they must be built on a Mac. A single x86_64 build runs on Intel natively and on Apple Silicon via Rosetta 2; native performance on both requires two arch-specific builds (universal2 is impractical because onnxruntime has no universal2 wheel). Distribution requires an Apple Developer ID ($99/yr) for signing + notarization.
- **Out of scope**: offline Whisper fallback on macOS builds (same as Windows — excluded to keep the bundle small).
