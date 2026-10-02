"""Spell checker built from scratch: edit-distance candidates ranked by how common each word is."""

import gzip
import json
from functools import lru_cache
from pathlib import Path

from . import text as T

LETTERS = "abcdefghijklmnopqrstuvwxyz"
_FREQ: dict[str, int] = {}
_extra: set[str] = set()
SUFFIXES = {"ing", "ed", "ly", "er", "est", "es", "s", "ness", "ment", "tion", "al", "ally", "ful", "less", "able",
            "ible", "ity", "ous", "ive", "ism", "ist", "ize", "ise", "en", "re", "un", "de", "ion"}
CONTRACTION_ENDINGS = ("'s", "'t", "'re", "'ve", "'ll", "'d", "'m")


def _load():
    if not _FREQ:
        path = Path(__file__).parent / "data" / "en_words.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as f:
            _FREQ.update(json.load(f))


def set_personal_words(words):
    """Words the writer has taught it (their dictionary and words from their own samples)."""
    _extra.clear()
    _extra.update(w.lower() for w in words if w)
    known.cache_clear()


@lru_cache(maxsize=50000)
def known(word: str) -> bool:
    _load()
    w = word.lower()
    if w in _FREQ or w in _extra:
        return True
    for end in CONTRACTION_ENDINGS:
        if w.endswith(end) and (w[: -len(end)] in _FREQ or w[: -len(end)] in _extra):
            return True
    return w in {"won't", "can't", "shan't", "ain't", "y'all", "o'clock"}


def frequency(word: str) -> int:
    _load()
    return _FREQ.get(word.lower(), 0)


def _edits1(w):
    splits = [(w[:i], w[i:]) for i in range(len(w) + 1)]
    deletes = [a + b[1:] for a, b in splits if b]
    swaps = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1]
    replaces = [a + c + b[1:] for a, b in splits if b for c in LETTERS]
    inserts = [a + c + b for a, b in splits for c in LETTERS]
    return set(deletes + swaps + replaces + inserts)


def suggestions(word: str, limit: int = 4) -> list[str]:
    _load()
    w = word.lower()
    pool = {e for e in _edits1(w) if e in _FREQ or e in _extra}
    if not pool and 4 <= len(w) <= 14:
        pool = {e2 for e1 in _edits1(w) for e2 in _edits1(e1) if e2 in _FREQ}
    # Run-together words: "alot" -> "a lot", "infact" -> "in fact"
    for i in range(1, len(w)):
        a, b = w[:i], w[i:]
        if (len(a) > 1 or a in "ai") and len(b) > 1 and b not in SUFFIXES and a not in SUFFIXES \
                and _FREQ.get(a, 0) > 50000 and _FREQ.get(b, 0) > 50000:
            pool.add(a + " " + b)

    def score(c):
        if " " in c:
            return min(_FREQ[p] for p in c.split()) / 5
        return _FREQ.get(c, 1000)

    ranked = sorted(pool, key=score, reverse=True)[:limit]
    return [_match_case(word, c) for c in ranked]


def _match_case(original, candidate):
    if original.isupper() and len(original) > 1:
        return candidate.upper()
    if original[:1].isupper():
        return candidate[:1].upper() + candidate[1:]
    return candidate


def check(text: str) -> list[dict]:
    """Find misspelled words. Skips names (capitalised mid-sentence), acronyms, URLs and code-like tokens."""
    masked = T.mask_urls(text)
    sentence_starts = {s.start for s in T.sentences(masked)}
    issues = []
    for w in T.words(masked):
        word = w.text
        if len(word) < 2 or known(word):
            continue
        if word.isupper():
            continue  # acronym
        if word[0].isupper() and w.start not in sentence_starts:
            continue  # probably a name
        nxt = text[w.end:w.end + 1]
        prv = text[w.start - 1:w.start] if w.start else ""
        if nxt.isdigit() or prv.isdigit() or nxt in ("_", "/") or prv in ("_", "/", "#", "@"):
            continue
        sugg = suggestions(word)
        issues.append({
            "kind": "spelling", "severity": "error", "start": w.start, "end": w.end,
            "message": f"Possible spelling mistake: “{word}”.",
            "suggestions": sugg,
            "autofix": bool(sugg) and _confident(word, sugg),
            "word": word,
        })
    return issues


def _confident(word, sugg):
    """Only auto-correct when the best guess is clearly better than the runner-up."""
    w, best = word.lower(), sugg[0].lower()
    if " " in best:
        return len(sugg) == 1
    second = sugg[1].lower() if len(sugg) > 1 else ""
    ratio = frequency(best) / max(1, frequency(second) if second and " " not in second else 0)
    if best not in _edits1(w):
        return ratio > 100
    if sorted(best) == sorted(w) and len(best) == len(w):
        return True  # swapped letters: "recieve" -> "receive"
    if second and second in _edits1(w):
        return ratio > 20  # two close candidates: only when one is far more common
    return not second or ratio > 5
