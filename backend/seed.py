#!/usr/bin/env python3
# Demo seed. Invented names and offices.
import os, secrets, sqlite3, sys
sys.path.insert(0, os.path.dirname(__file__))
from app import hash_pw, DB

if os.path.exists(DB):
    os.remove(DB)
conn = sqlite3.connect(DB)
conn.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, pw_hash TEXT, role TEXT);
CREATE TABLE couriers (id INTEGER PRIMARY KEY, name TEXT, office TEXT, route TEXT);
CREATE TABLE checklist (courier_id INTEGER, day TEXT, attendance INTEGER DEFAULT 0,
                        vehicle_ok INTEGER DEFAULT 0, phone_pct INTEGER, app_ok INTEGER DEFAULT 0,
                        route_received INTEGER DEFAULT 0, departed INTEGER DEFAULT 0,
                        exception_reason TEXT DEFAULT '', PRIMARY KEY (courier_id, day));
""")
salt = secrets.token_bytes(16)
conn.execute("INSERT INTO users VALUES (1, 'yardlead', ?, ?, 'yard_lead')",
             (salt.hex(), hash_pw("demo1234", salt)))
salt2 = secrets.token_bytes(16)
conn.execute("INSERT INTO users VALUES (2, 'yardview', ?, ?, 'viewer')",
             (salt2.hex(), hash_pw("view1234", salt2)))
couriers = [
    (1, "Karim S.", "North Gate Office", "Tanta North"),
    (2, "Omar E.", "North Gate Office", "Tanta South"),
    (3, "Mahmoud R.", "Sahel Partners", "El Mahalla 1"),
    (4, "Youssef A.", "Sahel Partners", "El Mahalla 2"),
    (5, "Hassan M.", "Delta Lines", "Kafr El Zayat"),
    (6, "Ali T.", "Delta Lines", "Zefta"),
    (7, "Mostafa N.", "North Gate Office", "Santa"),
    (8, "Adel F.", "Delta Lines", "Basyoun"),
]
conn.executemany("INSERT INTO couriers VALUES (?, ?, ?, ?)", couriers)
today = "2026-10-24"
checks = [
    # Karim is fully ready and already out
    (1, today, 1, 1, 86, 1, 1, 1, ""),
    # Omar is ready, still in the yard
    (2, today, 1, 1, 64, 1, 1, 0, ""),
    # Mahmoud's phone is nearly dead
    (3, today, 1, 1, 12, 1, 1, 0, "His charger is dead, waiting on a power bank from the store"),
    # Youssef's van failed its check
    (4, today, 1, 0, 78, 1, 1, 0, "Front tyre worn out, maintenance has been told"),
    # Ali is checked in, but his app is not confirmed working
    (6, today, 1, 1, 45, 0, 1, 0, "The app keeps freezing, reinstalling it now"),
    (7, today, 0, 0, None, 0, 0, 0, "Called in sick"),
    (8, today, 1, 1, 91, 1, 0, 0, ""),
]
conn.executemany("INSERT INTO checklist VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", checks)
yesterday = [
    (1, "2026-10-23", 1, 1, 77, 1, 1, 1, ""),
    (2, "2026-10-23", 1, 1, 58, 1, 1, 1, ""),
    (3, "2026-10-23", 1, 1, 83, 1, 1, 1, ""),
    (4, "2026-10-23", 1, 1, 40, 1, 1, 0, ""),
    (5, "2026-10-23", 1, 1, 22, 1, 1, 0, "Weak phone battery"),
    (6, "2026-10-23", 1, 0, 70, 1, 1, 0, "Van check never came back"),
    (7, "2026-10-23", 1, 1, 66, 0, 1, 0, ""),
    (8, "2026-10-23", 1, 1, 88, 1, 0, 0, ""),
    (1, "2026-10-22", 1, 1, 71, 1, 1, 1, ""),
    (2, "2026-10-22", 1, 1, 90, 1, 1, 1, ""),
    (3, "2026-10-22", 1, 1, 61, 1, 1, 1, ""),
    (4, "2026-10-22", 1, 1, 52, 1, 1, 1, ""),
    (5, "2026-10-22", 0, 0, None, 0, 0, 0, "Absent"),
    (6, "2026-10-22", 1, 1, 18, 1, 1, 0, ""),
    (7, "2026-10-22", 1, 1, 79, 1, 1, 0, ""),
    (8, "2026-10-22", 1, 0, 83, 1, 1, 0, ""),
    (1, "2026-10-21", 1, 1, 80, 1, 1, 1, ""),
    (2, "2026-10-21", 1, 1, 69, 1, 1, 0, ""),
    (3, "2026-10-21", 1, 1, 25, 1, 1, 0, ""),
    (4, "2026-10-21", 1, 1, 74, 0, 1, 0, ""),
    (5, "2026-10-21", 1, 1, 95, 1, 1, 1, ""),
    (1, "2026-10-20", 1, 1, 84, 1, 1, 1, ""),
    (2, "2026-10-20", 1, 0, 60, 1, 1, 0, ""),
    (3, "2026-10-20", 1, 1, 47, 1, 0, 0, ""),
    (4, "2026-10-20", 1, 1, 92, 1, 1, 1, ""),
    (5, "2026-10-20", 1, 1, 55, 1, 1, 0, ""),
]
conn.executemany("INSERT INTO checklist VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", yesterday)
conn.commit(); conn.close()
print("Seeded", DB)
