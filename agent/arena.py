"""Arena: buy tickets so `buy` have been bought today (a daily total, see
agent/purchase.py), then challenge the rightmost opponent `tickets` times,
limited by the tickets held ("N/20" at the top of the Arena page)."""
import json
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, read_fraction
from gui import say
from purchase import buy_daily


def log(context: Context, msg: str):
    say(context, "Arena", msg)


@AgentServer.custom_action("ArenaFarm")
class ArenaFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        wanted = int(param.get("tickets", 2))
        buy = int(param.get("buy", 0))

        bought = buy_daily(context, "Arena", buy, "Arena_Buy_Open", "Arena_BackOnPage")
        if bought is None:
            return False
        if bought:
            time.sleep(1.5)  # the ticket count updates a moment after buying

        held = read_fraction(context, "Arena_Tickets")
        if held is None:
            log(context, "could not read the arena tickets")
            return False
        runs = min(wanted, held[0])
        log(context, f"{held[0]} ticket(s), using {runs}")
        for i in range(runs):
            if context.tasker.stopping:
                log(context, "stop requested")
                return False
            log(context, f"challenge {i + 1}/{runs}")
            if not ok(context.run_task("Arena_Run")):
                log(context, f"challenge {i + 1} failed")
                return False
        log(context, "done")
        return True
