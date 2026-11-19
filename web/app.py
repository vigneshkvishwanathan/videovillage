import hmac
import os

import psycopg
import requests
from psycopg.rows import dict_row
from flask import Flask, Response, abort, redirect, render_template, request, url_for, flash

import tmdb
from rules import (  # NEW: two more rules
    RATING_FIELDS,
    parse_genres,
    parse_rating,
    parse_aspect_ratios,
    rating_band,
    score,
    score_band,
    sort_discs,
    watched_rule_error,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
app.jinja_env.globals["poster_base"] = tmdb.POSTER_BASE
app.jinja_env.globals["poster_big"] = tmdb.POSTER_BIG
DATABASE_URL = os.environ["DATABASE_URL"]


@app.template_filter("ratio")
def ratio_label(value):
    """2.39 -> "2.39:1", the way aspect ratios are written on disc cases."""
    return f"{float(value):.2f}:1"


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

STARTER_VIDEO = ["Dolby Vision", "HDR10", "HDR10+", "SDR"]
STARTER_AUDIO = ["Dolby Atmos", "DTS:X", "DTS-HD MA 5.1", "Dolby TrueHD 7.1"]
STARTER_ASPECT_RATIOS = [2.39, 2.20, 1.90, 1.85, 1.78, 1.43]

SUGGESTED_COLUMNS = ["label", "audio_format", "video_format"]  # NEW



def db():
    """Open a connection to Postgres. Rows come back as dictionaries."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def genre_choices(conn):  # NEW
    """Every genre worth offering: the starter list plus any you've used."""
    used = [row["genre"] for row in conn.execute("SELECT DISTINCT unnest(genres) AS genre FROM discs")]
    return sorted(set(STARTER_GENRES) | set(used), key=str.lower)

def ratio_choices(used):
    """Starter ratios plus any used, as plain numbers, each once, widest first."""
    numbers = {round(float(r), 2) for r in STARTER_ASPECT_RATIOS + list(used)}
    return sorted(numbers, reverse=True)

def ratio_chip_groups(used_counts, current, top=8):
    """Split the ratio chips into (shown, behind "More…").

    `used_counts` maps ratio -> how many discs use it. The `top` most-used are shown,
    plus any this disc already has, so a ticked chip is never hidden. Each group is
    widest first.
    """
    counts = {round(float(r), 2): n for r, n in used_counts.items()}
    current = [round(float(r), 2) for r in current]
    choices = ratio_choices(list(counts) + current)
    ranked = sorted(choices, key=lambda r: (-counts.get(r, 0), -r))
    shown = set(ranked[:top]) | set(current)
    return [r for r in choices if r in shown], [r for r in choices if r not in shown]


def text_choices(starters, used):
    """Starter values plus any used, each once (ignoring capitals), A to Z."""
    seen = {}
    for value in starters + list(used):
        seen.setdefault(value.lower(), value)
    return sorted(seen.values(), key=str.lower)

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
        ratios = parse_aspect_ratios(form.getlist("aspect_ratios"), form.get("new_aspect_ratio"))
    except ValueError:
        ratios = []
        errors.append("Aspect ratios must be numbers, like 2.39 or 2.40:1.")

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
        # A value typed into "+ New" wins over the chip that was picked.
        "audio_format": clean_text(form.get("new_audio_format")) or clean_text(form.get("audio_format")),
        "video_format": clean_text(form.get("new_video_format")) or clean_text(form.get("video_format")),
        "aspect_ratios": ratios,
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
    with db() as conn:
        genres = genre_choices(conn)
        suggestions = {column: used_values(conn, column) for column in SUGGESTED_COLUMNS}
        used_ratios = {
            row["r"]: row["n"]
            for row in conn.execute(
                "SELECT r, count(*) AS n FROM discs, unnest(aspect_ratios) AS r GROUP BY r ORDER BY n DESC"
            )
        }
    suggestions["video_format"] = text_choices(STARTER_VIDEO, suggestions["video_format"])
    suggestions["audio_format"] = text_choices(STARTER_AUDIO, suggestions["audio_format"])
    current_ratios = [round(float(r), 2) for r in disc.get("aspect_ratios") or []]
    shown_ratios, more_ratios = ratio_chip_groups(used_ratios, current_ratios)
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
        ratio_choices=shown_ratios,
        more_ratios=more_ratios,
        current_ratios=current_ratios,
    )

@app.route("/health")
def health():
    """For Render: "is the app up?" Deliberately skips the password and the database."""
    return "ok"


