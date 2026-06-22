## 1. Source-level platform branches (can be written from Windows)

- [ ] 1.1 Add a platform helper (`sys.platform` checks; optional `src/platform_mac.py` / `platform_win.py` split) so OS-specific code is selected cleanly
- [ ] 1.2 macOS auto-start: implement `is_autostart_enabled()` / `set_autostart()` via a `~/Library/LaunchAgents/*.plist` (RunAtLoad), mirroring the Windows Run-key behavior
- [ ] 1.3 macOS sound cues: implement `_play_cue` via `afplay`/`NSSound` (off-thread), graceful no-op if unavailable
- [ ] 1.4 macOS single-instance: replace the named mutex with an exclusive lock file (PID + liveness), `sys.platform`-guarded
- [ ] 1.5 Hide/disable Game Mode in `SettingsDialog` on macOS; ensure normal `pynput` typing path is used
- [ ] 1.6 Audit all `ctypes.windll` / `winreg` / `winsound` / frozen-DLL blocks are guarded so import + run on macOS never executes them
- [ ] 1.7 Generalize data-file paths (settings.json, VAD model) for the macOS bundle layout (decide: next-to-.app vs `~/Library/Application Support/`)

## 2. macOS tray / main-loop model (requires a Mac to validate)

- [ ] 2.1 Prototype tray model (a): pystray on the main thread + Tk pumped via `root.update()`; verify menu bar + Settings/overlay both work
- [ ] 2.2 If (a) is brittle, evaluate (b) `rumps` menu bar, or (c) tray-less fallback (main window)
- [ ] 2.3 Lock in the chosen model; ensure start/stop, settings, exit all work from the menu bar
- [ ] 2.4 macOS permissions: detect hotkey/typing failures and guide user to Accessibility + Input Monitoring; document in README

## 3. On-device runtime validation (Mac)

- [ ] 3.1 `pip install` deps on a Mac (arm64 + x86_64); confirm onnxruntime/soundfile/sounddevice wheels resolve per arch
- [ ] 3.2 Run `python -m src`; verify launch, VAD, mic capture, global hotkey, typing into active app
- [ ] 3.3 Verify auto-start (LaunchAgent), sound cues, single-instance, Game-Mode hidden
- [ ] 3.4 Verify on Apple Silicon (native) and Intel (or Silicon via Rosetta)

## 4. macOS packaging (requires a Mac)

- [ ] 4.1 Add `build_scripts/desktop_app_mac.spec` (collect onnxruntime + VAD model; macOS `.app` `BUNDLE`)
- [ ] 4.2 Add a macOS build script; produce an x86_64 `.app`
- [ ] 4.3 Verify the `.app` runs on Intel natively and on Apple Silicon via Rosetta 2
- [ ] 4.4 (Optional) produce an arm64-native `.app`; document the two-build vs Rosetta trade-off
- [ ] 4.5 Confirm bundled VAD model + settings path resolve correctly inside the `.app`

## 5. Signing & distribution (requires Apple Developer ID)

- [ ] 5.1 Document `codesign` (Developer ID Application) for the `.app`
- [ ] 5.2 Document `notarytool` submission + `stapler` stapling
- [ ] 5.3 Validate Gatekeeper opens the signed+notarized app cleanly on a fresh Mac
- [ ] 5.4 Document the unsigned local-test path and its Gatekeeper caveat

## 6. Docs

- [ ] 6.1 README: macOS install/run, required permissions, dual-arch strategy, build + signing steps
- [ ] 6.2 Note the constraint that macOS builds must be produced on a Mac (no cross-compile from Windows)
