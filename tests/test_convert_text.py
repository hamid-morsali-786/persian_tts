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


def test_audiobook_cli_execution(tmp_path):
    from unittest.mock import MagicMock, patch
    import zipfile
    import numpy as np
    from convert_text import process_audiobook_cli
    import argparse

    book_txt = tmp_path / "book.txt"
    book_txt.write_text("""# کتاب تست صوتی
فصل اول: مقدمه
این متن تست فصل اول برای پردازش است.

فصل دوم: پایان
این متن تست فصل دوم است.
""", encoding="utf-8")
    zip_out = tmp_path / "output.zip"

    args = argparse.Namespace(
        batch_dir=None,
        audiobook_text=str(book_txt),
        output_zip=str(zip_out),
        audio_format="mp3",
        title="کتاب صوتی من",
        pace=1.0,
        engine="local",
        api_key=None,
        play=False,
    )

    mock_engine = MagicMock()
    mock_engine.synthesize.return_value = (np.zeros(2400, dtype=np.float32), 24000, {})

    with patch("batch_manager.tts_engine.get_engine_manager") as mock_mgr:
        m = MagicMock()
        m.get_engine.return_value = mock_engine
        mock_mgr.return_value = m

        process_audiobook_cli(args, selected_voice="voices/male_hello.wav")

    assert zip_out.exists()
    assert zipfile.is_zipfile(str(zip_out))
    with zipfile.ZipFile(str(zip_out), "r") as zf:
        names = zf.namelist()
        assert "toc.txt" in names
        assert "metadata.json" in names
        assert any("01_فصل_اول_مقدمه.mp3" in n for n in names)
        assert any("02_فصل_دوم_پایان.mp3" in n for n in names)

