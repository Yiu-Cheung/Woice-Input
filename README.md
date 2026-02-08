# Speech-to-Text Application

A simple, powerful speech-to-text application powered by OpenAI Whisper and Ollama's gemma3n:e4b model.

## Features

- 🎤 **Microphone Recording**: Record audio directly from your browser
- 🌍 **Multi-language Support**: Auto-detect or manually select from 10+ languages
- 🤖 **AI Enhancement**: Optional post-processing with Ollama for grammar correction, summarization, and translation
- ⚡ **Fast Processing**: Optimized audio preprocessing pipeline
- 🎨 **Simple UI**: Clean, intuitive Gradio interface

## Prerequisites

Before running the application, ensure you have the following installed:

1. **Python 3.9+**
   ```bash
   python --version
   ```

2. **ffmpeg** (required for audio processing)
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or install via Chocolatey:
     ```bash
     choco install ffmpeg
     ```
   - **macOS**: Install via Homebrew:
     ```bash
     brew install ffmpeg
     ```
   - **Linux**: Install via package manager:
     ```bash
     sudo apt install ffmpeg  # Ubuntu/Debian
     sudo yum install ffmpeg  # CentOS/RHEL
     ```

3. **Ollama** (optional, for enhancement features)
   - Download and install from [ollama.ai](https://ollama.ai)
   - Pull the gemma3n:e4b model:
     ```bash
     ollama pull gemma3n:e4b
     ```

## Installation

1. **Clone or download this repository**

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   > **Note**: The first time you run the application, Whisper will download the base model (~140MB). This is a one-time download.

## Usage

1. **Start Ollama** (if you want enhancement features)
   ```bash
   ollama serve
   ```

2. **Run the application**
   ```bash
   python app.py
   ```

3. **Open your browser**
   - The application will automatically open at `http://127.0.0.1:7860`
   - If it doesn't open automatically, navigate to the URL shown in the terminal

4. **Record and transcribe**
   - Click the microphone button to start recording
   - Speak clearly into your microphone
   - Click stop when finished
   - Select your language (or use auto-detect)
   - Optionally enable Ollama enhancement
   - Click "Transcribe" to process

## Configuration

You can customize the application by editing `src/config.py`:

```python
# Whisper settings
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large

# Ollama settings
OLLAMA_MODEL = "gemma3n:e4b"
OLLAMA_TIMEOUT = 30

# Audio settings
TARGET_SAMPLE_RATE = 16000
MAX_AUDIO_LENGTH = 30  # seconds

# UI settings
SHARE_LINK = False  # Set True to create a public Gradio link
```

### Whisper Model Sizes

| Model  | Size   | Speed     | Accuracy |
|--------|--------|-----------|----------|
| tiny   | ~39MB  | Fastest   | Good     |
| base   | ~74MB  | Fast      | Better   |
| small  | ~244MB | Moderate  | Great    |
| medium | ~769MB | Slow      | Excellent|
| large  | ~1.5GB | Slowest   | Best     |

## Enhancement Features

When Ollama is enabled, you can enhance your transcriptions:

- **Improve Grammar & Punctuation**: Automatically fixes grammatical errors and adds proper punctuation
- **Summarize in Bullet Points**: Creates a concise bullet-point summary
- **Translate to Spanish**: Translates the transcription to Spanish (customizable in code)

## Troubleshooting

### "ffmpeg not found" Error
- Make sure ffmpeg is installed and in your system PATH
- Restart your terminal after installing ffmpeg
- Verify installation: `ffmpeg -version`

### "Ollama is not running" Warning
- This is only a warning if you want to use enhancement features
- Basic transcription works without Ollama
- To use enhancement features, start Ollama: `ollama serve`

### "Model not found" Error
- Pull the required model: `ollama pull gemma3n:e4b`
- Verify models: `ollama list`

### Slow Transcription
- Try a smaller Whisper model (tiny or small) in `src/config.py`
- Keep audio clips under 30 seconds
- Ensure your system meets minimum requirements

### Microphone Not Working
- Grant browser permissions for microphone access
- Check your browser's microphone settings
- Try a different browser (Chrome/Firefox recommended)

## Architecture

```
User speaks → Gradio captures audio → Audio preprocessing (16kHz mono)
  → Whisper transcription → [Optional] Ollama enhancement → Display result
```

The application uses:
- **Whisper** for speech-to-text (primary engine)
- **Ollama/gemma3n** for post-processing and enhancement
- **Gradio** for the web interface
- **SciPy** for audio resampling
- **Soundfile** for audio I/O

## Supported Languages

Auto-detection supports 99 languages. Common languages include:

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)
- Portuguese (pt)
- Russian (ru)
- Italian (it)
- And many more...

## License

This project uses the following open-source components:
- OpenAI Whisper (MIT License)
- Gradio (Apache 2.0 License)
- Ollama (MIT License)

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Future Enhancements

Planned features:
- Save transcriptions to file
- Transcription history
- Batch file processing
- Real-time streaming transcription
- Custom Ollama prompts
- Model selection in UI
