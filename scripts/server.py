# Demo web server for the pure-ONNX Persian TTS engine.
#
#   ./env/Scripts/python.exe scripts/server.py     -> http://127.0.0.1:8000
#
# Endpoints:
#   GET  /                  the single-page UI (web/index.html)
#   GET  /api/voices        available reference voices (builtin + uploaded)
#   POST /api/tts           {text, voice} -> {id, phonemes, duration, ...}
#   GET  /api/audio/{id}    generated WAV
#   POST /api/voice/upload  upload a custom voice (auto-trimmed to 5 s)
import asyncio
import io
import json
import os
import re
import queue
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from tts_engine import get_engine_manager
from batch_manager import get_batch_manager
from chapter_parser import (
    extract_book_title,
    parse_files_into_chapters,
    parse_text_into_chapters,
)

WEB = BASE / "web" / "index.html"
UPLOAD_DIR = BASE / "uploads" / "voices"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_TEXT = 50000        # supports long documents, articles, and book chapters
MAX_PHONEMES = 2400     # editable manual-phoneme input cap
MAX_VOICES = 64

BUILTIN_VOICE_META = {
    "male_hello.wav": ("آقا · صمیمی", "صدای مرد، لحن آرام و دوستانه"),
    "female_narration.wav": ("بانو · روایت", "صدای زن، روایت‌گر"),
    "male_news.wav": ("آقا · خبری", "صدای مرد، لحن خبرگزاری"),
}

app = FastAPI(title="پارسی‌گو — Persian TTS demo")

_engine = None
_engine_lock = threading.Lock()
_audio_store: dict[str, dict] = {}
_store_lock = threading.Lock()


def save_audio_item(audio_id: str, audio: np.ndarray, sr: int, meta: dict) -> None:
    """Encodes and caches synthesized audio in MP3 or WAV format."""
    fmt = (meta.get("format") or "mp3").lower()
    sf_fmt = "MP3" if fmt == "mp3" else "WAV"
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format=sf_fmt)
    data = buf.getvalue()
    item = {
        "audio": audio,
        "sr": sr,
        "format": fmt,
        "duration": len(audio) / sr,
        "cache": {fmt: data},
        "wav": data if fmt == "wav" else None,
        **meta,
    }
    with _store_lock:
        _audio_store[audio_id] = item

# punctuation-aware phrase splitting and the pause lengths live with the
# engine (single source of truth for where pauses fall and how long they
# last): PAUSE_S is the sentence-final pause — a real reader stops at a
# period, not just breathes (comma is 0.16 in the engine)
from tts_onnx import PKG, SENTENCE_GAP as PAUSE_S, plan_phrases, pack_phrases  # noqa: E402

# the model's audio format, from the same manifest key the engine reads — a
# future model with a different rate flows through the resample/pause math
# here instead of silently writing wrong-rate WAVs. Deliberately read from
# the static manifest, NOT from get_engine(), so a voice upload never
# triggers a full engine load.
SR: int = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))["constants"]["sample_rate"]


def get_engine():
    global _engine
    if _engine is None:
        from tts_onnx import OnnxTts

        _engine = OnnxTts()
        if not hasattr(_engine, "_g2p"):
            from g2p_onnx import OnnxG2P

            _engine._g2p = OnnxG2P(_engine.dir)
    return _engine


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!؟])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def list_voices() -> list[dict]:
    out = []
    for f in sorted((BASE / "voices").glob("*.wav")):
        name, desc = BUILTIN_VOICE_META.get(f.name, (f.stem, ""))
        out.append({"id": f.name, "name": name, "desc": desc, "builtin": True})
    for f in sorted(UPLOAD_DIR.glob("*.wav")):
        out.append({
            "id": f"upload:{f.name}", "name": f.name[:22],
            "desc": "صدای بارگذاری‌شده", "builtin": False,
        })
    return out[:MAX_VOICES]


