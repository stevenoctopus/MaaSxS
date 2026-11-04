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
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, settings_node, task_settings
from gui import say
from purchase import buy_daily
from screen import hit, read_int, screenshot

# (param key, name, title pattern on the list tile and the realm's tab, tile roi,
#  roi of the tile's tool-count badge)
REALMS = [
    ("ironvein", "Ironvein Pit", r"^Ironvein\s?Pit$", [20, 440, 300, 60], [318, 168, 40, 34]),
    ("gilded", "Gilded Depths", r"^Gilded\s?Depths$", [370, 440, 300, 60], [670, 168, 40, 34]),
    ("dread", "Dread Hollow", r"^Dread\s?Hollow$", [20, 950, 280, 60], [318, 672, 40, 34]),
    ("dustfall", "Dustfall Dune", r"^Dustfall\s?Dune$", [370, 945, 300, 60], [670, 672, 40, 34]),
]


def log(context: Context, msg: str):
    say(context, "Material Realms", msg)


def open_realm(context: Context, tile: str, roi) -> bool:
    return ok(context.run_task("MaterialRealms_OpenRealm", pipeline_override={
        "MaterialRealms_OpenRealm": {"expected": tile, "roi": roi},
        "MaterialRealms_OnRealm": {"all_of": [
            "Screen_MaterialTitle",
            {"recognition": "OCR", "expected": tile, "roi": [150, 1185, 210, 50]}]}}))


# ---------------------------------------------------------------- buying

def buy_sets(context: Context, name: str, wanted: int) -> bool:
    """On a realm's page: buy sets so that `wanted` have been bought today
    (a daily total, see agent/purchase.py)."""
    return buy_daily(context, f"Material Realms: {name}", wanted,
                     "MaterialRealms_Buy_Open", "MaterialRealms_OnRealmAgain") is not None


# ---------------------------------------------------------------- using

def quick_on(context: Context) -> bool:
    return hit(context, "MaterialRealms_QuickOn")


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


@AgentServer.custom_action("MaterialRealms")
class MaterialRealms(CustomAction):
    """Visit each realm once: buy (MaterialRealms_Buy's param), then use
    (this node's param). Realms with nothing to buy or use aren't opened."""
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        buy = settings_node(context, "MaterialRealms_Buy")
        use = task_settings(argv)
        # Tools held per realm, from the badges on the list (no badge = 0).
        image = screenshot(context)
        held = {}
        for key, _, _, _, badge in REALMS:
            held[key] = read_int(context, "MaterialRealms_ListCount", image,
                                 {"MaterialRealms_ListCount": {"roi": badge}}) or 0
        log(context, "tools: " + ", ".join(f"{name} {held[key]}" for key, name, *_ in REALMS))

        for key, name, tile, roi, _ in REALMS:
            sets = int(buy.get(key, 0))
            amount = str(use.get(key, "ALL"))
            use_some = amount.upper() == "ALL" or int(amount) > 0
            if sets <= 0 and (not use_some or held[key] == 0):
                continue  # nothing to buy, and nothing to use (or no tools)
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
