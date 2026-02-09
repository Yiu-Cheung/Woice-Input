## 1. Dependencies

- [ ] 1.1 Add `silero-vad-lite` to `requirements.txt`
- [ ] 1.2 Install `silero-vad-lite` in the virtual environment and verify import works

## 2. VAD Initialization

- [ ] 2.1 Import `SileroVAD` in `desktop_app.py` with try/except fallback
- [ ] 2.2 Create `SileroVAD(16000)` instance in `SimpleSTTApp.__init__` and store as `self.vad`
- [ ] 2.3 Add `self.vad_available` flag — `True` if VAD loaded, `False` on import/init failure

## 3. Settings

- [ ] 3.1 Add `vad_threshold` (default 0.5) to `_load_settings` defaults
- [ ] 3.2 Add VAD threshold slider (0.0-1.0) to `SettingsDialog`
- [ ] 3.3 Save and load `vad_threshold` in settings JSON

## 4. Continuous Mode VAD Integration

- [ ] 4.1 In `_continuous_loop`, replace amplitude check with Silero VAD: split each ~100ms buffer into 512-sample frames, call `vad.process()` per frame, use max probability as chunk score
- [ ] 4.2 Compare chunk score against `vad_threshold` instead of `silence_threshold`
- [ ] 4.3 If `self.vad_available` is `False`, fall back to original amplitude logic
- [ ] 4.4 Keep existing pause-detection, buffer-flush, and idle-timeout logic unchanged

## 5. Manual Recording VAD Integration

- [ ] 5.1 In `_record_audio`, replace amplitude-based idle detection with VAD probability check
- [ ] 5.2 If `self.vad_available` is `False`, fall back to original amplitude logic

## 6. Testing

- [ ] 6.1 Verify app starts and VAD initializes without errors
- [ ] 6.2 Test continuous mode: confirm speech is detected and noise is ignored
- [ ] 6.3 Test manual mode: confirm idle auto-stop works with VAD
- [ ] 6.4 Test fallback: simulate VAD unavailable and verify amplitude detection still works
- [ ] 6.5 Test settings: verify VAD threshold slider saves and applies correctly
