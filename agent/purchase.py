"""The Purchase popup: buying a daily-limited item (Arena tickets, Daily
Dungeon reward attempts, Material Realms tool sets).

The popup shows a Qty (starts at 1) with a "+", a "Daily Purchase Limit:
U/L" (bought today / limit), and Cancel / Purchase. Buy settings are a
daily total: purchases already made today count.

Its nodes are named <popup>_Limit, _Count, _More, _Purchase and _Cancel.
Arena and Material Realms share one set (Common_Purchase_*); Daily Dungeon
has its own (DailyDungeon_Buy_*).
"""
from maa.context import Context

from common import give_up, ok
from gui import say
from screen import read_fraction, read_int


def buy_daily(context: Context, name: str, wanted: int, open_node: str, back_node: str,
              popup: str = "Common_Purchase"):
    """Buy so that `wanted` have been bought today, within the daily limit.

    name       log prefix, e.g. "Arena"
    open_node  taps the "+" that opens the popup
    back_node  recognises the task's screen once the popup has closed

    Returns how many were bought (0: nothing to buy; the popup isn't opened
    when wanted is 0), or None if something went wrong (logged).
    """
    if wanted <= 0:
        return 0

    def log(msg):
        say(context, name, msg)

    def close(node):  # Purchase or Cancel, then check we're back
        return ok(context.run_task(node)) and ok(context.run_task(back_node))

    if not ok(context.run_task(open_node)):
        log("the purchase popup didn't open")
        return None
    limit = read_fraction(context, f"{popup}_Limit")
    if limit is None:
        log("could not read the purchase limit; not buying")
        close(f"{popup}_Cancel")
        return None
    bought, cap = limit
    count = max(0, min(wanted, cap) - bought)
    if count == 0:
        log(f"{bought}/{cap} already bought today, nothing to buy")
        return 0 if close(f"{popup}_Cancel") else None
    for _ in range(count - 1):  # Qty starts at 1
        context.run_task(f"{popup}_More")
    shown = read_int(context, f"{popup}_Count")
    if shown is not None and shown < count:
        # The game caps the Qty at what you can afford (and we never ask
        # past today's limit), so a Qty stuck below ours is short Dawnium.
        close(f"{popup}_Cancel")
        give_up(context, name, f"not enough Dawnium: set to have {wanted} bought today, "
                               f"{bought} bought, the popup allows only {shown} more")
        return None
    if shown != count:
        log(f"the purchase popup shows {shown}, expected {count}; not buying")
        close(f"{popup}_Cancel")
        return None
    log(f"buying {count} ({bought}/{cap} bought today)")
    if not close(f"{popup}_Purchase"):
        log("the purchase didn't go through")
        return None
    return count
