"""Style checks (wordiness, filler, passive voice, clichés, long sentences) and readability statistics."""

import re
from collections import Counter

from . import text as T

WORDY = {
    "in order to": "to", "due to the fact that": "because", "owing to the fact that": "because",
    "in light of the fact that": "because", "in spite of the fact that": "although",
    "despite the fact that": "although", "the fact that": "that", "at this point in time": "now",
    "at the present time": "now", "at this moment in time": "now", "in the event that": "if",
    "in the near future": "soon", "a large number of": "many", "a great deal of": "much",
    "a majority of": "most", "a number of": "several", "has the ability to": "can",
    "have the ability to": "can", "is able to": "can", "are able to": "can", "in close proximity to": "near",
    "with regard to": "about", "with respect to": "about", "in regard to": "about", "in regards to": "about",
    "in reference to": "about", "for the purpose of": "to", "for the reason that": "because",
    "in the process of": "", "on a daily basis": "daily", "on a regular basis": "regularly",
    "until such time as": "until", "it is important to note that": "", "it should be noted that": "",
    "it is worth noting that": "", "needless to say": "", "each and every": "every",
    "first and foremost": "first", "basic fundamentals": "fundamentals", "end result": "result",
    "final outcome": "outcome", "past history": "history", "future plans": "plans", "close proximity": "proximity",
    "completely finished": "finished", "absolutely essential": "essential", "advance planning": "planning",
    "unexpected surprise": "surprise", "free gift": "gift", "added bonus": "bonus", "true fact": "fact",
    "join together": "join", "repeat again": "repeat", "revert back": "revert", "return back": "return",
    "whether or not": "whether", "make a decision": "decide", "make a choice": "choose",
    "give consideration to": "consider", "take into consideration": "consider", "come to the conclusion": "conclude",
    "conduct an investigation": "investigate", "provide assistance": "help", "make an assumption": "assume",
    "is indicative of": "indicates", "in addition to": "besides", "prior to": "before", "subsequent to": "after",
    "a sufficient number of": "enough", "in the absence of": "without", "as a means of": "to",
    "by means of": "by", "in the amount of": "for", "in terms of": "in", "at all times": "always",
    "along the lines of": "like", "as of yet": "yet", "as to whether": "whether", "during the course of": "during",
    "in an effort to": "to", "in excess of": "more than", "is in need of": "needs", "the majority of": "most",
    "utilize": "use", "utilizes": "uses", "utilized": "used", "utilization": "use",
}

FILLERS = ["very", "really", "just", "quite", "rather", "somewhat", "basically", "actually", "literally",
           "totally", "extremely", "simply", "definitely", "certainly", "truly", "kind of", "sort of",
           "a bit", "a little bit", "pretty much", "in fact", "of course"]
# Fillers that can usually be deleted outright when tightening
SAFE_TO_DELETE = {"very", "really", "basically", "actually", "literally", "totally", "pretty much"}

HEDGES = ["i think", "i believe", "i feel like", "i feel that", "i guess", "in my opinion", "it seems that",
          "it appears that", "maybe", "perhaps", "might possibly", "could possibly"]

CLICHES = [
    "at the end of the day", "think outside the box", "low-hanging fruit", "move the needle",
    "game changer", "game-changer", "paradigm shift", "push the envelope", "touch base", "circle back",
    "in today's fast-paced world", "in today's world", "since the dawn of time", "throughout history",
    "it goes without saying", "last but not least", "few and far between", "the tip of the iceberg",
    "avoid it like the plague", "better late than never", "every cloud has a silver lining", "silver lining",
    "only time will tell", "read between the lines", "the bottom line", "time will tell", "when all is said and done",
    "a blessing in disguise", "a perfect storm", "at the drop of a hat", "beat around the bush",
    "bite the bullet", "break the ice", "by the same token", "cutting edge", "cutting-edge", "dead as a doornail",
    "easier said than done", "fit as a fiddle", "hit the ground running", "in the nick of time",
    "it is what it is", "leave no stone unturned", "level playing field", "lock, stock and barrel",
    "needle in a haystack", "on the same page", "plenty of fish in the sea", "raining cats and dogs",
    "the elephant in the room", "the writing on the wall", "think on your feet", "under the weather",
    "when push comes to shove", "win-win", "a whole new level", "the next level", "unlock the power",
    "delve into", "embark on a journey", "navigate the complexities", "a testament to", "rich tapestry",
    "in the realm of", "ever-evolving", "ever-changing landscape", "plays a crucial role", "stands as a",
]

