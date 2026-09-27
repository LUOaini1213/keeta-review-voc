-- Per storefront and calendar month (UTC): volume, mean rating, share of 1-2 star reviews,
-- and share mentioning each issue.
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), base AS (
    SELECT r.* FROM reviews r JOIN labelled USING (review_key)
), m AS (
    SELECT storefront, month, COUNT(*) AS n_reviews, AVG(rating) AS mean_rating,
           AVG(CASE WHEN rating <= 2 THEN 1.0 ELSE 0 END) AS share_negative
    FROM base GROUP BY storefront, month
), hits AS (
    SELECT b.storefront, b.month, l.label, COUNT(*) AS n_label
    FROM base b JOIN labels l ON l.review_key = b.review_key AND l.method = :method
    GROUP BY b.storefront, b.month, l.label
)
SELECT m.storefront, m.month, m.n_reviews, m.mean_rating, m.share_negative, t.label,
       COALESCE(h.n_label, 0)                      AS n_label,
       1.0 * COALESCE(h.n_label, 0) / m.n_reviews   AS share
FROM m
CROSS JOIN taxonomy t
LEFT JOIN hits h ON h.storefront = m.storefront AND h.month = m.month AND h.label = t.label
ORDER BY m.storefront, m.month, t.ord;
