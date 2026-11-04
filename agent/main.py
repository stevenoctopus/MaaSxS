import sys
from pathlib import Path

# The embedded Python in Windows releases does not add the script's folder
# to sys.path, so do it here for `import affection`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

import affection  # noqa: F401  (registers its custom actions on import)
import crucible  # noqa: F401
import conquest  # noqa: F401
import daily_dungeon  # noqa: F401
import common  # noqa: F401


def main():
    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)

    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
