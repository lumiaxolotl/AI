# Quill: a personal writing assistant built from scratch

Quill runs entirely on your own computer, using only plain Python. It needs no AI model download, no
API keys, no accounts and no special hardware. If a computer can run a web browser, it can run Quill. Every
part of it is written from scratch in this repository: the spell checker, grammar rules, style checker,
summarizer, research engine and a small language model that learns your writing style.

It uses the internet for web research (DuckDuckGo, with Bing as a backup) and word lookups
(the free [Datamuse](https://www.datamuse.com/api/) and [Free Dictionary](https://dictionaryapi.dev/) services).
Your documents never leave your computer.

## What it does

| Tool | What you get |
|---|---|
| **Check** | Live spelling, grammar, punctuation and style checking with one-click fixes, a writing score, and readability stats (reading ease, grade level, sentence length, word variety, reading/speaking time). It flags wordy phrases, filler words, hedging, clichés, passive voice, adverbs, overly long sentences and repetition. |
| **Tighten** | Applies every fix it's confident about in one go, and shows each change before you accept. |
| **Summarize** | Picks out the key sentences and key phrases from your text or a selection. |
| **Research** | Searches the web, reads the top pages, and pulls out the most relevant facts with numbered sources. One click inserts them as notes. |
| **Fact-check** | Looks up each factual sentence (names, dates, numbers) and shows matching statements from the web. It flags claims where a source gives different numbers. |
| **Outline** | Researches a topic and builds an outline from the sub-topics the sources share, with notes and citations under each heading. |
| **Ideas** | Titles, angles, questions people ask, and related topics. |
| **Words** | Definitions, synonyms (click to swap one in), similar words, opposites and rhymes. |
| **My voice** | A small language model built from scratch (a word n-gram model) that trains on **your own writing samples** in under a second and continues your text in your style. It's good for sparks and phrasing ideas, not for finished prose. |

Documents save automatically. Use **My writing samples** to teach Quill your style and **My dictionary**
for names and terms it shouldn't flag.

## Setup

1. **Install Python 3.10 or newer** from <https://www.python.org/downloads/>.
   On Windows, tick **"Add python.exe to PATH"** in the installer.
2. **Download Quill**: on GitHub click **Code → Download ZIP** and unzip it, or run
   `git clone https://github.com/lumiaxolotl/AI.git`.

That's it. There's nothing else to install.

## Start it

- **Windows:** double-click `start.bat`
- **Mac / Linux:** open a terminal in the folder and run `./start.sh` (or `python3 server.py`)

Your browser opens at <http://127.0.0.1:8765>. To stop Quill, close the terminal window or press `Ctrl+C`.

## Honest limits

Quill is not a chatbot, and it can't write fluent new essays for you. Large AI models do that by training
on enormous amounts of text with powerful hardware. Instead, Quill does what can be done well
from scratch on any computer: careful checking and editing, real research with sources, and structure and
ideas to write from. Fact-check finds evidence and shows it to you; you make the final call.

## Settings (optional)

| Variable | Default | Meaning |
|---|---|---|
| `WRITER_PORT` | `8765` | Port for the web page |
| `WRITER_DATA` | `./data` | Where documents, samples and your dictionary are stored |
| `WRITER_NO_BROWSER` | unset | Set to `1` to stop the browser from opening automatically |

## Files

| Path | What it does |
|---|---|
| `server.py` | Local web server and document storage |
| `static/index.html` | The app you see in your browser |
| `quill/spelling.py` | Spell checker (edit distance + word frequencies) |
| `quill/grammar.py` | Grammar and punctuation rules |
| `quill/style.py` | Style checks and readability statistics |
| `quill/editor.py` | Combines the checks; auto-fix ("Tighten") |
| `quill/summarize.py` | TextRank summaries, key phrases, BM25 ranking |
| `quill/research.py` | Research, outline, ideas and fact-check |
| `quill/voice.py` | The "My voice" n-gram language model |
| `quill/lexicon.py` | Synonyms, definitions and rhymes |
| `quill/websearch.py` | Web search and page reading |
| `quill/data/en_words.json.gz` | English word-frequency list (MIT licence, from [pyspellchecker](https://github.com/barrust/pyspellchecker); see `en_words.LICENSE`) |
