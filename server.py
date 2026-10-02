"""Quill writing assistant. Run:  python server.py  then open http://127.0.0.1:8765

Everything runs on this computer with plain Python: no AI model, no API keys, no special hardware.
The internet is used only for web research and word lookups.
"""

import json
import os
import re
import threading
import time
import uuid
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from quill import editor, lexicon, research, spelling, summarize, voice
from quill import text as T

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("WRITER_DATA", ROOT / "data"))
DOCS = DATA / "documents"
SAMPLES = DATA / "samples.txt"
DICTIONARY = DATA / "dictionary.txt"
HOST = os.environ.get("WRITER_HOST", "127.0.0.1")
PORT = int(os.environ.get("WRITER_PORT", "8765"))
ID_RE = re.compile(r"^[a-f0-9]{32}$")
MAX_TEXT = 200_000

_lock = threading.Lock()


# ---------------------------------------------------------------- storage

def _read(path: Path, default=""):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def load_doc(did: str):
    if not ID_RE.match(did or ""):
        return None
    try:
        return json.loads(_read(DOCS / f"{did}.json", "null"))
    except ValueError:
        return None


def list_docs():
    out = []
    for f in DOCS.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": d["id"], "title": d.get("title") or "Untitled", "updated": d.get("updated", 0),
                    "words": len(T.words(d.get("text", "")))})
    return sorted(out, key=lambda d: d["updated"], reverse=True)


def dictionary_words():
    return sorted({w.strip() for w in _read(DICTIONARY).splitlines() if w.strip()})


def refresh_personal_words():
    """Words in your dictionary, plus any word you use at least twice in your samples, count as correct."""
    sample_words = Counter(T.tokens(_read(SAMPLES)))
    spelling.set_personal_words(dictionary_words() + [w for w, c in sample_words.items() if c >= 2])


# ---------------------------------------------------------------- API actions

def _text(req, key="text"):
    value = str(req.get(key) or "")
    if len(value) > MAX_TEXT:
        raise ValueError(f"That's too long to process at once (limit {MAX_TEXT:,} characters).")
    return value


def act_save(req):
    with _lock:
        doc = load_doc(req.get("id")) or {"id": uuid.uuid4().hex, "created": time.time()}
        doc.update(title=str(req.get("title") or "")[:200], text=_text(req), updated=time.time())
        _write(DOCS / f"{doc['id']}.json", json.dumps(doc, ensure_ascii=False))
    return {"id": doc["id"], "updated": doc["updated"]}


def act_voice(req):
    extra = ""
    topic = str(req.get("topic") or "").strip()
    if topic:
        extra = "\n\n".join(s.get("text", "") for s in research.gather(topic, pages=4))
    words = max(10, min(300, int(req.get("words") or 80)))
    return voice.continue_text(_read(SAMPLES), _text(req, "prompt")[-500:], words, extra)


def act_dictionary(req):
    word = str(req.get("add") or "").strip()
    with _lock:
        words = set(dictionary_words())
        if word:
            words.add(word)
        if req.get("remove"):
            words.discard(str(req["remove"]))
        _write(DICTIONARY, "\n".join(sorted(words)) + "\n")
    refresh_personal_words()
    return {"words": sorted(words)}


def act_samples(req):
    _write(SAMPLES, _text(req))
    refresh_personal_words()
    return {"ok": True, "words": len(T.words(_read(SAMPLES)))}


ACTIONS = {
    "/api/check": lambda r: editor.check(_text(r)),
    "/api/tighten": lambda r: editor.tighten(_text(r)),
    "/api/summarize": lambda r: summarize.summarize(_text(r), float(r.get("ratio") or 0.25)),
    "/api/research": lambda r: research.research(_text(r, "query")),
    "/api/outline": lambda r: research.outline(_text(r, "topic")),
    "/api/ideas": lambda r: research.ideas(_text(r, "topic")),
    "/api/factcheck": lambda r: research.factcheck(_text(r)),
    "/api/lookup": lambda r: lexicon.lookup(_text(r, "word")[:60]),
    "/api/voice": act_voice,
    "/api/documents": act_save,
    "/api/dictionary": act_dictionary,
    "/api/samples": act_samples,
}


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "Quill/2.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _same_origin(self):
        # Stop other websites open in your browser from using this local app.
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}",
                                            f"http://127.0.0.1:{PORT}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            body = (ROOT / "static" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/documents":
            self._json(list_docs())
        elif path.startswith("/api/documents/"):
            doc = load_doc(path.rsplit("/", 1)[1])
            self._json(doc or {"error": "not found"}, 200 if doc else 404)
        elif path == "/api/samples":
            text = _read(SAMPLES)
            self._json({"text": text, "words": len(T.words(text))})
        elif path == "/api/dictionary":
            self._json({"words": dictionary_words()})
        else:
            self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        if not self._same_origin():
            return self._json({"error": "forbidden"}, 403)
        did = self.path.rsplit("/", 1)[1]
        if self.path.startswith("/api/documents/") and ID_RE.match(did):
            (DOCS / f"{did}.json").unlink(missing_ok=True)
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._same_origin():
            return self._json({"error": "forbidden"}, 403)
        action = ACTIONS.get(self.path.split("?")[0])
        if not action:
            return self._json({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(length) or b"{}")
            self._json(action(req))
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except OSError as e:
            self._json({"error": f"Couldn't reach the internet: {e}"}, 502)
        except Exception as e:
            self._json({"error": f"Something went wrong: {e}"}, 500)


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    refresh_personal_words()
    spelling.known("warmup")  # load the word list before the first request
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Quill is running at {url}  (press Ctrl+C to stop)")
    if os.environ.get("WRITER_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
