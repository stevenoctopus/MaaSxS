## Project

MaaSxS automates the game Sword x Staff with MaaFramework (pipeline JSON + a Python agent) and the MFAAvalonia GUI.

- Code map and dev tools: README.md, "Development".
- Adding or changing a task, or cleaning up: the `add-task` skill.
- Terms: GLOSSARY.md. Decisions: docs/adr/.
- Tests: `python -m unittest discover tests` (no emulator). Live checks: `tools/run.py` with `tools/overrides/no_spend.json`.
- The emulator is the user's game: use it only when they aren't playing.
- Rebuild the GUI (`cd tools; python install.py v0.1.3 win x86_64`) after changing `assets/` or `agent/`, with the GUI closed: ask the user to close it.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for stevenoctopus/MaaSxS (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
