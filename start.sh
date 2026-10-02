#!/usr/bin/env bash
# Start Quill on macOS / Linux.
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/"; exit 1
fi
exec python3 server.py
