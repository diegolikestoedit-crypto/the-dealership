"""Authoritative match simulation for The Dealership.

Everything that touches money, items or results happens here, on the server, under the
room lock. Clients only send intents (actions) and receive personalised views.
"""
import copy
import math
import random

import items as I
from content import (PERSONAS, LINES, PERSUADE, TOOLS, UPGRADES, EMPLOYEES, WAGES, MAX_EMPLOYEES, AI_HIRES, FIRST, LAST,
                     AI_DEALERS, AI_STYLES, EVENTS, EVENT_BY_KEY, ESTATE_NAMES, DEALERSHIP_TYPES, AI_TYPE_PREF)

START_CASH = 25000
PACES = {  # seconds per phase
    "quick": {"morning": 25, "shop": 110, "report": 18, "lot": 15},
    "normal": {"morning": 35, "shop": 150, "report": 25, "lot": 18},
    "relaxed": {"morning": 50, "shop": 200, "report": 35, "lot": 22},
}
MAX_LOAN = 40000
LOAN_RATE = 0.04  # per day
CONSIGN_FEE = 0.10
LIQUIDATION = 0.8  # unsold inventory counts at 80% of value toward net worth


class ActionError(Exception):
    pass


def clamp(v, a, b):
    return max(a, min(b, v))


