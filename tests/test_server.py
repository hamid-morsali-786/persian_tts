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
    assert "پارسی‌گو" in response.text or "persian" in response.text.lower()


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
