"""
ابزار تبدیل متن یا فایل متنی فارسی به گفتار (WAV)
سازگار با CPU و موتور ONNX پارسی‌گو
"""
import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# اضافه کردن دایرکتوری scripts به sys.path جهت ایمپورت ماژول‌های موتور ONNX
BASE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import soundfile as sf
import shutil
import time
from tts_onnx import synthesize_text, ONNX_DIR
from tts_engine import get_engine_manager
from chapter_parser import (
    extract_book_title,
    natural_sort_key,
    parse_files_into_chapters,
    parse_text_into_chapters,
)
from batch_manager import get_batch_manager


def text_to_speech(
    text: str,
    voice: str = "voices/male_hello.wav",
    output_file: str = "output/result.wav",
    pack: bool = True,
    engine: str = "local",
    api_key: str | None = None,
) -> str:
    """
    تبدیل متن به فایل صوتی گفتار فارسی با موتور محلی یا ابری.

    :param text: متن فارسی ورودی
    :param voice: مسیر فایل صدای مرجع محلی یا نام صدای ابری (Kore, Puck, ...)
    :param output_file: مسیر ذخیره‌سازی فایل صوتی خروجی
    :param pack: ادغام عبارات جهت مکث‌های طبیعی (موتور محلی)
    :param engine: موتور سنتز ('local' یا 'gemini')
    :param api_key: کلید API جمینای در صورت استفاده از موتور ابری
    :return: مسیر فایل ذخیره‌شده خروجی
    """
    out_dir = os.path.dirname(os.path.abspath(output_file))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if engine == "gemini":
        gemini_engine = get_engine_manager().get_engine("gemini")
        audio, sr, _ = gemini_engine.synthesize(
            text=text,
            voice=voice,
            api_key=api_key,
        )
    else:
        if not os.path.exists(voice):
            raise FileNotFoundError(f"فایل صدای مرجع یافت نشد: {voice}")

        audio, sr = synthesize_text(
            text=text,
            ref_wav=voice,
            pack=pack,
            model_dir=ONNX_DIR,
        )

    sf.write(output_file, audio, sr)
    return output_file


