## Context

The desktop app (`src/desktop_app.py`) supports two recording modes that share one weakness: audio is lost before it can be transcribed. Today each session opens its own `sd.InputStream` on demand, with no `blocksize` specified (host picks a variable size). Manual mode (`_record_audio`) appends every callback block but only opens the stream after the hotkey thread starts — so words spoken in the opening moment are gone. Continuous mode (`_continuous_loop`) gates capture on `_check_voice_activity`: chunks classified as non-speech while `is_speaking` is `False` are discarded, so the soft attack of an utterance is dropped before the VAD crosses its single 0.5 threshold. `_check_voice_activity` itself slices a chunk into 512-sample frames with `range(0, len-511, 512)`, dropping the trailing <512 samples each call and corrupting the streaming VAD state; the manual idle check feeds VAD only `self.audio_data[-1]` (one variable-size block, often <512 samples → zero frames → always "silence"). Finally, `transcribe_with_google` uses the free Google Web Speech endpoint with no retry; `UnknownValueError` and `RequestError` both collapse to empty/raised with no user feedback.

This change is delivered in two stages so low-risk tuning lands before the threading refactor. It builds on the per-frame VAD probability defined by the `voice-activity-detection` capability (currently a delta in the in-progress `integrate-silero-vad` change) and consumes it unchanged.

## Goals / Non-Goals

**Goals:**
- Eliminate onset clipping in both modes (pre-roll buffer + always-on stream).
- Stop mid-utterance cutoff via hysteresis.
- Feed VAD a correct, contiguous frame stream so its accuracy is not degraded by our plumbing.
- Keep genuine short words; still reject transient noise.
- Make transcription failures visible and optionally recoverable offline.
- Land Stage 1 (tuning) independently of Stage 2 (architecture) so each is shippable and revertible on its own.

**Non-Goals:**
- Replacing Google SR as the primary recognizer, or adding a new cloud provider.
- Changing the Silero VAD model, its 512-sample frame size, or its probability semantics.
- Reworking the Gradio web app (`web_app.py`) or the overlay rendering.
- Speaker diarization, partial/streaming transcripts, or punctuation restoration.

## Decisions

### Decision 1: Two-stage delivery (tuning, then architecture)
**Stage 1 (low risk, local edits):** hysteresis (`vad_exit_threshold`), short-utterance floor based on voiced-frame count, Google SR retry/backoff + failure surfacing. **Stage 2 (architecture):** persistent always-on stream with fixed `blocksize=512`, pre-roll ring buffer, contiguous frame feeding shared by both modes.
**Why:** Stage 1 addresses "mid-utterance cutoff", "short words", and "silent empty results" with small, easily-reverted function-level changes. Stage 2 addresses the structural "食開頭" in both modes but touches the threading/stream lifecycle and carries more risk. Separating them gives early relief and a clean rollback boundary.
**Alternative considered:** ship everything at once — rejected: larger blast radius, harder to bisect if capture regresses.

### Decision 2: Persistent stream + pre-roll ring buffer as the capture core
A single `sd.InputStream` opens at app start (or first use) and stays open. Its callback always pushes blocks into a fixed-capacity `collections.deque` (the pre-roll, sized to ≥500ms = 8000 samples). Sessions read from this shared buffer; on speech onset the deque snapshot is prepended to the captured audio.
**Why:** one mechanism fixes onset loss in *both* modes — manual no longer waits for stream open, continuous recovers pre-trigger audio. A ring buffer is the standard VAD "lookback/speech_pad" technique.
**Alternative considered:** open stream eagerly but keep per-mode logic separate — rejected: duplicates buffering and leaves continuous-mode onset loss unsolved.
**Side effect:** opening/closing a stream per session previously triggered the Windows device-activation chime on each start/stop. With one always-open stream that chime now fires only once at launch. To preserve audible start/stop feedback we add an explicit cue (`sound_cues`, default on): a short high beep on start, low beep on stop via `winsound` (Windows only, run off-thread).

### Decision 3: Fixed `blocksize=512` + sample-accurate carry-over
Open the stream with `blocksize=512` (or a multiple) and maintain a leftover-sample carry buffer so VAD always receives whole, contiguous 512-frames with nothing dropped.
**Why:** removes the dropped-tail-samples bug and the variable-block-size bug (manual idle check returning constant "silence"), and keeps Silero's streaming hidden state coherent.
**Alternative considered:** keep variable blocks and pad/truncate per call — rejected: padding injects artifacts and still breaks state continuity.

