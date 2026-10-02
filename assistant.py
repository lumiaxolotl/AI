"""Core writing assistant. Runs entirely on your own computer through Ollama: no API keys, no token costs."""

import json
import os
import re
import urllib.error
import urllib.request

import websearch

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("WRITER_MODEL", "llama3.1:8b")
CONTEXT_TOKENS = int(os.environ.get("WRITER_CONTEXT", "16384"))
MAX_TOOL_ROUNDS = 6

BASE_PROMPT = """You are a personal writing assistant working with one writer on their own projects.

You help with every stage of writing: brainstorming, outlining, drafting, revising, line editing, \
proofreading, research, and fact-checking. Match the writer's voice rather than imposing your own. \
When you edit, keep their meaning and briefly explain the important changes. When you draft, write \
finished prose they can use, not a description of what you would write.

You have internet access through two tools: web_search (find pages) and fetch_page (read a page). \
Use them whenever the writer asks about anything current, factual, or checkable (names, dates, \
quotes, statistics, recent events, sources), or shares a link. After using them, cite the pages you \
relied on as Markdown links. Do not search for purely creative tasks.

Format replies in Markdown. Keep chatter short; the writing itself is the deliverable."""

MODES = {
    "chat": "",
    "draft": "Mode: DRAFT. Write new prose from the writer's notes or prompt.",
    "edit": "Mode: EDIT. Improve the text: clarity, flow, grammar, concision. Return the revised "
            "text first, then a short list of the key changes.",
    "proofread": "Mode: PROOFREAD. Fix only spelling, grammar, and punctuation. Do not change the "
                 "style. Return the corrected text, then list each correction.",
    "brainstorm": "Mode: BRAINSTORM. Give a varied list of ideas, angles, titles, or directions.",
    "research": "Mode: RESEARCH. Search the web, compare several sources, and give a well-cited "
                "summary the writer can draw on.",
    "factcheck": "Mode: FACT-CHECK. Check each factual claim against web sources. Mark each as "
                 "confirmed, wrong (with the correction), or unverifiable, and cite sources.",
}
# Modes where we search up front, so even models without tool support get web results.
AUTO_SEARCH_MODES = {"research", "factcheck"}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet. Returns titles, URLs and snippets of matching pages.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to search for"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Download a web page and return its readable text.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL of the page"}},
                "required": ["url"],
            },
        },
    },
]

URL_RE = re.compile(r"https?://[^\s<>()\"']+")


class OllamaError(Exception):
    pass


# ---------------------------------------------------------------- Ollama API

