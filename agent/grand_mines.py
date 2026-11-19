"""Grand Mines: wait at an AFK spot on the world map and claim grand mines,
until the chosen number is claimed or the user stops the run.

  Farm (GrandMines_Farm)  {"mines": n or "ALL"}   claims to make (ALL: no end)
  Afk  (GrandMines_Afk)   {"spot": "sand"}        Resource Hunt resource to wait at
  GrandMines_Iron / _Sand / _Rolla  {"claim_iron": bool, ...} claim this type or not

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
from functools import cached_property

import numpy as np
from maa.context import Context

from screen import hit, parse_fraction, screenshot
from snapshots import keep
from task import Task, task

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


# ---------------------------------------------------------------- reading
# These read a screenshot (BGR numpy array) with the GrandMines_* nodes in
# grand_mines.json; the tests run them on saved screens.

def boxes(context: Context, node: str, image):
    """The boxes (x, y, w, h) of every result node `node` keeps (filtered_results)."""
    reco = context.run_recognition(node, image)
    return [tuple(int(v) for v in r.box) for r in (reco.filtered_results if reco and reco.hit else [])]


def find_links(context: Context, image):
    """Green links in the small chat: boxes (x, y, w, h), top to bottom.
    Grey links (already mined, or stale) aren't green."""
    # The green blobs (letters, underline), each grown 7 px sideways and 2 px
    # up and down; blobs that touch then are one link (one line).
    grown = [[x - 7, y - 2, x + w + 7, y + h + 2] for x, y, w, h in boxes(context, "GrandMines_Links", image)]
    merged = True
    while merged:
        merged = False
        for i, a in enumerate(grown):
            for b in grown[i + 1:]:
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    a[:] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    grown.remove(b)
                    merged = True
                    break
            if merged:
                break
    x0, y0, w0, h0 = CHAT
    links = []
    for left, top, right, bottom in grown:
        left, top, right, bottom = max(left, x0), max(top, y0), min(right, x0 + w0), min(bottom, y0 + h0)
        if (right - left) * (bottom - top) > 300 and bottom - top >= 12:
            links.append((left, top, right - left, bottom - top))
    return sorted(links, key=lambda b: (b[1], b[0]))


def relocate(box, boxes):
    """The same link in a newer screenshot: same x and width, at its old
    line or above (new messages push lines up). None if it's gone."""
    x, y, w, h = box
    same = [b for b in boxes if abs(b[0] - x) <= 6 and abs(b[2] - w) <= 6 and b[1] <= y + 6]
    return max(same, key=lambda b: b[1]) if same else None


def _neutral(px, lo=60, hi=200) -> bool:
    b, g, r = (int(v) for v in px)
    return max(b, g, r) - min(b, g, r) < 25 and lo <= (b + g + r) / 3 <= hi


# Map buttons with bar-like yellow, never mines (x, y, w, h): the minimap,
# the Timed Packs icon below it (tapping it opens a paid offer), the friends
# button (left), the tracker widget (bottom left).
_BAR_SKIP = [(510, 0, 210, 310), (600, 330, 120, 120), (0, 720, 90, 110), (0, 880, 320, 400)]


def find_bars(context: Context, image):
    """Mines with claims left: the yellow segments of their claim bars (one
    or more per mine, in a grey pill under the mine). Returns where to tap
    each mine (above its bars), as (x, y)."""
    # Segments are 12-19 px wide on bars of 3 or 4 claims, ~27 px on bars of 2.
    segs = [b for b in boxes(context, "GrandMines_Bars", image) if 12 <= b[2] <= 30 and 4 <= b[3] <= 8]
    mines = []
    for x, y, w, h in sorted(segs):
        if any(hx <= x < hx + hw and hy <= y < hy + hh for hx, hy, hw, hh in _BAR_SKIP):
            continue
        for m in mines:  # another segment of a bar already found
            if abs(m[1] - y) <= 3 and 0 < x - m[2] <= 70:
                m[2] = x
                break
        else:
            mines.append([x, y, x])  # leftmost x, y, rightmost x
    # The segments start about 6 px right of the pill's left end; the mine is
    # centred over the pill, ~35 px up.
    return [(left + 30, y - 32) for left, y, _ in mines]


