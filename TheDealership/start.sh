#!/bin/bash
# Linux / macOS terminal launcher
cd "$(dirname "$0")"
exec python3 server/server.py "$@"
