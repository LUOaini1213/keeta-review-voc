from keeta_voc.text import clean_text, detect_language, match_form, normalise_arabic, review_date


def test_clean_text_collapses_space_and_strips_controls():
    assert clean_text("  Late​  order\n\n again‏ ") == "Late order again"
    assert clean_text(None) == ""


def test_clean_text_folds_fullwidth_and_arabic_presentation_forms():
    assert clean_text("ＡＰＰ") == "APP"
    # presentation forms of the word mandoob (courier)
    assert clean_text("ﻣﻨﺪﻮﺏ") == "مندوب"


def test_arabic_normalisation():
    assert normalise_arabic("تأخير") == "تاخير"
    assert normalise_arabic("إلغاء") == "الغاء"
    assert normalise_arabic("خدمة") == "خدمه"
    assert normalise_arabic("مستشفى") == "مستشفي"
    assert normalise_arabic("طـــلب") == "طلب"          # tatweel
    assert normalise_arabic("طَلَبٌ") == "طلب"          # diacritics


def test_match_form_lowercases():
    assert match_form("LATE Delivery") == "late delivery"


def test_detect_language_basic():
    assert detect_language("The driver was very late") == "en"
    assert detect_language("التطبيق ممتاز") == "ar"
    assert detect_language("送餐好慢") == "zh"
    assert detect_language("\U0001f44d\U0001f44d\U0001f44d") == "other"
    assert detect_language("12345") == "other"
    assert detect_language("") == "other"


def test_detect_language_latin_without_english_words_is_other():
    assert detect_language("Mahal masyado ang bayad") == "other"


def test_detect_language_majority_script_wins():
    assert detect_language("التطبيق ممتاز جدا والتوصيل سريع app") == "ar"
    assert detect_language("good app but the delivery is slow جيد") == "en"
    # four Han characters (weight 3 each) outweigh four Latin letters
    assert detect_language("好用 好快 okay") == "zh"


def test_review_date_converts_to_utc():
    assert review_date("2026-09-25T20:46:41-07:00") == "2026-09-26"
    assert review_date("2026-09-25T11:46:41-07:00") == "2026-09-25"
