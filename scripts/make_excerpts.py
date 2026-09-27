"""Write data/derived/excerpts.json: the few short quotes used in REPORT.md.

    python scripts/make_excerpts.py          # needs the local snapshot (data/work/reviews_full.csv)

Each excerpt must be a verbatim substring of the review's title or body (checked here), at most
25 words, and contain no names, phone numbers or order ids. Arabic/Chinese quotes carry an
English gloss written by the author. Only these excerpts - not full review texts - are committed.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import DERIVED_DIR, WORK_DIR, read_csv  # noqa: E402

MAX_WORDS = 25

# (id, review_key, verbatim excerpt, English gloss or None)
SPEC = [
    ("cs_refund", "f3df51789c2fc975",
     "Haven't received my refund yet, it's been 3 days and no proper response from the customer service!", None),
    ("missing_items", "47037b92aca0c74c", "طلبت أربعة أصناف، ولم يصلني سوى صنف واحد",
     "I ordered four items and only one arrived"),
    ("eta_pushed", "62fef1370e1d76b0", "They just keep pushing your delivery schedule further", None),
    ("eta_edited", "3207519f00e7b5f6", "بعد مايتأخر التوصيل تحصل الوقت الي كان موجود متعدل وزايد ومايجيك تعويض",
     "once the delivery is late you find the promised time has been edited upwards, and no compensation comes"),
    ("cancel_10aed", "0f31924ddd1ba5fb", "sorry we can’t cancel the order we will refund you 10 AED", None),
    ("proof_of_delivery", "5c071c1ac37006b6", "مندوب جاب طلبيه صورها مع الباب وسرقها",
     "a courier brought the order, photographed it at the door and took it away"),
    ("daily_coupon", "6b7f1e1df8977a7f", "Love the daily coupon. Really saves a lot and makes me want to order.", None),
    ("no_cash", "1ee0c35cc16288d7", "لا يوجد دفع كاش فقط كي نت", "no cash payment, only KNET (debit card)"),
    ("hk_wrong_food", "630bff9019bfa2d7", "送錯食物,但拒絕退錢", "wrong food delivered, but they refused a refund"),
]


def main():
    rows = {r["review_key"]: r for r in read_csv(WORK_DIR / "reviews_full.csv")}
    out = []
    for qid, key, excerpt, gloss in SPEC:
        r = rows[key]
        if excerpt not in r["text"] and excerpt not in r["title"]:
            sys.exit(f"{qid}: excerpt is not a verbatim substring of review {key}")
        if len(excerpt.split()) > MAX_WORDS:
            sys.exit(f"{qid}: excerpt longer than {MAX_WORDS} words")
        out.append({"id": qid, "review_key": key, "storefront": r["storefront"], "rating": int(r["rating"]),
                    "review_date": r["review_date"], "excerpt": excerpt, "gloss": gloss})
    (DERIVED_DIR / "excerpts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8",
                                               newline="\n")
    print(f"wrote {len(out)} excerpts")


if __name__ == "__main__":
    main()
