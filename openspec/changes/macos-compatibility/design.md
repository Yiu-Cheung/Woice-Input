## Context

The app is a tray-resident, global-hotkey, "type-into-the-active-app" speech-to-text tool. Its core is portable (numpy, soundfile, sounddevice/PortAudio, onnxruntime/Silero VAD, SpeechRecognition over HTTP, tkinter), but five features are Win32-specific and one build target (PyInstaller exe) is Windows-only. The Windows-only pieces are already `sys.platform`-guarded, so on macOS they currently no-op (auto-start, sound, single-instance) or are inapplicable (Game Mode, frozen DLL pre-load). The hard parts are not the small platform branches but (1) the macOS GUI main-thread model and (2) packaging/distribution for two CPU architectures with signing.

This change is a **plan**. Some decisions cannot be finalized from Windows because they require a Mac to validate (tray model, build, signing). Those are called out as Open Questions rather than guessed.

## Goals / Non-Goals

**Goals:**
- The Python source runs on macOS (Intel + Apple Silicon) with platform-appropriate auto-start, sound, single-instance, tray, and permissions handling.
- A documented, repeatable macOS build that yields apps running on both architectures, signed + notarized for distribution.
- Zero behavior change on Windows — every macOS branch is additive and `sys.platform`-guarded.

**Non-Goals:**
- Game Mode on macOS (no `PostMessage`/`WM_CHAR` equivalent).
- Offline Whisper fallback in the macOS bundle (excluded, same as Windows, to keep size down).
- A single universal2 binary (impractical — onnxruntime has no universal2 wheel).
- Cross-compiling macOS builds from Windows (not possible with PyInstaller).

## Decisions

### Decision 1: Keep one codebase, branch by `sys.platform`
Add macOS branches alongside the existing Windows ones rather than forking. Optionally factor OS helpers into a small `src/platform_win.py` / `src/platform_mac.py` with a thin selector, if the branches grow.
**Why:** the portable core is the majority; the OS-specific surface is small and already guarded. A second codebase would drift.
**Alternative:** a separate macOS app — rejected (maintenance cost, duplicated logic).

### Decision 2: macOS tray/main-loop model (the crux) — needs validation on a Mac
On macOS, AppKit (which backs `pystray`'s menu-bar item) must run on the **main thread**, but today `tray_icon.run()` is started on a daemon thread while Tk owns the main loop. Two GUI loops both wanting the main thread is the core conflict. Candidate approaches, to be chosen after testing on a Mac:
- **(a)** Run `pystray` on the main thread and drive Tk via `root.update()` pumped from a timer/AppKit callback (give AppKit the main thread, cooperatively service Tk).
- **(b)** Replace the macOS menu bar with `rumps` (native, main-thread) and run Tk windows as needed.
- **(c)** macOS "no tray" fallback: keep the main window / a minimal menu instead of a tray, if (a)/(b) prove brittle.
**Why:** there is no way to verify which is robust without a Mac; the spec only requires that tray + Tk both function. Lock the choice during implementation on-device.

### Decision 3: Auto-start via LaunchAgent
Implement `is_autostart_enabled()` / `set_autostart()` macOS branches that write/remove `~/Library/LaunchAgents/com.<id>.speechtotext.plist` with a `ProgramArguments` pointing at the app (the `.app` bundle when frozen, or `pythonw`-equivalent + project for source) and `RunAtLoad`.
**Why:** LaunchAgents are the standard per-user login mechanism; no admin needed, mirrors the Windows Run-key model already in code.
**Alternative:** `osascript` "Login Items" — rejected (less scriptable, AppleScript brittleness).

### Decision 4: Sound cues via `afplay`/`NSSound`
Replace `winsound.Beep` on macOS with a short bundled sound played via `afplay` (subprocess, off-thread) or `NSSound`; fall back to the terminal bell. Keep the same `sound_cues` setting and high/low distinction where feasible.
**Why:** `winsound` is Windows-only; `afplay` is always present on macOS.

### Decision 5: Single-instance via lock file
Replace the named mutex with an exclusive lock on a file in the user's app-support/temp dir (e.g. `fcntl.flock` or atomic `O_CREAT|O_EXCL` with PID + liveness check).
**Why:** POSIX parity for the existing single-instance guarantee.

### Decision 6: Packaging — x86_64-first, two-build option
Default documented path: build **x86_64** on a Mac → runs natively on Intel and under **Rosetta 2** on Apple Silicon (simplest "both" coverage). Document the **two arch-native builds** option (build arm64 on Apple Silicon, x86_64 on Intel/Rosetta) for native performance. Reuse the Windows spec's `collect_all('onnxruntime')` + VAD-model bundling; anchor `settings.json`/model paths to the bundle (the absolute-path fix already done for Windows generalizes).
**Why:** universal2 is blocked by onnxruntime; x86_64+Rosetta is the least-effort way to cover both, with the two-build path documented for those who want native arm64.

### Decision 7: Signing + notarization documented, not automated initially
Document `codesign` (Developer ID Application) + `notarytool` submission + stapling. Provide an unsigned local-test path.
**Why:** signing needs an Apple Developer account and secrets that aren't available here; document the steps so a maintainer with a Mac + account can execute.

## Risks / Trade-offs

- **Tray/main-thread model may be brittle** → Mitigation: three fallback approaches (Decision 2); validate on-device; tray-less fallback acceptable per spec.
- **macOS permissions (Accessibility / Input Monitoring) can't be auto-granted** → Mitigation: detect failure, guide the user to System Settings; document in README.
- **pynput global hotkeys less reliable on macOS** → Mitigation: verify on-device; consider an alternative hotkey lib if needed (out of scope to pick now).
- **Rosetta path is slower / requires Rosetta installed** → Mitigation: document; offer arm64-native build option.
- **Cannot build or test from Windows** → Mitigation: this change ships the source-level compatibility + documented build steps; the actual `.app` build, signing, and on-device QA happen on a Mac (a follow-up execution step).
- **tkinter on macOS quirks** (focus, window levels, overlay always-on-top) → Mitigation: on-device QA of Settings + overlay.

## Migration Plan

1. Land source-level macOS branches (auto-start, sound, single-instance, Game-Mode gating, tray model) — Windows behavior unchanged.
2. On a Mac: `pip install` deps, run `python -m src`, validate runtime spec scenarios; finalize the tray model (Decision 2).
3. On a Mac: add the macOS PyInstaller spec/script; produce an x86_64 `.app`; validate on Intel + Apple Silicon (Rosetta).
4. Sign + notarize with a Developer ID; validate Gatekeeper on a clean Mac.
5. (Optional) add the arm64-native build for native performance.
6. Rollback: macOS branches are guarded; reverting them leaves Windows untouched.

## Open Questions

- Which tray model (Decision 2 a/b/c) survives real macOS testing?
- Is `pynput` sufficient for global hotkeys on macOS, or is a native hotkey path needed?
- Default distribution: ship x86_64-only (Rosetta on Silicon) or both arch-native builds?
- Is an Apple Developer ID available for signing/notarization, or is distribution limited to unsigned/local for now?
- Where should `settings.json` live on macOS — next to the `.app`, or `~/Library/Application Support/SpeechToText/` (more macOS-idiomatic)?
