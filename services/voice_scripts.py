"""Training scripts for EN / ES voice samples."""

VOICE_SCRIPTS = {
    "en": """Welcome to CATTS voice training. Read this in your natural voice, calmly, as if narrating an audiobook.

My name is [say your name]. I am recording a personal voice for reading books and live interpretation.

The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.

One, two, three, four, five, six, seven, eight, nine, ten.

Some sentences are short. Others are longer, with pauses, questions, and variety in tone — but always natural.

How are you today? I hope you are well.

Thank you. This sample will teach CATTS to sound like me.""",
    "es": """Bienvenido al entrenamiento de voz de CATTS. Lee esto con tu voz natural, con calma, como si narraras un audiolibro.

Me llamo [di tu nombre]. Estoy grabando mi voz personal para libros y interpretación en vivo.

El veloz murciélago hindú comía feliz cardillo y kiwi.

Uno, dos, tres, cuatro, cinco, seis, siete, ocho, nueve, diez.

Algunas frases son cortas. Otras son más largas, con pausas y variedad de tono.

¿Cómo estás hoy? Espero que muy bien.

Gracias. Esta muestra enseñará a CATTS a sonar como yo.""",
}


def script_for(lang: str | None) -> str:
    key = (lang or "en")[:2].lower()
    return VOICE_SCRIPTS.get(key, VOICE_SCRIPTS["en"])
