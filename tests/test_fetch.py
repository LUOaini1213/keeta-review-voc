import json

from keeta_voc.fetch import (KEPT_FIELDS, dedupe, minimise_entry, parse_feed, parse_feed_xml, pull_storefront,
                              review_key)


def _entry(i, rating=5):
    return {"author": {"uri": {"label": "https://itunes.apple.com/ae/reviews/id99"}, "name": {"label": "Real Name"}},
            "updated": {"label": "2026-09-25T11:46:41-07:00"}, "im:rating": {"label": str(rating)},
            "im:version": {"label": "3.12.401"}, "id": {"label": str(i)}, "title": {"label": "t"},
            "content": {"label": "body", "attributes": {"type": "text"}}}


def _feed(entries, last=10):
    return {"feed": {"entry": entries, "link": [{"attributes": {"rel": "last", "href":
            f"https://itunes.apple.com/ae/rss/customerreviews/page={last}/id=1/sortby=mostrecent/xml"}}]}}


def test_minimise_drops_identity():
    r = minimise_entry(_entry(7), "ae")
    assert set(r) == set(KEPT_FIELDS)
    blob = repr(r)
    assert "Real Name" not in blob and "reviews/id99" not in blob and "'7'" not in blob
    assert r["review_key"] == review_key("ae", "7") and len(r["review_key"]) == 16


def test_parse_feed_single_entry_and_last_page():
    reviews, last = parse_feed(_feed(_entry(1), last=4), "ae")
    assert len(reviews) == 1 and last == 4
    reviews, last = parse_feed({"feed": {}}, "sa")
    assert reviews == [] and last is None


def test_pull_retries_empty_pages_and_stops_at_last():
    calls = []
    # page 1: JSON empty, XML empty, JSON has data; page 2: JSON has data at once
    pages = {1: [_feed([], 10), _feed([_entry(1)], 2)], 2: [_feed([_entry(2), _entry(1)], 2)]}

    def get(url):
        page = int(url.split("page=")[1].split("/")[0])
        calls.append(page)
        return 200, json.dumps(pages[page].pop(0)) if url.endswith("json") else XML_EMPTY
    out = pull_storefront("1", "ae", get=get, sleep=lambda s: None)
    assert calls == [1, 1, 1, 2]
    assert len(dedupe(out)) == 2


def test_pull_gives_up_after_retries():
    seen = []

    def get(url):
        seen.append(url[-4:])
        return 200, json.dumps({"feed": {}}) if url.endswith("json") else XML_EMPTY
    out = pull_storefront("1", "sa", retries=3, max_pages=2, get=get, sleep=lambda s: None)
    assert out == [] and seen == ["json", "/xml", "json"] * 2


XML_EMPTY = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss"></feed>'
XML_ONE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:im="http://itunes.apple.com/rss" xmlns="http://www.w3.org/2005/Atom">
<link rel="last" href="https://itunes.apple.com/sa/rss/customerreviews/page=10/id=1/sortby=mostrecent/xml"/>
<entry><id>555</id><title>t1</title><content type="text">body text</content><im:rating>2</im:rating>
<updated>2026-09-25T20:26:21-07:00</updated><im:version>3.12.401</im:version>
<author><name>Somebody</name><uri>https://itunes.apple.com/sa/reviews/id1</uri></author>
<content type="html">&lt;b&gt;html copy&lt;/b&gt;</content></entry>
</feed>"""


def test_parse_xml_matches_json_shape_and_drops_identity():
    reviews, last = parse_feed_xml(XML_ONE, "sa")
    assert last == 10 and len(reviews) == 1
    r = reviews[0]
    assert set(r) == set(KEPT_FIELDS)
    assert (r["rating"], r["text"], r["title"], r["app_version"]) == (2, "body text", "t1", "3.12.401")
    assert r["review_key"] == review_key("sa", "555")
    assert "Somebody" not in repr(r)


def test_gap_page_is_skipped_not_fatal():
    calls = []

    def get(url):
        page = int(url.split("page=")[1].split("/")[0])
        calls.append(page)
        if page == 2:
            return 200, json.dumps({"feed": {}}) if url.endswith("json") else XML_EMPTY
        return 200, json.dumps(_feed([_entry(page)], 3)) if url.endswith("json") else XML_EMPTY
    out = pull_storefront("1", "ae", retries=2, get=get, sleep=lambda s: None)
    assert calls == [1, 2, 2, 3]
    assert len(out) == 2
