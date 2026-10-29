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


def sort_discs(discs, by, direction=None):
    """Sort by "score", "title" or "year", in direction "asc" or "desc".

    No direction means the natural one: score high to low, title A to Z, year newest first.
    Discs missing the thing being sorted on stay at the bottom either way.
    """
    if direction is None:
        direction = "asc" if by == "title" else "desc"

    if by == "title":
        return sorted(discs, key=lambda d: d["title"].lower(), reverse=(direction == "desc"))

    if by == "year":
        if direction == "asc":
            return sorted(discs, key=lambda d: (d["release_year"] is None, d["release_year"] or 0, d["title"].lower()))
        return sorted(discs, key=lambda d: (d["release_year"] is None, -(d["release_year"] or 0), d["title"].lower()))

    if direction == "asc":
        return sorted(discs, key=lambda d: (d["score"] is None, d["score"] or 0, d["title"].lower()))
    return sorted(discs, key=lambda d: (d["score"] is None, -(d["score"] or 0), d["title"].lower()))
    
def score_band(disc_score):
    """Which colour a score badge gets: green, lime, yellow, orange, red, or none when unscored."""
    if disc_score is None:
        return "none"
    if disc_score > 90:
        return "green"
    if disc_score >= 80:
        return "lime"
    if disc_score >= 75:
        return "yellow"
    if disc_score >= 70:
        return "orange"
    return "red"

def rating_band(rating):
    '''define the colors for the various ratings'''
    if rating is None:
        return "none"
    elif rating >= 4.5:
        return "green"
    elif rating >= 4:
        return "lime"
    elif rating >=3:
        return "yellow"
    elif rating >= 2:
        return "orange"
    return "red"

def parse_aspect_ratios(checked, typed):
    """Combine ticked ratios with typed ones ("2.40:1, 1.90") into numbers, widest first.

    Raises ValueError for anything that isn't a ratio between 0 and 100.
    """
    result = []
    for text in list(checked) + (typed or "").split(","):
        # 1. Trim the spaces off text.
        text = text.strip(" ")
        # 2. If it's now empty, skip it (continue).
        if text == "":
            continue
        # 3. If it ends with ":1", cut those 2 characters off.
        if text.endswith(":1"):
            text = text[:-2]
        # 4. Turn it into a number with float(). (For "abc", float() raises ValueError by itself.)
        
        value = float(text)
        
        # 5. If the number isn't above 0 and below 100, raise ValueError.
        if not (0 < value < 100):
            raise ValueError(f"{text} is not an aspect ratio")
        # 6. Round it to 2 decimal places.
        value = round(value, 2)
        # 7. If it's not already in result, add it.
        if value not in result:
            result.append(value)
    return sorted(result, reverse=True)
