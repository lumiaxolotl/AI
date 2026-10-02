#!/usr/bin/env bash
# Start the writing assistant on macOS / Linux.
cd "$(dirname "$0")"
MODEL="${WRITER_MODEL:-llama3.1:8b}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/"; exit 1
fi
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Get it from https://ollama.com/download, open it once, then run this again."; exit 1
fi
if ! ollama list >/dev/null 2>&1; then
  echo "Starting Ollama..."
  (ollama serve >/dev/null 2>&1 &)
  sleep 3
fi
if ! ollama show "$MODEL" >/dev/null 2>&1; then
  echo "Downloading the AI model ($MODEL). This happens once and can take a while..."
  ollama pull "$MODEL" || exit 1
fi
exec python3 server.py