### Decision 4: Hysteresis state machine over single threshold
Consume the VAD probability through an enter/exit pair: start at `vad_threshold`, end below `vad_exit_threshold` (default `vad_threshold − 0.15`, clamped ≥ 0). This replaces the single `>= threshold` decision that drives `is_speaking`/silence timing.
**Why:** natural speech amplitude fluctuates; one threshold makes capture flap and ends utterances early. Hysteresis is exactly how Silero's own `VADIterator` (threshold/neg_threshold) behaves.
**Alternative considered:** just lower the single threshold — rejected: trades mid-utterance cutoff for more noise false-positives in the user's fan/keyboard environment.

### Decision 5: Voiced-frame count for short-utterance gating
Track how many frames exceeded the enter threshold during a segment; gate on that count × frame-duration against a configurable floor, instead of `total_duration − trailing_silence`.
**Why:** the current heuristic counts mid-speech pauses as "voice" and discards genuine single-syllable words (common in Cantonese). A direct voiced-frame count is both more permissive for real short words and stricter for transient spikes.

**Tuned defaults (after live testing):** `vad_threshold` 0.4, `vad_exit_threshold` 0.25, `short_utterance_floor` 0.15s. Lowered from the initial 0.5 / 0.35 / 0.3 because Silero VAD already rejects most noise, so a low floor reliably keeps short 1–2 syllable Cantonese words (e.g. "12") without readmitting noise in the user's quiet-with-fan environment. All three remain user-adjustable in Settings.

### Decision 6: Transcription resilience as a thin wrapper
Wrap `transcribe_with_google`: retry only `RequestError` with bounded attempts + increasing backoff; never retry `UnknownValueError`. Return a structured result distinguishing "no speech" from "failed". Surface "failed"/"empty-on-detected-speech" to status + overlay. Offline fallback reuses the existing `transcribe_with_whisper` path, gated by an opt-in `offline_fallback` setting (default off).
**Why:** isolates network policy from capture logic; reuses code already present; preserves current default behavior unless the user opts in.

## Risks / Trade-offs

- **Always-on stream holds the mic open continuously** → some users expect the mic only active while recording (privacy/indicator light). Mitigation: tray/UI indicator reflects stream state; consider a setting to open lazily on first session and close on app idle.
- **Fixed `blocksize=512` rejected by some host APIs / sample-rate mismatch** → stream open could fail. Mitigation: fall back to a supported multiple of 512, else to host-default with the carry-over buffer still handling alignment; log and surface.
- **Pre-roll prepend could double-count audio** if onset detection overlaps the buffer window → duplicated/garbled start. Mitigation: snapshot-and-clear semantics; cover with the onset scenarios in the spec.
- **Hysteresis exit threshold too low in noisy rooms** → utterances run together / noise tail captured. Mitigation: default `−0.15`, expose control, keep pause-threshold segmentation downstream.
- **Offline Whisper fallback is slow on CPU** → latency spikes when network drops. Mitigation: off by default; document the trade-off; only triggers after online retries fail.
- **Threading refactor (Stage 2) regresses capture** → Mitigation: Stage 1 ships first; Stage 2 behind the same settings so it can be validated against the manual-test scenarios before archiving.

## Migration Plan

1. Ship Stage 1 (additive settings `vad_exit_threshold`, configurable short-utterance floor, SR retry/feedback). Saved settings gain defaults via the existing `_load_settings` merge; no user action needed.
2. Validate Stage 1 against the segmentation/short-word scenarios.
3. Ship Stage 2 (persistent stream + pre-roll + contiguous frames). Reuse the same settings.
4. Rollback: Stage 2 reverts to on-demand stream open without affecting Stage 1 tuning; Stage 1 reverts per-function.

## Open Questions

- Should the always-on stream close after a configurable idle period to release the mic, or stay open for the app lifetime?
- Default pre-roll window: is 500ms enough for the slowest onset, or should it be user-tunable (e.g. 300–800ms)?
- Should `integrate-silero-vad` be archived/synced before this change implements, so `voice-activity-detection` lives in main specs and `speech-capture` references it cleanly?
