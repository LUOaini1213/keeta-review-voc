-- Share of labelled reviews that mention each issue, per storefront (all ratings).
-- Denominator: reviews that have a valid label set from :method.
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), base AS (
    SELECT r.* FROM reviews r JOIN labelled USING (review_key)
), denom AS (
    SELECT storefront, COUNT(*) AS n_reviews FROM base GROUP BY storefront
), hits AS (
    SELECT b.storefront, l.label, COUNT(*) AS n_label
    FROM base b JOIN labels l ON l.review_key = b.review_key AND l.method = :method
    GROUP BY b.storefront, l.label
)
SELECT d.storefront, t.label, d.n_reviews,
       COALESCE(h.n_label, 0)                        AS n_label,
       1.0 * COALESCE(h.n_label, 0) / d.n_reviews     AS share
FROM denom d
CROSS JOIN taxonomy t
LEFT JOIN hits h ON h.storefront = d.storefront AND h.label = t.label
ORDER BY d.storefront, t.ord;
