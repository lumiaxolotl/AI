"""Basic text handling: words, sentences, paragraphs, syllables. Every span keeps its character offsets."""

import re

WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
URLISH_RE = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\w+")

ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "inc", "ltd", "co",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "no", "fig",
    "approx", "dept", "est", "gen", "gov", "lt", "col", "capt", "sgt", "mt", "u.s", "u.k", "a.m", "p.m",
}

STOPWORDS = set("""
a about above after again against all almost also am among an and any are aren't as at be because been
before being below between both but by can can't cannot could couldn't did didn't do does doesn't doing
don't down during each either else even ever every few for from further get gets got had hadn't has
hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's
however i i'd i'll i'm i've if in into is isn't it it's its itself just let's like made make many may
me might more most much must mustn't my myself neither no nor not now of off often on once one only or
other others ought our ours ourselves out over own per perhaps quite rather really said same say says
shan't she she'd she'll she's should shouldn't since so some such than that that's the their theirs
them themselves then there there's these they they'd they'll they're they've this those though through
thus to too under until up upon us use used using very via was wasn't we we'd we'll we're we've well
were weren't what what's when when's where where's whether which while who who's whom whose why why's
will with within without won't would wouldn't yet you you'd you'll you're you've your yours yourself
yourselves also within new first two three one's
""".split())


class Span:
    __slots__ = ("text", "start", "end")

    def __init__(self, text, start, end):
        self.text, self.start, self.end = text, start, end

    def __repr__(self):
        return f"Span({self.text!r}, {self.start}, {self.end})"


def words(text: str) -> list[Span]:
    return [Span(m.group().replace("’", "'"), m.start(), m.end()) for m in WORD_RE.finditer(text)]


def tokens(text: str) -> list[str]:
    """Lowercase word list."""
    return [w.text.lower() for w in words(text)]


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 2]


def paragraphs(text: str) -> list[Span]:
    out = []
    for m in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text):
        if m.group().strip():
            out.append(Span(m.group(), m.start(), m.end()))
    return out


_SENT_END = re.compile(r"[.!?]+[\"'”’)\]]*(?=\s+|$)")


def sentences(text: str) -> list[Span]:
    """Split into sentences, respecting common abbreviations, decimals and line breaks."""
    out = []
    for para in paragraphs(text):
        start = 0
        body = para.text
        for m in _SENT_END.finditer(body):
            before = body[start:m.start()]
            last = re.search(r"(?:^|[\s(\"'“])([A-Za-z.]+)$", before)
            if m.group().startswith(".") and last:
                token = last.group(1).lower().rstrip(".")
                if token in ABBREVIATIONS or (len(token) == 1 and token.isalpha()):
                    continue
            _add_sentence(out, body, start, m.end(), para.start)
            start = m.end()
        _add_sentence(out, body, start, len(body), para.start)
    return out


def _add_sentence(out, body, start, end, offset):
    chunk = body[start:end]
    lead = len(chunk) - len(chunk.lstrip())
    chunk = chunk.strip()
    if chunk:
        s = offset + start + lead
        out.append(Span(chunk, s, s + len(chunk)))


def syllables(word: str) -> int:
    w = word.lower().strip("'")
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def mask_urls(text: str) -> str:
    """Blank out URLs and emails (same length) so checks don't flag them."""
    return URLISH_RE.sub(lambda m: " " * len(m.group()), text)


def context(text: str, start: int, end: int, width: int = 40) -> dict:
    a = max(0, start - width)
    b = min(len(text), end + width)
    return {"before": ("…" if a > 0 else "") + text[a:start], "match": text[start:end],
            "after": text[end:b] + ("…" if b < len(text) else "")}