def voice_path(voice_id: str) -> Path:
    if voice_id.startswith("upload:"):
        p = UPLOAD_DIR / Path(voice_id[7:]).name
    else:
        p = BASE / "voices" / Path(voice_id).name
    if not p.is_file():
        raise HTTPException(404, "voice not found")
    return p


class TTSRequest(BaseModel):
    text: str
    voice: str
    engine: str = "local"
    api_key: Optional[str] = None
    pace: float = 1.0
    mode: str = "split"   # split: pause at every punctuation | pack: long breaths
    format: str = "mp3"   # default to mp3


class PhonemizeRequest(BaseModel):
    text: str
    mode: str = "split"


class PhonemeTTSRequest(BaseModel):
    phonemes: str
    voice: str
    pace: float = 1.0
    format: str = "mp3"


@app.get("/")
def index():
    return FileResponse(WEB)


@app.get("/api/engines")
def engines():
    return {"engines": get_engine_manager().list_engines()}


@app.get("/api/voices")
def voices(engine: Optional[str] = None):
    if engine == "gemini":
        return {"voices": get_engine_manager().get_engine("gemini").list_voices()}
    if engine == "all":
        return {"voices": list_voices() + get_engine_manager().get_engine("gemini").list_voices()}
    return {"voices": list_voices()}


@app.get("/api/config")
def config():
    """UI bootstrap values — the text cap lives here, not hardcoded in the HTML."""
    return {
        "max_text": MAX_TEXT,
        "max_phonemes": MAX_PHONEMES,
        "has_gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
        "default_engine": "local",
        "default_format": "mp3",
    }


@app.post("/api/upload-text")
async def upload_text(file: UploadFile = File(...)):
    """Upload a .txt document for long-text TTS processing."""
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = raw.decode("cp1256")
        except UnicodeDecodeError:
            raise HTTPException(400, "فایل متنی معتبر UTF-8 یا Windows-1256 نیست")
    content = content.strip()
    if not content:
        raise HTTPException(400, "محتوای فایل متنی خالی است")
    return {
        "text": content,
        "chars": len(content),
        "words": len(content.split()),
        "filename": file.filename or "uploaded.txt",
    }


@app.post("/api/phonemize")
def phonemize(req: PhonemizeRequest):
    """Convert Persian text to editable phonemes without generating audio."""
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "متن خالی است")
    if len(text) > MAX_TEXT:
        raise HTTPException(400, f"متن طولانی است (حداکثر {MAX_TEXT} نویسه)")
    if req.mode not in ("split", "pack"):
        raise HTTPException(400, "حالت گفتار باید split یا pack باشد")

    engine = get_engine()
    phonemes_all = []
    with _engine_lock:
        for sent in split_sentences(text):
            try:
                plan = plan_phrases(sent, engine._g2p, engine.sp)
            except ValueError as e:
                raise HTTPException(400, "متن فارسی معتبری پیدا نشد") from e
            if req.mode == "pack":
                plan = pack_phrases(plan)
            phonemes_all.extend(p.replace("1", "") for p, _ in plan)

    phonemes = " ".join(phonemes_all).strip()
    if not phonemes:
        raise HTTPException(400, "فونمی تولید نشد")
    return {"phonemes": phonemes}


@app.post("/api/tts-phonemes")
def tts_phonemes(req: PhonemeTTSRequest):
    """Generate speech directly from a user-edited phoneme string."""
    phonemes = req.phonemes.strip()
    if not phonemes:
        raise HTTPException(400, "فونم خالی است")
    if len(phonemes) > MAX_PHONEMES:
        raise HTTPException(400, f"فونم طولانی است (حداکثر {MAX_PHONEMES} نویسه)")
    if any("\u0600" <= ch <= "\u06FF" for ch in phonemes):
        raise HTTPException(400, "در کادر فونم فقط فونم لاتین وارد کنید؛ متن فارسی را در کادر متن بنویسید")

    engine = get_engine()
    pace = float(min(max(req.pace, 0.6), 1.5))
    with _engine_lock:
        audio = engine.synthesize(phonemes, voice_path(req.voice), pace=pace)

    if len(audio) == 0:
        raise HTTPException(400, "صوتی تولید نشد")
    duration = len(audio) / SR
    audio_id = uuid.uuid4().hex[:12]
    save_audio_item(
        audio_id,
        audio,
        SR,
        {
            "text": phonemes,
            "voice": req.voice,
            "phonemes": phonemes,
            "engine": "local",
            "format": req.format,
        },
    )
    return {
        "id": audio_id,
        "phonemes": phonemes,
        "duration": round(duration, 2),
        "pace": pace,
        "format": req.format.lower(),
        "mode": "manual-phonemes",
        "sentences": 1,
        "elapsed": None,
    }


