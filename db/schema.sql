CREATE TABLE discs (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    release_year INTEGER,
    disc_format  TEXT NOT NULL CHECK (disc_format IN ('4K UHD', 'Blu-ray')),
    label        TEXT,
    audio_format TEXT,
    video_format TEXT,
    aspect_ratio NUMERIC(4, 2) CHECK (aspect_ratio > 0),
    owned        BOOLEAN NOT NULL DEFAULT false,
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);