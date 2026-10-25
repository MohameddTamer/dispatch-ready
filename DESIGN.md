# Design, Dispatch Ready

## Concept

Morning dispatch is a yard, not an office. The board is safety signage:
black on hazard yellow, readable from two meters away, operable with gloves,
impossible to misunderstand. A courier's state is not a dot or a chip, it is
the color of his whole slab and a word set at poster size.

## Palette

- Hazard yellow `#FFD21F`, the sign itself, primary actions, the gate
- Black `#111111`, borders, text, hard shadows, the departed state
- Off-white `#F4F1EA`, the ground the signs stand on
- Go green `#17B169`, used only as a full-slab state change: READY
- Signal red `#E5322D`, used only as a full-slab state change and hold reasons

Green and red are never decoration. They are areas, not accents.

## Type

- **Archivo Black**, status words at poster size (READY / HELD / OUT),
  courier names, headings. One weight, no apologies.
- **Space Grotesk** (400/500/700), names, routes, body text, form fields.
  Technical enough for a yard sheet, human enough to read at dawn.

## Signature layout move

Every courier is a full-width slab with a 3px black border and a hard 6px
offset shadow, placed, not floated. The state word occupies its own cell at
display size, so the lead reads the yard by color area before he reads a
single name. The morning counts are one segmented sign across the top
(green segment, red segment, black segment), not three cards.

## Signature interaction

The mechanical button. Every action button carries the full 6px offset
shadow, and pressing it translates the button by exactly that offset while
the shadow collapses to zero, the control physically depresses, like
throwing a switch on a panel. 60ms, linear, no bounce, no fade. The gate
should feel mechanical because it is one.

## Deliberately avoided

- No border radius anywhere, no soft shadows, no gradients.
- No pill badges: state is a word at 44px and a slab of color.
- No KPI stat cards: the counts are one sign, read in one glance.
- No raw native controls: checkboxes are drawn 26px squares that fill black
  with a yellow core; the date field and CSV picker wear the same borders.
- No emoji or icon sets. The brand mark is a drawn yard-sign chevron.
