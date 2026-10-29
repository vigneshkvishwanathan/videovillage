import pytest

from rules import parse_genres, parse_aspect_ratios, parse_rating, rating_band, score, score_band, sort_discs, watched_rule_error
from decimal import Decimal

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
    
def test_sort_by_score_low_to_high_still_puts_unscored_last():
    discs = [make_row("B", disc_score=None), make_row("A", disc_score=80), make_row("C", disc_score=102)]
    assert titles(sort_discs(discs, "score", "asc")) == ["A", "C", "B"]


def test_sort_by_year_oldest_first_still_puts_unknown_last():
    discs = [make_row("Old", 1995), make_row("Unknown"), make_row("New", 2023)]
    assert titles(sort_discs(discs, "year", "asc")) == ["Old", "New", "Unknown"]


def test_sort_by_title_z_to_a():
    discs = [make_row("heat"), make_row("Alien"), make_row("Casino")]
    assert titles(sort_discs(discs, "title", "desc")) == ["heat", "Casino", "Alien"]


@pytest.mark.parametrize("by, direction", [("score", "desc"), ("year", "desc"), ("title", "asc")])
def test_naming_the_default_direction_changes_nothing(by, direction):
    discs = [make_row("heat", 1995, 80), make_row("Alien"), make_row("Casino", 2023, 102)]
    assert sort_discs(discs, by, direction) == sort_discs(discs, by)


def test_equal_scores_stay_a_to_z_in_both_directions():
    discs = [make_row("Zodiac", disc_score=90), make_row("Arrival", disc_score=90)]
    assert titles(sort_discs(discs, "score", "asc")) == ["Arrival", "Zodiac"]
    assert titles(sort_discs(discs, "score", "desc")) == ["Arrival", "Zodiac"]

# --- Score badges ---

@pytest.mark.parametrize("disc_score, band", [
    (None, "none"),
    (102, "green"),
    (90.5, "green"),
    (90, "lime"),      # exactly 90 is lime now: green is *above* 90
    (89.5, "lime"),
    (80, "lime"),
    (79.5, "yellow"),
    (75, "yellow"),
    (74.5, "orange"),
    (70, "orange"),
    (69.5, "red"),
    (12, "red"),
])
def test_score_band(disc_score, band):
    assert score_band(disc_score) == band

# --- Rating colours ---

@pytest.mark.parametrize("rating, band", [
    (None, "none"),
    (0, "red"), (0.5, "red"), (1, "red"), (1.5, "red"),
    (2, "orange"), (2.5, "orange"),
    (3, "yellow"), (3.5, "yellow"),
    (4, "lime"),
    (4.5, "green"), (5, "green"),
    (Decimal("4.5"), "green"),
])
def test_rating_band(rating, band):
    assert rating_band(rating) == band

# --- Aspect ratios ---

def test_aspect_ratios_from_chips():
    assert parse_aspect_ratios(["2.39", "1.78"], "") == [2.39, 1.78]


def test_aspect_ratio_typed_with_or_without_colon_one():
    assert parse_aspect_ratios([], "2.40:1") == [2.4]
    assert parse_aspect_ratios([], "2.40") == [2.4]


def test_aspect_ratios_typed_as_a_list():
    assert parse_aspect_ratios([], "1.90, 1.43:1") == [1.9, 1.43]


def test_aspect_ratios_drop_duplicates_and_blanks():
    assert parse_aspect_ratios(["2.39", ""], "2.39:1, ") == [2.39]


def test_aspect_ratios_widest_first():
    assert parse_aspect_ratios(["1.78"], "2.39") == [2.39, 1.78]


def test_no_aspect_ratios_is_an_empty_list():
    assert parse_aspect_ratios([], None) == []


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "100", "2.39:2"])
def test_bad_aspect_ratio_is_refused(bad):
    with pytest.raises(ValueError):
        parse_aspect_ratios([], bad)
