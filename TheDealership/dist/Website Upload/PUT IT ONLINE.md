# Put The Dealership online (free) — a link that works in any browser

When you're done, you'll have a permanent link like **https://the-dealership-ab12.onrender.com** that you and your
friends open in Chrome, Opera, Safari, Edge or Firefox — on any Wi-Fi, from anywhere. Nothing to install.

It takes about 10 minutes, once. You need two free accounts: **GitHub** (stores the game files) and **Render**
(runs the game). Use Chrome for the uploading steps.

---

## Part 1 — Put the files on GitHub
1. Go to **https://github.com** and click **Sign up** (free). Verify your email.
2. Click the **+** in the top-right corner → **New repository**.
3. **Repository name:** `the-dealership`. Leave it **Public**. Click **Create repository**.
4. On the next page, click the link **"uploading an existing file"**.
5. In Finder, open **Desktop → The Dealership → TheDealership → dist → Website Upload**.
   Press **⌘A** to select everything inside it, and **drag it all into the browser window**.
6. Wait until every file is listed, then click the green **Commit changes** button.

## Part 2 — Run it on Render
1. Go to **https://render.com** → **Get Started** → **Sign in with GitHub** (allow access when asked).
2. Click **+ New** → **Web Service** → pick your **the-dealership** repository → **Connect**.
3. Fill in:
   | Setting | Value |
   |---|---|
   | Name | `the-dealership` (this becomes part of your link) |
   | Language / Runtime | **Python 3** |
   | Build Command | `echo ok` |
   | Start Command | `python3 server/server.py --no-browser` |
   | Instance Type | **Free** |
4. Click **Deploy Web Service**. Wait 1–3 minutes until it says **Live**.
5. Your link is shown near the top (ends in **.onrender.com**). Click it — the game opens. 🎉

## Part 3 — Play with friends
1. Send your friends the **.onrender.com** link.
2. One person clicks **Host Multiplayer → Create Lobby** and shares the 4-letter **room code**.
3. Everyone else clicks **Join Multiplayer**, picks a dealership, enters the code and clicks **Join**.
4. Anyone can also play **Solo vs AI Dealers** from the same link.

---

## Good to know (free plan)
- **Sleeps when unused:** after ~15 minutes with nobody playing, the free server sleeps. The next visit takes
  about a minute to wake up — just wait for the page to load.
- **Progress isn't permanent:** levels, unlocks and solo saves are kept while the server is running, but they reset
  when it restarts (after an update or a long sleep). Matches themselves are never interrupted while people are playing.
- **Updating the game later:** upload the changed files to your GitHub repository again (step 4–6 of Part 1);
  Render redeploys automatically within a couple of minutes.
- The link is public — anyone who has it can play. Only share it with people you want to play with.
