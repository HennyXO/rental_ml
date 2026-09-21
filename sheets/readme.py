"""The plain-English instructions published to the Sheet's "Read Me" tab
(sheets/publish.py) for a non-technical reader. Kept as a plain string, one
line per row when it lands in the sheet -- not markdown, since Sheets
doesn't render it."""

README_TEXT = """
HOW THIS SPREADSHEET WORKS

This is where we track rental listings, rate them, and note what actually matters to each of us -- so we can quickly agree on what's worth inspecting. This spreadsheet is the only place you need to set or change any of that -- nothing here requires touching code or files on anyone's computer.

This tab, and the other three, get refreshed from our shared database every so often (Leo runs a command for this) -- so if something looks off, or numbers change after you've edited them, just say so rather than assuming you broke it.

===== THE "LISTINGS" TAB =====

One row per listing we've saved, newest/most-relevant first. Most columns fill in automatically. Three are for you to edit directly in the sheet:

status -- leave blank until something happens, then write one of:
  inspecting   we've booked / gone to an inspection
  applied      we've applied
  rejected     we're not going for it
  (or any other short note -- it's a free text field, not a fixed list)

pagni_rating -- your own gut score, 1 to 10, after actually looking at the listing (click the "url" column to open it -- photos, description, floorplan if there is one):
  1-3   no
  4-6   maybe / meh
  7-8   good, want to see it in person
  9-10  love it

pagni_comment -- anything you want to note. "Kitchen looks tiny", "love the balcony", whatever's useful to remember.

Everything with "leo_" or "_fit_score" in the name is the same idea for Leo, or the computer's own guess -- you don't need to touch those.

"suggested_action" is the computer's best guess at what to do next, based on both our ratings and each of our hard filters (see the "Hard filters" tab below). It's a suggestion, not a decision -- we still decide together.

===== THE "HARD FILTERS" TAB =====

These are your dealbreakers -- anything failing even one of these gets automatically flagged to skip, before it's worth either of us reading it properly. One row per filter, your column is pagni_value. See "what_this_means" for what each one does; a blank cell means that filter doesn't apply to you at all (not zero, just switched off). For example:

- max_weekly_rent_aud: write a number, e.g. 1100
- min_bedrooms: write a number, e.g. 3
- allowed_suburbs: write suburb names separated by commas, e.g. Glebe, Leichhardt, Redfern -- leave blank to allow any suburb. Usually you DON'T want this one filled in (see note below).
- pet_friendly_required: write TRUE if you only want pet-friendly places, otherwise leave blank

Change these any time -- if your budget shifts, just update the cell.

A note on suburbs specifically: allowed_suburbs here is a hard cutoff -- a listing one suburb outside your list gets thrown away automatically, even if it would've been great. Most of the time you actually want the softer version instead: leave allowed_suburbs blank, and use "preferred_suburbs_list" + "preferred_suburbs" in the Preferences tab below, which boosts the score for suburbs you like without ruling anything else out entirely.

===== THE "PREFERENCES" TAB =====

This is the useful one: it's where you tell the system what YOU actually care about, so it can score new listings roughly the way you would, before either of us has even looked at them properly.

One row is different from the rest: "preferred_suburbs_list" takes actual suburb names (comma-separated, e.g. Glebe, Leichhardt, Newtown), not a number -- it's the list that the "preferred_suburbs" row just below it scores against. Fill in the list, then set how much it matters using the same -1 to 1 scale as everything else.

Every other row is one feature of a listing -- see the "what_this_means" column for a plain-English explanation of each one. In your column (pagni_weight), put a number:

   1.0   an absolute must, I really want this
   0.5   I'd like this, matters a fair bit
   0.2   slight preference, nice if it's there
   0     don't care either way (or just leave the cell blank)
  -0.2   slight dislike
  -0.5   actively don't want this
  -1.0   basically a dealbreaker

A couple of examples to calibrate:
- If a short commute matters a lot to you, put something like -0.7 next to "Public transport time to the office" -- negative, because LESS time is better.
- If air conditioning would be nice but isn't essential, maybe 0.3.
- If you genuinely don't care about a swimming pool either way, just leave that row blank.

You don't need to fill in every row -- only the ones you actually have an opinion on. Blank just means "no opinion," not zero.

If something is a genuine dealbreaker (e.g. "must be under $X" or "must be 3 bedrooms"), put it in the "Hard filters" tab instead of a very negative weight here -- those work differently (they auto-skip a listing entirely, rather than just lowering its score).

Nothing here is final -- change your numbers any time your thinking changes, and the next refresh will pick them up.
"""
