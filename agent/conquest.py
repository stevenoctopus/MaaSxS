"""Conquest: run up to `runs` times, limited by the daily attempts left
("Daily Challenge Attempts: N/2" on the Conquest page)."""
from screen import read_fraction
from task import Task, task


@task("ConquestFarm", "Conquest")
def conquest(t: Task):
    left = t.need(read_fraction(t.c, "Conquest_Attempts"), "could not read the attempts left")[0]
    runs = min(t.settings["runs"], left)
    t.log(f"{left} attempt(s) left, running {runs}")
    t.run_times("Conquest_Run", runs)
    t.log("done")
