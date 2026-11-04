"""Recovery (Common_ToTabBar in common.json): getting back to the tab bar
from anywhere when something unexpected happens.

    python -m unittest discover tests

Nothing here names a task: adding a task needs no change to these tests.
A new screenshot in tests/screens is checked automatically; if recovery
doesn't know it, add the screen to Common_TabBar_BackOut (when Android
back is safe there) or give it its own Common_TabBar_* step.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from still import SCREENS, Still  # noqa: E402

from screen import hit  # noqa: E402

# Common_ToTabBar's on_error chain: each stage looks for the same screens.
STAGES = ["Common_ToTabBar", "Common_TabBar_Back1", "Common_TabBar_Back2", "Common_TabBar_StartGame"]

still = None


def setUpModule():
    global still
    still = Still()


def next_names(node):
    return [n["name"] for n in still.resource.get_node_data(node)["next"]]


class Recovery(unittest.TestCase):
    def test_every_stage_knows_the_same_screens(self):
        first = next_names(STAGES[0])
        for stage in STAGES[1:]:
            self.assertEqual(next_names(stage), first, f"{stage}'s next differs from {STAGES[0]}'s")

    def test_every_saved_screen_is_known(self):
        steps = next_names("Common_ToTabBar")
        for path in sorted(SCREENS.glob("*.png")):
            with self.subTest(screen=path.name):
                known = still.run(path.name, lambda c: any(hit(c, s) for s in steps))
                self.assertTrue(known, f"no recovery step recognises {path.name}: it would press back blind")


if __name__ == "__main__":
    unittest.main()
