"""The rules about ratings and the score. No Flask or database here, so it's easy to test."""

RATING_FIELDS = ["audio_rating", "video_rating", "overall_rating", "rewatch_rating"]


def parse_rating(text):
    """'' -> None, '4.5' -> 4.5. Raises ValueError unless it's 0-5 in half steps."""
    text = (text or "").strip()
    if not text:
        return None
    value = float(text)
    if value < 0 or value > 5 or (value * 2) % 1 != 0:
        raise ValueError(f"{text} is not a rating")
    return value


def watched_rule_error(disc):
    """You can only rate a disc you've watched. Returns a message, or None if it's fine."""
    has_rating = any(disc[field] is not None for field in RATING_FIELDS)
    if has_rating and disc["viewings"] < 1:
        return "You can only rate a disc you've watched. Add a viewing, or clear the ratings."
    return None


def score(disc):
    """(audio + video + overall + rewatch) x 5 + viewings - 1, or None if any rating is missing."""
    ratings = [disc[field] for field in RATING_FIELDS]
    if None in ratings:
        return None
    return float(sum(ratings)) * 5 + disc["viewings"] - 1

def parse_genres(checked, typed, known):
    """Combine ticked genres with newly typed ones ("Epic, Heist").

    Trims spaces, drops blanks and duplicates, and reuses the existing spelling
    when a typed genre matches a known one, so "sci-fi" becomes "Sci-Fi".
    """
    spelling = {name.lower(): name for name in known}
    result = []
    for name in list(checked) + (typed or "").split(","):
        name = name.strip()
        if not name:
            continue
        name = spelling.get(name.lower(), name)
        if name.lower() not in [g.lower() for g in result]:
            result.append(name)
    return result


def sort_discs(discs, by):
    """Sort by "title", "year" (newest first) or, by default, "score" (highest first).

    Discs missing the thing being sorted on go to the bottom, in title order.
    """
    if by == "title":
        return sorted(discs, key=lambda d: d["title"].lower())
    if by == "year":
        return sorted(
            discs,
            key=lambda d: (d["release_year"] is None, -(d["release_year"] or 0), d["title"].lower()),
        )
    return sorted(
        discs,
        key=lambda d: (d["score"] is None, -(d["score"] or 0), d["title"].lower()),
    )