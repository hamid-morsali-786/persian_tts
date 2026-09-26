<div align="center">

<img src="web/logo.png" width="128" alt="لوگوی پارسی‌گو">

<h1 align="center">پارسی‌گو (تبدیل متن فارسی به گفتار)</h1>

<p align="center"><b>استودیوی پیشرفته تبدیل متن و کتاب صوتی فارسی — موتور هیبریدی ONNX و پردازش دسته‌ای</b></p>
<p align="center">
  <b>توسعه و بهینه‌سازی توسط:</b> <a href="https://github.com/hamid-morsali-786">hamid-morsali-786</a> · 
  <b>انشعاب‌یافته از:</b> <a href="https://github.com/nimaone/persian_tts">nimaone/persian_tts</a>
</p>

**فارسی** | [English](README.en.md)

<a href="docs/demo.mp4"><img src="docs/demo-poster.jpg" width="640" alt="دموی ویدیویی پارسی‌گو — انتخاب صدا، تایپ متن و تولید گفتار در وب‌اپ"></a>

🎬 **دموی ویدیویی (با صدا)** — انتخاب صدای مرجع، تولید گفتار، کلونینگ صدا، پردازش دسته‌ای و استودیوی ساخت کتاب صوتی.
(نسخهٔ دانلودی داخل ریپو: [docs/demo.mp4](docs/demo.mp4) — پوستر: [docs/demo-poster.jpg](docs/demo-poster.jpg))

</div>

تبدیل متن فارسی به گفتار با **کلونینگ صدا**، کاملاً آفلاین روی **CPU** — بدون نیاز به کارت گرافیک (GPU) و بدون ارتباط اینترنتی در زمان اجرا. متن فارسی را مستقیم دریافت کرده، فونم‌سازی و سنتز آکوستیک را انجام می‌دهد و خروجی صوتی باکیفیت در قالب **MP3** یا **WAV** با نرخ نمونه ۲۴ کیلوهرتز تولید می‌کند.

---

## 🌟 ویژگی‌ها و امکانات توسعه‌یافته در این نسخه (New Features)

این مخزن به عنوان یک اثر اشتقاقی (Derivative Work / Downstream Project) با افزودن قابلیت‌های مدرن زیر نسبت به نسخه پایه توسعه یافته است:

1. 📚 **استودیوی ساخت کتاب صوتی و پردازش دسته‌ای (Audiobook & Batch Studio):**
   - تبدیل کتاب‌ها و اسناد متنی طولانی به کتاب صوتی در محیط وب.
   - تفکیک و پارتیشن‌بندی هوشمند متن به فصل‌ها و بخش‌های استاندارد بر مبنای عناوین و سرفصل‌ها.
   - مدیریت صف پردازش در پس‌زمینه (Asynchronous Background Task Queue) بدون قفل شدن رابط کاربری.
   - مانیتورینگ زنده پیشرفت با نوار پیشرفت درصددار و تخمین هوشمند زمان باقی‌مانده.
   - امکان دانلود تجمیعی تمام فصول در قالب **فایل فشرده ZIP** (همراه شناسنامه کتاب) یا یک **فایل صوتی یکپارچه (Merged Audio)**.

2. 🚀 **موتور چندگانه هیبریدی (Hybrid TTS Engine):**
   - سوئیچ آسان میان **موتور محلی آفلاین ONNX** (سبک، امن، مستقل از شبکه و فوق‌سریع روی CPU) و **موتور ابری با کیفیت فوق‌العاده Gemini Cloud TTS**.
   - مکانیزم Fallback خودکار برای بازگشت به موتور محلی در شرایط اختلال شبکه یا محدودیت‌های دسترسی منطقه‌ای.

3. 🎧 **پشتیبانی از خروجی‌های صوتی MP3 و WAV:**
   - خروجی فشرده و بهینه‌سازی‌شده **MP3** به صورت پیش‌فرض (با اینکودر استاندارد صوتی و سازگاری با انواع پلیرها و وب).
   - خروجی استودیویی **WAV** با کیفیت ۲۴kHz بدون افت (Lossless).
   - انتخاب مستقیم فرمت در صفحه اصلی و استودیوی کتاب صوتی.

4. 🎨 **رابط کاربری مدرن با تم دوگانه (Modern Light / Dark UI):**
   - طراحی چشم‌نواز مبتنی بر فلسفه *Intentional Minimalism*.
   - **تم روشن مدرن (Modern Light)** به عنوان حالت پیش‌فرض و **تم تیره (Dark Mode)** با ترنزیشن نرم و حفظ تنظیمات در مرورگر.
   - نمایش پیام‌های خطا و راهنما به صورت اعلان‌های پایدار با امکان بستن دستی توسط کاربر.
   - نمایش پیشرفت سنتز تکی با ثانیه‌شمار و پروگرس‌بار روان.

5. 🛠️ **ابزار خط فرمان تبدیل فایل متنی (`scripts/convert_text.py`):**
   - ابزار اختصاصی CLI برای تبدیل مستقیم فایل‌های متنی (`.txt`) به فایل صوتی.
   - پشتیبانی از پرچم `--play` جهت پخش فوری صدا پس از اتمام تبدیل، با قابلیت تنظیم سرعت (`--pace`) و حالت گفتار (`--mode`).

