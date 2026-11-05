#!/bin/bash
# Double-click to play (macOS). Keeps a server window open; close it to quit.
cd "$(dirname "$0")"
exec python3 server/server.py "$@"
