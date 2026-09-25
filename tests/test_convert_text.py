import os
import sys
import subprocess
from pathlib import Path
import pytest
import soundfile as sf

# اطمینان از وجود مسیر ریشه در sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from convert_text import text_to_speech


def test_short_sentence(tmp_path):
    out_path = str(tmp_path / "test_module_short.wav")
    voice_path = "voices/male_hello.wav"
    assert os.path.exists(voice_path), f"Voice reference not found: {voice_path}"

    res = text_to_speech("این یک آزمایش است.", voice=voice_path, output_file=out_path)
    assert os.path.exists(out_path)
    assert res == out_path

    info = sf.info(out_path)
    assert info.samplerate == 24000
    assert info.duration > 0.5


def test_voice_not_found(tmp_path):
    out_path = str(tmp_path / "test_fail.wav")
    with pytest.raises(FileNotFoundError):
        text_to_speech("سلام", voice="voices/non_existent.wav", output_file=out_path)


def test_cli_execution(tmp_path):
    out_path = str(tmp_path / "test_cli.wav")
    cmd = [
        sys.executable,
        str(ROOT_DIR / "convert_text.py"),
        "--text", "سلام دنیا",
        "--voice", "voices/male_hello.wav",
        "--output", out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT_DIR))
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert os.path.exists(out_path)
    info = sf.info(out_path)
    assert info.samplerate == 24000
    assert info.duration > 0.3
