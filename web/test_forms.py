import os

import pytest
from werkzeug.datastructures import MultiDict

os.environ.setdefault("DATABASE_URL", "postgresql://not-used-by-these-tests")

from decimal import Decimal

from app import (
    clean_text, read_form, used_values, build_filter, read_filters, prepare_disc, 
    mark_already_have, ratio_choices, text_choices, filter_summary, filters_active,
    effective_order, ratio_chip_groups, ratio_label
    )  # noqa: E402

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

SEARCH_RESULTS = [
    {"tmdb_id": 1, "title": "Arrival"},
    {"tmdb_id": 2, "title": "The Thing"},
    {"tmdb_id": 3, "title": "The Godfather"},
]
HAVE = {
    2: {"id": 40, "tmdb_id": 2, "owned": True},
    3: {"id": 41, "tmdb_id": 3, "owned": False},
}


def test_films_you_own_say_in_collection():
    results = mark_already_have([dict(m) for m in SEARCH_RESULTS], HAVE)
    assert results[1]["badge"] == "In collection"
    assert results[1]["disc_id"] == 40


def test_films_on_the_wishlist_say_so():
    results = mark_already_have([dict(m) for m in SEARCH_RESULTS], HAVE)
    assert results[2]["badge"] == "On wishlist"


def test_new_films_have_no_badge():
    results = mark_already_have([dict(m) for m in SEARCH_RESULTS], HAVE)
    assert results[0]["badge"] is None
    assert results[0]["disc_id"] is None

def test_text_choices_merge_starters_with_used_values():
    assert text_choices(["Dolby Atmos", "DTS:X"], ["Auro-3D"]) == ["Auro-3D", "Dolby Atmos", "DTS:X"]


def test_text_choices_ignore_capitals_when_dropping_duplicates():
    assert text_choices(["Dolby Atmos"], ["dolby atmos"]) == ["Dolby Atmos"]


def test_ratio_choices_include_starters_and_used_ones():
    choices = ratio_choices([Decimal("1.66")])
    assert 1.66 in choices
    assert 2.39 in choices


def test_ratio_choices_do_not_repeat_a_starter_that_came_from_the_database():
    choices = ratio_choices([Decimal("2.39")])
    assert choices.count(2.39) == 1


def test_ratio_choices_are_widest_first():
    choices = ratio_choices([])
    assert choices == sorted(choices, reverse=True)

def filters_with(**changes):
    filters = {"q": "", "format": "", "genres": [], "sort": "score", "dir": None, "layout": "list"}
    filters.update(changes)
    return filters


def test_summary_with_no_filters():
    assert filter_summary(filters_with()) == "Highest score · All discs"


def test_summary_lists_every_filter_in_order():
    filters = filters_with(dir="asc", q="nolan", format="4K UHD", genres=["War", "Drama"])
    assert filter_summary(filters) == "Lowest score · “nolan” · 4K UHD · War + Drama"


def test_summary_uses_each_sort_s_natural_direction():
    assert filter_summary(filters_with(sort="title")) == "A–Z · All discs"
    assert filter_summary(filters_with(sort="year")) == "Newest · All discs"


def test_sorting_alone_does_not_count_as_filtering():
    assert filters_active(filters_with(sort="year", dir="asc")) is False
    assert filters_active(filters_with(genres=["War"])) is True

def test_an_order_chip_sets_sort_and_direction():
    view, filters = read_filters(MultiDict({"order": "title-desc"}))
    assert filters["sort"] == "title"
    assert filters["dir"] == "desc"


@pytest.mark.parametrize("bad", ["title-sideways", "colour-desc", "title", "-desc", ""])
def test_a_bad_order_is_ignored(bad):
    view, filters = read_filters(MultiDict({"order": bad}))
    assert filters["sort"] == "score"
    assert filters["dir"] is None


def test_effective_order_fills_in_the_natural_direction():
    assert effective_order(filters_with(sort="title")) == ("title", "asc")
    assert effective_order(filters_with(sort="year", dir="asc")) == ("year", "asc")


def test_effective_order_falls_back_to_highest_score():
    assert effective_order(filters_with(sort="junk")) == ("score", "desc")





# ---- Disc form: "+ New" values and the aspect ratio chips ----

def test_a_typed_video_format_wins_over_the_picked_chip():
    disc, errors = read_form(valid_form(video_format="SDR", new_video_format="  Dolby Vision IQ "), GENRES)
    assert errors == []
    assert disc["video_format"] == "Dolby Vision IQ"


def test_a_picked_audio_chip_is_used_when_nothing_is_typed():
    disc, _ = read_form(valid_form(audio_format="Dolby Atmos", new_audio_format=""), GENRES)
    assert disc["audio_format"] == "Dolby Atmos"


def test_the_none_chip_leaves_the_format_empty():
    disc, _ = read_form(valid_form(video_format=""), GENRES)
    assert disc["video_format"] is None


def test_wishlist_chip_means_not_owned():
    disc, _ = read_form(valid_form(owned="off"), GENRES)
    assert disc["owned"] is False
    disc, _ = read_form(valid_form(owned="on"), GENRES)
    assert disc["owned"] is True


def test_most_used_ratios_are_shown_and_the_rest_go_behind_more():
    counts = {Decimal("2.39"): 90, Decimal("1.78"): 40, Decimal("2.00"): 3, Decimal("1.33"): 1}
    shown, more = ratio_chip_groups(counts, [], top=3)
    assert shown == [2.39, 2.0, 1.78]
    assert 1.33 in more and 2.39 not in more


def test_a_ratio_the_disc_already_has_is_never_hidden():
    counts = {Decimal("2.39"): 90, Decimal("1.78"): 40, Decimal("1.33"): 1}
    shown, more = ratio_chip_groups(counts, [Decimal("1.33")], top=2)
    assert 1.33 in shown and 1.33 not in more


def test_every_ratio_lands_in_exactly_one_group():
    counts = {Decimal("2.39"): 5, Decimal("2.76"): 1}
    shown, more = ratio_chip_groups(counts, [], top=8)
    assert sorted(shown + more) == sorted(set(shown + more))
    assert set(shown + more) == set(ratio_choices(list(counts)))


def test_ratios_are_written_like_on_the_case():
    assert ratio_label(Decimal("2.39")) == "2.39:1"
    assert ratio_label(2.2) == "2.20:1"
