"""The Dealership game server: static client, lobbies, authoritative matches, SSE state sync.

Zero third-party dependencies (Python 3.8+ standard library only).
Run:  python3 server.py [--port 8642] [--no-browser]
"""
import argparse
import json
import os
import re
import zlib
import secrets
import socket
import string
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game import Match, ActionError  # noqa: E402
from profile import ProfileStore  # noqa: E402
from content import DEALERSHIP_TYPES  # noqa: E402

VERSION = "1.0.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(ROOT, "client")
if sys.platform == "darwin":
    DATA = os.path.expanduser("~/Library/Application Support/TheDealership")
elif os.name == "nt":
    DATA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TheDealership")
else:
    DATA = os.path.expanduser("~/.thedealership")
DATA = os.environ.get("DEALERSHIP_DATA", DATA)
IDLE_EXIT = 0  # seconds; set by --exit-when-idle
# Hosted as a website (Render, Railway, Fly... all set $PORT): no desktop extras, sensible limits.
CLOUD = bool(os.environ.get("PORT"))
MAX_ROOMS = 300
MAX_PROFILES = 20000
STATE = {"seen_client": False, "idle_since": time.time()}
TIMESCALE = float(os.environ.get("DEALERSHIP_TIMESCALE", "1"))  # dev/QA only: speeds up the clock
PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]{8,40}$")


def save_path(owner=None):
    """Solo save file: the host's own, or one per remote player's browser profile."""
    if owner:
        return os.path.join(DATA, "profiles", "save_%s.json" % owner)
    return os.path.join(DATA, "solo_save.json")


profile_stores = {}


def profile_store(owner=None):
    if not owner:
        return profiles
    if owner not in profile_stores:
        pdir = os.path.join(DATA, "profiles")
        if not os.path.exists(os.path.join(pdir, "profile_%s.json" % owner)) and os.path.isdir(pdir) \
                and len(os.listdir(pdir)) > MAX_PROFILES:
            raise ActionError("This server is full right now")
        profile_stores[owner] = ProfileStore(os.path.join(DATA, "profiles"), "profile_%s.json" % owner)
    return profile_stores[owner]

profiles = None
rooms = {}
rooms_lock = threading.Lock()


class Room:
    def __init__(self, code, match):
        self.code = code
        self.match = match
        self.lock = threading.RLock()
        self.cond = threading.Condition(self.lock)
        self.tokens = {}  # token -> pid
        self.conns = {}  # pid -> open stream count
        self.touched = time.time()
        self.last_day_saved = 0
        self.owner = None  # profile id of the solo player (None = the host machine's own profile)


def new_code():
    while True:
        c = "".join(secrets.choice(string.ascii_uppercase.replace("O", "").replace("I", "")) for _ in range(4))
        if c not in rooms:
            return c


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def save_solo(room):
    m = room.match
    if not m.settings.get("solo") or m.phase in ("lobby",):
        return
    path = save_path(room.owner)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if m.phase == "final":
            if os.path.exists(path):
                os.remove(path)
            return
        d = {"match": m.to_dict(), "tokens": room.tokens, "saved": time.time()}
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, path)
    except OSError as e:
        print("save failed:", e)


