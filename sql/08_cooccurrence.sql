-- Among 1-2 star labelled reviews of each region, for every ordered pair of issues (a, b):
-- how many mention a, and what share of those also mention b.
-- Shows what a complaint about one topic is usually "about" (e.g. customer service + refunds).
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), neg AS (
    SELECT r.review_key, r.region FROM reviews r JOIN labelled USING (review_key) WHERE r.rating <= 2
), nl AS (
    SELECT n.review_key, n.region, l.label
    FROM neg n JOIN labels l ON l.review_key = n.review_key AND l.method = :method
    WHERE l.label NOT IN ('positive_praise', 'other')
), a_counts AS (
    SELECT region, label AS label_a, COUNT(*) AS n_a FROM nl GROUP BY region, label
), pairs AS (
    SELECT x.region, x.label AS label_a, y.label AS label_b, COUNT(*) AS n_ab
    FROM nl x JOIN nl y ON x.review_key = y.review_key AND x.label <> y.label
    GROUP BY x.region, x.label, y.label
)
SELECT a.region, a.label_a, tb.label AS label_b, a.n_a,
       COALESCE(p.n_ab, 0)                    AS n_ab,
       1.0 * COALESCE(p.n_ab, 0) / a.n_a       AS share_b_given_a
FROM a_counts a
JOIN taxonomy ta ON ta.label = a.label_a
CROSS JOIN taxonomy tb
LEFT JOIN pairs p ON p.region = a.region AND p.label_a = a.label_a AND p.label_b = tb.label
WHERE tb.label NOT IN ('positive_praise', 'other') AND tb.label <> a.label_a
ORDER BY a.region, ta.ord, tb.ord;
