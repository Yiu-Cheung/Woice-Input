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

# UI settings
GRADIO_THEME = "soft"
SHARE_LINK = False  # Set True to create public Gradio link
