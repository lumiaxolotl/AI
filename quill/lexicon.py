"""Synonyms, definitions and rhymes from free public word services (no keys, no accounts)."""

import json
import urllib.parse

from . import spelling, websearch


def _json(url):
    return json.loads(websearch.get(url))


def lookup(word: str) -> dict:
    word = word.strip()
    q = urllib.parse.quote(word.lower())
    out = {"word": word, "synonyms": [], "similar": [], "antonyms": [], "rhymes": [], "definitions": [],
           "spelling": [] if spelling.known(word) else spelling.suggestions(word, 6)}
    calls = {
        "synonyms": f"https://api.datamuse.com/words?rel_syn={q}&max=20",
        "similar": f"https://api.datamuse.com/words?ml={q}&max=20",
        "antonyms": f"https://api.datamuse.com/words?rel_ant={q}&max=10",
        "rhymes": f"https://api.datamuse.com/words?rel_rhy={q}&max=15",
    }
    errors = []
    for key, url in calls.items():
        try:
            out[key] = [w["word"] for w in _json(url)]
        except Exception as e:
            errors.append(str(e))
    out["similar"] = [w for w in out["similar"] if w not in out["synonyms"]][:15]
    try:
        for entry in _json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{q}")[:2]:
            for meaning in entry.get("meanings", []):
                for d in meaning.get("definitions", [])[:2]:
                    out["definitions"].append({"pos": meaning.get("partOfSpeech", ""),
                                               "text": d.get("definition", ""), "example": d.get("example", "")})
    except Exception:
        pass  # the dictionary service answers 404 for words it doesn't know
    if errors and not any(out[k] for k in calls):
        out["error"] = "Couldn't reach the word service. Check your internet connection."
    return out
