# Glossary

Terms used in MaaSxS's code, pipeline comments and option descriptions.

## The game

**Dawnium**: the premium currency. Everything bought with it is opt-in and
counted as a daily total. Gold buys Vendor Booth General items.

**Journal**: the tab bar's second tab (scroll icon), the hub for Daily
Dungeon, Daily Events (Crucible, Split Mirage), Competition (Arena) and
Material Realms. Reached with `Common_ToJournal`.

**Reward track**: the scrolling row of rewards on the Crucible and Split
Mirage menus, each unlocked at a score. **Today's best** is the day's top
score shown on the menu. A **marked reward** is a gift box (Crucible) or gem
(Split Mirage). Claiming one reward claims every reachable one, so a claimed
reward means everything left of it is claimed. Handled by `agent/track.py`;
modes: **Once** (one run, or none if today's best already shows a score),
**Marked** (run until the last marked reward), **All** (run until the end).

**Purchase popup**: the game's popup for buying a daily-limited item with
Dawnium: a Qty field (starts at 1) with a "+", a "Daily Purchase Limit: U/L"
line (bought today / limit), and Cancel / Purchase. Used for Arena tickets,
Daily Dungeon reward attempts and Material Realms tool sets. Handled by
`agent/purchase.py`. _Not_: the Vendor Booth, where tapping a price buys
instantly with no popup.

**Daily total**: how every buy setting counts. The number set is how many
should have been bought *today*, so purchases already made today (by hand or
by an earlier run) count: the bot buys `max(0, min(wanted, limit) - bought
today)`. Running a task twice never buys twice.

**Small chat**: the two-line chat box above the bottom of Home and the
world map, all channels together. Only its text and links react to taps.
_Not_: the full chat (opened from it, one tab per channel).

**Grand mine**: a mine on the world map that several players can claim, for
free, with **claim bars** under it (yellow = claims left). A claim is one
player mining it once; the reward shows as a toast ("Raw Ore x4.77K"). A
**grand mine link** is a green `<Grand Iron Mine>` in the small chat (Rolla's are
`<Grand Gold Mine>`); tapping
it travels there ("Travel to <region> now?", not shown when already in that
region) and shows a **flashing icon** that snaps the camera to the mine. Grey
links are mined out. _Not_: ore rocks (the ⚡5 ones), which spend energy as
soon as they're tapped.

**Resource Hunt**: Journal > Map Exploration > Resource Hunt: check a
resource (Rolla, Iron, Sand, Essence), Go >>, and it takes you to that
resource's current zone. Grand Mines waits there: its **AFK spot**.

## The bot

**Task**: one entry in the GUI's task list (`interface.json` `task`), with
its options. Its pipeline entry node has the task's name (`Arena`); its
custom action does the loop (`ArenaFarm` in `agent/arena.py`).
`.claude/skills/add-task` is the recipe for a new one.

**Screen check**: a `Screen_*` node in `screens.json` that recognises one
screen. Defined once, used by name everywhere
(`"recognition": "And", "all_of": ["Screen_X"]`).

**Route**: a task's `<Task>_ToPage` / `_ToMenu` / `_ToList` node, which gets
to the task's page from any screen: its `next` lists the screens on the way,
nearest first, then falls back to `[JumpBack]Common_ToJournal` or
`[JumpBack]Common_ToTabBar`.

**Recovery**: `Common_ToTabBar` in `common.json`, getting back to the tab
bar from anywhere (popups, results, a crash). Known screens get a step;
pages in `Common_TabBar_BackOut` get Android back; anything else gets back
twice, then the game is started again. `tests/test_recovery.py` checks it
knows every saved screen.

**Retry from Home**: a failed top-level step goes to `Common_Retry`, which
goes Home and starts the task over once (`RetryFromHome` in
`agent/common.py`). For unexpected failures.

**Safety stop**: `common.give_up()`: logs "Stopped: <reason>" and stops the
whole run, with no retry, for what only the user can fix (not enough Dawnium
or gold, or running more won't help). Later tasks don't run either
(`ContinueRunningWhenError` is off).

**Settings node**: a pipeline node that only holds settings for a task, in
its `custom_action_param`, e.g. `VendorBooth_Refreshes`,
`VendorBooth_Vault_*`, `MaterialRealms_Buy`. Needed because two GUI options
can't both set the same node's param. Read with `common.settings_node()`;
a task's own node's settings with `common.task_settings()`.

**Saved screen**: a real screenshot in `tests/screens/`, captured with
`python tools/still.py capture <name>`. The tests show it to the agent's own
code through the **Still** adapter (`tools/still.py`), a stand-in device
that always shows one image and ignores taps.

**No-spend check**: a live run with `--override
tools/overrides/no_spend.json`, where buys press Cancel and battles do
nothing (see `tools/overrides/README.md`).
