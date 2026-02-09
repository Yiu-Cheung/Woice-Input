"""
Transcription module handling Whisper, Google Speech Recognition, and Ollama integration.
"""

import os
import speech_recognition as sr
from .audio_processor import process_audio


# Global variable to cache the Whisper model
_whisper_model = None


def load_whisper_model(model_name=None):
    """
    Load Whisper model (cached for performance).
    Uses NVIDIA GPU if available, falls back to CPU.

    Args:
        model_name: size of Whisper model (tiny, base, small, medium, large)

    Returns:
        Whisper model instance
    """
    import whisper
    from .config import WHISPER_MODEL

    if model_name is None:
        model_name = WHISPER_MODEL

    global _whisper_model

    if _whisper_model is None:
        import torch

        # Check if CUDA (NVIDIA GPU) is available
        device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"Loading Whisper model on {device.upper()}...")
        _whisper_model = whisper.load_model(model_name, device=device)

    return _whisper_model


def transcribe_with_whisper(audio_path, language=None):
    """
    Transcribe audio file using Whisper with GPU fallback to CPU.

    Args:
        audio_path: path to audio file
        language: language code (e.g., "en", "es") or None for auto-detect

    Returns:
        dict: {
            "text": transcribed text,
            "language": detected language
        }
    """
    try:
        model = load_whisper_model()

        # Map Cantonese to Chinese (Whisper uses 'zh' for all Chinese dialects)
        if language == "yue":
            language = "zh"

        # Transcribe with optional language parameter
        options = {}
        if language and language != "auto":
            options["language"] = language

        try:
            result = model.transcribe(audio_path, **options)
        except (RuntimeError, ValueError) as e:
            # GPU error detected (NaN values, CUDA errors, constraint violations)
            error_msg = str(e)
            if "nan" in error_msg.lower() or "cuda" in error_msg.lower() or "constraint" in error_msg.lower():
                # Reload model on CPU and retry
                import torch
                import whisper
                from .config import WHISPER_MODEL
                global _whisper_model
                print("⚠ GPU error detected (NaN/CUDA issue), falling back to CPU...")
                _whisper_model = whisper.load_model(WHISPER_MODEL, device="cpu")
                model = _whisper_model
                result = model.transcribe(audio_path, **options)
            else:
                raise

        return {
            "text": result["text"].strip(),
            "language": result.get("language", "unknown")
        }
    except Exception as e:
        raise Exception(f"Whisper transcription failed: {str(e)}")


def transcribe_with_google(audio_path, language=None):
    """
    Transcribe audio file using Google Speech Recognition.
    Better Cantonese support with language code 'yue-HK'.

    Args:
        audio_path: path to audio file
        language: language code (e.g., "en-US", "yue-HK") or None for auto-detect

    Returns:
        dict: {
            "text": transcribed text,
            "language": detected/specified language
        }
    """
    try:
        recognizer = sr.Recognizer()

        # Map language codes to Google SR format
        lang_map = {
            "yue": "yue-HK",  # Cantonese (Hong Kong)
            "zh": "zh-CN",    # Chinese (Mandarin)
            "en": "en-US",    # English
            "es": "es-ES",    # Spanish
            "fr": "fr-FR",    # French
            "de": "de-DE",    # German
            "ja": "ja-JP",    # Japanese
            "ko": "ko-KR",    # Korean
            "pt": "pt-PT",    # Portuguese
            "ru": "ru-RU",    # Russian
            "it": "it-IT"     # Italian
        }

        # Convert language code
        google_lang = lang_map.get(language, language) if language else None

        # Load audio file
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        # Transcribe using Google Speech Recognition
        try:
            if google_lang:
                text = recognizer.recognize_google(audio_data, language=google_lang)
            else:
                text = recognizer.recognize_google(audio_data)  # Auto-detect

            return {
                "text": text.strip(),
                "language": language if language else "auto"
            }
        except sr.UnknownValueError:
            return {
                "text": "",
                "language": language if language else "unknown"
            }
        except sr.RequestError as e:
            raise Exception(f"Google Speech Recognition service error: {str(e)}")

    except Exception as e:
        raise Exception(f"Google transcription failed: {str(e)}")


