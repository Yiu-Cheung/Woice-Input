## ADDED Requirements

### Requirement: Application launches on macOS

The application SHALL start and run on macOS for both Intel (x86_64) and Apple Silicon (arm64). Windows-only code paths SHALL be guarded so they are skipped (not executed) on macOS, and no Win32-only import SHALL be required at import time on macOS.

#### Scenario: Launch on Apple Silicon

- **WHEN** the app is launched on an arm64 Mac
- **THEN** the UI, system tray, global hotkey, microphone capture, and VAD all initialize without error

#### Scenario: Launch on Intel

- **WHEN** the app is launched on an x86_64 Mac (natively or via Rosetta 2)
- **THEN** the app initializes the same way as on Apple Silicon

#### Scenario: Windows-only code is skipped

- **WHEN** running on macOS
- **THEN** the frozen-exe DLL pre-load, named-mutex single-instance, and registry/`winsound` calls SHALL be skipped via `sys.platform` guards, not raise

### Requirement: Tray and main loop coexist on macOS

The application SHALL present its menu-bar/tray UI on macOS using a model compatible with AppKit's main-thread requirement, so the tray and the Tk UI both function (today the tray runs on a daemon thread, which AppKit forbids).

#### Scenario: Menu bar usable on macOS

- **WHEN** the app runs on macOS
- **THEN** a menu-bar item is shown with Start/Stop, settings, and exit actions, and clicking them works

#### Scenario: Tk windows still open

- **WHEN** the user opens Settings or the overlay on macOS
- **THEN** those windows render and respond without deadlocking the menu bar

### Requirement: macOS auto-start on login

The system SHALL provide an opt-in "start on login" on macOS implemented with a per-user LaunchAgent (`~/Library/LaunchAgents/<id>.plist`) instead of the Windows registry. The toggle SHALL reflect the actual LaunchAgent state and SHALL be removable.

#### Scenario: Enable auto-start on macOS

- **WHEN** the user enables "start on login" on macOS
- **THEN** a LaunchAgent plist is written that launches the app at login, and the toggle reads as enabled

#### Scenario: Disable auto-start on macOS

- **WHEN** the user disables "start on login" on macOS
- **THEN** the LaunchAgent plist is removed and the toggle reads as disabled

### Requirement: macOS sound cues

The system SHALL play the start/stop audio cue on macOS using a macOS-available mechanism (e.g. `afplay` or `NSSound`) when `sound_cues` is enabled, and SHALL no-op gracefully if playback is unavailable.

#### Scenario: Cue on macOS

- **WHEN** `sound_cues` is enabled and the user starts or stops capture on macOS
- **THEN** a short audible cue plays without blocking the UI

### Requirement: macOS single-instance

The system SHALL prevent a second concurrent instance on macOS using a POSIX-appropriate mechanism (e.g. an exclusive lock file), giving parity with the Windows named mutex.

#### Scenario: Second instance blocked on macOS

- **WHEN** the app is already running on macOS and the user launches it again
- **THEN** the second launch SHALL detect the running instance and not start a duplicate

### Requirement: Game Mode hidden on macOS

Because the `PostMessage`/`WM_CHAR` typing path has no macOS equivalent, the Game Mode option SHALL be hidden or disabled on macOS, and normal typing into the active application SHALL use the cross-platform `pynput` path.

#### Scenario: Game Mode unavailable on macOS

- **WHEN** the user opens Settings on macOS
- **THEN** the Game Mode control SHALL not be offered (or is disabled), and transcription still types into the active app via `pynput`

### Requirement: macOS permissions guidance

The app SHALL detect or document the macOS permissions required for global hotkeys and typing (Accessibility and Input Monitoring) and guide the user to grant them when the corresponding feature does not work.

#### Scenario: Missing permission surfaced

- **WHEN** global hotkey or typing fails on macOS because permission was not granted
- **THEN** the app SHALL surface a message pointing the user to System Settings → Privacy & Security to grant Accessibility / Input Monitoring
