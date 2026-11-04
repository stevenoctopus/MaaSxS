"""Run agent code against saved screenshots instead of the emulator.

    python tools/still.py capture <name>   save the emulator's screen to tests/screens/<name>.png

In tests:

    still = Still()                        # loads assets/resource once
    still.run("vendor_vault.png", lambda context: ...)

run() shows the screenshot as the "device" screen and calls the function
with a real MaaFramework Context, so agent functions (screenshot,
run_recognition, overrides) work as they do in the GUI. Taps and swipes
do nothing.
"""
import sys
import types
from pathlib import Path

import cv2
from maa.controller import CustomController
from maa.custom_action import CustomAction
from maa.resource import Resource
from maa.tasker import Tasker

ROOT = Path(__file__).resolve().parent.parent
SCREENS = ROOT / "tests" / "screens"
sys.path.insert(0, str(ROOT / "agent"))


# Importing maa.agent reloads MaaFramework as an agent server, which breaks the
# Tasker used here. The agent modules only need its decorators, so stand in an
# AgentServer that only records the names, before they're imported.
class _AgentServer:
    actions = set()

    @staticmethod
    def custom_action(name):
        _AgentServer.actions.add(name)
        return lambda cls: cls

    custom_recognition = custom_action


_stub = types.ModuleType("maa.agent.agent_server")
_stub.AgentServer = _AgentServer
sys.modules.setdefault("maa.agent", types.ModuleType("maa.agent"))
sys.modules["maa.agent.agent_server"] = _stub


def agent_actions() -> set:
    """Names of the custom actions agent/main.py registers."""
    import main  # noqa: F401  (imports every task module, like the GUI's agent)
    return set(_AgentServer.actions)


class StillController(CustomController):
    """A device that always shows one image; inputs do nothing."""

    def __init__(self):
        super().__init__()
        self.image = None

    def connect(self): return True
    def request_uuid(self): return "still"
    def screencap(self): return self.image
    def click(self, x, y): return True
    def swipe(self, x1, y1, x2, y2, duration): return True
    def touch_down(self, contact, x, y, pressure): return True
    def touch_move(self, contact, x, y, pressure): return True
    def touch_up(self, contact): return True
    def click_key(self, keycode): return True
    def input_text(self, text): return True


class _Probe(CustomAction):
    def __init__(self):
        super().__init__()
        self.fn = None
        self.result = None
        self.error = None

    def run(self, context, argv):
        try:
            self.result = self.fn(context)
        except Exception as e:  # re-raised in Still.run
            self.error = e
        return True


class Still:
    # A node of our own for _Probe (the task's overrides would leak into any
    # pipeline node we borrowed).
    HOOK = "StillProbe"

    def __init__(self):
        self.resource = Resource()
        if not self.resource.post_bundle(str(ROOT / "assets" / "resource")).wait().succeeded:
            raise RuntimeError("could not load assets/resource")
        self.probe = _Probe()
        self.resource.register_custom_action("StillProbe", self.probe)
        if not self.resource.override_pipeline({self.HOOK: {
                "recognition": "DirectHit", "action": "Custom", "custom_action": "StillProbe",
                "pre_delay": 0, "post_delay": 0}}):
            raise RuntimeError("could not add the StillProbe node")
        self.controller = StillController()
        self.controller.post_connection().wait()
        self.tasker = Tasker()
        self.tasker.bind(self.resource, self.controller)
        if not self.tasker.inited:
            raise RuntimeError("tasker failed to start")

    def run(self, screen: str, fn):
        """fn(context) with tests/screens/<screen> on the screen; returns its result."""
        image = cv2.imread(str(SCREENS / screen))
        if image is None:
            raise FileNotFoundError(SCREENS / screen)
        self.controller.image = image
        self.probe.fn, self.probe.result, self.probe.error = fn, None, None
        self.tasker.post_task(self.HOOK).wait()
        if self.probe.error:
            raise self.probe.error
        return self.probe.result


def capture(name: str):
    from screenshot import connect

    image = connect().post_screencap().wait().get()
    SCREENS.mkdir(parents=True, exist_ok=True)
    path = SCREENS / f"{name}.png"
    cv2.imwrite(str(path), image)
    print(f"Saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "capture":
        sys.exit(__doc__)
    sys.path.insert(0, str(ROOT / "tools"))
    capture(sys.argv[2])
