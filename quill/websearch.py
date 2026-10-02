"""Free internet access: DuckDuckGo search and page reading, using only the standard library."""

import gzip
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20
MAX_PAGE_CHARS = 12000


def get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9",
                 "Accept-Encoding": "gzip"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read(5_000_000)
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        charset = resp.headers.get_content_charset() or "utf-8"
        ctype = resp.headers.get_content_type()
    if not (ctype.startswith("text/") or "html" in ctype or "json" in ctype or "xml" in ctype):
        raise ValueError(f"unsupported content type: {ctype}")
    return raw.decode(charset, errors="replace")


class _DDGParser(HTMLParser):
    """Pulls result titles, links and snippets out of DuckDuckGo's HTML results page."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._field = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if tag == "a" and "result__a" in cls:
            self.results.append({"title": "", "url": _clean_ddg_link(a.get("href", "")), "snippet": ""})
            self._field = "title"
        elif "result__snippet" in cls and self.results:
            self._field = "snippet"

    def handle_endtag(self, tag):
        if tag in ("a", "td", "div"):
            self._field = None

    def handle_data(self, data):
        if self._field and self.results:
            self.results[-1][self._field] += data


def _clean_ddg_link(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]
    return href


class _BingParser(HTMLParser):
    """Backup search engine parser for Bing's results page."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._depth = 0  # >0 while inside an <li class="b_algo">
        self._field = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li" and "b_algo" in (a.get("class") or ""):
            self._depth = 1
            self.results.append({"title": "", "url": "", "snippet": ""})
        elif self._depth:
            if tag == "li":
                self._depth += 1
            elif tag == "a" and not self.results[-1]["url"] and a.get("href", "").startswith("http"):
                self.results[-1]["url"] = a["href"]
                self._field = "title"
            elif tag == "p" and not self.results[-1]["snippet"]:
                self._field = "snippet"

    def handle_endtag(self, tag):
        if tag in ("a", "p"):
            self._field = None
        elif tag == "li" and self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._field and self._depth:
            self.results[-1][self._field] += data


def _clean(results: list[dict], max_results: int) -> list[dict]:
    out = []
    for r in results:
        url = r["url"]
        if not url.startswith("http") or "duckduckgo.com/y.js" in url or "bing.com/aclick" in url:
            continue  # skip ads
        out.append({k: " ".join(v.split()) for k, v in r.items()})
        if len(out) >= max_results:
            break
    return out


def search(query: str, max_results: int = 8) -> list[dict]:
    """Search the web (DuckDuckGo, falling back to Bing). Returns [{title, url, snippet}, ...]."""
    try:
        results = _search_ddg(query, max_results)
        if results:
            return results
    except Exception:
        pass
    parser = _BingParser()
    parser.feed(get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})))
    return _clean(parser.results, max_results)


def _search_ddg(query: str, max_results: int) -> list[dict]:
    body = urllib.parse.urlencode({"q": query}).encode()
    html = get("https://html.duckduckgo.com/html/", data=body)
    parser = _DDGParser()
    parser.feed(html)
    return _clean(parser.results, max_results)


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def fetch_page(url: str) -> dict:
    """Download a web page and return {title, url, text} with the readable text only."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    html = get(url)
    ex = _TextExtractor()
    ex.feed(html)
    text = "".join(ex.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + "\n\n[page truncated]"
    return {"title": " ".join(ex.title.split()) or url, "url": url, "text": text}
