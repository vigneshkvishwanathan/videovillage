import pytest

from rules import parse_genres, parse_rating, score, score_band, sort_discs, watched_rule_error


def make_disc(audio=None, video=None, overall=None, rewatch=None, viewings=0):
    return {
        "audio_rating": audio,
        "video_rating": video,
        "overall_rating": overall,
        "rewatch_rating": rewatch,
        "viewings": viewings,
    }


# --- The score ---

def test_score_worked_example():
    # Oppenheimer: all 5s, watched 3 times -> (5+5+5+5) * 5 + 3 - 1 = 102
    assert score(make_disc(5, 5, 5, 5, viewings=3)) == 102


def test_score_can_end_in_half():
    # 4.5 + 4 + 4 + 4 = 16.5 -> 16.5 * 5 + 1 - 1 = 82.5
    assert score(make_disc(4.5, 4, 4, 4, viewings=1)) == 82.5


def test_score_is_empty_when_a_rating_is_missing():
    assert score(make_disc(5, 5, 5, None, viewings=2)) is None


# --- Parsing a rating ---

@pytest.mark.parametrize("text, expected", [
    ("", None),
    ("0", 0),
    ("4.5", 4.5),
    ("5", 5),
])
def test_parse_rating_accepts(text, expected):
    assert parse_rating(text) == expected


@pytest.mark.parametrize("text", ["5.5", "-1", "2.3", "abc"])
def test_parse_rating_refuses(text):
    with pytest.raises(ValueError):
        parse_rating(text)


# --- The watched rule ---

def test_rating_an_unwatched_disc_is_refused():
    assert watched_rule_error(make_disc(audio=4, viewings=0)) is not None


def test_a_zero_rating_still_counts_as_a_rating():
    assert watched_rule_error(make_disc(audio=0, viewings=0)) is not None


def test_unrated_and_unwatched_is_fine():
    assert watched_rule_error(make_disc(viewings=0)) is None


def test_rated_after_watching_is_fine():
    assert watched_rule_error(make_disc(4, 4, 4, 4, viewings=1)) is None

# --- Genres ---

def test_typed_genres_are_split_and_trimmed():
    assert parse_genres([], " Epic , War ,", []) == ["Epic", "War"]


def test_typed_genre_reuses_the_existing_spelling():
    assert parse_genres([], "sci-fi", ["Sci-Fi"]) == ["Sci-Fi"]


def test_the_same_genre_is_only_kept_once():
    assert parse_genres(["Drama"], "drama, Drama", ["Drama"]) == ["Drama"]


def test_ticked_and_typed_genres_combine():
    assert parse_genres(["Drama"], "Biopic", ["Drama"]) == ["Drama", "Biopic"]


# --- Sorting ---

def make_row(title, year=None, disc_score=None):
    return {"title": title, "release_year": year, "score": disc_score}


def titles(discs):
    return [d["title"] for d in discs]


def test_sort_by_score_puts_unscored_last():
    discs = [make_row("B", disc_score=None), make_row("A", disc_score=80), make_row("C", disc_score=102)]
    assert titles(sort_discs(discs, "score")) == ["C", "A", "B"]


def test_sort_by_year_is_newest_first_with_unknown_last():
    discs = [make_row("Old", 1995), make_row("Unknown"), make_row("New", 2023)]
    assert titles(sort_discs(discs, "year")) == ["New", "Old", "Unknown"]


def test_sort_by_title_ignores_capitals():
    discs = [make_row("heat"), make_row("Alien"), make_row("Casino")]
    assert titles(sort_discs(discs, "title")) == ["Alien", "Casino", "heat"]

# --- Score badges ---

@pytest.mark.parametrize("disc_score, band", [
    (None, "none"),
    (102, "top"),
    (90, "top"),
    (89.5, "good"),
    (75, "good"),
    (74.5, "low"),
])
def test_score_band(disc_score, band):
    assert score_band(disc_score) == band