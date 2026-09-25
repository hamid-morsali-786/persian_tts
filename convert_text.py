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
from tts_onnx import synthesize_text, ONNX_DIR


def text_to_speech(
    text: str,
    voice: str = "voices/male_hello.wav",
    output_file: str = "output/result.wav",
    pack: bool = True,
) -> str:
    """
    تبدیل متن به فایل صوتی گفتار فارسی.

    :param text: متن فارسی ورودی
    :param voice: مسیر فایل صدای مرجع (WAV)
    :param output_file: مسیر ذخیره‌سازی فایل صوتی خروجی
    :param pack: ادغام عبارات جهت مکث‌های طبیعی
    :return: مسیر فایل ذخیره‌شده خروجی
    """
    if not os.path.exists(voice):
        raise FileNotFoundError(f"فایل صدای مرجع یافت نشد: {voice}")

    # ایجاد خودکار دایرکتوری خروجی در صورت عدم وجود
    out_dir = os.path.dirname(os.path.abspath(output_file))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # سنتز صدا با استفاده از موتور ONNX
    audio, sr = synthesize_text(
        text=text,
        ref_wav=voice,
        pack=pack,
        model_dir=ONNX_DIR,
    )

    sf.write(output_file, audio, sr)
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="تبدیل متن یا فایل متنی فارسی به گفتار (Persian TTS pure-ONNX)"
    )
    parser.add_argument("--text", "-t", type=str, help="متن مستقیم ورودی")
    parser.add_argument("--file", "-f", type=str, help="مسیر فایل متنی utf-8")
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
        "--play",
        "-p",
        action="store_true",
        help="پخش خودکار فایل صوتی پس از تولید",
    )

    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"خطا: فایل ورودی '{args.file}' یافت نشد.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read().strip()
    elif args.text:
        content = args.text.strip()
    else:
        print("خطا: لطفاً متن ورودی را با --text یا مسیر فایل را با --file مشخص کنید.", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not content:
        print("خطا: متن ورودی خالی است.", file=sys.stderr)
        sys.exit(1)

    print(f"در حال پردازش متن (طول: {len(content)} کاراکتر)...")
    pack = not args.no_pack
    out = text_to_speech(content, voice=args.voice, output_file=args.output, pack=pack)
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
