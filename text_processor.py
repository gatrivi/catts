import re

try:
    from langdetect import detect, LangDetectException
except ImportError:
    detect = None
    LangDetectException = Exception


_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text)


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


# Common Spanish words that lose accents in OCR / ASCII paste.
# Keys are lowercase unaccented; values are the correct form.
_ES_ACCENT_MAP: dict[str, str] = {
    "facil": "fácil",
    "mas": "más",
    "debil": "débil",
    "tambien": "también",
    "asi": "así",
    "aqui": "aquí",
    "alli": "allí",
    "despues": "después",
    "rapido": "rápido",
    "rapida": "rápida",
    "rapidas": "rápidas",
    "rapidos": "rápidos",
    "unico": "único",
    "unica": "única",
    "ultimos": "últimos",
    "ultimo": "último",
    "ultima": "última",
    "ultimas": "últimas",
    "numero": "número",
    "numeros": "números",
    "musica": "música",
    "pagina": "página",
    "paginas": "páginas",
    "capitulo": "capítulo",
    "capitulos": "capítulos",
    "informacion": "información",
    "atencion": "atención",
    "accion": "acción",
    "acciones": "acciones",
    "relacion": "relación",
    "relaciones": "relaciones",
    "situacion": "situación",
    "situaciones": "situaciones",
    "emocion": "emoción",
    "emociones": "emociones",
    "respiracion": "respiración",
    "explicacion": "explicación",
    "explicaciones": "explicaciones",
    "justificacion": "justificación",
    "justificaciones": "justificaciones",
    "estrategia": "estrategia",
    "inefectiva": "inefectiva",
    "manipulable": "manipulable",
    "inestables": "inestables",
    "camino": "camino",
    "elegido": "elegido",
    "crees": "crees",
    "cree": "cree",
    "fuiste": "fuiste",
    "infiel": "infiel",
    "deshaces": "deshacés",
    "deshace": "deshace",
    "conejito": "conejito",
    "dientes": "dientes",
    "lobo": "lobo",
    "derroche": "derroche",
    "emocional": "emocional",
    "emocionalmente": "emocionalmente",
    "volatil": "volátil",
    "volátil": "volátil",
    "culpable": "culpable",
    "sos": "sos",
    "gratos": "gratos",
    "futuros": "futuros",
    "posibles": "posibles",
    "metas": "metas",
    "distrae": "distrae",
    "dirigiendo": "dirigiendo",
    "nuestra": "nuestra",
    "nuestro": "nuestro",
    "nuestros": "nuestros",
    "nuestras": "nuestras",
    "realidad": "realidad",
    "identidad": "identidad",
    "demas": "demás",
    "piensan": "piensan",
    "dicen": "dicen",
    "hacen": "hacen",
    "creer": "creer",
    "afectar": "afectar",
    "dejarnos": "dejarnos",
    "mujer": "mujer",
    "mujeres": "mujeres",
    "celosa": "celosa",
    "terriblemente": "terriblemente",
    "nervios": "nervios",
    "parecer": "parecer",
    "sentir": "sentir",
    "ocurre": "ocurre",
    "gusta": "gusta",
    "reconocer": "reconocer",
    "cuando": "cuando",
    "como": "cómo",  # often "cómo" in questions; see note below
    "que": "qué",  # often "qué" in questions — applied carefully
    "si": "sí",  # affirmation; "si" conditional kept via context heuristic
    "esta": "está",
    "estas": "estás",
    "estan": "están",
    "tu": "tú",
    "el": "él",  # pronoun; article "el" restored via heuristic
    "mio": "mío",
    "mia": "mía",
    "mios": "míos",
    "mias": "mías",
    "dia": "día",
    "dias": "días",
    "ano": "año",
    "anos": "años",
    "senor": "señor",
    "senora": "señora",
    "nino": "niño",
    "nina": "niña",
    "ninos": "niños",
    "ninas": "niñas",
    "espanol": "español",
    "espanola": "española",
    "corazon": "corazón",
    "razon": "razón",
    "razones": "razones",
    "opinion": "opinión",
    "opiniones": "opiniones",
    "decision": "decisión",
    "decisiones": "decisiones",
    "solucion": "solución",
    "soluciones": "soluciones",
    "direccion": "dirección",
    "direcciones": "direcciones",
    "educacion": "educación",
    "comunicacion": "comunicación",
    "organizacion": "organización",
    "produccion": "producción",
    "construccion": "construcción",
    "introduccion": "introducción",
    "conclusion": "conclusión",
    "version": "versión",
    "versiones": "versiones",
    "region": "región",
    "regiones": "regiones",
    "nation": "nación",
    "nacion": "nación",
    "naciones": "naciones",
    "publico": "público",
    "publica": "pública",
    "politica": "política",
    "politico": "político",
    "economico": "económico",
    "economica": "económica",
    "historico": "histórico",
    "historica": "histórica",
    "basico": "básico",
    "basica": "básica",
    "practico": "práctico",
    "practica": "práctica",
    "tecnico": "técnico",
    "tecnica": "técnica",
    "medico": "médico",
    "medica": "médica",
    "fisico": "físico",
    "fisica": "física",
    "logico": "lógico",
    "logica": "lógica",
    "tipico": "típico",
    "tipica": "típica",
    "automatico": "automático",
    "automatica": "automática",
    "electronico": "electrónico",
    "electronica": "electrónica",
    "telefonico": "telefónico",
    "telefonica": "telefónica",
    "gramatica": "gramática",
    "matematica": "matemática",
    "matematicas": "matemáticas",
    "geografia": "geografía",
    "filosofia": "filosofía",
    "psicologia": "psicología",
    "biologia": "biología",
    "tecnologia": "tecnología",
    "energia": "energía",
    "memoria": "memoria",
    "historia": "historia",
    "victoria": "victoria",
    "gloria": "gloria",
    "categoria": "categoría",
    "categorias": "categorías",
    "teoria": "teoría",
    "teorias": "teorías",
    "experiencia": "experiencia",
    "existencia": "existencia",
    "conciencia": "conciencia",
    "paciencia": "paciencia",
    "ciencia": "ciencia",
    "ciencias": "ciencias",
    "diferencia": "diferencia",
    "diferencias": "diferencias",
    "preferencia": "preferencia",
    "referencia": "referencia",
    "referencias": "referencias",
    "presencia": "presencia",
    "ausencia": "ausencia",
    "urgencia": "urgencia",
    "emergencia": "emergencia",
    "agencia": "agencia",
    "tendencia": "tendencia",
    "dependencia": "dependencia",
    "independencia": "independencia",
    "correspondencia": "correspondencia",
    "correspondencias": "correspondencias",
}


