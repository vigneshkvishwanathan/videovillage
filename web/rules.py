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