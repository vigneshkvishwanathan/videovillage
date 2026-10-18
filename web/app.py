import hmac
import os

import psycopg
import requests
from psycopg.rows import dict_row
from flask import Flask, Response, abort, redirect, render_template, request, url_for

import tmdb
from rules import (  # NEW: two more rules
    RATING_FIELDS,
    parse_genres,
    parse_rating,
    score,
    score_band,
    sort_discs,
    watched_rule_error,
)

app = Flask(__name__)
app.jinja_env.globals["poster_base"] = tmdb.POSTER_BASE
DATABASE_URL = os.environ["DATABASE_URL"]

FORMATS = ["4K UHD", "Blu-ray"]
RATING_LABELS = {
    "audio_rating": "Audio",
    "video_rating": "Video",
    "overall_rating": "Overall",
    "rewatch_rating": "Rewatchability",
}
RATING_CHOICES = [n / 2 for n in range(11)]
FACT_FIELDS = ["runtime_minutes", "overview", "poster_path", "directors", "top_cast"]
TMDB_DOWN = "Couldn't reach TMDb. Check the API key, or try again in a minute."

# NEW: offered on the form before you've used any genres yourself.
STARTER_GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Drama", "Epic", "Fantasy",
    "Historical", "Horror", "Musical", "Mystery", "Romance", "Sci-Fi", "Sports",
    "Superhero", "Thriller", "War", "Western",
]
SUGGESTED_COLUMNS = ["label", "audio_format", "video_format"]  # NEW
SORTS = [("score", "Highest score"), ("title", "Title A–Z"), ("year", "Newest first")]  # NEW


def db():
    """Open a connection to Postgres. Rows come back as dictionaries."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def genre_choices(conn):  # NEW
    """Every genre worth offering: the starter list plus any you've used."""
    used = [row["genre"] for row in conn.execute("SELECT DISTINCT unnest(genres) AS genre FROM discs")]
    return sorted(set(STARTER_GENRES) | set(used), key=str.lower)


def used_values(conn, column):  # NEW
    """Values already used in a column, to suggest on the form.

    The column name goes straight into the SQL (placeholders only work for values,
    not column names), so it must come from SUGGESTED_COLUMNS, never from the browser.
    """
    if column not in SUGGESTED_COLUMNS:
        raise ValueError(f"Not a suggested column: {column}")
    rows = conn.execute(
        f"SELECT DISTINCT {column} AS value FROM discs WHERE {column} IS NOT NULL ORDER BY value"
    )
    return [row["value"] for row in rows]


def clean_text(value):
    """Trim spaces; an empty box becomes None (NULL in the database)."""
    value = (value or "").strip()
    return value or None


def clean_number(value, kind):
    """Turn text into a number. Raises ValueError if it isn't one."""
    value = clean_text(value)
    return None if value is None else kind(value)


def read_form(form, known_genres):  # NEW: needs the known genres to match spellings
    """Turn a submitted form into clean values, plus a list of problems."""
    errors = []

    try:
        year = clean_number(form.get("release_year"), int)
    except ValueError:
        year = None
        errors.append("Year must be a whole number.")

    try:
        ratio = clean_number(form.get("aspect_ratio"), float)
    except ValueError:
        ratio = None
        errors.append("Aspect ratio must be a number, like 2.39.")

    try:
        viewings = clean_number(form.get("viewings"), int) or 0
        if viewings < 0:
            raise ValueError
    except ValueError:
        viewings = 0
        errors.append("Viewings must be 0 or more.")

    try:
        tmdb_id = clean_number(form.get("tmdb_id"), int)
    except ValueError:
        tmdb_id = None

    disc = {
        "tmdb_id": tmdb_id,
        "title": clean_text(form.get("title")),
        "release_year": year,
        "disc_format": form.get("disc_format"),
        "label": clean_text(form.get("label")),
        "audio_format": clean_text(form.get("audio_format")),
        "video_format": clean_text(form.get("video_format")),
        "aspect_ratio": ratio,
        "owned": form.get("owned") == "on",
        "notes": clean_text(form.get("notes")),
        "viewings": viewings,
        # NEW: ticked boxes arrive as a list; typed ones as one comma-separated string.
        "genres": parse_genres(form.getlist("genres"), form.get("new_genres"), known_genres),
    }

    for field in RATING_FIELDS:
        try:
            disc[field] = parse_rating(form.get(field))
        except ValueError:
            disc[field] = None
            errors.append("Ratings go from 0 to 5 in steps of 0.5.")

    if not disc["title"]:
        errors.append("Title is required.")
    if disc["disc_format"] not in FORMATS:
        errors.append("Pick a disc format.")

    rule_error = watched_rule_error(disc)
    if rule_error:
        errors.append(rule_error)

    return disc, errors


