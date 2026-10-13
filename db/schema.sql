CREATE TABLE discs (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    release_year INTEGER,
    disc_format  TEXT NOT NULL CHECK (disc_format IN ('4K UHD', 'Blu-ray')),
    owned        BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);