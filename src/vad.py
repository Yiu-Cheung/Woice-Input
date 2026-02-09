"""
Silero VAD wrapper using ONNX Runtime (no PyTorch dependency).
Provides voice activity detection by running the Silero VAD model directly.
"""

import numpy as np
import os


class SileroVAD:
    """Pure-numpy wrapper for Silero VAD ONNX model."""

    def __init__(self, model_path=None):
        import onnxruntime

        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "models", "silero_vad.onnx"
            )

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Silero VAD model not found at {model_path}")

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1

        self.session = onnxruntime.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider'],
            sess_options=opts
        )

        self.sample_rate = 16000
        self._context_size = 64  # 64 samples context for 16kHz
        self._num_samples = 512  # 512 samples per frame for 16kHz
        self.reset_states()

    def reset_states(self):
        """Reset hidden state and context for a new audio stream."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._context_size), dtype=np.float32)

    def process(self, audio_chunk):
        """Process a 512-sample audio chunk and return speech probability.

        Args:
            audio_chunk: numpy float32 array of 512 samples, normalized to [-1, 1]

        Returns:
            float: speech probability between 0.0 and 1.0
        """
        if len(audio_chunk) != self._num_samples:
            raise ValueError(
                f"Expected {self._num_samples} samples, got {len(audio_chunk)}"
            )

        # Ensure float32 and correct shape: (1, 512)
        x = audio_chunk.astype(np.float32).reshape(1, -1)

        # Prepend context: (1, 64 + 512) = (1, 576)
        x = np.concatenate([self._context, x], axis=1)

        # Run inference
        ort_inputs = {
            'input': x,
            'state': self._state,
            'sr': np.array(self.sample_rate, dtype=np.int64)
        }
        out, new_state = self.session.run(None, ort_inputs)

        # Update state and context for next call
        self._state = new_state
        self._context = x[:, -self._context_size:]

        # out shape is (1, 1) — extract scalar probability
        return float(out.squeeze())