@app.post("/api/tts")
def tts(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "متن خالی است")
    if len(text) > MAX_TEXT:
        raise HTTPException(400, f"متن طولانی است (حداکثر {MAX_TEXT} نویسه)")

    pace = float(min(max(req.pace, 0.6), 1.5))

    # Cloud Google Gemini Engine path
    if req.engine == "gemini":
        gemini_engine = get_engine_manager().get_engine("gemini")
        try:
            audio, sr_out, meta = gemini_engine.synthesize(
                text=text,
                voice=req.voice,
                pace=pace,
                api_key=req.api_key,
            )
        except Exception as e:
            raise HTTPException(400, f"خطای موتور ابری گوگل: {str(e)}")

        duration = len(audio) / sr_out
        audio_id = uuid.uuid4().hex[:12]
        save_audio_item(
            audio_id,
            audio,
            sr_out,
            {
                "text": text,
                "voice": req.voice,
                "phonemes": "— (تولید مستقیم با مدل ابری Gemini)",
                "engine": "gemini",
                "format": req.format,
            },
        )
        return {
            "id": audio_id,
            "phonemes": "— (تولید مستقیم با مدل ابری Gemini)",
            "duration": round(duration, 2),
            "pace": pace,
            "format": req.format.lower(),
            "mode": "gemini-cloud",
            "sentences": meta.get("chunks_count", 1),
            "engine": "gemini",
            "elapsed": None,
        }

    # Local ONNX Engine path
    engine = get_engine()
    if req.mode not in ("split", "pack"):
        raise HTTPException(400, "حالت گفتار باید split یا pack باشد")
    phonemes_all, chunks = [], []

    with _engine_lock:
        for sent in split_sentences(text):
            # punctuation-aware plan: each phrase (comma/dash/colon-delimited)
            # is a pause unit with its own gap, and short lead-ins ending in
            # strong punctuation ("سؤال اصلی:") stay standalone
            try:
                plan = plan_phrases(sent, engine._g2p, engine.sp)
            except ValueError:
                continue
            if req.mode == "pack":
                plan = pack_phrases(plan)
            if not plan:
                continue
            # model card: retry a runaway once (stochastic; 2nd attempt usually ends)
            tokens = sum(len(engine.sp.encode(p.replace("1", ""), out_type=int))
                         for p, _ in plan)
            cap = tokens / engine.tps_est + engine.gen_pad + 1
            for attempt in range(2):
                audio = engine.synthesize(plan, voice_path(req.voice), pace=pace)
                if len(audio) / SR <= cap + 2.0:  # multi-chunk texts run longer
                    break
            phonemes_all.append(" ".join(p.replace("1", "") for p, _ in plan))
            chunks.append(audio)
            chunks.append(np.zeros(int(PAUSE_S / pace * SR), dtype=audio.dtype))

    if not chunks:
        raise HTTPException(400, "متنی برای ساخت صدا پیدا نشد")
    audio = np.concatenate(chunks[:-1])  # drop trailing pause
    duration = len(audio) / SR
    audio_id = uuid.uuid4().hex[:12]
    save_audio_item(
        audio_id,
        audio,
        SR,
        {
            "text": text,
            "voice": req.voice,
            "phonemes": " ".join(phonemes_all),
            "engine": "local",
            "format": req.format,
        },
    )
    return {
        "id": audio_id,
        "phonemes": " ".join(phonemes_all),
        "duration": round(duration, 2),
        "pace": pace,
        "format": req.format.lower(),
        "mode": req.mode,
        "sentences": len(phonemes_all),
        "engine": "local",
        "elapsed": None,
    }


