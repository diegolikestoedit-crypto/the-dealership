"""Headless tests for the counter-loop game: full matches, invariants, exploits, types, staff, save/load, balance."""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from game import Match, ActionError, LIQUIDATION  # noqa: E402
import items as I  # noqa: E402

FAIL = []


def check(cond, msg):
    if not cond:
        FAIL.append(msg)
        print("FAIL:", msg)


def est(m, it, k):
    return I.estimate(it, k, m.mult(I.CATALOG[it["tpl"]]["category"]))[1]


def human_turn(m, h):
    """A sensible scripted player using only the real action API."""
    p = m.players[h]
    try:
        if m.phase == "shop" and not p["done"]:
            v = p["visitor"]
            if not v:
                m.handle(h, "next", {})
            elif v["kind"] == "seller":
                it, k = v["item"], v["know"]
                li = est(m, it, k)
                if not k["auth"] and li > 5000 and p["cash"] > 5000:
                    m.handle(h, "examine", {})
                elif k["auth"] and not it["authentic"]:
                    m.handle(h, "pass", {})
                elif v["ask"] <= li * 0.7 and v["ask"] <= p["cash"]:
                    m.handle(h, "accept", {})
                elif v["rounds"] > 0 and not v["final"] and li * 0.6 < p["cash"]:
                    m.handle(h, "offer", {"amount": int(min(p["cash"], li * 0.6 if not v["last_offer"] else min(li * 0.7, v["last_offer"] * 1.1)))})
                else:
                    m.handle(h, "pass", {})
                    if p["visitor"]:
                        m.handle(h, "pass", {})
            else:
                e = p["inv"][v["entry_id"]]
                li = est(m, e["item"], e["know"])
                if v["offer"] >= max(e["paid"] * 1.1, li * 0.95):
                    m.handle(h, "accept", {})
                elif v["rounds"] > 0 and not v["final"]:
                    m.handle(h, "offer", {"amount": int(max(li * 1.15, e["paid"] * 1.2))})
                elif v["offer"] > e["paid"]:
                    m.handle(h, "accept", {})
                else:
                    m.handle(h, "pass", {})
        elif m.phase == "auction" and m.auction and m.auction["lot"] and not m.auction["lot"]["closed"]:
            lot = m.auction["lot"]
            if lot["bidder"] != h and m.min_bid(lot) < lot["likely"] * 0.55 and random.random() < 0.1:
                m.handle(h, "bid", {"amount": m.min_bid(lot)}, nonce="b%d" % random.randrange(1 << 30))
        elif m.phase == "evening" and not p["ready"]:
            if p["cash"] > 20000 and not p["staff"]:
                m.handle(h, "hire", {"role": "negotiator", "stars": 1})
            m.handle(h, "ready", {})
    except ActionError:
        pass


def invariants(m):
    seen = set()
    for p in m.players.values():
        for iid, e in p["inv"].items():
            check(iid == e["item"]["id"], "inventory key mismatch")
            check(iid not in seen, "duplicate item %s" % iid)
            seen.add(iid)
        check(len(p["inv"]) <= m.storage_cap(p), "%s over storage" % p["name"])
        check(p["vidx"] <= p["visitors"], "visitor counter overflow")
        check(0 <= p["rep"] <= 100, "rep range")


def run_match(seed, bots=4, days=5, my_type="general", **extra):
    st = {"days": days, "solo": True, "pace": "quick"}
    st.update(extra)
    m = Match("T", st, seed=seed)
    h = m.add_human("Tester", "tok")["id"]
    if m.settings["type_rule"] == "free":
        m.set_type(m.players[h], my_type)
    for _ in range(bots):
        m.add_bot()
    m.start()
    random.seed(seed)
    steps = 0
    while m.phase != "final" and steps < 200000:
        m.tick(0.5)
        p = m.players[h]
        p["connected"], p["last_seen"] = True, m.clock
        human_turn(m, h)
        steps += 1
        if steps % 40 == 0:
            invariants(m)
            json.dumps(m.view(h))
        if steps == 600:
            d = json.loads(json.dumps(m.to_dict()))
            m2 = Match.from_dict(d)
            check(m2.day == m.day and m2.phase == m.phase, "save/load roundtrip")
    check(m.phase == "final", "match did not finish (seed %d, phase %s)" % (seed, m.phase))
    for r in m.final["rows"]:
        check(r["net_worth"] == r["cash"] + r["inventory"] + r["assets"], "net worth formula")
    return m


