# Critique, Dispatch Ready

## Redesign pass, 2026-10-24 (neo-brutalist field signage + English conversion)

This file did not exist before this pass; the redesign is its first entry.

**What changed.** The frontend was rebuilt from the Arabic green field-ops
page into the Neo-Brutalist Field Signage direction from DESIGN-RESEARCH.md
(section 3.3): hazard yellow and black, 3px borders, hard offset shadows,
poster-size state words, courier slabs that flip fully green when READY and
black when OUT, buttons that depress by their full shadow offset. Everything
user-facing is English now: the page (LTR), the seeded exception notes and
comments in `backend/seed.py`, the one Arabic API error message and one
Arabic code comment in `backend/app.py` (copy only, no logic moved), plus
new DESIGN.md and SECURITY.md. README and CHANGELOG were already English;
the CHANGELOG gained a 0.4 entry.

**Evidence.**
- Tests before: `tests/test_api.py` passed (16 assertions) and
  `tests/test_deepening.py` passed 53/53. Total 69 checks.
- Tests after: identical. `Dispatch ready api tests passed`,
  `Dispatch deepening tests passed (53 checks)`. No test edits were needed;
  the suites assert behaviour and counts, not page copy.
- Numbers unchanged: the seed still boards 8 couriers for 2026-10-24 and the
  API tests re-assert the gate outcomes on it, the same 1 departed,
  1 ready, 6 blocked split the seed has always produced (two fully checked
  couriers, one of them departed; six held across phone, van, app, route,
  absence and no-checklist reasons). The phone threshold is still 30% and a
  140% phone value is still rejected by the backend.
- The new page serves at `/` with HTTP 200 and the English title; a scan of
  the whole project tree (excluding .db/.log binaries) finds zero lines
  containing Arabic characters.

**Gaps, honestly.**
- The redesign was verified over HTTP and by the API suites, not clicked
  through in a real browser in this environment; the two-meter readability
  claim of the signage direction is a design target checked by type sizes
  (44px state words), not by standing in a yard with a phone.
- Departed slabs restyle their checklist inputs for the black ground, but a
  departed courier's controls stay editable in the page, as they were before
  the redesign, the backend remains the authority on what can change.
- Google Fonts is a view-time network dependency; offline, Archivo Black
  falls back to Arial Black, which keeps the shout but loses the cut of the
  letterforms.
