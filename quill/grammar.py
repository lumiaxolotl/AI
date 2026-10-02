"""Rule-based grammar and punctuation checks."""

import re

from . import text as T

# Phrase -> correction for common mistakes. Matched case-insensitively on word boundaries.
CONFUSIONS = {
    "could of": "could have", "should of": "should have", "would of": "would have",
    "must of": "must have", "might of": "might have", "may of": "may have",
    "couldn't of": "couldn't have", "shouldn't of": "shouldn't have", "wouldn't of": "wouldn't have",
    "alot": "a lot", "irregardless": "regardless", "for all intensive purposes": "for all intents and purposes",
    "more then": "more than", "less then": "less than", "better then": "better than",
    "worse then": "worse than", "rather then": "rather than", "other then": "other than",
    "greater then": "greater than", "fewer then": "fewer than", "larger then": "larger than",
    "smaller then": "smaller than", "higher then": "higher than", "lower then": "lower than",
    "your welcome": "you're welcome", "it's own": "its own", "there own": "their own",
    "they're own": "their own", "suppose to": "supposed to", "free reign": "free rein",
    "case and point": "case in point", "one in the same": "one and the same", "per say": "per se",
    "wreck havoc": "wreak havoc", "baited breath": "bated breath", "peak my interest": "pique my interest",
    "peaked my interest": "piqued my interest", "sneak peak": "sneak peek", "each others": "each other's",
    "nip it in the butt": "nip it in the bud", "on accident": "by accident", "try and": "try to",
    "different than": "different from", "towards": "toward", "anyways": "anyway",
    "could care less": "couldn't care less", "make due": "make do", "deep seeded": "deep-seated",
    "tow the line": "toe the line", "hone in on": "home in on", "first come first serve": "first come, first served",
    "should of been": "should have been", "between you and I": "between you and me",
    "i seen": "I saw", "me and him": "he and I", "for awhile": "for a while", "a while ago": "a while ago",
    "in the mean time": "in the meantime", "every since": "ever since", "all of the sudden": "all of a sudden",
    "worse case scenario": "worst-case scenario", "statue of limitations": "statute of limitations",
    "intensive purposes": "intents and purposes", "lose cannon": "loose cannon", "would of been": "would have been",
}
# Style preferences rather than errors: reported as hints, never auto-applied.
SOFT_CONFUSIONS = {"towards", "anyways", "try and", "different than", "me and him", "a while ago"}

AN_EXCEPTIONS_CONSONANT_SOUND = ("uni", "use", "usu", "util", "uter", "ubiq", "eu", "ewe", "one", "once",
                                 "ufo", "uran", "ukr", "uga", "url", "user")
AN_EXCEPTIONS_VOWEL_SOUND = ("hour", "honest", "honor", "honour", "heir", "herb")


def _rx(phrase):
    return re.compile(r"(?<![\w'])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![\w'])", re.I)


_CONFUSION_RES = [(_rx(k), k, v) for k, v in CONFUSIONS.items() if k != v]


def _fix_case(original, replacement):
    if original[:1].isupper() and replacement[:1].islower():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _issue(kind, start, end, message, suggestions, severity="error", autofix=True):
    return {"kind": kind, "severity": severity, "start": start, "end": end, "message": message,
            "suggestions": suggestions, "autofix": autofix}