@app.post("/api/tts-stream")
def tts_stream(req: TTSRequest):
    """Streams live synthesis progress events via Server-Sent Events (SSE)."""
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "متن خالی است")
    if len(text) > MAX_TEXT:
        raise HTTPException(400, f"متن طولانی است (حداکثر {MAX_TEXT} نویسه)")

    pace = float(min(max(req.pace, 0.6), 1.5))
    event_q: queue.Queue = queue.Queue()

    def progress_cb(data: dict) -> None:
        event_q.put({"type": "progress", **data})

    def worker() -> None:
        try:
            manager = get_engine_manager()
            engine_id = (req.engine or "local").lower()
            engine = manager.get_engine(engine_id)

            kwargs = {"pace": pace, "progress_callback": progress_cb}
            if engine_id == "gemini":
                kwargs["api_key"] = req.api_key
            else:
                kwargs["mode"] = req.mode

            audio, sr_out, meta = engine.synthesize(text=text, voice=req.voice, **kwargs)

            duration = len(audio) / sr_out
            audio_id = uuid.uuid4().hex[:12]
            save_audio_item(
                audio_id,
                audio,
                sr_out,
                {
                    "text": text,
                    "voice": req.voice,
                    "phonemes": meta.get("phonemes", "—"),
                    "engine": engine_id,
                    "format": req.format,
                },
            )
            event_q.put({
                "type": "complete",
                "id": audio_id,
                "duration": round(duration, 2),
                "pace": pace,
                "format": req.format.lower(),
                "engine": engine_id,
                "phonemes": meta.get("phonemes", "—"),
                "sentences": meta.get("sentences", meta.get("chunks_count", 1)),
            })
        except Exception as e:
            event_q.put({"type": "error", "message": str(e)})
        finally:
            event_q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_generator():
        while True:
            item = event_q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/audio/{audio_id}")
def audio(audio_id: str, format: Optional[str] = None):
    with _store_lock:
        item = _audio_store.get(audio_id)
    if item is None:
        raise HTTPException(404, "not found")

    fmt = (format or item.get("format") or "mp3").lower()
    if fmt not in ("mp3", "wav"):
        fmt = "mp3"

    cache = item.setdefault("cache", {})
    if fmt not in cache:
        audio_data = item.get("audio")
        sr = item.get("sr", SR)
        if audio_data is not None:
            buf = io.BytesIO()
            sf.write(buf, audio_data, sr, format="MP3" if fmt == "mp3" else "WAV")
            cache[fmt] = buf.getvalue()
        elif item.get("wav") is not None:
            if fmt == "wav":
                cache["wav"] = item["wav"]
            else:
                data_wav, sr_wav = sf.read(io.BytesIO(item["wav"]))
                buf = io.BytesIO()
                sf.write(buf, data_wav, sr_wav, format="MP3")
                cache["mp3"] = buf.getvalue()

    media_type = "audio/mpeg" if fmt == "mp3" else "audio/wav"
    ext = "mp3" if fmt == "mp3" else "wav"
    return Response(
        content=cache[fmt],
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="parsigo_{audio_id}.{ext}"'},
    )


