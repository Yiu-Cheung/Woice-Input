"""
Audio preprocessing utilities for speech-to-text application.
Handles format conversion, resampling, normalization, and validation.
"""

import numpy as np
import soundfile as sf
from scipy import signal
import tempfile
import os
from .config import TARGET_SAMPLE_RATE, MAX_AUDIO_LENGTH


def convert_to_16khz_mono(audio_data, sample_rate):
    """
    Convert audio to 16kHz mono format.

    Args:
        audio_data: numpy array of audio samples
        sample_rate: original sample rate

    Returns:
        tuple: (converted_audio, new_sample_rate)
    """
    # Convert stereo to mono if needed
    if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
        # Average all channels
        audio_data = np.mean(audio_data, axis=1)

    # Resample if needed
    if sample_rate != TARGET_SAMPLE_RATE:
        # Calculate number of samples after resampling
        num_samples = int(len(audio_data) * TARGET_SAMPLE_RATE / sample_rate)
        # Use scipy.signal.resample for Fourier-based resampling
        audio_data = signal.resample(audio_data, num_samples)

    return audio_data, TARGET_SAMPLE_RATE


def normalize_audio(audio_data):
    """
    Normalize audio to float32 in range [-1, 1].

    Args:
        audio_data: numpy array of audio samples

    Returns:
        numpy array: normalized audio
    """
    # Convert to float32
    audio_data = audio_data.astype(np.float32)

    # Check if audio is silent (all zeros)
    if np.max(np.abs(audio_data)) == 0:
        return audio_data

    # Normalize to [-1, 1] range
    max_val = np.max(np.abs(audio_data))
    if max_val > 1.0:
        audio_data = audio_data / max_val

    return audio_data


def validate_audio_length(audio_data, sample_rate, max_seconds=MAX_AUDIO_LENGTH, min_seconds=0.1):
    """
    Validate audio length and return duration info.

    Args:
        audio_data: numpy array of audio samples
        sample_rate: sample rate of audio
        max_seconds: maximum recommended length
        min_seconds: minimum required length

    Returns:
        tuple: (duration_seconds, warning_message or None)

    Raises:
        ValueError: if audio is too short or empty
    """
    duration = len(audio_data) / sample_rate

    # Check minimum duration
    if duration < min_seconds:
        raise ValueError(f"Audio too short ({duration:.2f}s). Minimum {min_seconds}s required.")

    # Check if audio is essentially silent
    max_amplitude = np.max(np.abs(audio_data))
    if max_amplitude < 0.001:
        raise ValueError("Audio is silent or too quiet. Please speak louder.")

    if duration > max_seconds:
        warning = f"Warning: Audio is {duration:.1f}s. Recommended max is {max_seconds}s. Processing may be slow."
        return duration, warning

    return duration, None


def save_temp_audio(audio_data, sample_rate):
    """
    Save audio to a temporary WAV file.

    Args:
        audio_data: numpy array of audio samples
        sample_rate: sample rate of audio

    Returns:
        str: path to temporary WAV file
    """
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix='.wav',
        dir=tempfile.gettempdir()
    )
    temp_path = temp_file.name
    temp_file.close()

    # Write audio to file
    sf.write(temp_path, audio_data, sample_rate)

    return temp_path


def process_audio(audio_data, sample_rate):
    """
    Complete audio processing pipeline.

    Args:
        audio_data: numpy array of audio samples
        sample_rate: original sample rate

    Returns:
        tuple: (temp_file_path, duration, warning_message or None)
    """
    # Convert to 16kHz mono
    audio_data, new_sample_rate = convert_to_16khz_mono(audio_data, sample_rate)

    # Normalize audio
    audio_data = normalize_audio(audio_data)

    # Validate length
    duration, warning = validate_audio_length(audio_data, new_sample_rate)

    # Save to temporary file
    temp_path = save_temp_audio(audio_data, new_sample_rate)

    return temp_path, duration, warning
