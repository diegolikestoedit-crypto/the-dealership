# The Dealership

A competitive second-hand dealership business sim for 2–8 dealers (humans and/or AI).
Run a general store or specialise (cars, art, relics, jewelry, tech, music, collectibles). Buy from sellers, haggle, appraise, spot fakes, price your shelves against rivals, fight over
auction lots — highest net worth after the final day wins.

## Play

| Platform | How |
|---|---|
| macOS | Double-click **`dist/The Dealership.app`** (or `Play The Dealership.command`) |
| Windows | Double-click **`Play The Dealership (Windows).bat`** (needs Python 3.8+ from python.org) |
| Linux | `./start.sh` |

Requirements: Python 3.8+ (macOS ships one) and any modern browser. No installs, no internet.
The game opens in a chromeless Google Chrome/Edge app window when available, otherwise your
default browser. The `.app` shuts itself down ~45 s after you close the game window (or use
**Quit Game** on the main menu). Unsigned app: if macOS blocks it, right-click → Open once.

Saves & profile: `~/Library/Application Support/TheDealership` (macOS), `%APPDATA%\TheDealership`
(Windows), `~/.thedealership` (Linux). Solo matches autosave every morning and on quit; profile
writes are atomic.

## Multiplayer

See **HOW TO PLAY.md** for step-by-step instructions (same Wi-Fi, or a shareable online link via
`Share Online (Mac).command` / `Share Online (Windows).bat`, which uses the free localhost.run SSH tunnel).

### LAN details

1. Host: **Host Multiplayer** → lobby shows a room code and an address like `http://192.168.1.20:8642`.
2. Others: launch their own copy → **Join Multiplayer** → paste that address → pick the room or enter the code.
   (A plain browser pointed at the host address also works.)
3. Host fills empty seats with AI dealers and starts.

The host's game server is authoritative: all money, items, bids and results are computed there;
clients only send intents. Duplicate requests are de-duplicated by nonce; contested actions
(auction bids, private offers, shared staff, rival-shop purchases) are atomic. Dropped players are
put on autopilot after 20 s and regain control on reconnect (same browser session).

**Internet play** is not built in: it works over a LAN or a virtual LAN (Tailscale, ZeroTier,
Hamachi) or by forwarding TCP port 8642 on the host's router. It has only been tested on
localhost/LAN. Allow Python through the host firewall if prompted.

## Dealership types

Pick what kind of shop you run: **General Dealer** (everything), **Car Dealership**, **Art Gallery**,
**Relics & Antiquities**, **Jeweler**, **Tech Shop**, **Music Store** or **Collectibles Shop**.
Sellers only bring your trade's items and you can only display your trade's categories; off-type
items (auction estates, returns) can be wholesaled or consigned. Specialists get a buyer-trust
bonus; low-ticket shops get more foot traffic and car lots fewer, bigger deals. Buyer traffic is
split per dealer so specialists aren't starved next to general dealers.

- **Solo:** choose your type, then whether AI rivals are the same type, a random mix, or general dealers.
- **Multiplayer:** the host chooses "each dealer chooses" (players pick in the lobby; the host can
  set AI types) or forces one type for everyone (e.g. an all-cars match).

## Systems at a glance

- **103 item types / 12 categories** incl. Vehicles (Space Memorabilia unlocks at level 4), 6 conditions,
  4 edition tiers (rare "jackpot" editions), counterfeits, modified items, visual tells.
- **8 seller personalities** (desperate, shark, collector, uninformed, dishonest, impatient,
  wealthy, regular) with hidden floors, mood, patience, concessions and walk-away callbacks.
- **Negotiation**: offers/counters, accept ask, 4 persuasion tactics (pointing out flaws only works
  if you actually found them), walk away. Insulting lowballs anger sellers and cost reputation.
- **Appraisal**: inspection / authenticity scan / expert appraisal, each costing money and seller
  patience. Estimates are ranges that narrow as you learn more.
- **Selling**: you set prices; shared buyers compare every shop's display in their category.
  Verified items sell at a premium; unverified fakes can be exposed or returned for refunds.
  Wholesaler bulk sales, auction consignment, buying underpriced items from rivals.
- **Fairness**: identical starting cash; every dealer meets the same sellers in the same order.
- **Auctions**: timed lots with anti-sniping, partial catalogue info, estate bundles, consigned lots.
- **Economy**: per-category demand with mean-reverting trends, sales saturation, 14 market events
  announced a day ahead as rumors; market research / researchers give exact forecasts.
- **Business**: 8 upgrade lines, loans with daily interest, reputation.
- **Staff**: hire up to 4 of 10 specialists (Mechanic, Mentalist, Lucky Kid, Appraisal Expert, Negotiator,
  Salesperson, Security Guard, Market Analyst, Auction Scout, Marketer), 1–3 stars at $2k / $10k / $50k per week.
- **Progression** (cosmetic only): XP & levels, 6 store themes, 10 titles, 8 decorations,
  12 achievements, trophies.

Everyone starts with $25,000. Net worth = cash + inventory (80% of true value at the end; owner's estimate during play)
+ 40% of upgrade spending − loans.

## Development

```
python3 tests/test_sim.py 10        # headless matches: invariants, exploits, save/load, balance report
python3 tests/test_multiplayer.py   # live server + 3 HTTP/SSE clients: races, dedupe, disconnects
./build.sh                          # rebuild dist/The Dealership.app and dist/TheDealership.zip
```
`DEALERSHIP_TIMESCALE=10` speeds up the game clock for QA; `DEALERSHIP_DATA=/tmp/x` uses a
separate save/profile folder.

Layout: `server/` (Python stdlib: `game.py` simulation & AI, `items.py` catalog & valuation,
`content.py` data, `profile.py` progression, `server.py` HTTP + Server-Sent Events) and
`client/` (vanilla JS: `app.js` UI, `art.js` procedural vector art, `audio.js` synthesized audio).
