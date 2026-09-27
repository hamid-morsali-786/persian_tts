import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from scripts.server import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower()
    assert "<!doctype html>" in response.text.lower()
    assert "راوی" in response.text or "raavi" in response.text.lower()


def test_api_voices(client):
    response = client.get("/api/voices")
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert isinstance(data["voices"], list)
    assert len(data["voices"]) > 0

    voice_ids = [v["id"] for v in data["voices"]]
    assert "male_hello.wav" in voice_ids
    assert "female_narration.wav" in voice_ids
    assert "male_news.wav" in voice_ids

    # Check structure of voice object
    first_voice = data["voices"][0]
    assert "id" in first_voice
    assert "name" in first_voice
    assert "builtin" in first_voice
    assert first_voice["builtin"] is True


def test_api_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "max_text" in data
    assert "max_phonemes" in data
    assert data["max_text"] > 0
    assert data["max_phonemes"] > 0
    assert data.get("default_format") == "mp3"


def test_api_tts_stream(client):
    import numpy as np
    from unittest.mock import MagicMock, patch

    sr = 24000
    sine = (0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2)))).astype(np.float32)
    meta = {"phonemes": "s-a-l-a-m", "sentences": 1}

    mock_engine = MagicMock()
    def mock_synth(*args, **kwargs):
        cb = kwargs.get("progress_callback")
        if cb:
            cb({"stage": "synthesizing", "current": 1, "total": 1, "percent": 50})
        return sine, sr, meta

    mock_engine.synthesize.side_effect = mock_synth

    with patch("scripts.server.get_engine_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.get_engine.return_value = mock_engine
        mock_mgr_getter.return_value = mock_mgr

        with client.stream(
            "POST",
            "/api/tts-stream",
            json={"text": "تست استریم", "voice": "male_hello.wav", "engine": "local", "format": "mp3"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            lines = list(response.iter_lines())
            text_body = "\n".join(lines)
            assert "progress" in text_body
            assert "complete" in text_body
            assert '"format": "mp3"' in text_body


def test_api_audio_formats(client):
    import json
    import numpy as np
    from unittest.mock import MagicMock, patch

    sr = 24000
    sine = (0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2)))).astype(np.float32)
    mock_engine = MagicMock()
    mock_engine.synthesize.return_value = (sine, sr, {"phonemes": "t-e-s-t"})

    with patch("scripts.server.get_engine_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.get_engine.return_value = mock_engine
        mock_mgr_getter.return_value = mock_mgr

        with client.stream(
            "POST",
            "/api/tts-stream",
            json={"text": "تست فرمت", "voice": "male_hello.wav", "engine": "local", "format": "mp3"},
        ) as response:
            audio_id = None
            for line in response.iter_lines():
                if line.startswith("data:"):
                    evt = json.loads(line[5:].strip())
                    if evt.get("type") == "complete":
                        audio_id = evt["id"]
            assert audio_id is not None

        # Fetch default (MP3)
        res_mp3 = client.get(f"/api/audio/{audio_id}")
        assert res_mp3.status_code == 200
        assert "audio/mpeg" in res_mp3.headers.get("content-type", "")
        assert len(res_mp3.content) > 0

        # Fetch explicitly as WAV
        res_wav = client.get(f"/api/audio/{audio_id}?format=wav")
        assert res_wav.status_code == 200
        assert "audio/wav" in res_wav.headers.get("content-type", "")
        assert len(res_wav.content) > 0
