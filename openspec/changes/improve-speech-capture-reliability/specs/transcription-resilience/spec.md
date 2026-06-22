## ADDED Requirements

### Requirement: Retry recognizer requests with backoff

The system SHALL retry transient Google Speech Recognition request failures (`RequestError`) with a bounded number of attempts and increasing backoff before giving up. `UnknownValueError` (genuine no-speech) SHALL NOT be retried.

#### Scenario: Transient network error retried

- **WHEN** a Google SR request fails with a `RequestError`
- **THEN** the system SHALL retry up to a bounded number of attempts with increasing delay
- **AND** a successful retry returns the recognized text

#### Scenario: No-speech result not retried

- **WHEN** Google SR raises `UnknownValueError`
- **THEN** the system SHALL NOT retry
- **AND** it returns an empty result for that segment

### Requirement: Surface transcription failures to the user

The system SHALL make transcription failures visible instead of silently dropping audio. When a segment fails after retries, or the recognizer returns empty for audio that contained detected speech, the UI status and overlay SHALL indicate that the segment was not transcribed.

#### Scenario: Network failure shown in status

- **WHEN** transcription fails after exhausting retries
- **THEN** the status bar SHALL show a transcription-failed message
- **AND** the captured audio is not silently discarded without notice

#### Scenario: Empty result on detected speech is flagged

- **WHEN** a segment that the voice detector classified as speech returns empty text
- **THEN** the system SHALL log the event and indicate a missed transcription rather than appearing as normal silence

### Requirement: Optional offline transcription fallback

The system SHALL provide an optional offline fallback using the local Whisper path when the online recognizer is unavailable (e.g. no network or repeated `RequestError`). The fallback SHALL be controlled by a setting and SHALL be disabled by default to preserve current behavior.

#### Scenario: Fallback used when online unavailable

- **WHEN** the offline fallback setting is enabled
- **AND** the online recognizer fails after retries
- **THEN** the system SHALL transcribe the segment with the local Whisper model

#### Scenario: Fallback disabled by default

- **WHEN** the offline fallback setting is not enabled
- **AND** the online recognizer fails after retries
- **THEN** the system SHALL report the failure and SHALL NOT invoke the local model
