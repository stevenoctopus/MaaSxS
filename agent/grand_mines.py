"""Grand Mines: wait at an AFK spot on the world map and claim grand mines,
until the chosen number is claimed or the user stops the run.

  Farm (GrandMines_Farm)  {"mines": n or "ALL"}   claims to make (ALL: no end)
  Afk  (GrandMines_Afk)   {"spot": "iron"}        Resource Hunt resource to wait at
  GrandMines_Iron / _Sand / _Rolla  {"mine": bool} claim this type or not

The AFK spot: Journal > Map Exploration > Resource Hunt, check the resource,
Go >>, "Enter <region> to explore?" OK, tap the flashing icon (the camera
snaps to the zone), tap empty floor so the character walks over, then close
the Resource Hunt tracker (its icon stays on screen otherwise).

Each second at the spot:
  1. Mines on screen with claim bars (yellow = claims left): claim them.
  2. A green "<Grand X Mine>" link in the small chat: tap it, "Travel to
     <region> now?" OK (not shown when already in that region), tap the
     flashing icon, claim every mine with bars on screen, go back to the spot.
     "Ore tracking disabled due to depleted reserves." = mined out: skip.

A claim: tap the mine; the character walks over and mines it. Our reward
toast ("Raw Ore x4.77K") = claimed. The bars there disappearing with no
toast = someone else took the last claim. One claim at a time: tapping
another mine cancels the first.

Ore rocks (the ⚡5 ones) spend energy when tapped, so taps only go to claim
bars, the flashing icon, green links and checked-empty floor, and the run
stops if energy ever goes down.
"""
import re
import time
from pathlib import Path

import cv2
import numpy as np
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import give_up, ok, settings_node, task_settings
from gui import say
from screen import hit, parse_fraction, screenshot

TYPES = ("iron", "sand", "rolla")
# Resource Hunt: x of each resource's circle (y 350). Essence (281) is not a grand mine.
HUNT_X = {"rolla": 59, "iron": 133, "sand": 207}
HUNT_Y = 350

CENTRE = (360, 640)  # where the camera puts a mine after its icon is tapped
CHAT = (15, 1030, 690, 125)  # the small chat, on Home and on the map (x, y, w, h)

LINK_RE = re.compile(r"Grand\s?(\w+?)\s?Mine", re.I)
REWARD_RE = re.compile(r"[x×]\s?\d[\d.,]*\s?[KMB]?$")
DEPLETED_RE = re.compile(r"depleted", re.I)

CLAIM_TIMEOUT = 60  # s: a claim that neither lands nor goes away
GONE_FOR = 3        # s: bars gone this long with no toast = lost
STATUS_EVERY = 600  # s between "watching" log lines


def log(context: Context, msg: str):
    say(context, "Grand Mines", msg)


def keep(images, what: str):
    """Save screenshots of something that went wrong to debug/grand_mines/."""
    folder = Path("debug") / "grand_mines"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for i, image in enumerate(images):
        cv2.imwrite(str(folder / f"{stamp}_{what}_{i}.png"), image)


# ---------------------------------------------------------------- reading
# These take a screenshot (BGR numpy array) and need no context, so the
# tests can run them on saved screens.

