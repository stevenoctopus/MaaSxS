"""interface.json and the pipeline agree: everything the GUI's tasks and
options point at exists, and every Custom action is registered by the agent.

    python -m unittest discover tests
"""
import re
import sys
import unittest
from pathlib import Path

import jsonc

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from still import Still, agent_actions  # noqa: E402

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

interface = None
resource = None


def setUpModule():
    global interface, resource
    with open(ROOT / "assets" / "interface.json", encoding="utf-8") as f:
        interface = jsonc.load(f)
    resource = Still().resource


def overrides():
    """(where, node, override) for every pipeline_override in interface.json."""
    for name, opt in interface["option"].items():
        for node, ov in (opt.get("pipeline_override") or {}).items():
            yield name, node, ov
        for case in opt.get("cases", []):
            for node, ov in (case.get("pipeline_override") or {}).items():
                yield f"{name} / {case['name']}", node, ov


def placeholders(value):
    if isinstance(value, str):
        yield from PLACEHOLDER_RE.findall(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from placeholders(v)
    elif isinstance(value, list):
        for v in value:
            yield from placeholders(v)


class Interface(unittest.TestCase):
    def test_task_entries_exist(self):
        nodes = set(resource.node_list)
        for task in interface["task"]:
            self.assertIn(task["entry"], nodes, f"task {task['name']}")

    def test_options_exist(self):
        options = interface["option"]
        lists = [(t["name"], t.get("option", [])) for t in interface["task"]]
        lists += [(f"{n} / {c['name']}", c.get("option", []))
                  for n, o in options.items() for c in o.get("cases", [])]
        for where, names in lists:
            for name in names:
                self.assertIn(name, options, where)

    def test_overridden_nodes_exist(self):
        nodes = set(resource.node_list)
        for where, node, ov in overrides():
            self.assertIn(node, nodes, where)
            for target in ov.get("next", []) if isinstance(ov, dict) else []:
                self.assertIn(target, nodes, f"{where}: next of {node}")

    def test_placeholders_are_inputs(self):
        for name, opt in interface["option"].items():
            inputs = {i["name"] for i in opt.get("inputs", [])}
            for node, ov in (opt.get("pipeline_override") or {}).items():
                for p in placeholders(ov):
                    self.assertIn(p, inputs, f"{name}: {{{p}}} in {node}")

    def test_input_defaults_pass_verify(self):
        for name, opt in interface["option"].items():
            for i in opt.get("inputs", []):
                if "verify" in i:
                    self.assertRegex(i["default"], i["verify"], f"{name}: {i['name']}")

    def test_custom_actions_registered(self):
        registered = agent_actions()
        for node in resource.node_list:
            action = (resource.get_node_data(node) or {}).get("action", {})
            if action.get("type") == "Custom":
                name = action["param"]["custom_action"]
                self.assertIn(name, registered, f"{node} uses {name}; is it imported in agent/main.py?")


if __name__ == "__main__":
    unittest.main()
