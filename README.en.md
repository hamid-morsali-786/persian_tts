<div align="center">

<img src="web/logo.png" width="128" alt="ParSiGo logo">

<h1 align="center">ParSiGo (Persian Text-to-Speech)</h1>

<p align="center"><b>Advanced Persian Audiobook & Speech Studio — Hybrid ONNX Engine & Batch Processing</b></p>
<p align="center">
  <b>Developed by:</b> <a href="https://github.com/hamid-morsali-786">hamid-morsali-786</a> · 
  <b>Forked from:</b> <a href="https://github.com/nimaone/persian_tts">nimaone/persian_tts</a>
</p>

[فارسی](README.md) | **English**

<a href="docs/demo.mp4"><img src="docs/demo-poster.jpg" width="640" alt="ParSiGo video demo"></a>

🎬 **Video demo (with audio)** — Reference voice selection, speech synthesis, voice cloning, batch processing, and audiobook studio.
(Downloadable copy in repo: [docs/demo.mp4](docs/demo.mp4) — Poster: [docs/demo-poster.jpg](docs/demo-poster.jpg))

</div>

Persian text-to-speech with **voice cloning**, running fully offline on **CPU** — no GPU required, no runtime internet required. It accepts Persian text directly, performs phonemisation and acoustic synthesis, and delivers high-fidelity audio in **MP3** or lossless **WAV** format at a 24 kHz sample rate.

---

## 🌟 New Features & Enhancements

This repository extends the original upstream codebase with the following enterprise and production-ready features:

1. 📚 **Audiobook Studio & Batch Processing:**
   - Full audiobook conversion workflow directly in the browser.
   - Intelligent chapter segmentation based on markdown headers and titles.
   - Asynchronous background task queue (`scripts/batch_processor.py`) with non-blocking UI.
   - Real-time progress monitoring with percentage and estimated time remaining.
   - Bulk export as a **ZIP bundle** (with book metadata) or single continuous **Merged Audio**.

2. 🚀 **Hybrid TTS Architecture:**
   - Dual-engine architecture: Fast, lightweight, 100% offline **ONNX Runtime engine** on CPU + high-fidelity cloud **Gemini TTS**.
   - Automatic fallback resilience in case of network disruptions or regional API restrictions.

3. 🎧 **Dual Audio Export Formats (MP3 & WAV):**
   - High-efficiency **MP3** export as the default format (compatible with web and mobile).
   - Studio-grade lossless **WAV** format (24 kHz).
   - On-the-fly format selection in both the Web UI and API.

4. 🎨 **Avant-Garde Dual-Theme UI:**
   - Designed around *Intentional Minimalism*.
   - **Modern Light Theme** by default alongside an elegant **Dark Mode** with smooth transitions.
   - Non-intrusive dismissible alert modals and interactive progress meters.

5. 🛠️ **CLI Conversion Tool (`scripts/convert_text.py`):**
   - Direct text file (`.txt`) conversion via command line with an immediate playback flag (`--play`).

6. ⚡ **One-Click Windows Launchers:**
   - `run_web_ui.bat` for automatic local server launch and browser opening.
   - `push_to_github.bat` for seamless Git Credential authentication and GitHub synchronization.

---

## Project Structure

```
persian_tts/
├── env/                     Python virtual environment
├── model/
│   ├── v2/                  Core TTS model (mehdi-hf/pocket-tts-farsi-v2)
│   ├── g2p/                 Persian G2P model (mehdi-hf/Homo-GE2PE-Persian-HF)
│   └── onnx/                Integrated ONNX package (~480MB) + manifest.json
├── voices/                  Built-in reference voices (≤ 5 seconds)
├── output/                  Generated audio files (WAV/MP3/ZIP)
├── uploads/                 User-uploaded reference voices
├── docs/                    Technical benchmarks & optimization docs
├── scripts/
│   ├── batch_processor.py   Audiobook task queue and ZIP/Merged exporter
│   ├── hybrid_tts.py        Hybrid engine (local ONNX + cloud Gemini)
│   ├── audio_exporter.py    Audio encoding utility (MP3/WAV)
│   ├── convert_text.py      CLI text-to-speech converter with --play flag
│   ├── tts_onnx.py          Pure ONNX engine (no torch needed)
│   ├── g2p_onnx.py          Standalone ONNX G2P module
│   ├── server.py            FastAPI server with batch queue & REST API
│   ├── persian_tts.py       Reference PyTorch pipeline
│   ├── tts.py               PyTorch CLI
│   └── export_unified.py    ONNX exporter script
├── web/
│   └── index.html           Modern responsive RTL web UI with Audiobook Studio
├── run_web_ui.bat           One-click launcher for Windows
├── push_to_github.bat       One-click GitHub sync script
├── README.md                Persian documentation
└── README.en.md             English documentation
```

