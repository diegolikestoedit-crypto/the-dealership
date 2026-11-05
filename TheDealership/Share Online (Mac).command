#!/bin/bash
# Hosts The Dealership and creates a public link your friends can paste into any browser.
# Tries localhost.run first; if your network blocks it, falls back to Pinggy over port 443.
# Close this window to stop sharing.
cd "$(dirname "$0")"
python3 server/server.py --no-browser &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
sleep 1.5
open "http://localhost:8642/"
echo
echo "=================================================================="
echo "  Creating your public link... (takes up to ~20 seconds)"
echo "  Look for a line with https://  and send that link to your friends."
echo "  Keep this window open while you play."
echo "=================================================================="
echo
START=$(date +%s)
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
    -R 80:localhost:8642 nokey@localhost.run
if [ $(( $(date +%s) - START )) -lt 20 ]; then
  echo
  echo "------------------------------------------------------------------"
  echo "  First service couldn't connect on this network. Trying Pinggy..."
  echo "  If it asks for a password, just press Enter."
  echo "  Your link will end in .pinggy.link  (free links last 60 minutes;"
  echo "  run this again for a new one)."
  echo "------------------------------------------------------------------"
  echo
  ssh -p 443 -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 \
      -R0:localhost:8642 a.pinggy.io
fi
echo
echo "Sharing stopped. You can close this window."
