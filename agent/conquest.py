"""Conquest: run up to `runs` times, limited by the daily attempts left
("Daily Challenge Attempts: N/2" on the Conquest page)."""
import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, read_fraction
from gui import say


def log(context: Context, msg: str):
    say(context, "Conquest", msg)


@AgentServer.custom_action("ConquestFarm")
class ConquestFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        wanted = int(param.get("runs", 1))

        attempts = read_fraction(context, "Conquest_Attempts")
        if attempts is None:
            log(context, "could not read the attempts left")
            return False
        left = attempts[0]
        runs = min(wanted, left)
        log(context, f"{left} attempt(s) left, running {runs}")
        for i in range(runs):
            if context.tasker.stopping:
                log(context, "stop requested")
                return False
            log(context, f"run {i + 1}/{runs}")
            if not ok(context.run_task("Conquest_Run")):
                log(context, f"run {i + 1} failed")
                return False
        log(context, "done")
        return True
