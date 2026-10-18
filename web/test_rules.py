import pytest

from rules import parse_rating, score, watched_rule_error


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