def test_counter_rules():
    m = Match("X", {"days": 3, "solo": True}, seed=2)
    h = m.add_human("H", "t")["id"]
    m.add_bot()
    m.start()
    p = m.players[h]
    check(m.phase == "shop" and p["visitor"] is None, "day starts at an empty counter")
    m.handle(h, "next", {})
    v = p["visitor"]
    check(v and v["kind"] == "seller", "first visitor is a seller (no stock yet)")
    for bad in (-5, 0, 10 ** 9, "abc"):
        try:
            m.handle(h, "offer", {"amount": bad})
            check(False, "accepted bad offer %r" % bad)
        except ActionError:
            pass
    try:
        m.handle(h, "next", {})
        check(False, "skipped a visitor mid-negotiation")
    except ActionError:
        pass
    c0 = p["cash"]
    m.handle(h, "examine", {}, nonce="dup")
    m.handle(h, "examine", {}, nonce="dup")
    check(c0 - p["cash"] == 300, "examine charged once ($300)")
    p["cash"] = 10 ** 7
    m.handle(h, "accept", {})
    check(len(p["inv"]) == 1 and p["visitor"] is None and p["last"]["outcome"] == "good", "buying moves item to stock")
    # make the next visitor a buyer and sell to them
    for _ in range(30):
        m.handle(h, "next", {})
        if p["visitor"]["kind"] == "buyer":
            break
        m.handle(h, "pass", {})
        if p["visitor"]:
            m.handle(h, "pass", {})
    if p["visitor"] and p["visitor"]["kind"] == "buyer":
        c1, offer = p["cash"], p["visitor"]["offer"]
        m.handle(h, "accept", {})
        check(p["cash"] == c1 + offer or p["cash"] == c1 + I.nice(offer * 1.1), "selling pays the buyer's offer")
        check(len(p["inv"]) == 0, "sold item leaves stock")
    # closing early ends your day
    p["visitor"] = None
    m.handle(h, "ready", {})
    check(p["done"], "closing the shop early marks you done")
    for _ in range(4000):
        m.tick(0.5)
        if m.phase == "auction" and m.auction["lot"] and not m.auction["lot"]["closed"]:
            break
    check(m.phase == "auction", "day moves to the auction when everyone is done")
    lot = m.auction["lot"]
    for x in m.players.values():
        if x["is_ai"]:
            x["cash"] = 0
    p["cash"] = 10 ** 6
    try:
        m.handle(h, "bid", {"amount": lot["start"] - 1})
        check(False, "accepted a low bid")
    except ActionError:
        pass
    if m.lot_allowed(p, lot):
        m.handle(h, "bid", {"amount": m.min_bid(lot)})
        before, bid = p["cash"], lot["bid"]
        while not lot["closed"]:
            m.tick(0.25)
        check(p["cash"] == before - bid, "auction charges exactly the winning bid")
    print("counter rules done")


