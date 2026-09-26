import json
from pathlib import Path
import sys
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from scripts.server import app
from scripts.batch_manager import get_batch_manager


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_api_batch_parse_chapters_text(client):
    body = {
        "text": """
مقدمه
متن مقدمه کتاب برای تست پارسر.

فصل اول: گام نخست
شروع مسیر و مراحل اولیه.
""",
        "chunk_words": 1000,
    }
    response = client.post("/api/batch/parse-chapters", json=body)
    assert response.status_code == 200
    data = response.json()
    assert "chapters" in data
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["title"] == "مقدمه"
    assert data["chapters"][1]["title"] == "فصل اول: گام نخست"
    assert data["total_words"] > 0
    assert data["total_estimated_duration"] > 0


def test_api_batch_parse_files(client):
    files = [
        ("files", ("chap1.txt", "متن فصل اول".encode("utf-8"), "text/plain")),
        ("files", ("chap2.txt", "متن فصل دوم".encode("utf-8"), "text/plain")),
    ]
    response = client.post("/api/batch/parse-files", files=files)
    assert response.status_code == 200
    data = response.json()
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["title"] == "chap1"
    assert data["chapters"][1]["title"] == "chap2"


def test_api_batch_lifecycle_and_download(client, tmp_path):
    sr = 24000
    sine = (0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2)))).astype(np.float32)

    mock_engine = MagicMock()
    mock_engine.synthesize.return_value = (sine, sr, {})

    with patch("batch_manager.tts_engine.get_engine_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.get_engine.return_value = mock_engine
        mock_mgr_getter.return_value = mock_mgr

        with patch("batch_manager.BATCH_OUTPUT_DIR", tmp_path):
            # 1. Create job
            create_payload = {
                "title": "کتاب تست سرور",
                "chapters": [
                    {"title": "مقدمه", "text": "متن تستی مقدمه"},
                    {"title": "فصل ۱", "text": "متن تستی فصل یک"},
                ],
                "engine": "local",
                "voice": "male_hello.wav",
                "format": "mp3",
            }
            create_resp = client.post("/api/batch/create", json=create_payload)
            assert create_resp.status_code == 200
            res = create_resp.json()
            assert "job_id" in res
            job_id = res["job_id"]

            # 2. Check status
            status_resp = client.get(f"/api/batch/status/{job_id}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert status_data["title"] == "کتاب تست سرور"
            assert status_data["total_chapters"] == 2

            # 3. Wait for background completion
            max_wait = 5.0
            start = time.time()
            while time.time() - start < max_wait:
                s = client.get(f"/api/batch/status/{job_id}").json()
                if s["status"] in ("completed", "failed"):
                    break
                time.sleep(0.05)

            assert s["status"] == "completed"

            # 4. Stream endpoint test (completed snapshot)
            with client.stream("GET", f"/api/batch/stream/{job_id}") as stream_resp:
                assert stream_resp.status_code == 200
                lines = list(stream_resp.iter_lines())
                body = "\n".join(lines)
                assert "snapshot" in body

            # 5. Download ZIP
            zip_resp = client.get(f"/api/batch/download/{job_id}?type=zip")
            assert zip_resp.status_code == 200
            assert "application/zip" in zip_resp.headers["content-type"]
            assert len(zip_resp.content) > 100

            # 6. Download Merged Audio
            merged_resp = client.get(f"/api/batch/download/{job_id}?type=merged")
            assert merged_resp.status_code == 200
            assert "audio" in merged_resp.headers["content-type"]
            assert len(merged_resp.content) > 100

            # 7. Download single chapter audio
            chap_resp = client.get(f"/api/batch/chapter/{job_id}/1")
            assert chap_resp.status_code == 200
            assert "audio" in chap_resp.headers["content-type"]


def test_api_batch_cancel(client, tmp_path):
    mock_engine = MagicMock()
    mock_engine.synthesize.return_value = (np.zeros(2400, dtype=np.float32), 24000, {})

    with patch("batch_manager.tts_engine.get_engine_manager") as mock_mgr_getter:
        mock_mgr = MagicMock()
        mock_mgr.get_engine.return_value = mock_engine
        mock_mgr_getter.return_value = mock_mgr

        with patch("batch_manager.BATCH_OUTPUT_DIR", tmp_path):
            create_payload = {
                "title": "کتاب لغو شدنی",
                "chapters": [{"title": f"فصل {i}", "text": f"متن {i}"} for i in range(1, 4)],
            }
            create_resp = client.post("/api/batch/create", json=create_payload)
            job_id = create_resp.json()["job_id"]

            cancel_resp = client.post(f"/api/batch/cancel/{job_id}")
            assert cancel_resp.status_code == 200
            assert cancel_resp.json()["status"] == "cancelled"

            status_resp = client.get(f"/api/batch/status/{job_id}")
            assert status_resp.json()["status"] == "cancelled"


def test_api_batch_create_validation(client):
    # Empty chapters list
    resp1 = client.post("/api/batch/create", json={"chapters": []})
    assert resp1.status_code == 400

    # Chapters with only whitespace
    resp2 = client.post("/api/batch/create", json={"chapters": [{"title": "t", "text": "   "}]})
    assert resp2.status_code == 400

    # Invalid audio format
    resp3 = client.post("/api/batch/create", json={
        "chapters": [{"title": "t", "text": "valid text"}],
        "format": "invalid_format",
    })
    assert resp3.status_code == 400
