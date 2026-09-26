# Contributing to ParSiGo (Persian TTS)

Thank you for your interest in contributing to **ParSiGo**! We welcome bug fixes, documentation improvements, feature additions, and architectural optimizations.

---

## 🛠️ Development Setup

1. **Fork and Clone the Repository:**
   ```bash
   git clone https://github.com/hamid-morsali-786/persian_tts.git
   cd persian_tts
   ```

2. **Create and Activate Virtual Environment:**
   ```bash
   python -m venv env
   # On Windows:
   .\env\Scripts\activate
   # On Linux/macOS:
   source env/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .[dev]
   ```

4. **Download ONNX Model Package:**
   ```bash
   hf download Nimaone/pocket-tts-farsi-v2-onnx --local-dir model/onnx
   ```

---

## 🧪 Running Tests

Ensure all tests pass before submitting changes:

```bash
pytest tests/ -v
```

All 40+ unit and integration tests must pass cleanly.

---

## 📐 Coding Standards

- **Clean Code & SRP:** Functions should have single responsibilities and maintain concise lengths (LOC ≤ 15 where practical).
- **Code Comments & Commit Messages:** Write commit messages and code comments in **English** using Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
- **Linting & Formatting:** Ensure code adheres to PEP8 guidelines.

---

## 🚀 Pull Request Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Commit your changes:
   ```bash
   git commit -m "feat: describe your change"
   ```
3. Push to your fork:
   ```bash
   git push origin feat/my-new-feature
   ```
4. Open a Pull Request on GitHub against the `main` branch.
