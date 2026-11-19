"""Retry from Home, and ok() for run_task results. A task's own helpers
are in task.py."""
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from gui import say

def ok(detail) -> bool:
    """True if a run_task result succeeded."""
    return bool(detail and detail.status.succeeded)


_retrying = False


@AgentServer.custom_action("RetryFromHome")
class RetryFromHome(CustomAction):
    """Used by Common_Retry (on_error of a task's top-level steps): go Home
    and run the current task's entry again, once. If the retried task fails
    too, it lands here again while a retry is running, and we give up.
    Never retries while the run is stopping (a Safety stop or the Stop button)."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        global _retrying
        if context.tasker.stopping:  # a Safety stop, or the user pressed Stop
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
