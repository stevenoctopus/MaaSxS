"""Affection mode: run Daily Dungeons until this week's affection cap.

Flow:
  1. Affection_Check (pipeline): claim, read "Earned This Week: N/CAP", return
     to the Daily Dungeon list.
  2. runs = ceil((CAP - N) / per_run)
  3. Run DailyDungeon_Run that many times.
  4. Check once more; if still short (e.g. a run gave nothing), top up with
     the extra runs needed. Then stop.
"""
import json
import math
import re

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

TOTAL_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def log(msg):
    print(f"[Affection] {msg}", flush=True)


def check_affection(context: Context):
    """Run the Affection_Check pipeline; return (current, cap) or None."""
    detail = context.run_task("Affection_Check")
    if detail is None or not detail.status.succeeded:
        log("affection check failed")
        return None
    for node in detail.nodes:
        if node.name == "Affection_Read" and node.recognition and node.recognition.hit:
            m = TOTAL_RE.search(node.recognition.best_result.text)
            if m:
                return int(m.group(1)), int(m.group(2))
    log("could not read the affection total")
    return None


def run_dungeons(context: Context, count: int) -> int:
    """Run DailyDungeon_Run `count` times; returns how many succeeded."""
    done = 0
    for i in range(count):
        if context.tasker.stopping:
            log("stop requested")
            break
        log(f"run {i + 1}/{count}")
        detail = context.run_task("DailyDungeon_Run")
        if detail is None or not detail.status.succeeded:
            log(f"run {i + 1} failed, stopping")
            break
        done += 1
    return done


@AgentServer.custom_action("AffectionFarm")
class AffectionFarm(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        per_run = int(param.get("per_run", 7))

        for attempt in ("initial", "recheck"):
            total = check_affection(context)
            if total is None:
                return False
            current, cap = total
            runs = math.ceil(max(0, cap - current) / per_run)
            log(f"{attempt}: {current}/{cap}, {runs} run(s) needed")
            if runs == 0:
                log("weekly cap reached")
                return True
            if run_dungeons(context, runs) < runs:
                return False
        log("done (after one recheck)")
        return True
