# Security — Dispatch Ready

Local demo posture, stated plainly. This version runs on one machine at one
station gate; it is not hardened for the public internet.

- Passwords are stored as PBKDF2 hashes with a per-user salt. The seed's demo
  passwords (yardlead / demo1234, yardview / view1234) are printed in the
  README on purpose and must be changed before the app holds a real yard.
- Every route except login and health sits behind a bearer token. The viewer
  role is read-only; admin-only routes (backup) refuse it.
- The gate rule is enforced in the backend, not the page: a departure request
  with an incomplete checklist is refused with the blocker list attached, and
  a phone percentage outside 0–100 is rejected outright.
- All SQL is parameterised. Errors are structured JSON; no stack traces or
  SQL leak through the API.
- CSV import is capped, validates its header as a whole, and names duplicate
  and rejected rows instead of overwriting the lead's records.

Not done, on purpose, for a local demo: no TLS, no rate limiting on login,
tokens live in server memory and die with the process. Put it behind a real
proxy and a real secret before it leaves the building.