def show_form(disc, errors, disc_id=None):
    with db() as conn:  # NEW: the form now offers genres and suggestions from the database
        genres = genre_choices(conn)
        suggestions = {column: used_values(conn, column) for column in SUGGESTED_COLUMNS}
    return render_template(
        "disc_form.html",
        disc=disc,
        errors=errors,
        disc_id=disc_id,
        formats=FORMATS,
        ratings=RATING_LABELS.items(),
        rating_choices=RATING_CHOICES,
        genre_choices=genres,
        suggestions=suggestions,
    )

@app.route("/health")
def health():
    """For Render: "is the app up?" Deliberately skips the password and the database."""
    return "ok"


@app.before_request
def require_password():
    """Put the whole site behind one shared password, when APP_PASSWORD is set.

    It isn't set on your Mac, so local development stays password-free.
    """
    password = os.environ.get("APP_PASSWORD")
    if not password or request.endpoint == "health":
        return None
    auth = request.authorization
    if auth and hmac.compare_digest((auth.password or "").encode(), password.encode()):
        return None
    return Response(
        "This site needs a password.",
        401,
        {"WWW-Authenticate": 'Basic realm="Video Village"'},
    )

@app.route("/")
def index():
    # NEW: everything about what to show comes from the address bar, e.g.
    # /?view=wishlist&q=nolan&format=4K+UHD&genre=Drama&sort=year
    view = "wishlist" if request.args.get("view") == "wishlist" else "collection"
    filters = {
        "q": request.args.get("q", "").strip(),
        "format": request.args.get("format", ""),
        "genre": request.args.get("genre", ""),
        "sort": request.args.get("sort") or ("title" if view == "wishlist" else "score"),
    }

    # NEW: build the WHERE clause from fixed pieces; the values go in as placeholders.
    conditions = ["owned = %(owned)s"]
    params = {"owned": view == "collection"}
    if filters["q"]:
        conditions.append("(title ILIKE %(q)s OR directors ILIKE %(q)s OR top_cast ILIKE %(q)s)")
        params["q"] = f"%{filters['q']}%"
    if filters["format"] in FORMATS:
        conditions.append("disc_format = %(format)s")
        params["format"] = filters["format"]
    if filters["genre"]:
        conditions.append("%(genre)s = ANY(genres)")
        params["genre"] = filters["genre"]

    with db() as conn:
        discs = conn.execute(
            "SELECT * FROM discs WHERE " + " AND ".join(conditions), params
        ).fetchall()
        counts = {
            row["owned"]: row["n"]
            for row in conn.execute("SELECT owned, count(*) AS n FROM discs GROUP BY owned")
        }
        used_genres = [
            row["genre"]
            for row in conn.execute(
                "SELECT DISTINCT unnest(genres) AS genre FROM discs ORDER BY genre"
            )
        ]

    for disc in discs:
        disc["score"] = score(disc)
        disc["band"] = score_band(disc["score"])  # NEW: which colour its badge gets
    discs = sort_discs(discs, filters["sort"])  # NEW: sorting moved into rules.py

    return render_template(
        "index.html",
        discs=discs,
        view=view,
        filters=filters,
        counts={"collection": counts.get(True, 0), "wishlist": counts.get(False, 0)},
        genres=used_genres,
        formats=FORMATS,
        sorts=SORTS,
    )


