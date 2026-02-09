## 1. Dependencies

- [x] 1.1 Add `onnxruntime` to `requirements.txt` (switched from `silero-vad-lite` due to Python 3.14 incompatibility)
- [x] 1.2 Download `silero_vad.onnx` model to `models/` directory
- [x] 1.3 Install `onnxruntime` in the virtual environment and verify import works

## 2. VAD Wrapper

- [x] 2.1 Create `src/vad.py` with pure-numpy `SileroVAD` wrapper (no PyTorch dependency)
- [x] 2.2 Import `SileroVAD` in `desktop_app.py` with try/except fallback
- [x] 2.3 Create `SileroVAD()` instance in `SimpleSTTApp.__init__` and store as `self.vad`
- [x] 2.4 Add `self.vad_available` flag — `True` if VAD loaded, `False` on import/init failure
- [x] 2.5 Reset VAD hidden state at the start of each continuous recording session

## 3. Settings

- [x] 3.1 Add `vad_threshold` (default 0.5) to `_load_settings` defaults
- [x] 3.2 Add VAD threshold slider (0.0-1.0) to `SettingsDialog`
- [x] 3.3 Save and load `vad_threshold` in settings JSON

## 4. Continuous Mode VAD Integration

- [x] 4.1 Add `_check_voice_activity` helper: split chunk into 512-sample frames, call `vad.process()` per frame, use max probability as chunk score
- [x] 4.2 In `_continuous_loop`, replace amplitude check with `_check_voice_activity`
- [x] 4.3 If `self.vad_available` is `False`, fall back to original amplitude logic
- [x] 4.4 Keep existing pause-detection, buffer-flush, and idle-timeout logic unchanged

## 5. Manual Recording VAD Integration

- [x] 5.1 In `_record_audio`, replace amplitude-based idle detection with `_check_voice_activity`
- [x] 5.2 If `self.vad_available` is `False`, fall back to original amplitude logic

## 6. Testing

- [x] 6.1 Verify VAD initializes without errors (unit test with silence/noise/sine)
- [ ] 6.2 Test continuous mode: confirm speech is detected and noise is ignored
- [ ] 6.3 Test manual mode: confirm idle auto-stop works with VAD
- [ ] 6.4 Test fallback: simulate VAD unavailable and verify amplitude detection still works
- [ ] 6.5 Test settings: verify VAD threshold slider saves and applies correctly
