import pytest

from keeta_voc.taxonomy import InvalidLabels, finalise, issue_labels, label_names, load_taxonomy, validate_labels


def test_taxonomy_shape():
    names = label_names()
    assert names[-1] == "other"
    assert len(names) == len(set(names)) == 11
    for spec in load_taxonomy()["labels"].values():
        assert spec["definition"]
    assert "other" not in issue_labels()


def test_validate_canonicalises_order_and_duplicates():
    assert validate_labels(["positive_praise", "delivery_time", "delivery_time"]) == ["delivery_time", "positive_praise"]


@pytest.mark.parametrize("bad", [[], None, "delivery_time", ["late"], ["other", "app_ux"], [1], ["Delivery_Time"]])
def test_validate_rejects(bad):
    with pytest.raises(InvalidLabels):
        validate_labels(bad)


def test_finalise():
    assert finalise(set()) == ["other"]
    assert finalise({"other"}) == ["other"]
    assert finalise({"other", "app_ux"}) == ["app_ux"]
