"""Material Realms: buy tool sets with Quick Purchase, then use tools in each
realm. Starts and ends on the Material Realms list.

  MaterialBuy  {"ironvein": sets, ...}  sets of 5 tools per realm, within each
               row's daily purchase limit.
  MaterialUse  {"ironvein": n or "ALL", ...}  tools to use per realm. ALL turns
               Quick Mine / Quick Conquer on (it uses a few tools per tap) and
               taps until no tools are left; a number turns it off and taps
               once per tool.
"""
import json
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common import ok, read_fraction
from gui import say

# (param key, name on the list and on the realm's tab, tile roi, popup row centre y)
REALMS = [
    ("ironvein", "Ironvein Pit", r"^Ironvein\s?Pit$", [20, 440, 300, 60], 445),
    ("gilded", "Gilded Depths", r"^Gilded\s?Depths$", [370, 440, 300, 60], 557),
    ("dread", "Dread Hollow", r"^Dread\s?Hollow$", [20, 950, 280, 60], 669),
    ("dustfall", "Dustfall Dune", r"^Dustfall\s?Dune$", [370, 945, 300, 60], 781),
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


# ---------------------------------------------------------------- buying

def set_row(context: Context, y: int, target: int) -> bool:
    """Step a popup row's Set value to `target`; True if it reads `target`."""
    value_ov = {"MaterialRealms_Buy_Set": {"roi": [495, y - 20, 80, 40]}}
    for _ in range(25):
        value = read_int(context, "MaterialRealms_Buy_Set", value_ov)
        if value is None:
            return False
        if value == target:
            return True
        x = 578 if value < target else 456  # + or -
        context.run_task("MaterialRealms_Buy_Step", pipeline_override={
            "MaterialRealms_Buy_Step": {"target": [x, y - 16, 32, 32]}})
    return False


@AgentServer.custom_action("MaterialBuy")
class MaterialBuy(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        wanted = {k: int(v) for k, v in params(argv).items()}
        if not any(wanted.values()):
            return True
        if not ok(context.run_task("MaterialRealms_Buy_Open")):
            log(context, "could not open Quick Purchase")
            return False

        plan = []
        for key, name, _, _, y in REALMS:
            limit = read_fraction(context, "MaterialRealms_Buy_Limit", {
                "MaterialRealms_Buy_Limit": {"roi": [430, y - 45, 200, 30]}})
            bought, cap = limit if limit else (0, 0)
            sets = max(0, min(wanted.get(key, 0), cap - bought))
            if wanted.get(key, 0) > sets:
                log(context, f"{name}: bought {bought}/{cap} today, buying {sets} set(s)")
            if not set_row(context, y, sets):
                log(context, f"{name}: could not set the amount to {sets}; not buying")
                context.run_task("MaterialRealms_Buy_Cancel")
                return False
            if sets:
                plan.append(f"{name} {sets}")
        if not plan:
            log(context, "nothing left to buy today")
            return ok(context.run_task("MaterialRealms_Buy_Cancel"))
        log(context, "buying sets: " + ", ".join(plan))
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


@AgentServer.custom_action("MaterialUse")
class MaterialUse(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        wanted = params(argv)
        for key, name, tile, roi, _ in REALMS:
            amount = wanted.get(key, "ALL")
            if str(amount).upper() != "ALL" and int(amount) == 0:
                continue
            if not ok(context.run_task("MaterialRealms_OpenRealm", pipeline_override={
                    "MaterialRealms_OpenRealm": {"expected": tile, "roi": roi},
                    "MaterialRealms_OnRealm": {"all_of": [
                        "Screen_MaterialTitle",
                        {"recognition": "OCR", "expected": tile, "roi": [150, 1185, 210, 50]}]}})):
                log(context, f"could not open {name}")
                return False
            done = use_tools(context, name, amount)
            if not ok(context.run_task("MaterialRealms_RealmBack")):
                log(context, f"could not get back to the list from {name}")
                return False
            if not done:
                return False
        return True
