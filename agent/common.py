"""Shared actions and helpers."""
import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from gui import say

def ok(detail) -> bool:
    """True if a run_task result succeeded."""
    return bool(detail and detail.status.succeeded)


def task_settings(argv: CustomAction.RunArg) -> dict:
    """The settings the GUI's options put on this task's own node
    (its custom_action_param)."""
    param = argv.custom_action_param
    param = json.loads(param or "{}") if isinstance(param, str) else param
    return param or {}


def settings_node(context: Context, node: str) -> dict:
    """The settings on a settings node: a node that only holds settings, for
    options that can't go on the task's own node (two options can't both set
    one node's custom_action_param). Includes the task's overrides."""
    data = context.get_node_data(node) or {}
    param = data.get("action", {}).get("param", {}).get("custom_action_param")
    param = json.loads(param or "{}") if isinstance(param, str) else param
    return param or {}


def run_once(context: Context, name: str, entry: str, label: str, override=None):
    """One run of pipeline entry `entry` inside a task's loop: unless a stop
    was requested, log `label` (e.g. "run 2/5") and run it. Returns the
    run's detail, or None if stopping or the run failed (both logged)."""
    if context.tasker.stopping:
        say(context, name, "stop requested")
        return None
    say(context, name, label)
    detail = context.run_task(entry, pipeline_override=override or {})
    if not ok(detail):
        say(context, name, f"{label} failed")
        return None
    return detail


def run_times(context: Context, name: str, entry: str, count: int, noun: str = "run") -> bool:
    """Run `entry` `count` times (see run_once); False if stopped or a run failed."""
    for i in range(count):
        if run_once(context, name, entry, f"{noun} {i + 1}/{count}") is None:
            return False
    return True


def give_up(context: Context, name: str, reason: str) -> bool:
    """Stop on purpose: something only the user can fix (not enough Dawnium
    or gold, or a safety stop where running more won't help). Logs why and
    stops the whole run, so the retry from Home doesn't run and neither do
    later tasks (they may need the same Dawnium). Returns False, for
    `return give_up(...)` in an action."""
    say(context, name, f"Stopped: {reason}")
    context.tasker.post_stop()
    return False


_retrying = False


@AgentServer.custom_action("RetryFromHome")
class RetryFromHome(CustomAction):
    """Used by Common_Retry (on_error of a task's top-level steps): go Home
    and run the current task's entry again, once. If the retried task fails
    too, it lands here again while a retry is running, and we give up.
    Never retries while the run is stopping (give_up() or the Stop button)."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        global _retrying
        if context.tasker.stopping:  # give_up(), or the user pressed Stop
            return False
        if _retrying:
            say(context, "Retry", "failed again after retrying, stopping")
            return False
        detail = context.tasker.get_task_detail(context.get_task_job().job_id)
        entry = detail.entry if detail else None
        if not entry:
            return False
        _retrying = True
        try:
            say(context, "Retry", f"something went wrong: going Home and starting {entry} over")
            if not ok(context.run_task("Common_GoHome")):
                say(context, "Retry", "could not get Home, stopping")
                return False
            return ok(context.run_task(entry))
        finally:
            _retrying = False
