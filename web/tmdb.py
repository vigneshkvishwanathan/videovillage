"""Talking to TMDb (themoviedb.org). This runs on the server, so the API key stays private."""
import os

import requests

API = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w185"
POSTER_BIG = "https://image.tmdb.org/t/p/w500"
TOP_CAST = 5


def _get(path, **params):
    """Call TMDb and return the JSON reply as a dictionary. Raises if it fails."""
    params["api_key"] = os.environ["TMDB_API_KEY"]
    response = requests.get(API + path, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def year_of(date_text):
    """'2023-07-19' -> 2023. TMDb sends '' when it doesn't know."""
    return int(date_text[:4]) if date_text else None


def search(query):
    """Up to 10 films matching the query, with just enough to pick the right one."""
    data = _get("/search/movie", query=query, include_adult="false")
    return [
        {
            "tmdb_id": movie["id"],
            "title": movie["title"],
            "year": year_of(movie.get("release_date")),
            "poster_path": movie.get("poster_path"),
        }
        for movie in data["results"][:10]
    ]


def movie_facts(movie):
    """Turn TMDb's film details into our column names. No network here, so it's easy to test."""
    credits = movie.get("credits", {})
    crew = credits.get("crew", [])
    cast = sorted(credits.get("cast", []), key=lambda person: person.get("order", 999))

    return {
        "tmdb_id": movie["id"],
        "title": movie["title"],
        "release_year": year_of(movie.get("release_date")),
        "runtime_minutes": movie.get("runtime") or None,
        "overview": movie.get("overview") or None,
        "poster_path": movie.get("poster_path"),
        "directors": ", ".join(p["name"] for p in crew if p.get("job") == "Director") or None,
        "top_cast": ", ".join(p["name"] for p in cast[:TOP_CAST]) or None,
    }


def get_movie(tmdb_id):
    """One film's details and credits, in a single request."""
    return movie_facts(_get(f"/movie/{tmdb_id}", append_to_response="credits"))
