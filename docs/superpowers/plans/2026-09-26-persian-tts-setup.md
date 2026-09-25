# Persian TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** راه‌اندازی و پیاده‌سازی کامل خط لوله تبدیل متن فارسی به گفتار (Persian TTS) با مدل‌های بهینه‌شده ONNX، کلونینگ صدا، رابط وب، خط فرمان و اسکریپت سفارشی پردازش متون روی پردازنده لپ‌تاپ.

**Architecture:** استفاده از موتور خالص ONNX (`pocket-tts-farsi-v2` و `Homo-GE2PE-Persian`) بدون وابستگی به PyTorch یا کارت گرافیک؛ بهینه‌سازی شده برای اجرای سریع و سبک بر روی CPU لپ‌تاپ با مصرف رم اندک و محدودیت تعداد تردها تا لپ‌تاپ هنگام برنامه‌نویسی کند نشود.

**Tech Stack:** Python 3.12, ONNX Runtime (CPUExecutionProvider), NumPy, SciPy, SoundFile, SentencePiece, FastAPI, Uvicorn, Hugging Face Hub.

**Spec:** [docs/superpowers/specs/2026-09-26-persian-tts-design.md](file:///f:/work_3/ptts/docs/superpowers/specs/2026-09-26-persian-tts-design.md)

## Global Constraints
- اجرای ۱۰۰٪ بر روی CPU لپ‌تاپ برنامه‌نویسی بدون نیاز به GPU یا CUDA
- محدودسازی تردها (`intra_op_num_threads=2`, `inter_op_num_threads=1`) برای جلوگیری از درگیر شدن کامل هسته‌های لپ‌تاپ
- حجم وابستگی‌ها سبک (~۲۰۰ مگابایت) و عدم استفاده از کتابخانه سنگین torch در زمان اجرا
- دانلود مدل‌ها به صورت یکپارچه از `Nimaone/pocket-tts-farsi-v2-onnx` و اجرای کاملاً آفلاین پس از دانلود
- ساختار خروجی استاندارد صوتی: فایل WAV با نرخ نمونه‌برداری ۲۴,۰۰۰ هرتز (24kHz)

---

### Task 1: همگام‌سازی کدهای مخزن اصلی

**Files:**
- Modify: `f:\work_3\ptts/`
- Test: بررسی وجود پوشه‌های `scripts/`, `web/`, `voices/`

**Interfaces:**
- Consumes: مخزن گیت‌هاب `https://github.com/nimaone/persian_tts.git`
- Produces: ساختار کامل فایل‌ها و اسکریپت‌های پروژه در دایرکتوری کاری

- [ ] **Step 1: افزودن ریموت upstream و دریافت فایل‌ها**
افزودن ریموت گیت‌هاب مخزن اصلی و دریافت شاخه `main` بدون حذف مستندات ایجادشده:
```bash
git remote add upstream https://github.com/nimaone/persian_tts.git
git fetch upstream main
git merge upstream/main -m "chore: merge upstream repository code" --allow-unrelated-histories
```

- [ ] **Step 2: اعتبارسنجی ساختار دایرکتوری**
بررسی وجود فایل‌های کلیدی:
```powershell
Test-Path scripts/tts_onnx.py; Test-Path web/index.html; Test-Path voices/male_hello.wav
```
انتظار: بازگشت `True` برای هر سه مسیر.

- [ ] **Step 3: ثبت کامیت**
```bash
git status
```

---

### Task 2: راه‌اندازی محیط مجازی پایتون ۳.۱۲ و نصب پکیج‌های سبک

**Files:**
- Create: `env/` (دایرکتوری محیط مجازی)
- Test: اجرای smoke test برای اطمینان از صحت لود پکیج‌های صوتی و ONNX

**Interfaces:**
- Consumes: مفسر پایتون ۳.۱۲ سیستم (`py -3.12`)
- Produces: محیط مجازی فعال با بسته‌های `onnxruntime`, `soundfile`, `scipy`, `numpy`, `sentencepiece`, `fastapi`, `uvicorn`, `huggingface_hub`

- [ ] **Step 1: ایجاد محیط مجازی با پایتون ۳.۱۲**
```powershell
py -3.12 -m venv env
```

- [ ] **Step 2: ارتقای pip و نصب وابستگی‌های مسیر ONNX**
```powershell
./env/Scripts/python.exe -m pip install --upgrade pip
./env/Scripts/python.exe -m pip install onnxruntime numpy scipy soundfile sentencepiece fastapi uvicorn python-multipart pedalboard "huggingface_hub[cli]"
```

- [ ] **Step 3: اعتبارسنجی نصب پکیج‌ها (Smoke Test)**
اجرای دستور بررسی لود بدون خطا:
```powershell
./env/Scripts/python.exe -c "import onnxruntime, soundfile, scipy, numpy, sentencepiece, fastapi; print('ALL PACKAGES LOADED SUCCESSFULLY')"
```
انتظار: چاپ عبارت `ALL PACKAGES LOADED SUCCESSFULLY`.

---

### Task 3: دریافت مدل‌های یکپارچه ONNX از HuggingFace

**Files:**
- Create: `model/onnx/`
- Test: تست اعتبارسنجی فایل‌های مدل

**Interfaces:**
- Consumes: ریپازیتوری هاگینگ‌فیس `Nimaone/pocket-tts-farsi-v2-onnx`
- Produces: فایل‌های مدل ONNX شامل `flowlm_unified_kv.onnx`, `mimi_decoder.onnx`, `g2p_encoder.onnx`, `g2p_decoder.onnx`, `weights.npz`, `manifest.json`

- [ ] **Step 1: ایجاد پوشه مقصد و دانلود فایل‌های مدل**
دانلود مستقیم فایل‌های مدل با استفاده از اسکریپت پایتون پایدار هاگینگ‌فیس:
```powershell
New-Item -ItemType Directory -Force -Path model/onnx
./env/Scripts/python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Nimaone/pocket-tts-farsi-v2-onnx', local_dir='model/onnx')"
```

- [ ] **Step 2: بررسی یکپارچگی فایل‌های دانلود شده**
```powershell
Get-ChildItem model/onnx | Select-Object Name, Length
```
انتظار: وجود فایل‌های `.onnx` (با حجم‌های تقریبی ده‌ها تا صدها مگابایت)، فایل‌های `weights.npz` و `manifest.json`.

---

### Task 4: تست خط فرمان (CLI) و تولید اولین فایل صوتی فارسی

**Files:**
- Test: `output/cli_test.wav`

**Interfaces:**
- Consumes: `scripts/tts_onnx.py`, `model/onnx/`, `voices/male_hello.wav`
- Produces: فایل صوتی `output/cli_test.wav`

- [x] **Step 1: اجرای تولید گفتار از طریق خط فرمان**
```powershell
New-Item -ItemType Directory -Force -Path output
./env/Scripts/python.exe scripts/tts_onnx.py "سلام و درود، سیستم تبدیل متن فارسی به گفتار با موفقیت روی لپ‌تاپ راه‌اندازی شد." voices/male_hello.wav output/cli_test.wav --pack
```

- [x] **Step 2: اعتبارسنجی فایل صوتی خروجی**
بررسی اینکه فایل ایجاد شده، حجم دارد و مشخصات صوتی آن صحیح است:
```powershell
./env/Scripts/python.exe -c "import soundfile as sf; info = sf.info('output/cli_test.wav'); print(f'Samplerate: {info.samplerate}, Channels: {info.channels}, Duration: {info.duration:.2f}s'); assert info.samplerate == 24000; assert info.duration > 1.0"
```
انتظار: نمایش `Samplerate: 24000` و مدت زمان معتبر بدون بروز Assertion Error.

---

### Task 5: ایجاد اسکریپت سفارشی پایتون برای تبدیل فایل متنی و متون طولانی (`convert_text.py`)

**Files:**
- Create: `convert_text.py`
- Test: `tests/test_convert_text.py`

**Interfaces:**
- Consumes: ورودی متن یا مسیر فایل `.txt` و فایل صدای مرجع
- Produces: فایل WAV یکپارچه تولیدشده با رعایت مکث‌های طبیعی

- [x] **Step 1: نوشتن تست اعتبارسنجی ماژول تبدیل متن**
ایجاد فایل `tests/test_convert_text.py`:
```python
import os
import soundfile as sf
from convert_text import text_to_speech

def test_short_sentence():
    out_path = "output/test_module_short.wav"
    os.makedirs("output", exist_ok=True)
    res = text_to_speech("این یک آزمایش است.", voice="voices/male_hello.wav", output_file=out_path)
    assert os.path.exists(out_path)
    info = sf.info(out_path)
    assert info.samplerate == 24000
    assert info.duration > 0.5
```

- [x] **Step 2: اجرای اولیه تست برای مشاهده Fail (TDD)**
```powershell
./env/Scripts/python.exe -m pytest tests/test_convert_text.py
```
انتظار: خطا به دلیل عدم وجود ماژول `convert_text`.

- [x] **Step 3: پیاده‌سازی `convert_text.py`**
ایجاد ماژول کامل با پشتیبانی از آرگومان‌های CLI و فراخوانی تابعی:
```python
"""
ابزار تبدیل متن یا فایل متنی فارسی به گفتار (WAV)
سازگار با CPU و موتور ONNX پارسی‌گو
"""
import argparse
import os
import sys
from pathlib import Path

# اضافه کردن مسیر scripts به sys.path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from tts_onnx import synthesize_text, load_voice_reference, ONNX_DIR

def text_to_speech(text: str, voice: str = "voices/male_hello.wav", output_file: str = "output/result.wav", pack: bool = True):
    if not os.path.exists(voice):
        raise FileNotFoundError(f"فایل صدای مرجع یافت نشد: {voice}")
    
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # سنتز صدا
    audio, sr = synthesize_text(
        text=text,
        ref_wav=voice,
        pack=pack,
        model_dir=str(ONNX_DIR)
    )
    
    import soundfile as sf
    sf.write(output_file, audio, sr)
    return output_file

def main():
    parser = argparse.ArgumentParser(description="تبدیل متن یا فایل متنی فارسی به صوت")
    parser.add_argument("--text", "-t", type=str, help="متن مستقیم ورودی")
    parser.add_argument("--file", "-f", type=str, help="مسیر فایل متنی txt")
    parser.add_argument("--voice", "-v", default="voices/male_hello.wav", help="مسیر فایل صدای مرجع (پیش‌فرض male_hello.wav)")
    parser.add_argument("--output", "-o", default="output/speech.wav", help="مسیر فایل خروجی WAV")
    parser.add_argument("--no-pack", action="store_true", help="غیرفعال کردن ادغام عبارات و مکث‌های ویرگولی")
    
    args = parser.parse_args()
    
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read().strip()
    elif args.text:
        content = args.text.strip()
    else:
        print("خطا: لطفاً متن ورودی را با --text یا مسیر فایل را با --file مشخص کنید.")
        sys.exit(1)
        
    print(f"در حال پردازش متن (طول: {len(content)} کاراکتر)...")
    out = text_to_speech(content, voice=args.voice, output_file=args.output, pack=not args.no_pack)
    print(f"فایل صوتی با موفقیت ذخیره شد: {out}")

if __name__ == "__main__":
    main()
```

- [x] **Step 4: اجرای تست و اطمینان از پاس شدن آن**
```powershell
./env/Scripts/python.exe -m pip install pytest
./env/Scripts/python.exe -m pytest tests/test_convert_text.py
```
انتظار: `1 passed`.

- [x] **Step 5: تست کاربردی با فایل متنی**
ایجاد یک فایل متنی نمونه و تبدیل آن:
```powershell
Set-Content -Path "sample.txt" -Value "هوش مصنوعی تبدیل متن به گفتار، کلمات را با صدای طبیعی بازخوانی می‌کند." -Encoding UTF8
./env/Scripts/python.exe convert_text.py --file sample.txt --output output/sample_speech.wav
```
انتظار: تولید موفق `output/sample_speech.wav`.

- [x] **Step 6: ثبت کامیت**
```bash
git add convert_text.py tests/test_convert_text.py sample.txt
git commit -m "feat: add convert_text.py module and CLI wrapper for batch text processing"
```

---

### Task 6: اعتبارسنجی رابط وب و ایجاد لانچر سریع برای لپ‌تاپ

**Files:**
- Create: `run_web_ui.bat`
- Test: تست پاسخ‌دهی سرور وب

**Interfaces:**
- Consumes: `scripts/server.py`
- Produces: رابط وب قابل دسترسی در `http://127.0.0.1:8000` و فایل راه‌انداز یک‌کلیکی برای ویندوز

- [ ] **Step 1: ایجاد لانچر ویندوز `run_web_ui.bat`**
```bat
@echo off
chcp 65001 > nul
echo ====================================================
echo  Persian TTS Web UI Launcher
echo ====================================================
echo در حال اجرای سرور محلی تبدیل متن به گفتار...
echo پس از بالا آمدن سرور، آدرس زیر را در مرورگر باز کنید:
echo http://127.0.0.1:8000
echo.
.\env\Scripts\python.exe scripts\server.py
pause
```

- [ ] **Step 2: تست عملکرد اندپوینت‌های سرور**
اجرای تستی سرور به عنوان تسک پس‌زمینه و ارسال درخواست:
```powershell
# ارسال درخواست بررسی صداهای موجود به سرور پس از استارت
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/voices"
```
انتظار: بازگشت لیست صداهای پیش‌فرض (`male_hello.wav`, `female_narration.wav`, `male_news.wav`).

- [ ] **Step 3: ثبت کامیت نهایی**
```bash
git add run_web_ui.bat
git commit -m "feat: add Windows launcher batch file for Web UI"
```
