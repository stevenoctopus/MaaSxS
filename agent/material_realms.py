"""Material Realms: visit each realm once, buy tool sets, then use tools.
Starts and ends on the Material Realms list.

  Buy  (MaterialRealms_Buy) {"ironvein": sets, ...}  sets of 5 tools per realm
       to have bought today (sets already bought today count), within the
       daily purchase limit. Bought on each realm's own page: Quick Purchase
       can't set a realm to 0 once it has bought today.
  Use  (MaterialRealms_Use) {"ironvein": n or "ALL", ...}  tools to use per
       realm. ALL turns Quick Mine / Quick Conquer on (it uses a few tools per
       tap) and taps until no tools are left; a number turns it off and taps
       once per tool.
"""
import json
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, read_fraction
from gui import say

# (param key, name, title pattern on the list tile and the realm's tab, tile roi)
REALMS = [
    ("ironvein", "Ironvein Pit", r"^Ironvein\s?Pit$", [20, 440, 300, 60]),
    ("gilded", "Gilded Depths", r"^Gilded\s?Depths$", [370, 440, 300, 60]),
    ("dread", "Dread Hollow", r"^Dread\s?Hollow$", [20, 950, 280, 60]),
    ("dustfall", "Dustfall Dune", r"^Dustfall\s?Dune$", [370, 945, 300, 60]),
]


def log(context: Context, msg: str):
    say(context, "Material Realms", msg)


def screenshot(context: Context):
    return context.tasker.controller.post_screencap().wait().get()


def read_int(context: Context, node: str, override=None):
    reco = context.run_recognition(node, screenshot(context), pipeline_override=override or {})
    if reco and reco.hit:
        digits = "".join(c for c in reco.best_result.text if c.isdigit())
        return int(digits) if digits else None
    return None


def params(argv):
    return json.loads(argv.custom_action_param or "{}") or {}


def open_realm(context: Context, tile: str, roi) -> bool:
    return ok(context.run_task("MaterialRealms_OpenRealm", pipeline_override={
        "MaterialRealms_OpenRealm": {"expected": tile, "roi": roi},
        "MaterialRealms_OnRealm": {"all_of": [
            "Screen_MaterialTitle",
            {"recognition": "OCR", "expected": tile, "roi": [150, 1185, 210, 50]}]}}))


# ---------------------------------------------------------------- buying

def buy_sets(context: Context, name: str, wanted: int) -> bool:
    """On a realm's page: buy sets so that `wanted` have been bought today
    (sets already bought today count), within the daily purchase limit."""
    if not ok(context.run_task("MaterialRealms_Buy_Open")):
        log(context, f"{name}: the purchase popup didn't open")
        return False
    limit = read_fraction(context, "MaterialRealms_Buy_Limit")
    if limit is None:
        log(context, f"{name}: could not read the purchase limit; not buying")
        context.run_task("MaterialRealms_Buy_Cancel")
        return False
    bought, cap = limit
    sets = max(0, min(wanted, cap) - bought)
    if sets == 0:
        log(context, f"{name}: {bought} set(s) already bought today, nothing to buy")
        return ok(context.run_task("MaterialRealms_Buy_Cancel"))
    for _ in range(sets - 1):  # Qty starts at 1
        context.run_task("MaterialRealms_Buy_More")
    shown = read_int(context, "MaterialRealms_Buy_Count")
    if shown != sets:
        log(context, f"{name}: the purchase popup shows {shown}, expected {sets}; not buying")
        context.run_task("MaterialRealms_Buy_Cancel")
        return False
    log(context, f"{name}: buying {sets} set(s) ({bought} already bought today)")
    return ok(context.run_task("MaterialRealms_Buy_Purchase"))


# ---------------------------------------------------------------- using

def quick_on(context: Context) -> bool:
    reco = context.run_recognition("MaterialRealms_QuickOn", screenshot(context))
    return bool(reco and reco.hit)


def set_quick(context: Context, on: bool) -> bool:
    """Set Quick Mine / Quick Conquer, and check it took."""
    for _ in range(3):
        if quick_on(context) == on:
            return True
        context.run_task("MaterialRealms_QuickToggle")
    return quick_on(context) == on


def use_tools(context: Context, name: str, wanted) -> bool:
    """On a realm's page: use `wanted` tools ("ALL" or a number)."""
    held = read_int(context, "MaterialRealms_ToolCount")
    if held is None:
        log(context, f"{name}: could not read the tools held")
        return False
    use_all = str(wanted).upper() == "ALL"
    goal = 0 if use_all else max(0, held - int(wanted))  # tools left when done
    if held <= goal:
        log(context, f"{name}: {held} tool(s), nothing to use")
        return True
    log(context, f"{name}: {held} tool(s), using {'all' if use_all else held - goal}")

    # ALL: Quick on (faster); a number: Quick off (exactly 1 tool per tap).
    if not set_quick(context, use_all):
        log(context, f"{name}: could not turn Quick {'on' if use_all else 'off'}")
        return False

    stalls = 0
    while held > goal:
        if context.tasker.stopping:
            log(context, "stop requested")
            return False
        context.run_task("MaterialRealms_UseTool")
        now = read_int(context, "MaterialRealms_ToolCount")
        if now is None or now >= held:
            stalls += 1
            if stalls >= 5:  # taps aren't using tools (e.g. a popup is in the way)
                log(context, f"{name}: tools aren't going down, stopping")
                return False
            time.sleep(1)
            continue
        stalls = 0
        if not use_all and now < goal:
            log(context, f"{name}: used more than asked ({held} -> {now})")
        held = now
    log(context, f"{name}: done, {held} tool(s) left")
    return True


def node_param(context: Context, node: str) -> dict:
    """The custom_action_param of another node (with the task's overrides)."""
    data = context.get_node_data(node) or {}
    param = data.get("action", {}).get("param", {}).get("custom_action_param") or {}
    return json.loads(param) if isinstance(param, str) else param


@AgentServer.custom_action("MaterialRealms")
class MaterialRealms(CustomAction):
    """Visit each realm once: buy (MaterialRealms_Buy's param), then use
    (this node's param). Realms with nothing to buy or use aren't opened."""
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        buy = node_param(context, "MaterialRealms_Buy")
        use = params(argv)
        for key, name, tile, roi in REALMS:
            sets = int(buy.get(key, 0))
            amount = str(use.get(key, "ALL"))
            use_some = amount.upper() == "ALL" or int(amount) > 0
            if sets <= 0 and not use_some:
                continue
            if not open_realm(context, tile, roi):
                log(context, f"could not open {name}")
                return False
            done = (sets <= 0 or buy_sets(context, name, sets)) and \
                   (not use_some or use_tools(context, name, amount))
            if not ok(context.run_task("MaterialRealms_RealmBack")):
                log(context, f"could not get back to the list from {name}")
                return False
            if not done:
                return False
        log(context, "done")
        return True
