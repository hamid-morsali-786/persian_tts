import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from scripts.chapter_parser import (
    clean_text,
    estimate_speech_duration,
    extract_book_title,
    is_heading_line,
    parse_files_into_chapters,
    parse_text_into_chapters,
)


def test_estimate_speech_duration():
    assert estimate_speech_duration(0) == 0.0
    assert estimate_speech_duration(-10) == 0.0
    # 125 words at 125 WPM is exactly 60 seconds
    assert estimate_speech_duration(125, wpm=125) == 60.0
    # 250 words at 125 WPM is 120 seconds
    assert estimate_speech_duration(250, wpm=125) == 120.0


def test_is_heading_line():
    assert is_heading_line("فصل اول")[0] is True
    assert is_heading_line("فصل ۱: آغاز ماجرا")[0] is True
    assert is_heading_line("بخش دوم - کلیات")[0] is True
    assert is_heading_line("گفتار ۳")[0] is True
    assert is_heading_line("مقدمه")[0] is True
    assert is_heading_line("پیشگفتار: سخن مترجم")[0] is True
    assert is_heading_line("نتیجه‌گیری")[0] is True
    assert is_heading_line("# عنوان بزرگ")[0] is True
    assert is_heading_line("## زیرعنوان")[0] is True
    assert is_heading_line("---")[0] is True
    assert is_heading_line("===")[0] is True

    # Compound Persian ordinals and cardinals
    assert is_heading_line("فصل بیست و چهارم")[0] is True
    assert is_heading_line("فصل سی و پنجم: تحلیل داده‌ها")[0] is True
    assert is_heading_line("بخش چهل و یکم")[0] is True
    assert is_heading_line("Chapter 12 - Deep Dive")[0] is True

    # Regular sentences should NOT be headings (prevent false positives)
    assert is_heading_line("این یک جمله معمولی برای آزمایش است.")[0] is False
    assert is_heading_line("پایان کار نزدیک است و باید گزارش را ارسال کنیم.")[0] is False
    assert is_heading_line("فصل بهار یکی از زیباترین فصل‌های سال است.")[0] is False
    assert is_heading_line("بخش بزرگی از مردم در شهرها زندگی می‌کنند.")[0] is False
    assert is_heading_line("درس خواندن در شب تمرکز بالایی می‌خواهد.")[0] is False
    assert is_heading_line("قسمت اعظم این بودجه صرف بهداشت شد.")[0] is False
    assert is_heading_line("باب میل من نبود و آن را کنار گذاشتم.")[0] is False
    assert is_heading_line("")[0] is False


def test_parse_text_into_chapters_persian_headings():
    sample_text = """
مقدمه
این کتاب به بررسی راهکارهای نوین می‌پردازد.

فصل اول: شروع کار
برای شروع کار باید برنامه‌ریزی دقیقی انجام داد.
موفقیت در گرو پشتکار است.

فصل دوم - توسعه و پیشرفت
در این مرحله ابزارها را به کار می‌گیریم.

نتیجه‌گیری
در نهایت اهداف محقق شدند.
"""
    chapters = parse_text_into_chapters(sample_text)
    assert len(chapters) == 4
    assert chapters[0]["title"] == "مقدمه"
    assert "راهکارهای نوین" in chapters[0]["text"]

    assert chapters[1]["title"] == "فصل اول: شروع کار"
    assert "برنامه‌ریزی" in chapters[1]["text"]

    assert chapters[2]["title"] == "فصل دوم - توسعه و پیشرفت"
    assert "ابزارها" in chapters[2]["text"]

    assert chapters[3]["title"] == "نتیجه‌گیری"
    assert "اهداف محقق شدند" in chapters[3]["text"]


def test_parse_text_into_chapters_dividers():
    text = """
متن بخش اول پیش از جداکننده.
---
متن بخش دوم پس از جداکننده اول.
---
متن بخش سوم.
"""
    chapters = parse_text_into_chapters(text)
    assert len(chapters) == 3
    assert chapters[0]["index"] == 1
    assert "بخش اول" in chapters[0]["text"]
    assert chapters[1]["index"] == 2
    assert "بخش دوم" in chapters[1]["text"]


