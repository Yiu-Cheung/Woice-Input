"""
Speech-to-Text Application using Whisper and Ollama
Main Gradio application interface
"""

import gradio as gr
import shutil
import ollama
from src.transcription import transcribe_audio, transcribe_audio_stream
from src.config import GRADIO_THEME, SHARE_LINK, OLLAMA_MODEL


def check_prerequisites():
    """
    Check if all required tools are available.
    Returns tuple: (success: bool, message: str)
    """
    messages = []

    # Check ffmpeg
    if not shutil.which("ffmpeg"):
        messages.append("❌ ffmpeg not found. Please install ffmpeg for audio processing.")

    # Check Ollama (optional for basic transcription)
    try:
        # Check if gemma3n:e4b model is available
        models = ollama.list()
        model_names = [m.model for m in models.models]
        if OLLAMA_MODEL not in model_names:
            messages.append(f"⚠ Warning: {OLLAMA_MODEL} model not found. Run: ollama pull {OLLAMA_MODEL}")
        else:
            messages.append(f"✓ Ollama is running with {OLLAMA_MODEL}")
    except Exception:
        messages.append("⚠ Warning: Ollama is not running. Transcription will work, but enhancement features will be unavailable.")

    if not messages:
        messages.append("✓ All prerequisites are met!")

    return len([m for m in messages if m.startswith("❌")]) == 0, "\n".join(messages)


def toggle_ollama_task(use_ollama):
    """
    Show/hide Ollama task dropdown based on checkbox.
    """
    return gr.update(visible=use_ollama)


# Create Gradio interface
def create_interface():
    """
    Create and configure the Gradio interface.
    """
    # Check prerequisites on startup
    prereq_success, prereq_message = check_prerequisites()

    with gr.Blocks(title="Speech-to-Text") as app:
        gr.Markdown("# 🎤 Speech-to-Text Application")
        gr.Markdown("Powered by OpenAI Whisper and Ollama gemma3n:e4b")

        # Display prerequisites status
        with gr.Accordion("System Status", open=not prereq_success):
            gr.Markdown(prereq_message)

        # Create tabs for different modes
        with gr.Tabs() as tabs:
            # Tab 1: Record & Transcribe mode
            with gr.Tab("🎙️ Record & Transcribe"):
                _create_record_mode()

            # Tab 2: Real-time Streaming mode
            with gr.Tab("⚡ Real-time Streaming"):
                _create_streaming_mode()

    return app


def _create_record_mode():
    """Create the record and transcribe interface."""
    with gr.Row():
        # Left column: Input controls
        with gr.Column():
            gr.Markdown("### 🎙️ Audio Input")

            audio_input = gr.Audio(
                sources=["microphone"],
                type="numpy",
                label="Record Audio"
            )

            language = gr.Dropdown(
                choices=[
                    ("Auto-detect", "auto"),
                    ("English", "en"),
                    ("Spanish", "es"),
                    ("French", "fr"),
                    ("German", "de"),
                    ("Chinese (Mandarin)", "zh"),
                    ("Cantonese", "yue"),
                    ("Japanese", "ja"),
                    ("Korean", "ko"),
                    ("Portuguese", "pt"),
                    ("Russian", "ru"),
                    ("Italian", "it")
                ],
                value="auto",
                label="Language"
            )

            gr.Markdown("### ⚙️ Enhancement Options (Optional)")

            use_ollama = gr.Checkbox(
                label="Enhance with Ollama",
                value=False,
                info="Use Ollama for post-processing (grammar, summary, translation)"
            )

            ollama_task = gr.Dropdown(
                choices=[
                    ("Improve Grammar & Punctuation", "improve"),
                    ("Summarize in Bullet Points", "summarize"),
                    ("Translate to Spanish", "translate")
                ],
                value="improve",
                label="Enhancement Task",
                visible=False
            )

            transcribe_btn = gr.Button(
                "🚀 Transcribe",
                variant="primary",
                size="lg"
            )

        # Right column: Output
        with gr.Column():
            gr.Markdown("### 📝 Transcription Result")

            output_text = gr.Textbox(
                label="Transcription",
                lines=10,
                placeholder="Your transcription will appear here...",
                interactive=False
            )

            status = gr.Textbox(
                label="Status",
                lines=4,
                placeholder="Status messages will appear here...",
                interactive=False
            )

    # Examples section
    with gr.Accordion("💡 Tips", open=False):
        gr.Markdown("""
        ### How to Use:
        1. **Click the microphone button** to start recording
        2. **Speak clearly** into your microphone
        3. **Click stop** when finished
        4. **Select language** (or leave as Auto-detect)
        5. **Optionally enable Ollama** for text enhancement
        6. **Click Transcribe** to process your audio

        ### Tips for Best Results:
        - Speak clearly and at a moderate pace
        - Minimize background noise
        - Keep recordings under 30 seconds for faster processing
        - For longer audio, the system will still process it but may take more time

        ### Ollama Enhancement:
        - **Improve**: Fixes grammar and punctuation
        - **Summarize**: Creates bullet-point summary
        - **Translate**: Translates to Spanish (can be customized)
        """)

    # Event handlers
    use_ollama.change(
        fn=toggle_ollama_task,
        inputs=[use_ollama],
        outputs=[ollama_task]
    )

    transcribe_btn.click(
        fn=transcribe_audio,
        inputs=[audio_input, language, use_ollama, ollama_task],
        outputs=[output_text, status]
    )


def _create_streaming_mode():
    """Create the real-time streaming interface."""
    gr.Markdown("### 🎤 Live Transcription")
    gr.Markdown("Speak and see the transcription appear in real-time!")

    with gr.Row():
        with gr.Column():
            stream_audio = gr.Audio(
                sources=["microphone"],
                type="numpy",
                label="Microphone (Live)",
                streaming=True
            )

            stream_language = gr.Dropdown(
                choices=[
                    ("Auto-detect", "auto"),
                    ("English", "en"),
                    ("Spanish", "es"),
                    ("French", "fr"),
                    ("German", "de"),
                    ("Chinese (Mandarin)", "zh"),
                    ("Cantonese", "yue"),
                    ("Japanese", "ja"),
                    ("Korean", "ko"),
                    ("Portuguese", "pt"),
                    ("Russian", "ru"),
                    ("Italian", "it")
                ],
                value="auto",
                label="Language"
            )

        with gr.Column():
            stream_output = gr.Textbox(
                label="Live Transcription",
                lines=15,
                placeholder="Start speaking and transcription will appear here...",
                interactive=False
            )

    # Wire up streaming
    stream_audio.stream(
        fn=transcribe_audio_stream,
        inputs=[stream_audio, stream_language],
        outputs=[stream_output]
    )

    with gr.Accordion("💡 Real-time Tips", open=False):
        gr.Markdown("""
        ### How Real-time Mode Works:
        - Click the microphone button to start live transcription
        - Speak naturally - transcription updates automatically
        - Click stop when finished
        - Best for continuous speech and live captions

        ### Performance Tips:
        - Shorter audio chunks = faster updates but may be less accurate
        - Use "English" instead of auto-detect for better real-time performance
        - Close other applications for smoother performance
        - Real-time mode doesn't support Ollama enhancement (use Record mode for that)
        """)


if __name__ == "__main__":
    app = create_interface()
    app.launch(share=SHARE_LINK, theme=GRADIO_THEME)