def find_links(image):
    """Green links in the small chat: boxes (x, y, w, h), top to bottom.
    Grey links (already mined, or stale) aren't green."""
    x0, y0, w0, h0 = CHAT
    hsv = cv2.cvtColor(image[y0:y0 + h0, x0:x0 + w0], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (35, 90, 150), (55, 255, 255))
    # Join the letters and underline of one link (one line) into one box.
    mask = cv2.dilate(mask, np.ones((5, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes = [(int(x) + x0, int(y) + y0, int(w), int(h)) for x, y, w, h, a in stats[1:]
             if a > 300 and h >= 12]
    return sorted(boxes, key=lambda b: (b[1], b[0]))


def relocate(box, boxes):
    """The same link in a newer screenshot: same x and width, at its old
    line or above (new messages push lines up). None if it's gone."""
    x, y, w, h = box
    same = [b for b in boxes if abs(b[0] - x) <= 6 and abs(b[2] - w) <= 6 and b[1] <= y + 6]
    return max(same, key=lambda b: b[1]) if same else None


def _neutral(px, lo=60, hi=200) -> bool:
    b, g, r = (int(v) for v in px)
    return max(b, g, r) - min(b, g, r) < 25 and lo <= (b + g + r) / 3 <= hi


def find_bars(image):
    """Mines with claims left: the yellow segments of their claim bars (one
    or more per mine, in a grey pill under the mine). Returns where to tap
    each mine (above its bars), as (x, y)."""
    sub = image[130:1000]
    # The bars' yellow, BGR about (103, 207, 204).
    mask = cv2.inRange(sub, (80, 185, 180), (130, 230, 230))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    segs = [(int(x), int(y) + 130, int(w), int(h)) for x, y, w, h, a in stats[1:]
            if 12 <= w <= 19 and 4 <= h <= 8 and a >= 55]
    mines = []
    for x, y, w, h in sorted(segs):
        if x > 510 and y < 310 or x < 320 and y > 880:  # the minimap; the tracker widget's arrows
            continue
        for m in mines:  # another segment of a bar already found
            if abs(m[1] - y) <= 3 and 0 < x - m[2] <= 70:
                m[2] = x
                break
        else:
            mines.append([x, y, x])  # leftmost x, y, rightmost x
    # The bars are 3 or 4 segments, 22 px apart, from about 6 px right of
    # the pill's left end; the mine is centred over the pill, ~35 px up.
    return [(left + 30, y - 32) for left, y, _ in mines]


def _ring(rb: int):
    """The flashing icon's frame: a thin black ring of radius rb inside a
    white band. Everything else is masked out (the picture inside changes)."""
    s = 2 * (rb + 7) + 1
    c = s // 2
    yy, xx = np.mgrid[:s, :s]
    d = np.hypot(yy - c, xx - c)
    black = (d >= rb - 1) & (d <= rb + 1)
    white = (d >= rb + 2.5) & (d <= rb + 5)
    t = np.full((s, s), 128, np.uint8)
    t[black], t[white] = 20, 240
    return t, ((black | white) * 255).astype(np.uint8)


_RINGS = [_ring(rb) for rb in range(21, 25)]
# Buttons with the same frame: the flag (top left), the friends button
# (left), the tracker widget, its gear and the region timer (bottom left);
# and the small chat's text. (x, y, w, h)
_ICON_SKIP = [(0, 110, 110, 100), (0, 720, 90, 90), (0, 880, 320, 175), (0, 1055, 600, 175)]


def find_icons(image, threshold=0.965):
    """The flashing icons on the map, best first, as (x, y): the one that
    snaps the camera to a mine (it points to it from the screen edge, or
    sits over it), and the one that points to our own character when it's
    off screen. They look the same; the caller tells them apart."""
    # Down to the bottom: an icon pointing down sits above the small chat
    # (y ~1012), or down past it (bottom right, y ~1166).
    gray = cv2.cvtColor(image[130:1230], cv2.COLOR_BGR2GRAY)
    found = []
    for t, m in _RINGS:
        r = np.nan_to_num(cv2.matchTemplate(gray, t, cv2.TM_CCORR_NORMED, mask=m))
        half = t.shape[0] // 2
        for _ in range(4):
            _, v, _, (x, y) = cv2.minMaxLoc(r)
            if v < threshold:
                break
            found.append((v, x + half, y + half + 130))
            cv2.circle(r, (x, y), 30, 0, -1)
    icons = []
    for v, x, y in sorted(found, reverse=True):
        if any(bx <= x < bx + bw and by <= y < by + bh for bx, by, bw, bh in _ICON_SKIP):
            continue
        if all(abs(x - ix) > 25 or abs(y - iy) > 25 for ix, iy in icons):
            icons.append((x, y))
    return icons


def pin_at_centre(image) -> bool:
    """The camera is on a mine: its icon sits at the screen centre."""
    return any(abs(x - CENTRE[0]) <= 25 and abs(y - CENTRE[1]) <= 25 for x, y in find_icons(image))


def at_edge(icon) -> bool:
    """An icon pinned to the screen edge, pointing to something off screen."""
    x, y = icon
    return x < 90 or x > 630 or y < 230 or y > 900


def new_edge_icon(before, after) -> bool:
    """An icon at the screen edge in `after` that isn't in `before`."""
    old = [i for i in find_icons(before) if at_edge(i)]
    return any(at_edge(i) and all(abs(i[0] - o[0]) > 25 or abs(i[1] - o[1]) > 25 for o in old)
               for i in find_icons(after))


def find_floor(image, near=CENTRE):
    """A spot of plain floor (no rock, mine or player: flat, grey) near
    `near`, to tap so the character walks over. None if there's none."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sat = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    best = None
    for y in range(420, 880, 20):
        for x in range(140, 600, 20):
            if gray[y - 40:y + 40, x - 40:x + 40].std() >= 10 or sat[y - 40:y + 40, x - 40:x + 40].mean() >= 40:
                continue
            d = np.hypot(x - near[0], y - near[1])
            if d > 60 and (best is None or d < best[0]):  # not on the pin itself
                best = (d, x, y)
    return best[1:] if best else None


def hunt_checked(image, kind: str) -> bool:
    """Resource Hunt: `kind`'s circle has the checkmark (dark grey fill;
    unchecked is lighter)."""
    x = HUNT_X[kind]
    patch = image[HUNT_Y - 6:HUNT_Y + 6, x - 6:x + 6].reshape(-1, 3).mean(0)
    return _neutral(patch, 70, 118)


# Link names that aren't the Resource Hunt name: Rolla's mines are "Grand Gold Mine".
LINK_NAMES = {"gold": "rolla"}
SENDER_RE = re.compile(r"\]\s?([^:\]]+?)\s?:")


def link_type(text: str):
    """"<Grand Iron Mine>" -> "iron", "<Grand Gold Mine>" -> "rolla"; None
    if it's not a grand mine link. Other names are returned as they are."""
    m = LINK_RE.search(text or "")
    if not m:
        return None
    name = m.group(1).lower()
    return LINK_NAMES.get(name, name)


def link_key(line: str, kind: str) -> str:
    """Who posted which mine, to follow each only once: "[Nexus] Azrael: I
    found <Grand Iron Mine> ..." -> "azrael|iron". OCR reads the same line a
    little differently each time, so the whole line won't do."""
    m = SENDER_RE.search(line or "")
    return f"{m.group(1).strip().lower()}|{kind}" if m else f"{line}|{kind}"


# ---------------------------------------------------------------- with the game

def ocr(context: Context, node: str, image, roi=None):
    """Every text OCR node `node` reads (in `roi`, if given)."""
    override = {node: {"roi": list(roi)}} if roi else {}
    reco = context.run_recognition(node, image, pipeline_override=override)
    return [r.text for r in (reco.all_results if reco else [])]


def toasts(context: Context, image):
    return ocr(context, "GrandMines_Toast", image)


def energy(context: Context, image):
    reco = context.run_recognition("GrandMines_Energy", image)
    frac = parse_fraction(reco.best_result.text) if reco and reco.hit else None
    return frac[0] if frac else None


def tap(context: Context, x: int, y: int):
    context.tasker.controller.post_click(int(x), int(y)).wait()


class Stop(Exception):
    """A safety stop (give_up already called), or the user pressed Stop."""


class Run:
    def __init__(self, context: Context, argv: CustomAction.RunArg):
        self.c = context
        wanted = str(task_settings(argv).get("mines", "ALL")).strip()
        self.limit = None if wanted.upper() == "ALL" else int(wanted)
        self.spot = str(settings_node(context, "GrandMines_Afk").get("spot", "iron")).lower()
        self.claim = {k: bool(settings_node(context, f"GrandMines_{k.capitalize()}").get("mine", True))
                      for k in TYPES}
        self.claimed = 0
        self.seen = {}        # link_key -> times tried this run
        self.energy = None    # the last energy read

    # -- guards

    def check(self, image=None):
        """Stop requested, or energy went down (a tap hit an ore rock)."""
        if self.c.tasker.stopping:
            raise Stop()
        e = energy(self.c, screenshot(self.c) if image is None else image)
        if e is not None and self.energy is not None and e < self.energy:
            e = energy(self.c, screenshot(self.c))  # read again: one misread mustn't stop the run
            if e is not None and e < self.energy:
                give_up(self.c, "Grand Mines", f"energy went down ({self.energy} -> {e}): a tap may have hit an ore rock")
                raise Stop()
        if e is not None:
            self.energy = e  # it goes up by itself over time

    def done(self) -> bool:
        return self.limit is not None and self.claimed >= self.limit

    # -- the AFK spot

    def go_afk(self) -> bool:
        if not ok(self.c.run_task("GrandMines_ToHunt")):
            log(self.c, "could not get to Map Exploration")
            return False
        if not hunt_checked(screenshot(self.c), self.spot):
            x = HUNT_X[self.spot]
            self.c.run_task("GrandMines_HuntPick", pipeline_override={
                "GrandMines_HuntPick": {"target": [x - 15, HUNT_Y - 15, 30, 30]}})
            if not hunt_checked(screenshot(self.c), self.spot):
                log(self.c, f"could not select {self.spot} on Resource Hunt")
                return False
        if not ok(self.c.run_task("GrandMines_HuntGo")):
            log(self.c, "could not travel to the Resource Hunt region")
            return False
        if not self.snap(wait=8):
            log(self.c, "no icon pointing to the AFK spot")
            return False
        image = screenshot(self.c)
        floor = find_floor(image)
        if floor:
            tap(self.c, *floor)  # the character walks over: shorter walks win races
            time.sleep(1)
        # Close Resource Hunt's tracker: its icon would be taken for a link's.
        self.c.run_task("GrandMines_StopTracking")
        self.check()
        log(self.c, f"waiting at the {self.spot} spot")
        return True

    def snap(self, wait: float) -> bool:
        """Get the camera onto the mine the flashing icon points to. Only
        icons at the screen edge are tapped (they point to something off
        screen): a pin over something on screen may sit on an ore rock, like
        the Resource Hunt pin. The edge icon pointing to our own character
        looks the same; tapping it is free, it just snaps to us, so then the
        next one is tried. Done when, after a tap, a pin is at the centre;
        or, with no edge icon, a pin is at the centre or bars are on screen."""
        end = time.time() + wait
        tried, tapped = [], False
        while time.time() < end:
            image = screenshot(self.c)
            if tapped and pin_at_centre(image):
                return True
            edge = [i for i in find_icons(image) if at_edge(i)
                    and all(abs(i[0] - t[0]) > 25 or abs(i[1] - t[1]) > 25 for t in tried)]
            if edge:
                tried.append(edge[0])
                tap(self.c, *edge[0])
                tapped = True
                time.sleep(1.2)
                self.check()
                continue
            if pin_at_centre(image) or find_bars(image):
                return True
            time.sleep(0.5)
        image = screenshot(self.c)
        return pin_at_centre(image) or bool(find_bars(image))

    # -- claiming

    def claim_here(self, kind: str):
        """Claim every mine with bars on screen, nearest the centre first."""
        if not self.claim.get(kind, False):
            return
        tried = []
        while not self.done():
            spots = [s for s in find_bars(screenshot(self.c))
                     if all(abs(s[0] - t[0]) > 30 or abs(s[1] - t[1]) > 30 for t in tried)]
            if not spots:
                return
            spot = min(spots, key=lambda s: np.hypot(s[0] - CENTRE[0], s[1] - CENTRE[1]))
            tried.append(spot)
            self.claim_one(spot)

    def claim_one(self, spot):
        tap(self.c, *spot)
        start, gone, seen = time.time(), None, []
        while time.time() - start < CLAIM_TIMEOUT:
            time.sleep(0.5)
            image = screenshot(self.c)
            self.check(image)
            for text in toasts(self.c, image):
                if REWARD_RE.search(text.strip()):
                    self.claimed += 1
                    goal = f"/{self.limit}" if self.limit else ""
                    log(self.c, f"claimed {text.strip()} ({self.claimed}{goal})")
                    return
                if text not in seen:
                    seen.append(text)
            if hit(self.c, "Screen_TravelPopup", image) or not hit(self.c, "Screen_WorldMap", image):
                break  # a popup or another screen: not something we know
            near = any(abs(x - spot[0]) <= 30 and abs(y - spot[1]) <= 30 for x, y in find_bars(image))
            if near:
                gone = None
            elif gone is None:
                gone = time.time()
            elif time.time() - gone >= GONE_FOR:
                log(self.c, "someone else got there first")
                return
        give_up(self.c, "Grand Mines", "unknown result after tapping a grand mine (daily limit?): "
                "please capture the screen (python tools/still.py capture grand_mine_unknown)"
                + (f"; messages seen: {seen}" if seen else ""))
        raise Stop()

    # -- chat links

    def next_link(self, image):
        """The first green grand mine link of a wanted type not followed yet:
        (box, type, chat line), or None."""
        boxes = find_links(image)
        texts = [" ".join(ocr(self.c, "GrandMines_ChatText", image, (x - 4, y - 4, w + 8, h + 8)))
                 for x, y, w, h in boxes]
        for i, box in enumerate(boxes):
            text = texts[i]
            # A link wrapped onto the next line: read both parts.
            if "<" in text and ">" not in text and i + 1 < len(texts):
                text += " " + texts[i + 1]
            kind = link_type(text)
            if not kind:
                continue
            x, y, w, h = box
            line = link_key(" ".join(ocr(self.c, "GrandMines_ChatText", image, (CHAT[0], y - 6, CHAT[2], h + 12))), kind)
            if self.seen.get(line, 0) >= 2:  # followed, or missed twice
                continue
            self.seen[line] = self.seen.get(line, 0) + 1
            if kind not in self.claim:
                log(self.c, f"skipping a link to an unknown mine type: {text.strip()}")
                continue
            if not self.claim[kind]:
                continue
            return box, kind, line
        return None

    def follow(self, box, kind):
        """Tap a link and claim what's there. Returns \"missed\" if the tap
        missed the link (it can be tried once more)."""
        log(self.c, f"following a Grand {kind.capitalize()} Mine link")
        before = screenshot(self.c)
        # Reading the chat takes a moment, and a new message pushes the link
        # up a line: find it again (same x and width) where it is now.
        box = relocate(box, find_links(before))
        if box is None:
            log(self.c, "the link scrolled out of the chat")
            return
        x, y, w, h = box
        # The box includes the underline: tap the middle of the letters.
        # Anywhere else in the chat opens the full chat.
        tap(self.c, x + w // 2, y + h // 2 - 3)
        end, moved, frames = time.time() + 6, False, [before]
        while time.time() < end:
            time.sleep(0.5)
            image = screenshot(self.c)
            frames = frames[:1] + frames[-4:] + [image]  # the one before the tap, and the latest
            if hit(self.c, "Screen_FullChat", image):
                log(self.c, "missed the link (the full chat opened): closing it")
                keep(frames, "missed")
                self.c.tasker.controller.post_click_key(4).wait()
                time.sleep(1)
                return "missed"
            if hit(self.c, "Screen_TravelPopup", image):
                if not ok(self.c.run_task("GrandMines_Travel")):
                    log(self.c, "could not travel there")
                    return
                moved, end = True, time.time() + 8
                continue
            texts = toasts(self.c, image)
            if any(DEPLETED_RE.search(t) for t in texts):
                log(self.c, "already mined out")
                return
            # Arrived: after the popup; or with no popup (same region, or a
            # region next to it: an instant jump), "You have reached the
            # target region." or just a flashing icon at the edge that wasn't
            # there before the tap.
            arrived = moved or any("target region" in t for t in texts) or new_edge_icon(before, image)
            if arrived and hit(self.c, "Screen_WorldMap", image):
                if not self.snap(wait=6):
                    log(self.c, "arrived, but found no icon pointing to the mine")
                    keep(frames + [screenshot(self.c)], "noicon")
                    return
                claims = self.claimed
                self.claim_here(kind)
                if self.claimed == claims:
                    log(self.c, "no claims left there")
                return
        log(self.c, "nothing happened after tapping the link (stale)" if not moved
            else "travelled, but the map didn't show")
        keep(frames + [screenshot(self.c)], "link")

    # -- the loop

    def run(self) -> bool:
        if not self.go_afk():
            return False
        last_status = time.time()
        while not self.done():
            image = screenshot(self.c)
            self.check(image)
            if not hit(self.c, "Screen_WorldMap", image):
                log(self.c, "not on the map: going back to the AFK spot")
                if not self.go_afk():
                    return False
                continue
            if self.claim.get(self.spot) and find_bars(image):
                self.claim_here(self.spot)
                continue
            link = self.next_link(image)
            if link:
                box, kind, line = link
                if self.follow(box, kind) != "missed":
                    self.seen[line] = 2  # done with it
                if not self.done() and not self.go_afk():
                    return False
                continue
            if time.time() - last_status >= STATUS_EVERY:
                log(self.c, f"watching chat, {self.claimed} claimed")
                last_status = time.time()
            time.sleep(1)
        log(self.c, f"done: {self.claimed} claimed")
        return True


@AgentServer.custom_action("GrandMines")
class GrandMines(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            return Run(context, argv).run()
        except Stop:
            return False
