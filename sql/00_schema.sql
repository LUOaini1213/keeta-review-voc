-- Tables loaded by keeta_voc/db.py. One row per review; one row per (review, method, label).
CREATE TABLE reviews (
    review_key   TEXT PRIMARY KEY,
    storefront   TEXT NOT NULL,
    region       TEXT NOT NULL,   -- gulf / hk (derived from storefront)
    rating       INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    app_version  TEXT NOT NULL,
    review_date  TEXT NOT NULL,   -- YYYY-MM-DD (UTC)
    month        TEXT NOT NULL,   -- YYYY-MM
    lang         TEXT NOT NULL,   -- en / ar / zh / other
    n_chars      INTEGER NOT NULL
);
CREATE TABLE labels (
    review_key TEXT NOT NULL REFERENCES reviews(review_key),
    method     TEXT NOT NULL,     -- rules / llm / reference
    label      TEXT NOT NULL,
    PRIMARY KEY (review_key, method, label)
);
CREATE TABLE taxonomy (
    label TEXT PRIMARY KEY,
    ord   INTEGER NOT NULL
);
CREATE INDEX labels_by_method ON labels(method, label);
