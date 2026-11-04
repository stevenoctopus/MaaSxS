---
name: add-task
description: Add or change a MaaSxS task (a GUI task that automates one part of Sword x Staff), or clean up after one. Use when asked to automate a new game feature, add an option to a task, or tidy tasks up.
---

A task is a pipeline entry plus, when it loops or reads numbers, one Python custom action. Model a new task on the closest existing one: `conquest.json` + `agent/conquest.py` is the smallest; `arena` adds buying; `material_realms` and `vendor_booth` show settings nodes. Terms are in `GLOSSARY.md`; decisions in `docs/adr/`.

## Steps

1. **Map the screens with the user.** Ask how to reach the feature from Home and what "done" looks like. Capture each screen with `python tools/still.py capture <task>_<screen>` and read text and boxes with `python tools/ocr_dump.py <png>`. The emulator is free to use when the user isn't playing; ask first if unsure. Done when every screen on the route and in one run is saved in `tests/screens/`.

2. **Screen checks** in `assets/resource/pipeline/screens.json`: one `Screen_<Name>` per screen the task must recognise, defined once and used by name (`"recognition": "And", "all_of": ["Screen_X"]`). Add the task's pages to `Common_TabBar_BackOut` in `common.json` when Android back is safe there; otherwise give the screen its own `Common_TabBar_*` step in all four recovery lists.

3. **Pipeline** in `assets/resource/pipeline/<task>.json`, the same shape as `conquest.json`:
   - `<Task>`: entry, `next: ["<Task>_OnPage", "[JumpBack]<Task>_ToPage"]`, `on_error: ["Common_Retry"]`.
   - `<Task>_OnPage` → `<Task>_Farm` (the Custom action, its options in `custom_action_param`), both with `on_error: ["Common_Retry"]`.
   - `<Task>_ToPage`: a route from any screen, nearest screen first, ending in `[JumpBack]Common_ToJournal` (Journal features) or `[JumpBack]Common_ToTabBar`.
   - `<Task>_Run`: one run, from the task's page back to it.
   - OCR nodes the agent reads (counts, "N/M"), with tight rois.
   - `focus` messages on the steps worth seeing in the GUI log.
   Comment each section with the path in the game. The game font drops spaces, so OCR patterns use `\s?` between words.

4. **Agent module** `agent/<task>.py`, imported in `agent/main.py`:
   - Settings: `task_settings(argv)`; options on a settings node: `settings_node(context, node)`.
   - Reads: `screen.py` (`hit`, `read_int`, `read_fraction`, `screenshot`).
   - Runs: `run_times(context, name, entry, n)` or `run_once` in a loop.
   - Buying a daily-limited item: `purchase.buy_daily` (a daily total; the Purchase popup).
   - Log with `gui.say`. Something only the user can fix (not enough Dawnium or gold, a safety stop) → `common.give_up`, which stops the whole run. Any other failure returns False, and the retry from Home runs once.

5. **GUI options** in `assets/interface.json`: add the task (`name`, `label`, `entry`, `option`) and its options. Defaults are the safe choice (buy nothing, spend nothing). Two options can't both set one node's `custom_action_param`: give the second its own settings node. Describe buy options as a daily total, and say what each option spends.

6. **Tests** in `tests/test_screens.py`: one test per new reading on the saved screens (each count, badge, page check). `python -m unittest discover tests` must pass; it also checks interface.json against the pipeline, that every Custom action is registered, and that recovery knows every saved screen.

7. **Live check** with `python tools/run.py <Task> --opt "Option=Case" --override tools/overrides/no_spend.json`: Purchase presses Cancel, battles do nothing. Add the task's own run/buy nodes to a copy of that file if it spends something new. Done when the agent log lines show the route, the reads and the run loop working. Spend only with the user's OK.

8. **Finish**: README task table row and any new tool; new terms in `GLOSSARY.md`; ask the user to close the GUI, then `cd tools; python install.py v0.1.3 win x86_64`; commit and push.

These steps are defaults: where a feature doesn't fit them, follow the game and say why in the pipeline comments.

## Gotchas

- Solo battle setup already shows "Round 0/50", so its screen check must come before `Screen_Battle` wherever both are in one `next`.
- Read `tools/run.py` output to the end (filter with `Select-String`); cutting it off early (`Select-Object -First`) kills the run mid-task.
- Mapping screens costs nothing, but some taps spend a daily attempt (Match, Challenge, Purchase): take those only with the user's OK.

## Cleanup

For "clean up" or "tidy" requests, also check:

- Copies of a helper already in `screen.py`, `common.py`, `purchase.py` or `track.py`: use the shared one.
- Steps copied across tasks (a tab tap, a tile): a shared `Common_*` routine, like `Common_ToJournal`.
- Pipeline nodes nothing references (`next`, `on_error`, `all_of`/`any_of`, interface.json, agent code; agent code may build names, e.g. `f"{popup}_Count"`).
- Tests, rebuild, commit as in step 8.
