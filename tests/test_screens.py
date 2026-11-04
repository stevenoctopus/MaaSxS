"""What the agent reads off saved game screens (tests/screens).

    python -m unittest discover tests

Each test shows one real screenshot to the agent's own code through
tools/still.py; nothing touches the emulator. To add a case, capture the
screen with `python tools/still.py capture <name>` and add a test here.
The screens stay on this machine (tests/screens is in .gitignore: they show
the player's name); a test whose screen is missing is skipped.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from still import Still  # noqa: E402  (also puts agent/ on the path)

import crucible  # noqa: E402
import daily_dungeon  # noqa: E402
import grand_mines as gm  # noqa: E402
import material_realms  # noqa: E402
import split_mirage  # noqa: E402
import track  # noqa: E402
import vendor_booth as vb  # noqa: E402
from screen import hit, parse_fraction, parse_int, read_int, screenshot  # noqa: E402

from still import load  # noqa: E402

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
            read_int(c, "MaterialRealms_ListCount", override={"MaterialRealms_ListCount": {"roi": realm.badge_roi}})
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


def image(screen):
    return load(screen)


def near(point, x, y, tol=15):
    return abs(point[0] - x) <= tol and abs(point[1] - y) <= tol


class GrandMines(unittest.TestCase):
    def link_types(self, screen):
        def fn(c):
            img = screenshot(c)
            return [gm.link_type(" ".join(gm.ocr(c, "GrandMines_ChatText", img, (x - 4, y - 4, w + 8, h + 8))))
                    for x, y, w, h in gm.find_links(img)]
        return still.run(screen, fn)

    def test_grand_mine_links(self):
        self.assertEqual(self.link_types("grand_mine_chat_link.png"), ["iron"])
        self.assertEqual(self.link_types("grand_mine_chat_link_home.png"), ["iron"])  # the cut-off top line is ignored

    def test_other_green_links_and_grey_ones(self):
        # A party invite (<Prank Panic...>, over two lines), not a grand mine.
        self.assertEqual(set(self.link_types("resource_hunt_arrived.png")), {None})
        self.assertEqual(gm.find_links(image("grand_mine_depleted.png")), [])  # grey once tapped

    def test_link_moved_up_a_line(self):
        self.assertEqual(gm.relocate((304, 1125, 184, 24), [(29, 1071, 245, 24), (304, 1099, 184, 24)]),
                         (304, 1099, 184, 24))
        self.assertIsNone(gm.relocate((304, 1099, 184, 24), [(29, 1071, 245, 24)]))

    def test_link_type(self):
        self.assertEqual(gm.link_type("<Grand Sand Mine>"), "sand")
        self.assertEqual(gm.link_type("d<Grand Gold Mine>a"), "rolla")  # Rolla's mines are Gold
        self.assertEqual(gm.link_type("<Grand Copper Mine>"), "copper")  # unknown: skipped by the task
        self.assertEqual(gm.link_key("[Nexus] Azraël: Ich habe <Grand Iron Mine> bei", "iron"), "azraël|iron")
        self.assertEqual(gm.link_key("[Nexus]Azraël:Ich habe <Grand Iron Mine>", "iron"), "azraël|iron")
        self.assertIsNone(gm.link_type("<Fierce Monster>"))

    def test_claim_bars(self):
        bars = gm.find_bars(image("afk_zone_iron_bars.png"))
        self.assertEqual(len(bars), 1)
        self.assertTrue(near(bars[0], 463, 537))
        bars = sorted(gm.find_bars(image("grand_mine_on_map.png")))
        self.assertEqual(len(bars), 2)
        self.assertTrue(near(bars[0], 156, 820) and near(bars[1], 361, 716))
        for screen in ("afk_zone_iron_reward.png", "resource_hunt_arrived.png", "grand_mine_chat_link.png"):
            self.assertEqual(gm.find_bars(image(screen)), [], screen)

    def test_flashing_icon(self):
        icons = gm.find_icons(image("resource_hunt_arrived.png"))
        self.assertTrue(near(icons[0], 670, 567), icons)
        self.assertFalse(gm.pin_at_centre(image("resource_hunt_arrived.png")))
        self.assertTrue(near(gm.find_icons(image("grand_mine_same_map.png"))[0], 670, 440))
        self.assertTrue(near(gm.find_icons(image("grand_mine_icon_bottom.png"))[0], 670, 1167))  # past the chat
        self.assertTrue(gm.pin_at_centre(image("grand_mine_on_map.png")))
        self.assertTrue(gm.pin_at_centre(image("afk_zone_iron_bars.png")))
        # Only edge icons get tapped: the Resource Hunt pin sits on an ore rock.
        self.assertTrue(gm.at_edge(gm.find_icons(image("resource_hunt_arrived.png"))[0]))
        self.assertFalse(any(gm.at_edge(i) and near(i, 360, 640) for i in gm.find_icons(image("afk_zone_iron_bars.png"))))

    def test_jump_without_popup(self):
        # A link to a region next door: no popup, no toast, just a new icon at the edge.
        self.assertTrue(gm.new_edge_icon(image("grand_mine_jump_before.png"), image("grand_mine_jump_after.png")))
        self.assertFalse(gm.new_edge_icon(image("grand_mine_jump_after.png"), image("grand_mine_jump_after.png")))
        # Pointing down: the icon sits just above the small chat.
        self.assertTrue(gm.new_edge_icon(image("grand_mine_jump2_before.png"), image("grand_mine_jump2_after.png")))

    def test_tracker_widget(self):
        self.assertTrue(still.run("resource_hunt_arrived.png", lambda c: hit(c, "GrandMines_StopTracking")))
        self.assertFalse(still.run("afk_zone_untracked.png", lambda c: hit(c, "GrandMines_StopTracking")))
        self.assertEqual(gm.find_icons(image("afk_zone_untracked.png")), [])

    def test_floor_is_not_a_rock(self):
        x, y = gm.find_floor(image("afk_zone_iron_bars.png"))
        self.assertFalse(any(abs(x - bx) < 60 and abs(y - by) < 60
                             for bx, by in gm.find_bars(image("afk_zone_iron_bars.png"))))

    def test_resource_hunt_checkmark(self):
        rolla, iron = image("resource_hunt_rolla.png"), image("resource_hunt_iron.png")
        self.assertEqual([gm.hunt_checked(rolla, k) for k in ("rolla", "iron", "sand")], [True, False, False])
        self.assertEqual([gm.hunt_checked(iron, k) for k in ("rolla", "iron", "sand")], [False, True, False])

    def test_toasts(self):
        reward = lambda c: any(gm.REWARD_RE.search(t.strip()) for t in gm.toasts(c, screenshot(c)))  # noqa: E731
        self.assertTrue(still.run("afk_zone_iron_reward.png", reward))
        self.assertTrue(still.run("grand_mine_reward.png", reward))
        self.assertFalse(still.run("grand_mine_same_map.png", reward))
        self.assertTrue(still.run("grand_mine_depleted.png", lambda c: any(
            gm.DEPLETED_RE.search(t) for t in gm.toasts(c, screenshot(c)))))

    def test_energy(self):
        self.assertEqual(still.run("afk_zone_iron_bars.png", lambda c: gm.energy(c, screenshot(c))), 186)
        self.assertEqual(still.run("grand_mine_chat_link_home.png", lambda c: gm.energy(c, screenshot(c))), 183)

    def test_screens(self):
        checks = {
            "Screen_WorldMap": ["grand_mine_on_map.png", "resource_hunt_arrived.png", "afk_zone_iron_reward.png"],
            "Screen_TravelPopup": ["grand_mine_popup.png", "grand_mine_popup_other_map.png", "resource_hunt_popup.png"],
            "Screen_MapExploration": ["resource_hunt_iron.png"],
            "Screen_FullChat": ["chat_full_server_grey_links.png"],
        }
        for node, screens in checks.items():
            for screen in screens:
                self.assertTrue(still.run(screen, lambda c: hit(c, node)), f"{node} on {screen}")
        self.assertFalse(still.run("grand_mine_chat_link_home.png", lambda c: hit(c, "Screen_WorldMap")))


if __name__ == "__main__":
    unittest.main()
