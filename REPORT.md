# Keeta App Store reviews: what customers complain about (Gulf + Hong Kong)

*Voice-of-customer readout from 2,572 public App Store reviews, snapshot 2026-09-27.
Personal project built 2026-09 by Wenjie Luo from public data only. Not affiliated with Keeta or
Meituan; no internal data. Every number below is generated from `results/` and checked in CI.*

## TL;DR

1. **The written-review channel is a complaint channel.** In the 6 storefronts with enough
   data, 76–91% of written reviews are 1–2★ (mean
   1.34–1.89★), while the same app's all-ratings store
   average is 3.15–4.74★. Read these reviews as a list of
   *what goes wrong*, not as a satisfaction score.
2. **Customer service is the most-mentioned topic in 1–2★ reviews in 5 of
   6 markets** (Bahrain, Hong Kong, Kuwait, Qatar, Saudi Arabia); in the Gulf markets it appears in
   41–48% of complaints.
3. **It is mostly failed service recovery.** Of Gulf complaints that mention customer service,
   34% also mention payment/refunds,
   33% delivery time and
   30% a missing/wrong/undelivered order.
4. **UAE is different:** delivery time (45%) and customer service
   (44%) are statistically tied at the top, and rider behaviour is
   raised in 26% of complaints (Gulf-wide:
   19%).
5. **UAE, 2026-09:** the 1–2★ share of written reviews fell to
   56% from 93% in the previous three months,
   while mentions of prices/promos rose to 41%
   (from 19%). This data cannot say why (see below).
6. **Hong Kong** (comparison market): pricing & promos is the second-most-mentioned complaint topic
   (31% of 1–2★ reviews).

Method note: labels come from a keyword/rule labeler, which scored **higher** than a local LLM
(qwen2.5:3b) against a 180-review reference set (micro-F1
0.81 vs 0.70). Details and caveats at the end.

## 1. Market snapshot

| Storefront | Written reviews (n) | Date range | Mean ★ | 1–2★ share | Language mix | All ratings on store (n) | Store average ★ |
| --- | ---: | --- | ---: | ---: | --- | ---: | ---: |
| UAE (`ae`) | 500 | 2026-05-30 → 2026-09-25 | 1.56 | 86% | en 430, ar 64, other 6 | 10,321 | 3.49 |
| Bahrain (`bh`) | 165 | 2025-08-25 → 2026-09-25 | 1.73 | 80% | en 119, ar 43, other 3 | 1,992 | 4.17 |
| Hong Kong (`hk`) | 500 | 2025-04-05 → 2026-09-25 | 1.89 | 76% | zh 359, en 134, other 7 | 134,709 | 4.74 |
| Kuwait (`kw`) | 434 | 2025-07-07 → 2026-09-25 | 1.73 | 81% | en 229, ar 198, other 7 | 4,063 | 3.99 |
| Oman (`om`) | 10 | 2024-10-11 → 2026-09-24 | 1.40 | 90% | ar 8, en 2 | 239 | 4.47 |
| Qatar (`qa`) | 463 | 2024-12-24 → 2026-09-26 | 1.43 | 89% | en 372, ar 87, other 4 | 1,938 | 3.15 |
| Saudi Arabia (`sa`) | 500 | 2026-07-30 → 2026-09-26 | 1.34 | 91% | ar 410, en 86, other 4 | 659,110 | 4.68 |

Oman has only 10 written reviews in the feed and is not analysed on its own.
Date ranges differ by market because Apple's feed only serves the latest 500 reviews: in Saudi
Arabia those cover about two months, in Qatar more than a year.

## 2. Top pain points per market

Share of each market's 1–2★ reviews that mention the issue; 95% bootstrap intervals
(2000 resamples); *P(rank 1)* = how often the issue came out on top across resamples.

