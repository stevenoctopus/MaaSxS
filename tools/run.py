"""Run a task from interface.json against the emulator, without the GUI.

    python tools/run.py DailyDungeon
    python tools/run.py DailyDungeon --opt "Dungeon=Court of Purification" --opt Difficulty=Nightmare
    python tools/run.py Affection_Check     # any pipeline node works as an entry

Options not given use their default_case, like the GUI does. The agent
(agent/main.py) is started as a separate process through AgentClient, the
same way MFAAvalonia does it, so custom actions run exactly as in the GUI.
--override '{"Node": {...}}' (or a .json file) patches nodes for one run.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import jsonc
from maa.agent_client import AgentClient
from maa.resource import Resource
from maa.tasker import Tasker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screenshot import ROOT, connect  # noqa: E402

ASSETS = ROOT / "assets"


def merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], v)
        else:
            dst[k] = v


def build_override(interface, task, chosen):
    """Merge the pipeline_override of the task and each selected option case."""
    override = {}
    merge(override, task.get("pipeline_override", {}))
    for key in task.get("option", []):
        opt = interface["option"][key]
        name = chosen.get(key, opt.get("default_case"))
        case = next((c for c in opt["cases"] if c["name"] == name), None)
        if case is None:
            sys.exit(f"Option {key}: no case named {name!r}. "
                     f"Choices: {[c['name'] for c in opt['cases']]}")
        print(f"{key} = {name}")
        merge(override, case.get("pipeline_override", {}))
    return override


def start_agent(resource, interface):
    """Start the agent process and bind it to the resource. Returns (client, proc)."""
    agent = interface.get("agent")
    if not agent:
        return None, None
    client = AgentClient()
    client.bind(resource)
    cmd = [sys.executable if agent["child_exec"] == "python" else agent["child_exec"],
           *agent.get("child_args", []), client.identifier]
    # cwd mirrors the install layout: ./agent/main.py relative to the project root
    proc = subprocess.Popen(cmd, cwd=ROOT)
    if not client.connect():
        proc.kill()
        sys.exit("Agent failed to connect.")
    return client, proc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--opt", action="append", default=[], help="Option=Case")
    ap.add_argument("--override", help="extra pipeline override as JSON or a .json file")
    args = ap.parse_args()

    interface = jsonc.loads((ASSETS / "interface.json").read_text(encoding="utf-8"))
    task = next((t for t in interface["task"] if t["name"] == args.task), None)
    if task is None:
        # Not a GUI task: run it as a pipeline node (internal tasks like Affection_Check).
        print(f"{args.task!r} is not in interface.json; running it as a pipeline entry")
        task = {"name": args.task, "entry": args.task}
    chosen = dict(o.split("=", 1) for o in args.opt)
    override = build_override(interface, task, chosen)
    if args.override:
        src = Path(args.override)
        text = src.read_text(encoding="utf-8") if src.is_file() else args.override
        merge(override, json.loads(text))

    resource = Resource()
    if not resource.post_bundle(str(ASSETS / "resource")).wait().succeeded:
        sys.exit("Failed to load resources (check the pipeline JSON).")
    ctrl = connect()
    client, proc = start_agent(resource, interface)
    try:
        tasker = Tasker()
        tasker.bind(resource, ctrl)
        if not tasker.inited:
            sys.exit("Tasker failed to initialise.")

        detail = tasker.post_task(task["entry"], override).wait().get()
        for node in detail.nodes:
            reco = node.recognition
            box = reco.box if reco else None
            text = getattr(getattr(reco, "best_result", None), "text", None)
            print(f"  {node.name}: hit={bool(reco and reco.hit)} box={box} "
                  f"action_ok={node.completed}" + (f" text={text!r}" if text else ""))
        ok = detail.status.succeeded
        print("Task", "succeeded" if ok else "FAILED")
    finally:
        if client:
            client.disconnect()
            proc.wait(timeout=10)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