def process_audiobook_cli(args, selected_voice: str):
    """Handles batch directory or full audiobook text conversion via CLI."""
    chapters = []
    title = args.title

    if args.batch_dir:
        b_path = Path(args.batch_dir)
        if not b_path.is_dir():
            print(f"خطا: پوشه '{args.batch_dir}' یافت نشد.", file=sys.stderr)
            sys.exit(1)
        txt_files = sorted(b_path.glob("*.txt"), key=lambda p: natural_sort_key(p.name))
        if not txt_files:
            print(f"خطا: هیچ فایل .txt در پوشه '{args.batch_dir}' یافت نشد.", file=sys.stderr)
            sys.exit(1)
        file_tuples = []
        for tf in txt_files:
            try:
                content = tf.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                content = tf.read_text(encoding="cp1256").strip()
            if content:
                file_tuples.append((tf.name, content))
        chapters = parse_files_into_chapters(file_tuples)
        if not title:
            title = b_path.name.replace("_", " ")

    elif args.audiobook_text:
        a_path = Path(args.audiobook_text)
        if not a_path.is_file():
            print(f"خطا: فایل کتاب '{args.audiobook_text}' یافت نشد.", file=sys.stderr)
            sys.exit(1)
        try:
            content = a_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            content = a_path.read_text(encoding="cp1256").strip()
        if not content:
            print("خطا: محتوای فایل کتاب صوتی خالی است.", file=sys.stderr)
            sys.exit(1)
        chapters = parse_text_into_chapters(content)
        if not title:
            title = extract_book_title(content, default=a_path.stem.replace("_", " "))

    if not chapters:
        print("خطا: فصلی برای پردازش شناسایی نشد.", file=sys.stderr)
        sys.exit(1)

    audio_fmt = (args.audio_format or "mp3").lower()
    total_words = sum(c["words"] for c in chapters)
    print(f"شروع تبدیل کتاب صوتی: «{title}» ({len(chapters)} فصل · {total_words} واژه)")
    print(f"موتور: [{args.engine}] · صدا: [{selected_voice}] · فرمت: [{audio_fmt.upper()}]")

    manager = get_batch_manager()
    job = manager.create_job(
        title=title,
        chapters=chapters,
        engine=args.engine,
        voice=selected_voice,
        audio_format=audio_fmt,
        pace=float(args.pace),
        api_key=args.api_key,
    )

    last_pct = -1
    while job.status in ("queued", "processing"):
        curr_pct = int(job.total_progress)
        if curr_pct != last_pct:
            last_pct = curr_pct
            eta_txt = f"~{int(job.eta_seconds)}s" if job.eta_seconds else "در حال محاسبه"
            print(f"پیشرفت کل: {curr_pct}% | تخمین زمان باقی‌مانده: {eta_txt}", flush=True)
        time.sleep(0.4)

    if job.status == "completed":
        print(f"\nتبدیل کتاب صوتی با موفقیت پایان یافت!")
        print(f"مدت زمان کل: {job.total_duration:.1f} ثانیه")
        print(f"مسیر ذخیره فصول: {job.output_dir}")
        if job.merged_path:
            print(f"فایل صوتی یکپارچه: {job.merged_path}")
        if job.zip_path:
            print(f"آرشیو فشرده ZIP: {job.zip_path}")

        if args.output_zip and job.zip_path and os.path.exists(job.zip_path):
            out_zip = Path(args.output_zip)
            out_zip.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(job.zip_path, str(out_zip))
            print(f"فایل ZIP به مقصد کپی شد: {out_zip}")

        if getattr(args, "output", None) and args.output != "output/speech.wav" and job.merged_path and os.path.exists(job.merged_path):
            out_merged = Path(args.output)
            out_merged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(job.merged_path, str(out_merged))
            print(f"فایل صوتی یکپارچه به مقصد کپی شد: {out_merged}")

        if args.play and job.merged_path:
            print("در حال پخش فایل کتاب صوتی...")
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.abspath(job.merged_path))
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", os.path.abspath(job.merged_path)])
            except Exception as e:
                print(f"خطا در پخش: {e}", file=sys.stderr)
    else:
        print(f"خطا در پردازش کتاب صوتی: وضعیت [{job.status}], خطا: {job.error}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="تبدیل متن یا فایل متنی فارسی به گفتار (Persian TTS pure-ONNX & Audiobook Studio)"
    )
    parser.add_argument("--text", "-t", type=str, help="متن مستقیم ورودی")
    parser.add_argument("--file", "-f", type=str, help="مسیر فایل متنی utf-8")
    parser.add_argument(
        "--batch-dir",
        type=str,
        help="مسیر پوشه شامل چندین فایل متنی جهت تبدیل دسته‌ای فصول",
    )
    parser.add_argument(
        "--audiobook-text",
        type=str,
        help="مسیر فایل متنی یکپارچه کتاب با تفکیک خودکار فصول",
    )
    parser.add_argument(
        "--output-zip",
        type=str,
        help="مسیر ذخیره مستقیم پکیج کتاب صوتی در قالب فایل ZIP",
    )
    parser.add_argument(
        "--audio-format",
        choices=["mp3", "wav"],
        default=None,
        help="فرمت فایل‌های صوتی خروجی (پیش‌فرض: mp3 برای کتاب صوتی، wav برای تک‌فایل)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="عنوان کتاب صوتی (در صورت عدم تعیین، خودکار استخراج می‌شود)",
    )
    parser.add_argument(
        "--pace",
        type=float,
        default=1.0,
        help="سرعت گفتار (پیش‌فرض: 1.0)",
    )
    parser.add_argument(
        "--voice",
        "-v",
        default="voices/male_hello.wav",
        help="مسیر فایل صدای مرجع (پیش‌فرض voices/male_hello.wav)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="output/speech.wav",
        help="مسیر ذخیره خروجی wav (پیش‌فرض output/speech.wav)",
    )
    parser.add_argument(
        "--no-pack",
        action="store_true",
        help="غیرفعالسازی pack (ادغام عبارات)",
    )
    parser.add_argument(
        "--engine",
        "-e",
        choices=["local", "gemini"],
        default="local",
        help="موتور سنتز صدا: 'local' (پیش‌فرض ONNX) یا 'gemini' (ابری گوگل)",
    )
    parser.add_argument(
        "--gemini-voice",
        choices=["Kore", "Puck", "Charon", "Fenrir", "Aoede"],
        default="Kore",
        help="نام صدای پیش‌ساخته جمینای در حالت ابری (پیش‌فرض Kore)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="کلید API گوگل جمینای (یا مقداردهی متغیر محیطی GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--play",
        "-p",
        action="store_true",
        help="پخش خودکار فایل صوتی پس از تولید",
    )

    args = parser.parse_args()
    selected_voice = args.gemini_voice if args.engine == "gemini" else args.voice

    # Batch / Audiobook mode
    if args.batch_dir or args.audiobook_text:
        process_audiobook_cli(args, selected_voice)
        return

    # Single-text mode
    if args.file:
        if not os.path.exists(args.file):
            print(f"خطا: فایل ورودی '{args.file}' یافت نشد.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read().strip()
    elif args.text:
        content = args.text.strip()
    else:
        print("خطا: لطفاً متن ورودی را با --text یا --file یا حالت کتاب را با --audiobook-text / --batch-dir مشخص کنید.", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not content:
        print("خطا: متن ورودی خالی است.", file=sys.stderr)
        sys.exit(1)

    print(f"در حال پردازش متن با موتور [{args.engine}] (طول: {len(content)} کاراکتر)...")
    pack = not args.no_pack
    out = text_to_speech(
        content,
        voice=selected_voice,
        output_file=args.output,
        pack=pack,
        engine=args.engine,
        api_key=args.api_key,
    )
    print(f"فایل صوتی با موفقیت ذخیره شد: {out}")

    if args.play:
        print("در حال پخش صدا...")
        try:
            if sys.platform == "win32":
                os.startfile(os.path.abspath(out))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", os.path.abspath(out)])
        except Exception as e:
            print(f"خطا در پخش خودکار: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

