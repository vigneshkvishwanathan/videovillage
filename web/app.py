import os

import psycopg
import requests
from psycopg.rows import dict_row
from flask import Flask, abort, redirect, render_template, request, url_for

import tmdb  # NEW
from rules import RATING_FIELDS, parse_rating, score, watched_rule_error

app = Flask(__name__)
app.jinja_env.globals["poster_base"] = tmdb.POSTER_BASE  # NEW: every template can use it
DATABASE_URL = os.environ["DATABASE_URL"]

FORMATS = ["4K UHD", "Blu-ray"]
RATING_LABELS = {
    "audio_rating": "Audio",
    "video_rating": "Video",
    "overall_rating": "Overall",
    "rewatch_rating": "Rewatchability",
}
RATING_CHOICES = [n / 2 for n in range(11)]
FACT_FIELDS = ["runtime_minutes", "overview", "poster_path", "directors", "top_cast"]  # NEW
TMDB_DOWN = "Couldn't reach TMDb. Check the API key, or try again in a minute."  # NEW


def db():
    """Open a connection to Postgres. Rows come back as dictionaries."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def clean_text(value):
    """Trim spaces; an empty box becomes None (NULL in the database)."""
    value = (value or "").strip()
    return value or None


def clean_number(value, kind):
    """Turn text into a number. Raises ValueError if it isn't one."""
    value = clean_text(value)
    return None if value is None else kind(value)


def read_form(form):
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

    try:  # NEW: the hidden field that says which TMDb film this is
        tmdb_id = clean_number(form.get("tmdb_id"), int)
    except ValueError:
        tmdb_id = None

    disc = {
        "tmdb_id": tmdb_id,  # NEW
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
    return render_template(
        "disc_form.html",
        disc=disc,
        errors=errors,
        disc_id=disc_id,
        formats=FORMATS,
        ratings=RATING_LABELS.items(),
        rating_choices=RATING_CHOICES,
    )


@app.route("/")
def index():
    with db() as conn:
        discs = conn.execute("SELECT * FROM discs").fetchall()

    for disc in discs:
        disc["score"] = score(disc)

    # Highest score first; unscored discs go to the bottom, by title.
    discs.sort(key=lambda d: (d["score"] is None, -(d["score"] or 0), d["title"].lower()))

    return render_template("index.html", discs=discs)


@app.route("/discs/search")  # NEW
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

    if request.method == "GET":  # NEW: arriving from a search result pre-fills the form
        tmdb_id = request.args.get("tmdb_id", type=int)
        if tmdb_id:
            try:
                disc = tmdb.get_movie(tmdb_id)
            except requests.RequestException:
                errors.append(TMDB_DOWN)
        return show_form(disc, errors)

    disc, errors = read_form(request.form)

    # NEW: the film's facts come from TMDb, not from the browser.
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
                                   aspect_ratio, owned, notes,
                                   viewings, audio_rating, video_rating,
                                   overall_rating, rewatch_rating)
                VALUES (%(tmdb_id)s, %(title)s, %(release_year)s, %(runtime_minutes)s, %(overview)s,
                        %(poster_path)s, %(directors)s, %(top_cast)s,
                        %(disc_format)s, %(label)s, %(audio_format)s, %(video_format)s,
                        %(aspect_ratio)s, %(owned)s, %(notes)s,
                        %(viewings)s, %(audio_rating)s, %(video_rating)s,
                        %(overall_rating)s, %(rewatch_rating)s)
                """,
                disc,
            )
    except psycopg.errors.UniqueViolation:  # NEW: tmdb_id is UNIQUE in the table
        return show_form(disc, ["That film is already in your collection."])

    return redirect(url_for("index"))


@app.route("/discs/<int:disc_id>/edit", methods=["GET", "POST"])
def edit_disc(disc_id):
    with db() as conn:
        disc = conn.execute("SELECT * FROM discs WHERE id = %s", (disc_id,)).fetchone()
        if disc is None:
            abort(404)

        errors = []
        if request.method == "POST":
            saved = disc  # NEW: keep the TMDb facts to show if the form has errors
            disc, errors = read_form(request.form)
            disc.update({field: saved[field] for field in FACT_FIELDS})
            if not errors:
                conn.execute(
                    """
                    UPDATE discs
                    SET title = %(title)s, release_year = %(release_year)s,
                        disc_format = %(disc_format)s, label = %(label)s,
                        audio_format = %(audio_format)s, video_format = %(video_format)s,
                        aspect_ratio = %(aspect_ratio)s, owned = %(owned)s, notes = %(notes)s,
                        viewings = %(viewings)s, audio_rating = %(audio_rating)s,
                        video_rating = %(video_rating)s, overall_rating = %(overall_rating)s,
                        rewatch_rating = %(rewatch_rating)s
                    WHERE id = %(id)s
                    """,
                    {**disc, "id": disc_id},
                )
                return redirect(url_for("index"))

    return show_form(disc, errors, disc_id)


@app.post("/discs/<int:disc_id>/delete")
def delete_disc(disc_id):
    with db() as conn:
        conn.execute("DELETE FROM discs WHERE id = %s", (disc_id,))
    return redirect(url_for("index"))