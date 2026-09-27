# keeta-review-voc

AI-assisted, reproducible voice-of-customer (VOC) analysis of public App Store reviews of **Keeta**
(the food-delivery app, App Store id 1662451643) in the Gulf markets, with Hong Kong as a comparison.

> Personal project built 2026-09 by Wenjie Luo, using public reviews only.
> **Not affiliated with Keeta or Meituan. No internal data.** Nothing here measures or claims a
> business impact for Keeta.

**Read the findings: [REPORT.md](REPORT.md)** · interactive view: [docs/dashboard.html](docs/dashboard.html)
(download and open locally; single self-contained file).

## What it does

```
Apple customer-reviews RSS (public)            ── scripts/fetch_reviews.py  (the only network step)
  → frozen snapshot, reviewer identity dropped  ── data/raw/ (local) + data/derived/ (committed, text-free)
  → clean + language tag (en / ar / zh / other) ── keeta_voc/text.py
  → issue labels, two methods                   ── rules: keeta_voc/rules.py   LLM: keeta_voc/llm.py
  → scored against a blind reference set        ── scripts/evaluate_labels.py
  → SQLite + committed SQL (sql/*.sql)          ── scripts/compute_metrics.py  (each query re-implemented in pandas and compared)
  → REPORT.md / README.md / dashboard           ── every number rendered from results/ and checked in CI
```

## Data and privacy

- **Source:** Apple's public customer-reviews RSS feed (JSON and XML variants of the same feed), no
  login, throttled requests. Google Play and anything behind a login were deliberately not used.
- **App identity:** the store lookup lists the seller as "Kangaroo Limited" with bundle id
  `com.sankuai.sailor.ifooddelivery`; the Keeta rider and merchant apps share that seller, and
  `com.sankuai` is the Meituan group's namespace (Meituan's own delivery app is sold by
  "Sankuai Technology Co., Ltd."). Evidence: [data/derived/app_identity.json](data/derived/app_identity.json).
- **Storefronts:** Saudi Arabia, Kuwait, UAE, Qatar, Bahrain, Oman and Hong Kong all returned data.
  The feed serves at most 10 pages × 50 reviews per storefront and often answers with empty pages,
  so the snapshot is the union of 4 pulls on 2026-09-27 (every request is logged in
  `data/derived/pull_log_*.json`). In total 2,572 reviews.
- **Privacy:** reviewer names, profile URLs and Apple review ids are never written to disk. Each review
  is keyed by the first 16 hex characters of SHA-256("storefront:review id").
- **What is committed and what is not.** Review texts belong to their authors and are subject to Apple's
  terms, so the full texts are **not** in this repository. The repo commits a text-free table
  (`data/derived/reviews_meta.csv`: key, storefront, rating, app version, date, language, length and a
  hash of the text), the labels of every method, the SHA-256 of the local snapshot file, and only the
  9 short excerpts quoted in the report (`data/derived/excerpts.json`). Everything downstream of
  labelling (label quality, all SQL metrics, the docs) is reproducible from these files, and CI does
  exactly that. Re-running the text-dependent steps needs a fresh pull (see Reproduce).

## Method

- **Taxonomy** (`keeta_voc/taxonomy.yaml`): 11 topic labels for food-delivery ops:
  delivery time, order fulfilment, food quality, rider behaviour, merchant/menu availability, pricing &
  promos, payment & refunds, customer service, app bugs & UX, positive praise, and `other`
  (only when nothing else applies). Multi-label; a label means the topic is discussed, positive or negative.
- **Method 1, rules:** English regexes with word boundaries, Arabic keywords matched after normalisation
  (hamza/alef, ta marbuta, diacritics), Traditional Chinese / Cantonese keywords, and a small negation
  window for praise.
- **Method 2, local LLM:** qwen2.5:3b through Ollama on CPU, temperature 0, output constrained by a
  JSON schema whose enum is the taxonomy, then validated again in Python. Invalid outputs are recorded
  and scored as "no label", never dropped (30 invalid outputs among 2,572 LLM-labelled reviews;
  the snapshot has 2,572). Every prompt and response is logged
  (`data/labels/llm_log.jsonl`; the review text inside each prompt is kept only in the local log).
- **Reference set:** a seeded sample of 180 reviews stratified by storefront × rating band.
  **These reference labels are AI-assisted labels made in the author's workflow** (the AI coding
  assistant used to build the project labelled each review under [a written guide](docs/labeling_guide.md),
  seeing only the text, without ratings or either method's output). They are not independent human
  annotation and not "ground truth". They were committed before either method was scored.
- **Scores:** per-label precision / recall / F1 and Cohen's κ with 2000-resample bootstrap intervals,
  plus a paired bootstrap of the F1 difference between methods.
- **Primary labeler** (rule fixed before scoring, in `scripts/compute_metrics.py`): whichever method has the
  higher micro-F1 on the reference set. Result: **rules**. The other method's tables are kept in
  `results/metrics.json` for comparison.
- **Metrics:** SQL in [`sql/`](sql) (issue share by storefront, by rating, by app version, by month;
  pain-point ranking among 1–2★ reviews; co-occurrence), each checked against an independent pandas
  implementation. Intervals: Wilson and bootstrap for shares, Newcombe for differences.

## Results

### Label quality (reference set, n = 180)

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

**The local LLM scored lower than the keyword rules** (micro-F1 0.70 vs
0.81; difference -0.11, 95% CI [-0.16, -0.07]).
It was clearly worse on: Rider behaviour, Merchant/menu availability, Payment & refunds. It was clearly better on: none.
The language detector agreed with the reference language tag on 98.9% of the
180 reference reviews.