---

## Quick Start

### 1. Windows One-Click Launcher (Recommended)
Clone the repository:

```powershell
git clone https://github.com/hamid-morsali-786/persian_tts.git
cd persian_tts
```

Simply double-click **`run_web_ui.bat`**. It will initialize the environment, start the server, and automatically open `http://127.0.0.1:8000` in your default browser.

---

### 2. Manual Setup (Pure ONNX Path — Lightweight ~200MB)

```bash
# 1. Create virtualenv and install dependencies
python -m venv env
./env/Scripts/python.exe -m pip install onnxruntime numpy scipy soundfile sentencepiece fastapi uvicorn

# 2. Download ONNX model package from HuggingFace
./env/Scripts/python.exe -m pip install -U "huggingface_hub[cli]"
hf download Nimaone/pocket-tts-farsi-v2-onnx --local-dir model/onnx

# 3. Run Web Studio or CLI
./env/Scripts/python.exe scripts/server.py
./env/Scripts/python.exe scripts/convert_text.py input.txt --play
```

---

## REST API Overview

| Method | Endpoint | Payload | Response |
|---|---|---|---|
| `GET` | `/` | — | Web Studio app (`web/index.html`) |
| `GET` | `/api/voices` | — | Voice list `{voices: [...]}` |
| `POST` | `/api/tts` | `{text, voice, pace?, mode?, engine?, audio_format?}` | Audio metadata `{id, phonemes, duration, format}` |
| `GET` | `/api/audio/{id}` | Optional query `?format=mp3` or `?format=wav` | Audio stream (`audio/mpeg` or `audio/wav`) |
| `POST` | `/api/phonemize` | `{text, mode?}` | Phoneme string `{phonemes}` |
| `POST` | `/api/tts-phonemes` | `{phonemes, voice, pace?, engine?, audio_format?}` | Synthesize from custom phonemes |
| `POST` | `/api/voice/upload` | Multipart file upload | Voice profile `{id, name, seconds}` |
| `POST` | `/api/batch/audiobook` | `{title, text, voice, pace?, mode?, engine?, audio_format?}` | Queue task `{task_id, status, chapters}` |
| `GET` | `/api/batch/status/{id}` | — | Queue status `{progress, status, chapters}` |
| `GET` | `/api/batch/download/{id}` | Optional query `?format=zip` or `?format=merged` | ZIP package or Merged Audio file |

---

## Credits & Acknowledgments

- Extended and maintained by [hamid-morsali-786](https://github.com/hamid-morsali-786) based on [nimaone/persian_tts](https://github.com/nimaone/persian_tts).
- **Core Persian TTS Model:** [`mehdi-hf/pocket-tts-farsi-v2`](https://huggingface.co/mehdi-hf/pocket-tts-farsi-v2) by Mehdi Mallahyari ([`mallahyari/pocket-tts`](https://github.com/mallahyari/pocket-tts)), licensed under **CC-BY-NC-4.0**.
- **Persian G2P Model:** [`Homo-GE2PE-Persian`](https://huggingface.co/MahtaFetrat/Homo-GE2PE-Persian) developed by Elnaz Rahmati et al.
- **Base Architecture:** [`pocket-tts`](https://pypi.org/project/pocket-tts/) by [Kyutai](https://kyutai.org).

> **License Notice:** Due to upstream model licensing (**CC-BY-NC-4.0**), commercial usage of synthetic voice outputs generated by the base acoustic model is prohibited without explicit permission from the original model authors.
