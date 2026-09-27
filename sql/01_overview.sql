-- Reviews per storefront: volume, mean rating, share of 1-2 star reviews, date range.
SELECT r.storefront,
       COUNT(*)                                        AS n_reviews,
       AVG(r.rating)                                   AS mean_rating,
       AVG(CASE WHEN r.rating <= 2 THEN 1.0 ELSE 0 END) AS share_negative,
       MIN(r.review_date)                              AS first_date,
       MAX(r.review_date)                              AS last_date
FROM reviews r
GROUP BY r.storefront
ORDER BY r.storefront;
