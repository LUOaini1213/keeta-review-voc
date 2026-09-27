# Reference labelling guide

The reference set is a seeded, stratified sample of reviews (see `scripts/make_reference_sample.py`).
The labels are AI-assisted labels produced in the author's workflow: the AI coding assistant
used to build this project (Claude) read every sampled review and labelled it under the rules
below. They have **not** been independently verified by a human annotator, so they are not
"ground truth": they are a careful, documented reference that both automatic labelers are scored
against. Because the reference labeller is itself a (much larger) language model, agreement with
it partly measures agreement between models; see the limitations in the README.

Procedure

- The labeller sees only the review title and body, in shuffled order: no star rating, no
  storefront, and no output of either labeler (the worksheet is written before any labeler
  output is looked at, and the rule/LLM label files are not opened while labelling).
- Labels are fixed once written; they are not revised after seeing the rule or LLM scores.
- Each review also gets a language tag (`en`, `ar`, `zh`, `other`) used to score the language detector.

Rules

1. A label marks a topic the review **talks about**, positive or negative
   ("super fast delivery" and "2 hours late" are both `delivery_time`).
2. Multi-label: assign every topic that is actually discussed; do not infer topics that are not stated
   (a complaint that "the order was cancelled" is `order_fulfilment`, not also `customer_service`,
   unless support is mentioned).
3. `positive_praise` = the review expresses overall satisfaction or praise of Keeta/the service.
   A polite word inside a complaint ("good app but...") counts only if the praise is a real part of the message.
4. `rider_behavior` = the courier is discussed (conduct, communication, finding the address, handing over).
   A late order alone is `delivery_time`, not `rider_behavior`.
5. `order_fulfilment` = missing/wrong items, order never arrived, order cancelled by the merchant or platform.
6. `payment_refund` = charges, payment failures, refunds, wallet credit, compensation.
   `pricing_promos` = price level, fees, discounts, coupons, offers.
7. `app_ux` = the app itself: bugs, crashes, login/OTP, address/map entry, UI, language, tracking screen, ease of use.
8. `merchant_availability` = restaurant/store choice, menu or item availability, closed stores, coverage area.
9. `customer_service` = contact with support: responsiveness, helpfulness, complaint handling.
10. `other` if and only if none of the above applies (e.g. emoji only, "ok", off-topic text).
