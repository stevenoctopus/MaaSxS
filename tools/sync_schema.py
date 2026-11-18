"""Download MaaFramework's JSON schemas into deps/tools, for the version the
agent pins (maafw==X.Y.Z in agent/requirements.txt). Run it after bumping that
version. The boilerplate syncs from MaaFramework's main branch instead, which
can describe fields the pinned version doesn't have yet.

    python tools/sync_schema.py
"""
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["interface", "interface_config", "interface_import", "pipeline"]


def pinned_version() -> str:
    text = (ROOT / "agent" / "requirements.txt").read_text(encoding="utf-8")
    m = re.search(r"^maafw==(\S+)", text, re.M)
    if not m:
        sys.exit("agent/requirements.txt doesn't pin maafw==X.Y.Z")
    return m.group(1)


def main():
    tag = "v" + pinned_version()
    for name in FILES:
        url = f"https://raw.githubusercontent.com/MaaXYZ/MaaFramework/{tag}/tools/{name}.schema.json"
        target = ROOT / "deps" / "tools" / f"{name}.schema.json"
        data = urllib.request.urlopen(url, timeout=30).read()
        changed = not target.exists() or target.read_bytes().replace(b"\r\n", b"\n") != data.replace(b"\r\n", b"\n")
        if changed:
            target.write_bytes(data)
        print(f"{name}.schema.json: {'updated' if changed else 'up to date'} ({tag})")


if __name__ == "__main__":
    main()