6. ⚡ **راه‌اندازی آسان و همگام‌سازی با یک کلیک:**
   - فایل اجرایی `run_web_ui.bat` برای اجرای سرور محلی و باز شدن خودکار مرورگر در ویندوز.
   - فایل اجرایی `push_to_github.bat` جهت احراز هویت تعاملی و ارسال سریع آخرین تغییرات به گیت‌هاب.

---

## ساختار پروژه

```
persian_tts/
├── env/                     محیط مجازی پایتون
├── model/
│   ├── v2/                  مدل اصلی TTS (mehdi-hf/pocket-tts-farsi-v2)
│   ├── g2p/                 مدل G2P فارسی→فونم (mehdi-hf/Homo-GE2PE-Persian-HF)
│   └── onnx/                پکیج ONNX یکپارچه (~۴۸۰MB) + manifest.json
├── voices/                  صداهای مرجع داخلی (≤ ۵ ثانیه)
├── output/                  فایل‌های صوتی تولیدشده (WAV/MP3/ZIP)
├── uploads/                 صداهای بارگذاری‌شده توسط کاربر
├── docs/                    مستندات فنی معماری و بنچمارک‌ها
├── scripts/
│   ├── batch_processor.py   مدیریت صف وظایف کتاب صوتی و خروجی ZIP/Merged
│   ├── hybrid_tts.py        موتور چندگانه هیبریدی (ONNX محلی + Gemini Cloud)
│   ├── audio_exporter.py    مدیریت تبدیل فرمت‌های صوتی (MP3/WAV)
│   ├── convert_text.py      ابزار خط فرمان تبدیل مستقیم فایل متنی با پرچم --play
│   ├── tts_onnx.py          موتور و CLI مسیر آفلاین ONNX (بدون نیاز به torch)
│   ├── g2p_onnx.py          تبدیل متن به فونم در قالب ONNX
│   ├── server.py            سرور وب FastAPI با پشتیبانی از صف دسته‌ای و API
│   ├── persian_tts.py       ماژول خط لوله مرجع torch
│   ├── tts.py               CLI مسیر مرجع torch
│   └── export_unified.py    سازنده پکیج ONNX از مدل اصلی
├── web/
│   └── index.html           رابط وب فارسی مدرن با تم دوتایی و استودیو کتاب صوتی
├── run_web_ui.bat           لانچر اجرای وب در ویندوز (همراه باز شدن خودکار مرورگر)
├── push_to_github.bat       اسکریپت همگام‌سازی آسان با مخزن گیت‌هاب
├── README.md                مستندات فارسی
└── README.en.md             English documentation
```

---

## راه‌اندازی و اجرای سریع (Quick Start)

### ۱. اجرای سریع در ویندوز (پیشنهادی)
اگر مخزن را کلون کرده‌اید:

```powershell
git clone https://github.com/hamid-morsali-786/persian_tts.git
cd persian_tts
```

کافی است روی فایل **`run_web_ui.bat`** دابل‌کلیک کنید تا محیط بررسی شده، سرور اجرا و صفحه دمو در مرورگر باز شود.

---

### ۲. راه‌اندازی دستی مسیر سبک ONNX (بدون نیاز به torch)

**مرحله ۱: ایجاد محیط مجازی و نصب وابستگی‌های سبک (~۲۰۰MB)**
```bash
python -m venv env
./env/Scripts/python.exe -m pip install onnxruntime numpy scipy soundfile sentencepiece fastapi uvicorn
```

**مرحله ۲: دریافت پکیج مدل‌های ONNX از HuggingFace**
```bash
./env/Scripts/python.exe -m pip install -U "huggingface_hub[cli]"
hf download Nimaone/pocket-tts-farsi-v2-onnx --local-dir model/onnx
```

**مرحله ۳: اجرای سرور یا ابزار خط فرمان**
```bash
# اجرای رابط وب (پیش‌فرض: http://127.0.0.1:8000)
./env/Scripts/python.exe scripts/server.py

# تبدیل تکی مستقیم در ترمینال
./env/Scripts/python.exe scripts/tts_onnx.py "سلام دنیا، روز شما بخیر" voices/male_hello.wav output/out.wav

# تبدیل فایل متنی با پخش فوری
./env/Scripts/python.exe scripts/convert_text.py my_text.txt --play
```

---

## دموی وب (Web UI & Audiobook Studio)

سرور را اجرا کنید و در مرورگر آدرس `http://127.0.0.1:8000` را باز نمایید:

1. **تبدیل گفتار تکی (Single TTS):**
   - تایپ یا انتخاب متن فارسی، انتخاب صدای مرجع داخلی یا آپلود صدای شخصی.
   - انتخاب موتور سنتز (موتور محلی آفلاین یا موتور ابری هیبریدی).
   - انتخاب فرمت خروجی صوتی (**MP3** یا **WAV**).
   - تنظیم سرعت (۰٫۷× تا ۱٫۳۵×) و حالت خوانش («با مکث ویرگول‌ها» یا «یکپارچه و روان»).
   - ویرایش دستی فونم (اصلاح تلفظ) برای اسامی خاص یا واژگان لاتین.

