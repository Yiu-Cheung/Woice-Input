"""
Configuration settings for the speech-to-text application.
"""

# Whisper settings
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large
WHISPER_LANGUAGE = None  # Auto-detect by default (set to "en", "es", etc. to override)

# Ollama settings
OLLAMA_MODEL = "gemma3n:e4b"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_TIMEOUT = 30  # seconds

# Audio settings
TARGET_SAMPLE_RATE = 16000  # 16kHz required for optimal processing
MAX_AUDIO_LENGTH = 30  # seconds (recommended maximum)
AUDIO_FORMAT = "wav"

# Voice activity / capture tuning
VAD_FRAME_SAMPLES = 512  # Silero VAD frame size at 16kHz (~32ms)
PRE_ROLL_MS = 500  # Rolling pre-roll buffer length (ms) prepended on speech onset
VAD_EXIT_MARGIN = 0.15  # Hysteresis: exit threshold = vad_threshold - this margin
SHORT_UTTERANCE_FLOOR = 0.15  # Min voiced duration (s) to treat a segment as real speech
                              # (low because Silero VAD already rejects most noise;
                              #  keeps short 1-2 syllable words, e.g. Cantonese "12")

# Transcription resilience
SR_RETRY_COUNT = 2  # Extra attempts on transient Google SR RequestError (total = 1 + this)
SR_RETRY_BASE_BACKOFF = 0.5  # Base backoff (s); attempt N waits base * 2**(N-1)

# UI settings
GRADIO_THEME = "soft"
SHARE_LINK = False  # Set True to create public Gradio link
