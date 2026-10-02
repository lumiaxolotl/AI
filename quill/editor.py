"""Combines all checks and applies fixes."""

from . import grammar, spelling, style
from . import text as T

SEVERITY_ORDER = {"error": 0, "warning": 1, "hint": 2}
# When several checks flag exactly the same words, keep only the most useful one
KIND_PRIORITY = ["grammar", "spelling", "punctuation", "wordy", "cliche", "filler", "hedge", "passive",
                 "long", "adverb", "repetition", "style"]


def check(text: str) -> dict:
    issues = spelling.check(text) + grammar.check(text) + style.check(text)
    issues.sort(key=lambda i: SEVERITY_ORDER[i["severity"]])
    # Drop exact duplicates and issues nested inside a higher-priority one at the same spot
    issues.sort(key=lambda i: (i["start"], i["end"], KIND_PRIORITY.index(i["kind"])))
    seen, out = set(), []
    for i in issues:
        key = (i["start"], i["end"])
        if key in seen:
            continue
        seen.add(key)
        i["context"] = T.context(text, i["start"], i["end"])
        out.append(i)
    counts = {}
    for i in out:
        counts[i["kind"]] = counts.get(i["kind"], 0) + 1
    score = _score(out, max(1, len(T.words(text))))
    return {"issues": out, "counts": counts, "stats": style.stats(text), "score": score}


def _score(issues, n_words):
    weight = {"error": 4, "warning": 1.5, "hint": 0.5}
    penalty = sum(weight[i["severity"]] for i in issues) / n_words * 100
    return max(0, min(100, round(100 - penalty * 0.7)))


def apply_fixes(text: str, fixes: list[dict]) -> str:
    """Apply [{start, end, replacement}] from the end backwards, skipping overlaps."""
    out = text
    last_start = len(text) + 1
    for f in sorted(fixes, key=lambda f: f["start"], reverse=True):
        start, end, rep = f["start"], f["end"], f["replacement"]
        if end > last_start:
            continue
        if rep == "":
            # Deleting a word: also remove one neighbouring space
            if start > 0 and out[start - 1] == " ":
                start -= 1
            elif end < len(out) and out[end] == " ":
                end += 1
        out = out[:start] + rep + out[end:]
        last_start = start
    return out


def tighten(text: str) -> dict:
    """Automatically apply every confident fix: spelling, grammar, punctuation, wordy phrases, filler."""
    current, changes = text, []
    for _ in range(3):  # a fix can reveal another (e.g. a sentence now starts lowercase)
        result = check(current)
        fixes = []
        for i in result["issues"]:
            if i.get("autofix") and i["suggestions"]:
                fixes.append({"start": i["start"], "end": i["end"], "replacement": i["suggestions"][0]})
                changes.append({"from": current[i["start"]:i["end"]], "to": i["suggestions"][0],
                                "why": i["message"]})
        if not fixes:
            break
        current = apply_fixes(current, fixes)
    return {"text": current, "changes": changes,
            "before": style.stats(text), "after": style.stats(current)}
