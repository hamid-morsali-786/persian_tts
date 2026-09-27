"""
Intelligent chapter segmentation and detection for Persian and multilingual texts.
Detects chapter titles (e.g., 'فصل اول', 'بخش ۲', Markdown headings, dividers)
and provides intelligent fallback chunking by word count on sentence boundaries.
"""
from dataclasses import asdict, dataclass
import re
from typing import Any, List, Optional, Tuple


@dataclass
class ChapterData:
    """Represents a parsed chapter in an audiobook."""
    index: int
    title: str
    text: str
    words: int
    chars: int
    estimated_duration: float

    def to_dict(self) -> dict:
        return asdict(self)


DIVIDER_PATTERN = re.compile(r"^(?:[-=_*]{3,})$")
MARKDOWN_PATTERN = re.compile(r"^#{1,6}\s+(.+)$")

# Persian ordinal numbers in words (single and compound)
PERSIAN_ORDINALS = (
    r"(?:اول|نخست|یکم|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم|"
    r"یازدهم|دوازدهم|سیزدهم|چهاردهم|پانزدهم|شانزدهم|هفدهم|هجدهم|نوزدهم|بیستم|"
    r"سی‌ام|چهلم|پنجاهم|شصتم|هفتادم|هشتادم|نودم|صدم|"
    r"(?:بیست|سی|چهل|پنجاه|شصت|هفتاد|هشتاد|نود|صد)\s+و\s+"
    r"(?:اول|یکم|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم|"
    r"یازدهم|دوازدهم|سیزدهم|چهاردهم|پانزدهم|شانزدهم|هفدهم|هجدهم|نوزدهم))"
)

# Persian cardinal numbers in words (single and compound)
PERSIAN_CARDINALS = (
    r"(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|"
    r"یازده|دوازده|سیزده|چهارده|پانزده|شانزده|هفده|هجده|نوزده|بیست|"
    r"سی|چهل|پنجاه|شصت|هفتاد|هشتاد|نود|صد|"
    r"(?:بیست|سی|چهل|پنجاه|شصت|هفتاد|هشتاد|نود|صد)\s+و\s+"
    r"(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه))"
)

CHAPTER_NUMS = rf"(?:[۰-۹\d]+|[IVXLCDMivxlcdm]+|{PERSIAN_ORDINALS}|{PERSIAN_CARDINALS})"
CHAPTER_PREFIXES = r"(?:فصل|بخش|قسمت|گفتار|درس|باب|حکایت|Chapter|Section|Part)"
STANDALONE_KEYWORDS = r"(?:مقدمه|پیشگفتار|دیباچه|سرآغاز|نتیجه‌گیری|خاتمه|پایان|پیوست|ضمیمه|Epilogue|Prologue)"

PAT_CHAPTER_NUM = re.compile(rf"^{CHAPTER_PREFIXES}\s+{CHAPTER_NUMS}(?:[\s:：\-—–.].*)?$", re.IGNORECASE)
PAT_CHAPTER_DELIM = re.compile(rf"^{CHAPTER_PREFIXES}\s*[:：\-—–]\s*(.+)$", re.IGNORECASE)
PAT_STANDALONE = re.compile(rf"^{STANDALONE_KEYWORDS}(?:\s*[:：\-—–.]\s*.*|\s*)$", re.IGNORECASE)


def natural_sort_key(s: Any) -> List[Any]:
    """Sort strings containing numbers in human natural order (e.g. 1, 2, 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(s))]


def estimate_speech_duration(words: int, wpm: int = 125) -> float:
    """Estimates speech duration in seconds given word count and words-per-minute."""
    if words <= 0:
        return 0.0
    return round((words / max(1, wpm)) * 60.0, 1)


def clean_text(text: str) -> str:
    """Normalizes excessive blank lines and leading/trailing whitespace."""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_heading_line(line: str) -> Tuple[bool, str]:
    """
    Checks if a given line is a chapter heading or divider.
    Returns (is_heading, extracted_title).
    Prevents false positives on normal narrative sentences.
    """
    trimmed = line.strip()
    if not trimmed or len(trimmed) > 120:
        return False, ""

    if DIVIDER_PATTERN.match(trimmed):
        return True, ""

    md_match = MARKDOWN_PATTERN.match(trimmed)
    if md_match:
        return True, md_match.group(1).strip()

    # Reject if it ends with sentence-terminating punctuation unless it's very short (<= 3 words)
    if re.search(r"[.!؟]\s*$", trimmed) and len(trimmed.split()) > 3:
        return False, ""

    if PAT_CHAPTER_NUM.match(trimmed) or PAT_CHAPTER_DELIM.match(trimmed) or PAT_STANDALONE.match(trimmed):
        cleaned = re.sub(r"^#+\s*", "", trimmed).strip()
        return True, cleaned

    return False, ""


def extract_book_title(text: str, default: str = "کتاب صوتی") -> str:
    """Attempts to infer the book title from top lines or Markdown headers."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return default

    first_line = lines[0]
    if first_line.startswith("# "):
        return first_line[2:].strip()

    title_match = re.match(r"^(?:کتاب|عنوان|نام اثر)[:：\s]+(.+)$", first_line)
    if title_match:
        return title_match.group(1).strip()

    if len(first_line) < 60 and not is_heading_line(first_line)[0]:
        return first_line

    return default


