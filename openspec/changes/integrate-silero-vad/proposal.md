## Why

The current voice activity detection (VAD) in continuous mode uses a simple amplitude threshold to distinguish speech from silence. This causes frequent false positives in noisy environments (fans, keyboards, HVAC) and unreliable speech segmentation. Silero VAD (via `silero-vad-lite`) provides a neural-network-based VAD with ROC-AUC 0.97, drastically reducing noise misclassification with only ~6.6MB added and zero external dependencies.

## What Changes

- Replace amplitude-based voice detection in `_continuous_loop` with Silero VAD probability scoring
- Add `silero-vad-lite` package as a dependency
- Initialize Silero VAD model once at app startup, reuse across recording sessions
- Feed 512-sample (32ms) chunks to VAD instead of raw amplitude checks
- Keep the existing `silence_threshold` setting repurposed as the VAD probability threshold (0.0-1.0)
- Retain amplitude check in `validate_audio_length` for the "audio is silent" error (separate concern)

## Capabilities

### New Capabilities
- `voice-activity-detection`: Neural-network-based VAD using Silero to classify audio chunks as speech or noise, replacing amplitude-threshold detection

### Modified Capabilities

## Impact

- **Code**: `desktop_app.py` (`_continuous_loop`, `_record_audio`, `__init__`), `src/audio_processor.py` (minor, if VAD utility is added there)
- **Dependencies**: Add `silero-vad-lite` to `requirements.txt` (~6.6MB, bundles its own ONNX runtime, zero transitive deps)
- **Settings**: `silence_threshold` semantics change from amplitude (0.001-0.1) to VAD probability (0.0-1.0). Existing saved settings will need a migration default
- **Performance**: VAD inference <1ms per chunk on CPU — negligible overhead