# Pages anyone can look at without the password (only GET requests).
# Everything else (Add, Edit, Delete, +1 viewing, I own it, TMDb search)
# needs the password. New routes are locked unless they're added here.
PUBLIC_PAGES = {"health", "index", "search_page", "show_disc", "static"}


def needs_password(endpoint, method):
    """True if this request changes data or uses TMDb, so it needs the password."""
    return not (endpoint in PUBLIC_PAGES and method in ("GET", "HEAD"))


@app.before_request
def require_password():
    """Anyone can browse; only changes need the shared password (when APP_PASSWORD is set).

    It isn't set on your Mac, so local development stays password-free.
    """
    password = os.environ.get("APP_PASSWORD")
    if not password or not needs_password(request.endpoint, request.method):
        return None
    auth = request.authorization
    if auth and hmac.compare_digest((auth.password or "").encode(), password.encode()):
        return None
    return Response(
        "Changing the collection needs a password.",
        401,
        {"WWW-Authenticate": 'Basic realm="Video Village"'},
    )

SORT_DIRECTIONS = ("asc", "desc")


def read_filters(args):
    """What to show, read from the address bar. Anything unexpected falls back to a default."""
    view = "wishlist" if args.get("view") == "wishlist" else "collection"
    direction = args.get("dir")
    filters = {
        "q": args.get("q", "").strip(),
        "format": args.get("format", ""),
        "genres": [g for g in args.getlist("genre") if g],
        "sort": args.get("sort") or ("title" if view == "wishlist" else "score"),
        "dir": direction if direction in SORT_DIRECTIONS else None,
        "layout": "cards" if args.get("layout") == "cards" else "list",
    }
    sort_word, _, order_dir = args.get("order", "").partition("-")
    if (sort_word, order_dir) in SORT_WORDS:
        filters["sort"], filters["dir"] = sort_word, order_dir
    return view, filters

SORT_WORDS = {
    ("score", "desc"): "Highest score", ("score", "asc"): "Lowest score",
    ("title", "asc"): "A–Z",            ("title", "desc"): "Z–A",
    ("year", "desc"): "Newest",         ("year", "asc"): "Oldest",
}

def effective_order(filters):
    """The (sort, direction) pair actually in use. Unknown sorts fall back to highest score."""
    direction = filters["dir"] or ("asc" if filters["sort"] == "title" else "desc")
    order = (filters["sort"], direction)
    return order if order in SORT_WORDS else ("score", "desc")

def filter_summary(filters):
    """One line saying what the list shows, e.g. "Highest score · 4K UHD · War + Drama"."""
    direction = filters["dir"] or ("asc" if filters["sort"] == "title" else "desc")
    parts = [SORT_WORDS.get((filters["sort"], direction), "Highest score")]
    if filters["q"]:
        parts.append(f"“{filters['q']}”")
    if filters["format"]:
        parts.append(filters["format"])
    if filters["genres"]:
        parts.append(" + ".join(filters["genres"]))
    if len(parts) == 1:
        parts.append("All discs")
    return " · ".join(parts)


def filters_active(filters):
    """True when something is hidden from the list. Sorting alone doesn't count."""
    return bool(filters["q"] or filters["format"] or filters["genres"])

def build_filter(view, filters):
    """Turn the chosen view and filters into a WHERE clause and its values.

    Kept separate from index() so it can be tested without a database.
    """
    conditions = ["owned = %(owned)s"]
    params = {"owned": view == "collection"}
    if filters["q"]:
        conditions.append("(title ILIKE %(q)s OR directors ILIKE %(q)s OR top_cast ILIKE %(q)s)")
        params["q"] = f"%{filters['q']}%"
    if filters["format"] in FORMATS:
        conditions.append("disc_format = %(format)s")
        params["format"] = filters["format"]
    if filters["genres"]:
        conditions.append("genres @> %(genres)s::text[]")
        params["genres"] = filters["genres"]
    return " AND ".join(conditions), params

def prepare_disc(disc):
    """Add what's calculated, never stored: the score, its colour, and each rating's colour."""
    disc["score"] = score(disc)
    disc["band"] = score_band(disc["score"])
    disc["rating_rows"] = [
        {"label": label, "value": disc[field], "band": rating_band(disc[field])}
        for field, label in RATING_LABELS.items()
    ]
    return disc

def mark_already_have(results, have):
    """Label each TMDb result you already have. `have` maps tmdb_id -> your disc row."""
    for movie in results:
        mine = have.get(movie["tmdb_id"])
        if mine is None:
            movie["badge"] = None
            movie["disc_id"] = None
        else:
            movie["badge"] = "In collection" if mine["owned"] else "On wishlist"
            movie["disc_id"] = mine["id"]
    return results