class Match:
    SAVE_FIELDS = ["room", "settings", "players", "order", "phase", "phase_end", "clock", "day", "market",
                   "events_today", "events_tomorrow", "seller_specs", "buyer_next", "auction", "private_offer",
                   "candidates", "feed", "history", "final", "host", "paused", "seq", "report", "next_offer_at",
                   "consign_queue", "theft_rolls", "feed_seq"]

    def __init__(self, room, settings, seed=None):
        self.room = room
        self.settings = {
            "days": int(clamp(int(settings.get("days", 7)), 3, 15)),
            "pace": settings.get("pace", "normal") if settings.get("pace") in PACES else "normal",
            "max_players": int(clamp(int(settings.get("max_players", 6)), 2, 8)),
            "expansion_space": bool(settings.get("expansion_space", False)),
            "solo": bool(settings.get("solo", False)),
            "public": bool(settings.get("public", True)),
            "name": str(settings.get("name", "Dealership Match"))[:40],
            # "free": every dealer picks a type; otherwise a type key forced on everyone
            "type_rule": settings.get("type_rule") if settings.get("type_rule") in DEALERSHIP_TYPES else "free",
            # solo only: how AI rivals pick their type
            "rivals": settings.get("rivals") if settings.get("rivals") in ("same", "mix", "general") else "mix",
        }
        self.rng = random.Random(seed if seed is not None else random.randrange(1 << 30))
        self.players = {}
        self.order = []
        self.host = None
        self.phase = "lobby"
        self.phase_end = 0.0
        self.clock = 0.0
        self.day = 0
        self.market = {c: {"mult": 1.0, "target": 1.0, "prev": 1.0, "sold_today": 0} for c in self.all_cats()}
        self.events_today = []
        self.events_tomorrow = []
        self.seller_specs = {}  # dealership type -> today's shared seller list
        self.buyer_next = 0.0
        self.auction = None
        self.private_offer = None
        self.next_offer_at = None
        self.candidates = []
        self.feed = []
        self.feed_seq = 0
        self.history = []  # per-day leaderboard snapshots
        self.final = None
        self.paused = False
        self.seq = 0
        self.report = {}
        self.consign_queue = []
        self.theft_rolls = {}
        self.dirty = True

    # ------------------------------------------------------------------ utilities
    def pace(self, key):
        return PACES[self.settings["pace"]][key]

    def categories(self):
        return list(self.market.keys())

    def all_cats(self):
        return list(I.BASE_CATEGORIES) + (["space"] if self.settings["expansion_space"] else [])

    def cats_for(self, dtype):
        allc = self.all_cats()
        t = DEALERSHIP_TYPES.get(dtype, DEALERSHIP_TYPES["general"])["cats"]
        cats = allc if t is None else [c for c in t if c in allc]
        return cats or allc

    def can_trade(self, p, cat):
        return cat in p["cats"]

    def turnover(self, p):
        """Low-ticket shops see more customers; car lots fewer, bigger deals."""
        return DEALERSHIP_TYPES.get(p["dtype"], DEALERSHIP_TYPES["general"]).get("turnover", 1.0)

    def traffic(self, p):
        return self.turnover(p) * (1 + 0.1 * self.staff_skill(p, "marketer"))

    def type_name(self, p):
        return DEALERSHIP_TYPES.get(p["dtype"], DEALERSHIP_TYPES["general"])["name"]

    def mult(self, cat):
        return self.market[cat]["mult"]

    def uid(self, prefix):
        self.seq += 1
        return "%s%d" % (prefix, self.seq)

    def log(self, text, kind="info"):
        self.feed_seq += 1
        self.feed.append({"n": self.feed_seq, "t": round(self.clock, 1), "day": self.day, "text": text, "kind": kind})
        self.feed = self.feed[-60:]

    def note(self, p, text, kind="info"):
        p["note_seq"] += 1
        p["notes"].append({"n": p["note_seq"], "text": text, "kind": kind})
        p["notes"] = p["notes"][-40:]

    def say(self, cust, who, text):
        cust["lines"].append({"who": who, "text": text})
        cust["lines"] = cust["lines"][-14:]

    def line(self, group, persona=None, **kw):
        pool = LINES[group]
        if isinstance(pool, dict):
            pool = pool.get(persona) or pool["regular"]
        s = self.rng.choice(pool)
        for k, v in kw.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    def humans(self):
        return [p for p in self.players.values() if not p["is_ai"]]

    # ------------------------------------------------------------------ lobby
    def new_player(self, name, is_ai=False, style="balanced", token=None, cosmetics=None):
        pid = self.uid("p")
        cos = cosmetics or {}
        p = {
            "id": pid, "name": str(name)[:20] or "Dealer", "is_ai": is_ai, "style": style, "token": token,
            "dtype": "general", "cats": self.all_cats(),
            "connected": not is_ai, "last_seen": self.clock, "autopilot": False,
            "cash": START_CASH, "loan": 0, "rep": 50.0,
            "upgrades": {k: 0 for k in UPGRADES}, "specialty": None, "upgrade_spend": 0,
            "staff": [], "inv": {}, "queue": [], "active": None, "next_seller": 0.0, "seller_idx": 0,
            "buyer_offers": [], "notes": [], "note_seq": 0, "ready": False,
            "theme": cos.get("theme", "classic"), "title": cos.get("title", "Rookie Dealer"),
            "decor": cos.get("decor", []), "research": None, "consigned": False,
            "stats": {"bought": 0, "sold": 0, "revenue": 0, "spent": 0, "profit": 0, "fakes_caught": 0,
                      "fakes_bought": 0, "auction_wins": 0, "best_flip": 0, "best_flip_name": "",
                      "jackpots": 0, "walkouts": 0, "deals": 0, "rival_buys": 0, "complaints": 0},
            "day": self.blank_day(), "ai": {"decide_at": None, "est": {}},
            "nonces": [], "results": {},
        }
        self.players[pid] = p
        self.order.append(pid)
        self.dirty = True
        return p

    def blank_day(self):
        return {"revenue": 0, "spent": 0, "wages": 0, "interest": 0, "refunds": 0, "tools": 0,
                "bought": 0, "sold": 0, "auction": 0, "upgrades": 0, "start_nw": 0}

    def add_human(self, name, token, cosmetics=None):
        if self.phase != "lobby":
            raise ActionError("Match already started")
        if len(self.players) >= self.settings["max_players"]:
            raise ActionError("Room is full")
        p = self.new_player(name, token=token, cosmetics=cosmetics)
        if self.host is None:
            self.host = p["id"]
        self.log("%s joined the lobby." % p["name"])
        return p

    def add_bot(self):
        if self.phase != "lobby":
            raise ActionError("Match already started")
        if len(self.players) >= self.settings["max_players"]:
            raise ActionError("Room is full")
        used = {p["name"] for p in self.players.values()}
        choices = [d for d in AI_DEALERS if d["name"] not in used] or AI_DEALERS
        d = choices[0] if self.settings["solo"] else self.rng.choice(choices)
        themes = ["classic", "neon", "deco", "rustic", "velvet", "vault"]
        p = self.new_player(d["name"], is_ai=True, style=d["style"],
                            cosmetics={"theme": self.rng.choice(themes), "title": "AI Dealer"})
        p["dtype"] = AI_TYPE_PREF.get(d["style"]) or self.rng.choice(list(DEALERSHIP_TYPES))
        self.log("%s (AI) joined the lobby." % p["name"])
        return p

    def remove_player(self, pid):
        if self.phase != "lobby":
            return
        if pid in self.players:
            self.log("%s left the lobby." % self.players[pid]["name"])
            del self.players[pid]
            self.order.remove(pid)
            if self.host == pid:
                hs = self.humans()
                self.host = hs[0]["id"] if hs else None
            self.dirty = True

    def set_type(self, p, dtype):
        if self.phase != "lobby":
            raise ActionError("The match has already started")
        if dtype not in DEALERSHIP_TYPES:
            raise ActionError("Unknown dealership type")
        if self.settings["type_rule"] != "free":
            raise ActionError("The host has set one dealership type for everyone")
        p["dtype"] = dtype
        self.dirty = True

    def assign_types(self):
        rule = self.settings["type_rule"]
        host = self.players.get(self.host)
        for p in self.players.values():
            if rule != "free":
                p["dtype"] = rule
            elif p["is_ai"] and self.settings["solo"]:
                r = self.settings["rivals"]
                if r == "same" and host:
                    p["dtype"] = host["dtype"]
                elif r == "general":
                    p["dtype"] = "general"
                else:
                    p["dtype"] = self.rng.choice(list(DEALERSHIP_TYPES))
            p["cats"] = self.cats_for(p["dtype"])
        in_play = [c for c in self.all_cats() if any(c in p["cats"] for p in self.players.values())]
        self.market = {c: {"mult": 1.0, "target": 1.0, "prev": 1.0, "sold_today": 0} for c in in_play}

    def start(self):
        if self.phase != "lobby":
            raise ActionError("Already started")
        if len(self.players) < 2:
            raise ActionError("Need at least 2 dealers (add AI dealers to fill seats)")
        self.assign_types()
        self.log("The match begins! Every dealer starts with $%s." % format(START_CASH, ","), "big")
        self.begin_morning()

    # ------------------------------------------------------------------ phase flow
    def set_phase(self, phase, duration):
        self.phase = phase
        self.phase_end = self.clock + duration
        for p in self.players.values():
            p["ready"] = False
        self.dirty = True

    def begin_morning(self):
        self.day += 1
        # Market drifts toward targets; today's events kick in.
        self.events_today = self.events_tomorrow or []
        self.events_tomorrow = []
        for c, m in self.market.items():
            m["prev"] = m["mult"]
            m["target"] = 1.0 + (m["target"] - 1.0) * 0.6 + self.rng.gauss(0, 0.05)
        for ev in self.events_today:
            for c, d in ev.get("cats", {}).items():
                targets = self.categories() if c == "*" else [c]
                for t in targets:
                    if t in self.market:
                        self.market[t]["target"] += d
        for c, m in self.market.items():
            m["target"] = clamp(m["target"], 0.55, 1.9)
            m["mult"] = round(clamp(m["mult"] + (m["target"] - m["mult"]) * 0.7, 0.5, 2.0), 3)
            m["sold_today"] = 0
        # Schedule tomorrow's event (announced as a rumor today so players can plan).
        if self.day < self.settings["days"] and self.rng.random() < 0.75:
            self.events_tomorrow = [self.roll_event()]
        self.seller_specs = {}
        for dt in sorted({p["dtype"] for p in self.players.values()}):
            self.seller_specs[dt] = self.gen_seller_specs(70, self.cats_for(dt))
        for p in self.players.values():
            p["day"] = self.blank_day()
            self.payday(p)
            self.finish_repairs(p)
            p["day"]["start_nw"] = self.net_worth(p)
            p["seller_idx"] = 0
            p["consigned"] = False
            p["research"] = self.analyst_forecast(p)
            p["expert_used"] = 0
        names = ", ".join(e["name"] for e in self.events_today) or "a calm market"
        self.log("Day %d begins — %s." % (self.day, names), "big")
        first_mp = self.day == 1 and not self.settings["solo"]
        self.set_phase("morning", 180 if first_mp else self.pace("morning"))
        for p in self.players.values():
            if p["is_ai"] or p["autopilot"]:
                self.ai_morning(p)

    def roll_event(self):
        recent = {e["key"] for e in self.events_today}
        pool = [e for e in EVENTS if e["key"] not in recent]
        # only events that touch a category somebody actually trades (or generic events)
        pool = [e for e in pool if not e.get("cats") or "*" in e["cats"] or any(c in self.market for c in e["cats"])]
        ev = copy.deepcopy(self.rng.choice(pool))
        if ev["key"] == "shortage":
            c = self.rng.choice(self.categories())
            ev["cats"] = {c: 0.3}
            ev["shortage"] = c
            ev["desc"] = "%s are scarce: fewer sellers, higher prices." % I.CATEGORIES[c]["name"]
        return ev

    def event_active(self, key):
        return any(e["key"] == key for e in self.events_today)

    def begin_shop(self):
        self.set_phase("shop", self.pace("shop"))
        self.buyer_next = self.clock + 4
        self.next_offer_at = self.clock + self.rng.uniform(0.25, 0.7) * self.pace("shop")
        self.theft_rolls = {}
        for p in self.players.values():
            p["next_seller"] = self.clock + self.rng.uniform(1.0, 3.0)
            rate = 0.45 if self.event_active("recession") else 0.3
            if self.rng.random() < rate:
                self.theft_rolls[p["id"]] = self.clock + self.rng.uniform(20, self.pace("shop") - 10)
        self.log("Doors open! Customers are arriving.", "big")

    def end_shop(self):
        for p in self.players.values():
            if p["active"]:
                self.say(p["active"], "them", "Oh, you're closing? Never mind.")
            p["active"] = None
            p["queue"] = []
            for o in p["buyer_offers"]:
                self.note(p, "A buyer left when the shop closed.", "warn")
            p["buyer_offers"] = []
        self.private_offer = None
        self.begin_auction()

    def begin_auction(self):
        lots = self.gen_lots()
        self.auction = {"lots": lots, "idx": -1, "lot": None, "results": [], "gap_until": self.clock + 3}
        self.set_phase("auction", 999999)
        self.log("The auction house opens: %d lots today." % len(lots), "big")

    def end_day(self):
        days = self.settings["days"]
        for p in self.players.values():
            d = p["day"]
            if p["loan"] > 0:
                interest = int(math.ceil(p["loan"] * LOAN_RATE))
                p["loan"] += interest
                d["interest"] = interest
            self.process_complaints(p)
            if p["cash"] < 0:
                # Overdraft is converted into loan automatically (with a reputation hit).
                debt = -p["cash"]
                p["loan"] += int(debt * 1.1)
                p["cash"] = 0
                p["rep"] = clamp(p["rep"] - 3, 0, 100)
                self.note(p, "You couldn't cover expenses: $%d moved to an emergency loan." % debt, "bad")
            for e in p["inv"].values():
                e["days"] += 1
        for c, m in self.market.items():
            m["mult"] = round(clamp(m["mult"], 0.5, 2.0), 3)
        snap = {"day": self.day, "nw": {pid: self.net_worth(p) for pid, p in self.players.items()}}
        self.history.append(snap)
        self.report = {}
        for pid, p in self.players.items():
            d = p["day"]
            self.report[pid] = dict(d, end_nw=self.net_worth(p), cash=p["cash"], loan=p["loan"], rep=round(p["rep"]))
        if self.day >= days:
            self.finish()
        else:
            self.set_phase("report", self.pace("report"))

    def finish(self):
        rows = []
        for pid, p in self.players.items():
            inv_true = int(LIQUIDATION * sum(I.true_value(e["item"], self.mult(I.CATALOG[e["item"]["tpl"]]["category"])) for e in p["inv"].values()))
            book = sum(self.book_value(e) for e in p["inv"].values())
            assets = int(p["upgrade_spend"] * 0.4)
            nw = p["cash"] + inv_true + assets - p["loan"]
            rows.append({"id": pid, "name": p["name"], "is_ai": p["is_ai"], "dtype": p["dtype"], "cash": p["cash"], "inventory": inv_true,
                         "book": book, "assets": assets, "loan": p["loan"], "net_worth": nw, "rep": round(p["rep"]),
                         "stats": p["stats"], "title": p["title"], "theme": p["theme"]})
        rows.sort(key=lambda r: -r["net_worth"])
        for i, r in enumerate(rows):
            r["place"] = i + 1
        awards = []

        def award(title, key, fmt):
            best = max(rows, key=lambda r: r["stats"][key])
            if best["stats"][key] > 0:
                awards.append({"title": title, "name": best["name"], "value": fmt % best["stats"][key]})
        award("Auction Shark", "auction_wins", "%d lots won")
        award("Eagle Eye", "fakes_caught", "%d fakes caught")
        award("Best Single Flip", "best_flip", "$%d profit")
        award("Treasure Hunter", "jackpots", "%d rare editions found")
        award("Deal Machine", "deals", "%d purchases")
        self.final = {"rows": rows, "awards": awards, "days": self.settings["days"]}
        self.set_phase("final", 999999)
        self.log("The match is over! %s wins with a net worth of $%s." % (rows[0]["name"], format(rows[0]["net_worth"], ",")), "big")

    # ------------------------------------------------------------------ valuation
    def book_value(self, e):
        it = e["item"]
        cat = I.CATALOG[it["tpl"]]["category"]
        return I.estimate(it, e["know"], self.mult(cat))[1]

    def net_worth(self, p):
        inv = sum(self.book_value(e) for e in p["inv"].values()) * LIQUIDATION
        return int(p["cash"] + inv + p["upgrade_spend"] * 0.4 - p["loan"])

    def tv(self, item):
        return I.true_value(item, self.mult(I.CATALOG[item["tpl"]]["category"]))

    # ------------------------------------------------------------------ generation
    def gen_seller_specs(self, n, cats):
        """One shared list per day: every dealer meets the same sellers in the same order (fairness)."""
        specs = []
        weights = {k: v["weight"] for k, v in PERSONAS.items()}
        if self.event_active("recession"):
            weights["desperate"] *= 2
        if self.event_active("fake_ring"):
            weights["crook"] *= 2
        shortage = [e.get("shortage") for e in self.events_today if e.get("shortage")]
        fake_rate = 0.12 * (2.5 if self.event_active("fake_ring") else 1)
        full = [t for t in I.CATALOG.values() if t["category"] in cats]
        cheap_cap = max(30000, sorted(t["base"] for t in full)[len(full) // 2] * 1.5)
        for _ in range(n):
            persona = self.rng.choices(list(weights), weights=list(weights.values()))[0]
            if persona in ("wealthy", "collector"):
                pool = [t for t in full if t["base"] >= 5000] or full
                w = [t["rarity"] ** 1.5 for t in pool]
            elif persona == "crook":
                pool = [t for t in full if t["fakeable"]] or full
                w = [1.0 + t["rarity"] * 0.5 for t in pool]
            else:
                pool = [t for t in full if t["base"] <= cheap_cap] or full
                w = [1.0 / t["rarity"] for t in pool]
            w = [x * (0.35 if t["category"] in shortage else 1.0) for x, t in zip(w, pool)]
            tpl = self.rng.choices(pool, weights=w)[0]
            if persona == "crook" and tpl["fakeable"]:
                item = I.make_item(self.rng, tpl["key"], authentic=self.rng.random() > 0.7)
            else:
                item = I.make_item(self.rng, tpl["key"], fake_rate=fake_rate)
                if persona == "clueless" and item["authentic"] and self.rng.random() < 0.12:
                    item["edition"] = max(item["edition"], self.rng.choice([1, 2, 2, 3]))
            claimed = item["cond"]
            if persona == "crook":
                claimed = max(0, item["cond"] - self.rng.choice([1, 2, 2]))
            elif self.rng.random() < 0.15:
                claimed = max(0, item["cond"] - 1)
            specs.append({"persona": persona, "item": item, "claimed": claimed,
                          "name": "%s %s" % (self.rng.choice(FIRST), self.rng.choice(LAST)),
                          "look": self.gen_look(persona), "roll": self.rng.random(), "roll2": self.rng.random()})
        return specs

    def gen_look(self, persona):
        r = self.rng
        return {
            "skin": r.choice(["#f5d0b5", "#e8b48f", "#c98d63", "#a46a43", "#7a4a2a", "#5a3520"]),
            "hair": r.choice(["#1b1b1b", "#3b2a1a", "#6b4423", "#b5651d", "#d8b25a", "#9e9e9e", "#e0e0e0", "#8e2b2b"]),
            "style": r.randint(0, 5),
            "shirt": {"wealthy": r.choice(["#263238", "#3e2723", "#1a237e"]),
                      "crook": r.choice(["#212121", "#4a148c", "#37474f"]),
                      "desperate": r.choice(["#795548", "#607d8b", "#8d6e63"])}.get(
                persona, r.choice(["#e53935", "#43a047", "#1e88e5", "#fb8c00", "#8e24aa", "#00897b", "#f4511e", "#3949ab"])),
            "hat": persona in ("wealthy", "crook") and r.random() < 0.6 or r.random() < 0.15,
            "glasses": persona in ("collector", "shark") and r.random() < 0.6 or r.random() < 0.12,
            "beard": r.random() < 0.25,
            "persona": persona,
        }

    def gen_lots(self):
        lots = []
        n = 3 + (2 if self.event_active("auction_house") else 0)
        cats = self.categories()
        pool = [t for t in I.CATALOG.values() if t["category"] in cats and t["rarity"] >= 3]
        pool = pool or [t for t in I.CATALOG.values() if t["category"] in cats]
        for i in range(n):
            tpl = self.rng.choices(pool, weights=[t["rarity"] for t in pool])[0]
            item = I.make_item(self.rng, tpl["key"], fake_rate=0.1)
            if self.event_active("auction_house") and i == n - 1:
                item["edition"] = max(item["edition"], 2)
                item["authentic"] = True
            know = I.new_knowledge(item["cond"])
            know["cond"] = self.rng.random() < 0.6
            if not know["cond"]:
                know["claimed"] = max(0, item["cond"] - self.rng.choice([0, 1]))
            know["auth"] = self.rng.random() < 0.45
            know["edition"] = self.rng.random() < 0.3
            lots.append(self.make_lot([(item, know)], None))
        if self.event_active("estate"):
            bundle = []
            for _ in range(self.rng.randint(3, 5)):
                tpl = self.rng.choice([t for t in I.CATALOG.values() if t["category"] in cats])
                it = I.make_item(self.rng, tpl["key"])
                k = I.new_knowledge(it["cond"])
                bundle.append((it, k))
            lot = self.make_lot(bundle, None)
            lot["title"] = "Estate of %s (%d items)" % (self.rng.choice(ESTATE_NAMES), len(bundle))
            lots.append(lot)
        for c in self.consign_queue:
            if c["seller"] in self.players:
                lot = self.make_lot([(c["item"], c["know"])], c["seller"])
                lot["start"] = c["start"]
                lot["paid"] = c["paid"]
                lots.append(lot)
        self.consign_queue = []
        self.rng.shuffle(lots)
        return lots

    def make_lot(self, entries, seller):
        low = sum(I.estimate(it, k, self.mult(I.CATALOG[it["tpl"]]["category"]))[0] for it, k in entries)
        high = sum(I.estimate(it, k, self.mult(I.CATALOG[it["tpl"]]["category"]))[2] for it, k in entries)
        likely = sum(I.estimate(it, k, self.mult(I.CATALOG[it["tpl"]]["category"]))[1] for it, k in entries)
        title = I.CATALOG[entries[0][0]["tpl"]]["name"]
        return {"id": self.uid("lot"), "entries": [{"item": it, "know": k} for it, k in entries], "seller": seller,
                "title": title, "low": low, "high": high, "likely": likely,
                "start": I.nice(max(200, likely * 0.3)), "bid": 0, "bidder": None, "bids": [],
                "ends": None, "closed": False, "ai_caps": {}}

    # ------------------------------------------------------------------ main tick
    def tick(self, dt):
        if self.phase in ("lobby", "final") or self.paused:
            return
        self.clock += dt
        for p in self.players.values():
            if not p["is_ai"]:
                was = p["autopilot"]
                p["autopilot"] = (not p["connected"]) and (self.clock - p["last_seen"] > 20)
                if p["autopilot"] and not was:
                    self.log("%s lost connection — autopilot engaged." % p["name"], "warn")
                elif was and not p["autopilot"]:
                    self.log("%s is back in control." % p["name"])
        if self.phase == "morning":
            if self.clock >= self.phase_end or self.all_ready():
                self.begin_shop()
        elif self.phase == "shop":
            self.tick_shop(dt)
            if self.clock >= self.phase_end:
                self.end_shop()
        elif self.phase == "auction":
            self.tick_auction(dt)
        elif self.phase == "report":
            if self.clock >= self.phase_end or self.all_ready():
                self.begin_morning()
        self.dirty = True

    def all_ready(self):
        hs = [p for p in self.humans() if not p["autopilot"]]
        return bool(hs) and all(p["ready"] for p in hs)

    def tick_shop(self, dt):
        for p in self.players.values():
            self.tick_sellers(p, dt)
            if p["is_ai"] or p["autopilot"]:
                self.ai_shop(p)
            for o in list(p["buyer_offers"]):
                if self.clock >= o["expires"]:
                    p["buyer_offers"].remove(o)
                    self.note(p, "A buyer gave up waiting for your answer.", "warn")
            t = self.theft_rolls.get(p["id"])
            if t is not None and self.clock >= t:
                del self.theft_rolls[p["id"]]
                self.theft(p)
        if self.clock >= self.buyer_next:
            self.spawn_buyer()
            n = max(1.0, sum(self.traffic(p) for p in self.players.values()))
            interval = 8.5 / n * (0.65 if self.event_active("rush") else 1.0)
            if self.event_active("recession"):
                interval *= 1.25
            self.buyer_next = self.clock + interval * self.rng.uniform(0.6, 1.4)
        self.tick_private_offer()

    # ------------------------------------------------------------------ sellers / negotiation
    def staff_skill(self, p, role):
        """Star level (0-3) of the employee in this role."""
        return max([s["stars"] for s in p["staff"] if s["role"] == role] or [0])

    def tick_sellers(self, p, dt):
        specs = self.seller_specs.get(p["dtype"], [])
        if self.clock >= p["next_seller"] and len(p["queue"]) < 3 and p["seller_idx"] < len(specs):
            spec = specs[p["seller_idx"]]
            p["seller_idx"] += 1
            p["queue"].append(self.make_customer(p, spec))
            base = 15.0
            base /= 1 + 0.18 * p["upgrades"]["ads"]
            base /= 0.8 + 0.4 * p["rep"] / 100
            if self.event_active("rush"):
                base /= 1.6
            base /= self.turnover(p)
            base /= 1 + 0.15 * self.staff_skill(p, "marketer")
            p["next_seller"] = self.clock + base * self.rng.uniform(0.7, 1.3)
        for c in list(p["queue"]):
            c["wait"] -= dt
            if c["wait"] <= 0:
                p["queue"].remove(c)
                self.note(p, "%s got tired of waiting and left." % c["name"], "warn")
        if p["active"] is None and p["queue"]:
            c = p["queue"].pop(0)
            c["state"] = "active"
            p["active"] = c
            p["ai"]["decide_at"] = None
        c = p["active"]
        if c:
            c["patience"] -= dt
            if c["patience"] <= 0:
                self.customer_leaves(p, self.line("timeout"), angry=False)

    def make_customer(self, p, spec):
        item = copy.deepcopy(spec["item"])
        item["id"] = I.new_item_id()
        per = PERSONAS[spec["persona"]]
        mult = self.mult(I.CATALOG[item["tpl"]]["category"])
        tv = I.true_value(item, mult)
        nv = I.naive_value(item, spec["claimed"], mult)
        if spec["persona"] == "crook":
            perceived = nv
        else:
            perceived = tv * per["knowledge"] + nv * (1 - per["knowledge"])
        neg = self.staff_skill(p, "negotiator")
        ask = I.nice(perceived * per["greed"] * (0.95 + spec["roll"] * 0.15))
        reserve = perceived * per["reserve"] * (1 - 0.04 * neg) * (1 - 0.06 * (p["rep"] - 50) / 50)
        reserve *= 0.93 + spec["roll2"] * 0.14
        reserve = max(30, min(reserve, ask * 0.97))
        know = I.new_knowledge(spec["claimed"])
        lounge = 1 + 0.2 * p["upgrades"]["service"]
        cust = {
            "id": self.uid("c"), "persona": spec["persona"], "name": spec["name"], "look": spec["look"],
            "item": item, "know": know, "ask": ask, "reserve": reserve, "perceived": perceived,
            "mood": float(per["mood"]), "patience": per["patience"] * lounge, "patience_max": per["patience"] * lounge,
            "wait": 30 * lounge, "lines": [], "last_offer": 0, "offers": 0, "above": 0, "persuaded": [],
            "final": False, "state": "waiting", "flagged": False, "callback_used": False,
        }
        sec = self.staff_skill(p, "security")
        if spec["persona"] == "crook" and sec >= 1:
            cust["flagged"] = True
        if sec >= 2 and spec["claimed"] < item["cond"]:
            cust["lying"] = True  # guard notices the condition is worse than claimed
        cust["patience"] *= 1 + 0.08 * self.staff_skill(p, "lucky")
        self.say(cust, "them", self.line("greet", spec["persona"], item=I.CATALOG[item["tpl"]]["name"], ask=ask))
        return cust

    def customer_leaves(self, p, text, angry):
        c = p["active"]
        if not c:
            return
        self.say(c, "them", text)
        if angry:
            p["rep"] = clamp(p["rep"] - 1, 0, 100)
            p["stats"]["walkouts"] += 1
        self.note(p, "%s left%s." % (c["name"], " angry" if angry else ""), "warn" if angry else "info")
        p["last_customer"] = {"name": c["name"], "lines": c["lines"][-3:], "look": c["look"]}
        p["active"] = None

    def require_customer(self, p):
        if self.phase != "shop":
            raise ActionError("The shop is closed")
        if not p["active"]:
            raise ActionError("No customer at the counter")
        return p["active"]

    def act_offer(self, p, amount):
        c = self.require_customer(p)
        amount = int(amount)
        if amount <= 0:
            raise ActionError("Offer must be positive")
        if amount > p["cash"]:
            raise ActionError("You don't have that much cash")
        per = PERSONAS[c["persona"]]
        self.say(c, "you", "How about $%s?" % format(amount, ","))
        c["offers"] += 1
        c["patience"] -= 3
        if amount >= c["ask"]:
            return self.close_purchase(p, c["ask"] if amount > c["ask"] else amount)
        if c["last_offer"] and amount < c["last_offer"]:
            c["mood"] -= 15
            self.say(c, "them", self.line("backwards"))
        c["last_offer"] = max(c["last_offer"], amount)
        ratio = amount / max(1.0, c["reserve"])
        if ratio >= 1:
            span = max(1.0, c["ask"] - c["reserve"])
            pr = 0.4 + 0.6 * (amount - c["reserve"]) / span + (c["mood"] - 50) / 200 + 0.25 * c["above"]
            pr += [0, 0.08, 0.15, 0.25][self.staff_skill(p, "lucky")]
            c["above"] += 1
            if self.rng.random() < pr:
                return self.close_purchase(p, amount)
        else:
            c["mood"] -= 25 if ratio < 0.55 else 12 if ratio < 0.8 else 5
            if ratio < 0.55:
                self.say(c, "them", self.line("insulted"))
        if c["mood"] <= 0:
            self.customer_leaves(p, self.line("storm"), angry=True)
            return {"result": "left"}
        conc = per["concession"] * (0.5 + c["mood"] / 100)
        new_ask = c["ask"] - (c["ask"] - amount) * conc
        new_ask = I.nice(max(c["reserve"] * 1.0, new_ask))
        if new_ask >= c["ask"]:
            new_ask = c["ask"]
        c["ask"] = max(new_ask, int(math.ceil(c["reserve"])))
        if c["ask"] - c["reserve"] < max(50, c["reserve"] * 0.04):
            c["final"] = True
            self.say(c, "them", self.line("final", ask=format(c["ask"], ",")))
        else:
            self.say(c, "them", self.line("counter", c["persona"], ask=format(c["ask"], ",")))
        return {"result": "counter", "ask": c["ask"]}

    def act_accept_ask(self, p):
        c = self.require_customer(p)
        if c["ask"] > p["cash"]:
            raise ActionError("You can't afford that")
        self.say(c, "you", "Deal at $%s." % format(c["ask"], ","))
        return self.close_purchase(p, c["ask"])

    def storage_cap(self, p):
        return UPGRADES["storage"]["values"][p["upgrades"]["storage"]]

    def display_cap(self, p):
        return UPGRADES["showroom"]["values"][p["upgrades"]["showroom"]]

    def close_purchase(self, p, price):
        c = p["active"]
        price = int(price)
        if price > p["cash"]:
            raise ActionError("You can't afford that")
        if len(p["inv"]) >= self.storage_cap(p):
            raise ActionError("Your storage is full — sell or upgrade first")
        p["cash"] -= price
        p["day"]["spent"] += price
        p["day"]["bought"] += 1
        p["stats"]["bought"] += 1
        p["stats"]["spent"] += price
        p["stats"]["deals"] += 1
        it = c["item"]
        if not it["authentic"]:
            p["stats"]["fakes_bought"] += 1
        self.add_inventory(p, it, c["know"], price, "Bought from %s" % c["name"])
        self.say(c, "them", self.line("accept", c["persona"]))
        p["rep"] = clamp(p["rep"] + 0.3, 0, 100)
        self.note(p, "Bought %s for $%s." % (I.CATALOG[it["tpl"]]["name"], format(price, ",")), "good")
        p["last_customer"] = {"name": c["name"], "lines": c["lines"][-3:], "look": c["look"], "deal": price}
        p["active"] = None
        return {"result": "bought", "price": price, "item": it["id"]}

    def add_inventory(self, p, item, know, paid, source):
        p["inv"][item["id"]] = {"item": item, "know": know, "paid": int(paid), "listed": False, "price": 0,
                                "days": 0, "source": source, "day_in": self.day}
        if p["is_ai"] or p["autopilot"]:
            self.ai_list(p, p["inv"][item["id"]])

    def act_persuade(self, p, kind):
        c = self.require_customer(p)
        if kind not in PERSUADE:
            raise ActionError("Unknown tactic")
        if kind in c["persuaded"]:
            raise ActionError("You already tried that")
        c["persuaded"].append(kind)
        c["patience"] -= 3
        neg = self.staff_skill(p, "negotiator") + 2 * self.staff_skill(p, "mentalist")  # mentalist: +15% per star
        luck = 0.05 * self.staff_skill(p, "lucky")
        it, k = c["item"], c["know"]
        cat = I.CATALOG[it["tpl"]]["category"]
        ok = False
        msg = ""
        if kind == "flaws":
            self.say(c, "you", "I've had a close look at this. It's not what you say it is.")
            if k["auth"] and not it["authentic"]:
                fake_v = I.true_value(it, self.mult(cat))
                c["reserve"] = max(30, fake_v * 1.2)
                c["ask"] = I.nice(max(c["reserve"] * 1.3, fake_v * 2))
                c["mood"] -= 10
                msg = "...Fine. It's a replica. $%s." % format(c["ask"], ",")
                p["stats"]["fakes_caught"] += 1
                ok = True
            elif k["cond"] and it["cond"] > k["claimed"]:
                drop = 0.82 ** (it["cond"] - k["claimed"])
                c["reserve"] *= drop
                c["ask"] = I.nice(max(c["reserve"] * 1.05, c["ask"] * drop))
                msg = "Alright, alright — it's more worn than I said. $%s." % format(c["ask"], ",")
                ok = True
            elif k["cond"] and k.get("lab") and it["modified"]:
                c["reserve"] *= 0.8
                c["ask"] = I.nice(max(c["reserve"] * 1.05, c["ask"] * 0.8))
                msg = "Okay, yes, it's had some aftermarket parts. $%s." % format(c["ask"], ",")
                ok = True
            else:
                chance = 0.2 + 0.075 * neg + luck + (0.2 if c["persona"] == "clueless" else 0)
                if c["persona"] in ("shark", "collector"):
                    chance -= 0.15
                if self.rng.random() < chance:
                    c["reserve"] *= 0.92
                    c["ask"] = I.nice(max(c["reserve"] * 1.05, c["ask"] * 0.92))
                    msg = "Hmm... maybe you're right. $%s then." % format(c["ask"], ",")
                    ok = True
                else:
                    c["mood"] -= 22
                    msg = "Nice try. There's nothing wrong with it."
        elif kind == "cash":
            self.say(c, "you", "I can pay you in cash, right now. No waiting.")
            f = {"desperate": 0.86, "impatient": 0.9, "regular": 0.95, "clueless": 0.94}.get(c["persona"])
            if not f and self.rng.random() < 0.15 * self.staff_skill(p, "mentalist"):
                f = 0.95  # the mentalist finds the right words even for those not in a hurry
            if f:
                c["reserve"] *= f
                c["ask"] = I.nice(max(c["reserve"] * 1.04, c["ask"] * f))
                msg = "Cash now? ...That does help. $%s." % format(c["ask"], ",")
                ok = True
            else:
                c["mood"] -= 8
                msg = "I'm not in a rush for money."
        elif kind == "reputation":
            self.say(c, "you", "You won't find a more trusted dealer on this street.")
            chance = p["rep"] / 100 * (1.25 if c["persona"] in ("collector", "wealthy") else 0.9) + 0.075 * neg + luck
            if self.rng.random() < chance:
                c["reserve"] *= 0.92
                c["ask"] = I.nice(max(c["reserve"] * 1.04, c["ask"] * 0.93))
                c["mood"] += 10
                msg = "I have heard good things. $%s for you." % format(c["ask"], ",")
                ok = True
            else:
                c["mood"] -= 10
                msg = "Never heard of you."
        elif kind == "market":
            m = self.mult(cat)
            self.say(c, "you", "Honestly, nobody's buying %s right now." % I.CATEGORIES[cat]["name"].lower())
            if m < 0.95:
                f = 0.88 if c["persona"] in ("shark", "collector") else 0.9
                c["reserve"] *= f
                c["ask"] = I.nice(max(c["reserve"] * 1.04, c["ask"] * f))
                msg = "Yeah... I've seen the prices. $%s." % format(c["ask"], ",")
                ok = True
            elif m > 1.05:
                c["mood"] -= 18
                msg = "Ha! I read the news. Prices are up."
            elif self.rng.random() < 0.35 + 0.075 * neg + luck:
                c["reserve"] *= 0.95
                c["ask"] = I.nice(max(c["reserve"] * 1.04, c["ask"] * 0.95))
                msg = "Maybe. $%s then." % format(c["ask"], ",")
                ok = True
            else:
                c["mood"] -= 10
                msg = "I don't think so."
        c["ask"] = max(c["ask"], int(math.ceil(c["reserve"])))
        self.say(c, "them", msg)
        if c["mood"] <= 0:
            self.customer_leaves(p, self.line("storm"), angry=True)
            return {"result": "left"}
        return {"result": "success" if ok else "fail"}

    def act_walk(self, p):
        c = self.require_customer(p)
        per = PERSONAS[c["persona"]]
        self.say(c, "you", "Sorry, I'll pass.")
        if (not c["callback_used"] and c["last_offer"] >= c["reserve"] * 0.85
                and self.rng.random() < per["callback"] + 0.05 * self.staff_skill(p, "negotiator")):
            c["callback_used"] = True
            c["ask"] = I.nice(max(c["last_offer"] * 1.03, c["reserve"] * 0.97))
            c["reserve"] = min(c["reserve"], c["ask"])
            c["final"] = True
            c["patience"] = max(c["patience"], 10)
            self.say(c, "them", self.line("callback", ask=format(c["ask"], ",")))
            return {"result": "callback", "ask": c["ask"]}
        self.customer_leaves(p, "Your loss.", angry=False)
        return {"result": "left"}

    def tool_cost(self, p, tool):
        lab = p["upgrades"]["lab"]
        mult = [1.0, 0.7, 0.45][lab]
        tmult = [1.0, 0.75, 0.5][lab]
        return int(round(TOOLS[tool]["cost"] * mult)), TOOLS[tool]["time"] * tmult

    def act_tool(self, p, tool, target):
        if tool not in TOOLS:
            raise ActionError("Unknown tool")
        if self.phase in ("auction", "lobby", "final"):
            raise ActionError("Not available right now")
        if target == "counter":
            c = self.require_customer(p)
            it, k = c["item"], c["know"]
        else:
            e = p["inv"].get(target)
            if not e:
                raise ActionError("Item not found")
            it, k = e["item"], e["know"]
            c = None
        if (tool == "inspect" and k["cond"]) or (tool == "scan" and k["auth"]) or (tool == "expert" and k["expert"]):
            raise ActionError("Already known")
        cost, t = self.tool_cost(p, tool)
        if cost > p["cash"]:
            raise ActionError("Not enough cash")
        p["cash"] -= cost
        p["day"]["tools"] += cost
        if c:
            c["patience"] -= t
        name = I.CATALOG[it["tpl"]]["name"]
        if tool == "inspect":
            k["cond"] = True
            res = "Condition: %s" % I.COND_LABEL[it["cond"]]
        elif tool == "scan":
            k["auth"] = True
            if p["upgrades"]["lab"] >= 2:
                k["lab"] = True
            res = "Authentic" if it["authentic"] else "COUNTERFEIT"
            if not it["authentic"]:
                p["stats"]["fakes_caught"] += 1
                k["edition"] = True
            if it["modified"] and k.get("lab"):
                res += " — modified with aftermarket parts"
        else:
            k.update({"cond": True, "auth": True, "edition": True, "expert": True, "lab": True})
            if not it["authentic"]:
                p["stats"]["fakes_caught"] += 1
            res = "%s, %s, %s%s" % (I.COND_LABEL[it["cond"]], "authentic" if it["authentic"] else "counterfeit",
                                    I.EDITION_NAMES[I.CATALOG[it["tpl"]]["category"]][it["edition"]],
                                    ", modified" if it["modified"] else "")
            if it["edition"] >= 2 and it["authentic"]:
                p["stats"]["jackpots"] += 1
        if c:
            self.say(c, "you", "Mind if I take a closer look?")
        self.note(p, "%s → %s" % (name, res), "bad" if "COUNTER" in res or "counterfeit" in res else "info")
        return {"result": res, "cost": cost}

    # ------------------------------------------------------------------ inventory & selling
    def entry_status(self, e):
        k, it = e["know"], e["item"]
        if k["auth"]:
            return "verified" if it["authentic"] else "replica"
        return "unverified"

    def act_list(self, p, item_id, price):
        e = p["inv"].get(item_id)
        if not e:
            raise ActionError("Item not found")
        price = int(price)
        if price < 1 or price > 100000000:
            raise ActionError("Invalid price")
        if e.get("repair"):
            raise ActionError("That item is in the workshop until day %d" % e["repair"]["until"])
        cat = I.CATALOG[e["item"]["tpl"]]["category"]
        if not self.can_trade(p, cat):
            raise ActionError("A %s can't display %s — sell it to the wholesaler or consign it to the auction"
                              % (self.type_name(p), I.CATEGORIES[cat]["name"].lower()))
        if not e["listed"]:
            if sum(1 for x in p["inv"].values() if x["listed"]) >= self.display_cap(p):
                raise ActionError("Display is full — upgrade your showroom or unlist something")
            e["listed"] = True
        e["price"] = price
        return {"result": "listed"}

    def act_unlist(self, p, item_id):
        e = p["inv"].get(item_id)
        if not e:
            raise ActionError("Item not found")
        e["listed"] = False
        return {"result": "unlisted"}

    def act_bulk_sell(self, p, ids):
        if self.phase in ("auction", "lobby", "final"):
            raise ActionError("The wholesaler isn't available right now")
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise ActionError("Select items first")
        for i in ids:
            if i not in p["inv"]:
                raise ActionError("Item not found")
            if p["inv"][i].get("repair"):
                raise ActionError("An item you selected is still being repaired")
        total = 0
        for i in ids:
            e = p["inv"].pop(i)
            v = int(self.tv(e["item"]) * 0.45)
            total += v
            self.record_sale(p, e, v, wholesale=True)
        p["cash"] += total
        self.note(p, "Wholesaler paid $%s for %d item(s)." % (format(total, ","), len(ids)), "info")
        return {"result": "sold", "total": total}

    def record_sale(self, p, e, price, wholesale=False):
        p["day"]["revenue"] += price
        p["day"]["sold"] += 1
        p["stats"]["sold"] += 1
        p["stats"]["revenue"] += price
        profit = price - e["paid"]
        p["stats"]["profit"] += profit
        if profit > p["stats"]["best_flip"]:
            p["stats"]["best_flip"] = profit
            p["stats"]["best_flip_name"] = I.CATALOG[e["item"]["tpl"]]["name"]
        cat = I.CATALOG[e["item"]["tpl"]]["category"]
        m = self.market[cat]
        m["sold_today"] += 1
        m["mult"] = round(max(0.5, m["mult"] - (0.004 if wholesale else 0.007)), 3)

    def appeal(self, p, cat):
        a = 1 + 0.08 * p["upgrades"]["cases"] + 0.05 * self.staff_skill(p, "sales") + (p["rep"] - 50) / 250
        if p["dtype"] != "general" and len(p["cats"]) <= 3:
            a += 0.08  # buyers trust a specialist
        if p["specialty"] == cat:
            a += 0.15
        return a

    def buyer_value(self, p, e):
        it = e["item"]
        v = self.tv(it)
        st = self.entry_status(e)
        if st == "unverified" and it["authentic"] is not None:
            # undetected fakes still look genuine to an ordinary buyer
            looks = v if it["authentic"] else I.naive_value(it, it["cond"], self.mult(I.CATALOG[it["tpl"]]["category"]))
            if looks > 1500:
                looks *= 0.84 + 0.1 * p["rep"] / 100
            return looks
        if st == "verified":
            return v * 1.06
        return v

    def spawn_buyer(self):
        listings = []
        for p in self.players.values():
            for e in p["inv"].values():
                if e["listed"]:
                    listings.append((p, e))
        cats = self.categories()
        wts = []
        for c in cats:
            n = sum(1 for p, e in listings if I.CATALOG[e["item"]["tpl"]]["category"] == c)
            # each dealer draws the same foot traffic, spread over the categories it trades,
            # so a specialist isn't starved next to a dealer who sells everything
            share = sum(self.traffic(p) / len(p["cats"]) for p in self.players.values() if c in p["cats"])
            wts.append(share * self.mult(c) ** 2 * (1 + 0.15 * min(n, 6)) + 0.01)
        cat = self.rng.choices(cats, weights=wts)[0]
        kind = self.rng.choices(["bargain", "regular", "enthusiast", "collector"], weights=[30, 42, 20, 8])[0]
        wtp = {"bargain": 0.86, "regular": 1.0, "enthusiast": 1.15, "collector": 1.32}[kind]
        if cat == "antiques" and self.event_active("antique_collector") and self.rng.random() < 0.3:
            kind, wtp = "collector", 1.45
        best = None
        for p, e in listings:
            it = e["item"]
            if I.CATALOG[it["tpl"]]["category"] != cat:
                continue
            if kind == "collector" and I.CATALOG[it["tpl"]]["rarity"] < 3 and it["edition"] == 0:
                continue
            willing = self.buyer_value(p, e) * wtp * self.appeal(p, cat) * self.rng.uniform(0.9, 1.1)
            closing = 1 + 0.04 * self.staff_skill(p, "sales")
            if e["price"] > willing * 1.15:
                continue
            score = (willing - e["price"]) / willing + self.rng.uniform(0, 0.05)
            if best is None or score > best[0]:
                best = (score, p, e, willing, closing)
        if not best:
            return
        _, p, e, willing, closing = best
        it = e["item"]
        name = I.CATALOG[it["tpl"]]["name"]
        if not it["authentic"] and self.entry_status(e) == "unverified" and self.rng.random() < 0.25:
            e["know"]["auth"] = True
            e["listed"] = False
            p["rep"] = clamp(p["rep"] - 2, 0, 100)
            self.note(p, "A buyer examined your %s and declared it a FAKE. It's been pulled from display." % name, "bad")
            return
        if e["price"] <= willing * closing:
            price = e["price"]
            if self.rng.random() < 0.06 * self.staff_skill(p, "lucky"):
                price = I.nice(price * 1.1)
                self.note(p, "Lucky! The buyer loved it and paid a 10% tip.", "good")
            self.sell_to_buyer(p, e, price)
        else:
            offer = I.nice(min(willing, e["price"] * 0.98))
            if offer < e["price"] * 0.5:
                return
            if p["is_ai"] or p["autopilot"]:
                if offer >= self.ai_floor(p, e):
                    self.sell_to_buyer(p, e, offer)
            elif len(p["buyer_offers"]) < 3 and not any(o["item"] == e["item"]["id"] for o in p["buyer_offers"]):
                p["buyer_offers"].append({"id": self.uid("bo"), "item": e["item"]["id"], "offer": offer,
                                          "price": e["price"], "kind": kind, "expires": self.clock + 20,
                                          "name": "%s %s" % (self.rng.choice(FIRST), self.rng.choice(LAST)),
                                          "look": self.gen_look("regular")})

    def sell_to_buyer(self, p, e, price):
        it = e["item"]
        del p["inv"][it["id"]]
        p["cash"] += price
        self.record_sale(p, e, price)
        if self.entry_status(e) == "unverified" and not it["authentic"]:
            p.setdefault("pending_complaints", []).append({"item": it, "know": e["know"], "price": price})
        if p["day"]["sold"] <= 8:
            p["rep"] = clamp(p["rep"] + (1.0 if self.entry_status(e) == "verified" else 0.6), 0, 100)
        name = I.CATALOG[it["tpl"]]["name"]
        self.note(p, "SOLD %s for $%s (%s%s)." % (name, format(price, ","), "+" if price >= e["paid"] else "-",
                                                   format(abs(price - e["paid"]), ",")), "sale")
        if price - e["paid"] > 8000:
            self.log("%s flipped a %s for a $%s profit!" % (p["name"], name, format(price - e["paid"], ",")), "sale")

    def act_buyer_reply(self, p, offer_id, accept):
        o = next((x for x in p["buyer_offers"] if x["id"] == offer_id), None)
        if not o:
            raise ActionError("That buyer has left")
        p["buyer_offers"].remove(o)
        e = p["inv"].get(o["item"])
        if not e:
            raise ActionError("Item no longer available")
        if accept:
            self.sell_to_buyer(p, e, o["offer"])
            return {"result": "sold"}
        return {"result": "declined"}

    def process_complaints(self, p):
        sec = p["upgrades"]["security"]
        for c in p.pop("pending_complaints", []):
            if self.rng.random() < 0.5 * (1 - 0.15 * self.staff_skill(p, "lucky")):
                refund = c["price"]
                p["cash"] -= refund
                p["day"]["refunds"] += refund
                p["stats"]["revenue"] -= refund
                p["stats"]["complaints"] += 1
                p["rep"] = clamp(p["rep"] - (6 - 1.5 * sec), 0, 100)
                name = I.CATALOG[c["item"]["tpl"]]["name"]
                c["know"]["auth"] = True
                if len(p["inv"]) < self.storage_cap(p):
                    self.add_inventory(p, c["item"], c["know"], 0, "Returned (counterfeit)")
                self.note(p, "A customer returned the %s you sold — it was a counterfeit! Refunded $%s." % (name, format(refund, ",")), "bad")
                self.log("Scandal: %s sold a counterfeit %s!" % (p["name"], name), "warn")

    def theft(self, p):
        listed = [e for e in p["inv"].values() if e["listed"] and self.tv(e["item"]) < 9000]
        if not listed:
            return
        prevent = 0.45 * p["upgrades"]["security"] + 0.3 * self.staff_skill(p, "security") + 0.15 * self.staff_skill(p, "lucky")
        e = self.rng.choice(listed)
        name = I.CATALOG[e["item"]["tpl"]]["name"]
        if self.rng.random() < prevent:
            self.note(p, "Security stopped a shoplifter trying to grab your %s!" % name, "good")
            return
        del p["inv"][e["item"]["id"]]
        self.note(p, "A shoplifter stole your %s from the display!" % name, "bad")
        self.log("A shoplifter hit %s's store." % p["name"], "warn")

    def act_buy_rival(self, p, owner_id, item_id):
        if self.phase != "shop":
            raise ActionError("Rival shops are closed")
        o = self.players.get(owner_id)
        if not o or o is p:
            raise ActionError("Invalid store")
        e = o["inv"].get(item_id)
        if not e or not e["listed"]:
            raise ActionError("That item is no longer for sale")
        if e["price"] > p["cash"]:
            raise ActionError("Not enough cash")
        if len(p["inv"]) >= self.storage_cap(p):
            raise ActionError("Your storage is full")
        if not self.can_trade(p, I.CATALOG[e["item"]["tpl"]]["category"]):
            raise ActionError("That's outside what your dealership trades")
        price = e["price"]
        del o["inv"][item_id]
        o["cash"] += price
        self.record_sale(o, e, price)
        p["cash"] -= price
        p["day"]["spent"] += price
        p["stats"]["spent"] += price
        p["stats"]["rival_buys"] += 1
        know = copy.deepcopy(e["know"])
        self.add_inventory(p, e["item"], know, price, "Bought from %s" % o["name"])
        name = I.CATALOG[e["item"]["tpl"]]["name"]
        self.note(o, "%s bought your %s for $%s." % (p["name"], name, format(price, ",")), "sale")
        self.note(p, "You bought %s's %s for $%s." % (o["name"], name, format(price, ",")), "good")
        self.log("%s snapped up a %s from %s's shop." % (p["name"], name, o["name"]))
        return {"result": "bought"}

    def act_consign(self, p, item_id, start):
        if self.phase not in ("morning", "shop"):
            raise ActionError("Consignments close when the auction starts")
        if p["consigned"]:
            raise ActionError("One consignment per day")
        e = p["inv"].get(item_id)
        if not e:
            raise ActionError("Item not found")
        if e.get("repair"):
            raise ActionError("That item is still being repaired")
        start = int(start)
        if start < 100:
            raise ActionError("Starting bid too low")
        del p["inv"][item_id]
        p["consigned"] = True
        self.consign_queue.append({"seller": p["id"], "item": e["item"], "know": e["know"], "start": start, "paid": e["paid"]})
        self.note(p, "Consigned %s to tonight's auction (10%% fee)." % I.CATALOG[e["item"]["tpl"]]["name"], "info")
        return {"result": "consigned"}

    # ------------------------------------------------------------------ private offers (limited opportunity)
    def tick_private_offer(self):
        po = self.private_offer
        if po is None and self.next_offer_at is not None and self.clock >= self.next_offer_at:
            self.next_offer_at = None
            pool = [t for t in I.CATALOG.values() if t["category"] in self.market and t["rarity"] >= 3]
            tpl = self.rng.choice(pool)
            it = I.make_item(self.rng, tpl["key"], fake_rate=0.08)
            know = I.new_knowledge(it["cond"])
            know["cond"] = True
            tv = self.tv(it)
            price = I.nice(tv * self.rng.uniform(0.55, 0.9))
            self.private_offer = {"id": self.uid("po"), "item": it, "know": know, "price": price,
                                  "expires": self.clock + 18, "ai_at": {}}
            for p in self.players.values():
                if (p["is_ai"] or p["autopilot"]) and self.can_trade(p, tpl["category"]):
                    est = tv * (1 + self.rng.gauss(0, AI_STYLES[p["style"]]["noise"]))
                    if est * AI_STYLES[p["style"]]["buy"] * 1.15 > price:
                        self.private_offer["ai_at"][p["id"]] = self.clock + self.rng.uniform(4, 14)
            self.log("PRIVATE OFFER: A %s for $%s — first dealer to claim it gets it!" % (tpl["name"], format(price, ",")), "big")
        elif po:
            if self.clock >= po["expires"]:
                self.log("Nobody claimed the private offer.")
                self.private_offer = None
                return
            for pid, t in sorted(po["ai_at"].items(), key=lambda kv: kv[1]):
                if self.clock >= t:
                    try:
                        self.act_claim(self.players[pid], po["id"])
                    except ActionError:
                        po["ai_at"].pop(pid, None)
                    break

    def act_claim(self, p, offer_id):
        po = self.private_offer
        if not po or po["id"] != offer_id:
            raise ActionError("Too late — someone else claimed it")
        if po["price"] > p["cash"]:
            raise ActionError("Not enough cash")
        if len(p["inv"]) >= self.storage_cap(p):
            raise ActionError("Your storage is full")
        if not self.can_trade(p, I.CATALOG[po["item"]["tpl"]]["category"]):
            raise ActionError("That's outside what your dealership trades")
        self.private_offer = None
        p["cash"] -= po["price"]
        p["day"]["spent"] += po["price"]
        p["stats"]["spent"] += po["price"]
        self.add_inventory(p, po["item"], po["know"], po["price"], "Private offer")
        self.log("%s claimed the private offer (%s)." % (p["name"], I.CATALOG[po["item"]["tpl"]]["name"]), "big")
        return {"result": "claimed"}

    # ------------------------------------------------------------------ auction
    def tick_auction(self, dt):
        a = self.auction
        lot = a["lot"]
        if lot is None or lot["closed"]:
            if self.clock < a["gap_until"]:
                return
            a["idx"] += 1
            if a["idx"] >= len(a["lots"]):
                self.auction["lot"] = None
                self.end_day()
                return
            lot = a["lots"][a["idx"]]
            lot["ends"] = self.clock + self.pace("lot")
            lot["opened"] = self.clock
            a["lot"] = lot
            return
        for p in self.players.values():
            if p["is_ai"] or p["autopilot"]:
                self.ai_bid(p, lot)
        if self.clock >= lot["ends"]:
            self.close_lot(lot)

    def min_bid(self, lot):
        if not lot["bidder"]:
            return lot["start"]
        return lot["bid"] + max(100, I.nice(lot["bid"] * 0.06))

    def act_bid(self, p, amount):
        a = self.auction
        if self.phase != "auction" or not a or not a["lot"] or a["lot"]["closed"]:
            raise ActionError("No lot is open")
        lot = a["lot"]
        if self.clock >= lot["ends"]:
            raise ActionError("Bidding has closed")
        amount = int(amount)
        if lot["seller"] == p["id"]:
            raise ActionError("You can't bid on your own lot")
        if lot["bidder"] == p["id"]:
            raise ActionError("You're already the highest bidder")
        if amount < self.min_bid(lot):
            raise ActionError("Bid must be at least $%d" % self.min_bid(lot))
        if amount > p["cash"]:
            raise ActionError("You can't cover that bid")
        if len(p["inv"]) + len(lot["entries"]) > self.storage_cap(p):
            raise ActionError("Not enough storage space for this lot")
        if not self.lot_allowed(p, lot):
            raise ActionError("This lot is outside what your dealership trades")
        lot["bid"] = amount
        lot["bidder"] = p["id"]
        lot["bids"].append({"pid": p["id"], "name": p["name"], "amount": amount, "t": round(self.clock, 1)})
        lot["bids"] = lot["bids"][-12:]
        if lot["ends"] - self.clock < 5:
            lot["ends"] = self.clock + 5  # anti-sniping
        return {"result": "bid", "amount": amount}

    def scout_know(self, p, know):
        """Your Auction Scout's private report on a lot (only you see it)."""
        s = self.staff_skill(p, "scout")
        k = dict(know)
        if s >= 1:
            k["cond"] = True
        if s >= 2:
            k["auth"] = True
        if s >= 3:
            k["edition"] = True
        return k

    def lot_allowed(self, p, lot):
        return any(self.can_trade(p, I.CATALOG[x["item"]["tpl"]]["category"]) for x in lot["entries"])

    def close_lot(self, lot):
        lot["closed"] = True
        self.auction["gap_until"] = self.clock + 4
        seller = self.players.get(lot["seller"]) if lot["seller"] else None
        w = self.players.get(lot["bidder"]) if lot["bidder"] else None
        if w and w["cash"] >= lot["bid"] and len(w["inv"]) + len(lot["entries"]) <= self.storage_cap(w):
            w["cash"] -= lot["bid"]
            w["day"]["spent"] += lot["bid"]
            w["day"]["auction"] += lot["bid"]
            w["stats"]["spent"] += lot["bid"]
            w["stats"]["auction_wins"] += 1
            share = lot["bid"] / max(1, len(lot["entries"]))
            for ent in lot["entries"]:
                self.add_inventory(w, ent["item"], self.scout_know(w, ent["know"]), int(share), "Auction")
            if seller:
                proceeds = int(lot["bid"] * (1 - CONSIGN_FEE))
                seller["cash"] += proceeds
                self.record_sale(seller, {"item": lot["entries"][0]["item"], "paid": lot.get("paid", 0)}, proceeds)
                self.note(seller, "Your consigned %s sold for $%s (after fee)." % (lot["title"], format(proceeds, ",")), "sale")
            lot["result"] = {"winner": w["name"], "wid": w["id"], "amount": lot["bid"]}
            self.log("SOLD! %s goes to %s for $%s." % (lot["title"], w["name"], format(lot["bid"], ",")), "auction")
        else:
            lot["result"] = {"winner": None}
            if seller:
                for ent in lot["entries"]:
                    if len(seller["inv"]) < self.storage_cap(seller):
                        self.add_inventory(seller, ent["item"], ent["know"], lot.get("paid", 0), "Unsold consignment")
                self.note(seller, "Your consigned lot didn't sell and was returned.", "warn")
            self.log("No sale: %s." % lot["title"], "auction")
        self.auction["results"].append({"title": lot["title"], "result": lot["result"]})

    # ------------------------------------------------------------------ management
    def require_management(self):
        if self.phase not in ("morning", "shop", "report"):
            raise ActionError("Management is closed during the auction")

    def act_upgrade(self, p, key, specialty=None):
        self.require_management()
        if key not in UPGRADES:
            raise ActionError("Unknown upgrade")
        lvl = p["upgrades"][key]
        costs = UPGRADES[key]["costs"]
        if lvl >= len(costs):
            raise ActionError("Already at max level")
        cost = costs[lvl]
        if cost > p["cash"]:
            raise ActionError("Not enough cash")
        if key == "specialty":
            if specialty not in self.market or specialty not in p["cats"]:
                raise ActionError("Choose one of your dealership's categories")
            p["specialty"] = specialty
        p["cash"] -= cost
        p["upgrades"][key] += 1
        p["upgrade_spend"] += cost
        p["day"]["upgrades"] += cost
        self.note(p, "Upgraded %s to level %d." % (UPGRADES[key]["name"], lvl + 1), "good")
        return {"result": "upgraded"}

    def max_staff(self, p):
        return MAX_EMPLOYEES

    def week_days_left(self):
        """Days left in the current pay week, including today (weeks start on day 1, 8, 15...)."""
        d = max(1, self.day)
        return 7 - ((d - 1) % 7)

    def act_hire(self, p, role, stars):
        self.require_management()
        try:
            stars = int(stars or 0)
        except (TypeError, ValueError):
            stars = 0
        if role not in EMPLOYEES or stars not in WAGES:
            raise ActionError("Unknown employee")
        cur = next((s for s in p["staff"] if s["role"] == role), None)
        if cur and cur["stars"] >= stars:
            raise ActionError("You already have a %d-star %s" % (cur["stars"], EMPLOYEES[role]["name"]))
        if not cur and len(p["staff"]) >= MAX_EMPLOYEES:
            raise ActionError("You can only employ %d specialists — let someone go first" % MAX_EMPLOYEES)
        # pay for the rest of this week now (prorated); a promotion pays only the difference
        due = I.nice((WAGES[stars] - (WAGES[cur["stars"]] if cur else 0)) * self.week_days_left() / 7.0)
        if due > p["cash"]:
            raise ActionError("You need $%s to cover this week's wages" % format(due, ","))
        p["cash"] -= due
        p["day"]["wages"] += due
        if cur:
            cur["stars"] = stars
            self.note(p, "%s promoted to %d★ (paid $%s for the rest of the week)." % (cur["name"], stars, format(due, ",")), "good")
        else:
            name = "%s %s" % (self.rng.choice(FIRST), self.rng.choice(LAST))
            p["staff"].append({"id": self.uid("s"), "role": role, "stars": stars, "name": name, "hired": self.day})
            self.log("%s hired a %d★ %s." % (p["name"], stars, EMPLOYEES[role]["name"]))
            self.note(p, "Hired %s, %d★ %s ($%s for the rest of this week)." % (name, stars, EMPLOYEES[role]["name"], format(due, ",")), "good")
        return {"result": "hired", "paid": due}

    def act_fire(self, p, staff_id):
        self.require_management()
        s = next((x for x in p["staff"] if x["id"] == staff_id), None)
        if not s:
            raise ActionError("Not on your staff")
        if s["role"] == "mechanic" and any(e.get("repair") for e in p["inv"].values()):
            raise ActionError("Your mechanic is still working on a repair")
        p["staff"].remove(s)
        self.note(p, "%s has left your shop (wages already paid are not refunded)." % s["name"], "info")
        return {"result": "fired"}

    def payday(self, p):
        if self.day > 1 and (self.day - 1) % 7 == 0 and p["staff"]:
            wages = sum(WAGES[s["stars"]] for s in p["staff"])
            p["cash"] -= wages
            p["day"]["wages"] += wages
            self.note(p, "Payday: $%s in weekly wages." % format(wages, ","), "warn")

    # ---------------- mechanic repairs
    def repair_quote(self, p, e):
        s = self.staff_skill(p, "mechanic")
        it = e["item"]
        if not s or e.get("repair"):
            return None
        target = {1: 2, 2: 1, 3: 0}[s]
        if it["cond"] <= target:
            return None
        cur = it["cond"] if e["know"]["cond"] else e["know"]["claimed"]
        tpl = I.CATALOG[it["tpl"]]
        levels = it["cond"] - target
        base = tpl["base"] * self.mult(tpl["category"])
        # priced from what you can see (catalogue value and condition), never the hidden true value
        cost = I.nice(base * max(0.05, I.COND_MULT[target] - I.COND_MULT[cur]) * [0, 0.45, 0.35, 0.25][s] + 300)
        days = levels * (0.6 + 0.25 * tpl["rarity"]) * [0, 1.0, 0.75, 0.5][s]
        if tpl["category"] == "cars":
            days *= 1.4
        days = max(1, int(round(days)))
        return {"to": target, "toLabel": I.COND_LABEL[target], "cost": cost, "days": days}

    def act_repair(self, p, item_id):
        self.require_management()
        e = p["inv"].get(item_id)
        if not e:
            raise ActionError("Item not found")
        s = self.staff_skill(p, "mechanic")
        if not s:
            raise ActionError("Hire a mechanic first")
        if sum(1 for x in p["inv"].values() if x.get("repair")) >= s:
            raise ActionError("Your mechanic is busy (a %d★ mechanic handles %d job%s at a time)" % (s, s, "s" if s > 1 else ""))
        q = self.repair_quote(p, e)
        if not q:
            raise ActionError("Your mechanic can't improve this item any further")
        if q["cost"] > p["cash"]:
            raise ActionError("Not enough cash for the repair")
        p["cash"] -= q["cost"]
        p["day"]["tools"] += q["cost"]
        e["know"]["cond"] = True
        e["listed"] = False
        e["repair"] = {"until": self.day + q["days"], "to": q["to"]}
        self.note(p, "Mechanic started on the %s — ready on day %d." % (I.CATALOG[e["item"]["tpl"]]["name"], e["repair"]["until"]), "info")
        return {"result": "repairing", "until": e["repair"]["until"]}

    def finish_repairs(self, p):
        for e in p["inv"].values():
            r = e.get("repair")
            if r and self.day >= r["until"]:
                e["item"]["cond"] = min(e["item"]["cond"], r["to"])
                e["know"]["cond"] = True
                e["know"]["claimed"] = e["item"]["cond"]
                del e["repair"]
                self.note(p, "Your mechanic finished the %s — now %s!" % (I.CATALOG[e["item"]["tpl"]]["name"], I.COND_LABEL[e["item"]["cond"]]), "good")

    # ---------------- appraisal expert (free and instant, but fallible on rare pieces)
    def act_opinion(self, p, target):
        if self.phase in ("auction", "lobby", "final"):
            raise ActionError("Not available right now")
        s = self.staff_skill(p, "expert")
        if not s:
            raise ActionError("Hire an appraisal expert first")
        limit = [0, 4, 8, 999][s]
        if p.get("expert_used", 0) >= limit:
            raise ActionError("Your expert has given all %d opinions for today" % limit)
        if target == "counter":
            c = self.require_customer(p)
            it, k = c["item"], c["know"]
            c["patience"] -= 2
        else:
            e = p["inv"].get(target)
            if not e:
                raise ActionError("Item not found")
            it, k, c = e["item"], e["know"], None
        if k.get("expert") or k.get("opinion"):
            raise ActionError("You already have an expert view on this")
        p["expert_used"] = p.get("expert_used", 0) + 1
        tpl = I.CATALOG[it["tpl"]]
        rare = tpl["rarity"] >= 4 or it["edition"] >= 2
        fail = ([0, 0.4, 0.25, 0.1] if rare else [0, 0.06, 0.02, 0.0])[s]
        tv = self.tv(it)
        if self.rng.random() < fail:
            # a convincing but wrong read: misses the rare edition, or is taken in by a good fake
            if not it["authentic"]:
                val = I.naive_value(it, it["cond"], self.mult(tpl["category"]))
            elif it["edition"] > 0:
                val = I.true_value(dict(it, edition=0), self.mult(tpl["category"]))
            else:
                val = tv * self.rng.choice([0.6, 0.7, 1.4, 1.6])
            k["opinion"] = int(val)
            k["opinion_ok"] = False
        else:
            k["opinion"] = tv
            k["opinion_ok"] = True
            k["cond"] = True
            k["auth"] = True
            k["edition"] = True
            if not it["authentic"]:
                p["stats"]["fakes_caught"] += 1
            if it["edition"] >= 2 and it["authentic"]:
                p["stats"]["jackpots"] += 1
        if c:
            self.say(c, "you", "My expert will take a quick look, if you don't mind.")
        self.note(p, "🎓 Expert: \"I'd put the %s at about $%s.\"" % (tpl["name"], format(I.nice(k["opinion"]), ",")), "info")
        return {"result": "opinion", "value": I.nice(k["opinion"])}

    def act_loan(self, p, amount):
        self.require_management()
        amount = int(amount)
        if amount <= 0 or p["loan"] + amount > MAX_LOAN:
            raise ActionError("Loan limit is $%d" % MAX_LOAN)
        p["loan"] += amount
        p["cash"] += amount
        self.note(p, "Took a $%s loan (4%%/day interest)." % format(amount, ","), "warn")
        return {"result": "loaned"}

    def act_repay(self, p, amount):
        self.require_management()
        amount = min(int(amount), p["loan"], p["cash"])
        if amount <= 0:
            raise ActionError("Nothing to repay")
        p["loan"] -= amount
        p["cash"] -= amount
        return {"result": "repaid", "amount": amount}

    def act_research(self, p):
        self.require_management()
        cost = 800
        if p["cash"] < cost:
            raise ActionError("Not enough cash")
        if p["research"] and p["research"].get("exact"):
            raise ActionError("You already have today's full report")
        p["cash"] -= cost
        p["day"]["tools"] += cost
        p["research"] = self.forecast(exact=True)
        return {"result": "researched"}

    def forecast(self, exact, noise=0.0):
        cats = {}
        for c, m in self.market.items():
            t = 1.0 + (m["target"] - 1.0) * 0.6
            for ev in self.events_tomorrow:
                for k, d in ev.get("cats", {}).items():
                    if k == c or k == "*":
                        t += d
            t = clamp(m["mult"] + (t - m["mult"]) * 0.7, 0.5, 2.0)
            if not exact:
                t += self.rng.gauss(0, noise)
            cats[c] = round(t, 2)
        return {"exact": exact, "tomorrow": cats, "events": [e["name"] for e in self.events_tomorrow]}

    def analyst_forecast(self, p):
        s = self.staff_skill(p, "analyst")
        if not s:
            return None
        f = self.forecast(exact=s >= 2, noise=0.12)
        if s < 3:
            f["events"] = []
        return f

    def act_ready(self, p):
        p["ready"] = True
        return {"result": "ready"}

    # ------------------------------------------------------------------ AI
    def ai_style(self, p):
        return AI_STYLES.get(p["style"], AI_STYLES["balanced"])

    def ai_estimate(self, p, it, know):
        key = it["id"]
        if key in p["ai"]["est"]:
            return p["ai"]["est"][key]
        st = self.ai_style(p)
        mult = self.mult(I.CATALOG[it["tpl"]]["category"])
        if know["auth"] or know.get("expert"):
            base = I.true_value(it, mult)
        elif it["authentic"]:
            base = I.true_value(it, mult) if know["edition"] else I.true_value(dict(it, edition=0), mult)
            if not know["edition"] and any(h in I.TELL_RARE for h in it["hints"]):
                base *= 1.15  # a sharp-eyed AI notices the same visible clue a player would
        else:
            base = I.naive_value(it, it["cond"], mult)  # fooled
        est = base * (1 + self.rng.gauss(0, st["noise"]))
        if st["fav"] and I.CATALOG[it["tpl"]]["category"] == st["fav"]:
            est *= 1.08
        p["ai"]["est"][key] = max(50, est)
        if len(p["ai"]["est"]) > 400:
            p["ai"]["est"] = dict(list(p["ai"]["est"].items())[-200:])
        return p["ai"]["est"][key]

    def ai_shop(self, p):
        c = p["active"]
        st = self.ai_style(p)
        if c:
            if p["ai"]["decide_at"] is None:
                p["ai"]["decide_at"] = self.clock + self.rng.uniform(6, 14) / (1 + 0.1 * self.staff_skill(p, "expert"))
            elif self.clock >= p["ai"]["decide_at"]:
                p["ai"]["decide_at"] = None
                it, k = c["item"], c["know"]
                if not k["cond"]:
                    cost, _ = self.tool_cost(p, "inspect")
                    p["cash"] -= cost
                    p["day"]["tools"] += cost
                    k["cond"] = True
                nv = I.naive_value(it, k["claimed"], self.mult(I.CATALOG[it["tpl"]]["category"]))
                if I.CATALOG[it["tpl"]]["fakeable"] and nv >= st["scan"] and not k["auth"]:
                    cost, _ = self.tool_cost(p, "scan")
                    if p["cash"] > cost * 4:
                        p["cash"] -= cost
                        p["day"]["tools"] += cost
                        k["auth"] = True
                        if not it["authentic"]:
                            p["stats"]["fakes_caught"] += 1
                est = self.ai_estimate(p, it, k)
                cap = est * st["buy"]
                if not it["authentic"] and k["auth"]:
                    cap = I.true_value(it, self.mult(I.CATALOG[it["tpl"]]["category"])) * 0.6
                reserve = c["reserve"]
                room = len(p["inv"]) < self.storage_cap(p)
                if reserve <= cap and room:
                    price = I.nice(reserve + (min(c["ask"], cap) - reserve) * self.rng.uniform(0.05, 0.35))
                    price = max(price, int(math.ceil(reserve)))
                    if price <= p["cash"] * 0.85:
                        self.close_purchase(p, price)
                        return
                if not room:
                    self.ai_clear_storage(p)
                self.customer_leaves(p, "Alright, I'll try elsewhere.", angry=False)
        # Fill empty display slots, reprice stale listings
        free = self.display_cap(p) - sum(1 for e in p["inv"].values() if e["listed"])
        if free > 0:
            for e in sorted(p["inv"].values(), key=lambda x: -x["paid"]):
                if not e["listed"] and free > 0:
                    self.ai_list(p, e)
                    free -= 1
        # Occasionally snipe underpriced rival listings
        if self.rng.random() < 0.004 and len(p["inv"]) < self.storage_cap(p) - 1:
            for o in self.players.values():
                if o is p:
                    continue
                for e in list(o["inv"].values()):
                    if e["listed"] and e["price"] < p["cash"] * 0.5 and self.can_trade(p, I.CATALOG[e["item"]["tpl"]]["category"]):
                        est = self.ai_estimate(p, e["item"], e["know"])
                        if e["price"] < est * 0.55:
                            try:
                                self.act_buy_rival(p, o["id"], e["item"]["id"])
                            except ActionError:
                                pass
                            return

    def ai_list(self, p, e):
        st = self.ai_style(p)
        if not self.can_trade(p, I.CATALOG[e["item"]["tpl"]]["category"]):
            return
        if not e["listed"] and sum(1 for x in p["inv"].values() if x["listed"]) >= self.display_cap(p):
            return
        est = self.ai_estimate(p, e["item"], e["know"])
        if self.entry_status(e) == "replica":
            est = self.tv(e["item"])
        e["listed"] = True
        decay = 0.93 ** e["days"]
        e["price"] = I.nice(max(est * st["markup"] * decay, e["paid"] * 1.03 if e["days"] < 3 else est * 0.8))

    def ai_floor(self, p, e):
        est = self.ai_estimate(p, e["item"], e["know"])
        return max(e["paid"] * 1.06, est * 0.88 * (0.95 ** e["days"]))

    def ai_clear_storage(self, p):
        stored = [e for e in p["inv"].values() if not e["listed"]]
        if stored:
            e = min(stored, key=lambda x: self.ai_estimate(p, x["item"], x["know"]))
            self.act_bulk_sell(p, [e["item"]["id"]])

    def ai_morning(self, p):
        st = self.ai_style(p)
        days_left = self.settings["days"] - self.day
        if p["loan"] and p["cash"] > p["loan"] + 15000:
            self.act_repay(p, p["loan"])
        if p["style"] == "roller" and self.day == 1 and not p["loan"]:
            self.act_loan(p, 15000)
        off = [e["item"]["id"] for e in p["inv"].values() if not self.can_trade(p, I.CATALOG[e["item"]["tpl"]]["category"])]
        if off:
            self.act_bulk_sell(p, off)
        if days_left >= 2:
            for key in st["upgrades"]:
                lvl = p["upgrades"][key]
                costs = UPGRADES[key]["costs"]
                if lvl < len(costs) and p["cash"] > costs[lvl] * 2.6:
                    spec = st["fav"] if st["fav"] in p["cats"] else self.rng.choice(p["cats"])
                    try:
                        self.act_upgrade(p, key, specialty=spec if key == "specialty" else None)
                    except ActionError:
                        pass
                    break
            for role in AI_HIRES.get(p["style"], ["sales"]):
                cur = self.staff_skill(p, role)
                want = 2 if p["cash"] > 90000 and days_left >= 3 else 1
                if cur < want and p["cash"] > WAGES[want] * 3 and len(p["staff"]) < 3:
                    try:
                        self.act_hire(p, role, want)
                    except ActionError:
                        pass
                    break
        if days_left <= 1 and p["loan"] and p["cash"] > 0:
            self.act_repay(p, p["loan"])
        for e in p["inv"].values():
            if e["listed"]:
                self.ai_list(p, e)

    def ai_bid(self, p, lot):
        if lot["bidder"] == p["id"] or lot["seller"] == p["id"] or not self.lot_allowed(p, lot):
            return
        st = self.ai_style(p)
        if p["id"] not in lot["ai_caps"]:
            val = 0
            for ent in lot["entries"]:
                it, k = ent["item"], ent["know"]
                mult = self.mult(I.CATALOG[it["tpl"]]["category"])
                lo, likely, hi = I.estimate(it, k, mult)
                # AI only sees the public catalogue information, like everyone else
                guess = (0.7 * likely + 0.3 * (lo + hi) / 2) * (0.8 + 0.25 * st["risk"])
                val += guess * (1 + self.rng.gauss(0, st["noise"]))
            cap = val * st["buy"] * (0.85 + 0.3 * st["risk"])
            lot["ai_caps"][p["id"]] = max(0, min(cap, p["cash"] * (0.35 + 0.3 * st["risk"])))
        cap = lot["ai_caps"][p["id"]]
        nxt = self.min_bid(lot)
        if nxt > cap:
            return
        remain = lot["ends"] - self.clock
        chance = 0.03 if remain > 6 else 0.12
        if self.rng.random() < chance:
            try:
                self.act_bid(p, nxt)
            except ActionError:
                pass

    # ------------------------------------------------------------------ dispatch
    def handle(self, pid, action, args, nonce=None):
        p = self.players.get(pid)
        if not p:
            raise ActionError("Unknown player")
        if nonce:
            if nonce in p["results"]:
                return p["results"][nonce]  # duplicate request: replay, never re-apply
        if self.phase == "final" and action not in ("noop",):
            raise ActionError("The match is over")
        if p["autopilot"]:
            p["autopilot"] = False
        fn = {
            "offer": lambda: self.act_offer(p, args.get("amount", 0)),
            "accept_ask": lambda: self.act_accept_ask(p),
            "persuade": lambda: self.act_persuade(p, args.get("kind")),
            "walk": lambda: self.act_walk(p),
            "tool": lambda: self.act_tool(p, args.get("tool"), args.get("target", "counter")),
            "list": lambda: self.act_list(p, args.get("item"), args.get("price", 0)),
            "unlist": lambda: self.act_unlist(p, args.get("item")),
            "bulk_sell": lambda: self.act_bulk_sell(p, args.get("items") or []),
            "buyer_reply": lambda: self.act_buyer_reply(p, args.get("offer"), bool(args.get("accept"))),
            "buy_rival": lambda: self.act_buy_rival(p, args.get("owner"), args.get("item")),
            "consign": lambda: self.act_consign(p, args.get("item"), args.get("start", 0)),
            "claim": lambda: self.act_claim(p, args.get("offer")),
            "bid": lambda: self.act_bid(p, args.get("amount", 0)),
            "upgrade": lambda: self.act_upgrade(p, args.get("key"), args.get("specialty")),
            "hire": lambda: self.act_hire(p, args.get("role"), args.get("stars")),
            "repair": lambda: self.act_repair(p, args.get("item")),
            "opinion": lambda: self.act_opinion(p, args.get("target", "counter")),
            "fire": lambda: self.act_fire(p, args.get("staff")),
            "loan": lambda: self.act_loan(p, args.get("amount", 0)),
            "repay": lambda: self.act_repay(p, args.get("amount", 0)),
            "research": lambda: self.act_research(p),
            "ready": lambda: self.act_ready(p),
        }.get(action)
        if not fn:
            raise ActionError("Unknown action")
        try:
            res = fn()
        except (TypeError, ValueError):
            raise ActionError("Invalid input")
        self.dirty = True
        if nonce:
            p["results"][nonce] = res
            p["nonces"].append(nonce)
            if len(p["nonces"]) > 200:
                old = p["nonces"].pop(0)
                p["results"].pop(old, None)
        return res

    # ------------------------------------------------------------------ views
    def item_view(self, it, know, mult=None):
        tpl = I.CATALOG[it["tpl"]]
        mult = self.mult(tpl["category"]) if mult is None else mult
        lo, li, hi = I.estimate(it, know, mult)
        status = ("verified" if it["authentic"] else "replica") if know["auth"] else "unverified"
        v = {
            "id": it["id"], "name": tpl["name"], "kind": tpl["kind"], "cat": tpl["category"],
            "catName": I.CATEGORIES[tpl["category"]]["name"], "variant": it["variant"], "rarity": tpl["rarity"],
            "base": tpl["base"], "cond": I.COND_LABEL[it["cond"]] if know["cond"] else None,
            "claimed": I.COND_LABEL[know["claimed"]], "condIdx": it["cond"] if know["cond"] else know["claimed"],
            "status": status, "edition": I.EDITION_NAMES[tpl["category"]][it["edition"]] if know["edition"] else None,
            "editionIdx": it["edition"] if know["edition"] else 0, "expert": know.get("expert", False),
            "modified": it["modified"] if know.get("lab") else None,
            "low": lo, "likely": li, "high": hi, "hints": it["hints"], "fakeable": tpl["fakeable"],
            "opinion": I.nice(know["opinion"]) if know.get("opinion") and not know.get("expert") else None,
        }
        return v

    def customer_view(self, p, c):
        neg = self.staff_skill(p, "negotiator")
        ment = self.staff_skill(p, "mentalist")
        floor = None
        if ment >= 2:  # the mentalist senses how low they'd go
            w = 0.15 if ment == 2 else 0.06
            floor = [I.nice(c["reserve"] * (1 - w)), I.nice(c["reserve"] * (1 + w))]
        per = PERSONAS[c["persona"]]
        vibe = per["vibe"]
        if c["persona"] == "crook" and not c["flagged"]:
            vibe = "Friendly"
        return {
            "id": c["id"], "name": c["name"], "look": c["look"], "item": self.item_view(c["item"], c["know"]),
            "ask": c["ask"], "mood": round(c["mood"]), "moodExact": neg > 0 or ment > 0, "patience": max(0, round(c["patience"], 1)),
            "patienceMax": c["patience_max"], "lines": c["lines"], "lastOffer": c["last_offer"],
            "persuaded": c["persuaded"], "final": c["final"], "flagged": c["flagged"], "lying": c.get("lying", False),
            "persona": per["label"] if (neg >= 2 or ment >= 1) else None, "vibe": vibe, "floor": floor,
        }

    def leaderboard(self):
        rows = []
        for pid in self.order:
            p = self.players.get(pid)
            if not p:
                continue
            inv = int(sum(self.book_value(e) for e in p["inv"].values()) * LIQUIDATION)
            rows.append({"id": pid, "name": p["name"], "is_ai": p["is_ai"], "cash": p["cash"], "inventory": inv,
                         "loan": p["loan"], "net_worth": self.net_worth(p), "rep": round(p["rep"]),
                         "connected": p["connected"] or p["is_ai"], "autopilot": p["autopilot"], "theme": p["theme"],
                         "title": p["title"], "items": len(p["inv"]), "ready": p["ready"],
                         "staff": len(p["staff"]), "upgrades": sum(p["upgrades"].values()), "dtype": p["dtype"]})
        rows.sort(key=lambda r: -r["net_worth"])
        return rows

    def view(self, pid):
        p = self.players.get(pid)
        if not p:
            return {"error": "not in match"}
        v = {
            "you": pid, "host": self.host, "phase": self.phase, "day": self.day, "days": self.settings["days"],
            "left": max(0, round(self.phase_end - self.clock, 1)) if self.phase not in ("lobby", "final", "auction") else None,
            "paused": self.paused, "settings": self.settings, "room": self.room,
            "feed": self.feed[-25:], "leaderboard": self.leaderboard(),
            "market": {c: {"mult": m["mult"], "prev": m["prev"], "name": I.CATEGORIES[c]["name"],
                           "color": I.CATEGORIES[c]["color"]} for c, m in self.market.items()},
            "events": [{"name": e["name"], "desc": e["desc"]} for e in self.events_today],
            "rumors": [e["rumor"] for e in self.events_tomorrow],
            "history": self.history,
        }
        if self.phase == "lobby":
            v["types"] = DEALERSHIP_TYPES
            v["lobby"] = [{"id": x["id"], "name": x["name"], "is_ai": x["is_ai"], "title": x["title"], "theme": x["theme"], "dtype": x["dtype"]}
                          for x in (self.players[i] for i in self.order)]
            return v
        inv = []
        for e in p["inv"].values():
            iv = self.item_view(e["item"], e["know"])
            iv.update({"paid": e["paid"], "listed": e["listed"], "price": e["price"], "days": e["days"], "source": e["source"],
                       "repair": e.get("repair"), "repairQuote": self.repair_quote(p, e)})
            inv.append(iv)
        inv.sort(key=lambda x: (not x["listed"], x["name"]))
        tools = {}
        for t in TOOLS:
            cost, tm = self.tool_cost(p, t)
            tools[t] = {"name": TOOLS[t]["name"], "cost": cost, "time": round(tm, 1), "desc": TOOLS[t]["desc"]}
        v["me"] = {
            "cash": p["cash"], "loan": p["loan"], "rep": round(p["rep"], 1), "upgrades": p["upgrades"],
            "specialty": p["specialty"], "staff": p["staff"], "inventory": inv,
            "active": self.customer_view(p, p["active"]) if p["active"] else None,
            "queue": [{"name": c["name"], "look": c["look"], "wait": round(c["wait"])} for c in p["queue"]],
            "lastCustomer": p.get("last_customer"),
            "buyerOffers": [dict(o, left=round(o["expires"] - self.clock, 1), itemName=I.CATALOG[p["inv"][o["item"]]["item"]["tpl"]]["name"] if o["item"] in p["inv"] else "?")
                            for o in p["buyer_offers"]],
            "notes": p["notes"], "ready": p["ready"], "research": p["research"], "day": p["day"],
            "storage": self.storage_cap(p), "display": self.display_cap(p), "maxStaff": self.max_staff(p),
            "tools": tools, "netWorth": self.net_worth(p), "expertLeft": max(0, [0, 4, 8, 999][self.staff_skill(p, "expert")] - p.get("expert_used", 0)),
            "mechanicJobs": sum(1 for x in p["inv"].values() if x.get("repair")), "stats": p["stats"], "consigned": p["consigned"],
            "maxLoan": MAX_LOAN, "dtype": p["dtype"], "cats": p["cats"], "theme": p["theme"], "decor": p["decor"], "autopilot": p["autopilot"],
        }
        v["upgrades"] = UPGRADES
        v["types"] = DEALERSHIP_TYPES
        v["employees"] = EMPLOYEES
        v["wages"] = WAGES
        v["weekDaysLeft"] = self.week_days_left()
        v["startCash"] = START_CASH
        v["persuade"] = PERSUADE
        if self.phase == "shop":
            street = []
            for oid in self.order:
                o = self.players.get(oid)
                if not o or o is p:
                    continue
                its = []
                for e in o["inv"].values():
                    if e["listed"]:
                        pub = dict(e["know"])
                        pub["expert"] = False
                        iv = self.item_view(e["item"], pub)
                        iv["price"] = e["price"]
                        its.append(iv)
                street.append({"id": oid, "name": o["name"], "theme": o["theme"], "dtype": o["dtype"], "items": its})
            v["street"] = street
        po = self.private_offer
        if po:
            v["privateOffer"] = {"id": po["id"], "item": self.item_view(po["item"], po["know"]), "price": po["price"],
                                 "left": round(po["expires"] - self.clock, 1)}
        if self.phase == "auction" and self.auction:
            a = self.auction
            lot = a["lot"]
            av = {"index": a["idx"], "count": len(a["lots"]), "results": a["results"],
                  "upcoming": [l["title"] for l in a["lots"][a["idx"] + 1:]] if a["idx"] >= 0 else [l["title"] for l in a["lots"]]}
            if lot:
                av["lot"] = {"id": lot["id"], "title": lot["title"], "items": [self.item_view(x["item"], self.scout_know(p, x["know"])) for x in lot["entries"]],
                             "scouted": self.staff_skill(p, "scout"),
                             "low": lot["low"], "high": lot["high"], "start": lot["start"], "bid": lot["bid"],
                             "bidder": lot["bidder"], "bidderName": self.players[lot["bidder"]]["name"] if lot["bidder"] in self.players else None,
                             "bids": lot["bids"], "left": max(0, round(lot["ends"] - self.clock, 1)), "closed": lot["closed"],
                             "minBid": self.min_bid(lot), "seller": lot["seller"],
                             "sellerName": self.players[lot["seller"]]["name"] if lot["seller"] in self.players else None,
                             "result": lot.get("result")}
            v["auction"] = av
        if self.phase == "report" or self.phase == "final":
            v["report"] = self.report.get(pid)
        if self.final:
            v["final"] = self.final
        return v

    # ------------------------------------------------------------------ persistence
    def to_dict(self):
        d = {k: getattr(self, k) for k in self.SAVE_FIELDS}
        st = self.rng.getstate()
        d["rng"] = [st[0], list(st[1]), st[2]]
        d["version"] = 1
        return d

    @classmethod
    def from_dict(cls, d):
        m = cls(d["room"], d["settings"])
        for k in cls.SAVE_FIELDS:
            if k in d:
                setattr(m, k, d[k])
        r = d["rng"]
        m.rng.setstate((r[0], tuple(r[1]), r[2]))
        # saves from before dealership types existed
        m.settings.setdefault("type_rule", "free")
        m.settings.setdefault("rivals", "mix")
        if isinstance(m.seller_specs, list):
            m.seller_specs = {"general": m.seller_specs}
        hi = 0
        for p in m.players.values():
            p.setdefault("dtype", "general")
            p.setdefault("cats", list(m.market.keys()))
            p["connected"] = p["is_ai"]
            for iid in p["inv"]:
                try:
                    hi = max(hi, int(iid[2:]))
                except ValueError:
                    pass
        I.bump_ids(hi + 100000)
        return m
