"""
Core TTS engine abstraction and implementations (Local ONNX & Google Gemini Cloud).
Provides Strategy Pattern for pluggable speech synthesis engines.
"""
from abc import ABC, abstractmethod
import base64
import io
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

BASE_DIR = Path(__file__).resolve().parent.parent
VOICES_DIR = BASE_DIR / "voices"
UPLOADS_DIR = BASE_DIR / "uploads" / "voices"


class BaseTTSEngine(ABC):
    """Abstract base class for all TTS engines."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique identifier of the engine."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable display name in Persian/English."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if dependencies and resources for this engine are present."""
        pass

    @abstractmethod
    def list_voices(self) -> List[Dict[str, Any]]:
        """Returns list of available voices."""
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str,
        pace: float = 1.0,
        **kwargs: Any,
    ) -> Tuple[np.ndarray, int, Dict[str, Any]]:
        """
        Synthesizes text into audio.

        Returns:
            Tuple of (audio_array: np.ndarray, sample_rate: int, meta: dict)
        """
        pass


class LocalOnnxEngine(BaseTTSEngine):
    """Pure-ONNX offline TTS engine with voice cloning."""

    def __init__(self) -> None:
        self._engine: Optional[Any] = None
        self._lock = threading.Lock()

    @property
    def engine_id(self) -> str:
        return "local"

    @property
    def display_name(self) -> str:
        return "موتور محلی (Pure-ONNX / آفلاین)"

    def is_available(self) -> bool:
        model_manifest = BASE_DIR / "model" / "onnx" / "manifest.json"
        return model_manifest.exists()

    def _ensure_loaded(self) -> Any:
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is None:
                from tts_onnx import OnnxTts
                from g2p_onnx import OnnxG2P

                eng = OnnxTts()
                if not hasattr(eng, "_g2p"):
                    eng._g2p = OnnxG2P(eng.dir)
                self._engine = eng
        return self._engine

    def list_voices(self) -> List[Dict[str, Any]]:
        builtin_meta = {
            "male_hello.wav": ("آقا · صمیمی", "صدای مرد، لحن آرام و دوستانه"),
            "female_narration.wav": ("بانو · روایت", "صدای زن، روایت‌گر"),
            "male_news.wav": ("آقا · خبری", "صدای مرد، لحن خبرگزاری"),
        }
        out: List[Dict[str, Any]] = []
        for f in sorted(VOICES_DIR.glob("*.wav")):
            name, desc = builtin_meta.get(f.name, (f.stem, ""))
            out.append({"id": f.name, "name": name, "desc": desc, "builtin": True, "engine": "local"})

        if UPLOADS_DIR.exists():
            for f in sorted(UPLOADS_DIR.glob("*.wav")):
                out.append({
                    "id": f"upload:{f.name}",
                    "name": f.name[:22],
                    "desc": "صدای بارگذاری‌شده (کلون)",
                    "builtin": False,
                    "engine": "local",
                })
        return out

    def resolve_voice_path(self, voice_id: str) -> Path:
        if voice_id.startswith("upload:"):
            p = UPLOADS_DIR / Path(voice_id[7:]).name
        else:
            p = VOICES_DIR / Path(voice_id).name
        if not p.is_file():
            raise FileNotFoundError(f"Voice reference file not found: {p}")
        return p

    def synthesize(
        self,
        text: str,
        voice: str,
        pace: float = 1.0,
        **kwargs: Any,
    ) -> Tuple[np.ndarray, int, Dict[str, Any]]:
        from tts_onnx import plan_phrases, pack_phrases, split_sentences, SENTENCE_GAP

        engine = self._ensure_loaded()
        sr = 24000
        mode = kwargs.get("mode", "split")
        bounded_pace = float(min(max(pace, 0.6), 1.5))
        ref_path = self.resolve_voice_path(voice)

        phonemes_all: List[str] = []
        chunks: List[np.ndarray] = []
        sentences = [s for s in split_sentences(text) if s.strip()]
        total_sents = len(sentences)
        progress_cb = kwargs.get("progress_callback")

        if progress_cb:
            progress_cb({
                "stage": "started",
                "current": 0,
                "total": total_sents,
                "percent": 5,
                "message": "تحلیل ساختار متن و برنامه‌ریزی واج‌شناختی...",
            })

        with self._lock:
            for idx, sent in enumerate(sentences):
                try:
                    plan = plan_phrases(sent, engine._g2p, engine.sp)
                except ValueError:
                    continue
                if mode == "pack":
                    plan = pack_phrases(plan)
                if not plan:
                    continue

                tokens = sum(len(engine.sp.encode(p.replace("1", ""), out_type=int)) for p, _ in plan)
                cap = tokens / engine.tps_est + engine.gen_pad + 1

                audio = np.zeros(0, dtype=np.float32)
                for _ in range(2):
                    audio = engine.synthesize(plan, ref_path, pace=bounded_pace)
                    if len(audio) / sr <= cap + 2.0:
                        break

                phonemes_all.append(" ".join(p.replace("1", "") for p, _ in plan))
                chunks.append(audio)
                chunks.append(np.zeros(int(SENTENCE_GAP / bounded_pace * sr), dtype=audio.dtype))

                if progress_cb:
                    pct = round(10 + (80 * (idx + 1) / max(1, total_sents)), 1)
                    progress_cb({
                        "stage": "synthesizing",
                        "current": idx + 1,
                        "total": total_sents,
                        "percent": pct,
                        "sentence": sent[:60] + ("…" if len(sent) > 60 else ""),
                    })

        if not chunks:
            raise ValueError("No valid speech audio generated from input text.")

        if progress_cb:
            progress_cb({
                "stage": "finalizing",
                "current": total_sents,
                "total": total_sents,
                "percent": 96,
                "message": "یکپارچه‌سازی و مسترینگ نهایی صوت...",
            })

        final_audio = np.concatenate(chunks[:-1])
        meta = {
            "phonemes": " ".join(phonemes_all),
            "sentences": len(phonemes_all),
            "engine": "local",
        }
        return final_audio, sr, meta


