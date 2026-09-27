import io
import json
from pathlib import Path
import sys
import time
from unittest.mock import MagicMock, patch
import zipfile

import numpy as np
import pytest
import soundfile as sf

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from scripts.batch_manager import (
    BatchAudiobookJob,
    BatchJobManager,
    ChapterItem,
    format_duration_clock,
    sanitize_filename,
)


def test_sanitize_filename():
    assert sanitize_filename('فصل اول: آشنایی/شروع?') == 'فصل_اول_آشنایی_شروع'
    assert sanitize_filename('Chapter * 1 <>') == 'Chapter_1'
    assert sanitize_filename('   ') == 'chapter'


def test_format_duration_clock():
    assert format_duration_clock(0) == "00:00"
    assert format_duration_clock(65) == "01:05"
    assert format_duration_clock(3665) == "01:01:05"


def test_create_toc_and_metadata():
    job = BatchAudiobookJob(
        job_id="test1234",
        title="کتاب آزمایشی",
        engine="local",
        voice="male_hello.wav",
        format="mp3",
        pace=1.0,
        chapters=[
            ChapterItem(index=1, title="مقدمه", text="متن ۱", duration=30.0, audio_file="01_مقدمه.mp3"),
            ChapterItem(index=2, title="فصل اول", text="متن ۲", duration=60.0, audio_file="02_فصل_اول.mp3"),
        ],
        total_duration=90.0,
    )

    toc = job.create_toc_content()
    assert "کتاب آزمایشی" in toc
    assert "01. مقدمه" in toc
    assert "02. فصل اول" in toc

    meta_str = job.create_metadata_content()
    meta = json.loads(meta_str)
    assert meta["title"] == "کتاب آزمایشی"
    assert meta["total_chapters"] == 2
    assert meta["chapters"][0]["title"] == "مقدمه"


@patch("scripts.batch_manager.tts_engine.get_engine_manager")
def test_batch_worker_execution(mock_mgr_getter, tmp_path):
    manager = BatchJobManager()

    sr = 24000
    sine = (0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2)))).astype(np.float32)

    mock_engine = MagicMock()
    def mock_synthesize(*args, **kwargs):
        cb = kwargs.get("progress_callback")
        if cb:
            cb({"percent": 50, "stage": "synthesizing"})
            cb({"percent": 100, "stage": "finalizing"})
        return sine, sr, {}

    mock_engine.synthesize.side_effect = mock_synthesize
    mock_mgr = MagicMock()
    mock_mgr.get_engine.return_value = mock_engine
    mock_mgr_getter.return_value = mock_mgr

    with patch("scripts.batch_manager.BATCH_OUTPUT_DIR", tmp_path):
        chapters = [
            {"title": "بخش ۱", "text": "متن تستی بخش اول."},
            {"title": "بخش ۲", "text": "متن تستی بخش دوم."},
        ]

        job = manager.create_job(
            title="تست کامل بچ",
            chapters=chapters,
            engine="local",
            voice="male_hello.wav",
            audio_format="mp3",
        )

        max_wait = 5.0
        start = time.time()
        while job.status in ("queued", "processing") and time.time() - start < max_wait:
            time.sleep(0.05)

        assert job.status == "completed"
        assert len(job.chapters) == 2
        assert all(c.status == "completed" for c in job.chapters)
        assert job.zip_path is not None
        assert Path(job.zip_path).exists()
        assert job.merged_path is not None
        assert Path(job.merged_path).exists()

        # Verify ZIP contents
        with zipfile.ZipFile(job.zip_path, "r") as zf:
            names = zf.namelist()
            assert "toc.txt" in names
            assert "metadata.json" in names
            assert any("01_بخش_۱.mp3" in n for n in names)
            assert any("02_بخش_۲.mp3" in n for n in names)


@patch("scripts.batch_manager.tts_engine.get_engine_manager")
def test_batch_cancel_job(mock_mgr_getter, tmp_path):
    manager = BatchJobManager()
    chapters = [{"title": f"فصل {i}", "text": f"متن فصل {i}"} for i in range(1, 5)]

    mock_engine = MagicMock()
    def mock_synthesize(*args, **kwargs):
        time.sleep(0.05)
        return np.zeros(2400, dtype=np.float32), 24000, {}

    mock_engine.synthesize.side_effect = mock_synthesize
    mock_mgr = MagicMock()
    mock_mgr.get_engine.return_value = mock_engine
    mock_mgr_getter.return_value = mock_mgr

    with patch("scripts.batch_manager.BATCH_OUTPUT_DIR", tmp_path):
        job = manager.create_job(
            title="کتاب کنسل شونده",
            chapters=chapters,
            engine="local",
            voice="male_hello.wav",
            audio_format="wav",
        )

        # Cancel job
        success = manager.cancel_job(job.job_id)
        assert success is True
        assert job.cancel_requested is True
        assert job.status == "cancelled"

        # Wait for worker thread to finish the current job
        max_wait = 3.0
        start = time.time()
        while time.time() - start < max_wait:
            time.sleep(0.05)

        # Confirm job remains cancelled and was NOT overwritten to completed
        assert job.status == "cancelled"
        assert any(c.status == "cancelled" for c in job.chapters)


@patch("scripts.batch_manager.tts_engine.get_engine_manager")
def test_batch_cancellation_during_packaging(mock_mgr_getter, tmp_path):
    manager = BatchJobManager()
    chapters = [{"title": "فصل ۱", "text": "متن تستی برای پکیجینگ."}]

    mock_engine = MagicMock()
    mock_engine.synthesize.return_value = (np.zeros(2400, dtype=np.float32), 24000, {})
    mock_mgr = MagicMock()
    mock_mgr.get_engine.return_value = mock_engine
    mock_mgr_getter.return_value = mock_mgr

    with patch("scripts.batch_manager.BATCH_OUTPUT_DIR", tmp_path):
        job = manager.create_job(
            title="تست لغو در پکیجینگ",
            chapters=chapters,
            engine="local",
            audio_format="mp3",
        )

        # Request cancellation right after chapter synthesis
        job.cancel_requested = True

        max_wait = 3.0
        start = time.time()
        while job.status in ("queued", "processing") and time.time() - start < max_wait:
            time.sleep(0.05)

        # Must NOT be completed
        assert job.status == "cancelled"


@patch("scripts.batch_manager.tts_engine.get_engine_manager")
def test_batch_chapter_failure_handling(mock_mgr_getter, tmp_path):
    manager = BatchJobManager()
    chapters = [
        {"title": "فصل ۱", "text": "متن موفق"},
        {"title": "فصل ۲", "text": "متن ناموفق"},
        {"title": "فصل ۳", "text": "متن بعد از شکست"},
    ]

    mock_engine = MagicMock()
    call_count = [0]
    def mock_synthesize(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Engine simulated failure")
        return np.zeros(2400, dtype=np.float32), 24000, {}

    mock_engine.synthesize.side_effect = mock_synthesize
    mock_mgr = MagicMock()
    mock_mgr.get_engine.return_value = mock_engine
    mock_mgr_getter.return_value = mock_mgr

    with patch("scripts.batch_manager.BATCH_OUTPUT_DIR", tmp_path):
        job = manager.create_job(
            title="تست شکست در صف",
            chapters=chapters,
            engine="local",
            audio_format="wav",
        )

        max_wait = 4.0
        start = time.time()
        while job.status in ("queued", "processing") and time.time() - start < max_wait:
            time.sleep(0.05)

        assert job.status == "partial"
        assert job.chapters[0].status == "completed"
        assert job.chapters[1].status == "failed"
        assert job.chapters[2].status == "completed"
