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

from task import number, param_of, settings_nodes  # noqa: E402

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
SETTING_RE = re.compile(r"""settings\[["'](\w+)["']\]""")

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


def task_nodes():
    """custom action -> the nodes that run it (a task's own node and its
    Settings nodes), for actions with settings."""
    actions = {a for n in resource.node_list
               if (a := (resource.get_node_data(n) or {}).get("action", {}).get("param", {}).get("custom_action"))}
    found = {a: settings_nodes(resource.get_node_data, resource.node_list, a) for a in actions}
    return {a: nodes for a, nodes in found.items()
            if any(param_of(resource.get_node_data(n)) for n in nodes)}


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

    # -- settings (agent/task.py: t.settings merges a task's nodes' params)

    def test_settings_keys_are_unique_per_task(self):
        for action, nodes in task_nodes().items():
            seen = {}
            for node in nodes:
                for key in param_of(resource.get_node_data(node)):
                    self.assertNotIn(key, seen, f"{action}: {key} is on both {seen.get(key)} and {node}")
                    seen[key] = node

    def test_options_set_known_settings(self):
        # Each setting an option writes has a default on that node (a typo
        # would otherwise add a setting nothing reads).
        for where, node, ov in overrides():
            if isinstance(ov, dict) and "custom_action_param" in ov:
                defaults = param_of(resource.get_node_data(node))
                for key in ov["custom_action_param"]:
                    self.assertIn(key, defaults, f"{where}: {node} has no default for {key}")

    def test_gui_defaults_match_pipeline_defaults(self):
        # What the GUI starts with is what a run without the GUI gets
        # (tools/run.py), and what the agent's code was written against.
        for name, opt in interface["option"].items():
            if "inputs" in opt:
                values = {i["name"]: i["default"] for i in opt["inputs"]}
                for node, ov in (opt.get("pipeline_override") or {}).items():
                    for key, value in (ov.get("custom_action_param") or {}).items():
                        m = PLACEHOLDER_RE.fullmatch(str(value))
                        if m:
                            value = values[m.group(1)]
                        default = param_of(resource.get_node_data(node))[key]
                        self.assertEqual(number(value), default, f"{name}: {node}.{key}")
            elif "default_case" in opt:
                case = next(c for c in opt["cases"] if c["name"] == opt["default_case"])
                for node, ov in (case.get("pipeline_override") or {}).items():
                    for key, value in (ov.get("custom_action_param") or {}).items():
                        default = param_of(resource.get_node_data(node))[key]
                        self.assertEqual(value, default, f"{name} ({case['name']}): {node}.{key}")

    def test_settings_the_agent_reads_exist(self):
        keys = {k for nodes in task_nodes().values() for n in nodes for k in param_of(resource.get_node_data(n))}
        for path in sorted((ROOT / "agent").glob("*.py")):
            for key in SETTING_RE.findall(path.read_text(encoding="utf-8")):
                self.assertIn(key, keys, f"{path.name} reads t.settings[{key!r}]")

    def test_custom_actions_registered(self):
        registered = agent_actions()
        for node in set(resource.node_list) - {Still.HOOK}:
            action = (resource.get_node_data(node) or {}).get("action", {})
            if action.get("type") == "Custom":
                name = action["param"]["custom_action"]
                self.assertIn(name, registered, f"{node} uses {name}; is it imported in agent/main.py?")


if __name__ == "__main__":
    unittest.main()
