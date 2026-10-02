"""Local web app for the writing assistant. Run:  python server.py  then open http://127.0.0.1:8765"""

import json
import os
import re
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import assistant

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("WRITER_DATA", ROOT / "data"))
CONVOS = DATA / "conversations"
PROFILE = DATA / "profile.txt"
SETTINGS = DATA / "settings.json"
HOST = os.environ.get("WRITER_HOST", "127.0.0.1")
PORT = int(os.environ.get("WRITER_PORT", "8765"))
ID_RE = re.compile(r"^[a-f0-9]{32}$")

_lock = threading.Lock()


# ---------------------------------------------------------------- storage

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load_convo(cid: str):
    if not ID_RE.match(cid):
        return None
    return _read_json(CONVOS / f"{cid}.json", None)


def save_convo(convo: dict):
    convo["updated"] = time.time()
    with _lock:
        _write_json(CONVOS / f"{convo['id']}.json", convo)


def list_convos():
    items = []
    for f in CONVOS.glob("*.json"):
        c = _read_json(f, None)
        if c:
            items.append({"id": c["id"], "title": c.get("title", "Untitled"), "updated": c.get("updated", 0)})
    return sorted(items, key=lambda c: c["updated"], reverse=True)


def visible_messages(convo: dict):
    out = []
    for m in convo["messages"]:
        if m["role"] == "user":
            out.append({"role": "user", "text": m.get("display", m["content"])})
        elif m["role"] == "assistant" and (m.get("content") or m.get("sources")):
            if out and out[-1]["role"] == "assistant":
                out[-1]["text"] += m["content"]
                out[-1]["sources"] += m.get("sources", [])
            else:
                out.append({"role": "assistant", "text": m["content"], "sources": m.get("sources", [])})
    return out


def settings():
    return {"model": assistant.DEFAULT_MODEL, **_read_json(SETTINGS, {})}


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "WritingAssistant/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _same_origin(self):
        # Block other websites open in your browser from talking to this local app.
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            body = (ROOT / "static" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            self._json({**assistant.ollama_status(), "settings": settings(), "modes": list(assistant.MODES)})
        elif path == "/api/conversations":
            self._json(list_convos())
        elif path.startswith("/api/conversations/"):
            convo = load_convo(path.rsplit("/", 1)[1])
            if not convo:
                return self._json({"error": "not found"}, 404)
            self._json({"id": convo["id"], "title": convo["title"], "messages": visible_messages(convo)})
        elif path == "/api/profile":
            self._json({"profile": PROFILE.read_text(encoding="utf-8") if PROFILE.exists() else ""})
        else:
            self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        if not self._same_origin():
            return self._json({"error": "forbidden"}, 403)
        if self.path.startswith("/api/conversations/"):
            cid = self.path.rsplit("/", 1)[1]
            if ID_RE.match(cid):
                (CONVOS / f"{cid}.json").unlink(missing_ok=True)
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._same_origin():
            return self._json({"error": "forbidden"}, 403)
        path = self.path.split("?")[0]
        if path == "/api/profile":
            PROFILE.parent.mkdir(parents=True, exist_ok=True)
            PROFILE.write_text(self._body().get("profile", ""), encoding="utf-8")
            return self._json({"ok": True})
        if path == "/api/settings":
            with _lock:
                _write_json(SETTINGS, {**_read_json(SETTINGS, {}), **self._body()})
            return self._json(settings())
        if path == "/api/chat":
            return self._chat(self._body())
        self._json({"error": "not found"}, 404)

    def _chat(self, req):
        text = (req.get("text") or "").strip()
        if not text:
            return self._json({"error": "empty message"}, 400)
        convo = load_convo(req.get("conversation_id") or "")
        if not convo:
            title = " ".join(text.split())[:60]
            convo = {"id": uuid.uuid4().hex, "title": title or "Untitled", "messages": [], "created": time.time()}

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def send(event):
            self.wfile.write((json.dumps(event) + "\n").encode())
            self.wfile.flush()

        start = len(convo["messages"])
        sources = {}
        try:
            send({"type": "conversation", "id": convo["id"], "title": convo["title"]})
            user_msg, events = assistant.build_user_turn(text, req.get("mode", "chat"), bool(req.get("auto_search")))
            convo["messages"].append(user_msg)
            stream = assistant.stream_reply(convo["messages"], PROFILE.read_text(encoding="utf-8")
                                            if PROFILE.exists() else "", req.get("model") or settings()["model"])
            for event in [*events, *stream]:
                if event["type"] == "source":
                    sources.setdefault(event["url"], event["title"])
                send(event)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser closed or stopped the reply; keep what we have
        except Exception as e:
            try:
                send({"type": "error", "text": f"Something went wrong: {e}"})
            except OSError:
                pass
        finally:
            new = convo["messages"][start:]
            if any(m["role"] == "assistant" and m.get("content") for m in new):
                last = next(m for m in reversed(new) if m["role"] == "assistant")
                last["sources"] = [{"url": u, "title": t} for u, t in sources.items()]
                save_convo(convo)
            elif new:
                del convo["messages"][start:]  # nothing useful came back; don't keep a dangling turn


def main():
    CONVOS.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Writing assistant running at {url}  (press Ctrl+C to stop)")
    status = assistant.ollama_status()
    if not status["ok"]:
        print("WARNING:", status["error"])
    elif settings()["model"] not in status["models"] and settings()["model"] + ":latest" not in status["models"]:
        print(f"WARNING: model '{settings()['model']}' isn't downloaded yet. Run: ollama pull {settings()['model']}")
    if os.environ.get("WRITER_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
