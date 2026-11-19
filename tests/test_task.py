"""agent/task.py: what every task's custom action gets.

    python -m unittest discover tests

The failure handling runs on a stand-in context (no MaaFramework); the
settings are read from the real pipeline through tools/still.py, on a black
screen (no saved screen needed).
"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import still as still_module  # noqa: E402  (also puts agent/ on the path)
from still import Still  # noqa: E402

from task import Stop, Task, task  # noqa: E402

DONE = SimpleNamespace(status=SimpleNamespace(succeeded=True))


class FakeTasker:
    def __init__(self):
        self.stopping = False
        self.stopped = False

    def post_stop(self):
        self.stopped = self.stopping = True


class FakeContext:
    """run_task returns `results[entry]` (None = failed); logs are kept."""

    def __init__(self, results=None):
        self.tasker = FakeTasker()
        self.results = results or {}
        self.ran, self.logs = [], []

    def run_task(self, entry, pipeline_override=None):
        if entry == "Common_Log":
            self.logs.append(pipeline_override["Common_Log"]["focus"]["Node.Action.Starting"])
            return DONE
        self.ran.append(entry)
        return self.results.get(entry)


def argv(param=None):
    return SimpleNamespace(custom_action_param=json.dumps(param or {}))


def run_action(name, context, param=None):
    return still_module._AgentServer.actions[name]().run(context, argv(param))


@task("Test_Succeeds", "Test")
def succeeds(t):
    t.log("hello")


@task("Test_Fails", "Test")
def fails(t):
    t.run("Missing", fail="could not do it")
    t.log("not reached")


@task("Test_GivesUp", "Test")
def gives_up(t):
    t.give_up("not enough Dawnium")


@task("Test_Steps", "Test")
def steps(t):
    t.run_times("Step", 3)


class Actions(unittest.TestCase):
    def test_returning_is_success(self):
        c = FakeContext()
        self.assertTrue(run_action("Test_Succeeds", c))
        self.assertEqual(c.logs, ["[Test] hello"])

    def test_fail_logs_and_returns_false(self):
        c = FakeContext()
        self.assertFalse(run_action("Test_Fails", c))
        self.assertEqual(c.logs, ["[Test] could not do it"])
        self.assertFalse(c.tasker.stopped)  # the retry from Home still runs

    def test_give_up_stops_the_whole_run(self):
        c = FakeContext()
        self.assertFalse(run_action("Test_GivesUp", c))
        self.assertEqual(c.logs, ["[Test] Stopped: not enough Dawnium"])
        self.assertTrue(c.tasker.stopped)

    def test_run_times(self):
        c = FakeContext({"Step": DONE})
        self.assertTrue(run_action("Test_Steps", c))
        self.assertEqual(c.ran, ["Step"] * 3)
        self.assertEqual(c.logs, ["[Test] run 1/3", "[Test] run 2/3", "[Test] run 3/3"])

    def test_a_failed_step_ends_the_task(self):
        c = FakeContext()
        self.assertFalse(run_action("Test_Steps", c))
        self.assertEqual(c.ran, ["Step"])
        self.assertEqual(c.logs, ["[Test] run 1/3", "[Test] run 1/3 failed"])

    def test_the_stop_button_ends_the_task_before_the_next_step(self):
        c = FakeContext({"Step": DONE})
        c.tasker.stopping = True
        self.assertFalse(run_action("Test_Steps", c))
        self.assertEqual(c.ran, [])
        self.assertEqual(c.logs, ["[Test] stop requested"])

    def test_need(self):
        t = Task(FakeContext(), argv(), "Test_Succeeds", "Test")
        self.assertEqual(t.need(0, "unused"), 0)  # 0 is a reading, not a failure
        with self.assertRaises(Stop):
            t.need(None, "could not read it")


class Settings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.still = Still()

    def settings(self, action, param=None):
        return self.still.run(None, lambda c: Task(c, argv(param), action, "Test").settings)

    def test_own_node_and_settings_nodes(self):
        s = self.settings("VendorBooth", {"discount": 30})
        self.assertEqual(s["discount"], 30)   # the node being run
        self.assertEqual(s["refreshes"], 0)   # VendorBooth_Refreshes
        self.assertEqual(s["vault_stellatie"], 0)  # VendorBooth_Vault_Stellatie
        self.assertEqual(len([k for k in s if k.startswith("vault_")]), 8)

    def test_defaults_come_from_the_pipeline(self):
        s = self.settings("GrandMines", {"mines": "ALL"})
        self.assertEqual(s, {"mines": "ALL", "spot": "sand",
                             "claim_iron": True, "claim_sand": True, "claim_rolla": True})

    def test_typed_numbers_become_ints(self):
        s = self.settings("ArenaFarm", {"tickets": "3", "buy": "0"})
        self.assertEqual((s["tickets"], s["buy"]), (3, 0))
        self.assertEqual(self.settings("MaterialRealms", {"use_ironvein": "ALL"})["use_ironvein"], "ALL")


if __name__ == "__main__":
    unittest.main()
