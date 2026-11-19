"""What every task's custom action gets: a Task.

    @task("ArenaFarm", "Arena")          # custom action name, log prefix
    def arena(t: Task):
        held = t.need(read_fraction(t.c, "Arena_Tickets"), "could not read the arena tickets")
        t.run_times("Arena_Run", min(t.settings["tickets"], held[0]), noun="challenge")
        t.log("done")

Returning means the task succeeded. Anything that means it can't go on
raises Stop, already logged, and the action returns False:

  t.fail(why)     an unexpected failure: Retry from Home runs once.
  t.give_up(why)  a Safety stop: stops the whole run (GLOSSARY.md).
  t.check()       ends the task if the user pressed Stop.

Settings: t.settings is one dict of every setting the GUI's options put on
this task: its own node's custom_action_param plus its Settings nodes' (the
other nodes with the same custom_action). Keys are unique across them
(tests/test_interface.py); the defaults are the pipeline nodes' params.
"""
import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok
from gui import say


class Stop(Exception):
    """The task can't go on (already logged)."""


def param_of(node_data) -> dict:
    """A node's custom_action_param, as a dict."""
    param = ((node_data or {}).get("action") or {}).get("param", {}).get("custom_action_param")
    param = json.loads(param or "{}") if isinstance(param, str) else param
    return param or {}


def action_of(node_data):
    """The custom_action a node runs, or None."""
    action = (node_data or {}).get("action") or {}
    return action.get("param", {}).get("custom_action") if action.get("type") == "Custom" else None


def settings_nodes(get_node_data, node_list, action: str) -> list:
    """Every node that runs custom action `action`: a task's own node and its
    Settings nodes."""
    return [n for n in node_list if action_of(get_node_data(n)) == action]


def number(value):
    """A typed-in whole number ("5") as an int; anything else as it is."""
    return int(value) if isinstance(value, str) and value.strip().isdigit() else value


class Task:
    def __init__(self, context: Context, argv: CustomAction.RunArg, action: str, name: str):
        self.c = context
        self.name = name
        self._action = action
        self._own = argv.custom_action_param
        self._settings = None

    # -- settings

    @property
    def settings(self) -> dict:
        if self._settings is None:
            merged = {}
            for node in settings_nodes(self.c.get_node_data, self.c.tasker.resource.node_list, self._action):
                merged.update(param_of(self.c.get_node_data(node)))
            # The node being run: its param as this run got it.
            merged.update(param_of({"action": {"param": {"custom_action_param": self._own}}}))
            self._settings = {k: number(v) for k, v in merged.items()}
        return self._settings

    # -- logging and stopping

    def log(self, msg: str):
        say(self.c, self.name, msg)

    def fail(self, why: str):
        """End the task: something unexpected (the retry from Home runs once)."""
        self.log(why)
        raise Stop()

    def give_up(self, why: str):
        """End the whole run: something only the user can fix (not enough
        Dawnium or gold), or a safety stop where running more won't help. The
        retry from Home doesn't run, and neither do later tasks (they may need
        the same Dawnium)."""
        self.log(f"Stopped: {why}")
        self.c.tasker.post_stop()
        raise Stop()

    def check(self):
        """End the task if a stop was requested (the Stop button, give_up)."""
        if self.c.tasker.stopping:
            self.fail("stop requested")

    def need(self, value, why: str):
        """`value`, unless it's None (a reading failed): then fail(why)."""
        if value is None:
            self.fail(why)
        return value

    # -- running pipeline nodes

    def run(self, entry: str, override=None, fail: str = None):
        """Run pipeline `entry`: its detail, or None if it failed. With
        `fail`, a failure ends the task with that message instead."""
        detail = self.c.run_task(entry, pipeline_override=override or {})
        if ok(detail):
            return detail
        if fail:
            self.fail(fail)
        return None

    def step(self, entry: str, label: str, override=None):
        """One run inside the task's loop: ends the task if a stop was
        requested, logs `label` (e.g. "run 2/5"), runs `entry`; ends the
        task if it fails. Returns its detail."""
        self.check()
        self.log(label)
        return self.run(entry, override, fail=f"{label} failed")

    def run_times(self, entry: str, count: int, noun: str = "run"):
        for i in range(count):
            self.step(entry, f"{noun} {i + 1}/{count}")


def task(action: str, name: str):
    """Register `fn(t)` as custom action `action`, logging as `name`."""
    def register(fn):
        class Action(CustomAction):
            def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
                try:
                    fn(Task(context, argv, action, name))
                except Stop:
                    return False
                return True

        Action.__name__ = Action.__qualname__ = fn.__name__
        AgentServer.custom_action(action)(Action)
        return fn
    return register
