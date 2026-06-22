## ADDED Requirements

### Requirement: Persistent always-on input stream

The system SHALL keep a single microphone input stream open and flowing while the application is active, independent of whether a recording session is in progress. Pressing the hotkey or starting continuous mode SHALL begin consuming already-flowing audio rather than opening a new stream. The stream SHALL be opened with an explicit fixed `blocksize` aligned to the VAD frame size (512 samples).

#### Scenario: No startup latency on manual record

- **WHEN** the user presses the record hotkey
- **THEN** audio capture begins from the already-open stream within one block period
- **AND** no `InputStream` open call occurs on the hotkey path

#### Scenario: Fixed block size for frame alignment

- **WHEN** the input stream is opened
- **THEN** it SHALL request a `blocksize` that is a multiple of 512 samples at 16kHz
- **AND** each callback delivers a deterministic number of samples (not a host-chosen variable size)

#### Scenario: Stream survives session boundaries

- **WHEN** a manual or continuous session stops
- **THEN** the input stream SHALL remain open and continue filling the pre-roll buffer
- **AND** a subsequent session reuses the same stream

### Requirement: Pre-roll onset preservation

The system SHALL maintain a rolling pre-roll buffer holding at least the most recent 500ms of captured audio. When speech onset is detected (manual start, or continuous-mode voice trigger), the contents of the pre-roll buffer SHALL be prepended to the captured audio so the soft attack of the first word is not lost.

#### Scenario: Continuous-mode onset recovered

- **WHEN** continuous mode detects speech after a period of silence
- **THEN** the audio sent for segmentation SHALL include the pre-roll buffer captured before the VAD trigger fired
- **AND** the first syllable of the utterance is present in the captured audio

#### Scenario: Manual-mode onset recovered

- **WHEN** the user presses the record hotkey and begins speaking immediately
- **THEN** the captured audio SHALL include the pre-roll buffer preceding the hotkey press
- **AND** words spoken in the moment around the hotkey press are not clipped

#### Scenario: Pre-roll bounded in size

- **WHEN** no speech is occurring
- **THEN** the pre-roll buffer SHALL discard audio older than its configured window and not grow unbounded

### Requirement: Contiguous frame delivery to the voice detector

The system SHALL feed the voice detector contiguous, sample-accurate 512-sample frames. Samples that do not fill a complete 512-sample frame SHALL be carried over to the next batch rather than discarded, so no audio is dropped between processing iterations and the streaming VAD state is not corrupted.

#### Scenario: No dropped tail samples

- **WHEN** an accumulated audio batch is not an exact multiple of 512 samples
- **THEN** the remainder SHALL be retained and prepended to the next batch
- **AND** every captured sample is eventually evaluated by the voice detector exactly once

#### Scenario: Manual idle detection uses the same contiguous stream

- **WHEN** manual recording idle auto-stop is active
- **THEN** the idle detector SHALL evaluate the continuous frame stream
- **AND** it SHALL NOT base its decision solely on the most recent single callback block

### Requirement: Hysteresis-based segmentation

The system SHALL use two thresholds for speech segmentation: speech capture starts when the VAD probability rises to or above `vad_threshold` (enter), and continues until the probability falls below a lower `vad_exit_threshold` (exit). The exit threshold SHALL default to a value below the enter threshold (e.g. `vad_threshold - 0.15`).

#### Scenario: Mid-utterance dip does not end capture

- **WHEN** capture is active and the VAD probability briefly dips below `vad_threshold` but stays at or above `vad_exit_threshold`
- **THEN** capture SHALL continue without ending the utterance

#### Scenario: Capture ends only below exit threshold

- **WHEN** capture is active and the VAD probability falls below `vad_exit_threshold`
- **THEN** the chunk SHALL be treated as silence for pause-timing purposes

#### Scenario: Exit threshold configurable and bounded

- **WHEN** the user views settings
- **THEN** a `vad_exit_threshold` control SHALL be available
- **AND** the system SHALL keep `vad_exit_threshold` less than or equal to `vad_threshold`

### Requirement: Short-utterance gating preserves genuine speech

The system SHALL decide whether a captured segment is real speech using the count of frames the voice detector classified as speech, not the `total_duration - trailing_silence` heuristic. The minimum voiced-duration floor SHALL be configurable and default low enough (≤ 0.3s) to retain single-syllable words.

#### Scenario: Single-syllable word retained

- **WHEN** the user speaks a short single-syllable word (e.g. ~0.3s of voiced audio)
- **THEN** the segment SHALL be sent for transcription, not discarded as noise

#### Scenario: Brief noise spike still rejected

- **WHEN** a transient noise burst produces fewer voiced frames than the configured floor
- **THEN** the segment SHALL be discarded as noise
