from tmdb import movie_facts

# A trimmed-down copy of what TMDb sends back, so these tests never touch the internet.
FAKE_MOVIE = {
    "id": 872585,
    "title": "Oppenheimer",
    "release_date": "2023-07-19",
    "runtime": 181,
    "overview": "A physicist leads the race to build the bomb.",
    "poster_path": "/oppenheimer.jpg",
    "credits": {
        "crew": [
            {"name": "Christopher Nolan", "job": "Director"},
            {"name": "Christopher Nolan", "job": "Screenplay"},
            {"name": "Ludwig Göransson", "job": "Original Music Composer"},
        ],
        "cast": [
            {"name": "Emily Blunt", "order": 1},
            {"name": "Cillian Murphy", "order": 0},
            {"name": "Matt Damon", "order": 2},
            {"name": "Robert Downey Jr.", "order": 3},
            {"name": "Florence Pugh", "order": 4},
            {"name": "Josh Hartnett", "order": 5},
        ],
    },
}


def test_facts_use_our_column_names():
    facts = movie_facts(FAKE_MOVIE)
    assert facts["tmdb_id"] == 872585
    assert facts["title"] == "Oppenheimer"
    assert facts["release_year"] == 2023
    assert facts["runtime_minutes"] == 181


def test_only_directors_count_as_directors():
    assert movie_facts(FAKE_MOVIE)["directors"] == "Christopher Nolan"


def test_top_cast_follows_billing_order_and_stops_at_five():
    assert movie_facts(FAKE_MOVIE)["top_cast"] == (
        "Cillian Murphy, Emily Blunt, Matt Damon, Robert Downey Jr., Florence Pugh"
    )


def test_unknown_values_become_empty():
    # TMDb uses "" and 0 for "don't know". We store empty instead.
    facts = movie_facts({
        "id": 1,
        "title": "Unreleased",
        "release_date": "",
        "runtime": 0,
        "overview": "",
        "credits": {"crew": [], "cast": []},
    })
    assert facts["release_year"] is None
    assert facts["runtime_minutes"] is None
    assert facts["overview"] is None
    assert facts["poster_path"] is None
    assert facts["directors"] is None
    assert facts["top_cast"] is None