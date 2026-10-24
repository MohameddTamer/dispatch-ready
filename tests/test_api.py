#!/usr/bin/env python3
# End to end check for dispatch ready. Run: python3 tests/test_api.py
# The gate rule is the thing under test here, everything else is plumbing.
import json, os, subprocess, sys, time, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(__file__), "..")
PORT = "8092"
BASE = f"http://127.0.0.1:{PORT}"
DAY = "2026-10-24"

def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

def main():
    env = dict(os.environ, PORT=PORT)
    subprocess.run([sys.executable, "seed.py"], cwd=os.path.join(ROOT, "backend"), check=True)
    srv = subprocess.Popen([sys.executable, "app.py"], cwd=os.path.join(ROOT, "backend"), env=env)
    try:
        time.sleep(1.2)
        code, _ = call("GET", f"/api/board?day={DAY}")
        assert code == 401, code
        code, _ = call("POST", "/api/login", {"username": "yardlead", "password": "bad"})
        assert code == 401, code
        code, body = call("POST", "/api/login", {"username": "yardlead", "password": "demo1234"})
        assert code == 200, body
        tok = body["token"]
        code, board = call("GET", f"/api/board?day={DAY}", token=tok)
        assert code == 200, board
        # seed truth for today: 1 departed, 1 ready, 6 blocked including the one with no checklist row at all
        assert board["departed"] == 1 and board["ready"] == 1 and board["blocked"] == 6, board
        by_id = {c["id"]: c for c in board["couriers"]}
        assert by_id[5]["state"] == "blocked" and "no checklist yet" in by_id[5]["blockers"]
        assert any("phone at 12%" in b for b in by_id[3]["blockers"]), by_id[3]
        assert any("vehicle" in b for b in by_id[4]["blockers"]), by_id[4]
        # the gate: a blocked courier cannot depart, and the api must say why
        code, body = call("POST", "/api/depart", {"courier_id": 3, "day": DAY}, token=tok)
        assert code == 400 and body["blockers"], body
        code, body = call("POST", "/api/depart", {"courier_id": 5, "day": DAY}, token=tok)
        assert code == 400, body
        # fix courier 3 by charging the phone in the checklist, then he may leave
        code, body = call("POST", "/api/checklist",
                          {"courier_id": 3, "day": DAY, "attendance": True, "vehicle_ok": True,
                           "phone_pct": 55, "app_ok": True, "route_received": True,
                           "exception_reason": "power bank handed over at the gate"}, token=tok)
        assert code == 200 and body["blockers"] == [], body
        code, body = call("POST", "/api/depart", {"courier_id": 3, "day": DAY}, token=tok)
        assert code == 200 and body["departed"], body
        # validation still bites
        code, body = call("POST", "/api/checklist",
                          {"courier_id": 2, "day": DAY, "attendance": True, "vehicle_ok": True,
                           "phone_pct": 140, "app_ok": True, "route_received": True}, token=tok)
        assert code == 400, body
        code, body = call("POST", "/api/depart", {"courier_id": 2, "day": DAY}, token=tok)
        assert code == 200, body
        code, board = call("GET", f"/api/board?day={DAY}", token=tok)
        assert board["departed"] == 3 and board["blocked"] == 5 and board["ready"] == 0, board
        with urllib.request.urlopen(BASE + "/") as r:
            assert r.status == 200
        print("Dispatch ready api tests passed")
    finally:
        srv.terminate()

if __name__ == "__main__":
    main()
