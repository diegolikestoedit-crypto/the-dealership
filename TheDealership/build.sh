#!/bin/bash
# Rebuilds dist/The Dealership.app and dist/TheDealership.zip from source.
set -e
cd "$(dirname "$0")"
APP="dist/The Dealership.app"
ICNS=""
[ -f "$APP/Contents/Resources/AppIcon.icns" ] && ICNS=$(mktemp) && cp "$APP/Contents/Resources/AppIcon.icns" "$ICNS"
EXE=$(mktemp); cp "$APP/Contents/MacOS/TheDealership" "$EXE"; PL=$(mktemp); cp "$APP/Contents/Info.plist" "$PL"
rm -rf dist && mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$EXE" "$APP/Contents/MacOS/TheDealership"; chmod +x "$APP/Contents/MacOS/TheDealership"
cp "$PL" "$APP/Contents/Info.plist"; [ -n "$ICNS" ] && cp "$ICNS" "$APP/Contents/Resources/AppIcon.icns"
cp -R server client "$APP/Contents/Resources/"
find dist -name __pycache__ -type d -prune -exec rm -rf {} +
STAGE=$(mktemp -d)/TheDealership; mkdir -p "$STAGE"
cp -R server client tests README.md "HOW TO PLAY.md" "PUT IT ONLINE.md" render.yaml Procfile requirements.txt start.sh "Play The Dealership.command" "Play The Dealership (Windows).bat" "Share Online (Mac).command" "Share Online (Windows).bat" "$STAGE/"
cp -R "$APP" "$STAGE/"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +
(cd "$(dirname "$STAGE")" && zip -qry - TheDealership) > dist/TheDealership.zip
# Website version: only what a host like Render needs (drag the contents of this folder into GitHub).
WEB="dist/Website Upload"
rm -rf "$WEB" && mkdir -p "$WEB"
cp -R server client render.yaml Procfile requirements.txt README.md "PUT IT ONLINE.md" "$WEB/"
find "$WEB" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "Built: $APP, dist/TheDealership.zip and $WEB"