def _ollama(path: str, payload: dict | None = None, timeout: float = 600):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(OLLAMA_URL + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except ValueError:
            pass
        raise OllamaError(detail) from None
    except urllib.error.URLError:
        raise OllamaError(
            f"Can't reach Ollama at {OLLAMA_URL}. Make sure the Ollama app is installed and running."
        ) from None


def list_models() -> list[str]:
    with _ollama("/api/tags", timeout=10) as resp:
        return sorted(m["name"] for m in json.load(resp).get("models", []))


def ollama_status() -> dict:
    try:
        models = list_models()
    except OllamaError as e:
        return {"ok": False, "error": str(e), "models": []}
    return {"ok": True, "models": models}


# ---------------------------------------------------------------- prompt building

def system_prompt(profile: str) -> str:
    if profile.strip():
        return BASE_PROMPT + "\n\nAbout the writer (follow these preferences):\n" + profile.strip()
    return BASE_PROMPT


def build_user_turn(text: str, mode: str, auto_search: bool):
    """Return (message, events). Pre-reads links in the text and optionally searches up front,
    so the model has web material even if it can't call tools itself."""
    events = []
    extra = []

    for url in list(dict.fromkeys(URL_RE.findall(text)))[:3]:
        url = url.rstrip(".,;:!?")
        events.append({"type": "status", "text": f"Reading: {url}"})
        try:
            page = websearch.fetch_page(url)
            extra.append(f"Content of {page['url']} ({page['title']}):\n{page['text']}")
            events.append({"type": "source", "url": page["url"], "title": page["title"]})
        except Exception as e:
            extra.append(f"(Could not read {url}: {e})")

    if auto_search or mode in AUTO_SEARCH_MODES:
        query = " ".join(URL_RE.sub("", text).split())[:200]
        if query:
            events.append({"type": "status", "text": f"Searching: {query}"})
            try:
                results = websearch.search(query)
                extra.append("Web search results for the writer's message:\n" + _format_results(results))
                for r in results:
                    events.append({"type": "source", "url": r["url"], "title": r["title"]})
            except Exception as e:
                extra.append(f"(Web search failed: {e})")

    note = MODES.get(mode, "")
    content = f"[{note}]\n\n{text}" if note else text
    if extra:
        content += "\n\n---\nReference material gathered from the web:\n\n" + "\n\n".join(extra)
    return {"role": "user", "content": content, "display": text}, events


def _format_results(results: list[dict]) -> str:
    if not results:
        return "No results found."
    return "\n\n".join(f"[{i}] {r['title']}\n{r['url']}\n{r['snippet']}" for i, r in enumerate(results, 1))


# ---------------------------------------------------------------- tools

def run_tool(name: str, args: dict):
    """Run one tool call. Returns (result_text, events)."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    try:
        if name == "web_search":
            query = str(args.get("query", "")).strip()
            results = websearch.search(query)
            events = [{"type": "status", "text": f"Searching: {query}"}]
            events += [{"type": "source", "url": r["url"], "title": r["title"]} for r in results]
            return _format_results(results), events
        if name == "fetch_page":
            page = websearch.fetch_page(str(args.get("url", "")).strip())
            events = [{"type": "status", "text": f"Reading: {page['url']}"},
                      {"type": "source", "url": page["url"], "title": page["title"]}]
            return f"{page['title']}\n{page['url']}\n\n{page['text']}", events
        return f"Unknown tool: {name}", []
    except Exception as e:
        return f"Tool error: {e}", [{"type": "status", "text": f"{name} failed: {e}"}]


# ---------------------------------------------------------------- chat loop

UI_ONLY_KEYS = {"display", "sources"}


def _for_ollama(messages: list) -> list:
    return [{k: v for k, v in m.items() if k not in UI_ONLY_KEYS} for m in messages]


def stream_reply(messages: list, profile: str, model: str | None = None, use_tools: bool = True):
    """Stream one assistant reply, yielding UI events and appending new turns to `messages`.

    Events: {"type": "text"|"status"|"source"|"error", ...}
    """
    model = model or DEFAULT_MODEL
    system = {"role": "system", "content": system_prompt(profile)}

    for _ in range(MAX_TOOL_ROUNDS + 1):
        payload = {
            "model": model,
            "messages": [system] + _for_ollama(messages),
            "stream": True,
            "options": {"num_ctx": CONTEXT_TOKENS},
        }
        if use_tools:
            payload["tools"] = TOOLS
        try:
            resp = _ollama("/api/chat", payload)
        except OllamaError as e:
            if use_tools and "does not support tools" in str(e):
                use_tools = False  # older/smaller models: fall back to up-front web material only
                yield {"type": "status", "text": "This model can't use tools; answering without live searching."}
                continue
            if "not found" in str(e) and "model" in str(e):
                yield {"type": "error", "text": f"Model '{model}' isn't downloaded. Run: ollama pull {model}"}
            else:
                yield {"type": "error", "text": str(e)}
            return

        content, tool_calls = [], []
        yield {"type": "status", "text": "Writing…"}
        with resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    yield {"type": "error", "text": chunk["error"]}
                    return
                msg = chunk.get("message") or {}
                if msg.get("thinking"):
                    yield {"type": "status", "text": "Thinking…"}
                if msg.get("content"):
                    content.append(msg["content"])
                    yield {"type": "text", "text": msg["content"]}
                tool_calls.extend(msg.get("tool_calls") or [])

        assistant = {"role": "assistant", "content": "".join(content)}
        if tool_calls:
            assistant["tool_calls"] = tool_calls
        messages.append(assistant)

        if not tool_calls:
            yield {"type": "status", "text": ""}
            return

        for call in tool_calls:
            fn = call.get("function", {})
            result, events = run_tool(fn.get("name", ""), fn.get("arguments") or {})
            yield from events
            messages.append({"role": "tool", "tool_name": fn.get("name", ""), "content": result})

    yield {"type": "error", "text": "Stopped after too many web lookups in one reply."}
