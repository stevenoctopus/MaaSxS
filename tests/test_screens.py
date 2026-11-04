"""What the agent reads off saved game screens (tests/screens).

    python -m unittest discover tests

Each test shows one real screenshot to the agent's own code through
tools/still.py; nothing touches the emulator. To add a case, capture the
screen with `python tools/still.py capture <name>` and add a test here.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from still import Still  # noqa: E402  (also puts agent/ on the path)

import crucible  # noqa: E402
import daily_dungeon  # noqa: E402
import material_realms  # noqa: E402
import split_mirage  # noqa: E402
import track  # noqa: E402
import vendor_booth as vb  # noqa: E402
from screen import hit, parse_fraction, parse_int, read_int, screenshot  # noqa: E402

still = None


def setUpModule():
    global still
    still = Still()


class Parsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_int("5"), 5)
        self.assertEqual(parse_int("-40%"), 40)
        self.assertEqual(parse_int("Attempt 3/5"), 3)
        self.assertIsNone(parse_int("Refresh"))
        self.assertIsNone(parse_int(None))

    def test_fractions(self):
        self.assertEqual(parse_fraction("Daily Purchase Limit: 2/6"), (2, 6))
        self.assertEqual(parse_fraction("Earned This Week: 120 / 300"), (120, 300))
        self.assertIsNone(parse_fraction("12"))


class VendorBooth(unittest.TestCase):
    def general(self, screen):
        return still.run(screen, lambda c: {
            "general": hit(c, "VendorBooth_OnGeneral"),
            "vault": hit(c, "VendorBooth_OnVault"),
            "left": vb.read_left(c),
            "off": [vb.discount(c, screenshot(c), t) for t in range(9)],
            "sold": [t for t in range(9) if vb.sold_out(c, t)],
        })

    def test_discounts_and_refreshes(self):
        r = self.general("vendor_general_10left.png")
        self.assertTrue(r["general"])
        self.assertFalse(r["vault"])
        self.assertEqual(r["left"], 10)
        self.assertEqual(r["off"], [10, 10, 40, 30, 40, 40, 20, 0, 30])
        self.assertEqual(r["sold"], [])

    def test_seventy_off_and_seven_left(self):
        r = self.general("vendor_general_7left.png")
        self.assertEqual(r["left"], 7)
        self.assertEqual(r["off"], [70, 30, 40, 20, 0, 0, 20, 40, 10])

    def test_sold_out(self):
        r = self.general("vendor_general_soldout.png")
        self.assertEqual(r["sold"], [0])

    def test_vault_page(self):
        r = still.run("vendor_vault.png", lambda c: (
            hit(c, "VendorBooth_OnVault"), hit(c, "VendorBooth_OnGeneral"), vb.sold_out(c, 0)))
        self.assertEqual(r, (True, False, True))  # Free already claimed


class RewardTrack(unittest.TestCase):
    def read(self, screen, ev):
        def fn(c):
            view = track.read_track(c, ev)
            return [(v, marked, claimed) for v, _, marked, claimed in view], track.at_end(c, view)
        return still.run(screen, fn)

    def test_crucible_end(self):
        view, end = self.read("crucible_track_end.png", crucible.CRUCIBLE)
        self.assertTrue(end)
        self.assertEqual(view, [(9.84e9, False, True), (11.3e9, False, True),
                                (13.1e9, False, True), (14.9e9, False, False)])

    def test_crucible_middle(self):
        view, end = self.read("crucible_track_middle.png", crucible.CRUCIBLE)
        self.assertFalse(end)
        self.assertEqual(view[-1], (11.3e9, True, False))  # a gift box, not claimed

    def test_split_mirage_end(self):
        view, end = self.read("split_mirage_track_end.png", split_mirage.SPLIT_MIRAGE)
        self.assertTrue(end)
        self.assertEqual([v for v, *_ in view], [9, 10, 11, 12])
        self.assertTrue(all(claimed for *_, claimed in view))

    def test_todays_best(self):
        self.assertEqual(still.run("split_mirage_track_end.png",
                                   lambda c: track.read_best(c, split_mirage.SPLIT_MIRAGE)), 12)


class MaterialRealms(unittest.TestCase):
    def badges(self, screen):
        return still.run(screen, lambda c: [
            read_int(c, "MaterialRealms_ListCount", override={"MaterialRealms_ListCount": {"roi": realm[4]}})
            for realm in material_realms.REALMS])

    def test_tool_badges(self):
        # Ironvein, Gilded, Dread, Dustfall; None = no badge (no tools held)
        self.assertEqual(self.badges("realms_list_a.png"), [5, None, None, None])
        self.assertEqual(self.badges("realms_list_b.png"), [None, None, 3, None])
        self.assertEqual(self.badges("realms_list_c.png"), [None, None, 6, None])


class DailyDungeon(unittest.TestCase):
    def test_buy_option(self):
        shown = lambda c: daily_dungeon.buy_option_shown(c, wait=0)  # noqa: E731
        self.assertTrue(still.run("dungeon_detail_buy.png", shown))
        self.assertFalse(still.run("dungeon_detail_no_buy.png", shown))  # "Out of daily reward attempts."

    def test_results_grade(self):
        r = still.run("dungeon_results_s.png", lambda c: [
            hit(c, n) for n in ("DailyDungeon_Results", "DailyDungeon_GoodGrade", "DailyDungeon_LowGrade")])
        self.assertEqual(r, [True, True, False])


if __name__ == "__main__":
    unittest.main()
