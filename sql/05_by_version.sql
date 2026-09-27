-- Per storefront and app version (versions with at least :min_n labelled reviews):
-- volume, mean rating, share of 1-2 star reviews, and share mentioning each issue.
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), base AS (
    SELECT r.* FROM reviews r JOIN labelled USING (review_key)
), v AS (
    SELECT storefront, app_version, COUNT(*) AS n_reviews, AVG(rating) AS mean_rating,
           AVG(CASE WHEN rating <= 2 THEN 1.0 ELSE 0 END) AS share_negative
    FROM base GROUP BY storefront, app_version HAVING COUNT(*) >= :min_n
), hits AS (
    SELECT b.storefront, b.app_version, l.label, COUNT(*) AS n_label
    FROM base b JOIN labels l ON l.review_key = b.review_key AND l.method = :method
    GROUP BY b.storefront, b.app_version, l.label
)
SELECT v.storefront, v.app_version, v.n_reviews, v.mean_rating, v.share_negative, t.label,
       COALESCE(h.n_label, 0)                      AS n_label,
       1.0 * COALESCE(h.n_label, 0) / v.n_reviews   AS share
FROM v
CROSS JOIN taxonomy t
LEFT JOIN hits h ON h.storefront = v.storefront AND h.app_version = v.app_version AND h.label = t.label
ORDER BY v.storefront, v.app_version, t.ord;
