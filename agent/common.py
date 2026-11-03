"""Small shared actions."""
import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from gui import say


@AgentServer.custom_action("RunTask")
class RunTask(CustomAction):
    """Run a pipeline entry as one step: the node fails if the entry fails,
    so a task can catch it with on_error (e.g. Common_Retry)."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        entry = (json.loads(argv.custom_action_param or "{}") or {}).get("entry")
        if not entry:
            return False
        detail = context.run_task(entry)
        return bool(detail and detail.status.succeeded)


_retrying = False


@AgentServer.custom_action("RetryFromHome")
class RetryFromHome(CustomAction):
    """Used by Common_Retry (on_error of a task's top-level steps): go Home
    and run the current task's entry again, once. If the retried task fails
    too, it lands here again while a retry is running, and we give up."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        global _retrying
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
            home = context.run_task("Common_GoHome")
            if not (home and home.status.succeeded):
                say(context, "Retry", "could not get Home, stopping")
                return False
            result = context.run_task(entry)
            return bool(result and result.status.succeeded)
        finally:
            _retrying = False
