# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] - 2026-09-29

### Added
- **Project Rebranding:** Officially rebranded project from ParSiGo to **راوی (Raavi)** / `raavi-tts`.
- **Global Hybrid Engine Switcher:** Unified engine toggle accessible from both Single TTS and Audiobook Studio views with two-way API key synchronization and localStorage persistence.
- **Enterprise UI/UX Audit Improvements (P0/P1):**
  - Standardized audio waveform time axis from left to right (universal audio physical convention) with synced mouse/pointer scrub and keyboard arrow step navigation (`ArrowRight` = forward, `ArrowLeft` = backward).
  - Added a 6-second non-destructive Undo Toast mechanism for accidental chapter deletion in Audiobook Studio.
  - Implemented W3C ARIA APG Roving Tabindex for voice cards with Arrow key navigation.
  - Preserved physical tactile spring animation on the hardware theme toggle.
  - Added responsive mobile viewport breakpoint (`@media (max-width: 560px)`) for stacked studio layout.
  - Replaced all emoji glyphs with accessible, engineered inline SVG vector icons.
  - Aligned concentric corner radii ($R_{outer} = 32\text{px} = 12\text{px} + 20\text{px}$) across panels and form controls.
  - Enhanced dark obsidian theme text contrast (`--faint: #b4b4c0`, WCAG AAA compliant).
  - Scoped line-height inheritance (`1.4`) to prevent bloated UI control boxes.

### Fixed
- Fixed extra closing `</div>` in `renderChapterGrid()` template that corrupted chapter DOM cards.
- Eliminated all 17 generic `transition: all` declarations across CSS to resolve GPU repaint and layout thrashing bottlenecks.
- Isolated global Spacebar and 'K' keyboard play/pause shortcuts strictly to the Single TTS view.
- Purged legacy ambient `.orb` gradient DOM nodes.

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
