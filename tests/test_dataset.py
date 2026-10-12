from keeta_voc.dataset import clean_reviews
import pytest


def _r(key, text="Late again", title="", rating=2, sf="ae", updated="2026-09-25T20:46:41-07:00"):
    return {"review_key": key, "storefront": sf, "rating": rating, "app_version": "3.12.401", "updated": updated,
            "title": title, "text": text}


def test_clean_reviews_drops_duplicates_empty_and_bad_ratings():
    rows, dropped = clean_reviews([_r("a"), _r("a"), _r("b", text=" ​ ", title=""), _r("c", rating=0),
                                   _r("d", text="التطبيق ممتاز", sf="kw")])
    assert [r["review_key"] for r in rows] == ["a", "d"]
    assert dropped == {"duplicate": 1, "empty": 1, "bad_rating": 1}


def test_clean_reviews_fields():
    rows, _ = clean_reviews([_r("a", title="Bad", text="The  driver was late")])
    r = rows[0]
    assert r["review_date"] == "2026-09-26" and r["month"] == "2026-09"
    assert r["lang"] == "en" and r["text"] == "The driver was late"
    assert r["n_chars"] == len("Bad\nThe driver was late") and len(r["text_sha256"]) == 16


def test_language_falls_back_to_title_when_body_has_no_letters():
    rows, _ = clean_reviews([_r("a", title="التوصيل سريع", text="\U0001f44d")])
    assert rows[0]["lang"] == "ar"


@pytest.mark.parametrize("rating", [True, False, 1.0, 4.9, float("nan"), float("inf"), None, "garbage", "2.0", "", [], {}])
def test_invalid_rating_is_counted_without_coercion_or_crash(rating):
    rows, dropped = clean_reviews([_r("bad", rating=rating), _r("good", rating=5)])
    assert [r["review_key"] for r in rows] == ["good"]
    assert dropped["bad_rating"] == 1


@pytest.mark.parametrize("rating", [1, 5, "1", "5"])
def test_integer_ratings_and_snapshot_integer_strings_remain_valid(rating):
    rows, dropped = clean_reviews([_r("a", rating=rating)])
    assert rows[0]["rating"] == int(rating)
    assert dropped["bad_rating"] == 0
