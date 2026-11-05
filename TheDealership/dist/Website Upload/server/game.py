"""Authoritative match simulation for The Dealership.

The loop is deliberately simple and turn-based:
  🏪 Counter  — visitors come in one at a time. Sellers offer you an item, buyers want one of yours.
               You haggle, then press Next. No clock pressure.
  🔨 Auction  — a few lots, everyone bids live.
  🌙 Evening  — results, hire staff, buy upgrades, then the next day.
Everything that touches money or items happens here, under the room lock.
"""
import copy
import math
import random

import items as I
from content import (PERSONAS, LINES, BUYERS, BUYER_LINES, UPGRADES, EXAMINE_FEE, EMPLOYEES, WAGES, MAX_EMPLOYEES,
                     AI_HIRES, FIRST, LAST, AI_DEALERS, AI_STYLES, ESTATE_NAMES, DEALERSHIP_TYPES, AI_TYPE_PREF)

START_CASH = 25000
BASE_VISITORS = 8
TYPE_VISITORS = {"tech": 4, "collectibles": 4, "music": 2, "cars": -1, "general": -1}  # low-ticket shops see more people
# Buyers pay a premium to a specialist; more so for shops whose goods are cheap (keeps every type competitive).
TYPE_PREMIUM = {"tech": 0.24, "collectibles": 0.24, "music": 0.15, "gallery": 0.12, "relics": 0.14, "jeweler": 0.06, "cars": 0.02, "general": -0.1}
LIQUIDATION = 0.8  # unsold stock counts at 80% of its true value at the end
LOT_TIME = {"quick": 14, "normal": 18, "relaxed": 22}
SHOP_CAP_MP = 600  # multiplayer: a day can't be stalled forever by one player
EVENING_CAP_MP = 150
NEVER = 10 ** 9


class ActionError(Exception):
    pass


def clamp(v, a, b):
    return max(a, min(b, v))


def cat_of(item):
    return I.CATALOG[item["tpl"]]["category"]


