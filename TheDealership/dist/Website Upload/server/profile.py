"""Persistent, cosmetic-only progression. Nothing here affects match balance."""
import json
import os
import threading

THEMES = [  # key, name, unlock level
    ("classic", "Classic Pawn", 1), ("rustic", "Rustic Barn", 2), ("neon", "Neon Night", 3),
    ("deco", "Art Deco", 5), ("velvet", "Royal Velvet", 7), ("vault", "Cyber Vault", 10),
]
TITLES = [
    ("Rookie Dealer", 1), ("Bargain Hunter", 2), ("Haggler", 3), ("Appraiser", 4), ("Street Trader", 5),
    ("Auction Regular", 6), ("Antiques Roadster", 8), ("Market Mover", 10), ("Tycoon", 12), ("Legend of the Street", 15),
]
DECOR = [
    ("plant", "Potted Fern", 1), ("sign", "Neon 'OPEN' Sign", 2), ("cat", "Shop Cat", 4), ("aquarium", "Aquarium", 6),
    ("chandelier", "Chandelier", 8), ("trophy", "Trophy Shelf", 9), ("jukebox", "Jukebox", 11), ("statue", "Golden Statue", 14),
]
EXPANSIONS = [("space", "Space Memorabilia category", 4)]

ACHIEVEMENTS = {
    "first_match": ("Open for Business", "Finish your first match."),
    "first_win": ("Top Dealer", "Win a match."),
    "win_5": ("Dynasty", "Win 5 matches."),
    "nw_10k": ("Six Figures", "Finish with $100,000+ net worth."),
    "nw_25k": ("High Roller", "Finish with $250,000+ net worth."),
    "eagle": ("Eagle Eye", "Catch 3 counterfeits in one match."),
    "jackpot": ("Jackpot!", "Discover a rare edition with an expert appraisal."),
    "flip_1k": ("Big Flip", "Make $10,000+ profit on a single item."),
    "auction_3": ("Paddle Up", "Win 3 auction lots in one match."),
    "clean": ("Clean Record", "Finish a match with zero complaints and 10+ sales."),
    "deals_20": ("Deal Machine", "Buy 20 items in one match."),
    "rival": ("Corporate Raider", "Buy an item from a rival's shop."),
}
TROPHIES = {1: "Gold Ledger", 2: "Silver Scale", 3: "Bronze Coin"}


def xp_for_level(lv):
    return int(250 * (lv - 1) * (1 + 0.15 * (lv - 1)))


def level_of(xp):
    lv = 1
    while xp >= xp_for_level(lv + 1):
        lv += 1
    return lv


class ProfileStore:
    def __init__(self, data_dir, filename="profile.json"):
        self.dir = data_dir
        os.makedirs(self.dir, exist_ok=True)
        self.path = os.path.join(self.dir, filename)
        self.lock = threading.Lock()

    def default(self):
        return {"name": "Player", "xp": 0, "matches": 0, "wins": 0, "best_nw": 0, "achievements": [],
                "trophies": [], "selected": {"theme": "classic", "title": "Rookie Dealer", "decor": ["plant"]},
                "awarded": [], "settings": {"music": True, "sfx": True, "volume": 0.6}}

    def load(self):
        with self.lock:
            try:
                with open(self.path) as f:
                    d = json.load(f)
            except (OSError, ValueError):
                d = {}
            base = self.default()
            base.update(d)
            return base

    def save(self, d):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(d, f, indent=1)
            os.replace(tmp, self.path)  # atomic: a crash never leaves a half-written profile

    def public(self, d=None):
        d = d or self.load()
        lv = level_of(d["xp"])
        return dict(d, level=lv, next_xp=xp_for_level(lv + 1), cur_xp=xp_for_level(lv),
                    themes=[{"key": k, "name": n, "level": l, "unlocked": lv >= l} for k, n, l in THEMES],
                    titles=[{"name": n, "level": l, "unlocked": lv >= l} for n, l in TITLES],
                    decor=[{"key": k, "name": n, "level": l, "unlocked": lv >= l} for k, n, l in DECOR],
                    expansions=[{"key": k, "name": n, "level": l, "unlocked": lv >= l} for k, n, l in EXPANSIONS],
                    achievement_defs=ACHIEVEMENTS)

    def update(self, changes):
        d = self.load()
        lv = level_of(d["xp"])
        if "name" in changes:
            d["name"] = str(changes["name"]).strip()[:20] or "Player"
        sel = changes.get("selected") or {}
        if sel.get("theme") in [k for k, n, l in THEMES if lv >= l]:
            d["selected"]["theme"] = sel["theme"]
        if sel.get("title") in [n for n, l in TITLES if lv >= l]:
            d["selected"]["title"] = sel["title"]
        if isinstance(sel.get("decor"), list):
            ok = [k for k, n, l in DECOR if lv >= l]
            d["selected"]["decor"] = [x for x in sel["decor"] if x in ok][:4]
        if isinstance(changes.get("settings"), dict):
            d["settings"].update({k: v for k, v in changes["settings"].items() if k in ("music", "sfx", "volume")})
        self.save(d)
        return self.public(d)

    def award(self, match_key, row, players):
        d = self.load()
        if match_key in d["awarded"]:
            return {"profile": self.public(d), "gained": 0, "new": [], "duplicate": True}
        before = level_of(d["xp"])
        place = int(row.get("place", players))
        st = row.get("stats", {})
        nw = int(row.get("net_worth", 0))
        gained = 120 + max(0, players - place) * 60 + (150 if place == 1 else 0)
        gained += min(300, max(0, nw - 25000) // 500) + 10 * st.get("auction_wins", 0) + 15 * st.get("jackpots", 0)
        d["xp"] += gained
        d["matches"] += 1
        d["best_nw"] = max(d["best_nw"], nw)
        if place == 1:
            d["wins"] += 1
        new = []

        def ach(key, cond):
            if cond and key not in d["achievements"]:
                d["achievements"].append(key)
                new.append(ACHIEVEMENTS[key][0])
        ach("first_match", True)
        ach("first_win", place == 1)
        ach("win_5", d["wins"] >= 5)
        ach("nw_10k", nw >= 100000)
        ach("nw_25k", nw >= 250000)
        ach("eagle", st.get("fakes_caught", 0) >= 3)
        ach("jackpot", st.get("jackpots", 0) >= 1)
        ach("flip_1k", st.get("best_flip", 0) >= 10000)
        ach("auction_3", st.get("auction_wins", 0) >= 3)
        ach("clean", st.get("complaints", 0) == 0 and st.get("sold", 0) >= 10)
        ach("deals_20", st.get("deals", 0) >= 20)
        ach("rival", st.get("rival_buys", 0) >= 1)
        if place in TROPHIES and players >= 3:
            d["trophies"].append({"name": TROPHIES[place], "nw": nw, "players": players})
            d["trophies"] = d["trophies"][-30:]
        d["awarded"].append(match_key)
        d["awarded"] = d["awarded"][-200:]
        self.save(d)
        after = level_of(d["xp"])
        return {"profile": self.public(d), "gained": gained, "new": new, "levelUp": after > before, "level": after}
