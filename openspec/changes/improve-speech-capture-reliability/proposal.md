## Why

Users report that speech is frequently "not captured" (收錄唔到): the **beginning of utterances is clipped**, **whole short words/sentences go missing**, and recording sometimes **cuts off mid-speech**. This happens in both manual (hotkey) and continuous modes. Root causes are structural, not tuning: (1) manual mode loses the first words to input-stream startup latency, (2) continuous mode has no pre-roll buffer so the soft onset of speech is discarded before VAD triggers, (3) VAD is fed non-contiguous, misaligned frames that degrade its accuracy, (4) a single VAD threshold with no hysteresis lets mid-utterance dips end capture early, (5) the short-utterance filter discards single-syllable words, and (6) the free Google Speech Recognition endpoint silently returns empty text on network/rate-limit errors.

## What Changes

- Introduce a **persistent, always-on input stream** with a fixed `blocksize` so audio is already flowing before the user starts speaking — eliminating manual-mode startup latency.
- Add a **pre-roll ring buffer** (~500ms) that is continuously filled and prepended to the captured audio when speech onset is detected — recovering the clipped start of utterances in both modes.
- Feed VAD **contiguous, sample-accurate 512-sample frames** (carry-over across chunk boundaries, no dropped samples) instead of per-chunk fragments, and feed the manual idle-detector the same stream instead of only the last callback block.
- Add **hysteresis** to segmentation: enter speech at `vad_threshold`, keep capturing until probability drops below a lower exit threshold — preventing mid-utterance cutoff.
- Refine short-utterance gating so genuine single-syllable words are kept (lower floor, based on actual voiced-frame count rather than the current `total - trailing-silence` heuristic).
- Make transcription resilient: **retry Google SR with backoff**, **surface failures** (network error / empty result) in the UI and overlay instead of dropping them silently, and provide an **optional offline Whisper fallback** when the network is unavailable.

## Capabilities

### New Capabilities
- `speech-capture`: Reliable audio capture and utterance segmentation — persistent always-on stream, pre-roll onset preservation, contiguous frame delivery to the voice detector, hysteresis-based start/stop, and short-utterance gating.
- `transcription-resilience`: Robust delivery of recognized text — retry/backoff on recognizer errors, user-visible failure feedback, and an optional offline fallback.

### Modified Capabilities
<!-- None. The existing `voice-activity-detection` capability (currently a delta in the in-progress `integrate-silero-vad` change) supplies the per-frame speech probability and is consumed unchanged. `speech-capture` layers segmentation/capture behavior on top of it. See Impact for the relationship. -->

## Impact

- **Code**: `src/desktop_app.py` (`_record_audio`, `_continuous_loop`, `_check_voice_activity`, stream lifecycle, `__init__`), `src/transcription.py` (`transcribe_with_google`, Whisper fallback path), `src/config.py` (new tuning constants), `SettingsDialog` (new exit-threshold / fallback controls).
- **Settings**: Adds `vad_exit_threshold` (hysteresis floor) and an optional `offline_fallback` toggle. Existing `vad_threshold` keeps its meaning as the speech-enter threshold; short-utterance floor becomes configurable. Saved settings migrate via defaults.
- **Dependencies**: No new packages required for Stage 1/2. Optional Whisper fallback uses the already-present `whisper`/`torch` path in `transcription.py`.
- **Relationship to `integrate-silero-vad`**: This change builds on that capability's per-frame VAD probability. `speech-capture` supersedes the segmentation requirements currently described in the `integrate-silero-vad` delta spec ("Continuous mode uses VAD for segmentation", "Manual recording mode uses VAD for idle detection"). That change should be synced/archived so the segmentation picture stays coherent; until then the two are read together.
- **Performance**: Always-on stream adds a small steady-state CPU/memory cost (one open stream + ~500ms ring buffer). VAD inference cost is unchanged.
