-- One-time import: copy every disc from the old app's tables into the new discs table.
-- Runs in a throwaway database that holds both the old backup and the new schema.

INSERT INTO discs (
    tmdb_id, title, release_year, runtime_minutes, overview, poster_path,
    directors, top_cast,
    disc_format, label, audio_format, video_format, aspect_ratio,
    genres, owned, notes, viewings,
    audio_rating, video_rating, overall_rating, rewatch_rating,
    created_at
)
SELECT
    t."tmdbId",
    t.title,
    extract(year FROM t."releaseDate")::int,
    t."runtimeMinutes",
    t.overview,
    t."posterPath",

    -- Many people per film become one line of text, e.g. "Joel Coen, Ethan Coen".
    (SELECT string_agg(p.name, ', ' ORDER BY tp.id)
       FROM "TitlePerson" tp JOIN "Person" p ON p.id = tp."personId"
      WHERE tp."titleId" = t.id AND tp.role = 'DIRECTOR'),
    (SELECT string_agg(name, ', ' ORDER BY "billingOrder")
       FROM (SELECT p.name, tp."billingOrder"
               FROM "TitlePerson" tp JOIN "Person" p ON p.id = tp."personId"
              WHERE tp."titleId" = t.id AND tp.role = 'ACTOR'
              ORDER BY tp."billingOrder"
              LIMIT 5) AS top_five),

    CASE t."discFormat" WHEN 'UHD_4K' THEN '4K UHD' ELSE 'Blu-ray' END,
    v.name,
    a.name,
    vf.name,
    t."aspectRatio",

    -- The old join table becomes a plain list of genre names.
    COALESCE((SELECT array_agg(g.name ORDER BY g.name)
                FROM "_GenreToTitle" gt JOIN "Genre" g ON g.id = gt."A"
               WHERE gt."B" = t.id), '{}'),

    t.owned,
    t.notes,
    t.viewings,
    t."audioQuality",
    t."videoQuality",
    t."overallQuality",
    t.rewatchability,
    t."createdAt"
FROM "Title" t
LEFT JOIN "Vendor"      v  ON v.id  = t."vendorId"
LEFT JOIN "AudioFormat" a  ON a.id  = t."audioFormatId"
LEFT JOIN "VideoFormat" vf ON vf.id = t."videoFormatId"
ORDER BY t."createdAt";