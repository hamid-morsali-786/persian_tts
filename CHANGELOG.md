# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-09-26

### Added
- **Audiobook Studio & Batch Processing:** Full-text book conversion, automatic chapter segmentation, and asynchronous background worker queue.
- **Dual Export Formats:** Native support for both MP3 (default, compressed) and WAV (lossless 24kHz) export.
- **Bulk Packaging:** ZIP archive generator containing chapter audio and descriptive book metadata, plus continuous merged audio export.
- **Hybrid TTS Engine:** Native support for Google Cloud Gemini TTS API with automatic zero-downtime fallback to local ONNX.
- **CLI File Converter:** `scripts/convert_text.py` with immediate audio playback (`--play`).
- **Windows Launchers:** `run_web_ui.bat` and `push_to_github.bat` for one-click operations.
- **Modern Light Theme:** Redesigned responsive Web UI with intentional minimalism, high contrast, and smooth theme switching.
- **Dismissible Toasts:** Persistent error/warning alerts that user can manually dismiss.
- **Comprehensive Test Suite:** 40 automated tests covering batch processing, hybrid engine, chapter parsing, and endpoints.

### Changed
- Refactored server architecture to support concurrent batch queues and multi-format audio streams.
- Upgraded `.gitignore` to protect against credential leaks and large binary files.

---

## [2.0.0] - 2026-09-20

### Added
- Pure ONNX Runtime engine eliminating PyTorch dependency at runtime.
- G2P ByT5 tokenizer implemented in pure Python.
- Fast CPU-only inference pipeline with 24kHz acoustic synthesis.
- Web UI with voice cloning and audio waveform visualization.

---

## [1.0.0] - 2025-08-15

### Added
- Initial reference PyTorch pipeline for Persian TTS and voice cloning.
