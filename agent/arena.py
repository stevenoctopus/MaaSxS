"""Arena: buy tickets so `buy` have been bought today (a daily total, see
agent/purchase.py), then challenge the rightmost opponent `tickets` times,
limited by the tickets held ("N/20" at the top of the Arena page)."""
import time

from purchase import buy_daily
from screen import read_fraction
from task import Task, task


@task("ArenaFarm", "Arena")
def arena(t: Task):
    if buy_daily(t, t.settings["buy"], "Arena_Buy_Open", "Arena_BackOnPage"):
        time.sleep(1.5)  # the ticket count updates a moment after buying

    held = t.need(read_fraction(t.c, "Arena_Tickets"), "could not read the arena tickets")
    runs = min(t.settings["tickets"], held[0])
    t.log(f"{held[0]} ticket(s), using {runs}")
    t.run_times("Arena_Run", runs, noun="challenge")
    t.log("done")