def format_gemini_error(err: Exception) -> str:
    """Translates raw Google Gemini exceptions into concise, actionable Persian messages."""
    err_str = str(err)
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
        retry_m = re.search(r"retry in ([\d\.]+s?)", err_str, re.IGNORECASE)
        wait_tip = f" (زمان انتظار: {retry_m.group(1)})" if retry_m else ""
        if "free_tier" in err_str or "limit: 10" in err_str or "10" in err_str:
            return (
                "سهمیه روزانه کلید Gemini شما در پلن رایگان گوگل (Free Tier) به پایان رسیده است "
                f"(محدودیت ۱۰ درخواست در روز).{wait_tip} "
                "پیشنهاد می‌شود از «موتور محلی (Pure ONNX)» که کاملاً آفلاین، رایگان و بدون محدودیت است استفاده فرمایید."
            )
        return f"سقف مجاز نرخ درخواست‌های API گوگل تکمیل شد.{wait_tip} لطفاً کمی بعد امتحان کنید یا از موتور محلی استفاده نمایید."
    if "API_KEY_INVALID" in err_str or "api key not valid" in err_str.lower() or ("400" in err_str and "key" in err_str.lower()):
        return "کلید Google Gemini API نامعتبر است. لطفاً کلید معتبر خود را از Google AI Studio بررسی و وارد نمایید."
    return f"خطای موتور ابری گوگل: {err_str[:200]}"