def split_into_sentences(text: str) -> List[str]:
    """Splits Persian text into sentences respecting punctuation."""
    raw = re.split(r"(?<=[.!؟\n])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def to_persian_digits(n: int) -> str:
    """Converts ASCII digits to Persian digits."""
    trans = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(n).translate(trans)


def chunk_by_word_count(text: str, max_words: int = 1200) -> List[ChapterData]:
    """
    Fallback chapter chunker based on word limits.
    Never splits in the middle of sentences.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chapters: List[ChapterData] = []
    curr_sentences: List[str] = []
    curr_words = 0
    chapter_idx = 1

    for sent in sentences:
        sent_words = len(sent.split())
        if curr_words + sent_words > max_words and curr_sentences:
            chunk_body = " ".join(curr_sentences)
            chapters.append(
                ChapterData(
                    index=chapter_idx,
                    title=f"بخش {to_persian_digits(chapter_idx)}",
                    text=chunk_body,
                    words=curr_words,
                    chars=len(chunk_body),
                    estimated_duration=estimate_speech_duration(curr_words),
                )
            )
            chapter_idx += 1
            curr_sentences = [sent]
            curr_words = sent_words
        else:
            curr_sentences.append(sent)
            curr_words += sent_words

    if curr_sentences:
        chunk_body = " ".join(curr_sentences)
        chapters.append(
            ChapterData(
                index=chapter_idx,
                title=f"بخش {to_persian_digits(chapter_idx)}",
                text=chunk_body,
                words=curr_words,
                chars=len(chunk_body),
                estimated_duration=estimate_speech_duration(curr_words),
            )
        )

    return chapters


def parse_text_into_chapters(text: str, default_chunk_words: int = 1200) -> List[dict]:
    """
    Parses full text into a list of structured chapter dictionaries.
    Uses heading/divider pattern matching with intelligent word-count fallback.
    """
    cleaned = clean_text(text)
    if not cleaned:
        return []

    lines = cleaned.splitlines()
    raw_segments: List[Tuple[Optional[str], List[str]]] = []
    curr_title: Optional[str] = None
    curr_lines: List[str] = []

    for line in lines:
        is_hdr, extracted_title = is_heading_line(line)
        if is_hdr:
            if curr_lines or curr_title is not None:
                raw_segments.append((curr_title, curr_lines))
                curr_lines = []
            curr_title = extracted_title if extracted_title else None
        else:
            curr_lines.append(line)

    if curr_lines or curr_title is not None:
        raw_segments.append((curr_title, curr_lines))

    # If no headings or dividers were found at all, fallback to word-count chunking
    if len(raw_segments) <= 1 and raw_segments and raw_segments[0][0] is None:
        total_words = len(cleaned.split())
        if total_words > default_chunk_words:
            return [c.to_dict() for c in chunk_by_word_count(cleaned, max_words=default_chunk_words)]

    book_title = extract_book_title(cleaned)
    chapters: List[ChapterData] = []
    idx = 1
    for title, segment_lines in raw_segments:
        body = clean_text("\n".join(segment_lines))
        if not body:
            continue

        if not title or (idx == 1 and title == book_title and len(raw_segments) > 1):
            resolved_title = "مقدمه" if idx == 1 else f"فصل {to_persian_digits(idx)}"
        else:
            resolved_title = title

        words = len(body.split())
        if words > default_chunk_words:
            sub_chunks = chunk_by_word_count(body, max_words=default_chunk_words)
            for sub_idx, sub in enumerate(sub_chunks, 1):
                part_title = f"{resolved_title} — بخش {to_persian_digits(sub_idx)}" if len(sub_chunks) > 1 else resolved_title
                chapters.append(
                    ChapterData(
                        index=idx,
                        title=part_title,
                        text=sub.text,
                        words=sub.words,
                        chars=sub.chars,
                        estimated_duration=sub.estimated_duration,
                    )
                )
                idx += 1
        else:
            chapters.append(
                ChapterData(
                    index=idx,
                    title=resolved_title,
                    text=body,
                    words=words,
                    chars=len(body),
                    estimated_duration=estimate_speech_duration(words),
                )
            )
            idx += 1

    return [c.to_dict() for c in chapters]


def parse_files_into_chapters(files: List[Tuple[str, str]]) -> List[dict]:
    """
    Parses multiple files into chapters where each file corresponds to a chapter.
    Derives chapter titles from internal headers (first line if heading) or filenames.
    Sorts files naturally (e.g. chap2 before chap10).
    """
    sorted_files = sorted(files, key=lambda f: natural_sort_key(f[0]))
    chapters: List[dict] = []
    for idx, (filename, content) in enumerate(sorted_files, 1):
        cleaned = clean_text(content)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        title = ""
        chapter_body = cleaned
        if lines:
            is_hdr, extracted_title = is_heading_line(lines[0])
            if is_hdr and extracted_title:
                title = extracted_title
                # Strip heading line from spoken audio content
                rest = clean_text("\n".join(lines[1:]))
                if rest:
                    chapter_body = rest

        if not title:
            stem = re.sub(r"\.[^.]+$", "", filename).strip()
            stem = re.sub(r"[-_]+", " ", stem).strip()
            title = stem if stem else f"فصل {idx}"

        words = len(chapter_body.split())
        chapters.append(
            ChapterData(
                index=idx,
                title=title,
                text=chapter_body,
                words=words,
                chars=len(chapter_body),
                estimated_duration=estimate_speech_duration(words),
            ).to_dict()
        )
    return chapters
