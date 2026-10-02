"""Web research built from scratch: search, read pages, and pull out the most relevant facts with citations."""

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import summarize as S
from . import text as T
from . import websearch

BOILERPLATE = re.compile(
    r"cookie|subscribe|sign up|sign in|log in|newsletter|javascript|privacy policy|terms of (use|service)|"
    r"all rights reserved|click here|advertis|your browser|accept all|skip to|share this|follow us|"
    r"related articles|read more|copyright|©", re.I)


def gather(query: str, pages: int = 5) -> list[dict]:
    """Search the web and read the top pages. Returns numbered sources with their text."""
    results = websearch.search(query, max_results=max(pages + 3, 8))

    def read(r):
        try:
            return {**r, "text": websearch.fetch_page(r["url"])["text"]}
        except Exception:
            return {**r, "text": ""}

    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(read, results[:pages]))
    fetched += [{**r, "text": ""} for r in results[pages:]]
    return [{"n": i, **r} for i, r in enumerate(fetched, 1)]


def passages(sources: list[dict]) -> list[dict]:
    """Every usable sentence from every source (page text plus the search snippet)."""
    out, seen = [], set()
    for src in sources:
        snippet = src.get("snippet", "")
        if snippet.rstrip().endswith(("...", "…")) or not snippet.rstrip().endswith((".", "!", "?")):
            snippet = ""  # cut-off snippets can hide the part of a sentence that matters
        for body in (src.get("text", ""), snippet):
            for s in T.sentences(body):
                sent = " ".join(s.text.split())
                n = len(sent.split())
                if n < 7 or n > 60 or BOILERPLATE.search(sent) or sum(c.isalpha() for c in sent) < len(sent) * 0.6:
                    continue
                key = sent.lower()[:80]
                if key in seen:
                    continue
                seen.add(key)
                out.append({"text": sent, "source": src["n"], "tokens": T.content_tokens(sent)})
    return out


def best_passages(query: str, pool: list[dict], k: int = 8, extra_terms: list[str] = ()) -> list[dict]:
    """BM25 relevance plus a diversity rule so the points don't repeat each other."""
    if not pool:
        return []
    q = T.content_tokens(query) + [w for t in extra_terms for w in T.content_tokens(t)]
    bm = S.BM25([p["tokens"] for p in pool])
    scored = sorted(((bm.score(q, i), i) for i in range(len(pool))), reverse=True)
    chosen, per_source = [], Counter()
    for score, i in scored:
        if score <= 0 or len(chosen) >= k:
            break
        p = pool[i]
        if per_source[p["source"]] >= max(2, k // 3):
            continue
        toks = set(p["tokens"])
        if any(len(toks & set(c["tokens"])) / max(1, len(toks | set(c["tokens"]))) > 0.45 for c in chosen):
            continue
        chosen.append({**p, "score": round(score, 2)})
        per_source[p["source"]] += 1
    return chosen


def _public(sources):
    return [{"n": s["n"], "title": s["title"], "url": s["url"]} for s in sources]


def research(query: str) -> dict:
    sources = gather(query)
    pool = passages(sources)
    all_text = "\n".join(s.get("text", "") or s.get("snippet", "") for s in sources)
    terms = S.keyphrases(all_text, 12)
    points = best_passages(query, pool, 8)
    return {"query": query, "points": [{"text": p["text"], "source": p["source"]} for p in points],
            "keyterms": terms, "sources": _public(sources)}


def outline(topic: str) -> dict:
    """Build a structured outline: sections come from the key phrases the best sources share."""
    sources = gather(topic, pages=6)
    pool = passages(sources)
    docs = [s.get("text", "") or s.get("snippet", "") for s in sources]
    topic_words = set(T.content_tokens(topic))
    # Key phrases that show up in several sources are likely the real sub-topics
    doc_freq = Counter()
    for d in docs:
        for kp in set(S.keyphrases(d, 25)):
            doc_freq[kp] += 1
    candidates = [kp for kp, c in doc_freq.most_common(60) if c >= 2 and _good_heading(kp, topic_words)]
    candidates += [kp for kp in S.keyphrases("\n".join(docs), 30) if kp not in candidates
                   and _good_heading(kp, topic_words)]
    candidates.sort(key=lambda kp: (len(kp.split()) == 1, -doc_freq[kp]))
    sections, used = [], set()
    for kp in candidates:
        if len(sections) >= 6:
            break
        notes = [p for p in best_passages(topic + " " + kp, pool, 3, [kp])
                 if p["text"] not in used and set(kp.split()) & set(p["tokens"])]
        if not notes:
            continue
        used.update(n["text"] for n in notes)
        sections.append({"heading": title_case(kp), "notes": [{"text": n["text"], "source": n["source"]} for n in notes]})
    return {"topic": topic, "sections": sections, "sources": _public(sources)}


SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "nor", "of", "on", "or", "the", "to", "vs", "via"}