@app.post("/api/voice/upload")
async def upload_voice(file: UploadFile = File(...)):
    import scipy.signal as sig

    data = await file.read()
    try:
        wav, sr = sf.read(io.BytesIO(data))
    except Exception:
        raise HTTPException(400, "فایل صوتی خوانده نشد — WAV پیشنهاد می‌شود")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    wav = wav.astype(np.float32)
    if sr != SR:
        g = np.gcd(int(sr), SR)
        wav = sig.resample_poly(wav, SR // g, sr // g).astype(np.float32)
    if len(wav) < SR:  # < 1 s is too short to clone
        raise HTTPException(400, "صدای مرجع باید حداقل ۱ ثانیه باشد")
    wav = wav[: 5 * SR]  # model card: prompts beyond 5 s are out of distribution

    vid = f"upload:{uuid.uuid4().hex[:8]}.wav"
    sf.write(UPLOAD_DIR / vid[7:], wav, SR, format="WAV")
    return {"id": vid, "name": vid[7:], "seconds": round(len(wav) / SR, 1)}


# ---------- Batch Processing & Audiobook Endpoints ----------

class BatchParseRequest(BaseModel):
    text: Optional[str] = None
    chunk_words: Optional[int] = 1200


class BatchCreateRequest(BaseModel):
    title: Optional[str] = "کتاب صوتی"
    chapters: List[Dict[str, Any]]
    engine: str = "local"
    voice: str = "male_hello.wav"
    format: str = "mp3"
    pace: float = 1.0
    api_key: Optional[str] = None


@app.post("/api/batch/parse-chapters")
def api_batch_parse_chapters(req: BatchParseRequest):
    """Parses full book text into chapters using intelligent headings and fallback chunking."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "متن ورودی خالی است")
    chunk_words = req.chunk_words or 1200
    chapters = parse_text_into_chapters(text, default_chunk_words=chunk_words)
    title = extract_book_title(text, default="کتاب صوتی")
    total_words = sum(c["words"] for c in chapters)
    total_chars = sum(c["chars"] for c in chapters)
    total_dur = sum(c["estimated_duration"] for c in chapters)
    return {
        "title": title,
        "chapters": chapters,
        "total_words": total_words,
        "total_chars": total_chars,
        "total_estimated_duration": round(total_dur, 1),
    }


@app.post("/api/batch/parse-files")
async def api_batch_parse_files(files: List[UploadFile] = File(...)):
    """Accepts multiple uploaded text files and parses each into a chapter."""
    file_data: List[Tuple[str, str]] = []
    for f in files:
        raw = await f.read()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = raw.decode("cp1256")
            except UnicodeDecodeError:
                continue
        if content.strip():
            file_data.append((f.filename or "chapter.txt", content))
    if not file_data:
        raise HTTPException(400, "هیچ فایل متنی معتبری یافت نشد")
    chapters = parse_files_into_chapters(file_data)
    total_words = sum(c["words"] for c in chapters)
    total_chars = sum(c["chars"] for c in chapters)
    total_dur = sum(c["estimated_duration"] for c in chapters)
    title = Path(file_data[0][0]).stem.replace("_", " ") if file_data else "کتاب صوتی"
    return {
        "title": title,
        "chapters": chapters,
        "total_words": total_words,
        "total_chars": total_chars,
        "total_estimated_duration": round(total_dur, 1),
    }


@app.post("/api/batch/create")
def api_batch_create(req: BatchCreateRequest):
    """Enqueues an asynchronous batch audiobook production job."""
    if not req.chapters:
        raise HTTPException(400, "لیست فصول خالی است")
    fmt = (req.format or "mp3").lower().strip()
    if fmt not in ("mp3", "wav"):
        raise HTTPException(400, "فرمت صوتی نامعتبر است (تنها mp3 یا wav مجاز است)")

    valid_chapters = []
    for idx, ch in enumerate(req.chapters, 1):
        txt = (ch.get("text") or "").strip()
        if txt:
            valid_chapters.append({
                "title": ch.get("title") or f"فصل {idx}",
                "text": txt,
            })
    if not valid_chapters:
        raise HTTPException(400, "هیچ متنی در فصول یافت نشد")

    manager = get_batch_manager()
    job = manager.create_job(
        title=req.title or "کتاب صوتی",
        chapters=valid_chapters,
        engine=req.engine or "local",
        voice=req.voice or "male_hello.wav",
        audio_format=fmt,
        pace=float(min(max(req.pace, 0.6), 1.5)),
        api_key=req.api_key,
    )
    return {
        "job_id": job.job_id,
        "status": job.status,
        "total_chapters": len(job.chapters),
    }


@app.get("/api/batch/jobs")
def api_batch_jobs():
    """Lists all batch jobs and their statuses."""
    return {"jobs": get_batch_manager().list_jobs()}


@app.get("/api/batch/status/{job_id}")
def api_batch_status(job_id: str):
    """Returns the current state and per-chapter progress of a batch job."""
    manager = get_batch_manager()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "کار دسته‌ای یافت نشد")
    return job.to_dict()


@app.get("/api/batch/stream/{job_id}")
async def api_batch_stream(job_id: str):
    """Streams live batch progress and ETA updates via Server-Sent Events (SSE)."""
    manager = get_batch_manager()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "کار دسته‌ای یافت نشد")

    event_q = manager.subscribe(job_id)

    async def event_generator():
        try:
            snapshot = {"type": "snapshot", "job": job.to_dict()}
            yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"

            if job.status in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'done', 'job': job.to_dict()}, ensure_ascii=False)}\n\n"
                return

            while True:
                try:
                    ev = event_q.get_nowait()
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    if ev.get("type") in ("job_completed", "job_failed", "job_cancelled"):
                        break
                except queue.Empty:
                    await asyncio.sleep(0.35)
                    if job.status in ("completed", "failed", "cancelled"):
                        while True:
                            try:
                                ev = event_q.get_nowait()
                                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                            except queue.Empty:
                                break
                        yield f"data: {json.dumps({'type': 'done', 'job': job.to_dict()}, ensure_ascii=False)}\n\n"
                        break
        finally:
            manager.unsubscribe(job_id, event_q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/batch/cancel/{job_id}")
def api_batch_cancel(job_id: str):
    """Requests cancellation of a batch audiobook job."""
    manager = get_batch_manager()
    success = manager.cancel_job(job_id)
    if not success:
        raise HTTPException(404, "کار دسته‌ای یافت نشد")
    return {"job_id": job_id, "status": "cancelled"}


@app.get("/api/batch/download/{job_id}")
def api_batch_download(job_id: str, type: str = "zip"):
    """Downloads the final packaged audiobook (ZIP archive or merged audio file)."""
    manager = get_batch_manager()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "کار دسته‌ای یافت نشد")

    if type.lower() == "merged":
        if not job.merged_path or not os.path.exists(job.merged_path):
            raise HTTPException(404, "فایل صوتی یکپارچه هنوز آماده نشده یا یافت نشد")
        ext = job.format.lower()
        media_type = "audio/mpeg" if ext == "mp3" else "audio/wav"
        fname = Path(job.merged_path).name
        return FileResponse(job.merged_path, media_type=media_type, filename=fname)
    else:
        if not job.zip_path or not os.path.exists(job.zip_path):
            raise HTTPException(404, "فایل فشرده فصول هنوز آماده نشده یا یافت نشد")
        fname = Path(job.zip_path).name
        return FileResponse(job.zip_path, media_type="application/zip", filename=fname)


@app.get("/api/batch/chapter/{job_id}/{chapter_index}")
def api_batch_chapter_audio(job_id: str, chapter_index: int):
    """Streams or downloads an individual chapter's generated audio file."""
    manager = get_batch_manager()
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "کار دسته‌ای یافت نشد")

    chapter = next((c for c in job.chapters if c.index == chapter_index), None)
    if not chapter or not chapter.audio_file or not os.path.exists(chapter.audio_file):
        raise HTTPException(404, "صوت این فصل هنوز آماده نیست یا یافت نشد")

    ext = job.format.lower()
    media_type = "audio/mpeg" if ext == "mp3" else "audio/wav"
    fname = Path(chapter.audio_file).name
    return FileResponse(chapter.audio_file, media_type=media_type, filename=fname)



if __name__ == "__main__":
    # defaults keep the demo loopback-only; 0.0.0.0 exposes an
    # unauthenticated demo (disk-writing upload included) — opt in
    host = os.environ.get("PARSIGO_HOST", "127.0.0.1")
    port = int(os.environ.get("PARSIGO_PORT", "8000"))
    print("loading engine (first request may take a moment)...")
    get_engine()
    print(f"demo:  http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
