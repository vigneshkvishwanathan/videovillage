# Video Village

![CI](https://github.com/vigneshkvishwanathan/videovillage/actions/workflows/ci.yml/badge.svg)

A small web app my brother and I use to catalogue our 4K UHD and Blu-ray discs,
rate them, and see them ranked by score.

## What it does

- **Add a disc by searching TMDb.** Title, year, poster, director and cast fill in automatically.
- **Record the disc itself:** format, label, audio and video format, aspect ratio.
- **Rate it** on audio, video, overall and rewatchability (0–5, in half steps).
  You can only rate a disc you've watched, enforced by the app *and* the database.
- **Score:** `(audio + video + overall + rewatch) × 5 + viewings − 1`, calculated on the fly, never stored.
- **Browse** the collection and the wishlist, with search, format and genre filters, and sorting.

## How it's built

| Piece | Tool |
|---|---|
| Web app | Python, Flask, Jinja templates |
| Database | PostgreSQL, one table, plain SQL (no ORM) |
| Running it | Docker Compose: a `web` container and a `db` container |
| Tests | pytest, run inside the Docker image |
| CI | GitHub Actions: build the image once, run the tests inside it, push it to GitHub Container Registry |
| Deploy | Render runs that exact image, triggered by CI only after the tests pass |

## Run it locally

You need Docker and a free [TMDb API key](https://www.themoviedb.org/settings/api).

    echo 'TMDB_API_KEY=your-key-here' > .env
    docker compose up -d --build

Then open http://localhost:8000.

## Run the tests

    docker compose exec web pytest -v

---

This product uses the TMDB API but is not endorsed or certified by TMDB.
