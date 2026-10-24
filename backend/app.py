#!/usr/bin/env python3
# Dispatch ready. The morning gate before anyone leaves the yard.
# A van does not roll because a box was left unticked, that is the whole point of this file.
import csv, hashlib, hmac, io, json, logging, logging.handlers, os, re, secrets, sqlite3, time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8082"))
DB = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "dispatch.db")
LOG_PATH = os.environ.get("LOG_PATH") or os.path.join(BASE_DIR, "dispatch.log")
BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(BASE_DIR, "backups")
IMPORT_LIMIT = 500_000
TOKENS = {}
TOKEN_TTL = 8 * 3600
ADMIN_ROLES = ("yard_lead",)
PHONE_MIN = 30  # a phone under this dies mid route, so it does not leave

IMPORT_COLUMNS = ("courier_id", "day", "attendance", "vehicle_ok", "phone_pct", "app_ok", "route_received")
BOOL_WORDS = {"1": 1, "0": 0, "true": 1, "false": 0, "yes": 1, "no": 0}

log = logging.getLogger("dispatch")
if not log.handlers:
    try:
        handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=256_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    except OSError:
        log.addHandler(logging.NullHandler())

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000).hex()

def valid_date(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False

def day_range(start, end):
    first = date.fromisoformat(start)
    days = (date.fromisoformat(end) - first).days
    return [(first + timedelta(days=i)).isoformat() for i in range(days + 1)]

def blockers(row):
    out = []
    if row is None:
        return ["no checklist yet"]
    if not row["attendance"]:
        out.append("absent")
    if not row["vehicle_ok"]:
        out.append("vehicle check failed or not done")
    if row["phone_pct"] is None or row["phone_pct"] < PHONE_MIN:
        out.append(f"phone at {row['phone_pct'] if row['phone_pct'] is not None else 0}% (min {PHONE_MIN}%)")
    if not row["app_ok"]:
        out.append("delivery app not confirmed working")
    if not row["route_received"]:
        out.append("route not received")
    return out

def blocker_category(text):
    if text == "no checklist yet":
        return "no_checklist"
    if text == "absent":
        return "absent"
    if text.startswith("vehicle"):
        return "vehicle"
    if text.startswith("phone"):
        return "phone"
    if text.startswith("delivery app"):
        return "app"
    if text.startswith("route"):
        return "route"
    return "other"

def board_for_day(conn, day):
    rows = conn.execute("""
        SELECT c.*, cl.attendance, cl.vehicle_ok, cl.phone_pct, cl.app_ok,
               cl.route_received, cl.departed, cl.exception_reason
        FROM couriers c LEFT JOIN checklist cl ON cl.courier_id = c.id AND cl.day = ?
        ORDER BY c.office, c.name
    """, (day,)).fetchall()
    board = []
    for r in rows:
        d = dict(r)
        check = None
        if d["attendance"] is not None:
            check = {"attendance": d["attendance"], "vehicle_ok": d["vehicle_ok"],
                     "phone_pct": d["phone_pct"], "app_ok": d["app_ok"],
                     "route_received": d["route_received"]}
        stuck = blockers(check)
        d["checklist"] = check
        d["blockers"] = [] if d["departed"] else stuck
        d["state"] = "departed" if d["departed"] else ("ready" if not stuck else "blocked")
        board.append(d)
    return board

class H(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, err_code, message, **extra):
        payload = {"ok": False, "error": {"code": err_code, "message": message}}
        payload.update(extra)
        log.warning("request failed code=%s status=%s path=%s", err_code, code, urlparse(self.path).path)
        return self._send(code, payload)

    def _session(self):
        tok = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        s = TOKENS.get(tok)
        return s if s and s["expires"] > time.time() else None

    def _auth(self):
        s = self._session()
        return s["user"] if s else None

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return None

    def _raw_body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            return None
        return self.rfile.read(n)

    def do_POST(self):
        try:
            self._post()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("unhandled error on POST %s", self.path)
            try:
                self._send(500, {"ok": False, "error": {"code": "server_error", "message": "something broke on the server, the log has the details"}})
            except Exception:
                pass

    def _post(self):
        path = urlparse(self.path).path
        if path == "/api/import":
            return self._import()
        if path == "/api/admin/backup":
            return self._backup()
        data = self._body()
        if data is None:
            return self._err(400, "bad_body", "request body is not valid json or is too large")
        if path == "/api/login":
            user = str(data.get("username", ""))[:40]
            pw = str(data.get("password", ""))[:100]
            conn = db()
            row = conn.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
            conn.close()
            if not row or not hmac.compare_digest(hash_pw(pw, bytes.fromhex(row["salt"])), row["pw_hash"]):
                return self._err(401, "bad_credentials", "wrong username or password")
            tok = secrets.token_urlsafe(32)
            TOKENS[tok] = {"user": user, "role": row["role"], "expires": time.time() + TOKEN_TTL}
            log.info("login user=%s", user)
            return self._send(200, {"token": tok, "user": user, "role": row["role"]})
        if not self._auth():
            return self._err(401, "login_required", "login required")
        conn = db()
        if path == "/api/checklist":
            cid = data.get("courier_id")
            day = str(data.get("day", "")).strip()
            if not isinstance(cid, int) or not valid_date(day):
                conn.close()
                return self._err(400, "validation", "courier_id and a valid day are required")
            if not conn.execute("SELECT 1 FROM couriers WHERE id=?", (cid,)).fetchone():
                conn.close()
                return self._err(404, "courier_not_found", "courier not found")
            phone = data.get("phone_pct")
            if phone is not None and (not isinstance(phone, int) or phone < 0 or phone > 100):
                conn.close()
                return self._err(400, "validation", "phone_pct must be between 0 and 100")
            exc = str(data.get("exception_reason", "")).strip()[:300]
            conn.execute("""
                INSERT INTO checklist (courier_id, day, attendance, vehicle_ok, phone_pct, app_ok, route_received, exception_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(courier_id, day) DO UPDATE SET
                    attendance=excluded.attendance, vehicle_ok=excluded.vehicle_ok,
                    phone_pct=excluded.phone_pct, app_ok=excluded.app_ok,
                    route_received=excluded.route_received, exception_reason=excluded.exception_reason,
                    departed=0
            """, (cid, day, 1 if data.get("attendance") else 0, 1 if data.get("vehicle_ok") else 0,
                  phone, 1 if data.get("app_ok") else 0, 1 if data.get("route_received") else 0, exc))
            conn.commit()
            row = conn.execute("SELECT * FROM checklist WHERE courier_id=? AND day=?", (cid, day)).fetchone()
            conn.close()
            return self._send(200, {"ok": True, "blockers": blockers(row)})
        if path == "/api/depart":
            cid = data.get("courier_id")
            day = str(data.get("day", "")).strip()
            if not isinstance(cid, int) or not valid_date(day):
                conn.close()
                return self._err(400, "validation", "courier_id and a valid day are required")
            row = conn.execute("SELECT * FROM checklist WHERE courier_id=? AND day=?", (cid, day)).fetchone()
            stuck = blockers(row)
            if stuck:
                conn.close()
                return self._err(400, "blocked", "cannot depart", blockers=stuck)
            conn.execute("UPDATE checklist SET departed=1 WHERE courier_id=? AND day=?", (cid, day))
            conn.commit(); conn.close()
            return self._send(200, {"ok": True, "departed": True})
        conn.close()
        return self._err(404, "not_found", "not found")

    def _import(self):
        if not self._auth():
            return self._err(401, "login_required", "login required")
        raw = self._raw_body(IMPORT_LIMIT)
        if raw is None:
            return self._err(413, "import_too_large", f"csv body is over the {IMPORT_LIMIT} byte limit")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return self._err(400, "bad_encoding", "csv must be utf-8 text")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return self._err(400, "missing_columns", "csv has no header row", missing=list(IMPORT_COLUMNS))
        headers = [(h or "").strip().lower() for h in reader.fieldnames]
        missing = [c for c in IMPORT_COLUMNS if c not in headers]
        if missing:
            return self._err(400, "missing_columns", "csv is missing required columns", missing=missing)
        inserted = 0
        skipped = []
        rejected = []
        conn = db()
        known = {r[0] for r in conn.execute("SELECT id FROM couriers")}
        seen = {(r[0], r[1]) for r in conn.execute("SELECT courier_id, day FROM checklist")}
        total = 0
        for lineno, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
            if not any(row.values()):
                continue
            total += 1
            day = row.get("day", "")
            try:
                cid = int(row.get("courier_id", ""))
            except ValueError:
                cid = None
            problem = None
            values = {}
            if cid is None:
                problem = f"courier_id {row.get('courier_id', '')!r} is not a number"
            elif cid not in known:
                problem = f"courier_id {cid} does not exist"
            elif not valid_date(day):
                problem = f"day {day!r} is not a real YYYY-MM-DD date"
            if problem is None:
                for field in ("attendance", "vehicle_ok", "app_ok", "route_received"):
                    word = row.get(field, "").lower()
                    if word not in BOOL_WORDS:
                        problem = f"{field} value {row.get(field, '')!r} is not 1, 0, true or false"
                        break
                    values[field] = BOOL_WORDS[word]
            phone = None
            if problem is None:
                raw_phone = row.get("phone_pct", "")
                if raw_phone != "":
                    try:
                        phone = int(raw_phone)
                        if phone < 0 or phone > 100:
                            problem = f"phone_pct {phone} is outside 0 to 100"
                    except ValueError:
                        problem = f"phone_pct {raw_phone!r} is not a number"
            if problem:
                rejected.append({"row": lineno, "courier_id": cid, "day": day, "reason": problem})
                continue
            if (cid, day) in seen:
                skipped.append({"courier_id": cid, "day": day})
                continue
            conn.execute("""
                INSERT INTO checklist (courier_id, day, attendance, vehicle_ok, phone_pct, app_ok, route_received, exception_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, day, values["attendance"], values["vehicle_ok"], phone,
                  values["app_ok"], values["route_received"], row.get("exception_reason", "")[:300]))
            seen.add((cid, day))
            inserted += 1
        conn.commit(); conn.close()
        log.info("csv import inserted=%s skipped=%s rejected=%s", inserted, len(skipped), len(rejected))
        return self._send(200, {"ok": True, "inserted": inserted, "skipped_duplicates": skipped,
                                "rejected_rows": rejected, "total_rows": total})

    def _backup(self):
        session = self._session()
        if not session:
            return self._err(401, "login_required", "login required")
        if session["role"] not in ADMIN_ROLES:
            return self._err(403, "admin_only", "backup is limited to the yard lead account")
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = f"dispatch-backup-{stamp}.db"
        dest = os.path.join(BACKUP_DIR, name)
        counter = 1
        while os.path.exists(dest):
            counter += 1
            name = f"dispatch-backup-{stamp}-{counter}.db"
            dest = os.path.join(BACKUP_DIR, name)
        src = db()
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()
        size = os.path.getsize(dest)
        log.info("backup written name=%s bytes=%s by=%s", name, size, session["user"])
        return self._send(200, {"ok": True, "backup": name, "size": size})

    def do_GET(self):
        try:
            self._get()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("unhandled error on GET %s", self.path)
            try:
                self._send(500, {"ok": False, "error": {"code": "server_error", "message": "something broke on the server, the log has the details"}})
            except Exception:
                pass

    def _get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            fpath = os.path.join(BASE_DIR, "..", "frontend", "index.html")
            with open(fpath, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return self.wfile.write(body)
        if not path.startswith("/api/"):
            return self._err(404, "not_found", "not found")
        if not self._auth():
            return self._err(401, "login_required", "login required")
        q = parse_qs(parsed.query)
        day = (q.get("day") or [""])[0]
        conn = db()
        if path == "/api/report":
            start = (q.get("from") or [""])[0]
            end = (q.get("to") or [""])[0]
            conn.close()
            if not valid_date(start) or not valid_date(end) or start > end:
                return self._err(400, "validation", "from and to are required as YYYY-MM-DD, from before to")
            if (date.fromisoformat(end) - date.fromisoformat(start)).days > 62:
                return self._err(400, "validation", "report range is capped at 63 days")
            conn = db()
            trend = []
            reasons = {}
            totals = {"ready": 0, "blocked": 0, "departed": 0}
            for d in day_range(start, end):
                board = board_for_day(conn, d)
                entry = {"day": d,
                         "ready": sum(1 for b in board if b["state"] == "ready"),
                         "blocked": sum(1 for b in board if b["state"] == "blocked"),
                         "departed": sum(1 for b in board if b["state"] == "departed")}
                trend.append(entry)
                for key in totals:
                    totals[key] += entry[key]
                for b in board:
                    if b["state"] == "blocked":
                        for text in b["blockers"]:
                            cat = blocker_category(text)
                            reasons[cat] = reasons.get(cat, 0) + 1
            conn.close()
            return self._send(200, {"from": start, "to": end, "trend": trend,
                                    "blocker_reasons": reasons, "totals": totals})
        if path != "/api/board":
            conn.close()
            return self._err(404, "not_found", "not found")
        if not valid_date(day):
            conn.close()
            return self._err(400, "validation", "day is required, format YYYY-MM-DD")
        board = board_for_day(conn, day)
        conn.close()
        return self._send(200, {
            "day": day,
            "ready": sum(1 for b in board if b["state"] == "ready"),
            "blocked": sum(1 for b in board if b["state"] == "blocked"),
            "departed": sum(1 for b in board if b["state"] == "departed"),
            "couriers": board,
        })

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print(f"Dispatch ready on http://127.0.0.1:{PORT}")
    log.info("starting on port %s db=%s", PORT, DB)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
