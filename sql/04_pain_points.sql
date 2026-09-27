-- Pain points: among 1-2 star reviews of each storefront, share mentioning each issue,
-- ranked (1 = most mentioned). 'positive_praise' and 'other' are not pain points.
WITH labelled AS (
    SELECT DISTINCT review_key FROM labels WHERE method = :method
), neg AS (
    SELECT r.* FROM reviews r JOIN labelled USING (review_key) WHERE r.rating <= 2
), denom AS (
    SELECT storefront, COUNT(*) AS n_negative FROM neg GROUP BY storefront
), hits AS (
    SELECT n.storefront, l.label, COUNT(*) AS n_label
    FROM neg n JOIN labels l ON l.review_key = n.review_key AND l.method = :method
    GROUP BY n.storefront, l.label
), shares AS (
    SELECT d.storefront, t.label, t.ord, d.n_negative,
           COALESCE(h.n_label, 0)                       AS n_label,
           1.0 * COALESCE(h.n_label, 0) / d.n_negative   AS share
    FROM denom d
    CROSS JOIN taxonomy t
    LEFT JOIN hits h ON h.storefront = d.storefront AND h.label = t.label
    WHERE t.label NOT IN ('positive_praise', 'other')
)
SELECT storefront, label, n_negative, n_label, share,
       RANK() OVER (PARTITION BY storefront ORDER BY n_label DESC) AS rank
FROM shares
ORDER BY storefront, rank, ord;