def test_parse_text_into_chapters_markdown():
    text = """
# کتاب جامع معماری نرم‌افزار

## فصل ۱: مبانی معماری
محتوای فصل یک.

## فصل ۲: الگوهای طراحی
محتوای فصل دو.
"""
    chapters = parse_text_into_chapters(text)
    assert len(chapters) >= 2
    titles = [c["title"] for c in chapters]
    assert any("فصل ۱" in t for t in titles)
    assert any("فصل ۲" in t for t in titles)


def test_fallback_word_count_chunking():
    # Long text without any headings
    long_sentences = [f"این جمله شماره {i} برای پر کردن متن است." for i in range(1, 100)]
    long_text = " ".join(long_sentences)

    chapters = parse_text_into_chapters(long_text, default_chunk_words=100)
    assert len(chapters) > 1
    assert chapters[0]["title"] == "بخش ۱"
    assert chapters[1]["title"] == "بخش ۲"
    for chap in chapters:
        assert chap["words"] > 0
        assert chap["chars"] > 0
        assert chap["estimated_duration"] > 0


def test_secondary_chunking_on_long_chapter():
    # Long text with a heading, should be split into multiple sub-chapters
    long_sentences = [f"این جمله برای طولانی شدن متن شماره {i} است." for i in range(1, 150)]
    text = "# فصل طولانی\n\n" + " ".join(long_sentences)
    
    # Each sentence is ~8 words. 150 sentences = 1200 words.
    chapters = parse_text_into_chapters(text, default_chunk_words=300)
    
    # Because it exceeds 300 words, the chapter should be split into sub-parts
    assert len(chapters) > 1
    assert "فصل طولانی — بخش ۱" in chapters[0]["title"]
    assert "فصل طولانی — بخش ۲" in chapters[1]["title"]


def test_parse_files_into_chapters():
    files = [
        ("01_intro.txt", "متن مقدمه کتاب"),
        ("02_chapter_one.txt", "متن کامل فصل اول"),
    ]
    chapters = parse_files_into_chapters(files)
    assert len(chapters) == 2
    assert chapters[0]["index"] == 1
    assert chapters[0]["title"] == "01 intro"
    assert chapters[0]["text"] == "متن مقدمه کتاب"
    assert chapters[1]["index"] == 2
    assert chapters[1]["title"] == "02 chapter one"


def test_empty_or_whitespace_input():
    assert parse_text_into_chapters("") == []
    assert parse_text_into_chapters("   \n\n\t  ") == []


def test_extract_book_title():
    text1 = "# تاریخ بیهقی\n\nفصل اول..."
    assert extract_book_title(text1) == "تاریخ بیهقی"

    text2 = "کتاب: شازده کوچولو\n\nفصل ۱..."
    assert extract_book_title(text2) == "شازده کوچولو"

    text3 = "فصل اول: بدون عنوان کتاب\nمتن..."
    assert extract_book_title(text3) == "کتاب صوتی"


def test_parse_files_natural_sorting_and_internal_headers():
    files = [
        ("part_10.txt", "متن فصل دهم کتاب."),
        ("part_2.txt", "# فصل دوم: جهش بزرگ\nمتن بدنه فصل دوم که بدون تیتر باید باشد."),
        ("part_1.txt", "متن فصل اول بدون تیتر."),
    ]
    chapters = parse_files_into_chapters(files)
    assert len(chapters) == 3

    # Natural sorting checks: part_1 -> part_2 -> part_10
    assert chapters[0]["index"] == 1
    assert chapters[0]["title"] == "part 1"
    assert "متن فصل اول" in chapters[0]["text"]

    assert chapters[1]["index"] == 2
    assert chapters[1]["title"] == "فصل دوم: جهش بزرگ"
    assert "متن بدنه فصل دوم" in chapters[1]["text"]
    assert "# فصل دوم" not in chapters[1]["text"]

    assert chapters[2]["index"] == 3
    assert chapters[2]["title"] == "part 10"
    assert "متن فصل دهم" in chapters[2]["text"]


def test_markdown_heading_levels():
    text = """
# سطح یک
متن ۱

## سطح دو
متن ۲

### سطح سه
متن ۳

#### سطح چهار
متن ۴
"""
    chapters = parse_text_into_chapters(text)
    assert len(chapters) >= 3
    titles = [c["title"] for c in chapters]
    assert any("سطح دو" in t for t in titles)
    assert any("سطح سه" in t for t in titles)
    assert any("سطح چهار" in t for t in titles)