# Ambiguous forms: only restore accents in safe contexts.
_ES_AMBIGUOUS = frozenset({"como", "que", "si", "el", "tu", "esta", "estas", "estan"})


def restore_spanish_accents(text: str) -> str:
    """Restore common missing Spanish accents (OCR / ASCII paste).

    Safe unambiguous words always; ambiguous ones (el/él, si/sí, que/qué, como/cómo)
    only when punctuation/context strongly suggests the accented form.
    """

    def _replace(match: re.Match[str]) -> str:
        word = match.group(0)
        key = word.lower()
        if key not in _ES_ACCENT_MAP:
            return word
        if key in _ES_AMBIGUOUS:
            return word  # handled in a second pass
        repl = _ES_ACCENT_MAP[key]
        if word.isupper():
            return repl.upper()
        if word[0].isupper():
            return repl[0].upper() + repl[1:]
        return repl

    text = re.sub(r"\b[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+\b", _replace, text)

    # cómo / qué after ¿ or at start of question-like clauses
    text = re.sub(r"(¿\s*)como\b", r"\1cómo", text, flags=re.IGNORECASE)
    text = re.sub(r"(¿\s*)que\b", r"\1qué", text, flags=re.IGNORECASE)
    # sí as short affirmation: ", si." / "¡si!" / " si,"
    text = re.sub(r"(?<=[,:;¡¿\s])si(?=[!?.…,;:])", "sí", text, flags=re.IGNORECASE)
    # está / estás / están (verb) — common after pronouns / subjects
    text = re.sub(r"\b(esta)\b(?=\s+(terriblemente|muy|en|de|con|por|aquí|alli|allí))", "está", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(estas)\b(?=\s+(en|de|con|por|aquí|alli|allí|seguro|segura))", "estás", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(estan)\b(?=\s+(en|de|con|por|aquí|alli|allí))", "están", text, flags=re.IGNORECASE)
    return text


def polish_for_tts(text: str, lang: str | None = None) -> str:
    """Normalize text so TTS reads it naturally."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # Smart quotes → straight quotes
    text = text.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
    # Ellipsis variants
    text = text.replace("…", "...")
    # Common trademark/brand glyphs -> remove so TTS doesn't spell them out.
    text = text.replace("™", "").replace("®", "").replace("©", "").replace("℠", "")
    # Emoji glyphs (OCR can insert them; these make engines mispronounce or skip text).
    text = _strip_emojis(text)
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
    # Spanish accent restore (OCR / ASCII paste → TTS pronunciation)
    lang_code = (lang or detect_language(text) or "en")[:2].lower()
    if lang_code == "es":
        text = restore_spanish_accents(text)
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
