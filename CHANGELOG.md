# Changelog

## 0.4
The gate got its signage. English only, left to right, rebuilt as neo-brutalist field signage: hazard yellow and black, 3px borders, hard offset shadows, zero radius. Couriers are full-width slabs whose state word sits at poster size; a ready slab flips entirely green, a departed one goes black, and every button physically depresses by its shadow offset when pressed. The three summary cards became one segmented count sign. Archivo Black shouts, Space Grotesk explains, and the checkboxes, date field and CSV picker are all drawn to match. Seeded exception notes were translated to English; the gate rule, the backend and every demo number are untouched. See DESIGN.md and CRITIQUE.md.

## 0.3
CSV import for checklist sheets landed, keyed on courier plus day so a re sent sheet cannot overwrite what the yard lead recorded at the gate. Duplicates are named by courier and day, broken rows by line and reason. A new range report endpoint replays the gate day by day, and the page charts ready against blocked and the blocker reason totals from it, plus a printable daily and weekly report view. Errors are structured JSON everywhere now, the app keeps a rotating log file, configuration moved to environment variables, and the yard lead can take a timestamped database backup from an admin only endpoint. Seed history grew to five days so the trend has something honest to draw. One quiet fix underneath: dates that match the YYYY-MM-DD shape but do not exist are refused now.

## 0.2
Phone charge is a number now, not a tick. A tick said charged for phones at 12 percent and couriers went dark by noon, so the gate reads the percentage and holds anyone under 30. Exception notes sit on the card where the yard lead can actually see them.

## 0.1
First working version. Morning checklist per courier, depart action locked behind a complete checklist.