### Markets

| Storefront | Written reviews (n) | Date range | Mean ★ | 1–2★ share | Language mix | All ratings on store (n) | Store average ★ |
| --- | ---: | --- | ---: | ---: | --- | ---: | ---: |
| UAE (`ae`) | 500 | 2026-05-30 → 2026-09-25 | 1.56 | 86% | en 430, ar 64, other 6 | 10,321 | 3.49 |
| Bahrain (`bh`) | 165 | 2025-08-25 → 2026-09-25 | 1.73 | 80% | en 119, ar 43, other 3 | 1,992 | 4.17 |
| Hong Kong (`hk`) | 500 | 2025-04-05 → 2026-09-25 | 1.89 | 76% | zh 359, en 134, other 7 | 134,709 | 4.74 |
| Kuwait (`kw`) | 434 | 2025-07-07 → 2026-09-25 | 1.73 | 81% | en 229, ar 198, other 7 | 4,063 | 3.99 |
| Oman (`om`) | 10 | 2024-10-11 → 2026-09-24 | 1.40 | 90% | ar 8, en 2 | 239 | 4.47 |
| Qatar (`qa`) | 463 | 2024-12-24 → 2026-09-26 | 1.43 | 89% | en 372, ar 87, other 4 | 1,938 | 3.15 |
| Saudi Arabia (`sa`) | 500 | 2026-07-30 → 2026-09-26 | 1.34 | 91% | ar 410, en 86, other 4 | 659,110 | 4.68 |

### Top pain points (share of 1–2★ reviews, primary labeler)

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

See [REPORT.md](REPORT.md) for what the complaints are about, what changed, and recommendations.

## Limitations (这不是什么)

- Not Keeta or Meituan data, and not a measure of customer satisfaction: written reviews are a
  self-selected, complaint-heavy sample (76–91% are 1–2★ where the
  store-wide average is 3.15–4.74★).
- Only the latest 500 reviews per storefront are available, so each market covers a different window;
  Oman (10 reviews) and Bahrain (165) are small.
- Labels have errors (see the table); shares inherit them. Per-label reference support is small for
  some labels, so their intervals are wide.
- The reference labels are AI-assisted, by the same assistant that wrote the rule keywords: agreement
  partly measures consistency between the two, which may favour the rules over the LLM.
- Only a 3B-parameter local model on CPU was tried as the LLM labeler; a larger model or few-shot
  prompting may do better. That was not tested here.
- No causal claims: the UAE change in the latest month is described, not explained.

## Reproduce

From the committed, text-free data (what CI runs; no network, no LLM):

```bash
pip install -r requirements.txt
python -m pytest -q
python scripts/evaluate_labels.py --check && python scripts/compute_metrics.py --check && python scripts/check_numbers.py --check
```

Full re-run from a fresh pull (needs network; Apple only serves the latest reviews, so the numbers
will differ from this snapshot; the LLM step needs [Ollama](https://ollama.com) with `qwen2.5:3b`):

```bash
python scripts/fetch_reviews.py && python scripts/fetch_reviews.py --merge   # repeat --merge until no page gaps
python scripts/build_dataset.py && python scripts/label_rules.py
python scripts/make_reference_sample.py      # then label data/work/reference_worksheet.jsonl -> data/labels/reference.csv
python scripts/label_llm.py --reference-first
python scripts/evaluate_labels.py && python scripts/compute_metrics.py && python scripts/make_excerpts.py
python scripts/check_numbers.py --write && python scripts/build_dashboard.py
```

Test-suite strength is checked by mutation testing (`python scripts/mutation_check.py`): see
[MUTATION.md](MUTATION.md).

## 中文摘要

用公开的 App Store 评论（2,572 条，沙特/科威特/阿联酋/卡塔尔/巴林/阿曼 + 香港对照，快照
2026-09-27）做的 Keeta 用户之声分析，个人项目，与 Keeta/美团无关，不含任何内部数据。

- 书面评论几乎都是投诉：各市场 1–2★ 占 76–91%，而商店总评分均值为
  3.15–4.74★，所以这些评论只能回答"哪里出了问题"。
- 客服在 6 个样本足够的市场中的 5 个是 1–2★ 评论里最常被提到的话题；
  海湾地区提到客服的差评中，34% 同时提到支付/退款，
  问题核心是出错后的补救（退款被拒、只退钱包、只给小额券）。
- 阿联酋例外：配送时效（45%）与客服（44%）并列第一；
  最近一个月 1–2★ 占比从 93% 降到 56%，同时价格/优惠相关好评增加，原因无法从数据判断。
- 方法：关键词规则 vs 本地 LLM（qwen2.5:3b）两种打标，在 180 条参考集上规则更好
  （micro-F1 0.81 vs 0.70），因此主结果用规则；参考标注是 AI 辅助标注，
  不是独立人工标注。所有指标用 SQL 计算并与 pandas 逐项对拍，文档里每个数字由脚本从结果文件生成并在 CI 校验。

## Layout

```
keeta_voc/   package: fetch, text/language, taxonomy, rules, llm, evaluate, db, metrics_pd, stats, render, facts
sql/         schema + every metric query
scripts/     pipeline steps, --check modes, mutation_check.py
data/        derived/ (text-free, committed) · labels/ (all methods + reference) · raw/ work/ (local only)
results/     label_quality.json, metrics.json
docs/        templates for README/REPORT, labelling guide, dashboard.html
```

License: MIT for code and the author's labels and write-ups. Review texts belong to their authors.
