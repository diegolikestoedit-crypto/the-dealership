"""End-to-end multiplayer test over real HTTP + SSE against a live server process.

Spawns its own server (fast clock, temp data dir), connects 3 human clients + 2 AI seats,
then exercises lobby, sync, racing transactions, duplicate requests, disconnect/autopilot and
reconnection all the way to final results.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8711
BASE = "http://127.0.0.1:%d" % PORT
FAIL = []


def check(c, msg):
    print(("  ok   " if c else "  FAIL ") + msg)
    if not c:
        FAIL.append(msg)


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


class Client:
    def __init__(self, name):
        self.name = name
        self.view = None
        self.sess = None
        self.stop = False
        self.thread = None
        self.updates = 0

    def stream(self):
        url = "%s/api/stream?room=%s&token=%s" % (BASE, self.sess["room"], self.sess["token"])
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                for raw in r:
                    if self.stop:
                        break
                    line = raw.decode().strip()
                    if line.startswith("data: "):
                        self.view = json.loads(line[6:])
                        self.updates += 1
        except Exception:
            pass

    def connect(self):
        self.stop = False
        self.thread = threading.Thread(target=self.stream, daemon=True)
        self.thread.start()

    def disconnect(self):
        self.stop = True

    def act(self, action, args=None, nonce=None):
        return post("/api/action", {"room": self.sess["room"], "token": self.sess["token"], "action": action,
                                    "args": args or {}, "nonce": nonce})


def wait(pred, timeout=60, step=0.1):
    t = time.time()
    while time.time() - t < timeout:
        try:
            if pred():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def main():
    data = tempfile.mkdtemp(prefix="dealer-mp-")
    env = dict(os.environ, DEALERSHIP_DATA=data, DEALERSHIP_TIMESCALE="10")
    srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server", "server.py"), "--port", str(PORT), "--no-browser"],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        wait(lambda: json.loads(urllib.request.urlopen(BASE + "/api/info", timeout=1).read()), 10)
        print("Lobby")
        a, b, c = Client("Alice"), Client("Bob"), Client("Cara")
        r = post("/api/create", {"name": "Alice", "settings": {"name": "Test", "days": 3, "pace": "quick", "max_players": 5}})
        check(r["ok"], "host creates room")
        a.sess = r
        code = r["room"]
        rooms = json.loads(urllib.request.urlopen(BASE + "/api/rooms").read())["rooms"]
        check(any(x["code"] == code for x in rooms), "room appears in browser")
        b.sess = post("/api/join", {"room": code, "name": "Bob", "my_type": "music"})
        c.sess = post("/api/join", {"room": code, "name": "Cara"})
        check(b.sess["ok"] and c.sess["ok"], "two players join by code")
        for cl in (a, b, c):
            cl.connect()
        check(wait(lambda: all(cl.view and len(cl.view.get("lobby", [])) == 3 for cl in (a, b, c)), 5), "lobby synced to all clients")
        r = post("/api/lobby", {"room": code, "token": b.sess["token"], "op": "start"})
        check(not r.get("ok"), "non-host cannot start")
        post("/api/lobby", {"room": code, "token": a.sess["token"], "op": "add_bot"})
        post("/api/lobby", {"room": code, "token": a.sess["token"], "op": "add_bot"})
        r = post("/api/lobby", {"room": code, "token": a.sess["token"], "op": "add_bot"})
        check(r.get("ok") is False, "room capacity enforced (5)")
        print("Dealership types")
        check({p["name"]: p["dtype"] for p in a.view["lobby"]}.get("Bob") == "music", "type picked on the Join screen is applied")
        post("/api/lobby", {"room": code, "token": b.sess["token"], "op": "set_type", "dtype": "cars"})
        post("/api/lobby", {"room": code, "token": c.sess["token"], "op": "set_type", "dtype": "gallery"})
        r = post("/api/lobby", {"room": code, "token": b.sess["token"], "op": "set_type", "pid": c.sess["pid"], "dtype": "tech"})
        check(r.get("ok") is False, "players can't change someone else's type")
        check(wait(lambda: {p["name"]: p["dtype"] for p in a.view["lobby"]}.get("Bob") == "cars", 3), "chosen types sync to lobby")
        post("/api/lobby", {"room": code, "token": a.sess["token"], "op": "settings", "settings": {"type_rule": "relics"}})
        r = post("/api/lobby", {"room": code, "token": b.sess["token"], "op": "set_type", "dtype": "cars"})
        check(r.get("ok") is False, "forced rule blocks personal choice")
        post("/api/lobby", {"room": code, "token": a.sess["token"], "op": "settings", "settings": {"type_rule": "free"}})
        post("/api/lobby", {"room": code, "token": a.sess["token"], "op": "start"})
        check(wait(lambda: all(cl.view and cl.view["phase"] == "shop" for cl in (a, b, c)), 5), "match start synced")
        check(b.view["me"]["dtype"] == "cars" and b.view["me"]["cats"] == ["cars"], "Bob runs a car dealership")
        check(c.view["me"]["dtype"] == "gallery", "Cara runs an art gallery")
        cash = [cl.view["me"]["cash"] for cl in (a, b, c)]
        check(len(set(cash)) == 1 and cash[0] == 25000, "identical starting capital")

        print("Staff hiring under racing requests")
        res = {}

        def hire(n):
            res[n] = post("/api/action", {"room": code, "token": a.sess["token"], "action": "hire", "args": {"role": "mechanic", "stars": 1}})
        ts = [threading.Thread(target=hire, args=(n,)) for n in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        check(sum(1 for v in res.values() if v.get("ok")) == 1, "4 simultaneous hire clicks -> hired once, charged once")
        check(wait(lambda: a.view["me"]["cash"] == 25000 - 2000, 3), "week's wage charged exactly once")

        print("Latency")
        lat = []
        for i in range(5):
            t0 = time.time()
            prev = a.view["me"]["notes"][-1]["n"] if a.view["me"]["notes"] else 0
            a.act("upgrade", {"key": "desk"})
            lat.append(time.time() - t0)
            break
        t0 = time.time()
        before = len(a.view["me"]["staff"])
        a.act("hire", {"role": "negotiator", "stars": 1})
        wait(lambda: len(a.view["me"]["staff"]) > before, 3, 0.005)
        ms = (time.time() - t0) * 1000
        print("  action -> updated screen: %.0f ms" % ms)
        check(ms < 400, "actions show up on screen in under 0.4s")

        print("Remote friends' privacy")
        def raw(path, body=None, headers=None):
            req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers=dict({"Content-Type": "application/json"}, **(headers or {})))
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                return json.loads(e.read())
        fwd = {"X-Forwarded-For": "8.8.8.8"}
        check("error" in raw("/api/profile", headers=fwd), "tunnelled visitor without id can't read the host profile")
        pr = raw("/api/profile?profile=friend12345", headers=fwd)
        check(pr.get("name") == "Player" and pr.get("xp") == 0, "each friend gets their own fresh profile")
        raw("/api/profile", {"profile": "friend12345", "name": "Friendo"}, fwd)
        check(raw("/api/profile?profile=friend12345", headers=fwd).get("name") == "Friendo", "friend profile saves")
        check(raw("/api/profile").get("name") != "Friendo", "host profile untouched")
        check(raw("/api/quit", {}, fwd).get("ok") is False, "friends can't shut down the host's game")

        print("Compressed stream")
        import zlib as _z
        req = urllib.request.Request("%s/api/stream?room=%s&token=%s" % (BASE, code, c.sess["token"]), headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=10) as r:
            check(r.headers.get("Content-Encoding") == "gzip", "stream is gzip-encoded when the browser accepts it")
            d = _z.decompressobj(31)
            got, raw_n, txt = 0, 0, ""
            t0 = time.time()
            while got < 6 and time.time() - t0 < 6:
                chunk = r.read1(65536) if hasattr(r, "read1") else r.read(4096)
                raw_n += len(chunk)
                txt += d.decompress(chunk).decode()
                got = txt.count("\n\n")
            plain = len(txt.encode())
        print("  %d messages: %d KB raw -> %d KB on the wire" % (got, plain // 1024, raw_n // 1024))
        check(got >= 3 and raw_n < plain / 3, "compressed stream decodes and is >3x smaller")

        print("Counter")
        for cl in (a, b, c):
            cl.act("next")
        check(wait(lambda: all(cl.view["me"]["visitor"] for cl in (a, b, c)), 5), "every dealer gets their first visitor")
        check(b.view["me"]["visitor"]["item"]["cat"] == "cars", "car dealer's first seller brings a vehicle")
        check(c.view["me"]["visitor"]["item"]["cat"] in ("art", "furniture"), "gallery sellers bring art/furniture")
        before = a.view["me"]["cash"]
        r1 = a.act("examine", {}, nonce="dup-1")
        r2 = a.act("examine", {}, nonce="dup-1")
        check(r1 == r2, "duplicate request returns cached result")
        check(wait(lambda: a.view["me"]["cash"] == before - r1["res"]["cost"], 3), "charged exactly once")
        blob = json.dumps(b.view)
        check('"reserve"' not in blob and '"authentic"' not in blob and '"wtp"' not in blob, "views don't leak hidden values")
        res = {}

        def accept(n):
            res[n] = a.act("accept")
        ts = [threading.Thread(target=accept, args=(n,)) for n in range(3)]
        [x.start() for x in ts]
        [x.join() for x in ts]
        okn = sum(1 for v in res.values() if v.get("ok"))
        check(okn <= 1, "triple-clicking Buy buys once")
        if okn:
            check(wait(lambda: len(a.view["me"]["inventory"]) == 1, 3), "bought item lands in stock once")
        # everyone serves the rest of their visitors (pass on everything)
        def serve(cl):
            me = cl.view["me"]
            if me["done"]:
                return True
            if me["visitor"]:
                cl.act("pass")
                if cl.view["me"]["visitor"]:
                    cl.act("pass")
            else:
                cl.act("next")
            return False

        print("Disconnect / autopilot / reconnect")
        c.disconnect()
        check(wait(lambda: any(r["id"] == c.sess["pid"] and r["autopilot"] for r in a.view["leaderboard"]), 30), "dropped player goes on autopilot")
        c.connect()
        check(wait(lambda: c.view and not any(r["id"] == c.sess["pid"] and r["autopilot"] for r in a.view["leaderboard"]), 10), "reconnected player regains control")
        check(wait(lambda: all(serve(cl) for cl in (a, b, c)), 120, 0.05), "all dealers finish their visitors")

        print("Auction")
        check(wait(lambda: a.view["phase"] == "auction" and a.view.get("auction", {}).get("lot") and not a.view["auction"]["lot"]["closed"], 60), "auction opens")
        lot = a.view["auction"]["lot"]
        amt = lot["minBid"]
        res = {}

        def bid(cl):
            res[cl.name] = cl.act("bid", {"amount": amt})
        ts = [threading.Thread(target=bid, args=(cl,)) for cl in (a, b, c)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        okn = sum(1 for v in res.values() if v.get("ok"))
        reasons = [v.get("error", "") for v in res.values() if not v.get("ok")]
        eligible_fail = all(("trade" in r or "cover" in r or "storage" in r) for r in reasons)
        check(okn == 1 or (okn == 0 and eligible_fail), "simultaneous identical bids: at most one accepted, losers rejected cleanly")
        if okn == 0:
            print("   (nobody eligible for this lot: %s)" % "; ".join(sorted(set(reasons))))
        idx = a.view["auction"]["index"]
        done = lambda cl: cl.view.get("auction") and len(cl.view["auction"]["results"]) > idx
        check(wait(lambda: all(done(cl) for cl in (a, b, c)), 30), "lot closes for every client")
        results = [json.dumps(cl.view["auction"]["results"][idx]) for cl in (a, b, c)]
        check(len(set(results)) == 1, "all clients agree on the lot result")
        winner = a.view["auction"]["results"][idx]["result"]
        if okn:
            check(winner.get("winner") is not None, "a bidder won the contested lot")

        print("Run to the end")
        def readyall():
            for cl in (a, b, c):
                if cl.view and cl.view["phase"] == "evening" and not cl.view["me"]["ready"]:
                    cl.act("ready")
                elif cl.view and cl.view["phase"] == "shop":
                    serve(cl)
            return a.view["phase"] == "final"
        check(wait(readyall, 240, 0.3), "match reaches final results")
        f = a.view["final"]
        check(len(f["rows"]) == 5 and [r["place"] for r in f["rows"]] == [1, 2, 3, 4, 5], "final standings ranked")
        check(all(r["net_worth"] == r["cash"] + r["inventory"] + r["assets"] for r in f["rows"]), "net worth formula consistent")
        check(json.dumps(b.view["final"]) == json.dumps(f), "all clients see identical final results")
        r = a.act("offer", {"amount": 10})
        check(r.get("ok") is False, "actions rejected after match end")
        print("updates received:", a.updates, b.updates, c.updates)
    finally:
        srv.terminate()
        out = srv.communicate(timeout=5)[0].decode()
        if "Traceback" in out:
            print(out)
            FAIL.append("server traceback")
    print("\nRESULT:", "FAIL (%d)" % len(FAIL) if FAIL else "ALL MULTIPLAYER CHECKS PASSED")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
