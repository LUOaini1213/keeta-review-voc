"""Network layer: pull public App Store reviews for one app from Apple's customer-reviews RSS.

Only this module touches the network. Everything downstream runs from the frozen snapshot.

Privacy: the RSS entry carries the reviewer's display name and profile URI. They are never
written anywhere; `minimise_entry` keeps only the fields listed in KEPT_FIELDS and replaces the
Apple review id with a salted-free SHA-256 prefix of "<storefront>:<id>".
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405 - Apple feed
from dataclasses import dataclass, field

RSS_URL = "https://itunes.apple.com/{cc}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
LOOKUP_URL = "https://itunes.apple.com/lookup?id={app_id}&country={cc}"
USER_AGENT = "keeta-review-voc/1.0 (personal research; polite, throttled)"
_ATOM = "{http://www.w3.org/2005/Atom}"
_IM = "{http://itunes.apple.com/rss}"
KEPT_FIELDS = ("review_key", "storefront", "rating", "app_version", "updated", "title", "text")


def review_key(storefront: str, apple_review_id: str) -> str:
    """Stable, non-reversible-in-practice key for a review (16 hex chars of SHA-256)."""
    return hashlib.sha256(f"{storefront}:{apple_review_id}".encode("utf-8")).hexdigest()[:16]


def _label(entry: dict, name: str) -> str | None:
    v = entry.get(name)
    if isinstance(v, dict):
        return v.get("label")
    return None


def minimise_entry(entry: dict, storefront: str) -> dict:
    """Drop reviewer identity; keep only what the analysis needs."""
    rid = _label(entry, "id")
    if not rid:
        raise ValueError("RSS entry without a review id")
    rating = int(_label(entry, "im:rating"))
    return {
        "review_key": review_key(storefront, rid),
        "storefront": storefront,
        "rating": rating,
        "app_version": _label(entry, "im:version") or "",
        "updated": _label(entry, "updated") or "",
        "title": _label(entry, "title") or "",
        "text": (entry.get("content") or {}).get("label", "") or "",
    }


def parse_feed(payload: dict, storefront: str) -> tuple[list[dict], int | None]:
    """Return (minimised reviews, last page number advertised by the feed or None)."""
    feed = payload.get("feed", {})
    entries = feed.get("entry", [])
    if isinstance(entries, dict):  # a single entry is not wrapped in a list
        entries = [entries]
    # Old-style feeds put the app itself as the first entry; it has no rating.
    reviews = [minimise_entry(e, storefront) for e in entries if "im:rating" in e]
    last = None
    for link in feed.get("link", []):
        attrs = link.get("attributes", {})
        if attrs.get("rel") == "last" and "page=" in attrs.get("href", ""):
            try:
                last = int(attrs["href"].split("page=")[1].split("/")[0])
            except ValueError:
                last = None
    return reviews, last


def parse_feed_xml(text: str, storefront: str) -> tuple[list[dict], int | None]:
    """Same as parse_feed for the Atom/XML variant of the feed."""
    root = ET.fromstring(text)
    reviews = []
    for e in root.findall(f"{_ATOM}entry"):
        rating = e.find(f"{_IM}rating")
        if rating is None:
            continue
        content = next((c for c in e.findall(f"{_ATOM}content") if c.get("type") == "text"), None)
        as_json = {"id": {"label": e.findtext(f"{_ATOM}id")}, "im:rating": {"label": rating.text},
                   "im:version": {"label": e.findtext(f"{_IM}version")},
                   "updated": {"label": e.findtext(f"{_ATOM}updated")},
                   "title": {"label": e.findtext(f"{_ATOM}title")},
                   "content": {"label": content.text if content is not None else ""}}
        reviews.append(minimise_entry(as_json, storefront))
    last = None
    for link in root.findall(f"{_ATOM}link"):
        href = link.get("href", "")
        if link.get("rel") == "last" and "page=" in href:
            try:
                last = int(href.split("page=")[1].split("/")[0])
            except ValueError:
                last = None
    return reviews, last


def http_get(url: str, timeout: float = 30.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https host
        return resp.status, resp.read().decode("utf-8")


def http_get_json(url: str, timeout: float = 30.0) -> tuple[int, dict]:
    status, text = http_get(url, timeout)
    return status, json.loads(text)


@dataclass
class PullLog:
    requests: list[dict] = field(default_factory=list)

    def add(self, **kw):
        self.requests.append(kw)


# Four URL spellings of the same "most recent first" feed. Apple's default sort for this feed is
# most-recent (checked 2026-09-27: page 2 without `sortby` covered the days just before page 1),
# and each spelling is cached separately, so when one answers empty another often has data.
VARIANTS = (("sortby=mostrecent/", "json"), ("sortby=mostrecent/", "xml"), ("", "json"), ("", "xml"))


def feed_url(app_id: str, cc: str, page: int, variant: int) -> str:
    sort, fmt = VARIANTS[variant % len(VARIANTS)]
    return f"https://itunes.apple.com/{cc}/rss/customerreviews/page={page}/id={app_id}/{sort}{fmt}"


def fetch_page(app_id: str, cc: str, page: int, variant: int, get=http_get) -> tuple[int, list[dict], int | None]:
    url = feed_url(app_id, cc, page, variant)
    status, text = get(url)
    if url.endswith("xml"):
        reviews, last = parse_feed_xml(text, cc)
    else:
        reviews, last = parse_feed(json.loads(text), cc)
    return status, reviews, last


def pull_storefront(app_id: str, cc: str, *, max_pages: int = 10, retries: int = 8, pause: float = 3.0,
                    get=http_get, sleep=time.sleep, log: PullLog | None = None) -> list[dict]:
    """Pull up to `max_pages` pages (the feed caps at 10 x 50 reviews).

    The feed is flaky: a URL often answers HTTP 200 with zero entries while another spelling of
    the same feed has data, and this flips over time. Each page is therefore requested cycling
    through VARIANTS with growing back-off until it returns entries. A page still empty after
    `retries` attempts is logged as a gap and the pull moves on to the next page (the page count
    advertised by the feed's `last` link bounds the loop). Gaps are filled by later passes run
    with `fetch_reviews.py --merge`, which unions reviews by key."""
    log = log or PullLog()
    out: list[dict] = []
    last_page = max_pages
    page = 1
    while page <= min(max_pages, last_page):
        reviews: list[dict] = []
        for attempt in range(1, retries + 1):
            variant = attempt - 1
            try:
                status, reviews, adv_last = fetch_page(app_id, cc, page, variant, get=get)
                err = None
            except Exception as exc:  # network / parse errors are logged, then retried
                status, reviews, adv_last, err = None, [], None, repr(exc)[:200]
            log.add(storefront=cc, page=page, attempt=attempt, variant="".join(VARIANTS[variant % len(VARIANTS)]),
                    status=status, n=len(reviews), error=err)
            sleep(min(pause * attempt, 20.0) if not reviews else pause)
            if reviews:
                if adv_last:
                    last_page = adv_last
                break
        if not reviews:
            log.add(storefront=cc, page=page, gap=True)
        out.extend(reviews)
        page += 1
    return out


def dedupe(reviews: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in reviews:
        if r["review_key"] in seen:
            continue
        seen.add(r["review_key"])
        out.append(r)
    return out
