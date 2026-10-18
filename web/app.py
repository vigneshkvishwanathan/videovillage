import os

import psycopg
from psycopg.rows import dict_row
from flask import Flask, render_template

app = Flask(__name__)
DATABASE_URL = os.environ["DATABASE_URL"]


@app.route("/")
def index():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        discs = conn.execute(
            "SELECT title, release_year, disc_format, owned FROM discs ORDER BY title"
        ).fetchall()
    return render_template("index.html", discs=discs)