def ticker():
    last = time.time()
    while True:
        time.sleep(0.2)
        now = time.time()
        dt = min(1.0, now - last) * TIMESCALE
        last = now
        with rooms_lock:
            rs = list(rooms.values())
        for r in rs:
            with r.lock:
                m = r.match
                for pid, n in r.conns.items():
                    if pid in m.players:
                        p = m.players[pid]
                        p["connected"] = n > 0
                        if n > 0:
                            p["last_seen"] = m.clock
                try:
                    m.tick(dt)
                except Exception as e:  # never let one room kill the server
                    import traceback
                    traceback.print_exc()
                    m.log("Server error recovered: %s" % e, "warn")
                # Autosave solo games at the start of each morning (between days).
                if m.settings.get("solo") and m.phase == "morning" and r.last_day_saved != m.day:
                    r.last_day_saved = m.day
                    save_solo(r)
                if m.phase == "final" and r.last_day_saved != -1 and m.settings.get("solo"):
                    r.last_day_saved = -1
                    save_solo(r)
                if m.dirty:
                    m.dirty = False
                    r.cond.notify_all()
        # Launched from the app bundle: shut down once the game window has been closed a while.
        if IDLE_EXIT:
            open_streams = sum(sum(r.conns.values()) for r in rs)
            if open_streams:
                STATE["seen_client"] = True
                STATE["idle_since"] = now
            elif STATE["seen_client"] and now - STATE["idle_since"] > IDLE_EXIT:
                for r in rs:
                    with r.lock:
                        if r.match.settings.get("solo") and r.match.phase not in ("lobby", "final"):
                            save_solo(r)
                os._exit(0)
        # cleanup idle rooms
        with rooms_lock:
            for code in list(rooms):
                r = rooms[code]
                if sum(r.conns.values()) == 0 and now - r.touched > 1800:
                    del rooms[code]


class GameServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, TimeoutError)):
            return  # a client closing its connection is normal (tab closed, network drop)
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Dealership/" + VERSION

    def log_message(self, fmt, *args):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def is_local(self):
        """The person sitting at the host computer (not a friend coming in through a tunnel or LAN)."""
        if self.client_address[0] not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            return False
        if self.headers.get("X-Forwarded-For") or self.headers.get("Forwarded") or self.headers.get("X-Real-IP"):
            return False
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("localhost", "127.0.0.1", "[::1]", "")

    def owner(self, pid):
        """Which profile a request belongs to: None for the host, else the browser's own profile id."""
        if self.is_local():
            return None
        if not pid or not PROFILE_ID.match(str(pid)):
            raise ActionError("Missing profile id")
        return str(pid)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 200000:
            raise ActionError("Request too large")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            raise ActionError("Bad JSON")

    # -------------------------------------------------------------- GET
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/stream":
            return self.stream(parse_qs(u.query))
        if u.path == "/api/info":
            return self.send_json({"version": VERSION, "ip": lan_ip(), "port": self.server.server_address[1], "types": DEALERSHIP_TYPES})
        if u.path == "/api/rooms":
            out = []
            with rooms_lock:
                rs = list(rooms.values())
            for r in rs:
                m = r.match
                if m.phase == "lobby" and m.settings["public"] and not m.settings["solo"]:
                    out.append({"code": r.code, "name": m.settings["name"], "players": len(m.players),
                                "max": m.settings["max_players"], "days": m.settings["days"],
                                "host": m.players[m.host]["name"] if m.host in m.players else "?"})
            return self.send_json({"rooms": out})
        q = parse_qs(u.query)
        if u.path == "/api/profile":
            try:
                return self.send_json(profile_store(self.owner((q.get("profile") or [""])[0])).public())
            except ActionError as e:
                return self.send_json({"error": str(e)}, 400)
        if u.path == "/api/save":
            try:
                path = save_path(self.owner((q.get("profile") or [""])[0]))
            except ActionError:
                return self.send_json({"exists": False})
            info = {"exists": os.path.exists(path)}
            if info["exists"]:
                try:
                    with open(path) as f:
                        d = json.load(f)
                    info.update(day=d["match"]["day"], days=d["match"]["settings"]["days"], saved=d["saved"])
                except (OSError, ValueError, KeyError):
                    info = {"exists": False, "corrupt": True}
            return self.send_json(info)
        return self.static(u.path)

    def static(self, path):
        if path == "/":
            path = "/index.html"
        full = os.path.normpath(os.path.join(CLIENT, path.lstrip("/")))
        if not full.startswith(CLIENT) or not os.path.isfile(full):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        ext = os.path.splitext(full)[1]
        ctype = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json"}.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def stream(self, q):
        code = (q.get("room") or [""])[0]
        token = (q.get("token") or [""])[0]
        r = rooms.get(code)
        if not r or token not in r.tokens:
            return self.send_json({"error": "Invalid room or session"}, 404)
        pid = r.tokens[token]
        gz = "gzip" in (self.headers.get("Accept-Encoding") or "")
        comp = zlib.compressobj(6, zlib.DEFLATED, 31) if gz else None  # one stream: repeats compress to ~nothing
        self.send_response(200)
        self.cors()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        if gz:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        with r.lock:
            r.conns[pid] = r.conns.get(pid, 0) + 1
            if pid in r.match.players:
                r.match.players[pid]["connected"] = True
                r.match.players[pid]["last_seen"] = r.match.clock
            r.match.dirty = True
        last_sent = 0
        last_payload = None
        try:
            while True:
                with r.cond:
                    r.cond.wait(timeout=1.0)
                    if r.code not in rooms or pid not in r.match.players:
                        payload = json.dumps({"kicked": True})
                    else:
                        payload = json.dumps(r.match.view(pid))
                    r.touched = time.time()
                now = time.time()
                if payload == last_payload and now - last_sent < 5:
                    continue  # nothing changed: skip (a keep-alive copy goes out every 5s)
                if now - last_sent < 0.12:
                    time.sleep(0.12 - (now - last_sent))
                msg = ("data: %s\n\n" % payload).encode()
                if comp:
                    msg = comp.compress(msg) + comp.flush(zlib.Z_SYNC_FLUSH)
                self.wfile.write(msg)
                self.wfile.flush()
                last_sent = time.time()
                last_payload = payload
                if '"kicked"' in payload[:20]:
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with r.lock:
                r.conns[pid] = max(0, r.conns.get(pid, 1) - 1)
                if pid in r.match.players and r.conns[pid] == 0:
                    r.match.players[pid]["connected"] = False
                    r.match.players[pid]["last_seen"] = r.match.clock
                r.match.dirty = True

    # -------------------------------------------------------------- POST
    def do_POST(self):
        u = urlparse(self.path)
        try:
            b = self.body()
            fn = {
                "/api/create": self.create, "/api/join": self.join, "/api/rejoin": self.rejoin,
                "/api/lobby": self.lobby, "/api/action": self.action, "/api/pause": self.pause,
                "/api/leave": self.leave, "/api/profile": self.profile_update,
                "/api/profile/award": self.award, "/api/resume": self.resume, "/api/quit": self.quit,
            }.get(u.path)
            if not fn:
                return self.send_json({"error": "Not found"}, 404)
            return fn(b)
        except ActionError as e:
            return self.send_json({"ok": False, "error": str(e)})

    def room_for(self, b):
        r = rooms.get(str(b.get("room", "")).upper())
        if not r:
            raise ActionError("Room not found")
        tok = b.get("token")
        if tok is not None and tok not in r.tokens:
            raise ActionError("Session expired — rejoin the room")
        r.touched = time.time()
        return r

    def cosmetics(self, b):
        c = b.get("cosmetics") or {}
        return {"theme": str(c.get("theme", "classic"))[:20], "title": str(c.get("title", "Rookie Dealer"))[:30],
                "decor": [str(x)[:20] for x in (c.get("decor") or [])][:4]}

    def create(self, b):
        if len(rooms) >= MAX_ROOMS:
            raise ActionError("The server is busy — try again in a few minutes")
        s = b.get("settings") or {}
        code = new_code()
        m = Match(code, s)
        r = Room(code, m)
        if m.settings["solo"]:
            r.owner = self.owner(b.get("profile"))
        tok = secrets.token_urlsafe(16)
        with r.lock:
            p = m.add_human(b.get("name") or "Host", tok, self.cosmetics(b))
            r.tokens[tok] = p["id"]
            if s.get("my_type") and m.settings["type_rule"] == "free":
                m.set_type(p, s["my_type"])
            if m.settings["solo"]:
                for _ in range(max(1, min(7, int(s.get("bots", 3))))):
                    m.add_bot()
                m.start()
                m.paused = True  # the clock waits until the player has read the instructions
        with rooms_lock:
            rooms[code] = r
        return self.send_json({"ok": True, "room": code, "pid": p["id"], "token": tok})

    def join(self, b):
        r = self.room_for({"room": b.get("room")})
        tok = secrets.token_urlsafe(16)
        with r.lock:
            m = r.match
            if m.settings["solo"]:
                raise ActionError("That is a private solo match")
            p = m.add_human(b.get("name") or "Dealer", tok, self.cosmetics(b))
            r.tokens[tok] = p["id"]
            if b.get("my_type") in DEALERSHIP_TYPES and m.settings["type_rule"] == "free":
                m.set_type(p, b["my_type"])
            m.dirty = True
        return self.send_json({"ok": True, "room": r.code, "pid": p["id"], "token": tok})

    def rejoin(self, b):
        r = self.room_for(b)
        return self.send_json({"ok": True, "room": r.code, "pid": r.tokens[b["token"]]})

    def lobby(self, b):
        r = self.room_for(b)
        with r.lock:
            m = r.match
            pid = r.tokens[b["token"]]
            op = b.get("op")
            if op == "set_type":  # any player picks their own dealership type
                target = m.players.get(b.get("pid") or pid)
                if not target or (target["id"] != pid and not (pid == m.host and target["is_ai"])):
                    raise ActionError("You can only choose your own type (the host can set AI types)")
                m.set_type(target, b.get("dtype"))
                m.dirty = True
                r.cond.notify_all()
                return self.send_json({"ok": True})
            if pid != m.host:
                raise ActionError("Only the host can do that")
            if op == "add_bot":
                m.add_bot()
            elif op == "remove":
                target = b.get("pid")
                if target == pid:
                    raise ActionError("The host can't remove themselves")
                m.remove_player(target)
                for t, x in list(r.tokens.items()):
                    if x == target:
                        del r.tokens[t]
            elif op == "settings":
                if m.phase != "lobby":
                    raise ActionError("Match already started")
                s = b.get("settings") or {}
                for k in ("days", "max_players"):
                    if k in s:
                        m.settings[k] = max(3 if k == "days" else max(2, len(m.players)), min(15 if k == "days" else 8, int(s[k])))
                if s.get("pace") in ("quick", "normal", "relaxed"):
                    m.settings["pace"] = s["pace"]
                if "public" in s:
                    m.settings["public"] = bool(s["public"])
                if s.get("type_rule") == "free" or s.get("type_rule") in DEALERSHIP_TYPES:
                    m.settings["type_rule"] = s["type_rule"]
            elif op == "start":
                m.start()
            else:
                raise ActionError("Unknown lobby operation")
            m.dirty = True
            r.cond.notify_all()
        return self.send_json({"ok": True})

    def action(self, b):
        r = self.room_for(b)
        with r.lock:
            pid = r.tokens[b["token"]]
            res = r.match.handle(pid, str(b.get("action")), b.get("args") or {}, b.get("nonce"))
            r.cond.notify_all()
        return self.send_json({"ok": True, "res": res})

    def pause(self, b):
        r = self.room_for(b)
        with r.lock:
            m = r.match
            if not m.settings["solo"]:
                raise ActionError("Pausing is only available in solo matches")
            m.paused = bool(b.get("paused"))
            m.dirty = True
            r.cond.notify_all()
        return self.send_json({"ok": True, "paused": m.paused})

    def leave(self, b):
        r = self.room_for(b)
        with r.lock:
            m = r.match
            pid = r.tokens.get(b["token"])
            if m.phase == "lobby":
                m.remove_player(pid)
                r.tokens.pop(b["token"], None)
            elif pid in m.players and not m.settings["solo"]:
                m.players[pid]["connected"] = False
                m.players[pid]["last_seen"] = m.clock - 60  # autopilot immediately
                m.log("%s left the match — autopilot takes over." % m.players[pid]["name"], "warn")
            if m.settings["solo"] and m.phase != "final":
                save_solo(r)
            m.dirty = True
            r.cond.notify_all()
        return self.send_json({"ok": True})

    def profile_update(self, b):
        return self.send_json(profile_store(self.owner(b.get("profile"))).update(b))

    def award(self, b):
        key = "%s:%s:%s" % (b.get("host", ""), b.get("room", ""), b.get("pid", ""))
        return self.send_json(profile_store(self.owner(b.get("profile"))).award(key, b.get("row") or {}, int(b.get("players") or 4)))

    def quit(self, b):
        if not self.is_local():
            raise ActionError("Local only")
        with rooms_lock:
            rs = list(rooms.values())
        for r in rs:
            with r.lock:
                if r.match.settings.get("solo") and r.match.phase not in ("lobby", "final"):
                    save_solo(r)
        self.send_json({"ok": True})
        threading.Timer(0.3, lambda: os._exit(0)).start()

    def resume(self, b):
        owner = self.owner(b.get("profile"))
        try:
            with open(save_path(owner)) as f:
                d = json.load(f)
            m = Match.from_dict(d["match"])
        except (OSError, ValueError, KeyError) as e:
            raise ActionError("Save file could not be loaded (%s)" % e)
        code = new_code()
        m.room = code
        r = Room(code, m)
        r.tokens = d["tokens"]
        r.owner = owner
        r.last_day_saved = m.day
        m.paused = False
        tok = next(iter(r.tokens))
        with rooms_lock:
            rooms[code] = r
        return self.send_json({"ok": True, "room": code, "pid": r.tokens[tok], "token": tok})


