CREATE TABLE discs (
    id              SERIAL PRIMARY KEY,
    tmdb_id         INTEGER UNIQUE,
    title           TEXT NOT NULL,
    release_year    INTEGER,
    runtime_minutes INTEGER,
    overview        TEXT,
    poster_path     TEXT,
    directors       TEXT,
    top_cast        TEXT,
    disc_format     TEXT NOT NULL CHECK (disc_format IN ('4K UHD', 'Blu-ray')),
    label           TEXT,
    audio_format    TEXT,
    video_format    TEXT,
    aspect_ratio    NUMERIC(4, 2) CHECK (aspect_ratio > 0),
    owned           BOOLEAN NOT NULL DEFAULT false,
    notes           TEXT,
    viewings        INTEGER NOT NULL DEFAULT 0 CHECK (viewings >= 0),
    audio_rating    NUMERIC(2, 1) CHECK (audio_rating BETWEEN 0 AND 5 AND audio_rating * 2 = floor(audio_rating * 2)),
    video_rating    NUMERIC(2, 1) CHECK (video_rating BETWEEN 0 AND 5 AND video_rating * 2 = floor(video_rating * 2)),
    overall_rating  NUMERIC(2, 1) CHECK (overall_rating BETWEEN 0 AND 5 AND overall_rating * 2 = floor(overall_rating * 2)),
    rewatch_rating  NUMERIC(2, 1) CHECK (rewatch_rating BETWEEN 0 AND 5 AND rewatch_rating * 2 = floor(rewatch_rating * 2)),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT watched_before_rated CHECK (
        viewings > 0
        OR (audio_rating IS NULL AND video_rating IS NULL
            AND overall_rating IS NULL AND rewatch_rating IS NULL)
    )
);