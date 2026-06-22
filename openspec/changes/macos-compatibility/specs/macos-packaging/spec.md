## ADDED Requirements

### Requirement: macOS app bundle build

The project SHALL provide a PyInstaller-based build that produces a macOS `.app` bundle, built on a Mac (cross-compilation from Windows is not supported). The build SHALL bundle the Silero VAD model and onnxruntime, mirroring the Windows spec's collected data/binaries.

#### Scenario: Build produces a runnable .app

- **WHEN** the macOS build script is run on a Mac
- **THEN** it produces a `.app` that launches and initializes VAD, audio capture, tray, and hotkeys

#### Scenario: Bundled resources resolve in the bundle

- **WHEN** the packaged `.app` runs
- **THEN** the VAD model and `settings.json` resolve to stable paths within/next to the bundle regardless of the launch working directory

### Requirement: Dual-architecture coverage

The build process SHALL document and support producing apps that run on both Intel and Apple Silicon. The default supported path SHALL be explicit: either (a) a single x86_64 build that runs natively on Intel and under Rosetta 2 on Apple Silicon, or (b) two arch-native builds (x86_64 and arm64). A universal2 single binary is NOT required (onnxruntime has no universal2 wheel).

#### Scenario: Runs on both architectures

- **WHEN** the chosen build strategy is followed
- **THEN** the resulting app(s) run on both Intel and Apple Silicon Macs, and the README/docs state which strategy was used and any Rosetta 2 requirement

#### Scenario: Architecture strategy documented

- **WHEN** a maintainer reads the build docs
- **THEN** the docs SHALL state how to build for each architecture and the trade-offs (native vs Rosetta)

### Requirement: Code signing and notarization

For distribution outside the developer's own machine, the `.app` SHALL be code-signed with an Apple Developer ID and notarized so macOS Gatekeeper allows it to open without security warnings. The process SHALL be documented; an unsigned build MAY be used for local testing only.

#### Scenario: Signed and notarized app opens cleanly

- **WHEN** a signed + notarized build is distributed and opened on another Mac
- **THEN** Gatekeeper SHALL allow it to launch without "unidentified developer" / "damaged" warnings

#### Scenario: Unsigned build is local-only

- **WHEN** an unsigned build is produced
- **THEN** the docs SHALL note it is for local testing and will trigger Gatekeeper warnings if distributed