def main():
    global profiles
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT") or os.environ.get("DEALERSHIP_PORT") or 8642))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--exit-when-idle", type=int, default=0, help="quit N seconds after the last game window closes")
    args = ap.parse_args()
    global IDLE_EXIT
    IDLE_EXIT = args.exit_when_idle
    profiles = ProfileStore(DATA)
    port = args.port
    srv = None
    for attempt in range(1 if CLOUD else 10):  # a host's assigned port must be used exactly
        try:
            srv = GameServer((args.host, port + attempt), Handler)
            port = port + attempt
            break
        except OSError:
            continue
    if srv is None:
        print("Could not bind a port near %d" % args.port)
        sys.exit(1)
    srv.daemon_threads = True
    threading.Thread(target=ticker, daemon=True).start()
    url = "http://localhost:%d/" % port
    print("=" * 60)
    print(" THE DEALERSHIP  v%s" % VERSION)
    print(" Play:            %s" % url)
    print(" LAN players use: http://%s:%d/" % (lan_ip(), port))
    print(" Saves/profile:   %s" % DATA)
    print(" Close this window to quit the game server.")
    print("=" * 60, flush=True)
    if not args.no_browser and not CLOUD:
        threading.Timer(0.6, lambda: open_game(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def open_game(url):
    """Open in a chromeless app window when Chrome/Edge is available, otherwise the default browser."""
    import subprocess
    candidates = []
    if sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
    elif os.name == "nt":
        pf = [os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("LOCALAPPDATA", "")]
        for base in pf:
            candidates += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                           os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    else:
        candidates = ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]
    for c in candidates:
        if c and os.path.exists(c):
            try:
                prof = os.path.join(DATA, "window-profile")
                subprocess.Popen([c, "--app=" + url, "--window-size=1440,900", "--user-data-dir=" + prof,
                                  "--no-first-run", "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                pass
    webbrowser.open(url)


if __name__ == "__main__":
    main()