| Storefront | 1–2★ reviews | Issue (rank) | Share of 1–2★ [95% CI] | P(rank 1) |
| --- | ---: | --- | --- | ---: |
| UAE | 430 | 1. Delivery time | 45% [40–50%] | 0.62 |
|  |  | 2. Customer service | 44% [40–49%] | 0.41 |
|  |  | 3. Payment & refunds | 31% [27–35%] | 0.00 |
| Bahrain | 132 | 1. Customer service | 45% [37–54%] | 1.00 |
|  |  | 2. Payment & refunds | 31% [23–39%] | 0.01 |
|  |  | 3. Delivery time | 27% [19–34%] | 0.00 |
| Hong Kong | 380 | 1. Customer service | 34% [30–39%] | 0.88 |
|  |  | 2. Pricing & promos | 31% [26–35%] | 0.12 |
|  |  | 3. Payment & refunds | 29% [24–33%] | 0.02 |
| Kuwait | 351 | 1. Customer service | 48% [42–53%] | 1.00 |
|  |  | 2. Payment & refunds | 31% [26–36%] | 0.00 |
|  |  | 3. Delivery time | 30% [26–35%] | 0.00 |
| Oman | 9 | too few 1–2★ reviews to rank (< 30) |  |  |
| Qatar | 413 | 1. Customer service | 47% [42–52%] | 1.00 |
|  |  | 2. Delivery time | 32% [28–37%] | 0.00 |
|  |  | 3. Payment & refunds | 27% [23–31%] | 0.00 |
| Saudi Arabia | 456 | 1. Customer service | 41% [37–46%] | 1.00 |
|  |  | 2. Payment & refunds | 26% [22–30%] | 0.00 |
|  |  | 3. Order fulfilment | 24% [21–28%] | 0.00 |

Reading: customer service leads everywhere except the UAE; in the other Gulf markets its
P(rank 1) is at least 0.99. In the UAE, delivery time and customer service swap
places across resamples (P(rank 1) counts ties for both, so the column can sum to more than 1). The second place is contested between
payment/refunds, delivery time and order fulfilment, whose intervals overlap.

## 3. What a customer-service complaint is about

Gulf 1–2★ reviews that mention customer service, and what else they mention:

| Also mentions (Customer service complaints, Gulf (pooled)) | Reviews | Share |
| --- | ---: | ---: |
| Payment & refunds | 277 / 806 | 34% |
| Delivery time | 267 / 806 | 33% |
| Order fulfilment | 240 / 806 | 30% |
| Rider behaviour | 183 / 806 | 23% |
| Pricing & promos | 145 / 806 | 18% |
| Food quality | 103 / 806 | 13% |
| App bugs & UX | 60 / 806 | 7% |
| Merchant/menu availability | 16 / 806 | 2% |

The typical story is a chain: something goes wrong with the order (late, missing items, never
arrived), the customer contacts support, and the complaint is about the outcome: a refund refused,
paid to the in-app wallet only, or replaced by a small voucher. Examples (short excerpts; Arabic and
Chinese glossed by the author):

- “Haven't received my refund yet, it's been 3 days and no proper response from the customer service!” (Oman, 1★)
- “طلبت أربعة أصناف، ولم يصلني سوى صنف واحد” — *I ordered four items and only one arrived* (Saudi Arabia, 1★)
- “sorry we can’t cancel the order we will refund you 10 AED” (UAE, 1★)
- “送錯食物,但拒絕退錢” — *wrong food delivered, but they refused a refund* (Hong Kong, 1★)

Delivery-time complaints often question the ETA itself rather than lateness alone:

- “They just keep pushing your delivery schedule further” (UAE, 3★)
- “بعد مايتأخر التوصيل تحصل الوقت الي كان موجود متعدل وزايد ومايجيك تعويض” — *once the delivery is late you find the promised time has been edited upwards, and no compensation comes* (Saudi Arabia, 3★)

And a recurring rider-related claim is about proof of delivery:

- “مندوب جاب طلبيه صورها مع الباب وسرقها” — *a courier brought the order, photographed it at the door and took it away* (Oman, 1★)

## 4. What changed: UAE

The UAE is the only market with enough recent reviews to compare the latest month with the three
before it (at least 30 reviews in each period). Rows shown are those whose 95% interval excludes zero:

| Share of written reviews | 2026-06, 2026-07, 2026-08 (n = 386) | 2026-09 (n = 93) | Difference [95% CI] |
| --- | ---: | ---: | --- |
| 1–2★ reviews | 93% | 56% | -37 pp [-47, -27] |
| mentions Delivery time | 45% | 31% | -14 pp [-24, -3] |
| mentions Order fulfilment | 21% | 11% | -10 pp [-17, -2] |
| mentions Rider behaviour | 25% | 15% | -10 pp [-18, -1] |
| mentions Pricing & promos | 19% | 41% | +21 pp [+11, +32] |
| mentions Customer service | 44% | 19% | -24 pp [-33, -14] |
| mentions Positive praise | 14% | 38% | +24 pp [+14, +35] |

By app version (versions with at least 10 reviews):

| App version | Reviews | Mean ★ | 1–2★ share |
| --- | ---: | ---: | ---: |
| 3.8.401 | 34 | 1.12 | 97% |
| 3.8.402 | 34 | 1.24 | 94% |
| 3.8.500 | 23 | 1.52 | 83% |
| 3.9.200 | 59 | 1.24 | 95% |
| 3.9.300 | 14 | 1.00 | 100% |
| 3.9.400 | 38 | 1.26 | 95% |
| 3.9.500 | 30 | 1.30 | 90% |
| 3.10.200 | 50 | 1.10 | 98% |
| 3.10.400 | 45 | 1.29 | 93% |
| 3.11.200 | 17 | 1.35 | 94% |
| 3.11.300 | 27 | 1.41 | 89% |
| 3.11.400 | 52 | 1.92 | 77% |
| 3.12.200 | 52 | 2.92 | 52% |
| 3.12.401 | 24 | 2.58 | 58% |

The shift is concentrated in the 2026-09 reviews and the newest app versions, and it
comes with more short 4–5★ reviews that praise prices and vouchers (the same theme as in 4–5★
reviews elsewhere, e.g. “Love the daily coupon. Really saves a lot and makes me want to order.” (Qatar, 5★)). This data cannot separate the possible causes: a product change in the
newer versions, a promotion campaign, or a change in who is prompted to leave a review. In Saudi
Arabia, the other market with enough recent volume, the 1–2★ share did not move
(91% in 2026-09 vs 91% before).

## 5. Recommendations (each tied to a metric that would show whether it worked)

These are hypotheses for an operations team to test, not claims of impact. Each names the review-based
metric this pipeline already produces, plus the internal metric that would be the real test.

1. **Refund missing/wrong items to the original payment method, fast, with a photo-based self-serve
   flow.** Review metric: share of 1–2★ reviews mentioning payment/refunds (Gulf now
   29%) and order fulfilment (24%).
   Internal metric: time-to-refund and repeat contacts per order issue, compared between a pilot
   market/cohort and a holdout.
2. **Give first-line chat agents a bounded compensation budget so the first contact can close the
   case.** Review metric: share of 1–2★ reviews mentioning customer service
   (Gulf 45%). Internal metric: first-contact resolution rate and
   post-chat CSAT, A/B by agent group.
3. **Keep the promised ETA fixed for lateness compensation and show the reason for any revision.**
   Review metric: delivery-time share of UAE 1–2★ reviews (45%).
   Internal metric: share of orders delivered after the *first* promised ETA, and ETA revisions per order.
4. **Tighten proof of delivery for "left at the door" orders (geo-stamped photo plus customer
   confirmation) in the UAE first.** Review metric: rider-behaviour share of UAE 1–2★ reviews
   (26%). Internal metric: disputed-delivery rate and refunds for
   "not received" claims.
5. **Watch promo dependence.** Prices and vouchers are what 4–5★ reviewers praise
   (34% of Gulf 4–5★ reviews mention them), and the UAE
   improvement came with a promo-heavy review mix. Internal metric: retention and order frequency of
   promo-acquired users vs a holdout without the promotion.

## 6. Limitations: what this is not

- **Not Keeta data.** Public App Store reviews only (no Google Play, no in-app feedback, no order data).
- **A self-selected sample.** People who write reviews skew angry (see the store average vs the
  written-review mean above), so shares describe complaints, not the customer base.
- **Only the latest 500 reviews per market**, so windows differ by market; small n for Bahrain
  (165) and Oman (10); month and version comparisons are only made where
  n allows.
