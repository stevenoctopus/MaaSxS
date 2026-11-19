"""Material Realms: visit each realm once, buy tool sets, then use tools.
Starts and ends on the Material Realms list.

  Buy  (MaterialRealms_Buy) {"buy_ironvein": sets, ...}  sets of 5 tools per
       realm to have bought today (sets already bought today count), within
       the daily purchase limit. Bought on each realm's own page: Quick
       Purchase can't set a realm to 0 once it has bought today.
  Use  (MaterialRealms_Use) {"use_ironvein": n or "ALL", ...}  tools to use
       per realm. ALL turns Quick Mine / Quick Conquer on (it uses a few tools
       per tap) and taps until no tools are left; a number turns it off and
       taps once per tool.
"""
import time
from dataclasses import dataclass

from maa.context import Context

from purchase import buy_daily
from screen import hit, read_int, screenshot
from task import Task, task


@dataclass
class Realm:
    key: str        # in its settings: buy_<key>, use_<key>
    name: str       # for the log
    title: str      # OCR pattern for its name on the list tile and the realm's tab
    tile_roi: list  # where the title is on the list
    badge_roi: list  # the tile's tool-count badge on the list


REALMS = [
    Realm("ironvein", "Ironvein Pit", r"^Ironvein\s?Pit$", [20, 440, 300, 60], [318, 168, 40, 34]),
    Realm("gilded", "Gilded Depths", r"^Gilded\s?Depths$", [370, 440, 300, 60], [670, 168, 40, 34]),
    Realm("dread", "Dread Hollow", r"^Dread\s?Hollow$", [20, 950, 280, 60], [318, 672, 40, 34]),
    Realm("dustfall", "Dustfall Dune", r"^Dustfall\s?Dune$", [370, 945, 300, 60], [670, 672, 40, 34]),
]


def open_realm(t: Task, realm: Realm):
    t.run("MaterialRealms_OpenRealm", {
        "MaterialRealms_OpenRealm": {"expected": realm.title, "roi": realm.tile_roi},
        "MaterialRealms_OnRealm": {"all_of": [
            "Screen_MaterialTitle",
            {"recognition": "OCR", "expected": realm.title, "roi": [150, 1185, 210, 50]}]}},
        fail=f"could not open {realm.name}")


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


def use_tools(t: Task, name: str, wanted):
    """On a realm's page: use `wanted` tools ("ALL" or a number)."""
    held = t.need(read_int(t.c, "MaterialRealms_ToolCount"), f"{name}: could not read the tools held")
    use_all = str(wanted).upper() == "ALL"
    goal = 0 if use_all else max(0, held - int(wanted))  # tools left when done
    if held <= goal:
        t.log(f"{name}: {held} tool(s), nothing to use")
        return
    t.log(f"{name}: {held} tool(s), using {'all' if use_all else held - goal}")

    # ALL: Quick on (faster); a number: Quick off (exactly 1 tool per tap).
    if not set_quick(t.c, use_all):
        t.fail(f"{name}: could not turn Quick {'on' if use_all else 'off'}")

    stalls = 0
    while held > goal:
        t.check()
        t.run("MaterialRealms_UseTool")
        now = read_int(t.c, "MaterialRealms_ToolCount")
        if now is None or now >= held:
            stalls += 1
            if stalls >= 5:  # taps aren't using tools (e.g. a popup is in the way)
                t.fail(f"{name}: tools aren't going down, stopping")
            time.sleep(1)
            continue
        stalls = 0
        if not use_all and now < goal:
            t.log(f"{name}: used more than asked ({held} -> {now})")
        held = now
    t.log(f"{name}: done, {held} tool(s) left")


@task("MaterialRealms", "Material Realms")
def material_realms(t: Task):
    """Visit each realm once: buy, then use. Realms with nothing to buy or
    use aren't opened."""
    # Tools held per realm, from the badges on the list (no badge = 0).
    image = screenshot(t.c)
    held = {}
    for realm in REALMS:
        held[realm.key] = read_int(t.c, "MaterialRealms_ListCount", image,
                                   {"MaterialRealms_ListCount": {"roi": realm.badge_roi}}) or 0
    t.log("tools: " + ", ".join(f"{r.name} {held[r.key]}" for r in REALMS))

    for realm in REALMS:
        sets = t.settings[f"buy_{realm.key}"]
        amount = t.settings[f"use_{realm.key}"]
        use_some = str(amount).upper() == "ALL" or int(amount) > 0
        if sets <= 0 and (not use_some or held[realm.key] == 0):
            continue  # nothing to buy, and nothing to use (or no tools)
        open_realm(t, realm)
        buy_daily(t, sets, "MaterialRealms_Buy_Open", "Screen_MaterialTitle", item=realm.name)
        if use_some:
            use_tools(t, realm.name, amount)
        t.run("MaterialRealms_RealmBack", fail=f"could not get back to the list from {realm.name}")
    t.log("done")