2. **استودیوی کتاب صوتی (Audiobook Studio):**
   - بارگذاری متن بلند با عنوان اثر و نام گوینده.
   - تفکیک خودکار به فصل‌ها و ارسال به صف پردازش ناهمگام.
   - مشاهده پیشرفت زنده‌ی تبدیل هر فصل با پروگرس‌بار و زمان‌سنج.
   - دانلود مجزای هر فصل، دانلود بسته کامل ZIP و یا فایل صوتی پیوسته کتاب.

---

## API سرور (برای توسعه‌دهندگان)

سرور FastAPI مستقر در `scripts/server.py` نقاط پایانی زیر را در اختیار قرار می‌دهد:

| روش | مسیر | ورودی | خروجی |
|---|---|---|---|
| `GET` | `/` | — | صفحه وب اپلیکیشن (`web/index.html`) |
| `GET` | `/api/voices` | — | لیست صداهای داخلی و آپلودشده `{voices: [...]}` |
| `POST` | `/api/tts` | `{text, voice, pace?, mode?, engine?, audio_format?}` | شناسنامه صوت تولیدشده `{id, phonemes, duration, format}` |
| `GET` | `/api/audio/{id}` | پارامتر اختیاری `?format=mp3` یا `?format=wav` | جریان داده صوتی (`audio/mpeg` یا `audio/wav`) |
| `POST` | `/api/phonemize` | `{text, mode?}` | فونم‌های فارسی `{phonemes}` |
| `POST` | `/api/tts-phonemes` | `{phonemes, voice, pace?, engine?, audio_format?}` | سنتز مستقیم از رشته فونم |
| `POST` | `/api/voice/upload` | فایل صوتی کاربر (`multipart/form-data`) | `{id, name, seconds}` |
| `POST` | `/api/batch/audiobook` | `{title, text, voice, pace?, mode?, engine?, audio_format?}` | ایجاد وظیفه صف `{task_id, status, chapters}` |
| `GET` | `/api/batch/status/{id}` | — | آخرین وضعیت صف و درصد پیشرفت `{progress, status, chapters}` |
| `GET` | `/api/batch/download/{id}` | پارامتر اختیاری `?format=zip` یا `?format=merged` | فایل فشرده فصول یا فایل صوتی یکپارچه |

---

## مقایسه مسیر سبک ONNX و PyTorch اصلی

| معیار | مسیر ONNX (توصیه‌شده) | مسیر PyTorch (مرجع) |
|---|---|---|
| وابستگی‌ها | onnxruntime، numpy، scipy، soundfile، sentencepiece | torch، transformers، pocket-tts، soundfile |
| حجم وابستگی‌ها در ویندوز | **~۲۰۰MB** | **~۱٫۲GB** |
| کارت گرافیک (GPU) | **نیاز ندارد** (بهینه‌شده برای CPU) | نیاز ندارد (نسخه CPU تورچ) |
| استقلال شبکه | **۱۰۰٪ آفلاین** بدون نیاز به اینترنت | ۱۰۰٪ آفلاین |
| پلتفرم‌ها | ویندوز، لینوکس، مک (x64 و ARM64) | پایتون با وابستگی‌های تورچ |
| سرعت سنتز (نمونه ۲٫۸s) | ۳۲۸۳ms | ۳۴۲۳ms |

---

## اعتبارها و مجوزها (Credits & Acknowledgments)

- این مخزن توسط [hamid-morsali-786](https://github.com/hamid-morsali-786) بر پایه‌ی مخزن ارزشمند [nimaone/persian_tts](https://github.com/nimaone/persian_tts) ایجاد و با افزودن معماری کتاب صوتی، صف پس‌زمینه، موتور هیبریدی، خروجی MP3 و رابط کاربری مدرن گسترش یافته است.
- **مدل سنتز گفتار فارسی:** برگرفته از [`mehdi-hf/pocket-tts-farsi-v2`](https://huggingface.co/mehdi-hf/pocket-tts-farsi-v2) کاری از مهدی ملاحیاری ([`mallahyari/pocket-tts`](https://github.com/mallahyari/pocket-tts)) با مجوز **CC-BY-NC-4.0**.
- **مدل تبدیل متن به فونم (G2P):** مدل [`Homo-GE2PE-Persian`](https://huggingface.co/MahtaFetrat/Homo-GE2PE-Persian) توسعه‌یافته توسط سرکار خانم الناز رحمتی و همکاران.
- **معماری پایه TTS:** کتابخانه [`pocket-tts`](https://pypi.org/project/pocket-tts/) کاری از [Kyutai](https://kyutai.org).

> **هشدار مجوز تجاری:** طبق مجوز مدل پایه (**CC-BY-NC-4.0**)، هرگونه استفاده تجاری از خروجی‌های این مدل نیازمند اخذ مجوز از پدیدآورندگان مدل آکوستیک پایه است.
