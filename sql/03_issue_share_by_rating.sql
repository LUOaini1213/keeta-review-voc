-- Share of labelled reviews mentioning each issue, by star rating (all storefronts pooled).
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), base AS (
    SELECT r.* FROM reviews r JOIN labelled USING (review_key)
), denom AS (
    SELECT rating, COUNT(*) AS n_reviews FROM base GROUP BY rating
), hits AS (
    SELECT b.rating, l.label, COUNT(*) AS n_label
    FROM base b JOIN labels l ON l.review_key = b.review_key AND l.method = :method
    GROUP BY b.rating, l.label
)
SELECT d.rating, t.label, d.n_reviews,
       COALESCE(h.n_label, 0)                        AS n_label,
       1.0 * COALESCE(h.n_label, 0) / d.n_reviews     AS share
FROM denom d
CROSS JOIN taxonomy t
LEFT JOIN hits h ON h.rating = d.rating AND h.label = t.label
ORDER BY d.rating, t.ord;
