"""Conquest: run up to `runs` times, limited by the daily attempts left
("Daily Challenge Attempts: N/2" on the Conquest page)."""

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import run_times, task_settings
from gui import say
from screen import read_fraction


def log(context: Context, msg: str):
    say(context, "Conquest", msg)


@AgentServer.custom_action("ConquestFarm")
class ConquestFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = task_settings(argv)
        wanted = int(param.get("runs", 1))

        attempts = read_fraction(context, "Conquest_Attempts")
        if attempts is None:
            log(context, "could not read the attempts left")
            return False
        left = attempts[0]
        runs = min(wanted, left)
        log(context, f"{left} attempt(s) left, running {runs}")
        if not run_times(context, "Conquest", "Conquest_Run", runs):
            return False
        log(context, "done")
        return True
