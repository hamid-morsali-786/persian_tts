"""
Asynchronous batch processing and audiobook production manager.
Handles chapter queueing, background worker execution, real-time SSE progress,
ETA estimation, MP3/WAV export, table-of-contents generation, and ZIP packaging.
"""
from dataclasses import asdict, dataclass, field
import datetime
import io
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import zipfile

import numpy as np
import soundfile as sf

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import chapter_parser
import tts_engine

BATCH_OUTPUT_DIR = BASE_DIR / "output" / "batch"
BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str, max_len: int = 60) -> str:
    """Sanitizes strings for safe filenames across Windows and POSIX filesystems."""
    cleaned = re.sub(r'[\\/*?:"<>|]+', "_", name).strip()
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("_")
    return cleaned[:max_len] if cleaned else "chapter"


def format_duration_clock(seconds: float) -> str:
    """Formats seconds into mm:ss or hh:mm:ss."""
    s = int(round(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


@dataclass
class ChapterItem:
    index: int
    title: str
    text: str
    status: str = "pending"  # pending, processing, completed, failed, cancelled
    progress: float = 0.0
    duration: float = 0.0
    audio_file: Optional[str] = None
    error: Optional[str] = None
    words: int = 0
    chars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BatchAudiobookJob:
    job_id: str
    title: str
    engine: str
    voice: str
    format: str  # "mp3" or "wav"
    pace: float = 1.0
    api_key: Optional[str] = None
    status: str = "queued"  # queued, processing, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    chapters: List[ChapterItem] = field(default_factory=list)
    output_dir: Path = field(default_factory=lambda: BATCH_OUTPUT_DIR)
    zip_path: Optional[str] = None
    merged_path: Optional[str] = None
    total_duration: float = 0.0
    cancel_requested: bool = False
    error: Optional[str] = None
    total_progress: float = 0.0
    eta_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "engine": self.engine,
            "voice": self.voice,
            "format": self.format,
            "pace": self.pace,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "chapters": [c.to_dict() for c in self.chapters],
            "total_chapters": len(self.chapters),
            "completed_chapters": sum(1 for c in self.chapters if c.status == "completed"),
            "total_progress": round(self.total_progress, 1),
            "total_duration": round(self.total_duration, 2),
            "total_duration_clock": format_duration_clock(self.total_duration),
            "eta_seconds": round(self.eta_seconds, 1) if self.eta_seconds is not None else None,
            "has_zip": bool(self.zip_path and os.path.exists(self.zip_path)),
            "has_merged": bool(self.merged_path and os.path.exists(self.merged_path)),
            "error": self.error,
        }

    def create_toc_content(self) -> str:
        """Generates the text for the Table of Contents file (toc.txt)."""
        dt_str = datetime.datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"شناسنامه و فهرست کتاب صوتی: {self.title}",
            f"تاریخ تولید: {dt_str}",
            f"موتور تبدیل: {self.engine} ({self.voice})",
            f"فرمت صدا: {self.format.upper()}",
            f"سرعت گفتار: {self.pace:.2f}x",
            f"تعداد کل فصول: {len(self.chapters)}",
            f"مدت زمان کل: {format_duration_clock(self.total_duration)} ({self.total_duration:.1f} ثانیه)",
            "=" * 50,
            "فهرست فصول:",
        ]
        for c in self.chapters:
            dur_str = format_duration_clock(c.duration)
            fname = Path(c.audio_file).name if c.audio_file else "—"
            lines.append(f"{c.index:02d}. {c.title} — {dur_str} [{fname}]")
        return "\n".join(lines) + "\n"

    def create_metadata_content(self) -> str:
        """Generates structured metadata JSON."""
        meta = {
            "title": self.title,
            "engine": self.engine,
            "voice": self.voice,
            "format": self.format,
            "pace": self.pace,
            "created_at": self.created_at,
            "total_chapters": len(self.chapters),
            "total_duration": round(self.total_duration, 2),
            "total_duration_clock": format_duration_clock(self.total_duration),
            "chapters": [
                {
                    "index": c.index,
                    "title": c.title,
                    "duration": round(c.duration, 2),
                    "duration_clock": format_duration_clock(c.duration),
                    "words": c.words,
                    "filename": Path(c.audio_file).name if c.audio_file else None,
                }
                for c in self.chapters
            ],
        }
        return json.dumps(meta, ensure_ascii=False, indent=2)

    def create_zip(self) -> Optional[str]:
        """Packages all completed chapters, toc.txt, and metadata.json into a ZIP."""
        if self.cancel_requested:
            return None
        safe_book_name = sanitize_filename(self.title)
        zip_filename = f"{safe_book_name}_{self.job_id[:8]}.zip"
        zip_dest = self.output_dir / zip_filename

        try:
            with zipfile.ZipFile(str(zip_dest), "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("toc.txt", self.create_toc_content().encode("utf-8"))
                zf.writestr("metadata.json", self.create_metadata_content().encode("utf-8"))

                for c in self.chapters:
                    if self.cancel_requested:
                        zf.close()
                        if os.path.exists(zip_dest):
                            try:
                                os.remove(zip_dest)
                            except Exception:
                                pass
                        return None
                    if c.audio_file and os.path.exists(c.audio_file):
                        arc_name = Path(c.audio_file).name
                        zf.write(c.audio_file, arcname=arc_name)

            self.zip_path = str(zip_dest)
            return self.zip_path
        except Exception as e:
            print(f"Warning: Failed to create ZIP archive: {e}")
            if os.path.exists(zip_dest):
                try:
                    os.remove(zip_dest)
                except Exception:
                    pass
            return None

    def create_merged_audio(self) -> Optional[str]:
        """Concatenates all completed chapters with natural 1.5s pauses into one file sequentially."""
        completed_chapters = [c for c in self.chapters if c.audio_file and os.path.exists(c.audio_file)]
        if not completed_chapters:
            return None

        target_sr = 24000
        try:
            target_sr = sf.info(completed_chapters[0].audio_file).samplerate
        except Exception:
            pass

        ext = self.format.lower()
        fmt = "MP3" if ext == "mp3" else "WAV"
        safe_book_name = sanitize_filename(self.title)
        merged_filename = f"{safe_book_name}_full.{ext}"
        merged_dest = self.output_dir / merged_filename

        silence = np.zeros(int(1.5 * target_sr), dtype=np.float32)

        try:
            with sf.SoundFile(str(merged_dest), mode="w", samplerate=target_sr, channels=1, format=fmt) as outfile:
                for idx, c in enumerate(completed_chapters):
                    if self.cancel_requested:
                        outfile.close()
                        if os.path.exists(merged_dest):
                            try:
                                os.remove(merged_dest)
                            except Exception:
                                pass
                        return None
                    data, _ = sf.read(c.audio_file)
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    outfile.write(data.astype(np.float32))
                    if idx < len(completed_chapters) - 1:
                        outfile.write(silence)
            self.merged_path = str(merged_dest)
            return self.merged_path
        except Exception as e:
            print(f"Warning: Failed to create merged audio: {e}")
            if os.path.exists(merged_dest):
                try:
                    os.remove(merged_dest)
                except Exception:
                    pass
            return None


class BatchJobManager:
    """Singleton manager controlling the batch audiobook queue and workers."""

    def __init__(self) -> None:
        self._jobs: Dict[str, BatchAudiobookJob] = {}
        self._queue: queue.Queue[BatchAudiobookJob] = queue.Queue()
        self._subscribers: Dict[str, List[queue.Queue]] = {}
        self._lock = threading.RLock()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def create_job(
        self,
        title: str,
        chapters: List[Dict[str, Any]],
        engine: str = "local",
        voice: str = "male_hello.wav",
        audio_format: str = "mp3",
        pace: float = 1.0,
        api_key: Optional[str] = None,
    ) -> BatchAudiobookJob:
        import uuid

        job_id = uuid.uuid4().hex[:12]
        output_dir = BATCH_OUTPUT_DIR / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        chapter_items: List[ChapterItem] = []
        for idx, ch in enumerate(chapters, 1):
            ch_title = ch.get("title") or f"فصل {idx}"
            ch_text = (ch.get("text") or "").strip()
            words = len(ch_text.split())
            chapter_items.append(
                ChapterItem(
                    index=idx,
                    title=ch_title,
                    text=ch_text,
                    words=words,
                    chars=len(ch_text),
                )
            )

        job = BatchAudiobookJob(
            job_id=job_id,
            title=title or "کتاب صوتی",
            engine=engine.lower(),
            voice=voice,
            format=audio_format.lower(),
            pace=pace,
            api_key=api_key,
            chapters=chapter_items,
            output_dir=output_dir,
        )

        with self._lock:
            self._jobs[job_id] = job
            self._subscribers[job_id] = []

        self._queue.put(job)
        self.broadcast(job_id, {"type": "job_created", "job": job.to_dict()})
        return job

    def get_job(self, job_id: str) -> Optional[BatchAudiobookJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [j.to_dict() for j in sorted(self._jobs.values(), key=lambda x: x.created_at, reverse=True)]

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.cancel_requested = True
            job.status = "cancelled"
            for c in job.chapters:
                if c.status in ("pending", "processing"):
                    c.status = "cancelled"
            job_data = job.to_dict()

        self.broadcast(job_id, {"type": "job_cancelled", "job_id": job_id, "job": job_data})
        return True

    def subscribe(self, job_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = []
            self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        with self._lock:
            if job_id in self._subscribers and q in self._subscribers[job_id]:
                self._subscribers[job_id].remove(q)

    def broadcast(self, job_id: str, event: Dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers.get(job_id, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except Exception:
                pass

    def _worker_loop(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._process_job(job)
            except Exception as e:
                print(f"Error processing batch job {job.job_id}: {e}")
                job.status = "failed"
                job.error = str(e)
                self.broadcast(job.job_id, {"type": "job_failed", "error": str(e), "job": job.to_dict()})
            finally:
                self._queue.task_done()

    def _handle_cancellation(self, job: BatchAudiobookJob, from_idx: int = 0) -> None:
        job.status = "cancelled"
        for c in job.chapters[from_idx:]:
            if c.status in ("pending", "processing"):
                c.status = "cancelled"
        self.broadcast(job.job_id, {"type": "job_cancelled", "job": job.to_dict()})

    def _handle_failure(self, job: BatchAudiobookJob, chapter: ChapterItem, error_msg: str, from_idx: int) -> None:
        chapter.status = "failed"
        chapter.error = error_msg
        for rest in job.chapters[from_idx + 1:]:
            if rest.status == "pending":
                rest.status = "failed"
                rest.error = "Previous chapter failed"
        job.status = "failed"
        job.error = error_msg
        self.broadcast(job.job_id, {
            "type": "chapter_failed",
            "job_id": job.job_id,
            "chapter_index": chapter.index,
            "error": error_msg,
        })
        self.broadcast(job.job_id, {"type": "job_failed", "error": error_msg, "job": job.to_dict()})

    def _process_job(self, job: BatchAudiobookJob) -> None:
        if job.cancel_requested:
            self._handle_cancellation(job)
            return

        job.status = "processing"
        job.started_at = time.time()
        self.broadcast(job.job_id, {"type": "job_started", "job": job.to_dict()})

        engine_manager = tts_engine.get_engine_manager()
        tts_eng = engine_manager.get_engine(job.engine)
        total_dur = 0.0

        for idx, chapter in enumerate(job.chapters):
            if job.cancel_requested:
                self._handle_cancellation(job, idx)
                return

            chapter.status = "processing"
            chapter.progress = 5.0
            self._update_progress_and_eta(job, idx, 5.0)

            try:
                def on_chunk_progress(data: dict) -> None:
                    if job.cancel_requested:
                        raise InterruptedError("Batch job was cancelled")
                    pct = float(data.get("percent", 5.0))
                    chapter.progress = pct
                    self._update_progress_and_eta(job, idx, pct)
                    self.broadcast(job.job_id, {
                        "type": "chapter_progress",
                        "job_id": job.job_id,
                        "chapter_index": chapter.index,
                        "percent": pct,
                        "total_progress": job.total_progress,
                        "eta_seconds": job.eta_seconds,
                        "sentence": data.get("sentence", ""),
                    })

                kwargs: Dict[str, Any] = {
                    "pace": job.pace,
                    "progress_callback": on_chunk_progress,
                }
                if job.engine == "gemini":
                    kwargs["api_key"] = job.api_key
                else:
                    kwargs["mode"] = "split"

                audio, sr, _ = tts_eng.synthesize(
                    text=chapter.text,
                    voice=job.voice,
                    **kwargs,
                )

                if job.cancel_requested:
                    self._handle_cancellation(job, idx)
                    return

                duration = len(audio) / sr
                chapter.duration = duration
                total_dur += duration

                ext = job.format.lower()
                fmt = "MP3" if ext == "mp3" else "WAV"
                safe_title = sanitize_filename(chapter.title)
                chapter_file = job.output_dir / f"{chapter.index:02d}_{safe_title}.{ext}"
                sf.write(str(chapter_file), audio, sr, format=fmt)

                chapter.audio_file = str(chapter_file)
                chapter.progress = 100.0
                chapter.status = "completed"

                self._update_progress_and_eta(job, idx + 1, 0.0)
                self.broadcast(job.job_id, {
                    "type": "chapter_completed",
                    "job_id": job.job_id,
                    "chapter_index": chapter.index,
                    "duration": round(duration, 2),
                    "total_progress": job.total_progress,
                    "eta_seconds": job.eta_seconds,
                    "chapter": chapter.to_dict(),
                })

            except InterruptedError:
                self._handle_cancellation(job, idx)
                return
            except Exception as e:
                self._handle_failure(job, chapter, str(e), idx)
                return

        if job.cancel_requested:
            self._handle_cancellation(job)
            return

        job.total_duration = total_dur
        job.total_progress = 98.0
        self.broadcast(job.job_id, {
            "type": "packaging_started",
            "message": "در حال بسته‌بندی فایل فشرده ZIP و ادغام فصول…",
        })

        try:
            job.create_zip()
            job.create_merged_audio()
        except Exception as e:
            print(f"Warning: Packaging failed for job {job.job_id}: {e}")
            job.error = f"Packaging warning: {e}"

        if job.cancel_requested:
            self._handle_cancellation(job)
            return

        job.status = "completed"
        job.completed_at = time.time()
        job.total_progress = 100.0
        job.eta_seconds = 0.0

        self.broadcast(job.job_id, {
            "type": "job_completed",
            "job": job.to_dict(),
        })

    def _update_progress_and_eta(
        self,
        job: BatchAudiobookJob,
        completed_chapters: int,
        current_chapter_pct: float,
    ) -> None:
        total_chapters = len(job.chapters)
        if total_chapters == 0:
            job.total_progress = 100.0
            job.eta_seconds = 0.0
            return

        unit = 100.0 / total_chapters
        base = completed_chapters * unit
        partial = (current_chapter_pct / 100.0) * unit
        job.total_progress = min(99.0, max(0.0, base + partial))

        if job.started_at:
            elapsed = time.time() - job.started_at
            completed_fraction = (completed_chapters + current_chapter_pct / 100.0) / total_chapters
            if completed_fraction > 0.02:
                rate = completed_fraction / max(0.1, elapsed)
                rem_fraction = 1.0 - completed_fraction
                job.eta_seconds = max(0.0, rem_fraction / rate)


_default_batch_manager: Optional[BatchJobManager] = None


def get_batch_manager() -> BatchJobManager:
    global _default_batch_manager
    if _default_batch_manager is None:
        _default_batch_manager = BatchJobManager()
    return _default_batch_manager
