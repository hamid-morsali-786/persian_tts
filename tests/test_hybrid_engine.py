import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from scripts.server import app
from scripts.tts_engine import (
    GeminiCloudEngine,
    LocalOnnxEngine,
    TTSEngineManager,
    get_engine_manager,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_engine_manager_discovery():
    manager = get_engine_manager()
    engines = manager.list_engines()
    assert len(engines) >= 2
    engine_ids = [e["id"] for e in engines]
    assert "local" in engine_ids
    assert "gemini" in engine_ids

    local_eng = manager.get_engine("local")
    assert isinstance(local_eng, LocalOnnxEngine)
    assert local_eng.is_available() is True

    gemini_eng = manager.get_engine("gemini")
    assert isinstance(gemini_eng, GeminiCloudEngine)
    assert gemini_eng.is_available() is True

    with pytest.raises(ValueError):
        manager.get_engine("unsupported_engine")


def test_gemini_voice_list_and_chunks():
    gemini_eng = GeminiCloudEngine()
    voices = gemini_eng.list_voices()
    assert len(voices) >= 5
    voice_ids = [v["id"] for v in voices]
    assert "Kore" in voice_ids
    assert "Puck" in voice_ids

    # Test chunking of long text
    short_text = "سلام به دنیای هوش مصنوعی."
    chunks = gemini_eng._split_into_chunks(short_text, max_chars=100)
    assert chunks == [short_text]

    long_text = "پاراگراف اول.\n\nپاراگراف دوم.\n\nپاراگراف سوم."
    chunks_split = gemini_eng._split_into_chunks(long_text, max_chars=25)
    assert len(chunks_split) >= 2


def test_gemini_synthesize_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini_eng = GeminiCloudEngine(api_key="")
    with pytest.raises(ValueError, match="API key is required"):
        gemini_eng.synthesize("تست بدون کلید", voice="Kore")


def test_gemini_synthesize_mocked():
    gemini_eng = GeminiCloudEngine(api_key="mock_test_key")

    # Generate mock 1-second 24kHz sine wave WAV bytes
    sr = 24000
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, sine, sr, format="WAV")
    mock_wav_bytes = buf.getvalue()

    mock_client = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [MagicMock()]
    mock_candidate.content.parts[0].inline_data.data = mock_wav_bytes
    mock_client.models.generate_content.return_value.candidates = [mock_candidate]

    with patch("google.genai.Client", return_value=mock_client):
        audio, out_sr, meta = gemini_eng.synthesize(
            text="سلام دنیا",
            voice="Kore",
            api_key="mock_test_key",
        )

    assert out_sr == sr
    assert len(audio) > 0
    assert meta["engine"] == "gemini"


def test_api_engines_endpoint(client):
    response = client.get("/api/engines")
    assert response.status_code == 200
    data = response.json()
    assert "engines" in data
    ids = [e["id"] for e in data["engines"]]
    assert "local" in ids
    assert "gemini" in ids


def test_api_voices_filtered(client):
    # Gemini voices
    resp_gemini = client.get("/api/voices?engine=gemini")
    assert resp_gemini.status_code == 200
    gemini_voices = [v["id"] for v in resp_gemini.json()["voices"]]
    assert "Kore" in gemini_voices
    assert "male_hello.wav" not in gemini_voices

    # Local voices
    resp_local = client.get("/api/voices?engine=local")
    assert resp_local.status_code == 200
    local_voices = [v["id"] for v in resp_local.json()["voices"]]
    assert "male_hello.wav" in local_voices
    assert "Kore" not in local_voices


def test_api_upload_text_endpoint(client):
    content = "این یک متن طولانی برای تست تبدیل کتاب صوتی است."
    files = {"file": ("test_doc.txt", content.encode("utf-8"), "text/plain")}
    response = client.post("/api/upload-text", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == content
    assert data["chars"] == len(content)
    assert data["words"] == len(content.split())
    assert data["filename"] == "test_doc.txt"


def test_api_tts_gemini_mocked(client):
    sr = 24000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, sine, sr, format="WAV")
    mock_wav_bytes = buf.getvalue()

    mock_client = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [MagicMock()]
    mock_candidate.content.parts[0].inline_data.data = mock_wav_bytes
    mock_client.models.generate_content.return_value.candidates = [mock_candidate]

    with patch("google.genai.Client", return_value=mock_client):
        response = client.post(
            "/api/tts",
            json={
                "text": "متن تستی با موتور جمینای",
                "voice": "Kore",
                "engine": "gemini",
                "api_key": "mock_test_key",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["engine"] == "gemini"
    assert data["duration"] > 0

    # Retrieve audio (default format is MP3)
    audio_res = client.get(f"/api/audio/{data['id']}")
    assert audio_res.status_code == 200
    assert "audio/mpeg" in audio_res.headers["content-type"]

    # Retrieve audio explicitly as WAV
    wav_res = client.get(f"/api/audio/{data['id']}?format=wav")
    assert wav_res.status_code == 200
    assert "audio/wav" in wav_res.headers["content-type"]