def check(text: str) -> list[dict]:
    masked = T.mask_urls(text)
    issues = []

    # Repeated word: "the the"
    for m in re.finditer(r"(?<![\w'])([A-Za-z]+)(\s+)\1(?![\w'])", masked, re.I):
        if m.group(1).lower() in ("had", "that", "is", "do"):
            continue
        issues.append(_issue("grammar", m.start(), m.end(), f"Repeated word: “{m.group(1)}”.", [m.group(1)]))

    # a / an
    for m in re.finditer(r"(?<![\w'])(a|an|A|An)\s+([A-Za-z][\w'-]*)", masked):
        art, word = m.group(1), m.group(2)
        if word.isupper() and len(word) > 1:
            continue  # acronyms depend on pronunciation (an FBI agent, a NASA probe)
        lw = word.lower()
        vowel = lw[0] in "aeiou"
        if lw.startswith(AN_EXCEPTIONS_CONSONANT_SOUND):
            vowel = False
        if lw.startswith(AN_EXCEPTIONS_VOWEL_SOUND):
            vowel = True
        want = "an" if vowel else "a"
        if art.lower() != want:
            fixed = _fix_case(art, want)
            issues.append(_issue("grammar", m.start(1), m.end(1),
                                 f"Use “{want}” before “{word}”.", [fixed]))

    # Lowercase "i" as a word
    for m in re.finditer(r"(?<![\w'’-])i(?=(?:['’](?:m|ve|ll|d))?(?![\w-]))", masked):
        issues.append(_issue("grammar", m.start(), m.end(), "Capitalise “I”.", ["I"]))

    # Sentence should start with a capital letter
    for s in T.sentences(masked):
        m = re.match(r"[\"'“‘(]*([a-z])", s.text)
        if m and not s.text.startswith(("e.g", "i.e", "etc", "iPhone", "iPad", "eBay")):
            pos = s.start + m.start(1)
            issues.append(_issue("grammar", pos, pos + 1, "Start the sentence with a capital letter.",
                                 [m.group(1).upper()]))

    # Space before punctuation
    for m in re.finditer(r"(?<=\w)[ \t]+([,;:!?]|\.(?!\.))", masked):
        issues.append(_issue("punctuation", m.start(), m.end(), "Remove the space before the punctuation.",
                             [m.group(1)]))

    # Missing space after punctuation
    for m in re.finditer(r"(?<=[a-z])([,;!?])(?=[A-Za-z])|(?<=[a-z]{2})(\.)(?=[A-Z][a-z])", masked):
        p = m.group(1) or m.group(2)
        issues.append(_issue("punctuation", m.start(), m.end(), "Add a space after the punctuation.", [p + " "]))

    # Double spaces
    for m in re.finditer(r"(?<=\S)  +(?=\S)", masked):
        issues.append(_issue("punctuation", m.start(), m.end(), "Extra space.", [" "], severity="hint"))

    # Repeated punctuation
    for m in re.finditer(r"([!?]){2,}|,{2,}|;{2,}", masked):
        issues.append(_issue("punctuation", m.start(), m.end(), "Repeated punctuation.", [m.group()[0]],
                             severity="hint"))

    # Common confusions
    for rx, phrase, fix in _CONFUSION_RES:
        for m in rx.finditer(masked):
            soft = phrase in SOFT_CONFUSIONS
            issues.append(_issue("style" if soft else "grammar", m.start(), m.end(),
                                 f"“{m.group()}” → “{fix}”." if soft else f"Did you mean “{fix}”?",
                                 [_fix_case(m.group(), fix)], severity="hint" if soft else "error",
                                 autofix=not soft))

    # their / there
    for m in re.finditer(r"(?<![\w'])(their)\s+(is|are|was|were|will|has|have|had|would|could|should|may|might)"
                         r"(?![\w'])", masked, re.I):
        issues.append(_issue("grammar", m.start(1), m.end(1), "Did you mean “there”?",
                             [_fix_case(m.group(1), "there")]))

    # its / it's
    for m in re.finditer(r"(?<![\w'])(its)\s+(a|an|the|not|been|going|time|true|important|clear|hard|easy|"
                         r"possible|likely|just|never|always|also|very|so|too|still|only|really)(?![\w'])",
                         masked, re.I):
        issues.append(_issue("grammar", m.start(1), m.end(1), "Did you mean “it's” (it is)?",
                             [_fix_case(m.group(1), "it's")]))

    # Unbalanced brackets and quotes (per paragraph)
    for p in T.paragraphs(masked):
        if p.text.count("(") != p.text.count(")"):
            issues.append(_issue("punctuation", p.start, p.start + min(len(p.text), 40),
                                 "Unmatched parenthesis in this paragraph.", [], severity="warning", autofix=False))
        if p.text.count('"') % 2 or p.text.count("“") != p.text.count("”"):
            issues.append(_issue("punctuation", p.start, p.start + min(len(p.text), 40),
                                 "Unmatched quotation mark in this paragraph.", [], severity="warning", autofix=False))
    return issues
