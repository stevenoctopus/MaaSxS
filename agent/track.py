"""Daily events with a reward track (Crucible of Hieromon, Split Mirage).

Each has a menu showing today's best score and a scrolling track of rewards,
each unlocked at a score. Modes:

  once   one run, then claim; no run if today's best already shows a score.
  marked run until today's best reaches the last marked reward still on the
         track (Crucible's gift boxes, Split Mirage's gems), then claim.
  all    run until it reaches the last reward on the track, then claim.

The track can change from day to day, so marked/all read it first.

Claiming: tapping a claimable reward claims all claimable ones; tapping a
claimed one does nothing; tapping an unreached one opens an info popup. So we
tap the highest reward that today's best has reached.
"""
from dataclasses import dataclass
from typing import Callable

from maa.context import Context

from screen import hit, recognize, screenshot
from task import Task


@dataclass
class TrackEvent:
    name: str                      # the task's name, for the log
    marked: str                    # what the marked rewards are, e.g. "gift box"
    parse: Callable[[str], float]  # OCR text -> score (None if not a score)
    fmt: Callable[[float], str]    # score -> text for the log
    values: str                    # OCR node: the score labels under the rewards
    marker: str                    # recognition node: a marked, unclaimed reward icon
    best: str                      # OCR node: today's best score on the menu
    run: str                       # task: one run, menu to menu
    close: str                     # task: close the claim popup, back to the menu


def read_track(context: Context, ev: TrackEvent):
    """[(value, label_box, is_marked, is_claimed)] for the rewards visible on
    the track, lowest first. The reward icon sits right above its value label."""
    image = screenshot(context)
    reco = recognize(context, ev.values, image)
    out = []
    for r in (reco.filtered_results if reco else []):
        v = ev.parse(r.text)
        if v is None:
            continue
        x, y, w, _ = r.box
        marked = hit(context, ev.marker, image, {ev.marker: {"roi": [x + w // 2 - 40, y - 80, 80, 75]}})
        claimed = hit(context, "Common_TrackClaimed", image,
                      {"Common_TrackClaimed": {"roi": [x + w // 2 - 18, y - 65, 36, 36]}})
        out.append((v, r.box, marked, claimed))
    return sorted(out, key=lambda t: t[0])


def at_end(context: Context, view) -> bool:
    """No bar to the right of the rightmost reward: the track is at its end."""
    if not view:
        return False
    x, y, w, _ = max(view, key=lambda t: t[1][0])[1]
    left = x + w // 2 + 37  # just past the reward's icon
    if left + 16 > 695:  # the panel's right edge: can't tell
        return False
    return hit(context, "Common_TrackNoBar", override={
        "Common_TrackNoBar": {"roi": [left, y - 50, 16, 10]}})


def scan_from_end(context: Context, ev: TrackEvent, find, max_steps=12):
    """Jump to the right end of the track (unless it's already there), then step back towards the start
    until find(view) returns something (view = read_track()). Everything we
    look for is "the highest X", so the first view where X shows up has the
    answer. Returns find's result, or None if the track ran out.

    Claiming one reward claims every reward before it, so once a claimed
    reward shows, everything to its left is claimed too: stop there.
    """
    if not at_end(context, read_track(context, ev)):
        context.run_task("Common_TrackEnd")
    seen = set()
    for _ in range(max_steps):
        view = read_track(context, ev)
        found = find(view)
        if found is not None:
            return found
        if any(claimed for *_, claimed in view):
            return None
        values = {v for v, *_ in view}
        if values <= seen:  # nothing new: we're at the left end
            return None
        seen |= values
        context.run_task("Common_TrackStep")
    return None


def read_best(context: Context, ev: TrackEvent):
    reco = recognize(context, ev.best)
    return ev.parse(reco.best_result.text) if reco else None


def claim_rewards(t: Task, ev: TrackEvent):
    best = read_best(t.c, ev)
    if best is None:
        t.log("could not read today's best, skipping claim")
        return

    def highest_reached(view):
        reached = [(v, box, claimed) for v, box, _, claimed in view if v <= best]
        return reached[-1] if reached else None

    found = scan_from_end(t.c, ev, highest_reached)
    if found is None:
        t.log("no reward reached yet")
        return
    value, (x, y, w, _), claimed = found
    if claimed:
        t.log(f"rewards up to {ev.fmt(value)} already claimed")
        return
    t.log(f"claiming (tapping the {ev.fmt(value)} reward)")
    t.c.run_action("Common_TrackTap", [x + w // 2 - 20, y - 60, 40, 40])
    t.run(ev.close)


def find_target(t: Task, ev: TrackEvent, mode):
    """Score needed for this mode, from today's track. None = nothing left to aim for."""
    if mode == "all":
        found = scan_from_end(t.c, ev, lambda view: view[-1][0] if view else None)
        t.log(f"last reward: {ev.fmt(found)}" if found else "could not read the reward track")
        return found
    # Claimed rewards show a checkmark instead of their icon, so no marked
    # icon left on the track means every marked reward is already claimed.
    found = scan_from_end(
        t.c, ev, lambda view: max((v for v, _, m, _ in view if m), default=None))
    t.log(f"last {ev.marked}: {ev.fmt(found)}" if found else f"no unclaimed {ev.marked} on the track")
    return found


def farm(t: Task, ev: TrackEvent):
    """Run per the task's mode (once | marked | all), then claim. Starts and
    ends on the menu."""
    mode = t.settings["mode"]
    target = None
    if mode == "once":
        # Already played today (a best score shows): just claim.
        best = read_best(t.c, ev)
        if best:
            t.log(f"already played today (best: {ev.fmt(best)}), not running again")
            claim_rewards(t, ev)
            t.log("done")
            return
    else:
        target = find_target(t, ev, mode)
        if target is None:
            claim_rewards(t, ev)
            return
        t.log(f"target: {ev.fmt(target)} today")

    run = 0
    while True:
        if target is not None:
            best = read_best(t.c, ev)
            t.log(f"today's best: {ev.fmt(best) if best is not None else 'unreadable'}")
            if best is not None and best >= target:
                t.log("target reached")
                break
        run += 1
        t.step(ev.run, f"run {run}")
        if mode == "once":
            break
    claim_rewards(t, ev)
    t.log("done")
