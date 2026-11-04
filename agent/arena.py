"""Arena: buy `buy` tickets (within the daily purchase limit), then challenge
the rightmost opponent `tickets` times, limited by the tickets held ("N/20"
at the top of the Arena page)."""
import json
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, read_fraction
from gui import say


def log(context: Context, msg: str):
    say(context, "Arena", msg)


def read_int(context: Context, node: str):
    image = context.tasker.controller.post_screencap().wait().get()
    reco = context.run_recognition(node, image)
    return int(reco.best_result.text) if reco and reco.hit else None


def buy_tickets(context: Context, wanted: int) -> bool:
    """On the Arena page: buy tickets so that `wanted` have been bought today
    (tickets already bought today count), within the daily purchase limit,
    and end back on the Arena page."""
    if not ok(context.run_task("Arena_Buy_Open")):
        # No popup: today's purchases are used up.
        log(context, "no tickets left to buy today")
        return True
    limit = read_fraction(context, "Arena_Buy_Limit")
    bought, cap = limit if limit else (0, 0)
    count = max(0, min(wanted, cap) - bought)
    if count == 0:
        log(context, f"{bought} ticket(s) already bought today, nothing to buy")
        return ok(context.run_task("Arena_Buy_Cancel"))
    for _ in range(count - 1):  # Qty starts at 1
        context.run_task("Arena_Buy_More")
    shown = read_int(context, "Arena_Buy_Count")
    if shown != count:
        log(context, f"the purchase popup shows {shown}, expected {count}; not buying")
        context.run_task("Arena_Buy_Cancel")
        return False
    log(context, f"buying {count} ticket(s) ({bought} already bought today)")
    if not ok(context.run_task("Arena_Buy_Purchase")):
        log(context, "purchase failed")
        return False
    return True


@AgentServer.custom_action("ArenaFarm")
class ArenaFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        wanted = int(param.get("tickets", 2))
        buy = int(param.get("buy", 0))

        if buy > 0:
            if not buy_tickets(context, buy):
                return False
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