def test_types_and_staff():
    from content import WAGES
    m = Match("Y", {"days": 9, "solo": True, "rivals": "general"}, seed=3)
    h = m.add_human("H", "t")["id"]
    m.set_type(m.players[h], "cars")
    m.add_bot()
    m.start()
    p = m.players[h]
    check(p["cats"] == ["cars"], "car dealer trades only vehicles")
    m.handle(h, "next", {})
    check(I.CATALOG[p["visitor"]["item"]["tpl"]]["category"] == "cars", "car dealer's sellers bring vehicles")
    p["cash"] = 200000
    c0 = p["cash"]
    m.handle(h, "hire", {"role": "mechanic", "stars": 1})
    check(c0 - p["cash"] == WAGES[1], "day-1 hire pays a full week")
    for r in ("mentalist", "expert", "scout"):
        m.handle(h, "hire", {"role": r, "stars": 2})
    try:
        m.handle(h, "hire", {"role": "lucky", "stars": 1})
        check(False, "hired a 5th employee")
    except ActionError:
        pass
    check("limit" in m.view(h)["me"]["visitor"], "2-star mentalist shows the seller's limit")
    it = I.make_item(m.rng, "v_sedan", condition=5)
    k = I.new_knowledge(5)
    k["cond"] = True
    p["inv"][it["id"]] = {"item": it, "know": k, "paid": 1000, "days": 0, "source": "t", "day_in": 1}
    m.handle(h, "repair", {"item": it["id"]})
    until = p["inv"][it["id"]]["repair"]["until"]
    guard = 0
    while m.day < until and m.phase != "final" and guard < 50000:
        guard += 1
        m.tick(0.5)
        if m.phase == "shop" and not p["done"]:
            if p["visitor"]:
                m.handle(h, "pass", {})
                if p["visitor"]:
                    m.handle(h, "pass", {})
            else:
                m.handle(h, "ready", {})
        if m.phase == "evening":
            m.handle(h, "ready", {})
    check(p["inv"][it["id"]]["item"]["cond"] == 2 and "repair" not in p["inv"][it["id"]], "repair completes on schedule")
    wrong_rare = wrong_common = 0
    m.phase = "evening"
    for i in range(300):
        for tpl, ed, bucket in (("w_tourb", 2, "r"), ("f_stool", 0, "c")):
            item = I.make_item(m.rng, tpl, authentic=True, edition=ed)
            p["expert_used"] = 0
            p["inv"][item["id"]] = {"item": item, "know": I.new_knowledge(item["cond"]), "paid": 0, "days": 0, "source": "t", "day_in": 1}
            m.staff_skill = (lambda pp, role, _o=m.staff_skill: 1 if role == "expert" else _o(pp, role))
            m.handle(h, "opinion", {"target": item["id"]})
            if not p["inv"][item["id"]]["know"]["opinion_ok"]:
                if bucket == "r":
                    wrong_rare += 1
                else:
                    wrong_common += 1
            del p["inv"][item["id"]]
    print("  1-star expert wrong: rare %.0f%%, common %.0f%%" % (wrong_rare / 3, wrong_common / 3))
    check(25 < wrong_rare / 3 < 55 and wrong_common / 3 < 12, "expert fallibility matches spec")
    print("types & staff done")


if __name__ == "__main__":
    test_counter_rules()
    test_types_and_staff()
    from content import DEALERSHIP_TYPES
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    by = collections.defaultdict(list)
    places = []
    for i, dt in enumerate(DEALERSHIP_TYPES):
        for s in range(n):
            m = run_match(100 + 13 * s + i, my_type=dt, rivals="mix")
            for r in m.final["rows"]:
                by[("YOU:" if not r["is_ai"] else "AI:") + r["dtype"]].append(r["net_worth"])
                if not r["is_ai"]:
                    places.append(r["place"])
    m = run_match(7, type_rule="cars")
    print("Average final net worth (start $25,000):")
    for k, v in sorted(by.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        print("  %-18s %8d  n=%d" % (k, sum(v) / len(v), len(v)))
    print("scripted player placings:", collections.Counter(places))
    print("\nRESULT:", "FAIL (%d)" % len(FAIL) if FAIL else "ALL CHECKS PASSED")
    sys.exit(1 if FAIL else 0)
