import os

import pytest
from werkzeug.datastructures import MultiDict

os.environ.setdefault("DATABASE_URL", "postgresql://not-used-by-these-tests")

from app import clean_text, read_form, used_values  # noqa: E402

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