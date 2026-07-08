import re

try:
    from langdetect import detect, LangDetectException
except ImportError:
    detect = None
    LangDetectException = Exception


def strip_ocr_noise(text):
    """Remove common PDF OCR artifacts: page numbers, headers/footers, hyphenation."""
    lines = text.split("\n")
    cleaned = []
    page_num_re = re.compile(r"^\s*(?:page\s+)?\d+\s*(?:of\s+\d+)?\s*$", re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if page_num_re.match(stripped):
            continue
        if re.match(r"^\s*[-—–]\s*\d+\s*[-—–]\s*$", stripped):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_language(text, default="en"):
    """Detect es/en from sample text."""
    sample = text[:2000].strip()
    if not sample:
        return default
    if detect is None:
        es_hits = len(re.findall(r"\b(el|la|los|las|de|que|en|un|una|es|por|con)\b", sample.lower()))
        en_hits = len(re.findall(r"\b(the|and|of|to|in|is|that|for|with)\b", sample.lower()))
        return "es" if es_hits > en_hits else "en"
    try:
        code = detect(sample)
        if code.startswith("es"):
            return "es"
        if code.startswith("en"):
            return "en"
        return code[:2]
    except LangDetectException:
        return default


def chunk_for_tts(text, min_chars=200, max_chars=400):
    """Split text into TTS-friendly chunks by sentence boundaries."""
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current and len(current) >= min_chars:
            chunks.append(current)
            current = sentence
        elif current:
            chunks.append(current)
            current = sentence
        else:
            while len(sentence) > max_chars:
                chunks.append(sentence[:max_chars].rsplit(" ", 1)[0])
                sentence = sentence[max_chars:].strip()
            current = sentence

    if current:
        chunks.append(current)
    return chunks


def polish_for_tts(text: str) -> str:
    """Normalize text so TTS reads it naturally."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # Smart quotes → straight quotes
    text = text.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
    # Ellipsis variants
    text = text.replace("…", "...")
    # Common OCR / ebook glitches
    text = re.sub(r"\b(\w)\s+\.\s*$", r"\1.", text, flags=re.MULTILINE)
    text = re.sub(r"([a-z]),([A-Z])", r"\1, \2", text)
    # Expand common abbreviations for reading aloud
    abbrevs = {
        r"\bMr\.": "Mister",
        r"\bMrs\.": "Missus",
        r"\bDr\.": "Doctor",
        r"\bSr\.": "Señor",
        r"\bSra\.": "Señora",
        r"\betc\.": "etcetera",
        r"\be\.g\.": "for example",
        r"\bi\.e\.": "that is",
    }
    for pat, repl in abbrevs.items():
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    # Remove markdown link syntax [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chapters_to_markdown(chapters: list[dict], title: str = "Audiobook", author: str | None = None) -> str:
    lines = [f"# {title}"]
    if author:
        lines.append(f"**Author:** {author}")
    lines.append("")
    for ch in chapters:
        lines.append(f"## {ch['title']}")
        lines.append("")
        lines.append(ch["content"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def chapters_to_plain(chapters: list[dict]) -> str:
    parts = []
    for ch in chapters:
        parts.append(ch["title"])
        parts.append("")
        parts.append(ch["content"])
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def fix_spacing(text):
    """
    Fixes spacing issues where letters are separated by spaces.
    """
    # Normalize common invisible/non-breaking whitespace that PDF extraction can produce.
    text = text.replace("\u00A0", " ").replace("\u202F", " ").replace("\u200B", "")

    # Match sequences like: "m o d e" / "M O D E" where single letters are separated by whitespace.
    # Use lookarounds instead of word boundaries to be more tolerant around punctuation.
    pattern = r"(?<![a-zA-Z])(?:[a-zA-Z]\s){2,}[a-zA-Z](?![a-zA-Z])"
    
    def replace_spaced_letters(match):
        spaced_word = match.group(0)
        # Remove spaces and check if it looks like a real word
        fixed = spaced_word.replace(' ', '')
        # Basic check: if the fixed version is alphabetic and reasonable length
        if fixed.isalpha() and len(fixed) >= 2:
            return fixed
        return spaced_word
    
    fixed_text = re.sub(pattern, replace_spaced_letters, text)
    return fixed_text


def split_into_chapters(text):
    """
    Split text into chapters based on common patterns.
    Returns a list of dictionaries with 'title' and 'content' keys.
    """
    # More comprehensive patterns to identify chapter starts
    patterns = [
        r'^\s*CHAPTER\s+\d+\s*$',
        r'^\s*Chapter\s+\d+\s*$',
        r'^\s*CHAPTER\s+[IVXLCDM]+\s*$',
        r'^\s*Chapter\s+[IVXLCDM]+\s*$',
        r'^\s*\d+\s*$',
        r'^\s*[IVXLCDM]+\s*$',
        r'^\s*Section\s+\d+\s*$',
        r'^\s*SECTION\s+\d+\s*$',
        r'^\s*Capítulo\s+\d+\s*$',
        r'^\s*CAPÍTULO\s+\d+\s*$',
        r'^\s*Capitulo\s+\d+\s*$',
        r'^\s*CAPITULO\s+\d+\s*$',
        r'^\s*(?:Chapter|Capítulo|Capitulo)\s+[\dIVXLCDM]+\s*[:\-—–]\s*.+\s*$',
        r'^\s*(?:Section|Sección|Seccion)\s+\d+\s*[:\-—–]?\s*.*$',
    ]
    lines = text.split('\n')
    
    chapters = []
    # Start with an initial chapter
    current_title = 'Introduction'
    current_content = []
    in_chapter = False
    
    for line in lines:
        # Check if the line matches any chapter pattern
        is_chapter_header = False
        for pattern in patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                is_chapter_header = True
                break
        
        if is_chapter_header:
            # If we're already in a chapter, save it
            if in_chapter or current_content:
                chapter_content = '\n'.join(current_content).strip()
                if chapter_content:
                    chapters.append({'title': current_title, 'content': chapter_content})
                current_content = []
            # Start new chapter
            current_title = line.strip()
            in_chapter = True
        else:
            current_content.append(line)
    
    # Add the last chapter
    if current_content:
        chapter_content = '\n'.join(current_content).strip()
        if chapter_content:
            chapters.append({'title': current_title, 'content': chapter_content})
    
    # Handle case where no chapters were found
    if not chapters:
        chapters.append({'title': 'Full Text', 'content': text.strip()})
    
    return chapters


def process_book(
    text,
    min_chunk=200,
    max_chunk=400,
    title: str | None = None,
    author: str | None = None,
    chapter_mode: str = "detect",
    lang: str | None = None,
):
    """Process book text: clean OCR, polish, split chapters, add TTS chunks."""
    from services.book_metadata import apply_chapter_naming

    cleaned = strip_ocr_noise(text)
    fixed_text = fix_spacing(cleaned)
    polished = polish_for_tts(fixed_text)
    language = lang or detect_language(polished)
    chapters = split_into_chapters(polished)
    chapters = apply_chapter_naming(chapters, mode=chapter_mode, lang=language)
    for chapter in chapters:
        chapter["content"] = polish_for_tts(chapter["content"])
        chapter["chunks"] = chunk_for_tts(chapter["content"], min_chunk, max_chunk)
        chapter["language"] = language
    return chapters