class GeminiCloudEngine(BaseTTSEngine):
    """Google Gemini Cloud TTS engine (gemini-3.8-flash-tts)."""

    VOICES: List[Dict[str, Any]] = [
        {"id": "Kore", "name": "کوره (Kore)", "desc": "صدای زنانه، آرام و دلنشین", "builtin": True, "engine": "gemini"},
        {"id": "Puck", "name": "پوک (Puck)", "desc": "صدای مردانه، پرانرژی و رسا", "builtin": True, "engine": "gemini"},
        {"id": "Charon", "name": "کارون (Charon)", "desc": "صدای مردانه، بم و رسمی", "builtin": True, "engine": "gemini"},
        {"id": "Fenrir", "name": "فنریر (Fenrir)", "desc": "صدای مردانه، روایت‌گر عمیق", "builtin": True, "engine": "gemini"},
        {"id": "Aoede", "name": "آئوده (Aoede)", "desc": "صدای زنانه، شفاف و رسا", "builtin": True, "engine": "gemini"},
    ]

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    @property
    def engine_id(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "موتور ابری گوگل (Gemini 3.8 Flash TTS)"

    def is_available(self) -> bool:
        try:
            from google import genai
            return True
        except ImportError:
            return False

    def list_voices(self) -> List[Dict[str, Any]]:
        return self.VOICES

    def _split_into_chunks(self, text: str, max_chars: int = 3500) -> List[str]:
        """Splits long text on paragraph and sentence boundaries for cloud TTS."""
        text = text.strip()
        if len(text) <= max_chars:
            return [text]

        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current: List[str] = []
        curr_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if curr_len + len(para) + 2 <= max_chars:
                current.append(para)
                curr_len += len(para) + 2
            else:
                if current:
                    chunks.append("\n\n".join(current))
                    current, curr_len = [], 0
                if len(para) <= max_chars:
                    current.append(para)
                    curr_len = len(para)
                else:
                    sentences = re.split(r"(?<=[.!؟])\s+", para)
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        if curr_len + len(sent) + 1 <= max_chars:
                            current.append(sent)
                            curr_len += len(sent) + 1
                        else:
                            if current:
                                chunks.append(" ".join(current))
                            current = [sent]
                            curr_len = len(sent)

        if current:
            chunks.append("\n\n".join(current))
        return [c for c in chunks if c.strip()]

    def _synthesize_chunk(
        self,
        client: Any,
        text_chunk: str,
        voice: str,
    ) -> Tuple[np.ndarray, int]:
        from google.genai import types

        voice_name = voice if voice in [v["id"] for v in self.VOICES] else "Kore"

        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )

        models_to_try = ["gemini-3.8-flash-tts", "gemini-2.5-flash", "gemini-2.0-flash"]
        response = None
        last_error = None

        for model_name in models_to_try:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=text_chunk,
                        config=config,
                    )
                    break
                except Exception as e:
                    err_msg = str(e)
                    last_error = e
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                        if attempt < 2:
                            import time
                            time.sleep(5 * (3 ** attempt))  # 5s, 15s
                            continue
                        raise RuntimeError(format_gemini_error(e)) from e
                    if "not found" in err_msg.lower() or "not_found" in err_msg.lower() or "404" in err_msg:
                        break  # Break attempt loop, try next model
                    raise RuntimeError(format_gemini_error(e)) from e
            if response is not None:
                break

        if response is None:
            raise RuntimeError(format_gemini_error(last_error) if last_error else "پاسخی از مدل گوگل دریافت نشد.")

        candidates = getattr(response, "candidates", None)
        if not candidates or not candidates[0].content or not candidates[0].content.parts:
            raise RuntimeError("Gemini API returned no candidates or content.")

        audio_part = None
        for part in candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                mime = getattr(part.inline_data, "mime_type", "") or ""
                if mime.startswith("audio/") or not mime:
                    audio_part = part
                    break

        if not audio_part:
            raise RuntimeError("Gemini API response did not contain inline audio data.")

        raw_data = audio_part.inline_data.data
        if isinstance(raw_data, str):
            audio_bytes = base64.b64decode(raw_data)
        elif isinstance(raw_data, (bytes, bytearray)):
            audio_bytes = bytes(raw_data)
        else:
            raise RuntimeError(f"Unexpected audio data format: {type(raw_data)}")

        try:
            wav_data, sr = sf.read(io.BytesIO(audio_bytes))
        except Exception:
            # Fallback for raw 16-bit PCM little-endian audio (Gemini standard 24kHz)
            wav_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            sr = 24000

        if wav_data.ndim > 1:
            wav_data = wav_data.mean(axis=1)
        return wav_data.astype(np.float32), int(sr)

    def synthesize(
        self,
        text: str,
        voice: str,
        pace: float = 1.0,
        **kwargs: Any,
    ) -> Tuple[np.ndarray, int, Dict[str, Any]]:
        active_key = kwargs.get("api_key") or self.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not active_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY or provide api_key in request."
            )

        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "The 'google-genai' package is not installed. Run: pip install google-genai"
            ) from e

        client = genai.Client(api_key=active_key)
        chunks = self._split_into_chunks(text)
        audio_segments: List[np.ndarray] = []
        target_sr = 24000
        total_chunks = len(chunks)
        progress_cb = kwargs.get("progress_callback")

        if progress_cb:
            progress_cb({
                "stage": "started",
                "current": 0,
                "total": total_chunks,
                "percent": 5,
                "message": "اتصال به Google Gemini و ارسال قطعات...",
            })

        for idx, chunk in enumerate(chunks):
            wav_part, sr = self._synthesize_chunk(client, chunk, voice)
            target_sr = sr
            audio_segments.append(wav_part)
            # Add short 200ms natural gap between major chunks
            audio_segments.append(np.zeros(int(0.20 * target_sr), dtype=np.float32))

            if progress_cb:
                pct = round(10 + (80 * (idx + 1) / max(1, total_chunks)), 1)
                progress_cb({
                    "stage": "synthesizing",
                    "current": idx + 1,
                    "total": total_chunks,
                    "percent": pct,
                    "sentence": chunk[:60] + ("…" if len(chunk) > 60 else ""),
                })

        if not audio_segments:
            raise ValueError("No audio segments generated by Gemini.")

        if progress_cb:
            progress_cb({
                "stage": "finalizing",
                "current": total_chunks,
                "total": total_chunks,
                "percent": 96,
                "message": "یکپارچه‌سازی و مسترینگ نهایی صوت...",
            })

        final_audio = np.concatenate(audio_segments[:-1])
        meta = {
            "engine": "gemini",
            "voice": voice,
            "chunks_count": len(chunks),
        }
        return final_audio, target_sr, meta


class TTSEngineManager:
    """Singleton manager for discovering, configuring, and invoking TTS engines."""

    def __init__(self) -> None:
        self._engines: Dict[str, BaseTTSEngine] = {
            "local": LocalOnnxEngine(),
            "gemini": GeminiCloudEngine(),
        }

    def get_engine(self, engine_id: str) -> BaseTTSEngine:
        engine = self._engines.get(engine_id.lower())
        if engine is None:
            raise ValueError(
                f"Unknown TTS engine '{engine_id}'. Available engines: {list(self._engines.keys())}"
            )
        return engine

    def list_engines(self) -> List[Dict[str, Any]]:
        out = []
        for eid, eng in self._engines.items():
            out.append({
                "id": eid,
                "name": eng.display_name,
                "available": eng.is_available(),
                "voices": eng.list_voices(),
            })
        return out


_default_manager: Optional[TTSEngineManager] = None


def get_engine_manager() -> TTSEngineManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = TTSEngineManager()
    return _default_manager
