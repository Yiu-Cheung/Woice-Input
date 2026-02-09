## Context

The app currently uses `np.max(np.abs(chunk)) >= silence_threshold` for voice detection in both continuous and manual recording modes. This amplitude-only approach has no ability to distinguish human speech from environmental noise (fans, typing, HVAC) at similar volume levels. Silero VAD is a neural-network-based voice activity detector (ROC-AUC 0.97) available via `silero-vad-lite` — a self-contained package (~6.6MB) that bundles the ONNX model and runtime with zero external dependencies.

## Goals / Non-Goals

**Goals:**
- Replace amplitude-based voice detection with Silero VAD in both continuous and manual recording modes
- Maintain existing pause-detection and idle-timeout logic unchanged
- Add a `vad_threshold` setting for user control
- Graceful fallback to amplitude detection if VAD fails to load

**Non-Goals:**
- Noise cancellation or audio enhancement (VAD only classifies, doesn't clean audio)
- Changing the transcription engine (Google SR stays)
- Modifying the audio processing pipeline in `audio_processor.py` (format already compatible)
- Real-time probability display or visualization

## Decisions

### 1. Use `silero-vad-lite` instead of raw `onnxruntime` + manual model
**Rationale**: `silero-vad-lite` bundles the ONNX model and C++ runtime internally — zero transitive dependencies, ~6.6MB total. Using raw `onnxruntime` would require separately downloading the model, managing hidden state tensors (h, c), and writing ~30-40 lines of inference wrapper code for no practical benefit.
**Alternative considered**: `onnxruntime` + manual ONNX model — more flexible but unnecessary complexity for our use case.

### 2. New `vad_threshold` setting instead of repurposing `silence_threshold`
**Rationale**: The two thresholds have fundamentally different semantics (amplitude 0.001-0.1 vs probability 0.0-1.0). Repurposing `silence_threshold` would break existing saved settings and confuse users. Instead, add `vad_threshold` (default 0.5) and keep `silence_threshold` for the `validate_audio_length` "audio is silent" check in `audio_processor.py`.
**Alternative considered**: Repurpose `silence_threshold` with auto-migration — rejected because the old and new scales are incompatible.

### 3. Process in 512-sample chunks within the existing loop timing
**Rationale**: Silero VAD requires exactly 512 samples (32ms at 16kHz) per call. The current `_continuous_loop` already accumulates audio in `audio_buffer` and processes every 100ms. Each 100ms cycle contains ~1600 samples = 3 full VAD frames. Process all frames per cycle and use the max probability as the chunk's speech score.
**Alternative considered**: Restructure the loop to 32ms ticks — rejected because it would increase CPU wake-ups 3x for marginal benefit.

### 4. VAD instance lifecycle: create once in `__init__`, reuse across sessions
**Rationale**: `SileroVAD(16000)` loads the ONNX model (~2MB). Creating it once and reusing avoids repeated model loading. The object maintains internal hidden state that resets naturally between recording sessions (the silence gap between sessions acts as a natural reset).
**Alternative considered**: Create per-session — rejected because model loading latency would add noticeable delay to each start.

### 5. Fallback to amplitude detection on VAD init failure
**Rationale**: If `silero-vad-lite` fails to import or initialize (e.g., unsupported platform), the app should still work with the old behavior rather than crash. Set a flag `self.vad_available` and branch in the detection logic.

## Risks / Trade-offs

- **[Risk] `silero-vad-lite` platform support**: The package provides wheels for Windows/Linux/macOS but may not cover all architectures. → **Mitigation**: Fallback to amplitude detection with a warning log.
- **[Risk] VAD hidden state drift**: Very long continuous sessions may accumulate state. → **Mitigation**: Silero's internal state is designed for streaming; no known issues. Monitor in practice.
- **[Trade-off] Settings UI change**: Adding `vad_threshold` means one more slider in the settings dialog. → Acceptable, keeps concerns separate.
- **[Trade-off] Package size +6.6MB**: Small increase. → Acceptable given the accuracy improvement (ROC-AUC 0.73 → 0.97).