@app.route("/")
def index():
    # NEW: everything about what to show comes from the address bar, e.g.
    # /?view=wishlist&q=nolan&format=4K+UHD&genre=Drama&sort=year
    view, filters = read_filters(request.args)

    # NEW: build the WHERE clause from fixed pieces; the values go in as placeholders.
    where, params = build_filter(view, filters)

    with db() as conn:
        discs = conn.execute(
            "SELECT * FROM discs WHERE " + where, params
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
        prepare_disc(disc)
    
    discs = sort_discs(discs, filters["sort"], filters["dir"])

    return render_template(
        "index.html",
        discs=discs,
        view=view,
        filters=filters,
        counts={"collection": counts.get(True, 0), "wishlist": counts.get(False, 0)},
        genres=used_genres,
        formats=FORMATS,
        summary=filter_summary(filters),
        active=filters_active(filters)
    )

@app.route("/search")
def search_page():
    view, filters = read_filters(request.args)
    with db() as conn:
        genres = [
            row["genre"]
            for row in conn.execute("SELECT DISTINCT unnest(genres) AS genre FROM discs ORDER BY genre")
        ]
    return render_template(
        "search_page.html",
        view=view,
        filters=filters,
        genres=genres,
        formats=FORMATS,
        orders=SORT_WORDS.items(),
        current_order=effective_order(filters),
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
    if results:
        with db() as conn:
            rows = conn.execute(
                "SELECT id, tmdb_id, owned FROM discs WHERE tmdb_id = ANY(%s)",
                ([m["tmdb_id"] for m in results],),
            ).fetchall()
        mark_already_have(results, {row["tmdb_id"]: row for row in rows})
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
                                   aspect_ratios, owned, notes, genres,
                                   viewings, audio_rating, video_rating,
                                   overall_rating, rewatch_rating)
                VALUES (%(tmdb_id)s, %(title)s, %(release_year)s, %(runtime_minutes)s, %(overview)s,
                        %(poster_path)s, %(directors)s, %(top_cast)s,
                        %(disc_format)s, %(label)s, %(audio_format)s, %(video_format)s,
                        %(aspect_ratios)s, %(owned)s, %(notes)s, %(genres)s,
                        %(viewings)s, %(audio_rating)s, %(video_rating)s,
                        %(overall_rating)s, %(rewatch_rating)s)
                """,
                disc,
            )
    except psycopg.errors.UniqueViolation:
        return show_form(disc, ["That film is already in your collection."])
    
    flash(f"Added {disc['title']} to your {'collection' if disc['owned'] else 'wishlist'}.")
    return redirect(url_for("index", view="collection" if disc["owned"] else "wishlist"))


@app.route("/discs/<int:disc_id>")
def show_disc(disc_id):
    with db() as conn:
        disc = conn.execute("SELECT * FROM discs WHERE id = %s", (disc_id,)).fetchone()
    if disc is None:
        abort(404)
    return render_template("disc.html", disc=prepare_disc(disc))

@app.post("/discs/<int:disc_id>/view")
def add_viewing(disc_id):
    with db() as conn:
        updated = conn.execute(
            "UPDATE discs SET viewings = viewings + 1 WHERE id = %s RETURNING id", (disc_id,)
        ).fetchone()
    if updated is None:
        abort(404)
    return redirect(url_for("show_disc", disc_id=disc_id))

@app.post("/discs/<int:disc_id>/own")
def mark_owned(disc_id):
    with db() as conn:
        updated = conn.execute(
            "UPDATE discs SET owned = true WHERE id = %s RETURNING id", (disc_id,)
        ).fetchone()
    if updated is None:
        abort(404)
    return redirect(url_for("edit_disc", disc_id=disc_id))

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
                        aspect_ratios = %(aspect_ratios)s, owned = %(owned)s, notes = %(notes)s,
                        genres = %(genres)s,
                        viewings = %(viewings)s, audio_rating = %(audio_rating)s,
                        video_rating = %(video_rating)s, overall_rating = %(overall_rating)s,
                        rewatch_rating = %(rewatch_rating)s
                    WHERE id = %(id)s
                    """,
                    {**disc, "id": disc_id},
                )
                flash(f"Saved {disc['title']}.")
                return redirect(url_for("index", view="collection" if disc["owned"] else "wishlist"))
    
    return show_form(disc, errors, disc_id)


@app.post("/discs/<int:disc_id>/delete")
def delete_disc(disc_id):
    with db() as conn:
        conn.execute("DELETE FROM discs WHERE id = %s", (disc_id,))
    return redirect(url_for("index"))
