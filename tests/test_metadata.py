from services.book_metadata import apply_chapter_naming, guess_metadata_from_filename


def test_guess_gurdjieff_filename():
    g = guess_metadata_from_filename("Recordando-a-Gurdjieff-Peters-Fritz.pdf")
    assert "Gurdjieff" in g["title"]
    assert g["author"]


def test_chapter_numbering_es():
    chapters = [{"title": "Intro", "content": "x"}]
    out = apply_chapter_naming(chapters, mode="number", lang="es")
    assert out[0]["title"].startswith("Capítulo")
