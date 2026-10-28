"""
Lifeline backend (Python, no pip installs needed; Python 3.8+).

HOW TO USE
  1. Unzip the project. Open a terminal in the backend/ folder.
  2. Run:   python server.py        (Windows: py server.py)
  3. On the laptop open  http://localhost:3000
     On a phone (same Wi-Fi/hotspot) open  http://<laptop-ip>:3000
  4. In the app paste the same address into "Real server URL".

WHERE THINGS ARE SAVED (all next to this file, printed when the server starts)
  records.json            every entry
  history/YYYY-MM-DD.json one file per day
  ../frontend/lifeline-app.html  the frontend, served at  /  and  /app

API (same as the Node version, so the app works unchanged)
  GET  /health    -> ok
  GET  /records   -> all entries
  POST /records   -> save/update one entry (same id = update, never duplicate)
  GET  /history   -> all days in one JSON
"""
import json, os, re, shutil, time, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))          # folder of this file
APP_FILE = os.path.join(BASE, "..", "frontend", "lifeline-app.html")   # frontend folder
RECORDS = os.path.join(BASE, "records.json")
HDIR = os.path.join(BASE, "history")
PORT = int(os.environ.get("PORT", 3000))
MAX_BODY = 5 * 1024 * 1024
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
lock = threading.Lock()

os.makedirs(HDIR, exist_ok=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_write(path, obj):
    """Write to a temp file then rename, so a crash can't leave a half-written file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def load_records():
    if not os.path.exists(RECORDS):
        return []
    try:
        with open(RECORDS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        backup = os.path.join(BASE, "records.corrupt-%d.json" % int(time.time()))
        shutil.copyfile(RECORDS, backup)                   # never overwrite a damaged file
        print("records.json could not be read. Copy kept as", backup)
        return []


db = load_records()


def body_of(e):
    """Content used to tell a real change from a repeat upload."""
    return json.dumps([e.get(k) for k in ("data", "rows", "row", "name", "details", "status", "log")],
                      sort_keys=True)


def read_day(fname):
    path = os.path.join(HDIR, fname)
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    if isinstance(j, dict) and "data" in j and "firstSavedAt" in j:
        return j
    ts = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat().replace("+00:00", "Z")
    return {"date": fname[:10], "firstSavedAt": ts, "updatedAt": ts, "data": j}


def all_days():
    names = sorted(f for f in os.listdir(HDIR) if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f))
    return {n[:10]: read_day(n) for n in names}


def save_entry(e):
    """Store or update one entry. Original time (firstSavedAt) never changes."""
    if not isinstance(e, dict) or not isinstance(e.get("id"), str):
        raise ValueError("id required")
    with lock:
        idx = next((i for i, x in enumerate(db) if x.get("id") == e["id"]), -1)
        prev = db[idx] if idx >= 0 else None
        t = now()
        first = (prev and (prev.get("firstSavedAt") or prev.get("receivedAt"))) or e.get("createdAt") or t
        e["firstSavedAt"] = first
        e["receivedAt"] = first
        e["updatedAt"] = (prev.get("updatedAt") or first) if (prev and body_of(prev) == body_of(e)) else t
        if e.get("kind") == "hist":
            if not DATE_RE.match(str(e.get("date", ""))):
                raise ValueError("bad date")
            atomic_write(os.path.join(HDIR, e["date"] + ".json"),
                         {"date": e["date"], "firstSavedAt": first, "updatedAt": e["updatedAt"], "data": e.get("data")})
        if idx < 0:
            db.append(e)
        else:
            db[idx] = e
        atomic_write(RECORDS, db)
    return {"firstSavedAt": e["firstSavedAt"], "updatedAt": e["updatedAt"]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="text/plain"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, indent=1, ensure_ascii=False), "application/json")

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._send(200, "ok")
        if path == "/records":
            return self._json(200, db)
        if path == "/history":
            return self._json(200, all_days())
        if path in ("/", "/app"):
            if os.path.exists(APP_FILE):
                with open(APP_FILE, "rb") as f:
                    return self._send(200, f.read(), "text/html")
            return self._send(404, "frontend/lifeline-app.html not found")
        self._send(404)

    def do_POST(self):
        if self.path.split("?")[0] != "/records":
            return self._send(404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BODY:
                return self._send(413, "too big")
            e = json.loads(self.rfile.read(n).decode("utf-8"))
            self._json(200, save_entry(e))
        except Exception:
            self._send(400, "bad")

    def log_message(self, *a):  # quiet console
        pass


if __name__ == "__main__":
    print("Lifeline server on http://localhost:%d" % PORT)
    print("Frontend file :", APP_FILE, "(found)" if os.path.exists(APP_FILE) else "(NOT FOUND - keep frontend/lifeline-app.html in the project)")
    print("All entries   :", RECORDS)
    print("Each day      :", os.path.join(HDIR, "YYYY-MM-DD.json"))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
