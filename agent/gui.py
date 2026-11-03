"""Messages from the agent to the GUI log.

The GUI only shows pipeline `focus` messages, not the agent's stdout, so
say() runs the Common_Log node with the text as its focus. It also prints,
for the CLI runner and the GUI's log file.
"""
from maa.context import Context


def say(context: Context, prefix: str, msg: str):
    text = f"[{prefix}] {msg}"
    print(text, flush=True)
    context.run_task("Common_Log", pipeline_override={
        "Common_Log": {"focus": {"Node.Action.Starting": text}}
    })
