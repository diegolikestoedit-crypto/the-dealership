# The Dealership — quick start

## What you need
- **Only the person hosting** needs this folder. Everyone else just opens a link in their browser
  (Chrome, Edge, Firefox or Safari). Nothing to install for them.
- The host needs Python 3, which comes with macOS. On Windows, install it once from python.org
  (tick "Add Python to PATH").

---

## Play solo
1. Double-click **The Dealership.app** (Mac) or **Play The Dealership (Windows).bat**.
   - Mac: if it says "unidentified developer", right-click the app → **Open** → **Open** (only the first time).
2. Main menu → **Solo vs AI Dealers**.
3. Choose **your dealership** (General Dealer, Car Dealership, Art Gallery, Relics, Jeweler, Tech, Music, Collectibles),
   how your AI rivals are set up, how many rivals and how many days.
4. Press **Open for Business**. The instructions appear and the clock waits until you press **Start Day 1**.
5. You can **Pause** any time. The game saves every morning; choose **Continue** on the main menu next time.

---

## Play with friends

### A) Friends on the same Wi-Fi
1. Host: open the game → **Host Multiplayer** → choose the rule
   (*Each dealer chooses* = everyone picks their own dealership type) → **Create Lobby**.
2. The lobby shows a **room code** and an address like `http://192.168.1.20:8642`.
3. Friends type that address into their browser → **Join Multiplayer** → pick a dealership → enter the code → **Join**.
4. Everyone picks their dealership in the lobby. The host can **+ Add AI dealer** to fill seats, then **Start Match**.

If friends can't connect: allow Python through the host's firewall when asked, and make sure everyone is on the same network.

### B) Friends anywhere (a link they paste into their browser)
1. Host: double-click **Share Online (Mac).command** (or **Share Online (Windows).bat**).
2. A window opens and, after a few seconds, prints a link ending in **.lhr.life** — or, if your network blocks
   that service, it automatically tries a backup and prints one ending in **.pinggy.link** (press Enter if it asks
   for a password; backup links last 60 minutes). Send that link to your friends.
   Keep the window open while you play — closing it stops the link.
3. The host opens the game, goes to **Host Multiplayer → Create Lobby**, and tells friends the **room code**.
4. Friends paste the link into their browser → **Join Multiplayer** → pick a dealership → enter the code → **Join**.
5. Friends can also play **solo** from that same link; their progress is saved for them on the host's computer.

The link uses the free service localhost.run. It's a new link every time you start sharing. Only share it with people you
trust, and close the window when you're done.

---

## How a day works
| Step | What you do |
|---|---|
| 🏪 **Counter** | Visitors come in one at a time — no timer. **Sellers** offer you an item; **buyers** want one of yours. Make an offer, accept, or say *No deal*, then press **Next visitor**. |
| 🔨 **Auction** | A few special lots. Bid live against everyone — or just watch. |
| 🌙 **Evening** | See your results, hire staff, buy upgrades, then **Start the next day**. |

**Tips:** the coloured bar shows what an item is probably worth. **🔍 Examine** reveals its real condition and
whether it's fake. Offer too little and people get angry and leave. 🔥 Hot categories sell for more today.

**Win:** highest net worth after the last day = cash + stock (80% of its *true* value, revealed at the end)
+ 40% of upgrade spending. Everyone starts with **$25,000**.

## Staff (👥 tab) — up to 4 of these 10
| Specialist | What they do |
|---|---|
| 🔧 Mechanic | Repairs items for a fee; takes days depending on the item and how broken it is |
| 🔮 Mentalist | Better persuasion; at 2–3★ senses the seller's lowest price |
| 🍀 Lucky Kid | Offers land more often, buyers tip, thieves fail |
| 🎓 Appraisal Expert | Free instant value of any item — but can be fooled by very rare pieces |
| 💬 Negotiator | Sellers accept lower prices |
| 🤝 Salesperson | More buyers, closes sales above budget |
| 🛡️ Security Guard | Stops shoplifters, flags dishonest sellers |
| 📊 Market Analyst | Forecasts tomorrow's market |
| 🔭 Auction Scout | Private inspection report on auction lots |
| 📣 Marketer | More sellers and buyers |

Stars cost **$2,000 / $10,000 / $50,000 per week**, paid on day 1, 8, 15… (the first week is prorated).

## Keys
`Space` next visitor · `Enter` make offer · `A` accept · `N` no deal · `E` examine · `X` ask your expert ·
`B` bid · `1`–`4` tabs · `Esc` close
