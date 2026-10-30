import os

import pytest
from werkzeug.datastructures import MultiDict

os.environ.setdefault("DATABASE_URL", "postgresql://not-used-by-these-tests")

from app import clean_text, read_form, used_values, build_filter, read_filters, prepare_disc  # noqa: E402

GENRES = ["Drama", "Sci-Fi"]


def valid_form(**changes):
    """A form that should pass, with any fields you want to change swapped in."""
    form = {"title": "Heat", "disc_format": "Blu-ray", "viewings": "0"}
    form.update(changes)
    return MultiDict(form)


def test_a_valid_form_has_no_errors():
    disc, errors = read_form(valid_form(), GENRES)
    assert errors == []
    assert disc["title"] == "Heat"
    
#Vig's rules
def test_a_form_without_a_title_is_refused():
    disc, errors = read_form(valid_form(title="\t"), GENRES)
    assert errors == ["Title is required."]
    
def test_rating_an_unwatched_disc_through_the_form_is_refused():
    disc, errors = read_form(valid_form(audio_rating="4"), GENRES)
    assert any("watched" in e for e in errors)
    
def test_negative_viewings_are_refused():
    disc, errors = read_form(valid_form(viewings="-1"), GENRES)
    assert errors == ["Viewings must be 0 or more."]
    
def test_a_typed_genre_reuses_the_existing_spelling():
    disc, errors = read_form(valid_form(new_genres="sci-fi"), GENRES)
    assert disc["genres"] == ["Sci-Fi"]
    
def test_used_values_refuses_a_column_not_on_the_list():
    with pytest.raises(ValueError):
        used_values(None, "title; DROP TABLE discs")

def test_a_blank_box_becomes_none():
    assert clean_text("   ") is None
    
def test_two_aspect_ratios_are_saved():
    form = valid_form()
    form.setlist("aspect_ratios", ["2.39", "1.78"])
    disc, errors = read_form(form, GENRES)
    assert errors == []
    assert disc["aspect_ratios"] == [2.39, 1.78]


def test_a_typed_aspect_ratio_is_added():
    disc, errors = read_form(valid_form(new_aspect_ratio="2.40:1"), GENRES)
    assert disc["aspect_ratios"] == [2.4]


def test_a_bad_aspect_ratio_is_refused():
    disc, errors = read_form(valid_form(new_aspect_ratio="abc"), GENRES)
    assert any("aspect" in e.lower() for e in errors)

NO_FILTERS = {"q": "", "format": "", "genres": []}


def test_no_genres_adds_no_genre_filter():
    where, params = build_filter("collection", NO_FILTERS)
    assert "genres" not in where


def test_genres_must_all_match():
    where, params = build_filter("collection", {**NO_FILTERS, "genres": ["War", "Drama"]})
    assert "genres @> %(genres)s::text[]" in where
    assert params["genres"] == ["War", "Drama"]


def test_wishlist_view_looks_at_unowned_discs():
    where, params = build_filter("wishlist", NO_FILTERS)
    assert params["owned"] is False
    
def test_sort_direction_is_read_from_the_address_bar():
    view, filters = read_filters(MultiDict({"sort": "year", "dir": "asc"}))
    assert filters["dir"] == "asc"


def test_no_direction_means_the_default():
    view, filters = read_filters(MultiDict({}))
    assert filters["dir"] is None


@pytest.mark.parametrize("bad", ["sideways", "ASC", "", "desc; DROP TABLE discs"])
def test_a_bad_sort_direction_falls_back_to_the_default(bad):
    view, filters = read_filters(MultiDict({"dir": bad}))
    assert filters["dir"] is None


def test_several_genres_are_read_from_the_address_bar():
    view, filters = read_filters(MultiDict([("genre", "War"), ("genre", "Drama"), ("genre", "")]))
    assert filters["genres"] == ["War", "Drama"]

def test_card_layout_is_read_from_the_address_bar():
    view, filters = read_filters(MultiDict({"layout": "cards"}))
    assert filters["layout"] == "cards"


def test_layout_defaults_to_list():
    view, filters = read_filters(MultiDict({}))
    assert filters["layout"] == "list"


@pytest.mark.parametrize("bad", ["grid", "CARDS", ""])
def test_an_unknown_layout_falls_back_to_list(bad):
    view, filters = read_filters(MultiDict({"layout": bad}))
    assert filters["layout"] == "list"

def rated_disc(**changes):
    disc = {"viewings": 2, "audio_rating": 5, "video_rating": 4,
            "overall_rating": 3, "rewatch_rating": 1.5}
    disc.update(changes)
    return disc


def test_prepare_disc_adds_the_score_and_its_colour():
    disc = prepare_disc(rated_disc())
    assert disc["score"] == 68.5
    assert disc["band"] == "red"


def test_prepare_disc_colours_each_rating():
    rows = prepare_disc(rated_disc())["rating_rows"]
    assert [r["label"] for r in rows] == ["Audio", "Video", "Overall", "Rewatchability"]
    assert [r["band"] for r in rows] == ["green", "lime", "yellow", "red"]


def test_an_unrated_disc_has_no_score():
    disc = prepare_disc(rated_disc(viewings=0, audio_rating=None, video_rating=None,
                                   overall_rating=None, rewatch_rating=None))
    assert disc["score"] is None
    assert disc["band"] == "none"
    assert all(r["band"] == "none" for r in disc["rating_rows"])