def title_case(phrase: str) -> str:
    words = phrase.split()
    return " ".join(w if w.isupper() and len(w) > 1 else
                    (w.lower() if i and w.lower() in SMALL_WORDS else w[:1].upper() + w[1:])
                    for i, w in enumerate(words))


COMMON_VERBS = set("""is are was were be been has have had do does did say says said make makes made take takes took
give gives gave go goes went get gets got know knows knew see sees saw think thinks thought come comes came want
wants find finds found tell tells told become becomes became show shows showed leave leaves left feel feels felt
put puts bring brings brought begin begins began keep keeps hold holds held write writes wrote stand stands stood
hear hears heard let lets mean means meant set sets meet meets met run runs ran pay pays paid sit sits sat speak
speaks spoke lie lies lead leads led read reads grow grows grew lose loses lost fall falls fell send sends sent
build builds built understand understands draw draws drew break breaks broke spend spends spent cut cuts rise
rises rose drive drives drove buy buys bought wear wears wore choose chooses chose seek seeks sought throw throws
threw catch catches caught deal deals dealt win wins won uses helps includes provides offers allows remains
seems looks works needs believes admired argues argued suggests explains describes""".split())


def _good_heading(kp: str, topic_words: set) -> bool:
    """Noun-like phrases make good headings; verb phrases ("later writers adopted") don't."""
    words = kp.split()
    if set(words) <= topic_words or len(words) > 3:
        return False
    if any((w.endswith(("ed", "ly")) and len(w) > 4) or w in COMMON_VERBS for w in words):
        return False
    if len(words) == 1 and words[0].endswith("ing"):
        return False
    return len(words) > 1 or len(words[0]) > 4


TITLE_TEMPLATES = [
    "The Hidden Story of {X}", "Why {X} Matters More Than You Think", "{X}: What Nobody Tells You",
    "A Beginner's Guide to {X}", "{N} Things I Learned About {X}", "How {X} Is Changing {Y}",
    "The Truth About {X}", "{X}, Explained", "What {X} Can Teach Us About {Y}", "Rethinking {X}",
    "The Case For (and Against) {X}", "Inside {X}", "{X} and {Y}: An Unlikely Connection",
    "Everything You Need to Know About {X}", "The Future of {X}", "Before You Try {X}, Read This",
]
ANGLES = [
    ("Personal story", "Tell it through your own experience with {X}: when you first met it and what changed."),
    ("How-to", "Walk the reader step by step through doing or understanding {X}."),
    ("Contrarian", "Argue against the most common belief about {X}. What does everyone get wrong?"),
    ("History", "Trace how {X} came to be, and the turning points along the way."),
    ("Future", "Where is {X} heading? Make a prediction and defend it."),
    ("Comparison", "Set {X} side by side with {Y}. What does the contrast reveal?"),
    ("Explainer", "Explain {X} to a smart friend who knows nothing about it."),
    ("Interview / profile", "Find a person whose life is shaped by {X} and tell their story."),
    ("Myth-busting", "List the biggest myths about {X} and correct each with evidence."),
    ("Debate", "Present the strongest case on each side of {X}, then say where you land."),
]


