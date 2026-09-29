"""The plain-English instructions published to the Sheet's "Read Me" tab
(sheets/publish.py) for a non-technical reader. Built from
score.fit_score.people() rather than hardcoded names, so it reads
correctly for however many people are actually using the Sheet: two
housemates, four, or a household that forked this repo entirely. Kept as
a plain string, one line per row when it lands in the sheet, not
markdown, since Sheets doesn't render it."""
from __future__ import annotations

from score.fit_score import people


def _columns(suffix: str, names: list[str]) -> str:
    return ", ".join(f"{name}_{suffix}" for name in names) if names else f"<yourname>_{suffix}"


def _build_readme_text() -> str:
    names = people()
    rating_cols = _columns("rating", names)
    comment_cols = _columns("comment", names)
    value_cols = _columns("value", names)
    weight_cols = _columns("weight", names)

    return f"""
HOW THIS SPREADSHEET WORKS

This is where we track rental listings, rate them, and note what actually matters to each of us, so we can quickly agree on what's worth inspecting. This spreadsheet is the only place you need to set or change any of that: nothing here requires touching code or files on anyone's computer.

This tab, and the other three, get refreshed from our shared database every so often (whoever has this project set up locally runs `python refresh.py`). If something looks off, or numbers change after you've edited them, just say so rather than assuming you broke it.

===== THE "LISTINGS" TAB =====

One row per listing we've saved, newest/most-relevant first. Most columns fill in automatically. Three are for you to edit directly in the sheet, in the column with YOUR OWN name on it:

status: leave blank until something happens, then write one of:
  inspecting   we've booked / gone to an inspection
  applied      we've applied
  rejected     we're not going for it
  (or any other short note; it's a free text field, not a fixed list)

<yourname>_rating: your own gut score, 1 to 10, after actually looking at the listing (click the "url" column to open it: photos, description, floorplan if there is one). Right now that's: {rating_cols}.
  1-3   no
  4-6   maybe / meh
  7-8   good, want to see it in person
  9-10  love it

<yourname>_comment: anything you want to note. "Kitchen looks tiny", "love the balcony", whatever's useful to remember. Right now that's: {comment_cols}.

Any other column with someone else's name on it is the same idea for them. You don't need to touch those. A few computed columns are worth understanding, even though you don't edit them directly:

"_fit_score" (0-10) is how well a listing matches your weights on the Preferences tab. Important: it's a RANKING relative to the listings currently saved, not a fixed score. It can shift a little as more listings get added, even for one you've already looked at. With only a handful of listings saved, treat it as a rough sort order, not a precise verdict.

"predicted_weekly_rent" / "pct_over_or_under" is a different, separate signal: is this listing under- or over-priced for what it offers, based on a small price model, nothing to do with your personal taste. It needs ~50+ listings before it's worth trusting; with the few we have so far, treat it as indicative at best.

"lease_term_months" / "available_from" come from the listing itself: the lease length, if the agent states one (blank if not), and the date it's available to move in.

"commute_transit_minutes" / "nearest_train_station_walk_minutes" are the raw numbers behind two of the weighted features below, in case you want to judge those yourself rather than rely on the fit score alone. "nearest_rail_walk_minutes" is the walk to whichever is closest of a train, metro or light rail stop. "combined_fit_score" combines everyone's fit scores into one number to sort by. It's a "harmonic" average, so a listing one person loves and the other doesn't scores lower than a plain average would (9 and 3 gives 4.5, not 6).

"suggested_action" is the computer's best guess at what to do next, based on everyone's ratings and hard filters (see the "Hard filters" tab below). It's a suggestion, not a decision. We still decide together.

===== THE "LISTINGS - DETAIL" TAB =====

Most features (air conditioning, fly screens, whether the kitchen looks modern, etc.) are guessed by scanning the listing's own description for certain words, which misses anything only visible in photos, or only noticed at an actual inspection (the 3rd bedroom being small but fitting two desks is exactly this kind of thing). This tab is where you fix that: one row per listing, one column per feature, so you can correct or fill in anything the computer got wrong or couldn't tell from the text alone.

Tick or untick a checkbox to correct a yes/no feature; write a number for the lease term and the two size fields, and a date for "Available from". A correction here STICKS: it's saved straight to the listing's own record, so a later refresh won't silently reset it back to the computer's guess.

One column, "Smallest bedroom fits two desks (WFH)", is deliberately NOT a checkbox. It starts genuinely blank (nobody's checked) rather than showing "no" by default, so you can tell "not reviewed yet" apart from "reviewed, and it doesn't fit." Tick it once someone's actually looked.

===== THE "HARD FILTERS" TAB =====

These are your dealbreakers. Anything failing even one of these gets automatically flagged to skip, before it's worth anyone reading it properly. One row per filter, your column is <yourname>_value (right now that's: {value_cols}). See "what_this_means" for what each one does; a blank cell means that filter doesn't apply to you at all (not zero, just switched off). If a listing is missing data for one of these (e.g. its commute time never parsed), it's given the benefit of the doubt and won't be auto-skipped just because of a data gap. For example:

- max_weekly_rent_aud: write a number, e.g. 1100
- min_bedrooms: write a number, e.g. 3
- min_lease_term_months: write a number, e.g. 12 to rule out "6 month lease only" listings. Listings that don't say a lease length are kept.
- excluded_suburb: write suburb names separated by commas (genuine dealbreaker suburbs you'd never live in), e.g. Parramatta, Blacktown. Leave blank if you don't have any.
- pet_friendly_required: tick the checkbox if you only want pet-friendly places, otherwise leave it unticked

Change these any time. If your budget shifts, just update the cell.

A note on suburbs specifically: excluded_suburb here is a hard cutoff. A listing in one of those suburbs gets thrown away automatically, no exceptions. That's different from "preferred_suburbs_list" + "preferred_suburbs" in the Preferences tab below, which only *boosts* the score for suburbs you like, without ruling anything else out. Most people want both: a short excluded_suburb list for actual dealbreakers, and a preferred_suburbs list for the ones you'd love.

===== THE "PREFERENCES" TAB =====

This is the useful one: it's where you tell the system what YOU actually care about, so it can score new listings roughly the way you would, before anyone's even looked at them properly.

One row is different from the rest: "preferred_suburbs_list" takes actual suburb names (comma-separated, e.g. Bondi, Manly, Parramatta), not a number. It's the list that the "preferred_suburbs" row just below it scores against. Fill in the list, then set how much it matters using the same -5 to 5 scale as everything else.

Every other row is one feature of a listing. See the "what_this_means" column for a plain-English explanation of each one, including a [lower = better] or [higher = better] tag on anything measured in minutes, dollars, or size. In your column, <yourname>_weight (right now that's: {weight_cols}), put a WHOLE NUMBER from -5 to 5 (the sheet will warn you if you type something outside that range):

   5   an absolute must, I really want this
   3   I'd like this, matters a fair bit
   1   slight preference, nice if it's there
   0   don't care either way (or just leave the cell blank)
  -1   slight dislike
  -3   actively don't want this
  -5   basically a dealbreaker

IMPORTANT: for anything tagged [lower = better] (rent, commute time, walk-to-station, etc.), a NEGATIVE number is what rewards a SMALLER value. It's easy to get this backwards: if a short commute matters a lot to you, the instinct is to put a big POSITIVE number, but that would actually reward a LONGER commute instead, since positive weights reward more of whatever's in the column. A couple of examples to calibrate:
- If a short commute matters a lot to you, put something like -4 next to "Public transport time to the office": negative, because LESS time is better.
- If air conditioning would be nice but isn't essential, maybe 2. Amenities like this are tagged [higher = better] (or not tagged at all, if they're just a yes/no), so positive is the intuitive direction there.
- If you genuinely don't care about a swimming pool either way, just leave that row blank.

One more thing: the yes/no columns (air conditioning, dishwasher, pool, etc.) are detected by scanning the listing's own description for certain words, not independently verified. A "no" might just mean the agent didn't mention it in the listing text, not that it's definitely missing. If you spot one that's wrong (from a photo, or at the inspection), fix it in the "Listings - Detail" tab rather than here: this tab is about how much you care, that one's about what's actually true.

You only need to fill in the rows you actually have an opinion on. Blank just means "no opinion," not zero.

If something is a genuine dealbreaker (e.g. "must be under $X" or "must be 3 bedrooms"), put it in the "Hard filters" tab instead of a very negative weight here. Those work differently: they auto-skip a listing entirely, rather than just lowering its score.

Nothing here is final. Change your numbers any time your thinking changes, and the next refresh will pick them up.
"""


README_TEXT = _build_readme_text()