BE = r"(?:am|is|are|was|were|be|been|being)"
IRREGULAR_PP = ("known written given taken made done seen built found told held kept left lost paid sent "
                "shown sold spent thought brought bought caught taught chosen driven eaten forgotten hidden "
                "ridden spoken stolen worn broken frozen woken beaten bitten born drawn grown thrown flown "
                "shaken sung begun won hit put set cut read led fed met felt heard said understood meant "
                "sought fought struck bound ground wound hung laid lit shut split spread sworn torn")
ED_ADJECTIVES = set("interested tired excited bored worried scared married concerned pleased surprised "
                    "satisfied disappointed annoyed amazed confused embarrassed frightened exhausted relaxed "
                    "involved supposed used based located related required needed called named excited "
                    "inspired determined prepared qualified experienced talented advanced detailed limited "
                    "red bed shed seed need feed speed weed ted ned fred bred".split())
PASSIVE_RE = re.compile(rf"(?<![\w'])({BE})\s+(?:\w+ly\s+)?(\w+ed|{'|'.join(IRREGULAR_PP.split())})(?![\w'])",
                        re.I)

LY_NOT_ADVERBS = set("""only family reply early likely unlikely apply supply fly july italy ally belly bully
daily weekly monthly yearly hourly holy ugly silly lonely lovely friendly elderly costly deadly lively curly
jelly rally butterfly assembly monopoly anomaly homily ply rely sly wily oily hilly chilly jolly folly holly lily
emily kelly molly sally billy burly comply imply multiply gully reply sully tally dolly golly bodily
italy scholarly orderly kindly timely likely manly womanly worldly heavenly ghostly courtly""".split())

_rx = lambda p: re.compile(r"(?<![\w'])" + re.escape(p).replace(r"\ ", r"\s+") + r"(?![\w'])", re.I)
_WORDY_RES = [(_rx(k), k, v) for k, v in WORDY.items()]
_FILLER_RES = [(_rx(k), k) for k in FILLERS]
_HEDGE_RES = [(_rx(k), k) for k in HEDGES]
_CLICHE_RES = [(_rx(k), k) for k in CLICHES]


def _issue(kind, start, end, message, suggestions, severity="hint", autofix=False):
    return {"kind": kind, "severity": severity, "start": start, "end": end, "message": message,
            "suggestions": suggestions, "autofix": autofix}