def ideas(topic: str) -> dict:
    """Brainstorm titles, angles and questions, seeded by what the web is saying about the topic."""
    try:
        sources = gather(topic, pages=4)
    except Exception:
        sources = []
    docs = "\n".join((s.get("text") or "") + "\n" + (s.get("snippet") or "") for s in sources)
    topic_words = set(T.content_tokens(topic))
    related = [kp for kp in S.keyphrases(docs, 40) if _good_heading(kp, topic_words)][:12]
    X = title_case(topic.strip()) if len(topic) < 60 else "This Topic"
    Ys = [title_case(r) for r in related[:6]] or ["Everyday Life", "the World", "Writers"]
    titles = []
    for i, t in enumerate(TITLE_TEMPLATES):
        titles.append(t.format(X=X, Y=Ys[i % len(Ys)], N=[5, 7, 10, 12][i % 4]))
    angles = [{"name": n, "idea": d.format(X=topic.strip(), Y=Ys[i % len(Ys)].lower())}
              for i, (n, d) in enumerate(ANGLES)]
    questions = []
    for s in sources:
        if s["title"].strip().endswith("?"):
            questions.append(s["title"].strip())
    for sent in re.findall(r"[A-Z][^.?!]{15,140}\?", docs):
        if len(questions) >= 10:
            break
        q = " ".join(sent.split())
        if q not in questions and not BOILERPLATE.search(q):
            questions.append(q)
    return {"topic": topic, "titles": titles, "angles": angles, "related": related,
            "questions": questions[:10], "sources": _public(sources)}


OPINION_RE = re.compile(r"\b(I|we|you)\s+(think|believe|feel|guess|hope|wish|should|must|need|want|love|like|hate)\b|"
                        r"\b(should|ought to|in my opinion|I'd|let's)\b", re.I)
NUM_RE = re.compile(r"\d(?:[\d,.]*\d)?")


def factcheck(text: str, max_claims: int = 8) -> dict:
    """For each checkable sentence, find the closest matching statement on the web.

    This is an evidence finder, not a judge: it shows how well the web agrees, and flags numbers that differ.
    """
    claims, others = [], []
    for s in T.sentences(text):
        if len(T.content_tokens(s.text)) < 3 or OPINION_RE.search(s.text) or s.text.rstrip().endswith("?"):
            continue
        # Numbers, dates and names (capitalised words after the first) are what can be checked
        if NUM_RE.search(s.text) or re.search(r"\S\s+[A-Z][a-z]+", s.text):
            claims.append(s)
        else:
            others.append(s)
    claims = (claims or others)[:max_claims]

    def check_one(span):
        query = " ".join(T.content_tokens(span.text)[:12])
        try:
            sources = gather(query, pages=3)
        except Exception as e:
            return {"claim": span.text, "verdict": "error", "note": f"Search failed: {e}", "evidence": []}
        pool = passages(sources)
        claim_toks = set(T.content_tokens(span.text))
        best = []
        for p in pool:
            toks = set(p["tokens"])
            overlap = len(claim_toks & toks) / max(1, len(claim_toks))
            best.append((overlap, p))
        best.sort(key=lambda x: -x[0])
        top = best[:3]
        score = top[0][0] if top else 0
        verdict, note = "unverified", "No closely matching statement found online."
        if score >= 0.6:
            verdict, note = "supported", "A source says nearly the same thing."
        elif score >= 0.35:
            verdict, note = "partial", "Sources discuss this, but not in the same words. Read them to confirm."
        claim_nums = {n.replace(",", "") for n in NUM_RE.findall(span.text)}
        if claim_nums:
            for s, p in top:
                ev_nums = {n.replace(",", "") for n in NUM_RE.findall(p["text"])}
                if s >= 0.35 and ev_nums:
                    if not claim_nums & ev_nums:
                        verdict, note = "check", "A matching source gives different numbers. Double-check them."
                    break
        return {
            "claim": span.text, "start": span.start, "end": span.end, "verdict": verdict, "note": note,
            "match": round(score * 100),
            "evidence": [{"text": p["text"], "title": sources[p["source"] - 1]["title"],
                          "url": sources[p["source"] - 1]["url"]} for s, p in top if s > 0.2],
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check_one, claims))
    return {"claims": results}
