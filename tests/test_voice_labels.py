from services.voice_labels import voice_file_prefix


def test_voice_file_prefix():
    assert voice_file_prefix("My main voice", "en") == "My_main_voice_EN"
    assert voice_file_prefix("Mi voz principal", "es") == "Mi_voz_principal_ES"
    assert voice_file_prefix("", "en") == "voice_EN"