def check(text: str) -> list[dict]:
    masked = T.mask_urls(text)
    issues = []

    for rx, phrase, fix in _WORDY_RES:
        for m in rx.finditer(masked):
            msg = f"Wordy: “{m.group()}” → “{fix}”." if fix else f"“{m.group()}” can usually be cut."
            sugg = fix
            if fix and m.group()[:1].isupper():
                sugg = fix[:1].upper() + fix[1:]
            issues.append(_issue("wordy", m.start(), m.end(), msg, [sugg], "warning", autofix=bool(fix)))

    for rx, phrase in _FILLER_RES:
        for m in rx.finditer(masked):
            issues.append(_issue("filler", m.start(), m.end(),
                                 f"Filler word “{m.group()}” weakens the sentence.", [""],
                                 autofix=phrase in SAFE_TO_DELETE and not m.group()[:1].isupper()))

    for rx, phrase in _HEDGE_RES:
        for m in rx.finditer(masked):
            issues.append(_issue("hedge", m.start(), m.end(),
                                 f"Hedging (“{m.group()}”) can sound unsure. Cut it if you mean it.", [""]))

    for rx, phrase in _CLICHE_RES:
        for m in rx.finditer(masked):
            issues.append(_issue("cliche", m.start(), m.end(),
                                 f"Cliché: “{m.group()}”. Say it in your own words.", [], "warning"))

    for m in PASSIVE_RE.finditer(masked):
        if m.group(2).lower() in ED_ADJECTIVES:
            continue
        issues.append(_issue("passive", m.start(), m.end(),
                             f"Passive voice (“{m.group()}”). Active voice is usually clearer.", []))

    for w in T.words(masked):
        lw = w.text.lower()
        if lw.endswith("ly") and len(lw) > 4 and lw not in LY_NOT_ADVERBS:
            issues.append(_issue("adverb", w.start, w.end,
                                 f"Adverb “{w.text}”. A stronger verb often works better.", []))

    sents = T.sentences(masked)
    for s in sents:
        n = len(T.words(s.text))
        if n > 40:
            issues.append(_issue("long", s.start, s.end, f"Very long sentence ({n} words). Consider splitting it.",
                                 [], "warning"))
        elif n > 28:
            issues.append(_issue("long", s.start, s.end, f"Long sentence ({n} words).", []))

    # Three sentences in a row starting with the same word
    firsts = [(s, (T.tokens(s.text) or [""])[0]) for s in sents]
    for i in range(2, len(firsts)):
        w = firsts[i][1]
        if w and w == firsts[i - 1][1] == firsts[i - 2][1]:
            s = firsts[i][0]
            issues.append(_issue("repetition", s.start, s.start + len(w),
                                 f"Three sentences in a row start with “{w}”. Vary the openings.", []))

    # The same word overused in one paragraph
    for p in T.paragraphs(masked):
        ws = [w for w in T.words(p.text) if w.text.lower() not in T.STOPWORDS and len(w.text) > 3]
        counts = Counter(w.text.lower() for w in ws)
        flagged = set()
        for w in ws:
            lw = w.text.lower()
            if counts[lw] >= 3 and lw not in flagged and len(ws) < 300:
                flagged.add(lw)
                issues.append(_issue("repetition", p.start + w.start, p.start + w.end,
                                     f"“{w.text}” is used {counts[lw]} times in this paragraph.", []))
    return issues


def stats(text: str) -> dict:
    ws = T.words(text)
    sents = T.sentences(text)
    n_words, n_sents = len(ws), max(1, len(sents))
    syl = sum(T.syllables(w.text) for w in ws)
    complex_words = sum(1 for w in ws if T.syllables(w.text) >= 3)
    if n_words:
        ease = 206.835 - 1.015 * (n_words / n_sents) - 84.6 * (syl / n_words)
        grade = 0.39 * (n_words / n_sents) + 11.8 * (syl / n_words) - 15.59
        fog = 0.4 * ((n_words / n_sents) + 100 * complex_words / n_words)
    else:
        ease = grade = fog = 0
    lengths = [len(T.words(s.text)) for s in sents] or [0]
    passive = len([m for m in PASSIVE_RE.finditer(text) if m.group(2).lower() not in ED_ADJECTIVES])
    unique = len({w.text.lower() for w in ws})
    return {
        "words": n_words,
        "characters": len(text),
        "sentences": len(sents),
        "paragraphs": len(T.paragraphs(text)),
        "avg_sentence_words": round(n_words / n_sents, 1),
        "longest_sentence_words": max(lengths),
        "reading_ease": round(max(0, min(100, ease)), 1),
        "reading_ease_label": _ease_label(ease),
        "grade_level": round(max(0, grade), 1),
        "fog_index": round(fog, 1),
        "reading_time_min": round(n_words / 238, 1),
        "speaking_time_min": round(n_words / 150, 1),
        "vocabulary_variety": round(unique / n_words * 100) if n_words else 0,
        "passive_sentences": passive,
    }


def _ease_label(score):
    for limit, label in ((90, "Very easy"), (80, "Easy"), (70, "Fairly easy"), (60, "Plain English"),
                         (50, "Fairly difficult"), (30, "Difficult")):
        if score >= limit:
            return label
    return "Very difficult"
