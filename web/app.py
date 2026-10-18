import os

import psycopg
from psycopg.rows import dict_row
from flask import Flask, abort, redirect, render_template, request, url_for

app = Flask(__name__)
DATABASE_URL = os.environ["DATABASE_URL"]

FORMATS = ["4K UHD", "Blu-ray"]


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
    }

    if not disc["title"]:
        errors.append("Title is required.")
    if disc["disc_format"] not in FORMATS:
        errors.append("Pick a disc format.")

    return disc, errors


@app.route("/")
def index():
    with db() as conn:
        discs = conn.execute("SELECT * FROM discs ORDER BY title").fetchall()
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
                                       audio_format, video_format, aspect_ratio, owned, notes)
                    VALUES (%(title)s, %(release_year)s, %(disc_format)s, %(label)s,
                            %(audio_format)s, %(video_format)s, %(aspect_ratio)s, %(owned)s, %(notes)s)
                    """,
                    disc,
                )
            return redirect(url_for("index"))
    return render_template("disc_form.html", disc=disc, errors=errors, formats=FORMATS)


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
                        aspect_ratio = %(aspect_ratio)s, owned = %(owned)s, notes = %(notes)s
                    WHERE id = %(id)s
                    """,
                    {**disc, "id": disc_id},
                )
                return redirect(url_for("index"))

    return render_template(
        "disc_form.html", disc=disc, errors=errors, formats=FORMATS, disc_id=disc_id
    )


@app.post("/discs/<int:disc_id>/delete")
def delete_disc(disc_id):
    with db() as conn:
        conn.execute("DELETE FROM discs WHERE id = %s", (disc_id,))
    return redirect(url_for("index"))