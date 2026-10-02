"""Extractive summaries and key-phrase extraction (no AI model: word statistics and graph ranking)."""

import math
import re
from collections import Counter, defaultdict

from . import text as T


def keyphrases(text: str, limit: int = 12) -> list[str]:
    """RAKE-style: candidate phrases are runs of non-stopwords; score by word degree/frequency."""
    phrases = []
    for chunk in re.split(r"[.,;:!?()\[\]\"“”\n—–]+|\s-\s", text):
        current = []
        for tok in T.tokens(chunk):
            if tok in T.STOPWORDS or len(tok) < 3:
                if current:
                    phrases.append(tuple(current))
                current = []
            else:
                current.append(tok)
        if current:
            phrases.append(tuple(current))
    phrases = [p for p in phrases if len(p) <= 4]
    freq, degree = Counter(), Counter()
    for p in phrases:
        for w in p:
            freq[w] += 1
            degree[w] += len(p)
    phrase_count = Counter(phrases)
    scored = {}
    for p, c in phrase_count.items():
        s = sum(degree[w] / freq[w] for w in p) * (1 + math.log(c))
        if len(p) == 1 and freq[p[0]] < 2:
            s *= 0.5
        scored[p] = s
    out, used = [], set()
    for p, _ in sorted(scored.items(), key=lambda x: -x[1]):
        if p in used or any(set(p) <= set(q) for q in used):
            continue
        used.add(p)
        out.append(" ".join(p))
        if len(out) >= limit:
            break
    return out


def _similarity(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    num = sum(a[w] * b[w] for w in common)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


def rank_sentences(sents: list[str]) -> list[float]:
    """TextRank: sentences that share many words with other sentences are central."""
    bags = [Counter(T.content_tokens(s)) for s in sents]
    n = len(sents)
    sim = [[_similarity(bags[i], bags[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    out_sum = [sum(row) or 1 for row in sim]
    scores = [1.0] * n
    for _ in range(30):
        scores = [0.15 + 0.85 * sum(sim[j][i] / out_sum[j] * scores[j] for j in range(n)) for i in range(n)]
    return scores


def summarize(text: str, ratio: float = 0.25, max_sentences: int = 8) -> dict:
    sents = [s.text for s in T.sentences(text)]
    if len(sents) <= 2:
        return {"summary": " ".join(sents), "sentences": sents, "keyphrases": keyphrases(text)}
    if len(sents) > 400:
        sents = sents[:400]
    scores = rank_sentences(sents)
    for i in range(len(scores)):
        if i == 0:
            scores[i] *= 1.25  # openings often state the point
        if len(T.words(sents[i])) < 6:
            scores[i] *= 0.5
    k = max(1, min(max_sentences, round(len(sents) * ratio)))
    top = sorted(sorted(range(len(sents)), key=lambda i: -scores[i])[:k])
    chosen = [sents[i] for i in top]
    return {"summary": " ".join(chosen), "sentences": chosen, "keyphrases": keyphrases(text)}


class BM25:
    """Classic search-engine ranking, used to find the passages that best answer a query."""

    def __init__(self, docs: list[list[str]], k1=1.4, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.avg = sum(len(d) for d in docs) / max(1, len(docs))
        df = defaultdict(int)
        for d in docs:
            for w in set(d):
                df[w] += 1
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.tf = [Counter(d) for d in docs]

    def score(self, query: list[str], i: int) -> float:
        tf, dl = self.tf[i], len(self.docs[i])
        s = 0.0
        for w in query:
            if w in tf:
                f = tf[w]
                s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
        return s
