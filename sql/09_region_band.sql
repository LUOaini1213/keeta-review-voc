-- Share of labelled reviews mentioning each issue, by region (gulf / hk) and rating band
-- (neg = 1-2 stars, mid = 3, pos = 4-5).
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), base AS (
    SELECT r.review_key, r.region,
           CASE WHEN r.rating <= 2 THEN 'neg' WHEN r.rating = 3 THEN 'mid' ELSE 'pos' END AS band
    FROM reviews r JOIN labelled USING (review_key)
), denom AS (
    SELECT region, band, COUNT(*) AS n_reviews FROM base GROUP BY region, band
), hits AS (
    SELECT b.region, b.band, l.label, COUNT(*) AS n_label
    FROM base b JOIN labels l ON l.review_key = b.review_key AND l.method = :method
    GROUP BY b.region, b.band, l.label
)
SELECT d.region, d.band, t.label, d.n_reviews,
       COALESCE(h.n_label, 0)                      AS n_label,
       1.0 * COALESCE(h.n_label, 0) / d.n_reviews   AS share
FROM denom d
CROSS JOIN taxonomy t
LEFT JOIN hits h ON h.region = d.region AND h.band = d.band AND h.label = t.label
ORDER BY d.region, d.band, t.ord;
