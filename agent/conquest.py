"""Conquest: run up to `runs` times, limited by the daily attempts left
("Daily Challenge Attempts: N/2" on the Conquest page)."""
import json
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok
from gui import say

ATTEMPTS_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def log(context: Context, msg: str):
    say(context, "Conquest", msg)


def attempts_left(context: Context):
    image = context.tasker.controller.post_screencap().wait().get()
    reco = context.run_recognition("Conquest_Attempts", image)
    if reco and reco.hit:
        m = ATTEMPTS_RE.search(reco.best_result.text)
        if m:
            return int(m.group(1))
    return None


@AgentServer.custom_action("ConquestFarm")
class ConquestFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        wanted = int(param.get("runs", 1))

        left = attempts_left(context)
        if left is None:
            log(context, "could not read the attempts left")
            return False
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