@app.route("/discs/search")
def search_tmdb():
    query = request.args.get("q", "").strip()
    results, error = [], None
    if query:
        try:
            results = tmdb.search(query)
        except requests.RequestException:
            error = TMDB_DOWN
    return render_template("search.html", query=query, results=results, error=error)


@app.route("/discs/new", methods=["GET", "POST"])
def add_disc():
    disc, errors = {}, []

    if request.method == "GET":
        tmdb_id = request.args.get("tmdb_id", type=int)
        if tmdb_id:
            try:
                disc = tmdb.get_movie(tmdb_id)
            except requests.RequestException:
                errors.append(TMDB_DOWN)
        return show_form(disc, errors)

    with db() as conn:  # NEW
        known_genres = genre_choices(conn)
    disc, errors = read_form(request.form, known_genres)

    facts = {field: None for field in FACT_FIELDS}
    if disc["tmdb_id"]:
        try:
            movie = tmdb.get_movie(disc["tmdb_id"])
            facts = {field: movie[field] for field in FACT_FIELDS}
        except requests.RequestException:
            errors.append(TMDB_DOWN)
    disc.update(facts)

    if errors:
        return show_form(disc, errors)

    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO discs (tmdb_id, title, release_year, runtime_minutes, overview,
                                   poster_path, directors, top_cast,
                                   disc_format, label, audio_format, video_format,
                                   aspect_ratio, owned, notes, genres,
                                   viewings, audio_rating, video_rating,
                                   overall_rating, rewatch_rating)
                VALUES (%(tmdb_id)s, %(title)s, %(release_year)s, %(runtime_minutes)s, %(overview)s,
                        %(poster_path)s, %(directors)s, %(top_cast)s,
                        %(disc_format)s, %(label)s, %(audio_format)s, %(video_format)s,
                        %(aspect_ratio)s, %(owned)s, %(notes)s, %(genres)s,
                        %(viewings)s, %(audio_rating)s, %(video_rating)s,
                        %(overall_rating)s, %(rewatch_rating)s)
                """,
                disc,
            )
    except psycopg.errors.UniqueViolation:
        return show_form(disc, ["That film is already in your collection."])

    return redirect(url_for("index", view="collection" if disc["owned"] else "wishlist"))


@app.route("/discs/<int:disc_id>/edit", methods=["GET", "POST"])
def edit_disc(disc_id):
    with db() as conn:
        disc = conn.execute("SELECT * FROM discs WHERE id = %s", (disc_id,)).fetchone()
        if disc is None:
            abort(404)

        errors = []
        if request.method == "POST":
            saved = disc
            disc, errors = read_form(request.form, genre_choices(conn))
            disc.update({field: saved[field] for field in FACT_FIELDS})
            if not errors:
                conn.execute(
                    """
                    UPDATE discs
                    SET title = %(title)s, release_year = %(release_year)s,
                        disc_format = %(disc_format)s, label = %(label)s,
                        audio_format = %(audio_format)s, video_format = %(video_format)s,
                        aspect_ratio = %(aspect_ratio)s, owned = %(owned)s, notes = %(notes)s,
                        genres = %(genres)s,
                        viewings = %(viewings)s, audio_rating = %(audio_rating)s,
                        video_rating = %(video_rating)s, overall_rating = %(overall_rating)s,
                        rewatch_rating = %(rewatch_rating)s
                    WHERE id = %(id)s
                    """,
                    {**disc, "id": disc_id},
                )
                return redirect(url_for("index", view="collection" if disc["owned"] else "wishlist"))

    return show_form(disc, errors, disc_id)


@app.post("/discs/<int:disc_id>/delete")
def delete_disc(disc_id):
    with db() as conn:
        conn.execute("DELETE FROM discs WHERE id = %s", (disc_id,))
    return redirect(url_for("index"))