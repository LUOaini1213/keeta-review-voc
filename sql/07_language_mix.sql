-- Language mix per storefront.
SELECT storefront, lang, COUNT(*) AS n_reviews,
       1.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY storefront) AS share
FROM reviews
GROUP BY storefront, lang
ORDER BY storefront, n_reviews DESC, lang;
