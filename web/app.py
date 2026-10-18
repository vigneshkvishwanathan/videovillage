import os

import psycopg
from psycopg.rows import dict_row
from flask import Flask, abort, redirect, render_template, request, url_for

from rules import RATING_FIELDS, parse_rating, score, watched_rule_error  # NEW

app = Flask(__name__)
DATABASE_URL = os.environ["DATABASE_URL"]

FORMATS = ["4K UHD", "Blu-ray"]
RATING_LABELS = {  # NEW: what each rating is called on screen
    "audio_rating": "Audio",
    "video_rating": "Video",
    "overall_rating": "Overall",
    "rewatch_rating": "Rewatchability",
}
RATING_CHOICES = [n / 2 for n in range(11)]  # NEW: 0, 0.5, 1 ... 5


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

    try:  # NEW
        viewings = clean_number(form.get("viewings"), int) or 0
        if viewings < 0:
            raise ValueError
    except ValueError:
        viewings = 0
        errors.append("Viewings must be 0 or more.")

    disc = {
        "title": clean_text(form.get("title")),
        "release_year": year,
        "disc_format": form.get("disc_format"),
        "label": clean_text(form.get("label")),
        "audio_format": clean_text(form.get("audio_format")),
        "video_format": clean_text(form.get("video_format")),
        "aspect_ratio": ratio,
        "owned": form.get("owned") == "on",
        "notes": clean_text(form.get("notes")),
        "viewings": viewings,  # NEW
    }

    for field in RATING_FIELDS:  # NEW
        try:
            disc[field] = parse_rating(form.get(field))
        except ValueError:
            disc[field] = None
            errors.append("Ratings go from 0 to 5 in steps of 0.5.")

    if not disc["title"]:
        errors.append("Title is required.")
    if disc["disc_format"] not in FORMATS:
        errors.append("Pick a disc format.")

    rule_error = watched_rule_error(disc)  # NEW
    if rule_error:
        errors.append(rule_error)

    return disc, errors


def show_form(disc, errors, disc_id=None):  # NEW: one place that renders the form
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

    for disc in discs:  # NEW
        disc["score"] = score(disc)

    # NEW: highest score first; unscored discs go to the bottom, by title.
    discs.sort(key=lambda d: (d["score"] is None, -(d["score"] or 0), d["title"].lower()))

    return render_template("index.html", discs=discs)


@app.route("/discs/new", methods=["GET", "POST"])
def add_disc():
    disc, errors = {}, []
    if request.method == "POST":
        disc, errors = read_form(request.form)
        if not errors:
            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO discs (title, release_year, disc_format, label,
                                       audio_format, video_format, aspect_ratio, owned, notes,
                                       viewings, audio_rating, video_rating,
                                       overall_rating, rewatch_rating)
                    VALUES (%(title)s, %(release_year)s, %(disc_format)s, %(label)s,
                            %(audio_format)s, %(video_format)s, %(aspect_ratio)s, %(owned)s, %(notes)s,
                            %(viewings)s, %(audio_rating)s, %(video_rating)s,
                            %(overall_rating)s, %(rewatch_rating)s)
                    """,
                    disc,
                )
            return redirect(url_for("index"))
    return show_form(disc, errors)


@app.route("/discs/<int:disc_id>/edit", methods=["GET", "POST"])
def edit_disc(disc_id):
    with db() as conn:
        disc = conn.execute("SELECT * FROM discs WHERE id = %s", (disc_id,)).fetchone()
        if disc is None:
            abort(404)

        errors = []
        if request.method == "POST":
            disc, errors = read_form(request.form)
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