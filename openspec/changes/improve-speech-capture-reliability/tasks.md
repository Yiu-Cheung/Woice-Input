## 1. Stage 1 — Settings & config

- [x] 1.1 Add tuning constants to `src/config.py`: pre-roll window (default 500ms), VAD exit-threshold margin (default 0.15), short-utterance floor (default 0.3s), SR retry count + base backoff
- [x] 1.2 Add `vad_exit_threshold`, `short_utterance_floor`, and `offline_fallback` (default False) to `_load_settings` defaults in `desktop_app.py`
- [x] 1.3 Add a `vad_exit_threshold` slider to `SettingsDialog` and clamp it `<= vad_threshold` on save
- [x] 1.4 Add an "Offline fallback (Whisper)" checkbox to `SettingsDialog`; save/load all new keys in settings JSON

## 2. Stage 1 — Hysteresis segmentation

- [x] 2.1 Change `_check_voice_activity` to return the chunk's max VAD probability (or expose both prob and boolean) so the loop can apply enter/exit logic
- [x] 2.2 Track a `capturing` state in `_continuous_loop`: enter when prob `>= vad_threshold`, stay until prob `< vad_exit_threshold`
- [x] 2.3 Drive silence/pause timing off the exit threshold instead of the single threshold; keep `pause_threshold` segmentation downstream unchanged
- [x] 2.4 Verify a brief mid-utterance dip (between exit and enter) does not end capture (automated: hysteresis rule test)

## 3. Stage 1 — Short-utterance gating

- [x] 3.1 Count frames classified as speech (prob `>= vad_threshold`) per segment in `_continuous_loop`
- [x] 3.2 Replace the `voice_duration < 0.5` check (and the flush check) with `voiced_frames * frame_duration < short_utterance_floor`
- [x] 3.3 Verify a ~0.3s single-syllable word is sent for transcription; a transient spike below the floor is still dropped (automated: voiced-gating test)

## 4. Stage 1 — Transcription resilience

- [x] 4.1 Wrap Google SR in `transcription.py` with bounded retry + increasing backoff on `RequestError`; never retry `UnknownValueError`
- [x] 4.2 Return a structured result distinguishing "no speech" (empty) from "failed after retries"
- [x] 4.3 In `_process_continuous_chunk` / `_process_audio`, surface "failed" and "empty-on-detected-speech" to the status bar and overlay (not a silent drop)
- [x] 4.4 Implement opt-in offline fallback: when `offline_fallback` is on and online fails after retries, transcribe the segment via `transcribe_with_whisper`; when off, report failure and skip the model
- [x] 4.5 Verify fallback off by default reproduces current behavior (automated: `_transcribe` passthrough test)

## 5. Stage 2 — Persistent always-on input stream

- [x] 5.1 Open a single `sd.InputStream` at app start (or first session) with explicit `blocksize=512` (or supported multiple); store on the app instance
- [x] 5.2 Keep the stream open across session start/stop; route start/stop to consume from the shared buffer rather than opening/closing the stream
- [x] 5.3 Add open-failure handling: fall back to a supported block size, then host-default; log and surface to status
- [x] 5.4 Update tray/UI to reflect that the mic stream is active; close the stream cleanly in `on_closing`
- [x] 5.5 Add explicit start/stop sound cue (`sound_cues`, default on; high beep start / low beep stop via `winsound`) to replace the device-activation chime lost to the always-on stream; add Settings toggle

## 6. Stage 2 — Pre-roll ring buffer + onset preservation

- [x] 6.1 Add a fixed-capacity pre-roll `deque` (>= 500ms) filled by the stream callback at all times
- [x] 6.2 On continuous-mode speech onset, prepend a pre-roll snapshot to the captured segment
- [x] 6.3 On manual record start, prepend the pre-roll snapshot so audio around the hotkey press is retained
- [x] 6.4 Use snapshot-and-clear semantics to prevent double-counting audio at the boundary

## 7. Stage 2 — Contiguous frame delivery

- [x] 7.1 Maintain a leftover-sample carry buffer so VAD only ever receives whole, contiguous 512-sample frames (no dropped tail)
- [x] 7.2 Feed the manual idle detector the same contiguous frame stream instead of `self.audio_data[-1]`
- [x] 7.3 Verify every captured sample is evaluated by VAD exactly once and streaming state stays coherent across iterations (automated: carry-over framing test)

## 8. Verification

- [ ] 8.1 (LIVE-MIC) Continuous mode: first syllable of an utterance is present after a silence (onset recovered)
- [ ] 8.2 (LIVE-MIC) Manual mode: speaking immediately after the hotkey is not clipped (no startup latency loss)
- [ ] 8.3 (LIVE-MIC) Mid-utterance amplitude dips do not end capture; utterance ends only after real pause
- [ ] 8.4 (LIVE-MIC) Single-syllable words captured; fan/keyboard noise still rejected
- [x] 8.5 Simulated network failure shows a status/overlay message (automated); offline fallback (when enabled) produces a transcript — code-complete, needs live Whisper model to exercise end-to-end
- [x] 8.6 Validate specs apply cleanly via `openspec validate improve-speech-capture-reliability` (`sync` is not available in this CLI; specs apply at archive time)
