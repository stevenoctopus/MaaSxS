"""The Purchase popup: buying a daily-limited item (Arena tickets, Daily
Dungeon reward attempts, Material Realms tool sets).

The popup shows a Qty (starts at 1) with a "+", a "Daily Purchase Limit:
U/L" (bought today / limit), and Cancel / Purchase. Buy settings are a
daily total: purchases already made today count.

Its nodes are named <popup>_Limit, _Count, _More, _Purchase and _Cancel.
Arena and Material Realms share one set (Common_Purchase_*); Daily Dungeon
has its own (DailyDungeon_Buy_*).
"""
from screen import read_fraction, read_int
from task import Task


def buy_daily(t: Task, wanted: int, open_node: str, back_node: str,
              popup: str = "Common_Purchase", item: str = "", refused: str = None) -> int:
    """Buy so that `wanted` have been bought today, within the daily limit.

    open_node  taps the "+" that opens the popup
    back_node  recognises the task's screen once the popup has closed
    item       what's bought, to start log lines with (e.g. a realm's name)
    refused    a node in open_node's next that recognises the game refusing
               instead of opening the popup (a toast): nothing to buy

    Returns how many were bought (0: nothing to buy; the popup isn't opened
    when wanted is 0). Anything else ends the task: not enough Dawnium is a
    Safety stop, the rest are failures (all logged).
    """
    if wanted <= 0:
        return 0
    prefix = f"{item}: " if item else ""

    def close(node):  # Purchase or Cancel, then check we're back
        return t.run(node) and t.run(back_node)

    def cancel_and_fail(why):
        close(f"{popup}_Cancel")
        t.fail(prefix + why)

    opened = t.run(open_node, fail=prefix + "the purchase popup didn't open")
    if refused and any(n.name == refused for n in opened.nodes or []):
        t.log(f"{prefix}the game allows no more purchases today, nothing to buy")
        return 0
    limit = read_fraction(t.c, f"{popup}_Limit")
    if limit is None:
        cancel_and_fail("could not read the purchase limit; not buying")
    bought, cap = limit
    count = max(0, min(wanted, cap) - bought)
    if count == 0:
        t.log(f"{prefix}{bought}/{cap} already bought today, nothing to buy")
        if not close(f"{popup}_Cancel"):
            t.fail(prefix + "could not close the purchase popup")
        return 0
    if count > 1:  # Qty starts at 1
        t.run(f"{popup}_More", {f"{popup}_More": {"repeat": count - 1}})
    shown = read_int(t.c, f"{popup}_Count")
    if shown is not None and shown < count:
        # The game caps the Qty at what you can afford (and we never ask
        # past today's limit), so a Qty stuck below ours is short Dawnium.
        close(f"{popup}_Cancel")
        t.give_up(f"{prefix}not enough Dawnium: set to have {wanted} bought today, "
                  f"{bought} bought, the popup allows only {shown} more")
    if shown != count:
        cancel_and_fail(f"the purchase popup shows {shown}, expected {count}; not buying")
    t.log(f"{prefix}buying {count} ({bought}/{cap} bought today)")
    if not close(f"{popup}_Purchase"):
        t.fail(prefix + "the purchase didn't go through")
    return count
