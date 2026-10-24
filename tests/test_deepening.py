#!/usr/bin/env python3
# Deepening checks for dispatch ready. Run: python3 tests/test_deepening.py
# Boots the real server on its own port against a throwaway database in a temp folder.
import json, os, sqlite3, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(__file__), "..")
PORT = "8192"
BASE = f"http://127.0.0.1:{PORT}"
CHECKS = 0

def check(cond, msg):
    global CHECKS
    CHECKS += 1
    if not cond:
        raise AssertionError(f"check {CHECKS} failed: {msg}")
    print(f"ok {CHECKS}: {msg}")

def call(method, path, body=None, token=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, method=method, data=data,
        headers={"Content-Type": ctype, **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            payload = r.read()
            return r.status, json.loads(payload or b"{}")
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload or b"{}")
        except json.JSONDecodeError:
            return e.code, {}

def wait_up():
    for _ in range(50):
        try:
            with urllib.request.urlopen(BASE + "/", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False

HEADER = "courier_id,day,attendance,vehicle_ok,phone_pct,app_ok,route_received,exception_reason\n"
GOOD_CSV = HEADER + (
    "1,2026-10-25,1,1,82,1,1,\n"
    "2,2026-10-25,true,true,57,true,true,power bank in the van\n"
)
MIXED_CSV = HEADER + (
    "3,2026-10-25,1,1,80,1,1,\n"
    "4,2026-10-25,maybe,1,80,1,1,\n"
    "5,2026-10-25,1,1,140,1,1,\n"
    "99,2026-10-25,1,1,80,1,1,\n"
    "6,25-10-2026,1,1,80,1,1,\n"
    "1,2026-10-24,1,1,80,1,1,\n"
)

def main():
    tmp = tempfile.mkdtemp(prefix="dispatch-deep-")
    db_path = os.path.join(tmp, "deep.db")
    log_path = os.path.join(tmp, "deep.log")
    backup_dir = os.path.join(tmp, "backups")
    env = dict(os.environ, PORT=PORT, DB_PATH=db_path, LOG_PATH=log_path, BACKUP_DIR=backup_dir)
    subprocess.run([sys.executable, "seed.py"], cwd=os.path.join(ROOT, "backend"), env=env, check=True)
    srv = subprocess.Popen([sys.executable, "app.py"], cwd=os.path.join(ROOT, "backend"), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        check(wait_up(), "server boots on the PORT from the environment")
        check(os.path.exists(db_path), "seed wrote the database at the DB_PATH from the environment")

        code, body = call("GET", "/api/board?day=2026-10-24")
        check(code == 401, "board without a token is 401")
        check(isinstance(body.get("error"), dict), "unauthenticated error is a structured object")
        check(body["error"].get("code") == "login_required", "unauthenticated error names its code")
        check(bool(body["error"].get("message")), "unauthenticated error carries a message")

        code, viewer = call("POST", "/api/login", {"username": "yardview", "password": "view1234"})
        check(code == 200 and viewer.get("role") == "viewer", "viewer account logs in with the viewer role")
        code, body = call("POST", "/api/admin/backup", {}, token=viewer["token"])
        check(code == 403, "viewer cannot take a backup")
        check(body["error"].get("code") == "admin_only", "backup refusal names the admin_only code")

        code, body = call("POST", "/api/login", {"username": "yardlead", "password": "demo1234"})
        check(code == 200, "yard lead logs in")
        tok = body["token"]

        code, rep = call("GET", "/api/report?from=2026-10-20&to=2026-10-24", token=tok)
        check(code == 200, "report answers for a five day range")
        check(all(k in rep for k in ("from", "to", "trend", "blocker_reasons", "totals")), "report has the documented shape")
        check(len(rep["trend"]) == 5, "trend covers every day in the range")
        check(all("day" in t and "ready" in t and "blocked" in t and "departed" in t for t in rep["trend"]), "every trend entry carries day, ready, blocked and departed")
        check(sum(rep["totals"].values()) == 40, "report totals cover eight couriers over five days")
        check(rep["trend"][-1]["departed"] == 1 and rep["trend"][-1]["ready"] == 1 and rep["trend"][-1]["blocked"] == 6, "the last trend day matches the seeded gate board")
        check(rep["blocker_reasons"].get("phone", 0) >= 1, "blocker reasons count the low phone cases")
        check(rep["blocker_reasons"].get("vehicle", 0) >= 1, "blocker reasons count the vehicle cases")
        check(rep["blocker_reasons"].get("no_checklist", 0) >= 1, "blocker reasons count couriers with no checklist at all")
        check(sum(rep["blocker_reasons"].values()) >= rep["totals"]["blocked"], "every blocked courier contributes at least one counted reason")
        code, body = call("GET", "/api/report?from=2026-10-24&to=2026-10-20", token=tok)
        check(code == 400 and body["error"].get("code") == "validation", "backwards report range is a structured 400")
        code, body = call("GET", "/api/nope", token=tok)
        check(code == 404 and body["error"].get("code") == "not_found", "unknown api path is a structured 404")

        code, body = call("POST", "/api/import", raw=GOOD_CSV.encode(), ctype="text/csv")
        check(code == 401, "import without a token is 401")

        code, rep1 = call("POST", "/api/import", raw=GOOD_CSV.encode(), token=tok, ctype="text/csv")
        check(code == 200, "clean csv import succeeds")
        check(rep1["inserted"] == 2, "clean import inserts both checklist rows")
        check(rep1["skipped_duplicates"] == [], "clean import skips nothing")
        check(rep1["rejected_rows"] == [], "clean import rejects nothing")
        check(rep1["total_rows"] == 2, "import report counts the data rows")
        code, board = call("GET", "/api/board?day=2026-10-25", token=tok)
        check(board["ready"] == 2 and board["blocked"] == 6, "imported checklists show up on that day board")

        code, rep2 = call("POST", "/api/import", raw=GOOD_CSV.encode(), token=tok, ctype="text/csv")
        check(code == 200, "repeating the same import still answers")
        check(rep2["inserted"] == 0, "repeated import inserts nothing twice")
        named = sorted((d["courier_id"], d["day"]) for d in rep2["skipped_duplicates"])
        check(named == [(1, "2026-10-25"), (2, "2026-10-25")], "duplicates are named by courier and day")

        code, rep3 = call("POST", "/api/import", raw=MIXED_CSV.encode(), token=tok, ctype="text/csv")
        check(code == 200, "mixed csv import answers with a report instead of failing whole")
        check(rep3["inserted"] == 1, "the one valid row in the mixed file is inserted")
        check(rep3["skipped_duplicates"] == [{"courier_id": 1, "day": "2026-10-24"}], "an existing courier and day entry is named as a duplicate")
        check(len(rep3["rejected_rows"]) == 4, "the four broken rows are all rejected, none swallowed")
        check(all(isinstance(r["row"], int) and r["row"] >= 2 for r in rep3["rejected_rows"]), "rejected rows carry their csv line number")
        check(all(r["reason"] for r in rep3["rejected_rows"]), "every rejected row says why")
        check(any("attendance" in r["reason"] for r in rep3["rejected_rows"]), "the non boolean attendance value is called out")
        check(any("phone_pct" in r["reason"] for r in rep3["rejected_rows"]), "the phone charge over 100 is called out")
        check(any("courier_id" in r["reason"] for r in rep3["rejected_rows"]), "the unknown courier is called out")
        check(any("day" in r["reason"] for r in rep3["rejected_rows"]), "the day written backwards is called out")

        code, body = call("POST", "/api/import", raw=b"courier_id,day\n1,2026-10-25\n", token=tok, ctype="text/csv")
        check(code == 400, "a csv missing required columns is refused")
        check(body["error"].get("code") == "missing_columns", "missing columns error names its code")
        check("phone_pct" in body.get("missing", []) and "attendance" in body.get("missing", []), "the missing column names are listed")

        code, body = call("POST", "/api/admin/backup", {}, token=tok)
        check(code == 200, "yard lead backup succeeds")
        name = body.get("backup", "")
        check(name.startswith("dispatch-backup-") and name.endswith(".db"), "backup name is timestamped and named in the reply")
        dest = os.path.join(backup_dir, name)
        check(os.path.exists(dest), "the backup file exists in the configured BACKUP_DIR")
        check(body.get("size") == os.path.getsize(dest) and body["size"] > 0, "reported backup size matches the file")
        bconn = sqlite3.connect(dest)
        integrity = bconn.execute("PRAGMA integrity_check").fetchone()[0]
        backup_count = bconn.execute("SELECT COUNT(*) FROM checklist").fetchone()[0]
        bconn.close()
        check(integrity == "ok", "backup database passes integrity_check")
        live = sqlite3.connect(db_path)
        live_count = live.execute("SELECT COUNT(*) FROM checklist").fetchone()[0]
        live.close()
        check(backup_count == live_count, "backup holds every checklist row the live database holds")

        check(os.path.exists(log_path) and os.path.getsize(log_path) > 0, "the app wrote its rotating log file at LOG_PATH")
        with open(log_path, encoding="utf-8") as fh:
            log_text = fh.read()
        check("backup" in log_text or "import" in log_text, "the log recorded the import or backup work")

        print(f"Dispatch deepening tests passed ({CHECKS} checks)")
    finally:
        srv.terminate()

if __name__ == "__main__":
    main()
