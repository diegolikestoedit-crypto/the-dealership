@echo off
REM Hosts The Dealership and creates a public link friends can paste into a browser.
REM Tries localhost.run first; if that can't connect, falls back to Pinggy over port 443.
cd /d "%~dp0"
start "The Dealership server" cmd /c "py -3 server\server.py --no-browser || python server\server.py --no-browser"
timeout /t 2 >nul
start http://localhost:8642/
echo.
echo  Creating your public link... look for a line with https:// and send it to your friends.
echo  Keep this window open while you play.
echo.
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -R 80:localhost:8642 nokey@localhost.run
echo.
echo  Trying the backup service (Pinggy). If it asks for a password, just press Enter.
echo  Your link will end in .pinggy.link (free links last 60 minutes).
echo.
ssh -p 443 -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 -R0:localhost:8642 a.pinggy.io
pause
