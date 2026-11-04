"""Shared actions and helpers."""
import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from gui import say

FRACTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def ok(detail) -> bool:
    """True if a run_task result succeeded."""
    return bool(detail and detail.status.succeeded)


def read_fraction(context: Context, node: str, override=None):
    """Run OCR node `node` (with an optional pipeline override) on a fresh
    screenshot and return the first "N/M" in its text as (N, M), or None."""
    image = context.tasker.controller.post_screencap().wait().get()
    reco = context.run_recognition(node, image, pipeline_override=override or {})
    if reco and reco.hit:
        m = FRACTION_RE.search(reco.best_result.text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def give_up(context: Context, name: str, reason: str) -> bool:
    """Stop on purpose: something only the user can fix (not enough Dawnium
    or gold, or a safety stop where running more won't help). Logs why and
    stops the whole run, so the retry from Home doesn't run and neither do
    later tasks (they may need the same Dawnium). Returns False, for
    `return give_up(...)` in an action."""
    say(context, name, f"Stopped: {reason}")
    context.tasker.post_stop()
    return False


@AgentServer.custom_action("RunTask")
class RunTask(CustomAction):
    """Run a pipeline entry as one step: the node fails if the entry fails,
    so a task can catch it with on_error (e.g. Common_Retry)."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        entry = (json.loads(argv.custom_action_param or "{}") or {}).get("entry")
        return bool(entry) and ok(context.run_task(entry))


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