class Match:
    SAVE_FIELDS = ["room", "settings", "players", "order", "phase", "phase_end", "clock", "day", "market", "hot",
                   "cold", "next_hot", "next_cold", "seller_specs", "auction", "feed", "feed_seq", "history", "final",
                   "host", "paused", "seq", "report", "shop_started"]

    def __init__(self, room, settings, seed=None):
        self.room = room
        pace = settings.get("pace") if settings.get("pace") in LOT_TIME else "normal"
        self.settings = {
            "days": int(clamp(int(settings.get("days", 7)), 3, 15)),
            "pace": pace,
            "max_players": int(clamp(int(settings.get("max_players", 6)), 2, 8)),
            "expansion_space": bool(settings.get("expansion_space", False)),
            "solo": bool(settings.get("solo", False)),
            "public": bool(settings.get("public", True)),
            "name": str(settings.get("name", "Dealership Match"))[:40],
            "type_rule": settings.get("type_rule") if settings.get("type_rule") in DEALERSHIP_TYPES else "free",
            "rivals": settings.get("rivals") if settings.get("rivals") in ("same", "mix", "general") else "mix",
        }
        self.rng = random.Random(seed if seed is not None else random.randrange(1 << 30))
        self.players, self.order = {}, []
        self.host = None
        self.phase, self.phase_end, self.clock, self.day = "lobby", NEVER, 0.0, 0
        self.market = {c: {"mult": 1.0, "prev": 1.0} for c in self.all_cats()}
        self.hot = self.cold = self.next_hot = self.next_cold = None
        self.seller_specs = {}
        self.auction = None
        self.feed, self.feed_seq = [], 0
        self.history, self.final, self.report = [], None, {}
        self.paused, self.seq, self.shop_started = False, 0, 0.0
        self.dirty = True

    # ------------------------------------------------------------------ helpers
    def all_cats(self):
        return list(I.BASE_CATEGORIES) + (["space"] if self.settings["expansion_space"] else [])

    def categories(self):
        return list(self.market.keys())

    def cats_for(self, dtype):
        allc = self.all_cats()
        t = DEALERSHIP_TYPES.get(dtype, DEALERSHIP_TYPES["general"])["cats"]
        cats = allc if t is None else [c for c in t if c in allc]
        return cats or allc

    def can_trade(self, p, cat):
        return cat in p["cats"]

    def type_name(self, p):
        return DEALERSHIP_TYPES.get(p["dtype"], DEALERSHIP_TYPES["general"])["name"]

    def mult(self, cat):
        return self.market.get(cat, {"mult": 1.0})["mult"]

    def tv(self, item):
        return I.true_value(item, self.mult(cat_of(item)))

    def uid(self, prefix):
        self.seq += 1
        return "%s%d" % (prefix, self.seq)

    def log(self, text, kind="info"):
        self.feed_seq += 1
        self.feed.append({"n": self.feed_seq, "day": self.day, "text": text, "kind": kind})
        self.feed = self.feed[-50:]

    def note(self, p, text, kind="info"):
        p["note_seq"] += 1
        p["notes"].append({"n": p["note_seq"], "text": text, "kind": kind})
        p["notes"] = p["notes"][-30:]

    def line(self, pool, **kw):
        s = self.rng.choice(pool)
        for k, v in kw.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    def say(self, v, who, text):
        v["lines"].append({"who": who, "text": text})
        v["lines"] = v["lines"][-12:]

    def humans(self):
        return [p for p in self.players.values() if not p["is_ai"]]

    def bot(self, p):
        """AI dealers and disconnected humans (autopilot) are run by the computer."""
        return p["is_ai"] or p["autopilot"]

    def staff_skill(self, p, role):
        return max([s["stars"] for s in p["staff"] if s["role"] == role] or [0])

    def storage_cap(self, p):
        return UPGRADES["storage"]["values"][p["upgrades"]["storage"]]

    def examine_fee(self, p):
        return EXAMINE_FEE[p["upgrades"]["desk"]]

    def money(self, v):
        return "$" + format(int(v), ",")

    # ------------------------------------------------------------------ lobby
    def new_player(self, name, is_ai=False, style="balanced", token=None, cosmetics=None):
        pid = self.uid("p")
        cos = cosmetics or {}
        p = {
            "id": pid, "name": str(name)[:20] or "Dealer", "is_ai": is_ai, "style": style, "token": token,
            "dtype": "general", "cats": self.all_cats(),
            "connected": not is_ai, "last_seen": self.clock, "autopilot": False,
            "cash": START_CASH, "rep": 50.0, "upgrades": {k: 0 for k in UPGRADES}, "upgrade_spend": 0,
            "staff": [], "inv": {}, "notes": [], "note_seq": 0, "ready": False,
            "visitors": 0, "vidx": 0, "seller_idx": 0, "visitor": None, "last": None, "done": False,
            "theme": cos.get("theme", "classic"), "title": cos.get("title", "Rookie Dealer"), "decor": cos.get("decor", []),
            "stats": {"bought": 0, "sold": 0, "revenue": 0, "spent": 0, "profit": 0, "fakes_caught": 0,
                      "fakes_bought": 0, "auction_wins": 0, "best_flip": 0, "best_flip_name": "",
                      "jackpots": 0, "walkouts": 0, "deals": 0, "rival_buys": 0, "complaints": 0},
            "day": self.blank_day(), "ai": {"next": 0.0, "est": {}}, "expert_used": 0, "forecast": None,
            "nonces": [], "results": {}, "pending_complaints": [],
        }
        self.players[pid] = p
        self.order.append(pid)
        self.dirty = True
        return p

    def blank_day(self):
        return {"revenue": 0, "spent": 0, "wages": 0, "tools": 0, "refunds": 0, "upgrades": 0, "auction": 0,
                "bought": 0, "sold": 0, "start_nw": 0, "stolen": 0}

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
        p = self.new_player(d["name"], is_ai=True, style=d["style"],
                            cosmetics={"theme": self.rng.choice(["classic", "neon", "deco", "rustic", "velvet", "vault"]),
                                       "title": "AI Dealer"})
        p["dtype"] = AI_TYPE_PREF.get(d["style"]) or self.rng.choice(list(DEALERSHIP_TYPES))
        self.log("%s (AI) joined the lobby." % p["name"])
        return p

    def remove_player(self, pid):
        if self.phase != "lobby" or pid not in self.players:
            return
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
        rule, host = self.settings["type_rule"], self.players.get(self.host)
        for p in self.players.values():
            if rule != "free":
                p["dtype"] = rule
            elif p["is_ai"] and self.settings["solo"]:
                r = self.settings["rivals"]
                p["dtype"] = host["dtype"] if r == "same" and host else "general" if r == "general" \
                    else self.rng.choice(list(DEALERSHIP_TYPES))
            p["cats"] = self.cats_for(p["dtype"])
        in_play = [c for c in self.all_cats() if any(c in p["cats"] for p in self.players.values())]
        self.market = {c: {"mult": 1.0, "prev": 1.0} for c in in_play}

    def start(self):
        if self.phase != "lobby":
            raise ActionError("Already started")
        if len(self.players) < 2:
            raise ActionError("Need at least 2 dealers (add AI dealers to fill seats)")
        self.assign_types()
        self.next_hot, self.next_cold = self.pick_hot_cold()
        self.log("The match begins! Every dealer starts with %s." % self.money(START_CASH), "big")
        self.begin_day()

    # ------------------------------------------------------------------ day flow
    def set_phase(self, phase, cap):
        self.phase = phase
        self.phase_end = self.clock + cap
        for p in self.players.values():
            p["ready"] = False
        self.dirty = True

    def pick_hot_cold(self):
        cats = self.categories()
        if len(cats) == 1:
            r = self.rng.random()
            return (cats[0], None) if r < 0.4 else (None, cats[0]) if r < 0.7 else (None, None)
        hot, cold = self.rng.sample(cats, 2)
        return hot, cold

    def begin_day(self):
        self.day += 1
        self.hot, self.cold = self.next_hot, self.next_cold
        self.next_hot, self.next_cold = self.pick_hot_cold()
        for c, m in self.market.items():
            m["prev"] = m["mult"]
            base = 1 + (m.get("base", 1.0) - 1) * 0.5 + self.rng.gauss(0, 0.04)
            m["base"] = clamp(base, 0.85, 1.15)
            m["mult"] = round(m["base"] * (1.35 if c == self.hot else 0.75 if c == self.cold else 1.0), 3)
        self.seller_specs = {}
        for dt in sorted({p["dtype"] for p in self.players.values()}):
            self.seller_specs[dt] = self.gen_seller_specs(30, self.cats_for(dt))
        for p in self.players.values():
            p["day"] = self.blank_day()
            self.payday(p)
            self.finish_repairs(p)
            p["day"]["start_nw"] = self.net_worth(p)
            p["visitors"] = self.visitors_today(p)
            p["vidx"], p["seller_idx"], p["visitor"], p["last"], p["done"] = 0, 0, None, None, False
            p["expert_used"] = 0
            p["forecast"] = self.analyst_forecast(p)
            p["ai"]["next"] = self.clock + self.rng.uniform(2, 5)
        hot = I.CATEGORIES[self.hot]["name"] if self.hot else None
        cold = I.CATEGORIES[self.cold]["name"] if self.cold else None
        self.log("Day %d — %s" % (self.day, ", ".join(x for x in [hot and hot + " are HOT", cold and cold + " are cold"] if x)
                                  or "a calm market"), "big")
        self.shop_started = self.clock
        self.set_phase("shop", NEVER if self.settings["solo"] else SHOP_CAP_MP)
        for p in self.players.values():
            if self.bot(p):
                self.ai_morning(p)

    def visitors_today(self, p):
        return BASE_VISITORS + TYPE_VISITORS.get(p["dtype"], 0) + 2 * p["upgrades"]["shop"] + self.staff_skill(p, "marketer")

    def end_shop(self):
        for p in self.players.values():
            if p["visitor"]:
                self.say(p["visitor"], "them", "Oh, you're closing? Never mind.")
            p["visitor"], p["done"] = None, True
        self.begin_auction()

    def end_day(self):
        """Night: burglaries, complaints about fakes; then the evening report."""
        for p in self.players.values():
            self.process_complaints(p)
            self.night_theft(p)
        snap = {"day": self.day, "nw": {pid: self.net_worth(p) for pid, p in self.players.items()}}
        self.history.append(snap)
        self.report = {pid: dict(p["day"], end_nw=self.net_worth(p), cash=p["cash"], rep=round(p["rep"]))
                       for pid, p in self.players.items()}
        if self.day >= self.settings["days"]:
            self.finish()
        else:
            self.set_phase("evening", NEVER if self.settings["solo"] else EVENING_CAP_MP)
            for p in self.players.values():
                if self.bot(p):
                    p["ready"] = True

    def finish(self):
        rows = []
        for pid, p in self.players.items():
            inv_true = int(LIQUIDATION * sum(self.tv(e["item"]) for e in p["inv"].values()))
            book = sum(self.book_value(e) for e in p["inv"].values())
            assets = int(p["upgrade_spend"] * 0.4)
            rows.append({"id": pid, "name": p["name"], "is_ai": p["is_ai"], "dtype": p["dtype"], "cash": p["cash"],
                         "inventory": inv_true, "book": book, "assets": assets, "loan": 0,
                         "net_worth": p["cash"] + inv_true + assets, "rep": round(p["rep"]), "stats": p["stats"],
                         "title": p["title"], "theme": p["theme"]})
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
        award("Treasure Hunter", "jackpots", "%d rare finds")
        award("Deal Machine", "deals", "%d purchases")
        self.final = {"rows": rows, "awards": awards, "days": self.settings["days"]}
        self.set_phase("final", NEVER)
        self.log("The match is over! %s wins with %s." % (rows[0]["name"], self.money(rows[0]["net_worth"])), "big")

    # ------------------------------------------------------------------ valuation
    def book_value(self, e):
        return I.estimate(e["item"], e["know"], self.mult(cat_of(e["item"])))[1]

    def net_worth(self, p):
        inv = sum(self.book_value(e) for e in p["inv"].values()) * LIQUIDATION
        return int(p["cash"] + inv + p["upgrade_spend"] * 0.4)

    # ------------------------------------------------------------------ generation
    def gen_seller_specs(self, n, cats):
        """One list per dealership type and day: every dealer of a type meets the same sellers in the same order."""
        weights = {k: v["weight"] for k, v in PERSONAS.items()}
        full = [t for t in I.CATALOG.values() if t["category"] in cats]
        cheap_cap = max(30000, sorted(t["base"] for t in full)[len(full) // 2] * 1.5)
        specs = []
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
            w = [x * (1.3 if t["category"] == self.hot else 1.0) for x, t in zip(w, pool)]
            tpl = self.rng.choices(pool, weights=w)[0]
            if persona == "crook" and tpl["fakeable"]:
                item = I.make_item(self.rng, tpl["key"], authentic=self.rng.random() > 0.7)
            else:
                item = I.make_item(self.rng, tpl["key"], fake_rate=0.1)
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
            "beard": r.random() < 0.25, "persona": persona,
        }

    def gen_lots(self):
        lots, cats = [], self.categories()
        pool = [t for t in I.CATALOG.values() if t["category"] in cats and t["rarity"] >= 3] or \
               [t for t in I.CATALOG.values() if t["category"] in cats]
        for _ in range(3):
            tpl = self.rng.choices(pool, weights=[t["rarity"] for t in pool])[0]
            item = I.make_item(self.rng, tpl["key"], fake_rate=0.1)
            know = I.new_knowledge(item["cond"])
            know["cond"] = self.rng.random() < 0.6
            if not know["cond"]:
                know["claimed"] = max(0, item["cond"] - self.rng.choice([0, 1]))
            know["auth"] = self.rng.random() < 0.45
            know["edition"] = self.rng.random() < 0.3
            lots.append(self.make_lot([(item, know)]))
        if self.day % 3 == 0:  # every third day: a whole estate goes under the hammer
            bundle = []
            for _ in range(self.rng.randint(3, 4)):
                tpl = self.rng.choice([t for t in I.CATALOG.values() if t["category"] in cats])
                it = I.make_item(self.rng, tpl["key"])
                bundle.append((it, I.new_knowledge(it["cond"])))
            lot = self.make_lot(bundle)
            lot["title"] = "Estate of %s (%d items)" % (self.rng.choice(ESTATE_NAMES), len(bundle))
            lots.append(lot)
        return lots

    def make_lot(self, entries):
        ests = [I.estimate(it, k, self.mult(cat_of(it))) for it, k in entries]
        likely = sum(e[1] for e in ests)
        return {"id": self.uid("lot"), "entries": [{"item": it, "know": k} for it, k in entries],
                "title": I.CATALOG[entries[0][0]["tpl"]]["name"], "low": sum(e[0] for e in ests),
                "high": sum(e[2] for e in ests), "likely": likely, "start": I.nice(max(200, likely * 0.3)),
                "bid": 0, "bidder": None, "bids": [], "ends": None, "closed": False, "ai_caps": {}}

    # ------------------------------------------------------------------ main tick
    def tick(self, dt):
        if self.phase in ("lobby", "final") or self.paused:
            return
        self.clock += dt
        for p in self.humans():
            was = p["autopilot"]
            p["autopilot"] = (not p["connected"]) and (self.clock - p["last_seen"] > 20)
            if p["autopilot"] and not was:
                self.log("%s lost connection — autopilot engaged." % p["name"], "warn")
            elif was and not p["autopilot"]:
                self.log("%s is back in control." % p["name"])
        if self.phase == "shop":
            humans_done = all(p["done"] for p in self.players.values() if not self.bot(p))
            # computer dealers keep pace with the furthest human, so nobody feels rushed
            lead = max([(x["vidx"] + 1) / max(1, x["visitors"]) for x in self.players.values() if not self.bot(x)] or [1.0])
            for p in self.players.values():
                in_step = p["vidx"] / max(1, p["visitors"]) < lead
                if self.bot(p) and not p["done"] and (humans_done or (in_step and self.clock >= p["ai"]["next"])):
                    self.ai_visit(p)
                    p["ai"]["next"] = self.clock + self.rng.uniform(3, 8)
            if all(p["done"] for p in self.players.values()) or self.clock >= self.phase_end:
                self.end_shop()
        elif self.phase == "auction":
            self.tick_auction()
        elif self.phase == "evening":
            hs = [p for p in self.humans() if not p["autopilot"]]
            if (hs and all(p["ready"] for p in hs)) or not hs or self.clock >= self.phase_end:
                self.begin_day()
        self.dirty = True

    # ------------------------------------------------------------------ visitors
    def act_next(self, p):
        if self.phase != "shop":
            raise ActionError("The shop is closed")
        if p["visitor"]:
            raise ActionError("Finish with this visitor first")
        if p["vidx"] >= p["visitors"]:
            p["done"] = True
            return {"result": "done"}
        p["vidx"] += 1
        p["last"] = None
        sellable = [e for e in p["inv"].values() if not e.get("repair") and self.can_trade(p, cat_of(e["item"]))]
        specs = self.seller_specs.get(p["dtype"], [])
        buyer_chance = 0.0
        if sellable:
            buyer_chance = 0.42 + 0.04 * min(len(sellable), 6) + 0.04 * self.staff_skill(p, "sales")
            if len(p["inv"]) >= self.storage_cap(p):
                buyer_chance = 0.85
        if sellable and (self.rng.random() < buyer_chance or p["seller_idx"] >= len(specs)):
            p["visitor"] = self.make_buyer(p, sellable)
        elif p["seller_idx"] < len(specs):
            p["visitor"] = self.make_seller(p, specs[p["seller_idx"]])
            p["seller_idx"] += 1
        else:
            return self.act_next(p)
        if not p["visitor"]:  # a buyer exposed a fake and left on the spot
            return {"result": "left"}
        return {"result": "visitor", "kind": p["visitor"]["kind"]}

    def make_seller(self, p, spec):
        item = copy.deepcopy(spec["item"])
        item["id"] = I.new_item_id()
        per = PERSONAS[spec["persona"]]
        mult = self.mult(cat_of(item))
        tv, nv = I.true_value(item, mult), I.naive_value(item, spec["claimed"], mult)
        perceived = nv if spec["persona"] == "crook" else tv * per["knowledge"] + nv * (1 - per["knowledge"])
        ask = I.nice(perceived * per["greed"] * (0.95 + spec["roll"] * 0.15))
        reserve = perceived * per["reserve"] * (1 - 0.04 * self.staff_skill(p, "negotiator")) * (1 - 0.06 * (p["rep"] - 50) / 50)
        reserve = max(30, min(reserve * (0.93 + spec["roll2"] * 0.14), ask * 0.97))
        rounds = int(clamp(round(per["patience"] / 12.0), 3, 6))
        sec = self.staff_skill(p, "security")
        v = {"kind": "seller", "id": self.uid("v"), "persona": spec["persona"], "name": spec["name"], "look": spec["look"],
             "item": item, "know": I.new_knowledge(spec["claimed"]), "ask": ask, "reserve": reserve,
             "mood": float(per["mood"]), "rounds": rounds, "rounds_max": rounds, "lines": [], "last_offer": 0,
             "above": 0, "final": False, "callback_used": False, "examined": False,
             "flagged": spec["persona"] == "crook" and sec >= 1, "lying": sec >= 2 and spec["claimed"] < item["cond"]}
        self.say(v, "them", self.line(LINES["greet"].get(spec["persona"], LINES["greet"]["regular"]),
                                      item=I.CATALOG[item["tpl"]]["name"], ask=format(ask, ",")))
        return v

    def make_buyer(self, p, sellable):
        weights = [1.6 if cat_of(e["item"]) == self.hot else 0.6 if cat_of(e["item"]) == self.cold else 1.0 for e in sellable]
        e = self.rng.choices(sellable, weights=weights)[0]
        kind = self.rng.choices(list(BUYERS), weights=[30, 42, 20, 8])[0]
        b = BUYERS[kind]
        wtp = self.buyer_value(p, e) * b["wtp"] * self.rng.uniform(0.9, 1.1)
        wtp *= 1 + 0.08 * p["upgrades"]["cases"] + 0.05 * self.staff_skill(p, "sales") + (p["rep"] - 50) / 300
        wtp *= 1 + TYPE_PREMIUM.get(p["dtype"], 0.0)  # people trust (and pay) a specialist
        offer = I.nice(wtp * self.rng.uniform(*b["open"]))
        v = {"kind": "buyer", "id": self.uid("v"), "persona": kind, "name": "%s %s" % (self.rng.choice(FIRST), self.rng.choice(LAST)),
             "look": self.gen_look("regular"), "entry_id": e["item"]["id"], "wtp": wtp, "offer": offer,
             "mood": 70.0, "rounds": b["rounds"], "rounds_max": b["rounds"], "lines": [], "last_ask": 0, "final": False}
        name = I.CATALOG[e["item"]["tpl"]]["name"]
        if not e["item"]["authentic"] and not e["know"]["auth"] and self.rng.random() < 0.25:
            e["know"]["auth"] = True  # the buyer exposes the fake right at the counter
            p["rep"] = clamp(p["rep"] - 2, 0, 100)
            self.say(v, "them", self.line(BUYER_LINES["fake"]))
            p["visitor"] = v
            self.end_visitor(p, "bad", "%s spotted that your %s is a FAKE and walked out." % (v["name"], name))
            return None
        self.say(v, "them", self.line(BUYER_LINES["greet"], item=name, offer=format(offer, ",")))
        return v

    def buyer_value(self, p, e):
        it = e["item"]
        if e["know"]["auth"]:
            return self.tv(it) * (1.06 if it["authentic"] else 1.0)
        looks = self.tv(it) if it["authentic"] else I.naive_value(it, it["cond"], self.mult(cat_of(it)))
        return looks * (0.86 + 0.1 * p["rep"] / 100) if looks > 1500 else looks

    def require_visitor(self, p, kind=None):
        if self.phase != "shop":
            raise ActionError("The shop is closed")
        v = p["visitor"]
        if not v:
            raise ActionError("Nobody is at the counter — press Next visitor")
        if kind and v["kind"] != kind:
            raise ActionError("That doesn't work with this visitor")
        return v

    def end_visitor(self, p, outcome, text, price=None):
        v = p["visitor"]
        p["last"] = {"outcome": outcome, "text": text, "price": price,
                     "name": v["name"] if v else "", "look": v["look"] if v else None,
                     "lines": v["lines"][-3:] if v else [], "kind": v["kind"] if v else ""}
        p["visitor"] = None
        if p["vidx"] >= p["visitors"]:
            p["done"] = True
        self.note(p, text, "quiet-" + outcome)  # shown in the result card; the client only plays a sound

    # ---------------- seller actions
    def act_offer(self, p, amount):
        v = self.require_visitor(p)
        if v["kind"] == "buyer":
            return self.act_counter(p, amount)
        amount = int(amount)
        if amount <= 0:
            raise ActionError("Offer must be positive")
        if amount > p["cash"]:
            raise ActionError("You don't have that much cash")
        per = PERSONAS[v["persona"]]
        self.say(v, "you", "How about $%s?" % format(amount, ","))
        if amount >= v["ask"]:
            return self.buy(p, v["ask"])
        if v["final"]:
            self.say(v, "them", "I said that was my final price.")
            v["mood"] -= 30
            if v["mood"] <= 0 or v["rounds"] <= 0:
                return self.storm(p)
        if v["last_offer"] and amount < v["last_offer"]:
            v["mood"] -= 15
            self.say(v, "them", self.line(LINES["backwards"]))
        v["last_offer"] = max(v["last_offer"], amount)
        v["rounds"] -= 1
        ratio = amount / max(1.0, v["reserve"])
        if ratio >= 1:
            span = max(1.0, v["ask"] - v["reserve"])
            pr = 0.4 + 0.6 * (amount - v["reserve"]) / span + (v["mood"] - 50) / 200 + 0.25 * v["above"]
            pr += [0, 0.08, 0.15, 0.25][self.staff_skill(p, "lucky")]
            v["above"] += 1
            if self.rng.random() < pr or v["rounds"] <= 0:
                return self.buy(p, amount)
        else:
            v["mood"] -= 28 if ratio < 0.55 else 12 if ratio < 0.8 else 5
            if ratio < 0.55:
                self.say(v, "them", self.line(LINES["insulted"]))
        if v["mood"] <= 0 or (v["rounds"] <= 0 and v["final"]):
            return self.storm(p)
        conc = per["concession"] * (0.5 + v["mood"] / 100)
        new_ask = I.nice(max(v["reserve"], v["ask"] - (v["ask"] - amount) * conc))
        v["ask"] = max(min(new_ask, v["ask"]), int(math.ceil(v["reserve"])))
        if v["rounds"] <= 1 or v["ask"] - v["reserve"] < max(50, v["reserve"] * 0.04):
            v["final"] = True
            self.say(v, "them", self.line(LINES["final"], ask=format(v["ask"], ",")))
        else:
            self.say(v, "them", self.line(LINES["counter"].get(v["persona"], LINES["counter"]["regular"]), ask=format(v["ask"], ",")))
        return {"result": "counter", "ask": v["ask"]}

    def storm(self, p):
        v = p["visitor"]
        self.say(v, "them", self.line(LINES["storm"]))
        p["rep"] = clamp(p["rep"] - 1, 0, 100)
        p["stats"]["walkouts"] += 1
        self.end_visitor(p, "bad", "%s got annoyed and left." % v["name"])
        return {"result": "left"}

    def buy(self, p, price):
        v = p["visitor"]
        price = int(price)
        if price > p["cash"]:
            raise ActionError("You can't afford that")
        if len(p["inv"]) >= self.storage_cap(p):
            raise ActionError("Your stock room is full — sell something or upgrade the Back Room")
        it = v["item"]
        p["cash"] -= price
        p["day"]["spent"] += price
        p["day"]["bought"] += 1
        for k in ("bought", "deals"):
            p["stats"][k] += 1
        p["stats"]["spent"] += price
        if not it["authentic"]:
            p["stats"]["fakes_bought"] += 1
        p["inv"][it["id"]] = {"item": it, "know": v["know"], "paid": price, "days": 0,
                              "source": "Bought from %s" % v["name"], "day_in": self.day}
        self.say(v, "them", self.line(LINES["accept"].get(v["persona"], LINES["accept"]["regular"])))
        p["rep"] = clamp(p["rep"] + 0.3, 0, 100)
        self.end_visitor(p, "good", "You bought the %s for %s." % (I.CATALOG[it["tpl"]]["name"], self.money(price)), price)
        return {"result": "bought", "price": price, "item": it["id"]}

    def act_accept(self, p):
        v = self.require_visitor(p)
        if v["kind"] == "seller":
            self.say(v, "you", "Deal at $%s." % format(v["ask"], ","))
            return self.buy(p, v["ask"])
        self.say(v, "you", "Deal at $%s." % format(v["offer"], ","))
        return self.sell(p, v["offer"])

    def act_pass(self, p):
        v = self.require_visitor(p)
        if v["kind"] == "buyer":
            self.say(v, "you", "Sorry, not for that price.")
            self.say(v, "them", self.line(BUYER_LINES["leave"]))
            self.end_visitor(p, "info", "%s left without buying." % v["name"])
            return {"result": "left"}
        per = PERSONAS[v["persona"]]
        self.say(v, "you", "No thanks, I'll pass.")
        if (not v["callback_used"] and v["last_offer"] >= v["reserve"] * 0.85
                and self.rng.random() < per["callback"] + 0.05 * self.staff_skill(p, "negotiator")):
            v["callback_used"] = True
            v["ask"] = I.nice(max(v["last_offer"] * 1.03, v["reserve"] * 0.97))
            v["reserve"] = min(v["reserve"], v["ask"])
            v["final"] = True
            v["rounds"] = max(v["rounds"], 1)
            self.say(v, "them", self.line(LINES["callback"], ask=format(v["ask"], ",")))
            return {"result": "callback", "ask": v["ask"]}
        self.say(v, "them", "Your loss.")
        self.end_visitor(p, "info", "%s took the %s elsewhere." % (v["name"], I.CATALOG[v["item"]["tpl"]]["name"]))
        return {"result": "left"}

    # ---------------- buyer actions
    def act_counter(self, p, price):
        v = self.require_visitor(p, "buyer")
        price = int(price)
        if price <= 0:
            raise ActionError("Enter a price")
        self.say(v, "you", "I'd want $%s." % format(price, ","))
        if price <= v["offer"]:
            return self.sell(p, v["offer"])
        b = BUYERS[v["persona"]]
        v["rounds"] -= 1
        if v["last_ask"] and price > v["last_ask"]:
            v["mood"] -= 15
        v["last_ask"] = price
        if price <= v["wtp"]:
            span = max(1.0, v["wtp"] - v["offer"])
            pr = 0.45 + 0.55 * (v["wtp"] - price) / span + [0, 0.08, 0.15, 0.25][self.staff_skill(p, "lucky")]
            if self.rng.random() < pr or v["rounds"] <= 0:
                return self.sell(p, price)
        elif price > v["wtp"] * 1.35:
            v["mood"] -= 25
            self.say(v, "them", self.line(BUYER_LINES["insulted"]))
        else:
            v["mood"] -= 8
        if v["mood"] <= 0 or (v["rounds"] <= 0 and v["final"]):
            self.say(v, "them", self.line(BUYER_LINES["leave"]))
            p["stats"]["walkouts"] += 1
            self.end_visitor(p, "bad", "%s left — your price was too high." % v["name"])
            return {"result": "left"}
        target = min(price, v["wtp"])
        v["offer"] = max(v["offer"], I.nice(v["offer"] + (target - v["offer"]) * b["conc"] * (0.6 + v["mood"] / 100)))
        if v["rounds"] <= 1 or v["wtp"] - v["offer"] < max(50, v["wtp"] * 0.04):
            v["final"] = True
            self.say(v, "them", self.line(BUYER_LINES["final"], offer=format(v["offer"], ",")))
        else:
            self.say(v, "them", self.line(BUYER_LINES["counter"], offer=format(v["offer"], ",")))
        return {"result": "counter", "offer": v["offer"]}

    def sell(self, p, price):
        v = p["visitor"]
        e = p["inv"].pop(v["entry_id"], None)
        if not e:
            raise ActionError("That item is gone")
        price = int(price)
        if self.rng.random() < 0.06 * self.staff_skill(p, "lucky"):
            price = I.nice(price * 1.1)
            self.note(p, "Lucky! The buyer loved it and added a 10% tip.", "good")
        p["cash"] += price
        self.record_sale(p, e, price)
        if not e["item"]["authentic"] and not e["know"]["auth"]:
            p["pending_complaints"].append({"item": e["item"], "know": e["know"], "price": price})
        p["rep"] = clamp(p["rep"] + (1.0 if e["know"]["auth"] else 0.6), 0, 100)
        self.say(v, "them", self.line(BUYER_LINES["accept"]))
        name = I.CATALOG[e["item"]["tpl"]]["name"]
        profit = price - e["paid"]
        self.end_visitor(p, "sale", "SOLD the %s for %s (%s%s profit)." % (name, self.money(price), "+" if profit >= 0 else "−",
                                                                       self.money(abs(profit))), price)
        if profit > 8000:
            self.log("%s flipped a %s for a %s profit!" % (p["name"], name, self.money(profit)), "sale")
        return {"result": "sold", "price": price}

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
        m = self.market.get(cat_of(e["item"]))
        if m:
            m["mult"] = round(max(0.5, m["mult"] - (0.004 if wholesale else 0.008)), 3)

    # ---------------- examine / expert
    def act_examine(self, p, target):
        if self.phase in ("auction", "lobby", "final"):
            raise ActionError("Not available right now")
        it, k, v = self.target_item(p, target)
        if k["cond"] and k["auth"]:
            raise ActionError("You've already examined this")
        fee = self.examine_fee(p)
        if fee > p["cash"]:
            raise ActionError("Not enough cash")
        p["cash"] -= fee
        p["day"]["tools"] += fee
        k["cond"] = True
        k["auth"] = True
        if p["upgrades"]["desk"] >= 2:
            k["lab"] = True
        if v:
            self.say(v, "you", "Mind if I take a close look?")
        name = I.CATALOG[it["tpl"]]["name"]
        if not it["authentic"]:
            p["stats"]["fakes_caught"] += 1
            k["edition"] = True
            self.note(p, "🔍 The %s is a FAKE!" % name, "bad")
        else:
            self.note(p, "🔍 %s: genuine, %s." % (name, I.COND_LABEL[it["cond"]]), "info")
        return {"result": "examined", "fake": not it["authentic"], "cond": I.COND_LABEL[it["cond"]], "cost": fee}

    def target_item(self, p, target):
        if target == "counter":
            v = self.require_visitor(p)
            if v["kind"] == "seller":
                return v["item"], v["know"], v
            e = p["inv"].get(v["entry_id"])
            return e["item"], e["know"], v
        e = p["inv"].get(target)
        if not e:
            raise ActionError("Item not found")
        return e["item"], e["know"], None

    def act_opinion(self, p, target):
        if self.phase in ("auction", "lobby", "final"):
            raise ActionError("Not available right now")
        s = self.staff_skill(p, "expert")
        if not s:
            raise ActionError("Hire an Appraisal Expert first")
        limit = [0, 4, 8, 999][s]
        if p["expert_used"] >= limit:
            raise ActionError("Your expert has given all %d opinions for today" % limit)
        it, k, v = self.target_item(p, target)
        if k.get("opinion"):
            raise ActionError("Your expert has already looked at this")
        p["expert_used"] += 1
        tpl = I.CATALOG[it["tpl"]]
        rare = tpl["rarity"] >= 4 or it["edition"] >= 2
        fail = ([0, 0.4, 0.25, 0.1] if rare else [0, 0.06, 0.02, 0.0])[s]
        tv = self.tv(it)
        if self.rng.random() < fail:
            if not it["authentic"]:
                val = I.naive_value(it, it["cond"], self.mult(tpl["category"]))
            elif it["edition"] > 0:
                val = I.true_value(dict(it, edition=0), self.mult(tpl["category"]))
            else:
                val = tv * self.rng.choice([0.6, 0.7, 1.4, 1.6])
            k["opinion"], k["opinion_ok"] = int(val), False
        else:
            k["opinion"], k["opinion_ok"] = tv, True
            k.update({"cond": True, "auth": True, "edition": True})
            if not it["authentic"]:
                p["stats"]["fakes_caught"] += 1
            if it["edition"] >= 2 and it["authentic"]:
                p["stats"]["jackpots"] += 1
        if v:
            self.say(v, "you", "My expert will take a quick look.")
        self.note(p, "🎓 Expert: \"The %s is worth about %s.\"" % (tpl["name"], self.money(I.nice(k["opinion"]))), "info")
        return {"result": "opinion", "value": I.nice(k["opinion"])}

    def act_quick_sell(self, p, item_id):
        if self.phase in ("auction", "lobby", "final"):
            raise ActionError("The pawn broker is closed right now")
        e = p["inv"].get(item_id)
        if not e:
            raise ActionError("Item not found")
        if e.get("repair"):
            raise ActionError("That item is still being repaired")
        if p["visitor"] and p["visitor"].get("entry_id") == item_id:
            raise ActionError("A buyer is looking at that right now")
        del p["inv"][item_id]
        price = int(self.tv(e["item"]) * 0.45)
        p["cash"] += price
        self.record_sale(p, e, price, wholesale=True)
        self.note(p, "The pawn broker paid %s for the %s." % (self.money(price), I.CATALOG[e["item"]["tpl"]]["name"]), "info")
        return {"result": "sold", "price": price}

    # ---------------- night events
    def process_complaints(self, p):
        for c in p["pending_complaints"]:
            if self.rng.random() < 0.5 * (1 - 0.15 * self.staff_skill(p, "lucky")):
                p["cash"] -= c["price"]
                p["day"]["refunds"] += c["price"]
                p["stats"]["complaints"] += 1
                p["rep"] = clamp(p["rep"] - 6, 0, 100)
                name = I.CATALOG[c["item"]["tpl"]]["name"]
                self.note(p, "A customer returned the %s — it was a fake! You refunded %s." % (name, self.money(c["price"])), "bad")
                self.log("Scandal: %s sold a fake %s!" % (p["name"], name), "warn")
        p["pending_complaints"] = []
        if p["cash"] < 0:
            p["rep"] = clamp(p["rep"] - 3, 0, 100)

    def night_theft(self, p):
        cands = [e for e in p["inv"].values() if not e.get("repair") and self.tv(e["item"]) < 9000]
        if not cands or self.rng.random() > 0.2:
            return
        e = self.rng.choice(cands)
        name = I.CATALOG[e["item"]["tpl"]]["name"]
        if self.rng.random() < 0.3 * self.staff_skill(p, "security") + 0.15 * self.staff_skill(p, "lucky"):
            self.note(p, "Your security guard stopped a burglar trying to take the %s!" % name, "good")
            return
        del p["inv"][e["item"]["id"]]
        p["day"]["stolen"] += 1
        self.note(p, "Burglars broke in overnight and stole your %s!" % name, "bad")

    # ------------------------------------------------------------------ auction
    def begin_auction(self):
        self.auction = {"lots": self.gen_lots(), "idx": -1, "lot": None, "results": [], "gap_until": self.clock + 3}
        self.set_phase("auction", NEVER)
        self.log("The auction house opens: %d lots tonight." % len(self.auction["lots"]), "big")

    def tick_auction(self):
        a = self.auction
        lot = a["lot"]
        if lot is None or lot["closed"]:
            if self.clock < a["gap_until"]:
                return
            a["idx"] += 1
            if a["idx"] >= len(a["lots"]):
                a["lot"] = None
                self.end_day()
                return
            lot = a["lots"][a["idx"]]
            lot["ends"] = self.clock + LOT_TIME[self.settings["pace"]]
            a["lot"] = lot
            return
        for p in self.players.values():
            if self.bot(p):
                self.ai_bid(p, lot)
        if self.clock >= lot["ends"]:
            self.close_lot(lot)

    def min_bid(self, lot):
        return lot["start"] if not lot["bidder"] else lot["bid"] + max(100, I.nice(lot["bid"] * 0.06))

    def lot_allowed(self, p, lot):
        return any(self.can_trade(p, cat_of(x["item"])) for x in lot["entries"])

    def act_bid(self, p, amount):
        a = self.auction
        if self.phase != "auction" or not a or not a["lot"] or a["lot"]["closed"]:
            raise ActionError("No lot is open")
        lot = a["lot"]
        if self.clock >= lot["ends"]:
            raise ActionError("Bidding has closed")
        amount = int(amount)
        if lot["bidder"] == p["id"]:
            raise ActionError("You're already the highest bidder")
        if amount < self.min_bid(lot):
            raise ActionError("Bid must be at least %s" % self.money(self.min_bid(lot)))
        if amount > p["cash"]:
            raise ActionError("You can't cover that bid")
        if len(p["inv"]) + len(lot["entries"]) > self.storage_cap(p):
            raise ActionError("Not enough room in your stock for this lot")
        if not self.lot_allowed(p, lot):
            raise ActionError("This lot is outside what your dealership trades")
        lot["bid"], lot["bidder"] = amount, p["id"]
        lot["bids"].append({"pid": p["id"], "name": p["name"], "amount": amount})
        lot["bids"] = lot["bids"][-12:]
        if lot["ends"] - self.clock < 5:
            lot["ends"] = self.clock + 5  # no sniping
        return {"result": "bid", "amount": amount}

    def scout_know(self, p, know):
        s = self.staff_skill(p, "scout")
        k = dict(know)
        for key, need in (("cond", 1), ("auth", 2), ("edition", 3)):
            if s >= need:
                k[key] = True
        return k

    def close_lot(self, lot):
        lot["closed"] = True
        self.auction["gap_until"] = self.clock + 4
        w = self.players.get(lot["bidder"]) if lot["bidder"] else None
        if w and w["cash"] >= lot["bid"] and len(w["inv"]) + len(lot["entries"]) <= self.storage_cap(w):
            w["cash"] -= lot["bid"]
            w["day"]["spent"] += lot["bid"]
            w["day"]["auction"] += lot["bid"]
            w["stats"]["spent"] += lot["bid"]
            w["stats"]["auction_wins"] += 1
            share = lot["bid"] / max(1, len(lot["entries"]))
            for ent in lot["entries"]:
                w["inv"][ent["item"]["id"]] = {"item": ent["item"], "know": self.scout_know(w, ent["know"]),
                                               "paid": int(share), "days": 0, "source": "Auction", "day_in": self.day}
            lot["result"] = {"winner": w["name"], "wid": w["id"], "amount": lot["bid"]}
            self.log("SOLD! %s goes to %s for %s." % (lot["title"], w["name"], self.money(lot["bid"])), "auction")
        else:
            lot["result"] = {"winner": None}
            self.log("No sale: %s." % lot["title"], "auction")
        self.auction["results"].append({"title": lot["title"], "result": lot["result"]})

    # ------------------------------------------------------------------ evening: staff, upgrades, repairs
    def require_management(self):
        if self.phase not in ("shop", "evening"):
            raise ActionError("Not available during the auction")

    def act_upgrade(self, p, key):
        self.require_management()
        if key not in UPGRADES:
            raise ActionError("Unknown upgrade")
        lvl, costs = p["upgrades"][key], UPGRADES[key]["costs"]
        if lvl >= len(costs):
            raise ActionError("Already at max level")
        if costs[lvl] > p["cash"]:
            raise ActionError("Not enough cash")
        p["cash"] -= costs[lvl]
        p["upgrades"][key] += 1
        p["upgrade_spend"] += costs[lvl]
        p["day"]["upgrades"] += costs[lvl]
        if key == "shop" and self.phase == "shop":
            p["visitors"] += 2
            p["done"] = False
        self.note(p, "Upgraded %s to level %d." % (UPGRADES[key]["name"], lvl + 1), "good")
        return {"result": "upgraded"}

    def week_days_left(self):
        return 7 - ((max(1, self.day) - 1) % 7)

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
        due = I.nice((WAGES[stars] - (WAGES[cur["stars"]] if cur else 0)) * self.week_days_left() / 7.0)
        if due > p["cash"]:
            raise ActionError("You need %s to cover this week's wages" % self.money(due))
        p["cash"] -= due
        p["day"]["wages"] += due
        if cur:
            cur["stars"] = stars
            self.note(p, "%s promoted to %d★." % (cur["name"], stars), "good")
        else:
            name = "%s %s" % (self.rng.choice(FIRST), self.rng.choice(LAST))
            p["staff"].append({"id": self.uid("s"), "role": role, "stars": stars, "name": name, "hired": self.day})
            self.log("%s hired a %d★ %s." % (p["name"], stars, EMPLOYEES[role]["name"]))
            self.note(p, "Hired %s, %d★ %s." % (name, stars, EMPLOYEES[role]["name"]), "good")
        if role == "marketer" and self.phase == "shop":
            p["visitors"] = max(p["visitors"], self.visitors_today(p))
            p["done"] = p["vidx"] >= p["visitors"] and not p["visitor"]
        return {"result": "hired", "paid": due}

    def act_fire(self, p, staff_id):
        self.require_management()
        s = next((x for x in p["staff"] if x["id"] == staff_id), None)
        if not s:
            raise ActionError("Not on your staff")
        if s["role"] == "mechanic" and any(e.get("repair") for e in p["inv"].values()):
            raise ActionError("Your mechanic is still working on a repair")
        p["staff"].remove(s)
        self.note(p, "%s has left your shop." % s["name"])
        return {"result": "fired"}

    def payday(self, p):
        if self.day > 1 and (self.day - 1) % 7 == 0 and p["staff"]:
            wages = sum(WAGES[s["stars"]] for s in p["staff"])
            p["cash"] -= wages
            p["day"]["wages"] += wages
            self.note(p, "Payday: %s in weekly wages." % self.money(wages), "warn")

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
        base = tpl["base"] * self.mult(tpl["category"])
        cost = I.nice(base * max(0.05, I.COND_MULT[target] - I.COND_MULT[cur]) * [0, 0.45, 0.35, 0.25][s] + 300)
        days = (it["cond"] - target) * (0.6 + 0.25 * tpl["rarity"]) * [0, 1.0, 0.75, 0.5][s]
        if tpl["category"] == "cars":
            days *= 1.4
        return {"to": target, "toLabel": I.COND_LABEL[target], "cost": cost, "days": max(1, int(round(days)))}

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
        if p["visitor"] and p["visitor"].get("entry_id") == item_id:
            raise ActionError("A buyer is looking at that right now")
        q = self.repair_quote(p, e)
        if not q:
            raise ActionError("Your mechanic can't improve this item any further")
        if q["cost"] > p["cash"]:
            raise ActionError("Not enough cash for the repair")
        p["cash"] -= q["cost"]
        p["day"]["tools"] += q["cost"]
        e["know"]["cond"] = True
        e["repair"] = {"until": self.day + q["days"], "to": q["to"]}
        self.note(p, "Mechanic started on the %s — ready on day %d." % (I.CATALOG[e["item"]["tpl"]]["name"], e["repair"]["until"]))
        return {"result": "repairing", "until": e["repair"]["until"]}

    def finish_repairs(self, p):
        for e in p["inv"].values():
            e["days"] += 1 if self.day > 1 else 0
            r = e.get("repair")
            if r and self.day >= r["until"]:
                e["item"]["cond"] = min(e["item"]["cond"], r["to"])
                e["know"]["cond"] = True
                e["know"]["claimed"] = e["item"]["cond"]
                del e["repair"]
                self.note(p, "Your mechanic finished the %s — now %s!" % (I.CATALOG[e["item"]["tpl"]]["name"], I.COND_LABEL[e["item"]["cond"]]), "good")

    def analyst_forecast(self, p):
        s = self.staff_skill(p, "analyst")
        if not s:
            return None
        f = {"hot": self.next_hot}
        if s >= 2:
            f["cold"] = self.next_cold
        if s >= 3:
            f["swing"] = "+35% / -25%"
        return f

    def act_ready(self, p):
        if self.phase == "shop" and not p["done"]:
            if p["visitor"]:
                raise ActionError("Finish with the visitor at your counter first")
            p["done"] = True  # closing early: remaining visitors go home
            return {"result": "closed"}
        p["ready"] = True
        return {"result": "ready"}

    # ------------------------------------------------------------------ AI
    def ai_style(self, p):
        return AI_STYLES.get(p["style"], AI_STYLES["balanced"])

    def ai_estimate(self, p, it, know):
        key = it["id"]
        if key not in p["ai"]["est"]:
            st, mult = self.ai_style(p), self.mult(cat_of(it))
            if know["auth"] or know.get("opinion_ok"):
                base = I.true_value(it, mult)
            elif it["authentic"]:
                base = I.true_value(it, mult) if know["edition"] else I.true_value(dict(it, edition=0), mult)
                if not know["edition"] and any(h in I.TELL_RARE for h in it["hints"]):
                    base *= 1.15
            else:
                base = I.naive_value(it, it["cond"], mult)  # fooled by the fake
            est = base * (1 + self.rng.gauss(0, st["noise"]))
            if st["fav"] and cat_of(it) == st["fav"]:
                est *= 1.08
            p["ai"]["est"][key] = max(50, est)
            if len(p["ai"]["est"]) > 400:
                p["ai"]["est"] = dict(list(p["ai"]["est"].items())[-200:])
        return p["ai"]["est"][key]

    def ai_visit(self, p):
        """The computer plays one visitor for an AI dealer (or a disconnected player)."""
        if not p["visitor"]:
            if p["vidx"] >= p["visitors"]:
                p["done"] = True
                return
            self.act_next(p)
            if not p["visitor"]:
                return
        v, st = p["visitor"], self.ai_style(p)
        try:
            if v["kind"] == "seller":
                it, k = v["item"], v["know"]
                k["cond"] = True
                nv = I.naive_value(it, k["claimed"], self.mult(cat_of(it)))
                if I.CATALOG[it["tpl"]]["fakeable"] and nv >= st["scan"] and p["cash"] > self.examine_fee(p) * 4:
                    self.act_examine(p, "counter")
                est = self.ai_estimate(p, it, k)
                cap = est * st["buy"]
                if not it["authentic"] and k["auth"]:
                    cap = self.tv(it) * 0.6
                if v["reserve"] <= cap and len(p["inv"]) < self.storage_cap(p):
                    price = max(I.nice(v["reserve"] + (min(v["ask"], cap) - v["reserve"]) * self.rng.uniform(0.05, 0.35)),
                                int(math.ceil(v["reserve"])))
                    if price <= p["cash"] * 0.85:
                        self.buy(p, price)
                        return
                self.end_visitor(p, "info", "Passed on a %s." % I.CATALOG[it["tpl"]]["name"])
            else:
                e = p["inv"][v["entry_id"]]
                est = self.ai_estimate(p, e["item"], e["know"])
                floor = max(e["paid"] * 1.06, est * 0.85 * (0.95 ** e["days"]))
                if v["offer"] >= floor:
                    self.sell(p, v["offer"])
                elif v["wtp"] >= floor:
                    self.sell(p, I.nice(max(floor, (floor + v["wtp"]) / 2)))
                else:
                    self.end_visitor(p, "info", "No sale.")
        except ActionError:
            p["visitor"] = None
        if p["vidx"] >= p["visitors"] and not p["visitor"]:
            p["done"] = True

    def ai_morning(self, p):
        st = self.ai_style(p)
        days_left = self.settings["days"] - self.day
        off = [e["item"]["id"] for e in p["inv"].values() if not self.can_trade(p, cat_of(e["item"])) and not e.get("repair")]
        for iid in off:
            self.act_quick_sell(p, iid)
        while len(p["inv"]) > self.storage_cap(p) - 2:
            stored = [e for e in p["inv"].values() if not e.get("repair")]
            if not stored:
                break
            e = min(stored, key=lambda x: self.ai_estimate(p, x["item"], x["know"]))
            self.act_quick_sell(p, e["item"]["id"])
        if days_left >= 2:
            order = {"cautious": ["storage", "desk"], "roller": ["shop", "cases"], "collector": ["desk", "cases"],
                     "flipper": ["shop", "storage"], "bargain": ["storage", "shop"]}.get(p["style"], ["shop", "storage"])
            for key in order:
                lvl, costs = p["upgrades"][key], UPGRADES[key]["costs"]
                if lvl < len(costs) and p["cash"] > costs[lvl] * 2.5:
                    self.act_upgrade(p, key)
                    break
            for role in AI_HIRES.get(p["style"], ["sales"]):
                want = 2 if p["cash"] > 90000 and days_left >= 3 else 1
                if self.staff_skill(p, role) < want and p["cash"] > WAGES[want] * 3 and len(p["staff"]) < 3:
                    try:
                        self.act_hire(p, role, want)
                    except ActionError:
                        pass
                    break

    def ai_bid(self, p, lot):
        if lot["bidder"] == p["id"] or not self.lot_allowed(p, lot):
            return
        st = self.ai_style(p)
        if p["id"] not in lot["ai_caps"]:
            val = 0
            for ent in lot["entries"]:
                lo, likely, hi = I.estimate(ent["item"], ent["know"], self.mult(cat_of(ent["item"])))
                val += (0.7 * likely + 0.3 * (lo + hi) / 2) * (0.8 + 0.25 * st["risk"]) * (1 + self.rng.gauss(0, st["noise"]))
            cap = val * st["buy"] * (0.85 + 0.3 * st["risk"])
            lot["ai_caps"][p["id"]] = max(0, min(cap, p["cash"] * (0.35 + 0.3 * st["risk"])))
        nxt = self.min_bid(lot)
        if nxt <= lot["ai_caps"][p["id"]] and self.rng.random() < (0.03 if lot["ends"] - self.clock > 6 else 0.12):
            try:
                self.act_bid(p, nxt)
            except ActionError:
                pass

    # ------------------------------------------------------------------ dispatch
    def handle(self, pid, action, args, nonce=None):
        p = self.players.get(pid)
        if not p:
            raise ActionError("Unknown player")
        if nonce and nonce in p["results"]:
            return p["results"][nonce]  # duplicate request: replay, never re-apply
        if self.phase == "final":
            raise ActionError("The match is over")
        p["autopilot"] = False
        fn = {
            "next": lambda: self.act_next(p),
            "offer": lambda: self.act_offer(p, args.get("amount", 0)),
            "accept": lambda: self.act_accept(p),
            "accept_ask": lambda: self.act_accept(p),
            "pass": lambda: self.act_pass(p),
            "walk": lambda: self.act_pass(p),
            "examine": lambda: self.act_examine(p, args.get("target", "counter")),
            "opinion": lambda: self.act_opinion(p, args.get("target", "counter")),
            "quick_sell": lambda: self.act_quick_sell(p, args.get("item")),
            "bid": lambda: self.act_bid(p, args.get("amount", 0)),
            "upgrade": lambda: self.act_upgrade(p, args.get("key")),
            "hire": lambda: self.act_hire(p, args.get("role"), args.get("stars")),
            "fire": lambda: self.act_fire(p, args.get("staff")),
            "repair": lambda: self.act_repair(p, args.get("item")),
            "ready": lambda: self.act_ready(p),
        }.get(action)
        if not fn:
            raise ActionError("Unknown action")
        try:
            res = fn()
        except (TypeError, ValueError, KeyError):
            raise ActionError("Invalid input")
        self.dirty = True
        if nonce:
            p["results"][nonce] = res
            p["nonces"].append(nonce)
            if len(p["nonces"]) > 200:
                p["results"].pop(p["nonces"].pop(0), None)
        return res

    # ------------------------------------------------------------------ views (never include hidden values)
    def item_view(self, it, know):
        tpl = I.CATALOG[it["tpl"]]
        lo, li, hi = I.estimate(it, know, self.mult(tpl["category"]))
        return {
            "id": it["id"], "name": tpl["name"], "kind": tpl["kind"], "cat": tpl["category"],
            "catName": I.CATEGORIES[tpl["category"]]["name"], "variant": it["variant"], "rarity": tpl["rarity"],
            "cond": I.COND_LABEL[it["cond"]] if know["cond"] else None, "claimed": I.COND_LABEL[know["claimed"]],
            "condIdx": it["cond"] if know["cond"] else know["claimed"],
            "status": ("verified" if it["authentic"] else "replica") if know["auth"] else "unverified",
            "edition": I.EDITION_NAMES[tpl["category"]][it["edition"]] if know["edition"] else None,
            "editionIdx": it["edition"] if know["edition"] else 0, "fakeable": tpl["fakeable"],
            "low": lo, "likely": li, "high": hi, "hints": it["hints"],
            "opinion": I.nice(know["opinion"]) if know.get("opinion") else None,
            "hot": tpl["category"] == self.hot, "cold": tpl["category"] == self.cold,
        }

    def visitor_view(self, p, v):
        ment = self.staff_skill(p, "mentalist")
        out = {"kind": v["kind"], "id": v["id"], "name": v["name"], "look": v["look"], "mood": round(v["mood"]),
               "rounds": max(0, v["rounds"]), "roundsMax": v["rounds_max"], "lines": v["lines"], "final": v["final"],
               "moodExact": ment > 0}
        w = {2: 0.15, 3: 0.05}.get(ment)
        if v["kind"] == "seller":
            per = PERSONAS[v["persona"]]
            out.update({"item": self.item_view(v["item"], v["know"]), "ask": v["ask"], "lastOffer": v["last_offer"],
                        "vibe": "Friendly" if v["persona"] == "crook" and not v["flagged"] else per["vibe"],
                        "persona": per["label"] if ment else None, "flagged": v["flagged"], "lying": v["lying"]})
            if w:
                out["limit"] = [I.nice(v["reserve"] * (1 - w)), I.nice(v["reserve"] * (1 + w))]
        else:
            e = p["inv"].get(v["entry_id"])
            out.update({"item": self.item_view(e["item"], e["know"]) if e else None, "offer": v["offer"],
                        "paid": e["paid"] if e else 0, "lastAsk": v["last_ask"], "vibe": BUYERS[v["persona"]]["label"],
                        "persona": BUYERS[v["persona"]]["label"]})
            if w:
                out["limit"] = [I.nice(v["wtp"] * (1 - w)), I.nice(v["wtp"] * (1 + w))]
        return out

    def leaderboard(self):
        rows = []
        for pid in self.order:
            p = self.players.get(pid)
            if not p:
                continue
            inv = int(sum(self.book_value(e) for e in p["inv"].values()) * LIQUIDATION)
            rows.append({"id": pid, "name": p["name"], "is_ai": p["is_ai"], "cash": p["cash"], "inventory": inv,
                         "net_worth": self.net_worth(p), "rep": round(p["rep"]), "connected": p["connected"] or p["is_ai"],
                         "autopilot": p["autopilot"], "theme": p["theme"], "title": p["title"], "items": len(p["inv"]),
                         "ready": p["ready"], "done": p["done"], "dtype": p["dtype"], "vidx": p["vidx"], "visitors": p["visitors"]})
        rows.sort(key=lambda r: -r["net_worth"])
        return rows

    def view(self, pid):
        p = self.players.get(pid)
        if not p:
            return {"error": "not in match"}
        timed = self.phase_end < NEVER / 2 and self.phase in ("shop", "evening")
        v = {"you": pid, "host": self.host, "phase": self.phase, "day": self.day, "days": self.settings["days"],
             "left": max(0, round(self.phase_end - self.clock)) if timed else None, "paused": self.paused,
             "settings": self.settings, "room": self.room, "feed": self.feed[-20:], "leaderboard": self.leaderboard(),
             "types": DEALERSHIP_TYPES, "startCash": START_CASH, "history": self.history,
             "hot": self.hot, "cold": self.cold,
             "catNames": {c: I.CATEGORIES[c]["name"] for c in self.market}}
        if self.phase == "lobby":
            v["lobby"] = [{"id": x["id"], "name": x["name"], "is_ai": x["is_ai"], "title": x["title"], "theme": x["theme"],
                           "dtype": x["dtype"]} for x in (self.players[i] for i in self.order)]
            return v
        inv = []
        for e in p["inv"].values():
            iv = self.item_view(e["item"], e["know"])
            iv.update({"paid": e["paid"], "days": e["days"], "source": e["source"], "repair": e.get("repair"),
                       "repairQuote": self.repair_quote(p, e), "canSell": self.can_trade(p, cat_of(e["item"])),
                       "quick": None})
            inv.append(iv)
        inv.sort(key=lambda x: (not x["canSell"], x["name"]))
        v["me"] = {
            "cash": p["cash"], "rep": round(p["rep"], 1), "netWorth": self.net_worth(p), "dtype": p["dtype"], "cats": p["cats"],
            "inventory": inv, "storage": self.storage_cap(p), "upgrades": p["upgrades"], "staff": p["staff"],
            "maxStaff": MAX_EMPLOYEES, "visitor": self.visitor_view(p, p["visitor"]) if p["visitor"] else None,
            "vidx": p["vidx"], "visitors": p["visitors"], "done": p["done"], "last": p["last"], "ready": p["ready"],
            "notes": p["notes"], "day": p["day"], "stats": p["stats"], "examineFee": self.examine_fee(p),
            "expertLeft": max(0, [0, 4, 8, 999][self.staff_skill(p, "expert")] - p["expert_used"]),
            "forecast": p["forecast"], "theme": p["theme"], "decor": p["decor"], "autopilot": p["autopilot"],
        }
        v["upgrades"], v["employees"], v["wages"], v["weekDaysLeft"] = UPGRADES, EMPLOYEES, WAGES, self.week_days_left()
        v["waiting"] = [x["name"] for x in self.players.values() if not x["done"]] if self.phase == "shop" else \
            [x["name"] for x in self.humans() if not x["ready"]] if self.phase == "evening" else []
        if self.phase == "auction" and self.auction:
            a, lot = self.auction, self.auction["lot"]
            av = {"index": a["idx"], "count": len(a["lots"]), "results": a["results"],
                  "upcoming": [l["title"] for l in a["lots"][max(0, a["idx"] + 1):]]}
            if lot:
                av["lot"] = {"id": lot["id"], "title": lot["title"], "low": lot["low"], "high": lot["high"],
                             "items": [self.item_view(x["item"], self.scout_know(p, x["know"])) for x in lot["entries"]],
                             "scouted": self.staff_skill(p, "scout"), "start": lot["start"], "bid": lot["bid"],
                             "bidder": lot["bidder"], "bidderName": self.players[lot["bidder"]]["name"] if lot["bidder"] in self.players else None,
                             "bids": lot["bids"], "left": max(0, round(lot["ends"] - self.clock, 1)), "closed": lot["closed"],
                             "minBid": self.min_bid(lot), "seller": None, "result": lot.get("result"),
                             "allowed": self.lot_allowed(p, lot)}
            v["auction"] = av
        if self.phase in ("evening", "final"):
            v["report"] = self.report.get(pid)
        if self.final:
            v["final"] = self.final
        return v

    # ------------------------------------------------------------------ persistence
    def to_dict(self):
        d = {k: getattr(self, k) for k in self.SAVE_FIELDS}
        st = self.rng.getstate()
        d["rng"] = [st[0], list(st[1]), st[2]]
        d["version"] = 2
        return d

    @classmethod
    def from_dict(cls, d):
        if d.get("version") != 2:
            raise ValueError("This save is from an older version of the game")
        m = cls(d["room"], d["settings"])
        for k in cls.SAVE_FIELDS:
            if k in d:
                setattr(m, k, d[k])
        r = d["rng"]
        m.rng.setstate((r[0], tuple(r[1]), r[2]))
        hi = 0
        for p in m.players.values():
            p["connected"] = p["is_ai"]
            for iid in p["inv"]:
                try:
                    hi = max(hi, int(iid[2:]))
                except ValueError:
                    pass
        I.bump_ids(hi + 100000)
        return m
