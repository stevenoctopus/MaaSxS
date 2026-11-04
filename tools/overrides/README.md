# Overrides for live checks

`python tools/run.py <Task> --override tools/overrides/no_spend.json`

`no_spend.json` runs a task on the emulator without spending anything:
the Purchase popups press Cancel instead of Purchase, Vendor Booth buys and
refreshes, battles and tool uses do nothing. Everything else is real: the
route, the screen reads, the popups' limits and counts, the run loop's log
lines. Buying flows are checked this way, not offline
(`docs/adr/0001-buying-flows-are-tested-live.md`).

What to expect:

- Runs log `run 1/2`, `run 2/2` and succeed without a battle.
- Vendor Booth stops at its first buy with "could not buy ..." (the item
  never turns Sold Out); its reads before that are real.
- Material Realms stops with "tools aren't going down" when it's set to use
  tools; set its use options to 0 to check the list and the buying.

A new task that spends something new adds its run/buy nodes here.
