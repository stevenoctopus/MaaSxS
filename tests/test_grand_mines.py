"""Grand Mines' judgements: what the frames after a tap mean (ClaimWatch,
link_result in agent/grand_mines.py).

    python -m unittest discover tests

Stand-in frames (plain objects with the same fields) cover the timing
rules; saved screens (tests/screens, local only) check real ones. A bug seen
live can become a case here: grand_mines saves its frames to
debug/grand_mines/ when a link goes wrong; copy them to tests/screens.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from still import Still, load  # noqa: E402  (also puts agent/ on the path)

import grand_mines as gm  # noqa: E402
from screen import screenshot  # noqa: E402

SPOT = (300, 500)


def frame(at, bars=(), toasts=(), on_map=True, popup=False, full_chat=False, icons=()):
    """A stand-in Frame."""
    toasts = list(toasts)
    return SimpleNamespace(
        at=at, bars=list(bars), toasts=toasts, on_map=on_map, travel_popup=popup, full_chat=full_chat,
        reward=next((t for t in toasts if gm.REWARD_RE.search(t)), None),
        depleted=any(gm.DEPLETED_RE.search(t) for t in toasts),
        reached=any("target region" in t for t in toasts),
        edge_icons=[i for i in icons if gm.at_edge(i)])


def watch(*frames):
    """ClaimWatch's answer after each frame (tapped at 0)."""
    w = gm.ClaimWatch(SPOT, 0)
    return [w.see(f) for f in frames], w


class Claim(unittest.TestCase):
    def test_reward_toast(self):
        results, w = watch(frame(0.5, [SPOT]), frame(1, [SPOT], ["Raw Ore x4.77K"]))
        self.assertEqual(results, [None, gm.CLAIMED])
        self.assertEqual(w.reward, "Raw Ore x4.77K")

    def test_bars_gone_for_a_while_is_lost(self):
        results, _ = watch(frame(0.5, [SPOT]), frame(1), frame(2.5), frame(4))
        self.assertEqual(results, [None, None, None, gm.LOST])  # gone since 1, 3 s later

    def test_bars_back_restart_the_wait(self):
        results, _ = watch(frame(1), frame(3, [(SPOT[0] + 10, SPOT[1])]), frame(4), frame(6.5))
        self.assertEqual(results, [None, None, None, None])

    def test_other_bars_dont_count(self):
        results, _ = watch(frame(1, [(600, 200)]), frame(4.5, [(600, 200)]))
        self.assertEqual(results, [None, gm.LOST])

    def test_popup_or_another_screen_is_unknown(self):
        self.assertEqual(watch(frame(1, [SPOT], popup=True))[0], [gm.UNKNOWN])
        self.assertEqual(watch(frame(1, [SPOT], on_map=False))[0], [gm.UNKNOWN])

    def test_timeout_is_unknown(self):
        results, w = watch(frame(30, [SPOT], ["Mining..."]), frame(gm.CLAIM_TIMEOUT, [SPOT]))
        self.assertEqual(results, [None, gm.UNKNOWN])
        self.assertEqual(w.toasts, ["Mining..."])  # for the log


class Link(unittest.TestCase):
    before = frame(0)

    def result(self, after, travelled=False):
        return gm.link_result(self.before, after, travelled)

    def test_full_chat_is_missed(self):
        self.assertEqual(self.result(frame(1, on_map=False, full_chat=True)), gm.MISSED)

    def test_popup_is_travel(self):
        self.assertEqual(self.result(frame(1, popup=True)), gm.TRAVEL)

    def test_depleted(self):
        self.assertEqual(self.result(frame(1, toasts=["Ore tracking disabled due to depleted reserves."])),
                         gm.DEPLETED)

    def test_arrived(self):
        self.assertEqual(self.result(frame(1), travelled=True), gm.ARRIVED)
        self.assertEqual(self.result(frame(1, toasts=["You have reached the target region."])), gm.ARRIVED)
        self.assertEqual(self.result(frame(1, icons=[(670, 440)])), gm.ARRIVED)  # a new edge icon

    def test_not_yet(self):
        self.assertIsNone(self.result(frame(1)))
        self.assertIsNone(self.result(frame(1, on_map=False), travelled=True))  # still loading
        before = frame(0, icons=[(670, 440)])
        self.assertIsNone(gm.link_result(before, frame(1, icons=[(672, 442)]), False))  # the same icon


class OnSavedScreens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.still = Still()

    def framed(self, screen, fn):
        return self.still.run(screen, lambda c: fn(gm.Frame(c, screenshot(c))))

    def test_claimed(self):
        w = gm.ClaimWatch((0, 0), 0)
        self.assertEqual(self.framed("afk_zone_iron_reward.png", w.see), gm.CLAIMED)

    def test_link_results(self):
        before = gm.Frame(None, load("grand_mine_jump_before.png"))
        cases = {
            "chat_full_server_grey_links.png": gm.MISSED,
            "grand_mine_popup.png": gm.TRAVEL,
            "grand_mine_depleted.png": gm.DEPLETED,
            "grand_mine_jump_after.png": gm.ARRIVED,
        }
        for screen, expected in cases.items():
            with self.subTest(screen=screen):
                self.assertEqual(self.framed(screen, lambda f: gm.link_result(before, f, False)), expected)


if __name__ == "__main__":
    unittest.main()
