"""A small language model built from scratch: a word n-gram model trained on the writer's own samples.

It learns which words tend to follow which in *your* writing, then continues text in that style.
Training takes well under a second and it runs on any computer. Its output is a remix of your own
phrasing, so treat it as a source of sparks and phrases, not finished prose.
"""

import random
import re
from collections import Counter, defaultdict

TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d+(?:[.,]\d+)*|[.,!?;:—]")
END = {".", "!", "?"}
NO_SPACE_BEFORE = {".", ",", "!", "?", ";", ":"}


def tokenize(text: str) -> list[str]:
    out = []
    for para in re.split(r"\n\s*\n", text):
        toks = TOKEN_RE.findall(para.replace("’", "'"))
        if toks:
            out.extend(["<s>"] + toks)
    return out


class NGramModel:
    def __init__(self, order: int = 4):
        self.order = order
        self.counts: dict[tuple, Counter] = defaultdict(Counter)
        self.vocab: Counter = Counter()

    def train(self, text: str, weight: int = 1):
        toks = tokenize(text)
        self.vocab.update(t.lower() for t in toks)
        for i in range(1, len(toks)):
            for n in range(0, self.order):
                if i - n < 0:
                    break
                ctx = tuple(t.lower() for t in toks[i - n:i])
                self.counts[ctx][toks[i]] += weight
        return self

    @property
    def size(self) -> int:
        return sum(self.vocab.values())

    def _next(self, history: list[str], temperature: float, rng: random.Random):
        hist = [h.lower() for h in history]
        for n in range(self.order - 1, -1, -1):
            if n > len(hist):
                continue
            ctx = tuple(hist[len(hist) - n:]) if n else ()
            options = self.counts.get(ctx)
            # Prefer a long context, but only when it offers a real choice (avoids copying verbatim)
            if options and (len(options) > 1 or n <= 1 or rng.random() < 0.5):
                words = list(options)
                weights = [c ** (1 / temperature) for c in options.values()]
                return rng.choices(words, weights)[0]
        return None

    def generate(self, prompt: str = "", words: int = 80, temperature: float = 0.9, seed=None) -> str:
        rng = random.Random(seed)
        history = ["<s>"] + TOKEN_RE.findall(prompt.replace("’", "'"))
        out = []
        produced = 0
        for _ in range(words * 3):
            tok = self._next(history, temperature, rng)
            if tok is None or tok == "<s>":
                if produced >= words:
                    break
                history = ["<s>"]
                continue
            out.append(tok)
            history.append(tok)
            if tok not in NO_SPACE_BEFORE:
                produced += 1
            if produced >= words and tok in END:
                break
        return detokenize(out, capitalize_first=not prompt.strip() or prompt.rstrip()[-1:] in END)


def detokenize(toks: list[str], capitalize_first: bool = True) -> str:
    text, cap = "", capitalize_first
    for t in toks:
        word = t[:1].upper() + t[1:] if cap and t[:1].isalpha() else t
        if word == "i":
            word = "I"
        if t in NO_SPACE_BEFORE or not text:
            text += word
        else:
            text += " " + word
        if t[:1].isalpha():
            cap = False
        if t in END:
            cap = True
    return text


def continue_text(samples: str, prompt: str, words: int = 80, extra_text: str = "", variations: int = 3):
    model = NGramModel()
    model.train(samples, weight=3)
    if extra_text:
        model.train(extra_text, weight=1)
    if model.size < 30:
        return {"error": "Add some of your own writing under “My writing samples” first "
                         "(a few paragraphs at least; more is better).", "options": []}
    opts = [model.generate(prompt, words=words, seed=None) for _ in range(variations)]
    return {"options": opts, "trained_on_words": model.size}
