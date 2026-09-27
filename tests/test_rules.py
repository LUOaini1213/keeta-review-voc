import pytest

from keeta_voc.rules import rule_labels
from keeta_voc.taxonomy import validate_labels


@pytest.mark.parametrize("text,expected", [
    ("The food arrived cold and 2 hours late", {"delivery_time", "food_quality"}),
    ("Missing items again and support never answered the live chat", {"order_fulfilment", "customer_service"}),
    ("Delivery fee is too expensive, no coupons", {"pricing_promos"}),
    ("I want a refund to my card", {"payment_refund"}),
    ("App crashes after the update", {"app_ux"}),
    ("The driver was rude", {"rider_behavior"}),
    ("Not many restaurants in my area", {"merchant_availability"}),
    ("Great app!", {"positive_praise"}),
])
def test_english_rules(text, expected):
    assert set(rule_labels("", text)) == expected


@pytest.mark.parametrize("text,expected", [
    ("المندوب ما وصل الطلب", {"rider_behavior", "order_fulfilment"}),
    ("تأخير في التوصيل", {"delivery_time"}),
    ("خدمة العملاء سيئة", {"customer_service"}),
    ("الأسعار غالية", {"pricing_promos"}),
    ("استرجاع المبلغ", {"payment_refund"}),
    ("التطبيق ممتاز", {"positive_praise"}),
])
def test_arabic_rules_with_hamza_and_ta_marbuta_variants(text, expected):
    assert set(rule_labels("", text)) == expected


@pytest.mark.parametrize("text,expected", [
    ("送餐好慢", {"delivery_time"}),
    ("客服唔理人", {"customer_service"}),
    ("退款好難", {"payment_refund"}),
    ("好方便", {"positive_praise"}),
])
def test_chinese_rules(text, expected):
    assert set(rule_labels("", text)) == expected


def test_praise_negation():
    assert rule_labels("", "not good at all") == ["other"]
    assert rule_labels("", "it isn't great") == ["other"]
    assert rule_labels("", "مو زين") == ["other"]
    assert rule_labels("", "唔方便") == ["other"]
    # a negator far before the praise word does not cancel it
    assert rule_labels("", "no complaints, the whole experience was great") == ["customer_service", "positive_praise"]


def test_word_boundaries():
    # 'late' must not fire inside 'chocolate'; 'ui' not inside 'rebuild'
    assert "delivery_time" not in rule_labels("", "chocolate cake")
    assert "app_ux" not in rule_labels("", "rebuild")


def test_title_is_used():
    assert rule_labels("Refund please", "") == ["payment_refund"]


def test_other_only_when_nothing_else():
    assert rule_labels("", "hmm") == ["other"]
    assert "other" not in rule_labels("", "late")


def test_output_always_valid():
    for t in ["", "late", "great late refund driver", "送餐好慢", "مندوب"]:
        assert validate_labels(rule_labels("", t)) == rule_labels("", t)