- **Label errors.** The rule labeler's per-label F1 against the reference ranges from
  0.62 (App bugs & UX) to 0.94 (Rider behaviour); shares
  inherit those errors. Low-support labels (merchant availability, n = 10
  in the reference) are the least reliable.
- **The reference labels are AI-assisted** (see README): they were made by the same AI assistant that
  wrote the rule keywords, so the comparison may favour the rules.
- **Feed quirks.** Apple's feed returned empty pages at random; the snapshot is the union of
  4 pulls on 2026-09-27, so a few reviews at page boundaries may be missing.

## Appendix: label quality (reference set, n = 180)

| Label | Ref. n | Rules P / R | Rules F1 [95% CI] | Rules κ | LLM P / R | LLM F1 [95% CI] | LLM κ | LLM − rules F1 [95% CI] |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | --- |
| Delivery time | 41 | 0.77 / 0.90 | 0.83 [0.74–0.91] | 0.78 | 0.90 / 0.63 | 0.74 [0.62–0.85] | 0.68 | -0.09 [-0.22, +0.03] |
| Order fulfilment | 36 | 0.70 / 0.72 | 0.71 [0.58–0.82] | 0.64 | 0.76 / 0.61 | 0.68 [0.53–0.79] | 0.61 | -0.04 [-0.17, +0.11] |
| Food quality | 19 | 0.71 / 0.63 | 0.67 [0.45–0.82] | 0.63 | 0.83 / 0.53 | 0.65 [0.42–0.82] | 0.61 | -0.02 [-0.30, +0.26] |
| Rider behaviour | 24 | 0.96 / 0.92 | 0.94 [0.84–1.00] | 0.93 | 0.67 / 0.67 | 0.67 [0.49–0.81] | 0.62 | -0.27 [-0.46, -0.12] |
| Merchant/menu availability | 10 | 0.75 / 0.60 | 0.67 [0.35–0.89] | 0.65 | 0.25 / 0.60 | 0.35 [0.14–0.56] | 0.30 | -0.31 [-0.57, -0.05] |
| Pricing & promos | 38 | 0.77 / 0.89 | 0.83 [0.73–0.91] | 0.78 | 0.84 / 0.68 | 0.75 [0.62–0.86] | 0.70 | -0.08 [-0.20, +0.05] |
| Payment & refunds | 58 | 0.92 / 0.79 | 0.85 [0.77–0.92] | 0.79 | 0.85 / 0.48 | 0.62 [0.48–0.72] | 0.50 | -0.24 [-0.36, -0.13] |
| Customer service | 70 | 0.98 / 0.86 | 0.92 [0.86–0.96] | 0.87 | 0.80 / 0.91 | 0.85 [0.79–0.91] | 0.75 | -0.06 [-0.13, +0.00] |
| App bugs & UX | 17 | 0.67 / 0.59 | 0.62 [0.40–0.80] | 0.59 | 0.70 / 0.41 | 0.52 [0.24–0.73] | 0.48 | -0.11 [-0.41, +0.21] |
| Positive praise | 38 | 0.69 / 0.95 | 0.80 [0.70–0.88] | 0.74 | 1.00 / 0.61 | 0.75 [0.63–0.86] | 0.71 | -0.05 [-0.20, +0.11] |
| Other | 17 | 0.67 / 0.71 | 0.69 [0.48–0.84] | 0.65 | 0.75 / 0.35 | 0.48 [0.19–0.70] | 0.45 | -0.21 [-0.44, +0.00] |
| **Micro-F1, all labels** | 180 |  | **0.81** [0.78–0.84] |  |  | **0.70** [0.66–0.74] |  | -0.11 [-0.16, -0.07] |

The LLM (qwen2.5:3b, CPU, temperature 0, JSON-schema constrained) scored **lower**
than the rules overall. Labels where the LLM was better with a 95% interval above zero:
none. Labels where it was clearly worse: Rider behaviour, Merchant/menu availability, Payment & refunds. Its outputs are kept in
`data/labels/llm.csv` and every prompt/response in `data/labels/llm_log.jsonl`
(5 invalid outputs out of 638, counted as "no label", not dropped).
