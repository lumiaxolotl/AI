# Personal Writing Assistant

A private AI writing assistant that runs **entirely on your own laptop**. No accounts, no API keys,
no subscription, no per-use (token) costs. The AI model runs locally through [Ollama](https://ollama.com),
and the assistant searches and reads the web on its own (DuckDuckGo, with Bing as a backup).

It can:

- **Draft** new writing from your notes
- **Edit** for clarity, flow and concision, and explain what changed
- **Proofread** spelling, grammar and punctuation without touching your style
- **Brainstorm** ideas, angles and titles
- **Research** a topic on the live web, with cited sources
- **Fact-check** your text against current web sources
- **Read any link** you paste into the chat

Your conversations and writing profile are saved as files in the `data/` folder on your laptop and never
leave it. The only things sent over the internet are web searches and the pages it reads.

## Setup (one time)

1. **Install Python 3** (3.10 or newer): <https://www.python.org/downloads/>
   On Windows, tick **"Add python.exe to PATH"** in the installer.
2. **Install Ollama**: <https://ollama.com/download>, then open it once.
3. **Download this project**: on GitHub click **Code → Download ZIP** and unzip it, or
   `git clone https://github.com/lumiaxolotl/AI.git`.

No other installs are needed; the app only uses Python's standard library.

## Start it

- **Windows:** double-click `start.bat`
- **Mac / Linux:** open a terminal in the folder and run `./start.sh`

The first start downloads the AI model (about 5 GB, once). Then your browser opens at
<http://127.0.0.1:8765>. To stop it, close the terminal window or press `Ctrl+C`.

## Using it

- Choose a mode under the text box (Chat, Draft, Edit, Proofread, Brainstorm, Research, Fact-check),
  paste your text or describe what you need, and press **Enter**.
- Tick **Search the web first** to make it look things up before answering, in any mode.
  Research and Fact-check always search.
- Click **My writing profile** to tell it about you: what you write, your audience, your tone,
  British or American spelling, words you avoid, a sample of your writing. It follows this in every reply.
- Past conversations are in the sidebar; **Copy** under a reply copies it as Markdown.

## Choosing a model

The default model is `llama3.1:8b`, a good balance for most laptops (8 GB+ RAM). You can download others
and switch between them from the **Model** menu in the sidebar:

| Your laptop | Try | Download command |
|---|---|---|
| 8 GB RAM, older laptop | `llama3.2:3b` (fast, lighter) | `ollama pull llama3.2:3b` |
| 16 GB RAM | `llama3.1:8b` (default) or `qwen3:8b` | `ollama pull qwen3:8b` |
| 32 GB+ RAM or a strong GPU / Apple M-series Pro/Max | `qwen3:14b`, `gemma3:27b`, `qwen3:32b` | `ollama pull qwen3:14b` |

Bigger models write better but run slower. Models that support "tools" (Llama 3.1+, Qwen 3, Mistral)
can decide on their own when to search the web. Others still get web results through
**Search the web first**, the Research and Fact-check modes, and pasted links.

## Settings (optional)

Set these environment variables before starting if you want to change defaults:

| Variable | Default | Meaning |
|---|---|---|
| `WRITER_MODEL` | `llama3.1:8b` | Model used when none is picked in the app |
| `WRITER_CONTEXT` | `16384` | How much text (tokens) the model can consider at once; raise for long documents if you have the RAM |
| `WRITER_PORT` | `8765` | Port for the web page |
| `WRITER_DATA` | `./data` | Where conversations and your profile are stored |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Where Ollama is running |

## Troubleshooting

- **"Can't reach Ollama"**: open the Ollama app (or run `ollama serve`), then refresh the page.
- **"Model isn't downloaded"**: run the `ollama pull ...` command it shows.
- **Slow replies**: switch to a smaller model, such as `llama3.2:3b`.
- **Web search returns nothing**: search engines occasionally rate-limit; wait a minute and try again.

## Files

| File | What it does |
|---|---|
| `server.py` | Local web server and conversation storage |
| `assistant.py` | Talks to the local model, writing modes, tool use |
| `websearch.py` | Free web search and page reading |
| `static/index.html` | The app you see in your browser |
| `start.sh` / `start.bat` | One-click launchers |