def process_with_ollama(text, task="improve"):
    """
    Process transcribed text using Ollama.

    Args:
        text: input text to process
        task: processing task type (improve, summarize, translate)

    Returns:
        str: processed text
    """
    # Build prompt based on task type
    prompts = {
        "improve": f"Fix grammar and punctuation in this text, keeping the original meaning. Only return the corrected text:\n\n{text}",
        "summarize": f"Summarize this text in bullet points:\n\n{text}",
        "translate": f"Translate this text to Spanish:\n\n{text}"
    }

    prompt = prompts.get(task, prompts["improve"])

    try:
        import ollama
        from .config import OLLAMA_MODEL, OLLAMA_TIMEOUT

        # Check if Ollama is accessible
        try:
            ollama.list()
        except Exception:
            raise Exception("Ollama is not running. Please start Ollama first.")

        # Generate response with timeout
        client = ollama.Client(timeout=OLLAMA_TIMEOUT)
        response = client.generate(
            model=OLLAMA_MODEL,
            prompt=prompt
        )

        return response["response"].strip()

    except Exception as e:
        if "Ollama is not running" in str(e):
            raise
        raise Exception(f"Ollama processing failed: {str(e)}")


def transcribe_audio_stream(audio_tuple, language="auto"):
    """
    Real-time streaming transcription function.

    Args:
        audio_tuple: tuple of (sample_rate, audio_data) from Gradio streaming
        language: language code or "auto" for detection

    Returns:
        str: transcription text (partial or complete)
    """
    try:
        # Validate input
        if audio_tuple is None or audio_tuple[1] is None:
            return ""

        sample_rate, audio_data = audio_tuple

        # Check if audio is empty
        if len(audio_data) == 0:
            return ""

        # Process audio
        temp_path, duration, _ = process_audio(audio_data, sample_rate)

        # Map language code (yue -> zh for Cantonese)
        lang = language if language != "auto" else None
        if lang == "yue":
            lang = "zh"

        # Transcribe with Whisper
        result = transcribe_with_whisper(temp_path, lang)

        # Clean up temporary file
        try:
            os.unlink(temp_path)
        except Exception:
            pass

        return result["text"]

    except Exception as e:
        return f"[Error: {str(e)}]"


def transcribe_audio(audio_tuple, language="auto", use_ollama=False, ollama_task="improve"):
    """
    Main transcription function orchestrating the complete pipeline.

    Args:
        audio_tuple: tuple of (sample_rate, audio_data) from Gradio
        language: language code or "auto" for detection
        use_ollama: whether to enhance with Ollama
        ollama_task: type of Ollama processing

    Returns:
        tuple: (transcription_text, status_message)
    """
    try:
        # Validate input
        if audio_tuple is None:
            return "", "Error: No audio recorded. Please record audio first."

        sample_rate, audio_data = audio_tuple

        # Check if audio is empty
        if len(audio_data) == 0:
            return "", "Error: Empty audio. Please record some audio."

        # Process audio
        status = "Processing audio..."
        temp_path, duration, warning = process_audio(audio_data, sample_rate)

        # Add warning to status if audio is too long
        if warning:
            status += f"\n{warning}"

        # Transcribe with Whisper
        status += "\nTranscribing with Whisper..."
        result = transcribe_with_whisper(
            temp_path,
            language=language if language != "auto" else None
        )

        transcription = result["text"]
        detected_lang = result["language"]

        # Clean up temporary file
        try:
            os.unlink(temp_path)
        except Exception:
            pass  # Ignore cleanup errors

        # Enhance with Ollama if requested
        if use_ollama and transcription:
            status += "\nEnhancing with Ollama..."
            try:
                transcription = process_with_ollama(transcription, ollama_task)
                status += f"\n✓ Complete! (Language: {detected_lang}, Enhanced with Ollama)"
            except Exception as e:
                status += f"\n✓ Transcription complete (Language: {detected_lang})"
                status += f"\n⚠ Ollama enhancement failed: {str(e)}"
        else:
            status += f"\n✓ Complete! (Language: {detected_lang})"

        return transcription, status

    except Exception as e:
        return "", f"Error: {str(e)}"