# Buttons with the same frame: the flag (top left), the friends button
# (left), the tracker widget, its gear and the region timer (bottom left);
# the small chat's text; the back button (bottom left). (x, y, w, h)
# An icon can sit over Explore (bottom right): tapping it snaps to the mine.
_ICON_SKIP = [(0, 110, 110, 100), (0, 720, 90, 90), (0, 880, 320, 175), (0, 1055, 600, 110), (0, 1165, 150, 115)]


def _ring(rb):
    """The flashing icon's frame: a black ring (radius rb +-1) in a white band
    (rb+2.5 to rb+5), and the mask of those pixels (the picture inside changes)."""
    s = 2 * (rb + 7) + 1
    d = np.hypot(*(np.mgrid[:s, :s] - s // 2))
    black, white = (d >= rb - 1) & (d <= rb + 1), (d >= rb + 2.5) & (d <= rb + 5)
    t = np.where(black, 20.0, np.where(white, 240.0, 0.0))
    return t, (black | white).astype(np.float64)


_RINGS = [_ring(rb) for rb in range(21, 25)]  # the icon's four sizes
_ICON_TOP = 130  # below the energy bar; the search runs to the screen bottom


def _fast_len(n):
    """The next size with only 2, 3 and 5 as factors (fast FFTs)."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


def find_icons(image, threshold=0.965):
    """The flashing icons on the map, best first, as (x, y): the one that
    snaps the camera to a mine (it points to it from the screen edge, or
    sits over it), and the one that points to our own character when it's
    off screen. They look the same; the caller tells them apart.

    Masked normalised cross-correlation (OpenCV's TM_CCORR_NORMED with a
    mask) of the ring frames, done with FFTs in numpy: real icons score
    0.965+, other round things on the map under 0.89 (Resource Hunt's circles
    score 0.96, but icons are only looked for on the world map).
    MaaFramework's TemplateMatch gives the same scores but took 4 s per
    screenshot (1 s per masked template), too slow to catch a flashing icon."""
    gray = image[_ICON_TOP:].astype(np.float64) @ np.array([0.114, 0.587, 0.299])  # BGR -> grey
    H, W = gray.shape
    shape = (_fast_len(H + 64), _fast_len(W + 64))
    f_img, f_sq = np.fft.rfft2(gray, shape), np.fft.rfft2(gray * gray, shape)
    found = []
    for t, m in _RINGS:
        h, w = t.shape
        # Correlation is convolution with the flipped kernel; keep the "valid" part.
        num = np.fft.irfft2(f_img * np.fft.rfft2((t * m)[::-1, ::-1], shape), shape)[h - 1:H, w - 1:W]
        den = np.fft.irfft2(f_sq * np.fft.rfft2(m[::-1, ::-1], shape), shape)[h - 1:H, w - 1:W]
        score = num / np.sqrt(np.maximum(den, 1e-9) * (t * t * m).sum())
        yy, xx = np.mgrid[:score.shape[0], :score.shape[1]]
        for _ in range(4):  # the best few, 30 px apart
            y, x = np.unravel_index(np.argmax(score), score.shape)
            if score[y, x] < threshold:
                break
            found.append((score[y, x], int(x) + h // 2, int(y) + h // 2 + _ICON_TOP))
            score[(yy - y) ** 2 + (xx - x) ** 2 <= 900] = 0
    icons = []
    for v, x, y in sorted(found, reverse=True):
        if any(bx <= x < bx + bw and by <= y < by + bh for bx, by, bw, bh in _ICON_SKIP):
            continue
        if all(abs(x - ix) > 25 or abs(y - iy) > 25 for ix, iy in icons):
            icons.append((x, y))
    return icons


def at_edge(icon) -> bool:
    """An icon pinned to the screen edge, pointing to something off screen."""
    x, y = icon
    return x < 90 or x > 630 or y < 230 or y > 900


def find_floor(image, near=CENTRE):
    """A spot of plain floor (no rock, mine or player: flat, grey) near
    `near`, to tap so the character walks over. None if there's none."""
    img = image.astype(np.float32)
    gray = img @ np.float32([0.114, 0.587, 0.299])  # BGR -> grey
    hi, lo = img.max(axis=2), img.min(axis=2)
    sat = np.where(hi > 0, (hi - lo) * 255 / np.maximum(hi, 1), 0)  # HSV saturation (0-255)
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
    context.run_action("GrandMines_Tap", pipeline_override={
        "GrandMines_Tap": {"target": [int(x), int(y), 1, 1]}})


def back(context: Context):
    """Android back (Common_Back). Its max_hit counts over the whole task, and
    this one can run for hours: reset it first."""
    context.clear_hit_count("Common_Back")
    context.run_action("Common_Back")


class Frame:
    """One screenshot of the map, and what's on it: each thing is read once,
    the first time it's asked for. `context` can be None for what only
    needs the image (icons)."""

    def __init__(self, context: Context, image, at: float = None):
        self.c, self.image = context, image
        self.at = time.time() if at is None else at

    @cached_property
    def bars(self):
        return find_bars(self.c, self.image)

    @cached_property
    def icons(self):
        return find_icons(self.image)

    @cached_property
    def links(self):
        return find_links(self.c, self.image)

    @cached_property
    def toasts(self):
        return toasts(self.c, self.image)

    @cached_property
    def energy(self):
        return energy(self.c, self.image)

    @cached_property
    def on_map(self) -> bool:
        return hit(self.c, "Screen_WorldMap", self.image)

    @cached_property
    def travel_popup(self) -> bool:
        return hit(self.c, "Screen_TravelPopup", self.image)

    @cached_property
    def full_chat(self) -> bool:
        return hit(self.c, "Screen_FullChat", self.image)

    @property
    def reward(self):
        """Our reward toast ("Raw Ore x4.77K"), or None."""
        return next((t.strip() for t in self.toasts if REWARD_RE.search(t.strip())), None)

    @property
    def depleted(self) -> bool:
        """"Ore tracking disabled due to depleted reserves.": mined out."""
        return any(DEPLETED_RE.search(t) for t in self.toasts)

    @property
    def reached(self) -> bool:
        """"You have reached the target region." after an instant jump."""
        return any("target region" in t for t in self.toasts)

    @property
    def edge_icons(self):
        """Icons pinned to the screen edge, pointing to something off screen."""
        return [i for i in self.icons if at_edge(i)]

    @property
    def pin_at_centre(self) -> bool:
        """The camera is on a mine: its icon sits at the screen centre."""
        return any(abs(x - CENTRE[0]) <= 25 and abs(y - CENTRE[1]) <= 25 for x, y in self.icons)


def new_edge_icon(before: Frame, after: Frame) -> bool:
    """An icon at the screen edge in `after` that isn't in `before`."""
    return any(all(abs(i[0] - o[0]) > 25 or abs(i[1] - o[1]) > 25 for o in before.edge_icons)
               for i in after.edge_icons)


# ---------------------------------------------------------------- judging
# What the frames after a tap mean. No waiting or tapping here, so the tests
# can feed them saved screens, or stand-in frames, in order.

CLAIMED, LOST, UNKNOWN = "claimed", "lost", "unknown"


class ClaimWatch:
    """Watching a claim after tapping the mine at `spot` (at time `tapped`).
    see(frame) for each new frame returns CLAIMED (our reward toast), LOST
    (the bars there gone for GONE_FOR s with no toast: someone else took the
    last claim), UNKNOWN (a popup or another screen, or CLAIM_TIMEOUT s with
    neither), or None: keep watching."""

    def __init__(self, spot, tapped: float):
        self.spot, self.tapped = spot, tapped
        self.gone_since = None
        self.toasts = []    # every toast seen, for the log
        self.reward = None  # the reward toast, once CLAIMED

    def see(self, frame: Frame):
        for text in frame.toasts:
            if text not in self.toasts:
                self.toasts.append(text)
        if frame.reward:
            self.reward = frame.reward
            return CLAIMED
        if frame.travel_popup or not frame.on_map:
            return UNKNOWN
        if any(abs(x - self.spot[0]) <= 30 and abs(y - self.spot[1]) <= 30 for x, y in frame.bars):
            self.gone_since = None
        elif self.gone_since is None:
            self.gone_since = frame.at
        elif frame.at - self.gone_since >= GONE_FOR:
            return LOST
        if frame.at - self.tapped >= CLAIM_TIMEOUT:
            return UNKNOWN
        return None


MISSED, TRAVEL, DEPLETED, ARRIVED = "missed", "travel", "depleted", "arrived"


def link_result(before: Frame, frame: Frame, travelled: bool):
    """After tapping a chat link (`before`: the frame just before the tap):
    MISSED (the full chat opened), TRAVEL (the "Travel to <region> now?"
    popup), DEPLETED (mined out), ARRIVED, or None: keep watching.

    Arrived: on the map, after travelling; or with no popup (same region, or
    a region next to it: an instant jump), "You have reached the target
    region." or just a flashing icon at the edge that wasn't there before."""
    if frame.full_chat:
        return MISSED
    if frame.travel_popup:
        return TRAVEL
    if frame.depleted:
        return DEPLETED
    if (travelled or frame.reached or new_edge_icon(before, frame)) and frame.on_map:
        return ARRIVED
    return None


# ---------------------------------------------------------------- the run

class Run:
    def __init__(self, t: Task):
        self.t, self.c = t, t.c
        wanted = str(t.settings["mines"]).strip()
        self.limit = None if wanted.upper() == "ALL" else int(wanted)
        self.spot = str(t.settings["spot"]).lower()
        self.claim = {k: bool(t.settings[f"claim_{k}"]) for k in TYPES}
        self.claimed = 0
        self.seen = {}        # link_key -> times tried this run
        self.energy = None    # the last energy read

    def frame(self) -> Frame:
        return Frame(self.c, screenshot(self.c))

    # -- guards

    def check(self, frame: Frame = None):
        """Stop requested, or energy went down (a tap hit an ore rock)."""
        self.t.check()
        e = (frame or self.frame()).energy
        if e is not None and self.energy is not None and e < self.energy:
            e = self.frame().energy  # read again: one misread mustn't stop the run
            if e is not None and e < self.energy:
                self.t.give_up(f"energy went down ({self.energy} -> {e}): a tap may have hit an ore rock")
        if e is not None:
            self.energy = e  # it goes up by itself over time

    def done(self) -> bool:
        return self.limit is not None and self.claimed >= self.limit

    # -- the AFK spot

    def go_afk(self):
        self.t.run("GrandMines_ToHunt", fail="could not get to Map Exploration")
        if not hunt_checked(screenshot(self.c), self.spot):
            x = HUNT_X[self.spot]
            self.t.run("GrandMines_HuntPick", {"GrandMines_HuntPick": {"target": [x - 15, HUNT_Y - 15, 30, 30]}})
            if not hunt_checked(screenshot(self.c), self.spot):
                self.t.fail(f"could not select {self.spot} on Resource Hunt")
        self.t.run("GrandMines_HuntGo", fail="could not travel to the Resource Hunt region")
        if not self.snap(wait=8):
            self.t.fail("no icon pointing to the AFK spot")
        floor = find_floor(screenshot(self.c))
        if floor:
            tap(self.c, *floor)  # the character walks over: shorter walks win races
            time.sleep(1)
        # Close Resource Hunt's tracker: its icon would be taken for a link's.
        self.t.run("GrandMines_StopTracking")
        self.check()
        self.t.log(f"waiting at the {self.spot} spot")

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
            frame = self.frame()
            if tapped and frame.pin_at_centre:
                return True
            edge = [i for i in frame.edge_icons
                    if all(abs(i[0] - t[0]) > 25 or abs(i[1] - t[1]) > 25 for t in tried)]
            if edge:
                tried.append(edge[0])
                tap(self.c, *edge[0])
                tapped = True
                time.sleep(1.2)
                if hit(self.c, "Screen_ExploreConfirm", screenshot(self.c)):
                    # The icon sat over Explore and the tap reached the button:
                    # back closes its confirm without spending.
                    self.t.log("the tap opened Explore's confirm: closing it")
                    back(self.c)
                self.check()
                continue
            if frame.pin_at_centre or frame.bars:
                return True
            time.sleep(0.5)
        frame = self.frame()
        return frame.pin_at_centre or bool(frame.bars)

    # -- claiming

    def claim_here(self, kind: str):
        """Claim every mine with bars on screen, nearest the centre first."""
        if not self.claim.get(kind, False):
            return
        tried = []
        while not self.done():
            spots = [s for s in self.frame().bars
                     if all(abs(s[0] - t[0]) > 30 or abs(s[1] - t[1]) > 30 for t in tried)]
            if not spots:
                return
            spot = min(spots, key=lambda s: np.hypot(s[0] - CENTRE[0], s[1] - CENTRE[1]))
            tried.append(spot)
            self.claim_one(spot)

    def claim_one(self, spot):
        tap(self.c, *spot)
        watch = ClaimWatch(spot, time.time())
        while True:
            time.sleep(0.5)
            frame = self.frame()
            self.check(frame)
            result = watch.see(frame)
            if result == CLAIMED:
                self.claimed += 1
                goal = f"/{self.limit}" if self.limit else ""
                self.t.log(f"claimed {watch.reward} ({self.claimed}{goal})")
                return
            if result == LOST:
                self.t.log("someone else got there first")
                return
            if result == UNKNOWN:
                self.t.give_up("unknown result after tapping a grand mine (daily limit?): "
                               "please capture the screen (python tools/still.py capture grand_mine_unknown)"
                               + (f"; messages seen: {watch.toasts}" if watch.toasts else ""))

    # -- chat links

    def next_link(self, frame: Frame):
        """The first green grand mine link of a wanted type not followed yet:
        (box, type, chat line), or None."""
        boxes = frame.links
        texts = [" ".join(ocr(self.c, "GrandMines_ChatText", frame.image, (x - 4, y - 4, w + 8, h + 8)))
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
            line = link_key(" ".join(ocr(self.c, "GrandMines_ChatText", frame.image,
                                         (CHAT[0], y - 6, CHAT[2], h + 12))), kind)
            if self.seen.get(line, 0) >= 2:  # followed, or missed twice
                continue
            self.seen[line] = self.seen.get(line, 0) + 1
            if kind not in self.claim:
                self.t.log(f"skipping a link to an unknown mine type: {text.strip()}")
                continue
            if not self.claim[kind]:
                continue
            return box, kind, line
        return None

    def follow(self, box, kind):
        """Tap a link and claim what's there. Returns MISSED if the tap
        missed the link (it can be tried once more)."""
        self.t.log(f"following a Grand {kind.capitalize()} Mine link")
        before = self.frame()
        # Reading the chat takes a moment, and a new message pushes the link
        # up a line: find it again (same x and width) where it is now.
        box = relocate(box, before.links)
        if box is None:
            self.t.log("the link scrolled out of the chat")
            return None
        x, y, w, h = box
        # The box includes the underline: tap the middle of the letters.
        # Anywhere else in the chat opens the full chat.
        tap(self.c, x + w // 2, y + h // 2 - 3)
        end, travelled, frames = time.time() + 6, False, [before]

        def keep_frames(what):
            keep("grand_mines", [f.image for f in frames] + [screenshot(self.c)], what)

        while time.time() < end:
            time.sleep(0.5)
            frame = self.frame()
            frames = frames[:1] + frames[-4:] + [frame]  # the one before the tap, and the latest
            result = link_result(before, frame, travelled)
            if result == MISSED:
                self.t.log("missed the link (the full chat opened): closing it")
                keep_frames("missed")
                back(self.c)
                return MISSED
            if result == TRAVEL:
                if not self.t.run("GrandMines_Travel"):
                    self.t.log("could not travel there")
                    return None
                travelled, end = True, time.time() + 8
                continue
            if result == DEPLETED:
                self.t.log("already mined out")
                return None
            if result == ARRIVED:
                if not self.snap(wait=6):
                    self.t.log("arrived, but found no icon pointing to the mine")
                    keep_frames("noicon")
                    return None
                claims = self.claimed
                self.claim_here(kind)
                if self.claimed == claims:
                    self.t.log("no claims left there")
                return None
        self.t.log("nothing happened after tapping the link (stale)" if not travelled
                   else "travelled, but the map didn't show")
        keep_frames("link")
        return None

    # -- the loop

    def run(self):
        self.go_afk()
        last_status = time.time()
        while not self.done():
            frame = self.frame()
            self.check(frame)
            if not frame.on_map:
                self.t.log("not on the map: going back to the AFK spot")
                self.go_afk()
                continue
            if self.claim.get(self.spot) and frame.bars:
                self.claim_here(self.spot)
                continue
            link = self.next_link(frame)
            if link:
                box, kind, line = link
                if self.follow(box, kind) != MISSED:
                    self.seen[line] = 2  # done with it
                if not self.done():
                    self.go_afk()
                continue
            if time.time() - last_status >= STATUS_EVERY:
                self.t.log(f"watching chat, {self.claimed} claimed")
                last_status = time.time()
            time.sleep(1)
        self.t.log(f"done: {self.claimed} claimed")


@task("GrandMines", "Grand Mines")
def grand_mines(t: Task):
    Run(t).run()
