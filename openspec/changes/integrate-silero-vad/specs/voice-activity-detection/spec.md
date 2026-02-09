## ADDED Requirements

### Requirement: VAD model initialization
The system SHALL initialize a Silero VAD instance (via `silero-vad-lite`) once at application startup with a 16000 Hz sample rate and reuse it across all recording sessions.

#### Scenario: App starts successfully
- **WHEN** the application starts
- **THEN** a `SileroVAD(16000)` instance is created and stored for reuse

#### Scenario: VAD initialization failure
- **WHEN** the VAD model fails to load
- **THEN** the system SHALL log the error and fall back to amplitude-based detection

### Requirement: Speech classification per chunk
The system SHALL feed each 512-sample (32ms) audio chunk to the Silero VAD model and receive a speech probability between 0.0 and 1.0. A chunk is classified as speech when the probability exceeds the configured VAD threshold.

#### Scenario: Speech detected
- **WHEN** a 512-sample chunk is processed by the VAD
- **AND** the returned probability is >= the VAD threshold (default 0.5)
- **THEN** the chunk SHALL be classified as speech

#### Scenario: Noise detected
- **WHEN** a 512-sample chunk is processed by the VAD
- **AND** the returned probability is < the VAD threshold
- **THEN** the chunk SHALL be classified as noise/silence

#### Scenario: Audio format compatibility
- **WHEN** audio is captured from the microphone
- **THEN** it SHALL be 16kHz, mono, float32 normalized to [-1, 1] before being passed to the VAD — matching the existing audio pipeline format

### Requirement: Continuous mode uses VAD for segmentation
The `_continuous_loop` SHALL use Silero VAD instead of amplitude comparison to determine voice activity. The pause detection logic (silence duration >= pause threshold triggers processing) SHALL remain unchanged — only the per-chunk speech/noise decision changes.

#### Scenario: Continuous mode speech segmentation
- **WHEN** continuous mode is active
- **AND** consecutive chunks are classified as speech followed by enough silence chunks to exceed `pause_threshold`
- **THEN** the accumulated speech audio SHALL be sent for transcription

#### Scenario: Short noise burst ignored
- **WHEN** a brief noise spike (< 0.5s of voice-duration equivalent) is detected
- **THEN** it SHALL be discarded as noise, not sent to transcription

### Requirement: VAD threshold setting
The system SHALL provide a `vad_threshold` setting (0.0-1.0, default 0.5) controlling the speech probability cutoff. This is a new setting separate from the legacy `silence_threshold`.

#### Scenario: User configures VAD threshold in settings
- **WHEN** the user opens Settings
- **THEN** a "VAD threshold" control SHALL be available with range 0.0-1.0

#### Scenario: Lower threshold increases sensitivity
- **WHEN** `vad_threshold` is set to 0.3
- **THEN** quieter speech is more likely to be detected, but more noise may pass through

### Requirement: Manual recording mode uses VAD for idle detection
The `_record_audio` method SHALL use Silero VAD instead of amplitude to detect idle silence for auto-stop. The idle timeout logic remains the same — only the silence detection method changes.

#### Scenario: Manual recording idle auto-stop with VAD
- **WHEN** manual recording is active with idle timeout enabled
- **AND** the VAD classifies all chunks as non-speech for `idle_timeout` seconds
- **THEN** recording SHALL auto-stop and process the captured audio
